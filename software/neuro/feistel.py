"""V2/V3 position permutation: mixed-radix table Feistel on Z_W x Z_H (DESIGN §4.3).

Black-Rogaway "Method 3" with a = W, b = H: r = 8 rounds, round j adds a table value to one coordinate,
indexed by the other coordinate, modulo that coordinate's range:

    P_ctr(x, y):  for j in 0..7:  j even: x = (x + T_j[y]) mod W      j odd: y = (y + T_j[x]) mod H
    P_ctr^-1:     for j in 7..0:  j even: x = (x - T_j[y]) mod W      j odd: y = (y - T_j[x]) mod H

Tables come from Ascon keystream K_perm under nonce (sid, ctr, 0), restarted for every packet (§4.3.2):
T_0 first, entries in index order, each entry = (take(16) * M) >> 16 with M the modulus of that round.
Every output is in range, so there is no cycle walking (§4.3.4); `permute_walk` is the binary-domain variant
kept for the N2b ablation only. `shuffle_table` is the ideal-permutation control of §4.4.
"""
from dataclasses import dataclass

import numpy as np

from model import ascon

from .geometry import MIN_PERM_DIM
from .keys import nonce

ROUNDS = 8


@dataclass(frozen=True)
class Tables:
    W: int
    H: int
    r: int
    t: tuple          # r numpy int64 arrays; t[j] has H entries (values in Z_W) for even j, W entries (Z_H) for odd j


def _check_dims(W, H):
    if W < MIN_PERM_DIM or H < MIN_PERM_DIM:
        raise ValueError(f"V2/V3 need W, H >= {MIN_PERM_DIM} (DESIGN §2.3); got {W} x {H}")


def table_entries(ks, W, H, r=ROUNDS):
    """Draw the r tables from an open keystream, in fill order (also the RTL fill order)."""
    t = []
    for j in range(r):
        M, n = (W, H) if j % 2 == 0 else (H, W)
        t.append(np.array([(ks.take(16) * M) >> 16 for _ in range(n)], dtype=np.int64))
    return tuple(t)


def make_tables(k_perm, sid, ctr, W, H, r=ROUNDS):
    """Round tables of packet (sid, ctr) (§4.3.2). Raises for W or H below 16."""
    _check_dims(W, H)
    ks = ascon.Keystream(k_perm, nonce(sid, ctr, 0))
    return Tables(W, H, r, table_entries(ks, W, H, r))


def _xy(x, y):
    return np.asarray(x, dtype=np.int64).copy(), np.asarray(y, dtype=np.int64).copy()


def permute(x, y, tables):
    """P_ctr on arrays (or scalars) of coordinates; returns (x', y') as int64 arrays."""
    x, y = _xy(x, y)
    W, H = tables.W, tables.H
    for j in range(tables.r):
        if j % 2 == 0:
            x = (x + tables.t[j][y]) % W
        else:
            y = (y + tables.t[j][x]) % H
    return x, y


def unpermute(x, y, tables):
    """P_ctr^-1: exact inverse of permute with the same tables."""
    x, y = _xy(x, y)
    W, H = tables.W, tables.H
    for j in reversed(range(tables.r)):
        if j % 2 == 0:
            x = (x - tables.t[j][y]) % W
        else:
            y = (y - tables.t[j][x]) % H
    return x, y


def round_fn(x, y, j, tables):
    """One round j (the RTL stage view, neuro.hw.feistel_round)."""
    x, y = _xy(x, y)
    if j % 2 == 0:
        x = (x + tables.t[j][y]) % tables.W
    else:
        y = (y + tables.t[j][x]) % tables.H
    return x, y


# ------------------------------------------------------------------ ablation N2b: binary domain + cycle walking
def _bits(n):
    return max(1, (n - 1).bit_length())


def walk_tables(k_perm, sid, ctr, W, H, r=ROUNDS):
    """Tables of the balanced binary Feistel on 2*h bits, h = ceil(max(lg W, lg H)) (§4.3.4)."""
    _check_dims(W, H)
    h = max(_bits(W), _bits(H))
    ks = ascon.Keystream(k_perm, nonce(sid, ctr, 0))
    M = 1 << h
    t = tuple(np.array([(ks.take(16) * M) >> 16 for _ in range(M)], dtype=np.int64) for _ in range(r))
    return Tables(M, M, r, t), h


def permute_walk(x, y, k_perm, sid, ctr, W, H, r=ROUNDS, k_max=4):
    """Binary Feistel on (x, y) in Z_{2^h}^2, repeated while the result is outside W x H.

    Returns (x', y', calls): calls > k_max means the hardware would recirculate (counted, still exact).
    """
    tb, _ = walk_tables(k_perm, sid, ctr, W, H, r)
    x, y = _xy(x, y)
    calls = np.zeros(x.shape, dtype=np.int64)
    todo = np.ones(x.shape, dtype=bool)
    while todo.any():
        nx, ny = permute(x[todo], y[todo], tb)
        x[todo], y[todo] = nx, ny
        calls[todo] += 1
        todo = (x >= W) | (y >= H)
    return x, y, calls


def unpermute_walk(x, y, k_perm, sid, ctr, W, H, r=ROUNDS):
    tb, _ = walk_tables(k_perm, sid, ctr, W, H, r)
    x, y = _xy(x, y)
    todo = np.ones(x.shape, dtype=bool)
    while todo.any():
        nx, ny = unpermute(x[todo], y[todo], tb)
        x[todo], y[todo] = nx, ny
        todo = (x >= W) | (y >= H)
    return x, y


# ------------------------------------------------------------------ §4.4 ideal-permutation control
def shuffle_table(k_perm, sid, ctr, W, H):
    """Uniform random permutation of the W*H addresses (Knuth shuffle, rejection sampling on the keystream).

    Returns perm with perm[y*W + x] = y'*W + x'. Model only (control in N3, N4b, N8).
    """
    n = W * H
    ks = ascon.Keystream(k_perm, nonce(sid, ctr, 0))
    perm = np.arange(n, dtype=np.int64)
    for i in range(n - 1, 0, -1):
        nb = i.bit_length()
        while True:
            j = ks.take(nb)
            if j <= i:
                break
        perm[i], perm[j] = perm[j], perm[i]
    return perm
