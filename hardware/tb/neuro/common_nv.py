"""cocotb runner for the paper-2 RTL (hardware/rtl/neuro/), mirroring hardware/tb/common.py without editing it.

Paper-1 files reused unchanged: ascon_round.v, ascon_aead128_core.v, keystream_gen.v, skid_buf.v.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RTL = ROOT / "hardware" / "rtl"
NV = RTL / "neuro"
sys.path[:0] = [str(ROOT), str(ROOT / "software"), str(ROOT / "hardware" / "tb")]

KS = [RTL / "ascon_round.v", RTL / "ascon_aead128_core.v", RTL / "keystream_gen.v"]
SOURCES_NV = {
    "nv_feistel": [NV / "nv_sdp_ram.v", NV / "nv_feistel.v"],
    "nv_table_gen": KS + [NV / "nv_table_gen.v"],
    "nv_xor": KS + [NV / "nv_xor.v"],
}


def run_sim_nv(toplevel, test_module, parameters=None, testcase=None, build_tag=""):
    from cocotb_tools.runner import get_results, get_runner
    sim = os.getenv("SIM", "icarus")
    waves = os.getenv("WAVES", "0") == "1"
    build_dir = ROOT / "sim_build" / ("nv_" + toplevel.removeprefix("nv_") + build_tag)
    runner = get_runner(sim)
    runner.build(sources=SOURCES_NV[toplevel], includes=[RTL / "include"], hdl_toplevel=toplevel,
                 build_dir=build_dir, parameters=parameters or {}, timescale=("1ns", "1ps"), waves=waves,
                 always=True)
    xml = runner.test(hdl_toplevel=toplevel, test_module=test_module, test_dir=Path(__file__).resolve().parent,
                      build_dir=build_dir, waves=waves, testcase=testcase, seed=os.getenv("SEED"),
                      extra_env={"PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "software"),
                                                                str(ROOT / "hardware" / "tb"),
                                                                os.getenv("PYTHONPATH", "")])})
    total, failed = get_results(xml)
    assert failed == 0, f"{failed} of {total} cocotb tests failed in {toplevel} (see log above)"


def le(b):
    """16-byte key or nonce -> 128-bit port value (byte 0 in [7:0], paper-1 convention)."""
    return int.from_bytes(bytes(b), "little")
