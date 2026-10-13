"""Collect every result file into the paper's tables (one Markdown file, no number typed by hand).

    python -m future_work.figures.paper_tables                         # this repo (sim_out/, future_work/results/)
    python -m future_work.figures.paper_tables --root ~/kaggle_results # an unzipped results.zip (+ real_video_results.zip)

Looks for (whatever exists; missing parts are listed at the end):
  sim_out/runs/full_suite_*_rep*/        reaction time per attack type, mean ± std over repeated runs
  sim_out/runs/benign_*_rep*/            false alarms under benign impairments
  sim_out/benchmark/benchmark.md         RTL cycles per pixel per mode
  mode_tradeoff.json (synthetic + every real clip under sim_out/real/<clip>/ or <root>/<clip>/)
  jigsaw.json (synthetic + every clip)   E5 against the jigsaw solver
  learned_attack results.json (+ real pairs learned_pair*/)
  sim_out/policy_seeds/*/table.md        bandit vs threshold over seeds
  format_compliance.md
Writes <out>/paper_tables.md (default: <root>/paper_tables.md).
"""
import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODES = ["E0", "E1", "E2", "E3", "E4", "E5"]


def ms(v, nd=2):
    v = [x for x in v if isinstance(x, (int, float))]
    if not v:
        return "–"
    sd = statistics.stdev(v) if len(v) > 1 else 0.0
    return f"{statistics.mean(v):.{nd}f} ± {sd:.{nd}f}"


def find(root, pattern):
    return sorted(p for p in root.rglob(pattern) if "repo" not in p.relative_to(root).parts[:1])


def clip_name(p, root):
    """Name of the source a result file belongs to: the clip folder, or 'synthetic'."""
    try:
        src = json.loads(p.read_text()).get("source", "")
    except Exception:
        src = ""
    if src and src != "synthetic":
        return Path(src).stem
    parent = p.parent.name if p.parent.name not in ("jigsaw", "sim_out", "future_work_results", "results") else ""
    return parent or "synthetic"


def reaction_table(root, out, missing):
    runs = find(root, "summary.json")
    suite = [p for p in runs if p.parent.name.startswith("full_suite_") and "_rep" in p.parent.name]
    if not suite:
        missing.append("repeated full_suite runs (sim_out/runs/full_suite_*_rep*)")
        return
    eps = {}
    for p in suite:
        for e in json.loads(p.read_text())["episodes"]:
            eps.setdefault(e["type"], []).append(e)
    out += [f"## Reaction to each attack (full_suite, threshold policy, {len(suite)} runs)", "",
            "| Attack | Episodes | Mitigated | Receiver first rejection (s) | Time to mitigate (s) |", "|---|---|---|---|---|"]
    for t, es in eps.items():
        out.append(f"| {t} | {len(es)} | {sum(e['time_to_mitigate_s'] is not None for e in es)}/{len(es)} | "
                   f"{ms([e['rx_first_rejection_s'] for e in es])} | {ms([e['time_to_mitigate_s'] for e in es])} |")
    s = [json.loads(p.read_text()) for p in suite]
    out += ["", f"Overall: mean time to mitigate {ms([x['mean_time_to_mitigate_s'] for x in s])} s, "
            f"false alarms {sum(x['false_alarm_windows'] for x in s)}/{sum(x['calm_windows'] for x in s)} calm windows, "
            f"latency median {ms([x['latency_ms_median'] for x in s], 0)} ms.", ""]
    benign = [json.loads(p.read_text()) for p in runs if p.parent.name.startswith("benign_") and "_rep" in p.parent.name]
    if benign:
        out += [f"Benign impairments only ({len(benign)} runs): false alarms "
                f"{sum(x['false_alarm_windows'] for x in benign)}/{sum(x['calm_windows'] for x in benign)} windows, "
                f"latency median {ms([x['latency_ms_median'] for x in benign], 0)} ms, "
                f"p95 {ms([x['latency_ms_p95'] for x in benign], 0)} ms.", ""]
    else:
        missing.append("repeated benign runs")
    real = [p for p in runs if p.parent.name.startswith("scenario_")]
    if real:
        out += ["Same attacks with real video as the sender's source:", "",
                "| Source | Mitigated | Time to mitigate (s) | False alarms | Latency median (ms) |", "|---|---|---|---|---|"]
        for p in real:
            x = json.loads(p.read_text())
            out.append(f"| {p.parent.name.replace('scenario_', '')} | {x['mitigated_episodes']} | {x['mean_time_to_mitigate_s']} | "
                       f"{x['false_alarm_windows']}/{x['calm_windows']} | {x['latency_ms_median']} |")
        out.append("")


