"""Hardware tamper experiment (board day, docs/BOARD_DAY.html, part 6): bits flipped INSIDE the camera.

The overlay secure_jpeg_lanes_tamper.bit has a tamper injector (future_work/board/axis_tamper.v) between
the encoder and the receive DMA, i.e. after the Ascon tag is computed. Each shot flips one bit of one
frame's scan on its way through DMA, DDR, the ARM and the network. The claim to check: the receiver
rejects exactly the tampered frames (one per shot, within one frame time) and nothing else.

On the receiver laptop (Pico on USB, wired to PMOD A pin 1 of the board; SW1 up, SW0 down):
    python experiments/hw_tamper.py --external-sender <BOARD IP> --trigger serial:COM5
    (Linux/macOS: serial:/dev/ttyACM0; needs `pip install pyserial`)
  + --attacker <ATTACKER IP> for the two-laptop setup (the network attacker stays idle in this run)
  It prints the board command (bitstream secure_jpeg_lanes_tamper.bit) like experiments/scenario.py.
Without a Pico: --trigger manual (you press BTN0 when told; latency is then only good to ~1 s).
Rehearsal on one laptop, no board:
    python experiments/hw_tamper.py --external-sender 127.0.0.1 --trigger udp:127.0.0.1
    and in a second window the printed command with --mock-lanes 2 --mock-e5 --mock-tamper instead of --bitfile
Re-analyse a run:  python experiments/hw_tamper.py --analyse sim_out/runs/hw_tamper/events.jsonl

Writes to the run folder (default sim_out/runs/hw_tamper/): events.jsonl, the scenario tables, and
hw_tamper.json / hw_tamper.md: shots, frames rejected per shot, detection latency, missed shots and
rejections that no shot explains.
"""
import argparse
import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
import scenario  # noqa: E402

REJECT = {"tag-mismatch", "malformed"}
TAMPER_BIT = "future_work/board/overlay/secure_jpeg_lanes_tamper.bit"


def make_trigger(spec, sender_control_port):
    """spec: serial:<port> (Pico), udp:<board ip> (--mock-tamper rehearsal), manual (BTN0 by hand), none."""
    kind, _, arg = spec.partition(":")
    if kind == "serial":
        try:
            import serial                                  # pyserial
        except ImportError:
            sys.exit("--trigger serial needs pyserial:  pip install pyserial")
        port = serial.Serial(arg, 115200, timeout=1)
        port.write(b"?\r\n")
        port.readline()                                    # echo (MicroPython REPL echoes the line)
        hello = port.readline().decode(errors="replace").strip()
        if "PICO-TAMPER" not in hello:
            print(f"warning: the Pico did not answer as expected ({hello!r}); is main.py on it?", flush=True)

        def fire(step):
            port.reset_input_buffer()
            port.write(b"S\r\n")
            return "serial"
        return fire
    if kind == "udp":
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        def fire(step):
            s.sendto(json.dumps({"cmd": "tamper_shot"}).encode(), (arg, sender_control_port))
            return "udp"
        return fire
    if kind == "manual":
        def fire(step):
            print("\a   >>> press BTN0 on the board NOW <<<", flush=True)
            return "manual"
        return fire
    if kind == "none":
        return lambda step: "none"
    raise ValueError(f"unknown --trigger {spec!r}")


