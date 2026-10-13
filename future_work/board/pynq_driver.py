"""Driver for the secure JPEG IP on the PYNQ-Z2, plus a mock for testing without a board.

The register sequence is exactly the one verified in simulation (tb/test_top.py :: Encoder):
    once per session : KEY0..3, SESSION_ID (+ _HI), QT_ADDR = 0, 128 x QT_DATA (reciprocals)
    per frame        : WIDTH, HEIGHT, FRAME_CTR (+ _HI), CTRL = 1 | mode << 1,
                       DMA receive started first, then DMA send of the pixels,
                       wait for both + STATUS.DONE, read OUT_BYTES and TAG0..3

Backends
    PynqBackend : the real board (needs the `pynq` package and the overlay from
                  future_work/board/block_design.tcl). UNTESTED until the bitstream exists.
    MockBackend : emulates the registers and the DMA with the golden model
                  (model/hw.py, bit-exact with the RTL). Lets you develop and test the
                  driver, the board sender and the network side on any laptop today.

    ip = SecureJpegIP(MockBackend())                   # or PynqBackend("secure_jpeg.bit")
    ip.setup_session(key, session_id, quality=75)
    scan, tag = ip.encode(rgb, mode=2, frame_ctr=1)
    jpeg = ip.build_jpeg(rgb.shape[1], rgb.shape[0], 2, 1, scan, tag)
"""
import time

import numpy as np

from model import hw

# register map (rtl/axil_regs.v, docs/INTERFACES.md section 3)
CTRL, STATUS, VERSION = 0x00, 0x04, 0x08
WIDTH, HEIGHT, FRAME_CTR, SESSION_ID = 0x10, 0x14, 0x18, 0x1C
KEY0, OUT_BYTES, TAG0, QT_ADDR, QT_DATA = 0x20, 0x30, 0x34, 0x44, 0x48
SESSION_ID_HI, FRAME_CTR_HI = 0x4C, 0x50
EXPECTED_VERSION = 0x5EC00200


def pixels_to_words(rgb):
    """H x W x 3 uint8 RGB -> uint32 words {pad, B, G, R} (R in bits [7:0]), raster order."""
    p = rgb.astype(np.uint32)
    return (p[..., 0] | (p[..., 1] << 8) | (p[..., 2] << 16)).ravel()


class MockBackend:
    """Register file + DMA emulated with the golden model (bit-exact with the RTL)."""

    def __init__(self):
        self.regs = {}
        self.qt = [0] * 128
        self.qt_ptr = 0
        self.out = b""
        self.tag = bytes(16)
        self.done = False
        self.writes = []                      # (addr, value) log, for tests

    def write(self, addr, value):
        value &= 0xFFFFFFFF
        self.writes.append((addr, value))
        if addr == QT_ADDR:
            self.qt_ptr = value & 0x7F
        elif addr == QT_DATA:
            self.qt[self.qt_ptr] = value & 0x1FFFF
            self.qt_ptr = (self.qt_ptr + 1) & 0x7F
        elif addr == CTRL:
            self.regs[CTRL] = value & 0xE
            if value & 1:
                self.done = False
        elif addr == FRAME_CTR_HI:
            self.regs[addr] = value & 0x7FFFFFFF
        else:
            self.regs[addr] = value                # keys are stored but read back as 0

    def read(self, addr):
        if addr == VERSION:
            return EXPECTED_VERSION
        if addr == STATUS:
            return 0b101 if self.done else 0
        if addr == OUT_BYTES:
            return len(self.out)
        if TAG0 <= addr < TAG0 + 16:
            i = (addr - TAG0) // 4
            return int.from_bytes(self.tag[4 * i:4 * i + 4], "little")
        if addr in (KEY0, KEY0 + 4, KEY0 + 8, KEY0 + 12):
            return 0
        return self.regs.get(addr, 0)

    def transfer(self, words):
        """Send the pixel words, receive the scan bytes (what the two DMA channels do)."""
        r = self.regs
        w, h = r.get(WIDTH, 0), r.get(HEIGHT, 0)
        if w % 16 or h % 16 or w == 0 or h == 0 or len(words) != w * h:
            raise ValueError(f"bad frame setup: {w}x{h}, {len(words)} pixels")
        key = b"".join(r.get(KEY0 + 4 * i, 0).to_bytes(4, "little") for i in range(4))
        sid = r.get(SESSION_ID, 0) | (r.get(SESSION_ID_HI, 0) << 32)
        ctr = r.get(FRAME_CTR, 0) | (r.get(FRAME_CTR_HI, 0) << 32)
        mode = (r.get(CTRL, 0) >> 1) & 7
        rgb = np.stack([(words >> s) & 0xFF for s in (0, 8, 16)], -1).reshape(h, w, 3).astype(np.uint8)
        self.out, self.tag = _encode_with_reciprocals(rgb, self.qt[:64], self.qt[64:], mode, key, ctr, sid)
        self.done = True
        return self.out


