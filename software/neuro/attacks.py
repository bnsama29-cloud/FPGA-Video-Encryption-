"""Attacks on protected event streams (DESIGN §1.3, §1.4, §7.1).

Active attacks work on lists of packet byte strings (ours) and return a new list; the same functions apply
to the Du/Zhang baselines, which carry no tag. Passive helpers turn (possibly protected) events into the
pictures an eavesdropper would look at.
"""
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


DENSE_MAX = 1500        # above this many addresses the graph is built sparse


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
    # event i links to each of its k predecessors j with t[i] - t[j] <= dt_us (t is sorted), other pixel only
    rows, cols = [], []
    for lag in range(1, k + 1):
        ok = (t[lag:] - t[:-lag] <= dt_us) & (a[lag:] != a[:-lag])
        rows.append(a[lag:][ok])
        cols.append(a[:-lag][ok])
    r = np.concatenate(rows) if rows else np.zeros(0, np.int64)
    c = np.concatenate(cols) if cols else np.zeros(0, np.int64)
    if n <= DENSE_MAX:
        Wm = np.zeros((n, n))
        np.add.at(Wm, (r, c), 1.0)
        Wm = Wm + Wm.T
        d = Wm.sum(1)
        d[d == 0] = 1
        Dm = 1 / np.sqrt(d)
        vals, vecs = np.linalg.eigh(np.eye(n) - (Dm[:, None] * Wm * Dm[None, :]))
        return uniq, vecs[:, 1:3] * Dm[:, None]
    # large packets (e.g. Event-ReId at 640 x 480): sparse graph; the 2nd and 3rd smallest eigenvectors of the
    # normalised Laplacian are the 2nd and 3rd largest of the normalised adjacency D^-1/2 W D^-1/2
    from scipy import sparse
    from scipy.sparse.linalg import ArpackNoConvergence, eigsh
    Wm = sparse.coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)).tocsr()
    Wm = (Wm + Wm.T).tocsr()
    d = np.asarray(Wm.sum(1)).ravel()
    d[d == 0] = 1
    Dm = 1 / np.sqrt(d)
    A = sparse.diags(Dm) @ Wm @ sparse.diags(Dm)
    try:
        vals, vecs = eigsh(A, k=3, which="LA", tol=1e-6, maxiter=20 * n)
    except ArpackNoConvergence as e:
        vals, vecs = e.eigenvalues, e.eigenvectors
        if vecs.shape[1] < 3:
            return uniq, np.zeros((n, 2))
    o = np.argsort(vals)[::-1]
    return uniq, vecs[:, o[1:3]] * Dm[:, None]


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
    from scipy.spatial import cKDTree
    E = np.asarray(emb, float)
    m = min(5, n)
    _, nn = cKDTree(E).query(E, k=m)          # self + 4 nearest neighbours, O(n log n) memory
    nn = np.asarray(nn).reshape(n, m)
    sets = [set(row[row != i].tolist()) for i, row in enumerate(nn)]
    hit = sum(1 for i, j in pairs if j in sets[i] or i in sets[j])
    return hit / len(pairs)
