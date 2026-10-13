"""Learned (neural-network) attack on the selective encryption -- the GPU experiment.

Question for the paper: if an eavesdropper trains a network on lots of video,
how much of the picture can it recover WITHOUT the key, per mode? This is the
strongest attacker we model (in the spirit of the deep sign-retrieval attacks,
Suzuki et al. arXiv:2209.10712 / 2504.21632, and the optimisation-based sign
recovery of Lin et al. 2024). Expectation: E1/E2 leak structure a network can
partly undo; E5 (shuffled MCUs) should resist. Whatever comes out is the result.

    pip install -r requirements-gpu.txt      (PyTorch with CUDA, on the RTX 4060 laptop)
    python experiments/learned_attack.py --train-source clips/train.mp4 --test-source clips/test.mp4 \\
           --modes E1 E2 E4 E5 --size 160x128 --frames 3000 --epochs 25

Steps (all in one command, cached in sim_out/learned_attack/):
  1. data:  for each frame, encrypt with a random key (golden model), keep what an
            eavesdropper sees -- the no-key decode and the replacement-attack picture
            (6 input channels) -- and the original (target).
  2. train: a small U-Net, L1 loss, AdamW, mixed precision on CUDA.
  3. eval:  on the TEST video only: PSNR / SSIM / edge correlation of
            (a) the replacement attack (no learning) and (b) the network output.
Use DIFFERENT videos for --train-source and --test-source (different scenes), or
the network just memorises the background and the result means nothing.
Writes results.json, results.md and examples_<mode>.png (original | attack | network).
"""
import argparse
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.sources import open_source                                    # noqa: E402
from model.jpeg import analyse_frame, package_frame, replacement_attack_jpeg  # noqa: E402

OUT = ROOT / "sim_out" / "learned_attack"


# ------------------------------------------------------------------ data
def decode(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def cache_path(source, mode, n, size, stride, quality, tag):
    """Cache file of one dataset. The SOURCE is part of the name: without it, a second run with other
    videos silently reused the first run's frames (bug log #13)."""
    w, h = size
    src = hashlib.sha1(str(source).encode()).hexdigest()[:8]
    return OUT / f"data_{tag}_{Path(str(source)).stem[:20]}-{src}_{mode}_{w}x{h}_{n}_s{stride}_q{quality}.npz"


def make_pairs(source, mode, n, size, stride, quality, tag):
    """Returns (X uint8 [n, H, W, 6], Y uint8 [n, H, W, 3]); cached as .npz."""
    w, h = size
    cache = cache_path(source, mode, n, size, stride, quality, tag)
    if cache.exists():
        d = np.load(cache)
        return d["X"], d["Y"]
    src = open_source(source, w, h, loop=False)
    X, Y = [], []
    t0 = time.time()
    while len(Y) < n:
        for _ in range(stride - 1):
            src.read()
        rgb = src.read()
        if rgb is None:
            break
        key = os.urandom(16)                       # the attacker never knows the key
        e = package_frame(analyse_frame(rgb, quality), key, 1, len(Y) + 1, mode)
        X.append(np.concatenate([decode(e.jpeg), decode(replacement_attack_jpeg(e.jpeg))], axis=2))
        Y.append(rgb)
        if len(Y) % 200 == 0:
            print(f"    {tag} {mode}: {len(Y)} frames ({time.time() - t0:.0f} s)")
    if len(Y) < 50:
        raise SystemExit(f"only {len(Y)} frames from {source}; need a longer video or smaller --stride")
    X, Y = np.stack(X), np.stack(Y)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, X=X, Y=Y)
    return X, Y


# ----------------------------------------------------------------- metrics
def luma(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float64)


def edge_corr(a, b):
    ea = np.hypot(cv2.Sobel(luma(a), cv2.CV_64F, 1, 0), cv2.Sobel(luma(a), cv2.CV_64F, 0, 1)).ravel()
    eb = np.hypot(cv2.Sobel(luma(b), cv2.CV_64F, 1, 0), cv2.Sobel(luma(b), cv2.CV_64F, 0, 1)).ravel()
    return float(np.corrcoef(ea, eb)[0, 1]) if ea.std() and eb.std() else 0.0


def scores(pred, target):
    from skimage.metrics import structural_similarity
    mse = np.mean((pred.astype(np.float64) - target) ** 2)
    return dict(psnr=float(10 * np.log10(255 ** 2 / max(mse, 1e-9))),
                ssim=float(structural_similarity(luma(pred), luma(target), data_range=255)),
                edge_corr=edge_corr(pred, target))


# ------------------------------------------------------------------ model
def build_unet(torch, nn, base=32):
    def block(i, o):
        return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                             nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))

    class UNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.e1, self.e2, self.e3 = block(6, base), block(base, 2 * base), block(2 * base, 4 * base)
            self.mid = block(4 * base, 8 * base)
            self.u3, self.d3 = nn.ConvTranspose2d(8 * base, 4 * base, 2, 2), block(8 * base, 4 * base)
            self.u2, self.d2 = nn.ConvTranspose2d(4 * base, 2 * base, 2, 2), block(4 * base, 2 * base)
            self.u1, self.d1 = nn.ConvTranspose2d(2 * base, base, 2, 2), block(2 * base, base)
            self.out = nn.Conv2d(base, 3, 1)
            self.pool = nn.MaxPool2d(2)

        def forward(self, x):
            e1 = self.e1(x)
            e2 = self.e2(self.pool(e1))
            e3 = self.e3(self.pool(e2))
            m = self.mid(self.pool(e3))
            d3 = self.d3(torch.cat([self.u3(m), e3], 1))
            d2 = self.d2(torch.cat([self.u2(d3), e2], 1))
            d1 = self.d1(torch.cat([self.u1(d2), e1], 1))
            # predict a correction on top of the replacement-attack picture (channels 3..5)
            return x[:, 3:6] + self.out(d1)

    return UNet()


