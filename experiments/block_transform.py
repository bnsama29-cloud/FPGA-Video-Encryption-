"""R6 -- E5 hardened with a keyed flip/transpose of every 8x8 block in the DCT domain (research suite).

    python experiments/block_transform.py                                 # synthetic scene
    python experiments/block_transform.py --video clips/x.mp4 --frames 6 --stride 150

Why. Block-scrambling encryption with one shuffle for all blocks is vulnerable to jigsaw-puzzle
solvers; adding an independent keyed transform per block defeats them (Chuman and Kiya,
arXiv:2207.08109: neighbour score 0.51-0.94 for plain scrambling against 0.06 with independent block
keys). E5 is plain scrambling of 16x16 macroblocks.

How (format-compliant, nearly free in hardware). For the 8-point DCT-II, mirroring the samples of a
row multiplies coefficient k by (-1)^k, and transposing the block transposes the coefficients. So all
8 symmetries of the square (flips and transposition) are exact operations on the quantized
coefficients: negate odd columns / odd rows, swap u and v. The DC coefficient never changes (DC
prediction is unaffected), the result is valid baseline JPEG, and the key holder undoes the
transform exactly before dequantisation. 3 keystream bits per 8x8 block (a separate key, as for the
shuffle). In RTL: sign flips and an address swap at the quantiser output.

Attacker. The same keyless view as for E5 (replacement attack), then:
  * the greedy jigsaw solver over 16x16 tiles (as for E5, neighbour accuracy and edge correlation);
  * an orientation-repair attacker that even KNOWS the true tile positions (oracle) and only has to
    undo the block transforms: for every 8x8 luma block it picks, of the 8 orientations, the one that
    continues its already repaired left and top neighbours best. This bounds what the transform adds
    on top of the shuffle: if repair recovers the edges, the transform adds little.
Writes sim_out/block_transform/<name>.json and .md.

RESULT (synthetic scene, 15 Oct 2026) -- a negative result with a clear reason: the transform adds
almost nothing. In the DCT domain a flip IS a pattern of sign changes, and E4/E5 already encrypt every
sign; the attacker's replacement view drops signs anyway. Only the transposition is left (oracle-
position SSIM 0.555 -> 0.545). Hence E5's security rests on the block POSITIONS staying unsolved: an
attacker who found them would get SSIM ~0.55. Kept to confirm on the real clips (Kaggle).
"""
import argparse
import dataclasses
import json
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from future_work.attacks.jigsaw_attack import T, edge_corr, luma                # noqa: E402
from link.sources import open_source                                         # noqa: E402
from model import ascon                                                      # noqa: E402
from model.entropy import run_length_encode                                  # noqa: E402
from model.jpeg import analyse_frame                                         # noqa: E402
from restart_interval import KEY, attack_ri, decode, encode_ri, jigsaw_ri    # noqa: E402

OUT = ROOT / "sim_out" / "block_transform"
_ODD = (-1.0) ** np.arange(8)


def dihedral(c, k):
    """k in 0..7 applied to an 8x8 coefficient block: bit0 transpose, bit1 mirror columns (negate odd
    u), bit2 mirror rows (negate odd v). Works on quantised integer coefficients."""
    if k & 1:
        c = c.T
    if k & 2:
        c = c * _ODD[None, :]
    if k & 4:
        c = c * _ODD[:, None]
    return c


def _inverse_table():
    rng = np.random.default_rng(0)
    x = rng.integers(-50, 50, (8, 8))
    return [next(j for j in range(8) if np.array_equal(dihedral(dihedral(x, k), j), x)) for k in range(8)]


INV = _inverse_table()


def transform_key(key):
    return ascon.mac(key, ascon.make_nonce(0, 0, 0), b"E5 block transform")


def block_codes(key, sid, ctr, n_blocks):
    ks = ascon.Keystream(transform_key(key), ascon.make_nonce(sid, ctr, 0))
    return [ks.take(3) for _ in range(n_blocks)]


def apply_transform(quant, codes, inverse=False):
    q = quant.copy()
    flat = q.reshape(-1, 8, 8)
    for i, k in enumerate(codes):
        flat[i] = dihedral(flat[i], INV[k] if inverse else k).astype(q.dtype)
    return q


def pixel_dihedral(b, k):
    """Same symmetry on an 8x8 pixel block (transpose, then mirror columns, then rows)."""
    if k & 1:
        b = b.T
    if k & 2:
        b = b[:, ::-1]
    if k & 4:
        b = b[::-1, :]
    return b


