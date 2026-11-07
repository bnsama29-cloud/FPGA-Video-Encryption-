"""N8: does the V2/V3 permutation behave as specified, and can standard readers take the protected payload?

Usage:
    python experiments/neuro_perm_strength.py [--dataset dvsgesture --data <root>] [--quick]

Method (DESIGN §4.3, §8.2 N8):
  * inverse exactness over all W*H points for every sensor of §2.3 plus 16 x 16 and 1280 x 16 (the 16 x 1280
    domain with H <= MAXH), several packets each; refusal below 16;
  * table bias: empirical total-variation distance of table entries from uniform vs the multiply-shift bound of
    script (a) (experiments/neuro/fpe_design_numbers.py);
  * cross-packet independence: correlation of P_ctr(x, y) and P_ctr+1(x, y) over all points;
  * known plaintext available in real packets: distinct (x, y) addresses per packet (what an attacker who knows
    the scene, e.g. hot pixels, could pair with ciphertext) against the Durak-Vaudenay 4-round data requirement
    N^1.5 (N/2)^(1/6), N = sqrt(W H), per sensor and T;
  * round structure (oracle, full codebook of one packet, 34 x 34 and an unbalanced 64 x 16 domain): fraction of
    input pairs differing only in x whose outputs keep the same y, for r = 1, 2, 4, 6, 8, against an ideal random
    permutation (Knuth shuffle, §4.4). This is a structural distinguisher labelled "oracle, not achievable
    in-packet at measured rates"; it is not the Durak-Vaudenay table-recovery attack. No outcome is asserted.
  * N8-R readers: the extracted payloads (no header, trailer or tag) of V1/V2/V3 packets are written to a
    Prophesee RAW file and read back by neuro.evt2.read_raw/decode and, where installed, expelliarmus and Tonic;
    count read back vs n_cd, decode errors, and in-bucket timestamp order (V3).
Writes sim_out/neuro/n8/perm_strength.{json,md} and n8/readers.raw (scratch).
"""
import argparse
import importlib
import math

import numpy as np

import neuro_common as C
from model import ascon
from neuro import evt2, feistel, keys
from neuro.geometry import Geometry, SENSORS
from neuro.keys import nonce

SK = keys.subkeys(C.master(0), C.CAM, C.BOOT, 0)
SID = keys.session_id(C.CAM, C.BOOT, 0)


def all_points(W, H):
    y, x = np.divmod(np.arange(W * H), W)
    return x, y


def inverse_exact(g, n_packets):
    x, y = all_points(g.W, g.H)
    for ctr in range(n_packets):
        t = feistel.make_tables(SK.perm, SID, ctr, g.W, g.H)
        px, py = feistel.permute(x, y, t)
        if not ((0 <= px) & (px < g.W) & (0 <= py) & (py < g.H)).all():
            return False, f"ctr {ctr}: output out of range"
        if len(np.unique(py * g.W + px)) != g.W * g.H:
            return False, f"ctr {ctr}: not a bijection"
        ux, uy = feistel.unpermute(px, py, t)
        if not ((ux == x) & (uy == y)).all():
            i = int(np.argmax((ux != x) | (uy != y)))
            return False, f"ctr {ctr}: first mismatch at point {i} ({x[i]}, {y[i]})"
    return True, ""


def refuses_small():
    out = {}
    for W, H in [(15, 16), (16, 15), (1, 720), (1280, 1)]:
        try:
            feistel.make_tables(SK.perm, SID, 0, W, H)
            out[f"{W}x{H}"] = "accepted (BUG)"
        except ValueError:
            out[f"{W}x{H}"] = "refused"
    return out


