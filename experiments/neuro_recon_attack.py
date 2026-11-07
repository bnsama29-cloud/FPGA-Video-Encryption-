"""N3: can intensity reconstruction recover the scene from protected events?

Usage:
    python experiments/neuro_recon_attack.py [--dataset eventreid --data <root>] [--keys 5]
        [--recon-repo <rpg_e2vid checkout> --recon-ckpt e2vid=<E2VID_lightweight.pth.tar> firenet=<...>]
        [--win-ms 20] [--quick]

The E2VID / FireNet code is GPL-3.0 and is downloaded at run time into the Kaggle working directory by
software/system/kaggle/kaggle_neuro.py (never committed); checkpoints are SHA-256 pinned there. Without
--recon-repo only the classical attacks run (laptop smoke test).

Method (DESIGN §8.2 N3). Each sample is cut into windows; for every window and every view
(plain, V1, V2, V3, V4, Du 2021, Zhang 2024) the attacker runs every attack it has and the most revealing result
per window is kept (paper 1's rule):
  * classical: event-count image, time surface, signed integration (polarity accumulation, a direct-integration
    reconstruction), the same after a nearest-neighbour denoiser (Zhang 2024 eq. 3: same polarity, L1 <= 1,
    dt <= 5 ms), and at V1 the polarity-collapsed count image;
  * learned (with --recon-repo): E2VID and FireNet on 5-bin voxel grids (neuro.voxel), recurrent over windows.
  Target: the ground-truth intensity frame where the dataset has one (synthetic v2e-lite: exact), else the
  plaintext reconstruction (labelled "vs plaintext reconstruction").
Controls: (c) the training-median frame; (f) a prior conditioned on the public per-bucket count series (mean
target frame of the 5 nearest training windows in count-series space). Validity gate: the dataset counts only
if the best plaintext SSIM exceeds control (c) by >= 0.05 with a CI excluding 0.
Metrics: SSIM, PSNR, edge correlation (Sobel magnitudes). Statistics: --keys independent master keys (sample i
uses key i mod keys), cluster bootstrap over recordings, paired differences (best attack - control (f)) on
identical windows. Criterion P1 (fixed in §8.1): upper 95 % bound of SSIM_attack - SSIM_control(f) < 0.05.
Writes sim_out/neuro/n3/recon_attack.{json,md}.
"""
import argparse
from pathlib import Path

import numpy as np
from skimage.filters import sobel
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

import neuro_common as C
from neuro import attacks
from neuro.stats import cluster_bootstrap_ci, n_clusters, paired_bootstrap_diff
from neuro.voxel import voxel_grid

VIEWS = ["plain", "V1", "V2", "V3", "V4", "Du 2021", "Zhang 2024"]


def norm(img):
    img = np.asarray(img, float)
    lo, hi = np.quantile(img, 0.01), np.quantile(img, 0.99)
    return np.clip((img - lo) / (hi - lo), 0, 1) if hi > lo else np.zeros_like(img)


def signed_integration(ev, geom):
    img = np.zeros((geom.H, geom.W))
    np.add.at(img, (ev["y"].astype(int), ev["x"].astype(int)), 2.0 * ev["p"] - 1.0)
    return img


def nn_denoise(ev, dt_us=5000):
    """Keep events with a same-polarity event at L1 distance <= 1 within dt (Zhang 2024 eq. 3, NNf)."""
    if len(ev) < 2:
        return ev
    keep = np.zeros(len(ev), bool)
    last = {}
    t = ev["t"].astype(np.int64)
    for i in range(len(ev)):
        x, y, p = int(ev["x"][i]), int(ev["y"][i]), int(ev["p"][i])
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            j = last.get((x + dx, y + dy, p))
            if j is not None and t[i] - t[j] <= dt_us:
                keep[i] = keep[j] = True
        last[(x, y, p)] = i
    return ev[keep]


def classical(ev, geom, level):
    out = {"count": attacks.event_count_frame(ev, geom), "time_surface": attacks.time_surface(ev, geom, 20_000),
           "integration": signed_integration(ev, geom)}
    d = nn_denoise(ev)
    if len(d):
        out["denoise+count"] = attacks.event_count_frame(d, geom)
        out["denoise+integration"] = signed_integration(d, geom)
    if level == "V1":
        out["polarity_collapse"] = attacks.event_count_frame(attacks.polarity_collapse(ev), geom)
    return out


