"""Zig-zag/run-length, selective encryption and Huffman+packer vs the model
(milestone M3 and the encryption half of M5).

Edge cases from the project plan (section 14.2):
  run-length : all-zero AC (EOB only), 16+ zeros (ZRL), 62 zeros then a
               non-zero last coefficient (no EOB), DC differences across
               blocks and components, back-to-back blocks
  encryption : mode off == identity, every mode E1..E4, blocks with no
               non-zero AC, keystream starvation (avail < needed)
  huffman    : every code length, 0xFF stuffing, final-byte padding with 1s
"""
import cocotb
from cocotb.triggers import RisingEdge, FallingEdge, ReadOnly

from common import start, run_sim, rng_for, drive_stream, collect_stream, full_run
from model import hw as J, ascon
from model.testimage import make_image

SYM_FIELDS = ("is_dc", "run", "size", "amp", "eob", "comp")


def special_qblocks():
    z = [0] * 64
    only_dc = [37] + [0] * 63
    zrl = list(z); zrl[0] = -5; zrl[J.ZIGZAG[20]] = 3; zrl[J.ZIGZAG[40]] = -1
    last = list(z); last[0] = 1000; last[J.ZIGZAG[63]] = -7      # 62 zeros, no EOB
    dense = [((i * 37) % 23) - 11 for i in range(64)]
    big = [-1024] + [1023 if i % 2 else -1023 for i in range(63)]
    return [only_dc, z, zrl, last, dense, big]


def sym_stream_from_qblocks(qblocks, comps):
    pred = {0: 0, 1: 0, 2: 0}
    syms = []
    for q, c in zip(qblocks, comps):
        syms.extend(J.run_length(q, c, pred))
    return syms


# ----------------------------------------------------------------- run-length
@cocotb.test()
async def rle_matches_model(dut):
    rng = rng_for(dut)
    dut.start.value = 0
    dut.in_valid.value = 0
    await start(dut)
    frames = [special_qblocks()]
    enc = J.encode_frame(make_image(32, 32, "scene"), quality=75, mode=0)
    frames.append(enc["qcoeffs"])
    enc = J.encode_frame(make_image(32, 32, "noise"), quality=95, mode=0)
    frames.append(enc["qcoeffs"])
    for qblocks in frames:
        comps = [[0, 0, 0, 0, 1, 2][i % 6] for i in range(len(qblocks))]
        dut.start.value = 1
        await RisingEdge(dut.clk)
        dut.start.value = 0
        items = [(v, comps[b], int(i == 63), int(b == len(qblocks) - 1 and i == 63))
                 for b, q in enumerate(qblocks) for i, v in enumerate(q)]

        def apply(it):
            dut.in_data.value = it[0] & 0xFFFF
            dut.in_comp.value, dut.in_blast.value, dut.in_flast.value = it[1], it[2], it[3]

        def sample():
            return (J.Sym(*(int(getattr(dut, "o_" + f).value) for f in SYM_FIELDS)),
                    int(dut.o_flast.value))

        drv = cocotb.start_soon(drive_stream(dut.clk, dut.in_valid, dut.in_ready, items, apply, rng, 0.2))
        got = await collect_stream(dut.clk, dut.o_valid, dut.o_ready, sample,
                                   lambda o: o[-1][1] == 1, rng, 0.3)
        await drv
        exp = sym_stream_from_qblocks(qblocks, comps)
        syms = [g[0] for g in got]
        for i, (a, b) in enumerate(zip(syms, exp)):
            assert a == b, f"symbol {i}: got {a} expected {b}"
        assert len(syms) == len(exp), f"got {len(syms)} symbols, expected {len(exp)}"
        assert [g[1] for g in got].count(1) == 1


# --------------------------------------------------------- selective encryption
async def keystream_model(dut, bits, rng):
    """Drive the keystream window from a Python bit list. Window and avail are
    set at the falling edge; the take is read once the logic has settled."""
    p = 0
    while True:
        await FallingEdge(dut.clk)
        limit = 16 if rng.random() > 0.15 else rng.randint(0, 15)   # starvation
        avail = max(0, min(limit, len(bits) - p))
        dut.ks_avail.value = avail
        dut.ks_bits.value = sum(b << i for i, b in enumerate(bits[p:p + 16]))
        await ReadOnly()
        take, n = int(dut.ks_take.value), int(dut.ks_n.value)
        await RisingEdge(dut.clk)
        if take:
            assert n <= avail, "consumer took more keystream bits than available"
            p += n


