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
BINS = {"dvsgesture": 8}             # time bins of the CNN input (default 1: one count frame)
# The decryption check seals and decrypts a sample again: ~26 s per DVS Gesture recording (profiled 16 Nov), i.e. ~2 h
# for all 264 test recordings on top of the ~4.6 h of sealing. It shows exactness, not accuracy, so it runs on a fixed
# seeded subset of the ciphertext test samples (TESTING bug #65).
CHECK_N = 64
CT_DEFAULT = {"nmnist": (4000, 2000), "dvsgesture": (300, 264)}     # ciphertext subset (train, test), full run
CT_QUICK = {"nmnist": (40, 40), "dvsgesture": (16, 16)}   # QUICK: DVS Gesture costs 20-50 s per recording to seal
_NB = 1                              # time bins of features(), set by main() before sealing
_POOL = None                         # samples visible to the forked sealing workers (no pickling of event arrays)


def _seal_one(job):
    i, view, key = job
    ev, geom = _POOL[i][0], _POOL[i][3]
    return features(view_events(ev, geom, view, key), geom, _NB)


def _check_one(i):
    return decrypt_check([_POOL[i]], base=i)


def sealed_frames(samples, view, keys, workers):
    """features(view_events(...)) of every sample, in parallel over `workers` forked processes."""
    global _POOL
    _POOL = samples
    jobs = [(j, view, keys[j]) for j in range(len(samples))]
    if workers <= 1 or len(jobs) < 8:
        return np.stack([_seal_one(j) for j in jobs])
    with mp.get_context("fork").Pool(workers) as pool:
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


def features(ev, geom, nb=1):
    """CNN input (2 nb, H, W): ON / OFF counts in nb equal time bins of the sample, scaled by the sample's maximum.
    nb = 1 is frame()."""
    if nb == 1:
        return frame(ev, geom)
    x = bins(ev, geom, nb).reshape(2 * nb, geom.H, geom.W)
    return x / max(1.0, float(x.max()))


def view_events(ev, geom, view, k, T=1024):
    if view == "clear":
        return ev
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


def cnn(torch, classes, in_ch=2):
    """Two blocks of two conv-BN-ReLU layers (32, 64 channels), each max-pooled, then adaptive pooling to 8 x 8,
    dropout and two linear layers (bug #74: the previous two-layer CNN stayed under the N-MNIST gate)."""
    nn = torch.nn

    def blk(i, o):
        return [nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU()]
    return nn.Sequential(*blk(in_ch, 32), *blk(32, 32), nn.MaxPool2d(2), *blk(32, 64), *blk(64, 64), nn.MaxPool2d(2),
                         nn.AdaptiveAvgPool2d(8), nn.Dropout(0.25), nn.Flatten(), nn.Linear(64 * 64, 256), nn.ReLU(),
                         nn.Dropout(0.5), nn.Linear(256, classes))


def fit_eval(torch, Xtr, ytr, Xte, yte, classes, epochs, seed, dev, bs=64):
    """Train a fresh cnn() with AdamW and a one-cycle learning rate (peak 3e-3), return (model, test accuracy)."""
    torch.manual_seed(seed)
    m = cnn(torch, classes, Xtr.shape[1]).to(dev)
    opt = torch.optim.AdamW(m.parameters(), 1e-3)
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr).long()
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=max(1, epochs * ((len(Xt) + bs - 1) // bs)))
    for _ in range(epochs):
        m.train()
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), bs):
            j = perm[i:i + bs]
            loss = torch.nn.functional.cross_entropy(m(Xt[j].to(dev)), yt[j].to(dev))
            opt.zero_grad()
            loss.backward()
            opt.step()
            sch.step()
    return m, evaluate(torch, m, Xte, yte, dev)


