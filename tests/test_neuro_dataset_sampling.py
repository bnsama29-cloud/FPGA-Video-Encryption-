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
