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
