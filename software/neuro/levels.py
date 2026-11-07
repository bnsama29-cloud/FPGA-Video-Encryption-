"""Protection levels V0-V4 on the payload of one packet (DESIGN §4.1, §4.2, §4.5, §4.6).

V0  tag only
V1  polarity (word bit 28) XOR keystream bit 0 of each real CD word
V2  (x, y) of each real CD word through the packet's Feistel permutation P_ctr
V3  V2 + polarity XOR k0 + ts[i] XOR k(1+i), i < b
V4  Ascon-AEAD128 of payload || trailer (done in neuro.packet / neuro.sender, not here)

Only real CD words are changed: TIME_HIGH, EXT_TRIGGER, OTHERS, CONTINUED, reserved words and padding
dummies pass unchanged and consume no keystream. Keystream K_pol restarts in every packet; each real CD word
takes 1 + b bits in payload order (b = 0 at V1), bit 0 = first bit handed out.
"""
import numpy as np

from model import ascon

from .evt2 import is_cd
from .feistel import permute, unpermute
from .keys import nonce

V0, V1, V2, V3, V4 = 0, 1, 2, 3, 4
XOR_LEVELS = (V1, V3)
PERM_LEVELS = (V2, V3)


def ks_bits_per_word(level, b):
    if level == V1:
        return 1
    if level == V3:
        return 1 + b
    return 0


def xor_mask(k, b):
    """Word mask for one CD word from its 1 + b keystream bits k (§4.2)."""
    return ((k & 1) << 28) | (((k >> 1) & ((1 << b) - 1)) << 22)


def xor_fields(words, cd_mask, ks, b):
    """XOR p (and ts[b-1:0]) of the words selected by cd_mask, taking 1 + b bits per selected word, in order."""
    out = np.asarray(words, dtype=np.uint32).copy()
    for i in np.nonzero(cd_mask)[0]:
        out[i] ^= np.uint32(xor_mask(ks.take(1 + b), b))
    return out


def permute_words(words, cd_mask, tables, inverse=False):
    out = np.asarray(words, dtype=np.uint32).copy()
    idx = np.nonzero(cd_mask)[0]
    if len(idx) == 0:
        return out
    w = out[idx]
    x = ((w >> np.uint32(11)) & np.uint32(0x7FF)).astype(np.int64)
    y = (w & np.uint32(0x7FF)).astype(np.int64)
    x2, y2 = (unpermute if inverse else permute)(x, y, tables)
    out[idx] = (w & np.uint32(0xFFC00000)) | (x2.astype(np.uint32) << np.uint32(11)) | y2.astype(np.uint32)
    return out


def real_cd_mask(words, dummy_mask=None):
    m = is_cd(words)
    if dummy_mask is not None:
        m &= ~np.asarray(dummy_mask, dtype=bool)
    return m


def protect(words, level, b, tables, k_pol, sid, ctr, dummy_mask=None):
    """Apply level V0-V3 to one packet's payload words. tables: neuro.feistel.Tables or None (V0/V1)."""
    if level not in (V0, V1, V2, V3):
        raise ValueError(f"protect: level {level} is not a word-level (V0-V3) protection")
    w = np.asarray(words, dtype=np.uint32).copy()
    m = real_cd_mask(w, dummy_mask)
    if level in XOR_LEVELS:
        bb = 0 if level == V1 else b
        w = xor_fields(w, m, ascon.Keystream(k_pol, nonce(sid, ctr, 0)), bb)
    if level in PERM_LEVELS:
        w = permute_words(w, m, tables)
    return w


def unprotect(words, level, b, tables, k_pol, sid, ctr, dummy_mask=None):
    """Exact inverse of protect (XOR is an involution; the permutation is inverted)."""
    if level not in (V0, V1, V2, V3):
        raise ValueError(f"unprotect: level {level} is not a word-level (V0-V3) protection")
    w = np.asarray(words, dtype=np.uint32).copy()
    m = real_cd_mask(w, dummy_mask)
    if level in PERM_LEVELS:
        w = permute_words(w, m, tables, inverse=True)
    if level in XOR_LEVELS:
        bb = 0 if level == V1 else b
        w = xor_fields(w, m, ascon.Keystream(k_pol, nonce(sid, ctr, 0)), bb)
    return w
