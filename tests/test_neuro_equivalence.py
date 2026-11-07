"""Stage view (neuro.hw) == packet view (neuro.packet / neuro.sender), DESIGN §7.1 and §7.3."""
import numpy as np
import pytest

from model import ascon
from neuro import evt2, feistel, hw, keys, levels
from neuro.geometry import Geometry, SENSORS
from neuro.keys import nonce
from neuro.packet import from_bytes
from neuro.pad import FLOOR, LADDER, PadPolicy
from neuro.sender import Config, encrypt_stream

MASTER = bytes(range(16))
SID = keys.session_id(7, 9, 0)
SK = keys.subkeys(MASTER, 7, 9, 0)


def _stream(geom, n=300, seed=1, T_us=256):
    rng = np.random.default_rng(seed)
    ev = np.zeros(n, dtype=evt2.EVENT_DTYPE)
    ev["t"] = np.sort(rng.integers(1000, 1000 + 6 * T_us, n))
    ev["x"] = rng.integers(0, geom.W, n)
    ev["y"] = rng.integers(0, geom.H, n)
    ev["p"] = rng.integers(0, 2, n)
    return evt2.encode(ev, T_us)


CASES = [(lvl, 0 if lvl != 3 else 6, None) for lvl in range(5)] + [
    (3, 6, PadPolicy(FLOOR, 3)), (3, 6, PadPolicy(LADDER, 2, 8)), (4, 0, PadPolicy(FLOOR, 2)), (3, 2, None)]


@pytest.mark.parametrize("level,b,pad", CASES)
def test_blocks_reproduce_tag_and_ciphertext(level, b, pad):
    geom = SENSORS["dvsgesture"]
    cfg = Config(level=level, ts_bits=b, T_us=256, geom=geom, pad=pad)
    pkts, _ = encrypt_stream(_stream(geom), SK, SID, cfg)
    assert len(pkts) > 3
    for i, raw in enumerate(pkts):
        p = from_bytes(raw)
        if level == 4:          # keyless parse cannot split V4; rebuild the packet from the decryption
            h = p.header
            pt = ascon.decrypt(SK.aead, nonce(h.session_id, h.packet_ctr, 0), h.pack(), raw[48:])
            assert pt is not None
            from neuro.packet import Packet, Trailer
            tr = Trailer.unpack(pt, h.pad)
            pay = np.frombuffer(pt[:4 * tr.n_words], dtype="<u4").astype(np.uint32)
            p = Packet(h, pay, tr, raw[-16:], raw[48:-16])
        assert hw.check_packet(p, SK), f"packet {i}: stage-view blocks do not give the packet's tag"
        ow = hw.out_words(p)
        assert [w for w, _ in ow] == hw.words_of(raw), f"packet {i}: out_words differ from the packet bytes"
        assert [l for _, l in ow].count(1) == 1 and ow[-1][1] == 1
        if level != 4:
            assert hw.words_of(raw)[:12] == hw.header_words(p.header)
            assert hw.words_of(raw)[-16 // 4 - len(p.trailer) // 4:-4] == hw.trailer_words(p.trailer)


@pytest.mark.parametrize("n_bytes", [48, 52, 56, 60, 64, 76, 80])
def test_block_rules(n_bytes):
    """Last block of each type has blk_bytes < 16 (empty block when the length is a multiple of 16)."""
    blocks = hw.tag_blocks(bytes(48), np.zeros((n_bytes - 48) // 4, np.uint32), b"", hw.MAC)
    ad = [blk for blk in blocks if blk[3] == hw.AD]
    assert all(n == 16 and last == 0 for _, n, last, _ in ad[:-1])
    assert ad[-1][1] < 16 and ad[-1][2] == 1
    assert sum(n for _, n, _, _ in ad) == n_bytes
    assert blocks[-1] == (bytes(16), 0, 1, hw.PT)


def test_feistel_round_and_fill_order():
    W, H = 40, 23
    t = feistel.make_tables(SK.perm, SID, 5, W, H)
    ent = hw.table_fill_entries(SK.perm, SID, 5, W, H)
    assert len(ent) == 4 * (W + H)
    assert [v for _, _, v in ent[:H]] == t.t[0].tolist()
    rng = np.random.default_rng(0)
    for _ in range(200):
        x, y = int(rng.integers(W)), int(rng.integers(H))
        xx, yy = x, y
        for j in range(8):
            xx, yy = hw.feistel_round(xx, yy, j, t)
        ex, ey = feistel.permute(x, y, t)
        assert (xx, yy) == (int(ex), int(ey))


def test_xor_word_matches_levels():
    rng = np.random.default_rng(3)
    words = rng.integers(0, 1 << 32, 64, dtype=np.uint64).astype(np.uint32)
    for b in (0, 1, 6):
        ks = ascon.Keystream(SK.pol, nonce(SID, 2, 0))
        exp = levels.xor_fields(words, np.ones(64, bool), ascon.Keystream(SK.pol, nonce(SID, 2, 0)), b)
        got = [hw.xor_word(w, ks.take(1 + b), b) for w in words.tolist()]
        assert got == exp.tolist()


def test_commit_ok_is_the_sender_rule():
    assert hw.commit_ok(5, 6, None, None, 1, 0, 1) == (False, 1)
    assert hw.commit_ok(5, 7, None, None, 1, 0, 1)[0]
    base = keys.session_id(7, 9, 3)
    assert hw.commit_ok(5, 9, base, 100, base - 1, 0, base)[1] == 5      # older epoch: REWIND


def test_header_words_layout():
    g = Geometry("t", 346, 260)
    from neuro.packet import PacketHeader
    h = PacketHeader(level=3, flags=2, ts_bits=6, session_id=0x0102030405060708, packet_ctr=9, t_start=1024,
                     W=g.W, H=g.H, T_us=1024, pad_policy=0, link=7)
    w = hw.header_words(h)
    assert len(w) == 12 and w[0] == 0x3145564E
    assert w[1] == 1 | (3 << 8) | (2 << 16) | (6 << 24)
    assert w[2] == 0x04030201 and w[3] == 0x08070605
