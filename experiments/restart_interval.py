"""Restart interval of the E5 shuffle, and the non-zero counting attack (GUIDE.md B5 + B15).

    python experiments/restart_interval.py                                   # synthetic scene
    python experiments/restart_interval.py --video clips/open.mp4 --frames 8 --stride 120
    python experiments/restart_interval.py --video data/kodak --frames 24 --stride 1   # image folder

E5 cuts the scan into segments with restart markers and permutes the segments with a key.
The golden model and the paper use one MCU per segment (restart interval N = 1). Larger N
costs fewer marker bytes, but each segment carries more of the picture intact. Hirose et al.
(arXiv:2410.06522) found that large intervals let outlines reappear under a non-zero
counting attack. This script measures that trade-off for N = 1, 2, 4, 8, 32:

  overhead   bytes of E5(N) relative to the same E4 coefficients in one segment without markers
             (neither file carries the APP11 secure segment, so the ratio is the marker cost alone)
  replacement-attack edge correlation   keyless reconstruction (as in measure_mode_tradeoff)
  NZCA correlation      the number of non-zero AC coefficients per 8x8 block (visible: run/size
                        codes are never encrypted), correlated with the original's edge energy per
                        8x8 block -- i.e. how well a count map reveals the outline
  jigsaw                greedy region-growing solver whose pieces are whole segments (N tiles in a
                        strip): the attacker sees the restart markers and the DRI value, so it knows N
                        (computed when N divides the MCU columns)
  raster solver         works for every N: segments are laid in raster order, each time choosing the
                        unused segment whose borders best continue the tiles already placed (left
                        and above); every segment is tried as the first one and the ordering with the
                        lowest total cost wins. Segments wrap across rows, as in the real stream.
                        Reports the share of segments put back in their true place and the edge
                        correlation of the solved picture. With few segments (large N) this is the
                        attack that matters: N = 32 leaves about ten pieces.
The rows "E4" are the unshuffled reference. Global correlations understate what large intact
segments show locally (Hirose et al. judged NZCA visually): --save-images writes the attacker's
picture per N for the first frame. Writes sim_out/restart_interval/<name>.json / .md.

E5 with N > 1 is built here from the model's own building blocks (run-length coding per
group, keystream, Huffman per segment, restart markers, keyed permutation). The model's E5
(N = 1) is unchanged; tests/test_new_experiments.py checks that this encoder decodes to the
same picture as the model and that the key holder can invert it.
"""
import argparse
import io
import json
import math
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from future_work.attacks.jigsaw_attack import (T, _normalised, accuracies, assemble, dissimilarities,  # noqa: E402
                                               edge_corr, solve, tiles_of)
from link.sources import open_source                               # noqa: E402
from model import ascon                                            # noqa: E402
from model.container import build_jpeg                             # noqa: E402
from model.entropy import huffman_encode, join_restart, run_length_encode  # noqa: E402
from model.jpeg import _shuffle_order, analyse_frame, package_frame   # noqa: E402
from model.selective import apply_keystream, replacement_attack   # noqa: E402

KEY = bytes(range(16))
OUT = ROOT / "sim_out" / "restart_interval"


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def groups_of(n_mcu, n):
    return [range(i, min(i + n, n_mcu)) for i in range(0, n_mcu, n)]


def encode_ri(an, n, key=KEY, sid=7, ctr=1, mode="E4", shuffle=True):
    """E4-encrypted (key=None: plain) frame with restart interval n MCUs, segments optionally
    permuted with the model's keyed shuffle. Returns (jpeg, perm_mcu, shown_group_symbols, order):
    perm_mcu[k] = original index of the MCU shown at raster position k, order[p] = original index
    of the segment shown at position p."""
    q = an.quant
    groups = groups_of(len(q), n)
    per_group = [run_length_encode(q[g.start:g.stop]) for g in groups]   # DC predictors reset per group
    if key is not None:
        flat = [s for g in per_group for s in g]
        flat, _ = apply_keystream(flat, ascon.Keystream(key, ascon.make_nonce(sid, ctr, 0)), mode)
        it = iter(flat)
        per_group = [[next(it) for _ in g] for g in per_group]
    order = _shuffle_order(key, sid, ctr, len(groups)) if (shuffle and key is not None) else list(range(len(groups)))
    segs = [huffman_encode(g)[0] for g in per_group]
    scan = join_restart([segs[i] for i in order])
    jpeg = build_jpeg(an.width, an.height, an.qy, an.qc, scan, restart_interval=n if len(groups) > 1 else 0)
    perm_mcu = [m for p in order for m in groups[p]]
    return jpeg, perm_mcu, [per_group[i] for i in order], order


