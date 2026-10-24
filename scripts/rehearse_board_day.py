"""Board-day rehearsal on the laptop: every board command of docs/BOARD_DAY.html, with the bitstream emulated.

One command, no second window: the script starts the emulated board (board_sender --mock-lanes ...) itself,
runs each phase against it and prints PASS / FAIL per step and a summary at the end (~20 min).

    py scripts\\rehearse_board_day.py                 every step
    py scripts\\rehearse_board_day.py --only 1 3      only steps 1 and 3
    py scripts\\rehearse_board_day.py --quick         skip the two 5-minute runs (attacks, tamper) and the full test suite

Steps (board phase in brackets):
  1  FPGA bit-exact gate, 4 lanes / 2 lanes / YUYV / single pipeline       (5-7)
  2  ARM C baseline (needs gcc; CC=gcc) and the post-quantum key cost        (8)
  3  live link: receiver + dashboard, board sender, BTN1..BTN3               (10)
  4  the 11 network attacks against the board: 11/11 mitigated, 0 false alarms (11)
  5  tamper inside the board: 25 shots, 25 detected, 1 frame rejected each   (12)
  6  energy table without the USB meter (fps from steps 1-2, Vivado power)   (9)
  7  two-laptop / tamper / button tests, then the full test suite
  8  the bitstreams on this PC: present, with .hwh, run-12 / run-13 hashes (scripts/publish_bitstreams.py)
The emulated board is the Python golden model: its times are never results (64x48 frames keep it fast enough).
Logs: sim_out/rehearsal/<step>.log
"""
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "sim_out" / "rehearsal"
PY = sys.executable
WIN = os.name == "nt"
SMALL = ["--set", "sender.width=64", "--set", "sender.height=48"]
LOCAL = ["--set", "link.host=127.0.0.1", "--set", "link.bind_host=0.0.0.0"]
SCEN_PORTS = ["--set", "link.video_in=47200", "--set", "link.fb_out=47203", "--set", "link.sender_control=47205",
              "--set", "link.bus=[47210]", "--set", "sender.policy=threshold"]
RESULTS = []


def say(*a):
    print(*a, flush=True)


def record(step, name, ok, detail=""):
    RESULTS.append((step, name, ok, detail))
    say(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def run(args, log, timeout=900):
    """Run one command to the end; returns (exit code, output). The output also goes to sim_out/rehearsal/<log>."""
    try:
        r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out, code = r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        out, code = (e.stdout or "") + (e.stderr or "") + "\nTIMEOUT", -1
        out = out if isinstance(out, str) else out.decode("utf-8", "replace")
    (LOGS / log).write_text(out, encoding="utf-8")
    return code, out


def start(args, log):
    """Start a background node (the emulated board, the receiver); its output goes to sim_out/rehearsal/<log>."""
    f = open(LOGS / log, "w", encoding="utf-8")
    kw = dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) if WIN else dict(start_new_session=True)
    return subprocess.Popen([PY, "-u", *args], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, **kw), f


def stop(proc_file):
    """Stop a background node and everything it started (run_all starts one process per node)."""
    p, f = proc_file
    if p.poll() is None:
        if WIN:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()
    f.close()
    time.sleep(1)                                   # let the OS release the UDP ports