def analyse_hw(events, window_s=1.5):
    """Match every shot to the first rejected frame within window_s after it (each frame used once)."""
    shots = sorted(e["t"] for e in events if e.get("src") == "hw" and e.get("kind") == "hw_shot")
    frames = sorted((e for e in events if e.get("src") == "receiver" and e.get("kind") == "frame"),
                    key=lambda e: e["t"])
    rejected = [f for f in frames if f["verdict"] in REJECT]
    used, lat, per_shot = set(), [], []
    for i, ts in enumerate(shots):
        t_next = shots[i + 1] if i + 1 < len(shots) else float("inf")
        hits = [k for k, f in enumerate(rejected) if ts <= f["t"] <= min(ts + window_s, t_next) and k not in used]
        per_shot.append(len(hits))
        if hits:
            lat.append(rejected[hits[0]]["t"] - ts)
            used.update(hits)
    unexplained = [f for k, f in enumerate(rejected) if k not in used]
    lat_ms = sorted(round(1000 * x, 1) for x in lat)
    return dict(
        shots=len(shots),
        detected=sum(1 for n in per_shot if n),
        missed=sum(1 for n in per_shot if n == 0),
        frames_rejected_per_shot={str(n): per_shot.count(n) for n in sorted(set(per_shot))},
        frames_ok=sum(1 for f in frames if f["verdict"] == "ok"),
        frames_rejected=len(rejected),
        rejected_verdicts={v: sum(1 for f in rejected if f["verdict"] == v) for v in sorted(REJECT)},
        unexplained_rejections=len(unexplained),
        latency_ms_median=lat_ms[len(lat_ms) // 2] if lat_ms else None,
        latency_ms_max=lat_ms[-1] if lat_ms else None,
        window_s=window_s,
    )


def write_report(r, out):
    out = Path(out)
    (out / "hw_tamper.json").write_text(json.dumps(r, indent=2))
    md = ["| shots | detected | missed | frames rejected / shot | unexplained rejections | ok frames | latency median / max (ms) |",
          "|---|---|---|---|---|---|---|",
          f"| {r['shots']} | {r['detected']} | {r['missed']} | {r['frames_rejected_per_shot']} | "
          f"{r['unexplained_rejections']} | {r['frames_ok']} | {r['latency_ms_median']} / {r['latency_ms_max']} |"]
    (out / "hw_tamper.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--external-sender", metavar="BOARD_IP")
    ap.add_argument("--trigger", default="manual", help="serial:<port> | udp:<board ip> | manual | none")
    ap.add_argument("--attacker", metavar="ATTACKER_IP", help="two-laptop setup (experiments/scenario.py --attacker)")
    ap.add_argument("--scenario", default=str(ROOT / "experiments" / "scenarios" / "hw_tamper.json"))
    ap.add_argument("--policy", default="threshold", choices=["fixed", "threshold", "bandit"])
    ap.add_argument("--base-port", type=int, default=47200)
    ap.add_argument("--board-bitfile", default=TAMPER_BIT)
    ap.add_argument("--board-max-mode", default="E5", choices=["E4", "E5"])
    ap.add_argument("--window", type=float, default=None,
                    help="seconds after a shot in which a rejection counts for it (default 1.5; 4 with manual)")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--out")
    ap.add_argument("--analyse", metavar="EVENTS_JSONL", help="only re-analyse a finished run")
    a = ap.parse_args()
    window = a.window or (4.0 if a.trigger == "manual" else 1.5)
    if a.analyse:
        ev = [json.loads(l) for l in Path(a.analyse).read_text().splitlines() if l.strip()]
        write_report(analyse_hw(ev, window), Path(a.analyse).parent)
        return
    if not a.external_sender:
        ap.error("--external-sender <BOARD IP> is needed (the tamper injector is in the board's FPGA)")
    out = Path(a.out or ROOT / "sim_out" / "runs" / "hw_tamper")
    fire = make_trigger(a.trigger, a.base_port + 5)
    s = scenario.run(a.scenario, a.policy, out, a.base_port, a.set, external_sender=a.external_sender,
                     board_max_mode=a.board_max_mode, attacker=a.attacker, board_bitfile=a.board_bitfile,
                     hw_trigger=fire)
    scenario.print_summary(s)
    ev = [json.loads(l) for l in (out / "events.jsonl").read_text().splitlines() if l.strip()]
    time.sleep(0.1)
    write_report(analyse_hw(ev, window), out)
    print(f"\nwritten {out}/")


if __name__ == "__main__":
    main()
