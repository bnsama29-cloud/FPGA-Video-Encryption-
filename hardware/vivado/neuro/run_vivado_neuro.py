"""N2: Vivado runs for the paper-2 encryptor (area, Fmax, power), one command (DESIGN §8.2 N2).

    python hardware/vivado/neuro/run_vivado_neuro.py --steps ooc usweep blocks bd parse [--jobs 2] [--dry] [--resume]
                                                     [--impl fast|perf]

--impl fast (default): Vivado's default directives, redone with the timing-driven ones only when a build misses
100 MHz; --impl perf: the timing-driven directives everywhere (the flow of 7 Nov, hours per build). Area is the same;
the strategy is written to every build's impl.txt and shown in the N2 table.

Steps (run only when the PC is free of paper-1 runs):
  ooc      nv_top, plan of record U = 2, PAD = 1, at 100 MHz for MAXW x MAXH in {34x34, 128x128, 346x260, 1280x720}
  usweep   nv_top at 1280 x 720 for U in {1, 2, 4} (L = 1: lane builds L >= 2 are not in contract n1's RTL; §6.4).
           Every run is at 100 MHz (the board's clock); Fmax is reported from the slack, no faster-clock builds
  blocks   nv_ascon_core_u (U = 1, 2, 4), nv_feistel, nv_table_gen, nv_tag32 alone
  bd       PYNQ-Z2 block design + bitstream (software/system/board/neuro/block_design_neuro.tcl) -> overlay/neuro/
  power    report_power with a SAIF (set NV_SAIF to an XSim SAIF of the N1 run); without it the vectorless
           estimate of every ooc run is used and labelled "vectorless"
  parse    experiments/neuro_hw_tables.py: sim_build/vivado_neuro_* -> sim_out/neuro/n2/hw_tables.{json,md}
The N2b walk ablation (nv_feistel_walk) is not built: the walk variant exists in the model only (§4.3.4).
Each job's log goes to sim_build/vivado_neuro_logs/<job>.log; a failed job does not stop the others.
"""
import argparse
import hashlib
import os
import re
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
        for U in (1, 4):                   # U = 2 at 1280 x 720 is the last `ooc` build (not built twice)
            j.append((f"top_u{U}_1280x720", ["nv_top", "10.0", "U", str(U)]))
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


SOURCES = ["hardware/rtl/**/*.v", "hardware/rtl/**/*.vh", "hardware/rtl/**/*.sv", "hardware/vivado/neuro/*.tcl",
           "hardware/vivado/neuro/*.xdc"]


def sources_hash(root=None):
    """SHA-256 of every RTL source and the Vivado scripts, line endings normalised (a Windows checkout has CRLF).
    A build is only reused by --resume when it was made from exactly these sources (TESTING bug #76)."""
    root = Path(root or ROOT)
    h = hashlib.sha256()
    for pat in SOURCES:
        for f in sorted(root.glob(pat)):
            h.update(f.relative_to(root).as_posix().encode() + b"\0")
            h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def done(name, current=None):
    """True when this job's log holds its RESULT line AND its .src stamp equals the current sources_hash().
    Before 22 Nov a RESULT line alone counted, so --resume reused builds of older RTL (bug #76)."""
    log, stamp = LOGS / f"{name}.log", LOGS / f"{name}.src"
    if not (log.exists() and "RESULT top=" in log.read_text(errors="replace")):
        return False
    return stamp.exists() and stamp.read_text().strip() == (current or sources_hash())


def overlay_status(text):
    """(rc, message) of the bd step from its log: 0 only with a RESULT overlay line and WNS >= 0 (paper 1 checks the
    same line; a bitstream that misses its clock must not be reported as built)."""
    m = re.search(r"RESULT overlay .*WNS=(-?[\d.]+)ns", text)
    if not m:
        return 1, "bd: no 'RESULT overlay' line (implementation or bitstream failed; see the log)"
    wns = float(m.group(1))
    if wns < 0:
        return 1, f"bd: overlay misses its clock (WNS = {wns} ns): do not use nv.bit"
    return 0, f"bd: overlay meets its clock (WNS = {wns} ns)"


