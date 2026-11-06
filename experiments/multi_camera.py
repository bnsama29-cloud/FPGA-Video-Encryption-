"""Several cameras on one machine (journal experiment X22): how the link scales.

    python experiments/multi_camera.py                          # 1, 2, 4 cameras, benign scenario, 640x480
    python experiments/multi_camera.py --cameras 1 2 4 8 --set sender.width=320 --set sender.height=240

For each count N it starts N independent links at once (sender, channel and receiver each, own ports and
keys; scenarios/calm.json: no attack, no impairment) and reports per camera the frames received, verified
and lost, the end-to-end latency (median and 95th percentile) and the machine's CPU load while they run.
This measures the software pipeline of this repository on this machine (the receiver's cost per stream is
what grows with N; in a deployment each camera has its own board). Writes sim_out/multi_camera/table.md, .json.
"""
import argparse
import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import scenario as sc_mod      # noqa: E402


def cpu_times():
    """(busy, total) jiffies from /proc/stat, or None where there is no /proc (Windows, macOS)."""
    try:
        f = open("/proc/stat").readline().split()[1:]
    except OSError:
        return None
    v = [int(x) for x in f]
    idle = v[3] + (v[4] if len(v) > 4 else 0)
    return sum(v) - idle, sum(v)


class CpuMeter:
    """Mean CPU load (0..1 of all cores) between start() and stop(), sampled every second."""

    def __init__(self):
        self.samples, self._stop = [], threading.Event()

    def _run(self):
        prev = cpu_times()
        while prev and not self._stop.wait(1.0):
            now = cpu_times()
            db, dt = now[0] - prev[0], now[1] - prev[1]
            if dt > 0:
                self.samples.append(db / dt)
            prev = now

    def start(self):
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()
        return self

    def stop(self):
        self._stop.set()
        self.t.join()
        return statistics.mean(self.samples) if self.samples else None


def per_camera(s):
    f = s["frames"]
    ok = f.get("ok", 0) + f.get("gap", 0)
    return dict(frames_ok=ok, frames_rejected=sum(v for k, v in f.items() if k not in ("ok", "gap")),
                latency_ms_median=s["latency_ms_median"], latency_ms_p95=s["latency_ms_p95"],
                false_alarms=s["false_alarm_windows"], calm_windows=s["calm_windows"])


def aggregate(n, cams, cpu):
    lat = [c["latency_ms_median"] for c in cams if c["latency_ms_median"] is not None]
    p95 = [c["latency_ms_p95"] for c in cams if c["latency_ms_p95"] is not None]
    return dict(cameras=n, frames_ok_per_camera=statistics.mean(c["frames_ok"] for c in cams),
                latency_ms_median=statistics.median(lat) if lat else None,
                latency_ms_p95_worst=max(p95) if p95 else None,
                false_alarms=sum(c["false_alarms"] for c in cams), calm_windows=sum(c["calm_windows"] for c in cams),
                cpu_load=cpu, per_camera=cams)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cameras", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--scenario", default=str(ROOT / "experiments" / "scenarios" / "calm.json"))
    ap.add_argument("--policy", default="threshold")
    ap.add_argument("--base-port", type=int, default=48000)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "multi_camera"))
    a = ap.parse_args()
    out = Path(a.out)
    rows = []
    for n in a.cameras:
        print(f"\n=== {n} camera(s) ===", flush=True)
        meter = CpuMeter().start()

        def one(i, n=n):
            return sc_mod.run(a.scenario, a.policy, out / f"n{n}" / f"cam{i}", base_port=a.base_port + 40 * i,
                              extra_sets=[f"keys.master={os.urandom(16).hex()}", f"defence.seed={i + 1}"] + a.set,
                              quiet=True)
        with ThreadPoolExecutor(max_workers=n) as ex:
            summaries = list(ex.map(one, range(n)))
        rows.append(aggregate(n, [per_camera(s) for s in summaries], meter.stop()))
        time.sleep(2)
    md = ["# Several cameras on one machine", "", f"Scenario {Path(a.scenario).name}, {os.cpu_count()} CPU cores.", "",
          "| Cameras | frames verified per camera | latency median (ms) | worst p95 (ms) | false alarms | CPU load |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        cpu = "-" if r["cpu_load"] is None else f"{100 * r['cpu_load']:.0f} %"
        md.append(f"| {r['cameras']} | {r['frames_ok_per_camera']:.0f} | {r['latency_ms_median']} | "
                  f"{r['latency_ms_p95_worst']} | {r['false_alarms']}/{r['calm_windows']} | {cpu} |")
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.md").write_text("\n".join(md) + "\n")
    (out / "table.json").write_text(json.dumps(rows, indent=1))
    print("\n".join(md))


if __name__ == "__main__":
    main()