def _encode_with_reciprocals(rgb, luma_r, chroma_r, mode, key, ctr, sid):
    """model/hw.py :: encode_frame, but with the reciprocal tables actually loaded into QT_DATA."""
    from model import ascon
    blocks = hw.blocks_in_hw_order(rgb)
    syms, pred = [], {0: 0, 1: 0, 2: 0}
    for comp, smp in blocks:
        q = hw.quantise(hw.dct2d(smp), luma_r if comp == 0 else chroma_r)
        syms.extend(hw.run_length(q, comp, pred))
    enc, _ = hw.selective_encrypt(syms, mode, key, ascon.make_nonce(sid, ctr, 0))
    scan = hw.pack_bytes([hw.huffman_bits(s) for s in enc])
    h, w = rgb.shape[:2]
    return scan, hw.frame_tag(key, mode, ctr, sid, w, h, scan)


class PynqBackend:
    """The real PYNQ-Z2. Needs the overlay built by future_work/board/block_design.tcl.

    UNTESTED until the bitstream exists: names of the IP and the DMA in the overlay
    may differ -- print(Overlay(...).ip_dict.keys()) and pass ip_name / dma_name."""

    def __init__(self, bitfile, ip_name=None, dma_name=None, max_pixels=640 * 480):
        from pynq import Overlay, allocate          # only available on the board
        self.ol = Overlay(bitfile)
        names = list(self.ol.ip_dict)
        ip_name = ip_name or next(n for n in names if "sjpeg" in n or "secure_jpeg" in n)
        dma_name = dma_name or next(n for n in names if "dma" in n)
        self.ip = getattr(self.ol, ip_name)
        self.dma = getattr(self.ol, dma_name)
        self.inbuf = allocate(shape=(max_pixels,), dtype=np.uint32)
        self.outbuf = allocate(shape=(max_pixels,), dtype=np.uint32)   # >= worst-case scan

    def write(self, addr, value):
        self.ip.write(addr, value & 0xFFFFFFFF)

    def read(self, addr):
        return self.ip.read(addr)

    def transfer(self, words):
        n = len(words)
        self.inbuf[:n] = words
        self.inbuf.flush()
        self.dma.recvchannel.transfer(self.outbuf)                 # receive first
        self.dma.sendchannel.transfer(self.inbuf[:n])
        self.dma.sendchannel.wait()
        self.dma.recvchannel.wait()
        nbytes = self.read(OUT_BYTES)
        self.outbuf.invalidate()
        return self.outbuf.view(np.uint8)[:nbytes].tobytes()


class SecureJpegIP:
    def __init__(self, backend):
        self.b = backend
        self.quality = None
        self.session_id = None
        version = self.b.read(VERSION)
        if version != EXPECTED_VERSION:
            raise RuntimeError(f"VERSION register reads 0x{version:08x}, expected 0x{EXPECTED_VERSION:08x} "
                               "(wrong bitstream, or the AXI-Lite address is wrong)")

    def setup_session(self, key, session_id, quality=75):
        for i in range(4):
            self.b.write(KEY0 + 4 * i, int.from_bytes(key[4 * i:4 * i + 4], "little"))
        self.b.write(SESSION_ID, session_id & 0xFFFFFFFF)
        self.b.write(SESSION_ID_HI, session_id >> 32)
        luma, chroma = hw.quality_tables(quality)
        self.b.write(QT_ADDR, 0)
        for q in luma + chroma:
            self.b.write(QT_DATA, hw.reciprocal(q))
        self.quality, self.session_id = quality, session_id

    def encode(self, rgb, mode, frame_ctr, timeout_s=2.0):
        """Returns (scan bytes, 16-byte tag). mode 0..4 (E5 needs RTL restart markers)."""
        h, w = rgb.shape[:2]
        if w % 16 or h % 16:
            raise ValueError("width and height must be multiples of 16")
        if not 0 <= mode <= 4:
            raise ValueError("the RTL supports modes 0..4")
        self.b.write(WIDTH, w)
        self.b.write(HEIGHT, h)
        self.b.write(FRAME_CTR, frame_ctr & 0xFFFFFFFF)
        self.b.write(FRAME_CTR_HI, frame_ctr >> 32)
        self.b.write(CTRL, 1 | (mode << 1))
        scan = self.b.transfer(pixels_to_words(rgb))
        t0 = time.monotonic()
        while not self.b.read(STATUS) & 1:
            if time.monotonic() - t0 > timeout_s:
                raise TimeoutError("STATUS.DONE never set (check DMA, clock, reset and irq wiring)")
        n = self.b.read(OUT_BYTES)
        if n != len(scan):
            raise RuntimeError(f"OUT_BYTES = {n} but DMA returned {len(scan)} bytes")
        tag = b"".join(self.b.read(TAG0 + 4 * i).to_bytes(4, "little") for i in range(4))
        return scan, tag

    def build_jpeg(self, width, height, mode, frame_ctr, scan, tag):
        """What the ARM does after the fabric: headers + APP11 + scan + EOI."""
        return hw.build_frame(width, height, self.quality, mode, frame_ctr, self.session_id, scan, tag)
