"""R1 -- where do the encoder's cycles go? (research suite)

    python experiments/stall_profile.py                      # 128x96, scene/noise/bars, E0/E2/E4 (~2 min)
    python experiments/stall_profile.py --size 320x240       # slower, closer to the paper's frames
    python experiments/stall_profile.py --scaling 64x48 128x96 160x128 320x240   # fit the frame-size law

Finding (14 Oct 2026): cycles/pixel do not depend on the image or the protection level (the entropy
path never limits), and the excess over 1.5 is ~1/(MCU rows): the DCT waits while the first 16-line
buffer fills, once per frame. --scaling measures that law and fits cycles/pixel = 1.5 + a / rows.

Runs tb/stall_profile_bench.py on secure_jpeg_top in Icarus and summarises, for every internal
valid/ready link, the share of frame cycles with a transfer, a stall (consumer busy) and a starve
(producer empty). The floor for this architecture is 1.5 cycles/pixel (4:2:0 gives 1.5 samples per
pixel, the DCT takes one per clock); the table says how far each frame is above it and which link
stalls most, i.e. which stage to widen or pipeline first.
Writes sim_out/stall_profile/profile.json and table.md.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sim_out" / "stall_profile"
FLOOR = 1.5


def summarise(raw):
    rows = []
    for r in raw:
        links = r["links"]
        # the link with the largest share of stalled cycles marks the slowest consumer
        worst = max(links, key=lambda n: links[n]["stall"])
        rows.append(dict(image=r["image"], mode=f"E{r['mode']}", cpp=r["cycles_per_pixel"],
                         above_floor=r["cycles_per_pixel"] / FLOOR - 1,
                         worst_link=worst, worst_stall=links[worst]["stall"] / r["cycles"],
                         scan_bytes=r["scan_bytes"],
                         share={n: {k: v / r["cycles"] for k, v in c.items()} for n, c in links.items()}))
    return rows


def table(rows):
    md = ["### R1: stall profile of the encoder pipeline (Icarus, cycle-accurate)", "",
          f"Floor of this architecture: {FLOOR} cycles/pixel (4:2:0, one DCT sample per clock).", "",
          "| Image | Mode | Cycles/pixel | Above floor | Most-stalled link | Stall share | Scan bytes |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['image']} | {r['mode']} | {r['cpp']:.3f} | {100 * r['above_floor']:.1f} % | "
                  f"{r['worst_link']} | {100 * r['worst_stall']:.1f} % | {r['scan_bytes']} |")
    first = rows[0]
    md += ["", f"Per-link shares for {first['image']} {first['mode']} (transfer / stall / starve, % of cycles):", "",
           "| Link | Transfer | Stall | Starve |", "|---|---|---|---|"]
    for n, s in first["share"].items():
        md.append(f"| {n} | {100 * s['transfer']:.1f} | {100 * s['stall']:.1f} | {100 * s['starve']:.1f} |")
    return "\n".join(md) + "\n"


def scaling(sizes):
    """One frame (scene, E2) per size; least-squares fit of cpp - FLOOR = a / mcu_rows."""
    from common import run_sim
    pts = []
    for sz in sizes:
        os.environ.update(PROFILE_SIZE=sz, PROFILE_IMAGES="scene", PROFILE_MODES="2")
        run_sim("secure_jpeg_top", "stall_profile_bench")
        r = json.loads((OUT / "raw.json").read_text())[0]
        rows = r["height"] // 16
        pts.append(dict(size=sz, mcu_rows=rows, cpp=r["cycles_per_pixel"]))
    xs = [1 / p["mcu_rows"] for p in pts]
    ys = [p["cpp"] - FLOOR for p in pts]
    a = sum(x * y for x, y in zip(xs, ys)) / sum(x * x for x in xs)
    for p in pts:
        p["fit"] = FLOOR + a / p["mcu_rows"]
    pred = {f"{w}x{h}": FLOOR + a / (h // 16) for w, h in ((640, 480), (1280, 720), (1920, 1080))}
    res = dict(points=pts, a=a, predicted_cpp=pred,
               predicted_mpix_100mhz={k: 100 / v for k, v in pred.items()})
    (OUT / "scaling.json").write_text(json.dumps(res, indent=1))
    md = ["### R1b: cycles/pixel against frame size (scene, E2)", "",
          f"Fit: cycles/pixel = {FLOOR} + {a:.3f} / MCU rows (the first MCU row fills before the DCT starts).", "",
          "| Frame | MCU rows | Measured | Fit |", "|---|---|---|---|"]
    md += [f"| {p['size']} | {p['mcu_rows']} | {p['cpp']:.3f} | {p['fit']:.3f} |" for p in pts]
    md += ["", "| Predicted | cycles/pixel | Mpx/s at 100 MHz |", "|---|---|---|"]
    md += [f"| {k} | {v:.3f} | {100 / v:.1f} |" for k, v in pred.items()]
    (OUT / "scaling.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", default="128x96")
    ap.add_argument("--images", default="scene,noise,bars")
    ap.add_argument("--modes", default="0,2,4")
    ap.add_argument("--scaling", nargs="*", help="frame sizes for the frame-size law (skips the profile)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.scaling:
        sys.path.insert(0, str(ROOT / "tb"))
        return scaling(a.scaling)
    os.environ.update(PROFILE_SIZE=a.size, PROFILE_IMAGES=a.images, PROFILE_MODES=a.modes)
    sys.path.insert(0, str(ROOT / "tb"))
    from common import run_sim
    run_sim("secure_jpeg_top", "stall_profile_bench")
    raw = json.loads((OUT / "raw.json").read_text())
    rows = summarise(raw)
    (OUT / "profile.json").write_text(json.dumps(rows, indent=1))
    md = table(rows)
    (OUT / "table.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
