"""The Feistel table cache of experiments/neuro_common.py changes no output (TESTING bug #53).

The cache keys feistel.make_tables by (k_perm, sid, ctr, W, H, r). These tests check that a cached table equals a
freshly computed one entry by entry, that different keys / counters / geometries never share an entry, that
sealed packets are byte-identical with and without the cache, and that a cached table cannot be modified.
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

from neuro import feistel, keys
from neuro.geometry import Geometry

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
C = importlib.import_module("neuro_common")        # installs the cache into neuro.feistel ...
feistel.make_tables = C._make_tables_uncached       # ... undone at once: only this module's tests use it


@pytest.fixture(autouse=True, scope="module")
def _restore_make_tables():
    """Other test modules see the plain make_tables, whatever the collection order."""
    feistel.make_tables = C._make_tables_cached
    yield
    feistel.make_tables = C._make_tables_uncached


def _first_mismatch(a, b):
    for j, (x, y) in enumerate(zip(a.t, b.t)):
        if not np.array_equal(x, y):
            i = int(np.flatnonzero(x != y)[0])
            return f"table {j} index {i}: got {x[i]}, expected {y[i]}"
    return None


def test_patch_is_installed():
    assert feistel.make_tables is C._make_tables_cached


@pytest.mark.parametrize("ctr,W,H", [(0, 128, 128), (5, 128, 128), (5, 34, 34), (3, 640, 480)])
def test_cached_equals_uncached(ctr, W, H):
    sk = keys.subkeys(C.master(0), C.CAM, C.BOOT, 0)
    sid = keys.session_id(C.CAM, C.BOOT, 0)
    ref = C._make_tables_uncached(sk.perm, sid, ctr, W, H)
    for _ in range(2):                                   # miss, then hit
        got = feistel.make_tables(sk.perm, sid, ctr, W, H)
        assert (got.W, got.H, got.r) == (W, H, ref.r)
        assert _first_mismatch(got, ref) is None, _first_mismatch(got, ref)


def test_distinct_arguments_do_not_collide():
    sk0 = keys.subkeys(C.master(0), C.CAM, C.BOOT, 0)
    sk1 = keys.subkeys(C.master(1), C.CAM, C.BOOT, 0)
    sid = keys.session_id(C.CAM, C.BOOT, 0)
    sid1 = keys.session_id(C.CAM, C.BOOT, 1)
    base = feistel.make_tables(sk0.perm, sid, 2, 128, 128)
    for other in (feistel.make_tables(sk1.perm, sid, 2, 128, 128),     # other key
                  feistel.make_tables(sk0.perm, sid1, 2, 128, 128),    # other session
                  feistel.make_tables(sk0.perm, sid, 3, 128, 128)):    # other counter
        assert _first_mismatch(other, base) is not None, "two different arguments returned the same tables"


def test_cached_tables_are_read_only():
    sk = keys.subkeys(C.master(0), C.CAM, C.BOOT, 0)
    t = feistel.make_tables(sk.perm, keys.session_id(C.CAM, C.BOOT, 0), 1, 128, 128)
    with pytest.raises(ValueError):
        t.t[0][0] = 1


@pytest.mark.parametrize("level", [2, 3])
def test_sealed_packets_identical_with_and_without_cache(level, monkeypatch):
    geom = Geometry("t", 64, 48)
    rng = np.random.default_rng(level)
    n = 3000
    ev = np.zeros(n, dtype=[("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "u1")])
    ev["t"] = np.sort(rng.integers(0, 20_000, n))
    ev["x"], ev["y"], ev["p"] = rng.integers(0, 64, n), rng.integers(0, 48, n), rng.integers(0, 2, n)
    cached = C.protect(ev, geom, level, 1024)
    cached_again = C.protect(ev, geom, level, 1024)                    # every table now a cache hit
    monkeypatch.setattr(feistel, "make_tables", C._make_tables_uncached)
    plain = C.protect(ev, geom, level, 1024)
    assert len(cached) == len(plain), f"{len(cached)} packets cached vs {len(plain)} uncached"
    for i, (a, b, p) in enumerate(zip(cached, cached_again, plain)):
        assert a == p, f"packet {i} differs with the cache (first byte {next(k for k in range(len(a)) if a[k] != p[k])})"
        assert b == p, f"packet {i} differs on the cache-hit run"


def test_budget_stops_inserting(monkeypatch):
    monkeypatch.setattr(C, "_table_cache", {})
    monkeypatch.setattr(C, "_table_cache_bytes", 0)
    monkeypatch.setattr(C, "TABLE_CACHE_BYTES", 1)                   # nothing fits
    sk = keys.subkeys(C.master(0), C.CAM, C.BOOT, 0)
    sid = keys.session_id(C.CAM, C.BOOT, 0)
    t = feistel.make_tables(sk.perm, sid, 0, 32, 32)
    assert C._table_cache == {} and C._table_cache_bytes == 0
    assert _first_mismatch(t, C._make_tables_uncached(sk.perm, sid, 0, 32, 32)) is None
