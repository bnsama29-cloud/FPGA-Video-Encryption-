"""N4b: does co-activation of neighbouring pixels reveal the V2/V3 layout of a packet without the key?

Usage:
    python experiments/neuro_adjacency_attack.py [--dataset dvsgesture --data <root>] [--T 256 1024 4096]
                                                 [--dt 5 20 64] [--quick]

Method (DESIGN §4.3.6 item 3, §8.2 N4b). For every packet of a V2 stream the attacker sees the permuted addresses
and their timestamps (keyless extraction). It links addresses that fire within dt µs (k = 8 most recent), embeds
the graph in 2-D by a Laplacian eigenmap (neuro.attacks.adjacency_embed), aligns the embedding to the true pixel
positions (the experimenter knows them: the permutation is word-local, so the i-th CD word of the payload is the
i-th event of the packet) and reports
  * recovered 4-neighbour fraction (true 4-neighbour pairs that are 4-nearest neighbours in the embedding),
  * normalised Procrustes error (0 = layout recovered up to similarity, 1 = nothing),
per T and dt, against two references: plaintext addresses (the leak's upper bound: the embedding of the true
layout) and the ideal permutation control (Knuth shuffle, §4.4): a leak that also appears under the shuffle
belongs to V2 in principle, not to the Feistel. Packets with fewer than --min-addr distinct addresses are skipped.
Cluster bootstrap over recordings (groups).
Writes sim_out/neuro/n4b/adjacency.{json,md}.
"""
import argparse

import numpy as np

import neuro_common as C
from neuro import attacks, evt2, feistel, keys
from neuro.stats import cluster_bootstrap_ci, n_clusters

SK = keys.subkeys(C.master(0), C.CAM, C.BOOT, 0)
SID = keys.session_id(C.CAM, C.BOOT, 0)


def packet_views(ev, geom, T, max_packets):
    """[(true events, V2 events, shuffled events)] per packet with the same event order."""
    out = []
    k = (ev["t"].astype(np.int64) - int(ev["t"][0])) // T
    for ctr, kk in enumerate(np.unique(k)[:max_packets]):
        e = ev[k == kk]
        t = feistel.make_tables(SK.perm, SID, ctr, geom.W, geom.H)
        px, py = feistel.permute(e["x"], e["y"], t)
        v2 = e.copy()
        v2["x"], v2["y"] = px, py
        perm = feistel.shuffle_table(SK.perm, SID, ctr, geom.W, geom.H) if geom.W * geom.H <= 20000 else None
        sh = None
        if perm is not None:
            sh = e.copy()
            q = perm[e["y"].astype(np.int64) * geom.W + e["x"]]
            sh["x"], sh["y"] = q % geom.W, q // geom.W
        out.append((e, v2, sh))
    return out


def score(true_ev, seen_ev, dt, min_addr):
    """(neighbour recovery, procrustes error) of the embedding of seen addresses vs the true positions."""
    addr, emb = attacks.adjacency_embed(seen_ev, dt_us=dt, k=8)
    if len(addr) < min_addr:
        return None
    key = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(seen_ev["x"], seen_ev["y"]))}
    idx = [key[(int(a), int(b))] for a, b in addr]
    true_xy = np.stack([true_ev["x"][idx], true_ev["y"][idx]], 1)
    return attacks.neighbour_recovery(true_xy, emb), attacks.procrustes_error(true_xy, emb)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--T", type=int, nargs="+", default=[256, 1024, 4096])
    ap.add_argument("--dt", type=int, nargs="+", default=[5, 20, 64])
    ap.add_argument("--packets", type=int, default=20, help="packets per sample")
    ap.add_argument("--min-addr", type=int, default=16)
    a = ap.parse_args()
    if a.quick:
        a.T, a.dt, a.packets = [1024], [20], 3
    samples = C.load_samples(a.dataset, a.data, limit=a.limit or (3 if a.quick else 40), seed=a.seed)
    rows, res, skipped = [], [], []
    for T in a.T:
        for dt in a.dt:
            vals = {"plain": [], "V2": [], "shuffle": []}
            groups = {"plain": [], "V2": [], "shuffle": []}
            for ev, _, grp, geom, _ in samples:
                if len(ev) == 0:
                    continue
                for e, v2, sh in packet_views(ev, geom, T, a.packets):
                    for name, seen in (("plain", e), ("V2", v2), ("shuffle", sh)):
                        if seen is None:
                            continue
                        s = score(e, seen, dt, a.min_addr)
                        if s:
                            vals[name].append(s)
                            groups[name].append(grp)
            for name in vals:
                if not vals[name]:
                    skipped.append(f"T {T} µs, dt {dt} µs, {name}")
                    continue
                v = np.asarray(vals[name])
                nr = cluster_bootstrap_ci(v[:, 0], groups[name], n=500, seed=a.seed)
                pe = cluster_bootstrap_ci(v[:, 1], groups[name], n=500, seed=a.seed)
                res.append({"T_us": T, "dt_us": dt, "view": name, "packets": len(v),
                            "clusters": n_clusters(groups[name]), "neighbour_recovery": nr, "procrustes": pe})
                rows.append((T, dt, name, len(v), n_clusters(groups[name]), nr, pe))
    data = {"results": res, "skipped": skipped,
            "meta": C.meta(a, dataset=a.dataset, synthetic=a.data is None, n_keys=1,
                           ci="cluster bootstrap 95 % over recordings, 500 resamples")}
    md = ["# N4b adjacency attack" + (" (synthetic smoke data)" if a.data is None else ""), "",
          "neighbour recovery: fraction of true 4-neighbour pairs found; Procrustes: 0 = layout recovered.", "",
          C.table(["T µs", "dt µs", "view", "packets", "clusters", "neighbour recovery", "Procrustes error"], rows)]
    if skipped:     # e.g. N-MNIST (34 x 34, ~13 events per 1 ms packet): no packet reaches --min-addr addresses
        md += ["", f"No packet with at least {a.min_addr} distinct addresses (--min-addr), so no row for: "
               + "; ".join(skipped) + "."]
    C.write("n4b", "adjacency", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
