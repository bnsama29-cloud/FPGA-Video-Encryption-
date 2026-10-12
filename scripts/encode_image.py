"""Quick single-image check: plain JPEG, E1-E4 scrambled JPEGs, decrypted JPEGs.

    python scripts/encode_image.py photo.jpg --out out_image
    python scripts/encode_image.py --sample astronaut --out out_image
"""
import argparse
from pathlib import Path

import _common
import cv2
from skimage import data

from model.jpeg import analyse_frame, decode_pixels, package_frame, receive_frame
from model.metrics import psnr, ssim
from model.selective import MODES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?")
    ap.add_argument("--sample", default="astronaut", help="scikit-image sample if no image given")
    ap.add_argument("--out", default="out_image")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
    a = ap.parse_args()
    key = _common.parse_key(a.key)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    if a.image:
        bgr = cv2.imread(a.image)
        if bgr is None:
            raise SystemExit(f"cannot read {a.image}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    else:
        rgb = getattr(data, a.sample)()[..., :3]
    _common.save_rgb(out / "original.png", rgb)

    an = analyse_frame(rgb, a.quality)
    plain = package_frame(an)
    (out / "plain.jpg").write_bytes(plain.jpeg)
    pd = decode_pixels(plain.jpeg)
    print(f"image {an.width}x{an.height}, quality {a.quality}")
    print(f"plain JPEG: {len(plain.jpeg)} bytes, PSNR {psnr(rgb, pd):.2f} dB, SSIM {ssim(rgb, pd):.4f}")
    print(f"{'mode':4} {'bytes':>7} {'enc bits %':>10} {'noKey PSNR':>10} {'noKey SSIM':>10}  receiver")
    for i, mode in enumerate(MODES):
        if mode == "E0":
            continue
        enc = package_frame(an, key, session_id=0x5EC0 + i, frame_ctr=0, mode=mode)
        (out / f"scrambled_{mode}.jpg").write_bytes(enc.jpeg)
        nk = decode_pixels(enc.jpeg)
        r = receive_frame(enc.jpeg, key)
        (out / f"decrypted_{mode}.jpg").write_bytes(r.plain_jpeg)
        print(f"{mode:4} {len(enc.jpeg):7d} {100 * enc.enc_bits / enc.payload_bits:10.2f} "
              f"{psnr(rgb, nk):10.2f} {ssim(rgb, nk):10.4f}  tag {r.reason}, "
              f"bit-exact={r.plain_jpeg == plain.jpeg}")
    print(f"files written to {out}/  (open scrambled_*.jpg in any viewer)")


if __name__ == "__main__":
    main()
