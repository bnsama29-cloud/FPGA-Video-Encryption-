"""Event datasets for paper 2 (DESIGN.md §7.1, §8.3): N-MNIST, DVS Gesture, Event-ReId, SHA-256 manifests and
the per-bucket count cache used by N5.

Every loader is a generator of samples `(events, label, group, geom)`:
- `events`: structured array in EVENT_DTYPE (t µs, x, y, p in {0, 1}), sorted by t (stable);
- `label`: the class (digit, gesture index, person id) or None when the files do not give one;
- `group`: the cluster used for cluster-bootstrap statistics (recording/subject id, a string);
- `geom`: `neuro.geometry.Geometry` of the sensor.

Tonic (1.7.0, Kaggle only; not installable on the laptop's Python 3.14) is imported lazily inside the loaders,
so this module imports anywhere. `cache_counts` turns any loader's samples into a small .npz that N5 analyses on
the laptop without Tonic.

Readers and what each one assumes (an assumption that a file contradicts raises ValueError naming the file):

- `load_nmnist(root, split)`: `backend="tonic"` uses `tonic.datasets.NMNIST(save_to=root, train=...)`. The
  `backend="native"` reader decodes the original `.bin` files itself with the 5-byte layout Tonic's
  `read_mnist_file` uses (`lit_formats_data.md` §6): x = b0, y = b1, p = b2 >> 7,
  t = ((b2 & 0x7F) << 16) | (b3 << 8) | b4 µs. It looks for `*.bin` files under a directory whose name is the
  split (`Train`/`Test`, any case), with the digit as the parent directory name. `backend="auto"` uses Tonic
  when it imports, else the native reader. group = the file's stem (N-MNIST samples are independent images).
- `load_dvsgesture(root, split)`: Tonic only (Tonic's own preprocessed files are its official train/test
  split). group = the subject parsed from a `user<NN>` path component of the sample's file, else the index.
- `load_eventreid(root, split)`: the Event-ReId file format is read in the Kaggle QUICK run, not assumed
  (DESIGN.md §2.3), so this reader is tolerant: it accepts `.npy` and `.npz` (structured arrays with named
  fields, or plain numeric arrays with `columns=` given), `.h5`/`.hdf5` (h5py, lazily; datasets named
  t/x/y/p or aliases, or one (N, 4) dataset with `columns=`), and `.txt`/`.csv` (numeric columns; `columns=`
  required). Field aliases: t <- t, ts, timestamp, timestamps; p <- p, pol, polarity. Event-ReId timestamps
  are in **milliseconds** with a fractional part, so `t_scale` defaults to 1e3 (µs = t * t_scale). Evidence
  (001/cam01, Zenodo 8256439, 7 Nov 2026): the file spans 3229.9 units and its label.json has 95 frames of
  33.3 ms = 3163 ms, and the README gives 3-4 s per recording; read as µs the same file would span 3.2 ms at
  3e8 events/s (the first Kaggle QUICK run, TESTING bug #51). Every file's span must lie in
  [EVENTREID_SPAN_S] after scaling, else the reader raises, so a unit error cannot pass silently. `describe_eventreid(root)` prints what the
  files hold, for the QUICK run. label = the first integer in the parent directory's name (else in the
  file stem); group = label (person id, the identity cluster) or, without a label, the parent directory.
  Geometry: `W`, `H` when given, else max(x) + 1, max(y) + 1 of the sample (named "eventreid").
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np

from neuro.v2e_lite import event_dtype

BUCKET_SHIFT = 6  # one EVT 2.0 TIME_HIGH value = 64 µs (DESIGN.md §2.1)
_ALIASES = {"t": ("t", "ts", "timestamp", "timestamps"), "x": ("x",), "y": ("y",),
            "p": ("p", "pol", "polarity")}
_SPLIT_NAMES = {"train": True, "test": False}


def _geometry(name, W, H):
    from neuro.geometry import Geometry  # noqa: PLC0415 (sibling module, kept lazy for import order)
    return Geometry(name, int(W), int(H))


def _sensor(name):
    from neuro.geometry import SENSORS  # noqa: PLC0415
    return SENSORS[name]


def _to_events(t, x, y, p, t_scale=1.0):
    """EVENT_DTYPE array from columns, stable-sorted by t; p is mapped to {0, 1} (p > 0 is ON)."""
    t = np.asarray(t, dtype=np.float64) * t_scale
    if t.size and t.min() < 0:
        raise ValueError("negative timestamps")
    ev = np.zeros(t.size, dtype=event_dtype())
    ev["t"] = np.rint(t).astype(np.uint64)
    ev["x"], ev["y"] = np.asarray(x), np.asarray(y)
    ev["p"] = (np.asarray(p) > 0).astype(np.uint8)
    return ev[np.argsort(ev["t"], kind="stable")]


def _check_split(split):
    key = str(split).lower()
    if key not in _SPLIT_NAMES:
        raise ValueError(f"split must be 'train' or 'test', got {split!r}")
    return _SPLIT_NAMES[key]


def _tonic():
    try:
        import tonic  # noqa: PLC0415 (Kaggle only)
    except ImportError as e:  # pragma: no cover - depends on the machine
        raise ImportError("Tonic is not installed (pip install tonic==1.7.0; Kaggle only, DESIGN.md §8.4)") from e
    return tonic


def _from_tonic(ds, geom, group_of):
    """Samples from a Tonic-style dataset (len, [i] -> (events with x/y/p/t fields, target))."""
    for i in range(len(ds)):
        ev, target = ds[i]
        yield (_to_events(ev["t"], ev["x"], ev["y"], ev["p"]), None if target is None else int(target),
               group_of(ds, i), geom)


# ---------------------------------------------------------------- N-MNIST

def read_nmnist_bin(path):
    """Decode one N-MNIST .bin file (5 bytes per event, layout in the module docstring)."""
    raw = np.fromfile(path, dtype=np.uint8)
    if raw.size % 5:
        raise ValueError(f"{path}: size {raw.size} is not a multiple of 5 bytes")
    b = raw.reshape(-1, 5).astype(np.uint32)
    t = ((b[:, 2] & 0x7F) << 16) | (b[:, 3] << 8) | b[:, 4]
    return _to_events(t, b[:, 0], b[:, 1], b[:, 2] >> 7)


def _nmnist_files(root, split):
    want = "train" if _check_split(split) else "test"
    files = [f for f in Path(root).rglob("*.bin")
             if any(part.lower() == want for part in f.relative_to(root).parts[:-1])]
    files = [f for f in files if f.parent.name.isdigit()]
    return sorted(files, key=lambda f: f.relative_to(root).as_posix())


def load_nmnist(root, split, backend="auto", dataset=None):
    """N-MNIST samples (events, digit, group=file stem or index, Geometry nmnist 34 x 34)."""
    geom = _sensor("nmnist")
    if dataset is not None:  # an already built Tonic-style dataset (tests, or a caller with transforms)
        yield from _from_tonic(dataset, geom, lambda ds, i: str(i))
        return
    if backend == "auto":
        try:
            _tonic()
            backend = "tonic"
        except ImportError:
            backend = "native"
    if backend == "tonic":
        ds = _tonic().datasets.NMNIST(save_to=str(root), train=_check_split(split))
        yield from _from_tonic(ds, geom, lambda d, i: str(i))
        return
    if backend != "native":
        raise ValueError(f"unknown backend {backend!r}")
    files = _nmnist_files(root, split)
    if not files:
        raise FileNotFoundError(f"no N-MNIST .bin files for split {split!r} under {root}")
    for f in files:
        ev = read_nmnist_bin(f)
        if ev.size and (ev["x"].max() >= geom.W or ev["y"].max() >= geom.H):
            raise ValueError(f"{f}: event outside {geom.W} x {geom.H}")
        yield ev, int(f.parent.name), f.stem, geom


# ---------------------------------------------------------------- DVS Gesture

def _gesture_group(ds, i):
    paths = getattr(ds, "data", None)
    if paths is not None and i < len(paths):
        m = re.search(r"user(\d+)", str(paths[i]))
        if m:
            return f"user{int(m.group(1)):02d}"
    return str(i)


def load_dvsgesture(root, split, dataset=None):
    """DVS Gesture samples via Tonic's official train/test files (group = subject `userNN` when known)."""
    geom = _sensor("dvsgesture")
    ds = dataset if dataset is not None else _tonic().datasets.DVSGesture(save_to=str(root),
                                                                           train=_check_split(split))
    yield from _from_tonic(ds, geom, _gesture_group)


