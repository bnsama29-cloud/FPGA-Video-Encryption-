"""ASIC area estimate of the RTL with open standard-cell libraries (journal experiment X12).

    pip install yowasp-yosys          # or have yosys on the PATH
    python experiments/asic_estimate.py                       # crypto blocks, sky130 and Nangate 45 nm
    python experiments/asic_estimate.py --blocks ascon_aead128_core selective_enc secure_jpeg_top
    python experiments/asic_estimate.py --lib path/to/cells.lib --nand2 NAND2_X1

Crypto-hardware papers report area in gate equivalents (GE = area / area of the smallest 2-input NAND), so
an FPGA design can be compared with ASIC designs of the same cipher. This runs Yosys's generic synthesis,
maps flip-flops (dfflibmap) and logic (abc) onto the library's cells, and reads the cell area (stat -liberty).
Libraries (downloaded once into sim_out/asic_estimate/lib/ from the OpenROAD-flow-scripts repository):
  sky130    SkyWater 130 nm, sky130_fd_sc_hd, typical corner (tt, 25 C, 1.80 V); NAND2 = sky130_fd_sc_hd__nand2_1
  nangate45 Nangate Open Cell Library 45 nm (FreePDK45), typical; NAND2 = NAND2_X1

This is logic synthesis only: no placement, routing or timing closure, and RAMs (the line buffers of the
full encoder) become flip-flops, which overstates their area; the table gives each block's memory bits so
that a reader can see when that applies. It is an estimate for comparison, not a tape-out number.
Writes sim_out/asic_estimate/table.md and table.json.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "hardware" / "rtl"
OUT = ROOT / "sim_out" / "asic_estimate"
ORFS = "https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/"
LIBS = {
    "sky130": (ORFS + "sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib", "sky130_fd_sc_hd__nand2_1"),
    "nangate45": (ORFS + "nangate45/lib/NangateOpenCellLibrary_typical.lib", "NAND2_X1"),
}
# sky130's low-power isolation and level-shifter cells are not for ordinary logic (OpenROAD excludes them too)
DONT_USE = " -dont_use *lpflow* -dont_use *probe*"
DEFAULT_BLOCKS = ["ascon_round", "ascon_aead128_core", "keystream_gen", "tag_unit", "selective_enc"]


def yosys_cmd():
    for exe in ("yosys", "yowasp-yosys"):
        if shutil.which(exe):
            return exe
    return None


def fetch_lib(name, dest):
    url, _ = LIBS[name]
    f = dest / Path(url).name
    if not f.exists():
        dest.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            f.write_bytes(r.read())
    return f


def cell_area(lib, cell):
    """Area of one cell in a Liberty file (the NAND2 reference for gate equivalents)."""
    text = Path(lib).read_text(errors="replace")
    m = re.search(r'cell\s*\(\s*"?' + re.escape(cell) + r'"?\s*\)\s*\{.*?area\s*:\s*([\d.]+)', text, re.S)
    if not m:
        raise ValueError(f"cell {cell} not found in {lib}")
    return float(m.group(1))


def script(top, lib, params=()):
    files = " ".join(str(p.relative_to(ROOT)) for p in sorted(RTL.glob("*.v")))
    chp = "".join(f"chparam -set {k} {v} {top}\n" for k, v in params)
    return (f"read_verilog -Ihardware/rtl/include {files}\n{chp}"
            f"hierarchy -top {top}\nproc\nflatten\nopt\nmemory -nomap\ntee -o {{mem}} stat\n"
            f"synth -top {top}\ndfflibmap -liberty {lib}{DONT_USE}\nabc -liberty {lib}{DONT_USE}\nopt_clean\n"
            f"tee -o {{area}} stat -liberty {lib}\n")


def parse(mem_txt, area_txt):
    m = re.search(r"Chip area for (?:top )?module.*?:\s*([\d.]+)", area_txt)
    cells = (re.search(r"Number of cells:\s*(\d+)", area_txt)          # older Yosys
             or re.search(r"^\s*(\d+)\s+\S+\s+cells\s*$", area_txt, re.M))   # Yosys >= 0.50 table
    membits = (re.search(r"Number of memory bits:\s*(\d+)", mem_txt)
               or re.search(r"^\s*(\d+)\s.*memory bits", mem_txt, re.M))
    return dict(area_um2=float(m.group(1)) if m else None, cells=int(cells.group(1)) if cells else None,
                memory_bits=int(membits.group(1)) if membits else 0)


WORK = ROOT / "sim_build" / "asic_estimate"     # under the repository: yowasp-yosys only sees its working folder


def run_block(exe, top, libname, lib, params=()):
    WORK.mkdir(parents=True, exist_ok=True)
    local = WORK / Path(lib).name
    if not local.exists() or local.stat().st_size != Path(lib).stat().st_size:
        shutil.copyfile(lib, local)
    rel = lambda p: p.relative_to(ROOT).as_posix()
    mem, area = WORK / f"{top}_{libname}_mem.txt", WORK / f"{top}_{libname}_area.txt"
    ys = WORK / f"{top}_{libname}.ys"
    ys.write_text(script(top, rel(local), params).format(mem=rel(mem), area=rel(area)))
    r = subprocess.run([exe, "-q", "-s", rel(ys)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        return dict(error=(r.stderr or r.stdout).strip().splitlines()[-1:] or ["yosys failed"])
    return parse(mem.read_text(), area.read_text())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blocks", nargs="+", default=DEFAULT_BLOCKS)
    ap.add_argument("--libs", nargs="+", default=list(LIBS), choices=list(LIBS))
    ap.add_argument("--lib", help="your own Liberty file instead of --libs (with --nand2)")
    ap.add_argument("--nand2", help="with --lib: the NAND2 cell for gate equivalents")
    ap.add_argument("--set", action="append", default=[], metavar="PARAM=VALUE",
                    help="top-level parameter for every block that has it, e.g. LOG_MAXW=9")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    exe = yosys_cmd()
    if exe is None:
        sys.exit("neither yosys nor yowasp-yosys found: pip install yowasp-yosys")
    out = Path(a.out)
    libs = {}
    if a.lib:
        if not a.nand2:
            sys.exit("--lib needs --nand2")
        libs["custom"] = (Path(a.lib).resolve(), a.nand2)
    else:
        for n in a.libs:
            libs[n] = (fetch_lib(n, out / "lib"), LIBS[n][1])
    params = [tuple(s.split("=", 1)) for s in a.set]
    rows = []
    for libname, (lib, nand) in libs.items():
        ge = cell_area(lib, nand)
        for b in a.blocks:
            print(f"{b} / {libname} ...", flush=True)
            r = run_block(exe, b, libname, lib, params if b == "secure_jpeg_top" else ())
            r.update(block=b, lib=libname, nand2_um2=ge,
                     kge=round(r["area_um2"] / ge / 1000, 2) if r.get("area_um2") else None)
            rows.append(r)
    md = ["# ASIC area estimate (Yosys + abc, logic synthesis only)", "",
          "GE = area / area of the library's NAND2. RAMs are mapped to flip-flops (memory bits column).", "",
          "| Block | library | area (um^2) | kGE | cells | memory bits |", "|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            md.append(f"| {r['block']} | {r['lib']} | error: {r['error'][0]} | | | |")
        else:
            md.append(f"| {r['block']} | {r['lib']} | {r['area_um2']:.0f} | {r['kge']} | {r['cells']} | "
                      f"{r['memory_bits']} |")
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.md").write_text("\n".join(md) + "\n")
    (out / "table.json").write_text(json.dumps(rows, indent=1))
    print("\n".join(md))


if __name__ == "__main__":
    main()
