"""Ascon-AEAD128 core vs the official NIST SP 800-232 known-answer tests.

Milestone M1 'done when': every KAT passes in simulation.
Default run: a representative subset (all AD/PT length edge cases).
FULL=1: all 1089 vectors.
"""
import cocotb
from cocotb.triggers import RisingEdge

from common import start, run_sim, full_run, rng_for, ROOT
from model import ascon

KAT_FILE = ROOT / "vectors" / "LWC_AEAD_KAT_128_128.txt"


def blocks_for(data, typ):
    """Split data into core blocks: full blocks, then a final block < 16 bytes."""
    out = []
    full = len(data) // 16 * 16
    for i in range(0, full, 16):
        out.append((data[i:i + 16], 16, typ, 0))
    out.append((data[full:], len(data) - full, typ, 1))
    return out


async def run_vector(dut, key, nonce, ad, pt, rng):
    dut.key.value = int.from_bytes(key, "little")
    dut.nonce.value = int.from_bytes(nonce, "little")
    dut.init.value = 1
    await RisingEdge(dut.clk)
    dut.init.value = 0
    blocks = (blocks_for(ad, 0) if ad else []) + blocks_for(pt, 1)
    ct, tag = bytearray(), None
    pending = list(blocks)
    expected_pt_bytes = []
    for _ in range(5000):
        # random idle cycles on the input side
        if pending and rng.random() > 0.3:
            data, n, typ, last = pending[0]
            dut.blk_data.value = int.from_bytes(data.ljust(16, b"\0"), "little")
            dut.blk_bytes.value = n
            dut.blk_type.value = typ
            dut.blk_last.value = last
            dut.blk_valid.value = 1
        else:
            dut.blk_valid.value = 0
        await RisingEdge(dut.clk)
        if int(dut.blk_valid.value) and int(dut.blk_ready.value):
            data, n, typ, last = pending.pop(0)
            if typ == 1:
                expected_pt_bytes.append(n)
        if int(dut.ct_valid.value):
            n = expected_pt_bytes.pop(0)
            ct += int(dut.ct_data.value).to_bytes(16, "little")[:n]
        if int(dut.tag_valid.value):
            tag = int(dut.tag.value).to_bytes(16, "little")
            break
    dut.blk_valid.value = 0
    assert tag is not None, "core never produced a tag"
    return bytes(ct) + tag


@cocotb.test()
async def ascon_kat(dut):
    """Official known-answer tests (Key/Nonce/AD/PT -> CT||tag)."""
    rng = rng_for(dut)
    dut.init.value = 0
    dut.blk_valid.value = 0
    await start(dut)
    vecs = ascon.parse_kat(KAT_FILE)
    if not full_run():
        # every AD length 0..33 with PT 0, every PT length 0..33 with AD 0,
        # plus the longest few vectors
        vecs = [v for v in vecs if (len(v["PT"]) == 0 or len(v["AD"]) == 0)
                and max(len(v["PT"]), len(v["AD"])) <= 33] + vecs[-5:]
    for v in vecs:
        got = await run_vector(dut, v["Key"], v["Nonce"], v["AD"], v["PT"], rng)
        assert got == v["CT"], (f"KAT Count={v['Count']} mismatch\n"
                                f"  AD={v['AD'].hex()} PT={v['PT'].hex()}\n"
                                f"  expected {v['CT'].hex()}\n  got      {got.hex()}")
    dut._log.info("%d known-answer tests passed", len(vecs))


@cocotb.test()
async def ascon_random_vs_model(dut):
    """Random key/nonce/AD/PT against the Python golden model."""
    rng = rng_for(dut)
    dut.init.value = 0
    dut.blk_valid.value = 0
    await start(dut)
    for _ in range(40 if full_run() else 12):
        key = bytes(rng.randrange(256) for _ in range(16))
        nonce = bytes(rng.randrange(256) for _ in range(16))
        ad = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 70)))
        pt = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 70)))
        got = await run_vector(dut, key, nonce, ad, pt, rng)
        assert got == ascon.encrypt(key, nonce, ad, pt)


def test_ascon_core():
    run_sim("ascon_aead128_core", "test_ascon_core")
