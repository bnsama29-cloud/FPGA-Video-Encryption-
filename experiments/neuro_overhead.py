"""N9: what do packets cost in bytes, latency and FIFO depth at real event rates, and what does software cost?

Usage:
    python experiments/neuro_overhead.py [--dataset dvsgesture --data <root>] [--T 256 512 1024 4096] [--quick]
    (run the same script on the PYNQ-Z2 ARM for the ARM software column: --sw-only)

Method (DESIGN §8.2 N9):
  * event-rate distribution per dataset: events per 10 µs, 100 µs and 1 ms window (median, p99, max);
  * overhead bytes per event at the median and p99 rate for each T: header 48 + trailer 12 + tag 16 = 76 B per
    packet (+ bitmap and dummies with padding, measured by sealing real streams), against the 4 B payload word;
  * cycle model (neuro.cycle_model, checked against the RTL in N1): timed replay of the traces for U in
    {1, 2, 4}: authenticated latency (median, p99, ms), FIFO high-water mark, input backlog, and the
    maximum-rate replay throughput (words/clk), which at V2/V3 is bounded by the table fill (§6.3);
  * software cost: µs per event of our sender (model, Python) and of the Du / Zhang reimplementations in the same
    Python on the same machine (labelled with the machine). Du's own published numbers (0.20 µs/event on a
    Raspberry Pi 4B, BASELINES.md §1.4) are quoted separately, never mixed into this table.
Writes sim_out/neuro/n9/overhead.{json,md}.
"""
import argparse
import platform
import time

import numpy as np

import neuro_common as C
from neuro import cycle_model as CM
from neuro.pad import FLOOR, LADDER, PadPolicy

HDR_TRL_TAG = 48 + 12 + 16