def evaluate(torch, m, X, y, dev):
    m.eval()                                             # BatchNorm running statistics, no dropout
    with torch.no_grad():
        pred = torch.cat([m(torch.from_numpy(X[i:i + 256]).to(dev)).argmax(1).cpu() for i in range(0, len(X), 256)])
    return float((pred.numpy() == y).mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=20)
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
        a.seeds, a.epochs = [0], 2
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
    n_tr, n_te = CT_QUICK.get(a.dataset, (40, 40)) if a.quick else CT_DEFAULT.get(a.dataset, (None, None))
    n_tr, n_te = a.ct_train or n_tr, a.ct_test or n_te
    i_tr, i_te = subset(tr_s, n_tr, a.seed), subset(te_s, n_te, a.seed + 1)
    ct_tr, ct_te = [tr_s[i] for i in i_tr], [te_s[i] for i in i_te]
    ytr_ct, yte_ct = ytr[i_tr], yte[i_te]
    # Sealing first, in forked workers, while PyTorch has not initialised CUDA in this process. Keys: training
    # sample i -> key i, test sample i -> key 10 000 + i (fresh key per sample, as before the subset).
    global _NB
    _NB = BINS.get(a.dataset, 1)
    sealed = {}
    for view in a.views:
        if view in ("Du 2021", "Zhang 2024") and not C.baseline("du2021" if view.startswith("Du") else "zhang2024"):
            continue
        sealed[view] = (sealed_frames(ct_tr, view, i_tr, a.workers),
                        sealed_frames(ct_te, view, [10_000 + i for i in i_te], a.workers))
    global _POOL
    _POOL = ct_te
    i_ck = subset(ct_te, a.check, a.seed + 2)            # positions in ct_te; key of position k is k (as before)
    if a.workers > 1 and len(i_ck) >= 8:
        with mp.get_context("fork").Pool(a.workers) as pool:
            n_equal = int(sum(pool.map(_check_one, i_ck)))
    else:
        n_equal = int(sum(_check_one(k) for k in i_ck))
    Xtr = np.stack([features(s[0], geom, _NB) for s in tr_s])
    Xte = np.stack([features(s[0], geom, _NB) for s in te_s])
    clean, models = [], []
    for sd in a.seeds:
        m, acc = fit_eval(torch, Xtr, ytr, Xte, yte, classes, a.epochs, sd, dev)
        clean.append(acc)
        models.append(m)
    gate_thr = GATE.get(a.dataset)
    gate = gate_thr is None or np.mean(clean) >= gate_thr
    chance = 1 / classes
    res, rows = {"clean": mean_ci(clean)}, [("clear (clean)", mean_ci(clean), "-", "-")]
    if gate:
        for view, (Ctr, Cte) in sealed.items():
            r_i = [evaluate(torch, m, Cte, yte_ct, dev) for m in models]
            r_ii = [fit_eval(torch, Ctr, ytr_ct, Cte, yte_ct, classes, a.epochs, sd, dev)[1] for sd in a.seeds]
            d = mean_ci(np.asarray(r_ii) - chance)
            res[view] = {"i_clear_trained": mean_ci(r_i), "ii_cipher_trained": mean_ci(r_ii), "ii_minus_chance": d}
            rows.append((view, mean_ci(r_i), mean_ci(r_ii), d))
    snn = "SNN rows not run: the SNN of DESIGN §8.2 is not implemented, CNN only"
    data = {"results": res, "gate": {"threshold": gate_thr, "clean_mean": float(np.mean(clean)), "passes": bool(gate)},
            "decrypted_event_equal": f"{n_equal} of {len(i_ck)}",
            "ciphertext_subset": {"train": len(ct_tr), "test": len(ct_te), "of_train": len(tr_s), "of_test": len(te_s),
                                  "seed": a.seed},
            "chance": chance, "snn": snn,
            "meta": C.meta(a, dataset=a.dataset, synthetic=a.data is None, device=dev, seeds=a.seeds,
                           ci="Student-t 95 % over seeds", n_keys="fresh key per sample",
                           time_bins=_NB, epochs=a.epochs)}
    md = ["# N6 task accuracy" + (" (synthetic smoke data)" if a.data is None else ""), "",
          f"Clean model: {len(tr_s)} training / {len(te_s)} test samples; ciphertext rows and decryption check: a "
          f"fixed subset of {len(ct_tr)} / {len(ct_te)}. "
          f"Decryption check: {data['decrypted_event_equal']} test samples decrypt event-equal (V3). "
          f"Gate: clean {np.mean(clean):.3f} vs {gate_thr} -> {'pass' if gate else 'FAIL: no ciphertext rows'}. "
          f"Chance {chance:.3f}. {snn}.", "",
          C.table(["view", "(i) clear-trained on cipher", "(ii) cipher-trained", "(ii) - chance"], rows)]
    C.write("n6", "task_accuracy", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
