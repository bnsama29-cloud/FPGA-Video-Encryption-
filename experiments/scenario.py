"""Run one scripted attack scenario against the live simulated link and measure it.

    python experiments/scenario.py --scenario experiments/scenarios/quick.json --policy threshold
    python experiments/scenario.py --scenario experiments/scenarios/learning.json --policy bandit --watch
    python experiments/scenario.py --scenario experiments/scenarios/full_suite.json --external-sender <BOARD IP>
        (the PYNQ-Z2 is the sender; the script prints the command to start on the board
         and starts the scenario clock when the board's first report arrives)
    python experiments/scenario.py --scenario experiments/scenarios/full_suite.json --external-sender <BOARD IP> \
        --attacker <ATTACKER LAPTOP IP>
        (two laptops: the channel = the attacker runs on its own laptop between the
         board and this one; only the receiver runs here. Prints the commands for the attacker laptop and
         the board. Attacks are still started by this script, over the control port of the attacker node)

Starts channel + receiver + sender on their own port block (so a dashboard on the
default ports is not disturbed; --watch also sends telemetry to the dashboard),
replays the scenario's timeline of attacks / impairments, records every bus
event, and writes to the run folder:
    events.jsonl      every telemetry event
    windows.csv       one row per sender defence window (mode, threat, counts ...)
    episodes.csv      one row per attack episode (detection, time to mitigate ...)
    summary.json      everything aggregated (see analyse())

Scenario file (JSON):
    {"name": "...", "end_s": 120,
     "steps": [{"at": 15, "attack": "bitflip", "duration": 8, "rate": 1.0},
               {"at": 40, "impair": {"loss": 0.05}}, ...]}
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link import config, wire               # noqa: E402
from link.buslog import BusLogger           # noqa: E402

MODES = ["E0", "E1", "E2", "E3", "E4", "E5"]


BOARD_BIT = "system/board/overlay/secure_jpeg_lanes.bit"


def board_command(base_port, policy, laptop="<LAPTOP IP>", extra_sets=(), pq_kex=False, bus_host=None,
                  bitfile=BOARD_BIT):
    """The board_sender command whose ports match a scenario run on base_port. Settings that
    both ends must share (the pre-shared key, keys.*) are passed on, or every frame would fail its tag.
    bus_host: two-laptop setup -- video goes to `laptop` (the attacker), telemetry to bus_host (the receiver)."""
    ports = [f"link.host={laptop}", "link.bind_host=0.0.0.0", f"link.video_in={base_port}",
             f"link.fb_out={base_port + 3}", f"link.sender_control={base_port + 5}",
             f"link.bus=[{base_port + 10}]", f"sender.policy={policy}"]
    if bus_host:
        ports.append(f"link.bus_host={bus_host}")
    ports += [x for x in extra_sets if x.startswith(("keys.", "link.pad", "sender."))]
    return (f"sudo -E python3 -m system.board.board_sender --bitfile {bitfile} "
            + ("--pq-kex " if pq_kex else "") + " ".join(f"--set {x}" for x in ports))


def attacker_command(base_port, receiver_ip, board_ip, kex_tamper_s=0.0, dashboard=True):
    """The channel (attacker) node for the attacker laptop, ports matching a scenario run on base_port.
    Telemetry goes to the receiver laptop's logger and, with dashboard, to a dashboard on the attacker
    laptop itself (the attacker's screen: the 'wire' and 'attacker' tiles)."""
    bus = [f"'{receiver_ip}:{base_port + 10}'"] + (["'127.0.0.1:47010'"] if dashboard else [])
    sets = [f"link.host={receiver_ip}", f"link.sender_host={board_ip}", "link.bind_host=0.0.0.0",
            f"link.video_in={base_port}", f"link.video_out={base_port + 1}", f"link.fb_in={base_port + 2}",
            f"link.fb_out={base_port + 3}", f"link.control={base_port + 4}",
            f"\"link.bus=[{','.join(bus)}]\"", "channel.kex_relay=true"]
    if kex_tamper_s:
        sets.append(f"channel.kex_tamper_s={kex_tamper_s}")
    return "py -m link.channel " + " ".join(f"--set {x}" for x in sets)


def local_ip_towards(host):
    """This machine's address on the route to host (no packet is sent)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 9))
        return s.getsockname()[0]
    except OSError:
        return "<THIS LAPTOP IP>"
    finally:
        s.close()


def run(scenario, policy, out, base_port=47200, extra_sets=(), watch=False, memory=None, quiet=False,
        external_sender=None, wait_s=600, board_max_mode="E4", pq_kex=False, attacker=None,
        board_bitfile=BOARD_BIT, kex_tamper_s=0.0, hw_trigger=None):
    """external_sender = the board's IP: start only channel + receiver here, listen on the network,
    and let the PYNQ-Z2 (system/board/board_sender.py) be the sender. board_max_mode = the top level
    the bitstream offers: E4 for the run-6 bitstreams, E5 for a lane bitstream with VERSION bit 7.
    attacker = the attacker laptop's IP (needs external_sender): the channel runs there, only the receiver
    here; this laptop still starts the attacks (control port of the remote channel) and logs everything.
    hw_trigger(step) runs the scenario's {"hw": ...} steps (experiments/hw_tamper.py: one shot of the
    tamper injector in the FPGA); each is logged as a src="hw" event with this PC's time."""
    if attacker and not external_sender:
        raise ValueError("--attacker needs --external-sender (the board is the sender in the two-laptop setup)")
    sc = json.loads(Path(scenario).read_text())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bus = [base_port + 10] + ([47010] if watch else [])
    sets = [f"link.video_in={base_port}", f"link.video_out={base_port + 1}", f"link.fb_in={base_port + 2}",
            f"link.fb_out={base_port + 3}", f"link.control={base_port + 4}",
            f"link.sender_control={base_port + 5}", f"link.bus={bus}",
            f"sender.policy='{policy}'",
            f"defence.memory_file='{memory or (out / 'bandit_memory.json')}'"] + list(sc.get("set", [])) + list(extra_sets)
    me = local_ip_towards(attacker) if attacker else None
    if attacker:
        # the receiver sends feedback and control to the attacker (link.host); its telemetry stays here
        sets += [f"link.host='{attacker}'", "link.bus_host='127.0.0.1'"]
        print("\nOn the ATTACKER laptop, start this first (and `py -m link.dashboard` for its screen):\n  "
              + attacker_command(base_port, me, external_sender, kex_tamper_s), flush=True)
    to_board = dict(laptop=attacker or "<LAPTOP IP>", bus_host=me, bitfile=board_bitfile)
    if external_sender:
        # the top level is what the bitstream offers (system/board/board_sender.py caps at E4 unless
        # VERSION bit 7 says the RTL has E5); 'mitigated' means reaching that level (bug #31)
        sets += ["link.bind_host='0.0.0.0'", f"link.sender_host='{external_sender}'",
                 f"defence.max_mode='{board_max_mode}'"]
    if pq_kex:
        # post-quantum session key first (link/kex.py); the pre-shared key then only authenticates it
        kx = sets + (["link.bind_host='0.0.0.0'"] if external_sender else [])
        kargs = [x for s in kx for x in ("--set", s)]
        if external_sender:
            print("\nStart the sender on the board now (same ports as this run):\n  "
                  + board_command(base_port, policy, extra_sets=extra_sets, pq_kex=True, **to_board)
                  + "\nWaiting for the key exchange ...", flush=True)
            tx = None
        else:
            tx = subprocess.Popen([sys.executable, "-m", "link.kex", "--role", "sender"] + kargs, cwd=ROOT)
        if subprocess.call([sys.executable, "-m", "link.kex", "--role", "receiver", "--timeout", str(wait_s)]
                           + kargs, cwd=ROOT) != 0:
            raise RuntimeError("post-quantum key exchange failed")
        if tx is not None:
            tx.wait(timeout=30)
        sets += ["keys.master_file='configs/session_key.txt'"]
    args = [x for s in sets for x in ("--set", s)]
    cfg = config.load(overrides=sets)
    log = BusLogger(base_port + 10, host="0.0.0.0" if external_sender else "127.0.0.1")
    out_log = None if not quiet else subprocess.DEVNULL
    nodes = ("receiver",) if attacker else ("channel", "receiver") if external_sender else ("channel", "receiver", "sender")
    procs = [subprocess.Popen([sys.executable, "-m", f"link.{n}"] + args, cwd=ROOT, stdout=out_log)
             for n in nodes]
    if external_sender:
        if not pq_kex:
            print("\nStart the sender on the board now (same ports as this run):\n  "
                  + board_command(base_port, policy, extra_sets=extra_sets, **to_board))
        print("Waiting for the board's first report ...", flush=True)
        t_wait = time.time()
        while not log.take("window", "sender"):
            if time.time() - t_wait > wait_s:
                for p in procs:
                    p.terminate()
                log.close()
                raise RuntimeError(f"no report from the board in {wait_s} s: check IPs, firewall and ports")
            time.sleep(0.2)
        print("board is streaming: scenario clock starts", flush=True)
    t0 = time.time()
    hw_events = []
    try:
        for step in sorted(sc["steps"], key=lambda s: s["at"]):
            while time.time() - t0 < step["at"]:
                time.sleep(0.05)
                if any(p.poll() is not None for p in procs):
                    raise RuntimeError("a node exited early; run it alone to see the error")
            if "attack" in step:
                wire.send_control(cfg, "control", cmd="attack", type=step["attack"],
                                  duration=step.get("duration", 10), rate=step.get("rate", 1.0))
            if "impair" in step:
                wire.send_control(cfg, "control", cmd="impair", **step["impair"])
            if "hw" in step:
                if hw_trigger is None:
                    raise RuntimeError("the scenario has hardware steps: run it with experiments/hw_tamper.py")
                t_hw = time.time()
                hw_events.append(dict(src="hw", kind="hw_" + str(step["hw"]), t=t_hw, info=hw_trigger(step)))
            if not quiet:
                print(f"  t={time.time() - t0:5.1f}s  {step}")
        while time.time() - t0 < sc["end_s"]:
            time.sleep(0.2)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
        time.sleep(0.3)
        log.close()
    events = sorted(log.take() + hw_events, key=lambda e: e["t"])
    with open(out / "events.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    summary = analyse(events, cfg, t0)
    summary.update(scenario=sc.get("name", Path(scenario).stem), policy=policy)
    write_tables(summary, out)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def analyse(events, cfg, t0):
    """Turn the event log into the numbers for the paper."""
    d = cfg["defence"]
    leak, cost_tab = d["leakage"], d["cost"]
    top = d["max_mode"]
    windows = [e for e in events if e["src"] == "sender" and e["kind"] == "window"]
    frames = [e for e in events if e["src"] == "receiver" and e["kind"] == "frame"]
    starts = [e for e in events if e["kind"] == "attack_start"]
    ends = [e for e in events if e["kind"] == "attack_end"]
    episodes = []
    for s in starts:
        end = next((e["t"] for e in ends if e["type"] == s["type"] and e["t"] >= s["t"]), s["t"] + s["duration"])
        ep = dict(type=s["type"], start=s["t"] - t0, end=end - t0, duration=end - s["t"])
        bad = [f for f in frames if s["t"] <= f["t"] <= end + 2 and f["verdict"] != "ok"]
        ep["rx_rejected"] = len(bad)
        ep["rx_first_rejection_s"] = round(bad[0]["t"] - s["t"], 3) if bad else None
        # only windows inside this episode (+ a short tail), never the next attack's reaction
        ws = [w for w in windows if s["t"] <= w["t"] <= end + 5.0]
        aware = next((w for w in ws if w["threat"] >= 0.5), None)
        ep["sender_aware_s"] = round(aware["t"] - s["t"], 3) if aware else None
        # mitigated = the top level available is reached (E5 on the laptop; E4 on the board, which has no E5).
        # With top = E5 this is the old rule leak <= leak[E5] = 0 exactly (only E5 has zero leakage).
        mit = next((w for w in ws if MODES.index(w["mode"]) >= MODES.index(top)), None)
        ep["time_to_mitigate_s"] = round(mit["t"] - s["t"], 3) if mit else None
        during = [w for w in windows if s["t"] <= w["t"] <= end + 1]
        ep["mean_leakage_during"] = round(sum(leak[w["mode"]] for w in during) / len(during), 4) if during else None
        ep["modes_during"] = "".join(w["mode"][1] for w in during)
        ep["rekeys"] = sum(1 for e in events if e["kind"] == "rekey" and s["t"] <= e["t"] <= end + 2)
        episodes.append(ep)

    def under_attack(t, slack=2.0):
        return any(s["t"] <= t <= next((e["t"] for e in ends if e["type"] == s["type"] and e["t"] >= s["t"]),
                                       s["t"] + s["duration"]) + slack for s in starts)

    calm = [w for w in windows if not under_attack(w["t"], slack=d["hold_s"] + 2)]
    false_alarm = [w for w in calm if w["threat"] >= 0.5]
    verdicts = {}
    for f in frames:
        verdicts[f["verdict"]] = verdicts.get(f["verdict"], 0) + 1
    lat = sorted(f["latency_ms"] for f in frames if f["verdict"] == "ok" and f.get("latency_ms") is not None)
    tt = [e["time_to_mitigate_s"] for e in episodes if e["time_to_mitigate_s"] is not None]
    return dict(
        windows=len(windows),
        episodes=episodes,
        frames=verdicts,
        latency_ms_median=lat[len(lat) // 2] if lat else None,
        latency_ms_p95=lat[int(len(lat) * 0.95)] if lat else None,
        mean_cost=round(sum(cost_tab[w["mode"]] for w in windows) / max(1, len(windows)), 4),
        mean_cost_calm=round(sum(cost_tab[w["mode"]] for w in calm) / max(1, len(calm)), 4),
        mean_enc_fraction=round(sum(w["enc_fraction"] for w in windows) / max(1, len(windows)), 4),
        mean_leakage_under_attack=round(sum(e["mean_leakage_during"] or 0 for e in episodes) / max(1, len(episodes)), 4),
        mean_time_to_mitigate_s=round(sum(tt) / len(tt), 3) if tt else None,
        mitigated_episodes=f"{len(tt)}/{len(episodes)}",
        false_alarm_windows=len(false_alarm),
        calm_windows=len(calm),
        timeline=[dict(t=round(w["t"] - t0, 2), mode=w["mode"], threat=w["threat"], counts=w["counts"]) for w in windows],
        attacks=[dict(type=e["type"], start=e["start"], end=e["end"]) for e in episodes],
    )


def write_tables(summary, out):
    eps = summary["episodes"]
    if eps:
        with open(out / "episodes.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(eps[0]))
            w.writeheader()
            w.writerows(eps)
    with open(out / "windows.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "mode", "threat", "ok", "lost", "tag_fail", "replay", "malformed", "stale_epoch",
                    "fb_forged", "fb_replay"])
        for r in summary["timeline"]:
            c = r["counts"]
            w.writerow([r["t"], r["mode"], r["threat"], c["ok"], c["lost"], c["tag_fail"], c["replay"],
                        c["malformed"], c["stale_epoch"], c["fb_forged"], c["fb_replay"]])


def print_summary(s):
    print(f"\n{s['scenario']} / {s['policy']}: frames {s['frames']}, "
          f"latency median {s['latency_ms_median']} ms, p95 {s['latency_ms_p95']} ms")
    print(f"{'attack':<11}{'start':>7}{'rx first reject':>16}{'sender aware':>13}{'mitigated':>10}"
          f"{'leak':>7}{'rekeys':>7}  modes")
    for e in s["episodes"]:
        fmt = lambda v: "-" if v is None else f"{v:.1f}s"
        print(f"{e['type']:<11}{e['start']:>6.0f}s{fmt(e['rx_first_rejection_s']):>16}{fmt(e['sender_aware_s']):>13}"
              f"{fmt(e['time_to_mitigate_s']):>10}{e['mean_leakage_during'] or 0:>7.2f}{e['rekeys']:>7}  {e['modes_during']}")
    print(f"mean time to mitigate {s['mean_time_to_mitigate_s']} s ({s['mitigated_episodes']}), "
          f"leakage under attack {s['mean_leakage_under_attack']}, cost {s['mean_cost']} "
          f"(calm {s['mean_cost_calm']}), false alarms {s['false_alarm_windows']}/{s['calm_windows']} calm windows")
    if (s["latency_ms_median"] or 0) > 60000:
        print("WARNING: latency over a minute means the board's clock differs from the laptop's, so the latency and "
              "the sender-side times above are wrong. Run py scripts\\set_board_clock.py and run this again.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=str(ROOT / "experiments" / "scenarios" / "quick.json"))
    ap.add_argument("--policy", default="threshold", choices=["fixed", "threshold", "bandit"])
    ap.add_argument("--out", help="run folder (default sim_out/runs/<scenario>_<policy>)")
    ap.add_argument("--memory", help="bandit memory file to start from / keep (default: fresh in the run folder)")
    ap.add_argument("--base-port", type=int, default=47200)
    ap.add_argument("--watch", action="store_true", help="also send telemetry to a running dashboard")
    ap.add_argument("--set", action="append", default=[], help="extra config override")
    ap.add_argument("--external-sender", metavar="BOARD_IP",
                    help="the PYNQ-Z2 (board_sender.py) is the sender; start only channel + receiver here")
    ap.add_argument("--board-max-mode", default="E4", choices=["E4", "E5"],
                    help="with --external-sender: E5 when the board runs a lane bitstream with E5 (VERSION bit 7)")
    ap.add_argument("--pq-kex", action="store_true",
                    help="start with the post-quantum session key exchange (link/kex.py) between the two ends")
    ap.add_argument("--attacker", metavar="ATTACKER_IP",
                    help="two laptops: the channel (attacker) runs on this other laptop between board and receiver")
    ap.add_argument("--kex-tamper", type=float, default=0.0, metavar="S",
                    help="with --attacker --pq-kex: the printed attacker command corrupts the key exchange for S s")
    ap.add_argument("--board-bitfile", default=BOARD_BIT, help="bitstream named in the printed board command")
    a = ap.parse_args()
    out = a.out or ROOT / "sim_out" / "runs" / f"{Path(a.scenario).stem}_{a.policy}"
    s = run(a.scenario, a.policy, out, a.base_port, a.set, a.watch, a.memory, external_sender=a.external_sender,
          board_max_mode=a.board_max_mode, pq_kex=a.pq_kex, attacker=a.attacker, board_bitfile=a.board_bitfile,
          kex_tamper_s=a.kex_tamper)
    print_summary(s)
    print(f"\nwritten {out}/")


if __name__ == "__main__":
    main()
