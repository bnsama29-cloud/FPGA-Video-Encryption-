"""RGB -> YCbCr 4:2:0 + 8x8 blocking vs model.blocks_in_hw_order().

Edge cases: black/white/pure R,G,B (colour bars), rounding at 0 and 255,
a single-MCU frame, non-square frames, back-to-back frames, random stalls
on both input and output.
"""
import cocotb
from cocotb.triggers import RisingEdge

from common import start, run_sim, rng_for, drive_stream, collect_stream
from model import hw as J
from model.testimage import make_image


async def run_frame(dut, img, rng, p_idle=0.3, p_stall=0.3):
    h, w = img.shape[:2]
    dut.width.value = w
    dut.height.value = h
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0
    pixels = [int(p[0]) | (int(p[1]) << 8) | (int(p[2]) << 16) for row in img for p in row]
    nsamples = (h * w * 3) // 2

    def apply(px):
        dut.s_data.value = px

    def sample():
        return (int(dut.m_data.value), int(dut.m_comp.value),
                int(dut.m_blast.value), int(dut.m_flast.value))

    drv = cocotb.start_soon(drive_stream(dut.clk, dut.s_valid, dut.s_ready, pixels, apply, rng, p_idle))
    got = await collect_stream(dut.clk, dut.m_valid, dut.m_ready, sample,
                               lambda o: len(o) >= nsamples, rng, p_stall)
    await drv
    exp_blocks = J.blocks_in_hw_order(img)
    for b, (comp, smp) in enumerate(exp_blocks):
        chunk = got[b * 64:(b + 1) * 64]
        assert [c[0] for c in chunk] == smp, (
            f"block {b} (comp {comp}) samples differ; first bad index "
            f"{next(i for i in range(64) if chunk[i][0] != smp[i])}")
        assert all(c[1] == comp for c in chunk), f"block {b}: wrong component id"
        assert [c[2] for c in chunk] == [0] * 63 + [1], f"block {b}: m_blast wrong"
        last = b == len(exp_blocks) - 1
        assert chunk[63][3] == int(last), f"block {b}: m_flast wrong"


@cocotb.test()
async def blocks_match_model(dut):
    rng = rng_for(dut)
    dut.start.value = 0
    dut.s_valid.value = 0
    dut.m_ready.value = 0
    await start(dut)
    for w, h, kind in [(16, 16, "bars"), (64, 32, "scene"), (48, 48, "bars"),
                       (32, 16, "noise"), (32, 32, "checker")]:
        dut._log.info("frame %dx%d %s", w, h, kind)
        await run_frame(dut, make_image(w, h, kind, seed=w + h), rng)


@cocotb.test()
async def full_throughput(dut):
    """No stalls: measure cycles per frame (an early fps estimate)."""
    rng = rng_for(dut)
    dut.start.value = 0
    dut.s_valid.value = 0
    await start(dut)
    img = make_image(64, 64, "scene")
    t0 = cocotb.utils.get_sim_time("ns")
    await run_frame(dut, img, rng, p_idle=0.0, p_stall=0.0)
    cycles = (cocotb.utils.get_sim_time("ns") - t0) / 10
    dut._log.info("64x64 frame: %d cycles = %.2f cycles/pixel", cycles, cycles / 4096)


def test_rgb2ycbcr_block():
    run_sim("rgb2ycbcr_block", "test_rgb2ycbcr_block")
