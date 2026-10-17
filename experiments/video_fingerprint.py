"""Which video is playing? Identification from encrypted frame sizes (after Schuster et al., USENIX Security
2017, refs.bib schuster2017), for every protection level and the padding defences.

    python experiments/video_fingerprint.py --sources clips/a.mp4 clips/b.mp4 clips/c.mp4 --frames 600
    python experiments/video_fingerprint.py --demo          # three synthetic pan clips, smoke test only

Schuster et al. identify which of a set of known videos a victim streams from the burst sizes of
encrypted traffic. In our system every frame is one JPEG whose size the eavesdropper sees (E0-E4 keep
the size exactly, E5 adds restart markers), so the same attack applies frame by frame. The attacker:

  library   encodes every candidate video himself (any key: E0-E4 sizes do not depend on the key; for
            E5 the attacker's own key differs from the victim's, so the shuffle differs)
  query     observes W consecutive frame sizes of the victim's stream at an unknown position
  decision  the library video and offset with the highest Pearson correlation between the query and
            the library segment (z-normalised sizes, so a different quality factor would not matter);
            a constant query (padded to a fixed size) carries no information -> random guess

Accuracy over many random queries per window length W (frames; at 10 frames/s, W = 10 is one second),
against chance = 1/#videos. Schemes:
  E2, E5                 plain protected sizes (E1-E4 give the same sizes as E2)
  pad-1KB                every frame padded to a multiple of 1024 bytes
  pad-runmax             padded to the largest frame seen so far (deployable, link/ option)
  pad-win                padded to the largest of the last 100 frames (deployable)
  pad-const              every frame padded to one size for the whole session (the reference)
Writes sim_out/video_fingerprint/<name>.json and .md.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.sources import open_source                  # noqa: E402
from model.jpeg import analyse_frame, package_frame   # noqa: E402

VICTIM_KEY = bytes(range(16))
ATTACKER_KEY = bytes(range(16, 32))


def sizes(path, frames, stride, size, key, modes):
    w, h = map(int, size.split("x"))
    src = open_source(path, w, h, loop=False)
    out = {m: [] for m in modes}
    for i in range(frames * stride):
        f = src.read()
        if f is None:
            break
        if i % stride:
            continue
        an = analyse_frame(f)
        for m in modes:
            out[m].append(len(package_frame(an, key, 7, len(out[m]), m).jpeg))
    return {m: np.asarray(v, dtype=np.float64) for m, v in out.items()}


def pad(series, scheme, window=100):
    s = np.asarray(series, dtype=np.float64)
    if scheme == "pad-1KB":
        return np.ceil(s / 1024) * 1024
    if scheme == "pad-runmax":
        return np.maximum.accumulate(s)
    if scheme == "pad-win":
        return np.array([s[max(0, i - window + 1):i + 1].max() for i in range(len(s))])
    if scheme == "pad-const":
        return np.full_like(s, s.max())
    return s


def identify(query, library, rng):
    """Index of the library series that best explains the query (max Pearson over all offsets)."""
    W = len(query)
    q = query - query.mean()
    if np.allclose(q, 0):
        return int(rng.integers(len(library)))
    q = q / np.linalg.norm(q)
    best, arg = -2.0, 0
    for k, lib in enumerate(library):
        if len(lib) < W:
            continue
        segs = np.lib.stride_tricks.sliding_window_view(lib, W)
        segs = segs - segs.mean(axis=1, keepdims=True)
        n = np.linalg.norm(segs, axis=1)
        ok = n > 0
        if not ok.any():
            continue
        c = (segs[ok] @ q) / n[ok]
        if c.max() > best:
            best, arg = c.max(), k
    if best == -2.0:
        return int(rng.integers(len(library)))
    return arg


def demo_sources(tmp, n_frames):
    """Three synthetic 'videos': slow pans over three scikit-image photos (smoke test only)."""
    import cv2
    from skimage import data
    paths = []
    for nm in ("astronaut", "coffee", "chelsea"):
        im = getattr(data, nm)()
        d = Path(tmp) / nm
        d.mkdir(parents=True, exist_ok=True)
        H, W = im.shape[:2]
        for i in range(n_frames):
            x = int((W - 200) * (0.5 + 0.5 * np.sin(i / 7.0)))
            crop = cv2.resize(im[:200, x:x + 200], (160, 128))
            cv2.imwrite(str(d / f"{i:04d}.png"), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
        paths.append(str(d))
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", nargs="*", default=[])
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--windows", type=int, nargs="+", default=[5, 10, 30, 100])
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--name", default="fingerprint")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "video_fingerprint"))
    a = ap.parse_args()
    if a.demo:
        a.sources = demo_sources(Path(a.out) / "_demo", 120)
        a.frames, a.size, a.name = 120, "160x128", "demo"
    if len(a.sources) < 2:
        raise SystemExit("need at least two --sources (or --demo)")

    names = [Path(p).stem for p in a.sources]
    victim, attacker = [], []
    for p in a.sources:
        victim.append(sizes(p, a.frames, a.stride, a.size, VICTIM_KEY, ("E2", "E5")))
        attacker.append(sizes(p, a.frames, a.stride, a.size, ATTACKER_KEY, ("E2", "E5")))
        print(f"{Path(p).stem}: {len(victim[-1]['E2'])} frames, mean E2 size {victim[-1]['E2'].mean():.0f} B", flush=True)

    schemes = [("E2", "E2", None), ("E5", "E5", None), ("pad-1KB", "E2", "pad-1KB"),
               ("pad-runmax", "E2", "pad-runmax"), ("pad-win", "E2", "pad-win"), ("pad-const", "E2", "pad-const")]
    rng = np.random.default_rng(0)
    res = {}
    for label, mode, scheme in schemes:
        lib = [pad(at[mode], scheme) for at in attacker]
        vic = [pad(v[mode], scheme) for v in victim]
        cost = float(np.mean([v.sum() / x["E2"].sum() - 1 for v, x in zip(vic, victim)]))
        row = dict(overhead=round(cost, 4))
        for W in a.windows:
            hits = n = 0
            for _ in range(a.queries):
                k = int(rng.integers(len(vic)))
                if len(vic[k]) <= W:
                    continue
                o = int(rng.integers(len(vic[k]) - W + 1))
                hits += identify(vic[k][o:o + W], lib, rng) == k
                n += 1
            row[f"W{W}"] = round(hits / n, 3) if n else None
        res[label] = row
        print(label, row, flush=True)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(sources=names, frames=a.frames, stride=a.stride, size=a.size, queries=a.queries,
                chance=round(1 / len(names), 3),
                attack="max Pearson correlation over library videos and offsets (Schuster et al. style, "
                       "frame sizes instead of bursts); attacker library encoded with a different key")
    (out / f"{a.name}.json").write_text(json.dumps(dict(meta=meta, results=res), indent=1))
    hdr = " | ".join(f"W = {W}" for W in a.windows)
    lines = [f"# Video identification from frame sizes ({a.name}: {len(names)} videos, chance {meta['chance']})", "",
             f"| Scheme | bytes vs E2 | {hdr} |", "|---|---|" + "---|" * len(a.windows)]
    for label, row in res.items():
        lines.append(f"| {label} | {row['overhead']:+.1%} | " + " | ".join(str(row[f'W{W}']) for W in a.windows) + " |")
    (out / f"{a.name}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