def attack_ri(an, shown_groups, n, mode="E4"):
    """Replacement attack on the (shuffled) segments, re-encoded as a valid JPEG."""
    segs = [huffman_encode(replacement_attack(g, mode))[0] for g in shown_groups]
    return build_jpeg(an.width, an.height, an.qy, an.qc, join_restart(segs), restart_interval=n)


def nzca_map(an, perm_mcu):
    """Non-zero counting attack: the number of non-zero AC coefficients of every 8x8 luma block,
    laid out as the attacker sees the MCUs (perm_mcu). The counts come from the run/size codes,
    which are never encrypted. Returns one value per 8x8 block (rows*2, cols*2)."""
    q = an.quant                                   # (n_mcu, 6, 8, 8): blocks 0-3 are Y in 2x2 order
    cols = (an.width + 15) // 16
    rows = len(q) // cols
    cnt = (q[:, :4] != 0).sum(axis=(2, 3)) - (q[:, :4, 0, 0] != 0)       # AC only
    out = np.zeros((rows * 2, cols * 2))
    for k, m in enumerate(perm_mcu):
        r, c = divmod(k, cols)
        for b in range(4):
            out[r * 2 + b // 2, c * 2 + b % 2] = cnt[m, b]
    return out


def block_edge_energy(rgb, shape):
    """Mean Sobel gradient magnitude of the original luma in every 8x8 block (the outline at
    block resolution, which is what NZCA can reveal at best)."""
    y = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float64)
    g = np.hypot(cv2.Sobel(y, cv2.CV_64F, 1, 0), cv2.Sobel(y, cv2.CV_64F, 0, 1))
    r, c = shape
    return g[:r * 8, :c * 8].reshape(r, 8, c, 8).mean(axis=(1, 3))


def nzca_corr(an, perm_mcu, rgb):
    a = nzca_map(an, perm_mcu)
    b = block_edge_energy(rgb, a.shape)
    return float(np.corrcoef(a.ravel(), b.ravel())[0, 1]) if a.std() and b.std() else 0.0


def jigsaw_ri(att_img, n, order, crop):
    """The attacker knows N (DRI marker) and the segment boundaries (restart markers), so it solves
    the puzzle with whole segments as pieces: strips of N tiles. Only possible when N divides the
    number of MCU columns (then every segment is one horizontal strip); otherwise returns None."""
    rows, cols = crop.shape[0] // T, crop.shape[1] // T
    if cols % n:
        return None, None
    k = cols // n
    pieces = att_img[:rows * T, :cols * T].reshape(rows, T, k, T * n, 3).transpose(0, 2, 1, 3, 4)
    pieces = pieces.reshape(rows * k, T, T * n, 3).astype(np.float64)
    placement = solve(pieces, rows, k)
    _, nb = accuracies(placement, list(order), rows, k)
    solved = pieces[np.asarray(placement)].reshape(rows, k, T, T * n, 3).transpose(0, 2, 1, 3, 4)
    solved = np.clip(solved.reshape(rows * T, cols * T, 3), 0, 255).astype(np.uint8)
    return nb, edge_corr(solved, crop)


def segments_of(order, n, n_mcu):
    """Tile indices (raster positions in the attacker's picture) of every shown segment. The attacker
    knows these: restart markers delimit the segments and decoding counts their MCUs."""
    groups = groups_of(n_mcu, n)
    out, k = [], 0
    for g in order:
        out.append(np.arange(k, k + len(groups[g])))
        k += len(groups[g])
    return out


