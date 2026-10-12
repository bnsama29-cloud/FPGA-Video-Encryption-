"""Start the whole simulated link: channel, receiver, sender and dashboard.

    python -m link.run_all                         # then open http://localhost:8000
    python -m link.run_all --set sender.policy=bandit --set sender.source=clip.mp4
    python -m link.run_all --no-dashboard

Each node is a separate process talking UDP on localhost, exactly as they would
on separate machines (sender on the PYNQ-Z2, receiver + dashboard on a laptop).
You can also run each one in its own terminal (python -m link.<node>), which is
how the team splits the work. Ctrl+C stops everything.
"""
import argparse
import subprocess
import sys
import time

from . import config

NODES = ["channel", "receiver", "dashboard", "sender"]


def main():
    ap = config.add_args(argparse.ArgumentParser(description=__doc__,
                                                 formatter_class=argparse.RawDescriptionHelpFormatter))
    ap.add_argument("--no-dashboard", action="store_true")
    a = ap.parse_args()
    extra = (["--config", a.config] if a.config else []) + [x for s in a.set for x in ("--set", s)]
    procs = []
    try:
        for node in NODES:
            if node == "dashboard" and a.no_dashboard:
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
