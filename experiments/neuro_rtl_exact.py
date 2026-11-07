"""N1: is the paper-2 RTL bit-exact against the golden model, and how well does the cycle model predict it?

Usage:
    python experiments/neuro_rtl_exact.py [--full] [--seeds 1 2 3] [--quick]

Method (DESIGN §7.2, §8.2 N1). Runs the cocotb testbenches of hardware/tb/neuro/ (Icarus) once per seed:
  test_nv_feistel (every word leaves after exactly LAT = 16 clk: the fixed-latency claim), test_nv_table_gen,
  test_nv_xor, test_nv_tag32 (U = 1, 2, 4), test_nv_top (the neuro.vectors cases: output words, tlast, commit codes
  and counters vs neuro.sender, random input gaps and output backpressure; --full = FULL=1, every case).
Every test reports its first mismatch (index, input, got, expected) on failure; this script records pass/fail per
module, the words compared and the clocks per case (CYCLES register, via NV_REPORT), and compares the clocks with
neuro.cycle_model at maximum rate (the testbench's random input gaps and backpressure make the RTL slower than
the model's ideal; the ratio is reported, not asserted).
Writes sim_out/neuro/n1/rtl_exact.{json,md}.
"""
import argparse
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import neuro_common as C
from neuro import cycle_model as CM
from neuro import vectors as V
from neuro.packet import from_bytes

TB = C.ROOT / "hardware" / "tb" / "neuro"
MODULES = ["test_nv_feistel", "test_nv_table_gen", "test_nv_xor", "test_nv_tag32", "test_nv_top"]


def run_module(mod, seed, full, report):
    env = dict(os.environ, SEED=str(seed), NV_REPORT=str(report))
    if full:
        env["FULL"] = "1"
    t0 = time.time()
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", str(TB / f"{mod}.py")], cwd=C.ROOT, env=env,
                       capture_output=True, text=True)
    xml = TB / f"{mod}.result.xml"
    tests = fails = 0
    first = ""
    if xml.exists():
        for tc in ET.parse(xml).getroot().iter("testcase"):
            tests += 1
            f = tc.find("failure")
            if f is not None:
                fails += 1
                first = first or (f.get("message") or "")[:300]
    return {"module": mod, "seed": seed, "pytest_rc": p.returncode, "cocotb_tests": tests, "failed": fails,
            "first_failure": first, "seconds": round(time.time() - t0, 1)}


def model_cycles(case_name):
    c = next(c for c in V.cases(full=True) if c.name == case_name)
    r = V.run_model(c)
    pk = []
    words = [w for w, _ in r["out"]]
    i = 0
    raw_pkts = []
    cur = []
    for w, last in r["out"]:
        cur.append(w)
        if last:
            raw_pkts.append(b"".join(int(x).to_bytes(4, "little") for x in cur))
            cur = []
    loads = []
    for b in raw_pkts:
        h = from_bytes(b).header
        if h.level == 4:
            n = (len(b) - 48 - 16 - 12) // 4
            loads.append(CM.PacketLoad(n, 0))
        else:
            p = from_bytes(b)
            loads.append(CM.PacketLoad(p.trailer.n_words, p.trailer.n_cd, 0, len(p.trailer.bitmap) // 4))
    g = c.geom
    del words, i, pk
    return CM.replay(loads, c.level, 2, g.W, g.H, timed=False).cycles


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--quick", action="store_true", help="only nv_top default cases, one seed")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    mods = ["test_nv_top"] if a.quick else MODULES
    seeds = a.seeds[:1] if a.quick else a.seeds
    out_dir = a.out or (C.OUT / "n1")
    from pathlib import Path
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / "top_cases.jsonl"
    report.write_text("", encoding="utf-8")
    runs = [run_module(m, s, a.full, report) for s in seeds for m in mods]
    import json
    cases = [json.loads(l) for l in report.read_text(encoding="utf-8").splitlines() if l.strip()]
    cyc = {}
    for c in cases:
        if c["case"] not in cyc:
            m = model_cycles(c["case"])
            cyc[c["case"]] = m
        c["model_cycles_max_rate"] = cyc[c["case"]]
        c["rtl_over_model"] = c["cycles"] / max(1, cyc[c["case"]])
    ok = all(r["failed"] == 0 and r["pytest_rc"] == 0 for r in runs)
    data = {"all_pass": ok, "runs": runs, "top_cases": cases,
            "meta": C.meta(a, simulator="icarus", note="cycle ratio includes TB input gaps (15 %) and backpressure (25 %)")}
    md = ["# N1 RTL bit-exactness", "", f"All modules pass: **{ok}**", "",
          C.table(["module", "seed", "cocotb tests", "failed", "s", "first failure"],
                  [(r["module"], r["seed"], r["cocotb_tests"], r["failed"], r["seconds"], r["first_failure"] or "-")
                   for r in runs]), "",
          C.table(["case", "seed", "packets", "words out", "RTL clk", "model clk (max rate)", "RTL / model"],
                  [(c["case"], c["seed"], c["packets"], c["words_out"], c["cycles"], c["model_cycles_max_rate"],
                    c["rtl_over_model"]) for c in cases])]
    C.write("n1", "rtl_exact", data, "\n".join(md), out_dir)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
