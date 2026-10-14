"""The whole Vivado day in one command: XSim check, post-route numbers, overlay, paper table.

Open a terminal where Vivado is on the PATH, then from the repository root:
    Windows:  "C:\\Xilinx\\Vivado\\<version>\\settings64.bat"   (or open "Vivado <version> Tcl Shell")
    Linux:    source /tools/Xilinx/Vivado/<version>/settings64.sh

    python vivado/run_vivado_day.py                  # xsim + ooc + bd + parse  (~1 h of tool time)
    python vivado/run_vivado_day.py --steps xsim ooc parse      # skip the block design
    python vivado/run_vivado_day.py --steps ooc --blocks --fmax # + per-block runs, confirm fmax
    python vivado/run_vivado_day.py --dry-run        # only print what it would run
    python vivado/run_vivado_day.py --steps bd --fclk 50        # overlay at 50 MHz
    python vivado/run_vivado_day.py --steps bd --jobs 1         # less RAM (8 GB laptops: 1-2)
    python vivado/run_vivado_day.py --maxw 9 10                 # + line-buffer memory sweep
    python vivado/run_vivado_day.py --steps ooc parse --periods 8.0 6.667   # clock sweep 125/150 MHz
Run it from a normal terminal with YOUR Python (numpy + pillow), not with `exec` from the
Vivado Tcl console: that uses Vivado's bundled Python and hides all output until the end.

Steps (each logs to sim_build/vivado_logs/<step>.log and is checked, not just run):
  xsim   golden-model vectors -> XSim self-checking testbench -> "XSIM RESULT: PASS"
         -> check_xsim_output.py rebuilds the JPEGs and runs the receiver on them
  ooc    out-of-context synthesis + place + route of secure_jpeg_top at 100 MHz
         (--blocks: also the Ascon core, keystream, tag, DCT, quantiser, Huffman on their own;
          --fmax: re-run the top at the period the first run's slack suggests, to confirm fmax)
  bd     PYNQ-Z2 block design + bitstream -> future_work/board/overlay/secure_jpeg.bit/.hwh
  parse  every report -> sim_out/vivado/vivado_tables.md (the paper's hardware table)
At the end it prints a PASS/FAIL table with the time of every step. Paste a FAIL's log
(the first "ERROR:" line and ~20 lines around it) into Claude with docs/TEAM_CONTEXT.md.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "sim_build" / "vivado_logs"
BLOCKS = ["ascon_aead128_core", "keystream_gen", "tag_unit", "dct8x8", "quantiser", "huffman_enc", "selective_enc"]
WIN = os.name == "nt"
RESULTS = []


def run(name, cmd, check=None, dry=False):
    """Run one command from the repo root, log it, check for a success marker."""
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{name}.log"
    print(f"\n=== {name}\n$ {cmd}", flush=True)
    if dry:
        RESULTS.append((name, "DRY", 0.0, str(log)))
        return ""
    t0 = time.time()
    p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True, errors="replace")
    out = p.stdout + p.stderr
    log.write_text(out)
    ok = p.returncode == 0 and (check is None or re.search(check, out) is not None)
    dt = time.time() - t0
    RESULTS.append((name, "PASS" if ok else "FAIL", dt, str(log)))
    tail = [line for line in out.splitlines() if line.startswith(("RESULT", "XSIM RESULT", "CHECK", "ERROR"))][-6:]
    print("\n".join(tail) or "\n".join(out.splitlines()[-5:]))
    print(f"--> {'PASS' if ok else 'FAIL'} in {dt / 60:.1f} min   (log: {log.relative_to(ROOT)})", flush=True)
    if not ok:
        errs = [line for line in out.splitlines() if "ERROR" in line][:3]
        print("first errors:\n  " + "\n  ".join(errs) if errs else
              "first lines of the log:\n  " + "\n  ".join(out.splitlines()[:8]))
    return out


def vivado(name, script, args="", check=None, dry=False):
    tcl_args = f" -tclargs {args}" if args else ""
    log = (LOGS / f"{name}_vivado.log").relative_to(ROOT).as_posix()      # relative: no spaces from the user's path
    return run(name, f"vivado -mode batch -nojournal -log {log} -source {script}{tcl_args}",
               check, dry)


def step_xsim(a):
    run("xsim_vectors", f"{sys.executable} vivado/gen_xsim_vectors.py", dry=a.dry_run)
    sim = "vivado\\run_xsim.bat" if WIN else "bash vivado/run_xsim.sh"
    run("xsim_run", sim, check=r"XSIM RESULT: PASS", dry=a.dry_run)
    run("xsim_check", f"{sys.executable} vivado/check_xsim_output.py", dry=a.dry_run)


def step_ooc(a):
    out = vivado("ooc_secure_jpeg_top", "vivado/vivado_ooc.tcl", "secure_jpeg_top 10.0", r"RESULT top=", a.dry_run)
    for per in a.periods:               # clock sweep (research R5): which block limits 125 / 150 MHz?
        vivado(f"ooc_period_{per}ns", "vivado/vivado_ooc.tcl", f"secure_jpeg_top {per}", r"RESULT top=", a.dry_run)
    for w in a.maxw:                    # memory sweep (GUIDE B19): line buffers for 2^w-pixel lines
        vivado(f"ooc_maxw{w}", "vivado/vivado_ooc.tcl", f"secure_jpeg_top 10.0 LOG_MAXW {w}",
               r"RESULT top=", a.dry_run)
    if a.blocks:
        for b in BLOCKS:
            vivado(f"ooc_{b}", "vivado/vivado_ooc.tcl", f"{b} 10.0", r"RESULT top=", a.dry_run)
    if a.fmax and not a.dry_run:
        m = re.search(r"WNS=(-?[\d.]+)ns", out or "")
        if m:
            wns = float(m.group(1))
            period = max(4.0, round((10.0 - wns) * 1.05 * 2) / 2)      # 5 % margin, 0.5 ns steps
            if abs(period - 10.0) >= 0.5:
                vivado(f"ooc_fmax_{period}ns", "vivado/vivado_ooc.tcl", f"secure_jpeg_top {period}", r"RESULT top=")
            else:
                print("fmax run skipped: slack at 100 MHz is too small to suggest a faster clock")


def step_bd(a):
    vivado("block_design", "future_work/board/block_design.tcl", f"{a.fclk} {a.jobs}", r"RESULT overlay", a.dry_run)
    overlay = ROOT / "future_work" / "board" / "overlay"
    if not a.dry_run:
        have = [f.name for f in overlay.glob("secure_jpeg.*")] if overlay.exists() else []
        print(f"overlay files: {have or 'none'}")


def step_parse(a):
    run("parse_reports", f"{sys.executable} vivado/parse_reports.py", dry=a.dry_run)
    if not a.dry_run:
        run("paper_tables", f"{sys.executable} -m future_work.figures.paper_tables --root sim_out "
                            f"--out sim_out/paper_tables.md")


def check_python():
    """The XSim step runs the golden model, which needs numpy and Pillow. Fail in seconds, not
    after an hour of Vivado runs (bug #18: `exec python ...` typed in the Vivado Tcl console
    starts Vivado's bundled Python, which has numpy but not Pillow)."""
    missing = []
    for mod, pkg in (("numpy", "numpy"), ("PIL", "pillow")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        vivado_py = "vivado" in sys.executable.lower() or "xilinx" in sys.executable.lower()
        sys.exit(f"This Python ({sys.executable}) lacks {', '.join(missing)}.\n"
                 + ("It is Vivado's own Python: do not start this script from the Vivado Tcl console.\n"
                    if vivado_py else "")
                 + "Use your normal Python: open a Command Prompt, run settings64.bat (puts vivado on the\n"
                   "PATH), cd to the repository, then once:  python -m pip install numpy pillow\n"
                   "or skip the simulation:  --steps ooc bd parse")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="+", default=["xsim", "ooc", "bd", "parse"],
                    choices=["xsim", "ooc", "bd", "parse"])
    ap.add_argument("--blocks", action="store_true", help="also implement each main block on its own")
    ap.add_argument("--fmax", action="store_true", help="re-run the top at the clock the slack suggests")
    ap.add_argument("--fclk", type=int, default=100, help="PL clock of the overlay in MHz (block design)")
    ap.add_argument("--periods", type=float, nargs="*", default=[],
                    help="also run the encoder at these clock periods in ns (clock sweep, e.g. 8.0 6.667)")
    ap.add_argument("--maxw", type=int, nargs="*", default=[],
                    help="also run the encoder with LOG_MAXW = these values (memory sweep, e.g. 9 10)")
    ap.add_argument("--jobs", type=int, default=2, help="parallel runs in the block design (each ~2 GB RAM)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and shutil.which("vivado") is None and shutil.which("vivado.bat") is None:
        sys.exit("vivado is not on the PATH: run settings64.bat / settings64.sh first (see the top of this file)")
    if "xsim" in a.steps and not a.dry_run:
        check_python()
    t0 = time.time()
    for s in a.steps:
        globals()[f"step_{s}"](a)
    print("\n" + "\n".join(f"{n:<28}{st:<6}{dt / 60:>6.1f} min   {log}" for n, st, dt, log in RESULTS))
    fails = [n for n, st, *_ in RESULTS if st == "FAIL"]
    print(f"\n{len(RESULTS) - len(fails)} ok, {len(fails)} failed, {(time.time() - t0) / 60:.0f} min in total")
    if not a.dry_run and "parse" in a.steps:
        print(f"Paper table: {ROOT / 'sim_out' / 'vivado' / 'vivado_tables.md'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
