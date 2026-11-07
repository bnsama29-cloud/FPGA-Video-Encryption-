"""nv_table_gen against software/neuro/feistel.py :: make_tables() (DESIGN §4.3.2): every written entry,
in fill order (table 0 first, index order), and the fill time in clocks."""
import cocotb
from cocotb.triggers import FallingEdge, RisingEdge

from common_nv import le, run_sim_nv
from common import start
from neuro import feistel, keys
from neuro.keys import nonce

MASTER = bytes(range(16))
SID = keys.session_id(3, 5, 0)
SK = keys.subkeys(MASTER, 3, 5, 0)


async def fill(dut, W, H, ctr, bank):
    dut.key.value = le(SK.perm)
    dut.nonce.value = le(nonce(SID, ctr, 0))
    dut.W.value, dut.H.value, dut.bank.value = W, H, bank
    await FallingEdge(dut.clk)
    dut.start.value = 1
    await FallingEdge(dut.clk)
    dut.start.value = 0
    writes, cyc = [], 0
    while True:
        await FallingEdge(dut.clk)
        cyc += 1
        if int(dut.tw_en.value):
            writes.append((int(dut.tw_bank.value), int(dut.tw_tab.value), int(dut.tw_addr.value),
                           int(dut.tw_data.value)))
        if int(dut.done.value):
            return writes, cyc
        assert cyc < 200000, "table fill did not finish"


@cocotb.test()
async def table_gen_matches_model(dut):
    dut.start.value = 0
    await start(dut)
    for (W, H, ctr, bank) in [(16, 16, 0, 0), (34, 34, 5, 1), (40, 23, 11, 0)]:
        writes, cyc = await fill(dut, W, H, ctr, bank)
        t = feistel.make_tables(SK.perm, SID, ctr, W, H)
        exp = [(bank, j, i, int(v)) for j in range(8) for i, v in enumerate(t.t[j].tolist())]
        assert len(writes) == len(exp), f"{W}x{H}: {len(writes)} writes, expected {len(exp)}"
        for k, (g, e) in enumerate(zip(writes, exp)):
            assert g == e, f"{W}x{H} ctr {ctr}: first mismatch at write {k}: got {g}, expected {e}"
        dut._log.info("fill %dx%d: %d entries in %d clk", W, H, len(exp), cyc)


def test_nv_table_gen():
    run_sim_nv("nv_table_gen", "test_nv_table_gen")
