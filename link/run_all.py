"""Start the whole simulated link: channel, receiver, sender and dashboard.

    python -m link.run_all                         # then open http://localhost:8000
    python -m link.run_all --set sender.policy=bandit --set sender.source=clip.mp4
    python -m link.run_all --set dashboard.bind_host=0.0.0.0  # trusted-LAN dashboard access
    python -m link.run_all --no-dashboard
    python -m link.run_all --no-sender --pq-kex ...  # board as camera: post-quantum session key first
    python -m link.run_all --no-sender --no-channel --set link.host=<ATTACKER IP> --set link.bus_host=127.0.0.1 ...
                                                   # two laptops: the channel (attacker) runs on the other one

Each node is a separate process talking UDP on localhost, exactly as they would
on separate machines (sender on the PYNQ-Z2, receiver + dashboard on a laptop).
You can also run each one in its own terminal (python -m link.<node>), which is
how the nodes split the work. Ctrl+C stops everything.
"""
import argparse
import signal
import subprocess
import sys
import time

from . import config

NODES = ["channel", "receiver", "dashboard", "sender"]


def _stop(*_):
    raise KeyboardInterrupt


def main():
    ap = config.add_args(argparse.ArgumentParser(description=__doc__,
                                                 formatter_class=argparse.RawDescriptionHelpFormatter))
    ap.add_argument("--no-dashboard", action="store_true")
    ap.add_argument("--no-sender", action="store_true",
                    help="laptop side only (the sender runs on the PYNQ board)")
    ap.add_argument("--no-channel", action="store_true",
                    help="the channel (network + attacker) runs on another laptop")
    ap.add_argument("--pq-kex", action="store_true",
                    help="first run the post-quantum key exchange (link/kex.py) with the sender and use its "
                         "session key; keys.master is then only the pre-shared authentication key")
    a = ap.parse_args()
    # `kill <pid>` (SIGTERM) must stop the children too, exactly like Ctrl+C
    signal.signal(signal.SIGTERM, _stop)
    extra = (["--config", a.config] if a.config else []) + [x for s in a.set for x in ("--set", s)]
    procs = []
    try:
        if a.pq_kex:
            kex = [sys.executable, "-m", "link.kex", "--role", "receiver"] + extra
            if not a.no_sender:          # all on this PC: the simulated sender runs its half now too
                tx = subprocess.Popen([sys.executable, "-m", "link.kex", "--role", "sender"] + extra)
            if subprocess.call(kex) != 0:
                raise SystemExit("key exchange failed")
            if not a.no_sender:
                tx.wait(timeout=30)
            extra += ["--set", "keys.master_file=configs/session_key.txt"]
        for node in NODES:
            if (node == "dashboard" and a.no_dashboard) or (node == "sender" and a.no_sender) \
                    or (node == "channel" and a.no_channel):
                continue
            procs.append(subprocess.Popen([sys.executable, "-m", f"link.{node}"] + extra))
            time.sleep(0.4)
        cfg = config.load(a.config, a.set)
        if not a.no_dashboard:
            print(f"\n  dashboard: http://localhost:{cfg['dashboard']['http_port']}\n")
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        print("a node exited; stopping the others")
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