class Learned:
    """E2VID / FireNet from an rpg_e2vid checkout (run-time download; GPL code is never committed)."""

    def __init__(self, repo, ckpts):
        import sys
        import torch
        sys.path.insert(0, str(repo))
        from utils.loading_utils import load_model           # rpg_e2vid
        self.torch = torch
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.models = {}
        for spec in ckpts:
            name, path = spec.split("=", 1)
            m = load_model(path)
            self.models[name] = m.to(self.dev).eval()
        self.states = {}

    def reset(self):
        self.states = {k: None for k in self.models}

    def __call__(self, ev, geom):
        torch = self.torch
        vg = voxel_grid(ev, 5, H=geom.H, W=geom.W)
        # pad to a multiple of 16 (UNet downsampling)
        Hp, Wp = -(-geom.H // 16) * 16, -(-geom.W // 16) * 16
        x = np.zeros((1, 5, Hp, Wp), np.float32)
        x[0, :, :geom.H, :geom.W] = vg
        out = {}
        with torch.no_grad():
            t = torch.from_numpy(x).to(self.dev)
            for name, m in self.models.items():
                img, self.states[name] = m(t, self.states[name])
                out[name] = img[0, 0, :geom.H, :geom.W].float().cpu().numpy()
        return out


def views_of(ev, geom, key_index, T):
    """Events an eavesdropper sees per view (V4: none)."""
    out = {"plain": ev}
    for lv in (1, 2, 3, 4):
        out[f"V{lv}"] = C.keyless_events(C.protect(ev, geom, lv, T, key_index=key_index))
    du, zh = C.baseline("du2021"), C.baseline("zhang2024")
    if du:
        out["Du 2021"] = du.encrypt(ev, geom.W, geom.H, du.DuKey.from_seed(C.master(key_index)))
    if zh and geom.W * geom.H <= 64 * 64 * 4:
        out["Zhang 2024"], _ = zh.encrypt(ev, geom.W, geom.H, C.master(key_index))
    return out


def scores(img, target):
    a, b = norm(img), norm(target)
    s = structural_similarity(a, b, data_range=1.0)
    p = peak_signal_noise_ratio(b, a, data_range=1.0) if not np.allclose(a, b) else 99.0
    ea, eb = sobel(a).ravel(), sobel(b).ravel()
    e = float(np.corrcoef(ea, eb)[0, 1]) if ea.std() > 0 and eb.std() > 0 else 0.0
    return s, p, e


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--win-ms", type=float, default=20.0)
    ap.add_argument("--T", type=int, default=1024)
    ap.add_argument("--recon-repo", type=Path, default=None)
    ap.add_argument("--recon-ckpt", nargs="*", default=[])
    a = ap.parse_args()
    if a.quick:
        a.keys = 2
    samples = C.load_samples(a.dataset, a.data, limit=a.limit or (8 if a.quick else 400), seed=a.seed)
    learned = Learned(a.recon_repo, a.recon_ckpt) if a.recon_repo else None
    win = int(a.win_ms * 1000)
    recs = []                      # one record per (sample, window)
    for si, (ev, label, grp, geom, frames) in enumerate(samples):
        if len(ev) == 0:
            continue
        vs = views_of(ev, geom, si % a.keys, a.T)
        t0 = int(ev["t"].min())
        n_w = int((int(ev["t"].max()) - t0) // win) + 1
        per_view = {}
        for name, e in vs.items():
            if learned:
                learned.reset()
            wins = []
            for k in range(n_w):
                m = (e["t"].astype(np.int64) >= t0 + k * win) & (e["t"].astype(np.int64) < t0 + (k + 1) * win) \
                    if len(e) else np.zeros(0, bool)
                we = e[m] if len(e) else e
                imgs = classical(we, geom, name) if len(we) else {"none": np.zeros((geom.H, geom.W))}
                if learned and len(we):
                    imgs.update(learned(we, geom))
                wins.append(imgs)
            per_view[name] = wins
        for k in range(n_w):
            if frames is not None:
                fi = min(len(frames) - 1, int((t0 + (k + 1) * win - 10_000) // 1000))
                target, tgt_kind = frames[fi], "ground truth"
            else:
                target, tgt_kind = max(per_view["plain"][k].values(), key=lambda im: im.std()), "plaintext recon"
            we = ev[(ev["t"].astype(np.int64) >= t0 + k * win) & (ev["t"].astype(np.int64) < t0 + (k + 1) * win)]
            cnt = np.bincount(((we["t"].astype(np.int64) - (t0 + k * win)) // 64), minlength=win // 64)[:win // 64]
            r = {"sample": si, "group": grp, "window": k, "target": target, "target_kind": tgt_kind, "counts": cnt}
            for name, wins in per_view.items():
                best = max((scores(img, target) + (att,) for att, img in wins[k].items()), key=lambda s: s[0])
                r[name] = best
            recs.append(r)
    # controls: split groups in half (train / test)
    groups = sorted({r["group"] for r in recs})
    train_g = set(groups[: max(1, len(groups) // 2)])
    tr = [r for r in recs if r["group"] in train_g]
    te = [r for r in recs if r["group"] not in train_g] or recs
    med = np.median(np.stack([r["target"] for r in tr]), 0)
    Ctr = np.stack([r["counts"] for r in tr]).astype(float)
    for r in te:
        r["control_c"] = scores(med, r["target"])
        d = ((Ctr - r["counts"]) ** 2).sum(1)
        nn = np.argsort(d)[:5]
        r["control_f"] = scores(np.mean([tr[i]["target"] for i in nn], 0), r["target"])
    g = [r["group"] for r in te]
    res = {}
    rows = []
    for name in VIEWS + ["control_c", "control_f"]:
        if name not in te[0]:
            continue
        ss = [r[name][0] for r in te]
        ci = cluster_bootstrap_ci(ss, g, n=1000, seed=a.seed)
        d = paired_bootstrap_diff(ss, [r["control_f"][0] for r in te], g, n=1000, seed=a.seed)
        atk = {}
        for r in te:
            if len(r[name]) > 3:
                atk[r[name][3]] = atk.get(r[name][3], 0) + 1
        res[name] = {"ssim": ci, "psnr_mean": float(np.mean([r[name][1] for r in te])),
                     "edge_corr_mean": float(np.mean([r[name][2] for r in te])), "minus_control_f": d,
                     "best_attack_counts": atk, "P1_pass": bool(d[2] < 0.05)}
        rows.append((name, ci, res[name]["psnr_mean"], res[name]["edge_corr_mean"], d,
                     "yes" if d[2] < 0.05 else "no", max(atk, key=atk.get) if atk else "-"))
    gate_d = paired_bootstrap_diff([r["plain"][0] for r in te], [r["control_c"][0] for r in te], g, n=1000,
                                   seed=a.seed)
    gate = bool(gate_d[0] >= 0.05 and gate_d[1] > 0)
    data = {"results": res, "validity_gate": {"plain_minus_control_c": gate_d, "passes": gate},
            "windows_test": len(te), "clusters_test": n_clusters(g), "target": te[0]["target_kind"],
            "learned_attacks": bool(learned)}
    data["meta"] = C.meta(a, dataset=a.dataset, synthetic=a.data is None, n_keys=a.keys,
                          ci="cluster bootstrap 95 % over recordings, 1000 resamples",
                          baselines={b: bool(C.baseline(b)) for b in ("du2021", "zhang2024")})
    md = ["# N3 reconstruction attack" + (" (synthetic smoke data)" if a.data is None else ""), "",
          f"Target: {data['target']}; {len(te)} test windows, {data['clusters_test']} clusters, {a.keys} keys; "
          f"learned attacks: {'yes' if learned else 'no (classical only)'}.", "",
          f"Validity gate (plain - control (c) >= 0.05, CI excluding 0): {gate_d} -> "
          f"{'passes' if gate else 'FAILS: dataset not counted'}", "",
          C.table(["view", "SSIM [95 % CI]", "PSNR", "edge corr", "SSIM - control (f)", "P1 pass", "best attack"],
                  rows)]
    C.write("n3", "recon_attack", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
