"""SVE-Bench: one yardstick for format-compliant selective encryption of (M)JPEG video.

    python experiments/benchmark_suite.py                                   # synthetic scene, quick
    python experiments/benchmark_suite.py --video data/kodak --frames 12 --stride 1 --name kodak
    python experiments/benchmark_suite.py --video clip.mp4 --frames 20 --stride 30 --name clip

Every scheme below turns the same quantised frames into a JPEG that a normal viewer still decodes. Every
attacker below sees only what the network carries (Kerckhoffs: it knows the scheme, not the key), and
every one is scored the same way, so schemes from different papers become comparable.

SCHEMES (re-implemented from the papers in paper/refs.bib; randomness from our Ascon keystream, which only
helps them: the originals use AES-OFB, a 10-bit LFSR or unspecified generators)
  plain            standard JPEG (reference: what an unprotected camera leaks)
  E1 .. E4         ours, contract v2 (signs; + DC signs; + AC amplitudes; + DC amplitudes)
  E5 (v2)          ours, model reference: E4 + keyed MCU shuffle, one keystream per frame
  E5 (v3, hw)      ours, hardware form (docs/INTERFACES.md §8.6): one segment per MCU, keyed per frame
  VanDroogenbroeck appended bits of every AC coefficient XORed, DC in clear, one key for the stream [vandroogenbroeck2002]
  Kishore          8x8 blocks permuted within each component (DPCM before scrambling, so DC differences
                   travel with their block) + run/level symbols permuted inside each block; fixed seed [kishore2015]
  Auer             run/level pairs permuted inside each block + AC value bits toggled + blocks that share a
                   Huffman table permuted inside each MCU; file-dependent IV = per frame [auer2013]
  Hirose RI=r      restart-marker extended blocks of r MCUs permuted + additional bits XORed (we XOR all of
                   them, an upper bound on their byte-pattern subset); keys K1, K2 fixed [hirose2024]

ATTACKS (each gives the edge correlation of its picture or sketch with the original, 0 = nothing)
  A1 decode        the stream in a normal viewer
  A2 replacement   encrypted values replaced by fixed guesses (|v| for sign-only fields, the smallest value of the
                   size category for amplitude fields, DC difference 0), re-coded, decoded
  A3 NZCA          non-zero AC count per 8x8 luma block, as received (the sketch attack applied by Hirose et al.),
                   correlated with the original block edge energy
  A4 cross-frame   the permutation recovered on one frame (Li et al.'s chosen plaintext does it in one designed
                   frame; here: given) applied to every later frame, then A2 and A3. Schemes whose permutation
                   does not change per frame fall to this; per-frame permutations do not transfer.
Also reported: bytes vs plain JPEG, whether every output decodes (PIL and OpenCV), per-frame randomness,
frame authentication. Writes sim_out/benchmark_suite/<name>.json and .md.
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
sys.path.insert(0, str(ROOT / "experiments"))
from link.sources import open_source                                         # noqa: E402
from model import ascon, hw                                                  # noqa: E402
from model.container import build_jpeg, parse_jpeg                           # noqa: E402
from model.entropy import (COMP_OF_BLOCK, Symbol, huffman_decode, huffman_encode, join_restart,  # noqa: E402
                           run_length_encode, split_restart)
from model.jpeg import _shuffle_order, analyse_frame, package_frame         # noqa: E402
from model.selective import symbol_mask                                      # noqa: E402

KEY, SID = bytes(range(16)), 0x5EC0_BE7C


# ------------------------------------------------------------------ symbol helpers
def xor_fields(symbols, ks, ac_sign=False, ac_all=False, dc_sign=False, dc_all=False):
    """model/selective.py :: apply_keystream with an explicit field selection."""
    out = []
    for s in symbols:
        if s.size == 0:
            out.append(s)
            continue
        all_bits, sign = (dc_all, dc_sign) if s.is_dc else (ac_all, ac_sign)
        if all_bits:
            mask = symbol_mask(s.size, ks.take(s.size), True)
        elif sign:
            mask = symbol_mask(s.size, ks.take(1), False)
        else:
            out.append(s)
            continue
        a = s.amp
        b = (a if a >= 0 else a + (1 << s.size) - 1) ^ mask
        out.append(s._replace(amp=b if (b >> (s.size - 1)) else b - (1 << s.size) + 1))
    return out


def split_blocks(symbols):
    """Symbol list -> list of blocks (each starts with its DC symbol)."""
    blocks = []
    for s in symbols:
        if s.is_dc:
            blocks.append([s])
        else:
            blocks[-1].append(s)
    return blocks


def units(block):
    """AC part of a block -> units: zero or more ZRLs followed by one non-zero symbol (positions
    stay valid under any permutation of units), plus the EOB if present."""
    us, cur, eob = [], [], []
    for s in block[1:]:
        if s.eob:
            eob = [s]
        elif s.size == 0:
            cur.append(s)
        else:
            us.append(cur + [s])
            cur = []
    return us, eob


def keyed_perm(n, ks):
    order = list(range(n))
    for i in range(n - 1, 0, -1):
        bits = i.bit_length()
        while True:
            j = ks.take(bits)
            if j <= i:
                break
        order[i], order[j] = order[j], order[i]
    return order


def permute_units(block, ks):
    us, eob = units(block)
    if len(us) < 2:
        return block
    order = keyed_perm(len(us), ks)
    return [block[0]] + [s for i in order for s in us[i]] + eob


def jpeg_of(an, symbols, restart_interval=0, scan=None):
    if scan is None:
        scan, _ = huffman_encode(symbols)
    return build_jpeg(an.width, an.height, an.qy, an.qc, scan, restart_interval=restart_interval)


def stream_ks(tag, ctr=None):
    """Our Ascon keystream for a published scheme; ctr=None = the same stream for every frame (schemes
    without a nonce or IV), else one stream per frame."""
    return ascon.Keystream(KEY, ascon.make_nonce(0x0BE7C + tag, 0 if ctr is None else ctr + 1, 0))


# ------------------------------------------------------------------ schemes
# Each scheme: fn(an, ctr) -> (jpeg, perm), perm = what an attacker who recovered this frame's
# permutation knows (None = no permutation). Fields: what the replacement attack replaces.
def s_plain(an, ctr):
    return jpeg_of(an, an.symbols), None


def s_ours(mode, segmented=False):
    def fn(an, ctr):
        f = package_frame(an, KEY, SID, ctr, mode, segmented=segmented)
        perm = None
        if mode == "E5":
            perm = ("segments", hw.e5_order(KEY, SID, ctr, an.n_mcu) if segmented
                    else _shuffle_order(KEY, SID, ctr, an.n_mcu))
        return f.jpeg, perm
    return fn


def s_vandroogenbroeck(an, ctr):
    return jpeg_of(an, xor_fields(an.symbols, stream_ks(1), ac_all=True)), None


def s_kishore(an, ctr):
    ks = stream_ks(2)                                   # fixed seed: the same sequence for every frame
    blocks = split_blocks(an.symbols)
    by_comp = {c: [i for i in range(len(blocks)) if COMP_OF_BLOCK[i % 6] == c] for c in (0, 1, 2)}
    out = list(blocks)
    perm = {}
    for c, slots in by_comp.items():
        order = keyed_perm(len(slots), ks)
        perm[c] = order
        for k, i in enumerate(order):
            out[slots[k]] = blocks[slots[i]]            # DPCM before scrambling: the DC diff moves along
    out = [permute_units(b, ks) for b in out]
    return jpeg_of(an, [s for b in out for s in b]), ("blocks", perm)


def s_auer(an, ctr):
    ks = stream_ks(3, ctr)                              # file-dependent IV -> per frame
    blocks = [permute_units(b, ks) for b in split_blocks(an.symbols)]
    syms = xor_fields([s for b in blocks for s in b], ks, ac_all=True)
    blocks = split_blocks(syms)
    out, perm = [], []
    for m in range(an.n_mcu):
        mb = blocks[6 * m:6 * m + 6]
        oy = keyed_perm(4, ks)                          # Y0..Y3 share a table
        oc = keyed_perm(2, ks)                          # Cb, Cr share the chroma table
        perm.append((oy, oc))
        out += [mb[i] for i in oy] + [mb[4 + i] for i in oc]
    return jpeg_of(an, [s for b in out for s in b]), ("mcu_inner", perm)


def s_hirose(ri):
    def fn(an, ctr):
        segs, n = [], an.n_mcu
        ks1 = stream_ks(4)                              # K1 fixed
        for m0 in range(0, n, ri):
            sym = xor_fields(run_length_encode(an.quant[m0:m0 + ri]), ks1, ac_all=True, dc_all=True)
            segs.append(huffman_encode(sym)[0])
        order = keyed_perm(len(segs), stream_ks(5))     # K2 fixed: same permutation every frame
        scan = join_restart([segs[i] for i in order])
        return jpeg_of(an, None, restart_interval=ri, scan=scan), ("segments", order)
    return fn


SCHEMES = {
    "plain":            dict(fn=s_plain, fields={}, per_frame="-", auth=False, cite="-"),
    "E1":               dict(fn=s_ours("E1"), fields=dict(ac_sign=True), per_frame="yes", auth=True, cite="ours"),
    "E2":               dict(fn=s_ours("E2"), fields=dict(ac_sign=True, dc_sign=True), per_frame="yes", auth=True, cite="ours"),
    "E3":               dict(fn=s_ours("E3"), fields=dict(ac_all=True, dc_sign=True), per_frame="yes", auth=True, cite="ours"),
    "E4":               dict(fn=s_ours("E4"), fields=dict(ac_all=True, dc_all=True), per_frame="yes", auth=True, cite="ours"),
    "E5 (v2)":          dict(fn=s_ours("E5"), fields=dict(ac_all=True, dc_all=True), per_frame="yes", auth=True, cite="ours"),
    "E5 (v3, hw)":      dict(fn=s_ours("E5", True), fields=dict(ac_all=True, dc_all=True), per_frame="yes", auth=True, cite="ours"),
    "VanDroogenbroeck": dict(fn=s_vandroogenbroeck, fields=dict(ac_all=True), per_frame="no", auth=False, cite="vandroogenbroeck2002"),
    "Kishore":          dict(fn=s_kishore, fields={}, per_frame="no", auth=False, cite="kishore2015"),
    "Auer":             dict(fn=s_auer, fields=dict(ac_all=True), per_frame="yes", auth=False, cite="auer2013"),
    "Hirose RI=1":      dict(fn=s_hirose(1), fields=dict(ac_all=True, dc_all=True), per_frame="no", auth=False, cite="hirose2024"),
    "Hirose RI=4":      dict(fn=s_hirose(4), fields=dict(ac_all=True, dc_all=True), per_frame="no", auth=False, cite="hirose2024"),
}


# ------------------------------------------------------------------ attacker side
def received_segments(jpeg):
    """(width, height, qy, qc, restart interval, list of symbol lists per segment) from the bytes alone."""
    p = parse_jpeg(jpeg)
    dri = p.segment(0xDD)
    ri = int.from_bytes(dri[:2], "big") if dri else 0
    n_mcu = ((p.width + 15) // 16) * ((p.height + 15) // 16)
    qy, qc = p.qtables()
    if ri:
        segs = [huffman_decode(s, min(ri, n_mcu - k * ri)) for k, s in enumerate(split_restart(p.scan))]
    else:
        segs = [huffman_decode(p.scan, n_mcu)]
    return p.width, p.height, qy, qc, ri, segs


def rebuild(w, h, qy, qc, ri, segs):
    scan = join_restart([huffman_encode(s)[0] for s in segs]) if ri else huffman_encode(segs[0])[0]
    return build_jpeg(w, h, qy, qc, scan, restart_interval=ri)


def replace_fields(symbols, ac_sign=False, ac_all=False, dc_sign=False, dc_all=False):
    out = []
    for s in symbols:
        if s.size == 0:
            out.append(s)
        elif s.is_dc and (dc_sign or dc_all):
            out.append(Symbol(1, 0, 0, 0, 0, s.comp))
        elif not s.is_dc and ac_all:
            out.append(s._replace(amp=1 << (s.size - 1)))
        elif not s.is_dc and ac_sign:
            out.append(s._replace(amp=abs(s.amp)))
        else:
            out.append(s)
    return out


def undo_permutation(w, h, ri, segs, perm):
    """Apply the inverse of a (possibly stale) permutation to what was received."""
    kind, p = perm
    if kind == "segments":
        nat = [None] * len(segs)
        for pos, i in enumerate(p):
            nat[i] = segs[pos]
        return nat
    syms = [s for seg in segs for s in seg]
    blocks = split_blocks(syms)
    if kind == "blocks":
        out = list(blocks)
        for c, order in p.items():
            slots = [i for i in range(len(blocks)) if COMP_OF_BLOCK[i % 6] == c]
            for k, i in enumerate(order):
                out[slots[i]] = blocks[slots[k]]
        return [[s for b in out for s in b]]
    if kind == "mcu_inner":
        out = []
        for m, (oy, oc) in enumerate(p):
            mb = blocks[6 * m:6 * m + 6]
            y, c = [None] * 4, [None] * 2
            for k, i in enumerate(oy):
                y[i] = mb[k]
            for k, i in enumerate(oc):
                c[i] = mb[4 + k]
            out += y + c
        return [[s for b in out for s in b]]
    raise ValueError(kind)


def nz_map(w, segs, ri):
    """Non-zero AC count per 8x8 luma block, at the position where the block is received."""
    cols = (w + 15) // 16
    syms = [s for seg in segs for s in seg]
    counts, cur = [], -1
    for s in syms:
        if s.is_dc:
            counts.append(0)
        elif s.size and not s.eob:
            counts[-1] += 1
    n_mcu = len(counts) // 6
    rows = n_mcu // cols
    out = np.zeros((rows * 2, cols * 2))
    for m in range(n_mcu):
        r, c = divmod(m, cols)
        for b in range(4):
            out[r * 2 + b // 2, c * 2 + b % 2] = counts[6 * m + b]
    return out


def luma(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float64)


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def edge_corr(y0, img):
    g = lambda y: np.hypot(cv2.Sobel(y, cv2.CV_64F, 1, 0), cv2.Sobel(y, cv2.CV_64F, 0, 1)).ravel()
    a, b = g(y0), g(luma(img))
    return float(np.corrcoef(a, b)[0, 1]) if a.std() and b.std() else 0.0


def block_energy(y0, shape):
    g = np.hypot(cv2.Sobel(y0, cv2.CV_64F, 1, 0), cv2.Sobel(y0, cv2.CV_64F, 0, 1))
    r, c = shape
    return g[:r * 8, :c * 8].reshape(r, 8, c, 8).mean(axis=(1, 3))


def corr(a, b):
    a, b = np.ravel(a), np.ravel(b)
    return float(np.corrcoef(a, b)[0, 1]) if a.std() and b.std() else 0.0


def views(jpeg, fields, y0, energy, perm0=None):
    """The four attacks on one received frame. perm0 = the permutation recovered on an earlier frame."""
    w, h, qy, qc, ri, segs = received_segments(jpeg)
    a1 = edge_corr(y0, decode(jpeg))
    repl = rebuild(w, h, qy, qc, ri, [replace_fields(s, **fields) for s in segs])
    a2 = edge_corr(y0, decode(repl))
    a3 = corr(nz_map(w, segs, ri), energy)
    a4 = None
    if perm0 is not None:
        nat = undo_permutation(w, h, ri, segs, perm0)
        ri2 = ri if perm0[0] == "segments" else 0
        rep2 = rebuild(w, h, qy, qc, ri2, [replace_fields(s, **fields) for s in nat])
        a4 = max(edge_corr(y0, decode(rep2)), corr(nz_map(w, nat, ri2), energy))
    return dict(decode=a1, replacement=a2, nzca=a3, cross_frame=a4,
                ssim_decode=float(max(0.0, structural_similarity(y0, luma(decode(jpeg)), data_range=255))))


def compliant(jpeg):
    try:
        a = decode(jpeg)
        b = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        return a is not None and b is not None and a.shape[:2] == b.shape[:2]
    except Exception:
        return False


def frames_of(a):
    w, h = map(int, a.size.split("x"))
    src = open_source(a.video, w, h, loop=False)
    out = []
    for i in range(a.frames * a.stride):
        f = src.read()
        if f is None:
            break
        if i % a.stride == 0:
            out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=6, help="frames; the first is the one whose permutation leaks")
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--schemes", nargs="+", default=list(SCHEMES))
    ap.add_argument("--name", default="synthetic")
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "benchmark_suite"))
    a = ap.parse_args()
    frames = frames_of(a)
    if len(frames) < 2:
        raise SystemExit("need at least 2 frames")
    ans = [analyse_frame(f) for f in frames]
    y0s = [luma(f) for f in frames]
    plain_bytes = [len(jpeg_of(an, an.symbols)) for an in ans]
    energies = [block_energy(y, (an.height // 8, an.width // 8)) for y, an in zip(y0s, ans)]
    rows = {}
    for name in a.schemes:
        sc = SCHEMES[name]
        out = [sc["fn"](an, ctr) for ctr, an in enumerate(ans)]
        perm0 = out[0][1]
        per = [views(j, sc["fields"], y0s[t], energies[t], perm0) for t, (j, _) in enumerate(out) if t > 0]
        mean = lambda k: float(np.mean([p[k] for p in per])) if per[0][k] is not None else None
        r = dict(cite=sc["cite"], per_frame=sc["per_frame"], authenticated=sc["auth"],
                 bytes_vs_plain=float(np.mean([len(j) / b - 1 for (j, _), b in zip(out, plain_bytes)])),
                 compliant=all(compliant(j) for j, _ in out),
                 **{k: mean(k) for k in ("decode", "replacement", "nzca", "cross_frame", "ssim_decode")})
        r["max_leak"] = max(v for v in (r["decode"], r["replacement"], r["nzca"], r["cross_frame"]) if v is not None)
        rows[name] = r
        print(f"{name:18s} bytes {r['bytes_vs_plain']:+.1%}  decode {r['decode']:.2f}  repl {r['replacement']:.2f}  "
              f"nzca {r['nzca']:.2f}  cross {('%.2f' % r['cross_frame']) if r['cross_frame'] is not None else '  - '}  "
              f"-> max {r['max_leak']:.2f}" + ("" if r["compliant"] else "  NOT COMPLIANT"), flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(source=a.video, frames=len(frames), scored_frames=len(frames) - 1, size=a.size,
                note="edge correlation with the original luma (0 = nothing); max_leak = the best attack")
    (out / f"{a.name}.json").write_text(json.dumps(dict(meta=meta, schemes=rows), indent=1))
    f = lambda v: "-" if v is None else f"{v:.2f}"
    lines = [f"# SVE-Bench ({a.name}, {a.size}, {len(frames) - 1} scored frames)", "",
             "| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | A4 cross-frame | **Max leak** |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in rows.items():
        lines.append(f"| {name} | {r['cite']} | {r['per_frame']} | {'yes' if r['authenticated'] else 'no'} | "
                     f"{r['bytes_vs_plain']:+.1%} | {'yes' if r['compliant'] else 'NO'} | {f(r['decode'])} | "
                     f"{f(r['replacement'])} | {f(r['nzca'])} | {f(r['cross_frame'])} | **{f(r['max_leak'])}** |")
    (out / f"{a.name}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
