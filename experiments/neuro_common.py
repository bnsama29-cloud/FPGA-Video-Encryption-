"""Shared helpers for the paper-2 experiments (experiments/neuro_*.py, DESIGN §8).

Every script writes sim_out/neuro/<exp>/<name>.json (data + `meta`) and <name>.md (the paper table) through
`write()`. `meta()` records inputs with SHA-256, the git commit, seeds, number of keys and clusters, and the CI
method. Data come from `load_samples()`: a real dataset from --data (N-MNIST, DVS Gesture via neuro.datasets,
Event-ReId) or, without --data, a small synthetic set labelled "synthetic" (moving blobs through v2e-lite, with
exact intensity ground truth); results on synthetic data are smoke tests, never paper numbers.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "software"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from neuro import evt2, keys                                   # noqa: E402
from neuro.geometry import Geometry, SENSORS                   # noqa: E402
from neuro.packet import from_bytes                            # noqa: E402
from neuro.sender import Config, Encryptor                     # noqa: E402
from neuro.v2e_lite import frames_to_events                    # noqa: E402

OUT = ROOT / "sim_out" / "neuro"
CAM, BOOT = 1, 1


# ------------------------------------------------------------------ bookkeeping
def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except OSError:
        return ""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def meta(args=None, inputs=(), **kw):
    m = {"commit": git_sha(), "date": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": sys.argv[1:],
         "inputs": {str(p): sha256(p) for p in inputs if Path(p).is_file()}}
    if args is not None:
        m["args"] = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    m.update(kw)
    return m


def write(exp, name, data, md, out=None):
    d = Path(out) if out else OUT / exp
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(data, indent=1, default=_json), encoding="utf-8")
    (d / f"{name}.md").write_text(md if md.endswith("\n") else md + "\n", encoding="utf-8")
    print(f"wrote {d / name}.json and .md")
    return d


def _json(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        out.append("| " + " | ".join(fmt(v) for v in r) + " |")
    return "\n".join(out)


def fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, tuple) and len(v) == 3 and all(isinstance(x, float) for x in v):
        return f"{v[0]:.3f} [{v[1]:.3f}, {v[2]:.3f}]"
    return str(v)


# ------------------------------------------------------------------ keys and protection
def master(i):
    """Independent experiment master key i (PSK profile, reproducible from the index)."""
    return hashlib.sha256(b"neuro-exp-master-%d" % i).digest()[:16]


def protect(events, geom, level, T_us=1024, ts_bits=None, pad=None, key_index=0, epoch=0):
    """Sealed packets (list of bytes) of an event array, PSK profile, master `key_index`."""
    if ts_bits is None:
        ts_bits = 6 if level == 3 else 0
    words = evt2.encode(events, T_us)
    sk = keys.subkeys(master(key_index), CAM, BOOT, epoch)
    sid = keys.session_id(CAM, BOOT, epoch)
    enc = Encryptor(sk, sid, Config(level, ts_bits, T_us, geom, pad))
    return enc.push(words) + enc.flush()


def keyless_payloads(packets):
    """What an eavesdropper extracts from the public framing: per packet (header, payload words). V4 -> None."""
    out = []
    for raw in packets:
        p = from_bytes(raw)
        out.append((p.header, None if p.header.level == 4 else p.payload))
    return out


def keyless_events(packets):
    """All CD events of the extracted payloads (dummies included: the attacker cannot remove them)."""
    w = [pl for _, pl in keyless_payloads(packets) if pl is not None and len(pl)]
    if not w:
        return np.zeros(0, dtype=evt2.EVENT_DTYPE)
    ev, _ = evt2.decode(np.concatenate(w))
    return ev


# ------------------------------------------------------------------ data
SYN_GEOM = Geometry("syn64", 64, 64)


def synthetic_clip(label, seed, geom=SYN_GEOM, n_frames=40, fps=1000):
    """A bright blob moving in direction `label` (0 right, 1 left, 2 down, 3 up) over a textured background.

    Returns (events, frames) with frames (n_frames, H, W) in [0, 255]: exact intensity ground truth.
    """
    rng = np.random.default_rng(seed)
    H, W = geom.H, geom.W
    yy, xx = np.mgrid[0:H, 0:W]
    bg = 60 + 30 * np.sin(xx / 5.0 + rng.uniform(0, 6)) * np.cos(yy / 7.0 + rng.uniform(0, 6))
    cx, cy = rng.uniform(0.3, 0.7) * W, rng.uniform(0.3, 0.7) * H
    v = rng.uniform(0.35, 0.6)
    d = [(1, 0), (-1, 0), (0, 1), (0, -1)][label % 4]
    r = rng.uniform(5, 9)
    frames = []
    for k in range(n_frames):
        x0, y0 = cx + d[0] * v * k, cy + d[1] * v * k
        blob = 150 * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * r * r))
        frames.append(np.clip(bg + blob, 0, 255))
    frames = np.asarray(frames)
    ev = frames_to_events(frames, fps, C=0.15, refractory_us=200)
    ev = np.asarray(ev).astype(evt2.EVENT_DTYPE)
    ev["t"] += 10_000                              # start away from t = 0
    return ev, frames


def synthetic_samples(n=24, seed=0, geom=SYN_GEOM, classes=4):
    """[(events, label, group, geom, frames)]; group = 'subject' id (n / 6 groups) for cluster statistics."""
    out = []
    for i in range(n):
        ev, fr = synthetic_clip(i % classes, seed * 1000 + i, geom)
        out.append((ev, i % classes, f"s{i // 6}", geom, fr))
    return out


def load_samples(name, root=None, split="test", limit=None, seed=0):
    """Samples of a dataset as (events, label, group, geom, frames or None). Without root: synthetic."""
    if root is None or name == "synthetic":
        return synthetic_samples(limit or 24, seed)
    from neuro import datasets
    if name == "eventreid":
        # no train/test folders of its own: all files (persons split later by group); a limit takes every k-th
        # file so a small run still spans many persons
        every = max(1, datasets.eventreid_count(root) // limit) if limit else 1
        it = datasets.load_eventreid(root, None, every=every)
    else:
        tonic = datasets._tonic()
        cls = tonic.datasets.NMNIST if name == "nmnist" else tonic.datasets.DVSGesture
        ds = cls(save_to=str(root), train=(split == "train"))
        if limit:                                   # spread over every class (Tonic orders N-MNIST by digit)
            ds = datasets.Strided(ds, max(1, len(ds) // limit))
        loader = datasets.load_nmnist if name == "nmnist" else datasets.load_dvsgesture
        it = loader(root, split, dataset=ds)
    out = []
    for i, (ev, label, group, geom) in enumerate(it):
        if limit and i >= limit:
            break
        out.append((ev, label, group, geom, None))
    return out


def dataset_arg(ap, default="synthetic"):
    ap.add_argument("--dataset", default=default, choices=["synthetic", "nmnist", "dvsgesture", "eventreid"])
    ap.add_argument("--data", type=Path, default=None, help="dataset root (omit: synthetic smoke data)")
    ap.add_argument("--limit", type=int, default=None, help="at most this many samples")
    ap.add_argument("--keys", type=int, default=5, help="independent master keys (>= 5 for paper runs)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quick", action="store_true", help="tiny smoke run (tests)")
    ap.add_argument("--out", type=Path, default=None)


def baseline(name):
    """The Du 2021 / Zhang 2024 reimplementation, or None while docs/neuro/BASELINES.md is not written."""
    try:
        import importlib
        return importlib.import_module(f"neuro.baselines.{name}")
    except ImportError:
        return None


def windows(events, win_us):
    """Split events into consecutive windows of win_us (list of arrays, empty windows skipped)."""
    if len(events) == 0:
        return []
    t = np.asarray(events["t"], dtype=np.int64)
    k = (t - t[0]) // win_us
    cuts = np.nonzero(np.diff(k))[0] + 1
    return [w for w in np.split(events, cuts) if len(w)]
