"""Jigsaw-solver attack on E5: can an eavesdropper put the shuffled MCUs back in place?

E5 hides WHERE each 16x16 MCU belongs, so the edge sketch that E1-E4 leak disappears
(edge correlation 0.33 -> 0.00). A smarter attacker treats the frame as a jigsaw: it
decodes every MCU on its own (replacement attack, no key), then places the tiles so
that neighbouring borders continue smoothly. If that works, E5's claim is weaker than
the 0.00 suggests -- so we measure it instead of assuming it.

    python -m future_work.attacks.jigsaw_attack                       # synthetic scene
    python -m future_work.attacks.jigsaw_attack --video clips/gate.mp4 --frames 10 --size 320x240

Solver (greedy region growing, in the style of Pomeranz et al. CVPR 2011):
  * dissimilarity D_lr[i, j] = how badly tile j continues tile i to the right: the
    border column of j is compared with the linear extrapolation of i's last two
    columns (gradient continuation); D_tb likewise vertically. Each D is normalised
    by the second-best alternative of both tiles, so unambiguous matches win;
  * start from the tile with the most "best buddies" (mutual best matches); then
    repeatedly place the (empty slot next to the placed region, unused tile) pair
    with the lowest normalised cost, keeping the region inside the rows x cols grid.
  * sanity check (tests/test_future_work.py): on UNENCRYPTED shuffled tiles of a
    textured photo it must reassemble most neighbours -- otherwise its E5 numbers
    would say nothing.
Metrics (ground truth from the key, which the attacker never has):
  position accuracy  share of tiles placed exactly where they belong
  neighbour accuracy share of placed left/right and top/bottom pairs that are true neighbours
  edge correlation   of the solved picture vs the original (compare: E2/E4 sketch ~0.33)
Writes future_work/results/jigsaw.json/.md and, with --save-images, before/after PNGs.
A real attacker could do better (e.g. Gallagher-style solvers, learned compatibilities):
treat our number as a lower bound on what E5 leaks, not an upper bound.
"""
import argparse
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from link.sources import open_source
from model.jpeg import _shuffle_order, analyse_frame, package_frame, replacement_attack_jpeg

OUT = Path(__file__).resolve().parents[1] / "results"
T = 16


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def luma(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float64)


def edge_corr(a, b):
    ea = np.hypot(cv2.Sobel(luma(a), cv2.CV_64F, 1, 0), cv2.Sobel(luma(a), cv2.CV_64F, 0, 1)).ravel()
    eb = np.hypot(cv2.Sobel(luma(b), cv2.CV_64F, 1, 0), cv2.Sobel(luma(b), cv2.CV_64F, 0, 1)).ravel()
    return float(np.corrcoef(ea, eb)[0, 1]) if ea.std() and eb.std() else 0.0


def tiles_of(img):
    h, w = img.shape[:2]
    rows, cols = h // T, w // T
    t = img[:rows * T, :cols * T].reshape(rows, T, cols, T, -1).transpose(0, 2, 1, 3, 4)
    return t.reshape(rows * cols, T, T, -1).astype(np.float64), rows, cols


def assemble(tiles, placement, rows, cols):
    """placement[pos] = tile index -> image."""
    t = tiles[np.asarray(placement)].reshape(rows, cols, T, T, -1).transpose(0, 2, 1, 3, 4)
    return np.clip(t.reshape(rows * T, cols * T, -1), 0, 255).astype(np.uint8)


def dissimilarities(tiles):
    """D_lr[i, j]: cost of j right of i; D_tb[i, j]: cost of j below i (gradient continuation)."""
    right_pred = 2 * tiles[:, :, -1, :] - tiles[:, :, -2, :]          # (n, T, C) extrapolated next column
    left = tiles[:, :, 0, :]
    down_pred = 2 * tiles[:, -1, :, :] - tiles[:, -2, :, :]
    top = tiles[:, 0, :, :]
    n = len(tiles)
    a, b = right_pred.reshape(n, -1), left.reshape(n, -1)
    d_lr = (a ** 2).sum(1)[:, None] + (b ** 2).sum(1)[None, :] - 2 * a @ b.T
    a, b = down_pred.reshape(n, -1), top.reshape(n, -1)
    d_tb = (a ** 2).sum(1)[:, None] + (b ** 2).sum(1)[None, :] - 2 * a @ b.T
    np.fill_diagonal(d_lr, np.inf)
    np.fill_diagonal(d_tb, np.inf)
    return np.maximum(d_lr, 0), np.maximum(d_tb, 0)


def _normalised(d_lr, d_tb):
    """Divide each dissimilarity by the second-best alternative of BOTH tiles involved."""
    def second(x, axis):
        return np.partition(x, 1, axis=axis).take(1, axis=axis) + 1e-6
    n_lr = 0.5 * (d_lr / second(d_lr, 1)[:, None] + d_lr / second(d_lr, 0)[None, :])
    n_tb = 0.5 * (d_tb / second(d_tb, 1)[:, None] + d_tb / second(d_tb, 0)[None, :])
    return n_lr, n_tb


