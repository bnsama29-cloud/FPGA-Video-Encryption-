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
        serial = N6.sealed_frames(S, view, keys, 1, N6.DEFAULT_CONFIG)
        par = N6.sealed_frames(S, view, keys, 2, N6.DEFAULT_CONFIG)
        assert serial.shape == par.shape and np.array_equal(serial, par), f"{view}: parallel frames differ"


def test_n6_decryption_check_runs_on_a_fixed_subset_and_still_decrypts():
    """Bug #65: the V3 decryption check (~26 s per DVS Gesture recording) runs on --check (64) fixed samples."""
    import neuro_common as C
    import neuro_task_accuracy as N6
    assert N6.CHECK_N == 64
    ct_te = C.synthetic_samples(6, seed=4)
    i_ck = N6.subset(ct_te, 3, 2)
    assert i_ck == N6.subset(ct_te, 3, 2) and len(i_ck) == 3, i_ck            # fixed and seeded
    got = [N6._check_one((ct_te[k], k)) for k in i_ck]
    assert got == [1, 1, 1], f"positions {i_ck}: decryption event-equal flags {got}, expected all 1"
    assert N6.subset(ct_te, N6.CHECK_N, 2) == list(range(6)), "fewer samples than --check: all are checked"


def test_n5_knn_in_blocks_equals_the_one_shot_computation():
    """Bug #66: N5's 5-NN built one (n_test, n_train, 7) array (~69 GB on N-MNIST, Killed). Blocks must not change it."""
    import neuro_leakage as N5
    rng = np.random.default_rng(1)
    Zte, Ztr = rng.normal(size=(301, 7)), rng.normal(size=(457, 7))
    Ztr[10] = Ztr[11]                                                     # a tie: argsort order must be kept
    ref = np.argsort(((Zte[:, None] - Ztr[None]) ** 2).sum(-1), 1)[:, :5]
    for mb in (1, 7 * 8 * 457 * 3, 1 << 30):                              # 1 row, 3 rows, everything per block
        got = N5.knn_indices(Zte, Ztr, 5, max_bytes=mb)
        bad = np.argwhere(got != ref)
        assert not len(bad), f"max_bytes {mb}: first mismatch at {tuple(bad[0])}: got {got[tuple(bad[0])]}, " \
                             f"expected {ref[tuple(bad[0])]}"
    assert N5.knn_indices(Zte, Ztr[:3], 5).shape == (301, 3), "fewer training rows than k"


def test_dataset_groups_are_unique_across_splits_and_name_the_split(tmp_path):
    """Bug #67: N-MNIST groups were str(index) in both splits (train 5 and test 5 shared a group)."""
    from neuro import datasets as D

    class Fake:                                        # Tonic-style: len, [i] -> (events, target)
        def __init__(self, n):
            self.n = n
        def __len__(self):
            return self.n
        def __getitem__(self, i):
            ev = np.zeros(3, dtype=[("t", "<i8"), ("x", "<i2"), ("y", "<i2"), ("p", "<i1")])
            ev["t"] = [0, 5, 9]
            return ev, i % 10
    tr = [g for _, _, g, _ in D.load_nmnist(None, "train", dataset=Fake(4))]
    te = [g for _, _, g, _ in D.load_nmnist(None, "test", dataset=Fake(4))]
    assert not set(tr) & set(te), f"train and test share groups {sorted(set(tr) & set(te))}"
    assert all(g.startswith("train/") for g in tr) and all(g.startswith("test/") for g in te), (tr, te)
    gtr = [g for _, _, g, _ in D.load_dvsgesture(None, "train", dataset=Fake(2))]
    assert gtr == ["train/0", "train/1"], gtr


def test_n5_uses_the_official_test_split_when_groups_name_it():
    import neuro_leakage as N5
    g = np.array(["train/0", "train/1", "train/2", "test/0", "test/1"])
    got = sorted(N5.official_test_groups(g).tolist())
    assert got == ["test/0", "test/1"], f"official split: got {got}, expected ['test/0', 'test/1']"
    persons = np.array(["p1", "p2", "p3", "p4"])                    # Event-ReId: no split prefix, half of the groups
    assert N5.official_test_groups(persons).tolist() == ["p3", "p4"]


