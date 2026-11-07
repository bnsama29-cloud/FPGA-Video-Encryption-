"""Dummy-event padding (DESIGN §5).

Allowed only at V3 with ts_bits = 6 and at V4 (§5.1). Per 64 µs bucket of the packet:
    floor  (policy 1): pad to at least PAD_MIN CD words
    ladder (policy 2): pad to the smallest PAD_MIN * 2^k >= n_real; no padding above PAD_CAP
Every bucket of the packet gets a TIME_HIGH (inserted if absent); dummies go at the end of their bucket.

One K_dum keystream per packet, nonce (sid, ctr, 0), consumed in payload order: for the i-th CD word take one
mask bit m_i; if it is a dummy take 39 more bits (x: 16, y: 16, p: 1, ts: 6). After the last CD word take the
mask bits of the bitmap's zero padding. Bitmap bit i (LSB-first in each byte) = d_i XOR m_i.
"""
from dataclasses import dataclass

import numpy as np

from model import ascon

from .evt2 import CD_ON, TH_MASK, TIME_HIGH, cd_word, time_high
from .keys import nonce

NONE, FLOOR, LADDER = 0, 1, 2
MAX_CD_PAD = 131072


@dataclass(frozen=True)
class PadPolicy:
    kind: int
    pad_min: int
    pad_cap: int = 0
    max_cd: int = MAX_CD_PAD

    def __post_init__(self):
        if self.kind not in (FLOOR, LADDER):
            raise ValueError(f"PadPolicy.kind must be 1 (floor) or 2 (ladder), got {self.kind}")
        if self.pad_min < 1:
            raise ValueError("PadPolicy.pad_min must be >= 1")


class PadError(ValueError):
    pass


def check_allowed(level, ts_bits):
    """§5.1: padding only at V3 with ts_bits = 6, or at V4."""
    if not ((level == 3 and ts_bits == 6) or level == 4):
        raise PadError(f"padding is allowed only at V3 with ts_bits = 6 or at V4 (got V{level}, b = {ts_bits})")


def bucket_target(n_real, policy):
    if policy.kind == FLOOR:
        return max(n_real, policy.pad_min)
    if n_real > policy.pad_cap:
        return n_real
    t = policy.pad_min
    while t < n_real:
        t *= 2
    return t


