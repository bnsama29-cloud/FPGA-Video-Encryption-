"""R2 -- more pixels per second with parallel encoder lanes over restart segments (research suite).

    python experiments/parallel_lanes.py                          # synthetic scene, 320x240
    python experiments/parallel_lanes.py --video clips/x.mp4 --frames 6 --stride 150

Idea. E5 already cuts the scan into segments with restart markers for security. A restart marker
also resets the DC prediction, so a segment can be entropy-coded with no knowledge of the others:
L encoder lanes can each take every L-th segment, and a merger writes the segments back in order.
The security feature becomes a parallelism feature.

What this script shows (model level; nothing here is an RTL measurement):
 1. Exactness: for every frame, merging the per-lane segments gives the same bytes as coding the
    segments one after another (plain scan, any N and L), and the JPEG decodes to the same pixels as
    the standard file (the restart markers change no sample).
 2. The catch, and its fix: today's keystream is one Ascon stream per frame, so the bits a segment
    uses depend on every earlier segment -- lanes could not encrypt independently. The fix proposed
    here (contract-v3 candidate, model only): K_seg = Ascon-MAC(K, N_enc(session, frame), "lanes") once
    per frame, then segment s uses the keystream of K_seg under nonce (s, frame). K_seg is unique per
    frame, so no (key, nonce) pair repeats. The script checks that decryption returns the plain
    symbols and that lanes still merge to the sequential bytes.
 3. Cost: bitrate of one restart segment per MCU row relative to no restart markers.
 4. Throughput: a small event simulation of the front end (pixel input at P pixels/clock, B MCU-row
    buffers, L lanes at 1 DCT sample/clock each, a fixed cost per segment). For L = 1, B = 2, P = 1
    it reproduces the measured RTL law (experiments/stall_profile.py: 1.5 + a/rows cycles/pixel);
    larger L and P are projections. Area per lane from the Vivado per-block numbers
    (paper/data/vivado), also a projection.
Writes sim_out/parallel_lanes/<name>.json and .md.
"""
import argparse
import io
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.sources import open_source                                   # noqa: E402
from model import ascon                                                # noqa: E402
from model.container import build_jpeg                                 # noqa: E402
from model.entropy import huffman_encode, join_restart, run_length_encode   # noqa: E402
from model.jpeg import analyse_frame, package_frame                    # noqa: E402
from model.selective import apply_keystream                            # noqa: E402

OUT = ROOT / "sim_out" / "parallel_lanes"
KEY = bytes(range(16))
SAMPLES_PER_MCU = 384            # 4 Y + Cb + Cr blocks of 64 samples (4:2:0)
SEG_OVERHEAD_CYCLES = 16         # Ascon initialisation (12 rounds) + marker and DC reset, per segment


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def segments(n_mcu, n):
    return [range(i, min(i + n, n_mcu)) for i in range(0, n_mcu, n)]


def segment_key(key, sid, ctr):
    """Per-frame key for seekable segment keystreams (contract-v3 candidate)."""
    return ascon.mac(key, ascon.make_nonce(sid, ctr, 0), b"lanes")


def code_segment(q, g, s_idx, key=None, sid=0, ctr=0, mode="E4"):
    """One segment, coded with no state from any other segment: run-length coding with a fresh DC
    predictor, optional encryption with the segment's own keystream, Huffman coding."""
    sym = run_length_encode(q[g.start:g.stop])
    if key is not None:
        ks = ascon.Keystream(segment_key(key, sid, ctr), ascon.make_nonce(s_idx, ctr, 0))
        sym, _ = apply_keystream(sym, ks, mode)
    return sym, huffman_encode(sym)[0]


def lanes_scan(an, n, lanes, **kw):
    """Lane l codes segments l, l+L, l+2L, ...; the merger restores the order."""
    segs = segments(len(an.quant), n)
    per_lane = {l: {i: code_segment(an.quant, segs[i], i, **kw)[1] for i in range(l, len(segs), lanes)}
                for l in range(lanes)}
    merged = [per_lane[i % lanes][i] for i in range(len(segs))]
    return join_restart(merged)


def check_exact(an, rgb):
    """1 + 2 above. Returns a dict of booleans (all must be True)."""
    cols = (an.width + 15) // 16
    res = {}
    seq = {n: lanes_scan(an, n, 1) for n in (1, cols, 4 * cols)}
    for n, ref in seq.items():
        for L in (2, 3, 4):
            res[f"plain_N{n}_L{L}"] = lanes_scan(an, n, L) == ref
    std = decode(package_frame(an).jpeg)
    jp = build_jpeg(an.width, an.height, an.qy, an.qc, seq[cols], restart_interval=cols)
    res["restart_rows_decode_same_pixels"] = bool(np.array_equal(decode(jp), std))
    kw = dict(key=KEY, sid=7, ctr=3, mode="E4")
    enc1 = lanes_scan(an, cols, 1, **kw)
    res["encrypted_lanes_merge_exact"] = all(lanes_scan(an, cols, L, **kw) == enc1 for L in (2, 4))
    ok = True
    segs = segments(len(an.quant), cols)
    for i, g in enumerate(segs):                  # XOR twice with the same segment keystream = plain
        sym, _ = code_segment(an.quant, g, i, **kw)
        ks = ascon.Keystream(segment_key(KEY, 7, 3), ascon.make_nonce(i, 3, 0))
        back, _ = apply_keystream(sym, ks, "E4")
        ok &= back == run_length_encode(an.quant[g.start:g.stop])
    res["segment_keystream_decrypts"] = bool(ok)
    return res


