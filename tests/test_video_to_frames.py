"""scripts/video_to_frames.py: a clip becomes a folder of frames that link/sources.py :: ImageFolder plays."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from link.sources import ImageFolder               # noqa: E402
from scripts import video_to_frames as v2f       # noqa: E402


def test_clip_to_frames_plays_as_a_source(tmp_path):
    import cv2
    clip = tmp_path / "clip.avi"
    vw = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"MJPG"), 10, (200, 120))
    for k in range(12):
        vw.write(np.full((120, 200, 3), 20 * k, np.uint8))
    vw.release()
    n = v2f.convert(clip, tmp_path / "frames", (64, 48), every=2)
    assert n == 6, f"12 frames, every 2nd -> 6, got {n}"
    src = ImageFolder(str(tmp_path / "frames"), 64, 48)
    img = src.read()
    assert img.shape == (48, 64, 3), img.shape
