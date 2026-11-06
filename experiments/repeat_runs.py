"""The attack suite repeated, with 95 % intervals per attack (journal experiment X3).

    python experiments/repeat_runs.py --reps 5                                   # simulation, full_suite.json
    python experiments/repeat_runs.py --scenario experiments/scenarios/quick.json --reps 2      # smoke test
    python experiments/repeat_runs.py --reps 5 --external-sender <BOARD IP> --board-max-mode E5  # board as camera
    python experiments/repeat_runs.py --summarise sim_out/repeat_runs/full_suite                 # table only
    python experiments/repeat_runs.py --summarise results/board/board_day_24oct/runs --glob "board_full_suite_rep*"

One run per scenario cannot carry error bars. Every repetition runs the same scenario with a different
defence/channel seed (defence.seed = rep) and writes its own folder (rep<k>/, as experiments/scenario.py
writes it). The table gives, per attack type over all repetitions: how many episodes were mitigated, the
mean time to the receiver's first rejection and to mitigation with a 95 % interval (Student t over
episodes), and the false-alarm windows over all calm windows. With the board as sender, start the board
command that experiments/scenario.py prints before each repetition (it prints it again).
Writes <out>/table.md, table.csv and runs.json.
"""
import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import scenario as sc_mod      # noqa: E402

# two-sided 95 % Student t quantiles for n-1 degrees of freedom (n = 2..30); normal beyond
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
       11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
       20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048,
       29: 2.045}


def mean_ci(v):
    """(mean, half-width of the 95 % interval) of the numbers in v; (None, None) if empty, (mean, None) for one."""
    v = [float(x) for x in v if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x))]
    if not v:
        return None, None
    if len(v) == 1:
        return v[0], None
    t = T95.get(len(v) - 1, 1.96)
    return statistics.mean(v), t * statistics.stdev(v) / math.sqrt(len(v))


def episodes_of(run_dir):
    """Episodes of one run folder: summary.json if present, else episodes.csv (board day copies)."""
    d = Path(run_dir)
    if (d / "summary.json").exists():
        s = json.loads((d / "summary.json").read_text())
        return s.get("episodes", []), s
    rows = []
    with open(d / "episodes.csv", newline="") as f:
        for r in csv.DictReader(f):
            for k in ("rx_first_rejection_s", "time_to_mitigate_s", "sender_aware_s"):
                r[k] = float(r[k]) if r.get(k) not in (None, "", "None") else None
            rows.append(r)
    return rows, {}


def summarise(runs):
    """runs: list of (episodes, summary) -> {'by_type': {type: stats}, 'false_alarms', 'calm_windows', 'reps'}."""
    by = {}
    for eps, _ in runs:
        for e in eps:
            by.setdefault(e["type"], []).append(e)
    table = {}
    for typ, eps in by.items():
        m_rej, h_rej = mean_ci([e.get("rx_first_rejection_s") for e in eps])
        m_mit, h_mit = mean_ci([e.get("time_to_mitigate_s") for e in eps])
        table[typ] = dict(episodes=len(eps), mitigated=sum(e.get("time_to_mitigate_s") is not None for e in eps),
                          first_rejection_s=m_rej, first_rejection_ci=h_rej, mitigate_s=m_mit, mitigate_ci=h_mit)
    fa = sum(s.get("false_alarm_windows", 0) for _, s in runs)
    calm = sum(s.get("calm_windows", 0) for _, s in runs)
    all_mit = [e.get("time_to_mitigate_s") for eps, _ in runs for e in eps]
    m, h = mean_ci(all_mit)
    return dict(by_type=table, false_alarms=fa, calm_windows=calm, reps=len(runs), mitigate_all_s=m,
                mitigate_all_ci=h, mitigated_all=sum(x is not None for x in all_mit), episodes_all=len(all_mit))


def fmt(m, h, nd=2):
    if m is None:
        return "-"
    return f"{m:.{nd}f}" + ("" if h is None else f" ± {h:.{nd}f}")


def write(res, out, title):
    md = [f"# {title}", "", f"{res['reps']} repetitions; mean ± half-width of the 95 % interval over episodes "
          "(Student t).", "",
          "| Attack | episodes | mitigated | first rejection at the receiver (s) | time to mitigate (s) |",
          "|---|---|---|---|---|"]
    for typ, r in res["by_type"].items():
        md.append(f"| {typ} | {r['episodes']} | {r['mitigated']}/{r['episodes']} | "
                  f"{fmt(r['first_rejection_s'], r['first_rejection_ci'], 3)} | {fmt(r['mitigate_s'], r['mitigate_ci'])} |")
    md += ["", f"All attacks: {res['mitigated_all']}/{res['episodes_all']} episodes mitigated, mean time to mitigate "
           f"{fmt(res['mitigate_all_s'], res['mitigate_all_ci'])} s.",
           f"False alarms: {res['false_alarms']} of {res['calm_windows']} calm windows (summed over repetitions)."]
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.md").write_text("\n".join(md) + "\n")
    with open(out / "table.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["attack", "episodes", "mitigated", "first_rejection_s", "first_rejection_ci95",
                    "mitigate_s", "mitigate_ci95"])
        for typ, r in res["by_type"].items():
            w.writerow([typ, r["episodes"], r["mitigated"], r["first_rejection_s"], r["first_rejection_ci"],
                        r["mitigate_s"], r["mitigate_ci"]])
    (out / "runs.json").write_text(json.dumps(res, indent=1))
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=str(ROOT / "experiments" / "scenarios" / "full_suite.json"))
    ap.add_argument("--policy", default="threshold", choices=["fixed", "threshold", "bandit"])
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--first-rep", type=int, default=1, help="continue an interrupted series")
    ap.add_argument("--base-port", type=int, default=47200)
    ap.add_argument("--external-sender", metavar="BOARD_IP")
    ap.add_argument("--attacker", metavar="ATTACKER_IP")
    ap.add_argument("--board-max-mode", default="E5", choices=["E4", "E5"])
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--out")
    ap.add_argument("--summarise", metavar="FOLDER", help="only build the table from run folders in FOLDER")
    ap.add_argument("--glob", default="rep*", help="with --summarise: which sub-folders are runs")
    a = ap.parse_args()
    if a.summarise:
        dirs = sorted(d for d in Path(a.summarise).glob(a.glob) if d.is_dir())
        if not dirs:
            sys.exit(f"no run folders matching {a.glob} in {a.summarise}")
        write(summarise([episodes_of(d) for d in dirs]), Path(a.summarise), f"Repeated runs: {Path(a.summarise).name}")
        return
    name = Path(a.scenario).stem + ("_board" if a.external_sender else "")
    out = Path(a.out or ROOT / "sim_out" / "repeat_runs" / name)
    for k in range(a.first_rep, a.first_rep + a.reps):
        print(f"\n=== repetition {k} ===", flush=True)
        sc_mod.run(a.scenario, a.policy, out / f"rep{k}", base_port=a.base_port,
                   extra_sets=[f"defence.seed={k}"] + a.set, quiet=True, external_sender=a.external_sender,
                   board_max_mode=a.board_max_mode, attacker=a.attacker)
    dirs = sorted(d for d in out.glob("rep*") if d.is_dir())
    write(summarise([episodes_of(d) for d in dirs]), out, f"Repeated runs: {name}")


if __name__ == "__main__":
    main()
