"""Privacy metrics of the eavesdropper's pictures (journal experiment X17): faces, perception, edges.

    python experiments/privacy_metrics.py                                         # synthetic scene, quick
    python experiments/privacy_metrics.py --video clips/people.mp4 --frames 60 --stride 15 --name people
    pip install lpips   # optional: adds LPIPS (AlexNet), the learned perceptual distance

Video-privacy papers judge protection by what a viewer or an analytics model can still tell, not only by
PSNR. For every frame and protection level this takes every picture the attacker can make without the key
(the no-key decode and the replacement-attack picture, as in experiments/recognition.py) and reports the
one that is WORST for privacy (highest similarity), averaged over the frames:

  SSIM            luma structural similarity to the original (1 = identical)
  LPIPS           learned perceptual distance to the original (0 = identical; only if lpips is installed)
  edge corr.      correlation of the Sobel edge magnitudes (what a viewer uses to see shapes)
  face recall     share of the faces that a face detector finds in the original that it also finds
                  (IoU >= 0.3) in an attacker picture. Detector: --face-model, either OpenCV's YuNet
                  (face_detection_yunet_2023mar.onnx from github.com/opencv/opencv_zoo, works with OpenCV
                  4.8+ and 5) or a Haar cascade .xml (OpenCV 4 only). Frames without a face in the
                  original do not count.
  face false      share of the face-free frames in which a face is "found" in an attacker picture

Both face detectors are small and run on any laptop CPU. The person detector
of experiments/recognition.py is the stronger check. Writes sim_out/privacy_metrics/<name>.json and .md.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "software")]
sys.path.insert(0, str(ROOT / "experiments"))
from link.sources import open_source            # noqa: E402
from recognition import IOU, LEVELS, attacker_pictures, iou   # noqa: E402

OUT = ROOT / "sim_out" / "privacy_metrics"


def luma(rgb):
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float64)


def ssim(a, b):
    return float(structural_similarity(luma(a), luma(b), data_range=255.0))


def edge_corr(a, b):
    def mag(x):
        y = luma(x)
        return np.hypot(cv2.Sobel(y, cv2.CV_64F, 1, 0), cv2.Sobel(y, cv2.CV_64F, 0, 1)).ravel()
    ea, eb = mag(a), mag(b)
    if ea.std() == 0 or eb.std() == 0:
        return 0.0
    return float(np.corrcoef(ea, eb)[0, 1])


def face_detector(model=None):
    """A function rgb -> list of (x1, y1, x2, y2), or None when no detector is available.
    model: a YuNet .onnx file (cv2.FaceDetectorYN, OpenCV >= 4.8; the default choice) or a Haar cascade .xml
    (cv2.CascadeClassifier, OpenCV 4 only: OpenCV 5 moved the cascades out of the main package). Without
    model, OpenCV's bundled frontal-face cascade is tried."""
    path = model
    if path is None:
        base = getattr(getattr(cv2, "data", None), "haarcascades", "")
        path = str(Path(base) / "haarcascade_frontalface_default.xml") if base else ""
    if not path or not Path(path).exists():
        return None
    if str(path).endswith(".onnx"):
        if not hasattr(cv2, "FaceDetectorYN"):
            return None
        yn = cv2.FaceDetectorYN.create(str(path), "", (320, 320), 0.7)

        def detect(rgb):
            h, w = rgb.shape[:2]
            yn.setInputSize((w, h))
            _, faces = yn.detect(cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2BGR))
            return [] if faces is None else [(int(x), int(y), int(x + fw), int(y + fh))
                                              for x, y, fw, fh in faces[:, :4]]
        return detect
    if not hasattr(cv2, "CascadeClassifier"):
        return None
    clf = cv2.CascadeClassifier(str(path))
    if clf.empty():
        return None

    def detect(rgb):
        g = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY)
        return [(x, y, x + w, y + h) for x, y, w, h in clf.detectMultiScale(g, 1.1, 4, minSize=(20, 20))]
    return detect


