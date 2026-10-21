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
    ip = SecureJpegIP(MockBackend(contract=3))         # or PynqBackend("secure_jpeg_lanes.bit")

Two overlays exist: secure_jpeg.bit (contract v2, rtl/secure_jpeg_top.v) and secure_jpeg_lanes.bit
(contract v3, rtl/secure_jpeg_lanes_top.v: 2 lanes, 64-bit pixel DMA = 2 pixels per beat). The driver
reads the VERSION register and adapts: the pixel words are the same uint32 array for both (the
64-bit DMA just moves two of them per beat), and v3 frames get version 3 in APP11 and a DRI segment.
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
CYCLES, IN_WAIT, OUT_STALL = 0x54, 0x58, 0x5C   # performance counters (bitstreams from 21 Oct 2026; older read 0)
FABRIC_HZ = 100e6                               # default fabric clock (FCLK_CLK0); PynqBackend reads the
                                                # real one (run 10: the 4-lane overlay is built for 125 MHz)
EXPECTED_VERSION = 0x5EC00200          # contract v2
V3_VERSION_BASE = 0x5EC00300           # contract v3: 0x5EC003LL, LL = number of lanes
E5_CAP = 0x80                          # v3 VERSION bit 7: the RTL implements mode 5 (INTERFACES.md §8.6)
YUYV_CAP = 0x40                        # v3 VERSION bit 6: built for camera-native YUYV input (4 pixels/beat)


def contract_of(version):
    """VERSION register -> (contract, lanes), or None for an unknown bitstream. Bit 7 (E5) is read by
    has_e5()."""
    if version == EXPECTED_VERSION:
        return 2, 1
    if version & 0xFFFFFF00 == V3_VERSION_BASE and version & 0x3F in (1, 2, 4):
        return 3, version & 0x3F
    return None


def has_yuyv(version):
    return version & 0xFFFFFF00 == V3_VERSION_BASE and bool(version & YUYV_CAP)


def is_yuyv_frame(frame):
    """A YUYV frame is H x 2W uint8 (2-D); an RGB frame is H x W x 3."""
    return getattr(frame, "ndim", 3) == 2


