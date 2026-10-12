"""8x8 forward DCT (fixed-point, HLS-friendly) and the quantiser.

DCT definition (bit-exact contract for the Vitis HLS block):
    x      = sample - 128                         (level shift, int)
    T[u,x] = round(4096 * c(u) * cos((2x+1) u pi / 16)),
             c(0) = sqrt(1/8), c(u>0) = sqrt(2/8)  (12-bit fixed-point matrix)
    P      = T . X . T^T                          (exact integer, fits in 40 bits)
    F      = sign(P) * ((|P| + 2^23) >> 24)       (round half away from zero)
F is a 16-bit signed coefficient in row-major order (coefficient stream contract).

Quantiser:
    q = sign(F) * ((|F| + (Q >> 1)) // Q)         (round half away from zero)

Quantisation tables are the JPEG Annex K tables scaled with the libjpeg quality
formula. Tables here are in natural (row-major) order; DQT stores them zig-zag.
"""
import numpy as np


def _dct_matrix():
    T = np.zeros((8, 8))
    for u in range(8):
        c = np.sqrt(1 / 8) if u == 0 else np.sqrt(2 / 8)
        for x in range(8):
            T[u, x] = c * np.cos((2 * x + 1) * u * np.pi / 16)
    return np.round(T * 4096).astype(np.int64)


T_INT = _dct_matrix()                 # export to HLS as a constant ROM
DCT_SHIFT = 24


def fdct(blocks):
    """blocks: (..., 8, 8) unsigned samples 0..255 -> (..., 8, 8) int32 coefficients."""
    X = blocks.astype(np.int64) - 128
    P = T_INT @ X @ T_INT.T
    mag = (np.abs(P) + (1 << (DCT_SHIFT - 1))) >> DCT_SHIFT
    return (np.sign(P) * mag).astype(np.int32)


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


def quantise(coeffs, table):
    """Accepts a flat block of 64 (with any 8x8 or 64-entry table) or (...,8,8) arrays."""
    c = np.asarray(coeffs, dtype=np.int64)
    q = np.asarray(table, dtype=np.int64)
    if c.shape[-1] == 64 and q.size == 64:
        q = q.reshape(64)
    mag = (np.abs(c) + (q >> 1)) // q
    return (np.sign(c) * mag).astype(np.int32)
