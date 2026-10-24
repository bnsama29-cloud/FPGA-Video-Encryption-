"""The standard image-encryption metrics, per protection level.

    python experiments/standard_metrics.py                                   # synthetic scene
    python experiments/standard_metrics.py --video data/kodak --frames 24 --stride 1 --size 768x512 --name kodak
    python experiments/standard_metrics.py --quality 50 75 90                # quality sweep

Image-encryption papers report these numbers almost always, so reviewers ask for them. They were
designed for schemes that scramble every pixel; a format-compliant selective scheme is SUPPOSED to
keep the stream decodable and part of its structure, so read them next to the attack results:

  key space            128 bits in every level (the E5 permutation is derived from the key, so it adds
                       no key bits; its log2(#segments!) is reported separately as the permutation space
                       a key-ignoring attacker would have to search)
  key sensitivity      decrypt with the key with one bit flipped: SSIM to the original and share of
                       pixels that differ from the correct decryption (correct key: bit-exact, checked)
  NPCR / UACI (key)    between the no-key pictures of the same frame under two keys one bit apart
  NPCR / UACI (plain)  between the no-key pictures of two frames that differ in ONE pixel (inverted, so the
                       change survives quantisation), same key and nonce. There is no diffusion step, but
                       keystream bits are consumed per selected field: if the change alters a coefficient's
                       size, every later field gets different keystream bits, so the rest of the frame
                       changes too. (In the protocol a nonce is never reused, so two real frames never
                       share a keystream anyway.)
  entropy              Shannon entropy of the luma histogram of the no-key picture (8 = flat)
  adjacent correlation horizontal / vertical / diagonal, 2000 random pixel pairs, luma
  PSNR / SSIM          luma of the no-key picture against the original frame
Levels: E1-E5 in contract v2 (the model reference) and "E5 (v3, hw)", E5 as the hardware lane encoder
produces it (docs/INTERFACES.md §8.6: one restart segment per MCU, each with its own keystream).
Each mean has a 95 % percentile-bootstrap interval over frames in the json (ci).
Writes sim_out/standard_metrics/<name>.json (quality 75) and <name>_q<Q>.json (other qualities) / .md.
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
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.sources import open_source                                         # noqa: E402
from model import ascon                                                      # noqa: E402
from model.container import build_jpeg, parse_jpeg                           # noqa: E402
from model.entropy import (huffman_decode, huffman_encode, run_length_encode,  # noqa: E402
                           split_restart, symbols_to_blocks)
from model.dct_quant import DEFAULT_QUALITY                                  # noqa: E402
from model.jpeg import (_shuffle_order, analyse_frame, package_frame, receive_frame,  # noqa: E402
                        segment_key, segment_mcus, unpermute_segments)
from model.selective import MODE_NAME, MODES, apply_keystream               # noqa: E402

KEY = bytes(range(16))
OUT = ROOT / "sim_out" / "standard_metrics"
RNG = np.random.default_rng(12345)


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def luma(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def flip_bit(key, bit=0):
    k = bytearray(key)
    k[bit // 8] ^= 1 << (bit % 8)
    return bytes(k)


def decrypt_ignoring_tag(jpeg, key):
    """What the receiver would decode with `key` if it skipped the tag check (for key sensitivity
    only -- the real receiver rejects a wrong key at the tag). Same steps as model.jpeg.receive_frame."""
    p = parse_jpeg(jpeg)
    meta, mode_id, sid, ctr, _ = p.secure()
    mode = MODE_NAME[mode_id]
    n_mcu = ((p.width + 15) // 16) * ((p.height + 15) // 16)
    qy, qc = p.qtables()
    if meta[4] == 3:                       # contract v3: same steps as model.jpeg._receive_segmented
        per = segment_mcus(p.width, mode)
        scan = unpermute_segments(p.scan, _shuffle_order(key, sid, ctr, n_mcu)) if MODES[mode].shuffle else p.scan
        kseg = segment_key(key, sid, ctr)
        blocks = []
        for s, seg in enumerate(split_restart(scan)):
            sym = huffman_decode(seg, per)
            if mode != "E0":
                sym, _ = apply_keystream(sym, ascon.Keystream(kseg, ascon.make_nonce(s, ctr, 0)), mode)
            blocks.append(symbols_to_blocks(sym, per))
        return build_jpeg(p.width, p.height, qy, qc, huffman_encode(run_length_encode(np.concatenate(blocks)))[0])
    if MODES[mode].shuffle:
        segs = split_restart(p.scan)
        order = _shuffle_order(key, sid, ctr, n_mcu)
        natural = [None] * n_mcu
        for pos, i in enumerate(order):
            natural[i] = segs[pos]
        symbols = [s for seg in natural for s in huffman_decode(seg, 1)]
    else:
        symbols = huffman_decode(p.scan, n_mcu)
    if mode != "E0":
        symbols, _ = apply_keystream(symbols, ascon.Keystream(key, ascon.make_nonce(sid, ctr, 0)), mode)
    if MODES[mode].shuffle:
        symbols = run_length_encode(symbols_to_blocks(symbols, n_mcu, restart=True))
    return build_jpeg(p.width, p.height, qy, qc, huffman_encode(symbols)[0])


def npcr_uaci(a, b):
    a, b = a.astype(np.int16), b.astype(np.int16)
    return 100 * float(np.mean(a != b)), 100 * float(np.mean(np.abs(a - b)) / 255)


def entropy(rgb):
    h = np.bincount(luma(rgb).ravel(), minlength=256).astype(np.float64)
    p = h[h > 0] / h.sum()
    return float(-(p * np.log2(p)).sum())


def adjacent_corr(rgb, n=2000):
    y = luma(rgb).astype(np.float64)
    H, W = y.shape
    out = {}
    for name, (dy, dx) in (("h", (0, 1)), ("v", (1, 0)), ("d", (1, 1))):
        r = RNG.integers(0, H - dy, n)
        c = RNG.integers(0, W - dx, n)
        a, b = y[r, c], y[r + dy, c + dx]
        out[name] = float(np.corrcoef(a, b)[0, 1]) if a.std() and b.std() else 0.0
    return out


LEVELS = (("E1", "E1", False), ("E2", "E2", False), ("E3", "E3", False), ("E4", "E4", False),
          ("E5", "E5", False), ("E5 (v3, hw)", "E5", True))


def psnr(rgb, img):
    mse = float(np.mean((luma(rgb).astype(np.float64) - luma(img).astype(np.float64)) ** 2))
    return 99.0 if mse == 0 else 10 * math.log10(255 ** 2 / mse)


def measure(rgb, ctr, quality=DEFAULT_QUALITY):
    an = analyse_frame(rgb, quality)
    plain = decode(package_frame(an).jpeg)
    k2 = flip_bit(KEY, 0)
    rgb2 = rgb.copy()
    y, x = rgb.shape[0] // 2, rgb.shape[1] // 2
    rgb2[y, x] = 255 - rgb2[y, x]          # one pixel inverted (a 1-level change vanishes in quantisation)
    an2 = analyse_frame(rgb2, quality)
    res = {"plain JPEG": dict(entropy=entropy(plain), **{f"corr_{k}": v for k, v in adjacent_corr(plain).items()},
                              psnr=psnr(rgb, plain), ssim=float(structural_similarity(luma(rgb), luma(plain), data_range=255)))}
    n_mcu = ((rgb.shape[1] + 15) // 16) * ((rgb.shape[0] + 15) // 16)
    for label, m, seg in LEVELS:
        c1 = package_frame(an, KEY, 7, ctr, m, segmented=seg).jpeg
        c2 = package_frame(an, k2, 7, ctr, m, segmented=seg).jpeg
        c3 = package_frame(an2, KEY, 7, ctr, m, segmented=seg).jpeg
        v1 = decode(c1)
        ok = receive_frame(c1, KEY)
        assert ok.ok and decode(ok.plain_jpeg).tobytes() == plain.tobytes(), "correct key must be bit-exact"
        assert decrypt_ignoring_tag(c1, KEY) == ok.plain_jpeg, "decrypt_ignoring_tag must match the receiver"
        wrong = decode(decrypt_ignoring_tag(c1, k2))
        npcr_k, uaci_k = npcr_uaci(v1, decode(c2))
        npcr_p, uaci_p = npcr_uaci(v1, decode(c3))
        res[label] = dict(
            key_bits=128,
            perm_bits=math.lgamma(n_mcu + 1) / math.log(2) if MODES[m].shuffle else 0.0,
            wrong_key_ssim=float(structural_similarity(luma(rgb), luma(wrong), data_range=255)),
            wrong_key_differ_pct=100 * float(np.mean(wrong != plain)),
            npcr_key=npcr_k, uaci_key=uaci_k, npcr_plain=npcr_p, uaci_plain=uaci_p,
            entropy=entropy(v1), **{f"corr_{k}": v for k, v in adjacent_corr(v1).items()},
            psnr=psnr(rgb, v1), ssim=float(structural_similarity(luma(rgb), luma(v1), data_range=255)))
    return res


def bootstrap_ci(values, n=2000, seed=0):
    """95 % percentile-bootstrap interval of the mean (same as experiments/learned_attack.py)."""
    v = np.asarray(values, dtype=np.float64)
    if len(v) < 2:
        return [float(v.mean()), float(v.mean())]
    means = v[np.random.default_rng(seed).integers(0, len(v), (n, len(v)))].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic", help="video file, image folder or 'synthetic'")
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--stride", type=int, default=30)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--quality", type=int, nargs="+", default=[DEFAULT_QUALITY],
                    help="JPEG quality factors; more than one runs a sweep (e.g. 50 75 90)")
    ap.add_argument("--name")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    src = open_source(a.video, w, h, loop=False)
    frames = []
    for i in range(a.frames):
        for _ in range(a.stride - 1):
            if src.read() is None:
                break
        rgb = src.read()
        if rgb is None:
            break
        if rgb.std() >= 2:
            frames.append((i + 1, rgb))
    if not frames:
        raise SystemExit("no usable frames")
    name = a.name or ("synthetic" if a.video == "synthetic" else Path(str(a.video).rstrip("/")).stem.strip())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for q in a.quality:
        per = []
        for ctr, rgb in frames:
            per.append(measure(rgb, ctr, q))
            print(f"q{q} frame {ctr}: " + "  ".join(f"{m} NPCRk {r['npcr_key']:.1f}" for m, r in per[-1].items()
                                                  if m != "plain JPEG"), flush=True)
        summ = {m: {k: statistics.mean(f[m][k] for f in per) for k in per[0][m]} for m in per[0]}
        ci = {m: {k: bootstrap_ci([f[m][k] for f in per]) for k in per[0][m]} for m in per[0]}
        tag = name if q == DEFAULT_QUALITY else f"{name}_q{q}"   # the default quality keeps the plain name; a sweep adds _q<Q> files
        (out / f"{tag}.json").write_text(json.dumps(dict(source=str(a.video), size=a.size, quality=q, frames=len(per),
                                                         summary=summ, ci=ci), indent=1))
        g = lambda m, k, nd=2: f"{summ[m][k]:.{nd}f}" if k in summ[m] else "–"
        md = [f"Source: {a.video}, {len(per)} frames, {a.size}, quality {q} (means over frames; 95 % CIs in the json)", "",
              "| Level | Key (bits) | Permutation space (bits) | Wrong key: SSIM / % px differ | NPCR / UACI key (%) | "
              "NPCR / UACI 1-pixel (%) | Entropy | Corr. h / v / d | No-key PSNR (dB) / SSIM |",
              "|---|---|---|---|---|---|---|---|---|"]
        for m in summ:
            md.append(f"| {m} | {g(m, 'key_bits', 0)} | {g(m, 'perm_bits', 0)} | {g(m, 'wrong_key_ssim')} / {g(m, 'wrong_key_differ_pct', 1)} | "
                      f"{g(m, 'npcr_key', 1)} / {g(m, 'uaci_key', 1)} | {g(m, 'npcr_plain', 2)} / {g(m, 'uaci_plain', 2)} | "
                      f"{g(m, 'entropy', 3)} | {g(m, 'corr_h')} / {g(m, 'corr_v')} / {g(m, 'corr_d')} | {g(m, 'psnr', 1)} / {g(m, 'ssim')} |")
        (out / f"{tag}.md").write_text("\n".join(md) + "\n")
        print("\n" + "\n".join(md) + f"\n\nwritten {out}/{tag}.json / .md")


if __name__ == "__main__":
    main()
