"""Bit-exact golden model of the hardware JPEG encoder with selective encryption.

Each function here corresponds to one RTL block:

  rgb_to_ycbcr / blocks_in_hw_order  -> rtl/rgb2ycbcr_block.v
  dct2d (two dct_stage passes)       -> rtl/dct8x8.v (+ rtl/dct_stage.v)
  quantise                           -> rtl/quantiser.v
  run_length                         -> rtl/zigzag_rle.v
  selective_encrypt                  -> rtl/selective_enc.v (+ keystream_gen.v)
  huffman_bits / pack_bytes          -> rtl/huffman_enc.v + rtl/bit_packer.v
  ascon.mac(scan)                    -> rtl/tag_unit.v

The integer arithmetic is chosen so that hardware and model agree exactly.
"""
import math
from collections import namedtuple

from . import ascon
from .tables import (Q_LUMA_BASE, Q_CHROMA_BASE, ZIGZAG, DC_CODES, AC_CODES,
                     DC_LUMA_BITS, DC_LUMA_VALS, DC_CHROMA_BITS, DC_CHROMA_VALS,
                     AC_LUMA_BITS, AC_LUMA_VALS, AC_CHROMA_BITS, AC_CHROMA_VALS)

# Encryption modes (CTRL[3:1])
MODE_OFF, MODE_E1, MODE_E2, MODE_E3, MODE_E4 = 0, 1, 2, 3, 4
MODE_NAMES = {0: "off", 1: "E1 AC signs", 2: "E2 +DC signs",
              3: "E3 +AC amplitudes", 4: "E4 +DC amplitudes"}

# One run-length symbol. amp holds the JPEG-coded amplitude bits (size bits,
# ones'-complement form for negatives), exactly as they appear in the file.
Sym = namedtuple("Sym", "is_dc run size amp eob comp")


# ------------------------------------------------------------ colour + blocks
def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def rgb_to_ycbcr(r, g, b):
    """BT.601 full-range (JFIF) integer conversion, as in rgb2ycbcr_block.v."""
    y = (77 * r + 150 * g + 29 * b + 128) >> 8
    cb = (-43 * r - 85 * g + 128 * b + 32896) >> 8
    cr = (128 * r - 107 * g - 21 * b + 32896) >> 8
    return _clamp(y, 0, 255), _clamp(cb, 0, 255), _clamp(cr, 0, 255)


