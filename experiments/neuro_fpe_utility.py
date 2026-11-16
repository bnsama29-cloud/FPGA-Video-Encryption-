"""N11: is format preservation (V1-V3) worth its cost compared with V4 + padding?

Usage:
    python experiments/neuro_fpe_utility.py [--dataset dvsgesture --data <root>] [--quick]

Method (DESIGN §1.6, §8.2 N11):
  (a) bandwidth: bytes of the plain EVT 2.0 payload and of the V1/V2/V3 payloads after a general-purpose
      compressor (zstd if installed, else lzma and zlib from the standard library, labelled), and of V4 (which
      does not compress); and of the plain and V1-V3 events re-encoded as EVT 3.0 by expelliarmus (evt3_bytes; the
      keyless events, time-sorted for every view alike as EVT 3.0 needs a monotone clock).
  (b) keyless function: activity / wake-up detection by an untrusted node from what each packet shows without the
      key. Streams alternate idle stretches (sparse uniform background events, 2 kev/s) and active stretches (the
      dataset's recordings); a packet is "active" if it lies in an active stretch. Detector score per packet:
      the CD count of the extracted payload (V1-V3), the packet length (V4), the padded packet length (V3 and V4
      with floor / ladder padding). AUC against the active labels, compared with the same detector on plaintext.
      Pass criterion fixed in §8.1: some keyless function with AUC within 0.05 of plaintext for V1-V3 **and**
      lost by V4 + padding; otherwise V1-V3 are reframed as "compatible transport".
  (c) reader compatibility: copied from N8-R (sim_out/neuro/n8/perm_strength.json) when present.
Writes sim_out/neuro/n11/fpe_utility.{json,md}.
"""
import argparse
import json
import lzma
import zlib

import numpy as np

import neuro_common as C
from neuro import evt2
from neuro.packet import PacketHeader
from neuro.pad import FLOOR, LADDER, PadPolicy


def compressors():
    out = {"lzma": lambda b: len(lzma.compress(b, preset=6)), "zlib": lambda b: len(zlib.compress(b, 9))}
    try:
        import zstandard
        out["zstd-19"] = lambda b: len(zstandard.ZstdCompressor(level=19).compress(b))
    except ImportError:
        pass
    return out


def bandwidth(samples):
    comp = compressors()
    tot = {"plain": {k: 0 for k in comp} | {"raw": 0}}
    for level in (1, 2, 3, 4):
        tot[f"V{level}"] = {k: 0 for k in comp} | {"raw": 0}
    for ev, _, _, geom, _ in samples:
        w = evt2.encode(ev, 1024).astype("<u4").tobytes()
        tot["plain"]["raw"] += len(w)
        for k, f in comp.items():
            tot["plain"][k] += f(w)
        for level in (1, 2, 3, 4):
            pk = C.protect(ev, geom, level, 1024)
            if level == 4:
                b = b"".join(pk)
            else:
                b = np.concatenate([pl for _, pl in C.keyless_payloads(pk) if pl is not None and len(pl)]
                                   ).astype("<u4").tobytes()
            tot[f"V{level}"]["raw"] += len(b)
            for k, f in comp.items():
                tot[f"V{level}"][k] += f(b)
    return tot


def evt3_bytes(samples):
    """Bytes of each sample's events written as EVT 3.0 by expelliarmus (an independent Prophesee-format writer), plain
    and V1-V3 keyless events (sum over samples). EVT 3.0 codes addresses relative to the previous event, so it rewards
    the locality that V2/V3 remove. Before 17 Nov the table printed a placeholder instead (TESTING bug #74)."""
    try:
        from expelliarmus import Wizard
    except ImportError:
        return "not run: expelliarmus not installed"
    import os
    import tempfile
    wz, tot = Wizard(encoding="evt3"), {v: 0 for v in ("plain", "V1", "V2", "V3")}
    tmp = tempfile.TemporaryDirectory()
    f = os.path.join(tmp.name, "n11_evt3.raw")
    for ev, _, _, geom, _ in samples:
        for v in tot:
            e = ev if v == "plain" else C.keyless_events(C.protect(ev, geom, int(v[1]), 1024))
            if not len(e):
                continue
            wz.save(f, np.sort(e, order="t", kind="stable"))
            tot[v] += os.path.getsize(f)
    tmp.cleanup()
    return tot


def idle(geom, t0, dur_us, rate_hz, seed):
    rng = np.random.default_rng(seed)
    n = max(1, int(dur_us * rate_hz / 1e6))
    e = np.zeros(n, dtype=evt2.EVENT_DTYPE)
    e["t"] = np.sort(rng.integers(t0, t0 + dur_us, n))
    e["x"], e["y"], e["p"] = rng.integers(0, geom.W, n), rng.integers(0, geom.H, n), rng.integers(0, 2, n)
    return e