@cocotb.test()
async def selective_enc_matches_model(dut):
    rng = rng_for(dut)
    dut.i_valid.value = 0
    dut.ks_avail.value = 0
    dut.ks_bits.value = 0
    await start(dut)
    key, nonce = bytes(range(16)), ascon.make_nonce(9, 3, 0)
    syms = J.encode_frame(make_image(32, 32, "scene"), 75, 0)["symbols"]
    syms += sym_stream_from_qblocks(special_qblocks(), [0, 1, 2, 0, 1, 2])
    for mode in range(5):
        dut.mode.value = mode
        exp, nbits = J.selective_encrypt(syms, mode, key, nonce)
        if mode == 0:
            assert exp == syms
        bits = ascon.keystream_bits(key, nonce, nbits + 16)
        ks = cocotb.start_soon(keystream_model(dut, bits, rng))
        items = [(s, int(i == len(syms) - 1)) for i, s in enumerate(syms)]

        def apply(it):
            s, last = it
            for f in SYM_FIELDS:
                getattr(dut, "i_" + f).value = getattr(s, f)
            dut.i_flast.value = last

        def sample():
            return J.Sym(*(int(getattr(dut, "o_" + f).value) for f in SYM_FIELDS))

        drv = cocotb.start_soon(drive_stream(dut.clk, dut.i_valid, dut.i_ready, items, apply, rng, 0.2))
        got = await collect_stream(dut.clk, dut.o_valid, dut.o_ready, sample,
                                   lambda o: len(o) >= len(syms), rng, 0.2)
        await drv
        ks.cancel()
        for i, (a, b) in enumerate(zip(got, exp)):
            assert a == b, f"mode {mode} symbol {i}: got {a} expected {b} (input {syms[i]})"
        # decrypting = applying the same keystream again
        dec, _ = J.selective_encrypt(got, mode, key, nonce)
        assert dec == syms
        dut._log.info("mode %s: %d symbols, %d keystream bits", J.MODE_NAMES[mode], len(syms), nbits)


# ------------------------------------------------------------- Huffman + packer
@cocotb.test()
async def huffman_packer_matches_model(dut):
    rng = rng_for(dut)
    dut.i_valid.value = 0
    await start(dut)
    cases = []
    for kind, q, mode in [("scene", 75, 0), ("noise", 95, 2), ("bars", 50, 4), ("checker", 90, 3)]:
        e = J.encode_frame(make_image(32, 32, kind), q, mode, bytes(16), 1, 1)
        cases.append((kind, e["enc_symbols"], e["scan"]))
    # every AC code length: one symbol per (run, size) in the luma and chroma tables
    every = []
    for comp in (0, 1):
        for rs in sorted(J.AC_CODES[comp]):
            run, size = rs >> 4, rs & 15
            every.append(J.Sym(0, run, size, (1 << size) - 1 if size else 0, 0, comp))
    cases.append(("all-codes", every, J.pack_bytes([J.huffman_bits(s) for s in every])))
    stuffed = sum(c[2].count(b"\xff\x00") for c in cases)
    assert stuffed > 0, "test data never exercises 0xFF stuffing"
    for name, syms, exp in cases:
        items = [(s, int(i == len(syms) - 1)) for i, s in enumerate(syms)]

        def apply(it):
            s, last = it
            for f in ("is_dc", "run", "size", "amp", "comp"):
                getattr(dut, "i_" + f).value = getattr(s, f)
            dut.i_flast.value = last

        drv = cocotb.start_soon(drive_stream(dut.clk, dut.i_valid, dut.i_ready, items, apply, rng, 0.2))
        got = await collect_stream(dut.clk, dut.o_valid, dut.o_ready,
                                   lambda: (int(dut.o_data.value), int(dut.o_last.value)),
                                   lambda o: o[-1][1] == 1, rng, 0.3)
        await drv
        data = bytes(g[0] for g in got)
        if data != exp:
            i = next((k for k in range(min(len(data), len(exp))) if data[k] != exp[k]), min(len(data), len(exp)))
            assert False, (f"{name}: first byte mismatch at offset {i}: got "
                           f"{data[max(0, i - 4):i + 4].hex()} expected {exp[max(0, i - 4):i + 4].hex()} "
                           f"(lengths {len(data)} vs {len(exp)})")
        dut._log.info("%s: %d bytes, %d stuffed 0xFF bytes, byte-exact", name, len(data), exp.count(b"\xff\x00"))


def test_zigzag_rle():
    run_sim("zigzag_rle", "test_entropy", testcase="rle_matches_model")


def test_selective_enc():
    run_sim("selective_enc", "test_entropy", testcase="selective_enc_matches_model")


def test_huffman_packer():
    run_sim("huffman_packer", "test_entropy", testcase="huffman_packer_matches_model")
