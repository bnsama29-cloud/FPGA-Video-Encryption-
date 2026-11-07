"""N5: what do event rate, per-bucket counts, multiplicity and dummy position reveal, and what does padding cost?

Usage:
    python experiments/neuro_leakage.py --counts sim_out/neuro/n5/dvsgesture_counts.npz [--quick]
    python experiments/neuro_leakage.py [--dataset nmnist --data <root>]        # computes the counts itself

The Kaggle job writes the per-bucket count cache with neuro.datasets.cache_counts (so this laptop never needs
Tonic); with --counts the class/count analysis runs from the cache alone. The dummy distinguisher needs events
(--data or synthetic).

Method (DESIGN §5.4, §8.2 N5). What a passive attacker sees per level:
    V2, V3          exact CD count per 64 µs bucket
    V3 + pad        bucket_target(count) per bucket (floor: max(n, PAD_MIN); ladder: PAD_MIN * 2^k, exact above
                    PAD_CAP)
    V4              payload length per packet (sum over its buckets, + TIME_HIGH words)
    V4 + pad        padded length per packet
  * MI between a per-sample feature (total visible count, quantised to 8 equal-frequency bins) and the class:
    plug-in with Miller-Madow correction, permutation null of 200 shuffles, p-value.
  * Classifier on the visible series (summary features: mean, std, max, p90, total, duration, fraction of
    non-empty units): standardised nearest-centroid and 5-NN (scikit-learn GBT and a 1-D CNN on Kaggle when
    installed), train/test split by group (official split when given), balanced accuracy with chance level and a
    cluster-bootstrap CI over test groups.
  * Dummy distinguisher (§5.4): AUC for "is this CD word a dummy" from multiplicity only, position from the end of
    the bucket only, and both (mean of the two ranks), on padded packets.
  * Padding cost: dummy words / real CD words; fraction of buckets above PAD_MIN (floor) or PAD_CAP (ladder).
Writes sim_out/neuro/n5/leakage.{json,md}.
"""
import argparse

import numpy as np

import neuro_common as C
from neuro import evt2
from neuro.packet import packetize
from neuro.pad import FLOOR, LADDER, PadPolicy, bucket_target, bucket_targets, pad_packet
from neuro.stats import cluster_bootstrap_ci, mi_perm_null, n_clusters, quantize

POLICIES = {"floor 4": PadPolicy(FLOOR, 4), "floor 16": PadPolicy(FLOOR, 16), "ladder 2..64": PadPolicy(LADDER, 2, 64)}


def series_from_samples(samples):
    out = []
    for ev, label, group, geom, _ in samples:
        t = ev["t"].astype(np.int64)
        b = (t >> 6) - (t.min() >> 6) if len(t) else np.zeros(0, np.int64)
        out.append((np.bincount(b).astype(np.int64) if len(b) else np.zeros(1, np.int64), label, group))
    return out


def series_from_cache(path):
    from neuro.datasets import load_counts
    return [(s.astype(np.int64), lab, grp) for s, lab, grp, _, _ in load_counts(path)]


def visible(series, view, T=1024):
    nb = T // 64
    if view in ("V2", "V3"):
        return series
    if view.startswith("V3 + pad"):
        pol = POLICIES[view.split("pad ")[1]]
        return bucket_targets(series, pol)
    pad = len(series) % nb
    s = np.concatenate([series, np.zeros((nb - pad) % nb, np.int64)]).reshape(-1, nb)
    if view == "V4":
        return s.sum(1) + (s > 0).sum(1)
    pol = POLICIES[view.split("pad ")[1]]
    return bucket_targets(s, pol).sum(1) + nb


def features(v):
    v = np.asarray(v, float)
    return np.array([v.mean(), v.std(), v.max(), np.quantile(v, 0.9), v.sum(), len(v), (v > 0).mean()])


def classify(X, y, g, test_groups):
    te = np.isin(g, test_groups)
    tr = ~te
    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
    Z = (X - mu) / sd
    classes = np.unique(y[tr])
    cent = np.stack([Z[tr & (y == c)].mean(0) for c in classes])
    pred_c = classes[np.argmin(((Z[te][:, None] - cent[None]) ** 2).sum(-1), 1)]
    d = ((Z[te][:, None] - Z[tr][None]) ** 2).sum(-1)
    nn = np.argsort(d, 1)[:, :5]
    ytr = y[tr]
    pred_k = np.array([np.bincount(ytr[r], minlength=classes.max() + 1).argmax() for r in nn])
    return te, {"nearest-centroid": pred_c, "5-NN": pred_k}


def balanced_correct(pred, ytrue):
    """Per-item weights so that the mean over items is the balanced accuracy."""
    w = np.zeros(len(ytrue))
    for c in np.unique(ytrue):
        m = ytrue == c
        w[m] = (pred[m] == c) / m.sum() / len(np.unique(ytrue)) * len(ytrue)
    return w


