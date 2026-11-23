"""N6: is task utility kept with the key and lost without it?

Usage (Kaggle GPU; needs PyTorch):
    python experiments/neuro_task_accuracy.py --dataset nmnist --data <root> [--seeds 0 1 2] [--epochs 20] [--quick]

Method (DESIGN §8.2 N6). Official train/test files (Tonic 1.7.0 loaders in neuro.datasets).
  * Decryption is exact, so "accuracy on decrypted data" is not a result: the script decrypts every test sample
    through neuro.receiver.Decryptor at V3 and asserts event equality, reporting the count in one sentence.
  * Model: a CNN on ON / OFF count frames, cut into BINS time bins per dataset (DVS Gesture: 8, because a single
    time-integrated frame cannot tell clockwise from counter-clockwise arm rotation); two conv-BN-ReLU blocks of two
    layers, dropout, AdamW with a one-cycle schedule. The first CNN (two plain conv layers pooled to 4 x 4, constant
    learning rate) reached 0.974 on N-MNIST, under the 0.98 gate, so no ciphertext row was produced (Kaggle part C,
    16 Nov 2026; TESTING bug #74). The SNN of DESIGN §8.2 is not implemented (stated in the table).
  * Gate (fixed in §8.2): clean test accuracy >= 98 % (N-MNIST) / >= 90 % (DVS Gesture) before any ciphertext
    row is reported; synthetic data have no gate.
  * Rows per view (V1, V2, V3, V4 = empty input, Du 2021, Zhang 2024): (i) trained on clear, tested on
    ciphertext; (ii) trained and tested on ciphertext with a fresh key per sample. Measure fixed in advance:
    accuracy (ii) - chance, with a Student-t CI over >= 3 seeds (neuro.stats.mean_ci).
  * Zhang anchor (BASELINES.md §2.2): their Table 1 gives 0.06-0.14 on N-MNIST for Zhang ciphertext.
  * Cost (TESTING bug #62): sealing is Python and ~0.7 s (N-MNIST) / 20-50 s (DVS Gesture) per sample for the six
    views, so the clean model uses the whole training set (frames only) but the ciphertext rows and the decryption
    check use a fixed seeded subset (--ct-train / --ct-test, default N-MNIST 4000 / 2000, DVS Gesture 300 / all
    264), sealed in parallel over --workers processes before PyTorch touches the GPU. The decryption check runs on
    --check (default 64) of the ciphertext test samples (bug #65: ~26 s per DVS Gesture recording).
Writes sim_out/neuro/n6/task_accuracy.{json,md}.
"""
import argparse
import multiprocessing as mp
import os

import numpy as np

import neuro_common as C
from neuro import evt2, keys, receiver
from neuro.stats import mean_ci

GATE = {"nmnist": 0.98, "dvsgesture": 0.90}
# Model of each dataset (TESTING bug #75). N-MNIST: the bug #74 CNN, 0.991 on Kaggle (16 Nov). DVS Gesture: the bug #74
# CNN on 8 bins reached 0.732 (seeds 0.62 / 0.73 / 0.85: undertrained, 20 epochs = 340 steps on 1077 samples), so the
# DVS model is chosen by experiments/neuro_n6_select.py among CANDIDATES on users held out of the TRAINING split
# (never on the test split) and copied here by hand with the selection table it came from.
CONFIG = {"nmnist": dict(nb=1, arch="small", epochs=20, shift=0, down=1),
          "dvsgesture": dict(nb=8, arch="small", epochs=20, shift=0, down=1)}
