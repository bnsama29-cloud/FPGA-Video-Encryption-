"""N15: security margin of the eight-round mixed-radix Feistel at the data a real packet carries.

Usage:
    python experiments/neuro_margin.py [--n8 results/neuro/N8_N9dvs_b968fac/sim_out/neuro/n8/perm_strength.json] [--quick]

Method, fixed before the run (DESIGN §4.3.5; BipBip-style analysis on the real cipher):
  * Data budget: the distinct (x, y) addresses of one packet, from N8's DVS Gesture measurement at T = 1024 µs
    (median, 99th percentile, maximum; --n8), plus 1000 and 10 000 as stress values.
  * Two sampling models for the known plaintexts of a packet: uniform over the sensor, and clustered (uniform in a
    32 x 32 box, like one moving hand), which gives an attacker more same-row and same-column pairs.
  * Distinguisher for r = 1..8 rounds (prefix of the packet's eight tables): over all pairs of known plaintexts that
    share y (or x), the fraction whose ciphertexts keep the input difference in x (in y) or share y (x). These are
    the truncated differentials that a few Feistel rounds keep. Per packet this gives one statistic; its
    distribution over --packets packets of the cipher is compared with an ideal permutation (n distinct uniformly
    random outputs) by the AUC, i.e. the probability of telling cipher from ideal from one packet (0.5 = no
    advantage). The margin is 8 minus the first r whose AUC 95 % interval contains 0.5.
  * Attack coverage for r = 1..3 at the same budgets (neuro_reduced_rounds.attack), uniform and clustered.
Writes sim_out/neuro/n15/margin.{json,md}.
"""
import argparse
import json
from pathlib import Path

import numpy as np

import neuro_common as C
import neuro_reduced_rounds as N14
from neuro import feistel, keys

SK = keys.subkeys(C.master(1), C.CAM, C.BOOT, 0)
SID = keys.session_id(C.CAM, C.BOOT, 0)
N8_DEFAULT = C.ROOT / "results/neuro/N8_N9dvs_b968fac/sim_out/neuro/n8/perm_strength.json"


def auc(a, b, n=1000, seed=0):
    """P(a > b) + P(a = b) / 2 (Mann-Whitney AUC) of two samples, with a 95 % bootstrap interval over both."""
    a, b = np.asarray(a, float), np.asarray(b, float)

    def one(x, y):
        return float(((x[:, None] > y[None]).sum() + 0.5 * (x[:, None] == y[None]).sum()) / (len(x) * len(y)))
    rng = np.random.default_rng(seed)
    boots = [one(rng.choice(a, len(a)), rng.choice(b, len(b))) for _ in range(n)]
    return one(a, b), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def budgets(n8_path):
    kp = [k for k in json.loads(Path(n8_path).read_text())["known_plaintext"] if k["T_us"] == 1024][0]
    return {"median": int(kp["distinct_median"]), "p99": int(kp["distinct_p99"]), "max": int(kp["distinct_max"]),
            "1000": 1000, "10000": 10000}


def sample(W, H, n, mode, rng):
    if mode == "uniform":
        p = rng.choice(W * H, size=n, replace=False)
        y, x = np.divmod(p, W)
        return x, y
    b = 32
    n = min(n, b * b)
    x0, y0 = rng.integers(0, W - b + 1), rng.integers(0, H - b + 1)
    p = rng.choice(b * b, size=n, replace=False)
    dy, dx = np.divmod(p, b)
    return x0 + dx, y0 + dy


def stat(x, y, cx, cy, W, H):
    """Fraction of same-row / same-column plaintext pairs whose ciphertexts keep the difference or the other
    coordinate (the truncated differentials of few Feistel rounds); nan when no such pair exists."""
    hits = total = 0
    for a, b, ca, cb, M, N in ((x, y, cx, cy, W, H), (y, x, cy, cx, H, W)):
        order = np.argsort(b, kind="stable")
        bs = b[order]
        starts = np.flatnonzero(np.r_[True, bs[1:] != bs[:-1]])
        ends = np.r_[starts[1:], len(bs)]
        for s, e in zip(starts, ends):
            if e - s < 2:
                continue
            idx = order[s:e]
            i, j = np.triu_indices(len(idx), 1)
            u, v = idx[i], idx[j]
            keep_diff = ((ca[u] - ca[v]) % M) == ((a[u] - a[v]) % M)
            same_other = cb[u] == cb[v]
            hits += int(keep_diff.sum() + same_other.sum())
            total += 2 * len(u)
    return hits / total if total else np.nan


