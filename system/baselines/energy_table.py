"""Energy per frame on the PYNQ-Z2 (A4). The USB power meter is optional.

    python -m system.baselines.energy_table system/baselines/power_template.csv \\
        --fpga-json sim_out/board/lanes4_final/first_contact.json \\
        --arm-json sim_out/board/arm_final/arm_baseline.json            [--no-meter] [--zero-copy]

One CSV row per workload:  method,mode,width,height,fps,power_w,idle_power_w,image,notes

  fps           frames per second. Left empty, it is read from the board's own result files:
                --fpga-json for rows with an `image` (first_contact.json, `full_fps` of that size and mode),
                --arm-json for rows whose `method` is a row name of arm_baseline.md.
  power_w       board input power while that workload runs: the USB meter's 30 s average. Optional.
  idle_power_w  the same board booted and idle (meter). Optional; gives the energy above idle.
  image         Vivado design of the bitstream the row ran (overlay_lanes4, overlay_lanes, overlay, ...).
                With no meter reading, that row uses Vivado's post-route power estimate of the design
                (paper/data/vivado/vivado_results.json) and is marked "Vivado estimate".

Without a meter (--no-meter, or power_w left empty) the FPGA rows get the Vivado estimate and the ARM rows
show their fps only: Vivado has no model of the ARM's load, so their energy stays "not measured".
Ratios are only given between rows of the same size whose power comes from the same source.
Writes <csv>.md and <csv>.json next to the CSV.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIVADO_JSON = ROOT / "paper" / "data" / "vivado" / "vivado_results.json"


def _num(s):
    s = (s or "").strip()
    return float(s) if s else None


def _mode_int(mode):
    m = (mode or "").strip().upper()
    return int(m[1:]) if len(m) == 2 and m[0] == "E" and m[1].isdigit() else None


def vivado_power(image, path=VIVADO_JSON):
    """(watts, label) of Vivado's post-route power estimate for one design, or (None, None)."""
    if not image or not Path(path).exists():
        return None, None
    for e in json.loads(Path(path).read_text(encoding="utf-8")):
        if e.get("name") == image and isinstance(e.get("power"), dict) and e["power"].get("total"):
            p = e["power"]
            return float(p["total"]), f"Vivado estimate ({image}, confidence {p.get('confidence', '?')})"
    return None, None


def fpga_fps(js, size, mode, zero_copy=False):
    """full_fps of that size and mode. zero_copy: the run with the frame already in the DMA buffer (what a camera
    writing into that buffer gives; the other run includes the ARM copying the pixels in with numpy)."""
    rows = [s for s in (js or {}).get("speed", []) if s.get("size") == size and s.get("mode") == mode]
    for s in rows:
        if bool(s.get("zero_copy")) == zero_copy:
            return s.get("full_fps")
    return None


def arm_fps(js, size, method):
    row = (js or {}).get("sizes", {}).get(size, {}).get(method)
    return row.get("fps") if row else None


def build(rows, fpga_js=None, arm_js=None, no_meter=False, vivado_json=VIVADO_JSON, zero_copy=False):
    """Rows of the table: dicts with method, mode, size, fps, power_w, source, energy_mj, dyn_mj, ratio."""
    out = []
    for r in rows:
        size = f"{r['width']}x{r['height']}"
        image = (r.get("image") or "").strip()
        fps = _num(r.get("fps"))
        if fps is None and image:
            fps = fpga_fps(fpga_js, size, _mode_int(r.get("mode")), zero_copy)
        if fps is None and not image:
            fps = arm_fps(arm_js, size, r["method"])
        meter = None if no_meter else _num(r.get("power_w"))
        idle = None if no_meter else _num(r.get("idle_power_w"))
        if meter is not None:
            power, source = meter, "USB meter"
        else:
            power, source = vivado_power(image, vivado_json)
            idle = None                      # Vivado's static power is not the board's idle power
        energy = power / fps * 1000.0 if (power and fps) else None
        dyn = (power - idle) / fps * 1000.0 if (energy is not None and idle) else None
        out.append(dict(method=r["method"], mode=r.get("mode", ""), size=size, fps=fps, power_w=power,
                        source=source or "not measured", energy_mj=energy, dyn_mj=dyn, image=image or None))
    ref = {}
    for o in out:
        if o["energy_mj"] is None:
            o["ratio"] = None
            continue
        key = (o["size"], o["source"].split(" (")[0])
        ref.setdefault(key, o["energy_mj"])
        o["ratio"] = o["energy_mj"] / ref[key]
    return out


def markdown(table, zero_copy=False):
    f = lambda v, fmt: "–" if v is None else format(v, fmt)
    lines = ["| Method | Mode | Size | fps | Power (W) | Power source | Energy / frame (mJ) | Above idle (mJ) | vs first row |",
             "|---|---|---|---|---|---|---|---|---|"]
    for o in table:
        lines.append(f"| {o['method']} | {o['mode']} | {o['size']} | {f(o['fps'], '.1f')} | {f(o['power_w'], '.2f')} | "
                     f"{o['source']} | {f(o['energy_mj'], '.1f')} | {f(o['dyn_mj'], '.1f')} | "
                     f"{'–' if o['ratio'] is None else format(o['ratio'], '.2f') + 'x'} |")
    notes = []
    if any(o["source"].startswith("Vivado") for o in table):
        notes.append("Vivado estimate = post-route power of the whole Zynq design (PS at default activity), not a "
                     "measurement: report it as an estimate, next to the measured fps.")
    if zero_copy:
        notes.append("FPGA fps: first_contact's zero-copy run (the frame is already in the DMA buffer, as a camera "
                     "writing there would leave it); the ARM rows read the frame from memory the same way.")
    if any(o["source"] == "not measured" and o["fps"] for o in table):
        notes.append("not measured = no meter reading and no Vivado model (ARM rows): fps only.")
    return "\n".join(lines) + ("\n\n" + "\n".join(f"* {n}" for n in notes) if notes else "") + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--fpga-json", type=Path, help="first_contact.json of the FPGA run (fills empty fps)")
    ap.add_argument("--arm-json", type=Path, help="arm_baseline.json of the ARM run (fills empty fps)")
    ap.add_argument("--no-meter", action="store_true", help="no USB meter: ignore power_w, use Vivado estimates")
    ap.add_argument("--zero-copy", action="store_true",
                    help="FPGA fps from first_contact's zero-copy timing rows (run it with --zero-copy)")
    ap.add_argument("--vivado-json", type=Path, default=VIVADO_JSON, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p and p.exists() else None
    for p in (a.fpga_json, a.arm_json):
        if p and not p.exists():
            print(f"warning: {p} not found, its fps stay empty")
    rows = [r for r in csv.DictReader(a.csv.open(encoding="utf-8")) if r.get("method") and not r["method"].startswith("#")]
    table = build(rows, load(a.fpga_json), load(a.arm_json), a.no_meter, a.vivado_json, a.zero_copy)
    if not any(o["fps"] for o in table):
        sys.exit("no fps yet: give --fpga-json / --arm-json from the board runs, or fill the fps column")
    md = markdown(table, a.zero_copy)
    a.csv.with_suffix(".md").write_text(md, encoding="utf-8")
    a.csv.with_suffix(".json").write_text(json.dumps(dict(no_meter=a.no_meter, zero_copy=a.zero_copy, rows=table), indent=1), encoding="utf-8")
    print(md + f"\nwritten {a.csv.with_suffix('.md')} / .json")


if __name__ == "__main__":
    main()
