"""8x8 DCT and quantiser vs model.dct2d() / model.quantise() (milestone M2).

Edge cases: flat blocks (0, 128, 255), checkerboard, alternating max/min,
random blocks, several quality tables, negative rounding, clamping.
"""
import cocotb
from cocotb.triggers import RisingEdge

from common import start, run_sim, rng_for, drive_stream, collect_stream, sval
from model import jpeg as J


def special_blocks():
    flat = [[v] * 64 for v in (0, 128, 255)]
    checker = [255 if ((i // 8) + (i % 8)) % 2 else 0 for i in range(64)]
    stripes = [255 if (i % 8) % 2 else 0 for i in range(64)]
    ramp = [i * 4 for i in range(64)]
    return flat + [checker, stripes, ramp]


@cocotb.test()
async def dct_matches_model(dut):
    rng = rng_for(dut)
    dut.in_valid.value = 0
    await start(dut)
    blocks = special_blocks() + [[rng.randrange(256) for _ in range(64)] for _ in range(40)]
    items = []
    for b, blk in enumerate(blocks):
        comp = b % 3
        for i, s in enumerate(blk):
            items.append((s, comp, int(b == len(blocks) - 1 and i == 63)))

    def apply(it):
        dut.in_data.value, dut.in_comp.value, dut.in_flast.value = it

    def sample():
        return (sval(dut.out_data), int(dut.out_comp.value),
                int(dut.out_blast.value), int(dut.out_flast.value))

    drv = cocotb.start_soon(drive_stream(dut.clk, dut.in_valid, dut.in_ready, items, apply, rng, 0.2))
    got = await collect_stream(dut.clk, dut.out_valid, dut.out_ready, sample,
                               lambda o: len(o) >= 64 * len(blocks), rng, 0.2)
    await drv
    for b, blk in enumerate(blocks):
        exp = J.dct2d(blk)
        chunk = got[b * 64:(b + 1) * 64]
        vals = [c[0] for c in chunk]
        assert vals == exp, (f"block {b}: first mismatch at index "
                             f"{next(i for i in range(64) if vals[i] != exp[i])}: "
                             f"got {vals} expected {exp}")
        assert all(c[1] == b % 3 for c in chunk), f"block {b}: comp lost"
        assert chunk[63][2] == 1 and chunk[63][3] == int(b == len(blocks) - 1)


@cocotb.test()
async def quantiser_matches_model(dut):
    rng = rng_for(dut)
    dut.in_valid.value = 0
    dut.qt_we.value = 0
    await start(dut)
    for quality in (10, 50, 75, 95, 100):
        luma, chroma = J.quality_tables(quality)
        recips = [[J.reciprocal(q) for q in luma], [J.reciprocal(q) for q in chroma]]
        for t in range(2):
            for i in range(64):
                dut.qt_we.value = 1
                dut.qt_addr.value = t * 64 + i
                dut.qt_data.value = recips[t][i]
                await RisingEdge(dut.clk)
        dut.qt_we.value = 0
        blocks = [[rng.randint(-2048, 2047) for _ in range(64)] for _ in range(12)]
        blocks += [[-1024] + [0] * 63, [2047] * 64, [-2048] * 64, [-1] * 64, [1] * 64]
        items = []
        for b, blk in enumerate(blocks):
            for i, v in enumerate(blk):
                items.append((v, b % 3, int(i == 63)))

        def apply(it):
            dut.in_data.value = it[0] & 0xFFFF
            dut.in_comp.value = it[1]
            dut.in_blast.value = it[2]
            dut.in_flast.value = 0

        drv = cocotb.start_soon(drive_stream(dut.clk, dut.in_valid, dut.in_ready, items, apply, rng, 0.2))
        got = await collect_stream(dut.clk, dut.out_valid, dut.out_ready,
                                   lambda: sval(dut.out_data),
                                   lambda o: len(o) >= len(items), rng, 0.2)
        await drv
        for b, blk in enumerate(blocks):
            r = recips[0 if b % 3 == 0 else 1]
            exp = J.quantise(blk, r)
            g = got[b * 64:(b + 1) * 64]
            if g != exp:
                i = next(k for k in range(64) if g[k] != exp[k])
                raise AssertionError(
                    f"quality {quality} block {b} (comp {b % 3}) first mismatch at index {i}: "
                    f"input F={blk[i]}, reciprocal R={r[i]}, got {g[i]}, expected {exp[i]} "
                    f"(|F|*R = {abs(blk[i]) * r[i]}, exact quotient {abs(blk[i]) * r[i] / 65536:.4f})")


def test_dct8x8():
    run_sim("dct8x8", "test_dct_quant", testcase="dct_matches_model")


def test_quantiser():
    run_sim("quantiser", "test_dct_quant", testcase="quantiser_matches_model")
