"""N13: can the public count series be hidden without dummy events, by mixing cameras or by shaped padding?

Usage:
    python experiments/neuro_mixing.py --counts sim_out/neuro/n5/nmnist_counts.npz --dataset nmnist [--quick]
    python experiments/neuro_mixing.py [--quick]                      # synthetic smoke data

Method, fixed before the run (extends N5, DESIGN §5.4):
  * Mixing (communication). k cameras of one site feed one encryptor that is configured as a virtual sensor of
    k W x H (camera index in the high part of x). The V2/V3 permutation then hides which camera an event came from,
    and the attacker sees only the per-bucket count of the k streams together. No RTL change: k W must fit the 11-bit
    x field (k <= 2048 // W), and the tables grow with k W + H. For every sample (the target camera) k - 1 partner
    samples of the same split, from other groups and of random class, are added bucket by bucket from a random
    phase (cameras are not synchronised; a partner shorter than the target is repeated). The attacker knows k,
    trains on mixtures of the training split and classifies the target's label on mixtures of the test split.
  * Shaped padding (bio-inspired: a peak detector with exponential decay, like a membrane potential that jumps
    with input and leaks): every bucket is padded up to s_b = ceil(max_{j <= b} n_j lam^(b - j)). Rises stay
    visible, falls are smeared over ~1 / (1 - lam) buckets; the cost is the dummies s_b - n_b. Model-only policy
    (the RTL pads by floor or ladder, §5).
  * Attackers: the N5 count-only classifiers (nearest-centroid and 5-NN on the summary features of
    neuro_leakage.features), balanced accuracy with a cluster-bootstrap 95 % CI over test groups; chance 1 / classes.
    Views: V3 (k = 1, the reference), V3 mixed k in {2, 4, 8}, V3 + pad floor 4 / floor 16 / ladder (N5's policies,
    for cost comparison), V3 + shaped lam in {0.9, 0.98}. Cost: dummy words per real CD word (0 for mixing).
  No pass criterion is asserted; the numbers are reported against N5's padding rows.
Writes sim_out/neuro/n13/mixing.{json,md}.
"""
import argparse

import numpy as np

import neuro_common as C
import neuro_leakage as L
from neuro.pad import bucket_targets
from neuro.stats import cluster_bootstrap_ci, n_clusters

KS = (2, 4, 8)
LAMS = (0.9, 0.98)
X_FIELD = 2048                       # 11-bit x field of an EVT 2.0 CD word


def shaped(n, lam, chunk=256):
    """Peak-hold with exponential decay: s_b = ceil(max_{j <= b} n_j lam^(b - j)); s_b >= n_b, integer."""
    n = np.asarray(n, dtype=np.float64)
    out = np.empty_like(n)
    carry = 0.0                                       # envelope value at the bucket before the chunk
    for a in range(0, len(n), chunk):
        x = n[a:a + chunk]
        i = np.arange(len(x), dtype=np.float64)
        w = lam ** (-i)                               # bounded: chunk <= 256, lam >= 0.5 -> < 2^256
        env = np.maximum.accumulate(x * w) * lam ** i
        env = np.maximum(env, carry * lam ** (i + 1))
        out[a:a + chunk] = env
        carry = env[-1] if len(env) else carry
    return np.maximum(np.ceil(out - 1e-9), n).astype(np.int64)


def mix(series, y, g, sel, k, rng):
    """Mixture of every selected sample with k - 1 partners of the same selection (other groups, random phase)."""
    idx = np.flatnonzero(sel)
    out = []
    for i in idx:
        s = series[i].astype(np.int64).copy()
        cand = idx[g[idx] != g[i]]
        for p in rng.choice(cand, size=k - 1, replace=len(cand) < k - 1):
            q = series[p]
            if len(q) == 0:
                continue
            ph = int(rng.integers(len(q)))
            s += np.resize(np.roll(q, -ph), len(s))
        out.append(s)
    return out


