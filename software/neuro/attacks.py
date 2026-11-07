"""Attacks on protected event streams (DESIGN §1.3, §1.4, §7.1).

Active attacks work on lists of packet byte strings (ours) and return a new list; the same functions apply
to the Du/Zhang baselines, which carry no tag. Passive helpers turn (possibly protected) events into the
pictures an eavesdropper would look at.
"""
import struct

import numpy as np

from .packet import HEADER_LEN, PacketHeader

# ------------------------------------------------------------------ active (packet lists)


def inject(packets, at, forged):
    """Insert a forged packet (bytes) before index at."""
    return packets[:at] + [bytes(forged)] + packets[at:]


def replay(packets, src, at):
    """Insert a copy of packets[src] before index at."""
    return packets[:at] + [packets[src]] + packets[at:]


def delete(packets, idx):
    return [p for i, p in enumerate(packets) if i not in set(np.atleast_1d(idx).tolist())]


def delete_tail(packets, n):
    """Drop the last n packets (e.g. the FINAL packet): the receiver must report `truncated`."""
    return packets[:len(packets) - n]


def reorder(packets, i, j):
    out = list(packets)
    out[i], out[j] = out[j], out[i]
    return out


def flip_bit(pkt, byte, bit=0):
    b = bytearray(pkt)
    b[byte] ^= 1 << bit
    return bytes(b)


def splice(a, b, cut=None):
    """First part of packet a + rest of packet b (same length framing assumed)."""
    cut = len(a) // 2 if cut is None else cut
    return bytes(a[:cut]) + bytes(b[cut:])


def set_header_field(pkt, **fields):
    """Rewrite header fields (no re-tag): downgrade (level), epoch jump (session_id), counter changes."""
    h = PacketHeader.unpack(pkt)
    d = {k: getattr(h, k) for k in ("level", "flags", "ts_bits", "session_id", "packet_ctr", "t_start", "W", "H",
                                     "T_us", "pad_policy", "link", "rounds", "version", "magic")}
    d.update(fields)
    return PacketHeader(**d).pack() + bytes(pkt[HEADER_LEN:])


def downgrade(pkt, level=0):
    return set_header_field(pkt, level=level)


def epoch_jump(pkt, delta=0xFFFF):
    h = PacketHeader.unpack(pkt)
    sid = (h.session_id & ~0xFFFF) | ((h.session_id + delta) & 0xFFFF)
    return set_header_field(pkt, session_id=sid)


def flood(n, length=128, seed=0):
    """n junk datagrams of random bytes (some start with a valid-looking magic)."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        b = bytearray(rng.integers(0, 256, length, dtype=np.uint8).tobytes())
        if i % 2 == 0:
            b[0:4] = b"NVE1"
            b[4], b[38] = 1, 8
        out.append(bytes(b))
    return out


# ------------------------------------------------------------------ passive helpers (events -> pictures)
def polarity_collapse(events):
    ev = np.array(events, copy=True)
    ev["p"] = 1
    return ev


def event_count_frame(events, geom):
    img = np.zeros((geom.H, geom.W), dtype=np.float64)
    np.add.at(img, (np.asarray(events["y"], int), np.asarray(events["x"], int)), 1.0)
    return img


def time_surface(events, geom, tau_us=50_000.0):
    """Exponential time surface at the time of the last event (latest event per pixel)."""
    ts = np.full((geom.H, geom.W), -np.inf)
    if len(events) == 0:
        return np.zeros((geom.H, geom.W))
    t = np.asarray(events["t"], dtype=np.float64)
    np.maximum.at(ts, (np.asarray(events["y"], int), np.asarray(events["x"], int)), t)
    return np.exp((ts - t.max()) / tau_us)


def adjacency_embed(events, dt_us=20, k=8, geom=None):
    """N4b: k-NN co-activation graph over (permuted) addresses + 2-D Laplacian eigenmap.

    Returns (addresses (n, 2) int, embedding (n, 2) float). Pixels that fire within dt_us of each other are
    linked; the embedding is the second and third eigenvectors of the normalised graph Laplacian.
    """
    ev = np.asarray(events)
    if len(ev) == 0:
        return np.zeros((0, 2), int), np.zeros((0, 2))
    addr = np.stack([ev["x"].astype(np.int64), ev["y"].astype(np.int64)], 1)
    uniq, inv = np.unique(addr, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    n = len(uniq)
    if n < 4:
        return uniq, np.zeros((n, 2))
    order = np.argsort(ev["t"], kind="stable")
    t = ev["t"][order].astype(np.int64)
    a = inv[order]
    Wm = np.zeros((n, n))
    j0 = 0
    for i in range(len(t)):
        while t[i] - t[j0] > dt_us:
            j0 += 1
        for j in range(max(j0, i - k), i):
            if a[i] != a[j]:
                Wm[a[i], a[j]] += 1
                Wm[a[j], a[i]] += 1
    d = Wm.sum(1)
    d[d == 0] = 1
    Dm = 1 / np.sqrt(d)
    Lsym = np.eye(n) - (Dm[:, None] * Wm * Dm[None, :])
    vals, vecs = np.linalg.eigh(Lsym)
    return uniq, vecs[:, 1:3] * Dm[:, None]


def procrustes_error(true_xy, emb):
    """Align emb to true_xy (rotation, reflection, scale, shift); return normalised RMS error in [0, 1]."""
    A = np.asarray(true_xy, float)
    B = np.asarray(emb, float)
    A = A - A.mean(0)
    B = B - B.mean(0)
    na, nb = np.linalg.norm(A), np.linalg.norm(B)
    if na == 0 or nb == 0:
        return 1.0
    A, B = A / na, B / nb
    U, s, Vt = np.linalg.svd(B.T @ A)
    return float(np.sqrt(max(0.0, 1 - s.sum() ** 2)))


def neighbour_recovery(true_xy, emb):
    """Fraction of true 4-neighbour pairs that are mutual nearest neighbours in the embedding."""
    A = np.asarray(true_xy, int)
    n = len(A)
    if n < 2:
        return 0.0
    idx = {tuple(p): i for i, p in enumerate(A.tolist())}
    pairs = [(i, idx[(x + 1, y)]) for i, (x, y) in enumerate(A.tolist()) if (x + 1, y) in idx]
    pairs += [(i, idx[(x, y + 1)]) for i, (x, y) in enumerate(A.tolist()) if (x, y + 1) in idx]
    if not pairs:
        return 0.0
    E = np.asarray(emb, float)
    d = ((E[:, None, :] - E[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d, np.inf)
    nn = d.argsort(1)[:, :4]
    hit = sum(1 for i, j in pairs if j in nn[i] or i in nn[j])
    return hit / len(pairs)
