"""N12: person re-identification with and without the key (comparable to Ahmad et al., ICCV 2023, and AnonyNoise,
Bendig et al., WACV 2025).

Usage (Kaggle GPU):
    python experiments/neuro_reid.py --data <eventreid root> [--views ...] [--seeds 0 1 2] [--workers 4]
    python experiments/neuro_reid.py --dataset dvsgesture --data <dvsgesture root> --recipe strong
    python experiments/neuro_reid.py ... --recipe strong        the published recipe (below), not the 22 Nov one

Question: can an attacker without the key still tell who is in the stream? Ahmad et al. (ICCV 2023, Tables 3-4) and
AnonyNoise (WACV 2025, Tables 1-2) answer it for their schemes with rank-1 accuracy and mAP of a ResNet-50 re-id
network; this script gives the same numbers for ours and the baselines.

Protocol (fixed before the run; "basic" 22 Nov 2026, "strong" and DVS Gesture 23 Nov 2026):
  * Event-ReId: every recording (33 persons x 4 cameras); persons split 22 train / 11 test with a fixed seed (Ahmad
    et al. split randomly 22 / 11 and did not publish theirs). Sample: one labelled frame (33.3 ms), at most
    --per-file frames spread evenly over a recording. Retrieval is cross-camera: every test frame is a query, the
    gallery is every test frame of the other cameras.
  * DVS Gesture (AnonyNoise's re-id setting): the official split, 23 training users / 6 test users (identities never
    seen in training); one sample = one recording. Every test sample is a query; the gallery is every other test
    sample except those of the same user AND the same gesture (AnonyNoise excludes the same pair; they use one query
    per user and gesture, we use all).
  * Input: ON / OFF counts in --bins time bins over the sample (2 x bins channels), summed over --down x --down
    pixel blocks, scaled by the maximum. AnonyNoise uses 2 x 5 channels.
  * Each view is applied to the whole recording (one fresh key per recording, as in N6), then cut into samples.
    View "counts only" gives every event a fresh uniform position and polarity: what remains is when events
    happen, i.e. exactly the count series that every level leaves public (control (f) of N3 / N4).
  * Network: ImageNet ResNet-50 with 2 x bins input channels; embedding = the 2048-d pooled feature.
    basic: cross-entropy, AdamW 1e-4, cosine, batch 32, 30 epochs, 1 bin, 4 x 4 blocks.
    strong: cross-entropy + batch-hard triplet loss (margin 0.3, P x K = 8 x 4 batches), as both papers;
    AdamW 1e-3 with cosine decay, batch 32, 60 epochs (Ahmad: 60; AnonyNoise Event-ReId: lr 1e-3 cosine), 5 bins,
    2 x 2 blocks on Event-ReId (240 x 320), none on DVS Gesture (128 x 128); mixed precision on the GPU.
  * Evaluation: cosine distance; rank-1 and mAP over the test identities; mean and Student-t 95 % interval over
    --seeds. Rows per view: (ii) network trained on that view's training samples (the attacker who holds ciphertext
    of other people) and (i) the clear-trained network applied to the view. "clear" is what the key holder gets,
    because decryption is exact (N1/N6).
Writes <out>/reid.{json,md} (default sim_out/neuro/n12/<dataset>/).
"""
import argparse
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import neuro_common as C
import neuro_task_accuracy as N6
from neuro.stats import mean_ci

FRAME_US = 100_000 / 3                 # one Event-ReId labelled frame (README "Labels/BBOX")
DOWN = 4
RECIPES = {
    "basic": {"bins": 1, "down": {"eventreid": 4, "dvsgesture": 1, "synthetic": 4}, "epochs": 30, "lr": 1e-4,
              "triplet": False, "per_file": 40},
    "strong": {"bins": 5, "down": {"eventreid": 2, "dvsgesture": 1, "synthetic": 2}, "epochs": 60, "lr": 1e-3,
               "triplet": True, "per_file": 20},
}
P_IDS, K_PER_ID, MARGIN = 8, 4, 0.3


def split_persons(persons, n_train=22, seed=0):
    """(train, test) person ids: n_train drawn with a fixed seed from the sorted ids, the rest test."""
    ids = sorted(set(persons))
    if n_train >= len(ids):
        raise SystemExit(f"{len(ids)} persons, cannot keep {n_train} for training and any for testing")
    tr = set(np.random.default_rng(seed).choice(ids, n_train, replace=False).tolist())
    return sorted(tr), sorted(set(ids) - tr)