def repair_orientation(y):
    """Oracle-position attacker: undo the unknown per-block orientations greedily (luma)."""
    h, w = (y.shape[0] // 8) * 8, (y.shape[1] // 8) * 8
    out = y[:h, :w].astype(np.float64).copy()
    for r in range(0, h, 8):
        for c in range(0, w, 8):
            blk = out[r:r + 8, c:c + 8].copy()
            best, cost_best = blk, None
            for k in range(8):
                cand = pixel_dihedral(blk, INV[k])
                cost = 0.0
                if c:
                    cost += np.abs(cand[:, 0] - out[r:r + 8, c - 1]).sum()
                if r:
                    cost += np.abs(cand[0, :] - out[r - 1, c:c + 8]).sum()
                if cost_best is None or cost < cost_best:
                    best, cost_best = cand, cost
            out[r:r + 8, c:c + 8] = best
    return out


def edge_corr_luma(a, b):
    from future_work.attacks.jigsaw_attack import _normalised  # noqa: F401  (same module, same Sobel)
    import cv2
    g = lambda x: np.hypot(cv2.Sobel(x, cv2.CV_64F, 1, 0), cv2.Sobel(x, cv2.CV_64F, 0, 1)).ravel()
    ga, gb = g(a.astype(np.float64)), g(b.astype(np.float64))
    return float(np.corrcoef(ga, gb)[0, 1]) if ga.std() and gb.std() else 0.0


def measure(rgb, ctr):
    an = analyse_frame(rgb)
    rows_px, cols_px = (rgb.shape[0] // T) * T, (rgb.shape[1] // T) * T
    crop = rgb[:rows_px, :cols_px]
    res = {}
    codes = block_codes(KEY, 7, ctr, an.quant.shape[0] * 6)
    qt = apply_transform(an.quant, codes)
    assert np.array_equal(apply_transform(qt, codes, inverse=True), an.quant), "transform not invertible"
    an_t = dataclasses.replace(an, quant=qt, symbols=run_length_encode(qt))
    for name, a in (("E5", an), ("E5+T", an_t)):
        jpeg, perm, shown, order = encode_ri(a, 1, ctr=ctr)
        att = decode(attack_ri(a, shown, 1))[:rows_px, :cols_px]
        nb, ec = jigsaw_ri(att, 1, order, crop)
        # oracle placement: put every shown tile back where it belongs
        rows, cols = rows_px // T, cols_px // T
        tiles = att.reshape(rows, T, cols, T, 3).transpose(0, 2, 1, 3, 4).reshape(rows * cols, T, T, 3)
        placed = np.empty_like(tiles)
        for p, m in enumerate(perm[:rows * cols]):
            placed[m] = tiles[p]
        oracle = placed.reshape(rows, cols, T, T, 3).transpose(0, 2, 1, 3, 4).reshape(rows_px, cols_px, 3)
        from skimage.metrics import structural_similarity as ssim
        yc = luma(crop)
        r = dict(size=len(jpeg), jigsaw_neighbours=nb, edge_jigsaw=ec, edge_shown=edge_corr(att, crop),
                 edge_oracle_positions=edge_corr(oracle, crop),
                 ssim_oracle_positions=float(ssim(luma(oracle), yc, data_range=255)))
        if name == "E5+T":
            rep = repair_orientation(luma(oracle))
            yc8 = yc[:rep.shape[0], :rep.shape[1]]
            r["edge_oracle_positions_repaired"] = edge_corr_luma(rep, yc8)
            r["ssim_oracle_positions_repaired"] = float(ssim(rep, yc8, data_range=255))
        res[name] = r
    res["E5+T"]["size_vs_E5_pct"] = 100 * (res["E5+T"]["size"] / res["E5"]["size"] - 1)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--stride", type=int, default=30)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    name = a.name or Path(a.video).stem
    src = open_source(a.video, w, h, loop=False)
    per = []
    for i in range(a.frames):
        rgb = None
        for _ in range(a.stride if i else 1):
            rgb = src.read()
            if rgb is None:
                break
        if rgb is None:
            break
        per.append(measure(rgb, i + 1))
    keys = ["jigsaw_neighbours", "edge_shown", "edge_jigsaw", "edge_oracle_positions", "ssim_oracle_positions"]
    mean = {m: {k: statistics.mean(f[m][k] for f in per) for k in keys} for m in ("E5", "E5+T")}
    mean["E5+T"]["edge_oracle_positions_repaired"] = statistics.mean(f["E5+T"]["edge_oracle_positions_repaired"] for f in per)
    mean["E5+T"]["ssim_oracle_positions_repaired"] = statistics.mean(f["E5+T"]["ssim_oracle_positions_repaired"] for f in per)
    mean["E5+T"]["size_vs_E5_pct"] = statistics.mean(f["E5+T"]["size_vs_E5_pct"] for f in per)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(dict(source=name, frames=len(per), mean=mean, per_frame=per), indent=1))
    md = [f"### R6: E5 with keyed DCT-domain block transforms ({name}, {len(per)} frames)", "",
          "| Level | Jigsaw neighbours | Edge, as seen | Edge, after jigsaw | Oracle positions: edge / SSIM | "
          "+ orientation repair: edge / SSIM | Size vs E5 |", "|---|---|---|---|---|---|---|"]
    for m in ("E5", "E5+T"):
        v = mean[m]
        rep = (f"{v['edge_oracle_positions_repaired']:.3f} / {v['ssim_oracle_positions_repaired']:.3f}"
               if "edge_oracle_positions_repaired" in v else "--")
        sz = f"{v['size_vs_E5_pct']:+.1f} %" if "size_vs_E5_pct" in v else "--"
        md.append(f"| {m} | {100 * v['jigsaw_neighbours']:.1f} % | {v['edge_shown']:.3f} | {v['edge_jigsaw']:.3f} | "
                  f"{v['edge_oracle_positions']:.3f} / {v['ssim_oracle_positions']:.3f} | {rep} | {sz} |")
    md += ["", "Oracle columns are upper bounds for an attacker who knows every tile position; for E5+T the "
               "last column also undoes the block orientations greedily."]
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
