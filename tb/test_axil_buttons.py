"""BTN1..BTN3 peripheral (system/board/axil_buttons.v) of the tamper overlay: the ARM reads presses and
changes the protection level through the sender's "mode" command (board_sender.py :: ButtonLevels).

Random press sequences with contact bounce, glitches shorter than the debounce time, BTN0 activity and AXI
writes. Checks: ID, STATE follows the debounced buttons, COUNT rises by exactly one per real press of
BTN1..BTN3 (none for a glitch, none for BTN0), writes are acknowledged and change nothing.
"""
import cocotb
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge

from common import rng_for, run_sim, start

DEB = 16                                              # DEBOUNCE parameter of this build


async def axil_read(dut, addr):
    await FallingEdge(dut.clk)
    dut.s_axil_araddr.value = addr
    dut.s_axil_arvalid.value = 1
    dut.s_axil_rready.value = 1
    while True:
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
        if int(dut.s_axil_arready.value) == 0 or int(dut.s_axil_rvalid.value):
            dut.s_axil_arvalid.value = 0
        if int(dut.s_axil_rvalid.value):
            v = int(dut.s_axil_rdata.value)
            assert int(dut.s_axil_rresp.value) == 0
            await RisingEdge(dut.clk)
            await FallingEdge(dut.clk)
            dut.s_axil_rready.value = 0
            return v


async def axil_write(dut, addr, data):
    await FallingEdge(dut.clk)
    dut.s_axil_awaddr.value = addr
    dut.s_axil_wdata.value = data
    dut.s_axil_wstrb.value = 0xF
    dut.s_axil_awvalid.value = 1
    dut.s_axil_wvalid.value = 1
    dut.s_axil_bready.value = 1
    for _ in range(20):
        await RisingEdge(dut.clk)
        took = int(dut.s_axil_awready.value)
        await FallingEdge(dut.clk)
        if took:
            dut.s_axil_awvalid.value = 0
            dut.s_axil_wvalid.value = 0
        if int(dut.s_axil_bvalid.value):
            assert int(dut.s_axil_bresp.value) == 0
            await FallingEdge(dut.clk)
            dut.s_axil_bready.value = 0
            return
    raise AssertionError(f"write to 0x{addr:x} never answered")


async def hold(dut, value, cycles):
    await FallingEdge(dut.clk)
    dut.btn.value = value
    await ClockCycles(dut.clk, cycles)


async def bounce(dut, rng, base, bit):
    """Contact bounce around a change of one button: short random toggles, each shorter than DEB."""
    for _ in range(rng.randrange(1, 5)):
        await hold(dut, base ^ bit, rng.randrange(1, DEB - 4))
        await hold(dut, base, rng.randrange(1, DEB - 4))


@cocotb.test()
async def buttons(dut):
    rng = rng_for(dut)
    for s in ("s_axil_arvalid", "s_axil_rready", "s_axil_awvalid", "s_axil_wvalid", "s_axil_bready",
              "s_axil_araddr", "s_axil_awaddr", "s_axil_wdata", "s_axil_wstrb", "s_axil_awprot",
              "s_axil_arprot", "btn"):
        getattr(dut, s).value = 0
    await start(dut)
    got = await axil_read(dut, 0x0)
    assert got == 0xB7750001, f"ID: got 0x{got:08x}, expected 0xB7750001"
    want = [0, 0, 0]
    for step in range(60):
        b = rng.randrange(4)                           # 0 = BTN0 (must be ignored), 1..3 = BTN1..BTN3
        bit = 1 << b
        kind = rng.choice(["press", "press", "glitch", "write"])
        if kind == "write":
            before = await axil_read(dut, 0x8)
            await axil_write(dut, rng.choice([0x0, 0x4, 0x8]), rng.randrange(1 << 32))
            after = await axil_read(dut, 0x8)
            assert after == before, f"step {step}: a write changed COUNT 0x{before:06x} -> 0x{after:06x}"
            continue
        if kind == "glitch":
            await hold(dut, bit, rng.randrange(1, DEB - 4))
            await hold(dut, 0, DEB + 4)
        else:
            await bounce(dut, rng, 0, bit)
            await hold(dut, bit, DEB + 6)
            state = await axil_read(dut, 0x4)
            exp_state = (bit >> 1) & 7
            assert state == exp_state, f"step {step}: BTN{b} held, STATE got {state:03b}, expected {exp_state:03b}"
            await bounce(dut, rng, bit, bit)
            await hold(dut, 0, DEB + 6)
            if b:
                want[b - 1] = (want[b - 1] + 1) & 0xFF
        cnt = await axil_read(dut, 0x8)
        got = [cnt & 0xFF, (cnt >> 8) & 0xFF, (cnt >> 16) & 0xFF]
        state = await axil_read(dut, 0x4)
        assert got == want and state == 0, \
            f"step {step} ({kind} BTN{b}): COUNT got {got}, expected {want}; STATE {state:03b} (expected 000)"
    dut._log.info("presses counted %s", want)


def test_axil_buttons():
    run_sim("axil_buttons", "test_axil_buttons", parameters={"DEBOUNCE": DEB}, testcase="buttons")