def dummy_auc(samples, policy, T=1024, max_packets=200):
    from scipy.stats import rankdata
    mult, pos, lab = [], [], []
    for ev, _, _, geom, _ in samples:
        if len(ev) == 0:
            continue
        t = ev["t"].astype(np.int64)
        ev = ev[t < t[0] + max_packets * T]               # long recordings (DVS Gesture, 6 s): only what is used
        words = evt2.encode(ev, T)
        for raw in packetize(words, geom, T)[:max_packets]:
            w, _, _, dm = pad_packet(raw.words, policy, bytes(16), 1 << 16, raw.ctr, geom, raw.t_start, T)
            cd = evt2.is_cd(w)
            th = (w >> 28) == 8
            bucket = np.cumsum(th)
            addr = np.where(cd, (w & np.uint32(0x3FFFFF)).astype(np.int64), -1)
            for b in np.unique(bucket):
                m = (bucket == b) & cd
                idx = np.nonzero(m)[0]
                if len(idx) == 0:
                    continue
                a = addr[idx]
                _, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
                mult.extend((-cnt[inv]).tolist())              # singletons are suspicious: higher score
                pos.extend((np.arange(len(idx)) - len(idx) + 1).tolist())          # 0 = last word of the bucket
                lab.extend(dm[idx].tolist())
    lab = np.asarray(lab, bool)
    if lab.all() or not lab.any():
        return {"multiplicity": float("nan"), "position": float("nan"), "both": float("nan"), "words": len(lab)}

    def auc(s):
        r = rankdata(s)
        n1 = lab.sum()
        return float((r[lab].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(lab) - n1)))
    m, p = np.asarray(mult, float), np.asarray(pos, float)
    return {"multiplicity": auc(m), "position": auc(p), "both": auc(rankdata(m) + rankdata(p)), "words": len(lab)}


def pad_cost(series_list):
    out = {}
    for name, pol in POLICIES.items():
        real = dummies = above = nb = 0
        for s, _, _ in series_list:
            t = bucket_targets(s, pol)
            real += s.sum()
            dummies += (t - s).sum()
            lim = pol.pad_min if pol.kind == FLOOR else pol.pad_cap
            above += (s > lim).sum()
            nb += len(s)
        out[name] = {"dummies_per_real": float(dummies / max(1, real)), "buckets_above_limit": float(above / max(1, nb))}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--counts", default=None, help="npz from neuro.datasets.cache_counts")
    a = ap.parse_args()
    samples = C.load_samples(a.dataset, a.data, limit=a.limit or (12 if a.quick else 200), seed=a.seed)
    sl = series_from_cache(a.counts) if a.counts else series_from_samples(samples)
    sl = [s for s in sl if s[1] is not None]
    y = np.array([lab for _, lab, _ in sl])
    g = np.array([grp for _, _, grp in sl])
    groups = np.unique(g)
    test_groups = groups[len(groups) // 2:] if len(groups) > 1 else groups
    # Event-ReId: label = person = group, so no test label is ever seen in training and a classifier scores 0 by
    # construction (first Kaggle QUICK run, TESTING bug #54). Classifiers then report n/a; MI is still valid.
    tr_labels = set(y[~np.isin(g, test_groups)].tolist())
    clf_ok = bool(set(y[np.isin(g, test_groups)].tolist()) & tr_labels)
    views = ["V2", "V3", "V3 + pad floor 4", "V3 + pad floor 16", "V3 + pad ladder 2..64", "V4", "V4 + pad floor 4",
             "V4 + pad ladder 2..64"]
    res, rows = {}, []
    for v in views:
        vis = [visible(s, v) for s, _, _ in sl]
        tot = quantize([x.sum() for x in vis], 8)
        mi, null, p = mi_perm_null(tot, y, n=40 if a.quick else 200, seed=a.seed)
        X = np.stack([features(x) for x in vis])
        r = {"mi_bits": mi, "mi_null_mean": null, "mi_p": p}
        if clf_ok:
            te, preds = classify(X, y, g, test_groups)
            for name, pred in preds.items():
                r[name] = cluster_bootstrap_ci(balanced_correct(pred, y[te]), g[te], n=500, seed=a.seed)
        else:
            r["nearest-centroid"] = r["5-NN"] = "n/a"
        res[v] = r
        rows.append((v, mi, p, r["nearest-centroid"], r["5-NN"]))
    chance = 1 / len(np.unique(y))
    data = {"views": res, "chance": chance, "test_clusters": n_clusters(g[np.isin(g, test_groups)]),
            "dummy_auc": {k: dummy_auc(samples[:4] if a.quick else samples, p) for k, p in POLICIES.items()},
            "pad_cost": pad_cost(sl)}
    data["meta"] = C.meta(a, inputs=[a.counts] if a.counts else [], dataset=a.dataset, synthetic=a.data is None,
                          split="by group (half of the groups for test)", ci="cluster bootstrap 95 % over test groups",
                          classifiers="nearest-centroid, 5-NN (GBT / 1-D CNN only on Kaggle)")
    md = ["# N5 leakage" + (" (synthetic smoke data)" if a.data is None and not a.counts else ""), "",
          f"Chance level {chance:.3f}; {data['test_clusters']} test clusters."
          + ("" if clf_ok else " Classifiers n/a: every test label is a group never seen in training "
             "(label = group, e.g. Event-ReId persons), so only MI is reported."), "",
          C.table(["view", "MI bits (total count)", "p (perm.)", "bal. acc. nearest-centroid", "bal. acc. 5-NN"], rows),
          "", "Dummy distinguisher AUC (0.5 = indistinguishable):", "",
          C.table(["policy", "multiplicity", "position", "both", "CD words"],
                  [(k, v["multiplicity"], v["position"], v["both"], v["words"]) for k, v in data["dummy_auc"].items()]),
          "", C.table(["policy", "dummies per real CD word", "buckets above PAD_MIN/PAD_CAP"],
                      [(k, v["dummies_per_real"], v["buckets_above_limit"]) for k, v in data["pad_cost"].items()])]
    C.write("n5", "leakage", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
