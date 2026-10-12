"""Model-level preview of RQ1/RQ3: visual security, encryption space, size
overhead and a replacement attack for every mode. Final numbers must come from
the board, but the model is bit-exact with the RTL, so these are the same images.

    python scripts/visual_security.py                      # synthetic 256x192
    python scripts/visual_security.py --image photo.png --quality 75

Writes sim_out/visual/*.jpg and prints a table.
Replacement attack: the attacker knows which bits are encrypted and replaces
them with a fixed guess (every sign positive, every encrypted low amplitude
bit 0) hoping the result looks closer to the original than the ciphertext.
"""
import argparse
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from model import jpeg as J            # noqa: E402
from model.testimage import make_image, psnr   # noqa: E402


def replacement_attack(syms, mode):
    out = []
    for s in syms:
        n = J.bits_needed(s, mode)
        if n == 0:
            out.append(s)
            continue
        top = 1 << (s.size - 1)                    # MSB set = positive value
        low = (s.amp & (top - 1)) if n == 1 else 0  # sign only, or sign + amplitude
        out.append(s._replace(amp=top | low))
    return out


def ac_zeroing_attack(syms):
    """Keep every DC symbol, replace each block's AC symbols by one EOB.
    If DC is not encrypted (E1) this reveals a 1/8-resolution thumbnail."""
    out = []
    for s in syms:
        if s.is_dc:
            out.append(s)
            out.append(J.Sym(0, 0, 0, 0, 1, s.comp))
    return out


def decode(jpeg):
    return np.array(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    ap.add_argument("--quality", type=int, default=75)
    a = ap.parse_args()
    if a.image:
        img = np.array(Image.open(a.image).convert("RGB"))
        img = img[:img.shape[0] // 16 * 16, :img.shape[1] // 16 * 16]
    else:
        img = make_image(256, 192, "scene")
    h, w = img.shape[:2]
    out = ROOT / "sim_out" / "visual"
    out.mkdir(parents=True, exist_ok=True)
    key, wrong_key, sid = bytes(range(16)), bytes([1]) + bytes(range(1, 16)), 7
    plain = J.encode_frame(img, a.quality, 0, key, 1, sid)
    Image.fromarray(img).save(out / "original.png")
    print(f"{w}x{h}, quality {a.quality}, plain scan {len(plain['scan'])} bytes, "
          f"PSNR plain {psnr(decode(plain['jpeg']), img):.2f} dB\n")
    print(f"{'mode':<20}{'enc bits':>9}{'% of scan':>10}{'size +B':>9}"
          f"{'PSNR no key':>13}{'replacement':>13}{'AC-zeroing':>12}{'1-bit key':>11}")
    for mode in range(1, 5):
        e = J.encode_frame(img, a.quality, mode, key, 1, sid)
        scr = decode(e["jpeg"])
        att = replacement_attack(e["enc_symbols"], mode)
        att_jpg = J.headers(w, h, a.quality) + J.pack_bytes([J.huffman_bits(s) for s in att]) + b"\xFF\xD9"
        zero = ac_zeroing_attack(e["enc_symbols"])
        zero_jpg = J.headers(w, h, a.quality) + J.pack_bytes([J.huffman_bits(s) for s in zero]) + b"\xFF\xD9"
        (out / f"E{mode}_ac_zeroing_attack.jpg").write_bytes(zero_jpg)
        # decrypt with a key differing in one bit (ignoring the tag) -> key sensitivity
        n_enc = J.ascon.make_nonce(1, sid, 0)
        wk, _ = J.selective_encrypt(e["enc_symbols"], mode, wrong_key, n_enc)
        wk_jpg = J.headers(w, h, a.quality) + J.pack_bytes([J.huffman_bits(s) for s in wk]) + b"\xFF\xD9"
        (out / f"E{mode}_no_key.jpg").write_bytes(e["jpeg"])
        (out / f"E{mode}_replacement_attack.jpg").write_bytes(att_jpg)
        (out / f"E{mode}_wrong_key.jpg").write_bytes(wk_jpg)
        print(f"{J.MODE_NAMES[mode]:<20}{e['keystream_bits_used']:>9}"
              f"{100 * e['keystream_bits_used'] / (8 * len(e['scan'])):>9.1f}%"
              f"{len(e['scan']) - len(plain['scan']):>+9d}"
              f"{psnr(scr, img):>11.2f}dB{psnr(decode(att_jpg), img):>11.2f}dB"
              f"{psnr(decode(zero_jpg), img):>10.2f}dB"
              f"{psnr(decode(wk_jpg), img):>9.2f}dB")
    dc_only = ac_zeroing_attack(plain["symbols"])
    ref = J.headers(w, h, a.quality) + J.pack_bytes([J.huffman_bits(s) for s in dc_only]) + b"\xFF\xD9"
    print(f"\nreference: DC-only thumbnail of the clear image = {psnr(decode(ref), img):.2f} dB")
    print(f"images in {out.relative_to(ROOT)}/ (lower PSNR without the key = better hiding)")


if __name__ == "__main__":
    main()
