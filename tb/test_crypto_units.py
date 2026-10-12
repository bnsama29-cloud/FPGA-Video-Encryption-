"""Keystream generator and per-frame tag unit vs the golden model.

Edge cases (project doc 14.2): different nonces -> different keystreams,
restart mid-stream, AD lengths 26 + (1..120) incl. exact multiples of 16.
The tag AD is the 26-byte header prefix (latched at start) followed by the
scan bytes (contract v2).
"""
import cocotb
from cocotb.triggers import RisingEdge, FallingEdge

from common import start, run_sim, rng_for
from model import ascon


async def pulse_start(dut, key, nonce, prefix=None):
    if prefix is not None:
        dut.ad_prefix.value = int.from_bytes(prefix, "little")   # byte 0 in [7:0]
    dut.key.value = int.from_bytes(key, "little")
    dut.nonce.value = int.from_bytes(nonce, "little")
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0


async def take_bits(dut, nbits, rng):
    """Consume nbits through the window port in random chunk sizes.
    Decisions are made at the falling edge, when all outputs are settled."""
    got = []
    for _ in range(100_000):
        if len(got) >= nbits:
            break
        await FallingEdge(dut.clk)
        avail = int(dut.ks_avail.value)
        n = min(rng.randint(1, 12), nbits - len(got))
        window = int(dut.ks_bits.value)
        if avail >= n and rng.random() > 0.2:
            dut.ks_take.value = 1
            dut.ks_n.value = n
            got.extend((window >> i) & 1 for i in range(n))
        else:
            dut.ks_take.value = 0
        await RisingEdge(dut.clk)
    dut.ks_take.value = 0
    await RisingEdge(dut.clk)
    return got


@cocotb.test()
async def keystream_matches_model(dut):
    rng = rng_for(dut)
    dut.start.value = 0
    dut.ks_take.value = 0
    await start(dut)
    key = bytes(range(16))
    seen = set()
    for frame in range(4):
        nonce = ascon.make_nonce(0xABCD_0000_1234_5678, frame + (1 << 40), 0)
        await pulse_start(dut, key, nonce)
        await RisingEdge(dut.clk)
        nbits = 700 if frame < 3 else 37          # frame 3: restart early
        got = await take_bits(dut, nbits, rng)
        exp = ascon.keystream_bits(key, nonce, nbits)
        assert got == exp, f"frame {frame}: first mismatch at bit {next(i for i in range(nbits) if got[i] != exp[i])}"
        seen.add(tuple(got[:128]))
    assert len(seen) == 4, "different nonces must give different keystreams"


@cocotb.test()
async def tag_matches_model(dut):
    rng = rng_for(dut)
    dut.start.value = 0
    dut.ad_valid.value = 0
    await start(dut)
    key = bytes(rng.randrange(256) for _ in range(16))
    lengths = [1, 5, 6, 7, 15, 16, 17, 22, 38, 100]   # 26+6 = 32, 26+22 = 48 + [rng.randint(1, 120) for _ in range(6)]
    for frame, n in enumerate(lengths):
        nonce = ascon.make_nonce(7, frame, 1)
        data = bytes(rng.randrange(256) for _ in range(n))
        prefix = bytes(rng.randrange(256) for _ in range(26))
        await pulse_start(dut, key, nonce, prefix)
        dut.ad_prefix.value = 0          # must have been latched at start
        i = 0
        while i < n:
            if rng.random() < 0.3:
                dut.ad_valid.value = 0
            else:
                dut.ad_valid.value = 1
                dut.ad_data.value = data[i]
                dut.ad_last.value = int(i == n - 1)
            await RisingEdge(dut.clk)
            if int(dut.ad_valid.value) and int(dut.ad_ready.value):
                i += 1
        dut.ad_valid.value = 0
        for _ in range(200):
            await RisingEdge(dut.clk)
            if int(dut.tag_valid.value):
                break
        assert int(dut.tag_valid.value), f"no tag for length {n}"
        got = int(dut.tag.value).to_bytes(16, "little")
        assert got == ascon.mac(key, nonce, prefix + data), f"tag mismatch for AD length 26+{n}"


def test_keystream_gen():
    run_sim("keystream_gen", "test_crypto_units", testcase="keystream_matches_model")


def test_tag_unit():
    run_sim("tag_unit", "test_crypto_units", testcase="tag_matches_model")
