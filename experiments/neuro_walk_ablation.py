"""N2b (model part): what would cycle walking cost instead of the mixed-radix Feistel?

Usage:
    python experiments/neuro_walk_ablation.py [--keys 16] [--quick]

Method (DESIGN §4.3.4, §8.2 N2b), fixed before the run:
  * For every sensor geometry W x H of §2.3 and both binary domains of neuro.feistel.walk_domain ("pow2", the
    smallest binary domain containing W x H, i.e. the fair baseline; "balanced", 2^h x 2^h), and for --keys
    independent packet counters: walk *every* point of W x H through the eight-round binary table Feistel
    (same Ascon keystream and fill order as the product) and count cipher passes until the result is in range.
    Every address is walked, so the statistics are exact for each key; no event data is needed, because which
    addresses an event stream touches does not change the per-address walk length distribution.
  * Report per geometry and domain: mean passes, 99th and 99.9th percentile, maximum, the fraction of addresses
    that need more than K passes for K = 1..8, and the expected extra passes beyond K, E[max(0, calls - K)].
  * Hardware cost model of the K-unrolled ablation nv_feistel_walk (DESIGN §4.3.4): every word takes K passes
    (K x 16 clk latency); a word still out of range freezes the pipeline while a side unit finishes it at
    PASS_CLK clk per extra pass plus SIDE_OVH clk. Dense input (one CD word per clock) then sustains
    1 / (1 + E[stall]) words per clock, against exactly 1 for the mixed-radix stage. The worst case per word
    is unbounded; the maximum observed is reported.
  * Table memory: 4 (Wb + Hb) entries per packet against 4 (W + H), and the fill time of neuro.cycle_model.
Writes sim_out/neuro/n2b/walk_stats.{json,md}.
"""
import argparse

import numpy as np

import neuro_common as C
from neuro import cycle_model, feistel, keys
from neuro.geometry import SENSORS

SK = keys.subkeys(C.master(0), C.CAM, C.BOOT, 0)
SID = keys.session_id(C.CAM, C.BOOT, 0)
KS = tuple(range(1, 9))
K_RTL = 4            # unrolled passes in nv_feistel_walk (DESIGN §4.3.4)
PASS_CLK = 16        # one eight-round pass, 2 clk per round (as nv_feistel)
SIDE_OVH = 1         # frozen clock that hands the word to the side unit (nv_feistel_walk, checked by its tb)


def walk_lengths(W, H, ctr, domain):
    """Passes needed by every address of W x H for packet ctr (exact, all W*H points)."""
    tb, dom = feistel.walk_tables(SK.perm, SID, ctr, W, H, domain=domain)
    y, x = np.divmod(np.arange(W * H, dtype=np.int64), W)
    px, py, calls = feistel.walk_calls(x, y, tb, W, H)
    codes = py * W + px
    if len(np.unique(codes)) != W * H:          # the walk must be a bijection of W x H
        raise AssertionError(f"walk on {W}x{H} ({domain}, ctr {ctr}) is not a bijection")
    return calls, dom


def summarise(calls, K_rtl=K_RTL):
    c = calls.astype(np.float64)
    extra = {K: float(np.mean(np.maximum(0, c - K))) for K in KS}
    stall = PASS_CLK * extra[K_rtl] + SIDE_OVH * float(np.mean(c > K_rtl))
    return {
        "mean": float(c.mean()), "p99": float(np.percentile(c, 99)), "p999": float(np.percentile(c, 99.9)),
        "max": int(c.max()),
        "frac_gt": {K: float(np.mean(c > K)) for K in KS},
        "extra_beyond": extra,
        "rtl_stall_clk_per_word": stall,
        "rtl_dense_words_per_clk": 1.0 / (1.0 + stall),
    }


def run(geoms, domains, n_keys):
    rows, out = [], {}
    for g in geoms:
        for dom in domains:
            per_key = [walk_lengths(g.W, g.H, ctr, dom) for ctr in range(n_keys)]
            Wb, Hb = per_key[0][1]
            allc = np.concatenate([c for c, _ in per_key])
            s = summarise(allc)
            s["per_key_mean"] = [float(c.mean()) for c, _ in per_key]
            s["per_key_max"] = [int(c.max()) for c, _ in per_key]
            s.update(domain=[Wb, Hb], ratio=Wb * Hb / (g.W * g.H), table_entries=4 * (Wb + Hb),
                     table_entries_mixed=4 * (g.W + g.H), fill_clk=cycle_model.fill_clk(Wb, Hb),
                     fill_clk_mixed=cycle_model.fill_clk(g.W, g.H))
            out[f"{g.name}/{dom}"] = s
            rows.append((g.name, f"{g.W}x{g.H}", dom, f"{Wb}x{Hb}", round(s["ratio"], 3), round(s["mean"], 3),
                         s["p99"], s["max"], round(s["frac_gt"][K_RTL], 4), round(s["rtl_dense_words_per_clk"], 3),
                         f"{s['table_entries']} / {s['table_entries_mixed']}"))
    return out, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--keys", type=int, default=16, help="independent packet counters per geometry")
    ap.add_argument("--quick", action="store_true", help="small geometries and 2 keys (smoke test)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    names = ("nmnist", "dvsgesture") if args.quick else ("nmnist", "dvsgesture", "davis346", "cif", "vga", "imx636")
    geoms = [SENSORS[n] for n in names]
    n_keys = 2 if args.quick else args.keys
    stats, rows = run(geoms, feistel.WALK_DOMAINS[::-1], n_keys)
    data = {"meta": C.meta(args, K_rtl=K_RTL, pass_clk=PASS_CLK, side_ovh=SIDE_OVH, keys=n_keys), "stats": stats}
    md = ["# N2b (model): cycle walking on a binary domain vs the mixed-radix Feistel", "",
          f"All W*H addresses walked for {n_keys} packet keys per row. Mixed-radix Feistel: 1 pass, 1 word/clk.",
          f"RTL model: K = {K_RTL} unrolled passes, {PASS_CLK} clk per extra pass + {SIDE_OVH} clk side-unit overhead.",
          "", C.table(["sensor", "W x H", "domain", "binary", "ratio", "mean passes", "p99", "max",
                       f"frac > {K_RTL}", "dense words/clk", "table entries walk / mixed"], rows)]
    C.write("n2b", "walk_stats", data, "\n".join(md), out=args.out)
    return data


if __name__ == "__main__":
    main()
