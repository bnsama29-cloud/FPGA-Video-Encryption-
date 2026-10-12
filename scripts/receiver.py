"""Key-holder receiver: verify tag -> replay check -> decrypt -> show clear video.

From the live stream (PC server now, PYNQ-Z2 later):
    python scripts/receiver.py --url http://localhost:8080/stream.mjpg
    python scripts/receiver.py --url http://192.168.2.99:8080/stream.mjpg      # the board

From a recorded file (e.g. results/scrambled_E2.mjpeg):
    python scripts/receiver.py --file results/scrambled_E2.mjpeg --save-dir rx_out

Window shows: left = what VLC/an attacker sees, right = verified + decrypted.
Press q to quit. A log CSV records every frame's verdict and timing.
"""
import argparse
import csv
import time
import urllib.request
from pathlib import Path

import _common
import cv2
import numpy as np

from model.container import split_mjpeg
from model.jpeg import ReplayGuard, decode_pixels, receive_frame


def frames_from_http(url):
    """Parses multipart/x-mixed-replace; yields each JPEG body."""
    resp = urllib.request.urlopen(url, timeout=10)
    while True:
        line = resp.readline()
        if not line:
            return
        if not line.startswith(b"--"):
            continue
        length = None
        while True:
            h = resp.readline()
            if h in (b"\r\n", b"\n", b""):
                break
            k, _, v = h.decode(errors="replace").partition(":")
            if k.strip().lower() == "content-length":
                length = int(v.strip())
        if length is None:
            continue
        yield resp.read(length)


def frames_from_file(path):
    yield from split_mjpeg(Path(path).read_bytes())


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--file")
    ap.add_argument("--key", default=_common.DEMO_KEY_HEX)
    ap.add_argument("--no-display", action="store_true")
    ap.add_argument("--save-dir", help="write decrypted frames as clear .jpg files here")
    ap.add_argument("--log", default="receiver_log.csv")
    ap.add_argument("--max-frames", type=int, default=0)
    a = ap.parse_args()
    key = _common.parse_key(a.key)
    guard = ReplayGuard()
    save = Path(a.save_dir) if a.save_dir else None
    if save:
        save.mkdir(parents=True, exist_ok=True)
    source = frames_from_http(a.url) if a.url else frames_from_file(a.file)

    counts = {}
    t0 = time.time()
    last_clear = None
    with open(a.log, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n", "bytes", "verdict", "mode", "session", "frame_ctr", "verify_decrypt_ms"])
        for n, jpeg in enumerate(source):
            t = time.perf_counter()
            r = receive_frame(jpeg, key, guard)
            ms = (time.perf_counter() - t) * 1000
            counts[r.reason] = counts.get(r.reason, 0) + 1
            w.writerow([n, len(jpeg), r.reason, r.mode, r.session_id, r.frame_ctr, f"{ms:.1f}"])
            print(f"frame {n:5d} ctr={r.frame_ctr} mode={r.mode} -> {r.reason.upper():14s} "
                  f"({ms:.0f} ms)", flush=True)
            if r.ok and save:
                (save / f"frame_{r.frame_ctr:06d}.jpg").write_bytes(r.plain_jpeg)
            if not a.no_display:
                try:
                    scr = decode_pixels(jpeg)
                except Exception:
                    scr = np.zeros((240, 320, 3), np.uint8)
                if r.ok:
                    last_clear = decode_pixels(r.plain_jpeg)
                    right = _common.label(last_clear, f"VERIFIED ctr={r.frame_ctr}")
                else:
                    right = np.zeros_like(scr) if last_clear is None else (last_clear // 3)
                    right = _common.label(right, f"REJECTED: {r.reason}")
                if right.shape != scr.shape:
                    right = cv2.resize(right, (scr.shape[1], scr.shape[0]))
                view = np.hstack([_common.label(scr, "VLC view (no key)"), right])
                cv2.imshow("secure MJPEG receiver", cv2.cvtColor(view, cv2.COLOR_RGB2BGR))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if a.max_frames and n + 1 >= a.max_frames:
                break
    dt = time.time() - t0
    total = sum(counts.values())
    print(f"\n{total} frames in {dt:.1f} s; verdicts: {counts}; log -> {a.log}")
    if not a.no_display:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
