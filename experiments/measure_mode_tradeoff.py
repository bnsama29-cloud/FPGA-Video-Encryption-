"""Measure leakage vs cost for every encryption mode (the numbers the defence policy uses).

    python experiments/measure_mode_tradeoff.py                         # synthetic CCTV scene
    python experiments/measure_mode_tradeoff.py --video clip.mp4 --frames 30 --size 320x240

For each mode E0..E4 and each frame it computes what an eavesdropper WITHOUT the
key gets, two ways: (a) decoding the scrambled stream as a normal viewer would,
(b) the replacement attack (model/jpeg.py :: replacement_attack_jpeg) -- and keeps
the better of the two. (E5 also shuffles the MCUs; an attacker who solves the
jigsaw would do better than this -- see HELP_GUIDE.md.)
  leakage   = SSIM(original, best attacker image) on luma, clipped to 0..1
  edge_leak = correlation of Sobel edge maps (sign/DC encryption leaks outlines)
  cost      = encrypted bits / payload bits (keystream needed per frame)
Writes sim_out/mode_tradeoff.json and prints a [defence] snippet for configs/default.toml.
"""
import argparse
import io
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.sources import open_source                     # noqa: E402
from model.jpeg import analyse_frame, package_frame, replacement_attack_jpeg   # noqa: E402
from model.metrics import psnr                           # noqa: E402
from model.selective import MODES                        # noqa: E402

KEY = bytes(range(16))


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def luma(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float64)


def edges(y):
    gx = cv2.Sobel(y, cv2.CV_64F, 1, 0)
    gy = cv2.Sobel(y, cv2.CV_64F, 0, 1)
    return np.hypot(gx, gy).ravel()


def attacker_views(jpeg, mode):
    yield "no-key view", decode(jpeg)
    if mode != "E0":
        yield "replacement attack", decode(replacement_attack_jpeg(jpeg))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "mode_tradeoff.json"))
    ap.add_argument("--save-images", action="store_true", help="write the attacker images of frame 0")
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    src = open_source(a.video, w, h, loop=False)
    rows = {m: [] for m in MODES}
    out_dir = Path(a.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(a.frames):
        for _ in range(a.stride - 1):
            src.read()
        rgb = src.read()
        if rgb is None:
            break
        an = analyse_frame(rgb, a.quality)
        y0 = luma(rgb)
        for m in MODES:
            e = package_frame(an, KEY, 1, i + 1, m)
            best = None
            for name, img in attacker_views(e.jpeg, m):
                y = luma(img)
                s = structural_similarity(y0, y, data_range=255)
                if best is None or s > best[0]:
                    best = (s, name, img)
            s, name, img = best
            e0, e1 = edges(y0), edges(luma(img))
            # a flat/black frame has no edges (zero variance): correlation is undefined, so skip it in the mean
            ec = float(np.corrcoef(e0, e1)[0, 1]) if e0.std() > 0 and e1.std() > 0 else float("nan")
            rows[m].append(dict(ssim=s, psnr=psnr(rgb, img), edge_corr=ec, best_view=name,
                                cost=e.enc_bits / e.payload_bits))
            if a.save_images and i == 0:
                cv2.imwrite(str(out_dir / f"attacker_{m}.png"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        print(f"frame {i}: " + "  ".join(f"{m} ssim {rows[m][-1]['ssim']:.2f}" for m in MODES))
    summary = {}
    for m, r in rows.items():
        summary[m] = {k: float(np.nanmean([x[k] for x in r])) for k in ("ssim", "psnr", "edge_corr", "cost")}
        summary[m]["edge_corr_frames"] = int(sum(not np.isnan(x["edge_corr"]) for x in r))   # frames with defined edges
        summary[m]["ssim_std"] = float(np.std([x["ssim"] for x in r]))
        summary[m]["frames"] = len(r)
    Path(a.out).write_text(json.dumps(dict(source=a.video, size=a.size, quality=a.quality, modes=summary), indent=2))
    print(f"\n{'mode':<5}{'leakage (SSIM)':>16}{'edge corr':>11}{'PSNR dB':>9}{'cost':>8}")
    for m, s in summary.items():
        print(f"{m:<5}{s['ssim']:>11.3f} ±{s['ssim_std']:.2f}{s['edge_corr']:>11.3f}{s['psnr']:>9.2f}{s['cost']:>8.3f}")
    leak = ", ".join(f'{m} = {max(0.0, min(1.0, s["ssim"])):.3f}' for m, s in summary.items())
    cost = ", ".join(f'{m} = {s["cost"]:.3f}' for m, s in summary.items())
    print(f"\npaste into configs/default.toml:\n[defence.leakage]\n{leak.replace(', ', chr(10))}\n"
          f"[defence.cost]\n{cost.replace(', ', chr(10))}\n\nwritten {a.out}")


if __name__ == "__main__":
    main()
