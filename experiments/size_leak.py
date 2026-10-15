"""R7 -- the frame-size side channel of every protection level, and what closes it (research suite).

    python experiments/size_leak.py                                   # synthetic scene, 90 frames
    python experiments/size_leak.py --video clips/x.mp4 --frames 120 --stride 3

Encryption hides content, not length. Wampler, Uluagac and Beyah (IEEE 2015) detected people
walking and lights switching in ENCRYPTED IP-camera traffic from packet sizes and timing. Our levels
E0-E5 keep the JPEG size (E5 adds restart markers), so every level shows the eavesdropper the size of
every frame. This script measures how much that reveals about motion, for every level, and tests
defences:

  E0..E5             plain sizes of the protected frames (quality 75)
  pad-1KB (E2/E5)    every frame padded up to a multiple of 1024 bytes (cheap, coarse)
  pad-max (E2/E5)    every frame padded to the largest frame of the run (constant size; an upper bound
                     on the cost of a constant-size stream)
  FF+PI (E2)         the bitrate controller of experiments/rate_control.py holding a constant budget
                     (median E2 size); its frames are then padded to 105 % of the budget. Frames that
                     still exceed it are counted (each one leaks). Checks the hypothesis that rate
                     control moves the leak into the quality factor, which the DQT header shows in clear.

Leakage metrics (the attacker sees sizes, and the quantisation tables, never pixels):
  size_corr   Pearson correlation of the frame size with the true motion energy (mean |dY|)
  event_auc   separability max(AUC, 1 - AUC) of a simple causal event detector, score = size minus
              the smallest size of the last 30 frames (rise above the empty-scene background), events =
              the 25 % of frames with the most motion (0.5 = chance, 1 = perfect)
  q_corr / q_auc   the same for the quality factor (only for FF+PI, where it varies)
Cost: bytes relative to the plain E2 stream; quality: mean SSIM for FF+PI.
Writes sim_out/size_leak/<name>.json and .md.
"""
import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from link.sources import open_source                       # noqa: E402
from model.jpeg import analyse_frame, package_frame        # noqa: E402

OUT = ROOT / "sim_out" / "size_leak"
KEY = bytes(range(16))
LEVELS = ["E0", "E1", "E2", "E3", "E4", "E5"]


def luma(rgb):
    return rgb.astype(np.float64) @ np.array([0.299, 0.587, 0.114])


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0


def auc(scores, labels):
    """Mann-Whitney AUC (ties count half)."""
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return 0.5
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def detector(series, k=30):
    """Rise above the recent background: value minus the minimum of the last k values (an empty
    scene gives the smallest frames). Causal; the attacker needs no training."""
    return [series[t] - min(series[max(0, t - k):t + 1]) for t in range(len(series))]


def leak(series, motion):
    lab_thr = np.quantile(motion[1:], 0.75)
    labels = [m >= lab_thr for m in motion]
    a = auc(detector(series)[1:], labels[1:])
    return dict(size_corr=corr(series[1:], motion[1:]), event_auc=max(a, 1 - a))   # separability


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=90)
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    name = a.name or Path(a.video).stem
    src = open_source(a.video, w, h, loop=True)
    frames = []
    for i in range(a.frames * a.stride):
        f = src.read()
        if f is None:
            break
        if i % a.stride == 0:
            frames.append(f)
    motion = [0.0] + [float(np.mean(np.abs(luma(frames[t]) - luma(frames[t - 1])))) for t in range(1, len(frames))]
    sizes = {lv: [] for lv in LEVELS}
    for t, f in enumerate(frames):
        an = analyse_frame(f)
        for lv in LEVELS:
            sizes[lv].append(len(package_frame(an, KEY, 1, t + 1, lv).jpeg))
    base = sum(sizes["E2"])
    res = {}
    for lv in LEVELS:
        res[lv] = dict(**leak(sizes[lv], motion), bytes_vs_E2=sum(sizes[lv]) / base)
    for lv in ("E2", "E5"):
        b1 = [math.ceil(s / 1024) * 1024 for s in sizes[lv]]
        res[f"{lv} pad-1KB"] = dict(**leak(b1, motion), bytes_vs_E2=sum(b1) / base)
        m = max(sizes[lv])
        bm = [m] * len(frames)                       # constant size from the first frame on
        res[f"{lv} pad-max"] = dict(**leak(bm, motion), bytes_vs_E2=sum(bm) / base)
    # FF+PI at a constant budget, then pad to 105 % of it
    import rate_control as RC
    budget = statistics.median(sizes["E2"])
    c = RC.FFPI()
    sz, qs, ss = [], [], []
    for t, f in enumerate(frames):
        c.last_q = c.q
        qs.append(c.q)
        s, pic = RC.encode(f, c.q, t + 1)
        from PIL import Image
        from skimage.metrics import structural_similarity
        ss.append(structural_similarity(np.asarray(Image.fromarray(f).convert("L")), pic, data_range=255))
        sz.append(s)
        c.update(s, budget)
    cap = 1.05 * budget
    padded = [max(s, cap) for s in sz]
    padded[0] = max(padded)                          # the start-up frame padded like the rest
    over = sum(s > cap for s in sz[1:]) / max(1, len(sz) - 1)
    r = dict(**leak(padded, motion), bytes_vs_E2=sum(padded) / base, frames_over_cap=over,
             mean_ssim=statistics.mean(ss))
    lq = leak([round(q) for q in qs], motion)       # same detector on the (visible) quality factor
    r.update(q_corr=lq["size_corr"], q_auc=lq["event_auc"])
    res["E2 FF+PI + pad-105%"] = r
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(dict(source=name, frames=len(frames), results=res), indent=1))
    md = [f"### R7: frame-size side channel ({name}, {len(frames)} frames)", "",
          "| Stream | Size-motion corr. | Event AUC (0.5 = chance) | Bytes vs E2 | Notes |", "|---|---|---|---|---|"]
    for k, v in res.items():
        note = ""
        if "frames_over_cap" in v:
            note = (f"{100 * v['frames_over_cap']:.0f} % frames over cap; quality factor leaks: corr {v['q_corr']:.2f}, "
                    f"AUC {v['q_auc']:.2f}; SSIM {v['mean_ssim']:.3f}")
        md.append(f"| {k} | {v['size_corr']:.2f} | {v['event_auc']:.2f} | {100 * v['bytes_vs_E2']:.0f} % | {note} |")
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
