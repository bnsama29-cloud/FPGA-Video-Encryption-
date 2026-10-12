"""Zig-zag + run-length symbols, standard JPEG Huffman coding, bit packing, 0xFF stuffing.

Symbol (symbol-stream contract): is_dc, run, size, amp, eob, comp
  * DC symbol : is_dc=1, run=0, size=category(diff), amp=diff from previous DC of same comp
  * AC symbol : run = zeros before this coefficient (0..15), size = category(amp)
  * ZRL       : run=15, size=0, amp=0   (16 zeros)
  * EOB       : eob=1, run=0, size=0    (only emitted when coefficient 63 is zero)
  * comp      : 0 = Y, 1 = Cb, 2 = Cr

Amplitude bits written after each Huffman code (T.81): for v >= 0 the `size`
low bits of v; for v < 0 the `size` low bits of v + 2^size - 1 (= ones' complement
of |v|). So the MSB of the field is the sign (1 = positive) and ANY bit pattern of
length `size` is a valid value of that size -> XOR on these bits never changes
the code length. That is what makes the selective encryption format-compliant.

Bit packer: MSB-first, final byte padded with 1s, then every 0xFF byte is followed
by 0x00 (byte stuffing).
"""
from typing import NamedTuple

import numpy as np

ZIGZAG = np.array([
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63])

COMP_OF_BLOCK = (0, 0, 0, 0, 1, 2)       # Y0 Y1 Y2 Y3 Cb Cr

