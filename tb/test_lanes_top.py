"""Contract v3 encoder (rtl/secure_jpeg_lanes_top.v) driven like the PYNQ will drive it, checked
against the golden model (model/hw.py :: encode_frame_v3).

  * scan bytes and tag bit-exact with the model, for every mode, and for LANES = 1, 2 and 4
    (the claim "the bytes do not depend on the lane count" is checked on the RTL, not assumed);
  * the receiver verifies, decrypts and returns exactly the contract-v2 plain JPEG;
  * frames whose MCU-row count is not a multiple of LANES (a lane with fewer or no rows);
  * random stalls on both DMA streams, back-to-back frames, tamper/replay detection;
  * throughput: clocks per pixel measured from the CTRL write to irq_done (no polling overhead),
    written to sim_out/lanes_throughput_L<n>.json for experiments/lanes_rtl_throughput.py.
"""
import io
import itertools
import json
import os

import cocotb
import numpy as np
import pytest
from cocotb.triggers import RisingEdge
from cocotbext.axi import (AxiLiteBus, AxiLiteMaster, AxiStreamBus,
                           AxiStreamSource, AxiStreamSink, AxiStreamFrame)
from PIL import Image

from common import start, run_sim, rng_for, full_run, ROOT
from model import hw as J
from model.testimage import make_image

CTRL, STATUS, VERSION = 0x00, 0x04, 0x08
WIDTH, HEIGHT, FRAME_CTR, SESSION_ID = 0x10, 0x14, 0x18, 0x1C
KEY0, OUT_BYTES, TAG0, QT_ADDR, QT_DATA = 0x20, 0x30, 0x34, 0x44, 0x48
SESSION_ID_HI, FRAME_CTR_HI = 0x4C, 0x50
OUT_DIR = ROOT / "sim_out"


def lanes_of(dut):
    return int(dut.LANES.value)


class Encoder:
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
        await self.wr(SESSION_ID, session_id)
        await self.wr(SESSION_ID_HI, session_id >> 32)
        luma, chroma = J.quality_tables(quality)
        await self.wr(QT_ADDR, 0)
        for q in luma + chroma:
            await self.wr(QT_DATA, J.reciprocal(q))

    async def encode(self, img, mode, frame_ctr):
        """Returns (scan, tag, clocks from the CTRL write to irq_done)."""
        h, w = img.shape[:2]
        await self.wr(WIDTH, w)
        await self.wr(HEIGHT, h)
        await self.wr(FRAME_CTR, frame_ctr)
        await self.wr(FRAME_CTR_HI, frame_ctr >> 32)
        px = img.astype(np.uint32)
        words = (px[..., 0] | (px[..., 1] << 8) | (px[..., 2] << 16)).flatten()
        # 64-bit beats: the left pixel in tdata[31:0] = the first 4 bytes, so the byte stream
        # is the same as the 32-bit stream of contract v2
        send = cocotb.start_soon(self.src.send(AxiStreamFrame(words.astype("<u4").tobytes())))
        recv = cocotb.start_soon(self.sink.recv())
        timing = cocotb.start_soon(self._time_frame())
        await self.wr(CTRL, 1 | (mode << 1))
        clocks = await timing
        await send
        frame = await recv
        assert (await self.rd(STATUS)) & 1, "STATUS.DONE not set"
        n = await self.rd(OUT_BYTES)
        tag = b""
        for i in range(4):
            tag += (await self.rd(TAG0 + 4 * i)).to_bytes(4, "little")
        scan = bytes(frame.tdata)
        assert len(scan) == n, f"OUT_BYTES={n} but DMA received {len(scan)} bytes"
        return scan, tag, clocks


async def _time_frame_impl(self):
    """Clocks from the internal start pulse to irq_done (excludes AXI-Lite polling)."""
    dut = self.dut
    while not int(dut.start.value):
        await RisingEdge(dut.clk)
    t0 = cocotb.utils.get_sim_time("ns")
    t_in = t_out = None
    await RisingEdge(dut.clk)
    while not int(dut.irq_done.value):
        if t_in is None and int(dut.s_axis_tvalid.value) and int(dut.s_axis_tready.value):
            t_in = cocotb.utils.get_sim_time("ns")
        if t_out is None and int(dut.m_axis_tvalid.value):
            t_out = cocotb.utils.get_sim_time("ns")
        await RisingEdge(dut.clk)
    # latency: first pixel accepted -> first scan word offered to the DMA
    self.latency = (t_out - t_in) / 10 if t_in is not None and t_out is not None else None
    return (cocotb.utils.get_sim_time("ns") - t0) / 10


Encoder._time_frame = _time_frame_impl


async def init(dut):
    dut.s_axis_tvalid.value = 0
    dut.m_axis_tready.value = 0
    await start(dut, cycles=10)
    return Encoder(dut)


def first_diff(a, b):
    return next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))


