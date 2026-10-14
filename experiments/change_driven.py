"""R4 -- retina-inspired change-driven encoding, and what its change map leaks (research suite).

    python experiments/change_driven.py                                   # synthetic scene
    python experiments/change_driven.py --video clips/x.mp4 --frames 90 --stride 3

A retina reports changes, not the whole scene again. A security camera mostly watches a static
scene, so the encoder could code (and encrypt) only the 16x16 macroblocks that changed, each as its
own restart segment (as in E5), and the receiver keeps the rest from its previous picture. The
encoder decides against its copy of the receiver's picture (closed loop, so errors cannot drift).

The catch is privacy: WHICH blocks change is a motion detector for the eavesdropper. Policies:
  full          every frame complete (MJPEG today; reference)
  map-visible   changed blocks sent with a plaintext block map: the attacker sees the motion mask
  map-hidden    the map is encrypted and the segments shuffled (as E5): only the COUNT is visible
  bins          the count is padded up to a power of two with "chaff" blocks
  constant-r    exactly r * blocks per frame: changed blocks first (largest change first), the rest
                filled with the blocks not refreshed for the longest time -- the chaff is useful,
                it refreshes the picture. If more than r * blocks changed, the smallest changes wait.
Every policy except constant-r forces a full refresh every 30 frames; constant-r needs none (its
chaff is a rolling refresh), which is what makes padding it to a constant size affordable.

Metrics per policy: bytes relative to full, blocks coded per frame (the encoder core's work, so a
projected cycles/pixel of max(1, 1.5 * share) with one pixel per clock at the input), PSNR/SSIM of
the receiver's picture, and three leakage numbers: mask_corr (correlation of the visible map with the
true per-block motion), count_corr (correlation over time of the blocks-per-frame count with the true
motion energy) and size_corr (the same for the frame size in bytes, which is visible whatever the
policy -- a residual side channel unless sizes are padded too). "+pad" pads every frame to the
largest one of the run; finding (synthetic scene): plain MJPEG frame sizes already track motion, so
this side channel exists for E0-E5 too, not only for change-driven coding.
Writes sim_out/change_driven/<name>.json and .md.
"""
import argparse
import io
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.sources import open_source                                  # noqa: E402
from model.entropy import huffman_encode, run_length_encode            # noqa: E402
from model.jpeg import analyse_frame, package_frame                    # noqa: E402

OUT = ROOT / "sim_out" / "change_driven"
KEY = bytes(range(16))
REFRESH = 30


def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def luma(rgb):
    return rgb.astype(np.float64) @ np.array([0.299, 0.587, 0.114])


def per_mcu(img2d, rows, cols):
    return img2d[:rows * 16, :cols * 16].reshape(rows, 16, cols, 16).mean(axis=(1, 3)).ravel()


def mcu_bytes(an):
    """Coded bytes of every MCU as its own restart segment (+2 marker bytes)."""
    return np.array([len(huffman_encode(run_length_encode(an.quant[i:i + 1]))[0]) + 2
                     for i in range(len(an.quant))])


def psnr(a, b):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if mse == 0 else 10 * math.log10(255 ** 2 / mse)


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0


def prepare(frames):
    """Everything that does not depend on the policy, computed once per frame."""
    out = []
    for t, rgb in enumerate(frames):
        an = analyse_frame(rgb)
        full = package_frame(an, KEY, 1, t + 1, "E2")
        out.append(dict(header=len(full.jpeg) - len(full.scan), scan_len=len(full.scan),
                        full_len=len(full.jpeg), dec=decode(package_frame(an).jpeg), mb=mcu_bytes(an)))
    return out


