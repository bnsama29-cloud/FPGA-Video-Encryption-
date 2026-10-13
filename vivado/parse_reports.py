"""Turn Vivado reports into the paper's hardware table (no number typed by hand).

    python vivado/parse_reports.py                       # every sim_build/vivado_*/ and the overlay
    python vivado/parse_reports.py sim_build/vivado_secure_jpeg_top future_work/board/overlay

Reads, in each folder: utilization.txt (LUT / FF / BRAM / DSP), timing.txt (WNS, TNS, WHS),
power.txt (total / dynamic / static W) and utilization_hier.txt (per-block LUT / FF).
Writes sim_out/vivado/vivado_tables.md and vivado_results.json; paper_tables.py includes them.

Formats: Vivado 2019.2-2024.x text reports. If a field is missing the table shows "?" and the
script says which file and field -- it never guesses a number.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sim_out" / "vivado"
DEVICE = dict(lut=53200, ff=106400, bram=140, dsp=220)        # xc7z020 totals (for the % column)
ROWS = {"lut": ("Slice LUTs",), "ff": ("Slice Registers", "Register as Flip Flop"),
        "bram": ("Block RAM Tile",), "dsp": ("DSPs",)}


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_utilization(text):
    """{'lut': (used, available, pct), ...} from report_utilization (flat)."""
    res = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        c = _cells(line)
        name = c[0].rstrip("*").strip()
        for key, names in ROWS.items():
            if key not in res and name in names:
                try:
                    used, avail, pct = float(c[1]), float(c[-2]), c[-1]
                    res[key] = (used, avail, float(pct.replace("<", "")))
                except (ValueError, IndexError):
                    pass
    return res


def parse_timing(text):
    """{'wns': ns, 'tns': ns, 'whs': ns, 'met': bool} from report_timing_summary."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "WNS(ns)" in line and "TNS(ns)" in line:
            # fixed column order: WNS, TNS, TNS failing, TNS total, WHS, THS, ... (headers contain spaces)
            for nxt in lines[i + 1:i + 6]:
                parts = nxt.split()
                if parts and not set(nxt.strip()) <= set("- "):
                    try:
                        v = [float(p) for p in parts[:5]]
                    except ValueError:
                        break
                    met = "All user specified timing constraints are met" in text
                    return dict(wns=v[0], tns=v[1], whs=v[4], met=met)
    return {}


def parse_period(text, folder):
    m = re.search(r"\{0\.000\s+([\d.]+)\}\s+([\d.]+)\s+([\d.]+)", text)    # clock table: {0.000 5.000} 10.000 100.000
    if m:
        return float(m.group(2))
    m = re.search(r"_([\d.]+)ns$", folder.name)
    return float(m.group(1)) if m else 10.0


def parse_power(text):
    res = {}
    for key, label in (("total", "Total On-Chip Power (W)"), ("dynamic", "Dynamic (W)"),
                       ("static", "Device Static (W)")):
        m = re.search(r"\|\s*" + re.escape(label) + r"\s*\|\s*([\d.]+)", text)
        if m:
            res[key] = float(m.group(1))
    m = re.search(r"\|\s*Confidence Level\s*\|\s*(\w+)", text)
    if m:
        res["confidence"] = m.group(1)
    return res


def parse_hier(text, depth=2):
    """[(indent_level, instance, module, total_luts, ffs, bram36+bram18/2, dsp)] from the hierarchical report."""
    rows, head = [], None
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        raw = line.strip().strip("|").split("|")
        c = [x.strip() for x in raw]
        if c[0] == "Instance":
            head = c
            continue
        if head is None or len(c) != len(head):
            continue
        level = (len(raw[0]) - len(raw[0].lstrip(" ")) - 1) // 2
        if level > depth:
            continue
        row = dict(zip(head, c))
        num = lambda k: float(row.get(k, "0") or 0)
        try:
            bram = num("RAMB36") + num("RAMB18") / 2
            rows.append((level, c[0], row.get("Module", ""), int(num("Total LUTs")), int(num("FFs")), bram,
                         int(num("DSP48 Blocks") or num("DSP Blocks"))))
        except ValueError:
            continue
    return rows


def read_folder(folder):
    folder = Path(folder)
    rd = lambda n: (folder / n).read_text(errors="replace") if (folder / n).exists() else ""
    t = rd("timing.txt")
    r = dict(folder=str(folder), name=folder.name.replace("vivado_", ""), util=parse_utilization(rd("utilization.txt")),
             timing=parse_timing(t), power=parse_power(rd("power.txt")), hier=parse_hier(rd("utilization_hier.txt")),
             period=parse_period(t, folder), missing=[])
    for f in ("utilization.txt", "timing.txt", "power.txt"):
        if not (folder / f).exists():
            r["missing"].append(f)
    wns = r["timing"].get("wns")
    r["fmax_mhz"] = round(1000 / (r["period"] - wns), 1) if wns is not None and r["period"] - wns > 0 else None
    return r


def fmt(v, nd=0):
    return "?" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def tables(results):
    md = ["## Hardware results from Vivado (post-route, xc7z020clg400-1)", "",
          "| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        u, t, p = r["util"], r["timing"], r["power"]
        cell = lambda k: f"{fmt(u[k][0], 1 if k == 'bram' else 0)} ({u[k][2]:.1f}%)" if k in u else "?"
        md.append(f"| {r['name']} | {cell('lut')} | {cell('ff')} | {cell('bram')} | {cell('dsp')} | "
                  f"{fmt(1000 / r['period'], 0)} | {fmt(t.get('wns'), 3)} | {'yes' if t.get('met') else ('NO' if t else '?')} | "
                  f"{fmt(r['fmax_mhz'], 1)} | {fmt(p.get('total'), 3)} / {fmt(p.get('dynamic'), 3)} |")
    md += ["", "Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.",
           "Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.", ""]
    for r in results:
        if r["hier"]:
            md += [f"### Resource breakdown: {r['name']}", "", "| Block | Module | LUT | FF | BRAM | DSP |",
                   "|---|---|---|---|---|---|"]
            md += [f"| {'&nbsp;' * 2 * lvl}{inst} | {mod} | {lut} | {ff} | {bram:g} | {dsp} |"
                   for lvl, inst, mod, lut, ff, bram, dsp in r["hier"]]
            md.append("")
    probs = [f"* {r['name']}: missing {', '.join(r['missing'])}" for r in results if r["missing"]]
    probs += [f"* {r['name']}: no {k} in utilization.txt" for r in results for k in ROWS if k not in r["util"]
              and not r["missing"]]
    if probs:
        md += ["### Not found (check these files)", ""] + probs
    return "\n".join(md) + "\n"


def main():
    folders = [Path(a) for a in sys.argv[1:]] or sorted((ROOT / "sim_build").glob("vivado_*")) + \
        [p for p in [ROOT / "future_work" / "board" / "overlay"] if p.exists()]
    folders = [f for f in folders if f.is_dir()]
    if not folders:
        sys.exit("no report folders: run vivado/vivado_ooc.tcl (or vivado/run_vivado_day.py) first")
    results = [read_folder(f) for f in folders]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "vivado_results.json").write_text(json.dumps(results, indent=1))
    md = tables(results)
    (OUT / "vivado_tables.md").write_text(md)
    print(md + f"\nwritten {OUT}/vivado_tables.md and vivado_results.json")


if __name__ == "__main__":
    main()
