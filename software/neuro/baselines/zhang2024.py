"""Zhang, Zhu, Lam 2024 event encryption (Neuromorph. Comput. Eng. 4:014002, §3.2), per docs/neuro/BASELINES.md §2.

    enc, key = encrypt(events, W, H, k)      # original events + synthetic noise filling every empty pixel,
                                             # polarity XOR (szudzik(x, y) mod 2) on all events
    dec = decrypt(enc, key, W)               # keeps the events at the key's pixels, undoes the polarity map

Recursive fill (Algorithm 1): pixels with events are processed first, in order of first occurrence; each pixel's
4-neighbours still in the mask receive |E_c| noise events (random p, t = t0 + (t_i - t0)(1 + sigma)) and join the
queue; stops when the mask is empty. The random polarities come from an Ascon keystream under k [choice].
"""
from collections import deque

import numpy as np

from model import ascon

from ..evt2 import EVENT_DTYPE

SIGMA = 0.05


def szudzik(x, y):
    x = np.asarray(x, dtype=np.int64)
    y = np.asarray(y, dtype=np.int64)
    return np.where(x >= y, x * x + x + y, y * y + x)


def encrypt(events, W, H, k: bytes, sigma=SIGMA):
    """Returns (encrypted events sorted by t, key = sorted pixel indices of Ex)."""
    ev = np.asarray(events)
    if len(ev) == 0:
        return ev.copy(), np.zeros(0, np.int64)
    t0 = int(ev["t"].min())
    pix = ev["y"].astype(np.int64) * W + ev["x"]
    order, first = np.unique(pix, return_index=True)
    ex = order[np.argsort(first)]                       # pixels in order of first occurrence
    srt = np.argsort(pix, kind="stable")
    bounds = np.searchsorted(pix[srt], ex)
    ends = np.searchsorted(pix[srt], ex, side="right")
    times = {int(p): ev["t"][srt[b:e]].astype(np.int64) for p, b, e in zip(ex, bounds, ends)}
    mask = np.ones(W * H, dtype=bool)
    mask[ex] = False
    left = int(mask.sum())
    ks = ascon.Keystream(k, ascon.make_nonce(0x2A2A, 0, 0))
    q = deque(int(p) for p in ex)
    nt, nx, ny = [], [], []
    while q and left:
        p = q.popleft()
        x, y = p % W, p // W
        tc = times[p]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = x + dx, y + dy
            if not (0 <= xx < W and 0 <= yy < H):
                continue
            r = yy * W + xx
            if not mask[r]:
                continue
            mask[r] = False
            left -= 1
            tn = t0 + np.round((tc - t0) * (1 + sigma)).astype(np.int64)
            times[r] = tn
            nt.append(tn)
            nx.append(np.full(len(tn), xx))
            ny.append(np.full(len(tn), yy))
            q.append(r)
    n_noise = sum(len(a) for a in nt)
    noise = np.zeros(n_noise, dtype=EVENT_DTYPE)
    if n_noise:
        noise["t"] = np.concatenate(nt)
        noise["x"] = np.concatenate(nx)
        noise["y"] = np.concatenate(ny)
        raw = np.frombuffer(b"".join(ks.next_block() for _ in range((n_noise + 127) // 128)), dtype=np.uint8)
        noise["p"] = np.unpackbits(raw, bitorder="little")[:n_noise]
    out = np.concatenate([np.asarray(ev, dtype=EVENT_DTYPE), noise])
    out["p"] ^= (szudzik(out["x"], out["y"]) & 1).astype(out["p"].dtype)
    out = out[np.argsort(out["t"], kind="stable")]
    return out, np.sort(ex)


def _pix(ev, W):
    return ev["y"].astype(np.int64) * W + ev["x"]


def decrypt(events, key, W):
    """Keep the events at the key's pixels and undo the polarity map (order and timestamps unchanged)."""
    ev = np.array(events, copy=True)
    ev = ev[np.isin(_pix(ev, W), key)]
    ev["p"] ^= (szudzik(ev["x"], ev["y"]) & 1).astype(ev["p"].dtype)
    return ev


def key_bytes(key, k: bytes):
    """rho(szudzik(Ex)) with rho = Ascon-AEAD128 [choice]: the key material the receiver needs (size in N9)."""
    data = np.asarray(key, dtype="<u4").tobytes()
    return ascon.encrypt(k, ascon.make_nonce(0x2A2A, 1, 0), b"", data)
