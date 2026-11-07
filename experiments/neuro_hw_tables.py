"""N2 tables: area, Fmax, power and authenticated throughput of the paper-2 Vivado runs.

Usage:
    python experiments/neuro_hw_tables.py [--dir sim_build] [--out sim_out/neuro/n2]

Reads every sim_build/vivado_neuro_* folder written by hardware/vivado/neuro/vivado_ooc_neuro.tcl (through
hardware/vivado/neuro/run_vivado_neuro.py) with paper 1's report parsers (hardware/vivado/run_vivado_day.py,
imported, not edited) and adds per build:
  * RAMB18 per nv_sdp_ram instance (from utilization_hier.txt), to check the 24 / 16 estimate of §6.6;
  * authenticated rate = min(1, tag rate(U), fill-bound rate) words/clk x Fmax (DESIGN §6.3), where tag rate =
    4 words per (8/U + 1) clk and the fill-bound rate is given for a 1 ms packet at the sensor's peak rate
    (fill_clk from neuro.cycle_model); reported in Mev/s at the build's Fmax and at 100 MHz;
  * K_pol generators per build (1 for every n1 build) and the power source (SAIF or vectorless).
Writes sim_out/neuro/n2/hw_tables.{json,md}.
"""
import argparse
import importlib.util
import re
from pathlib import Path

import neuro_common as C
from neuro.cycle_model import fill_clk


def p1_parsers():
    spec = importlib.util.spec_from_file_location("rvd", C.ROOT / "hardware" / "vivado" / "run_vivado_day.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def params(folder):
    name = folder.name.replace("vivado_neuro_", "")
    # the Tcl appends _<period>ns and _<param><value> to the top's name; strip them to get the top back
    # (splitting at "_" gave "nv_ascon" for nv_ascon_core_u and "nv_table" for nv_table_gen)
    d = {"top": re.sub(r"(_\d+(\.\d+)?ns|_(u|maxw|maxh|pad)\d+)+$", "", name)}
    for k, v in re.findall(r"_(u|maxw|maxh|pad)(\d+)", name):
        d[k] = int(v)
    m = re.search(r"_(\d+\.\d+)ns", name)
    d["period"] = float(m.group(1)) if m else 10.0
    return d


def bram_per_ram(hier_text):
    rows = []
    for line in hier_text.splitlines():
        if "nv_sdp_ram" in line or "bank0" in line or "bank1" in line or "bm_ram" in line or "u_fifo" in line:
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            rows.append(c)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=C.ROOT / "sim_build")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    rvd = p1_parsers()
    builds = []
    for f in sorted(a.dir.glob("vivado_neuro_*")):
        if not f.is_dir() or f.name.endswith("logs"):
            continue
        r = rvd.read_folder(f)
        p = params(f)
        U = p.get("u", 2 if "nv_top" in f.name else None)
        fmax = r.get("fmax_mhz")
        row = {"build": f.name.replace("vivado_neuro_", ""), "params": p, "util": r["util"], "timing": r["timing"],
               "fmax_mhz": fmax, "power": r["power"], "power_source": "SAIF" if (f / "power_saif.txt").exists()
               else "vectorless", "missing": r["missing"], "kpol_generators": 1}
        if U and "nv_top" in f.name:
            tag = 4 / (8 // U + 1)
            W, H = p.get("maxw", 1280), p.get("maxh", 720)
            row["tag_words_per_clk"] = tag
            row["fill_clk"] = fill_clk(W, H)
            row["auth_mev_s_100mhz"] = min(1.0, tag) * 100
            row["auth_mev_s_fmax"] = min(1.0, tag) * fmax if fmax else None
        hier = (f / "utilization_hier.txt")
        row["bram_rows"] = bram_per_ram(hier.read_text(errors="replace")) if hier.exists() else []
        builds.append(row)

    def u(r, k):
        v = r["util"].get(k)
        if not v:
            return "-"
        return f"{v[0]:g}" if k == "bram" else int(v[0])     # BRAM tiles come in halves (RAMB18 = 0.5 tile)
    rows = [(b["build"], u(b, "lut"), u(b, "ff"), u(b, "bram"), u(b, "dsp"), b["timing"].get("wns", "-"),
             b["fmax_mhz"] or "-", b.get("auth_mev_s_fmax") or "-", b["power"].get("total", "-"), b["power_source"])
            for b in builds]
    data = {"builds": builds, "meta": C.meta(a, note="authenticated rate = min(1, tag rate) x Fmax; fill-bound "
                                                     "rate per packet is in fill_clk (see §6.3)")}
    md = ["# N2 hardware tables (Vivado, xc7z020clg400-1, post-route OOC)", "",
          "No build found: run hardware/vivado/neuro/run_vivado_neuro.py first." if not builds else
          C.table(["build", "LUT", "FF", "BRAM tiles", "DSP", "WNS ns", "Fmax MHz", "auth Mev/s at Fmax", "power W",
                   "power source"], rows)]
    C.write("n2", "hw_tables", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
