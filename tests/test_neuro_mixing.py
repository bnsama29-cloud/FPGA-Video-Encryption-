"""N13: experiments/neuro_mixing.py (camera mixing and shaped padding)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import neuro_mixing as M  # noqa: E402


def naive_shaped(n, lam):
    out = []
    for b in range(len(n)):
        env = max(n[j] * lam ** (b - j) for j in range(b + 1))
        out.append(max(int(np.ceil(env - 1e-9)), int(n[b])))
    return np.array(out)


@pytest.mark.parametrize("lam", [0.5, 0.9, 0.98])
def test_shaped_equals_definition_across_chunks(lam):
    rng = np.random.default_rng(1)
    n = rng.poisson(3, 700) * (rng.random(700) < 0.3)
    got, exp = M.shaped(n, lam, chunk=64), naive_shaped(n, lam)
    bad = np.flatnonzero(got != exp)
    assert bad.size == 0, f"first mismatch at bucket {bad[0]}: n={n[bad[0]]}, got {got[bad[0]]}, expected {exp[bad[0]]}"
    assert (got >= n).all()


def test_mix_keeps_length_adds_partner_counts_and_avoids_own_group():
    series = [np.array([1, 0, 2]), np.array([5, 5]), np.array([0, 0, 0, 7])]
    y = np.array([0, 1, 2])
    g = np.array(["a", "a", "b"])
    sel = np.array([True, True, True])
    out = M.mix(series, y, g, sel, 2, np.random.default_rng(0))
    assert [len(s) for s in out] == [3, 2, 4]

    def added(target, partners):          # every count a partner of another group can add, over all phases
        return {int(np.resize(np.roll(series[p], -ph), len(series[target])).sum())
                for p in partners for ph in range(len(series[p]))}

    for t, partners in ((0, [2]), (1, [2]), (2, [0, 1])):
        d = int(out[t].sum() - series[t].sum())
        assert d in added(t, partners), f"sample {t}: added {d}, not a phase of a partner from another group"


def test_quick_run_writes_all_views(tmp_path):
    d = M.main(["--quick", "--out", str(tmp_path)])
    v = d["views"]
    assert {"V3", "V3 mixed k=2", "V3 + shaped lam=0.9", "V3 + pad floor 16"} <= set(v)
    assert v["V3"]["dummies_per_real"] == 0 and v["V3 mixed k=2"]["dummies_per_real"] == 0
    assert v["V3 + shaped lam=0.98"]["dummies_per_real"] >= v["V3 + shaped lam=0.9"]["dummies_per_real"]
    assert d["kmax_by_sensor"]["imx636"] == 1 and d["kmax_by_sensor"]["nmnist"] == 60
    assert (tmp_path / "mixing.json").is_file()
