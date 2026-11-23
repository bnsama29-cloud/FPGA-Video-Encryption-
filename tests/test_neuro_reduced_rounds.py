"""N14: experiments/neuro_reduced_rounds.py (known-plaintext attacks on 1-3 rounds of the mixed-radix Feistel)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import neuro_reduced_rounds as N14  # noqa: E402
from neuro import feistel  # noqa: E402


@pytest.mark.parametrize("r", [1, 2, 3])
def test_full_codebook_gives_exact_prediction_of_everything(r):
    W, H = 40, 23
    t = feistel.make_tables(N14.SK.perm, N14.SID, 4, W, H, r=r)
    y, x = np.divmod(np.arange(W * H), W)
    cx, cy = feistel.permute(x, y, t)
    ok, px, py = N14.attack(r, x, y, cx, cy, W, H)(x, y)
    assert ok.all(), f"r={r}: {int((~ok).sum())} plaintexts unpredictable with the full codebook"
    bad = np.flatnonzero((px != cx) | (py != cy))
    assert bad.size == 0, f"r={r}: first wrong prediction at plaintext {bad[0]}: ({px[bad[0]]}, {py[bad[0]]}) vs ({cx[bad[0]]}, {cy[bad[0]]})"


def test_no_pairs_predict_nothing_and_r4_is_refused():
    e = np.zeros(0, np.int64)
    ok, _, _ = N14.attack(3, e, e, e, e, 40, 23)(np.array([1, 2]), np.array([3, 4]))
    assert not ok.any()
    with pytest.raises(ValueError):
        N14.attack(4, e, e, e, e, 40, 23)


def test_quick_run_coverage_grows_with_pairs(tmp_path):
    d = N14.main(["--quick", "--out", str(tmp_path)])
    res = d["results"]
    for r in (1, 2, 3):
        lo, hi = res[f"34x34/r{r}/n30"]["mean"], res[f"34x34/r{r}/n300"]["mean"]
        assert hi >= lo and hi == pytest.approx(1.0), f"r={r}: coverage {lo} -> {hi}"
    assert (tmp_path / "reduced_rounds.json").is_file()
