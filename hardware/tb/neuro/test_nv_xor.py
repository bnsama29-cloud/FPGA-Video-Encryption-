"""nv_xor against software/neuro/levels.py :: xor_fields() (DESIGN §4.2): random input gaps, random output
backpressure, b in {0 (V1), 1, 6 (V3)}, keystream restart per packet; no word lost, duplicated or reordered."""
import cocotb
from cocotb.triggers import FallingEdge, RisingEdge, Timer
import numpy as np

from common_nv import le, run_sim_nv
from common import rng_for, start
from model import ascon
from neuro import keys, levels
from neuro.keys import nonce

MASTER = bytes(range(16))
SID = keys.session_id(3, 5, 0)
SK = keys.subkeys(MASTER, 3, 5, 0)


async def one_packet(dut, rng, ctr, b, n=150):
    dut.key.value = le(SK.pol)
    dut.nonce.value = le(nonce(SID, ctr, 0))
    dut.b.value = b
    await FallingEdge(dut.clk)
    dut.start.value = 1
    await FallingEdge(dut.clk)
    dut.start.value = 0
    words = [rng.randrange(1 << 32) for _ in range(n)]
    xm = [rng.random() < 0.7 for _ in range(n)]
    exp = levels.xor_fields(np.array(words, np.uint32), np.array(xm), ascon.Keystream(SK.pol, nonce(SID, ctr, 0)),
                            b).tolist()
    got, i, holding = [], 0, False
    dut.in_valid.value = 0
    guard = 0
    while len(got) < n:
        await FallingEdge(dut.clk)
        guard += 1
        assert guard < 50 * n, f"packet ctr {ctr}: stuck after {len(got)} of {n} words"
        # drive this cycle's signals; they are sampled at the next rising edge
        dut.out_ready.value = int(rng.random() < 0.7)
        if i < n and (holding or rng.random() < 0.85):
            dut.in_valid.value, dut.in_word.value, dut.in_xor.value, dut.in_meta.value = 1, words[i], xm[i], i & 0xFF
            holding = True                            # valid stays up until the word is taken
        else:
            dut.in_valid.value = 0
        await Timer(1, "ns")                          # let in_ready (combinational in out_ready) settle
        if int(dut.out_valid.value) and int(dut.out_ready.value):
            got.append((int(dut.out_word.value), int(dut.out_meta.value)))
        if i < n and holding and int(dut.in_ready.value):
            i += 1
            holding = False
    for k, ((w, m), e) in enumerate(zip(got, exp)):
        assert m == (k & 0xFF), f"packet ctr {ctr}: word order broken at {k} (meta {m})"
        assert w == e, f"packet ctr {ctr}, b={b}: first mismatch at word {k}: input {words[k]:08x}, got {w:08x}, expected {e:08x}"


@cocotb.test()
async def xor_matches_model_with_backpressure(dut):
    rng = rng_for(dut)
    dut.start.value = 0
    dut.in_valid.value = 0
    dut.out_ready.value = 1
    await start(dut)
    for ctr, b in [(0, 0), (1, 6), (2, 1), (3, 6)]:
        await one_packet(dut, rng, ctr, b)
        # drain: let the output register empty before the next restart
        dut.in_valid.value = 0
        dut.out_ready.value = 1
        for _ in range(3):
            await RisingEdge(dut.clk)


def test_nv_xor():
    run_sim_nv("nv_xor", "test_nv_xor")
