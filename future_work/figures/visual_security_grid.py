"""The paper's visual-security figure: what each party sees, per mode, on the same frame.

    python -m future_work.figures.visual_security_grid                         # synthetic CCTV frame
    python -m future_work.figures.visual_security_grid --image photo.jpg --size 320x240

Row 1 ("plays in any viewer, no key"): original | E1 | E2 | E4 | E5
Row 2 ("eavesdropper's best effort"):  plain JPEG | replacement attack E1 | E2 | E4 | E5 + jigsaw solver
Row 3 ("key holder"): decrypted output of every mode, with a check that it is bit-exact.
Under each attacker image: edge correlation with the original (0 = nothing leaked).
Writes future_work/results/visual_security_grid.png (and .pdf for the paper).
"""
import argparse
import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from future_work.attacks.jigsaw_attack import assemble, edge_corr, solve, tiles_of
from link.sources import open_source
from model.jpeg import analyse_frame, package_frame, receive_frame, replacement_attack_jpeg

OUT = Path(__file__).resolve().parents[1] / "results"
KEY = bytes(range(16))
MODES = ["E1", "E2", "E4", "E5"]
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def build(rgb, quality=75):
    an = analyse_frame(rgb, quality)
    plain = package_frame(an)
    cells = {"original": rgb, "plain": decode(plain.jpeg)}
    for i, m in enumerate(MODES):
        e = package_frame(an, KEY, 7, i + 1, m)
        cells[f"wire_{m}"] = decode(e.jpeg)
        att = decode(replacement_attack_jpeg(e.jpeg))
        if m == "E5":
            tiles, rows, cols = tiles_of(att)
            att = assemble(tiles, solve(tiles, rows, cols), rows, cols)
        cells[f"attack_{m}"] = att
        r = receive_frame(e.jpeg, KEY)
        cells[f"decrypted_{m}"] = decode(r.plain_jpeg)
        cells[f"exact_{m}"] = r.ok and r.plain_jpeg == plain.jpeg
    return cells


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image")
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frame", type=int, default=30)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    if a.image:
        rgb = cv2.resize(cv2.cvtColor(cv2.imread(a.image), cv2.COLOR_BGR2RGB), (w, h), interpolation=cv2.INTER_AREA)
    else:
        src = open_source(a.video, w, h, loop=True)
        for _ in range(a.frame):
            rgb = src.read()
    c = build(rgb)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 5, figsize=(7.0, 4.2), facecolor=SURFACE)   # sized for 0.7\textwidth: labels stay >= 5 pt
    rows = [
        ("Any viewer, no key", [("original", "Original")] + [(f"wire_{m}", m) for m in MODES]),
        ("Eavesdropper", [("plain", "Unprotected")]
         + [(f"attack_{m}", f"{m} attack" + (" + jigsaw" if m == "E5" else "")) for m in MODES]),
        ("Key holder", [("original", "Original")] + [(f"decrypted_{m}", f"{m} decrypted") for m in MODES]),
    ]
    for r, (label, cells) in enumerate(rows):
        for k, (key, title) in enumerate(cells):
            ax = axes[r][k]
            ax.imshow(c[key])
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
            sub = ""
            if r == 1:
                sub = f"\nedge corr. {edge_corr(c[key], c['original']):.2f}"
            if r == 2 and k > 0:
                sub = "\nbit-exact" if c[f"exact_{MODES[k - 1]}"] else "\nNOT bit-exact"
            ax.set_title(title + sub, fontsize=7, color=INK, pad=2)
            if k == 0:
                ax.set_ylabel(label, fontsize=7, color=INK2)
    fig.tight_layout(pad=0.3, h_pad=0.4, w_pad=0.2)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "visual_security_grid.png", dpi=300)
    fig.savefig(out / "visual_security_grid.pdf")
    plt.close(fig)
    print(f"written {out}/visual_security_grid.png / .pdf")


if __name__ == "__main__":
    main()
