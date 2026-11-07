"""Du et al. 2021 event encryption (Sensors 21:4320, §4), as specified in docs/neuro/BASELINES.md §1.

    key = DuKey.from_seed(b"...")                    # 306-bit key: x0, y0, H (52 bits each), G1..G6 (25 bits)
    enc = encrypt(events, W, H, key)                 # same t, scrambled (x, y), flipped p
    dec = decrypt(enc, W, H, key)                    # exact inverse
    encrypt(..., ascon_keyed=True, ascon_key=k)      # "Ascon-keyed Du" (N7/N9 only)

Per event (W = M, H = N), Algorithm 1: two position rounds with r1..r4, then two rank maps with r5 (length 2N)
and r6 (length 2M) that move y (then x) together with the polarity. Sequences are renewed every
`update_every(W, H)` events (updating score > threshold, eq. 12).
"""
import hashlib
import math
from dataclasses import dataclass

import numpy as np

from model import ascon

A, B = 1.0, 5.0                      # 2D-SIMM parameters (p. 7)
K_PI = 36_694_061                    # Raspberry Pi 4B processing speed (Table 3)
THRESHOLD = 8.4                      # updating-score threshold [choice, BASELINES §1.3]
SCALE = 10 ** 14                     # real -> integer [choice, BASELINES §1.1]


@dataclass(frozen=True)
class DuKey:
    x0: int        # 52-bit fractions
    y0: int
    h: int
    g: tuple       # six 25-bit integers

    @classmethod
    def from_seed(cls, seed: bytes):
        d = hashlib.sha512(b"du2021-key" + bytes(seed)).digest()
        v = int.from_bytes(d, "big")
        f = []
        for bits in (52, 52, 52) + (25,) * 6:
            f.append(v & ((1 << bits) - 1))
            v >>= bits
        return cls(f[0], f[1], f[2], tuple(f[3:]))

    def bits(self):
        return 3 * 52 + 6 * 25


def simm(x, y, n):
    """n iterates (x_1..x_n) of the 2D-SIMM map from (x, y) (eq. 6), x component."""
    out = np.empty(n)
    for i in range(n):
        x = A * math.sin(math.pi * y) * math.sin(B / x if x != 0 else B / 1e-300)
        y = A * math.sin(math.pi * x) * math.sin(B / y if y != 0 else B / 1e-300)
        out[i] = x
    return out


def sequences(key: DuKey, W, H, update=0):
    """(r1, r2, r3, r4 as integer shifts; r5, r6 as reals) for update index `update`."""
    lens = (W, H, W, H, 2 * H, 2 * W)
    mods = (H, W, H, W, None, None)
    out = []
    x0, y0, hh = key.x0 / 2 ** 52, key.y0 / 2 ** 52, key.h / 2 ** 52
    for k in range(6):
        g = key.g[k]
        xs, ys = (x0 + g * hh) % 1.0, (y0 + g * hh) % 1.0
        n = lens[k]
        v = simm(xs, ys, n * (update + 1))[n * update:]
        if mods[k] is None:
            out.append(v)
        else:
            out.append((np.floor(np.abs(v) * SCALE).astype(np.int64)) % mods[k])
    return out


def ascon_sequences(k: bytes, W, H, update=0):
    lens = (W, H, W, H, 2 * H, 2 * W)
    mods = (H, W, H, W, 1 << 32, 1 << 32)
    nonce = ascon.make_nonce(0xD0D0, update, 0)
    ks = ascon.Keystream(k, nonce)
    return [np.array([ks.take(32) % m for _ in range(n)], dtype=np.int64) for n, m in zip(lens, mods)]


def update_every(W, H, threshold=THRESHOLD, K=K_PI):
    """Events between updates: smallest L with log10(L / (W H) * K) > threshold."""
    return max(1, int(math.floor(10 ** threshold * W * H / K)) + 1)


def _ranks(r):
    """S[i] = position of r[i] in sorted order (stable)."""
    s = np.empty(len(r), dtype=np.int64)
    s[np.argsort(r, kind="stable")] = np.arange(len(r))
    return s


def _segments(n, every):
    return [(s, min(n, s + every)) for s in range(0, n, every)]


def _seqs(key, W, H, u, ascon_keyed, ascon_key):
    return ascon_sequences(ascon_key, W, H, u) if ascon_keyed else sequences(key, W, H, u)


def encrypt(events, W, H, key=None, ascon_keyed=False, ascon_key=None, every=None):
    ev = np.array(events, copy=True)
    every = every or update_every(W, H)
    for u, (s, e) in enumerate(_segments(len(ev), every)):
        r1, r2, r3, r4, r5, r6 = _seqs(key, W, H, u, ascon_keyed, ascon_key)
        S5, S6 = _ranks(r5), _ranks(r6)
        x = ev["x"][s:e].astype(np.int64)
        y = ev["y"][s:e].astype(np.int64)
        p = ev["p"][s:e].astype(np.int64)
        y = (y + r1[x]) % H
        x = (x + r2[y]) % W
        y = (y + r3[x]) % H
        x = (x + r4[y]) % W
        v = S5[p * H + y]
        pt, y = v // H, v % H
        q = S6[pt * W + x]
        p, x = q // W, q % W
        ev["x"][s:e], ev["y"][s:e], ev["p"][s:e] = x, y, p
    return ev


def decrypt(events, W, H, key=None, ascon_keyed=False, ascon_key=None, every=None):
    ev = np.array(events, copy=True)
    every = every or update_every(W, H)
    for u, (s, e) in enumerate(_segments(len(ev), every)):
        r1, r2, r3, r4, r5, r6 = _seqs(key, W, H, u, ascon_keyed, ascon_key)
        I5, I6 = np.argsort(r5, kind="stable"), np.argsort(r6, kind="stable")      # inverse rank maps
        x = ev["x"][s:e].astype(np.int64)
        y = ev["y"][s:e].astype(np.int64)
        p = ev["p"][s:e].astype(np.int64)
        q = I6[p * W + x]
        pt, x = q // W, q % W
        v = I5[pt * H + y]
        p, y = v // H, v % H
        x = (x - r4[y]) % W
        y = (y - r3[x]) % H
        x = (x - r2[y]) % W
        y = (y - r1[x]) % H
        ev["x"][s:e], ev["y"][s:e], ev["p"][s:e] = x, y, p
    return ev
