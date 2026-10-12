"""8x8 forward DCT and quantiser: bit-exact with rtl/dct8x8.v and rtl/quantiser.v.

DCT (contract v2 = the arithmetic the RTL and the HLS block implement):
    C[u][x] = round(2^13 * c(u)/2 * cos((2x+1) u pi / 16)),  c(0)=1/sqrt(2), c(u>0)=1
    pass 1 on the rows of (sample - 128):  A[u][y] = (sum_x C[u][x] X[y][x] + 2^10) >> 11
    pass 2 on the rows of A:               F[v][u] = (sum_y C[v][y] A[u][y] + 2^14) >> 15
    (>> = arithmetic shift, i.e. floor). F is a 16-bit signed coefficient, row-major.
    Each pass is one rtl/dct_stage.v (8 multiply-accumulates, output transposed).

Quantiser (one DSP multiply instead of a divider):
    R = round(65536 / Q) = (131072 + Q) // (2Q)          17-bit reciprocal
    q = sign(F) * ((|F| * R + 2^15) >> 16)
    DC clamped to -1024..1023, AC to -1023..1023.

Contract v1 used a one-pass 12-bit DCT and a true division; about 6% of the
coefficients differed by 1 from the RTL, so v1 could not check the hardware.

Quantisation tables are the JPEG Annex K tables scaled with the libjpeg quality
formula. Tables here are in natural (row-major) order; DQT stores them zig-zag.
"""
import math

import numpy as np

DCT_SCALE_BITS = 13
STAGE1_SHIFT, STAGE2_SHIFT = 11, 15


def _dct_coeff(u, x):
    cu = 1 / math.sqrt(2) if u == 0 else 1.0
    return int(math.floor((1 << DCT_SCALE_BITS) * cu / 2 * math.cos((2 * x + 1) * u * math.pi / 16) + 0.5))


DCT_C = np.array([[_dct_coeff(u, x) for x in range(8)] for u in range(8)], dtype=np.int64)


def fdct(blocks):
    """blocks: (..., 8, 8) unsigned samples 0..255 -> (..., 8, 8) int32 coefficients F[v, u]."""
    X = np.asarray(blocks, dtype=np.int64) - 128
    A = (np.einsum("ux,...yx->...uy", DCT_C, X) + (1 << (STAGE1_SHIFT - 1))) >> STAGE1_SHIFT
    F = (np.einsum("vy,...uy->...vu", DCT_C, A) + (1 << (STAGE2_SHIFT - 1))) >> STAGE2_SHIFT
    return F.astype(np.int32)


BASE_LUMA = np.array([
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99]).reshape(8, 8)

BASE_CHROMA = np.array([
    17, 18, 24, 47, 99, 99, 99, 99,
    18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99]).reshape(8, 8)

DEFAULT_QUALITY = 75


def scale_table(base, quality):
    quality = int(min(max(quality, 1), 100))
    scale = 5000 // quality if quality < 50 else 200 - 2 * quality
    return np.clip((base * scale + 50) // 100, 1, 255).astype(np.int32)


def tables(quality=DEFAULT_QUALITY):
    return scale_table(BASE_LUMA, quality), scale_table(BASE_CHROMA, quality)


Q_LUMA, Q_CHROMA = tables(DEFAULT_QUALITY)


def reciprocal(q):
    """17-bit reciprocal R = round(65536 / Q) loaded into rtl/quantiser.v (QT_DATA)."""
    q = np.asarray(q, dtype=np.int64)
    return (131072 + q) // (2 * q)


def quantise(coeffs, table):
    """Bit-exact rtl/quantiser.v. table = quantisation steps Q (not reciprocals).

    Accepts a flat block of 64 (with any 8x8 or 64-entry table) or (..., 8, 8) arrays."""
    c = np.asarray(coeffs, dtype=np.int64)
    q = np.asarray(table, dtype=np.int64)
    if c.shape[-1] == 64 and q.size == 64:
        q = q.reshape(64)
    m = (np.abs(c) * reciprocal(q) + (1 << 15)) >> 16
    out = np.sign(c) * m
    lo = np.full(out.shape, -1023, dtype=np.int64)
    if c.shape[-1] == 64:
        lo[..., 0] = -1024
    else:
        lo[..., 0, 0] = -1024
    return np.clip(out, lo, 1023).astype(np.int32)