def test_n3_target_is_the_plaintext_e2vid_reconstruction_when_available():
    """Bug #68: without ground truth N3 picked the most structured plain image (the sparse count image), so plain
    scored 1.000 by construction and the median frame beat the count-series control."""
    import neuro_recon_attack as N3
    e2 = np.full((8, 8), 0.4)
    e2[2, 3] = 1.7                                                       # E2VID output can leave [0, 1]
    cnt = np.zeros((8, 8))
    cnt[1:7, 1:7] = 9.0                                                  # far more contrast than e2
    tgt, kind = N3.pick_target({"count": cnt, "e2vid": e2}, None)
    assert kind == "plaintext E2VID reconstruction", kind
    assert tgt.max() == 1.0 and tgt[0, 0] == 0.4, "E2VID target must be used, clipped to [0, 1]"
    tgt, kind = N3.pick_target({"count": cnt, "integration": e2}, None)  # no E2VID: smoke-run fallback, labelled
    assert kind.startswith("most structured") and tgt is cnt, kind


class _FakeE2VID:
    """Stands in for N3's Learned: recurrent state = number of calls since reset."""
    def __init__(self):
        self.n = 0
    def reset(self):
        self.n = 0
    def __call__(self, ev, geom):
        self.n += 1
        return {"e2vid": np.full((geom.H, geom.W), 0.1 * self.n)}


def test_n4_trains_toward_plaintext_e2vid_targets_reset_per_recording():
    import neuro_common as C
    import neuro_learned_attack as N4
    samples = [(ev, lab, grp, geom, None) for ev, lab, grp, geom, _ in C.synthetic_samples(2, seed=3)]
    win = 2_000
    tg = N4.plain_targets(samples, win, _FakeE2VID())
    assert [round(float(t[0][0, 0]), 3) for t in tg] == [0.1, 0.1], "E2VID state must restart per recording"
    assert round(float(tg[0][1][0, 0]), 3) == 0.2, "windows of one recording run in order through E2VID"
    W_ = N4.windows_of(samples, "V2", 1024, win, 2, None, tg)
    first = W_[0][2]
    assert np.allclose(first, tg[0][0]), f"N4 target is not the plaintext E2VID window (got mean {first.mean()})"
    assert N4.plain_targets(samples, win, None) == [None, None], "without E2VID: count-image fallback"


def test_n4_control_f_starts_at_the_median_frame_and_learns_a_correction():
    """Bug #69: control (f) was an MLP from ~300 counts to every pixel; on Event-ReId it did not even learn the mean
    frame (0.29 vs 0.57 for the median), so every view was 'invalid'. It is now median + learned correction."""
    torch = pytest.importorskip("torch")
    import neuro_learned_attack as N4
    rng = np.random.default_rng(0)
    H, W, n = 6, 5, 4
    med = rng.uniform(size=(H, W)).astype(np.float32)
    _, f = N4.build(torch, H, W, n, median=med)
    x = torch.from_numpy(rng.uniform(size=(3, n)).astype(np.float32))
    out = f(x).detach().numpy().reshape(3, H, W)
    assert np.allclose(out, med[None], atol=1e-6), "untrained control (f) must equal control (c), the median frame"
    Y = np.stack([med * 0 + 0.9] * 8).astype(np.float32)                  # a target the counts could explain
    X = rng.uniform(size=(8, n)).astype(np.float32)
    f = N4.train(torch, f, X, Y.reshape(8, -1), 30, "cpu", 0, bs=8)
    after = np.abs(f(torch.from_numpy(X)).detach().numpy() - Y.reshape(8, -1)).mean()
    assert after < np.abs(med - 0.9).mean(), f"training did not move control (f) toward the target ({after})"


def test_n4_holdout_split_is_by_group_and_never_empty_for_fit():
    """Bug #70: model selection on held-out training recordings (never windows of the same recording)."""
    import neuro_learned_attack as N4
    groups = ["a", "a", "b", "c", "c", "d", "e"]
    fit, hold = N4.holdout_split(groups)
    assert {groups[i] for i in hold} == {"e"} and set(fit) | set(hold) == set(range(7)), (fit, hold)
    assert not {groups[i] for i in fit} & {groups[i] for i in hold}, "a group is on both sides"
    fit1, hold1 = N4.holdout_split(["x", "x"])
    assert len(hold1) == 0 and len(fit1) == 2, "a single group cannot be split"


