"""N2: Vivado runs for the paper-2 encryptor (area, Fmax, power), one command (DESIGN §8.2 N2).

    python hardware/vivado/neuro/run_vivado_neuro.py --steps ooc usweep blocks bd parse [--jobs 2] [--dry]

Steps (run only when the PC is free of paper-1 runs):
  ooc      nv_top, plan of record U = 2, PAD = 1, at 100 MHz for MAXW x MAXH in {34x34, 128x128, 346x260, 1280x720}
  usweep   nv_top at 1280 x 720 for U in {1, 2, 4} (L = 1: lane builds L >= 2 are not in contract n1's RTL; §6.4)
           and U = 4 at 125 MHz (stretch goal)
  blocks   nv_ascon_core_u (U = 1, 2, 4), nv_feistel, nv_table_gen, nv_tag32 alone
  bd       PYNQ-Z2 block design + bitstream (software/system/board/neuro/block_design_neuro.tcl) -> overlay/neuro/
  power    report_power with a SAIF (set NV_SAIF to an XSim SAIF of the N1 run); without it the vectorless
           estimate of every ooc run is used and labelled "vectorless"
  parse    experiments/neuro_hw_tables.py: sim_build/vivado_neuro_* -> sim_out/neuro/n2/hw_tables.{json,md}
The N2b walk ablation (nv_feistel_walk) is not built: the walk variant exists in the model only (§4.3.4).
Each job's log goes to sim_build/vivado_neuro_logs/<job>.log; a failed job does not stop the others.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TCL = "hardware/vivado/neuro/vivado_ooc_neuro.tcl"
LOGS = ROOT / "sim_build" / "vivado_neuro_logs"
GEOMS = [(34, 34), (128, 128), (346, 260), (1280, 720)]


def jobs_for(step):
    j = []
    if step == "ooc":
        for W, H in GEOMS:
            j.append((f"top_u2_{W}x{H}", ["nv_top", "10.0", "U", "2", "MAXW", str(W), "MAXH", str(H)]))
    elif step == "usweep":
        for U in (1, 2, 4):
            j.append((f"top_u{U}_1280x720", ["nv_top", "10.0", "U", str(U)]))
        j.append(("top_u4_1280x720_125MHz", ["nv_top", "8.0", "U", "4"]))
    elif step == "blocks":
        for U in (1, 2, 4):
            j.append((f"core_u{U}", ["nv_ascon_core_u", "10.0", "U", str(U)]))
        j += [("feistel", ["nv_feistel", "10.0"]), ("table_gen", ["nv_table_gen", "10.0"]),
              ("tag32_u2", ["nv_tag32", "10.0", "U", "2"])]
    return j


def vivado():
    exe = shutil.which("vivado") or shutil.which("vivado.bat")
    if not exe:
        raise SystemExit("vivado not on PATH (source settings64 / run from the Vivado command prompt)")
    return exe


def run_job(name, cmd, dry):
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{name}.log"
    if dry:
        print("DRY", " ".join(cmd))
        return name, 0, 0.0
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    print(f"{name}: rc={rc} in {time.time() - t0:.0f} s (log {log})")
    return name, rc, time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="+", default=["ooc", "usweep", "blocks", "parse"],
                    choices=["ooc", "usweep", "blocks", "bd", "power", "parse"])
    ap.add_argument("--jobs", type=int, default=2, help="parallel Vivado runs (each needs ~6 GB RAM)")
    ap.add_argument("--dry", action="store_true", help="print the commands only")
    a = ap.parse_args()
    exe = "vivado" if a.dry else None
    todo = []
    for s in a.steps:
        for name, args in jobs_for(s):
            todo.append((name, [exe or vivado(), "-mode", "batch", "-nojournal", "-nolog", "-source", TCL,
                                "-tclargs", *args]))
    results = []
    if todo:
        with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
            results = list(ex.map(lambda t: run_job(t[0], t[1], a.dry), todo))
    if "bd" in a.steps:
        results.append(run_job("bd", [exe or vivado(), "-mode", "batch", "-nojournal", "-nolog", "-source",
                                      "software/system/board/neuro/block_design_neuro.tcl"], a.dry))
    if "power" in a.steps and not os.getenv("NV_SAIF"):
        print("power: NV_SAIF not set; the tables use the vectorless estimate (labelled)")
    if "parse" in a.steps:
        subprocess.run([sys.executable, str(ROOT / "experiments" / "neuro_hw_tables.py")], cwd=ROOT, check=False)
    bad = [n for n, rc, _ in results if rc]
    if bad:
        raise SystemExit(f"failed jobs: {', '.join(bad)}")


if __name__ == "__main__":
    main()