# ---- Standard Huffman tables (ITU-T T.81 Annex K.3) -------------------------
DC_LUMA_BITS = [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
DC_LUMA_VALS = list(range(12))
DC_CHROMA_BITS = [0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
DC_CHROMA_VALS = list(range(12))
AC_LUMA_BITS = [0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7D]
AC_LUMA_VALS = [
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07,
    0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0,
    0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49,
    0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
    0x6A, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7,
    0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5,
    0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
    0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8,
    0xF9, 0xFA]
AC_CHROMA_BITS = [0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 0x77]
AC_CHROMA_VALS = [
    0x00, 0x01, 0x02, 0x03, 0x11, 0x04, 0x05, 0x21, 0x31, 0x06, 0x12, 0x41, 0x51, 0x07, 0x61, 0x71,
    0x13, 0x22, 0x32, 0x81, 0x08, 0x14, 0x42, 0x91, 0xA1, 0xB1, 0xC1, 0x09, 0x23, 0x33, 0x52, 0xF0,
    0x15, 0x62, 0x72, 0xD1, 0x0A, 0x16, 0x24, 0x34, 0xE1, 0x25, 0xF1, 0x17, 0x18, 0x19, 0x1A, 0x26,
    0x27, 0x28, 0x29, 0x2A, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48,
    0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68,
    0x69, 0x6A, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
    0x88, 0x89, 0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5,
    0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3,
    0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA,
    0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8,
    0xF9, 0xFA]

for _b, _v in ((DC_LUMA_BITS, DC_LUMA_VALS), (DC_CHROMA_BITS, DC_CHROMA_VALS),
               (AC_LUMA_BITS, AC_LUMA_VALS), (AC_CHROMA_BITS, AC_CHROMA_VALS)):
    assert sum(_b) == len(_v)


def build_codes(bits, vals):
    """Canonical Huffman codes: {value: (code, length)} (T.81 Annex C)."""
    codes, code, k = {}, 0, 0
    for length in range(1, 17):
        for _ in range(bits[length - 1]):
            codes[vals[k]] = (code, length)
            code += 1
            k += 1
        code <<= 1
    return codes


DC_CODES = (build_codes(DC_LUMA_BITS, DC_LUMA_VALS), build_codes(DC_CHROMA_BITS, DC_CHROMA_VALS))
AC_CODES = (build_codes(AC_LUMA_BITS, AC_LUMA_VALS), build_codes(AC_CHROMA_BITS, AC_CHROMA_VALS))


class Symbol(NamedTuple):
    is_dc: int
    run: int
    size: int
    amp: int
    eob: int
    comp: int


def category(v):
    return abs(int(v)).bit_length()


def amp_to_bits(v, size):
    return v if v >= 0 else v + (1 << size) - 1


def bits_to_amp(b, size):
    if size == 0:
        return 0
    return b if (b >> (size - 1)) else b - (1 << size) + 1


# ---- Zig-zag + run-length -----------------------------------------------------
def zigzag(qblocks):
    """(n, 6, 8, 8) -> (n, 6, 64) in zig-zag order."""
    n = qblocks.shape[0]
    return qblocks.reshape(n, 6, 64)[:, :, ZIGZAG]


def run_length_encode(qblocks, restart=False):
    """Quantised blocks (n_mcu, 6, 8, 8) -> list[Symbol] in coding order.

    restart=True: restart interval of one MCU (T.81 F.1.2.3): the DC predictors
    are reset to 0 at the start of every MCU, so each MCU decodes on its own."""
    zz = zigzag(qblocks).tolist()
    pred = [0, 0, 0]
    out = []
    app = out.append
    for mcu in zz:
        if restart:
            pred = [0, 0, 0]
        for b in range(6):
            c = COMP_OF_BLOCK[b]
            blk = mcu[b]
            diff = blk[0] - pred[c]
            pred[c] = blk[0]
            app(Symbol(1, 0, category(diff), diff, 0, c))
            last = 63
            while last > 0 and blk[last] == 0:
                last -= 1
            run = 0
            for k in range(1, last + 1):
                v = blk[k]
                if v == 0:
                    run += 1
                    continue
                while run > 15:
                    app(Symbol(0, 15, 0, 0, 0, c))
                    run -= 16
                app(Symbol(0, run, category(v), v, 0, c))
                run = 0
            if last < 63:
                app(Symbol(0, 0, 0, 0, 1, c))
    return out


def symbols_to_blocks(symbols, n_mcu, restart=False):
    """Inverse of run_length_encode: list[Symbol] -> quantised blocks (n_mcu, 6, 8, 8)."""
    zz = np.zeros((n_mcu * 6, 64), dtype=np.int32)
    pred = [0, 0, 0]
    blk, k = -1, 64
    for s in symbols:
        if s.is_dc:
            blk += 1
            if restart and blk % 6 == 0:
                pred = [0, 0, 0]
            pred[s.comp] += s.amp
            zz[blk, 0] = pred[s.comp]
            k = 1
        elif s.eob:
            k = 64
        elif s.size == 0:              # ZRL: 16 zeros
            k += 16
        else:
            k += s.run
            zz[blk, k] = s.amp
            k += 1
    nat = np.zeros_like(zz)
    nat[:, ZIGZAG] = zz
    return nat.reshape(n_mcu, 6, 8, 8)


# ---- Huffman encoding + bit packing + stuffing ---------------------------------
def huffman_encode(symbols):
    """list[Symbol] -> (stuffed scan bytes, number of payload bits before padding)."""
    out = bytearray()
    acc, nbits, total = 0, 0, 0
    for s in symbols:
        t = 0 if s.comp == 0 else 1
        if s.is_dc:
            code, ln = DC_CODES[t][s.size]
        else:
            code, ln = AC_CODES[t][(s.run << 4) | s.size]
        size = s.size
        if size:
            v = s.amp if s.amp >= 0 else s.amp + (1 << size) - 1
            code = (code << size) | v
            ln += size
        acc = (acc << ln) | code
        nbits += ln
        total += ln
        while nbits >= 8:
            nbits -= 8
            out.append((acc >> nbits) & 0xFF)
        acc &= (1 << nbits) - 1
    if nbits:
        out.append(((acc << (8 - nbits)) | ((1 << (8 - nbits)) - 1)) & 0xFF)
    return bytes(out).replace(b"\xff", b"\xff\x00"), total


def _build_lut(codes):
    lut = [None] * 65536
    for val, (code, ln) in codes.items():
        start = code << (16 - ln)
        for i in range(start, start + (1 << (16 - ln))):
            lut[i] = (val, ln)
    return lut


_DC_LUT = None
_AC_LUT = None


def _luts():
    global _DC_LUT, _AC_LUT
    if _DC_LUT is None:
        _DC_LUT = (_build_lut(DC_CODES[0]), _build_lut(DC_CODES[1]))
        _AC_LUT = (_build_lut(AC_CODES[0]), _build_lut(AC_CODES[1]))
    return _DC_LUT, _AC_LUT


class ScanError(ValueError):
    pass


def huffman_decode(scan, n_mcu):
    """Stuffed scan bytes -> list[Symbol] (exact inverse of huffman_encode)."""
    dc_lut, ac_lut = _luts()
    data = scan.replace(b"\xff\x00", b"\xff")
    nb = len(data) * 8
    bits = bin(int.from_bytes(data, "big") | (1 << nb))[3:] + "1" * 16 if data else "1" * 16
    pos = 0
    out = []
    app = out.append
    for _ in range(n_mcu):
        for b in range(6):
            c = COMP_OF_BLOCK[b]
            t = 0 if c == 0 else 1
            hit = dc_lut[t][int(bits[pos:pos + 16], 2)]
            if hit is None or pos >= nb:
                raise ScanError(f"bad DC code at bit {pos}")
            size, ln = hit
            pos += ln
            v = int(bits[pos:pos + size], 2) if size else 0
            pos += size
            app(Symbol(1, 0, size, bits_to_amp(v, size), 0, c))
            k = 1
            lut = ac_lut[t]
            while k < 64:
                hit = lut[int(bits[pos:pos + 16], 2)]
                if hit is None or pos >= nb:
                    raise ScanError(f"bad AC code at bit {pos}")
                rs, ln = hit
                pos += ln
                run, size = rs >> 4, rs & 15
                if size == 0:
                    if run == 15:
                        app(Symbol(0, 15, 0, 0, 0, c))
                        k += 16
                        continue
                    app(Symbol(0, 0, 0, 0, 1, c))
                    break
                v = int(bits[pos:pos + size], 2)
                pos += size
                k += run
                if k > 63:
                    raise ScanError(f"coefficient index overflow at bit {pos}")
                app(Symbol(0, run, size, bits_to_amp(v, size), 0, c))
                k += 1
    if pos > nb:
        raise ScanError("scan data truncated")
    return out


# ---- Restart intervals (used by mode E5: one MCU per interval) -----------------
RST = [bytes([0xFF, 0xD0 + i]) for i in range(8)]


def mcu_segments(symbols):
    """Split a coding-order symbol list into per-MCU lists (an MCU = 6 blocks)."""
    segs, cur, blocks = [], [], 0
    for s in symbols:
        if s.is_dc:
            if blocks == 6:
                segs.append(cur)
                cur, blocks = [], 0
            blocks += 1
        cur.append(s)
    if cur:
        segs.append(cur)
    return segs


def encode_segments(symbols):
    """Huffman-code each MCU separately (each padded to a byte with 1s and stuffed).
    Returns (list of segment bytes, payload bits before padding)."""
    out, total = [], 0
    for seg in mcu_segments(symbols):
        b, n = huffman_encode(seg)
        out.append(b)
        total += n
    return out, total


def join_restart(segments):
    """seg0 RST0 seg1 RST1 ... segN (markers numbered modulo 8, none after the last)."""
    parts = []
    for i, seg in enumerate(segments):
        if i:
            parts.append(RST[(i - 1) % 8])
        parts.append(seg)
    return b"".join(parts)


def split_restart(scan):
    """Inverse of join_restart. RST markers cannot occur inside stuffed data."""
    segs, start, i = [], 0, 0
    while True:
        j = scan.find(b"\xff", i)
        if j < 0 or j + 1 >= len(scan):
            break
        if 0xD0 <= scan[j + 1] <= 0xD7:
            segs.append(scan[start:j])
            start = i = j + 2
        else:
            i = j + 2
    segs.append(scan[start:])
    return segs
