"""Full pipeline: secure_jpeg_top driven like the PYNQ Python driver will drive
the board (AXI-Lite registers + AXI4-Stream in/out), checked against the model.

Milestones M4 + M5 in simulation:
  * scan data byte-exact with the model and the frame opens in Pillow
  * every encryption mode; mode off == plain JPEG
  * per-frame tag correct; receiver verifies, decrypts bit-exactly,
    rejects tampered, replayed and wrong-session frames
  * back-to-back frames with random DMA stalls (backpressure)
Output JPEGs are written to sim_out/ so you can look at them.
"""
import io
import itertools
import os

import cocotb
import numpy as np
from cocotb.triggers import RisingEdge
from cocotbext.axi import (AxiLiteBus, AxiLiteMaster, AxiStreamBus,
                           AxiStreamSource, AxiStreamSink, AxiStreamFrame)
from PIL import Image

from common import start, run_sim, rng_for, full_run, ROOT
from model import hw as J, ascon
from model.testimage import make_image, psnr

# register map (rtl/axil_regs.v)
CTRL, STATUS, VERSION = 0x00, 0x04, 0x08
WIDTH, HEIGHT, FRAME_CTR, SESSION_ID = 0x10, 0x14, 0x18, 0x1C
KEY0, OUT_BYTES, TAG0, QT_ADDR, QT_DATA = 0x20, 0x30, 0x34, 0x44, 0x48
CYCLES, IN_WAIT, OUT_STALL = 0x54, 0x58, 0x5C          # performance counters (axil_regs.v)
SESSION_ID_HI, FRAME_CTR_HI = 0x4C, 0x50

OUT_DIR = ROOT / "sim_out"