def rates(samples, win_us):
    r = []
    for ev, *_ in samples:
        if len(ev) == 0:
            continue
        t = ev["t"].astype(np.int64) - int(ev["t"][0])
        r.append(np.bincount(t // win_us) * (1e6 / win_us))      # events/s
    return np.concatenate(r) if r else np.zeros(1)


def overhead_rows(samples, Ts, pads):
    rows = []
    n_ev = sum(len(s[0]) for s in samples)
    for T in Ts:
        for name, level, pad in pads:
            total = 0
            for ev, _, _, geom, _ in samples:
                total += sum(len(p) for p in C.protect(ev, geom, level, T, pad=pad))
            rows.append({"T_us": T, "config": name, "bytes_per_event": total / max(1, n_ev),
                         "overhead_vs_4B": total / max(1, n_ev) / 4 - 1})
    return rows


def cycle_rows(samples, Ts, Us, level=3):
    rows = []
    for T in Ts:
        pk_all = []
        for ev, _, _, geom, _ in samples:
            pk_all.append((CM.packets_from_sender(C.protect(ev, geom, level, T), T), geom))
        for U in Us:
            lat, fifo, back, thr = [], 0, 0, []
            for pk, geom in pk_all:
                r = CM.replay(pk, level, U, geom.W, geom.H, timed=True)
                lat.extend((r.latency / 100.0).tolist())                  # clk at 100 MHz -> µs
                fifo, back = max(fifo, r.fifo_max), max(back, r.backlog_max)
                thr.append(CM.replay(pk, level, U, geom.W, geom.H, timed=False).throughput)
            # finalisation: packet end -> tag; worst case for an event: its packet's start -> tag (= T + fin.)
            rows.append({"T_us": T, "U": U, "finalisation_us_median": float(np.median(lat)),
                         "finalisation_us_p99": float(np.quantile(lat, 0.99)),
                         "auth_latency_worst_ms_p99": (T + float(np.quantile(lat, 0.99))) / 1000,
                         "fifo_max_words": fifo,
                         "input_backlog_max": back, "max_rate_words_per_clk": float(np.median(thr))})
    return rows


def sw_cost(samples, reps=1):
    ev, _, _, geom, _ = samples[0]
    n = len(ev)
    out = {}

    def timeit(fn):
        best = float("inf")
        for _ in range(reps):
            t0 = time.perf_counter()
            fn()
            best = min(best, time.perf_counter() - t0)
        return 1e6 * best / max(1, n)

    for level in (1, 2, 3, 4):
        out[f"ours V{level} (model)"] = timeit(lambda: C.protect(ev, geom, level, 1024))
    du = C.baseline("du2021")
    if du:
        k = du.DuKey.from_seed(b"n9")
        out["Du 2021 (own 2D-SIMM)"] = timeit(lambda: du.encrypt(ev, geom.W, geom.H, k))
        out["Du 2021 (Ascon-keyed)"] = timeit(lambda: du.encrypt(ev, geom.W, geom.H, ascon_keyed=True,
                                                                 ascon_key=bytes(16)))
    zh = C.baseline("zhang2024")
    if zh:
        out["Zhang 2024"] = timeit(lambda: zh.encrypt(ev, geom.W, geom.H, bytes(16)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--T", type=int, nargs="+", default=[256, 512, 1024, 4096])
    ap.add_argument("--U", type=int, nargs="+", default=[1, 2, 4])
    ap.add_argument("--sw-only", action="store_true", help="only the software-cost table (ARM run)")
    a = ap.parse_args()
    if a.quick:
        a.T, a.U = [1024], [2]
    samples = C.load_samples(a.dataset, a.data, limit=a.limit or (3 if a.quick else 30), seed=a.seed)
    data = {"machine": f"{platform.machine()} {platform.processor()} {platform.python_implementation()} "
                       f"{platform.python_version()}"}
    data["software_us_per_event"] = sw_cost(samples, reps=1 if a.quick else 3)
    md = ["# N9 overhead" + (" (synthetic smoke data)" if a.data is None else ""), "",
          f"Software cost on {data['machine']} (µs per event, same Python for every scheme):", "",
          C.table(["scheme", "µs/event"], list(data["software_us_per_event"].items())), "",
          "Du 2021's own figure (0.20 µs/event, Raspberry Pi 4B, score 8.4) is quoted separately (BASELINES.md §1.4)."]
    if not a.sw_only:
        data["rates"] = {}
        rrows = []
        for w in (10, 100, 1000):
            r = rates(samples, w)
            data["rates"][f"{w}us"] = {"median": float(np.median(r)), "p99": float(np.quantile(r, 0.99)),
                                       "max": float(r.max())}
            rrows.append((f"{w} µs", *data["rates"][f"{w}us"].values()))
        pads = [("V3", 3, None), ("V3 + pad floor 4", 3, PadPolicy(FLOOR, 4)),
                ("V3 + pad ladder 2..64", 3, PadPolicy(LADDER, 2, 64)), ("V4", 4, None)]
        data["bytes"] = overhead_rows(samples, a.T, pads if not a.quick else pads[:2])
        data["cycle_model"] = cycle_rows(samples, a.T, a.U)
        data["fixed_bytes_per_packet"] = HDR_TRL_TAG
        md += ["", "Event rate (events/s) per window:", "",
               C.table(["window", "median", "p99", "max"], rrows), "",
               f"Fixed cost per packet: {HDR_TRL_TAG} B (header 48 + trailer 12 + tag 16).", "",
               C.table(["T µs", "config", "bytes/event", "overhead vs 4 B"],
                       [(r["T_us"], r["config"], r["bytes_per_event"], r["overhead_vs_4B"]) for r in data["bytes"]]),
               "", "Cycle model (V3, 100 MHz, timed replay; max-rate replay throughput separately):", "",
               C.table(["T µs", "U", "finalisation µs median", "p99 µs", "auth latency worst ms (p99)", "FIFO max words",
                        "input backlog",
                        "max-rate words/clk"], [tuple(r.values()) for r in data["cycle_model"]])]
    data["meta"] = C.meta(a, dataset=a.dataset, synthetic=a.data is None, n_keys=1,
                          note="cycle model is an estimate checked against RTL CYCLES in N1")
    C.write("n9", "overhead", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
