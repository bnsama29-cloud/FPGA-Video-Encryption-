"""Run one scenario under several defence policies and make the paper table + figures.

    python experiments/compare_policies.py                                   # quick.json, ~6 min
    python experiments/compare_policies.py --scenario experiments/scenarios/learning.json \\
           --policies threshold bandit                                       # learning curve, ~16 min
    python experiments/compare_policies.py --replot sim_out/compare/quick    # redraw from saved runs

Writes sim_out/compare/<scenario>/:
    table.md / table.csv        one row per policy (time to mitigate, leakage, cost, false alarms)
    timeline.png                protection level over time, one panel per policy, attacks shaded
    tradeoff.png                leakage under attack vs cost, one point per policy
    rounds.png                  time to mitigate per attack round (learning scenarios)
Runs are sequential (they share the CPU, and timing is part of the result).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import scenario as sc_mod      # noqa: E402

# Validated categorical palette (dataviz reference slots 1-3, fixed order): passes
# lightness, chroma, CVD and normal-vision checks on the light surface.
COLORS = {"fixed": "#2a78d6", "threshold": "#eb6834", "bandit": "#1baf7a"}
INK, INK2, GRID, SURFACE, BAND = "#0b0b0b", "#52514e", "#e4e2dc", "#fcfcfb", "#ecebe6"
MODES = ["E0", "E1", "E2", "E3", "E4", "E5"]


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot(results, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pols = list(results)
    # 1) protection level over time, small multiples (one series per panel)
    fig, axes = plt.subplots(len(pols), 1, figsize=(9, 1.9 * len(pols) + 0.6), sharex=True, facecolor=SURFACE)
    axes = [axes] if len(pols) == 1 else axes
    for ax, p in zip(axes, pols):
        s = results[p]
        style(ax)
        for a in s["attacks"]:
            ax.axvspan(a["start"], a["end"], color=BAND, lw=0)
            ax.text((a["start"] + a["end"]) / 2, 5.35, a["type"], ha="center", va="bottom", fontsize=7.5, color=INK2)
        t = [w["t"] for w in s["timeline"]]
        m = [MODES.index(w["mode"]) for w in s["timeline"]]
        ax.step(t, m, where="post", color=COLORS.get(p, INK), lw=2)
        ax.set_ylim(-0.3, 6.1)
        ax.set_yticks(range(6))
        ax.set_yticklabels(MODES)
        ax.set_title(f"{p} policy", loc="left", fontsize=10, color=INK, pad=12)
    axes[-1].set_xlabel("time (s); shaded = attack running", color=INK2, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "timeline.png", dpi=160)
    plt.close(fig)
    # 2) leakage under attack vs cost (one point per policy, direct labels)
    fig, ax = plt.subplots(figsize=(5.2, 3.8), facecolor=SURFACE)
    style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    for p in pols:
        s = results[p]
        ax.scatter(s["mean_cost"], s["mean_leakage_under_attack"], s=70, color=COLORS.get(p, INK),
                   edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(p, (s["mean_cost"], s["mean_leakage_under_attack"]), xytext=(7, 5),
                    textcoords="offset points", fontsize=9, color=INK)
    ax.set_xlabel("mean cost (fraction of payload bits encrypted)", color=INK2, fontsize=9)
    ax.set_ylabel("mean leakage while attacked\n(edge correlation, lower is better)", color=INK2, fontsize=9)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(out / "tradeoff.png", dpi=160)
    plt.close(fig)
    # 3) time to mitigate per round of each attack type (learning scenarios)
    types = sorted({e["type"] for s in results.values() for e in s["episodes"]})
    rounds = max((sum(1 for e in s["episodes"] if e["type"] == types[0]) for s in results.values()), default=0)
    if rounds >= 2:
        fig, axes = plt.subplots(1, len(types), figsize=(4.2 * len(types), 3.2), facecolor=SURFACE, squeeze=False)
        for ax, ty in zip(axes[0], types):
            style(ax)
            for p in pols:
                eps = [e for e in results[p]["episodes"] if e["type"] == ty]
                y = [e["time_to_mitigate_s"] if e["time_to_mitigate_s"] is not None else float("nan") for e in eps]
                x = list(range(1, len(y) + 1))
                ax.plot(x, y, color=COLORS.get(p, INK), lw=2, marker="o", ms=6, mec=SURFACE, mew=2, label=p)
            ax.set_title(f"{ty}: time to reach maximum protection", loc="left", fontsize=10, color=INK)
            ax.set_xlabel("attack round", color=INK2, fontsize=9)
            ax.set_ylabel("seconds", color=INK2, fontsize=9)
            ax.set_xticks(range(1, rounds + 1))
            ax.set_ylim(bottom=0)
            ax.legend(frameon=False, fontsize=8.5, loc="upper right")
        fig.tight_layout()
        fig.savefig(out / "rounds.png", dpi=160)
        plt.close(fig)


def table(results, out):
    cols = ["policy", "mitigated", "mean_time_to_mitigate_s", "mean_leakage_under_attack", "mean_cost",
            "mean_cost_calm", "false_alarm_windows", "calm_windows", "latency_ms_median", "latency_ms_p95"]
    rows = []
    for p, s in results.items():
        rows.append(dict(policy=p, mitigated=s["mitigated_episodes"], **{c: s.get(c) for c in cols[2:]}))
    with open(out / "table.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    head = ("| Policy | Mitigated | Time to mitigate (s) | Leakage under attack | Cost | Cost when calm "
            "| False alarms | Latency median / p95 (ms) |\n|---|---|---|---|---|---|---|---|\n")
    body = "".join(f"| {r['policy']} | {r['mitigated']} | {r['mean_time_to_mitigate_s']} | "
                   f"{r['mean_leakage_under_attack']} | {r['mean_cost']} | {r['mean_cost_calm']} | "
                   f"{r['false_alarm_windows']}/{r['calm_windows']} | {r['latency_ms_median']} / {r['latency_ms_p95']} |\n"
                   for r in rows)
    (out / "table.md").write_text(head + body)
    print("\n" + head + body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=str(ROOT / "experiments" / "scenarios" / "quick.json"))
    ap.add_argument("--policies", nargs="+", default=["fixed", "threshold", "bandit"])
    ap.add_argument("--out")
    ap.add_argument("--replot", help="folder with <policy>/summary.json from an earlier run")
    ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    if a.replot:
        out = Path(a.replot)
        results = {p.parent.name: json.loads(p.read_text()) for p in sorted(out.glob("*/summary.json"))}
    else:
        out = Path(a.out or ROOT / "sim_out" / "compare" / Path(a.scenario).stem)
        results = {}
        for i, p in enumerate(a.policies):
            print(f"\n=== {Path(a.scenario).stem}: policy {p} ===")
            s = sc_mod.run(a.scenario, p, out / p, base_port=47300 + 20 * i, extra_sets=a.set, quiet=True)
            sc_mod.print_summary(s)
            results[p] = s
    table(results, out)
    plot(results, out)
    print(f"written {out}/ (table.md, table.csv, timeline.png, tradeoff.png"
          f"{', rounds.png' if (out / 'rounds.png').exists() else ''})")


if __name__ == "__main__":
    main()