def wait_for(path, text, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if path.exists() and text in path.read_text(encoding="utf-8", errors="replace"):
            return True
        time.sleep(1)
    return False


# ------------------------------------------------------------------------------------------------- steps
def step1():
    say("\nStep 1  FPGA bit-exact gate (board phases 5-7)")
    for name, extra in (("4 lanes + E5", ["--mock-lanes", "4", "--mock-e5"]),
                        ("2 lanes + E5", ["--mock-lanes", "2", "--mock-e5"]),
                        ("4 lanes YUYV", ["--mock-lanes", "4", "--mock-e5", "--mock-yuyv"]),
                        ("single pipeline", ["--mock"])):
        tag = name.split()[0] + ("yuyv" if "YUYV" in name else "")
        code, out = run(["-m", "future_work.board.first_contact", *extra, "--sizes", "64x48", "--frames", "1",
                         "--timing-frames", "2", "--out", f"sim_out/rehearsal/fc_{tag}"], f"1_first_contact_{tag}.log")
        record(1, f"bit-exact, {name}", code == 0 and "**yes**" in out,
               "" if "**yes**" in out else "see sim_out/rehearsal/1_*.log")


def step2():
    say("\nStep 2  ARM baseline and key-exchange cost (board phase 8)")
    cc = os.environ.get("CC", "gcc" if WIN else "cc")
    if shutil.which(cc) is None:
        record(2, "ARM C baseline", False, f"no C compiler '{cc}' on the PATH (install gcc, open a new window)")
    else:
        code, out = run(["-m", "future_work.arm.arm_baseline", "--sizes", "64x48", "--frames", "2",
                         "--out", "sim_out/rehearsal/arm"], "2_arm_baseline.log")
        record(2, "ARM C baseline: bit-exact gate + table", code == 0 and "ours on the PS, E5" in out)
    code, out = run(["experiments/pq_kex_cost.py", "--runs", "3"], "2_pq_kex_cost.log")
    record(2, "post-quantum key cost", code == 0 and "total (ms)" in out)


def step3():
    say("\nStep 3  live link, board as camera, BTN1-BTN3 (board phase 10)")
    rx = start(["-m", "link.run_all", "--no-sender", "--pq-kex", "--set", "link.bind_host=0.0.0.0",
                "--set", "link.sender_host=127.0.0.1", "--set", "dashboard.bind_host=127.0.0.1"], "3_receiver.log")
    time.sleep(4)
    tx = start(["-m", "future_work.board.board_sender", "--mock-lanes", "2", "--mock-e5", "--mock-buttons",
                "--pq-kex", *LOCAL, "--set", "link.pad=runmax", *SMALL], "3_board.log")
    try:
        board_log = LOGS / "3_board.log"
        record(3, "key exchange (ML-KEM-768 + X25519)", wait_for(board_log, "session key established", 40))
        record(3, "board sender streaming", wait_for(board_log, "encoder=board", 20))
        time.sleep(20)
        total = {}
        try:
            state = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/state", timeout=5).read())
            total = state["latest"].get("receiver.heartbeat", {}).get("total", {})
        except Exception as e:                       # noqa: BLE001 -- reported as a failed check
            total = {"error": str(e)}
        record(3, "dashboard: frames verified, none rejected", total.get("ok", 0) > 20 and total.get("tag_fail", 1) == 0,
               f"verified {total.get('ok')}, tag failures {total.get('tag_fail')}" if "error" not in total
               else total["error"])
        for n, want in ((2, "BTN2 -> manual"), (1, "BTN1 -> manual"), (3, "BTN3 -> automatic")):
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(
                json.dumps({"cmd": "button", "n": n}).encode(), ("127.0.0.1", 47005))
            record(3, f"BTN{n} pressed: '{want} ...'", wait_for(board_log, want, 5))
    finally:
        stop(tx)
        stop(rx)


def step4():
    say("\nStep 4  the 11 network attacks against the board (board phase 11, ~5 min)")
    out_dir = ROOT / "sim_out" / "rehearsal" / "full_suite"
    shutil.rmtree(out_dir, ignore_errors=True)
    sc = start(["experiments/scenario.py", "--scenario", "experiments/scenarios/full_suite.json",
                "--external-sender", "127.0.0.1", "--board-max-mode", "E5", "--pq-kex",
                "--out", "sim_out/rehearsal/full_suite"], "4_scenario.log")
    time.sleep(5)
    tx = start(["-m", "future_work.board.board_sender", "--mock-lanes", "2", "--mock-e5", "--pq-kex", *LOCAL,
                *SCEN_PORTS, "--set", "link.pad=runmax", *SMALL], "4_board.log")
    try:
        sc[0].wait(600)
    except subprocess.TimeoutExpired:
        pass
    stop(tx)
    stop(sc)
    try:
        d = json.loads((out_dir / "summary.json").read_text())
        ok = d["mitigated_episodes"] == "11/11" and d["false_alarm_windows"] == 0
        record(4, "11/11 attacks mitigated, 0 false alarms", ok,
               f"mitigated {d['mitigated_episodes']}, false-alarm windows {d['false_alarm_windows']}")
    except Exception as e:                           # noqa: BLE001
        record(4, "11/11 attacks mitigated, 0 false alarms", False, f"no summary ({e}); see 4_scenario.log")


def step5():
    say("\nStep 5  tamper inside the board (board phase 12, ~4 min)")
    out_dir = ROOT / "sim_out" / "rehearsal" / "tamper"
    shutil.rmtree(out_dir, ignore_errors=True)
    ht = start(["experiments/hw_tamper.py", "--external-sender", "127.0.0.1", "--trigger", "udp:127.0.0.1",
                "--out", "sim_out/rehearsal/tamper"], "5_hw_tamper.log")
    time.sleep(5)
    tx = start(["-m", "future_work.board.board_sender", "--mock-lanes", "2", "--mock-e5", "--mock-tamper",
                "--mock-buttons", *LOCAL, *SCEN_PORTS, *SMALL], "5_board.log")
    try:
        ht[0].wait(600)
    except subprocess.TimeoutExpired:
        pass
    stop(tx)
    stop(ht)
    md = out_dir / "hw_tamper.md"
    row = next((l for l in md.read_text(encoding="utf-8").splitlines() if l.startswith("| 25 ")), "") if md.exists() else ""
    cells = [c.strip() for c in row.strip("|").split("|")]
    ok = len(cells) >= 5 and cells[:3] == ["25", "25", "0"] and cells[3] == "{'1': 25}" and cells[4] == "0"
    record(5, "25 shots, 25 detected, 1 frame rejected per shot, 0 unexplained", ok,
           row or "no hw_tamper.md; see 5_hw_tamper.log")


def step6():
    say("\nStep 6  energy table without the USB meter (board phase 9)")
    fc = LOGS / "fc_4" / "first_contact.json"
    if not fc.exists():                             # step 1 not run: make the 4-lane result it reads
        run(["-m", "future_work.board.first_contact", "--mock-lanes", "4", "--mock-e5", "--sizes", "64x48",
             "--frames", "1", "--timing-frames", "2", "--out", "sim_out/rehearsal/fc_4"], "6_first_contact.log")
    tpl = (ROOT / "future_work" / "baselines" / "power_template.csv").read_text(encoding="utf-8")
    csv_path = LOGS / "energy.csv"                  # the template at the rehearsal's 64x48 size
    csv_path.write_text(tpl.replace(",640,480,", ",64,48,"), encoding="utf-8")
    args = ["-m", "future_work.baselines.energy_table", str(csv_path), "--no-meter", "--fpga-json", str(fc)]
    arm = LOGS / "arm" / "arm_baseline.json"
    if arm.exists():
        args += ["--arm-json", str(arm)]
    code, out = run(args, "6_energy_table.log")
    record(6, "energy table: FPGA rows from fps + Vivado estimate, no meter", code == 0 and "Vivado estimate" in out,
           "" if code == 0 else "see sim_out/rehearsal/6_energy_table.log")


def step7(quick):
    say("\nStep 7  tests")
    code, out = run(["-m", "pytest", "tests/test_two_laptop.py", "tests/test_hw_tamper.py",
                     "tests/test_board_buttons.py", "-q", "-p", "no:cacheprovider"], "7_board_tests.log")
    record(7, "two-laptop, tamper and button tests", code == 0, out.strip().splitlines()[-1] if out.strip() else "")
    if not quick:
        code, out = run(["-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], "7_full_suite.log", timeout=1200)
        record(7, "full test suite", code == 0, out.strip().splitlines()[-1] if out.strip() else "")


def step8():
    say("\nStep 8  bitstreams on this PC")
    sys.path.insert(0, str(ROOT))
    from scripts import publish_bitstreams as pb
    rows = pb.check(use_manifest=True)
    for r in rows:
        if r["status"] != "missing":                # missing optional images are not a failure
            record(8, f"{r['file']}: present with .hwh, expected build", r["status"] == "ok",
                   r["problem"] or (r["sha256"] or "")[:16])
    n = sum(r["status"] == "ok" for r in rows)
    say(f"  {n} of {len(rows)} board images here; missing optional ones: "
        f"{', '.join(r['file'] for r in rows if r['status'] == 'missing') or 'none'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", type=int, nargs="+", choices=range(1, 9), help="run only these steps")
    ap.add_argument("--quick", action="store_true", help="skip steps 4 and 5 and the full test suite")
    a = ap.parse_args()
    steps = a.only or ([1, 2, 3, 6, 7, 8] if a.quick else [1, 2, 3, 4, 5, 6, 7, 8])
    LOGS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for s in steps:
        {1: step1, 2: step2, 3: step3, 4: step4, 5: step5, 6: step6, 7: lambda: step7(a.quick), 8: step8}[s]()
    fails = [r for r in RESULTS if not r[2]]
    say(f"\n{'=' * 72}\n{len(RESULTS) - len(fails)} of {len(RESULTS)} checks passed in {(time.time() - t0) / 60:.0f} min")
    for step, name, _, detail in fails:
        say(f"  FAIL step {step}: {name}" + (f" -- {detail}" if detail else ""))
    say("Ready for the board: follow docs/BOARD_DAY.html from phase 2." if not fails else
        f"Fix the failures first; the logs are in {LOGS}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
