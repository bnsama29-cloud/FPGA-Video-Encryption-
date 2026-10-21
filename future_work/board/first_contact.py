"""First contact with the PYNQ-Z2: is the FPGA bit-exact with the golden model, and how fast is it?

On the board (Jupyter terminal or ssh), from the repo folder copied to the board:
    sudo -E python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg.bit
    sudo -E python3 -m future_work.board.first_contact --bitfile future_work/board/overlay/secure_jpeg_lanes.bit
Without a board (tests the script itself, golden-model emulation of the IP):
    python -m future_work.board.first_contact --mock --sizes 64x48 --frames 2 --timing-frames 2
    python -m future_work.board.first_contact --mock-lanes 2 --sizes 64x48 --frames 2 --timing-frames 2

Part 1 -- bit-exactness (the gate: nothing else counts until this passes)
    For every size and mode 0..4: encode N frames on the FPGA, rebuild the JPEG on the ARM and
    compare it with model/hw.encode_frame (encode_frame_v3 for the lane bitstream) byte for byte, then decrypt it with the receiver.
    Reports the first mismatch (size, mode, frame, byte offset). If any frame differs, the board
    is wrong, not the model: check the clock, reset polarity, DMA lengths, pixel word order.
Part 2 -- speed (only after Part 1 passed)
    Times ip.encode alone (registers + DMA + fabric) and the full frame (+ headers on the ARM)
    over --timing-frames frames per size and mode -> fps and ms/frame, split into: load (ARM writes the
    pixels into the DMA buffer + cache flush), DMA (both channels + invalidate), ARM after (headers, E5
    shuffle) and the fabric-only time from the CYCLES register (bitstreams from 21 Oct 2026).
Writes sim_out/board/first_contact.json and .md (paper_tables.py picks the .md up).
"""
import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np

from future_work.board.pynq_driver import MockBackend, SecureJpegIP
from link.sources import open_source
from model import hw
from model.jpeg import receive_frame

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sim_out" / "board"
KEY = bytes(range(16))
SID = 0x5EC0_1234_5678


def frames(source, w, h, n):
    src = open_source(source, w, h, loop=True)
    return [src.read() for _ in range(n)]


def first_diff(a, b):
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def expected_jpeg(ip, rgb, quality, mode, ctr):
    """What the golden model says this bitstream must produce: contract v2 (secure_jpeg.bit) or
    contract v3 (secure_jpeg_lanes.bit, restart segments; the bytes do not depend on the lane count)."""
    if ip.contract == 3:
        pf = getattr(ip, "pixfmt", "rgb")       # a YUYV bitstream codes the camera's YCbCr (hw.rgb_to_yuyv)
        src = hw.rgb_to_yuyv(rgb) if pf == "yuyv" else rgb
        jpeg = hw.encode_frame_v3(src, quality, mode, KEY, ctr, SID, pixfmt=pf)["jpeg"]
        return hw.arm_shuffle(jpeg, KEY, SID, ctr) if mode == hw.MODE_E5 else jpeg
    return hw.encode_frame(rgb, quality, mode, KEY, ctr, SID)["jpeg"]


def check(ip, sizes, n, source, quality):
    rows, ok_all = [], True
    for (w, h) in sizes:
        imgs = frames(source, w, h, n)
        for mode in range(ip.max_mode + 1):
            bad = None
            for i, rgb in enumerate(imgs):
                ctr = 1000 * mode + i + 1
                scan, tag = ip.encode(rgb, mode, ctr)
                got = ip.build_jpeg(w, h, mode, ctr, scan, tag)
                exp = expected_jpeg(ip, rgb, quality, mode, ctr)
                if got != exp or not receive_frame(got, KEY).ok:
                    bad = dict(frame=i, got_len=len(got), expected_len=len(exp), first_diff_byte=first_diff(got, exp))
                    break
            rows.append(dict(size=f"{w}x{h}", mode=mode, frames=n, bit_exact=bad is None, first_mismatch=bad))
            ok_all &= bad is None
            print(f"  {w}x{h} E{mode}: " + ("bit-exact" if bad is None else f"MISMATCH {bad}"), flush=True)
    return ok_all, rows