def run(W, H, rounds, buds, modes, packets, seed):
    rng = np.random.default_rng(seed)
    res = {}
    for mode in modes:
        for bname, n in buds.items():
            if n > W * H // 2:
                continue
            cs = {r: [] for r in rounds}
            ideal, cover = [], {r: [] for r in (1, 2, 3)}
            for ctr in range(packets):
                t8 = feistel.make_tables(SK.perm, SID, ctr, W, H)
                x, y = sample(W, H, n, mode, rng)
                for r in rounds:
                    tr = feistel.Tables(W, H, r, t8.t[:r])
                    cx, cy = feistel.permute(x, y, tr)
                    cs[r].append(stat(x, y, cx, cy, W, H))
                    if r <= 3 and ctr < 5:
                        q = rng.choice(W * H, size=min(5000, W * H), replace=False)
                        qy, qx = np.divmod(q, W)
                        ok, px, py = N14.attack(r, x, y, cx, cy, W, H)(qx, qy)
                        ex, ey = feistel.permute(qx, qy, tr)
                        assert not (ok & ((px != ex) | (py != ey))).any(), "attack predicted a wrong ciphertext"
                        cover[r].append(float(ok.mean()))
                out = rng.choice(W * H, size=len(x), replace=False)        # ideal permutation on these inputs
                oy, ox = np.divmod(out, W)
                ideal.append(stat(x, y, ox, oy, W, H))
            ideal_a = np.array(ideal)
            for r in rounds:
                c = np.array(cs[r])
                ok = ~np.isnan(c) & ~np.isnan(ideal_a)
                a = auc(c[ok], ideal_a[ok]) if ok.sum() >= 4 else (float("nan"), float("nan"), float("nan"))
                res[f"{W}x{H}/{mode}/{bname}/r{r}"] = {"n": n, "auc": a, "cipher_mean": float(np.nanmean(c)),
                                                        "ideal_mean": float(np.nanmean(ideal_a)),
                                                        "coverage": float(np.mean(cover[r])) if r <= 3 else None}
    return res


def margin(res, W, H, mode, bname, rounds):
    for r in rounds:
        a = res[f"{W}x{H}/{mode}/{bname}/r{r}"]["auc"]
        if not np.isnan(a[1]) and a[1] <= 0.5 <= a[2]:
            return r, 8 - r
    return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n8", default=str(N8_DEFAULT), help="N8 perm_strength.json (per-packet distinct addresses)")
    ap.add_argument("--packets", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    buds = budgets(a.n8)
    rounds = tuple(range(1, 9))
    if a.quick:
        geoms, buds, packets = [(34, 34)], {"p99": min(buds["p99"], 200)}, 12
    else:
        geoms, packets = [(128, 128), (1280, 720)], a.packets
    modes = ("uniform", "clustered")
    res, rows = {}, []
    for W, H in geoms:
        res.update(run(W, H, rounds, buds, modes, packets if W * H < 10 ** 5 else max(20, packets // 4), a.seed))
        for mode in modes:
            for bname, n in buds.items():
                if f"{W}x{H}/{mode}/{bname}/r1" not in res:
                    continue
                first, mg = margin(res, W, H, mode, bname, rounds)
                aucs = [res[f"{W}x{H}/{mode}/{bname}/r{r}"]["auc"][0] for r in rounds]
                cov3 = res[f"{W}x{H}/{mode}/{bname}/r3"]["coverage"]
                rows.append((f"{W}x{H}", mode, f"{bname} ({n})", *[round(v, 2) for v in aucs], round(cov3, 4),
                             "-" if first is None else f"{first} / {mg}"))
    data = {"results": res, "budgets": buds,
            "meta": C.meta(a, inputs=[a.n8], packets=packets, rounds=list(rounds),
                           auc="per-packet statistic, cipher vs ideal permutation, Mann-Whitney AUC with 95 % bootstrap CI")}
    md = ["# N15 security margin at the data of one packet", "",
          "AUC of telling the r-round cipher from an ideal permutation from ONE packet's known pairs (0.5 = none); "
          "r3 cover = fraction of the codebook the exact 3-round attack predicts; first indistinguishable r / margin "
          "8 - r.", "",
          C.table(["sensor", "sampling", "pairs", *[f"r{r}" for r in rounds], "r3 cover", "first r / margin"], rows)]
    C.write("n15", "margin", data, "\n".join(md), a.out)
    return data


if __name__ == "__main__":
    main()
