"""Fixes from the first paper-2 Kaggle QUICK runs (7 Nov 2026; TESTING bugs #54, #55, #56 and #57).

#54 N5: with label = group (Event-ReId persons) no test label is seen in training; classifiers must say n/a
    instead of reporting 0 balanced accuracy as if it were a result.
#55 N4b: a view with no packet of --min-addr distinct addresses (N-MNIST) must be named, not silently dropped.
#57 N3 / N4: a 3 s Event-ReId recording is 160 windows of 640 x 480; both keep the busiest contiguous run only.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from neuro import datasets
from neuro.geometry import SENSORS

ROOT = Path(__file__).resolve().parents[1]


def _run(args):
    p = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]


def _counts(tmp_path, label_is_group):
    rng = np.random.default_rng(0)
    items = []
    for i in range(16):
        ev = np.zeros(400, dtype=[("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "u1")])
        ev["t"] = np.sort(rng.integers(1000, 200_000, 400))
        ev["x"], ev["y"], ev["p"] = rng.integers(0, 34, 400), rng.integers(0, 34, 400), rng.integers(0, 2, 400)
        label = i % 4 if not label_is_group else i // 2
        items.append((ev, label, f"g{i // 2}", SENSORS["nmnist"]))
    path = tmp_path / "c.npz"
    datasets.cache_counts(iter(items), path)
    return path


def test_n5_classifiers_na_when_label_is_group(tmp_path):
    _run(["experiments/neuro_leakage.py", "--quick", "--counts", str(_counts(tmp_path, True)), "--out", str(tmp_path)])
    d = json.loads((tmp_path / "leakage.json").read_text())
    for view, r in d["views"].items():
        assert r["nearest-centroid"] == "n/a" and r["5-NN"] == "n/a", f"{view}: got {r['nearest-centroid']}"
    assert "Classifiers n/a" in (tmp_path / "leakage.md").read_text()


def test_n5_classifiers_run_when_labels_shared(tmp_path):
    _run(["experiments/neuro_leakage.py", "--quick", "--counts", str(_counts(tmp_path, False)), "--out", str(tmp_path)])
    d = json.loads((tmp_path / "leakage.json").read_text())
    r = d["views"]["V2"]
    assert r["nearest-centroid"] != "n/a", "classifier skipped although test labels occur in training"


def test_n4b_names_views_without_rows(tmp_path):
    _run(["experiments/neuro_adjacency_attack.py", "--quick", "--min-addr", "100000", "--out", str(tmp_path)])
    d = json.loads((tmp_path / "adjacency.json").read_text())
    assert d["results"] == [] and len(d["skipped"]) == 3, d["skipped"]
    assert "--min-addr" in (tmp_path / "adjacency.md").read_text()


# ---------------------------------------------------------------- #57: window cap (N3, N4)
sys.path.insert(0, str(ROOT / "experiments"))


def _burst(n_windows=12, burst=(5, 6, 7), per_burst=300, per_quiet=10, win=20_000, seed=0):
    rng = np.random.default_rng(seed)
    parts = []
    for w in range(n_windows):
        n = per_burst if w in burst else per_quiet
        parts.append(rng.integers(w * win, (w + 1) * win, n))
    t = np.sort(np.concatenate(parts))
    t[0] = 0                      # windows are counted from the first event (as in N3 / N4): align them with 0
    ev = np.zeros(len(t), dtype=[("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "u1")])
    ev["t"], ev["x"], ev["y"] = t, rng.integers(0, 64, len(t)), rng.integers(0, 48, len(t))
    return ev


def test_crop_keeps_the_busiest_contiguous_run_rebased_to_zero():
    import neuro_common as C
    ev = _burst()
    out = C.crop_to_busiest_windows(ev, 20_000, 3)
    assert len(out) == 3 * 300, f"kept {len(out)} events, expected the 900 of windows 5-7"
    assert int(out["t"].min()) >= 0 and int(out["t"].max()) < 3 * 20_000, (int(out["t"].min()), int(out["t"].max()))
    assert np.all(np.diff(out["t"].astype(np.int64)) >= 0), "cropped events must stay sorted"
    src = ev[(ev["t"] >= 5 * 20_000) & (ev["t"] < 8 * 20_000)]
    assert out["x"].tolist() == src["x"].tolist(), "the cropped events are not the events of windows 5-7"


def test_crop_is_a_no_op_for_short_recordings_and_for_frames():
    import neuro_common as C
    ev = _burst(n_windows=3, burst=(1,))
    assert C.crop_to_busiest_windows(ev, 20_000, 6) is ev
    assert C.crop_to_busiest_windows(ev, 20_000, None) is ev
    long_ev = _burst()
    kept = C.crop_samples([(long_ev, 0, "g", None, np.zeros((3, 4, 4)))], 20_000, 3)[0][0]
    assert kept is long_ev, "samples with ground-truth frames are indexed by time and must not be cropped"


def test_cropped_event_reid_style_stream_seals_at_every_level():
    """The Kaggle failure: a full recording (t up to 6.7e10 us) went to evt2.encode and was refused."""
    import neuro_common as C
    from neuro.geometry import Geometry
    ev = C.crop_to_busiest_windows(_burst(), 20_000, 3)
    for level in (1, 2, 3, 4):
        assert len(C.protect(ev, Geometry("t", 64, 48), level, 1024)) > 0, f"V{level}: no packets"


def test_n4_builds_at_most_max_windows_per_recording():
    import neuro_common as C
    import neuro_learned_attack as N4
    from neuro.geometry import Geometry
    geom = Geometry("t", 64, 48)
    cropped = C.crop_samples([(_burst(), 0, "g0", geom, None)], 20_000, 3)
    w = N4.windows_of(cropped, "plain", 1024, 20_000, 1)
    assert len(w) == 3, f"{len(w)} windows built, expected 3"


@pytest.mark.parametrize("px,expected", [(34 * 34, 32), (128 * 128, 32), (480 * 640, 9)])
def test_n4_batch_size_shrinks_with_image_size(px, expected):
    import neuro_learned_attack as N4
    assert N4.batch_size(px) == expected, f"{px} px: got {N4.batch_size(px)}, expected {expected}"
