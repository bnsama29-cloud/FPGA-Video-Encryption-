"""Small runs sample every class / person (neuro.datasets.Strided, load_eventreid(every=...))."""
import numpy as np

from neuro import datasets


class FakeTonic:
    """Tonic-like dataset ordered by class, as Tonic's N-MNIST is."""

    def __init__(self, n_per_class=50, classes=10):
        self.items = [(c, i) for c in range(classes) for i in range(n_per_class)]
        self.data = [f"user{c:02d}/s{i}" for c, i in self.items]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        c, k = self.items[i]
        ev = np.zeros(3, dtype=[("t", "<u8"), ("x", "<i2"), ("y", "<i2"), ("p", "<i1")])
        ev["t"] = [10, 20, 30]
        return ev, c


def test_strided_view_spans_every_class():
    ds = FakeTonic()
    s = datasets.Strided(ds, len(ds) // 20)
    labels = {s[i][1] for i in range(len(s))}
    assert labels == set(range(10)) and len(s) == 20
    assert s.data[1] == ds.data[25]
    first20 = {ds[i][1] for i in range(20)}
    assert first20 == {0}                       # what a plain limit would have given


def test_eventreid_every_reads_spread_files(tmp_path):
    for person in range(6):
        for k in range(4):
            d = tmp_path / f"person{person}"
            d.mkdir(exist_ok=True)
            a = np.zeros(5, dtype=[("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "u1")])
            a["t"] = np.arange(5) * 100
            a["x"], a["y"] = 3, 4
            np.save(d / f"r{k}.npy", a)
    assert datasets.eventreid_count(tmp_path) == 24
    got = [lab for _, lab, _, _ in datasets.load_eventreid(tmp_path, every=4)]
    assert got == [0, 1, 2, 3, 4, 5]


def test_eventreid_text_layout_from_its_readme(tmp_path):
    """<id>/<camera>/events.txt; first row 'width height', then 't x y p' (µs with a fraction)."""
    for pid in ("001", "010"):
        for cam in ("cam01", "cam04"):
            d = tmp_path / "Event_ReId" / pid / cam
            (d / "labels").mkdir(parents=True)
            (d / "labels" / "label.json").write_text("{}")
            (d / "events.txt").write_text("640 480\n5636037.609375 327 322 1\n5636037.61875 330 278 0\n"
                                          "5636037.628125001 332 249 1\n")
    got = list(datasets.load_eventreid(tmp_path))
    assert [(lab, grp) for _, lab, grp, _ in got] == [(1, "1"), (1, "1"), (10, "10"), (10, "10")]
    ev, _, _, geom = got[0]
    assert (geom.W, geom.H) == (640, 480)
    assert ev["t"].tolist() == [5636038, 5636038, 5636038] and ev["x"].tolist() == [327, 330, 332]
    assert ev["p"].tolist() == [1, 0, 1]


def test_bucket_targets_equals_the_scalar_rule():
    from neuro.pad import FLOOR, LADDER, PadPolicy, bucket_target, bucket_targets
    n = np.arange(0, 300)
    for pol in (PadPolicy(FLOOR, 4), PadPolicy(LADDER, 2, 64), PadPolicy(LADDER, 3, 100), PadPolicy(LADDER, 1, 0)):
        assert bucket_targets(n, pol).tolist() == [bucket_target(int(v), pol) for v in n]
