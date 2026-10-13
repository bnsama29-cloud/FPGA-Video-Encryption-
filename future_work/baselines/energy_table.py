"""Energy per frame = measured power / measured fps -- the board comparison table for the paper.

    python -m future_work.baselines.energy_table future_work/baselines/power_template.csv

The CSV holds what you MEASURED on the PYNQ-Z2 (one row per method and mode):
    method,mode,width,height,fps,power_w,idle_power_w,notes
power_w = board input power while streaming (USB power meter on the 5 V / 12 V supply);
idle_power_w = same board, booted and idle (so "dynamic" power can be reported too).
Writes <csv>.md with fps, power, energy per frame (total and dynamic), and the ratio
to the first row of the same resolution.
"""
import csv
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    rows = [r for r in csv.DictReader(path.open()) if r.get("fps") and not r["method"].startswith("#")]
    if not rows:
        sys.exit("no measured rows yet (fill fps and power_w)")
    lines = ["| Method | Mode | Size | fps | Power (W) | Energy / frame (mJ) | Dynamic energy / frame (mJ) | vs first row |",
             "|---|---|---|---|---|---|---|---|"]
    ref = {}
    for r in rows:
        fps, p = float(r["fps"]), float(r["power_w"])
        idle = float(r["idle_power_w"]) if r.get("idle_power_w") else 0.0
        e = p / fps * 1000.0
        ed = (p - idle) / fps * 1000.0 if idle else float("nan")
        size = f"{r['width']}x{r['height']}"
        ref.setdefault(size, e)
        lines.append(f"| {r['method']} | {r['mode']} | {size} | {fps:.1f} | {p:.2f} | {e:.1f} | "
                     f"{ed:.1f} | {e / ref[size]:.2f}x |")
    out = path.with_suffix(".md")
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines) + f"\n\nwritten {out}")


if __name__ == "__main__":
    main()
