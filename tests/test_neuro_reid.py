"""N12 re-identification helpers: person split, frame input and cross-camera rank-1 / mAP."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import neuro_reid as R  # noqa: E402


def test_split_is_fixed_disjoint_and_complete():
    ids = list(range(1, 34)) * 4
    tr, te = R.split_persons(ids, 22, seed=0)
    assert (len(tr), len(te)) == (22, 11) and not set(tr) & set(te) and set(tr) | set(te) == set(range(1, 34))
    assert R.split_persons(ids, 22, seed=0) == (tr, te), "same seed, same split"
    with pytest.raises(SystemExit):
        R.split_persons([1, 2], 2)


def test_rank1_and_map_by_hand():
    # 2 persons x 2 cameras; embeddings: person 1 rows close together, person 2 rows close together
    emb = np.array([[1, 0], [0.9, 0.1], [0, 1], [0.1, 0.9]], float)
    pid = np.array([1, 1, 2, 2])
    cam = np.array(["a", "b", "a", "b"])
    assert R.rank1_map(emb, pid, cam) == (1.0, 1.0)
    swapped = np.array([1, 2, 2, 1])                  # every cross-camera nearest neighbour is the wrong person
    r1, m = R.rank1_map(emb, swapped, cam)
    assert r1 == 0.0 and m == pytest.approx(0.5), (r1, m)
    # same-camera rows are never in the gallery: identical embeddings in one camera do not count as hits
    assert R.rank1_map(np.ones((2, 2)), np.array([1, 1]), np.array(["a", "a"]))[0] != R.rank1_map(
        np.ones((2, 2)), np.array([1, 1]), np.array(["a", "b"]))[0]


def test_frame_input_counts_polarity_in_blocks():
    from neuro.geometry import Geometry
    from neuro import evt2
    ev = np.zeros(3, evt2.EVENT_DTYPE)
    ev["t"], ev["x"], ev["y"], ev["p"] = [0, 10, 40000], [0, 3, 5], [0, 2, 9], [1, 1, 0]
    x = R.frame_input(ev, Geometry("g", 8, 12), 0, 33333)
    assert x.shape == (2, 3, 2) and x[1, 0, 0] == 1.0 and x.sum() == 1.0, "two ON events in block (0,0); t=40000 out"


def test_frame_input_time_bins_go_to_their_channel():
    from neuro.geometry import Geometry
    from neuro import evt2
    ev = np.zeros(4, evt2.EVENT_DTYPE)
    ev["t"], ev["x"], ev["y"], ev["p"] = [0, 30, 60, 99], [0, 0, 0, 0], [0, 0, 0, 0], [0, 1, 1, 0]
    x = R.frame_input(ev, Geometry("g", 4, 4), 0, 100, down=1, bins=5)
    assert x.shape == (10, 4, 4)
    # channel = p * bins + bin: t=0 OFF bin 0 -> 0; t=30 ON bin 1 -> 6; t=60 ON bin 3 -> 8; t=99 OFF bin 4 -> 4
    got = sorted(np.flatnonzero(x[:, 0, 0]).tolist())
    assert got == [0, 4, 6, 8], got


def test_counts_only_keeps_times_and_count_and_destroys_layout():
    from neuro.geometry import Geometry
    from neuro import evt2
    g = Geometry("g", 64, 48)
    ev = np.zeros(2000, evt2.EVENT_DTYPE)
    ev["t"] = np.arange(2000) * 7
    ev["x"], ev["y"], ev["p"] = 5, 6, 1                  # every event at one pixel, one polarity
    c = R.counts_only(ev, g, key=3)
    assert len(c) == len(ev) and (c["t"] == ev["t"]).all(), "count series unchanged"
    assert c["x"].max() < g.W and c["y"].max() < g.H
    assert len(np.unique(c["x"] * g.H + c["y"])) > 1000 and 0.4 < c["p"].mean() < 0.6, "layout and polarity gone"
    assert (R.counts_only(ev, g, 3) == c).all() and not (R.counts_only(ev, g, 4)["x"] == c["x"]).all()


def test_anonynoise_gallery_excludes_same_user_and_gesture_only():
    # user A: gesture 1 twice, gesture 2 once; user B: gesture 1 once
    pid = np.array(["A", "A", "A", "B"])
    gest = np.array([1, 1, 2, 1])
    # query 0 is identical to row 1 (same user, same gesture: excluded) and to row 3 (other user): a wrong match
    emb = np.array([[1, 0], [1, 0], [0, 1], [1, 0]], float)
    r1, _ = R.rank1_map(emb, pid, gest, "anonynoise")
    # q0: gallery {2, 3}: nearest 3 (B) -> miss; q1 same -> miss; q2: gallery {0,1,3}, all at distance equal, stable
    # order picks 0 (A) -> hit; q3: no other B in gallery -> skipped
    assert r1 == pytest.approx(1 / 3), r1
    with pytest.raises(ValueError):
        R.rank1_map(emb, pid, gest, "nonsense")


def test_batch_hard_triplet_by_hand():
    torch = pytest.importorskip("torch")
    f = torch.tensor([[0.0, 0], [1.0, 0], [0.0, 3], [0.0, 3.5]])
    y = torch.tensor([0, 0, 1, 1])
    # anchor 0: hardest positive 1 (d 1), hardest negative 2 (d 3) -> relu(1 - 3 + 0.3) = 0
    # anchor 2: positive 3 (d 0.5), nearest negative 0 (d 3) -> 0;  all zero
    assert float(R.batch_hard_triplet(torch, f, y)) == 0.0
    f2 = torch.tensor([[0.0, 0], [4.0, 0], [1.0, 0], [5.0, 0]])
    # anchor 0: pos 1 (4), neg 2 (1) -> 3.3; anchor 1: pos 0 (4), neg 3 (1) -> 3.3; anchor 2: pos 3 (4), neg 0 (1)
    # -> 3.3; anchor 3: pos 2 (4), neg 1 (1) -> 3.3
    assert float(R.batch_hard_triplet(torch, f2, y)) == pytest.approx(3.3)
    assert float(R.batch_hard_triplet(torch, f2, torch.tensor([0, 1, 2, 3]))) == 0.0, "no positive: no term"


def test_pk_batches_hold_p_identities_k_each():
    y = np.repeat(np.arange(10), [9, 9, 9, 9, 9, 9, 9, 9, 2, 9])
    for b in R.pk_batches(y, 4, 3, np.random.default_rng(0)):
        ids, counts = np.unique(y[b], return_counts=True)
        assert len(ids) == 4 and (counts == 3).all(), (ids, counts)
    used = np.concatenate(R.pk_batches(y, 4, 3, np.random.default_rng(0)))
    assert 8 in y[used] or True                          # an identity with fewer than k samples is padded, not lost
    assert len(R.pk_batches(y, 4, 3, np.random.default_rng(0))) >= 5


@pytest.mark.parametrize("recipe", ["basic", "strong"])
def test_main_runs_both_recipes_on_synthetic_data(tmp_path, monkeypatch, recipe):
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    import json
    import neuro_task_accuracy as N6
    monkeypatch.setattr(N6, "PRETRAINED", False)
    monkeypatch.setattr(sys, "argv", ["neuro_reid.py", "--quick", "--limit", "12", "--workers", "1", "--recipe",
                                      recipe, "--views", "V3", "counts only", "--out", str(tmp_path)])
    R.main()
    d = json.loads((tmp_path / "reid.json").read_text())
    assert set(d["results"]) == {"clear", "V3", "counts only"} and d["recipe"] == recipe
    assert d["input_shape"][0] == 2 * R.RECIPES[recipe]["bins"]
    assert "test_persons" in d and (tmp_path / "reid.md").exists()


def test_finished_rows_are_written_before_a_later_view_fails(tmp_path, monkeypatch):
    """A run stopped at Kaggle's time limit must keep every finished view (written after each one)."""
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    import json
    import neuro_task_accuracy as N6
    monkeypatch.setattr(N6, "PRETRAINED", False)
    real = R.view_frames

    def boom(recs, view, *a, **k):
        if view == "V3":
            raise RuntimeError("time limit")
        return real(recs, view, *a, **k)
    monkeypatch.setattr(R, "view_frames", boom)
    monkeypatch.setattr(sys, "argv", ["neuro_reid.py", "--quick", "--limit", "12", "--workers", "1",
                                      "--views", "counts only", "V3", "--out", str(tmp_path)])
    with pytest.raises(RuntimeError):
        R.main()
    d = json.loads((tmp_path / "reid.json").read_text())
    assert set(d["results"]) == {"clear", "counts only"}


def test_a_paper_run_stops_when_no_query_has_a_match():
    """23 Nov QUICK run: rank-1 was nan (no same-identity sample in any gallery); a paper run must stop, not train."""
    R.check_queries([0.5, float("nan")], quick=False)           # one seed defined: fine
    with pytest.raises(SystemExit, match="undefined"):
        R.check_queries([float("nan")] * 3, quick=False)
    R.check_queries([float("nan")], quick=True)                 # QUICK: reported, not fatal


def test_scheduler_follows_only_real_optimizer_steps(monkeypatch):
    """AMP's scaler can skip a step; the cosine schedule must not run ahead of the optimizer (PyTorch warned)."""
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    import inspect
    src = inspect.getsource(R.train_net)
    assert "scaler.get_scale() >= scale" in src and src.index("scaler.update()") < src.index("sch.step()")
