"""Stronger jigsaw solver for the E5 attack (GUIDE B9): minimum spanning tree over Mahalanobis gradient
compatibility, in the style of Gallagher (CVPR 2012, "Jigsaw puzzles with pieces of unknown orientation";
here orientation is known).

  compatibility  MGC: the colour gradient ACROSS a border should look like the gradients just INSIDE
                 each tile's border. For tile i on the left of tile j:
                   inside gradients of i: g = p_i[:, -1] - p_i[:, -2] (one RGB vector per row), mean mu_i,
                   covariance S_i (regularised); the step across the border d = p_j[:, 0] - p_i[:, -1];
                   D(i -> j) = sum over rows of (d - mu_i) S_i^-1 (d - mu_i)^T, plus the same from j's side.
                 Each cost is divided by the second-smallest cost of its row (confidence), as in Gallagher.
  assembly       Kruskal: take candidate (i, j, direction) pairs in order of cost; join their clusters
                 when the relative placement makes no two tiles collide and the joint bounding box still
                 fits the frame (rows x cols). Tiles left over (clusters that could not be joined) are put
                 into the empty slots greedily, best compatibility with the slot's placed neighbours first.
Gate (tests/test_future_work.py): on unencrypted shuffled tiles it must beat the greedy solver of
jigsaw_attack.py before its E5 numbers count.
"""
import numpy as np


def _mgc_side(a_in, a_edge, b_edge, eps=1e-6):
    """a_in, a_edge: (n, T, C) second-to-last and last line of every tile on the joining side;
    b_edge: (n, T, C) first line of every candidate neighbour. Returns D[i, j] (n x n)."""
    n, t, c = a_edge.shape
    g = a_edge - a_in                                            # inside gradients (n, T, C)
    dummy = np.array([[0, 0, 0], [1, 1, 1], [-1, -1, -1], [0, 0, 1], [0, 1, 0], [1, 0, 0],
                      [-1, 0, 0], [0, -1, 0], [0, 0, -1]], float)[:, :c]   # Gallagher's regulariser
    mu = g.mean(axis=1)                                          # (n, C)
    gd = np.concatenate([g, np.broadcast_to(dummy, (n,) + dummy.shape)], axis=1)
    cov = np.einsum("nti,ntj->nij", gd - gd.mean(1, keepdims=True), gd - gd.mean(1, keepdims=True)) / (gd.shape[1] - 1)
    inv = np.linalg.inv(cov + eps * np.eye(c))                   # (n, C, C)
    d = b_edge[None, :, :, :] - a_edge[:, None, :, :]            # (n, n, T, C): step across the border
    x = d - mu[:, None, None, :]
    return np.einsum("ijtc,icd,ijtd->ij", x, inv, x)


def mgc(tiles):
    """D_lr[i, j]: j right of i; D_tb[i, j]: j below i (symmetric MGC, confidence-normalised)."""
    lr = _mgc_side(tiles[:, :, -2], tiles[:, :, -1], tiles[:, :, 0]) + \
        _mgc_side(tiles[:, :, 1], tiles[:, :, 0], tiles[:, :, -1]).T
    tb = _mgc_side(tiles[:, -2], tiles[:, -1], tiles[:, 0]) + _mgc_side(tiles[:, 1], tiles[:, 0], tiles[:, -1]).T
    for m in (lr, tb):
        np.fill_diagonal(m, np.inf)
    norm = lambda m: m / (np.partition(m, 1, axis=1)[:, 1:2] + 1e-9)
    return norm(lr), norm(tb)


def solve(tiles, rows, cols):
    """Returns placement[pos] = tile index (raster positions), like jigsaw_attack.solve."""
    n = len(tiles)
    lr, tb = mgc(tiles)
    cand = [(lr[i, j], i, j, 0, 1) for i in range(n) for j in range(n) if i != j] + \
           [(tb[i, j], i, j, 1, 0) for i in range(n) for j in range(n) if i != j]
    cand.sort(key=lambda e: e[0])
    owner = list(range(n))                                       # cluster id of each tile
    members = {i: {i: (0, 0)} for i in range(n)}                 # cluster -> {tile: (r, c)}
    for _, i, j, dr, dc in cand:
        a, b = owner[i], owner[j]
        if a == b:
            continue
        ri, ci = members[a][i]
        rj, cj = members[b][j]
        off = (ri + dr - rj, ci + dc - cj)                       # shift of b's frame that puts j next to i
        if len(members[a]) < len(members[b]):                    # move the smaller cluster: a into b
            a, b, off = b, a, (-off[0], -off[1])
        moved = {t: (r + off[0], c + off[1]) for t, (r, c) in members[b].items()}
        if set(moved.values()) & set(members[a].values()):
            continue                                             # two tiles in one slot
        allp = list(members[a].values()) + list(moved.values())
        rs, cs = [q[0] for q in allp], [q[1] for q in allp]
        if max(rs) - min(rs) >= rows or max(cs) - min(cs) >= cols:
            continue                                             # would not fit in the frame
        members[a].update(moved)
        for t in moved:
            owner[t] = a
        del members[b]
        if len(members) == 1:
            break
    big = max(members.values(), key=len)
    r0, c0 = min(p[0] for p in big.values()), min(p[1] for p in big.values())
    grid = {(r - r0, c - c0): t for t, (r, c) in big.items()}
    used = set(big)
    # fill the remaining slots greedily (most placed neighbours first, lowest compatibility cost)
    while len(grid) < rows * cols:
        best = (np.inf, None, None)
        for r in range(rows):
            for c in range(cols):
                if (r, c) in grid:
                    continue
                cost, k = np.zeros(n), 0
                if (r, c - 1) in grid:
                    cost += lr[grid[(r, c - 1)]]; k += 1
                if (r, c + 1) in grid:
                    cost += lr[:, grid[(r, c + 1)]]; k += 1
                if (r - 1, c) in grid:
                    cost += tb[grid[(r - 1, c)]]; k += 1
                if (r + 1, c) in grid:
                    cost += tb[:, grid[(r + 1, c)]]; k += 1
                if k == 0:
                    continue
                cost = cost / k - 0.05 * (k - 1)
                cost[list(used)] = np.inf
                j = int(np.argmin(cost))
                if cost[j] < best[0]:
                    best = (cost[j], (r, c), j)
        if best[1] is None:                                      # nothing adjacent (should not happen)
            free = [p for p in ((r, c) for r in range(rows) for c in range(cols)) if p not in grid]
            best = (0, free[0], next(t for t in range(n) if t not in used))
        grid[best[1]] = best[2]
        used.add(best[2])
    return [grid[divmod(p, cols)] for p in range(rows * cols)]
