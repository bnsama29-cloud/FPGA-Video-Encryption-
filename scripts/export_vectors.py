"""Export every pipeline stage as test vectors for the RTL/HLS testbenches.

    python scripts/export_vectors.py --sample astronaut --size 64x64 --out vectors/astro64
    python scripts/export_vectors.py --image my.png --size 640x480 --out vectors/my640
    python scripts/export_vectors.py --video clip.mp4 --frame 10 --size 64x64 --out vectors/clip64

Files (one value per line, hex, readable by $readmemh, cocotb or numpy):
    config.json              size, quality, key, session, counter, nonces, tag per mode
    pixels.hex               32-bit words {pad, B, G, R}: R in bits [7:0] (DDR byte order R,G,B,pad)
    blocks.hex               8-bit samples, 64 per block row-major, blocks Y0 Y1 Y2 Y3 Cb Cr per MCU
    coeffs.hex               16-bit two's complement DCT output, 64 per block row-major
    quant.hex                16-bit two's complement quantiser output, row-major
    qtable_luma.hex / qtable_chroma.hex   8-bit, row-major
    dct_matrix.hex           16-bit two's complement T_INT (8x8) for the HLS ROM
    symbols_plain.hex        23-bit packed symbols (format below), coding order
    symbols_<mode>.hex       same, after selective encryption
    symbols_*.csv            human-readable version
    keystream.hex            first keystream bytes for N_enc (one byte per line)
    scan_plain.hex           stuffed scan bytes from the plain encoder
    scan_<mode>.hex          stuffed scan bytes after in-encoder encryption
    frame_<mode>.jpg / plain.jpg   complete JPEG files for viewing
    stages.npz               all stage arrays (np.load) for Python/cocotb testbenches

Packed symbol word (MSB first, 23 bits):
    [22] is_dc  [21:18] run  [17:14] size  [13:3] amplitude (11-bit two's complement)
    [2] eob  [1:0] comp
"""
import argparse
import json
from pathlib import Path

import _common
import cv2
import numpy as np
from skimage import data

from model import ascon
from model.dct_quant import T_INT
from model.jpeg import analyse_frame, package_frame
from model.selective import MODE_ID, MODES


def write_hex(path, values, bits):
    mask = (1 << bits) - 1
    digits = (bits + 3) // 4
    with open(path, "w") as f:
        for v in np.asarray(values).ravel().tolist():
            f.write(f"{int(v) & mask:0{digits}x}\n")


def pack_symbol(s):
    return ((s.is_dc << 22) | (s.run << 18) | (s.size << 14) | ((s.amp & 0x7FF) << 3) |
            (s.eob << 2) | s.comp)


def write_symbols(out, name, symbols):
    write_hex(out / f"symbols_{name}.hex", [pack_symbol(s) for s in symbols], 23)
    with open(out / f"symbols_{name}.csv", "w") as f:
        f.write("index,is_dc,run,size,amp,eob,comp\n")
        for i, s in enumerate(symbols):
            f.write(f"{i},{s.is_dc},{s.run},{s.size},{s.amp},{s.eob},{s.comp}\n")


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--image")
    src.add_argument("--video")
    src.add_argument("--sample", default="astronaut")
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--size", default="64x64")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
    ap.add_argument("--session", type=lambda s: int(s, 0), default=0x1234)
    ap.add_argument("--ctr", type=int, default=0)
    ap.add_argument("--keystream-bytes", type=int, default=1024)
    ap.add_argument("--out", default="vectors/frame")
    a = ap.parse_args()
    key = _common.parse_key(a.key)
    size = _common.parse_size(a.size)

    if a.image:
        rgb = cv2.cvtColor(cv2.imread(a.image), cv2.COLOR_BGR2RGB)
    elif a.video:
        rgb = next(f for i, f in _common.read_frames(a.video, None, start=a.frame, max_frames=1))
    else:
        rgb = getattr(data, a.sample)()[..., :3]
    if size:
        rgb = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    an = analyse_frame(rgb, a.quality, keep_stages=True)
    st = an.stages
    px = st["rgb_padded"].astype(np.uint32)
    write_hex(out / "pixels.hex", px[..., 0] | (px[..., 1] << 8) | (px[..., 2] << 16), 32)
    write_hex(out / "blocks.hex", st["blocks"], 8)
    write_hex(out / "coeffs.hex", st["coeffs"], 16)
    write_hex(out / "quant.hex", st["quant"], 16)
    write_hex(out / "qtable_luma.hex", an.qy, 8)
    write_hex(out / "qtable_chroma.hex", an.qc, 8)
    write_hex(out / "dct_matrix.hex", T_INT, 16)
    np.savez(out / "stages.npz", **st)          # same data for Python testbenches
    write_symbols(out, "plain", an.symbols)

    plain = package_frame(an)
    write_hex(out / "scan_plain.hex", np.frombuffer(plain.scan, np.uint8), 8)
    (out / "plain.jpg").write_bytes(plain.jpeg)
    ks = ascon.Keystream(key, ascon.make_nonce(a.session, a.ctr, 0))
    write_hex(out / "keystream.hex",
              np.frombuffer(ks.bits(8 * a.keystream_bytes).to_bytes(a.keystream_bytes, "big"), np.uint8), 8)

    cfg = dict(width=an.width, height=an.height, padded=list(st["rgb_padded"].shape[:2][::-1]),
               n_mcu=an.n_mcu, n_blocks=an.n_mcu * 6, quality=a.quality, key=key.hex(),
               session_id=a.session, frame_ctr=a.ctr,
               nonce_enc=ascon.make_nonce(a.session, a.ctr, 0).hex(),
               nonce_mac=ascon.make_nonce(a.session, a.ctr, 1).hex(),
               plain_scan_bytes=len(plain.scan), plain_payload_bits=plain.payload_bits, modes={})
    for mode in MODES:
        enc = package_frame(an, key, a.session, a.ctr, mode)
        write_symbols(out, mode, enc.symbols)
        write_hex(out / f"scan_{mode}.hex", np.frombuffer(enc.scan, np.uint8), 8)
        (out / f"frame_{mode}.jpg").write_bytes(enc.jpeg)
        cfg["modes"][mode] = dict(mode_id=MODE_ID[mode], scan_bytes=len(enc.scan),
                                  encrypted_bits=enc.enc_bits, tag=enc.tag.hex())
    (out / "config.json").write_text(json.dumps(cfg, indent=2))
    print(f"vectors for {an.width}x{an.height} ({an.n_mcu} MCUs, {len(an.symbols)} symbols) -> {out}/")


if __name__ == "__main__":
    main()
