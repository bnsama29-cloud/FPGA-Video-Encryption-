"""N2 Vivado flow (TESTING bug #61): NV_IMPL=fast by default, redone with the perf directives only when a build misses
the clock; the strategy reaches every build (impl.txt, RESULT line) and the N2 table.

The Tcl script runs in plain tclsh with stand-in Vivado commands (skipped where tclsh is not installed)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TCL = ROOT / "hardware" / "vivado" / "neuro" / "vivado_ooc_neuro.tcl"

STUB = r"""
set ::CALLS {}
foreach c {read_verilog read_xdc synth_design report_utilization opt_design place_design phys_opt_design route_design
           report_timing_summary report_power write_checkpoint open_checkpoint close_design read_saif
           get_timing_paths} {
    proc $c {args} "lappend ::CALLS \[list $c {*}\$args\]; return {}"
}
proc get_property {name obj} {
    set s [lindex $::SLACKS 0]; set ::SLACKS [lrange $::SLACKS 1 end]; if {$s eq ""} {set s 0.1}; return $s
}
rename glob _glob
proc glob {args} { return {} }
set argv {nv_top 10.0 U 2}
set argc 3
source $::SCRIPT
set f [open sim_build/vivado_neuro_nv_top_u2/impl.txt]; set used [string trim [read $f]]; close $f
puts "IMPL=$used"
foreach c $::CALLS { puts "CALL=$c" }
"""


def flow(tmp_path, slacks, impl=None):
    if not shutil.which("tclsh"):
        pytest.skip("tclsh not installed")
    env = {k: v for k, v in os.environ.items() if k != "NV_IMPL"}
    if impl:
        env["NV_IMPL"] = impl
    script = f"set ::SLACKS {{{' '.join(map(str, slacks))}}}\nset ::SCRIPT {{{TCL.as_posix()}}}\n" + STUB
    p = subprocess.run(["tclsh"], input=script, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    used = next(l[5:] for l in p.stdout.splitlines() if l.startswith("IMPL="))
    calls = [l[5:] for l in p.stdout.splitlines() if l.startswith("CALL=")]
    result = next(l for l in p.stdout.splitlines() if l.startswith("RESULT "))
    return used, calls, result


def steps(calls):
    return [c.split()[0] for c in calls if c.split()[0] in ("opt_design", "route_design", "open_checkpoint")]


def test_fast_flow_meeting_timing_uses_default_directives_once(tmp_path):
    used, calls, result = flow(tmp_path, [0.5, 0.5])
    assert used == "fast" and "impl=fast " in result, result
    assert steps(calls) == ["opt_design", "route_design"], steps(calls)
    assert not any("-directive" in c for c in calls if c.startswith(("opt_design", "place_design", "route_design")))


def test_fast_flow_missing_timing_is_redone_with_perf_from_the_synthesised_netlist(tmp_path):
    used, calls, result = flow(tmp_path, [-0.3, 0.2, 0.2])
    assert used == "fast+perf" and "WNS=0.2ns" in result, result
    assert steps(calls) == ["opt_design", "route_design", "open_checkpoint", "opt_design", "route_design"]
    assert "route_design -directive AggressiveExplore" in calls
    assert any(c.startswith("open_checkpoint") and c.endswith("synth.dcp") for c in calls)


def test_perf_flow_is_the_7_nov_flow(tmp_path):
    used, calls, _ = flow(tmp_path, [0.4], impl="perf")
    assert used == "perf"
    assert [c for c in calls if c.startswith(("opt_design", "place_design", "phys_opt_design", "route_design"))] == \
        ["opt_design -directive Explore", "place_design -directive ExtraTimingOpt",
         "phys_opt_design -directive Explore", "route_design -directive AggressiveExplore"]


def test_runner_passes_the_strategy_to_vivado(monkeypatch):
    sys.path.insert(0, str(ROOT / "hardware" / "vivado" / "neuro"))
    import run_vivado_neuro as R
    monkeypatch.delenv("NV_IMPL", raising=False)
    monkeypatch.setattr(sys, "argv", ["x", "--steps", "blocks", "--dry", "--impl", "perf"])
    R.main()
    assert os.environ["NV_IMPL"] == "perf"
    monkeypatch.setattr(sys, "argv", ["x", "--steps", "blocks", "--dry"])
    R.main()
    assert os.environ["NV_IMPL"] == "fast", "fast must be the default"


def test_hw_table_shows_the_strategy(tmp_path):
    for name, impl in (("nv_top_u2", "fast+perf"), ("nv_feistel", None)):
        d = tmp_path / f"vivado_neuro_{name}"
        d.mkdir()
        if impl:
            (d / "impl.txt").write_text(impl + "\n")
    p = subprocess.run([sys.executable, "experiments/neuro_hw_tables.py", "--dir", str(tmp_path), "--out", str(tmp_path)],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    builds = {b["build"]: b["impl"] for b in json.loads((tmp_path / "hw_tables.json").read_text())["builds"]}
    assert builds == {"nv_top_u2": "fast+perf", "nv_feistel": "perf"}, builds


@pytest.mark.parametrize("log,rc,word", [
    ("OVERLAY written ...\nRESULT overlay fclk=100MHz U=2 WNS=0.412ns\n", 0, "meets"),
    ("RESULT overlay fclk=100MHz U=2 WNS=-1.205ns\n", 1, "misses"),          # paper 1 bug #20: never "built"
    ("ERROR: [Place 30-640] ...\n", 1, "no 'RESULT overlay'"),
])
def test_bd_step_fails_without_timing_or_result(log, rc, word):
    sys.path.insert(0, str(ROOT / "hardware" / "vivado" / "neuro"))
    import run_vivado_neuro as R
    got_rc, msg = R.overlay_status(log)
    assert (got_rc, word in msg) == (rc, True), f"log {log!r}: got ({got_rc}, {msg!r}), expected rc {rc} with {word!r}"


def test_bd_script_prints_the_overlay_wns():
    tcl = (ROOT / "software" / "system" / "board" / "neuro" / "block_design_neuro.tcl").read_text()
    assert 'puts "RESULT overlay fclk=${fclk}MHz U=$U WNS=${wns}ns"' in tcl


def test_resume_reuses_a_build_only_from_the_same_sources(tmp_path, monkeypatch):
    """Bug #76: --resume reused any log with a RESULT line, including builds of the RTL before bug #71's fix."""
    sys.path.insert(0, str(ROOT / "hardware" / "vivado" / "neuro"))
    import run_vivado_neuro as R
    monkeypatch.setattr(R, "LOGS", tmp_path)
    (tmp_path / "top_u2_34x34.log").write_text("...\nRESULT top=nv_top WNS=0.1\n")
    assert R.done("top_u2_34x34", "abc") is False, "a log without a .src stamp is from unknown sources"
    (tmp_path / "top_u2_34x34.src").write_text("abc\n")
    assert R.done("top_u2_34x34", "abc") is True
    assert R.done("top_u2_34x34", "def") is False, "sources changed since the build: rebuild"
    (tmp_path / "core_u1.log").write_text("ERROR: out of memory\n")
    (tmp_path / "core_u1.src").write_text("abc\n")
    assert R.done("core_u1", "abc") is False, "no RESULT line: not built"


def test_sources_hash_ignores_line_endings_and_sees_rtl_edits(tmp_path):
    sys.path.insert(0, str(ROOT / "hardware" / "vivado" / "neuro"))
    import run_vivado_neuro as R
    rtl = tmp_path / "hardware" / "rtl" / "neuro"
    rtl.mkdir(parents=True)
    (tmp_path / "hardware" / "vivado" / "neuro").mkdir(parents=True)
    (rtl / "a.v").write_bytes(b"module a;\nendmodule\n")
    h = R.sources_hash(tmp_path)
    (rtl / "a.v").write_bytes(b"module a;\r\nendmodule\r\n")          # Windows checkout
    assert R.sources_hash(tmp_path) == h, "CRLF must not look like an RTL change"
    (rtl / "a.v").write_bytes(b"module a; wire w;\nendmodule\n")
    assert R.sources_hash(tmp_path) != h, "an RTL edit must change the hash"
    assert R.sources_hash() == R.sources_hash(), "deterministic"