async def check_frame(dut, enc, img, quality, mode, ctr, key, sid, receiver, name):
    h, w = img.shape[:2]
    scan, tag, clocks = await enc.encode(img, mode, ctr)
    model = J.encode_frame_v3(img, quality, mode, key, ctr, sid, lanes=lanes_of(dut))
    if scan != model["scan"]:
        i = first_diff(scan, model["scan"])
        raise AssertionError(f"{name}: scan differs from model at byte {i} (hw {len(scan)} B, "
                             f"model {len(model['scan'])} B): hw {scan[i:i+8].hex()} "
                             f"model {model['scan'][i:i+8].hex()}")
    assert tag == model["tag"], f"{name}: tag mismatch"
    jpg = J.build_frame(w, h, quality, mode, ctr, sid, scan, tag, version=3)
    np.array(Image.open(io.BytesIO(jpg)).convert("RGB"))        # must decode in a normal viewer
    verdict, clear = receiver.process(jpg)
    assert verdict == "ok", f"{name}: receiver said {verdict}"
    plain_v2 = J.encode_frame(img, quality, 0, key, ctr, sid)["scan"]
    assert J.split_scan(clear)[1] == plain_v2, f"{name}: decryption not bit-exact"
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"v3_L{lanes_of(dut)}_{name}.jpg").write_bytes(jpg)
    dut._log.info("L=%d %-18s %5d B %8d clk  %.3f clk/px", lanes_of(dut), name, len(scan),
                  clocks, clocks / (w * h))
    return jpg, clocks


@cocotb.test()
async def registers(dut):
    enc = await init(dut)
    got = await enc.rd(VERSION)
    assert got == 0x5EC00300 + lanes_of(dut), f"VERSION 0x{got:08x}"


@cocotb.test()
async def frame_every_mode(dut):
    """One frame per mode, bit-exact with the model; 5 MCU rows so lanes get unequal rows."""
    enc = await init(dut)
    key, sid, quality = bytes(range(16)), 0x00FFC0EE_00C0FFEE, 75
    await enc.setup_session(key, sid, quality)
    rx = J.Receiver(key, sid)
    img = make_image(64, 80, "scene")
    for mode in range(5):
        await check_frame(dut, enc, img, quality, mode, (1 << 33) + mode, key, sid, rx, f"mode{mode}")


@cocotb.test()
async def back_to_back_with_stalls(dut):
    rng = rng_for(dut)
    enc = await init(dut)
    enc.src.set_pause_generator(itertools.cycle([rng.random() < 0.3 for _ in range(97)]))
    enc.sink.set_pause_generator(itertools.cycle([rng.random() < 0.4 for _ in range(89)]))
    key = bytes(rng.randrange(256) for _ in range(16))
    sid, quality = rng.randrange(1 << 64), 50
    await enc.setup_session(key, sid, quality)
    rx = J.Receiver(key, sid)
    # 16 lines: lanes 1..3 get no rows; 48x48: 3 rows; noise: big segments that fill the FIFOs
    frames = [(16, 16, "bars"), (48, 48, "noise"), (32, 32, "checker"), (64, 96, "scene"),
              (16, 160, "noise")]
    if full_run():
        frames.append((320, 240, "scene"))
    jpgs = []
    for ctr, (w, h, kind) in enumerate(frames, start=100):
        mode = rng.choice([1, 2, 3, 4])
        jpgs.append((await check_frame(dut, enc, make_image(w, h, kind, seed=ctr), quality, mode,
                                       ctr, key, sid, rx, f"b2b_{w}x{h}_{kind}"))[0])
    assert rx.process(jpgs[-1])[0] == "replay"
    bad = bytearray(jpgs[1]); bad[-10] ^= 0x04
    assert J.Receiver(key, sid).process(bytes(bad))[0] == "tag-mismatch"
    # the version byte is authenticated: a v3 frame relabelled as v2 must fail
    down = bytearray(jpgs[0]); k = down.find(b"SJV1"); down[k + 4] = 2
    assert J.Receiver(key, sid).process(bytes(down))[0] != "ok", "version downgrade not detected"


@cocotb.test()
async def throughput(dut):
    """Clocks per pixel with no stalls (scene image, quality 75, E2)."""
    enc = await init(dut)
    key, sid, quality = bytes(16), 1, 75
    await enc.setup_session(key, sid, quality)
    size = os.getenv("THROUGHPUT_SIZE", "640x480" if full_run() else "128x96")
    w, h = (int(v) for v in size.split("x"))
    img = make_image(w, h, "scene")
    if os.getenv("THROUGHPUT_WARMUP", "1") == "1":
        await enc.encode(img, 2, 0)                      # warm-up (frames are independent)
    scan, tag, clocks = await enc.encode(img, 2, 1)
    model = J.encode_frame_v3(img, quality, 2, key, 1, sid)
    assert scan == model["scan"] and tag == model["tag"], "throughput frame not bit-exact"
    cpp = clocks / (w * h)
    res = dict(lanes=lanes_of(dut), width=w, height=h, clocks=clocks, clocks_per_pixel=cpp,
               mpx_per_s_at_100mhz=100 / cpp, scan_bytes=len(scan),
               latency_clocks=enc.latency, latency_lines=(enc.latency / (w / 2)) if enc.latency else None,
               measured_from="internal start pulse to irq_done, no DMA stalls, Icarus cycle-accurate")
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"lanes_throughput_L{lanes_of(dut)}_{w}x{h}.json").write_text(json.dumps(res, indent=1))
    dut._log.info("L=%d %dx%d: %.0f clocks, %.3f clocks/pixel -> %.1f Mpx/s at 100 MHz",
                  lanes_of(dut), w, h, clocks, cpp, 100 / cpp)


@pytest.mark.parametrize("lanes", [1, 2, 4])
def test_secure_jpeg_lanes_top(lanes):
    log_l = {1: 1, 2: 1, 4: 2}[lanes]
    run_sim("secure_jpeg_lanes_top", "test_lanes_top",
            parameters=dict(LANES=lanes, LOG_L=log_l, LOG_MAXW=10, LOG_FIFO=10), build_tag=f"_L{lanes}")
