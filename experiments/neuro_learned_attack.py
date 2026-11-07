"""N4: can a network trained on (ciphertext, plaintext) pairs undo V1-V3?

Usage (Kaggle GPU; needs PyTorch):
    python experiments/neuro_learned_attack.py --dataset eventreid --data <root> [--keys 5] [--epochs 30] [--quick]

Method (DESIGN §8.2 N4). Every sample is protected under its own master key (fresh key per sample, key index =
sample index), cut into windows, and turned into the attacker's input: a 5-bin voxel grid of the keyless events
(neuro.voxel) plus a per-pixel count channel. A small U-Net (3 levels) is trained to output the target frame:
the ground-truth frame where it exists (synthetic v2e-lite, HQF), else the plaintext count image (labelled).
Train and test recordings are disjoint (split by group; the overlap guard asserts no group is in both).
Control (f): an MLP that sees only the public per-bucket count series of the window. Leakage measure fixed in
§8.1: network SSIM - control (f) SSIM, paired cluster-bootstrap CI on identical test windows. Views: plain
(upper bound), V1, V2, V3, Du 2021, Zhang 2024 (V4 shows no events: not trained).
Writes sim_out/neuro/n4/learned_attack.{json,md}.
"""
import argparse

import numpy as np

import neuro_common as C
from neuro import attacks
from neuro.stats import cluster_bootstrap_ci, n_clusters, paired_bootstrap_diff
from neuro.voxel import voxel_grid


