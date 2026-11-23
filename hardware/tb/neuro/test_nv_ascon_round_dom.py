"""nv_ascon_round_dom (masking-cost ablation) against software/model/ascon.py :: permutation().

Checks: twelve masked rounds, one per clock with fresh randomness and a fresh random split of the input, recombine
to Ascon-p[12] of the model; the shares themselves differ from the unmasked state (the sharing is not degenerate).
Functional check only: side-channel security is not evaluated.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

from common_nv import run_sim_nv
from common import rng_for
from model import ascon


def pack(S):
    return sum(w << (64 * i) for i, w in enumerate(S))


def unpack(v):
    return [(v >> (64 * i)) & ((1 << 64) - 1) for i in range(5)]


@cocotb.test()
async def dom_rounds_recombine_to_p12(dut):
    rng = rng_for(dut)
    dut.s0_in.value, dut.s1_in.value, dut.rc.value, dut.rnd.value = 0, 0, 0, 0
    cocotb.start_soon(Clock(dut.clk, 10, "ns").start())      # no reset: the round has no state but its registers
    await RisingEdge(dut.clk)
    for trial in range(20):
        S = [rng.getrandbits(64) for _ in range(5)]
        exp = list(S)
        ascon.permutation(exp, 12)
        m = rng.getrandbits(320)
        s0, s1 = pack(S) ^ m, m
        differs = False
        for r in range(12):
            await FallingEdge(dut.clk)
            dut.s0_in.value, dut.s1_in.value = s0, s1
            dut.rc.value = ((0xF - r) << 4) | r
            dut.rnd.value = rng.getrandbits(320)
            await RisingEdge(dut.clk)
            await FallingEdge(dut.clk)
            s0, s1 = int(dut.s0_out.value), int(dut.s1_out.value)
            differs |= s1 != 0 and s0 != (s0 ^ s1)
        got = unpack(s0 ^ s1)
        assert got == exp, (f"trial {trial}: first mismatch at word "
                            f"{next(i for i in range(5) if got[i] != exp[i])}: input {[hex(w) for w in S]}, "
                            f"got {[hex(w) for w in got]}, expected {[hex(w) for w in exp]}")
        assert differs, f"trial {trial}: a share equals the unmasked state"


def test_nv_ascon_round_dom():
    run_sim_nv("nv_ascon_round_dom", "test_nv_ascon_round_dom")
