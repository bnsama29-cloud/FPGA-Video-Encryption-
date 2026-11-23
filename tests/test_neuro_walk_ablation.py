"""N2b model part: experiments/neuro_walk_ablation.py (cycle walking vs the mixed-radix Feistel)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import neuro_walk_ablation as N2b  # noqa: E402


def test_summarise_known_lengths():
    calls = np.array([1, 1, 2, 5, 9])
    s = N2b.summarise(calls, K_rtl=4)
    assert s["mean"] == pytest.approx(3.6) and s["max"] == 9
    assert s["frac_gt"][4] == pytest.approx(0.4)
    assert s["extra_beyond"][4] == pytest.approx((1 + 5) / 5)
    assert s["rtl_stall_clk_per_word"] == pytest.approx(N2b.PASS_CLK * 6 / 5 + N2b.SIDE_OVH * 0.4)
    assert s["rtl_dense_words_per_clk"] == pytest.approx(1 / (1 + s["rtl_stall_clk_per_word"]))


def test_quick_run_is_consistent(tmp_path):
    d = N2b.main(["--quick", "--out", str(tmp_path)])
    st = d["stats"]
    pow2 = st["dvsgesture/pow2"]                          # 128 x 128 is already binary: no walk
    assert pow2["max"] == 1 and pow2["rtl_dense_words_per_clk"] == 1.0
    nm = st["nmnist/pow2"]                                # 34 x 34 in 64 x 64
    assert nm["domain"] == [64, 64] and nm["mean"] == pytest.approx(nm["ratio"], rel=0.05), (
        f"mean passes {nm['mean']} far from the domain ratio {nm['ratio']} (cycle walking: E[calls] = N / k)")
    fr = [nm["frac_gt"][k] for k in N2b.KS]
    assert all(a >= b for a, b in zip(fr, fr[1:])), f"fraction above K not monotone: {fr}"
    assert (tmp_path / "walk_stats.json").is_file() and (tmp_path / "walk_stats.md").is_file()
