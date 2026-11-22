"""Driver for the paper-2 encryptor (nv_top) on the PYNQ-Z2, plus a model-backed mock (DESIGN §6.7, §8.2 N10).

The register sequence is the one verified in simulation (hardware/tb/neuro/test_nv_top.py):
    configure : shadow set (MODE, GEOM, T_US, SID, CTR0, PAD_MIN, PAD_CAP, MAX_GAP_US, 5 keys),
                CTRL = COMMIT with ENABLE = 0 (fresh start), CTRL = ENABLE
    stream    : MM2S DMA of EVT 2.0 words; S2MM transfers, one packet each (tlast ends a transfer)
    commit    : shadow set + COMMIT_AT, CTRL = ENABLE | COMMIT, CFG_CODE tells whether it was refused
    flush     : CTRL = ENABLE | FLUSH (closes the open packet and emits the FINAL packet)
    counters  : CTRL = ENABLE | SNAP, then read (64-bit pairs are consistent)

Backends
    PynqBackend : the board (needs `pynq` and overlay/neuro/nv.bit + nv.hwh from block_design_neuro.tcl);
                  checked against a fake of pynq (tests/test_neuro_board_pynq.py) until the first board run.
    MockBackend : the golden model (neuro.sender.Encryptor) behind the same register interface; used by the
                  --mock paths of nv_first_contact.py / nv_replay.py and by tests/test_neuro_board.py.

    ip = NvIP(MockBackend())                    # or NvIP(PynqBackend("overlay/neuro/nv.bit"))
    ip.configure(subkeys, sid, Config(3, 6, 1024, geom), ctr0=0)
    packets = ip.push(words) + ip.flush()
"""
import time

import numpy as np

from neuro.keys import SubKeys
from neuro.pad import PadPolicy
from neuro.sender import CFG_NONE, ConfigError, Config, Encryptor

VERSION, CTRL, STATUS, MODE, GEOM, T_US = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14
SID_LO, SID_HI, CTR0_LO, CTR0_HI, PAD_MIN, PAD_CAP, MAX_GAP = 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30
AT_LO, AT_HI, CFG_CODE = 0x34, 0x38, 0x3C
K_BASE = {"tag": 0x40, "pol": 0x50, "perm": 0x60, "dum": 0x70, "aead": 0x80}
CUR_CTR, LAST_SID, LAST_CTR = 0x90, 0x98, 0xA0
COUNTERS64 = {"PKTS": 0xA8, "WORDS_IN": 0xB0, "WORDS_OUT": 0xB8, "CYCLES": 0xC0}
COUNTERS32 = {"IN_WAIT": 0xC8, "OUT_STALL": 0xCC, "TABLE_WAIT": 0xD0, "KS_WAIT": 0xD4, "ERR_RANGE": 0xD8,
              "ERR_ORDER": 0xDC, "ERR_PRE_TH": 0xE0, "ERR_JUMP": 0xE4, "ERR_PADOVF": 0xE8, "ERR_CFG": 0xEC}
EN, SRST, FLUSH, COMMIT, SNAP = 1, 2, 4, 8, 16
VERSION_BASE = 0x4E5601            # 'N' 'V' contract n1; low byte = build {0, PAD, log2U, L}
NV_EVENTS = 6                      # link.wire message type for event packets (paper 1 uses 1..5)


def build_of(version):
    if version >> 8 != VERSION_BASE:
        return None
    b = version & 0xFF
    return {"pad": bool(b & 0x40), "U": 1 << ((b >> 4) & 3), "L": b & 0xF}


def mode_word(cfg):
    p = cfg.pad
    return (cfg.level | (cfg.ts_bits << 4) | ((p is not None) << 8) | ((p.kind if p else 0) << 9)
            | (cfg.jump_mode << 12))


def le32(key, i):
    return int.from_bytes(bytes(key)[4 * i:4 * i + 4], "little")