class Encoder:
    """What the ARM-side Python does, expressed against the simulated IP."""

    def __init__(self, dut):
        self.dut = dut
        self.regs = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axil"), dut.clk, dut.rst)
        self.src = AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis"), dut.clk, dut.rst)
        self.sink = AxiStreamSink(AxiStreamBus.from_prefix(dut, "m_axis"), dut.clk, dut.rst)

    async def wr(self, addr, val):
        await self.regs.write_dword(addr, val & 0xFFFFFFFF)

    async def rd(self, addr):
        return await self.regs.read_dword(addr)

    async def setup_session(self, key, session_id, quality):
        for i in range(4):
            await self.wr(KEY0 + 4 * i, int.from_bytes(key[4 * i:4 * i + 4], "little"))
        await self.wr(SESSION_ID, session_id)              # bits [31:0]
        await self.wr(SESSION_ID_HI, session_id >> 32)     # bits [63:32]
        luma, chroma = J.quality_tables(quality)
        await self.wr(QT_ADDR, 0)
        for q in luma + chroma:
            await self.wr(QT_DATA, J.reciprocal(q))

    async def encode(self, img, mode, frame_ctr, timeout_cycles=3_000_000):
        h, w = img.shape[:2]
        await self.wr(WIDTH, w)
        await self.wr(HEIGHT, h)
        await self.wr(FRAME_CTR, frame_ctr)                # bits [31:0]
        await self.wr(FRAME_CTR_HI, frame_ctr >> 32)       # bits [62:32]
        t0 = cocotb.utils.get_sim_time("ns")
        await self.wr(CTRL, 1 | (mode << 1))
        px = img.astype(np.uint32)
        words = (px[..., 0] | (px[..., 1] << 8) | (px[..., 2] << 16)).flatten()
        await self.src.send(AxiStreamFrame(words.astype("<u4").tobytes()))
        frame = await self.sink.recv()
        for _ in range(timeout_cycles // 100):
            if (await self.rd(STATUS)) & 1:
                break
            await RisingEdge(self.dut.clk)
        else:
            raise TimeoutError("STATUS.DONE never set")
        cycles = (cocotb.utils.get_sim_time("ns") - t0) / 10
        n = await self.rd(OUT_BYTES)
        tag = b""
        for i in range(4):                       # (no await inside a generator expression)
            tag += (await self.rd(TAG0 + 4 * i)).to_bytes(4, "little")
        scan = bytes(frame.tdata)
        assert len(scan) == n, f"OUT_BYTES={n} but DMA received {len(scan)} bytes"
        return scan, tag, cycles


def build_jpeg(w, h, quality, mode, frame_ctr, session_id, scan, tag):
    """ARM side: headers + APP11 tag segment + scan + EOI (model/container.py)."""
    return J.build_frame(w, h, quality, mode, frame_ctr, session_id, scan, tag)


async def init(dut):
    dut.s_axis_tvalid.value = 0
    dut.m_axis_tready.value = 0
    await start(dut, cycles=10)
    return Encoder(dut)


@cocotb.test()
async def registers(dut):
    """Write and read back every register; keys must not be readable."""
    enc = await init(dut)
    assert await enc.rd(VERSION) == 0x5EC00200
    for addr, val in [(WIDTH, 0x280), (HEIGHT, 0x1E0), (FRAME_CTR, 0xDEADBEEF),
                      (SESSION_ID, 0x12345678), (SESSION_ID_HI, 0x9ABCDEF0),
                      (FRAME_CTR_HI, 0x7FFFFFFF), (QT_ADDR, 0x55)]:
        await enc.wr(addr, val)
        got = await enc.rd(addr)
        assert got == val, f"reg 0x{addr:02x}: wrote 0x{val:x} read 0x{got:x}"
    await enc.wr(FRAME_CTR_HI, 0xFFFFFFFF)               # counter is 63 bits
    assert await enc.rd(FRAME_CTR_HI) == 0x7FFFFFFF
    await enc.wr(KEY0, 0xCAFEF00D)
    assert await enc.rd(KEY0) == 0, "key register must read back as 0"
    assert await enc.rd(0xFC) == 0, "unused address must read 0"
    await enc.wr(0xFC, 0x1)                              # ignored, still OKAY
    await enc.regs.write(FRAME_CTR + 1, b"\x00")          # WSTRB: byte 1 only
    assert await enc.rd(FRAME_CTR) == 0xDEAD00EF
    await enc.wr(CTRL, 3 << 1)                           # mode only, no start
    assert await enc.rd(CTRL) == 3 << 1
    assert (await enc.rd(STATUS)) & 0b011 == 0, "idle after reset"


async def check_frame(dut, enc, img, quality, mode, ctr, key, sid, receiver, tag_name):
    h, w = img.shape[:2]
    scan, tag, cycles = await enc.encode(img, mode, ctr)
    model = J.encode_frame(img, quality, mode, key, ctr, sid)
    if scan != model["scan"]:
        i = next((k for k in range(min(len(scan), len(model["scan"])))
                  if scan[k] != model["scan"][k]), None)
        raise AssertionError(f"{tag_name}: scan differs from model at byte {i} "
                             f"(hw {len(scan)} bytes, model {len(model['scan'])})")
    assert tag == model["tag"], f"{tag_name}: tag mismatch"
    jpg = build_jpeg(w, h, quality, mode, ctr, sid, scan, tag)
    dec = np.array(Image.open(io.BytesIO(jpg)).convert("RGB"))   # must decode
    verdict, clear = receiver.process(jpg)
    assert verdict == "ok", f"{tag_name}: receiver said {verdict}"
    plain = J.encode_frame(img, quality, 0, key, ctr, sid)["scan"]
    assert J.split_scan(clear)[1] == plain, f"{tag_name}: decryption not bit-exact"
    clear_img = np.array(Image.open(io.BytesIO(clear)).convert("RGB"))
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"{tag_name}_scrambled.jpg").write_bytes(jpg)
    (OUT_DIR / f"{tag_name}_decrypted.jpg").write_bytes(clear)
    dut._log.info("%-22s %5d B  %7d cycles (%.2f cyc/px)  PSNR no-key %5.2f dB, with key %5.2f dB",
                  tag_name, len(scan), cycles, cycles / (w * h), psnr(dec, img), psnr(clear_img, img))
    return jpg


