"""N14: known-plaintext attacks on reduced-round versions of the mixed-radix Feistel, inside one packet.

Usage:
    python experiments/neuro_reduced_rounds.py [--quick]

Method, fixed before the run (cryptanalysis on the real cipher, as small domains allow; DESIGN §4.3.5):
  * Rounds r = 1, 2, 3 of neuro.feistel with the product's tables (Ascon keystream of one packet). The attacker
    knows n (plaintext, ciphertext) address pairs of distinct random plaintexts of that packet, i.e. it knows where n
    events came from (hot pixels, a static scene).
  * Attack, exact and deterministic: r = 1 and 2 read table entries off the pairs; r = 3 solves the linear relations
    x3 - x = T0[y] + T2[y2] (mod W) on the bipartite graph of (y, y2) nodes by breadth-first search, which recovers
    the tables up to one additive constant per connected component (an equivalent key), and reads T1 at x + T0[y].
  * Score: the fraction of all W x H plaintexts whose ciphertext the attacker can now predict (coverage), checked
    against the real cipher: every prediction must be right, else the attack is wrong and the script stops.
  * r = 4 is not attacked here: Durak and Vaudenay's table recovery needs N^1.5 (N/2)^(1/6) pairs (N8 reports it per
    sensor against the events of real packets). r = 8 is the product.
Writes sim_out/neuro/n14/reduced_rounds.{json,md}.
"""
import argparse
from collections import deque

import numpy as np

import neuro_common as C
from neuro import feistel, keys

SK = keys.subkeys(C.master(0), C.CAM, C.BOOT, 0)
SID = keys.session_id(C.CAM, C.BOOT, 0)


def attack(r, x, y, cx, cy, W, H):
    """Learn from known pairs; return predict(px, py) -> (ok mask, qx, qy) for arrays of plaintexts."""
    if r == 1:                                         # (x + T0[y], y)
        t0 = {int(b): (int(c) - int(a)) % W for a, b, c in zip(x, y, cx)}

        def pred(px, py):
            ok = np.array([int(b) in t0 for b in py])
            qx = np.array([(int(a) + t0.get(int(b), 0)) % W for a, b in zip(px, py)])
            return ok, qx, py.copy()
        return pred
    if r == 2:                                         # x1 = x + T0[y]; (x1, y + T1[x1])
        t0 = {int(b): (int(c) - int(a)) % W for a, b, c in zip(x, y, cx)}
        t1 = {int(c): (int(d) - int(b)) % H for b, c, d in zip(y, cx, cy)}

        def pred(px, py):
            ok, qx, qy = [], [], []
            for a, b in zip(px.tolist(), py.tolist()):
                x1 = (a + t0[b]) % W if b in t0 else None
                good = x1 is not None and x1 in t1
                ok.append(good)
                qx.append(x1 if good else 0)
                qy.append((b + t1[x1]) % H if good else 0)
            return np.array(ok), np.array(qx), np.array(qy)
        return pred
    if r == 3:                                         # x1 = x + T0[y]; y1 = y + T1[x1]; (x1 + T2[y1], y1)
        adj = {}
        for a, b, c, d in zip(x.tolist(), y.tolist(), cx.tolist(), cy.tolist()):
            w = (c - a) % W                            # = T0[y] + T2[y1]
            adj.setdefault(("c", b), []).append((("t", d), w))
            adj.setdefault(("t", d), []).append((("c", b), w))
        val, comp = {}, {}
        for start in adj:
            if start in val:
                continue
            val[start], comp[start] = 0, start
            dq = deque([start])
            while dq:
                u = dq.popleft()
                for v, w in adj[u]:
                    want = (w - val[u]) % W            # c + t = w
                    if v not in val:
                        val[v], comp[v] = want, start
                        dq.append(v)
                    elif val[v] != want:
                        raise AssertionError("inconsistent pairs: the r = 3 model is wrong")
        t1 = {}
        for a, b, d in zip(x.tolist(), y.tolist(), cy.tolist()):
            k = (comp[("c", b)], (a + val[("c", b)]) % W)
            t1[k] = (d - b) % H

        def pred(px, py):
            ok, qx, qy = [], [], []
            for a, b in zip(px.tolist(), py.tolist()):
                good = False
                if ("c", b) in val:
                    cp, x1 = comp[("c", b)], (a + val[("c", b)]) % W
                    if (cp, x1) in t1:
                        y1 = (b + t1[(cp, x1)]) % H
                        node = ("t", y1)
                        if node in val and comp[node] == cp:
                            ok.append(True)
                            qx.append((x1 + val[node]) % W)
                            qy.append(y1)
                            good = True
                if not good:
                    ok.append(False)
                    qx.append(0)
                    qy.append(0)
            return np.array(ok), np.array(qx), np.array(qy)
        return pred
    raise ValueError("only r = 1, 2, 3 are attacked")


def run_one(r, n, W, H, ctr, probe, rng):
    t = feistel.make_tables(SK.perm, SID, ctr, W, H, r=r)
    pts = rng.choice(W * H, size=n, replace=False)
    y, x = np.divmod(pts, W)
    cx, cy = feistel.permute(x, y, t)
    pred = attack(r, x, y, cx, cy, W, H)
    q = rng.choice(W * H, size=probe, replace=False)
    qy, qx = np.divmod(q, W)
    ok, px, py = pred(qx, qy)
    ex, ey = feistel.permute(qx, qy, t)
    wrong = ok & ((px != ex) | (py != ey))
    if wrong.any():
        i = int(np.flatnonzero(wrong)[0])
        raise AssertionError(f"r={r}: wrong prediction for ({qx[i]}, {qy[i]}): got ({px[i]}, {py[i]}), "
                             f"expected ({ex[i]}, {ey[i]})")
    return float(ok.mean())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--packets", type=int, default=5, help="independent packets (tables) per cell")
    ap.add_argument("--probe", type=int, default=20000, help="random plaintexts scored per cell")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    geoms = [(34, 34)] if a.quick else [(346, 260), (1280, 720)]
    ns = (30, 300) if a.quick else (100, 300, 1000, 3000, 10000, 30000)
    packets, probe = (2, 500) if a.quick else (a.packets, a.probe)
    rng = np.random.default_rng(0)
    res, rows = {}, []
    for W, H in geoms:
        for r in (1, 2, 3):
            for n in ns:
                if n > W * H // 2:
                    continue
                cov = [run_one(r, n, W, H, ctr, min(probe, W * H), rng) for ctr in range(packets)]
                m, lo, hi = float(np.mean(cov)), float(np.min(cov)), float(np.max(cov))
                res[f"{W}x{H}/r{r}/n{n}"] = {"coverage": cov, "mean": m}
                rows.append((f"{W}x{H}", r, n, round(m, 4), round(lo, 4), round(hi, 4)))
    data = {"results": res, "meta": C.meta(a, packets=packets, probe=probe, ns=list(ns))}
    md = ["# N14 known-plaintext attacks on reduced-round mixed-radix Feistel (one packet)", "",
          f"Coverage = fraction of all plaintexts whose ciphertext the attacker predicts (every prediction checked "
          f"correct); {packets} packets per row, {probe} random probes each; min and max over packets.", "",
          C.table(["sensor", "rounds", "known pairs", "coverage mean", "min", "max"], rows)]
    C.write("n14", "reduced_rounds", data, "\n".join(md), a.out)
    return data


if __name__ == "__main__":
    main()