def planes(rgb):
    """rgb: H x W x 3 nested list / numpy array of uint8. Returns (Y, Cb, Cr)
    where Y is H x W and Cb/Cr are (H/2) x (W/2) 4:2:0 averages."""
    h, w = len(rgb), len(rgb[0])
    assert h % 16 == 0 and w % 16 == 0, "width and height must be multiples of 16"
    Y = [[0] * w for _ in range(h)]
    CB = [[0] * w for _ in range(h)]
    CR = [[0] * w for _ in range(h)]
    for i in range(h):
        row = rgb[i]
        for j in range(w):
            r, g, b = (int(v) for v in row[j][:3])
            Y[i][j], CB[i][j], CR[i][j] = rgb_to_ycbcr(r, g, b)
    cb = [[(CB[2 * i][2 * j] + CB[2 * i][2 * j + 1] + CB[2 * i + 1][2 * j]
            + CB[2 * i + 1][2 * j + 1] + 2) >> 2 for j in range(w // 2)]
          for i in range(h // 2)]
    cr = [[(CR[2 * i][2 * j] + CR[2 * i][2 * j + 1] + CR[2 * i + 1][2 * j]
            + CR[2 * i + 1][2 * j + 1] + 2) >> 2 for j in range(w // 2)]
          for i in range(h // 2)]
    return Y, cb, cr


def blocks_in_hw_order(rgb):
    """List of (comp, [64 samples row-major]) in the order the hardware emits
    them: MCU rows top to bottom, MCUs left to right, Y0 Y1 Y2 Y3 Cb Cr."""
    Y, cb, cr = planes(rgb)
    h, w = len(Y), len(Y[0])
    out = []
    for my in range(h // 16):
        for mx in range(w // 16):
            for k in range(4):
                r0, c0 = my * 16 + (k >> 1) * 8, mx * 16 + (k & 1) * 8
                out.append((0, [Y[r0 + i][c0 + j] for i in range(8) for j in range(8)]))
            for comp, p in ((1, cb), (2, cr)):
                out.append((comp, [p[my * 8 + i][mx * 8 + j] for i in range(8) for j in range(8)]))
    return out


# ------------------------------------------------------------------- 8x8 DCT
DCT_SCALE_BITS = 13


def _dct_coeff(u, x):
    cu = 1 / math.sqrt(2) if u == 0 else 1.0
    return int(math.floor((1 << DCT_SCALE_BITS) * cu / 2 * math.cos((2 * x + 1) * u * math.pi / 16) + 0.5))


DCT_C = [[_dct_coeff(u, x) for x in range(8)] for u in range(8)]
STAGE1_SHIFT, STAGE2_SHIFT = 11, 15


def dct_stage(block, shift):
    """1-D DCT on each row, output transposed (row-major): exactly dct_stage.v.
    out[u*8 + y] = round(sum_x C[u][x] * in[y*8 + x] / 2^shift)."""
    half = 1 << (shift - 1)
    return [(sum(DCT_C[u][x] * block[y * 8 + x] for x in range(8)) + half) >> shift
            for u in range(8) for y in range(8)]


def dct2d(samples):
    """samples: 64 unsigned 8-bit values (row-major). Returns F[v*8+u]."""
    return dct_stage(dct_stage([s - 128 for s in samples], STAGE1_SHIFT), STAGE2_SHIFT)


# ----------------------------------------------------------------- quantiser
def quality_tables(quality):
    """libjpeg quality scaling. Returns (luma, chroma) natural-order tables."""
    quality = _clamp(quality, 1, 100)
    s = 5000 // quality if quality < 50 else 200 - 2 * quality
    scale = lambda t: [_clamp((q * s + 50) // 100, 1, 255) for q in t]
    return scale(Q_LUMA_BASE), scale(Q_CHROMA_BASE)


def reciprocal(q):
    """17-bit reciprocal R = round(65536 / Q) used by quantiser.v."""
    return (131072 + q) // (2 * q)


def quantise(coeffs, recips):
    """coeffs: 64 DCT values (natural order); recips: 64 reciprocals."""
    out = []
    for i, f in enumerate(coeffs):
        m = (abs(f) * recips[i] + 32768) >> 16
        q = -m if f < 0 else m
        out.append(_clamp(q, -1024, 1023) if i == 0 else _clamp(q, -1023, 1023))
    return out


# --------------------------------------------------------- zig-zag + run-length
def category(v):
    """JPEG size category: number of bits needed for |v| (0 for 0)."""
    return abs(v).bit_length()


def amp_bits(v):
    """Amplitude bits written to the file (negatives in ones' complement)."""
    s = category(v)
    return (v if v >= 0 else v - 1) & ((1 << s) - 1)


def amp_value(bits, size):
    """Inverse of amp_bits."""
    if size == 0:
        return 0
    return bits if bits >> (size - 1) else bits - (1 << size) + 1


def run_length(qblock, comp, pred):
    """One block -> symbol list. pred: dict comp -> previous DC (updated)."""
    syms = []
    dc = qblock[0]
    diff = dc - pred[comp]
    pred[comp] = dc
    syms.append(Sym(1, 0, category(diff), amp_bits(diff), 0, comp))
    run = 0
    for k in range(1, 64):
        c = qblock[ZIGZAG[k]]
        if c == 0:
            if k == 63:
                syms.append(Sym(0, 0, 0, 0, 1, comp))       # EOB
            else:
                run += 1
            continue
        while run >= 16:
            syms.append(Sym(0, 15, 0, 0, 0, comp))          # ZRL
            run -= 16
        syms.append(Sym(0, run, category(c), amp_bits(c), 0, comp))
        run = 0
    return syms


# ------------------------------------------------------- selective encryption
def bits_needed(sym, mode):
    """Keystream bits consumed by one symbol (selective_enc.v)."""
    if sym.size == 0:
        return 0
    sgn = mode >= (MODE_E2 if sym.is_dc else MODE_E1)
    amp = mode >= (MODE_E4 if sym.is_dc else MODE_E3)
    return (1 if sgn else 0) + (sym.size - 1 if amp else 0)


def encrypt_symbol(sym, mode, ks):
    """ks: list of the keystream bits for this symbol (len == bits_needed).
    Bit 0 flips the sign (inverts all size bits); bits 1.. XOR the low
    (size-1) amplitude bits, LSB first. XOR is its own inverse."""
    n = bits_needed(sym, mode)
    if n == 0:
        return sym
    mask = (1 << sym.size) - 1
    a = sym.amp ^ (mask if ks[0] else 0)
    for i in range(1, n):
        a ^= ks[i] << (i - 1)
    return sym._replace(amp=a)


def selective_encrypt(syms, mode, key, nonce):
    total = sum(bits_needed(s, mode) for s in syms)
    ks = ascon.keystream_bits(key, nonce, total)
    out, p = [], 0
    for s in syms:
        n = bits_needed(s, mode)
        out.append(encrypt_symbol(s, mode, ks[p:p + n]))
        p += n
    return out, total


# ------------------------------------------------------- Huffman + bit packing
def huffman_bits(sym):
    """(value, length) emitted by huffman_enc.v for one symbol (code then amp)."""
    t = 0 if sym.comp == 0 else 1
    if sym.is_dc:
        code, clen = DC_CODES[t][sym.size]
    else:
        code, clen = AC_CODES[t][(sym.run << 4) | sym.size]
    return (code << sym.size) | sym.amp, clen + sym.size


def pack_bytes(chunks):
    """MSB-first bit packing, 0xFF -> 0xFF 0x00 stuffing, pad final byte with 1s."""
    out, acc, n = bytearray(), 0, 0
    for val, ln in chunks:
        acc = (acc << ln) | (val & ((1 << ln) - 1))
        n += ln
        while n >= 8:
            n -= 8
            byte = (acc >> n) & 0xFF
            out.append(byte)
            if byte == 0xFF:
                out.append(0x00)
        acc &= (1 << n) - 1
    if n:
        byte = ((acc << (8 - n)) | ((1 << (8 - n)) - 1)) & 0xFF
        out.append(byte)
        if byte == 0xFF:
            out.append(0x00)
    return bytes(out)


# --------------------------------------------------------------- file format
def _seg(marker, payload):
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


APP11_ID = b"SJPG"   # our tag segment: id, version, mode, frame_ctr, session_id, tag


def app11_segment(mode, frame_ctr, session_id, tag):
    payload = (APP11_ID + bytes([1, mode]) + frame_ctr.to_bytes(4, "little")
               + session_id.to_bytes(4, "little") + bytes(tag))
    return _seg(0xEB, payload)


def headers(width, height, quality, app11=b""):
    """SOI, APP0 (JFIF), [APP11 tag], DQT, SOF0, DHT x4, SOS."""
    luma, chroma = quality_tables(quality)
    h = b"\xFF\xD8"
    h += _seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    h += app11
    h += _seg(0xDB, bytes([0x00]) + bytes(luma[ZIGZAG[k]] for k in range(64))
              + bytes([0x01]) + bytes(chroma[ZIGZAG[k]] for k in range(64)))
    h += _seg(0xC0, bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big")
              + bytes([3, 1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1]))
    for cls_id, bits, vals in ((0x00, DC_LUMA_BITS, DC_LUMA_VALS),
                               (0x10, AC_LUMA_BITS, AC_LUMA_VALS),
                               (0x01, DC_CHROMA_BITS, DC_CHROMA_VALS),
                               (0x11, AC_CHROMA_BITS, AC_CHROMA_VALS)):
        h += _seg(0xC4, bytes([cls_id]) + bytes(bits) + bytes(vals))
    h += _seg(0xDA, bytes([3, 1, 0x00, 2, 0x11, 3, 0x11, 0, 63, 0]))
    return h


def segments(jpeg):
    """Walk the marker segments of a JPEG header: yields (marker, offset, payload)
    up to and including SOS. Never byte-search for markers: 0xFF 0xC0 can occur
    inside other segments' payloads (e.g. a session ID or a tag)."""
    assert jpeg[:2] == b"\xFF\xD8", "not a JPEG (no SOI)"
    i = 2
    while i + 4 <= len(jpeg):
        assert jpeg[i] == 0xFF, f"expected a marker at offset {i}"
        marker = jpeg[i + 1]
        seglen = int.from_bytes(jpeg[i + 2:i + 4], "big")
        yield marker, i, jpeg[i + 4:i + 2 + seglen]
        if marker == 0xDA:
            return
        i += 2 + seglen


def parse_app11(jpeg):
    """Returns dict(mode, frame_ctr, session_id, tag) or None."""
    for marker, _, p in segments(jpeg):
        if marker == 0xEB and p[:4] == APP11_ID:
            return dict(mode=p[5], frame_ctr=int.from_bytes(p[6:10], "little"),
                        session_id=int.from_bytes(p[10:14], "little"), tag=bytes(p[14:30]))
    return None


def frame_size(jpeg):
    """(width, height) from the SOF0 segment."""
    for marker, _, p in segments(jpeg):
        if marker == 0xC0:
            return int.from_bytes(p[3:5], "big"), int.from_bytes(p[1:3], "big")
    raise ValueError("no SOF0 segment")


def split_scan(jpeg):
    """Return (header_bytes_up_to_and_including_SOS, scan_bytes) of one JPEG."""
    for marker, off, p in segments(jpeg):
        if marker == 0xDA:
            start = off + 4 + len(p)
            assert jpeg[-2:] == b"\xFF\xD9", "missing EOI"
            return jpeg[:start], jpeg[start:-2]
    raise ValueError("no SOS segment")


# ------------------------------------------------------------- full encoder
def encode_frame(rgb, quality=75, mode=MODE_E2, key=bytes(16), frame_ctr=0,
                 session_id=0):
    """Returns a dict with every intermediate stage (used as test vectors)."""
    h, w = len(rgb), len(rgb[0])
    luma, chroma = quality_tables(quality)
    recips = [[reciprocal(q) for q in luma], [reciprocal(q) for q in chroma]]
    blocks = blocks_in_hw_order(rgb)
    coeffs, qcoeffs, syms = [], [], []
    pred = {0: 0, 1: 0, 2: 0}
    for comp, smp in blocks:
        f = dct2d(smp)
        q = quantise(f, recips[0 if comp == 0 else 1])
        coeffs.append(f)
        qcoeffs.append(q)
        syms.extend(run_length(q, comp, pred))
    n_enc = ascon.make_nonce(frame_ctr, session_id, 0)
    n_mac = ascon.make_nonce(frame_ctr, session_id, 1)
    enc_syms, ks_bits = selective_encrypt(syms, mode, key, n_enc)
    scan = pack_bytes([huffman_bits(s) for s in enc_syms])
    tag = ascon.mac(key, n_mac, scan)
    jpeg = headers(w, h, quality, app11_segment(mode, frame_ctr, session_id, tag)) + scan + b"\xFF\xD9"
    return dict(blocks=blocks, coeffs=coeffs, qcoeffs=qcoeffs, symbols=syms,
                enc_symbols=enc_syms, keystream_bits_used=ks_bits, scan=scan,
                tag=tag, jpeg=jpeg, width=w, height=h, recips=recips)


# ------------------------------------------------------------- Huffman decode
class _BitReader:
    def __init__(self, scan):
        data, i = bytearray(), 0
        while i < len(scan):                      # remove byte stuffing
            data.append(scan[i])
            i += 2 if scan[i] == 0xFF and i + 1 < len(scan) and scan[i + 1] == 0 else 1
        self.data, self.pos = bytes(data), 0

    def bit(self):
        byte = self.data[self.pos >> 3] if (self.pos >> 3) < len(self.data) else 0xFF
        b = (byte >> (7 - (self.pos & 7))) & 1
        self.pos += 1
        return b

    def bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v

    def huff(self, codes):
        lookup = {(c, l): s for s, (c, l) in codes.items()}
        code = 0
        for length in range(1, 17):
            code = (code << 1) | self.bit()
            if (code, length) in lookup:
                return lookup[(code, length)]
        raise ValueError("invalid Huffman code at bit %d" % self.pos)


def decode_symbols(scan, width, height):
    """Parse scan data back into the symbol list (the receiver's first step)."""
    br = _BitReader(scan)
    nmcu = (width // 16) * (height // 16)
    syms = []
    for _ in range(nmcu):
        for comp in (0, 0, 0, 0, 1, 2):
            t = 0 if comp == 0 else 1
            size = br.huff(DC_CODES[t])
            syms.append(Sym(1, 0, size, br.bits(size), 0, comp))
            k = 1
            while k < 64:
                rs = br.huff(AC_CODES[t])
                run, size = rs >> 4, rs & 15
                if rs == 0:
                    syms.append(Sym(0, 0, 0, 0, 1, comp))
                    break
                syms.append(Sym(0, run, size, br.bits(size), 0, comp))
                k += run + 1
    return syms


# ------------------------------------------------------------------ receiver
class Receiver:
    """Laptop-side golden receiver: verify tag, reject replays, decrypt."""

    def __init__(self, key, session_id):
        self.key, self.session_id, self.last_ctr = bytes(key), session_id, -1

    def process(self, jpeg):
        """Returns (verdict, clear_jpeg_or_None). verdict in
        {'ok', 'bad-format', 'wrong-session', 'replay', 'tag-mismatch'}."""
        try:
            info = parse_app11(jpeg)
        except (AssertionError, IndexError):
            info = None
        if info is None:
            return "bad-format", None
        if info["session_id"] != self.session_id:
            return "wrong-session", None
        if info["frame_ctr"] <= self.last_ctr:
            return "replay", None
        hdr, scan = split_scan(jpeg)
        n_mac = ascon.make_nonce(info["frame_ctr"], self.session_id, 1)
        if ascon.mac(self.key, n_mac, scan) != info["tag"]:
            return "tag-mismatch", None
        self.last_ctr = info["frame_ctr"]
        w, h = frame_size(hdr)
        syms = decode_symbols(scan, w, h)
        n_enc = ascon.make_nonce(info["frame_ctr"], self.session_id, 0)
        clear, _ = selective_encrypt(syms, info["mode"], self.key, n_enc)
        return "ok", hdr + pack_bytes([huffman_bits(s) for s in clear]) + b"\xFF\xD9"
