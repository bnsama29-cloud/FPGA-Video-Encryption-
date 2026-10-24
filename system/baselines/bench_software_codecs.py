"""Optimised software baselines: what a CPU (laptop or the PYNQ's ARM) does without our FPGA.

    python -m system.baselines.bench_software_codecs                    # this machine
    python3 -m system.baselines.bench_software_codecs --sizes 640x480 --frames 30   # on the PYNQ

Per frame it times:
  jpeg (libjpeg-turbo)          cv2.imencode, quality 75, 4:2:0 -- the optimised software encoder
  + full AES-128-GCM            whole JPEG, OpenSSL (`cryptography`)        -> unplayable
  + full ChaCha20-Poly1305      whole JPEG, OpenSSL                          -> unplayable
  + selective E2 / E4 (Python)  model.jpeg.selective_encrypt_jpeg on the libjpeg output
                                (our format-compliant scheme done in software after encoding)
and, for reference, the FPGA estimate from the RTL cycle count (--fpga-cpp, default 1.64
cycles/pixel measured in simulation; replace with the board's measured fps).

Writes system/results/baselines_<host>.json and .md. Run it on the PYNQ's ARM
(python3, OpenCV and cryptography are on the PYNQ image or pip-installable) and on a
laptop. Combine with measured power in energy_table.py.
"""
import argparse
import json
import platform
import socket
import time
from pathlib import Path

import cv2
import numpy as np

from link.sources import open_source
from model.jpeg import selective_encrypt_jpeg

OUT = Path(__file__).resolve().parents[1] / "results"


def timed(fn, reps):
    fn()                                            # warm-up
    t = time.perf_counter()
    for _ in range(reps):
        r = fn()
    return r, (time.perf_counter() - t) / reps * 1000.0


def bench(size, frames, source, quality, reps, with_selective):
    w, h = size
    src = open_source(source, w, h, loop=True)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
        aes, cha = AESGCM(bytes(16)), ChaCha20Poly1305(bytes(32))
    except ImportError:
        aes = cha = None
    rows = {}
    key, nonce = bytes(range(16)), bytes(12)
    for i in range(frames):
        bgr = cv2.cvtColor(src.read(), cv2.COLOR_RGB2BGR)
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        (ok, buf), t_jpg = timed(lambda: cv2.imencode(".jpg", bgr, params), reps)
        jpg = buf.tobytes()
        rows.setdefault("jpeg (libjpeg-turbo)", []).append((t_jpg, len(jpg), True))
        if aes is not None:
            _, t = timed(lambda: aes.encrypt(nonce, jpg, None), reps)
            rows.setdefault("jpeg + full AES-128-GCM", []).append((t_jpg + t, len(jpg) + 16, False))
            _, t = timed(lambda: cha.encrypt(nonce, jpg, None), reps)
            rows.setdefault("jpeg + full ChaCha20-Poly1305", []).append((t_jpg + t, len(jpg) + 16, False))
        if with_selective:
            for m in ("E2", "E4"):
                try:
                    out, t = timed(lambda: selective_encrypt_jpeg(jpg, key, 1, i + 1, m), 1)
                    rows.setdefault(f"jpeg + selective {m} (Python, after encoding)", []).append(
                        (t_jpg + t, len(out), True))
                except ValueError as e:                     # libjpeg output our parser cannot handle
                    rows.setdefault(f"jpeg + selective {m} (Python, after encoding)", []).append(
                        (float("nan"), 0, True))
                    print(f"  selective {m} skipped: {e}")
    res = {}
    for k, v in rows.items():
        ms = float(np.nanmean([x[0] for x in v]))
        res[k] = dict(ms_per_frame=ms, fps=1000.0 / ms if ms == ms and ms > 0 else None,
                      bytes=float(np.mean([x[1] for x in v])), playable=v[0][2])
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", nargs="+", default=["320x240", "640x480"])
    ap.add_argument("--frames", type=int, default=10)
    ap.add_argument("--reps", type=int, default=5, help="repetitions per measurement")
    ap.add_argument("--source", default="synthetic")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--no-selective", action="store_true", help="skip the (slow) Python selective rows")
    ap.add_argument("--fpga-cpp", type=float, default=1.64, help="FPGA cycles per pixel (RTL sim or board)")
    ap.add_argument("--fpga-mhz", type=float, default=100.0)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    host = socket.gethostname()
    result = dict(host=host, machine=platform.machine(), processor=platform.processor(),
                  python=platform.python_version(), opencv=cv2.__version__, sizes={})
    lines = [f"# Software baselines on `{host}` ({platform.machine()})\n"]
    for sz in a.sizes:
        w, h = (int(v) for v in sz.split("x"))
        r = bench((w, h), a.frames, a.source, a.quality, a.reps, not a.no_selective)
        fpga_ms = a.fpga_cpp * w * h / (a.fpga_mhz * 1e6) * 1000
        r["FPGA encoder + in-pipeline encryption (from cycles/pixel)"] = dict(
            ms_per_frame=fpga_ms, fps=1000 / fpga_ms, bytes=None, playable=True)
        result["sizes"][sz] = r
        lines += [f"\n## {sz}, quality {a.quality}, mean of {a.frames} frames\n",
                  "| Method | ms / frame | fps | bytes | plays in VLC |", "|---|---|---|---|---|"]
        for k, v in r.items():
            fps = f"{v['fps']:.1f}" if v["fps"] else "-"
            b = f"{v['bytes']:.0f}" if v["bytes"] else "-"
            lines.append(f"| {k} | {v['ms_per_frame']:.2f} | {fps} | {b} | {'yes' if v['playable'] else 'no'} |")
        print(f"{sz}: done")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"baselines_{host}.json").write_text(json.dumps(result, indent=2))
    (out / f"baselines_{host}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwritten {out}/baselines_{host}.json / .md")


if __name__ == "__main__":
    main()