def frame_input(ev, geom, lo, hi, down=DOWN, bins=1):
    """(2 bins) x (H / down) x (W / down) ON / OFF counts of the events in [lo, hi), in `bins` equal time bins
    (channel p * bins + b), scaled by their maximum."""
    m = (ev["t"] >= lo) & (ev["t"] < hi)
    e = ev[m]
    h, w = -(-geom.H // down), -(-geom.W // down)
    x = np.zeros((2 * bins, h, w), np.float32)
    if len(e):
        b = np.minimum(((e["t"].astype(np.float64) - lo) * bins / max(hi - lo, 1e-9)).astype(np.int64), bins - 1)
        ch = e["p"].astype(np.int64) * bins + b
        np.add.at(x, (ch, np.minimum(e["y"] // down, h - 1), np.minimum(e["x"] // down, w - 1)), 1)
        x /= x.max()
    return x


def frame_times(roi, ev, per_file):
    """Start times of up to per_file labelled frames, evenly spread; all frames of the recording without labels."""
    if roi is not None and len(roi):
        starts = np.unique(roi[:, 0])
    else:
        n = int((int(ev["t"][-1]) if len(ev) else 0) // FRAME_US) + 1
        starts = np.arange(n) * FRAME_US
    if len(starts) > per_file:
        starts = starts[np.linspace(0, len(starts) - 1, per_file).round().astype(int)]
    return starts


def counts_only(ev, geom, key):
    """Every event at a fresh uniform pixel with a fresh polarity; times kept: only the count series is left."""
    rng = np.random.default_rng([key, 0x12C])
    out = ev.copy()
    out["x"] = rng.integers(0, geom.W, len(ev))
    out["y"] = rng.integers(0, geom.H, len(ev))
    out["p"] = rng.integers(0, 2, len(ev))
    return out


def apply_view(ev, geom, view, key):
    return counts_only(ev, geom, key) if view == "counts only" else N6.view_events(ev, geom, view, key)


def _frames_one(job):
    ev, geom, view, key, roi, per_file, whole, down, bins = job
    v = apply_view(ev, geom, view, key)
    if whole:                                         # one sample = the whole recording (DVS Gesture)
        hi = float(ev["t"].max()) + 1 if len(ev) else 1.0
        return frame_input(v, geom, 0, hi, down, bins)[None].astype(np.float16)
    return np.stack([frame_input(v, geom, s, s + FRAME_US, down, bins)
                     for s in frame_times(roi, ev, per_file)]).astype(np.float16)


def view_frames(recs, view, per_file, workers, whole=False, down=DOWN, bins=1):
    """Frames (n, 2 bins, h, w) of every recording under `view`, and the recording index of each frame."""
    jobs = [(r["ev"], r["geom"], view, i, r["roi"], per_file, whole, down, bins) for i, r in enumerate(recs)]
    if workers > 1 and len(jobs) >= 8:
        with ProcessPoolExecutor(workers, mp_context=mp.get_context("forkserver")) as ex:
            out = list(ex.map(_frames_one, jobs))
    else:
        out = [_frames_one(j) for j in jobs]
    idx = np.concatenate([np.full(len(f), i) for i, f in enumerate(out)])
    return np.concatenate(out), idx


def rank1_map(emb, pid, cam, gallery="cross-camera"):
    """Retrieval: every row is a query; (rank-1, mAP). gallery "cross-camera": the rows of other cameras;
    "anonynoise": every other row except those with the same person AND the same cam (= gesture) value.
    Queries with no same-person row in their gallery are skipped."""
    e = emb / np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-12)
    sim = e @ e.T
    r1, aps = [], []
    idx = np.arange(len(e))
    for q in range(len(e)):
        if gallery == "cross-camera":
            g = cam != cam[q]
        elif gallery == "anonynoise":
            g = (idx != q) & ~((pid == pid[q]) & (cam == cam[q]))
        else:
            raise ValueError(gallery)
        match = pid[g] == pid[q]
        if not match.any():
            continue
        order = np.argsort(-sim[q, g], kind="stable")
        hits = match[order]
        r1.append(float(hits[0]))
        ranks = np.flatnonzero(hits) + 1
        aps.append(float(np.mean(np.arange(1, len(ranks) + 1) / ranks)))
    return (float(np.mean(r1)) if r1 else float("nan")), (float(np.mean(aps)) if aps else float("nan"))


def check_queries(rank1, quick):
    """Stop a paper run at once when no test sample had a same-identity sample in its gallery (every rank-1 is nan):
    the split or the gallery rule is wrong, and the hours of training that follow would report nothing."""
    if all(np.isnan(v) for v in rank1):
        msg = "no test sample has a same-identity sample in its gallery: rank-1 / mAP undefined"
        if not quick:
            raise SystemExit(msg)
        print("QUICK:", msg, "(small --limit; a paper run stops here)", flush=True)


def batch_hard_triplet(torch, f, y, margin=MARGIN):
    """Batch-hard triplet loss (Hermans et al. 2017): for every anchor, its farthest positive and nearest negative
    in the batch (Euclidean); anchors without a positive or a negative are left out."""
    d = torch.cdist(f, f)
    same = y[:, None] == y[None, :]
    eye = torch.eye(len(y), dtype=torch.bool, device=f.device)
    pos = same & ~eye
    neg = ~same
    ok = pos.any(1) & neg.any(1)
    if not ok.any():
        return f.sum() * 0.0
    hp = torch.where(pos, d, torch.full_like(d, -1e9)).max(1).values
    hn = torch.where(neg, d, torch.full_like(d, 1e9)).min(1).values
    return torch.relu(hp - hn + margin)[ok].mean()


def pk_batches(y, p, k, rng):
    """One epoch of P x K batches: every identity's samples shuffled and cut into groups of k (sampled with
    replacement up to k when an identity has fewer), groups shuffled, p groups of different identities per batch."""
    groups = []
    for c in np.unique(y):
        ix = rng.permutation(np.flatnonzero(y == c))
        if len(ix) < k:
            ix = np.concatenate([ix, rng.choice(ix, k - len(ix))])
        groups += [(c, ix[i:i + k]) for i in range(0, len(ix) - k + 1, k)]
    order = rng.permutation(len(groups))
    batches, cur, seen = [], [], set()
    for g in order:
        c, ix = groups[g]
        if c in seen:
            continue
        cur.append(ix)
        seen.add(c)
        if len(cur) == p:
            batches.append(np.concatenate(cur))
            cur, seen = [], set()
    return batches


def features(m, x):
    """2048-d pooled feature of a torchvision ResNet (the layers before m.fc)."""
    x = m.maxpool(m.relu(m.bn1(m.conv1(x))))
    x = m.layer4(m.layer3(m.layer2(m.layer1(x))))
    return m.avgpool(x).flatten(1)


def train_net(torch, X, y, classes, epochs, seed, dev, bs=32, lr=1e-4, triplet=False, shift=4):
    """basic: N6's fit_eval (cross-entropy). triplet: own loop, cross-entropy + batch-hard triplet on P x K batches,
    AdamW at lr with cosine decay, float16 autocast on CUDA."""
    if not triplet:
        X = X.astype(np.float32)               # frames are kept as float16 (memory); the network trains in float32
        m, _ = N6.fit_eval(torch, X, y, X[:1], y[:1], classes, epochs, seed, dev, bs=bs, arch="resnet50",
                           shift=shift, lr=lr)
        return m
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    rng = np.random.default_rng(seed)
    m = N6.cnn(torch, classes, X.shape[1], "resnet50").to(dev)
    per_epoch = max(1, len(pk_batches(y, P_IDS, K_PER_ID, np.random.default_rng(seed))))
    opt = torch.optim.AdamW(m.parameters(), lr)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs * per_epoch)
    amp = dev == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=amp)
    yt = torch.from_numpy(y).long()
    for _ in range(epochs):
        m.train()
        for b in pk_batches(y, P_IDS, K_PER_ID, rng):
            xb = N6.shift_batch(torch, torch.from_numpy(X[b].astype(np.float32)), shift, gen).to(dev)
            yb = yt[b].to(dev)
            with torch.autocast("cuda", dtype=torch.float16, enabled=amp):
                f = features(m, xb)
                loss = torch.nn.functional.cross_entropy(m.fc(f), yb)
            loss = loss + batch_hard_triplet(torch, f.float(), yb)
            opt.zero_grad()
            scaler.scale(loss).backward()
            scale = scaler.get_scale()
            scaler.step(opt)
            scaler.update()
            if scaler.get_scale() >= scale:   # the scaler skipped this step (inf / nan gradients): keep the schedule
                sch.step()                    # in step with the optimizer (PyTorch warns otherwise)
    return m


def embed(torch, m, X, dev):
    m.eval()
    with torch.no_grad():
        out = torch.cat([features(m, torch.from_numpy(X[i:i + 128].astype(np.float32)).to(dev)).float().cpu()
                         for i in range(0, len(X), 128)]).numpy()
    return out


def load(a):
    """[{ev, geom, pid, cam, roi, train}] of every recording (synthetic stand-in without --data). train is None
    when the split is drawn by person (Event-ReId, synthetic), True / False for DVS Gesture's official split."""
    if a.data is None:
        S = C.synthetic_samples(a.limit or 24, a.seed)
        return [{"ev": s[0], "geom": s[3], "pid": int(s[2][1:]), "cam": i % 2, "roi": None, "train": None}
                for i, s in enumerate(S)]
    if a.dataset == "dvsgesture":
        out = []
        for split in ("train", "test"):
            for ev, label, group, geom, _ in C.load_samples("dvsgesture", a.data, split, a.limit):
                if "/user" not in str(group):
                    raise SystemExit(f"DVS Gesture sample without a user id ({group!r}): re-identification needs one")
                out.append({"ev": ev, "geom": geom, "pid": str(group).split("/")[1], "cam": int(label), "roi": None,
                            "train": split == "train"})
        return out
    from neuro import datasets
    S = C.load_samples("eventreid", a.data, None, a.limit)
    rois = C.load_rois("eventreid", a.data, a.limit)
    every = max(1, datasets.eventreid_count(a.data) // a.limit) if a.limit else 1
    files = datasets._eventreid_files(a.data, None)[::every][:len(S)]
    return [{"ev": s[0], "geom": s[3], "pid": int(s[1]), "cam": f.parent.name, "roi": r, "train": None}
            for s, r, f in zip(S, rois, files)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="eventreid", choices=["eventreid", "dvsgesture"])
    ap.add_argument("--data", default=None, help="dataset root (omit: synthetic smoke data)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--views", nargs="+", default=["V1", "V2", "V3", "Du 2021"])
    ap.add_argument("--recipe", default="basic", choices=sorted(RECIPES))
    ap.add_argument("--per-file", type=int, default=None, help="frames per Event-ReId recording (recipe default)")
    ap.add_argument("--epochs", type=int, default=None, help="override the recipe's epochs")
    ap.add_argument("--train-persons", type=int, default=22)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    rec = RECIPES[a.recipe]
    ds = a.dataset if a.data else "synthetic"
    bins, down, lr, triplet = rec["bins"], rec["down"][ds], rec["lr"], rec["triplet"]
    epochs = a.epochs or rec["epochs"]
    per_file = a.per_file or rec["per_file"]
    if a.quick:
        epochs, a.seeds, per_file = 1, a.seeds[:1], min(per_file, 4)
    whole = ds == "dvsgesture"
    gallery = "anonynoise" if whole else "cross-camera"
    recs = load(a)
    pid = np.array([r["pid"] for r in recs])
    cams = np.array([str(r["cam"]) for r in recs])
    if whole:
        is_tr = np.array([r["train"] for r in recs])
        tr_ids, te_ids = sorted(set(pid[is_tr])), sorted(set(pid[~is_tr]))
        if set(tr_ids) & set(te_ids):
            raise SystemExit("DVS Gesture: a user is in both splits")
    else:
        tr_ids, te_ids = split_persons(pid, a.train_persons if a.data else max(1, len(set(pid)) // 2), a.seed)
    lab = {p: i for i, p in enumerate(tr_ids)}
    res, t0 = {}, time.time()
    X, idx = view_frames(recs, "clear", per_file, a.workers, whole, down, bins)
    tr = np.isin(pid[idx], tr_ids)
    ytr = np.array([lab[p] for p in pid[idx][tr]])
    te = ~tr
    fit = dict(lr=lr, triplet=triplet)
    clear_nets = [train_net(torch, X[tr], ytr, len(tr_ids), epochs, sd, dev, **fit) for sd in a.seeds]

    def score(nets, Xte):
        r = [rank1_map(embed(torch, m, Xte, dev), pid[idx][te], cams[idx][te], gallery) for m in nets]
        return {"rank1": [v[0] for v in r], "map": [v[1] for v in r]}
    def report():
        def cell(d, k):
            if d is None:
                return "-"
            m, lo, hi = mean_ci(d[k])
            return f"{100 * m:.1f} [{100 * lo:.1f}, {100 * hi:.1f}]"
        rows = [(v, cell(r["cipher_trained"], "rank1"), cell(r["cipher_trained"], "map"), cell(r["clear_trained"], "rank1"),
                 cell(r["clear_trained"], "map")) for v, r in res.items()]
        n_q = int(te.sum())
        name = {"eventreid": "Event-ReId", "dvsgesture": "DVS Gesture (users)"}.get(ds, "synthetic smoke data")
        h, w = X.shape[2:]
        if whole:
            unit = (f"{n_q} test recordings (one sample each), retrieval against every other test recording except the "
                    f"same user and gesture (AnonyNoise's gallery rule)")
        else:
            unit = (f"{n_q} test frames (33.3 ms each, up to {per_file} per recording), cross-camera retrieval")
        md = [f"# N12 person re-identification on {name}", "",
              f"{len(recs)} recordings, identities {len(tr_ids)} train / {len(te_ids)} test; {unit}; chance rank-1 about "
              f"{100 / max(1, len(te_ids)):.0f} %. Recipe {a.recipe}: ResNet-50 (ImageNet), input {2 * bins} x {h} x {w} "
              f"({bins} time bin(s), {down} x {down} blocks), {'cross-entropy + batch-hard triplet' if triplet else 'cross-entropy'}, "
              f"AdamW {lr:g} cosine, {epochs} epochs, seeds {a.seeds}; mean and 95 % interval in %.", "",
              C.table(["view", "rank-1, trained on the view", "mAP, trained on the view", "rank-1, clear-trained net",
                       "mAP, clear-trained net"], rows), "",
              "clear = what the key holder gets (decryption is exact). counts only = every event at a random position "
              "and polarity: the public count series alone. Published reference points (their protocol, their split): "
              "Ahmad et al. ICCV 2023 Event-ReId re-id rank-1 63.7 % on raw events; AnonyNoise WACV 2025 retrained "
              "attacker, Event-ReId top-1 59.1 % raw / 38.6 % anonymised, DVS Gesture 98.3 % raw / 40.0 % anonymised."]
        data = {"results": res, "train_ids": tr_ids, "test_ids": te_ids, "test_samples": n_q, "dataset": ds,
                "recipe": a.recipe, "input_shape": [2 * bins, int(h), int(w)], "epochs": epochs, "gallery": gallery,
                "meta": C.meta(a, synthetic=a.data is None, device=dev)}
        # keys kept for the 22 Nov readers (make_figures / make_summary read train_persons / test_persons)
        data["train_persons"], data["test_persons"], data["test_frames"] = tr_ids, te_ids, n_q
        C.write("n12", "reid", data, "\n".join(md), a.out or (C.OUT / "n12" / ds))

    res["clear"] = {"cipher_trained": score(clear_nets, X[te]), "clear_trained": None}
    print("clear", res["clear"], f"{time.time() - t0:.0f} s", flush=True)
    check_queries(res["clear"]["cipher_trained"]["rank1"], a.quick)
    report()                                  # written after every view: a run stopped at the time limit keeps
    #                                           every finished row
    for view in a.views:
        V, vidx = view_frames(recs, view, per_file, a.workers, whole, down, bins)
        assert (vidx == idx).all(), "frame order must not depend on the view"
        nets = [train_net(torch, V[tr], ytr, len(tr_ids), epochs, sd, dev, **fit) for sd in a.seeds]
        res[view] = {"cipher_trained": score(nets, V[te]), "clear_trained": score(clear_nets, V[te])}
        print(view, res[view], f"{time.time() - t0:.0f} s", flush=True)
        report()
        del V



if __name__ == "__main__":
    main()