def test_n4_training_keeps_the_untrained_control_when_training_hurts_held_out_data():
    """Bug #70: epoch 0 of control (f) is control (c); selection must keep it when every update makes held-out worse."""
    torch = pytest.importorskip("torch")
    import neuro_learned_attack as N4
    rng = np.random.default_rng(1)
    H, W, n = 4, 4, 3
    med = np.full((H, W), 0.5, np.float32)
    _, f = N4.build(torch, H, W, n, median=med)
    X = rng.uniform(size=(16, n)).astype(np.float32)
    Yfit = np.full((16, H * W), 1.0, np.float32)                         # pulls the correction up ...
    Yval = np.full((4, H * W), 0.5, np.float32)                          # ... which hurts the held-out recordings
    f = N4.train(torch, f, X, Yfit, 20, "cpu", 0, bs=16, val=(X[:4], Yval, None))
    out = f(torch.from_numpy(X[:4])).detach().numpy()
    assert np.allclose(out, 0.5, atol=1e-6), f"held-out selection should keep the median frame, got {out.mean()}"


def test_n4_masked_ssim_scores_the_same_region_as_the_test_metric():
    """Bug #72: weights are selected by held-out SSIM in the scoring region; it must equal N4's test-time metric."""
    from skimage.metrics import structural_similarity
    import neuro_common as C
    import neuro_learned_attack as N4
    rng = np.random.default_rng(5)
    p, t = rng.uniform(size=(40, 50)), rng.uniform(size=(40, 50))
    box = (5, 30, 8, 41)
    want = structural_similarity(C.in_roi(p, box), C.in_roi(t, box), data_range=1.0)
    got = N4.masked_ssim(p, t, N4.mask_of(box, 40, 50))
    assert abs(got - want) < 1e-12, f"selection SSIM {got} != test SSIM {want}"
    assert abs(N4.masked_ssim(p, t) - structural_similarity(p, t, data_range=1.0)) < 1e-12, "no box: full frame"


def test_n4_selection_by_ssim_keeps_the_median_frame_when_updates_hurt_held_out_ssim():
    torch = pytest.importorskip("torch")
    import neuro_learned_attack as N4
    rng = np.random.default_rng(2)
    H, W, n = 8, 8, 3
    med = rng.uniform(0.2, 0.8, size=(H, W)).astype(np.float32)        # structured: SSIM of med vs med = 1
    _, f = N4.build(torch, H, W, n, median=med)
    X = rng.uniform(size=(16, n)).astype(np.float32)
    Yfit = np.full((16, H * W), 0.5, np.float32)                         # pulls toward a flat frame ...
    Yval = np.stack([med.reshape(-1)] * 4)                               # ... which ruins held-out structure
    f = N4.train(torch, f, X, Yfit, 20, "cpu", 0, bs=16, val=(X[:4], Yval, None), shape=(H, W))
    out = f(torch.from_numpy(X[:4])).detach().numpy().reshape(4, H, W)
    assert np.allclose(out, med[None], atol=1e-6), "SSIM selection must keep the epoch-0 (median) weights"


def test_n8_readers_check_payloads_with_expelliarmus_event_by_event(tmp_path):
    """Bug #73: claim (iii)'s independent-reader check was a placeholder ("run on Kaggle") that never ran."""
    pytest.importorskip("expelliarmus")
    import neuro_common as C
    import neuro_perm_strength as N8
    res = N8.readers(C.synthetic_samples(1, seed=1), tmp_path)
    for lv in ("V1", "V2", "V3"):
        n = res[lv]["n_cd"]
        want = f"{n} read, {n} equal to ours, in range"
        assert res[lv]["expelliarmus"] == want, f"{lv}: got {res[lv]['expelliarmus']!r}, expected {want!r}"
        assert res[lv]["tonic"] == "no EVT 2.0 RAW reader in Tonic 1.7.0"


def test_n8_expelliarmus_check_reports_a_mismatch(tmp_path):
    pytest.importorskip("expelliarmus")
    import neuro_common as C
    import neuro_perm_strength as N8
    from neuro import evt2
    ev, _, _, g, _ = C.synthetic_samples(1, seed=2)[0]
    words = evt2.encode(ev, 1024)
    path = tmp_path / "x.raw"
    evt2.write_raw(path, words, g)
    ours, _ = evt2.decode(words)
    wrong = ours.copy()
    wrong["x"][0] = (wrong["x"][0] + 1) % g.W                        # one event differs from what the file holds
    got = N8.expelliarmus_check(path, wrong, g)
    assert got == f"{len(ours)} read, {len(ours) - 1} equal to ours, in range", got


