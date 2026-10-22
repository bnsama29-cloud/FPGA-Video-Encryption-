"""Shared helpers for every cocotb testbench in this repository.

* run_sim(): builds + runs one RTL top with cocotb's Python runner (called
  from the pytest functions at the bottom of each test_*.py file).
* clock/reset helpers and generic valid/ready drivers and monitors with
  random stalls (backpressure), so every block is tested under stalls.

Environment variables:
  SIM=icarus|verilator   simulator (default icarus)
  WAVES=1                dump waveforms (sim_build/<top>/*.fst -> GTKWave)
  SEED=<int>             fix the random seed to reproduce a failure
  FULL=1                 run the long tests (bigger images, all KATs)
"""
import os
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

ROOT = Path(__file__).resolve().parent.parent
RTL = ROOT / "rtl"
sys.path.insert(0, str(ROOT))          # so `import model` works inside cocotb

# Source lists per top level (dependencies first)
ASCON = ["ascon_round.v", "ascon_aead128_core.v"]
SOURCES = {
    "ascon_aead128_core": ASCON,
    "keystream_gen": ASCON + ["keystream_gen.v"],
    "tag_unit": ASCON + ["tag_unit.v"],
    "rgb2ycbcr_block": ["rgb2ycbcr_block.v"],
    "dct8x8": ["dct_stage.v", "dct8x8.v"],
    "quantiser": ["quantiser.v"],
    "zigzag_rle": ["zigzag_rle.v"],
    "selective_enc": ["skid_buf.v", "selective_enc.v"],
    "huffman_packer": ["skid_buf.v", "huffman_enc.v", "bit_packer.v", "huffman_packer.v"],
    "axil_regs": ["axil_regs.v"],
    "axis_tamper": ["../future_work/board/axis_tamper.v"],     # board-day test equipment, not the encoder
    "axil_buttons": ["../future_work/board/axil_buttons.v"],   # BTN1..BTN3 -> protection level (tamper overlay)
    "secure_jpeg_top": ASCON + [
        "skid_buf.v", "keystream_gen.v", "tag_unit.v", "rgb2ycbcr_block.v", "dct_stage.v",
        "dct8x8.v", "quantiser.v", "zigzag_rle.v", "selective_enc.v",
        "huffman_enc.v", "bit_packer.v", "scan_word_packer.v", "axil_regs.v",
        "secure_jpeg_top.v"],
    "secure_jpeg_lanes_top": ASCON + [
        "skid_buf.v", "keystream_gen.v", "tag_unit.v", "kseg_unit.v", "rgb2ycbcr_2px.v", "yuyv_4px.v", "dct_stage.v",
        "dct8x8.v", "quantiser.v", "zigzag_rle.v", "selective_enc.v",
        "huffman_enc.v", "bit_packer.v", "byte_fifo.v", "encoder_lane.v", "segment_merger.v",
        "scan_word_packer.v", "axil_regs.v", "secure_jpeg_lanes_top.v"],
}


def run_sim(toplevel, test_module, parameters=None, testcase=None, build_tag=""):
    """Build and run `toplevel` with cocotb tests from `test_module`.
    build_tag separates builds of one top with different parameters (e.g. "_L2")."""
    from cocotb_tools.runner import get_runner, get_results
    sim = os.getenv("SIM", "icarus")
    waves = os.getenv("WAVES", "0") == "1"
    build_dir = ROOT / "sim_build" / (toplevel + build_tag)
    runner = get_runner(sim)
    build_args = []
    if sim == "verilator":
        build_args = ["-Wno-fatal", "--trace-fst", "--trace-structs"] if waves else ["-Wno-fatal"]
    runner.build(
        sources=[RTL / f for f in SOURCES[toplevel]],
        includes=[RTL / "include"],
        hdl_toplevel=toplevel,
        build_dir=build_dir,
        parameters=parameters or {},
        build_args=build_args,
        timescale=("1ns", "1ps"),
        waves=waves,
        always=True,
    )
    xml = runner.test(
        hdl_toplevel=toplevel,
        test_module=test_module,
        test_dir=Path(__file__).resolve().parent,
        build_dir=build_dir,
        waves=waves,
        testcase=testcase,
        seed=os.getenv("SEED"),
        extra_env={"PYTHONPATH": str(ROOT) + os.pathsep + os.getenv("PYTHONPATH", "")},
    )
    total, failed = get_results(xml)
    assert failed == 0, f"{failed} of {total} cocotb tests failed in {toplevel} (see log above)"


def full_run():
    return os.getenv("FULL", "0") == "1"


def rng_for(dut):
    seed = int(os.getenv("SEED", "0")) or random.randrange(1 << 30)
    dut._log.info("random seed = %d  (re-run with SEED=%d to reproduce)", seed, seed)
    return random.Random(seed)


# ------------------------------------------------------------- basic helpers
async def start(dut, cycles=5):
    """Start a 100 MHz clock on dut.clk and pulse dut.rst."""
    cocotb.start_soon(Clock(dut.clk, 10, "ns").start())
    dut.rst.value = 1
    await ClockCycles(dut.clk, cycles)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


def sval(sig):
    """Signed integer value of a signal (works on cocotb 1.x and 2.x)."""
    v = sig.value
    return v.to_signed() if hasattr(v, "to_signed") else v.signed_integer


def uval(sig):
    return int(sig.value)


def to_bits(v, width):
    return int(v) & ((1 << width) - 1)


# --------------------------------------------- generic valid/ready transactors
async def drive_stream(clk, valid, ready, items, apply, rng=None, p_idle=0.0):
    """Send `items` over a valid/ready interface.

    apply(item) puts one item on the data signals. With p_idle > 0 random
    idle cycles (valid low) are inserted between items."""
    for item in items:
        while rng is not None and p_idle and rng.random() < p_idle:
            valid.value = 0
            await RisingEdge(clk)
        apply(item)
        valid.value = 1
        await RisingEdge(clk)
        while not int(ready.value):
            await RisingEdge(clk)
    valid.value = 0


async def collect_stream(clk, valid, ready, sample, done, rng=None, p_stall=0.0,
                         timeout=2_000_000):
    """Receive items until done(list) is True. sample() reads one item.
    With p_stall > 0, ready is randomly held low (backpressure)."""
    out = []
    for _ in range(timeout):
        ready.value = 0 if (rng is not None and p_stall and rng.random() < p_stall) else 1
        await RisingEdge(clk)
        if int(valid.value) and int(ready.value):
            out.append(sample())
            if done(out):
                ready.value = 0
                return out
    raise TimeoutError(f"collect_stream timed out after {timeout} cycles with {len(out)} items")