def restart_overhead(an):
    """Bytes of one restart segment per MCU row relative to a single segment (plain scan)."""
    cols = (an.width + 15) // 16
    one = len(lanes_scan(an, len(an.quant), 1))
    rows = len(lanes_scan(an, cols, 1))
    return rows / one - 1


def simulate(w, h, lanes=1, buffers=2, px_per_clk=1, overlap=False):
    """Front-end event model: rows of 16 lines are written into `buffers` MCU-row buffers at
    px_per_clk; a free lane takes a full buffer and needs 384 cycles per MCU + SEG_OVERHEAD_CYCLES.
    overlap=True: the next frame streams in while this one drains (steady state, no fill cost).
    Returns cycles per pixel."""
    rows, mcus = h // 16, w // 16
    fill = 16 * w / px_per_clk
    work = mcus * SAMPLES_PER_MCU + SEG_OVERHEAD_CYCLES
    if overlap:                                    # steady state: the slower of input and lanes
        return max(fill, work / lanes) * rows / (w * h)
    t_in = 0.0                                     # time the writer finishes the current row
    buf_free = [0.0] * buffers                     # time each buffer becomes free again
    lane_free = [0.0] * lanes
    done = 0.0
    for r in range(rows):
        b = min(range(buffers), key=lambda i: buf_free[i])
        start_fill = max(t_in, buf_free[b])
        t_in = start_fill + fill                   # row r is complete in buffer b
        k = min(range(lanes), key=lambda i: lane_free[i])
        start = max(t_in, lane_free[k])
        lane_free[k] = buf_free[b] = start + work
        done = max(done, lane_free[k])
    return done / (w * h)


def area(lanes):
    """LUT / DSP / BRAM36 for L lanes from the Vivado per-block numbers (projection)."""
    p = ROOT / "paper" / "data" / "vivado" / "vivado_results.json"
    if not p.exists():
        return None
    r = next(x for x in json.loads(p.read_text()) if x["name"] == "secure_jpeg_top")
    h = {row[1]: row for row in r["hier"] if row[0] == 1}
    lane_blocks = ["u_dct", "u_quant", "u_rle", "u_enc", "u_huff", "u_pack", "u_ks"]
    per_lane = lambda k: sum(h[n][k] for n in lane_blocks if n in h)
    u = r["util"]                                  # measured totals for L = 1, plus (L-1) more lanes
    conv_bram = h["u_conv"][5] if "u_conv" in h else 0
    return dict(lut=round(u["lut"][0] + (lanes - 1) * per_lane(3)),
                dsp=round(u["dsp"][0] + (lanes - 1) * per_lane(6)),
                bram=u["bram"][0] + conv_bram * (lanes - 1) / 2)   # + one MCU-row buffer per extra lane


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--stride", type=int, default=30)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    name = a.name or Path(a.video).stem
    src = open_source(a.video, w, h, loop=False)
    checks, overhead = [], []
    for i in range(a.frames):
        for _ in range(a.stride if i else 1):
            rgb = src.read()
            if rgb is None:
                break
        if rgb is None:
            break
        an = analyse_frame(rgb)
        checks.append(check_exact(an, rgb))
        overhead.append(restart_overhead(an))
    exact = {k: all(c[k] for c in checks) for k in checks[0]} if checks else {}
    configs = []
    for (fw, fh) in ((640, 480), (1280, 720)):
        for L, P, ov in ((1, 1, False), (1, 1, True), (2, 1, False), (2, 1, True), (2, 2, True), (4, 2, True)):
            cpp = simulate(fw, fh, lanes=L, buffers=L + 1, px_per_clk=P, overlap=ov)
            configs.append(dict(frame=f"{fw}x{fh}", lanes=L, px_per_clk=P, overlap=ov, cpp=cpp,
                                mpix={mhz: mhz / cpp for mhz in (100, 125, 150)}, area=area(L)))
    res = dict(source=name, frames=len(checks), exact=exact,
               restart_row_overhead_mean=statistics.mean(overhead) if overhead else None,
               restart_row_overhead_max=max(overhead) if overhead else None,
               model_check_L1=dict(sim_160x128=simulate(160, 128), sim_320x240=simulate(320, 240)),
               configs=configs)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(res, indent=1))
    md = [f"### R2: parallel lanes over restart segments ({name}, {len(checks)} frames)", "",
          "Exactness (all frames): " + ", ".join(f"{k} {'OK' if v else 'FAIL'}" for k, v in exact.items()), "",
          f"Bitrate cost of one restart segment per MCU row: {100 * res['restart_row_overhead_mean']:.2f} % "
          f"mean, {100 * res['restart_row_overhead_max']:.2f} % max.", "",
          f"Model check against the RTL law (L=1, B=2, P=1): 160x128 -> {simulate(160, 128):.3f}, "
          f"320x240 -> {simulate(320, 240):.3f} cycles/pixel (measured: 1.639, 1.570).", "",
          "| Frame | Lanes | Input px/clk | Frame overlap | Cycles/px | Mpx/s @100 | @125 | @150 | LUT | DSP | BRAM36 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in configs:
        ar = c["area"] or {}
        md.append(f"| {c['frame']} | {c['lanes']} | {c['px_per_clk']} | {'yes' if c['overlap'] else 'no'} | "
                  f"{c['cpp']:.3f} | {c['mpix'][100]:.0f} | {c['mpix'][125]:.0f} | {c['mpix'][150]:.0f} | "
                  f"{ar.get('lut', '?')} | {ar.get('dsp', '?')} | {ar.get('bram', '?')} |")
    md += ["", "Lanes > 1, 2 px/clk input and overlap are projections from the event model, not RTL measurements."]
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