class MockBackend:
    """Register file + DMA emulated with neuro.sender.Encryptor (bit-exact with nv_top, test_nv_top)."""

    def __init__(self, U=2, pad=True):
        self.regs = {}
        self.version = (VERSION_BASE << 8) | (int(pad) << 6) | ({1: 0, 2: 1, 4: 2}[U] << 4) | 1
        self.enc = None
        self.enable = False
        self.code = 0
        self.snap = {}
        self.out = []
        self.cycles = 0

    # registers
    def write(self, addr, value):
        self.regs[addr] = value & 0xFFFFFFFF
        if addr != CTRL:
            return
        if value & SRST:
            self.enc, self.enable = None, False
            return
        if value & COMMIT:
            self._commit()
        self.enable = bool(value & EN)
        if value & FLUSH and self.enc is not None:
            self.out += self.enc.flush()
        if value & SNAP and self.enc is not None:
            self.snap = dict(self.enc.counters)

    def read(self, addr):
        if addr == VERSION:
            return self.version
        if addr == CFG_CODE:
            return self.code
        if addr == STATUS:
            return (0x40 if (self.enc and self.enc.halted) else 0) | (0x10 if self.enc else 0)
        for name, a in COUNTERS64.items():
            if addr in (a, a + 4):
                v = self.snap.get(name, 0)
                return (v >> 32) if addr == a + 4 else v & 0xFFFFFFFF
        for name, a in COUNTERS32.items():
            if addr == a:
                return self.snap.get(name, 0) & 0xFFFFFFFF
        return self.regs.get(addr, 0)

    def _shadow(self):
        r = self.regs.get
        m, g = r(MODE, 0), r(GEOM, 0)
        from neuro.geometry import Geometry
        W, H = g & 0x7FF, (g >> 16) & 0x7FF
        pad = None
        if m & 0x100:
            pad = PadPolicy((m >> 9) & 3, r(PAD_MIN, 0), r(PAD_CAP, 0))
        cfg = Config(m & 7, (m >> 4) & 7, r(T_US, 1024), Geometry(f"{W}x{H}", W, H), pad, r(MAX_GAP, 1_000_000),
                     (m >> 12) & 1)
        key = lambda n: b"".join(r(K_BASE[n] + 4 * i, 0).to_bytes(4, "little") for i in range(4))
        sk = SubKeys(**{n: key(n) for n in K_BASE})
        sid = r(SID_LO, 0) | (r(SID_HI, 0) << 32)
        ctr0 = r(CTR0_LO, 0) | (r(CTR0_HI, 0) << 32)
        at = r(AT_LO, 0) | (r(AT_HI, 0) << 32)
        return cfg, sk, sid, ctr0, at

    def _commit(self):
        cfg, sk, sid, ctr0, at = self._shadow()
        try:
            if self.enc is None or not self.enable:
                self.enc = Encryptor(sk, sid, cfg, ctr0)
            else:
                self.out += self.enc.commit(at, cfg=cfg, subkeys=sk, sid=sid, ctr0=ctr0)
            self.code = CFG_NONE
        except ConfigError as e:
            self.code = e.code
            if self.enc is not None:
                pass

    # DMA
    def transfer(self, words):
        if self.enc is None or not self.enable:
            raise RuntimeError("encryptor not configured and enabled")
        t0 = time.perf_counter()
        self.out += self.enc.push(np.asarray(words, dtype=np.uint32))
        self.cycles += int((time.perf_counter() - t0) * 1e8)
        out, self.out = self.out, []
        return out

    def drain(self):
        out, self.out = self.out, []
        return out