def test_n11_evt3_bytes_writes_every_view_and_round_trips(tmp_path):
    """Bug #74: N11's EVT 3.0 column was a placeholder ("needs expelliarmus (Kaggle job)") on Kaggle itself."""
    pytest.importorskip("expelliarmus")
    from expelliarmus import Wizard
    import neuro_common as C
    import neuro_fpe_utility as N11
    S = C.synthetic_samples(1, seed=3)
    got = N11.evt3_bytes(S)
    assert set(got) == {"plain", "V1", "V2", "V3"} and all(v > 0 for v in got.values()), got
    ev = np.sort(S[0][0], order="t", kind="stable")                  # what evt3_bytes writes for plain
    f = tmp_path / "p.raw"
    Wizard(encoding="evt3").save(f, ev)
    assert got["plain"] == f.stat().st_size
    back = Wizard(encoding="evt3", fpath=f).read()
    assert len(back) == len(ev)
    for k in "txyp":
        bad = np.flatnonzero(back[k].astype(np.int64) != ev[k].astype(np.int64))
        assert not len(bad), f"field {k}: first mismatch at {bad[0]}: got {back[k][bad[0]]}, expected {ev[k][bad[0]]}"


def test_n11_evt3_bytes_says_when_expelliarmus_is_missing(monkeypatch):
    import neuro_fpe_utility as N11
    monkeypatch.setitem(sys.modules, "expelliarmus", None)
    assert N11.evt3_bytes([]) == "not run: expelliarmus not installed"


# ---------------------------------------------------------------- #74: N6 model under the gate, time-binned input
def test_n6_features_bins_tell_a_stream_from_its_time_reverse():
    """DVS Gesture separates clockwise from counter-clockwise rotation: one count frame cannot, BINS[dvsgesture] can."""
    import neuro_common as C
    import neuro_task_accuracy as N6
    ev, _, _, g, _ = C.synthetic_samples(1, seed=5)[0]
    rev = ev.copy()
    rev["t"] = ev["t"].max() + ev["t"].min() - ev["t"]           # same events, played backwards
    rev = rev[np.argsort(rev["t"], kind="stable")]
    assert np.array_equal(N6.features(ev, g, 1), N6.frame(ev, g))
    assert np.array_equal(N6.features(ev, g, 1), N6.features(rev, g, 1)), "one frame is blind to time order"
    nb = 8
    f, r = N6.features(ev, g, nb), N6.features(rev, g, nb)
    assert f.shape == (2 * nb, g.H, g.W) and f.max() == 1.0
    assert not np.array_equal(f, r), "time bins must see the order"
    assert np.allclose(f.reshape(nb, 2, g.H, g.W).sum(0) / f.reshape(nb, 2, g.H, g.W).sum(0).max(), N6.frame(ev, g))


def test_n6_cnn_learns_and_evaluates_deterministically():
    """The new CNN (BatchNorm, dropout) must be evaluated in eval mode: two evaluations give the same accuracy."""
    torch = pytest.importorskip("torch")
    import neuro_task_accuracy as N6
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 128)
    X = rng.random((128, 4, 34, 34), dtype=np.float32) * 0.1
    X[y == 1, 0, :17] += 1.0                                       # class 1: bright top half in channel 0
    m, acc = N6.fit_eval(torch, X[:96], y[:96], X[96:], y[96:], 2, 10, 0, "cpu", bs=16)
    assert acc == 1.0, f"separable toy task: accuracy {acc}"
    m.train()
    assert N6.evaluate(torch, m, X[96:], y[96:], "cpu") == acc and not m.training, "evaluate() must switch to eval"
    assert N6.cnn(torch, 11, 16)(torch.zeros(2, 16, 128, 128)).shape == (2, 11)      # DVS Gesture input


# ---------------------------------------------------------------- #75: N6 gate before sealing, model selection
def test_n6_gate_runs_before_any_sealing(monkeypatch, tmp_path):
    """Bug #75: N6 sealed ~10 h of DVS Gesture before learning that the clean model failed its gate. A failing gate
    must now end the run without one call of the sealer."""
    torch = pytest.importorskip("torch")
    import neuro_task_accuracy as N6
    calls = []
    monkeypatch.setattr(N6, "sealed_frames", lambda *a, **k: calls.append(a[1]) or np.zeros((1,)))
    monkeypatch.setattr(N6, "GATE", {"synthetic": 1.01})                 # unreachable: the gate must fail
    monkeypatch.setattr(sys, "argv", ["n6", "--quick", "--limit", "24", "--out", str(tmp_path)])
    N6.main()
    data = json.loads((tmp_path / "task_accuracy.json").read_text())
    assert data["gate"]["passes"] is False and calls == [], f"sealed {calls} after a failed gate"
    assert data["decrypted_event_equal"] == "not run (gate failed)"