def score(vis_tr, vis_te, y, g, tr, te, seed):
    """Balanced accuracy of the N5 count-only classifiers trained on vis_tr, tested on vis_te."""
    X = np.zeros((len(y), 7))
    X[tr] = np.stack([L.features(v) for v in vis_tr])
    X[te] = np.stack([L.features(v) for v in vis_te])
    te_mask, preds = L.classify(X, y, g, np.unique(g[te]))
    assert np.array_equal(te_mask, te)
    return {name: cluster_bootstrap_ci(L.balanced_correct(pred, y[te]), g[te], n=500, seed=seed)
            for name, pred in preds.items()}


def cost(series_list, targets):
    real = sum(int(s.sum()) for s in series_list)
    return float(sum(int((t - s).sum()) for s, t in zip(series_list, targets)) / max(1, real))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--counts", default=None, help="npz from neuro.datasets.cache_counts (N5 cache)")
    a = ap.parse_args(argv)
    if a.counts:
        sl = L.series_from_cache(a.counts)
    else:
        sl = L.series_from_samples(C.load_samples(a.dataset, a.data, limit=a.limit or (24 if a.quick else 200),
                                                  seed=a.seed))
    sl = [s for s in sl if s[1] is not None and s[1] >= 0]
    series = [s.astype(np.int64) for s, _, _ in sl]
    y = np.array([lab for _, lab, _ in sl])
    g = np.array([grp for _, _, grp in sl]).astype(str)
    te = np.isin(g, L.official_test_groups(g))
    tr = ~te
    if not (set(y[te].tolist()) & set(y[tr].tolist())):
        raise SystemExit("N13 needs classes shared by train and test (not Event-ReId persons): use nmnist or dvsgesture")
    rng = np.random.default_rng(a.seed)
    res, rows = {}, []

    def add(name, vis, k=1, dummies=0.0):
        r = score([vis[i] for i in np.flatnonzero(tr)], [vis[i] for i in np.flatnonzero(te)], y, g, tr, te, a.seed)
        r.update(k=k, dummies_per_real=dummies)
        res[name] = r
        rows.append((name, k, round(dummies, 3), r["nearest-centroid"], r["5-NN"]))

    add("V3", series)
    for k in (KS[:1] if a.quick else KS):
        mixed = [None] * len(series)
        for sel in (tr, te):
            for i, s in zip(np.flatnonzero(sel), mix(series, y, g, sel, k, rng)):
                mixed[i] = s
        add(f"V3 mixed k={k}", mixed, k=k)
    for name, pol in L.POLICIES.items():
        t = [bucket_targets(s, pol) for s in series]
        add(f"V3 + pad {name}", t, dummies=cost(series, t))
    for lam in LAMS:
        t = [shaped(s, lam) for s in series]
        add(f"V3 + shaped lam={lam}", t, dummies=cost(series, t))
    chance = 1 / len(np.unique(y))
    geoms = {n: geo for n, geo in __import__("neuro.geometry", fromlist=["SENSORS"]).SENSORS.items()}
    kmax = {n: X_FIELD // geo.W for n, geo in geoms.items()}
    data = {"views": res, "chance": chance, "test_clusters": n_clusters(g[te]), "kmax_by_sensor": kmax,
            "meta": C.meta(a, inputs=[a.counts] if a.counts else [], dataset=a.dataset,
                           synthetic=a.data is None and not a.counts, ks=KS, lams=LAMS,
                           ci="cluster bootstrap 95 % over test groups")}
    md = ["# N13 mixing and shaped padding" + (" (synthetic smoke data)" if a.data is None and not a.counts else ""),
          "", f"Chance {chance:.3f}; {data['test_clusters']} test clusters. Mixing k cameras costs no dummies;",
          f"largest k per sensor (k W <= {X_FIELD}): " + ", ".join(f"{n} {v}" for n, v in kmax.items()), "",
          C.table(["view", "k", "dummies per real", "bal. acc. nearest-centroid", "bal. acc. 5-NN"], rows)]
    C.write("n13", "mixing", data, "\n".join(md), a.out)
    return data


if __name__ == "__main__":
    main()