def leakage_table(root, out, missing):
    files = find(root, "mode_tradeoff.json")
    if not files:
        missing.append("mode_tradeoff.json")
        return
    data = {}
    for p in files:
        d = json.loads(p.read_text())
        data[clip_name(p, root)] = d["modes"]
    names = list(data)
    out += ["## Leakage per mode: edge correlation of the eavesdropper's best picture with the original",
            "(0 = no outline leaks; frames without edges, e.g. black frames, are skipped)", "",
            "| Mode | " + " | ".join(names) + " | Cost (bits encrypted) |", "|" + "---|" * (len(names) + 2)]
    for m in MODES:
        cells = [f"{data[n][m]['edge_corr']:.3f}" if m in data[n] else "–" for n in names]
        cost = next((f"{data[n][m]['cost']:.3f}" for n in names if m in data[n]), "–")
        out.append(f"| {m} | " + " | ".join(cells) + f" | {cost} |")
    out += ["", "SSIM of the eavesdropper's best picture (1 = identical):", "",
            "| Mode | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 1)]
    for m in MODES:
        out.append(f"| {m} | " + " | ".join(f"{data[n][m]['ssim']:.3f}" if m in data[n] else "–" for n in names) + " |")
    out.append("")


def jigsaw_table(root, out, missing):
    files = find(root, "jigsaw.json")
    if not files:
        missing.append("jigsaw.json")
        return
    out += ["## E5 against the jigsaw solver (no key; ground truth from the key)", "",
            "| Source | Frames | Tiles placed correctly | Correct neighbours | Edge corr after solving | Edge corr if positions were known |",
            "|---|---|---|---|---|---|"]
    for p in files:
        d = json.loads(p.read_text())
        s = d["summary"]
        f = lambda k: f"{s[k]['mean']:.3f} ± {s[k]['std']:.3f}"
        out.append(f"| {clip_name(p, root)} | {d['frames']} | {f('position_accuracy')} | {f('neighbour_accuracy')} | "
                   f"{f('edge_corr_solved')} | {f('edge_corr_perfect_placement')} |")
    out.append("")


def learned_table(root, out, missing):
    files = [p for p in find(root, "results.json") if "learned" in str(p)]
    if not files:
        missing.append("learned attack results")
        return
    out += ["## Learned (neural) attacker vs the plain replacement attack", "",
            "| Run | Mode | Train / test frames | Device | Replacement PSNR / SSIM / edge | Learned PSNR / SSIM / edge |",
            "|---|---|---|---|---|---|"]
    for p in files:
        for m, r in json.loads(p.read_text()).items():
            a, b = r["replacement_attack"], r["learned_attack"]
            tag = p.parent.name + (" (pipeline test only)" if r.get("train_frames", 0) < 500 else "")
            out.append(f"| {tag} | {m} | {r.get('train_frames')} / {r.get('test_frames')} | {r.get('device')} | "
                       f"{a['psnr']:.2f} / {a['ssim']:.3f} / {a['edge_corr']:.3f} | {b['psnr']:.2f} / {b['ssim']:.3f} / {b['edge_corr']:.3f} |")
    out.append("")


def include(root, out, missing, pattern, title, start=None):
    files = find(root, pattern)
    if not files:
        missing.append(pattern)
        return
    for p in files:
        text = p.read_text()
        if start:
            if start not in text:
                missing.append(f"'{start}' section in {p.relative_to(root)}")
                continue
            text = text[text.index(start):]
        out += [f"## {title} ({p.parent.name})" if len(files) > 1 else f"## {title}", "", text.strip(), ""]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    out, missing = ["# Paper tables (generated by future_work/figures/paper_tables.py; do not edit by hand)", "",
                    f"Source folder: `{root}`", ""], []
    include(root, out, missing, "benchmark*/benchmark.md", "Hardware: cycles per pixel per mode (RTL simulation)", start="### RTL")
    reaction_table(root, out, missing)
    include(root, out, missing, "policy_seeds/*/table.md", "Bandit vs threshold over seeds (experiments/policy_seeds.py)")
    include(root, out, missing, "compare/*/table.md", "Policies, one run each (experiments/compare_policies.py)")
    leakage_table(root, out, missing)
    jigsaw_table(root, out, missing)
    learned_table(root, out, missing)
    include(root, out, missing, "format_compliance.md", "Format compliance: decoders that open the protected stream")
    if missing:
        out += ["## Not found (run these to complete the tables)", ""] + [f"* {m}" for m in missing]
    dest = Path(a.out) if a.out else root / "paper_tables.md"
    dest.write_text("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\nwritten {dest}")


if __name__ == "__main__":
    main()
