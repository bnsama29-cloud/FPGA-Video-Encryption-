"""nv_feistel_walk (ablation N2b) against software/neuro/feistel.py :: permute_walk(domain="pow2").

Checks: every permuted word equals the model's cycle walk, bypass words leave unchanged, word order is kept
under random gaps and stalls, and the frozen clocks equal the cost model of experiments/neuro_walk_ablation.py:
SIDE_OVH + PASS_CLK * (calls - K) for every word that needs more than K passes.
"""
import os

import cocotb
from cocotb.triggers import FallingEdge, RisingEdge

from common_nv import run_sim_nv
from common import rng_for, start
from neuro import feistel, keys

MASTER = bytes(range(16))
SID = keys.session_id(3, 5, 0)
SK = keys.subkeys(MASTER, 3, 5, 0)
TW, TH = 40, 23                    # binary domain 64 x 32: about 2.2 passes per address
PASS_CLK, SIDE_OVH = 16, 1


async def load_tables(dut, tables, bank):
    for j, t in enumerate(tables.t):
        for i, v in enumerate(t.tolist()):
            dut.tw_en.value, dut.tw_bank.value, dut.tw_tab.value = 1, bank, j
            dut.tw_addr.value, dut.tw_data.value = i, v
            await RisingEdge(dut.clk)
    dut.tw_en.value = 0


@cocotb.test()
async def walk_bit_exact_in_order(dut):
    K = int(dut.K.value)
    rng = rng_for(dut)
    dut.in_valid.value = 0
    dut.tw_en.value = 0
    await start(dut)
    ctrs = (7, 8)
    for bank, c in enumerate(ctrs):
        tb, dom = feistel.walk_tables(SK.perm, SID, c, TW, TH, domain="pow2")
        assert dom == (64, 32)
        await load_tables(dut, tb, bank)

    n = 300
    exp, expected_stall = [], 0
    got, stalls = [], 0
    done = False

    async def collect():
        nonlocal stalls
        while not done:
            await FallingEdge(dut.clk)
            if int(dut.out_valid.value):
                got.append(int(dut.out_word.value))
            stalls += int(dut.stall.value)

    cocotb.start_soon(collect())
    i = 0
    offer = None
    while i < n:
        await FallingEdge(dut.clk)
        if offer is None:
            if rng.random() < 0.2:
                dut.in_valid.value = 0
                continue
            perm = rng.random() < 0.8
            x, y, hi = rng.randrange(TW), rng.randrange(TH), rng.randrange(1 << 10)
            word = (hi << 22) | (x << 11) | y if perm else rng.randrange(1 << 32)
            bank = rng.randrange(2)
            if perm:
                px, py, calls = feistel.permute_walk(x, y, SK.perm, SID, ctrs[bank], TW, TH, domain="pow2")
                e = (hi << 22) | (int(px) << 11) | int(py)
                c = int(calls)
                expected_stall += (SIDE_OVH + PASS_CLK * (c - K)) if c > K else 0
            else:
                e = word
            offer = (word, perm, bank, e)
            dut.in_valid.value, dut.in_word.value = 1, word
            dut.in_perm.value, dut.in_bank.value = int(perm), bank
        if int(dut.in_ready.value):          # accepted at the coming rising edge
            exp.append(offer)
            offer = None
            i += 1
    await FallingEdge(dut.clk)
    dut.in_valid.value = 0
    for _ in range(100000):
        if len(got) >= n:
            break
        await RisingEdge(dut.clk)
    done = True
    assert len(got) == n, f"{len(got)} of {n} words left the module"
    for k, ((w_in, perm, bank, e), g) in enumerate(zip(exp, got)):
        assert g == e, f"first mismatch at word {k}: input {w_in:08x} (perm {perm}, bank {bank}), got {g:08x}, expected {e:08x}"
    assert stalls == expected_stall, f"frozen clocks {stalls}, cost model {expected_stall} (K = {K})"
    dut._log.info(f"K = {K}: {n} words, {stalls} frozen clocks (model {expected_stall})")


def test_nv_feistel_walk_k2():
    run_sim_nv("nv_feistel_walk", "test_nv_feistel_walk", parameters={"W": TW, "H": TH, "K": 2}, build_tag="_k2")


def test_nv_feistel_walk_k4():
    run_sim_nv("nv_feistel_walk", "test_nv_feistel_walk", parameters={"W": TW, "H": TH, "K": 4}, build_tag="_k4")