def raster_solve(tiles, segs, cols, beam=32):
    """Order the shown segments by raster placement with a beam search (see the module docstring).
    tiles are the attacker's T x T tiles in shown order, segs the tile indices per shown segment.
    Every full-length segment starts a hypothesis; at each step every hypothesis is extended by each
    unused segment, scored by how well its borders continue the tiles already placed to its left and
    above, and the `beam` lowest-cost hypotheses are kept. Returns the shown-segment indices in
    placement order (the shorter last group, which the attacker recognises by its length, goes last)."""
    d_lr, d_tb = dissimilarities(tiles)
    n_lr, n_tb = _normalised(d_lr, d_tb)
    L = max(len(s) for s in segs)
    full = [i for i, s in enumerate(segs) if len(s) == L]
    short = [i for i, s in enumerate(segs) if len(s) < L]
    A = np.array([segs[i] for i in full])                       # (F, L) tile indices
    F = len(full)
    hyps = [(0.0, [j]) for j in range(F)]
    for step in range(1, F):
        p0 = step * L
        cand = []
        for total, seq in hyps:
            tile_at = lambda p: A[seq[p // L], p % L]
            cost, k = np.zeros(F), 0
            for i in range(L):
                p = p0 + i
                r, c = divmod(p, cols)
                if i == 0 and c > 0:
                    cost += n_lr[tile_at(p - 1), A[:, 0]]
                    k += 1
                if r > 0 and p - cols < p0:
                    cost += n_tb[tile_at(p - cols), A[:, i]]
                    k += 1
            cost = total + cost / max(k, 1)
            cost[seq] = np.inf
            for j in np.argsort(cost)[:beam]:
                if np.isfinite(cost[j]):
                    cand.append((float(cost[j]), seq + [int(j)]))
        cand.sort(key=lambda h: h[0])
        hyps = cand[:beam]
    return [full[j] for j in hyps[0][1]] + short


def raster_attack(att_img, n, order, crop):
    """Raster solver on the attacker's picture: (share of segments in their true place, share of
    consecutive pairs that are true successors -- a shift-tolerant measure --, edge corr)."""
    tiles, rows, cols = tiles_of(att_img)
    segs = segments_of(order, n, rows * cols)
    seq = raster_solve(tiles, segs, cols)
    correct = sum(order[s] == q for q, s in enumerate(seq)) / len(seq)
    succ = sum(order[b] == order[a] + 1 for a, b in zip(seq, seq[1:])) / max(len(seq) - 1, 1)
    placement = np.concatenate([segs[s] for s in seq])
    return correct, succ, edge_corr(assemble(tiles, placement, rows, cols), crop)


def measure(rgb, ns, ctr, do_jigsaw=True, save_dir=None):
    an = analyse_frame(rgb)
    rows_px, cols_px = (rgb.shape[0] // T) * T, (rgb.shape[1] // T) * T
    crop = rgb[:rows_px, :cols_px]
    e4 = package_frame(an, KEY, 7, ctr, "E4").jpeg
    identity = list(range(len(an.quant)))
    from model.jpeg import replacement_attack_jpeg
    att4 = decode(replacement_attack_jpeg(e4))[:rows_px, :cols_px]
    if save_dir is not None:
        Image.fromarray(crop).save(save_dir / "original.png")
        Image.fromarray(att4).save(save_dir / "attack_E4.png")
    out = {"E4": dict(overhead_pct=0.0, edge_attack=edge_corr(att4, crop),
                      edge_nzca=nzca_corr(an, identity, rgb))}
    ref = encode_ri(an, len(an.quant), ctr=ctr, shuffle=False)[0]    # same E4 coefficients, one segment, no markers
    for n in ns:
        jpeg, perm, shown, order = encode_ri(an, n, ctr=ctr)
        att = decode(attack_ri(an, shown, n))[:rows_px, :cols_px]
        r = dict(overhead_pct=100 * (len(jpeg) / len(ref) - 1), edge_attack=edge_corr(att, crop),
                 edge_nzca=nzca_corr(an, perm, rgb),
                 segments=len(groups_of(len(an.quant), n)),
                 key_space_perm_bits=math.lgamma(len(groups_of(len(an.quant), n)) + 1) / math.log(2))
        if do_jigsaw:
            nb, ec = jigsaw_ri(att, n, order, crop)
            if nb is not None:
                r["jigsaw_neighbours"], r["edge_jigsaw"] = nb, ec
            r["raster_correct"], r["raster_successors"], r["edge_raster"] = raster_attack(att, n, order, crop)
        if save_dir is not None:
            Image.fromarray(att).save(save_dir / f"attack_E5_N{n}.png")
        out[f"E5 N={n}"] = r
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic", help="video file, image folder or 'synthetic'")
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--stride", type=int, default=30)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--intervals", nargs="+", type=int, default=[1, 2, 4, 8, 32])
    ap.add_argument("--no-jigsaw", action="store_true")
    ap.add_argument("--save-images", action="store_true", help="attacker pictures of the first frame per N")
    ap.add_argument("--name", help="output name (default: from --video)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    src = open_source(a.video, w, h, loop=False)
    per = []
    for i in range(a.frames):
        for _ in range(a.stride - 1):
            if src.read() is None:
                break
        rgb = src.read()
        if rgb is None:
            break
        if rgb.std() < 2:                 # black / flat frame: no outline to leak
            continue
        save = None
        if a.save_images and not per:
            save = Path(a.out) / f"{a.name or 'images'}_frame0"
            save.mkdir(parents=True, exist_ok=True)
        r = measure(rgb, a.intervals, i + 1, not a.no_jigsaw, save)
        per.append(r)
        print(f"frame {i}: " + "  ".join(f"{k}: att {v['edge_attack']:.2f} nzca {v['edge_nzca']:.2f}"
                                         for k, v in r.items()), flush=True)
    if not per:
        raise SystemExit("no usable frames")
    keys = list(per[0])
    summ = {}
    for k in keys:
        metrics = sorted({m for f in per for m in f[k]})
        summ[k] = {}
        for m in metrics:
            v = [f[k][m] for f in per if m in f[k]]
            summ[k][m] = dict(mean=statistics.mean(v), std=statistics.stdev(v) if len(v) > 1 else 0.0)
    name = a.name or ("synthetic" if a.video == "synthetic" else Path(str(a.video).rstrip("/")).stem.strip())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(dict(source=str(a.video), size=a.size, frames=len(per),
                                                      summary=summ), indent=1))
    f = lambda k, m, nd=2: f"{summ[k][m]['mean']:.{nd}f}" if m in summ[k] else "–"
    chance = lambda k: (f" ({1 / (summ[k]['segments']['mean'] - 1):.2f})"
                        if "segments" in summ[k] and "raster_successors" in summ[k] else "")
    md = [f"Source: {a.video}, {len(per)} frames, {a.size}", "",
          "| Variant | Overhead vs E4 (%) | Edge corr. replacement attack | NZCA corr. (block level) | Jigsaw neighbours | Edge corr. jigsaw | Raster solver: segments in place | Raster solver: true successors (chance) | Edge corr. raster solver | Permutation key space (bits) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {k} | {f(k, 'overhead_pct', 1)} | {f(k, 'edge_attack')} | {f(k, 'edge_nzca')} | "
           f"{f(k, 'jigsaw_neighbours')} | {f(k, 'edge_jigsaw')} | {f(k, 'raster_correct')} | "
           f"{f(k, 'raster_successors')}{chance(k)} | {f(k, 'edge_raster')} | "
           f"{f(k, 'key_space_perm_bits', 0)} |" for k in keys]
    (out / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md) + f"\n\nwritten {out}/{name}.json / .md")


if __name__ == "__main__":
    main()
