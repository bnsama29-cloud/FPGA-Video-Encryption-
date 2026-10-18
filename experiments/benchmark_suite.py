"""SVE-Bench: one yardstick for format-compliant selective encryption of (M)JPEG video.

    python experiments/benchmark_suite.py                                   # synthetic scene, quick
    python experiments/benchmark_suite.py --video data/kodak --frames 24 --stride 1 --size 768x512 --name kodak
    python experiments/benchmark_suite.py --video clip.mp4 --frames 20 --stride 30 --quality 50 75 90 --name clip

Every scheme below turns the same quantised frames into a JPEG that a normal viewer still decodes. Every
attacker below sees only what the network carries (Kerckhoffs: it knows the scheme, not the key), and
every one is scored the same way, so schemes from different papers become comparable. The method, and which
published paper reports which number, is in docs/BENCHMARK_METHOD.md.

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
  A4 known plain.  the attacker knows one frame in clear and its ciphertext (the loaded frame with the most
                   detail, so a black opening frame does not hide the attack) (one leaked or designed frame, as in
                   Li et al.'s chosen-plaintext attack on block shuffling [li2025shuffle]). From that pair alone it
                   (a) recovers the permutation by matching each received segment / block to a clear one with the
                   same structure (run/size pattern, plus clear amplitudes), and (b) recovers the keystream bits by
                   XORing clear and received fields. It applies both to every later frame (decrypt with the
                   recovered bits, or replacement after undoing the permutation, or NZCA, whichever leaks most).
                   Schemes whose key material does not change per frame fall to this; per-frame keys do not transfer.
                   Also reported: the share of the known frame's permutation recovered exactly.

METRICS THAT PAPERS REPORT (computed on the no-key picture, A1, so the numbers line up with the papers)
  PSNR / SSIM      luma of the no-key picture vs the original frame (Hirose et al., Kishore, Auer report PSNR)
  entropy          Shannon entropy of the luma histogram (8 = flat)
  adjacent corr.   horizontal / vertical / diagonal, all neighbour pairs of the luma
  NPCR / UACI key  between the no-key pictures of the same frame under two keys one bit apart
  NPCR / UACI px   between the no-key pictures of two frames that differ in one pixel, same key and counter
Every mean comes with a 95 % percentile-bootstrap interval over the scored frames (all but the known one).
Also reported: bytes vs plain JPEG, whether every output decodes (PIL and OpenCV), per-frame randomness,
frame authentication. Writes sim_out/benchmark_suite/<name>.json (quality 75) and <name>_q<Q>.json (other qualities) and .md.
"""
import argparse
import io
import json
import sys
from collections import defaultdict, deque
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
from model.dct_quant import DEFAULT_QUALITY                                  # noqa: E402
from model.jpeg import _shuffle_order, analyse_frame, package_frame         # noqa: E402
from model.selective import symbol_mask                                      # noqa: E402

KEY, SID = bytes(range(16)), 0x5EC0_BE7C
KEY2 = bytes([KEY[0] ^ 1]) + KEY[1:]          # the same key with one bit flipped (key sensitivity)


# ------------------------------------------------------------------ symbol helpers
def selected(s, ac_sign=False, ac_all=False, dc_sign=False, dc_all=False):
    """(all bits, sign only) for one symbol under a field selection."""
    return (dc_all, dc_sign) if s.is_dc else (ac_all, ac_sign)


def xor_fields(symbols, ks, **fields):
    """model/selective.py :: apply_keystream with an explicit field selection."""
    out = []
    for s in symbols:
        if s.size == 0:
            out.append(s)
            continue
        all_bits, sign = selected(s, **fields)
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


def stream_ks(tag, ctr=None, key=KEY):
    """Our Ascon keystream for a published scheme; ctr=None = the same stream for every frame (schemes
    without a nonce or IV), else one stream per frame."""
    return ascon.Keystream(key, ascon.make_nonce(0x0BE7C + tag, 0 if ctr is None else ctr + 1, 0))


# ------------------------------------------------------------------ schemes
# Each scheme: fn(an, ctr, key) -> (jpeg, perm), perm = the permutation actually used on this frame
# (None = no permutation; only the tests and the "exact share recovered" figure look at it, the
# attacker recovers its own). fields: which amplitude fields are XORed (and replaced by A2).
# stream: how the XORed bits are drawn, as the attacker (who knows the scheme) sees it:
# "frame" = one keystream through the frame in natural order, "segment" = one per restart segment,
# None = no keystream the A4 attacker can line up (no XOR, or XOR interleaved with keyed shuffles).
def s_plain(an, ctr, key=KEY):
    return jpeg_of(an, an.symbols), None


