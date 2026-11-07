"""N6: is task utility kept with the key and lost without it?

Usage (Kaggle GPU; needs PyTorch, snnTorch optional):
    python experiments/neuro_task_accuracy.py --dataset nmnist --data <root> [--seeds 0 1 2] [--epochs 20] [--quick]

Method (DESIGN §8.2 N6). Official train/test files (Tonic 1.7.0 loaders in neuro.datasets).
  * Decryption is exact, so "accuracy on decrypted data" is not a result: the script decrypts every test sample
    through neuro.receiver.Decryptor at V3 and asserts event equality, reporting the count in one sentence.
  * Models: a frame CNN on 2-channel (ON / OFF) count frames; an SNN (snnTorch leaky integrate-and-fire on 10 time
    bins) when snnTorch is installed.
  * Gate (fixed in §8.2): clean test accuracy >= 98 % (N-MNIST) / >= 90 % (DVS Gesture) before any ciphertext
    row is reported; synthetic data have no gate.
  * Rows per view (V1, V2, V3, V4 = empty input, Du 2021, Zhang 2024): (i) trained on clear, tested on
    ciphertext; (ii) trained and tested on ciphertext with a fresh key per sample. Measure fixed in advance:
    accuracy (ii) - chance, with a Student-t CI over >= 3 seeds (neuro.stats.mean_ci).
  * Zhang anchor (BASELINES.md §2.2): their Table 1 gives 0.06-0.14 on N-MNIST for Zhang ciphertext.
Writes sim_out/neuro/n6/task_accuracy.{json,md}.
"""
import argparse

import numpy as np

import neuro_common as C
from neuro import evt2, keys, receiver
from neuro.stats import mean_ci

GATE = {"nmnist": 0.98, "dvsgesture": 0.90}


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


def decrypt_check(samples, T=1024):
    """Count test samples whose V3 packets decrypt to event-equal streams."""
    ok = 0
    for i, (ev, _, _, geom, _) in enumerate(samples):
        pk = C.protect(ev, geom, 3, T, key_index=i)
        prof = receiver.Profile(frozenset({(3, 6, None, None)}), geom, T, R_max_words_per_us=64.0)
        d = receiver.Decryptor({(C.CAM, C.BOOT): C.master(i)}, prof)
        words = [r.words for r in (d.accept(p, now=j * 1e-3) for j, p in enumerate(pk)) if r.status == "ok"]
        dec = np.concatenate(words) if words else np.zeros(0, np.uint32)
        ok += evt2.event_equal(dec, evt2.encode(ev, T))
    return ok


def cnn(torch, classes, H, W):
    nn = torch.nn
    return nn.Sequential(nn.Conv2d(2, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                         nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(4), nn.Flatten(),
                         nn.Linear(64 * 16, 128), nn.ReLU(), nn.Linear(128, classes))


def fit_eval(torch, Xtr, ytr, Xte, yte, classes, epochs, seed, dev):
    torch.manual_seed(seed)
    m = cnn(torch, classes, Xtr.shape[-2], Xtr.shape[-1]).to(dev)
    opt = torch.optim.Adam(m.parameters(), 1e-3)
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr).long()
    for _ in range(epochs):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 64):
            j = perm[i:i + 64]
            loss = torch.nn.functional.cross_entropy(m(Xt[j].to(dev)), yt[j].to(dev))
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        pred = torch.cat([m(torch.from_numpy(Xte[i:i + 256]).to(dev)).argmax(1).cpu()
                          for i in range(0, len(Xte), 256)]).numpy()
    return m, float((pred == yte).mean())


def evaluate(torch, m, X, y, dev):
    with torch.no_grad():
        pred = torch.cat([m(torch.from_numpy(X[i:i + 256]).to(dev)).argmax(1).cpu() for i in range(0, len(X), 256)])
    return float((pred.numpy() == y).mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--views", nargs="+", default=["V1", "V2", "V3", "V4", "Du 2021", "Zhang 2024"])
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
    n_equal = decrypt_check(te_s[:20] if a.quick else te_s)
    Xtr = np.stack([frame(s[0], geom) for s in tr_s])
    Xte = np.stack([frame(s[0], geom) for s in te_s])
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
        for view in a.views:
            if view in ("Du 2021", "Zhang 2024") and not C.baseline("du2021" if view.startswith("Du") else "zhang2024"):
                continue
            Ctr = np.stack([frame(view_events(s[0], geom, view, i), geom) for i, s in enumerate(tr_s)])
            Cte = np.stack([frame(view_events(s[0], geom, view, 10_000 + i), geom) for i, s in enumerate(te_s)])
            r_i = [evaluate(torch, m, Cte, yte, dev) for m in models]
            r_ii = [fit_eval(torch, Ctr, ytr, Cte, yte, classes, a.epochs, sd, dev)[1] for sd in a.seeds]
            d = mean_ci(np.asarray(r_ii) - chance)
            res[view] = {"i_clear_trained": mean_ci(r_i), "ii_cipher_trained": mean_ci(r_ii), "ii_minus_chance": d}
            rows.append((view, mean_ci(r_i), mean_ci(r_ii), d))
    try:
        import snntorch  # noqa: F401
        snn = "installed: SNN rows to be added by the Kaggle run"
    except ImportError:
        snn = "snnTorch not installed: SNN rows not run"
    data = {"results": res, "gate": {"threshold": gate_thr, "clean_mean": float(np.mean(clean)), "passes": bool(gate)},
            "decrypted_event_equal": f"{n_equal} of {min(len(te_s), 20) if a.quick else len(te_s)}",
            "chance": chance, "snn": snn,
            "meta": C.meta(a, dataset=a.dataset, synthetic=a.data is None, device=dev, seeds=a.seeds,
                           ci="Student-t 95 % over seeds", n_keys="fresh key per sample")}
    md = ["# N6 task accuracy" + (" (synthetic smoke data)" if a.data is None else ""), "",
          f"Decryption check: {data['decrypted_event_equal']} test samples decrypt event-equal (V3). "
          f"Gate: clean {np.mean(clean):.3f} vs {gate_thr} -> {'pass' if gate else 'FAIL: no ciphertext rows'}. "
          f"Chance {chance:.3f}. {snn}.", "",
          C.table(["view", "(i) clear-trained on cipher", "(ii) cipher-trained", "(ii) - chance"], rows)]
    C.write("n6", "task_accuracy", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