def solve(tiles, rows, cols):
    """Greedy region growing; returns placement[pos] = tile index (raster positions)."""
    d_lr, d_tb = dissimilarities(tiles)
    n_lr, n_tb = _normalised(d_lr, d_tb)
    n = len(tiles)
    # best buddies: i's best right neighbour is j and j's best left neighbour is i (same vertically)
    br, bl = np.argmin(d_lr, 1), np.argmin(d_lr, 0)
    bd, bu = np.argmin(d_tb, 1), np.argmin(d_tb, 0)
    buddies = (bl[br] == np.arange(n)).astype(int) + (br[bl] == np.arange(n)).astype(int) + \
              (bu[bd] == np.arange(n)).astype(int) + (bd[bu] == np.arange(n)).astype(int)
    start = int(np.argmax(buddies))
    placed = {(0, 0): start}
    used = np.zeros(n, bool)
    used[start] = True
    rmin = rmax = cmin = cmax = 0
    while len(placed) < n:
        best = (np.inf, None, None)
        frontier = {(r + dr, c + dc) for (r, c) in placed for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0))}
        for (r, c) in frontier:
            if (r, c) in placed:
                continue
            if max(rmax, r) - min(rmin, r) >= rows or max(cmax, c) - min(cmin, c) >= cols:
                continue                                        # would not fit in the frame
            cost, k = np.zeros(n), 0
            if (r, c - 1) in placed:
                cost += n_lr[placed[(r, c - 1)]]; k += 1
            if (r, c + 1) in placed:
                cost += n_lr[:, placed[(r, c + 1)]]; k += 1
            if (r - 1, c) in placed:
                cost += n_tb[placed[(r - 1, c)]]; k += 1
            if (r + 1, c) in placed:
                cost += n_tb[:, placed[(r + 1, c)]]; k += 1
            cost = cost / k - 0.05 * (k - 1)                    # prefer slots with more known neighbours
            cost[used] = np.inf
            j = int(np.argmin(cost))
            if cost[j] < best[0]:
                best = (cost[j], (r, c), j)
        _, (r, c), j = best
        placed[(r, c)] = j
        used[j] = True
        rmin, rmax, cmin, cmax = min(rmin, r), max(rmax, r), min(cmin, c), max(cmax, c)
    return [placed[(rmin + p // cols, cmin + p % cols)] for p in range(rows * cols)]


def accuracies(placement, truth, rows, cols):
    """truth[tile] = true position of that tile."""
    pos_acc = float(np.mean([truth[t] == p for p, t in enumerate(placement)]))
    good = total = 0
    for p, t in enumerate(placement):
        r, c = divmod(p, cols)
        if c + 1 < cols:
            total += 1
            good += truth[placement[p + 1]] == truth[t] + 1 and truth[t] % cols != cols - 1
        if r + 1 < rows:
            total += 1
            good += truth[placement[p + cols]] == truth[t] + cols
    return pos_acc, good / max(1, total)


def attack_frame(rgb, mode="E5", key=bytes(range(16)), sid=7, ctr=1, quality=75, use_attack_view=True,
                 solver="greedy"):
    """Returns dict of metrics (+ images) for one frame."""
    e = package_frame(analyse_frame(rgb, quality), key, sid, ctr, mode)
    seen = decode(replacement_attack_jpeg(e.jpeg)) if use_attack_view else decode(e.jpeg)
    tiles, rows, cols = tiles_of(seen)
    n = rows * cols
    order = _shuffle_order(key, sid, ctr, n)          # ground truth: tile at slot p belongs at order[p]
    if solver == "mst":                               # stronger solver (GUIDE B9)
        from future_work.attacks.mst_jigsaw import solve as mst_solve
        placement = mst_solve(tiles, rows, cols)
    else:
        placement = solve(tiles, rows, cols)
    solved = assemble(tiles, placement, rows, cols)
    pos_acc, nb_acc = accuracies(placement, order, rows, cols)
    unshuffled = np.empty(n, int)
    unshuffled[np.asarray(order)] = np.arange(n)
    oracle = assemble(tiles, unshuffled, rows, cols)  # attacker with perfect placement (upper bound)
    crop = rgb[:rows * T, :cols * T]
    return dict(position_accuracy=pos_acc, neighbour_accuracy=nb_acc,
                edge_corr_shuffled=edge_corr(seen[:rows * T, :cols * T], crop),
                edge_corr_solved=edge_corr(solved, crop),
                edge_corr_perfect_placement=edge_corr(oracle, crop),
                images=dict(seen=seen, solved=solved, oracle=oracle))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=5)
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--save-images", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--solver", choices=["greedy", "mst"], default="greedy",
                    help="greedy region growing, or the MST solver of mst_jigsaw.py (GUIDE B9)")
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    src = open_source(a.video, w, h, loop=False)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(a.frames):
        for _ in range(a.stride - 1):
            src.read()
        rgb = src.read()
        if rgb is None:
            break
        r = attack_frame(rgb, ctr=i + 1, solver=a.solver)
        imgs = r.pop("images")
        rows.append(r)
        print(f"frame {i}: position {r['position_accuracy']:.2f}, neighbours {r['neighbour_accuracy']:.2f}, "
              f"edge corr shuffled {r['edge_corr_shuffled']:.3f} -> solved {r['edge_corr_solved']:.3f} "
              f"(perfect placement {r['edge_corr_perfect_placement']:.3f})")
        if a.save_images and i == 0:
            cv2.imwrite(str(out / "jigsaw_original.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
            for k, v in imgs.items():
                cv2.imwrite(str(out / f"jigsaw_{k}.png"), cv2.cvtColor(v, cv2.COLOR_RGB2BGR))
    keys = list(rows[0])
    summary = {k: dict(mean=float(np.mean([r[k] for r in rows])), std=float(np.std([r[k] for r in rows])))
               for k in keys}
    (out / "jigsaw.json").write_text(json.dumps(dict(source=a.video, size=a.size, frames=len(rows), solver=a.solver,
                                                     summary=summary, per_frame=rows), indent=2))
    md = ["| Metric (E5, mean ± std) | Value |", "|---|---|"] + \
         [f"| {k.replace('_', ' ')} | {v['mean']:.3f} ± {v['std']:.3f} |" for k, v in summary.items()]
    (out / "jigsaw.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md) + f"\n\nwritten {out}/jigsaw.json / .md")


if __name__ == "__main__":
    main()
