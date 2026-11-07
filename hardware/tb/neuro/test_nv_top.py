"""nv_top against software/neuro/sender.py :: Encryptor (DESIGN §6, §7.2): the cases of software/neuro/vectors.py.

Every case is played on the model first (neuro.vectors.run_model) and then on the RTL through AXI-Lite and
AXI-Stream, as the ARM would: write the shadow set, COMMIT with ENABLE = 0 (fresh start), ENABLE, stream the words
with random input gaps, COMMIT at the resolved COMMIT_AT (only after every word of the previous step has been
accepted, which is when the model's commit happens), FLUSH. The output is taken with random tready.
Checks: every output word and tlast (first mismatch reported with its packet), every commit's CFG_CODE, the
counters after SNAP (PKTS, WORDS_IN, WORDS_OUT, ERR_*), and the FIFO overflow flag.
FULL=1 adds every geometry x level case.
"""
import json
import os

import cocotb
from cocotb.triggers import FallingEdge, RisingEdge, Timer
from cocotbext.axi import AxiLiteBus, AxiLiteMaster

from common_nv import le, run_sim_nv
from common import rng_for, start
from neuro import vectors as V

CTRL, STATUS, MODE, GEOM, T_US = 0x04, 0x08, 0x0C, 0x10, 0x14
SID_LO, SID_HI, CTR0_LO, CTR0_HI, PAD_MIN, PAD_CAP, MAX_GAP = 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30
AT_LO, AT_HI, CFG_CODE, VERSION = 0x34, 0x38, 0x3C, 0x00
K_BASE = {"tag": 0x40, "pol": 0x50, "perm": 0x60, "dum": 0x70, "aead": 0x80}
COUNTERS = {"PKTS": 0xA8, "WORDS_IN": 0xB0, "WORDS_OUT": 0xB8}
ERRS = {"ERR_RANGE": 0xD8, "ERR_ORDER": 0xDC, "ERR_PRE_TH": 0xE0, "ERR_JUMP": 0xE4, "ERR_PADOVF": 0xE8,
        "ERR_CFG": 0xEC}
EN, SRST, FLUSH, COMMIT, SNAP = 1, 2, 4, 8, 16


class Dut:
    def __init__(self, dut, rng):
        self.dut, self.rng = dut, rng
        self.regs = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axil"), dut.clk, dut.rst)
        self.queue, self.out = [], []
        self.accepted = 0

    async def wr(self, a, v):
        await self.regs.write_dword(a, v & 0xFFFFFFFF)

    async def rd(self, a):
        return await self.regs.read_dword(a)

    async def shadow(self, s):
        mode = (s["level"] | (s["ts_bits"] << 4) | ((s["pad_kind"] != 0) << 8) | (s["pad_kind"] << 9)
                | (s["jump_mode"] << 12))
        for a, v in [(MODE, mode), (GEOM, s["W"] | (s["H"] << 16)), (T_US, s["T_us"]), (SID_LO, s["sid"]),
                     (SID_HI, s["sid"] >> 32), (CTR0_LO, s["ctr0"]), (CTR0_HI, s["ctr0"] >> 32),
                     (PAD_MIN, s["pad_min"]), (PAD_CAP, s["pad_cap"]), (MAX_GAP, s["max_gap_us"])]:
            await self.wr(a, v)
        sk = V.subkeys_for(s["epoch"])
        for name, base in K_BASE.items():
            k = le(getattr(sk, name))
            for i in range(4):
                await self.wr(base + 4 * i, k >> (32 * i))

    async def feeder(self):
        d = self.dut
        while True:
            await FallingEdge(d.clk)
            if self.queue and self.rng.random() < 0.85:
                d.s_axis_tvalid.value, d.s_axis_tdata.value = 1, self.queue[0]
                while True:
                    await RisingEdge(d.clk)
                    if int(d.s_axis_tready.value):
                        self.queue.pop(0)
                        self.accepted += 1
                        break
                d.s_axis_tvalid.value = 0
            else:
                d.s_axis_tvalid.value = 0

    async def sink(self):
        d = self.dut
        while True:
            await FallingEdge(d.clk)
            d.m_axis_tready.value = int(self.rng.random() < 0.75)
            await RisingEdge(d.clk)
            if int(d.m_axis_tvalid.value) and int(d.m_axis_tready.value):
                self.out.append((int(d.m_axis_tdata.value), int(d.m_axis_tlast.value)))

    async def wait_for(self, cond, limit, what):
        for _ in range(limit):
            if cond():
                return
            await RisingEdge(self.dut.clk)
        raise AssertionError(f"timeout waiting for {what}")


