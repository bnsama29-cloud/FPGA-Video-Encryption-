"""N12: person re-identification on Event-ReId with and without the key (comparable to Ahmad et al., ICCV 2023).

Usage (Kaggle GPU):
    python experiments/neuro_reid.py --data <eventreid root> [--views ...] [--seeds 0 1 2] [--workers 4]

Question: can an attacker without the key still tell who is in the stream? Ahmad et al. (ICCV 2023, Tables 3-4) and
AnonyNoise (WACV 2025, Table 2) answer it for their schemes with rank-1 accuracy and mAP of a ResNet-50 re-id
network on Event-ReId; this script gives the same numbers for ours and the baselines.

Protocol (fixed before the run, 22 Nov 2026):
  * Data: every Event-ReId recording (33 persons x 4 cameras); persons split 22 train / 11 test with a fixed seed
    (Ahmad et al. split randomly 22 / 11 and did not publish theirs).
  * Sample: one labelled frame (33.3 ms) of a recording, at most --per-file frames spread evenly over it; input =
    ON / OFF counts of the frame's events, summed over 4 x 4 pixel blocks (2 x 120 x 160), scaled by the maximum.
    The dataset keeps only the events inside the person box, so the full frame is the person.
  * Each view is applied to the whole recording (one fresh key per recording, as in N6), then cut into frames.
  * Network: ImageNet ResNet-50 with 2 input channels (as both papers), cross-entropy over the 22 train identities,
    AdamW 1e-4, cosine decay, --epochs; embedding = the 2048-d pooled feature (their triplet loss is not used).
  * Evaluation (test identities only, cross-camera): every test frame is a query; the gallery is every test frame of
    the other cameras; cosine distance; rank-1 accuracy and mAP; mean and Student-t 95 % interval over --seeds.
    Chance rank-1 is about 1 / 11.
  * Rows per view: (ii) attacker trained on that view's train frames (the attacker who has ciphertext of other
    people, our N6 setting) and (i) the network trained on clear frames applied to the view. "clear" is what the key
    holder gets, because decryption is exact (N1/N6).
Writes sim_out/neuro/n12/reid.{json,md}.
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


def split_persons(persons, n_train=22, seed=0):
    """(train, test) person ids: n_train drawn with a fixed seed from the sorted ids, the rest test."""
    ids = sorted(set(persons))
    if n_train >= len(ids):
        raise SystemExit(f"{len(ids)} persons, cannot keep {n_train} for training and any for testing")
    tr = set(np.random.default_rng(seed).choice(ids, n_train, replace=False).tolist())
    return sorted(tr), sorted(set(ids) - tr)


def frame_input(ev, geom, lo, hi, down=DOWN):
    """2 x (H / down) x (W / down) ON / OFF counts of the events in [lo, hi), scaled by their maximum."""
    m = (ev["t"] >= lo) & (ev["t"] < hi)
    e = ev[m]
    h, w = geom.H // down, geom.W // down
    x = np.zeros((2, h, w), np.float32)
    if len(e):
        np.add.at(x, (e["p"].astype(np.int64), np.minimum(e["y"] // down, h - 1), np.minimum(e["x"] // down, w - 1)), 1)
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


def _frames_one(job):
    ev, geom, view, key, roi, per_file = job
    v = N6.view_events(ev, geom, view, key)
    return np.stack([frame_input(v, geom, s, s + FRAME_US) for s in frame_times(roi, ev, per_file)]).astype(np.float16)


def view_frames(recs, view, per_file, workers):
    """Frames (n, 2, h, w) of every recording under `view`, and the recording index of each frame."""
    jobs = [(r["ev"], r["geom"], view, i, r["roi"], per_file) for i, r in enumerate(recs)]
    if workers > 1 and len(jobs) >= 8:
        with ProcessPoolExecutor(workers, mp_context=mp.get_context("forkserver")) as ex:
            out = list(ex.map(_frames_one, jobs))
    else:
        out = [_frames_one(j) for j in jobs]
    idx = np.concatenate([np.full(len(f), i) for i, f in enumerate(out)])
    return np.concatenate(out), idx


def rank1_map(emb, pid, cam):
    """Cross-camera retrieval: every row is a query against the rows of other cameras; (rank-1, mAP).
    Queries with no same-person row in the other cameras are skipped."""
    e = emb / np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-12)
    sim = e @ e.T
    r1, aps = [], []
    for q in range(len(e)):
        g = cam != cam[q]
        match = pid[g] == pid[q]
        if not match.any():
            continue
        order = np.argsort(-sim[q, g], kind="stable")
        hits = match[order]
        r1.append(float(hits[0]))
        ranks = np.flatnonzero(hits) + 1
        aps.append(float(np.mean(np.arange(1, len(ranks) + 1) / ranks)))
    return (float(np.mean(r1)) if r1 else float("nan")), (float(np.mean(aps)) if aps else float("nan"))


def train_net(torch, X, y, classes, epochs, seed, dev, bs=32, lr=1e-4):
    X = X.astype(np.float32)                   # frames are kept as float16 (memory); the network trains in float32
    m, _ = N6.fit_eval(torch, X, y, X[:1], y[:1], classes, epochs, seed, dev, bs=bs, arch="resnet50", shift=4, lr=lr)
    return m


def embed(torch, m, X, dev):
    fc, m.fc = m.fc, torch.nn.Identity()
    m.eval()
    with torch.no_grad():
        out = torch.cat([m(torch.from_numpy(X[i:i + 128].astype(np.float32)).to(dev)).cpu()
                         for i in range(0, len(X), 128)]).numpy()
    m.fc = fc
    return out


def load(a):
    """[{ev, geom, pid, cam, roi}] of every recording (synthetic stand-in without --data)."""
    if a.data is None:
        S = C.synthetic_samples(a.limit or 24, a.seed)
        return [{"ev": s[0], "geom": s[3], "pid": int(s[2][1:]), "cam": i % 2, "roi": None} for i, s in enumerate(S)]
    from neuro import datasets
    S = C.load_samples("eventreid", a.data, None, a.limit)
    rois = C.load_rois("eventreid", a.data, a.limit)
    every = max(1, datasets.eventreid_count(a.data) // a.limit) if a.limit else 1
    files = datasets._eventreid_files(a.data, None)[::every][:len(S)]
    return [{"ev": s[0], "geom": s[3], "pid": int(s[1]), "cam": f.parent.name, "roi": r}
            for s, r, f in zip(S, rois, files)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=None, help="Event-ReId root (omit: synthetic smoke data)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--views", nargs="+", default=["V1", "V2", "V3", "Du 2021"])
    ap.add_argument("--per-file", type=int, default=40)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--train-persons", type=int, default=22)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if a.quick:
        a.epochs, a.seeds, a.per_file = 1, a.seeds[:1], min(a.per_file, 4)
    recs = load(a)
    pid = np.array([r["pid"] for r in recs])
    cams = np.array([str(r["cam"]) for r in recs])
    tr_ids, te_ids = split_persons(pid, a.train_persons if a.data else max(1, len(set(pid)) // 2), a.seed)
    lab = {p: i for i, p in enumerate(tr_ids)}
    res, t0 = {}, time.time()
    X, idx = view_frames(recs, "clear", a.per_file, a.workers)
    tr = np.isin(pid[idx], tr_ids)
    ytr = np.array([lab[p] for p in pid[idx][tr]])
    clear_nets = [train_net(torch, X[tr], ytr, len(tr_ids), a.epochs, sd, dev) for sd in a.seeds]
    te = ~tr

    def score(nets, Xte):
        r = [rank1_map(embed(torch, m, Xte, dev), pid[idx][te], cams[idx][te]) for m in nets]
        return {"rank1": [v[0] for v in r], "map": [v[1] for v in r]}
    res["clear"] = {"cipher_trained": score(clear_nets, X[te]), "clear_trained": None}
    print("clear", res["clear"], f"{time.time() - t0:.0f} s", flush=True)
    for view in a.views:
        V, vidx = view_frames(recs, view, a.per_file, a.workers)
        assert (vidx == idx).all(), "frame order must not depend on the view"
        nets = [train_net(torch, V[tr], ytr, len(tr_ids), a.epochs, sd, dev) for sd in a.seeds]
        res[view] = {"cipher_trained": score(nets, V[te]), "clear_trained": score(clear_nets, V[te])}
        print(view, res[view], f"{time.time() - t0:.0f} s", flush=True)
        del V

    def cell(d, k):
        if d is None:
            return "-"
        m, lo, hi = mean_ci(d[k])
        return f"{100 * m:.1f} [{100 * lo:.1f}, {100 * hi:.1f}]"
    rows = [(v, cell(r["cipher_trained"], "rank1"), cell(r["cipher_trained"], "map"), cell(r["clear_trained"], "rank1"),
             cell(r["clear_trained"], "map")) for v, r in res.items()]
    n_q = int(te.sum())
    md = ["# N12 person re-identification" + (" (synthetic smoke data)" if a.data is None else " on Event-ReId"), "",
          f"{len(recs)} recordings, persons {len(tr_ids)} train / {len(te_ids)} test (seed {a.seed}); {n_q} test frames "
          f"(33.3 ms each, up to {a.per_file} per recording), cross-camera retrieval; chance rank-1 about "
          f"{100 / max(1, len(te_ids)):.0f} %. ResNet-50 (ImageNet), {a.epochs} epochs, seeds {a.seeds}; mean and "
          f"95 % interval in %.", "",
          C.table(["view", "rank-1, trained on the view", "mAP, trained on the view", "rank-1, clear-trained net",
                   "mAP, clear-trained net"], rows), "",
          "clear = what the key holder gets (decryption is exact). Published reference points (their protocol, their "
          "split): Ahmad et al. ICCV 2023 re-id rank-1 63.7 % on raw events; AnonyNoise WACV 2025 retrained attacker "
          "top-1 59.1 % raw, 38.6 % anonymised."]
    data = {"results": res, "train_persons": tr_ids, "test_persons": te_ids, "test_frames": n_q,
            "meta": C.meta(a, synthetic=a.data is None, device=dev)}
    C.write("n12", "reid", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