DEFAULT_CONFIG = CONFIG["nmnist"]
CANDIDATES = {   # fixed before the selection run (22 Nov 2026)
    "A_bug74": dict(nb=8, arch="small", epochs=20, shift=0, down=1),
    "B_deep16": dict(nb=16, arch="deep", epochs=60, shift=8, down=1),
    "C_deep16_64px": dict(nb=16, arch="deep", epochs=100, shift=4, down=2),
    # Round 2, fixed 22 Nov 2026 after round 1 (A-C) reached at most 0.785 on the held-out users: an ImageNet-
    # pretrained ResNet-18, the backbone of the event-representation literature (EST, Gehrig et al. 2019).
    # D: 3 channels ON count, OFF count, time of the last event per pixel (keeps motion direction);
    # E / F: 16 time bins through a first convolution initialised from the mean of the pretrained RGB filters.
    "D_rn18_ts3": dict(nb=1, feat="ts3", arch="resnet18", epochs=40, shift=8, down=1),
    "E_rn18_bins16": dict(nb=16, arch="resnet18", epochs=40, shift=8, down=1),
    "F_rn18_bins16_64px": dict(nb=16, arch="resnet18", epochs=60, shift=4, down=2),
    # Round 3, fixed 22 Nov 2026 after round 2 (best 0.762): not a new design but the published DVS Gesture recipe of
    # AnonyNoise (Bendig et al., WACV 2025, Sec. 4.2 and Table 5), whose target network reached 92.4 % on the test
    # split: ImageNet ResNet-50, 2T = 10 histogram channels (T = 5), AdamW 1e-4 with cosine decay, batch 32,
    # 200 epochs, random crop after zero padding by 1/12 of the size (shift 10 of 128); their 15 degree rotation is
    # not used.
    "G_anonynoise_rn50": dict(nb=5, arch="resnet50", epochs=200, shift=10, down=1, lr=1e-4, bs=32),
}
# Extra N6 models (22 Nov 2026), run with --config, each against the gate of its dataset:
#   N_bins8 / N_ts3: does the verdict on a view depend on the input representation? Zhang 2024 scrambles time and
#     polarity but leaves every real event in place (BASELINES §2.3), so a count image reads it (0.966) where the
#     time-binned classifiers of its Table 1 did not. Same CNN, 8 time bins / last-event time instead of one frame.
#   N_snn10: the SNN of DESIGN §8.2: leaky integrate-and-fire convolutional network over 10 time bins.
EXTRA = {
    "N_bins8": dict(nb=8, arch="small", epochs=20, shift=0, down=1),
    "N_ts3": dict(nb=1, feat="ts3", arch="small", epochs=20, shift=0, down=1),
    "N_snn10": dict(nb=10, arch="snn", epochs=20, shift=0, down=1),
    # N_bins8 (the strongest keyless attacker of 22 Nov: 0.40 on V3) against V3 with N5's padding policies
    "N_bins8_pad": dict(nb=8, arch="small", epochs=20, shift=0, down=1),
    # N_bins8 against V2 and the ideal-permutation control (23 Nov): equal accuracy = no leak beyond the ideal cipher
    "N_bins8_ideal": dict(nb=8, arch="small", epochs=20, shift=0, down=1),
}
ROUNDS = {"A_bug74": 1, "B_deep16": 1, "C_deep16_64px": 1, "D_rn18_ts3": 2, "E_rn18_bins16": 2,
          "F_rn18_bins16_64px": 2, "G_anonynoise_rn50": 3}
# The decryption check seals and decrypts a sample again: ~26 s per DVS Gesture recording (profiled 16 Nov), i.e. ~2 h
# for all 264 test recordings on top of the ~4.6 h of sealing. It shows exactness, not accuracy, so it runs on a fixed
# seeded subset of the ciphertext test samples (TESTING bug #65).
CHECK_N = 64
CT_DEFAULT = {"nmnist": (4000, 2000), "dvsgesture": (300, 264)}     # ciphertext subset (train, test), full run
CT_QUICK = {"nmnist": (40, 40), "dvsgesture": (16, 16)}   # QUICK: DVS Gesture costs 20-50 s per recording to seal


def _seal_one(job):
    ev, geom, view, key, cfg = job
    return features_cfg(view_events(ev, geom, view, key), geom, cfg)


def _check_one(job):
    sample, i = job
    return decrypt_check([sample], base=i)


def _pool(workers):
    """Worker pool for sealing. Sealing now runs after the GPU gate (bug #75), so CUDA is initialised in this process
    and plain fork is unsafe: the forkserver starts workers from a fresh interpreter; jobs carry their samples."""
    return mp.get_context("forkserver").Pool(workers)