class PynqBackend:
    """The PYNQ-Z2 overlay (overlay/neuro/nv.bit + nv.hwh from block_design_neuro.tcl; cells `nv` and `dma`).

    Checked against a model-backed fake of pynq's Overlay / DMA / cacheable buffers (tests/test_neuro_board_pynq.py)
    before the first board run. Follows the paper-1 board lessons (software/system/board/pynq_driver.py):
      * cache: the input words are flushed and every received packet invalidated before it is read (the buffers
        from allocate() are cacheable; the DMA sees memory, the ARM its cache);
      * no pynq channel.wait() without a deadline (it hung the first paper-1 board run, bug #32): `idle` is
        polled and a timeout raises with the DMA status registers;
      * the receive channel is never stopped mid-transfer: one S2MM transfer stays armed until a packet (tlast)
        completes it, and the next one is armed at once, so output never backs up into the input;
      * push() returns the packets completed so far without waiting (a fixed wait per chunk would cap the replay
        rate); drain(), after FLUSH, waits until no packet completes for quiet_s.
    """

    S2MM_LENGTH, MM2S_SR, S2MM_SR = 0x58, 0x04, 0x34

    def __init__(self, bitfile, max_words=1 << 22, max_packet_bytes=1 << 20, fclk_mhz=None, timeout_s=5.0,
                 quiet_s=0.05):
        from pynq import Overlay, allocate
        from system.board.pynq_driver import built_fclk_mhz, choose_fclk
        self.ol = Overlay(str(bitfile))
        # PYNQ copies the .hwh's FCLK0 dividers, which assume Vivado's IO PLL: a 100 MHz image then runs at
        # 62.5 MHz on the PYNQ-Z2 (paper-1 bug #44). Set FCLK0 to the clock the image was built for.
        from pynq import Clocks
        target, note = choose_fclk(built_fclk_mhz(bitfile), Clocks.fclk0_mhz, fclk_mhz)
        if note:
            print(note)
        if target:
            Clocks.fclk0_mhz = target
        self.fabric_mhz = Clocks.fclk0_mhz
        self.ip = self.ol.nv
        self.dma = self.ol.dma
        self.inbuf = allocate(shape=(max_words,), dtype=np.uint32)
        self.outbuf = allocate(shape=(max_packet_bytes // 4,), dtype=np.uint32)
        self.timeout_s, self.quiet_s = timeout_s, quiet_s
        self.armed = False

    def write(self, addr, value):
        self.ip.write(addr, value & 0xFFFFFFFF)

    def read(self, addr):
        return self.ip.read(addr)

    def _regs(self):
        return (f"STATUS=0x{self.read(STATUS):x} MM2S_SR=0x{self.dma.mmio.read(self.MM2S_SR):08x} "
                f"S2MM_SR=0x{self.dma.mmio.read(self.S2MM_SR):08x}")

    def _arm(self):
        if not self.armed:
            self.dma.recvchannel.transfer(self.outbuf)
            self.armed = True

    def _take(self, out):
        """Collect the packet of a completed receive transfer (if any) and arm the next one; True if one came."""
        if not (self.armed and self.dma.recvchannel.idle):
            return False
        self.dma.recvchannel.wait()                       # idle: returns at once, raises on a DMA error
        n = self.dma.mmio.read(self.S2MM_LENGTH)          # bytes of this packet (tlast ended the transfer)
        if n % 4 or n > 4 * len(self.outbuf):
            raise RuntimeError(f"S2MM length {n} bytes: not a whole packet of 32-bit words ({self._regs()})")
        view = self.outbuf[:n // 4]
        view.invalidate()
        out.append(np.array(view, dtype=np.uint32).tobytes())
        self.armed = False
        self._arm()
        return True

    def _collect(self, out):
        """Receive packets until none completes for quiet_s (the encryptor holds the open packet until it closes)."""
        self._arm()
        t = time.monotonic()
        while True:
            if self._take(out):
                t = time.monotonic()
            elif time.monotonic() - t > self.quiet_s:
                return out

    def transfer(self, words):
        w = np.asarray(words, dtype=np.uint32)
        out = []
        for i in range(0, len(w), len(self.inbuf)):
            chunk = w[i:i + len(self.inbuf)]
            view = self.inbuf[:len(chunk)]
            view[:] = chunk
            view.flush()
            self._arm()
            self.dma.sendchannel.transfer(view)
            t0 = time.monotonic()
            while not self.dma.sendchannel.idle:          # receive while sending: packets must not back up
                if not self._take(out) and time.monotonic() - t0 > self.timeout_s:
                    raise TimeoutError(f"MM2S not finished after {self.timeout_s} s ({self._regs()})")
            self.dma.sendchannel.wait()
        while self._take(out):                            # packets already complete; the rest come with the next
            pass                                          # push or drain() (the receive channel stays armed)
        return out

    def drain(self):
        return self._collect([])


class NvIP:
    def __init__(self, backend):
        self.b = backend

    def version(self):
        return self.b.read(VERSION)

    def _shadow(self, subkeys, sid, cfg, ctr0=0, at=0):
        w = self.b.write
        p = cfg.pad
        for a, v in [(MODE, mode_word(cfg)), (GEOM, cfg.geom.W | (cfg.geom.H << 16)), (T_US, cfg.T_us),
                     (SID_LO, sid), (SID_HI, sid >> 32), (CTR0_LO, ctr0), (CTR0_HI, ctr0 >> 32),
                     (PAD_MIN, p.pad_min if p else 0), (PAD_CAP, p.pad_cap if p else 0),
                     (MAX_GAP, cfg.max_gap_us), (AT_LO, at), (AT_HI, at >> 32)]:
            w(a, v & 0xFFFFFFFF)
        for name, base in K_BASE.items():
            k = getattr(subkeys, name)
            for i in range(4):
                w(base + 4 * i, le32(k, i))

    def configure(self, subkeys, sid, cfg, ctr0=0):
        self.b.write(CTRL, SRST)
        self._shadow(subkeys, sid, cfg, ctr0)
        self.b.write(CTRL, COMMIT)
        code = self.b.read(CFG_CODE)
        if code:
            raise ConfigError(code, "initial configuration refused")
        self.b.write(CTRL, EN)

    def push(self, words):
        return self.b.transfer(words)

    def flush(self):
        self.b.write(CTRL, EN | FLUSH)
        return self.b.drain()

    def commit(self, at, subkeys, sid, cfg, ctr0=0):
        """Returns CFG_CODE (0 = accepted)."""
        self._shadow(subkeys, sid, cfg, ctr0, at)
        self.b.write(CTRL, EN | COMMIT)
        return self.b.read(CFG_CODE)

    def counters(self):
        self.b.write(CTRL, EN | SNAP)
        r = self.b.read
        out = {k: r(a) | (r(a + 4) << 32) for k, a in COUNTERS64.items()}
        out.update({k: r(a) for k, a in COUNTERS32.items()})
        return out
