"""Fixes from the first paper-2 Kaggle QUICK runs (7 Nov 2026; TESTING bugs #54, #55, #56 and #57).

#54 N5: with label = group (Event-ReId persons) no test label is seen in training; classifiers must say n/a
    instead of reporting 0 balanced accuracy as if it were a result.
#55 N4b: a view with no packet of --min-addr distinct addresses (N-MNIST) must be named, not silently dropped.
#57 N3 / N4: a 3 s Event-ReId recording is 160 windows of 640 x 480; both keep the busiest contiguous run only.
#58 N3 / N4 on Event-ReId are scored inside the person box: on the full frame a blank image scored SSIM ~0.97.
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


@pytest.mark.parametrize("px,expected", [(34 * 34, 32), (128 * 128, 32), (480 * 640, 8)])
def test_n4_batch_size_shrinks_with_image_size(px, expected):
    import neuro_learned_attack as N4
    assert N4.batch_size(px) == expected, f"{px} px: got {N4.batch_size(px)}, expected {expected}"


# ---------------------------------------------------------------- #58: scoring inside the person box (N3, N4)
def _labelled_eventreid(root, persons=4, W=160, H=120, box=(70, 40, 89, 69), span_us=300_000, n=6000, seed=0):
    """Event-ReId layout (<id>/<cam>/events.txt + labels/label.json); every event inside one person box."""
    rng = np.random.default_rng(seed)
    x1, y1, x2, y2 = box
    frames = int(span_us // datasets.EVENTREID_FRAME_US) + 1
    for pid in range(1, persons + 1):
        d = root / "Event_ReId" / f"{pid:03d}" / "cam01"
        (d / "labels").mkdir(parents=True)
        (d / "labels" / "label.json").write_text(json.dumps(
            {"bounding_boxes": [[[x1, y1, x2, y2], f] for f in range(1, frames + 1)]}))
        t = np.sort(rng.uniform(0, span_us, n)) / 1e3                      # ms, as in the dataset
        xs, ys = rng.integers(x1, x2 + 1, n), rng.integers(y1 + 4 * pid, y2 + 1, n)   # a different shape per person
        rows = "".join(f"{a:.4f} {b} {c} {e}\n" for a, b, c, e in zip(t, xs, ys, rng.integers(0, 2, n)))
        (d / "events.txt").write_text(f"{W} {H}\n" + rows)


def test_load_eventreid_boxes_reads_frames_in_file_order(tmp_path):
    _labelled_eventreid(tmp_path, persons=2, span_us=100_000)
    b = datasets.load_eventreid_boxes(tmp_path)
    n_frames = len(json.loads((tmp_path / "Event_ReId" / "001" / "cam01" / "labels" / "label.json").read_text())
                   ["bounding_boxes"])
    assert len(b) == 2 and b[0].shape == (n_frames, 6), [None if x is None else x.shape for x in b]
    assert b[0][0].tolist() == [0.0, datasets.EVENTREID_FRAME_US, 70.0, 40.0, 89.0, 69.0], b[0][0].tolist()
    assert abs(b[0][1][0] - datasets.EVENTREID_FRAME_US) < 1e-6, "frame 2 must start at 33.3 ms"


def test_roi_box_union_margin_clip_and_minimum():
    import neuro_common as C
    roi = np.array([[0, 33_333, 10, 20, 30, 40], [33_333, 66_667, 12, 18, 35, 41], [66_667, 100_000, 600, 0, 639, 3]])
    assert C.roi_box(roi, 0, 20_000, 640, 480) == (16, 45, 6, 35), "one frame, +4 px"
    assert C.roi_box(roi, 20_000, 40_000, 640, 480) == (14, 46, 6, 40), "union of frames 1 and 2"
    y0, y1, x0, x1 = C.roi_box(roi, 70_000, 80_000, 640, 480)
    assert (x1 == 640, y0 == 0) == (True, True) and y1 - y0 >= 7, (y0, y1, x0, x1)
    assert C.roi_box(roi, 200_000, 220_000, 640, 480) is None, "no labelled frame overlaps"
    assert C.roi_box(None, 0, 1, 640, 480) is None
    tiny = np.array([[0, 10, 5, 5, 5, 5]])
    y0, y1, x0, x1 = C.roi_box(tiny, 0, 10, 640, 480, margin=0)
    assert (y1 - y0, x1 - x0) == (7, 7), "SSIM needs at least 7 x 7"


def test_crop_samples_shifts_the_boxes_with_the_events():
    import neuro_common as C
    ev = _burst()                                  # windows 5-7 are the busiest
    roi = np.array([[0.0, 1e9, 1, 2, 3, 4]])
    s, r = C.crop_samples([(ev, 0, "g", None, None)], 20_000, 3, rois=[roi])
    assert r[0][0, 0] == -5 * 20_000 and r[0][0, 2:].tolist() == [1, 2, 3, 4], r[0].tolist()
    assert C.crop_samples([(ev, 0, "g", None, None)], 20_000, 3, rois=[None])[1] == [None]


def test_n3_scores_event_reid_inside_the_person_box(tmp_path):
    """A blank image (V4) scored ~0.97 on the full frame; inside the box it must score clearly lower."""
    _labelled_eventreid(tmp_path / "d")
    _run(["experiments/neuro_recon_attack.py", "--dataset", "eventreid", "--data", str(tmp_path / "d"), "--quick",
          "--out", str(tmp_path / "o")])
    d = json.loads((tmp_path / "o" / "recon_attack.json").read_text())
    assert d["scored"].startswith("inside the person box"), d["scored"]
    v4 = d["results"]["V4"]["ssim"][0]
    assert v4 < 0.8, f"V4 (no events) scored SSIM {v4}: the blank background is being scored"
    assert d["windows_unlabelled_skipped"] == 0
    # above 128 x 128 (the fixture is 160 x 120): Zhang 2024 is not run, and the table says why instead of dropping the row (16 Nov, B's QUICK table)
    assert "Zhang 2024" not in d["results"], "Zhang 2024 must not run above 128 x 128"
    assert "every empty pixel" in d["views_not_run"].get("Zhang 2024", ""), d["views_not_run"]
    assert "Zhang 2024: not run at 160 x 120" in (tmp_path / "o" / "recon_attack.md").read_text()


def test_n4_masks_its_loss_and_scores_inside_the_box():
    import neuro_learned_attack as N4
    m = N4.mask_of((2, 5, 3, 7), 8, 10)
    assert m.sum() == 3 * 4 and m[2:5, 3:7].all(), m
    assert N4.mask_of(None, 8, 10).all()


# ---------------------------------------------------------------- #59: N4 control (f) must not be worse than (c)
def test_n4_verdict_is_invalid_when_control_f_is_worse_than_the_median_frame():
    import neuro_learned_attack as N4
    rng = np.random.default_rng(0)
    g = [f"g{i % 6}" for i in range(48)]
    net, f_bad, c = 0.64 + 0.01 * rng.random(48), 0.015 + 0.01 * rng.random(48), 0.6 + 0.01 * rng.random(48)
    d, fc, valid, p1 = N4.verdict(net, f_bad, c, g)
    assert (valid, p1) == (False, None), f"control (f) {fc} below control (c): P1 must be invalid, got {valid, p1}"
    f_ok = c + 0.02
    _, _, valid, p1 = N4.verdict(f_ok + 0.001, f_ok, c, g)
    assert (valid, p1) == (True, True), "network = control (f) >= control (c): P1 passes"
    _, _, valid, p1 = N4.verdict(f_ok + 0.3, f_ok, c, g)
    assert (valid, p1) == (True, False), "network far above a valid control (f): P1 fails"


# ---------------------------------------------------------------- #62: N6 seals a fixed subset, in parallel
def test_n6_subset_is_fixed_sorted_and_complete_when_small():
    import neuro_task_accuracy as N6
    a, b = N6.subset(list(range(100)), 10, 3), N6.subset(list(range(100)), 10, 3)
    assert a == b and a == sorted(a) and len(set(a)) == 10, a
    assert N6.subset(list(range(5)), 10, 3) == [0, 1, 2, 3, 4]
    assert N6.subset(list(range(5)), None, 3) == [0, 1, 2, 3, 4]


def test_n6_parallel_sealing_equals_serial():
    import neuro_common as C
    import neuro_task_accuracy as N6
    S = C.synthetic_samples(10, 0)
    keys = list(range(10))
    for view in ("V2", "V3"):
        serial = N6.sealed_frames(S, view, keys, 1)
        par = N6.sealed_frames(S, view, keys, 2)
        assert serial.shape == par.shape and np.array_equal(serial, par), f"{view}: parallel frames differ"


def test_n6_decryption_check_runs_on_a_fixed_subset_and_still_decrypts():
    """Bug #65: the V3 decryption check (~26 s per DVS Gesture recording) runs on --check (64) fixed samples."""
    import neuro_common as C
    import neuro_task_accuracy as N6
    assert N6.CHECK_N == 64
    ct_te = C.synthetic_samples(6, seed=4)
    i_ck = N6.subset(ct_te, 3, 2)
    assert i_ck == N6.subset(ct_te, 3, 2) and len(i_ck) == 3, i_ck            # fixed and seeded
    N6._POOL = ct_te
    got = [N6._check_one(k) for k in i_ck]
    assert got == [1, 1, 1], f"positions {i_ck}: decryption event-equal flags {got}, expected all 1"
    assert N6.subset(ct_te, N6.CHECK_N, 2) == list(range(6)), "fewer samples than --check: all are checked"