def run_job(name, cmd, dry):
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{name}.log"
    if dry:
        print("DRY", " ".join(cmd))
        return name, 0, 0.0
    t0 = time.time()
    for attempt in (1, 2):                 # a run without a RESULT line is repeated once (paper-1 bug #37)
        with open(log, "w", encoding="utf-8") as f:
            rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        if "RESULT top=" in log.read_text(errors="replace") or "-tclargs" not in cmd:
            break
        text = log.read_text(errors="replace")
        kept = LOGS / f"{name}.attempt{attempt}.log"      # the retry overwrites the log: keep the failed one
        kept.write_text(text, encoding="utf-8")
        errors = [l for l in text.splitlines() if l.startswith(("ERROR", "CRITICAL WARNING"))][:6]
        print(f"{name}: no RESULT line (attempt {attempt}), log kept in {kept.name}; first errors:")
        print("\n".join(errors or text.splitlines()[-8:]))
        rc = rc or 1
        if attempt == 1 and any("[Synth " in l or "[DRC " in l for l in errors):
            break                          # a design / tool error repeats: do not spend another hour on it
    if "RESULT top=" in log.read_text(errors="replace"):
        (LOGS / f"{name}.src").write_text(sources_hash() + "\n")       # which sources this build was made from
    print(f"{name}: rc={rc} in {time.time() - t0:.0f} s (log {log})")
    return name, rc, time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="+", default=["ooc", "usweep", "blocks", "parse"],
                    choices=["ooc", "usweep", "blocks", "bd", "power", "parse"])
    ap.add_argument("--jobs", type=int, default=2, help="parallel Vivado runs (each needs ~6 GB RAM)")
    ap.add_argument("--dry", action="store_true", help="print the commands only")
    ap.add_argument("--impl", choices=["fast", "perf"], default="fast", help="Vivado implementation strategy")
    ap.add_argument("--resume", action="store_true",
                    help="skip jobs already built from the current sources (RESULT line and matching .src stamp)")
    a = ap.parse_args()
    os.environ["NV_IMPL"] = a.impl                 # read by vivado_ooc_neuro.tcl (inherited by every Vivado job)
    exe = "vivado" if a.dry else None
    todo = []
    current = sources_hash()
    for s in a.steps:
        for name, args in jobs_for(s):
            if a.resume and done(name, current):
                print(f"{name}: already built from the current sources ({LOGS / (name + '.log')}), skipped")
                continue
            if a.resume and (LOGS / f"{name}.log").exists():
                print(f"{name}: log is from other or unknown sources, rebuilt")
            todo.append((name, [exe or vivado(), "-mode", "batch", "-nojournal", "-nolog", "-source", TCL,
                                "-tclargs", *args]))
    results = []
    if todo:
        with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
            results = list(ex.map(lambda t: run_job(t[0], t[1], a.dry), todo))
    if "bd" in a.steps:
        name, rc, dt = run_job("bd", [exe or vivado(), "-mode", "batch", "-nojournal", "-nolog", "-source",
                                      "software/system/board/neuro/block_design_neuro.tcl"], a.dry)
        if not a.dry:
            rc, msg = overlay_status((LOGS / "bd.log").read_text(errors="replace"))
            print(msg)
        results.append((name, rc, dt))
    if "power" in a.steps and not os.getenv("NV_SAIF"):
        print("power: NV_SAIF not set; the tables use the vectorless estimate (labelled)")
    if "parse" in a.steps:
        subprocess.run([sys.executable, str(ROOT / "experiments" / "neuro_hw_tables.py")], cwd=ROOT, check=False)
    bad = [n for n, rc, _ in results if rc]
    if bad:
        raise SystemExit(f"failed jobs: {', '.join(bad)}")


if __name__ == "__main__":
    main()
