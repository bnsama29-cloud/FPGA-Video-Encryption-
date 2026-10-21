"""R2b -- MEASURED throughput of the contract-v3 lane encoder (rtl/secure_jpeg_lanes_top.v).

    python experiments/lanes_rtl_throughput.py                    # 128x96, 320x240, 640x480; L = 1, 2, 4
    python experiments/lanes_rtl_throughput.py --sizes 640x480 --lanes 2 4
    python experiments/lanes_rtl_throughput.py --hd              # adds 1280x720 (LOG_MAXW = 11, slow)
    python experiments/lanes_rtl_throughput.py --sizes 320x240 --modes 2 5   # E5 cost (one segment per MCU)

R2 (experiments/parallel_lanes.py) PROJECTED the lane architecture with an event model. This script
replaces the projection with a cycle-accurate measurement: it runs tb/test_lanes_top.py::throughput
in Icarus for each lane count and frame size (scene image, quality 75, E2 unless --modes, per-lane output FIFO 2 KB (LOG_FIFO = 11, as the Vivado runs and
the board images; --log-fifo 10 repeats the measurements before 21 Oct 2026), no DMA stalls; clocks
from the internal start pulse to irq_done; every measured frame is also checked bit-exact against
model/hw.py :: encode_frame_v3). The contract-v2 encoder (rtl/secure_jpeg_top.v) measured by R1
(experiments/stall_profile.py, paper/data/research/stall_profile/scaling.json) is the baseline.

Writes sim_out/lanes_rtl/results.json and table.md. Mpx/s are given at 100 MHz (the clock the
current design closes timing at on the PYNQ-Z2) and as clocks/pixel, so other clocks scale
linearly: Mpx/s = f_MHz / (clocks/pixel).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tb"))
sys.path.insert(0, str(ROOT))
OUT = ROOT / "sim_out" / "lanes_rtl"
V2_SCALING = ROOT / "paper" / "data" / "research" / "stall_profile" / "scaling.json"


def measure(lanes, size, log_maxw, mode=2, nbuf=2, pixfmt="rgb", log_fifo=11):
    from common import run_sim
    os.environ["THROUGHPUT_SIZE"] = size
    os.environ["THROUGHPUT_MODE"] = str(mode)
    os.environ["THROUGHPUT_WARMUP"] = "0"
    os.environ["THROUGHPUT_NBUF"] = str(nbuf)
    log_l = {1: 1, 2: 1, 4: 2}[lanes]
    run_sim("secure_jpeg_lanes_top", "test_lanes_top",
            parameters=dict(LANES=lanes, LOG_L=log_l, LOG_MAXW=log_maxw, LOG_FIFO=log_fifo, NBUF=nbuf,
                            PIXFMT=1 if pixfmt == "yuyv" else 0),
            testcase="throughput", build_tag=f"_L{lanes}_W{log_maxw}" + ("" if nbuf == 2 else f"_B{nbuf}")
            + ("_yuyv" if pixfmt == "yuyv" else "") + f"_F{log_fifo}")
    suffix = ("" if mode == 2 else f"_E{mode}") + ("" if nbuf == 2 else f"_B{nbuf}") + \
        ("_yuyv" if pixfmt == "yuyv" else "")
    return json.loads((ROOT / "sim_out" / f"lanes_throughput_L{lanes}_{size}{suffix}.json").read_text())


def v2_baseline():
    """Measured clocks/pixel of the contract-v2 encoder per frame size (R1b)."""
    if not V2_SCALING.exists():
        return {}
    return {p["size"]: float(p["cpp"]) for p in json.loads(V2_SCALING.read_text())["points"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="+", default=["128x96", "320x240", "640x480"])
    ap.add_argument("--lanes", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--hd", action="store_true", help="also 1280x720 (needs LOG_MAXW = 11)")
    ap.add_argument("--modes", nargs="+", type=int, default=[2], help="encryption modes (5 = E5)")
    ap.add_argument("--nbuf", default="2", choices=["1", "2"],
                    help="converter line-buffer sets per lane (rgb2ycbcr_2px.v NBUF): 2 = the RTL default, "
                         "1 = half the block RAM (the 1080p 4-lane option)")
    ap.add_argument("--pixfmt", default="rgb", choices=["rgb", "yuyv"],
                    help="input format: rgb (2 pixels per beat) or camera-native yuyv (4 per beat, rtl/yuyv_4px.v)")
    ap.add_argument("--log-fifo", type=int, default=11,
                    help="per-lane output FIFO 2^n bytes: 11 (2 KB) = what the Vivado runs and the board images build "
                         "(secure_jpeg_lanes_top default); the measurements before 21 Oct 2026 used 10")
    ap.add_argument("--out", default=None, help="results folder (default sim_out/lanes_rtl, sim_out/lanes_rtl_nbuf1 "
                                                "or sim_out/lanes_rtl_yuyv)")
    a = ap.parse_args()
    global OUT
    if a.out or a.nbuf != "2" or a.pixfmt != "rgb" or a.log_fifo != 11:
        OUT = Path(a.out) if a.out else ROOT / "sim_out" / (
            ("lanes_rtl_yuyv" if a.pixfmt == "yuyv" else f"lanes_rtl_nbuf{a.nbuf}" if a.nbuf != "2" else "lanes_rtl")
            + ("" if a.log_fifo == 11 else f"_fifo{a.log_fifo}"))
    sizes = a.sizes + (["1280x720"] if a.hd else [])
    OUT.mkdir(parents=True, exist_ok=True)
    res = []
    for size in sizes:
        w = int(size.split("x")[0])
        log_maxw = 10 if w <= 1024 else 11
        for lanes in a.lanes:
            for mode in a.modes:
                r = measure(lanes, size, log_maxw, mode, int(a.nbuf), a.pixfmt, a.log_fifo)
                r["log_maxw"] = log_maxw
                r["log_fifo"] = a.log_fifo
                res.append(r)
                print(f"L={lanes} E{mode} {size}: {r['clocks_per_pixel']:.3f} clk/px, "
                      f"{r['mpx_per_s_at_100mhz']:.1f} Mpx/s at 100 MHz", flush=True)
    base = v2_baseline()
    (OUT / "results.json").write_text(json.dumps(dict(v2_measured_clocks_per_pixel=base, rows=res), indent=1))
    md = ["| Frame | Lanes | Mode | Clocks/pixel | Mpx/s @100 MHz | @125 MHz | @150 MHz | v2 encoder (R1) |",
          "|---|---|---|---|---|---|---|---|"]
    for r in res:
        size = f"{r['width']}x{r['height']}"
        c = r["clocks_per_pixel"]
        b = base.get(size)
        md.append(f"| {size} | {r['lanes']} | E{r.get('mode', 2)} | {c:.3f} | {100 / c:.1f} | {125 / c:.1f} | {150 / c:.1f} | "
                  + (f"{b:.3f} clk/px = {100 / b:.1f} Mpx/s" if b else "-") + " |")
    (OUT / "table.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
