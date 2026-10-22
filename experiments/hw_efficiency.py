"""Hardware figures of merit in the units published FPGA papers use (RESEARCH.md items 12-13, GUIDE B40).

    python experiments/hw_efficiency.py
    python experiments/hw_efficiency.py --vivado sim_out/vivado/vivado_results.json   # a fresh Vivado run

Hardware papers compare designs by throughput per area and energy per unit of work, not by raw LUTs or
raw Mpixel/s alone. This script joins numbers that other scripts already measured, and computes nothing
by hand:
  throughput   Mpixel/s at 100 MHz from RTL simulation: experiments/lanes_rtl_throughput.py (lane encoder,
               per mode, so E5 has its own row) and R1 (stall_profile.py, contract-v2 encoder)
  area, power  post-route Vivado results (run_vivado_day.py parse): LUT/FF/BRAM/DSP; power from the
               SAIF-annotated report of that mode when the run has one (step power), else the vectorless total
  published    paper/data/related/compare.json (numbers copied from each cited source)
Derived columns:
  fps 1080p        Mpixel/s / (1920 x 1080)
  Mpx/s per kLUT   throughput / area, the efficiency metric of hardware papers
  Gbit/s in        Mpixel/s x 24 bit (the RGB data the design consumes), for comparison with cipher cores
  nJ/pixel         total on-chip power / throughput (energy per pixel)
Limits: throughput is RTL simulation with no DMA stalls; SAIF and vectorless power are estimates. A Vivado run
older than the E5 RTL (run 6, 17 Oct 2026) has no E5 logic in its netlist, so with it E5 rows pair E5
throughput with the pre-E5 area; run 7 (18 Oct) includes E5. Board measurements replace both (GUIDE A4).
Writes sim_out/hw_efficiency/hw_efficiency.json and .md.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sim_out" / "hw_efficiency"
DESIGNS = {   # lanes -> Vivado design name (100 MHz, the configurations the board uses)
    "v2": "secure_jpeg_top",
    2: "secure_jpeg_lanes_top_lanes2_log_l1",
    4: "secure_jpeg_lanes_top_lanes4_log_l2_log_maxw10",
}


def first(*paths):
    return next((Path(p) for p in paths if p and Path(p).exists()), None)


def throughput_rows(paths):
    """[(lanes, mode, size, mpx/s)], the largest measured frame per (lanes, mode) over the given files."""
    best, v2 = {}, {}
    for path in paths:
        d = json.loads(path.read_text())
        v2.update(d.get("v2_measured_clocks_per_pixel") or {})
        best = merge(best, d["rows"])
    rows = [(l, m, s, v) for (l, m), (_, s, v) in sorted(best.items())]
    if v2:
        size = max(v2, key=lambda s: int(s.split("x")[0]) * int(s.split("x")[1]))
        rows.insert(0, ("v2", 2, size, 100.0 / v2[size]))
    return rows


def merge(best, rows):
    for r in rows:
        key = (r["lanes"], r.get("mode", 2))
        px = r["width"] * r["height"]
        if key not in best or px > best[key][0]:
            best[key] = (px, f"{r['width']}x{r['height']}", r["mpx_per_s_at_100mhz"])
    return best


def power_of(res, tag):
    """(watts, source) for a design: its SAIF report for this mode when present, else vectorless."""
    saif = (res.get("power_saif") or {}).get(tag)
    if saif and saif.get("total") is not None:
        return saif["total"], f"SAIF ({saif.get('confidence', '?')})"
    p = res.get("power") or {}
    return p.get("total"), f"vectorless ({p.get('confidence', '?')})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vivado", help="vivado_results.json (default: sim_out/vivado, else paper/data/vivado)")
    ap.add_argument("--throughput", nargs="+", help="lanes results.json files (default: paper/data/lanes_rtl and "
                                                    "sim_out/lanes_rtl, the largest frame per lane count and mode)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    viv_path = first(a.vivado, ROOT / "sim_out" / "vivado" / "vivado_results.json",
                     ROOT / "paper" / "data" / "vivado" / "vivado_results.json")
    tp_paths = [Path(p) for p in (a.throughput or [ROOT / "paper" / "data" / "lanes_rtl" / "results.json",
                                                     ROOT / "sim_out" / "lanes_rtl" / "results.json"]) if Path(p).exists()]
    if viv_path is None or not tp_paths:
        raise SystemExit("need a Vivado results json and a lanes throughput json (see the docstring)")
    viv = {r["name"]: r for r in json.loads(viv_path.read_text())}
    rows = []
    tp_src = ", ".join(str(p.resolve().relative_to(ROOT)) for p in tp_paths)
    for lanes, mode, size, mpx in throughput_rows(tp_paths):
        name = DESIGNS.get(lanes)
        res = viv.get(name)
        if res is None or not res.get("timing", {}).get("met"):
            continue
        u = res["util"]
        tag = ("v2" if lanes == "v2" else "v3") + f"_E{mode}"
        watts, psrc = power_of(res, tag)
        lut = u["lut"][0]
        rows.append(dict(design="ours, contract v2 (1 pipeline)" if lanes == "v2" else f"ours, {lanes} lanes",
                         mode=f"E{mode}", vivado=name, size=size, lut=lut, ff=u["ff"][0], bram=u["bram"][0],
                         dsp=u["dsp"][0], mhz=100, mpix_s=mpx, fps_1080p=mpx * 1e6 / (1920 * 1080),
                         mpix_s_per_klut=mpx / (lut / 1000), gbit_s_in=mpx * 24 / 1000,
                         power_w=watts, power_source=psrc,
                         nj_per_px=(watts / (mpx * 1e6) * 1e9) if watts else None,
                         throughput_from=tp_src, area_from=str(viv_path.resolve().relative_to(ROOT))))
    rel_path = ROOT / "paper" / "data" / "related" / "compare.json"
    published = []
    if rel_path.exists():
        for r in json.loads(rel_path.read_text())["rows"]:
            mpx, lut = r.get("mpix_s"), r.get("lut")
            published.append(dict(design=r["work"].replace("\\u{g}", "ğ"), cite=r["cite"], device=r["device"], function=r["function"],
                                  lut=lut, bram=r.get("bram"), dsp=r.get("dsp"), mhz=r.get("mhz"), mpix_s=mpx,
                                  mpix_s_per_klut=(mpx / (lut / 1000)) if (mpx and lut) else None,
                                  crypto=r.get("crypto")))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "hw_efficiency.json").write_text(json.dumps(dict(ours=rows, published=published), indent=1))
    f = lambda v, nd=1: "-" if v is None else f"{v:,.{nd}f}"
    md = [f"# Hardware figures of merit (throughput: {tp_src}; area/power: {viv_path.resolve().relative_to(ROOT)})", "",
          "| Design | Mode | Frame | LUT | BRAM | DSP | MHz | Mpx/s | fps 1080p | Mpx/s per kLUT | Gbit/s in | Power (W) | nJ/pixel |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['design']} | {r['mode']} | {r['size']} | {f(r['lut'], 0)} | {f(r['bram'])} | {f(r['dsp'], 0)} | "
                  f"{r['mhz']} | {f(r['mpix_s'])} | {f(r['fps_1080p'])} | {f(r['mpix_s_per_klut'], 2)} | "
                  f"{f(r['gbit_s_in'], 2)} | {f(r['power_w'], 3)} {r['power_source']} | {f(r['nj_per_px'], 2)} |")
    md += ["", "Published (copied from each source, paper/data/related/compare.json; different devices and functions):", "",
           "| Work | Device | Function | LUT (Stratix: ALUT) | DSP (Stratix: 18-bit mult.) | MHz | Mpx/s | Mpx/s per kLUT | Crypto |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in published:
        md.append(f"| {r['design']} [{r['cite']}] | {r['device']} | {r['function']} | {f(r['lut'], 0)} | {f(r['dsp'], 0)} | "
                  f"{r['mhz']} | {f(r['mpix_s'])} | {f(r['mpix_s_per_klut'], 2)} | {r['crypto']} |")
    md += ["", "Throughput: RTL simulation, no DMA stalls. Power: as labelled (vectorless = estimate). "
               "E5 rows use the area of the Vivado run named above; a run older than the E5 RTL has no E5 logic in it."]
    (out / "hw_efficiency.md").write_text("\n".join(md) + "\n", encoding="utf-8")   # names with non-Latin-1 letters
    print("\n".join(md).encode("ascii", "replace").decode())    # a Windows console is cp1252


if __name__ == "__main__":
    main()