def to_tensor(torch, a, device):
    return torch.from_numpy(a).to(device).permute(0, 3, 1, 2).float().div_(255.0)


def train_and_eval(mode, Xtr, Ytr, Xte, Yte, a):
    import torch
    from torch import nn
    torch.manual_seed(0)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cpu":
        print("    WARNING: no CUDA GPU found, training on the CPU (slow; use --epochs 2 just to test)")
    net = build_unet(torch, nn, a.width).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs)
    use_amp = dev == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    n = len(Xtr)
    for ep in range(a.epochs):
        net.train()
        perm = np.random.default_rng(ep).permutation(n)
        tot, t0 = 0.0, time.time()
        for i in range(0, n - a.batch + 1, a.batch):
            idx = perm[i:i + a.batch]
            x, y = to_tensor(torch, Xtr[idx], dev), to_tensor(torch, Ytr[idx], dev)
            if np.random.random() < 0.5:                       # flips keep the 8x8 grid aligned
                x, y = x.flip(3), y.flip(3)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                loss = nn.functional.l1_loss(net(x), y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            tot += loss.item() * len(idx)
        sched.step()
        print(f"    {mode} epoch {ep + 1}/{a.epochs}: L1 {tot / n:.4f} ({time.time() - t0:.0f} s)")
    torch.save(net.state_dict(), OUT / f"unet_{mode}.pt")
    net.eval()
    base, learned, examples = [], [], []
    with torch.no_grad():
        for i in range(0, len(Xte), a.batch):
            x = to_tensor(torch, Xte[i:i + a.batch], dev)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                p = net(x).float().clamp_(0, 1)
            pred = (p.permute(0, 2, 3, 1).cpu().numpy() * 255 + 0.5).astype(np.uint8)
            for j, pr in enumerate(pred):
                k = i + j
                base.append(scores(Xte[k, :, :, 3:6], Yte[k]))
                learned.append(scores(pr, Yte[k]))
                if k in (0, len(Xte) // 2, len(Xte) - 1):
                    examples.append(np.hstack([Yte[k], Xte[k, :, :, 3:6], pr]))
    cv2.imwrite(str(OUT / f"examples_{mode}.png"), cv2.cvtColor(np.vstack(examples), cv2.COLOR_RGB2BGR))
    mean = lambda rows, key: float(np.mean([r[key] for r in rows]))
    return {"replacement_attack": {k: mean(base, k) for k in ("psnr", "ssim", "edge_corr")},
            "learned_attack": {k: mean(learned, k) for k in ("psnr", "ssim", "edge_corr")},
            "train_frames": int(n), "test_frames": int(len(Xte)), "epochs": a.epochs, "device": dev}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train-source", required=True, help="video file / webcam:N / synthetic (synthetic: testing only)")
    ap.add_argument("--test-source", required=True, help="a DIFFERENT video for evaluation")
    ap.add_argument("--modes", nargs="+", default=["E1", "E2", "E4", "E5"])
    ap.add_argument("--size", default="160x128", help="WxH, multiples of 16")
    ap.add_argument("--frames", type=int, default=3000, help="training frames")
    ap.add_argument("--test-frames", type=int, default=300)
    ap.add_argument("--stride", type=int, default=2, help="use every Nth video frame")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--width", type=int, default=32, help="U-Net base channels (32 fits an 8 GB GPU)")
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--out", help="output folder (default sim_out/learned_attack); use one per train/test pair")
    a = ap.parse_args()
    if a.train_source == a.test_source and a.train_source != "synthetic":
        raise SystemExit("use different videos for training and testing (otherwise the network memorises the scene)")
    size = tuple(int(v) for v in a.size.split("x"))
    global OUT
    if a.out:
        OUT = Path(a.out)
    OUT.mkdir(parents=True, exist_ok=True)
    res_file = OUT / "results.json"
    results = json.loads(res_file.read_text()) if res_file.exists() else {}
    for mode in a.modes:
        print(f"== {mode}: building data")
        Xtr, Ytr = make_pairs(a.train_source, mode, a.frames, size, a.stride, a.quality, "train")
        Xte, Yte = make_pairs(a.test_source, mode, a.test_frames, size, a.stride, a.quality, "test")
        print(f"== {mode}: training on {len(Xtr)} frames, testing on {len(Xte)}")
        results[mode] = train_and_eval(mode, Xtr, Ytr, Xte, Yte, a)
        res_file.write_text(json.dumps(results, indent=2))
    lines = ["| Mode | Replacement attack PSNR / SSIM / edge corr | Learned attack PSNR / SSIM / edge corr |",
             "|---|---|---|"]
    for m, r in results.items():
        b, l = r["replacement_attack"], r["learned_attack"]
        lines.append(f"| {m} | {b['psnr']:.2f} dB / {b['ssim']:.3f} / {b['edge_corr']:.3f} "
                     f"| {l['psnr']:.2f} dB / {l['ssim']:.3f} / {l['edge_corr']:.3f} |")
    (OUT / "results.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines) + f"\n\nwritten {OUT}/")


if __name__ == "__main__":
    main()
