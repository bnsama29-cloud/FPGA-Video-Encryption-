"""How expensive is a keyed position permutation of DVS pixel addresses, per design option?

Usage:
    python experiments/neuro/fpe_design_numbers.py [--out sim_out/neuro_fpe]

Paper 2 (event-camera encryption), design note docs/neuro/notes/lit_fpe_crypto.md.
Pure arithmetic, no data, runs in well under a second. For each sensor (W x H) it computes:

  * cycle walking (Black-Rogaway 2002, Method 2) for a binary Feistel domain of N >= k = W*H points:
    exact walk-length law for an ideal random permutation of [0, N) started in M = [0, k):
        P(T > j) = prod_{i=0}^{j-1} (N-k-i) / (N-1-i)        (T = number of cipher calls)
    and E[T] = sum_j P(T > j), checked against the closed form (N+1)/(k+1).
    Two binary domains: "packed" (index y*W+x on the smallest even bit width, balanced halves) and
    "fields" (x on ceil(lg W) bits, y on ceil(lg H) bits, padded to a balanced width).
  * mixed-radix Feistel on Z_W x Z_H (Black-Rogaway Method 3 with a*b = k, Delta = 0): no walking.
  * per-packet round-table size, Ascon fill time (128 keystream bits per 9 clocks, as
    hardware/rtl/ascon_aead128_core.v: p8 per block + 1 handshake clock; +12 clocks p12 init) and a
    RAMB18 count (7-series aspect ratios 16Kx1 .. 512x36), double-buffered.
  * the bias of a table entry drawn as (r * m) >> b from a uniform b-bit r (multiply-shift reduction).
  * data needed by the Durak-Vaudenay (CRYPTO 2017) known-plaintext 4-round attack, N^1.5 (N/2)^(1/6),
    with N the branch size.
  * the number of swap-or-not rounds (Hoang-Morris-Rogaway 2012, eq. 1) for a target CCA advantage.
  * the q at which the Black-Rogaway Theorem 2 (3-round generalized Feistel) bound reaches 1/2.

Writes sim_out/neuro_fpe/fpe_design_numbers.json and .md
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sim_out" / "neuro_fpe"

SENSORS = [  # (name, W, H)
    ("N-MNIST (ATIS crop) 34x34", 34, 34),
    ("DVS128 / DVS Gesture 128x128", 128, 128),
    ("DAVIS346 346x260", 346, 260),
    ("VGA-class 640x480", 640, 480),
    ("HD-class 1280x720", 1280, 720),
]
CLK_HZ = 100e6
ASCON_BITS_PER_BLOCK, ASCON_CLK_PER_BLOCK, ASCON_INIT_CLK = 128, 9, 12
PACKET_S = 1e-3
WALK_K = (1, 2, 3, 4, 8, 16)
ROUNDS = (4, 6, 8, 10)
RAMB18_SHAPES = [(16384, 1), (8192, 2), (4096, 4), (2048, 9), (1024, 18), (512, 36)]


def clog2(v):
    return max(1, math.ceil(math.log2(v)))


def walk_law(N, k, jmax=64):
    """P(T > j) for j = 0..jmax for an ideal permutation of [0,N) started inside [0,k)."""
    p, out = 1.0, [1.0]
    for i in range(jmax):
        if N - k - i <= 0:
            p = 0.0
        else:
            p *= (N - k - i) / (N - 1 - i)
        out.append(p)
    return out


def walk_stats(N, k):
    law = walk_law(N, k, jmax=4096)
    mean = sum(law)
    return {
        "N": N, "k": k, "N_over_k": N / k,
        "E_calls": mean, "E_calls_closed_form": (N + 1) / (k + 1),
        "P_more_than_K_calls": {str(K): law[K] for K in WALK_K},
        "worst_case_calls": N - k + 1,
    }


def ramb18(depth, width):
    best = None
    for d, w in RAMB18_SHAPES:
        n = math.ceil(depth / d) * math.ceil(width / w)
        best = n if best is None else min(best, n)
    return best


def tables_mixed(W, H, r, entry_bits):
    """Round j odd: F_j: Z_H -> Z_W (H entries); even: F_j: Z_W -> Z_H (W entries) (BR Fig. 3, a=W, b=H)."""
    t = []
    for j in range(1, r + 1):
        depth, stored = (H, clog2(W)) if j % 2 else (W, clog2(H))
        t.append((depth, stored, entry_bits))
    return t


def tables_binary(half_bits, r, entry_bits):
    return [(1 << half_bits, half_bits, entry_bits) for _ in range(r)]


def table_cost(tables):
    draw_bits = sum(d * e for d, _, e in tables)
    stored_bits = sum(d * s for d, s, _ in tables)
    blocks = math.ceil(draw_bits / ASCON_BITS_PER_BLOCK)
    clocks = ASCON_INIT_CLK + blocks * ASCON_CLK_PER_BLOCK
    bram = sum(ramb18(d, s) for d, s, _ in tables)
    return {
        "keystream_bits": draw_bits, "stored_bits": stored_bits, "ascon_blocks": blocks,
        "fill_clocks": clocks, "fill_us_at_100MHz": clocks / CLK_HZ * 1e6,
        "fill_share_of_1ms_packet": clocks / (CLK_HZ * PACKET_S),
        "ramb18_single": bram, "ramb18_double_buffered": 2 * bram,
    }


def mulshift_bias(m, b):
    """Total-variation distance of (r*m)>>b, r uniform on [0,2^b), from uniform on [0,m)."""
    R = 1 << b
    lo, hi = R // m, R // m + 1
    n_hi = R - lo * m  # values that get hi preimages
    return 0.5 * (n_hi * abs(hi / R - 1 / m) + (m - n_hi) * abs(lo / R - 1 / m))


def dv_kpa_4round(N):
    return N ** 1.5 * (N / 2) ** (1 / 6)


def swap_or_not_rounds(N, q, target):
    """Smallest R with 8 N^1.5/(R+4) * ((q+N)/(2N))^(R/4+1) <= target (HMR 2012, eq. 1)."""
    R = 4
    while R < 100000:
        if 8 * N ** 1.5 / (R + 4) * ((q + N) / (2 * N)) ** (R / 4 + 1) <= target:
            return R
        R += 4
    return None


def br3_q_half(W, H):
    """q where (q+Delta)^2/2^(n+1) * (ceil(2^n/a)+ceil(2^n/b)) = 1/2, Delta = 0, smallest n with 2^n > a, b."""
    n = clog2(max(W, H) + 1)
    c = (math.ceil(2 ** n / W) + math.ceil(2 ** n / H)) / 2 ** (n + 1)
    return {"n": n, "q_at_adv_half": math.sqrt(0.5 / c)}


def fisher_yates(k):
    """Full per-packet random permutation table (Black-Rogaway Method 1 in spirit, built by a Knuth shuffle).
    Assumes one swap per clock (dual-port RAM) and a (lg k + 16)-bit multiply-shift draw per step."""
    w = clog2(k)
    draw = (k - 1) * (w + 16)
    blocks = math.ceil(draw / ASCON_BITS_PER_BLOCK)
    ascon_clk = ASCON_INIT_CLK + blocks * ASCON_CLK_PER_BLOCK
    shuffle_clk = k - 1
    return {"table_bits": k * w, "ramb18_single": ramb18(k, w), "ramb18_double_buffered": 2 * ramb18(k, w),
            "keystream_bits": draw, "ascon_clocks": ascon_clk, "shuffle_clocks": shuffle_clk,
            "share_of_1ms_packet": max(ascon_clk, shuffle_clk) / (CLK_HZ * PACKET_S),
            "zynq7020_ramb18_total": 280}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    res = {"meta": {"source": "experiments/neuro/fpe_design_numbers.py", "clk_hz": CLK_HZ,
                    "ascon": f"{ASCON_BITS_PER_BLOCK} bits / {ASCON_CLK_PER_BLOCK} clk + {ASCON_INIT_CLK} init",
                    "packet_s": PACKET_S}, "sensors": []}
    for name, W, H in SENSORS:
        k = W * H
        bx, by = clog2(W), clog2(H)
        packed_half = math.ceil(clog2(k) / 2)
        fields_half = max(bx, by)
        s = {"name": name, "W": W, "H": H, "k": k, "x_bits": bx, "y_bits": by,
             "walk_packed_balanced": walk_stats(1 << (2 * packed_half), k) | {"half_bits": packed_half},
             "walk_fields_balanced": walk_stats(1 << (2 * fields_half), k) | {"half_bits": fields_half},
             "walk_fields_unbalanced": walk_stats(1 << (bx + by), k),
             "mixed_radix": {}, "binary_packed": {},
             "mulshift_bias_16bit": {"to_W": mulshift_bias(W, 16), "to_H": mulshift_bias(H, 16)},
             "dv_kpa_4round_known_pairs": {"mixed_branch_sqrt_k": dv_kpa_4round(math.sqrt(k)),
                                           "mixed_share_of_codebook": dv_kpa_4round(math.sqrt(k)) / k,
                                           "binary_branch": dv_kpa_4round(1 << packed_half)},
             "br_thm2_3round": br3_q_half(W, H),
             "fisher_yates_table": fisher_yates(k),
             "swap_or_not_rounds_adv_2^-30": {f"q=N/{d}": swap_or_not_rounds(k, k / d, 2 ** -30)
                                               for d in (100, 10, 2)}}
        for r in ROUNDS:
            s["mixed_radix"][str(r)] = {
                "entry_bits_exact": table_cost([(d, st, st) for d, st, _ in tables_mixed(W, H, r, 0)]),
                "entry_bits_16_mulshift": table_cost(tables_mixed(W, H, r, 16)),
            }
            s["binary_packed"][str(r)] = table_cost(tables_binary(packed_half, r, packed_half))
        res["sensors"].append(s)

    (a.out / "fpe_design_numbers.json").write_text(json.dumps(res, indent=1))

    L = ["# FPE design numbers (experiments/neuro/fpe_design_numbers.py)", "",
         "## Cycle walking, ideal permutation: E[calls] and P(more than K calls)", "",
         "| sensor | domain | N/k | E[calls] | P(>1) | P(>2) | P(>4) | P(>8) | P(>16) |", "|---|---|---|---|---|---|---|---|---|"]
    for s in res["sensors"]:
        for key, lab in (("walk_packed_balanced", "packed y*W+x, balanced"),
                         ("walk_fields_unbalanced", "x,y fields, unbalanced"),
                         ("walk_fields_balanced", "x,y fields, balanced")):
            w = s[key]
            P = w["P_more_than_K_calls"]
            L.append(f"| {s['name']} | {lab} 2^{int(math.log2(w['N']))} | {w['N_over_k']:.3f} | {w['E_calls']:.3f} | "
                     f"{P['1']:.3g} | {P['2']:.3g} | {P['4']:.3g} | {P['8']:.3g} | {P['16']:.3g} |")
        L.append(f"| {s['name']} | mixed radix Z_W x Z_H | 1.000 | 1.000 | 0 | 0 | 0 | 0 | 0 |")
    L += ["", "## Per-packet round tables (Ascon fill, RAMB18 double-buffered)", "",
          "| sensor | scheme | rounds | keystream bits | fill clk | fill us | share of 1 ms | RAMB18 x2 |",
          "|---|---|---|---|---|---|---|---|"]
    for s in res["sensors"]:
        for r in ROUNDS:
            for lab, c in (("mixed, exact-width draw", s["mixed_radix"][str(r)]["entry_bits_exact"]),
                           ("mixed, 16-bit draw", s["mixed_radix"][str(r)]["entry_bits_16_mulshift"]),
                           ("binary packed", s["binary_packed"][str(r)])):
                L.append(f"| {s['name']} | {lab} | {r} | {c['keystream_bits']} | {c['fill_clocks']} | "
                         f"{c['fill_us_at_100MHz']:.1f} | {100 * c['fill_share_of_1ms_packet']:.2f} % | {c['ramb18_double_buffered']} |")
    L += ["", "## Attack / bound numbers", "",
          "| sensor | DV17 4-round KPA pairs (mixed) | share of k | (binary) | BR02 Thm2 q@adv=1/2 | SoN rounds q=N/100 | N/10 | N/2 | mulshift TV to W | to H |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s in res["sensors"]:
        d, so = s["dv_kpa_4round_known_pairs"], s["swap_or_not_rounds_adv_2^-30"]
        L.append(f"| {s['name']} | {d['mixed_branch_sqrt_k']:.3g} | {100 * d['mixed_share_of_codebook']:.1f} % | {d['binary_branch']:.3g} | "
                 f"{s['br_thm2_3round']['q_at_adv_half']:.1f} | {so['q=N/100']} | {so['q=N/10']} | {so['q=N/2']} | "
                 f"{s['mulshift_bias_16bit']['to_W']:.2e} | {s['mulshift_bias_16bit']['to_H']:.2e} |")
    L += ["", "## Full random permutation table per packet (Knuth shuffle), xc7z020 has 280 RAMB18", "",
          "| sensor | table bits | RAMB18 x2 | Ascon clk | shuffle clk | share of 1 ms |", "|---|---|---|---|---|---|"]
    for s in res["sensors"]:
        f = s["fisher_yates_table"]
        L.append(f"| {s['name']} | {f['table_bits']} | {f['ramb18_double_buffered']} | {f['ascon_clocks']} | "
                 f"{f['shuffle_clocks']} | {100 * f['share_of_1ms_packet']:.1f} % |")
    md = "\n".join(L) + "\n"
    (a.out / "fpe_design_numbers.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
