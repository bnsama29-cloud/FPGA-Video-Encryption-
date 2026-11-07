"""Du 2021 and Zhang 2024 reimplementations (docs/neuro/BASELINES.md): exact round trip and stated structure."""
import numpy as np
import pytest

from neuro import evt2
from neuro.baselines import du2021, zhang2024


def ev(n, W, H, seed=0):
    rng = np.random.default_rng(seed)
    e = np.zeros(n, dtype=evt2.EVENT_DTYPE)
    e["t"] = np.sort(rng.integers(1000, 50000, n))
    e["x"], e["y"], e["p"] = rng.integers(0, W, n), rng.integers(0, H, n), rng.integers(0, 2, n)
    return e


def same(a, b):
    return all((a[f] == b[f]).all() for f in ("t", "x", "y", "p"))


@pytest.mark.parametrize("W,H,keyed", [(34, 34, False), (40, 23, False), (128, 128, True)])
def test_du_round_trip_and_updates(W, H, keyed):
    e = ev(3000, W, H)
    k = du2021.DuKey.from_seed(b"k")
    kw = dict(ascon_keyed=keyed, ascon_key=bytes(16), every=700)
    c = du2021.encrypt(e, W, H, k, **kw)
    assert (c["x"] < W).all() and (c["y"] < H).all() and (c["t"] == e["t"]).all()
    assert not same(c, e)
    assert same(du2021.decrypt(c, W, H, k, **kw), e)
    assert k.bits() == 306


def test_du_is_a_bijection_per_segment():
    W, H = 20, 16
    y, x = np.divmod(np.arange(W * H * 2) % (W * H), W)
    e = np.zeros(W * H * 2, dtype=evt2.EVENT_DTYPE)
    e["x"], e["y"], e["p"] = x, y, np.arange(W * H * 2) // (W * H)
    c = du2021.encrypt(e, W, H, du2021.DuKey.from_seed(b"b"), every=10 ** 9)
    assert len(np.unique(c["p"].astype(int) * W * H + c["y"].astype(int) * W + c["x"])) == 2 * W * H


def test_du_update_interval_follows_eq12():
    assert du2021.update_every(128, 128) == int(10 ** 8.4 * 128 * 128 / du2021.K_PI) + 1


def test_zhang_fills_every_pixel_and_round_trips():
    W, H = 34, 34
    e = ev(400, W, H)
    c, key = zhang2024.encrypt(e, W, H, bytes(16))
    assert len(np.unique(c["y"].astype(int) * W + c["x"])) == W * H          # mask = S \ Ex is filled
    assert len(c) > len(e) and (np.diff(c["t"].astype(np.int64)) >= 0).all()
    d = zhang2024.decrypt(c, key, W)
    o = np.lexsort((e["p"], e["y"], e["x"], e["t"]))
    o2 = np.lexsort((d["p"], d["y"], d["x"], d["t"]))
    assert same(d[o2], e[o])
    assert len(zhang2024.key_bytes(key, bytes(16))) == 4 * len(key) + 16


def test_szudzik_is_a_pairing():
    v = zhang2024.szudzik(*np.divmod(np.arange(400), 20))
    assert len(np.unique(v)) == 400