def windows_of(samples, view, T, win_us, n_keys):
    """[(x (6, H, W), counts (win/64,), target (H, W), group)] for one view."""
    out = []
    for si, (ev, _, grp, geom, frames) in enumerate(samples):
        if len(ev) == 0:
            continue
        k = si % n_keys
        if view == "plain":
            e = ev
        elif view.startswith("V"):
            e = C.keyless_events(C.protect(ev, geom, int(view[1]), T, key_index=k))
        elif view == "Du 2021":
            du = C.baseline("du2021")
            e = du.encrypt(ev, geom.W, geom.H, du.DuKey.from_seed(C.master(k)))
        else:
            e, _ = C.baseline("zhang2024").encrypt(ev, geom.W, geom.H, C.master(k))
        t0 = int(ev["t"].min())
        n_w = int((int(ev["t"].max()) - t0) // win_us) + 1
        for w in range(n_w):
            lo, hi = t0 + w * win_us, t0 + (w + 1) * win_us
            we = e[(e["t"].astype(np.int64) >= lo) & (e["t"].astype(np.int64) < hi)]
            pe = ev[(ev["t"].astype(np.int64) >= lo) & (ev["t"].astype(np.int64) < hi)]
            vg = voxel_grid(we, 5, H=geom.H, W=geom.W) if len(we) else np.zeros((5, geom.H, geom.W))
            cnt_img = attacks.event_count_frame(we, geom) if len(we) else np.zeros((geom.H, geom.W))
            x = np.concatenate([vg, cnt_img[None] / max(1.0, cnt_img.max())]).astype(np.float32)
            cs = np.bincount((pe["t"].astype(np.int64) - lo) // 64, minlength=win_us // 64)[:win_us // 64]
            if frames is not None:
                tgt = frames[min(len(frames) - 1, int((hi - 10_000) // 1000))] / 255.0
            else:
                c = attacks.event_count_frame(pe, geom)
                tgt = c / max(1.0, c.max())
            out.append((x, cs.astype(np.float32), tgt.astype(np.float32), grp))
    return out


def build(torch, H, W, n_counts):
    nn = torch.nn

    class UNet(nn.Module):
        def __init__(self, c=32):
            super().__init__()
            def blk(i, o):
                return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.ReLU(), nn.Conv2d(o, o, 3, padding=1), nn.ReLU())
            self.e1, self.e2, self.e3 = blk(6, c), blk(c, 2 * c), blk(2 * c, 4 * c)
            self.d2, self.d1 = blk(6 * c, 2 * c), blk(3 * c, c)
            self.out = nn.Conv2d(c, 1, 1)

        def forward(self, x):
            f = nn.functional
            a = self.e1(x)
            b = self.e2(f.max_pool2d(a, 2))
            c = self.e3(f.max_pool2d(b, 2))
            u = f.interpolate(c, size=b.shape[-2:])
            d = self.d2(torch.cat([u, b], 1))
            u = f.interpolate(d, size=a.shape[-2:])
            return torch.sigmoid(self.out(self.d1(torch.cat([u, a], 1))))[:, 0]

    mlp = nn.Sequential(nn.Linear(n_counts, 256), nn.ReLU(), nn.Linear(256, H * W), nn.Sigmoid())
    return UNet(), mlp


def batch_size(px, cap=32, budget_px=3_000_000):
    """Images per batch: the U-Net keeps ~14 activation maps of up to 32 channels per image for backward, about
    0.4 GB at 480 x 640, so 32 of them do not fit a 15 GB T4. 32 for N-MNIST / DVS Gesture, 9 for Event-ReId."""
    return max(1, min(cap, budget_px // px))


def train(torch, model, X, Y, epochs, dev, seed, bs=None):
    bs = bs or batch_size(Y[0].size)             # pixels per sample (flattened for the MLP control, too)
    torch.manual_seed(seed)
    model = model.to(dev)
    opt = torch.optim.Adam(model.parameters(), 1e-3)
    Xt, Yt = torch.from_numpy(X), torch.from_numpy(Y)
    for _ in range(epochs):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), bs):
            j = perm[i:i + bs]
            p = model(Xt[j].to(dev)).reshape(Yt[j].shape)
            loss = torch.nn.functional.l1_loss(p, Yt[j].to(dev))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model


def predict(torch, model, X, shape, dev):
    bs = 2 * batch_size(shape[0] * shape[1])
    with torch.no_grad():
        return np.concatenate([model(torch.from_numpy(X[i:i + bs]).to(dev)).reshape(-1, *shape).cpu().numpy()
                               for i in range(0, len(X), bs)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--win-ms", type=float, default=20.0)
    ap.add_argument("--T", type=int, default=1024)
    ap.add_argument("--max-windows", type=int, default=6,
                    help="windows kept per recording: the contiguous run with the most events (4 with --quick)")
    ap.add_argument("--views", nargs="+", default=["plain", "V1", "V2", "V3", "Du 2021", "Zhang 2024"])
    a = ap.parse_args()
    try:
        import torch
    except ImportError:
        raise SystemExit("N4 needs PyTorch (Kaggle job: software/system/kaggle/kaggle_neuro.py); not run")
    from skimage.metrics import structural_similarity
    if a.quick:
        a.epochs, a.keys = 2, 2
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    samples = C.load_samples(a.dataset, a.data, limit=a.limit or (12 if a.quick else 400), seed=a.seed)
    win = int(a.win_ms * 1000)
    samples = C.crop_samples(samples, win, min(a.max_windows, 4) if a.quick else a.max_windows)
    groups = sorted({s[2] for s in samples})
    train_g = set(groups[: max(1, len(groups) // 2)])
    test_g = set(groups) - train_g
    assert not (train_g & test_g), "overlap guard: a recording group is in train and test"
    res, rows = {}, []
    for view in a.views:
        if view in ("Du 2021", "Zhang 2024") and not C.baseline("du2021" if view.startswith("Du") else "zhang2024"):
            continue
        W_ = windows_of(samples, view, a.T, win, a.keys)
        tr = [w for w in W_ if w[3] in train_g]
        te = [w for w in W_ if w[3] in test_g]
        if not tr or not te:
            continue
        H, Wd = tr[0][2].shape
        net, mlp = build(torch, H, Wd, len(tr[0][1]))
        X, Y = np.stack([w[0] for w in tr]), np.stack([w[2] for w in tr])
        net = train(torch, net, X, Y, a.epochs, dev, a.seed)
        Xc = np.stack([w[1] for w in tr])
        mlp = train(torch, mlp, Xc / max(1.0, Xc.max()), Y.reshape(len(Y), -1), a.epochs, dev, a.seed)
        pn = predict(torch, net, np.stack([w[0] for w in te]), (H, Wd), dev)
        pc = predict(torch, mlp, np.stack([w[1] for w in te]) / max(1.0, Xc.max()), (H, Wd), dev)
        sn = [structural_similarity(p, w[2], data_range=1.0) for p, w in zip(pn, te)]
        sc = [structural_similarity(p, w[2], data_range=1.0) for p, w in zip(pc, te)]
        g = [w[3] for w in te]
        d = paired_bootstrap_diff(sn, sc, g, n=1000, seed=a.seed)
        res[view] = {"ssim_net": cluster_bootstrap_ci(sn, g, n=1000, seed=a.seed),
                     "ssim_control_f": cluster_bootstrap_ci(sc, g, n=1000, seed=a.seed), "net_minus_control_f": d,
                     "train_windows": len(tr), "test_windows": len(te), "test_clusters": n_clusters(g),
                     "P1_pass": bool(d[2] < 0.05)}
        rows.append((view, res[view]["ssim_net"], res[view]["ssim_control_f"], d, "yes" if d[2] < 0.05 else "no",
                     n_clusters(g)))
    data = {"results": res,
            "meta": C.meta(a, dataset=a.dataset, synthetic=a.data is None, n_keys=a.keys, device=dev,
                           target="ground truth" if samples[0][4] is not None else "plaintext count image",
                           ci="paired cluster bootstrap 95 %, 1000 resamples")}
    md = ["# N4 learned attack" + (" (synthetic smoke data)" if a.data is None else ""), "",
          C.table(["view", "SSIM network", "SSIM control (f)", "network - control (f)", "P1 pass", "test clusters"],
                  rows)]
    C.write("n4", "learned_attack", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
