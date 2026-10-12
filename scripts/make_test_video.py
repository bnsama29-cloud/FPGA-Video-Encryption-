"""Creates a test video so you can run everything without your own footage.

Pans and zooms across scikit-image sample photos (faces, text-like detail, flat
areas, fine texture) with a moving overlay and a frame counter.

    python scripts/make_test_video.py --out test_video.mp4 --frames 90 --size 640x480
"""
import argparse

import _common  # noqa: F401
import cv2
import numpy as np
from skimage import data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="test_video.mp4")
    ap.add_argument("--frames", type=int, default=90)
    ap.add_argument("--size", default="640x480")
    ap.add_argument("--fps", type=float, default=30)
    a = ap.parse_args()
    W, H = _common.parse_size(a.size)

    sources = [data.astronaut(), data.coffee(), data.rocket(), data.chelsea()]
    sources = [cv2.resize(s, (int(W * 1.4), int(H * 1.4)), interpolation=cv2.INTER_CUBIC)
               for s in sources]
    per = max(1, a.frames // len(sources))
    vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, H))
    for f in range(a.frames):
        src = sources[min(f // per, len(sources) - 1)]
        t = (f % per) / max(1, per - 1)
        sh, sw = src.shape[:2]
        x0 = int((sw - W) * t)
        y0 = int((sh - H) * (0.5 + 0.5 * np.sin(2 * np.pi * t)) )
        frame = src[y0:y0 + H, x0:x0 + W].copy()
        cx = int(W * (0.1 + 0.8 * t))
        cv2.circle(frame, (cx, H - 60), 30, (255, 220, 0), -1)
        cv2.putText(frame, f"FRAME {f:04d}  CAM-01", (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (255, 255, 255), 2, cv2.LINE_AA)
        vw.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    vw.release()
    print(f"wrote {a.out}: {a.frames} frames, {W}x{H} @ {a.fps} fps")


if __name__ == "__main__":
    main()
