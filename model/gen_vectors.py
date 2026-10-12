"""Write each pipeline stage's golden output to vectors/ (walkthrough step 3).

Usage:  python -m model.gen_vectors [--width 64 --height 64 --kind scene
                                     --quality 75 --mode 2]

Creates vectors/<name>/ with:
  pixels.txt      one pixel per line: R G B
  blocks.txt      one block per line: comp s0..s63          (converter output)
  coeffs.txt      one block per line: comp F0..F63          (DCT output)
  qcoeffs.txt     one block per line: comp q0..q63          (quantiser output)
  symbols.txt     one symbol per line: is_dc run size amp eob comp
  enc_symbols.txt same, after selective encryption
  scan.bin        scan bytes (after stuffing); tag.hex; frame.jpg
  config.txt      key, nonce words, quality, mode, register values
and vectors/dct_quant_vectors.txt for the HLS C testbench.
These files are what you feed to XSim / Vitis HLS testbenches, or diff against
when something fails on the board.
"""
import argparse
import os

import numpy as np

from . import hw as J, ascon
from .testimage import make_image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def write_lines(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(" ".join(str(v) for v in r) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=64)
    ap.add_argument("--height", type=int, default=64)
    ap.add_argument("--kind", default="scene")
    ap.add_argument("--image", help="use a real image file instead (cropped to x16)")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--mode", type=int, default=2)
    ap.add_argument("--frame-ctr", type=int, default=1)
    ap.add_argument("--session-id", type=lambda s: int(s, 0), default=0x1234ABCD)
    ap.add_argument("--key", default="000102030405060708090a0b0c0d0e0f")
    a = ap.parse_args()

    if a.image:
        from PIL import Image
        img = np.array(Image.open(a.image).convert("RGB"))
        img = img[:img.shape[0] // 16 * 16, :img.shape[1] // 16 * 16]
        name = os.path.splitext(os.path.basename(a.image))[0]
    else:
        img = make_image(a.width, a.height, a.kind)
        name = f"{a.kind}_{a.width}x{a.height}"
    name += f"_q{a.quality}_m{a.mode}"
    key = bytes.fromhex(a.key)
    e = J.encode_frame(img, a.quality, a.mode, key, a.frame_ctr, a.session_id)
    out = os.path.join(ROOT, "vectors", name)
    os.makedirs(out, exist_ok=True)

    write_lines(os.path.join(out, "pixels.txt"), [p[:3] for row in img for p in row])
    write_lines(os.path.join(out, "blocks.txt"), [[c] + s for c, s in e["blocks"]])
    comps = [c for c, _ in e["blocks"]]
    write_lines(os.path.join(out, "coeffs.txt"), [[c] + f for c, f in zip(comps, e["coeffs"])])
    write_lines(os.path.join(out, "qcoeffs.txt"), [[c] + q for c, q in zip(comps, e["qcoeffs"])])
    write_lines(os.path.join(out, "symbols.txt"), [list(s) for s in e["symbols"]])
    write_lines(os.path.join(out, "enc_symbols.txt"), [list(s) for s in e["enc_symbols"]])
    with open(os.path.join(out, "scan.bin"), "wb") as f:
        f.write(e["scan"])
    with open(os.path.join(out, "tag.hex"), "w") as f:
        f.write(e["tag"].hex() + "\n")
    with open(os.path.join(out, "frame.jpg"), "wb") as f:
        f.write(e["jpeg"])
    kw = [int.from_bytes(key[4 * i:4 * i + 4], "little") for i in range(4)]
    with open(os.path.join(out, "config.txt"), "w") as f:
        f.write(f"WIDTH 0x{img.shape[1]:x}\nHEIGHT 0x{img.shape[0]:x}\n"
                f"FRAME_CTR 0x{a.frame_ctr:x}\nSESSION_ID 0x{a.session_id:x}\n"
                + "".join(f"KEY{i} 0x{w:08x}\n" for i, w in enumerate(kw))
                + f"CTRL 0x{1 | (a.mode << 1):x}\nQUALITY {a.quality}\n"
                f"N_ENC {ascon.make_nonce(a.session_id, a.frame_ctr, 0).hex()}\n"
                f"N_MAC {ascon.make_nonce(a.session_id, a.frame_ctr, 1).hex()}\n"
                f"OUT_BYTES {len(e['scan'])}\nKEYSTREAM_BITS {e['keystream_bits_used']}\n")

    # HLS testbench vectors: reciprocals, then one block per line
    with open(os.path.join(ROOT, "vectors", "dct_quant_vectors.txt"), "w") as f:
        f.write("RECIP " + " ".join(map(str, e["recips"][0] + e["recips"][1])) + "\n")
        for (c, s), q in zip(e["blocks"], e["qcoeffs"]):
            f.write(f"BLOCK {c} " + " ".join(map(str, s)) + " Q " + " ".join(map(str, q)) + "\n")
    print(f"wrote vectors/{name}/ ({len(e['blocks'])} blocks, {len(e['symbols'])} symbols, "
          f"{len(e['scan'])} scan bytes) and vectors/dct_quant_vectors.txt")


if __name__ == "__main__":
    main()
