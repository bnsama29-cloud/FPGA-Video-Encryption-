"""Paper 2 model: the mixed-radix Feistel (DESIGN §4.3) and levels V0-V3 (§4.1-§4.5)."""
import numpy as np
import pytest

from neuro import evt2, feistel, levels
from neuro_helpers import sid, sk, stream


@pytest.mark.parametrize("W,H", [(16, 16), (34, 34), (16, 1280), (128, 128), (346, 260)])
def test_permutation_is_a_bijection_and_inverse_is_exact(W, H):
    t = feistel.make_tables(sk().perm, sid(), 7, W, H)
    y, x = np.divmod(np.arange(W * H), W)
    px, py = feistel.permute(x, y, t)
    assert px.min() >= 0 and px.max() < W and py.min() >= 0 and py.max() < H
    assert len(np.unique(py * W + px)) == W * H
    ux, uy = feistel.unpermute(px, py, t)
    bad = np.nonzero((ux != x) | (uy != y))[0]
    assert len(bad) == 0, f"first mismatch at index {bad[0]}: ({x[bad[0]]},{y[bad[0]]}) -> ({ux[bad[0]]},{uy[bad[0]]})"


def test_refusal_below_16():
    with pytest.raises(ValueError):
        feistel.make_tables(sk().perm, sid(), 0, 15, 128)
    with pytest.raises(ValueError):
        feistel.make_tables(sk().perm, sid(), 0, 128, 1)


def test_tables_follow_spec_derivation_and_change_per_packet():
    from model import ascon
    from neuro.keys import nonce
    W, H = 20, 17
    t = feistel.make_tables(sk().perm, sid(), 3, W, H)
    ks = ascon.Keystream(sk().perm, nonce(sid(), 3, 0))
    for j in range(8):
        M, n = (W, H) if j % 2 == 0 else (H, W)
        exp = [(ks.take(16) * M) >> 16 for _ in range(n)]
        assert t.t[j].tolist() == exp, f"table {j}"
    t4 = feistel.make_tables(sk().perm, sid(), 4, W, H)
    assert any(not np.array_equal(a, b) for a, b in zip(t.t, t4.t))


def test_walk_variant_is_exact_and_counts_calls():
    W, H = 34, 34
    y, x = np.divmod(np.arange(W * H), W)
    px, py, calls = feistel.permute_walk(x, y, sk().perm, sid(), 1, W, H)
    assert px.max() < W and py.max() < H and calls.min() >= 1
    ux, uy = feistel.unpermute_walk(px, py, sk().perm, sid(), 1, W, H)
    assert np.array_equal(ux, x) and np.array_equal(uy, y)


def test_shuffle_table_is_a_permutation():
    p = feistel.shuffle_table(sk().perm, sid(), 0, 16, 16)
    assert sorted(p.tolist()) == list(range(256))


@pytest.mark.parametrize("level,b", [(0, 0), (1, 0), (2, 0), (3, 1), (3, 6)])
def test_levels_roundtrip_and_touch_only_their_fields(level, b):
    w = stream(300)
    t = feistel.make_tables(sk().perm, sid(), 9, 128, 128) if level in (2, 3) else None
    p = levels.protect(w, level, b, t, sk().pol, sid(), 9)
    assert np.array_equal(levels.unprotect(p, level, b, t, sk().pol, sid(), 9), w)
    cd = evt2.is_cd(w)
    assert np.array_equal(p[~cd], w[~cd]), "non-CD words must pass unchanged"
    diff = (p ^ w)[cd]
    allowed = 0
    if level in (1, 3):
        allowed |= 1 << 28
    if level == 3:
        allowed |= ((1 << b) - 1) << 22
    if level in (2, 3):
        allowed |= 0x3FFFFF
    assert not (diff & ~np.uint32(allowed)).any()
    if level == 1:
        assert (diff == (1 << 28)).sum() > 100       # about half the polarities flip


def test_keystream_bit_order_v3():
    from model import ascon
    from neuro.keys import nonce
    w = np.array([evt2.time_high(1), evt2.cd_word(3, 4, 0, 0)], dtype=np.uint32)
    p = levels.protect(w, 3, 6, feistel.make_tables(sk().perm, sid(), 2, 16, 16), sk().pol, sid(), 2)
    k = ascon.Keystream(sk().pol, nonce(sid(), 2, 0)).take(7)
    assert (int(p[1]) >> 28) & 1 == k & 1
    assert (int(p[1]) >> 22) & 63 == (k >> 1) & 63