def test_n6_passing_gate_seals_every_view_and_adds_the_subset_reference(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    import neuro_task_accuracy as N6
    monkeypatch.setattr(sys, "argv", ["n6", "--quick", "--limit", "24", "--views", "V2", "V4", "--workers", "1",
                                      "--out", str(tmp_path)])
    N6.main()                                                             # synthetic data: no gate
    data = json.loads((tmp_path / "task_accuracy.json").read_text())
    assert {"clean", "clear_subset", "V2", "V4"} <= set(data["results"]), sorted(data["results"])
    assert data["decrypted_event_equal"].endswith(f"of {data['ciphertext_subset']['test']}"), data["decrypted_event_equal"]


def test_n6_features_downsample_sums_blocks():
    import neuro_common as C
    import neuro_task_accuracy as N6
    ev, _, _, g, _ = C.synthetic_samples(1, seed=6)[0]
    full = N6.bins(ev, g, 4).reshape(8, g.H, g.W)
    got = N6.features(ev, g, 4, 2)
    ref = full.reshape(8, g.H // 2, 2, g.W // 2, 2).sum((2, 4))
    assert got.shape == (8, g.H // 2, g.W // 2) and np.allclose(got, ref / ref.max())
    assert np.isclose(got.sum() * ref.max(), len(ev)), "every event counted once"


def test_n6_shift_augmentation_moves_content_and_keeps_shape():
    torch = pytest.importorskip("torch")
    import neuro_task_accuracy as N6
    x = torch.zeros(3, 2, 10, 10)
    x[:, :, 5, 5] = 1.0
    g = torch.Generator().manual_seed(0)
    y = N6.shift_batch(torch, x, 2, g)
    assert y.shape == x.shape and torch.equal(y.sum((1, 2, 3)), x.sum((1, 2, 3))), "a 2 px shift of a centre dot keeps it"
    pos = [tuple(torch.nonzero(y[k, 0])[0].tolist()) for k in range(3)]
    assert all(3 <= r <= 7 and 3 <= c <= 7 for r, c in pos), pos
    assert N6.shift_batch(torch, x, 0, g) is x


def test_n6_every_candidate_builds_on_its_dvs_input(monkeypatch):
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    import neuro_common as C
    import neuro_task_accuracy as N6
    monkeypatch.setattr(N6, "PRETRAINED", False)                         # no weight download in tests
    g = C.Geometry("dvs", 128, 128)
    ev = C.synthetic_samples(1, seed=2)[0][0]
    for name, c in N6.CANDIDATES.items():
        x = N6.features_cfg(ev, g, c)
        out = N6.cnn(torch, 11, x.shape[0], c["arch"])(torch.from_numpy(np.stack([x, x])))
        assert out.shape == (2, 11), (name, x.shape, out.shape)
        assert name in N6.ROUNDS, f"{name}: selection round not recorded"


def test_n6_ts3_counts_events_and_keeps_the_last_time():
    import neuro_common as C
    import neuro_task_accuracy as N6
    g = C.Geometry("t", 8, 8)
    ev = np.zeros(4, C.synthetic_samples(1)[0][0].dtype)
    ev["t"], ev["x"], ev["y"], ev["p"] = [0, 10, 20, 30], [1, 1, 2, 3], [1, 1, 2, 3], [1, 1, 0, 1]
    x = N6.ts3(ev, g)
    assert x.shape == (3, 8, 8)
    assert x[1, 1, 1] == 1.0 and x[0, 2, 2] == 0.5 and x[1, 3, 3] == 0.5, "ON/OFF counts scaled by the maximum (2)"
    assert np.isclose(x[2, 1, 1], 10 / 30, atol=1e-6) and np.isclose(x[2, 3, 3], 1.0) and x[2, 0, 0] == 0.0


def test_n6_resnet18_first_conv_keeps_the_pretrained_response_on_flat_input(monkeypatch):
    """Init of the 2*nb-channel conv: a flat input of value v gives the same response as the original RGB conv on
    (v, v, v), so the pretrained filters still mean something on the first step."""
    torch = pytest.importorskip("torch")
    tv = pytest.importorskip("torchvision")
    import copy
    import neuro_task_accuracy as N6
    torch.manual_seed(0)
    ref = tv.models.resnet18(weights=None)
    monkeypatch.setattr(tv.models, "resnet18", lambda weights=None: copy.deepcopy(ref))
    m = N6.resnet18(torch, 11, 32, pretrained=False)
    with torch.no_grad():
        a = m.conv1(torch.full((1, 32, 16, 16), 0.5))
        b = ref.conv1(torch.full((1, 3, 16, 16), 0.5))
    assert torch.allclose(a, b, atol=1e-5), f"max difference {float((a - b).abs().max())}"
    assert m.fc.out_features == 11
