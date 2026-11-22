"""N6 model selection: which CANDIDATES config of neuro_task_accuracy.py to use, chosen WITHOUT the test split.

Usage (Kaggle GPU):
    python experiments/neuro_n6_select.py --dataset dvsgesture --data <root> [--holdout 5] [--seeds 0 1]

Why (TESTING bug #75): the bug #74 CNN reached 0.732 on the DVS Gesture test split against the 0.90 gate of DESIGN
§8.2, after ~10 h of sealing. Choosing a better model by its TEST accuracy would bias the gate, so every candidate is
trained on the training users minus `--holdout` users drawn with a fixed seed and scored on those held-out users.
The best mean held-out accuracy is copied into CONFIG of neuro_task_accuracy.py by hand, citing this table.

The script also reports the data it trained on (events and duration per recording, class counts) and times the
sealing of `--profile` training recordings per view, so the cost of the full N6 run is known before it starts.
Writes sim_out/neuro/n6sel/<dataset>/selection.{json,md}.
"""
import argparse
import time

import numpy as np

import neuro_common as C
import neuro_task_accuracy as N6


def holdout_users(groups, n, seed=0):
    """n user groups drawn with a fixed seed from the sorted distinct groups (the rest train)."""
    users = sorted(set(groups))
    if n >= len(users):
        raise SystemExit(f"--holdout {n}: only {len(users)} user groups in the training split")
    return sorted(np.random.default_rng(seed).choice(users, n, replace=False).tolist())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--holdout", type=int, default=5, help="training users held out for scoring")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--profile", type=int, default=2, help="training recordings whose sealing is timed per view")
    ap.add_argument("--candidates", nargs="+", default=list(N6.CANDIDATES))
    a = ap.parse_args()
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if a.data is None:
        S = C.synthetic_samples(a.limit or 36, a.seed)
    else:
        S = C.load_samples(a.dataset, a.data, "train", a.limit)
    geom = S[0][3]
    y = np.array([s[1] for s in S])
    groups = [s[2] for s in S]
    classes = int(y.max()) + 1
    held = holdout_users(groups, a.holdout, a.seed)
    va = np.array([g in held for g in groups])
    n_ev = np.array([len(s[0]) for s in S])
    dur = np.array([(int(s[0]["t"].max()) - int(s[0]["t"].min())) / 1e6 if len(s[0]) else 0.0 for s in S])
    stats = {"recordings": len(S), "users": len(set(groups)), "held_out_users": held, "fit": int((~va).sum()),
             "held_out": int(va.sum()), "events_median": float(np.median(n_ev)), "events_max": int(n_ev.max()),
             "duration_s_median": float(np.median(dur)), "class_counts": np.bincount(y).tolist()}
    print(stats, flush=True)

    rows, res, cache = [], {}, {}
    for name in a.candidates:
        cfg = N6.CANDIDATES[name]
        key = (cfg.get("feat", "bins"), cfg["nb"], cfg["down"])
        if key not in cache:
            cache[key] = np.stack([N6.features_cfg(s[0], geom, cfg) for s in S])
        X = cache[key]
        accs = []
        t0 = time.time()
        for sd in a.seeds:
            _, acc = N6.fit_eval(torch, X[~va], y[~va], X[va], y[va], classes, 2 if a.quick else cfg["epochs"], sd,
                                 dev, **N6.fit_args(cfg))
            accs.append(acc)
            print(f"{name} seed {sd}: held-out accuracy {acc:.4f}", flush=True)
        res[name] = {"config": cfg, "held_out_accuracy": accs, "mean": float(np.mean(accs)),
                     "train_s": round(time.time() - t0, 1)}
        res[name]["round"] = N6.ROUNDS.get(name)
        rows.append((name, N6.ROUNDS.get(name), str(cfg), " / ".join(f"{v:.3f}" for v in accs), f"{np.mean(accs):.3f}", res[name]["train_s"]))
    best = max(res, key=lambda k: res[k]["mean"])
    gate = N6.GATE.get(a.dataset)

    prof = {}
    for view in ("V1", "V2", "V3", "V4", "Du 2021", "Zhang 2024"):
        if view in ("Du 2021", "Zhang 2024") and not C.baseline("du2021" if view.startswith("Du") else "zhang2024"):
            continue
        t = []
        for i in range(min(a.profile, len(S))):
            t0 = time.time()
            N6.view_events(S[i][0], geom, view, i)
            t.append(time.time() - t0)
        prof[view] = {"s_per_recording": t, "mean_s": float(np.mean(t))}
    n_tr, n_te = N6.CT_DEFAULT.get(a.dataset, (len(S), len(S)))
    per_rec = sum(v["mean_s"] for v in prof.values())
    est_h = per_rec * (n_tr + n_te) / 4 / 3600          # Kaggle: 4 sealing processes

    data = {"data": stats, "candidates": res, "chosen": best, "chosen_mean": res[best]["mean"], "gate": gate,
            "sealing_profile": prof, "sealing_estimate_h_4_workers": est_h,
            "meta": C.meta(a, dataset=a.dataset, synthetic=a.data is None, device=dev)}
    md = ["# N6 model selection" + (" (synthetic smoke data)" if a.data is None else ""), "",
          f"Training split only: {stats['fit']} recordings to fit, {stats['held_out']} of held-out users {held} to "
          f"score. Median {stats['events_median']:.0f} events and {stats['duration_s_median']:.2f} s per recording "
          f"(max {stats['events_max']} events); class counts {stats['class_counts']}.", "",
          C.table(["candidate", "round", "config", "held-out accuracy per seed", "mean", "train s"], rows), "",
          f"Chosen: {best} (mean {res[best]['mean']:.3f}) of {len(res)} candidates over "
          f"{len({N6.ROUNDS.get(k) for k in res})} selection round(s) on the same held-out users (report the count: "
          f"choosing the best of several on one split is itself optimistic); gate of the full run on the test split: "
          f"{gate}.", "",
          C.table(["view", "sealing s per recording (mean)"], [(v, f"{p['mean_s']:.1f}") for v, p in prof.items()]),
          "", f"Estimated sealing of the full N6 run ({n_tr} + {n_te} recordings, 4 processes): {est_h:.1f} h."]
    C.write("n6sel", "selection", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
