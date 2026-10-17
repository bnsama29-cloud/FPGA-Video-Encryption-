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
    over --timing-frames frames per size and mode -> fps and ms/frame.
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
        return hw.encode_frame_v3(rgb, quality, mode, KEY, ctr, SID)["jpeg"]
    return hw.encode_frame(rgb, quality, mode, KEY, ctr, SID)["jpeg"]


def check(ip, sizes, n, source, quality):
    rows, ok_all = [], True
    for (w, h) in sizes:
        imgs = frames(source, w, h, n)
        for mode in range(5):
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


def timing(ip, sizes, n, source):
    rows = []
    for (w, h) in sizes:
        imgs = frames(source, w, h, n)
        for mode in range(5):
            t_enc, t_full = [], []
            for i, rgb in enumerate(imgs):
                t0 = time.perf_counter()
                scan, tag = ip.encode(rgb, mode, 50_000 + i)
                t1 = time.perf_counter()
                ip.build_jpeg(w, h, mode, 50_000 + i, scan, tag)
                t2 = time.perf_counter()
                t_enc.append(t1 - t0)
                t_full.append(t2 - t0)
            me, mf = statistics.median(t_enc), statistics.median(t_full)
            rows.append(dict(size=f"{w}x{h}", mode=mode, frames=n, encode_ms=round(1000 * me, 2),
                             encode_fps=round(1 / me, 1), full_ms=round(1000 * mf, 2), full_fps=round(1 / mf, 1)))
            print(f"  {w}x{h} E{mode}: encode {1000 * me:.2f} ms ({1 / me:.1f} fps), "
                  f"with headers {1000 * mf:.2f} ms ({1 / mf:.1f} fps)", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bitfile", default=str(ROOT / "future_work" / "board" / "overlay" / "secure_jpeg.bit"))
    ap.add_argument("--mock", action="store_true", help="golden-model emulation instead of the board")
    ap.add_argument("--mock-lanes", type=int, choices=[1, 2, 4],
                    help="emulate the contract-v3 lane bitstream with this many lanes (implies --mock)")
    ap.add_argument("--sizes", nargs="+", default=["320x240", "640x480"])
    ap.add_argument("--frames", type=int, default=10, help="frames per size and mode for the bit-exact check")
    ap.add_argument("--timing-frames", type=int, default=50)
    ap.add_argument("--source", default="synthetic", help="synthetic | video file | webcam:0")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--ip-name")
    ap.add_argument("--dma-name")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    sizes = [tuple(int(v) for v in s.split("x")) for s in a.sizes]
    a.mock = a.mock or bool(a.mock_lanes)
    if a.mock:
        backend = MockBackend(contract=3, lanes=a.mock_lanes) if a.mock_lanes else MockBackend()
    else:
        from future_work.board.pynq_driver import PynqBackend
        backend = PynqBackend(a.bitfile, a.ip_name, a.dma_name, max_pixels=max(w * h for w, h in sizes))
    ip = SecureJpegIP(backend)                      # checks the VERSION register
    ip.setup_session(KEY, SID, a.quality)
    print(f"IP found ({'mock' if a.mock else a.bitfile}), VERSION ok: contract v{ip.contract}"
          + (f", {ip.lanes} lanes" if ip.contract == 3 else "") + ". Part 1: bit-exact check", flush=True)
    ok, exact = check(ip, sizes, a.frames, a.source, a.quality)
    speed = []
    if ok:
        print("Part 2: speed", flush=True)
        speed = timing(ip, sizes, a.timing_frames, a.source)
    else:
        print("Part 1 FAILED: speed not measured (a fast wrong encoder is worthless). See the docstring.")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = dict(backend="mock" if a.mock else "pynq", bitfile=None if a.mock else a.bitfile, all_bit_exact=ok,
               exactness=exact, speed=speed, source=a.source, quality=a.quality)
    (out / "first_contact.json").write_text(json.dumps(res, indent=1))
    md = [f"Backend: {res['backend']}. Bit-exact with the golden model in every size and mode: "
          f"**{'yes' if ok else 'NO'}** ({a.frames} frames each).", ""]
    if speed:
        md += ["| Size | Mode | Encode only (ms) | fps | Incl. headers on ARM (ms) | fps |", "|---|---|---|---|---|---|"]
        md += [f"| {r['size']} | E{r['mode']} | {r['encode_ms']} | {r['encode_fps']} | {r['full_ms']} | {r['full_fps']} |"
               for r in speed]
        if a.mock:
            md += ["", "MOCK backend: these times are the Python emulation, NOT the FPGA. Do not report them."]
    (out / "first_contact.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md) + f"\n\nwritten {out}/first_contact.json / .md")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