def frame_size(frame):
    """(width, height) of an RGB or YUYV frame."""
    return (frame.shape[1] // 2, frame.shape[0]) if is_yuyv_frame(frame) else (frame.shape[1], frame.shape[0])


def has_e5(version):
    return version & 0xFFFFFF00 == V3_VERSION_BASE and bool(version & E5_CAP)


def pixels_to_words(rgb):
    """H x W x 3 uint8 RGB -> uint32 words {pad, B, G, R} (R in bits [7:0]), raster order."""
    p = rgb.astype(np.uint32)
    return (p[..., 0] | (p[..., 1] << 8) | (p[..., 2] << 16)).ravel()


def load_pixels_into(words_u32, rgb):
    """Write the pixel words straight into a uint32 buffer (the DMA buffer) without temporaries: viewed
    as bytes, word i is R, G, B, pad, so one strided uint8 copy does it (on the A9 this replaces three
    uint32 temporaries and two shifts per pixel). The pad byte is left as it is (the RTL ignores bits
    [31:24]). Returns the number of words written. Same words as pixels_to_words."""
    n = rgb.shape[0] * rgb.shape[1]
    dst = words_u32.view(np.uint8).reshape(-1, 4)[:n, :3]
    if not np.shares_memory(dst, rgb):                 # a frame already in the buffer needs no copy
        dst[...] = rgb.reshape(n, 3)
    return n


def load_yuyv_into(words_u32, yuyv):
    """A YUYV frame (H x 2W bytes) into the DMA buffer as it is: 2 bytes per pixel, so W*H/2 words."""
    nbytes = yuyv.shape[0] * yuyv.shape[1]
    dst = words_u32.view(np.uint8)[:nbytes]
    if not np.shares_memory(dst, yuyv):
        dst[...] = yuyv.reshape(-1)
    return nbytes // 4


def yuyv_view(words_u32, w, h):
    """H x 2W uint8 view on the DMA buffer for a YUYV camera (zero-copy, as pixel_view for RGB)."""
    return words_u32.view(np.uint8)[:2 * w * h].reshape(h, 2 * w)


def pixel_view(words_u32, w, h):
    """An H x W x 3 uint8 view on the DMA buffer: a camera or decoder that writes its frame here puts
    the pixels where the DMA reads them, so the ARM copies nothing (load() then only flushes)."""
    return words_u32.view(np.uint8)[:4 * w * h].reshape(h, w, 4)[..., :3]


class MockBackend:
    """Register file + DMA emulated with the golden model (bit-exact with the RTL)."""

    def __init__(self, contract=2, lanes=2, e5=False, yuyv=False):
        self.contract, self.lanes, self.e5 = contract, lanes, e5 and contract == 3
        self.yuyv = yuyv and contract == 3
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
            return EXPECTED_VERSION if self.contract == 2 else (V3_VERSION_BASE + self.lanes + (E5_CAP if self.e5 else 0)
                                                                + (YUYV_CAP if self.yuyv else 0))
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

    def pixel_buffer(self, w, h):
        if getattr(self, "_buf", None) is None or self._buf.size < w * h:
            self._buf = np.zeros(w * h, np.uint32)
        return yuyv_view(self._buf, w, h) if self.yuyv else pixel_view(self._buf, w, h)

    def load(self, frame):
        """Put one frame into the (emulated) DMA buffer; returns the number of 32-bit words."""
        if is_yuyv_frame(frame):
            self._words = np.frombuffer(np.ascontiguousarray(frame, dtype=np.uint8).tobytes(), "<u4").copy()
        else:
            self._words = pixels_to_words(frame)
        return len(self._words)

    def run(self, n, timeout_s=2.0):
        """Start both DMA channels on the loaded frame and return the scan bytes."""
        return self.transfer(self._words[:n])

    def transfer(self, words):
        """Send the pixel words, receive the scan bytes (what the two DMA channels do)."""
        r = self.regs
        w, h = r.get(WIDTH, 0), r.get(HEIGHT, 0)
        if w % 16 or h % 16 or w == 0 or h == 0 or len(words) != (w * h // 2 if self.yuyv else w * h):
            raise ValueError(f"bad frame setup: {w}x{h}, {len(words)} words")
        key = b"".join(r.get(KEY0 + 4 * i, 0).to_bytes(4, "little") for i in range(4))
        sid = r.get(SESSION_ID, 0) | (r.get(SESSION_ID_HI, 0) << 32)
        ctr = r.get(FRAME_CTR, 0) | (r.get(FRAME_CTR_HI, 0) << 32)
        mode = (r.get(CTRL, 0) >> 1) & 7
        if mode > 4 and not self.e5:
            raise ValueError(f"mode {mode}: this bitstream has no E5 (VERSION bit 7 = 0)")
        if self.yuyv:
            frame = np.frombuffer(np.asarray(words, "<u4").tobytes(), np.uint8).reshape(h, 2 * w)
        else:
            frame = np.stack([(words >> s) & 0xFF for s in (0, 8, 16)], -1).reshape(h, w, 3).astype(np.uint8)
        self.out, self.tag = _encode_with_reciprocals(frame, self.qt[:64], self.qt[64:], mode, key, ctr, sid,
                                                      self.contract, "yuyv" if self.yuyv else "rgb")
        self.done = True
        return self.out


def _encode_with_reciprocals(rgb, luma_r, chroma_r, mode, key, ctr, sid, contract=2, pixfmt="rgb"):
    """model/hw.py :: encode_frame (v2) / encode_frame_v3 (v3), but with the reciprocal tables
    actually loaded into QT_DATA."""
    from model import ascon
    blocks = hw.blocks_in_hw_order(rgb, pixfmt)
    w, h = hw.frame_dims(rgb, pixfmt)

    def symbols(blks):
        syms, pred = [], {0: 0, 1: 0, 2: 0}
        for comp, smp in blks:
            q = hw.quantise(hw.dct2d(smp), luma_r if comp == 0 else chroma_r)
            syms.extend(hw.run_length(q, comp, pred))
        return syms

    if contract == 2:
        enc, _ = hw.selective_encrypt(symbols(blocks), mode, key, ascon.make_nonce(sid, ctr, 0))
        scan = hw.pack_bytes([hw.huffman_bits(s) for s in enc])
        return scan, hw.frame_tag(key, mode, ctr, sid, w, h, scan)
    per_seg = 6 if mode == hw.MODE_E5 else (w // 16) * 6          # blocks per restart segment
    enc_mode = hw.MODE_E4 if mode == hw.MODE_E5 else mode
    kseg, segs = hw.segment_key(key, sid, ctr), []
    for s in range(len(blocks) // per_seg):
        enc, _ = hw.selective_encrypt(symbols(blocks[s * per_seg:(s + 1) * per_seg]), enc_mode, kseg,
                                      ascon.make_nonce(s, ctr, 0))
        segs.append(hw.pack_bytes([hw.huffman_bits(x) for x in enc]))
    scan = b"".join((hw.RST_MARKERS[(s - 1) % 8] if s else b"") + b for s, b in enumerate(segs))
    return scan, hw.frame_tag(key, mode, ctr, sid, w, h, scan, version=3)


class PynqBackend:
    """The real PYNQ-Z2. Needs the overlay built by future_work/board/block_design.tcl.

    UNTESTED until the bitstream exists: names of the IP and the DMA in the overlay
    may differ -- print(Overlay(...).ip_dict.keys()) and pass ip_name / dma_name."""

    def __init__(self, bitfile, ip_name=None, dma_name=None, max_pixels=1920 * 1088, partial_cache=True,
                 fclk_mhz=None):
        from pynq import Overlay, allocate          # only available on the board
        self.ol = Overlay(bitfile)
        # Fabric clock: PYNQ sets FCLK0 from the .hwh when it loads the bitstream (100 MHz for the v2 and
        # 2-lane overlays, 125 MHz for the run-10 4-lane overlay). fclk_mhz lowers it, e.g. 100 for a first
        # bring-up of the 4-lane overlay: a design that meets timing at 125 MHz also works at 100 MHz.
        # Never set it above the clock in the .hwh: timing was only checked up to that clock.
        self.fabric_hz = FABRIC_HZ
        try:
            from pynq import Clocks
            if fclk_mhz:
                built = Clocks.fclk0_mhz
                if fclk_mhz > built + 0.5:
                    raise ValueError(f"fclk {fclk_mhz} MHz is above the {built:.1f} MHz this bitstream was built for")
                Clocks.fclk0_mhz = fclk_mhz
            self.fabric_hz = Clocks.fclk0_mhz * 1e6
        except ImportError:
            pass
        names = list(self.ol.ip_dict)
        ip_name = ip_name or next(n for n in names if "sjpeg" in n or "secure_jpeg" in n)
        dma_name = dma_name or next(n for n in names if "dma" in n)
        self.ip = getattr(self.ol, ip_name)
        self.dma = getattr(self.ol, dma_name)
        self.inbuf = allocate(shape=(max_pixels,), dtype=np.uint32)
        self.outbuf = allocate(shape=(max_pixels,), dtype=np.uint32)   # >= worst-case scan
        self.inbuf[:] = 0                                          # pad bytes stay 0 from here on
        self.inbuf.flush()
        # Flush / invalidate only the bytes of this frame (a slice of a PynqBuffer keeps its physical
        # address, which is how the DMA already receives inbuf[:n]). If this pynq version cannot do it on
        # a slice, fall back to the whole buffer; the bit-exact gate would catch a wrong cache operation.
        self.partial_cache = partial_cache
        self.n = 0
        self.yuyv = has_yuyv(self.read(VERSION))

    def _flush(self, buf):
        if self.partial_cache:
            try:
                buf.flush()
                return
            except Exception:
                self.partial_cache = False
        self.inbuf.flush()

    def _invalidate(self, buf):
        if self.partial_cache:
            try:
                buf.invalidate()
                return
            except Exception:
                self.partial_cache = False
        self.outbuf.invalidate()

    def pixel_buffer(self, w, h):
        """Zero-copy input: fill this view (e.g. cv2 capture.read(image=...) or np.copyto) and pass it to
        encode(); the ARM then only flushes the cache (see load_pixels_into). H x 2W bytes for a YUYV
        bitstream (VERSION bit 6), else H x W x 3."""
        return yuyv_view(self.inbuf, w, h) if self.yuyv else pixel_view(self.inbuf, w, h)

    def load(self, frame):
        """Write the frame straight into the DMA buffer and flush those bytes from the cache."""
        n = load_yuyv_into(self.inbuf, frame) if is_yuyv_frame(frame) else load_pixels_into(self.inbuf, frame)
        self._flush(self.inbuf[:n])
        self.n = n
        return n

    def run(self, n, timeout_s=2.0):
        """Start both DMA channels on the loaded frame; return the scan bytes."""
        self.dma.recvchannel.transfer(self.outbuf)                 # receive first
        self.dma.sendchannel.transfer(self.inbuf[:n])
        self._wait(self.dma.sendchannel, "send (MM2S, pixels in)", timeout_s)
        self._wait(self.dma.recvchannel, "receive (S2MM, scan out)", timeout_s)
        nbytes = self.read(OUT_BYTES)
        self._invalidate(self.outbuf[:(nbytes + 3) // 4])
        return self.outbuf.view(np.uint8)[:nbytes].tobytes()

    def write(self, addr, value):
        self.ip.write(addr, value & 0xFFFFFFFF)

    def read(self, addr):
        return self.ip.read(addr)

    def _wait(self, channel, name, timeout_s):
        """pynq's channel.wait() has no timeout: a DMA that never finishes hung the first board run
        silently (bug #32). Poll `idle` instead and fail with the registers that say why."""
        t0 = time.monotonic()
        while not channel.idle:
            if time.monotonic() - t0 > timeout_s:
                raise TimeoutError(
                    f"DMA {name} not finished after {timeout_s} s: STATUS=0x{self.read(STATUS):x} "
                    f"OUT_BYTES={self.read(OUT_BYTES)} MM2S_SR=0x{self.dma.read(0x04):08x} "
                    f"S2MM_SR=0x{self.dma.read(0x34):08x} (see docs/BOARD_BRINGUP.md section 9)")
        channel.wait()                                             # idle: returns at once, raises on DMA errors

    def transfer(self, words, timeout_s=2.0):
        """Old interface (uint32 words already packed): kept for scripts written before load/run."""
        n = len(words)
        self.inbuf[:n] = words
        self._flush(self.inbuf[:n])
        return self.run(n, timeout_s)


class SecureJpegIP:
    def __init__(self, backend):
        self.b = backend
        self.quality = None
        self.session_id = None
        version = self.b.read(VERSION)
        known = contract_of(version)
        if known is None:
            raise RuntimeError(f"VERSION register reads 0x{version:08x}, expected 0x{EXPECTED_VERSION:08x} "
                               f"(v2) or 0x{V3_VERSION_BASE + 2:08x} (v3, 2 lanes) "
                               "(wrong bitstream, or the AXI-Lite address is wrong)")
        self.contract, self.lanes = known
        self.e5 = has_e5(version)
        self.pixfmt = "yuyv" if has_yuyv(version) else "rgb"
        self.key = None
        self.last_timing = {}

    def pixel_buffer(self, w, h):
        """H x W x 3 view on the DMA input buffer (zero-copy path; None if the backend has none)."""
        f = getattr(self.b, "pixel_buffer", None)
        return f(w, h) if f else None

    @property
    def max_mode(self):
        return 5 if self.e5 else 4

    def setup_session(self, key, session_id, quality=75):
        self.key = bytes(key)
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
        """Returns (scan bytes, 16-byte tag) as the fabric produced them. mode 0..4, and 5 when the
        bitstream reports E5 (VERSION bit 7); for E5 the scan is in raster order (build_jpeg shuffles).
        rgb: an RGB frame (H x W x 3), or for a YUYV bitstream (VERSION bit 6) a YUYV frame (H x 2W bytes,
        straight from the camera); an RGB frame given to a YUYV bitstream is converted on the ARM
        (model/hw.py :: rgb_to_yuyv), which costs time: give the camera's YUYV when there is one."""
        if self.pixfmt == "yuyv" and not is_yuyv_frame(rgb):
            rgb = hw.rgb_to_yuyv(rgb)
        elif self.pixfmt == "rgb" and is_yuyv_frame(rgb):
            raise ValueError("a YUYV frame needs a bitstream built for YUYV (PIXFMT = 1, VERSION bit 6)")
        w, h = frame_size(rgb)
        if w % 16 or h % 16:
            raise ValueError("width and height must be multiples of 16")
        if not 0 <= mode <= self.max_mode:
            raise ValueError(f"this bitstream supports modes 0..{self.max_mode}")
        self.b.write(WIDTH, w)
        self.b.write(HEIGHT, h)
        self.b.write(FRAME_CTR, frame_ctr & 0xFFFFFFFF)
        self.b.write(FRAME_CTR_HI, frame_ctr >> 32)
        t0 = time.perf_counter()
        npix = self.b.load(rgb)                                    # pixels into the DMA buffer (+ cache flush)
        t1 = time.perf_counter()
        self.b.write(CTRL, 1 | (mode << 1))
        scan = self.b.run(npix, timeout_s)
        t2 = time.perf_counter()
        t0w = time.monotonic()
        while not self.b.read(STATUS) & 1:
            if time.monotonic() - t0w > timeout_s:
                raise TimeoutError("STATUS.DONE never set (check DMA, clock, reset and irq wiring)")
        n = self.b.read(OUT_BYTES)
        if n != len(scan):
            raise RuntimeError(f"OUT_BYTES = {n} but DMA returned {len(scan)} bytes")
        tag = b"".join(self.b.read(TAG0 + 4 * i).to_bytes(4, "little") for i in range(4))
        cyc = self.b.read(CYCLES)
        # Where the time went (ms): load = ARM writes the pixels and flushes; dma = start, wait, invalidate,
        # copy out; fabric = START..DONE in the fabric's own clock (None if the bitstream has no counter or
        # this is the mock); in_wait / out_stall = fabric clocks lost waiting for pixels / for the DMA.
        self.last_timing = dict(load_ms=1e3 * (t1 - t0), dma_ms=1e3 * (t2 - t1),
                                fabric_ms=1e3 * cyc / getattr(self.b, 'fabric_hz', FABRIC_HZ) if cyc else None, cycles=cyc or None,
                                in_wait=self.b.read(IN_WAIT) if cyc else None,
                                out_stall=self.b.read(OUT_STALL) if cyc else None)
        return scan, tag

    def build_jpeg(self, width, height, mode, frame_ctr, scan, tag):
        """What the ARM does after the fabric: headers + APP11 + scan + EOI; for E5 also the keyed
        permutation of the restart segments (model/hw.py :: arm_shuffle, INTERFACES.md §8.6)."""
        jpeg = hw.build_frame(width, height, self.quality, mode, frame_ctr, self.session_id, scan, tag,
                              version=self.contract)
        if mode == hw.MODE_E5:
            from .fast_e5 import arm_shuffle             # C order + bytes.find; same bytes as hw.arm_shuffle
            jpeg = arm_shuffle(jpeg, self.key, self.session_id, frame_ctr)
        return jpeg
