"""Fixes from the first paper-2 Kaggle QUICK runs (7 Nov 2026; TESTING bugs #54 and #55).

#54 N5: with label = group (Event-ReId persons) no test label is seen in training; classifiers must say n/a
    instead of reporting 0 balanced accuracy as if it were a result.
#55 N4b: a view with no packet of --min-addr distinct addresses (N-MNIST) must be named, not silently dropped.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

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