def mixed_stream(samples, seed, idle_us=40_000):
    """Idle / active alternation; returns (events, [(start, end) of active stretches])."""
    parts, active, t = [], [], 10_000
    geom = samples[0][3]
    for i, (ev, *_rest) in enumerate(samples):
        parts.append(idle(geom, t, idle_us, 2000, seed + i))
        t += idle_us
        if len(ev):
            e = ev.copy()
            e["t"] = e["t"] - e["t"].min() + t
            dur = int(e["t"].max() - t) + 1
            parts.append(e)
            active.append((t, t + dur))
            t += dur
    return np.concatenate(parts), active, geom


def auc(scores, labels):
    s, y = np.asarray(scores, float), np.asarray(labels, bool)
    if y.all() or not y.any():
        return float("nan")
    from scipy.stats import rankdata
    r = rankdata(s)
    n1 = y.sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1)))


def activity(samples, seed, T=1024):
    ev, active, geom = mixed_stream(samples, seed)
    configs = [("plain", None, None), ("V1", 1, None), ("V2", 2, None), ("V3", 3, None), ("V4", 4, None),
               ("V3 + pad floor 8", 3, PadPolicy(FLOOR, 8)), ("V3 + pad ladder 2..64", 3, PadPolicy(LADDER, 2, 64)),
               ("V4 + pad floor 8", 4, PadPolicy(FLOOR, 8)), ("V4 + pad ladder 2..64", 4, PadPolicy(LADDER, 2, 64))]
    out = {}
    pk_plain = C.protect(ev, geom, 0, T)
    for name, level, pad in configs:
        pk = pk_plain if level is None else C.protect(ev, geom, level, T, pad=pad)
        scores, labels = [], []
        for raw in pk:
            h = PacketHeader.unpack(raw)
            mid = h.t_start + h.T_us // 2
            labels.append(any(a <= mid < b for a, b in active))
            if level is None or (level in (1, 2, 3) and pad is None):
                p = C.keyless_payloads([raw])[0][1]
                scores.append(int(evt2.is_cd(p).sum()))
            else:
                scores.append(len(raw))
        out[name] = auc(scores, labels)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    a = ap.parse_args()
    samples = C.load_samples(a.dataset, a.data, limit=a.limit or (4 if a.quick else 40), seed=a.seed)
    data = {"bandwidth_bytes": bandwidth(samples[:2] if a.quick else samples),
            "activity_auc": activity(samples, a.seed),
            "evt3": evt3_bytes(samples[:2] if a.quick else samples)}
    n8 = C.OUT / "n8" / "perm_strength.json"
    data["readers"] = json.loads(n8.read_text())["readers"] if n8.exists() else "run N8 first"
    pa = data["activity_auc"]["plain"]
    keep = [k for k in ("V1", "V2", "V3") if abs(data["activity_auc"][k] - pa) <= 0.05]
    lost = [k for k in data["activity_auc"] if k.startswith("V4 + pad") and data["activity_auc"][k] < pa - 0.05]
    data["criterion"] = {"kept_by": keep, "lost_by_V4_pad": lost,
                         "fpe_worth_it": bool(keep and lost),
                         "rule": "AUC within 0.05 of plaintext for V1-V3 and lost (> 0.05 lower) by V4 + padding"}
    data["meta"] = C.meta(a, dataset=a.dataset, synthetic=a.data is None, n_keys=1,
                          compressors=list(compressors()))
    bw = data["bandwidth_bytes"]
    cols = list(next(iter(bw.values())))
    md = ["# N11 FPE utility" + (" (synthetic smoke data)" if a.data is None else ""), "",
          "(a) Bytes (sum over samples):", "", C.table(["payload"] + cols, [(k, *v.values()) for k, v in bw.items()]),
          "", "(b) Activity detection AUC from what a packet shows without the key:", "",
          C.table(["view", "AUC"], list(data["activity_auc"].items())), "",
          f"Criterion: kept by {keep or 'none'}; lost by V4 + padding: {lost or 'none'} -> "
          f"{'FPE worth it' if data['criterion']['fpe_worth_it'] else 'reframe V1-V3 as compatible transport'}.",
          "", "EVT 3.0 bytes (expelliarmus writer, sum over samples): " + (
              ", ".join(f"{k} {v}" for k, v in data["evt3"].items()) if isinstance(data["evt3"], dict) else data["evt3"])]
    C.write("n11", "fpe_utility", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
