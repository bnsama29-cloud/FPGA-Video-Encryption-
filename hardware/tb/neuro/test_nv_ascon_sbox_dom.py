"""nv_ascon_sbox_dom (PROLEAD verification column) against the Ascon S-box.

Expected values come from the 5-bit Ascon S-box table of the specification (x0 is the most significant bit), which
tests/test_neuro_tvla_sim.py and software/model/ascon.py agree with through the full round. Every input, several random
splits and random refresh bits; the recombined output must equal S(x).
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

from common_nv import run_sim_nv
from common import rng_for

SBOX = [0x04, 0x0B, 0x1F, 0x14, 0x1A, 0x15, 0x09, 0x02, 0x1B, 0x05, 0x08, 0x12, 0x1D, 0x03, 0x06, 0x1C,
        0x1E, 0x13, 0x07, 0x0E, 0x00, 0x0D, 0x11, 0x18, 0x10, 0x0C, 0x01, 0x19, 0x16, 0x0A, 0x0F, 0x17]


def to_col(v):
    """Spec value (x0 = MSB) -> column bits (bit i = x_i)."""
    return sum(((v >> (4 - i)) & 1) << i for i in range(5))


@cocotb.test()
async def sbox_column_recombines(dut):
    rng = rng_for(dut)
    cocotb.start_soon(Clock(dut.clk, 10, "ns").start())
    await RisingEdge(dut.clk)
    for x in range(32):
        for _ in range(8):
            m = rng.getrandbits(5)
            await FallingEdge(dut.clk)
            dut.x_s0.value, dut.x_s1.value, dut.r.value = to_col(x) ^ m, m, rng.getrandbits(7)
            await RisingEdge(dut.clk)
            await FallingEdge(dut.clk)
            got = int(dut.y_s0.value) ^ int(dut.y_s1.value)
            exp = to_col(SBOX[x])
            assert got == exp, f"first mismatch: x={x:#04x} mask={m:#04x}: got {got:#04x}, expected {exp:#04x}"


def test_nv_ascon_sbox_dom():
    run_sim_nv("nv_ascon_sbox_dom", "test_nv_ascon_sbox_dom")
