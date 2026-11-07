"""Small runs sample every class / person (neuro.datasets.Strided, load_eventreid(every=...))."""
import numpy as np
import pytest

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


def _write_eventreid(root, rows_by_file):
    for (pid, cam), rows in rows_by_file.items():
        d = root / "Event_ReId" / pid / cam
        (d / "labels").mkdir(parents=True)
        (d / "labels" / "label.json").write_text("{}")
        (d / "events.txt").write_text("640 480\n" + "".join(f"{t} {x} {y} {p}\n" for t, x, y, p in rows))


# rows as in Event_ReId/001/cam01/events.txt (t in ms with a fraction; the file spans 3229.9 ms)
_ROWS = [("66626956.4031432", 213, 291, 1), ("66626956.40523866", 186, 230, 1), ("66630186.29694171", 205, 215, 0)]


def test_eventreid_text_layout_from_its_readme(tmp_path):
    """<id>/<camera>/events.txt; first row 'width height', then 't x y p' with t in ms (TESTING bug #51)."""
    _write_eventreid(tmp_path, {(pid, cam): _ROWS for pid in ("001", "010") for cam in ("cam01", "cam04")})
    got = list(datasets.load_eventreid(tmp_path))
    assert [(lab, grp) for _, lab, grp, _ in got] == [(1, "1"), (1, "1"), (10, "10"), (10, "10")]
    ev, _, _, geom = got[0]
    assert (geom.W, geom.H) == (640, 480)
    assert ev["t"].tolist() == [66626956403, 66626956405, 66630186297], ev["t"].tolist()   # ms -> µs
    assert ev["x"].tolist() == [213, 186, 205] and ev["p"].tolist() == [1, 1, 0]
    span_s = (int(ev["t"][-1]) - int(ev["t"][0])) / 1e6
    assert abs(span_s - 3.2299) < 1e-3, f"span {span_s} s, expected 3.2299 s (README: 3-4 s per recording)"


def test_eventreid_wrong_unit_is_refused(tmp_path):
    """Read as µs (t_scale=1) the same file would span 3.2 ms: the reader must raise, not run on it."""
    _write_eventreid(tmp_path, {("001", "cam01"): _ROWS})
    with pytest.raises(ValueError, match="wrong timestamp unit"):
        list(datasets.load_eventreid(tmp_path, t_scale=1.0))


def test_bucket_targets_equals_the_scalar_rule():
    from neuro.pad import FLOOR, LADDER, PadPolicy, bucket_target, bucket_targets
    n = np.arange(0, 300)
    for pol in (PadPolicy(FLOOR, 4), PadPolicy(LADDER, 2, 64), PadPolicy(LADDER, 3, 100), PadPolicy(LADDER, 1, 0)):
        assert bucket_targets(n, pol).tolist() == [bucket_target(int(v), pol) for v in n]


def test_count_cache_round_trip(tmp_path):
    from neuro.geometry import SENSORS
    rng = np.random.default_rng(0)
    items = []
    for i in range(30):
        ev = np.zeros(50, dtype=[("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "u1")])
        ev["t"] = np.sort(rng.integers(1000, 100000, 50))
        items.append((ev, i % 3, f"g{i}", SENSORS["nmnist"]))
    assert datasets.cache_counts(iter(items), tmp_path / "c.npz") == 30
    back = datasets.load_counts(tmp_path / "c.npz")
    for (ev, lab, grp, _), (series, lab2, grp2, wh, b0) in zip(items, back):
        _, want = datasets.bucket_counts(ev)
        assert series.tolist() == want.tolist() and (lab2, grp2, wh) == (lab, grp, (34, 34))