def s_ours(mode, segmented=False):
    def fn(an, ctr, key=KEY):
        f = package_frame(an, key, SID, ctr, mode, segmented=segmented)
        perm = None
        if mode == "E5":
            perm = ("segments", hw.e5_order(key, SID, ctr, an.n_mcu) if segmented
                    else _shuffle_order(key, SID, ctr, an.n_mcu))
        return f.jpeg, perm
    return fn


def s_vandroogenbroeck(an, ctr, key=KEY):
    return jpeg_of(an, xor_fields(an.symbols, stream_ks(1, key=key), ac_all=True)), None


def s_kishore(an, ctr, key=KEY):
    ks = stream_ks(2, key=key)                          # fixed seed: the same sequence for every frame
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


def s_auer(an, ctr, key=KEY):
    ks = stream_ks(3, ctr, key)                         # file-dependent IV -> per frame
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
    def fn(an, ctr, key=KEY):
        segs, n = [], an.n_mcu
        ks1 = stream_ks(4, key=key)                     # K1 fixed
        for m0 in range(0, n, ri):
            sym = xor_fields(run_length_encode(an.quant[m0:m0 + ri]), ks1, ac_all=True, dc_all=True)
            segs.append(huffman_encode(sym)[0])
        order = keyed_perm(len(segs), stream_ks(5, key=key))   # K2 fixed: same permutation every frame
        scan = join_restart([segs[i] for i in order])
        return jpeg_of(an, None, restart_interval=ri, scan=scan), ("segments", order)
    return fn


E4F = dict(ac_all=True, dc_all=True)
SCHEMES = {
    "plain":            dict(fn=s_plain, fields={}, stream=None, per_frame="-", auth=False, cite="-"),
    "E1":               dict(fn=s_ours("E1"), fields=dict(ac_sign=True), stream="frame", per_frame="yes", auth=True, cite="ours"),
    "E2":               dict(fn=s_ours("E2"), fields=dict(ac_sign=True, dc_sign=True), stream="frame", per_frame="yes", auth=True, cite="ours"),
    "E3":               dict(fn=s_ours("E3"), fields=dict(ac_all=True, dc_sign=True), stream="frame", per_frame="yes", auth=True, cite="ours"),
    "E4":               dict(fn=s_ours("E4"), fields=E4F, stream="frame", per_frame="yes", auth=True, cite="ours"),
    "E5 (v2)":          dict(fn=s_ours("E5"), fields=E4F, stream="frame", per_frame="yes", auth=True, cite="ours"),
    "E5 (v3, hw)":      dict(fn=s_ours("E5", True), fields=E4F, stream="segment", per_frame="yes", auth=True, cite="ours"),
    "VanDroogenbroeck": dict(fn=s_vandroogenbroeck, fields=dict(ac_all=True), stream="frame", per_frame="no", auth=False, cite="vandroogenbroeck2002"),
    "Kishore":          dict(fn=s_kishore, fields={}, stream=None, per_frame="no", auth=False, cite="kishore2015"),
    "Auer":             dict(fn=s_auer, fields=dict(ac_all=True), stream=None, per_frame="yes", auth=False, cite="auer2013"),
    "Hirose RI=1":      dict(fn=s_hirose(1), fields=E4F, stream="frame", per_frame="no", auth=False, cite="hirose2024"),
    "Hirose RI=4":      dict(fn=s_hirose(4), fields=E4F, stream="frame", per_frame="no", auth=False, cite="hirose2024"),
}
PERM_KIND = {"E5 (v2)": "segments", "E5 (v3, hw)": "segments", "Kishore": "blocks", "Auer": "mcu_inner",
             "Hirose RI=1": "segments", "Hirose RI=4": "segments"}   # public: part of each scheme's description


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


# ---- A4: what one known (clear, ciphertext) frame pair gives away
def plain_segments(an, ri):
    """The clear symbols the attacker computes from the known frame, cut like the received stream
    (restart intervals of ri MCUs with fresh DC predictors; ri = 0: one scan)."""
    if not ri:
        return [list(an.symbols)]
    return [run_length_encode(an.quant[m0:m0 + ri]) for m0 in range(0, an.n_mcu, ri)]


