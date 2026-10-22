"""Hardware tamper injector (future_work/board/axis_tamper.v) for the board-day attack demonstration.

Random scan-like frames (with 0xFF00 stuffing and RST markers), random valid gaps and backpressure.
Checks: nothing changes while SW1 (enable) is off; a trigger pulse changes exactly one bit of the next
frame that has a safe beat; continuous mode changes one bit of every such frame; marker bytes are never
touched; valid / ready / last / keep pass through; the counter equals the number of changed frames.
"""
import cocotb
from cocotb.triggers import FallingEdge, RisingEdge, ClockCycles

from common import start, run_sim, rng_for


def make_frame(rng, nbytes):
    out = bytearray()
    while len(out) < nbytes:
        r = rng.random()
        if r < 0.05:
            out += b"\xff\x00"                       # stuffed 0xFF
        elif r < 0.08:
            out += bytes([0xFF, 0xD0 + rng.randrange(8)])  # restart marker
        else:
            out.append(rng.randrange(0xFF))
    return bytes(out[:nbytes])


def beats(frame):
    out = []
    for i in range(0, len(frame), 4):
        chunk = frame[i:i + 4]
        out.append((int.from_bytes(chunk.ljust(4, b"\0"), "little"), (1 << len(chunk)) - 1,
                    int(i + 4 >= len(frame))))
    return out


async def send_frame(dut, rng, frame):
    """Drive one frame (inputs set at the falling edge), return the output bytes seen at each handshake."""
    got = bytearray()
    todo = beats(frame)
    k = 0
    while k < len(todo):
        await FallingEdge(dut.clk)
        valid = rng.random() > 0.2
        d, keep, last = todo[k]
        dut.s_axis_tvalid.value = int(valid)
        dut.s_axis_tdata.value = d if valid else rng.randrange(1 << 32)
        dut.s_axis_tkeep.value = keep
        dut.s_axis_tlast.value = last if valid else rng.randrange(2)
        dut.m_axis_tready.value = int(rng.random() > 0.3)
        await RisingEdge(dut.clk)
        if int(dut.m_axis_tvalid.value) != valid or int(dut.s_axis_tready.value) != int(dut.m_axis_tready.value):
            raise AssertionError("valid / ready must pass through unchanged")
        if valid and int(dut.m_axis_tready.value):
            assert int(dut.m_axis_tkeep.value) == keep and int(dut.m_axis_tlast.value) == last, \
                f"keep/last changed at beat {k}"
            got += int(dut.m_axis_tdata.value).to_bytes(4, "little")[:bin(keep).count("1")]
            k += 1
    await FallingEdge(dut.clk)
    dut.s_axis_tvalid.value = 0
    return bytes(got)


async def gap(dut, n=12, trig=False):
    await FallingEdge(dut.clk)
    if trig:
        dut.pmod_trig.value = 1
        await ClockCycles(dut.clk, 3)
        await FallingEdge(dut.clk)
        dut.pmod_trig.value = 0
    await ClockCycles(dut.clk, n)


def diff(frame, got, fi):
    d = [(i, a ^ b) for i, (a, b) in enumerate(zip(frame, got)) if a != b]
    assert len(got) == len(frame), f"frame {fi}: length {len(got)} != {len(frame)}"
    for i, x in d:
        assert bin(x).count("1") == 1, f"frame {fi}: byte {i} changed in more than one bit ({x:#04x})"
        assert i % 4 == 0 and i >= 4, f"frame {fi}: byte {i} is not byte 0 of a later beat"
        assert frame[i] != 0xFF and got[i] != 0xFF and frame[i - 1] != 0xFF, \
            f"frame {fi}: marker byte touched at {i}: {frame[i - 1]:#04x} {frame[i]:#04x} -> {got[i]:#04x}"
    assert len(d) <= 1, f"frame {fi}: {len(d)} bytes changed (index, xor) {d}"
    return len(d)


@cocotb.test()
async def tamper_injector(dut):
    rng = rng_for(dut)
    for s in ("s_axis_tvalid", "s_axis_tdata", "s_axis_tkeep", "s_axis_tlast", "m_axis_tready", "pmod_trig"):
        getattr(dut, s).value = 0
    dut.btn.value = 0
    dut.sw.value = 0
    await start(dut)
    changed_total = 0

    # 1. disabled: continuous on, triggers fired, SW1 down -> nothing changes
    dut.sw.value = 0b01
    for fi in range(6):
        await gap(dut, trig=True)
        f = make_frame(rng, rng.randint(4, 400))
        assert diff(f, await send_frame(dut, rng, f), fi) == 0, f"frame {fi} changed while SW1 was off"

    # 2. enabled, one shot per trigger; the shot waits when a frame has no safe beat
    dut.sw.value = 0b10
    pending = 0
    for fi in range(40):
        t = rng.random() < 0.5
        await gap(dut, trig=t)
        pending = pending or t
        f = make_frame(rng, rng.choice([3, rng.randint(5, 600)]))
        n = diff(f, await send_frame(dut, rng, f), fi)
        if not pending:
            assert n == 0, f"frame {fi} changed without a trigger"
        elif len(f) >= 100:
            # beats 1..15 are targets and every later beat is tried until byte 0 is safe: a long frame
            # always has one (a short one may not: the shot then waits for the next frame)
            assert n == 1, f"frame {fi} ({len(f)} bytes): trigger pending, nothing changed"
        if n:
            pending = 0
        changed_total += n
    await ClockCycles(dut.clk, 2)
    assert int(dut.tampered_frames.value) == changed_total, \
        f"counter {int(dut.tampered_frames.value)} != frames changed {changed_total}"

    # 3. continuous: every frame with a safe beat changes in exactly one bit
    dut.sw.value = 0b11
    for fi in range(20):
        await gap(dut)
        f = make_frame(rng, rng.randint(60, 900))
        n = diff(f, await send_frame(dut, rng, f), fi)
        assert n == 1, f"continuous mode: frame {fi} ({len(f)} bytes) not changed"
        changed_total += n
    await ClockCycles(dut.clk, 2)
    assert int(dut.tampered_frames.value) == changed_total
    assert int(dut.led.value) & 0b0101 == 0b0101, "LED0 (enabled) and LED2 (continuous) must be on"


def test_axis_tamper():
    run_sim("axis_tamper", "test_axis_tamper", testcase="tamper_injector")
