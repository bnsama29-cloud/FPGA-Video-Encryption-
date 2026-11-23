"""N15: experiments/neuro_margin.py (single-packet distinguisher by rounds, margin)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import neuro_margin as N15  # noqa: E402


def test_auc_known_values():
    assert N15.auc([3, 4], [1, 2], n=50)[0] == 1.0
    assert N15.auc([1, 2], [3, 4], n=50)[0] == 0.0
    assert N15.auc([1, 1], [1, 1], n=50)[0] == 0.5


def test_stat_one_round_keeps_every_same_row_difference():
    W, H = 40, 23
    t8 = N15.feistel.make_tables(N15.SK.perm, N15.SID, 0, W, H)
    t1 = N15.feistel.Tables(W, H, 1, t8.t[:1])
    x, y = N15.sample(W, H, 300, "uniform", np.random.default_rng(0))
    cx, cy = N15.feistel.permute(x, y, t1)
    # one round: x' = x + T0[y], y' = y -> every same-y pair keeps dx and y, every same-x pair keeps y-difference 0
    s = N15.stat(x, y, cx, cy, W, H)
    assert s > 0.5, f"one round should keep most truncated differentials, got {s}"
    ox, oy = np.divmod(np.random.default_rng(1).choice(W * H, len(x), replace=False), W)[::-1]
    assert N15.stat(x, y, ox, oy, W, H) < 0.2


def test_clustered_sampling_stays_in_a_box():
    x, y = N15.sample(1280, 720, 500, "clustered", np.random.default_rng(2))
    assert len(x) == 500 and x.max() - x.min() < 32 and y.max() - y.min() < 32
    assert len(set(zip(x.tolist(), y.tolist()))) == 500


def test_quick_run(tmp_path):
    d = N15.main(["--quick", "--out", str(tmp_path)])
    r1 = d["results"]["34x34/uniform/p99/r1"]["auc"][0]
    assert r1 == pytest.approx(1.0), f"one round must be fully distinguishable, AUC {r1}"
    assert (tmp_path / "margin.json").is_file()