async def run_case(d, case):
    ref = V.run_model(case)
    d.out.clear()
    d.dut.rst.value = 1                            # power-on reset: LAST_SID / LAST_CTR survive SOFT_RST
    for _ in range(5):
        await RisingEdge(d.dut.clk)
    d.dut.rst.value = 0
    await RisingEdge(d.dut.clk)
    await d.shadow(ref["initial"])
    await d.wr(CTRL, COMMIT)                       # ENABLE = 0: fresh start at CTR0
    assert await d.rd(CFG_CODE) == 0, f"{case.name}: initial commit refused"
    await d.wr(CTRL, EN)
    for i, s in enumerate(ref["steps"]):
        if s["op"] == "push":
            d.queue.extend(s["words"])
            if s["halts"]:
                for _ in range(200000):
                    if (await d.rd(STATUS)) & 0x40:
                        break
                else:
                    raise AssertionError(f"{case.name} step {i}: JUMP_HALT never set")
            else:
                await d.wait_for(lambda: not d.queue, 400000, f"{case.name} step {i}: input accepted")
            for _ in range(4):
                await RisingEdge(d.dut.clk)
        elif s["op"] == "flush":
            await d.wr(CTRL, EN | FLUSH)
        else:
            await d.shadow(s["shadow"])
            await d.wr(AT_LO, s["at"])
            await d.wr(AT_HI, s["at"] >> 32)
            await d.wr(CTRL, EN | COMMIT)
            code = await d.rd(CFG_CODE)
            assert code == s["expect"], f"{case.name} step {i}: commit at {s['at']} gave code {code}, model {s['expect']}"
            if s["expect"] == 0 and d.queue:       # a resume: the held words go on
                await d.wait_for(lambda: not d.queue, 400000, f"{case.name} step {i}: held words accepted")
    exp = ref["out"]
    await d.wait_for(lambda: len(d.out) >= len(exp), 2_000_000, f"{case.name}: {len(exp)} output words")
    for _ in range(50):
        await RisingEdge(d.dut.clk)
    got = d.out
    pkt = 0
    for k, (g, e) in enumerate(zip(got, exp)):
        assert g == e, (f"{case.name}: first mismatch at output word {k} (packet {pkt}): got {g[0]:08x} "
                        f"last={g[1]}, expected {e[0]:08x} last={e[1]}")
        pkt += e[1]
    assert len(got) == len(exp), f"{case.name}: {len(got)} output words, expected {len(exp)}"
    assert not int(d.dut.fifo_overflow.value), f"{case.name}: FIFO overflow"
    await d.wr(CTRL, EN | SNAP)
    c = ref["counters"]
    for name, a in COUNTERS.items():
        v = (await d.rd(a)) | ((await d.rd(a + 4)) << 32)
        assert v == c[name], f"{case.name}: {name} = {v}, model {c[name]}"
    for name, a in ERRS.items():
        v = await d.rd(a)
        assert v == c[name], f"{case.name}: {name} = {v}, model {c[name]}"
    cycles = (await d.rd(0xC0)) | ((await d.rd(0xC4)) << 32)
    d.dut._log.info("%-22s ok: %d packets, %d words, %d clk", case.name, ref["packets"], len(exp), cycles)
    rep = os.getenv("NV_REPORT")
    if rep:                                        # experiments/neuro_rtl_exact.py (N1) collects these
        with open(rep, "a", encoding="utf-8") as f:
            f.write(json.dumps({"case": case.name, "packets": ref["packets"], "words_out": len(exp),
                                "words_in": c["WORDS_IN"], "cycles": cycles,
                                "seed": os.getenv("SEED")}) + "\n")


@cocotb.test()
async def top_matches_model(dut):
    rng = rng_for(dut)
    dut.s_axis_tvalid.value = 0
    dut.s_axis_tdata.value = 0
    dut.m_axis_tready.value = 1
    await start(dut, cycles=10)
    d = Dut(dut, rng)
    v = await d.rd(VERSION)
    assert v >> 8 == 0x4E5601, f"VERSION {v:08x}"
    cocotb.start_soon(d.feeder())
    cocotb.start_soon(d.sink())
    only = os.getenv("NV_CASE")
    for case in V.cases(full=os.getenv("FULL", "0") == "1"):
        if only and case.name != only:
            continue
        await run_case(d, case)


def test_nv_top():
    run_sim_nv("nv_top", "test_nv_top", parameters={"U": 2, "PAD": 1, "MAX_CD": V.MAX_CD_TB, "BM_AW": 3})
