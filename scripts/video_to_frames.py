"""Turn a video clip into a folder of JPEG frames, for a sender that cannot decode the clip itself.

    py scripts\\video_to_frames.py clip.mp4 frames_clip                 every frame, 320x240
    py scripts\\video_to_frames.py clip.mp4 frames_clip --every 3 --max 300 --size 640x480

The board's OpenCV may lack a codec for some files (an MP4 from a phone, for example). The laptop decodes it
here; copy the folder to the board and use `--set sender.source=frames_clip` (link/sources.py :: ImageFolder
plays the images in name order and loops). Frames are scaled to --size, so the board does no resizing.
"""
import argparse
import sys
from pathlib import Path


def convert(src, out, size=(320, 240), every=1, limit=600, quality=95):
    import cv2
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {src}: is the path right, and is it a video file?")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    n = i = 0
    while n < limit:
        ok, frame = cap.read()
        if not ok:
            break
        if i % every == 0:
            frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(out / f"f{n:05d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            n += 1
        i += 1
    cap.release()
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("out")
    ap.add_argument("--size", default="320x240", help="WxH, multiples of 16 (default 320x240)")
    ap.add_argument("--every", type=int, default=1, help="keep every Nth frame (default 1)")
    ap.add_argument("--max", type=int, default=600, help="at most this many frames (default 600 = 1 min at 10 fps)")
    a = ap.parse_args(argv)
    w, h = (int(x) for x in a.size.lower().split("x"))
    if w % 16 or h % 16:
        ap.error("--size: width and height must be multiples of 16 (the encoder works on 16x16 blocks)")
    n = convert(a.clip, a.out, (w, h), a.every, a.max)
    print(f"wrote {n} frames ({w}x{h}) to {a.out}")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
