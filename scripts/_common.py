"""Helpers shared by the scripts (path setup, key parsing, video reading)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

DEMO_KEY_HEX = "000102030405060708090a0b0c0d0e0f"   # Phase I pre-shared key (demo only!)


def parse_key(hexstr):
    key = bytes.fromhex(hexstr)
    if len(key) != 16:
        raise SystemExit("key must be 32 hex characters (128 bits)")
    return key


def parse_size(s):
    if not s:
        return None
    w, h = s.lower().split("x")
    return int(w), int(h)


def open_video(src):
    """src: path to a video file, or a webcam index such as '0'."""
    cap = cv2.VideoCapture(int(src) if str(src).isdigit() else str(src))
    if not cap.isOpened():
        raise SystemExit(f"could not open video source {src!r}")
    return cap


def read_frames(src, size=None, max_frames=None, stride=1, start=0):
    """Yields (index, RGB uint8 frame). Resizes to size=(w, h) when given."""
    cap = open_video(src)
    idx = 0
    out = 0
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            if idx >= start and (idx - start) % stride == 0:
                if size:
                    bgr = cv2.resize(bgr, size, interpolation=cv2.INTER_AREA)
                yield idx, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                out += 1
                if max_frames and out >= max_frames:
                    break
            idx += 1
    finally:
        cap.release()


def video_fps(src, default=30.0):
    cap = open_video(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or default
    cap.release()
    return fps if fps > 1 else default


def label(img_rgb, text):
    out = img_rgb.copy()
    cv2.rectangle(out, (0, 0), (min(out.shape[1], 12 + 11 * len(text)), 26), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def save_rgb(path, rgb):
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def as_np(b):
    return np.frombuffer(b, np.uint8)