def table_bias(g, n_packets):
    """Empirical TV distance from uniform of the entries of even (mod W) tables, vs the analytic bound."""
    M = g.W
    cnt = np.zeros(M)
    for ctr in range(n_packets):
        t = feistel.make_tables(SK.perm, SID, ctr, g.W, g.H)
        for j in range(0, 8, 2):
            cnt += np.bincount(t.t[j], minlength=M)
    p = cnt / cnt.sum()
    tv = 0.5 * np.abs(p - 1 / M).sum()
    n = cnt.sum()
    noise = 0.5 * math.sqrt(M / n) * math.sqrt(2 / math.pi) if n else float("nan")   # E[TV] of a uniform sample
    exact = 0.5 * sum(abs(((((v + 1) << 16) + M - 1) // M - ((v << 16) + M - 1) // M) / 65536 - 1 / M)
                      for v in range(M))
    return {"samples": int(n), "tv_empirical": float(tv), "tv_sampling_noise": float(noise),
            "tv_multiply_shift_exact": float(exact)}


def cross_packet(g):
    x, y = all_points(g.W, g.H)
    a = feistel.permute(x, y, feistel.make_tables(SK.perm, SID, 0, g.W, g.H))
    b = feistel.permute(x, y, feistel.make_tables(SK.perm, SID, 1, g.W, g.H))
    ia, ib = a[1] * g.W + a[0], b[1] * g.W + b[0]
    return float(np.corrcoef(ia, ib)[0, 1])


def dv_requirement(g):
    N = math.sqrt(g.W * g.H)
    return N ** 1.5 * (N / 2) ** (1 / 6)


def known_plaintext(samples, Ts):
    rows = []
    for T in Ts:
        per = []
        for ev, *_ in samples:
            if len(ev) == 0:
                continue
            k = (ev["t"].astype(np.int64) - int(ev["t"][0])) // T
            for kk in np.unique(k):
                e = ev[k == kk]
                per.append(len(np.unique(e["y"].astype(np.int64) * 4096 + e["x"])))
        g = samples[0][3]
        need = dv_requirement(g)
        per = np.asarray(per)
        rows.append({"T_us": T, "packets": int(len(per)), "distinct_median": float(np.median(per)),
                     "distinct_p99": float(np.quantile(per, 0.99)), "distinct_max": int(per.max()),
                     "dv_4round_need": need, "max_over_need": float(per.max() / need)})
    return rows


def round_structure(W, H, rounds=(1, 2, 4, 6, 8), pairs=20000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.integers(0, W, pairs)
    y = rng.integers(0, H, pairs)
    x2 = (x + rng.integers(1, W, pairs)) % W
    ks = ascon.Keystream(SK.perm, nonce(SID, 7, 0))
    full = feistel.table_entries(ks, W, H, 8)
    out = {}
    for r in rounds:
        t = feistel.Tables(W, H, r, full[:r])
        _, ya = feistel.permute(x, y, t)
        _, yb = feistel.permute(x2, y, t)
        out[f"r{r}"] = float((ya == yb).mean())
    perm = feistel.shuffle_table(SK.perm, SID, 7, W, H)
    ia, ib = perm[y * W + x], perm[y * W + x2]
    out["ideal"] = float((ia // W == ib // W).mean())
    out["ideal_expected"] = (W - 1) / (W * H - 1)
    return out


def readers(samples, out_dir):
    """N8-R: extracted payloads of V1/V2/V3 written to RAW and read back."""
    ev, _, _, g, _ = samples[0]
    res = {}
    for level in (1, 2, 3):
        pk = C.protect(ev, g, level, 1024)
        pls = [pl for _, pl in C.keyless_payloads(pk) if pl is not None and len(pl)]
        words = np.concatenate(pls)
        n_cd = int(evt2.is_cd(words).sum())
        path = out_dir / f"readers_v{level}.raw"
        evt2.write_raw(path, words, g)
        w2, g2 = evt2.read_raw(path)
        e2, _ = evt2.decode(w2)
        t = e2["t"].astype(np.int64)
        row = {"n_cd": n_cd, "ours_read": int(len(e2)), "ours_geometry_ok": (g2.W, g2.H) == (g.W, g.H),
               "in_range": bool(((e2["x"] < g.W) & (e2["y"] < g.H)).all()),
               "non_monotone_pairs": int((np.diff(t) < 0).sum()),
               "max_backstep_us": int(max(0, -np.diff(t).min())) if len(t) > 1 else 0}
        for mod in ("expelliarmus", "tonic"):
            try:
                importlib.import_module(mod)
                row[mod] = "installed: run on Kaggle (reader call in kaggle_neuro.py)"
            except ImportError:
                row[mod] = "not installed here"
        res[f"V{level}"] = row
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    a = ap.parse_args()
    out_dir = a.out or C.OUT / "n8"
    out_dir.mkdir(parents=True, exist_ok=True)
    geoms = [SENSORS[n] for n in ("nmnist", "dvsgesture", "davis346", "cif", "vga", "imx636")] + [
        Geometry("16x16", 16, 16), Geometry("1280x16", 1280, 16)]
    if a.quick:
        geoms = [SENSORS["nmnist"], Geometry("16x16", 16, 16), Geometry("1280x16", 1280, 16)]
    npk = 1 if a.quick else 3
    data = {"inverse": {}, "bias": {}, "cross_packet_corr": {}}
    rows = []
    for g in geoms:
        ok, why = inverse_exact(g, npk)
        data["inverse"][g.name] = {"exact": ok, "detail": why, "points": g.W * g.H, "packets": npk}
        data["bias"][g.name] = table_bias(g, 2 if a.quick else 20)
        data["cross_packet_corr"][g.name] = cross_packet(g)
        rows.append((g.name, g.W * g.H, "yes" if ok else f"NO: {why}", data["bias"][g.name]["tv_empirical"],
                     data["bias"][g.name]["tv_sampling_noise"], data["cross_packet_corr"][g.name]))
    data["refusal_below_16"] = refuses_small()
    samples = C.load_samples(a.dataset, a.data, limit=a.limit or (4 if a.quick else 50), seed=a.seed)
    data["known_plaintext"] = known_plaintext(samples, (1024,) if a.quick else (256, 1024, 4096))
    data["round_structure"] = {"34x34": round_structure(34, 34, pairs=2000 if a.quick else 20000),
                               "64x16": round_structure(64, 16, pairs=2000 if a.quick else 20000)}
    data["readers"] = readers(samples, out_dir)
    data["meta"] = C.meta(a, dataset=a.dataset, synthetic=a.data is None, n_keys=1,
                          note="round_structure is an oracle structural distinguisher, not the DV attack")
    md = ["# N8 permutation strength" + (" (synthetic smoke data)" if a.data is None else ""), "",
          C.table(["domain", "points", "inverse exact", "table TV", "TV sampling noise", "corr(P_k, P_k+1)"], rows),
          "", "Refusal below 16: " + ", ".join(f"{k} {v}" for k, v in data["refusal_below_16"].items()), "",
          C.table(["T µs", "packets", "distinct addr median", "p99", "max", "DV 4-round need", "max/need"],
                  [(r["T_us"], r["packets"], r["distinct_median"], r["distinct_p99"], r["distinct_max"],
                    r["dv_4round_need"], r["max_over_need"]) for r in data["known_plaintext"]]), "",
          "Round structure (oracle, full codebook): P(same y | inputs differ only in x)", "",
          C.table(["domain"] + list(data["round_structure"]["34x34"]),
                  [(k,) + tuple(v.values()) for k, v in data["round_structure"].items()]), "",
          C.table(["level", "n_cd", "read back", "in range", "non-monotone pairs", "max back-step µs", "expelliarmus",
                   "tonic"], [(k, v["n_cd"], v["ours_read"], v["in_range"], v["non_monotone_pairs"],
                               v["max_backstep_us"], v["expelliarmus"], v["tonic"])
                              for k, v in data["readers"].items()])]
    C.write("n8", "perm_strength", data, "\n".join(md), out_dir)


if __name__ == "__main__":
    main()