def run(frames, policy, tau=4.0, rate=0.25, pre=None):
    pre = pre or prepare(frames)
    h, w = frames[0].shape[:2]
    rows, cols = h // 16, w // 16
    n = rows * cols
    recon = None
    ref_src = None                 # source luma of every block when it was last sent (bug #21)
    age = np.zeros(n)
    prev = None
    out = dict(bytes=[], full_bytes=[], sent=[], psnr=[], ssim=[], motion=[], mask_corr=[])
    for t, rgb in enumerate(frames):
        P = pre[t]
        header, dec = P["header"], P["dec"]
        y = luma(rgb)
        motion = per_mcu(np.abs(y - prev), rows, cols) if prev is not None else np.zeros(n)
        prev = y
        periodic = t % REFRESH == 0 and policy != "constant"   # constant-r refreshes by its chaff
        if recon is None or policy == "full" or periodic:
            send = np.ones(n, bool)
        else:
            change = per_mcu(np.abs(y - ref_src), rows, cols)
            changed = change > tau
            if policy in ("map-visible", "map-hidden"):
                send = changed
            elif policy == "bins":
                k = int(changed.sum())
                target = min(n, 1 << max(3, math.ceil(math.log2(max(k, 1)))))
                send = changed.copy()
                extra = np.argsort(-age + 1e9 * changed)[: target - k]   # stalest unchanged blocks
                send[extra] = True
            else:                                                       # constant-r
                budget = int(round(rate * n))
                order = np.argsort(-(change * changed) - 1e-6 * age)    # biggest changes, then stalest
                send = np.zeros(n, bool)
                send[order[:budget]] = True
        mb = P["mb"]
        size = header + (P["scan_len"] if send.all() else int(mb[send].sum()) + (n + 7) // 8)
        if recon is None:
            recon = dec.copy()
        else:
            m = send.reshape(rows, cols).repeat(16, 0).repeat(16, 1)
            recon = recon.copy()
            recon[:rows * 16, :cols * 16][m] = dec[:rows * 16, :cols * 16][m]
        age = np.where(send, 0, age + 1)
        m16 = send.reshape(rows, cols).repeat(16, 0).repeat(16, 1)
        if ref_src is None:
            ref_src = y.copy()
        else:
            ref_src[:rows * 16, :cols * 16][m16] = y[:rows * 16, :cols * 16][m16]
        out["bytes"].append(size)
        out["full_bytes"].append(P["full_len"])
        out["sent"].append(int(send.sum()))
        out["psnr"].append(psnr(rgb, recon))
        out["ssim"].append(structural_similarity(luma(rgb), luma(recon), data_range=255))
        out["motion"].append(float(motion.sum()))
        if t % REFRESH and motion.std() > 0:
            out["mask_corr"].append(corr(send, motion))
    return out, n


def pad_sizes(o):
    """Constant-size stream: every frame padded to the largest frame of the run (an upper bound on
    the cost of closing the size side channel; a real link would pad to a fixed budget)."""
    m = max(o["bytes"][1:])                       # frame 0 is the one-off start of the session
    o = dict(o)
    o["bytes"] = o["bytes"][:1] + [m] * (len(o["bytes"]) - 1)
    return o


def summarise(o, n, policy):
    nonref = [i for i in range(len(o["sent"])) if i % REFRESH]
    share = statistics.mean(o["sent"][i] / n for i in nonref) if nonref else 1.0
    visible_map = policy == "map-visible"
    count_series = [o["sent"][i] for i in nonref]
    motion_series = [o["motion"][i] for i in nonref]
    return dict(bytes_ratio=sum(o["bytes"]) / sum(o["full_bytes"]), block_share=share,
                projected_cpp=max(1.0, 1.5 * share),
                psnr=statistics.mean(o["psnr"]), ssim=statistics.mean(o["ssim"]),
                mask_corr=statistics.mean(o["mask_corr"]) if (visible_map and o["mask_corr"]) else None,
                count_corr=None if policy == "full" else corr(count_series, motion_series),
                size_corr=corr([o["bytes"][i] for i in nonref], motion_series))


POLICIES = [("full", {}), ("full+pad", {}), ("map-visible", {}), ("map-hidden", {}), ("bins", {}),
            ("constant-0.25", dict(rate=0.25)), ("constant-0.25+pad", dict(rate=0.25)),
            ("constant-0.5", dict(rate=0.5))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="synthetic")
    ap.add_argument("--frames", type=int, default=90)
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--size", default="320x240")
    ap.add_argument("--tau", type=float, default=4.0, help="change threshold, mean |dY| per block")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split("x"))
    name = a.name or Path(a.video).stem
    src = open_source(a.video, w, h, loop=True)
    frames = []
    for i in range(a.frames * a.stride):
        f = src.read()
        if f is None:
            break
        if i % a.stride == 0:
            frames.append(f)
    res = {}
    pre = prepare(frames)
    for pol, kw in POLICIES:
        base = pol.replace("+pad", "")
        base = "constant" if base.startswith("constant") else base
        o, n = run(frames, base, tau=a.tau, pre=pre, **kw)
        if pol.endswith("+pad"):
            o = pad_sizes(o)
        res[pol] = summarise(o, n, base)
        print(pol, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[pol].items()})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(dict(source=name, frames=len(frames), tau=a.tau,
                                                      refresh=REFRESH, results=res), indent=1))
    f2 = lambda v: "--" if v is None else f"{v:.2f}"
    md = [f"### R4: change-driven encoding ({name}, {len(frames)} frames, threshold {a.tau}, refresh every {REFRESH})", "",
          "| Policy | Bytes vs full | Blocks coded | Projected cycles/px | PSNR | SSIM | Mask leak | Count leak | Size leak |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res.items():
        md.append(f"| {k} | {100 * v['bytes_ratio']:.0f} % | {100 * v['block_share']:.0f} % | {v['projected_cpp']:.2f} | "
                  f"{v['psnr']:.1f} | {v['ssim']:.3f} | {f2(v['mask_corr'])} | {f2(v['count_corr'])} | {f2(v['size_corr'])} |")
    md += ["", "Leak columns: correlation with the true motion (1 = the attacker sees the motion exactly). "
               "Projected cycles/px assumes one input pixel per clock (the input then limits at 1.0)."]
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