def bucket_targets(n_real, policy):
    """bucket_target over an array of per-bucket counts (vectorised; equal to the scalar rule element by element)."""
    n = np.asarray(n_real, dtype=np.int64)
    if policy.kind == FLOOR:
        return np.maximum(n, policy.pad_min)
    k = np.ceil(np.log2(np.maximum(n, 1) / policy.pad_min)).clip(min=0).astype(np.int64)
    t = policy.pad_min * (1 << k)
    t = np.where(t < n, t * 2, t)                         # guard against log2 rounding just below an integer
    t = np.where((t // 2 >= n) & (t // 2 >= policy.pad_min), t // 2, t)
    return np.where(n > policy.pad_cap, n, t)


def _dummy_from(ks, W, H):
    x = (ks.take(16) * W) >> 16
    y = (ks.take(16) * H) >> 16
    p = ks.take(1)
    ts6 = ks.take(6)
    return cd_word(x, y, p, ts6)


def dummy_word(ks, geom):
    """Next dummy CD word from an open K_dum keystream (39 bits)."""
    return _dummy_from(ks, geom.W, geom.H)


def _buckets(words, t_start, T_us):
    """Split payload words into the T_us/64 buckets of the packet: list of (th_value, [words])."""
    th0 = t_start // 64
    nb = T_us // 64
    buckets = [[] for _ in range(nb)]
    cur = None
    for w in words:
        if (w >> 28) == TIME_HIGH:
            cur = (w & TH_MASK) - th0
            if not 0 <= cur < nb:
                raise ValueError(f"TIME_HIGH {w & TH_MASK} outside the packet's buckets")
        elif cur is None:
            raise ValueError("payload word before the first TIME_HIGH of a non-empty packet")
        buckets[cur].append(w)
    return th0, buckets


def pad_packet(words, policy, k_dum, sid, ctr, geom, t_start, T_us):
    """Insert TIME_HIGHs and dummies (§5.2-§5.3).

    Returns (words, masked_bitmap, n_dropped, dummy_mask): dummy_mask marks the dummy words, n_dropped counts
    real CD words dropped by the MAX_CD_PAD overflow (ERR_PADOVF).
    """
    th0, buckets = _buckets([int(w) for w in np.asarray(words, dtype=np.uint32)], t_start, T_us)
    ks = ascon.Keystream(k_dum, nonce(sid, ctr, 0))
    out, dmask, bits = [], [], []
    n_cd = n_dropped = 0
    full = False

    def emit_cd(w, is_dummy):
        m = ks.take(1)
        if is_dummy:
            w = _dummy_from(ks, geom.W, geom.H)
        out.append(w)
        dmask.append(is_dummy)
        bits.append(int(is_dummy) ^ m)

    for j, bw in enumerate(buckets):
        if not bw or (bw[0] >> 28) != TIME_HIGH:
            out.append(time_high(th0 + j))
            dmask.append(False)
        n_real = 0
        for w in bw:
            if (w >> 28) <= CD_ON:
                if n_cd >= policy.max_cd:
                    full = True
                    n_dropped += 1
                    continue
                emit_cd(w, False)
                n_cd += 1
                n_real += 1
            else:
                out.append(w)
                dmask.append(False)
        if full:
            continue
        for _ in range(bucket_target(n_real, policy) - n_real):
            if n_cd >= policy.max_cd:
                full = True
                break
            emit_cd(None, True)
            n_cd += 1
    pad_bits = (-n_cd) % 32
    bits.extend(ks.take(1) for _ in range(pad_bits))
    bm = bytearray(len(bits) // 8)
    for i, b in enumerate(bits):
        bm[i >> 3] |= b << (i & 7)
    return (np.array(out, dtype=np.uint32), bytes(bm), n_dropped, np.array(dmask, dtype=bool))


class StripError(ValueError):
    """Padding is not authentic or not conforming (receiver status `policy`)."""


def strip(words, masked_bitmap, k_dum, sid, ctr, geom, policy, t_start, T_us):
    """Receiver side of §5.3: returns (real words, dummy_mask). Raises StripError on any mismatch."""
    w = [int(v) for v in np.asarray(words, dtype=np.uint32)]
    ks = ascon.Keystream(k_dum, nonce(sid, ctr, 0))
    keep, dmask = [], []
    i = 0
    for v in w:
        if (v >> 28) <= CD_ON:
            if (i >> 3) >= len(masked_bitmap):
                raise StripError("bitmap shorter than the CD word count")
            d = ((masked_bitmap[i >> 3] >> (i & 7)) & 1) ^ ks.take(1)
            i += 1
            if d:
                if v != _dummy_from(ks, geom.W, geom.H):
                    raise StripError(f"dummy at CD index {i - 1} does not match its keystream")
                dmask.append(True)
                continue
        keep.append(v)
        dmask.append(False)
    for k in range(i, 8 * len(masked_bitmap)):
        if ((masked_bitmap[k >> 3] >> (k & 7)) & 1) != ks.take(1):
            raise StripError("bitmap padding bits are not the masked zeros")
    # conformance: every bucket opens with its TIME_HIGH and holds the CD count the policy requires
    th0, nb = t_start // 64, T_us // 64
    seen = [False] * nb
    n_all, n_real = [0] * nb, [0] * nb
    cur = None
    for k, v in enumerate(w):
        if (v >> 28) == TIME_HIGH:
            cur = (v & TH_MASK) - th0
            if not 0 <= cur < nb:
                raise StripError(f"TIME_HIGH {v & TH_MASK} outside the packet's buckets")
            seen[cur] = True
        elif cur is None:
            raise StripError("payload word before the first TIME_HIGH")
        elif (v >> 28) <= CD_ON:
            n_all[cur] += 1
            n_real[cur] += not dmask[k]
    total = 0
    for j in range(nb):
        if not seen[j]:
            raise StripError(f"bucket {j} has no TIME_HIGH")
        total += n_all[j]
        if total >= policy.max_cd:          # MAX_CD_PAD overflow: the rest of the packet is not padded
            break
        if n_all[j] != bucket_target(n_real[j], policy):
            raise StripError(f"bucket {j}: {n_all[j]} CD words, policy wants {bucket_target(n_real[j], policy)}")
    return np.array(keep, dtype=np.uint32), np.array(dmask, dtype=bool)
