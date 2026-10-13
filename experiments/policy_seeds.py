"""Repeated, seeded comparison of defence policies: is the bandit really better than the threshold rule?

    python experiments/policy_seeds.py                                    # learning.json, seeds 1-3, ~46 min
    python experiments/policy_seeds.py --seeds 1 2 3 4 5 --parallel 2     # on a 4-core machine (Kaggle)
    python experiments/policy_seeds.py --scenario experiments/scenarios/quick.json --seeds 1 2   # smoke test
    python experiments/policy_seeds.py --summarise sim_out/policy_seeds/learning               # redo the table

Why: one run per policy is not evidence. The bandit explores at random and the channel adds random
loss / jitter / attack positions, so a single "bandit 13% cheaper" (or "bandit worse") can be luck.
Every (policy, seed) pair runs the same scenario with defence.seed = seed. The table reports
mean +- std over seeds and, paired by seed, in how many seeds the bandit beat the threshold policy.
Writes sim_out/policy_seeds/<scenario>/: table.md, table.csv, runs.json, <policy>_s<seed>/ (one run each).
Runs that share the CPU (--parallel > 1) can be slower to react; keep 1 unless the machine has spare cores.
"""
import argparse
import csv
import json
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import scenario as sc_mod      # noqa: E402

METRICS = [("mean_time_to_mitigate_s", "time to mitigate (s)", "lower"),
           ("mean_leakage_under_attack", "leakage under attack", "lower"),
           ("mean_cost", "cost", "lower"),
           ("mean_cost_calm", "cost when calm", "lower"),
           ("latency_ms_median", "latency median (ms)", "lower")]


def mean_std(v):
    v = [x for x in v if isinstance(x, (int, float))]
    if not v:
        return None, None
    return statistics.mean(v), (statistics.stdev(v) if len(v) > 1 else 0.0)


def summarise(runs, out):
    """runs: list of summary dicts (each has 'policy' and 'seed')."""
    policies = sorted({r["policy"] for r in runs}, key=["fixed", "threshold", "bandit"].index)
    seeds = sorted({r["seed"] for r in runs})
    rows = []
    for p in policies:
        rs = [r for r in runs if r["policy"] == p]
        row = {"policy": p, "runs": len(rs),
               "mitigated": " ".join(r["mitigated_episodes"] for r in rs),
               "false_alarms": sum(r["false_alarm_windows"] for r in rs),
               "calm_windows": sum(r["calm_windows"] for r in rs)}
        for k, _, _ in METRICS:
            row[k] = mean_std([r[k] for r in rs])
        rows.append(row)
    # paired by seed: bandit vs threshold
    paired = {}
    by = {(r["policy"], r["seed"]): r for r in runs}
    if "bandit" in policies and "threshold" in policies:
        for k, _, better in METRICS:
            d = [by[("bandit", s)][k] - by[("threshold", s)][k] for s in seeds
                 if ("bandit", s) in by and ("threshold", s) in by
                 and isinstance(by[("bandit", s)][k], (int, float)) and isinstance(by[("threshold", s)][k], (int, float))]
            if d:
                wins = sum(x < 0 for x in d) if better == "lower" else sum(x > 0 for x in d)
                paired[k] = dict(mean_diff=statistics.mean(d), wins=wins, n=len(d))
    fmt = lambda ms, nd=3: "n/a" if ms[0] is None else f"{ms[0]:.{nd}f} ± {ms[1]:.{nd}f}"
    md = [f"Seeds: {seeds}  (mean ± std over seeds; std uses n-1)", "",
          "| Policy | Runs | Mitigated per run | " + " | ".join(t for _, t, _ in METRICS) + " | False alarms |",
          "|" + "---|" * (len(METRICS) + 4)]
    for r in rows:
        md.append(f"| {r['policy']} | {r['runs']} | {r['mitigated']} | "
                  + " | ".join(fmt(r[k], 0 if "latency" in k else 3) for k, _, _ in METRICS)
                  + f" | {r['false_alarms']}/{r['calm_windows']} |")
    if paired:
        md += ["", "Paired by seed, bandit minus threshold (negative = bandit better):", "",
               "| Metric | Mean difference | Bandit better in |", "|---|---|---|"]
        md += [f"| {t} | {paired[k]['mean_diff']:+.3f} | {paired[k]['wins']}/{paired[k]['n']} seeds |"
               for k, t, _ in METRICS if k in paired]
        n = next(iter(paired.values()))["n"]
        if n < 5:
            md += ["", f"Only {n} seeds: report this as an indication, not as a significant difference."]
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.md").write_text("\n".join(md) + "\n")
    with open(out / "table.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["policy", "seed"] + [k for k, _, _ in METRICS] + ["mitigated", "false_alarm_windows", "calm_windows"])
        for r in sorted(runs, key=lambda r: (r["policy"], r["seed"])):
            w.writerow([r["policy"], r["seed"]] + [r[k] for k, _, _ in METRICS]
                       + [r["mitigated_episodes"], r["false_alarm_windows"], r["calm_windows"]])
    print("\n".join(md))
    return rows, paired


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=str(ROOT / "experiments" / "scenarios" / "learning.json"))
    ap.add_argument("--policies", nargs="+", default=["threshold", "bandit"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3])
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--out")
    ap.add_argument("--summarise", help="folder of an earlier run: only rebuild the table")
    ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    if a.summarise:
        out = Path(a.summarise)
        runs = [json.loads(p.read_text()) for p in sorted(out.glob("*_s*/summary.json"))]
        for r, p in zip(runs, sorted(out.glob("*_s*/summary.json"))):
            r["seed"] = int(p.parent.name.rsplit("_s", 1)[1])
        summarise(runs, out)
        return
    out = Path(a.out or ROOT / "sim_out" / "policy_seeds" / Path(a.scenario).stem)
    jobs = [(p, s) for s in a.seeds for p in a.policies]

    def one(i_job):
        i, (p, s) = i_job
        r = sc_mod.run(a.scenario, p, out / f"{p}_s{s}", base_port=46000 + 40 * i,
                       extra_sets=[f"defence.seed={s}"] + a.set, quiet=True)
        r["seed"] = s
        print(f"done: {p} seed {s}: mitigate {r['mean_time_to_mitigate_s']} s, cost {r['mean_cost']}", flush=True)
        return r

    with ThreadPoolExecutor(max_workers=max(1, a.parallel)) as ex:
        runs = list(ex.map(one, enumerate(jobs)))
    (out / "runs.json").write_text(json.dumps([{k: v for k, v in r.items() if k not in ("timeline", "episodes")}
                                               for r in runs], indent=1))
    summarise(runs, out)
    print(f"\nwritten {out}/ (table.md, table.csv, runs.json)")


if __name__ == "__main__":
    main()