@cocotb.test()
async def frame_every_mode(dut):
    """One frame per mode; bit-exact with the model; receiver round trip."""
    enc = await init(dut)
    key, sid, quality = bytes(range(16)), 0x00FFC0EE_00C0FFEE, 75   # FF C0 inside APP11
    await enc.setup_session(key, sid, quality)
    rx = J.Receiver(key, sid)
    img = make_image(64, 48, "scene")
    for mode in range(5):
        await check_frame(dut, enc, img, quality, mode, (1 << 33) + mode, key, sid, rx, f"mode{mode}")


@cocotb.test()
async def back_to_back_with_stalls(dut):
    """Several frames, different sizes/content, random stalls on both DMA streams,
    then tamper / replay / wrong-session attacks on the received frames."""
    rng = rng_for(dut)
    enc = await init(dut)
    enc.src.set_pause_generator(itertools.cycle([rng.random() < 0.3 for _ in range(97)]))
    enc.sink.set_pause_generator(itertools.cycle([rng.random() < 0.4 for _ in range(89)]))
    key = bytes(rng.randrange(256) for _ in range(16))
    sid, quality = rng.randrange(1 << 64), 50
    await enc.setup_session(key, sid, quality)
    rx = J.Receiver(key, sid)
    frames = [(16, 16, "bars"), (48, 32, "noise"), (32, 32, "checker"), (64, 32, "scene")]
    if full_run():
        frames.append((320, 240, "scene"))
    jpgs = []
    for ctr, (w, h, kind) in enumerate(frames, start=100):
        jpgs.append(await check_frame(dut, enc, make_image(w, h, kind, seed=ctr), quality,
                                      2, ctr, key, sid, rx, f"b2b_{w}x{h}_{kind}"))
    # integrity tests on what an attacker could capture
    assert rx.process(jpgs[-1])[0] == "replay"
    bad = bytearray(jpgs[1]); bad[-10] ^= 0x04
    assert J.Receiver(key, sid).process(bytes(bad))[0] == "tag-mismatch"
    assert J.Receiver(key, sid ^ 1).process(jpgs[0])[0] == "wrong-session"
    assert J.Receiver(key, sid ^ (1 << 63)).process(jpgs[0])[0] == "wrong-session"
    # contract v2: the mode byte is authenticated (v1 tagged the scan only)
    down = bytearray(jpgs[0]); k = down.find(b"SJV1"); down[k + 5] = 1
    assert J.Receiver(key, sid).process(bytes(down))[0] == "tag-mismatch", "mode downgrade not detected"
    other = J.Receiver(bytes(16), sid)
    assert other.process(jpgs[0])[0] == "tag-mismatch", "wrong key must fail"


@cocotb.test()
async def throughput(dut):
    """No stalls: cycles per pixel -> frames per second at 100 MHz."""
    enc = await init(dut)
    key, sid, quality = bytes(16), 1, 75
    await enc.setup_session(key, sid, quality)
    w, h = (128, 96) if not full_run() else (320, 240)
    img = make_image(w, h, "scene")
    await enc.encode(img, 2, 0)                          # warm-up
    scan, tag, cycles = await enc.encode(img, 2, 1)
    cpp = cycles / (w * h)
    hw_cycles = await enc.rd(CYCLES)     # START..DONE in hardware; the polled count adds AXI-Lite latency
    assert 0 < hw_cycles <= cycles, f"CYCLES register {hw_cycles} vs {cycles:.0f} polled clocks"
    assert cycles - hw_cycles < 200, f"CYCLES register {hw_cycles} far below {cycles:.0f} polled clocks"
    dut._log.info("%dx%d: %.0f cycles, %.3f cycles/pixel -> 640x480 @100MHz ~ %.0f fps, "
                  "1280x720 ~ %.0f fps (register-polling overhead included)",
                  w, h, cycles, cpp, 100e6 / (cpp * 640 * 480), 100e6 / (cpp * 1280 * 720))


def test_secure_jpeg_top():
    run_sim("secure_jpeg_top", "test_top")
