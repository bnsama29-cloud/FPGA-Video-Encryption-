"""Gate for the jigsaw attack on E5: how well do the greedy and the MST solvers reassemble
UNENCRYPTED shuffled tiles? A solver's E5 result only means something if it works on plain tiles.

    python -m system.attacks.jigsaw_gate                 # scikit-image test photos, 320x240, 16x16 tiles

Writes sim_out/jigsaw_gate.json and .md: neighbour and position accuracy per photo and solver.
"""
import json
import time
from pathlib import Path

import cv2
import numpy as np

from system.attacks.jigsaw_attack import accuracies, solve as greedy, tiles_of
from system.attacks.mst_jigsaw import solve as mst

OUT = Path(__file__).resolve().parents[2] / "sim_out"
PHOTOS = ["astronaut", "chelsea", "coffee", "rocket", "cat", "immunohistochemistry"]


def main():
    from skimage import data
    rows_out = {}
    for name in PHOTOS:
        img = getattr(data, name)()
        if img.ndim == 2:
            img = np.dstack([img] * 3)
        rgb = cv2.resize(img[..., :3], (320, 240), interpolation=cv2.INTER_AREA)
        tiles, rows, cols = tiles_of(rgb)
        order = np.random.default_rng(1).permutation(len(tiles))
        rows_out[name] = {}
        for sname, f in (("greedy", greedy), ("mst", mst)):
            t0 = time.time()
            pos, nb = accuracies(f(tiles[order], rows, cols), list(order), rows, cols)
            rows_out[name][sname] = dict(neighbours=nb, positions=pos, seconds=time.time() - t0)
        print(name, {k: round(v["neighbours"], 3) for k, v in rows_out[name].items()})
    OUT.mkdir(exist_ok=True)
    (OUT / "jigsaw_gate.json").write_text(json.dumps(dict(size="320x240", tile=16, photos=rows_out), indent=1))
    md = ["| Photo (plain tiles) | Greedy: neighbours / positions | MST: neighbours / positions |", "|---|---|---|"]
    md += [f"| {n} | {v['greedy']['neighbours']:.2f} / {v['greedy']['positions']:.2f} | "
           f"{v['mst']['neighbours']:.2f} / {v['mst']['positions']:.2f} |" for n, v in rows_out.items()]
    (OUT / "jigsaw_gate.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
