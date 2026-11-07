"""neuro.stats, neuro.cycle_model and neuro.vectors (DESIGN §7.1, §7.2, §8.3)."""
import json

import numpy as np
import pytest

from neuro import cycle_model as CM
from neuro import stats as S
from neuro import vectors as V


def test_clopper_pearson_known_values():
    # all successes: the lower bound of 0.95 two-sided for n = 100 is (alpha/2)^(1/n)
    p, lo, hi = S.clopper_pearson(100, 100)
    assert p == 1 and hi == 1 and lo == pytest.approx(0.025 ** (1 / 100), rel=1e-9)
    p, lo, hi = S.clopper_pearson(0, 50)
    assert lo == 0 and hi == pytest.approx(1 - 0.025 ** (1 / 50), rel=1e-9)
    with pytest.raises(ValueError):
        S.clopper_pearson(3, 2)


def test_mean_and_bootstrap_cover_the_mean():
    rng = np.random.default_rng(0)
    v = rng.normal(5, 1, 400)
    m, lo, hi = S.mean_ci(v)
    assert lo < 5 < hi and m == pytest.approx(v.mean())
    m2, lo2, hi2 = S.bootstrap_ci(v, n=500)
    assert lo2 < m2 < hi2 and abs(lo2 - lo) < 0.05


def test_cluster_bootstrap_is_wider_than_item_bootstrap_for_clustered_data():
    rng = np.random.default_rng(1)
    groups = np.repeat(np.arange(10), 50)
    v = rng.normal(0, 1, 10)[groups] + rng.normal(0, 0.1, 500)
    _, lo_i, hi_i = S.bootstrap_ci(v, n=500)
    _, lo_c, hi_c = S.cluster_bootstrap_ci(v, groups, n=500)
    assert (hi_c - lo_c) > 3 * (hi_i - lo_i)
    assert S.n_clusters(groups) == 10
    d = S.paired_bootstrap_diff(v + 1, v, groups, n=200)
    assert d[0] == pytest.approx(1.0)


def test_mutual_information():
    rng = np.random.default_rng(2)
    x = rng.integers(0, 4, 4000)
    assert S.mi_plugin_mm(x, x) == pytest.approx(2.0, abs=0.01)                 # H(X) = 2 bits
    assert S.mi_plugin_mm(x, rng.integers(0, 4, 4000)) < 0.01
    mi, null, p = S.mi_perm_null(x, (x + (rng.random(4000) < 0.2)) % 4, n=50)
    assert mi > 0.5 and null < 0.01 and p < 0.05
    assert set(S.quantize(rng.random(1000), 4).tolist()) == {0, 1, 2, 3}


def test_cycle_model_orders_the_builds():
    pk = [CM.PacketLoad(200, 180, 1024 * 100 * (k + 1)) for k in range(20)]
    r1 = CM.replay(pk, level=3, U=1, timed=False)
    r2 = CM.replay(pk, level=3, U=2, timed=False)
    r4 = CM.replay(pk, level=3, U=4, timed=False)
    assert r1.cycles > r2.cycles > r4.cycles
    assert r1.words_in == 4000 and r1.words_out == 20 * (12 + 200 + 3 + 4)
    assert 0 < r1.fifo_max <= 512
    t = CM.replay(pk, level=3, U=2, timed=True)
    assert (t.latency > 0).all() and t.cycles >= 20 * 1024 * 100
    assert CM.fill_clk(1280, 720) > CM.fill_clk(128, 128)


def test_vectors_are_written_and_consistent(tmp_path):
    cs = [c for c in V.cases() if c.name in ("dvsgesture_v3", "jump_halt_v3")]
    names = V.write_vectors(tmp_path, cs)
    assert names == ["dvsgesture_v3", "jump_halt_v3"]
    for n in names:
        cfg = json.loads((tmp_path / n / "config.json").read_text())
        out = (tmp_path / n / "out.hex").read_text().split("\n")
        assert sum(1 for l in out if l.endswith(" L")) == json.loads((tmp_path / n / "counters.json").read_text())["PKTS"]
        assert cfg["initial"]["level"] == 3
    r = V.run_model(cs[1])
    assert [s["expect"] for s in r["steps"] if s["op"] == "commit"] == [0]
    assert any(s.get("halts") for s in r["steps"])


def test_default_cases_cover_the_design_list():
    names = {c.name for c in V.cases(full=True)}
    for need in ("gap_pad_floor_v3", "pad_overflow_v3", "jump_drop_v3", "jump_halt_v3", "commit_new_epoch",
                 "commit_level_change", "input_rules_v3", "pad_ladder_v3", "pad_floor_v4"):
        assert need in names
    assert {c.name for c in V.cases()} == V.DEFAULT_CASES