def sym_sig(s, fields):
    """What survives encryption of one symbol: run, size, EOB, and the amplitude where it is clear
    (its magnitude where only the sign is encrypted)."""
    all_bits, sign = selected(s, **fields) if s.size else (False, False)
    amp = None if all_bits else abs(s.amp) if sign else s.amp
    return (s.is_dc, s.run, s.size, s.eob, amp)


def block_sig(block, fields):
    """Structure of one 8x8 block that does not change when its run/level units are reordered."""
    us, eob = units(block)
    return (sym_sig(block[0], fields), tuple(sorted(tuple(sym_sig(s, fields) for s in u) for u in us)), bool(eob))


def match(plain_sigs, recv_sigs):
    """For each received item, the index of a clear item with the same signature (first unused one;
    items left over are paired in index order). Identical items are interchangeable for every attack."""
    pool = defaultdict(deque)
    for i, g in enumerate(plain_sigs):
        pool[g].append(i)
    out = [pool[g].popleft() if pool.get(g) else None for g in recv_sigs]
    rest = iter(sorted(set(range(len(plain_sigs))) - {i for i in out if i is not None}))
    return [i if i is not None else next(rest) for i in out]


def recover_perm(kind, an0, segs, ri, fields):
    """Permutation of the known frame, in the scheme's own format, from the clear frame and what was received."""
    if kind == "segments":
        plain = plain_segments(an0, ri)
        return ("segments", match([tuple(sym_sig(s, fields) for s in g) for g in plain],
                                  [tuple(sym_sig(s, fields) for s in g) for g in segs]))
    pb = split_blocks(an0.symbols)
    rb = split_blocks([s for seg in segs for s in seg])
    if kind == "blocks":
        perm = {}
        for c in (0, 1, 2):
            slots = [i for i in range(len(pb)) if COMP_OF_BLOCK[i % 6] == c]
            perm[c] = match([block_sig(pb[i], fields) for i in slots], [block_sig(rb[i], fields) for i in slots])
        return ("blocks", perm)
    if kind == "mcu_inner":
        perm = []
        for m in range(len(pb) // 6):
            p6, r6 = pb[6 * m:6 * m + 6], rb[6 * m:6 * m + 6]
            perm.append((match([block_sig(b, fields) for b in p6[:4]], [block_sig(b, fields) for b in r6[:4]]),
                         match([block_sig(b, fields) for b in p6[4:]], [block_sig(b, fields) for b in r6[4:]])))
        return ("mcu_inner", perm)
    raise ValueError(kind)


def perm_items(perm):
    kind, p = perm
    if kind == "segments":
        return list(p)
    if kind == "blocks":
        return [i for c in sorted(p) for i in p[c]]
    return [i for oy, oc in p for i in list(oy) + list(oc)]


def recover_bits(plain, recv, fields):
    """Keystream bits consumed by the XORed fields, in order: clear field XOR received field, read back
    through model/selective.py :: symbol_mask (bit 0 = top mask bit, the rest = the lower mask bits)."""
    bits = []
    for p, c in zip(plain, recv):
        if p.size == 0 or c.size != p.size:
            continue
        all_bits, sign = selected(p, **fields)
        if not (all_bits or sign):
            continue
        n, full = p.size, (1 << p.size) - 1
        code = lambda a: a if a >= 0 else a + full
        m = code(p.amp) ^ code(c.amp)
        b0 = (m >> (n - 1)) & 1
        bits.append(b0)
        if all_bits:
            low = (m ^ (full if b0 else 0)) & (full >> 1)
            bits += [(low >> j) & 1 for j in range(n - 1)]
    return bits


class Replay:
    """A recovered keystream, handed out like ascon.Keystream.take; past its end it gives 0 (no change)."""
    def __init__(self, bits):
        self.bits, self.i = bits, 0

    def take(self, n):
        v = 0
        for j in range(n):
            if self.i < len(self.bits) and self.bits[self.i]:
                v |= 1 << j
            self.i += 1
        return v


def learn_known_frame(an0, jpeg0, sc, kind):
    """Everything the A4 attacker gets from the known frame (clear) and its ciphertext."""
    w, h, qy, qc, ri, segs = received_segments(jpeg0)
    perm = recover_perm(kind, an0, segs, ri, sc["fields"]) if kind else None
    bits = None
    if sc["stream"]:
        nat = undo_permutation(w, h, ri, segs, perm) if perm else segs
        plain = plain_segments(an0, ri if (perm is None or perm[0] == "segments") else 0)
        if sc["stream"] == "frame":
            bits = [recover_bits([s for g in plain for s in g], [s for g in nat for s in g], sc["fields"])]
        else:
            bits = [recover_bits(p, r, sc["fields"]) for p, r in zip(plain, nat)]
    return dict(perm=perm, bits=bits, stream=sc["stream"])


def nz_map(w, segs, ri):
    """Non-zero AC count per 8x8 luma block, at the position where the block is received."""
    cols = (w + 15) // 16
    syms = [s for seg in segs for s in seg]
    counts = []
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


def known_plaintext(w, h, qy, qc, ri, segs, fields, learned, y0, energy):
    """A4 on one later frame: decrypt with the recovered keystream after undoing the recovered permutation;
    for permuting schemes also replacement and NZCA on the un-permuted frame. The best of them. (Without a
    permutation, replacement and NZCA would repeat A2 and A3, so they are left out here.)"""
    perm = learned["perm"]
    nat = undo_permutation(w, h, ri, segs, perm) if perm else segs
    ri2 = ri if (perm is None or perm[0] == "segments") else 0
    scores = []
    if perm:
        scores += [corr(nz_map(w, nat, ri2), energy),
                   edge_corr(y0, decode(rebuild(w, h, qy, qc, ri2, [replace_fields(s, **fields) for s in nat])))]
    if learned["bits"] is not None:
        if learned["stream"] == "frame":
            ks = Replay(learned["bits"][0])
            dec = [xor_fields(s, ks, **fields) for s in nat]
        else:
            bits = learned["bits"]
            dec = [xor_fields(s, Replay(bits[k] if k < len(bits) else []), **fields) for k, s in enumerate(nat)]
        scores.append(edge_corr(y0, decode(rebuild(w, h, qy, qc, ri2, dec))))
    return max(scores)


def psnr(y0, img):
    mse = float(np.mean((y0 - luma(img)) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255 ** 2 / mse)


def npcr_uaci(a, b):
    a, b = a.astype(np.int16), b.astype(np.int16)
    return 100 * float(np.mean(a != b)), 100 * float(np.mean(np.abs(a - b)) / 255)


def entropy(img):
    y = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h = np.bincount(y.ravel(), minlength=256).astype(np.float64)
    p = h[h > 0] / h.sum()
    return float(-(p * np.log2(p)).sum())


def adjacent_corr(img):
    """Correlation of every pixel with its right, lower and lower-right neighbour (luma)."""
    y = luma(img)
    return dict(corr_h=corr(y[:, :-1], y[:, 1:]), corr_v=corr(y[:-1], y[1:]), corr_d=corr(y[:-1, :-1], y[1:, 1:]))


def views(jpeg, fields, y0, energy, learned=None, jpeg_key2=None, jpeg_px=None):
    """The four attacks and the published metrics on one received frame. learned = what A4 got from
    the known frame; jpeg_key2 = the same frame under a key one bit apart; jpeg_px = the frame with
    one pixel changed, same key."""
    w, h, qy, qc, ri, segs = received_segments(jpeg)
    img = decode(jpeg)
    a1 = edge_corr(y0, img)
    repl = rebuild(w, h, qy, qc, ri, [replace_fields(s, **fields) for s in segs])
    a2 = edge_corr(y0, decode(repl))
    a3 = corr(nz_map(w, segs, ri), energy)
    a4 = known_plaintext(w, h, qy, qc, ri, segs, fields, learned, y0, energy) if learned is not None else None
    r = dict(decode=a1, replacement=a2, nzca=a3, known_plaintext=a4,
             ssim_decode=float(max(0.0, structural_similarity(y0, luma(img), data_range=255))),
             psnr_decode=psnr(y0, img), entropy=entropy(img), **adjacent_corr(img))
    if jpeg_key2 is not None:
        r["npcr_key"], r["uaci_key"] = npcr_uaci(img, decode(jpeg_key2))
    if jpeg_px is not None:
        r["npcr_px"], r["uaci_px"] = npcr_uaci(img, decode(jpeg_px))
    return r


def compliant(jpeg):
    try:
        a = decode(jpeg)
        b = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        return a is not None and b is not None and a.shape[:2] == b.shape[:2]
    except Exception:
        return False


def bootstrap_ci(values, n=2000, seed=0):
    """95 % percentile-bootstrap interval of the mean (same as experiments/learned_attack.py)."""
    v = np.asarray(values, dtype=np.float64)
    if len(v) < 2:
        return [float(v.mean()), float(v.mean())]
    means = v[np.random.default_rng(seed).integers(0, len(v), (n, len(v)))].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def native_size(spec):
    """Width x height of the source itself (rounded down to whole MCUs), for --size native."""
    if spec in ("synthetic", "", None):
        return 320, 240
    if Path(str(spec)).is_dir():
        f = next(p for p in sorted(Path(spec).iterdir()) if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".ppm", ".tif", ".tiff"))
        h, w = cv2.imread(str(f)).shape[:2]
    else:
        cap = cv2.VideoCapture(str(spec))
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
    return w // 16 * 16, h // 16 * 16


def frames_of(a):
    w, h = native_size(a.video) if a.size == "native" else map(int, a.size.split("x"))
    src = open_source(a.video, w, h, loop=False)
    out = []
    for i in range(a.frames * a.stride):
        f = src.read()
        if f is None:
            break
        if i % a.stride == 0:
            out.append(f)
    return out, f"{w}x{h}"


METRICS = ("decode", "replacement", "nzca", "known_plaintext", "ssim_decode", "psnr_decode", "entropy",
           "corr_h", "corr_v", "corr_d", "npcr_key", "uaci_key", "npcr_px", "uaci_px")
ATTACKS = ("decode", "replacement", "nzca", "known_plaintext")


def one_pixel(rgb):
    out = rgb.copy()
    y, x = rgb.shape[0] // 2, rgb.shape[1] // 2
    out[y, x] = 255 - out[y, x]              # inverted, so the change survives quantisation
    return out


def known_frame(ans):
    """The attacker's known frame: the one with the most non-zero AC coefficients. A black or faded
    opening frame (common in films) has no structure to match and almost no encrypted bits, so taking
    frame 0 blindly would understate what one known frame gives away."""
    nz = [sum(1 for s in an.symbols if s.size and not s.is_dc) for an in ans]
    return max(range(len(ans)), key=lambda t: (nz[t], -t))


def evaluate(name, frames, quality, y0s, energies, ans, ans_px, plain_bytes, kf=0):
    """All attacks and metrics for one scheme over the frames; frame kf is the attacker's known frame
    and every other frame is scored."""
    sc = SCHEMES[name]
    out = [sc["fn"](an, ctr) for ctr, an in enumerate(ans)]
    kind = PERM_KIND.get(name)
    learned = learn_known_frame(ans[kf], out[kf][0], sc, kind) if (kind or sc["stream"]) else None
    per = []
    for t in (t for t in range(len(ans)) if t != kf):
        k2 = sc["fn"](ans[t], t, KEY2)[0] if name != "plain" else None
        px = sc["fn"](ans_px[t], t)[0]
        per.append(views(out[t][0], sc["fields"], y0s[t], energies[t], learned, k2, px))
    r = dict(cite=sc["cite"], per_frame=sc["per_frame"], authenticated=sc["auth"],
             bytes_vs_plain=float(np.mean([len(j) / b - 1 for (j, _), b in zip(out, plain_bytes)])),
             compliant=all(compliant(j) for j, _ in out), ci={})
    for k in METRICS:
        vals = [p[k] for p in per if p.get(k) is not None]
        r[k] = float(np.mean(vals)) if vals else None
        if vals:
            r["ci"][k] = bootstrap_ci(vals)
    r["perm_recovered"] = None
    if learned is not None and learned["perm"] is not None and out[kf][1] is not None:
        true, got = perm_items(out[kf][1]), perm_items(learned["perm"])
        r["perm_recovered"] = float(np.mean([a == b for a, b in zip(true, got)]))
    r["keystream_bits_recovered"] = (sum(len(b) for b in learned["bits"])
                                     if learned is not None and learned["bits"] is not None else None)
    best = max((k for k in ATTACKS if r[k] is not None), key=lambda k: r[k])
    r["max_leak"], r["max_leak_attack"], r["ci"]["max_leak"] = r[best], best, r["ci"][best]
    return r


def tables(name, size, quality, n_scored, rows):
    f = lambda v, nd=2: "-" if v is None else f"{v:.{nd}f}"
    ci = lambda r, k, nd=2: "-" if r.get(k) is None else f"{r[k]:.{nd}f} [{r['ci'][k][0]:.{nd}f}, {r['ci'][k][1]:.{nd}f}]"
    lines = [f"# SVE-Bench ({name}, {size}, quality {quality}, {n_scored} scored frames, mean [95 % CI])", "",
             "## Attacks (edge correlation with the original, 0 = nothing)", "",
             "| Scheme | Source | Per-frame key | Auth. | Bytes | Decodes | A1 decode | A2 repl. | A3 NZCA | "
             "A4 known plaintext | Perm. recovered | **Max leak** |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in rows.items():
        pr = "-" if r["perm_recovered"] is None else f"{r['perm_recovered']:.0%}"
        lines.append(f"| {n} | {r['cite']} | {r['per_frame']} | {'yes' if r['authenticated'] else 'no'} | "
                     f"{r['bytes_vs_plain']:+.1%} | {'yes' if r['compliant'] else 'NO'} | {f(r['decode'])} | "
                     f"{f(r['replacement'])} | {f(r['nzca'])} | {f(r['known_plaintext'])} | {pr} | "
                     f"**{ci(r, 'max_leak')}** |")
    lines += ["", "## Metrics papers report (no-key picture)", "",
              "| Scheme | PSNR (dB) | SSIM | Entropy | Corr. h / v / d | NPCR / UACI key (%) | NPCR / UACI 1 px (%) |",
              "|---|---|---|---|---|---|---|"]
    for n, r in rows.items():
        lines.append(f"| {n} | {ci(r, 'psnr_decode')} | {ci(r, 'ssim_decode')} | {f(r['entropy'], 3)} | "
                     f"{f(r['corr_h'])} / {f(r['corr_v'])} / {f(r['corr_d'])} | "
                     f"{f(r['npcr_key'], 1)} / {f(r['uaci_key'], 1)} | {f(r['npcr_px'], 1)} / {f(r['uaci_px'], 1)} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=6, help="frames; the one with the most detail is the attacker's known frame")
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--size", default="320x240", help="WxH, or 'native' (the source's own size, whole MCUs)")
    ap.add_argument("--quality", type=int, nargs="+", default=[DEFAULT_QUALITY],
                    help="JPEG quality factors; more than one runs a sweep (e.g. 50 75 90)")
    ap.add_argument("--schemes", nargs="+", default=list(SCHEMES))
    ap.add_argument("--name", default="synthetic")
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "benchmark_suite"))
    a = ap.parse_args()
    frames, size = frames_of(a)
    if len(frames) < 2:
        raise SystemExit("need at least 2 frames")
    y0s = [luma(f) for f in frames]
    frames_px = [one_pixel(f) for f in frames]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for q in a.quality:
        ans = [analyse_frame(f, quality=q) for f in frames]
        ans_px = [analyse_frame(f, quality=q) for f in frames_px]
        plain_bytes = [len(jpeg_of(an, an.symbols)) for an in ans]
        energies = [block_energy(y, (an.height // 8, an.width // 8)) for y, an in zip(y0s, ans)]
        k = known_frame(ans)
        rows = {}
        for name in a.schemes:
            r = rows[name] = evaluate(name, frames, q, y0s, energies, ans, ans_px, plain_bytes, k)
            kp = r["known_plaintext"]
            print(f"q{q} {name:18s} bytes {r['bytes_vs_plain']:+.1%}  decode {r['decode']:.2f}  "
                  f"repl {r['replacement']:.2f}  nzca {r['nzca']:.2f}  kpa {('%.2f' % kp) if kp is not None else '  - '}  "
                  f"-> max {r['max_leak']:.2f}  PSNR {r['psnr_decode']:.1f}" + ("" if r["compliant"] else "  NOT COMPLIANT"),
                  flush=True)
        tag = a.name if q == DEFAULT_QUALITY else f"{a.name}_q{q}"   # the default quality keeps the plain name; a sweep adds _q<Q> files
        meta = dict(source=a.video, frames=len(frames), scored_frames=len(frames) - 1, size=size, quality=q,
                    known_frame=k, ci="95 % percentile bootstrap over scored frames (2000 resamples)",
                    note="attacks: edge correlation with the original luma (0 = nothing); max_leak = the best attack; "
                         "metrics on the no-key picture (A1)")
        (out / f"{tag}.json").write_text(json.dumps(dict(meta=meta, schemes=rows), indent=1))
        md = tables(a.name, size, q, len(frames) - 1, rows)
        (out / f"{tag}.md").write_text(md)
        print(md)


if __name__ == "__main__":
    main()