# ---------------------------------------------------------------- Event-ReId (tolerant reader)

EVENTREID_EXT = (".npy", ".npz", ".h5", ".hdf5", ".txt", ".csv")


def _named(names):
    """Map our field names to the file's names via _ALIASES; None if any is missing."""
    low = {n.lower(): n for n in names}
    out = {}
    for ours, aliases in _ALIASES.items():
        hit = next((low[a] for a in aliases if a in low), None)
        if hit is None:
            return None
        out[ours] = hit
    return out


def _from_matrix(arr, columns, path):
    arr = np.asarray(arr)
    if arr.ndim != 2 or columns is None or arr.shape[1] < len(columns):
        raise ValueError(f"{path}: unnamed array of shape {arr.shape}; pass columns=(...) naming its columns "
                         "(the Event-ReId layout is read in the QUICK run, not assumed)")
    return {c: arr[:, j] for j, c in enumerate(columns) if c in _ALIASES}


def read_event_file(path, columns=None):
    """Columns {t, x, y, p} (raw units) of one event file; see the module docstring for what is accepted."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".npy", ".npz"):
        obj = np.load(path, allow_pickle=False)
        if ext == ".npz":
            keys = list(obj.keys())
            m = _named(keys)
            if m:
                return {k: obj[v] for k, v in m.items()}
            if len(keys) == 1:
                obj = obj[keys[0]]
            else:
                raise ValueError(f"{path}: npz keys {keys} do not name t/x/y/p")
        if obj.dtype.names:
            m = _named(obj.dtype.names)
            if m is None:
                raise ValueError(f"{path}: fields {obj.dtype.names} do not name t/x/y/p")
            return {k: obj[v] for k, v in m.items()}
        return _from_matrix(obj, columns, path)
    if ext in (".h5", ".hdf5"):
        import h5py  # noqa: PLC0415 (optional)
        with h5py.File(path, "r") as h:
            dsets = {}
            h.visititems(lambda n, o: dsets.setdefault(n.split("/")[-1], o[()]) if isinstance(o, h5py.Dataset)
                         else None)
        m = _named(dsets)
        if m:
            return {k: dsets[v] for k, v in m.items()}
        if len(dsets) == 1:
            return _from_matrix(next(iter(dsets.values())), columns, path)
        raise ValueError(f"{path}: datasets {sorted(dsets)} do not name t/x/y/p")
    if ext in (".txt", ".csv"):
        # Event-ReId (its README, read 7 Nov 2026): first row "width height", then "t x y p" per row, t in ms
        # with a fractional part (unit measured, module docstring; the README does not state it). A first row of two numbers is taken as the resolution; four columns without
        # names default to (t, x, y, p).
        sep = "," if ext == ".csv" else None
        with open(path, encoding="utf-8", errors="replace") as fh:
            first = fh.readline().replace(",", " ").split()
        skip, res = 0, None
        if len(first) == 2 and all(v.replace(".", "", 1).isdigit() for v in first):
            skip, res = 1, (int(float(first[0])), int(float(first[1])))
        try:
            import pandas as pd  # noqa: PLC0415 (fast C parser when present)
            arr = pd.read_csv(path, sep=sep or r"\s+", header=None, skiprows=skip).to_numpy(dtype=np.float64)
        except ImportError:
            arr = np.loadtxt(path, delimiter=sep, ndmin=2, skiprows=skip)
        cols = columns or (("t", "x", "y", "p") if arr.ndim == 2 and arr.shape[1] == 4 else None)
        out = _from_matrix(arr, cols, path)
        if res:
            out["_resolution"] = res
        return out
    raise ValueError(f"{path}: unsupported extension {ext}")


def _eventreid_files(root, split):
    root = Path(root)
    files = [f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in EVENTREID_EXT]
    if split is not None:
        key = str(split).lower()
        files = [f for f in files if any(key in part.lower() for part in f.relative_to(root).parts[:-1])]
    return sorted(files, key=lambda f: f.relative_to(root).as_posix())


def _first_int(text):
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else None


EVENTREID_SPAN_S = (0.1, 60.0)      # plausible span of one recording in seconds (README: 3-4 s)


def load_eventreid(root, split=None, columns=None, t_scale=1e3, W=None, H=None, every=1):
    """Event-ReId samples, one per event file (tolerant reader; rules in the module docstring).

    every > 1 reads every `every`-th file only (spread over all persons, for a small smoke run)."""
    files = _eventreid_files(root, split)[::max(1, int(every))]
    if not files:
        raise FileNotFoundError(f"no event files ({', '.join(EVENTREID_EXT)}) for split {split!r} under {root}")
    for f in files:
        c = read_event_file(f, columns)
        res = c.pop("_resolution", None)
        ev = _to_events(c["t"], c["x"], c["y"], c["p"], t_scale)
        if ev.size > 1:
            span_s = (int(ev["t"][-1]) - int(ev["t"][0])) / 1e6
            lo, hi = EVENTREID_SPAN_S
            if not lo <= span_s <= hi:
                raise ValueError(f"{f}: {ev.size} events span {span_s:.4g} s with t_scale={t_scale}, outside "
                                 f"{lo}-{hi} s: wrong timestamp unit?")
        if ev.size and (ev["x"].astype(np.int64).min() < 0):
            raise ValueError(f"{f}: negative x")
        gw = W if W is not None else (res[0] if res else (int(ev["x"].max()) + 1 if ev.size else 1))
        gh = H if H is not None else (res[1] if res else (int(ev["y"].max()) + 1 if ev.size else 1))
        if ev.size and (ev["x"].max() >= gw or ev["y"].max() >= gh):
            raise ValueError(f"{f}: event outside {gw} x {gh}")
        # person id: the all-digit folder of the path (Event-ReId: <id>/<camera>/events.txt); the camera folder
        # (cam01..) must not become the label
        rel = f.relative_to(Path(root)).parts[:-1]
        ids = [p for p in rel if p.isdigit()]
        label = int(ids[-1]) if ids else _first_int(f.parent.name)
        if label is None:
            label = _first_int(f.stem)
        group = str(label) if label is not None else f.parent.relative_to(root).as_posix()
        yield ev, label, group, _geometry("eventreid", gw, gh)


def eventreid_count(root, split=None):
    return len(_eventreid_files(root, split))


class Strided:
    """Every `every`-th sample of a Tonic-style dataset (len, [i], optional .data), keeping all classes in a small
    run: Tonic orders N-MNIST by digit, so the first n samples would be one class."""

    def __init__(self, ds, every):
        self.ds, self.every = ds, max(1, int(every))
        self.data = getattr(ds, "data", None)
        if self.data is not None:
            self.data = self.data[::self.every]

    def __len__(self):
        return (len(self.ds) + self.every - 1) // self.every

    def __getitem__(self, i):
        return self.ds[i * self.every]


def describe_eventreid(root, max_files=3):
    """What the Event-ReId files look like (extensions, first files' fields/shapes), for the QUICK run print."""
    root = Path(root)
    files = [f for f in root.rglob("*") if f.is_file()]
    ext = {}
    for f in files:
        ext[f.suffix.lower()] = ext.get(f.suffix.lower(), 0) + 1
    first = []
    for f in [f for f in sorted(files) if f.suffix.lower() in (".npy", ".npz")][:max_files]:
        obj = np.load(f, allow_pickle=False)
        if f.suffix.lower() == ".npz":
            first.append({"file": f.relative_to(root).as_posix(), "keys": list(obj.keys())})
        else:
            first.append({"file": f.relative_to(root).as_posix(), "shape": list(obj.shape),
                          "fields": list(obj.dtype.names or [])})
    dirs = sorted({f.parent.relative_to(root).as_posix() for f in files})
    return {"n_files": len(files), "extensions": ext, "dirs_first": dirs[:20], "n_dirs": len(dirs),
            "first_files": first}


# ---------------------------------------------------------------- manifest and count cache

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest(root):
    """{relative posix path: {"sha256": hex, "bytes": n}} for every file under root, sorted by path."""
    root = Path(root)
    files = sorted((f for f in root.rglob("*") if f.is_file()), key=lambda f: f.relative_to(root).as_posix())
    return {f.relative_to(root).as_posix(): {"sha256": sha256_file(f), "bytes": f.stat().st_size} for f in files}


def bucket_counts(events):
    """(first bucket, counts per 64 µs bucket from the first to the last event's bucket), counts uint32."""
    t = np.asarray(events["t"], dtype=np.uint64)
    if t.size == 0:
        return 0, np.zeros(0, dtype=np.uint32)
    b = (t >> np.uint64(BUCKET_SHIFT)).astype(np.int64)
    b0 = int(b.min())
    return b0, np.bincount(b - b0).astype(np.uint32)


def cache_counts(dataset, out_npz):
    """Write the per-bucket CD counts of every sample of `dataset` (an iterable of loader samples) to out_npz.

    Arrays: counts (all samples' series concatenated), offsets (n + 1; sample i is counts[offsets[i]:
    offsets[i+1]]), bucket0 (first bucket index), n_events, n_on, label (-1 = none), group (str), W, H, and
    bucket_us = 64. Returns the number of samples written.
    """
    series, b0s, n_ev, n_on, labels, groups, ws, hs = [], [], [], [], [], [], [], []
    for ev, label, group, geom in dataset:
        b0, c = bucket_counts(ev)
        series.append(c)
        b0s.append(b0)
        n_ev.append(ev.size)
        n_on.append(int(np.count_nonzero(ev["p"])))
        labels.append(-1 if label is None else int(label))
        groups.append(str(group))
        ws.append(geom.W)
        hs.append(geom.H)
    offsets = np.zeros(len(series) + 1, dtype=np.int64)
    if series:
        offsets[1:] = np.cumsum([s.size for s in series])
    counts = np.concatenate(series) if series else np.zeros(0, dtype=np.uint32)
    out_npz = Path(out_npz)
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_npz, counts=counts, offsets=offsets, bucket0=np.asarray(b0s, dtype=np.int64),
                        n_events=np.asarray(n_ev, dtype=np.int64), n_on=np.asarray(n_on, dtype=np.int64),
                        label=np.asarray(labels, dtype=np.int64), group=np.asarray(groups, dtype=str),
                        W=np.asarray(ws, dtype=np.int64), H=np.asarray(hs, dtype=np.int64),
                        bucket_us=np.int64(1 << BUCKET_SHIFT))
    return len(series)


def load_counts(npz):
    """Inverse of cache_counts: list of (series, label or None, group, (W, H), bucket0)."""
    # Every z[...] on an NpzFile decompresses the whole array again: read each array once (indexing z["counts"]
    # inside the loop made N5 on 400 DVS Gesture samples allocate 400 x 166 MB and get Killed on Kaggle).
    with np.load(npz, allow_pickle=False) as z:
        a = {k: z[k] for k in ("offsets", "counts", "label", "group", "W", "H", "bucket0")}
    off, counts, label = a["offsets"], a["counts"], a["label"]
    return [(counts[off[i]:off[i + 1]], None if label[i] < 0 else int(label[i]),
             str(a["group"][i]), (int(a["W"][i]), int(a["H"][i])), int(a["bucket0"][i]))
            for i in range(off.size - 1)]