def timing(ip, sizes, n, source, zero_copy=False):
    rows = []
    for (w, h) in sizes:
        imgs = frames(source, w, h, n)
        if getattr(ip, "pixfmt", "rgb") == "yuyv":     # time what a YUYV camera delivers (not the ARM converting)
            imgs = [hw.rgb_to_yuyv(x) for x in imgs]
        for mode in range(ip.max_mode + 1):
            t_enc, t_full, parts = [], [], []
            for i, rgb in enumerate(imgs):
                if zero_copy:                      # the frame is already in the DMA buffer (as a camera
                    buf = ip.pixel_buffer(w, h)    # writing there would leave it): not timed
                    np.copyto(buf, rgb)
                    rgb = buf
                t0 = time.perf_counter()
                scan, tag = ip.encode(rgb, mode, 50_000 + i)
                t1 = time.perf_counter()
                ip.build_jpeg(w, h, mode, 50_000 + i, scan, tag)
                t2 = time.perf_counter()
                t_enc.append(t1 - t0)
                t_full.append(t2 - t0)
                parts.append(dict(ip.last_timing, arm_ms=1e3 * (t2 - t1)))
            me, mf = statistics.median(t_enc), statistics.median(t_full)

            def med(k, nd=2):
                v = [p[k] for p in parts if p.get(k) is not None]
                return round(statistics.median(v), nd) if v else None
            row = dict(size=f"{w}x{h}", mode=mode, frames=n, zero_copy=zero_copy, encode_ms=round(1000 * me, 2),
                       encode_fps=round(1 / me, 1), full_ms=round(1000 * mf, 2), full_fps=round(1 / mf, 1),
                       load_ms=med("load_ms"), dma_ms=med("dma_ms"), arm_ms=med("arm_ms"),
                       fabric_ms=med("fabric_ms", 3), cycles=med("cycles", 0), in_wait=med("in_wait", 0),
                       out_stall=med("out_stall", 0))
            if row["fabric_ms"]:
                row["fabric_fps"] = round(1000 / row["fabric_ms"], 1)
            rows.append(row)
            fab = (f", fabric {row['fabric_ms']:.3f} ms = {row['fabric_fps']} fps (in_wait {row['in_wait']:.0f}, "
                   f"out_stall {row['out_stall']:.0f} clocks)") if row["fabric_ms"] else ", fabric: no counter"
            print(f"  {w}x{h} E{mode}: encode {1000 * me:.2f} ms ({1 / me:.1f} fps), "
                  f"with headers {1000 * mf:.2f} ms ({1 / mf:.1f} fps); load {row['load_ms']} + DMA {row['dma_ms']} "
                  f"+ ARM {row['arm_ms']} ms{fab}", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bitfile", default=str(ROOT / "future_work" / "board" / "overlay" / "secure_jpeg.bit"))
    ap.add_argument("--mock", action="store_true", help="golden-model emulation instead of the board")
    ap.add_argument("--mock-lanes", type=int, choices=[1, 2, 4],
                    help="emulate the contract-v3 lane bitstream with this many lanes (implies --mock)")
    ap.add_argument("--mock-e5", action="store_true", help="with --mock-lanes: the emulated bitstream has E5")
    ap.add_argument("--mock-yuyv", action="store_true",
                    help="with --mock-lanes: the emulated bitstream takes YUYV input (PIXFMT = 1, VERSION bit 6)")
    ap.add_argument("--sizes", nargs="+", default=["320x240", "640x480"])
    ap.add_argument("--frames", type=int, default=10, help="frames per size and mode for the bit-exact check")
    ap.add_argument("--timing-frames", type=int, default=50)
    ap.add_argument("--source", default="synthetic", help="synthetic | video file | webcam:0")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--ip-name")
    ap.add_argument("--dma-name")
    ap.add_argument("--fclk", type=float, metavar="MHZ",
                    help="run the fabric slower than the bitstream's clock (e.g. 100 for the 125 MHz 4-lane overlay)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--zero-copy", action="store_true",
                    help="Part 2 with each frame already in the DMA buffer (ip.pixel_buffer): what a camera "
                         "writing straight into that buffer would give; reported in its own column")
    ap.add_argument("--full-cache-ops", action="store_true",
                    help="flush/invalidate the whole DMA buffers instead of only the frame's bytes")
    a = ap.parse_args()
    sizes = [tuple(int(v) for v in s.split("x")) for s in a.sizes]
    a.mock = a.mock or bool(a.mock_lanes)
    if a.mock:
        backend = (MockBackend(contract=3, lanes=a.mock_lanes, e5=a.mock_e5, yuyv=a.mock_yuyv) if a.mock_lanes
                   else MockBackend())
    else:
        from future_work.board.pynq_driver import PynqBackend
        backend = PynqBackend(a.bitfile, a.ip_name, a.dma_name, max_pixels=max(w * h for w, h in sizes),
                              partial_cache=not a.full_cache_ops, fclk_mhz=a.fclk)
        print(f"fabric clock: {backend.fabric_hz / 1e6:.1f} MHz")
    ip = SecureJpegIP(backend)                      # checks the VERSION register
    ip.setup_session(KEY, SID, a.quality)
    print(f"IP found ({'mock' if a.mock else a.bitfile}), VERSION ok: contract v{ip.contract}"
          + (f", {ip.lanes} lanes" if ip.contract == 3 else "") + (", E5 in hardware" if ip.e5 else "")
          + ". Part 1: bit-exact check", flush=True)
    ok, exact = check(ip, sizes, a.frames, a.source, a.quality)
    speed = []
    if ok:
        print("Part 2: speed", flush=True)
        speed = timing(ip, sizes, a.timing_frames, a.source)
        if a.zero_copy:
            print("Part 2b: speed with the frame already in the DMA buffer (zero copy)", flush=True)
            speed += timing(ip, sizes, a.timing_frames, a.source, zero_copy=True)
    else:
        print("Part 1 FAILED: speed not measured (a fast wrong encoder is worthless). See the docstring.")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = dict(backend="mock" if a.mock else "pynq", bitfile=None if a.mock else a.bitfile, all_bit_exact=ok,
               exactness=exact, speed=speed, source=a.source, quality=a.quality,
               lanes=getattr(ip, "lanes", None), pixfmt=getattr(ip, "pixfmt", "rgb"), e5=getattr(ip, "e5", False))
    (out / "first_contact.json").write_text(json.dumps(res, indent=1))
    md = [f"Backend: {res['backend']}. Bit-exact with the golden model in every size and mode: "
          f"**{'yes' if ok else 'NO'}** ({a.frames} frames each).", ""]
    if speed:
        md += ["| Size | Mode | Zero copy | Encode only (ms) | fps | Incl. headers on ARM (ms) | fps | load (ms) | DMA (ms) "
               "| ARM after (ms) | fabric (ms) | fabric fps |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        md += [f"| {r['size']} | E{r['mode']} | {'yes' if r.get('zero_copy') else 'no'} | {r['encode_ms']} | {r['encode_fps']} | {r['full_ms']} | {r['full_fps']} "
               f"| {r['load_ms']} | {r['dma_ms']} | {r['arm_ms']} | {r['fabric_ms'] if r['fabric_ms'] else '-'} "
               f"| {r.get('fabric_fps', '-')} |" for r in speed]
        md += ["", f"fabric = CYCLES register (START to DONE, {getattr(backend, 'fabric_hz', 100e6) / 1e6:.0f} MHz clocks): the encoder alone, without the ARM; "
               "'-' = bitstream built before the counters (21 Oct 2026)."]
        if a.mock:
            md += ["", "MOCK backend: these times are the Python emulation, NOT the FPGA. Do not report them."]
    (out / "first_contact.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md) + f"\n\nwritten {out}/first_contact.json / .md")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