def lpips_metric():
    """A function (a, b) -> LPIPS distance, or None if lpips/torch are not installed."""
    try:
        import lpips
        import torch
    except ImportError:
        return None
    net = lpips.LPIPS(net="alex", verbose=False)

    def dist(a, b):
        t = lambda x: torch.from_numpy(x.astype(np.float32) / 127.5 - 1).permute(2, 0, 1)[None]
        with torch.no_grad():
            return float(net(t(a), t(b)).item())
    return dist


def evaluate(frames, detect=None, lp=None, levels=LEVELS):
    """frames: list of RGB arrays. -> {level: metrics}. Takes, per frame, the attacker picture with the
    highest SSIM (the most revealing one) for SSIM/LPIPS/edges, and any picture for faces."""
    acc = {lv: dict(ssim=[], lpips=[], edge=[], faces=0, faces_found=0, face_frames=0, empty_frames=0,
                    false_faces=0) for lv in levels}
    for k, rgb in enumerate(frames):
        pics = attacker_pictures(rgb, ctr=(1 << 32) + k)
        truth = detect(rgb) if detect else []
        for lv in levels:
            r = acc[lv]
            cand = pics[lv]
            best = max(cand, key=lambda p: ssim(p, rgb))
            r["ssim"].append(ssim(best, rgb))
            r["edge"].append(max(edge_corr(p, rgb) for p in cand))
            if lp:
                r["lpips"].append(min(lp(p, rgb) for p in cand))
            if detect:
                found = [b for p in cand for b in detect(p)]
                if truth:
                    r["face_frames"] += 1
                    r["faces"] += len(truth)
                    r["faces_found"] += sum(any(iou(t, f) >= IOU for f in found) for t in truth)
                else:
                    r["empty_frames"] += 1
                    r["false_faces"] += bool(found)
    out = {}
    for lv, r in acc.items():
        m = lambda v: round(statistics.mean(v), 4) if v else None
        out[lv] = dict(ssim=m(r["ssim"]), lpips=m(r["lpips"]), edge_corr=m(r["edge"]),
                       face_recall=(r["faces_found"] / r["faces"]) if r["faces"] else None,
                       face_false=(r["false_faces"] / r["empty_frames"]) if r["empty_frames"] else None,
                       faces=r["faces"], face_frames=r["face_frames"], empty_frames=r["empty_frames"])
    return out


def read_frames(video, n, stride, w, h):
    src = open_source(video, w, h, loop=False)
    frames = []
    for i in range(n):
        rgb = None
        for _ in range(stride if i else 1):
            rgb = src.read()
        if rgb is None:
            break
        frames.append(rgb)
    return frames


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--stride", type=int, default=30)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--face-model", help="YuNet .onnx or Haar cascade .xml (default: OpenCV's bundled cascade, "
                                         "if this OpenCV has one)")
    ap.add_argument("--no-lpips", action="store_true")
    ap.add_argument("--name")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    name = a.name or Path(a.video).stem
    frames = read_frames(a.video, a.frames, a.stride, w, h)
    detect = face_detector(a.face_model)
    lp = None if a.no_lpips else lpips_metric()
    res = evaluate(frames, detect, lp)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(dict(source=name, frames=len(frames), face_detector=bool(detect),
                                                      lpips=bool(lp), results=res), indent=1))
    f2 = lambda v: "-" if v is None else f"{v:.3f}"
    pc = lambda v: "-" if v is None else f"{100 * v:.0f} %"
    r0 = next(iter(res.values()))
    md = [f"### Privacy metrics of the attacker's pictures ({name}, {len(frames)} frames)", "",
          "Most revealing attacker picture per frame (no-key decode or replacement attack). "
          + (f"Faces in the original: {r0['faces']} in {r0['face_frames']} frames."
             if detect else "No face detector (--face-model): face columns empty.")
          + ("" if lp else " LPIPS not installed: column empty."), "",
          "| Level | SSIM | LPIPS | edge corr. | face recall | face false alarms |", "|---|---|---|---|---|---|"]
    for lv, v in res.items():
        md.append(f"| {lv} | {f2(v['ssim'])} | {f2(v['lpips'])} | {f2(v['edge_corr'])} | "
                  f"{pc(v['face_recall'])} | {pc(v['face_false'])} |")
    (out / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
