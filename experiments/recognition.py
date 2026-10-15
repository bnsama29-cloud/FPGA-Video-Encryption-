"""Recognition test (GUIDE B23): can an off-the-shelf detector find the PEOPLE in the eavesdropper's
pictures? Correlations need the picture to be in the right place; a person looking at the screen, or a
detector, does not.

    python experiments/recognition.py --video clips/x.mp4 --frames 40 --stride 30 --name x     # needs a GPU
                                                                                              # or patience

Detector: torchvision Faster R-CNN ResNet-50 FPN v2 with COCO weights (downloaded on first use), class
"person", score >= 0.5. Every picture is 320x240 RGB.

Attacker pictures per level (the attacker runs the detector on every picture it can make, and a person
counts as found if ANY of them shows it):
  E1, E2, E4   the no-key decode and the replacement-attack picture
  E5 (N=1)     the same two pictures of the shuffled stream (restart marker after every macroblock)
  E5 (N=32)    the same for segments of 32 macroblocks (long intact strips)
  plain        the unencrypted JPEG (reference; should find what the original shows)

Metrics, over the frames in which the detector finds at least one person in the ORIGINAL:
  recall@IoU   share of the original's person boxes matched (IoU >= 0.3) by a box in an attacker picture
               (meaningful for E1-E4; shuffled levels move blocks, so a match there is luck)
  frame hit    share of those frames in which the attacker picture shows at least one person anywhere
and over the frames without a person in the original:
  false alarm  share in which the attacker picture shows a person (what "frame hit" means by chance)
Writes sim_out/recognition/<name>.json and .md.
"""
import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from link.sources import open_source                                           # noqa: E402
from model.jpeg import analyse_frame, package_frame, replacement_attack_jpeg   # noqa: E402

OUT = ROOT / "sim_out" / "recognition"
KEY = bytes(range(16))
LEVELS = ["plain", "E1", "E2", "E4", "E5 (N=1)", "E5 (N=32)"]
SCORE, IOU = 0.5, 0.3


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def attacker_pictures(rgb, ctr):
    """level -> list of pictures the attacker can make without the key."""
    from restart_interval import attack_ri, encode_ri
    an = analyse_frame(rgb)
    out = {"plain": [decode(package_frame(an).jpeg)]}
    for lv in ("E1", "E2", "E4"):
        j = package_frame(an, KEY, 1, ctr, lv).jpeg
        out[lv] = [decode(j), decode(replacement_attack_jpeg(j))]
    for n, lv in ((1, "E5 (N=1)"), (32, "E5 (N=32)")):
        jpeg, _, shown, _ = encode_ri(an, n, ctr=ctr)
        out[lv] = [decode(jpeg), decode(attack_ri(an, shown, n))]
    return out


def iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def torchvision_detector():
    """Returns detect(list of HxWx3 uint8) -> list of person boxes [x1, y1, x2, y2] per picture."""
    import torch
    from torchvision.models.detection import FasterRCNN_ResNet50_FPN_V2_Weights, fasterrcnn_resnet50_fpn_v2
    w = FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT
    net = fasterrcnn_resnet50_fpn_v2(weights=w, box_score_thresh=SCORE).eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    net.to(dev)
    person = w.meta["categories"].index("person")

    @torch.no_grad()
    def detect(imgs):
        x = [torch.from_numpy(i.copy()).permute(2, 0, 1).float().div(255).to(dev) for i in imgs]
        res = net(x)
        return [[b.tolist() for b, l, s in zip(r["boxes"], r["labels"], r["scores"])
                 if int(l) == person and float(s) >= SCORE] for r in res]
    return detect


def evaluate(frames, detect):
    """frames: list of RGB pictures. Returns per-level metrics (see module docstring)."""
    stats = {lv: dict(gt=0, matched=0, frames_with=0, hit=0, frames_without=0, false_alarm=0) for lv in LEVELS}
    for t, rgb in enumerate(frames):
        pics = attacker_pictures(rgb, ctr=t + 1)
        flat = [rgb] + [p for lv in LEVELS for p in pics[lv]]
        boxes = detect(flat)
        gt, k = boxes[0], 1
        for lv in LEVELS:
            found = []                                   # union over the attacker's pictures
            for _ in pics[lv]:
                found += boxes[k]
                k += 1
            s = stats[lv]
            if gt:
                s["frames_with"] += 1
                s["gt"] += len(gt)
                s["matched"] += sum(any(iou(g, f) >= IOU for f in found) for g in gt)
                s["hit"] += bool(found)
            else:
                s["frames_without"] += 1
                s["false_alarm"] += bool(found)
    res = {}
    for lv, s in stats.items():
        res[lv] = dict(recall_iou=s["matched"] / s["gt"] if s["gt"] else None,
                       frame_hit=s["hit"] / s["frames_with"] if s["frames_with"] else None,
                       false_alarm=s["false_alarm"] / s["frames_without"] if s["frames_without"] else None,
                       frames_with_person=s["frames_with"], frames_without=s["frames_without"], persons=s["gt"])
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--stride", type=int, default=30)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    name = a.name or Path(a.video).stem
    src = open_source(a.video, w, h, loop=False)
    frames = []
    for i in range(a.frames):
        rgb = None
        for _ in range(a.stride if i else 1):
            rgb = src.read()
        if rgb is None:
            break
        frames.append(rgb)
    res = evaluate(frames, torchvision_detector())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(dict(source=name, frames=len(frames), score=SCORE, iou=IOU,
                                                      results=res), indent=1))
    f = lambda v: "--" if v is None else f"{100 * v:.0f} %"
    r0 = next(iter(res.values()))
    md = [f"### B23: person detection in the attacker's pictures ({name}, {len(frames)} frames; "
          f"{r0['frames_with_person']} with a person, {r0['persons']} persons)", "",
          "| Level | Recall (IoU >= 0.3) | Frames with a person found | False alarms (no person in original) |",
          "|---|---|---|---|"]
    for lv, v in res.items():
        md.append(f"| {lv} | {f(v['recall_iou'])} | {f(v['frame_hit'])} | {f(v['false_alarm'])} |")
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