def sealed_frames(samples, view, keys, workers, cfg):
    """features(view_events(...)) of every sample, in parallel over `workers` processes."""
    jobs = [(s[0], s[3], view, keys[j], cfg) for j, s in enumerate(samples)]
    if workers <= 1 or len(jobs) < 8:
        return np.stack([_seal_one(j) for j in jobs])
    with _pool(workers) as pool:
        return np.stack(pool.map(_seal_one, jobs, chunksize=max(1, len(jobs) // (8 * workers))))


def subset(samples, n, seed):
    """A fixed seeded subset of n samples (all when n >= len), in their original order, with their indices."""
    if n is None or n >= len(samples):
        return list(range(len(samples)))
    return sorted(np.random.default_rng(seed).choice(len(samples), n, replace=False).tolist())


def frame(ev, geom, size=None):
    img = np.zeros((2, geom.H, geom.W), np.float32)
    if len(ev):
        np.add.at(img, (ev["p"].astype(int), ev["y"].astype(int), ev["x"].astype(int)), 1.0)
    return img / max(1.0, img.max())


def bins(ev, geom, nb=10):
    out = np.zeros((nb, 2, geom.H, geom.W), np.float32)
    if len(ev):
        t = ev["t"].astype(np.int64)
        b = np.minimum(nb - 1, (t - t.min()) * nb // max(1, int(t.max() - t.min()) + 1))
        np.add.at(out, (b, ev["p"].astype(int), ev["y"].astype(int), ev["x"].astype(int)), 1.0)
    return out


def ts3(ev, geom):
    """(3, H, W): ON count, OFF count (each scaled by its maximum) and the time of each pixel's last event, scaled
    to [0, 1] over the sample (0 where no event): one image that still shows where motion went last."""
    out = np.zeros((3, geom.H, geom.W), np.float32)
    if len(ev):
        p, y, x = ev["p"].astype(int), ev["y"].astype(int), ev["x"].astype(int)
        np.add.at(out, (p, y, x), 1.0)
        out[:2] /= max(1.0, float(out[:2].max()))
        t = ev["t"].astype(np.float64)
        tn = (t - t.min()) / max(1.0, t.max() - t.min())
        last = np.zeros((geom.H, geom.W))
        np.maximum.at(last, (y, x), tn + 1e-9)       # events are time-ordered, max = last; +eps marks "seen"
        out[2] = np.clip(last, 0.0, 1.0).astype(np.float32)
    return out


def features_cfg(ev, geom, cfg):
    """features() of a CONFIG / CANDIDATES entry."""
    if cfg.get("feat") == "ts3":
        return ts3(ev, geom)
    return features(ev, geom, cfg["nb"], cfg["down"])


def features(ev, geom, nb=1, down=1):
    """CNN input (2 nb, H / down, W / down): ON / OFF counts in nb equal time bins of the sample, summed over
    down x down pixel blocks, scaled by the sample's maximum. nb = down = 1 is frame()."""
    if nb == 1 and down == 1:
        return frame(ev, geom)
    x = bins(ev, geom, nb).reshape(2 * nb, geom.H, geom.W)
    if down > 1:
        x = x.reshape(2 * nb, geom.H // down, down, geom.W // down, down).sum((2, 4))
    return x / max(1.0, float(x.max()))


def ideal_view(ev, geom, k, T=1024):
    """V2 with an ideal cipher: in every packet window of T µs, (x, y) mapped by a fresh uniformly random
    permutation of all W * H addresses (numpy, keyed by k and the window); polarity and time kept, as at V2.
    The control for "does the eight-round network leak more than an ideal permutation to this attacker"."""
    out = ev.copy()
    if not len(ev):
        return out
    W, H = geom.W, geom.H
    win = ev["t"].astype(np.int64) // T
    addr = ev["y"].astype(np.int64) * W + ev["x"].astype(np.int64)
    new = np.empty_like(addr)
    for w in np.unique(win):
        m = win == w
        perm = np.random.default_rng([k, int(w), 0x1DEA]).permutation(W * H)
        new[m] = perm[addr[m]]
    out["y"], out["x"] = np.divmod(new, W)
    return out


def view_events(ev, geom, view, k, T=1024):
    if view == "clear":
        return ev
    if view == "ideal":                                     # control (23 Nov): what V2 would be with an ideal cipher
        return ideal_view(ev, geom, k, T)
    if view.startswith("V") and " + pad " in view:          # e.g. "V3 + pad floor 16" (N5's policies, DESIGN §5)
        pol = C.pad_policies()[view.split(" + pad ")[1]]
        return C.keyless_events(C.protect(ev, geom, int(view[1]), T, pad=pol, key_index=k))
    if view.startswith("V"):
        return C.keyless_events(C.protect(ev, geom, int(view[1]), T, key_index=k))
    if view == "Du 2021":
        du = C.baseline("du2021")
        return du.encrypt(ev, geom.W, geom.H, du.DuKey.from_seed(C.master(k)))
    e, _ = C.baseline("zhang2024").encrypt(ev, geom.W, geom.H, C.master(k))
    return e


def decrypt_check(samples, T=1024, base=0):
    """Count test samples whose V3 packets decrypt to event-equal streams."""
    ok = 0
    for i, (ev, _, _, geom, _) in enumerate(samples, start=base):
        pk = C.protect(ev, geom, 3, T, key_index=i)
        prof = receiver.Profile(frozenset({(3, 6, None, None)}), geom, T, R_max_words_per_us=64.0)
        d = receiver.Decryptor({(C.CAM, C.BOOT): C.master(i)}, prof)
        words = [r.words for r in (d.accept(p, now=j * 1e-3) for j, p in enumerate(pk)) if r.status == "ok"]
        dec = np.concatenate(words) if words else np.zeros(0, np.uint32)
        ok += evt2.event_equal(dec, evt2.encode(ev, T))
    return ok


def resnet18(torch, classes, in_ch, pretrained=True, depth=18):
    """torchvision ResNet-18 (or -50 with depth=50; ImageNet weights when pretrained) with a new classifier; for
    in_ch != 3 the first convolution gets in_ch input channels, each initialised with the mean of the pretrained RGB
    filters x 3 / in_ch."""
    import torchvision
    if depth == 50:
        w = torchvision.models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
        m = torchvision.models.resnet50(weights=w)
    else:
        w = torchvision.models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        m = torchvision.models.resnet18(weights=w)
    if in_ch != 3:
        old = m.conv1
        m.conv1 = torch.nn.Conv2d(in_ch, 64, 7, 2, 3, bias=False)
        with torch.no_grad():
            m.conv1.weight.copy_(old.weight.mean(1, keepdim=True).repeat(1, in_ch, 1, 1) * 3.0 / in_ch)
    m.fc = torch.nn.Linear(m.fc.in_features, classes)
    return m


PRETRAINED = True          # tests set False (no download)


def snn(torch, classes, in_ch, beta=0.9):
    """Convolutional SNN: the input (2 nb, H, W) is nb time steps of ON/OFF counts; two conv-BN layers with leaky
    integrate-and-fire neurons (membrane u <- beta u + I, spike when u >= 1, reset by subtraction; surrogate gradient
    of a fast sigmoid), then a linear LIF readout whose membrane, summed over the steps, is the logit."""
    nn = torch.nn

    class Spike(torch.autograd.Function):
        @staticmethod
        def forward(ctx, u):
            ctx.save_for_backward(u)
            return (u >= 1.0).float()

        @staticmethod
        def backward(ctx, g):
            (u,) = ctx.saved_tensors
            return g / (1.0 + 10.0 * (u - 1.0).abs()) ** 2

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.steps = in_ch // 2
            self.c1 = nn.Sequential(nn.Conv2d(2, 32, 3, padding=1), nn.BatchNorm2d(32), nn.MaxPool2d(2))
            self.c2 = nn.Sequential(nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.MaxPool2d(2))
            self.pool = nn.AdaptiveAvgPool2d(4)
            self.fc = nn.Linear(64 * 16, classes)

        def forward(self, x):
            n, _, h, w = x.shape
            x = x.view(n, self.steps, 2, h, w)
            u1 = u2 = u3 = 0.0
            out = 0.0
            for t in range(self.steps):
                u1 = beta * u1 + self.c1(x[:, t])
                s1 = Spike.apply(u1)
                u1 = u1 - s1
                u2 = beta * u2 + self.c2(s1)
                s2 = Spike.apply(u2)
                u2 = u2 - s2
                u3 = beta * u3 + self.fc(self.pool(s2).flatten(1))
                out = out + u3
            return out / self.steps
    return Net()


def cnn(torch, classes, in_ch=2, arch="small"):
    """Two blocks of two conv-BN-ReLU layers (32, 64 channels), each max-pooled, then adaptive pooling to 8 x 8,
    dropout and two linear layers (bug #74: the previous two-layer CNN stayed under the N-MNIST gate)."""
    nn = torch.nn

    def blk(i, o):
        return [nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU()]
    if arch == "snn":
        return snn(torch, classes, in_ch)
    if arch == "resnet18":
        return resnet18(torch, classes, in_ch, PRETRAINED)
    if arch == "resnet50":
        return resnet18(torch, classes, in_ch, PRETRAINED, depth=50)
    if arch == "deep":           # four conv-BN-ReLU-pool stages (32, 64, 128, 128), as the DVS Gesture CNNs of the
        layers, c = [], in_ch    # SpikingJelly examples; global pooling keeps it valid for any input size
        for o in (32, 64, 128, 128):
            layers += blk(c, o) + [nn.MaxPool2d(2)]
            c = o
        return nn.Sequential(*layers, nn.AdaptiveAvgPool2d(4), nn.Flatten(), nn.Dropout(0.5),
                             nn.Linear(128 * 16, 256), nn.ReLU(), nn.Dropout(0.5), nn.Linear(256, classes))
    return nn.Sequential(*blk(in_ch, 32), *blk(32, 32), nn.MaxPool2d(2), *blk(32, 64), *blk(64, 64), nn.MaxPool2d(2),
                         nn.AdaptiveAvgPool2d(8), nn.Dropout(0.25), nn.Flatten(), nn.Linear(64 * 64, 256), nn.ReLU(),
                         nn.Dropout(0.5), nn.Linear(256, classes))


def shift_batch(torch, x, s, gen):
    """Random translation of each sample by up to s pixels in x and y, with zero fill (data augmentation)."""
    if s <= 0:
        return x
    n, _, h, w = x.shape
    xp = torch.nn.functional.pad(x, (s, s, s, s))
    d = torch.randint(0, 2 * s + 1, (n, 2), generator=gen)
    return torch.stack([xp[k, :, d[k, 0]:d[k, 0] + h, d[k, 1]:d[k, 1] + w] for k in range(n)])


def fit_eval(torch, Xtr, ytr, Xte, yte, classes, epochs, seed, dev, bs=64, arch="small", shift=0, lr=None):
    """Train a fresh cnn() with AdamW, return (model, test accuracy). lr None: one-cycle learning rate (peak 3e-3);
    lr given: AdamW at lr with cosine decay to 0 (the fine-tuning recipe of AnonyNoise, Bendig et al. WACV 2025)."""
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    m = cnn(torch, classes, Xtr.shape[1], arch).to(dev)
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr).long()
    steps = max(1, epochs * ((len(Xt) + bs - 1) // bs))
    if lr is None:
        opt = torch.optim.AdamW(m.parameters(), 1e-3)
        sch = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=steps)
    else:
        opt = torch.optim.AdamW(m.parameters(), lr)
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    for _ in range(epochs):
        m.train()
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), bs):
            j = perm[i:i + bs]
            loss = torch.nn.functional.cross_entropy(m(shift_batch(torch, Xt[j], shift, gen).to(dev)), yt[j].to(dev))
            opt.zero_grad()
            loss.backward()
            opt.step()
            sch.step()
    return m, evaluate(torch, m, Xte, yte, dev)


def fit_args(cfg):
    """fit_eval keyword arguments of a CONFIG / CANDIDATES / EXTRA entry (lr and bs only where the entry sets them)."""
    return {k: cfg[k] for k in ("arch", "shift", "lr", "bs") if k in cfg}


def evaluate(torch, m, X, y, dev):
    m.eval()                                             # BatchNorm running statistics, no dropout
    with torch.no_grad():
        pred = torch.cat([m(torch.from_numpy(X[i:i + 256]).to(dev)).argmax(1).cpu() for i in range(0, len(X), 256)])
    return float((pred.numpy() == y).mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, help="override the dataset's CONFIG epochs")
    ap.add_argument("--config", help="model of EXTRA or CANDIDATES instead of the dataset's CONFIG (extra rows)")
    ap.add_argument("--views", nargs="+", default=["V1", "V2", "V3", "V4", "Du 2021", "Zhang 2024"])
    ap.add_argument("--ct-train", type=int, help="training samples sealed for row (ii) (default by dataset)")
    ap.add_argument("--ct-test", type=int, help="test samples sealed for rows (i), (ii) and the decryption check")
    ap.add_argument("--check", type=int, default=CHECK_N,
                    help="ciphertext test samples whose V3 decryption is checked (fixed seeded subset)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1, help="processes that seal in parallel")
    a = ap.parse_args()
    try:
        import torch
    except ImportError:
        raise SystemExit("N6 needs PyTorch (Kaggle job: software/system/kaggle/kaggle_neuro.py); not run")
    if a.quick:
        a.seeds = [0]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if a.data is None:
        allS = C.synthetic_samples(a.limit or 48, a.seed)
        groups = sorted({s[2] for s in allS})
        tr_s = [s for s in allS if s[2] in groups[: len(groups) // 2]]
        te_s = [s for s in allS if s[2] not in groups[: len(groups) // 2]]
    else:
        tr_s = C.load_samples(a.dataset, a.data, "train", a.limit)
        te_s = C.load_samples(a.dataset, a.data, "test", a.limit)
    geom = tr_s[0][3]
    classes = int(max(s[1] for s in tr_s + te_s)) + 1
    ytr = np.array([s[1] for s in tr_s])
    yte = np.array([s[1] for s in te_s])
    if a.config and a.config not in {**EXTRA, **CANDIDATES}:
        raise SystemExit(f"--config {a.config}: not in EXTRA or CANDIDATES")
    cfg = dict({**EXTRA, **CANDIDATES}[a.config] if a.config else CONFIG.get(a.dataset, DEFAULT_CONFIG))
    if a.epochs:
        cfg["epochs"] = a.epochs
    if a.quick:
        cfg["epochs"] = 2
    n_tr, n_te = CT_QUICK.get(a.dataset, (40, 40)) if a.quick else CT_DEFAULT.get(a.dataset, (None, None))
    n_tr, n_te = a.ct_train or n_tr, a.ct_test or n_te
    i_tr, i_te = subset(tr_s, n_tr, a.seed), subset(te_s, n_te, a.seed + 1)
    ct_tr, ct_te = [tr_s[i] for i in i_tr], [te_s[i] for i in i_te]
    ytr_ct, yte_ct = ytr[i_tr], yte[i_te]
    fit = fit_args(cfg)
    # 1. Gate first (bug #75): the clean model needs no sealing, and a failed gate ends the run here, in minutes,
    #    instead of after hours of sealing whose rows the gate would discard.
    Xtr = np.stack([features_cfg(s[0], geom, cfg) for s in tr_s])
    Xte = np.stack([features_cfg(s[0], geom, cfg) for s in te_s])
    clean, models = [], []
    for sd in a.seeds:
        m, acc = fit_eval(torch, Xtr, ytr, Xte, yte, classes, cfg["epochs"], sd, dev, **fit)
        clean.append(acc)
        models.append(m)
        print(f"clean seed {sd}: {acc:.4f}", flush=True)
    gate_thr = GATE.get(a.dataset)
    gate = gate_thr is None or np.mean(clean) >= gate_thr
    chance = 1 / classes
    res, rows = {"clean": mean_ci(clean)}, [("clear (clean)", mean_ci(clean), "-", "-")]
    n_equal, i_ck = 0, []
    if gate:
        # 2. Reference for row (ii): the same model trained on the CLEAR events of the ciphertext training subset,
        #    so (ii) is compared with a model that saw as many samples (bug #75).
        ref = [fit_eval(torch, Xtr[i_tr], ytr_ct, Xte[i_te], yte_ct, classes, cfg["epochs"], sd, dev, **fit)[1]
               for sd in a.seeds]
        res["clear_subset"] = mean_ci(ref)
        rows.append(("clear, trained on the subset", "-", mean_ci(ref), mean_ci(np.asarray(ref) - chance)))
        # 3. Seal (keys: training sample i -> key i, test sample i -> key 10 000 + i) and check decryption.
        for view in a.views:
            if view in ("Du 2021", "Zhang 2024") and not C.baseline("du2021" if view.startswith("Du") else "zhang2024"):
                continue
            Ctr = sealed_frames(ct_tr, view, i_tr, a.workers, cfg)
            Cte = sealed_frames(ct_te, view, [10_000 + i for i in i_te], a.workers, cfg)
            print(f"sealed {view}", flush=True)
            r_i = [evaluate(torch, m, Cte, yte_ct, dev) for m in models]
            r_ii = [fit_eval(torch, Ctr, ytr_ct, Cte, yte_ct, classes, cfg["epochs"], sd, dev, **fit)[1]
                    for sd in a.seeds]
            d = mean_ci(np.asarray(r_ii) - chance)
            res[view] = {"i_clear_trained": mean_ci(r_i), "ii_cipher_trained": mean_ci(r_ii), "ii_minus_chance": d}
            rows.append((view, mean_ci(r_i), mean_ci(r_ii), d))
        i_ck = subset(ct_te, a.check, a.seed + 2)        # positions in ct_te; key of position k is k
        jobs = [(ct_te[k], k) for k in i_ck]
        if a.workers > 1 and len(jobs) >= 8:
            with _pool(a.workers) as pool:
                n_equal = int(sum(pool.map(_check_one, jobs)))
        else:
            n_equal = int(sum(_check_one(j) for j in jobs))
    snn = ("this table is the SNN of DESIGN §8.2" if cfg["arch"] == "snn" else
           "SNN rows: run with --config N_snn10")
    data = {"results": res, "gate": {"threshold": gate_thr, "clean_mean": float(np.mean(clean)), "passes": bool(gate)},
            "decrypted_event_equal": f"{n_equal} of {len(i_ck)}" if gate else "not run (gate failed)",
            "ciphertext_subset": {"train": len(ct_tr), "test": len(ct_te), "of_train": len(tr_s), "of_test": len(te_s),
                                  "seed": a.seed},
            "chance": chance, "snn": snn,
            "meta": C.meta(a, dataset=a.dataset, synthetic=a.data is None, device=dev, seeds=a.seeds,
                           ci="Student-t 95 % over seeds", n_keys="fresh key per sample", config=cfg,
                           config_name=a.config or "CONFIG")}
    md = ["# N6 task accuracy" + (" (synthetic smoke data)" if a.data is None else ""), "",
          f"Clean model ({cfg}): {len(tr_s)} training / {len(te_s)} test samples; ciphertext rows and decryption "
          f"check: a fixed subset of {len(ct_tr)} / {len(ct_te)}, with a clear reference trained on the same subset. "
          f"Decryption check: {data['decrypted_event_equal']} test samples decrypt event-equal (V3). "
          f"Gate: clean {np.mean(clean):.3f} vs {gate_thr} -> {'pass' if gate else 'FAIL: no ciphertext rows'}. "
          f"Chance {chance:.3f}. {snn}.", "",
          C.table(["view", "(i) clear-trained on cipher", "(ii) cipher-trained", "(ii) - chance"], rows)]
    C.write("n6", "task_accuracy", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
