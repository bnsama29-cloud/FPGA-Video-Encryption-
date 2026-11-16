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
from pathlib import Path

import numpy as np

import neuro_common as C
from neuro import attacks
from neuro.stats import cluster_bootstrap_ci, n_clusters, paired_bootstrap_diff
from neuro.voxel import voxel_grid


def plain_targets(samples, win_us, recon):
    """Per recording, the plaintext E2VID reconstruction of every window (E2VID is recurrent: reset per recording,
    windows in order, as in N3). The target where a dataset has no intensity frames (DESIGN §8.2 N4); bug #68: the
    plaintext count image used before is mostly zero even inside the person box, so the L1 loss drove the network to
    a blank output on every view, plaintext included."""
    out = []
    for ev, _, _, geom, frames in samples:
        if frames is not None or len(ev) == 0 or recon is None:
            out.append(None)
            continue
        recon.reset()
        t0 = int(ev["t"].min())
        n_w = int((int(ev["t"].max()) - t0) // win_us) + 1
        ims = []
        for w in range(n_w):
            pe = ev[(ev["t"].astype(np.int64) >= t0 + w * win_us) & (ev["t"].astype(np.int64) < t0 + (w + 1) * win_us)]
            ims.append(np.clip(recon(pe, geom)["e2vid"], 0, 1).astype(np.float32) if len(pe)
                       else (ims[-1] if ims else np.zeros((geom.H, geom.W), np.float32)))
        out.append(ims)
    return out


def windows_of(samples, view, T, win_us, n_keys, rois=None, targets=None):
    """[(x (6, H, W), counts (win/64,), target (H, W), group, box)] for one view. With rois (C.load_rois), box is
    the scoring region (C.roi_box) and windows without a labelled frame are left out; else box is None. targets
    (plain_targets) gives the per-window target where the dataset has no frames; without it the plaintext count
    image (laptop smoke runs only)."""
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
            box = C.roi_box(rois[si], lo, hi, geom.W, geom.H) if rois is not None else None
            if rois is not None and rois[si] is not None and box is None:
                continue
            we = e[(e["t"].astype(np.int64) >= lo) & (e["t"].astype(np.int64) < hi)]
            pe = ev[(ev["t"].astype(np.int64) >= lo) & (ev["t"].astype(np.int64) < hi)]
            vg = voxel_grid(we, 5, H=geom.H, W=geom.W) if len(we) else np.zeros((5, geom.H, geom.W))
            cnt_img = attacks.event_count_frame(we, geom) if len(we) else np.zeros((geom.H, geom.W))
            x = np.concatenate([vg, cnt_img[None] / max(1.0, cnt_img.max())]).astype(np.float32)
            cs = np.bincount((pe["t"].astype(np.int64) - lo) // 64, minlength=win_us // 64)[:win_us // 64]
            if frames is not None:
                tgt = frames[min(len(frames) - 1, int((hi - 10_000) // 1000))] / 255.0
            elif targets is not None and targets[si] is not None:
                tgt = targets[si][w]
            else:
                c = attacks.event_count_frame(pe, geom)
                tgt = c / max(1.0, c.max())
            out.append((x, cs.astype(np.float32), tgt.astype(np.float32), grp, box))
    return out


def build(torch, H, W, n_counts, median=None):
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

    class CountNet(nn.Module):
        """Control (f): the training-median frame plus a correction learned from the count series alone. The last
        layer starts at zero, so before training it IS control (c), and training can only add what the counts reveal.
        Bug #69: a plain MLP from ~300 counts to 307 200 pixels did not even learn the mean frame on Event-ReId
        (SSIM 0.29 vs 0.57 for the median), so every view was reported invalid."""
        def __init__(self):
            super().__init__()
            self.hidden = nn.Sequential(nn.Linear(n_counts, 256), nn.ReLU())
            self.out = nn.Linear(256, H * W)
            nn.init.zeros_(self.out.weight)
            nn.init.zeros_(self.out.bias)
            med = torch.zeros(H * W) if median is None else torch.as_tensor(median, dtype=torch.float32).reshape(-1)
            self.register_buffer("median", med)

        def forward(self, x):
            return (self.median + self.out(self.hidden(x))).clamp(0, 1)

    return UNet(), CountNet()


def holdout_split(groups, frac=0.2):
    """(fit, held-out) window indices: the last frac of the sorted training groups (at least one, none if there is
    only one group) are held out for model selection (bug #70)."""
    gs = sorted(set(groups))
    k = max(1, int(round(frac * len(gs)))) if len(gs) > 1 else 0
    held = set(gs[len(gs) - k:]) if k else set()
    idx = np.arange(len(groups))
    return idx[[g not in held for g in groups]], idx[[g in held for g in groups]]


def verdict(s_net, s_f, s_c, groups, seed=0):
    """(network - control (f), control (f) - control (c), valid, P1 pass or None).

    Control (f) sees strictly more than control (c) (the count series vs nothing), so a working (f) is never
    clearly worse than (c). If it is (upper CI bound of (f) - (c) below 0), (f) failed to train and
    network - control (f) measures that failure, not leakage (local QUICK 15 Nov 2026: (f) 0.015 against a network
    that output the mean frame, 0.639, on every view; TESTING bug #59). P1 is then None ("invalid")."""
    d = paired_bootstrap_diff(s_net, s_f, groups, n=1000, seed=seed)
    fc = paired_bootstrap_diff(s_f, s_c, groups, n=1000, seed=seed)
    valid = bool(fc[2] >= 0)
    return d, fc, valid, (bool(d[2] < 0.05) if valid else None)


def batch_size(px, cap=32, budget_px=2_500_000):
    """Images per batch. One training step of the U-Net at 480 x 640 needs 0.72-0.92 GB per image (measured on CPU,
    15 Nov 2026: 0.92 GB at batch 1, 0.72 GB at batch 4), so 32 images do not fit a 15 GB T4. 8 at 480 x 640
    (about 6 GB), 32 for N-MNIST / DVS Gesture."""
    return max(1, min(cap, budget_px // px))


def mask_of(box, H, W):
    """1 inside the scoring region (the whole frame when box is None)."""
    m = np.zeros((H, W), np.float32) if box is not None else np.ones((H, W), np.float32)
    if box is not None:
        m[box[0]:box[1], box[2]:box[3]] = 1
    return m


def _loss(torch, p, y, m):
    if m is None:
        return torch.nn.functional.l1_loss(p, y)
    return ((p - y).abs() * m).sum() / m.sum().clamp(min=1.0)


def masked_ssim(pred, tgt, mask=None):
    """SSIM inside the scoring region (the bounding box of mask; the whole frame without one), as N3/N4 score."""
    from skimage.metrics import structural_similarity
    if mask is not None and mask.any():
        r, c = np.flatnonzero(mask.any(1)), np.flatnonzero(mask.any(0))
        pred, tgt = pred[r[0]:r[-1] + 1, c[0]:c[-1] + 1], tgt[r[0]:r[-1] + 1, c[0]:c[-1] + 1]
    if min(pred.shape) < 7:
        return float(1.0 - np.abs(pred - tgt).mean())
    return float(structural_similarity(pred, tgt, data_range=1.0))


def train(torch, model, X, Y, epochs, dev, seed, bs=None, M=None, val=None, shape=None):
    """L1 loss, over the scoring region only when M (masks shaped like Y) is given: on Event-ReId ~95 % of a frame is
    empty, and a full-frame loss rewards a blank prediction (TESTING bug #58).

    val = (Xv, Yv, Mv or None): held-out training recordings. The weights with the best held-out score are kept,
    the untrained model (epoch 0) included. For control (f) epoch 0 IS control (c), so (f) cannot end below (c) on
    held-out data; without it the count correction overfit few recordings (bug #70). The score is the metric P1 uses,
    SSIM inside the scoring region, when `shape` (H, W) is given: selecting by L1 kept blurry weights that beat the
    median frame in L1 but lost to it in SSIM (Kaggle 16 Nov: control (f) 0.620 vs (c) 0.687; bug #72). The attack
    network gets the same rule, which can only make the attacker stronger."""
    import copy
    bs = bs or batch_size(Y[0].size)             # pixels per sample (flattened for the MLP control, too)
    torch.manual_seed(seed)
    model = model.to(dev)
    opt = torch.optim.Adam(model.parameters(), 1e-3)
    Xt, Yt = torch.from_numpy(X), torch.from_numpy(Y)
    Mt = torch.from_numpy(M) if M is not None else None

    def val_loss():
        """Lower is better: held-out L1, or minus mean held-out SSIM when shape is given."""
        Xv, Yv, Mv = val
        tot, n = 0.0, 0
        with torch.no_grad():
            for i in range(0, len(Xv), bs):
                p = model(torch.from_numpy(Xv[i:i + bs]).to(dev)).reshape(Yv[i:i + bs].shape)
                if shape is not None:
                    pn = p.cpu().numpy().reshape(-1, *shape)
                    yn = Yv[i:i + bs].reshape(-1, *shape)
                    mn = [None] * len(pn) if Mv is None else Mv[i:i + bs].reshape(-1, *shape)
                    tot -= sum(masked_ssim(a, b, m) for a, b, m in zip(pn, yn, mn))
                else:
                    m = None if Mv is None else torch.from_numpy(Mv[i:i + bs]).to(dev)
                    tot += float(_loss(torch, p, torch.from_numpy(Yv[i:i + bs]).to(dev), m)) * len(p)
                n += len(p)
        return tot / max(1, n)

    best = (val_loss(), copy.deepcopy(model.state_dict())) if val is not None else None
    for _ in range(epochs):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), bs):
            j = perm[i:i + bs]
            p = model(Xt[j].to(dev)).reshape(Yt[j].shape)
            loss = _loss(torch, p, Yt[j].to(dev), None if Mt is None else Mt[j].to(dev))
            opt.zero_grad()
            loss.backward()
            opt.step()
        if val is not None:
            v = val_loss()
            if v < best[0]:
                best = (v, copy.deepcopy(model.state_dict()))
    if best is not None:
        model.load_state_dict(best[1])
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
    ap.add_argument("--recon-repo", type=Path, default=None, help="rpg_e2vid checkout: plaintext E2VID targets")
    ap.add_argument("--recon-ckpt", nargs="*", default=[])
    a = ap.parse_args()
    try:
        import torch
    except ImportError:
        raise SystemExit("N4 needs PyTorch (Kaggle job: software/system/kaggle/kaggle_neuro.py); not run")
    from skimage.metrics import structural_similarity
    if a.quick:
        a.epochs, a.keys = 2, 2
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    lim = a.limit or (12 if a.quick else 400)
    samples = C.load_samples(a.dataset, a.data, limit=lim, seed=a.seed)
    win = int(a.win_ms * 1000)
    rois = C.load_rois(a.dataset, a.data, lim)
    if rois is None:
        samples = C.crop_samples(samples, win, min(a.max_windows, 4) if a.quick else a.max_windows)
    else:
        samples, rois = C.crop_samples(samples, win, min(a.max_windows, 4) if a.quick else a.max_windows, rois=rois)
    boxed = rois is not None and any(r is not None for r in rois)
    recon = None
    if a.recon_repo:
        from neuro_recon_attack import Learned
        recon = Learned(a.recon_repo, [c for c in a.recon_ckpt if c.startswith("e2vid=")])
    targets = plain_targets(samples, win, recon)
    target_kind = ("ground truth" if samples and samples[0][4] is not None else
                   "plaintext E2VID reconstruction" if recon else "plaintext count image (no E2VID: smoke run only)")
    groups = sorted({s[2] for s in samples})
    train_g = set(groups[: max(1, len(groups) // 2)])
    test_g = set(groups) - train_g
    assert not (train_g & test_g), "overlap guard: a recording group is in train and test"
    res, rows = {}, []
    for view in a.views:
        if view in ("Du 2021", "Zhang 2024") and not C.baseline("du2021" if view.startswith("Du") else "zhang2024"):
            continue
        W_ = windows_of(samples, view, a.T, win, a.keys, rois, targets)
        tr = [w for w in W_ if w[3] in train_g]
        te = [w for w in W_ if w[3] in test_g]
        if not tr or not te:
            continue
        H, Wd = tr[0][2].shape
        X, Y = np.stack([w[0] for w in tr]), np.stack([w[2] for w in tr])
        net, mlp = build(torch, H, Wd, len(tr[0][1]), median=np.median(Y, 0))
        M = np.stack([mask_of(w[4], H, Wd) for w in tr]) if boxed else None
        Xc = np.stack([w[1] for w in tr])
        fit, hold = holdout_split([w[3] for w in tr])          # by recording group, never by window
        sel = lambda A, i: None if A is None else A[i]          # noqa: E731
        net = train(torch, net, X[fit], Y[fit], a.epochs, dev, a.seed, M=sel(M, fit),
                    val=(X[hold], Y[hold], sel(M, hold)) if len(hold) else None, shape=(H, Wd))
        Yf, Mf = Y.reshape(len(Y), -1), None if M is None else M.reshape(len(M), -1)
        Xn = Xc / max(1.0, Xc.max())
        mlp = train(torch, mlp, Xn[fit], Yf[fit], a.epochs, dev, a.seed, M=sel(Mf, fit),
                    val=(Xn[hold], Yf[hold], sel(Mf, hold)) if len(hold) else None, shape=(H, Wd))
        pn = predict(torch, net, np.stack([w[0] for w in te]), (H, Wd), dev)
        pc = predict(torch, mlp, np.stack([w[1] for w in te]) / max(1.0, Xc.max()), (H, Wd), dev)
        sn = [structural_similarity(C.in_roi(p, w[4]), C.in_roi(w[2], w[4]), data_range=1.0) for p, w in zip(pn, te)]
        sc = [structural_similarity(C.in_roi(p, w[4]), C.in_roi(w[2], w[4]), data_range=1.0) for p, w in zip(pc, te)]
        med = np.median(Y, 0)                                            # control (c): training-median frame
        s_c = [structural_similarity(C.in_roi(med, w[4]), C.in_roi(w[2], w[4]), data_range=1.0) for w in te]
        g = [w[3] for w in te]
        d, fc, valid, p1 = verdict(sn, sc, s_c, g, a.seed)
        res[view] = {"ssim_net": cluster_bootstrap_ci(sn, g, n=1000, seed=a.seed),
                     "ssim_control_f": cluster_bootstrap_ci(sc, g, n=1000, seed=a.seed),
                     "ssim_control_c": cluster_bootstrap_ci(s_c, g, n=1000, seed=a.seed), "net_minus_control_f": d,
                     "control_f_minus_control_c": fc, "control_f_valid": valid,
                     "train_windows": len(tr), "test_windows": len(te), "test_clusters": n_clusters(g),
                     "P1_pass": p1}
        rows.append((view, res[view]["ssim_net"], res[view]["ssim_control_f"], res[view]["ssim_control_c"], d,
                     ("yes" if d[2] < 0.05 else "no") if valid else "invalid: control (f) < control (c)",
                     n_clusters(g)))
    data = {"results": res,
            "scored": C.SCORED[boxed], "target": target_kind,
            "meta": C.meta(a, dataset=a.dataset, synthetic=a.data is None, n_keys=a.keys, device=dev,
                           target=target_kind,
                           ci="paired cluster bootstrap 95 %, 1000 resamples")}
    md = ["# N4 learned attack" + (" (synthetic smoke data)" if a.data is None else ""), "",
          f"Target: {target_kind}. Scored {data['scored']}.", "",
          "Validity: control (f) (count series) must not be clearly worse than control (c) (median frame), "
          "else P1 is reported as invalid.", "",
          C.table(["view", "SSIM network", "SSIM control (f)", "SSIM control (c)", "network - control (f)", "P1 pass",
                   "test clusters"], rows)]
    C.write("n4", "learned_attack", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
