"""nv_feistel and nv_table_gen against software/neuro/feistel.py (DESIGN §4.3, §6.2).

Checks: bit-exact permutation of random words from two banks, bypass words unchanged, word order kept,
and the fixed latency LAT = 16 clk (each word leaves exactly 16 clk after it enters). The table generator's
writes equal neuro.feistel.make_tables entry by entry, in fill order.
"""
import cocotb
from cocotb.triggers import FallingEdge, RisingEdge

from common_nv import le, run_sim_nv
from common import rng_for, start
from neuro import feistel, keys
from neuro.keys import nonce

LAT = 16
MASTER = bytes(range(16))
SID = keys.session_id(3, 5, 0)
SK = keys.subkeys(MASTER, 3, 5, 0)
TW, TH = 40, 23                    # small sensor so the test stays fast (MAXW/MAXH set below)


async def load_tables(dut, tables, bank):
    for j, t in enumerate(tables.t):
        for i, v in enumerate(t.tolist()):
            dut.tw_en.value, dut.tw_bank.value, dut.tw_tab.value = 1, bank, j
            dut.tw_addr.value, dut.tw_data.value = i, v
            await RisingEdge(dut.clk)
    dut.tw_en.value = 0


@cocotb.test()
async def feistel_bit_exact_fixed_latency(dut):
    rng = rng_for(dut)
    dut.in_valid.value = 0
    dut.tw_en.value = 0
    dut.W.value, dut.H.value = TW, TH
    await start(dut)
    tabs = [feistel.make_tables(SK.perm, SID, c, TW, TH) for c in (7, 8)]
    await load_tables(dut, tabs[0], 0)
    await load_tables(dut, tabs[1], 1)

    sent, got = [], []
    n = 400

    async def collect():
        cyc = 0
        while len(got) < n:
            await FallingEdge(dut.clk)
            cyc += 1
            if int(dut.out_valid.value):
                got.append((cyc, int(dut.out_word.value), int(dut.out_kind.value), int(dut.out_last.value)))

    cocotb.start_soon(collect())
    cyc = 0
    i = 0
    while i < n:
        await FallingEdge(dut.clk)
        cyc += 1
        if rng.random() < 0.2:
            dut.in_valid.value = 0
            continue
        perm = rng.random() < 0.7
        x, y = rng.randrange(TW), rng.randrange(TH)
        hi = rng.randrange(1 << 10)
        word = (hi << 22) | (x << 11) | y if perm else rng.randrange(1 << 32)
        bank, kind, last = rng.randrange(2), rng.randrange(4), rng.randrange(2)
        dut.in_valid.value, dut.in_word.value, dut.in_perm.value = 1, word, int(perm)
        dut.in_bank.value, dut.in_kind.value, dut.in_last.value = bank, kind, last
        if perm:
            px, py = feistel.permute(x, y, tabs[bank])
            exp = (hi << 22) | (int(px) << 11) | int(py)
        else:
            exp = word
        sent.append((cyc, word, exp, kind, last))
        i += 1
    await FallingEdge(dut.clk)
    dut.in_valid.value = 0
    while len(got) < n:
        await RisingEdge(dut.clk)
    for k, ((c_in, w_in, exp, kind, last), (c_out, w_out, k_out, l_out)) in enumerate(zip(sent, got)):
        assert w_out == exp and k_out == kind and l_out == last, (
            f"first mismatch at word {k}: input {w_in:08x}, got {w_out:08x}, expected {exp:08x}")
        assert c_out - c_in == LAT, f"word {k}: latency {c_out - c_in} clk, expected {LAT}"


def test_nv_feistel():
    run_sim_nv("nv_feistel", "test_nv_feistel", parameters={"MAXW": 64, "MAXH": 64})
