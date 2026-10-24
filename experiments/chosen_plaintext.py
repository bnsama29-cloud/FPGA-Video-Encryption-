"""Chosen-plaintext attack on block shuffling, transferred across frames (research R8).

    python experiments/chosen_plaintext.py                                  # synthetic scene
    python experiments/chosen_plaintext.py --video clips/x.mp4 --frames 6 --stride 30

Why. Li et al. (J. Shanghai Jiaotong Univ. (Sci.) 30(5), 2025, online 2023) break JPEG encryption
with block-position shuffling by a chosen-plaintext attack: the attacker shows the camera a designed
picture, reads where each block went (the number of non-zero coefficients per block survives the
shuffle), and then undoes the same permutation on every other image. That works whenever the
permutation is a function of the key alone.

E5 draws its permutation from Ascon under a separate key AND the frame nonce (session, counter), so
every frame has a fresh permutation. This script gives the attacker the best case -- the exact
permutation of frame t, as if the chosen-plaintext step had succeeded perfectly -- and applies it to
frame t+1:

  as seen          the E5 replacement-attack picture of frame t+1, not unshuffled
  key-only shuffle a scheme whose permutation depends on the key only: the learned permutation IS
                   frame t+1's permutation, so the attacker gets the oracle picture
  E5 (per frame)   the permutation of frame t applied to frame t+1
Metrics: share of 16x16 tiles put back in the right place, edge correlation and SSIM (luma) with the
original. Writes sim_out/chosen_plaintext/<name>.json and .md.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from system.attacks.jigsaw_attack import T, edge_corr, luma   # noqa: E402
from link.sources import open_source                               # noqa: E402
from model.jpeg import analyse_frame                               # noqa: E402
from restart_interval import attack_ri, decode, encode_ri          # noqa: E402

OUT = ROOT / "sim_out" / "chosen_plaintext"


def unshuffle(img, perm, rows, cols):
    """Put the tile shown at raster position k back to position perm[k]."""
    tiles = img.reshape(rows, T, cols, T, 3).transpose(0, 2, 1, 3, 4).reshape(rows * cols, T, T, 3)
    out = np.empty_like(tiles)
    for k, m in enumerate(perm[:rows * cols]):
        out[m] = tiles[k]
    return out.reshape(rows, cols, T, T, 3).transpose(0, 2, 1, 3, 4).reshape(rows * T, cols * T, 3)


def pair(rgb_next, ctr):
    """Attacker knows the permutation of frame `ctr`; frame ctr+1 is protected with E5."""
    from skimage.metrics import structural_similarity as ssim
    an = analyse_frame(rgb_next)
    rows, cols = rgb_next.shape[0] // T, rgb_next.shape[1] // T
    crop = rgb_next[:rows * T, :cols * T]
    _, perm_learned, _, _ = encode_ri(an, 1, ctr=ctr)                 # frame t (chosen plaintext)
    _, perm_true, shown, _ = encode_ri(an, 1, ctr=ctr + 1)            # frame t+1
    seen = decode(attack_ri(an, shown, 1))[:rows * T, :cols * T]
    yc = luma(crop)
    res = {}
    identity = list(range(rows * cols))
    for name, perm in (("as seen", None), ("key-only shuffle", perm_true), ("E5 (per frame)", perm_learned)):
        pic = seen if perm is None else unshuffle(seen, perm, rows, cols)
        guess = identity if perm is None else perm
        placed = float(np.mean([guess[k] == perm_true[k] for k in range(rows * cols)]))
        res[name] = dict(tiles_correct=placed, edge=edge_corr(pic, crop),
                         ssim=float(ssim(luma(pic), yc, data_range=255)))
    res["n_tiles"] = rows * cols
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--stride", type=int, default=30)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    name = a.name or Path(a.video).stem
    src = open_source(a.video, w, h, loop=True)
    per = []
    for i in range(a.frames):
        rgb = None
        for _ in range(a.stride if i else 1):
            rgb = src.read()
        if rgb is None:
            break
        per.append(pair(rgb, ctr=2 * i + 1))
    keys = ["as seen", "key-only shuffle", "E5 (per frame)"]
    mean = {k: {m: statistics.mean(f[k][m] for f in per) for m in ("tiles_correct", "edge", "ssim")} for k in keys}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(dict(source=name, frames=len(per), n_tiles=per[0]["n_tiles"],
                                                      mean=mean, per_frame=per), indent=1))
    md = [f"### R8: chosen-plaintext permutation transferred to the next frame ({name}, {len(per)} frame pairs, "
          f"{per[0]['n_tiles']} tiles)", "",
          "| Attacker's picture of frame t+1 | Tiles in place | Edge corr. | SSIM |", "|---|---|---|---|"]
    for k in keys:
        v = mean[k]
        md.append(f"| {k} | {100 * v['tiles_correct']:.1f} % | {v['edge']:.3f} | {v['ssim']:.3f} |")
    md += ["", "The attacker is given the exact permutation of frame t (a perfect chosen-plaintext step). "
               "Key-only shuffle: that permutation is also frame t+1's (oracle)."]
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
