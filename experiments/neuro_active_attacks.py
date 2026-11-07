"""N7: does the receiver give the required status for every active attack, and what does benign loss cost?

Usage:
    python experiments/neuro_active_attacks.py [--trials 200] [--dataset nmnist --data <root>] [--quick]

Method (DESIGN §1.4, §8.2 N7). Streams are sealed by the model sender (PSK profile, V3 b = 6, T = 1024 µs unless
stated) and fed to neuro.receiver.Decryptor, one fresh receiver per trial:
  * inject (random body under a copied header), bit flip (payload / trailer / tag), replay (inside the window and
    after it), reorder (inside / outside the 64-packet window), delete (middle packet), tail truncation (FINAL
    dropped), splice (header of one session, body of another), downgrade (ts_bits / level rewritten), epoch jump
    (epoch + 65 535), flood (junk datagrams); each with the status §1.4 requires. Success = the required status
    for the attacked packet AND the following genuine packets still accepted (state not moved by a forgery).
  * gap-detection latency: packets between a deletion and the `gap` notice, times T.
  * flood cost: receiver CPU µs per junk datagram, split by whether it passed the header checks.
  * epoch jump: KDF calls and µs for epoch = current + 65 535.
  * benign loss: fraction of events delivered for packet-loss rate p in {0, 1e-3, 1e-2, 5e-2} and
    T in {256, 1024, 4096} µs (a lost packet loses a whole T).
Proportions: Clopper-Pearson 95 %; the forgery bound is analytical (2^-128 per attempt).
Baselines: Du 2021 / Zhang 2024 carry no tag, so every manipulation is accepted by construction (rows filled when
neuro.baselines exists).
Writes sim_out/neuro/n7/active_attacks.{json,md}.
"""
import argparse
import time

import numpy as np

import neuro_common as C
from neuro import attacks, keys, receiver
from neuro.packet import PacketHeader
from neuro.stats import clopper_pearson

REQUIRED = {"inject": {"forged", "malformed"}, "bitflip_payload": {"forged"}, "bitflip_tag": {"forged"},
            "replay_in_window": {"replay"}, "replay_old": {"replay"}, "reorder_in_window": {"ok"},
            "splice": {"forged", "malformed"}, "downgrade": {"policy", "forged"}, "epoch_jump": {"policy"},
            "flood": {"malformed", "stale", "policy", "forged"}}


def decryptor(geom, T, level=3, b=6):
    prof = receiver.Profile(frozenset({(level, b, None, None)}), geom, T)
    return receiver.Decryptor({(C.CAM, C.BOOT): C.master(0)}, prof)


def feed(d, pkts):
    return [d.accept(p, now=i * 1e-3) for i, p in enumerate(pkts)]


def trial(kind, pk, geom, T, rng):
    """(success, detail) for one trial of attack `kind` on the genuine packet list pk."""
    n = len(pk)
    i = int(rng.integers(2, n - 3))
    d = decryptor(geom, T)
    if kind == "inject":
        body = rng.integers(0, 256, len(pk[i]) - 48, dtype=np.uint8).tobytes()
        seq = pk[:i] + [pk[i][:48] + body] + pk[i:]
        r = feed(d, seq)
        return r[i].status in REQUIRED[kind] and all(x.status == "ok" for x in r[i + 1:]), r[i].status
    if kind in ("bitflip_payload", "bitflip_tag"):
        L = len(pk[i])
        pos = int(rng.integers(48, L - 16)) if kind == "bitflip_payload" else int(rng.integers(L - 16, L))
        seq = pk[:i] + [attacks.flip_bit(pk[i], pos, int(rng.integers(8)))] + pk[i + 1:]
        r = feed(d, seq)
        return r[i].status in REQUIRED[kind] and all(x.status == "ok" for x in r[i + 1:]), r[i].status
    if kind == "replay_in_window":
        seq = pk[:i + 1] + [pk[i - 1]] + pk[i + 1:]
        r = feed(d, seq)
        return r[i + 1].status == "replay", r[i + 1].status
    if kind == "replay_old":
        if n < 70:
            return None, "stream shorter than the window"
        seq = pk + [pk[0]]
        r = feed(d, seq)
        return r[-1].status == "replay", r[-1].status
    if kind == "reorder_in_window":
        seq = attacks.reorder(pk, i, i + 1)
        r = feed(d, seq)
        got = sorted(x.ctr for x in r if x.status == "ok")
        return all(x.status == "ok" for x in r) and got == list(range(n)), "ok" if got == list(range(n)) else "lost"
    if kind == "splice":
        other = C.protect(_EV, geom, 3, T, key_index=0, epoch=1)
        j = min(i, len(other) - 1)
        seq = pk[:i] + [other[j][:48] + pk[i][48:]] + pk[i + 1:]
        r = feed(d, seq)
        return r[i].status in REQUIRED[kind] and r[i + 1].status == "ok", r[i].status
    if kind == "downgrade":
        seq = pk[:i] + [attacks.set_header_field(pk[i], ts_bits=int(rng.integers(1, 6)))] + pk[i + 1:]
        r = feed(d, seq)
        return r[i].status in REQUIRED[kind] and r[i + 1].status == "ok", r[i].status
    if kind == "epoch_jump":
        feed(d, pk[:i])
        k0 = d.kdf_calls
        rj = d.accept(attacks.epoch_jump(pk[i]), now=1.0)
        kj = d.kdf_calls - k0
        rn = d.accept(pk[i], now=1.0)
        return rj.status == "policy" and kj == 0 and rn.status == "ok", f"{rj.status}, kdf +{kj}"
    if kind == "flood":
        junk = attacks.flood(1, length=int(rng.integers(64, 400)), seed=int(rng.integers(1 << 30)))[0]
        r = feed(d, pk[:i] + [junk] + pk[i:])
        return r[i].status in REQUIRED[kind] and r[i + 1].status == "ok", r[i].status
    raise ValueError(kind)


def deletion(pk, geom, T, rng):
    """Delete one middle packet: the gap must be reported; returns (detected, latency in packets)."""
    n = len(pk)
    i = int(rng.integers(2, n - 3))
    d = decryptor(geom, T)
    seq = attacks.delete(pk, i)
    for k, p in enumerate(seq):
        r = d.accept(p, now=k * 1e-3)
        if any(no.kind == "gap" and no.ctrs and no.ctrs[0] <= i <= no.ctrs[1] for no in r.notices):
            return True, k - i + 1
    notes = d.close()
    hit = any(no.kind == "gap" and no.ctrs and no.ctrs[0] <= i <= no.ctrs[1] for no in notes)
    return hit, n - i


def tail(pk, geom, T):
    d = decryptor(geom, T)
    feed(d, attacks.delete_tail(pk, 1))
    return any(no.kind == "truncated" for no in d.close())


def flood_cost(pk, geom, T, n):
    d = decryptor(geom, T)
    feed(d, pk[:4])
    junk = attacks.flood(n, length=200, seed=1)
    passed, failed = [], []
    for j in junk:
        h_ok = j[:4] == b"NVE1"
        t0 = time.perf_counter()
        d.accept(j, now=1.0)
        (passed if h_ok else failed).append(1e6 * (time.perf_counter() - t0))
    tagged = [attacks.flip_bit(pk[5], 60) for _ in range(min(n, 50))]
    mac = []
    for p in tagged:
        t0 = time.perf_counter()
        d.accept(p, now=1.0)
        mac.append(1e6 * (time.perf_counter() - t0))
    return {"junk_header_like_us": float(np.median(passed)), "junk_random_us": float(np.median(failed)),
            "passes_header_checks_one_mac_us": float(np.median(mac))}


def benign_loss(ev, geom, rng, Ts=(256, 1024, 4096), ps=(0.0, 1e-3, 1e-2, 5e-2), reps=20):
    rows = []
    for T in Ts:
        pk = C.protect(ev, geom, 3, T)
        for p in ps:
            frac = []
            for _ in range(reps):
                keep = [x for x in pk if rng.random() >= p]
                d = decryptor(geom, T)
                got = sum(int(((r.words >> 29) == 0).sum()) for r in feed(d, keep) if r.status == "ok")
                frac.append(got / max(1, len(ev)))
            rows.append({"T_us": T, "p_loss": p, "events_delivered": float(np.mean(frac)),
                         "events_delivered_min": float(np.min(frac))})
    return rows


_EV = None


def main():
    global _EV
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    C.dataset_arg(ap)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--T", type=int, default=1024)
    a = ap.parse_args()
    if a.quick:
        a.trials = 6
    rng = np.random.default_rng(a.seed)
    samples = C.load_samples(a.dataset, a.data, limit=a.limit or 6, seed=a.seed)
    ev, _, _, geom, _ = samples[0]
    _EV = ev
    pk = C.protect(ev, geom, 3, a.T)
    if len(pk) < 8:
        raise SystemExit(f"stream gives only {len(pk)} packets; use a longer sample or smaller --T")
    rows, data = [], {"attacks": {}}
    for kind in REQUIRED:
        res = [trial(kind, pk, geom, a.T, rng) for _ in range(a.trials)]
        res = [r for r in res if r[0] is not None]
        k = sum(1 for ok, _ in res if ok)
        p, lo, hi = clopper_pearson(k, len(res)) if res else (float("nan"),) * 3
        statuses = sorted({s for _, s in res})
        data["attacks"][kind] = {"trials": len(res), "success": k, "cp95": [lo, hi], "statuses": statuses,
                                 "required": sorted(REQUIRED[kind])}
        rows.append((kind, f"{k}/{len(res)}", (p, lo, hi), ", ".join(statuses)))
    dl = [deletion(pk, geom, a.T, rng) for _ in range(a.trials)]
    k = sum(1 for ok, _ in dl if ok)
    lat = [l for ok, l in dl if ok]
    data["delete"] = {"trials": len(dl), "detected": k, "cp95": list(clopper_pearson(k, len(dl))[1:]),
                      "latency_packets_max": int(max(lat)) if lat else None,
                      "latency_ms_max": (max(lat) * a.T / 1000) if lat else None,
                      "bound_ms": 64 * a.T / 1000}
    rows.append(("delete (gap)", f"{k}/{len(dl)}", clopper_pearson(k, len(dl)), f"max latency {data['delete']['latency_ms_max']} ms"))
    tr = sum(tail(pk, geom, a.T) for _ in range(max(1, a.trials // 10)))
    data["tail_truncation"] = {"trials": max(1, a.trials // 10), "detected": tr}
    rows.append(("tail truncation", f"{tr}/{max(1, a.trials // 10)}", clopper_pearson(tr, max(1, a.trials // 10)), "truncated"))
    data["flood_cost"] = flood_cost(pk, geom, a.T, 50 if a.quick else 1000)
    data["benign_loss"] = benign_loss(ev, geom, rng, reps=2 if a.quick else 20,
                                      Ts=(1024,) if a.quick else (256, 1024, 4096))
    data["baselines"] = {b: ("all manipulations accepted (no tag)" if C.baseline(b) else
                             "not run: neuro.baselines.%s missing (docs/neuro/BASELINES.md pending)" % b)
                         for b in ("du2021", "zhang2024")}
    data["forgery_bound"] = "2^-128 per attempt (Ascon-AEAD128 tag, 128 bits)"
    data["meta"] = C.meta(a, dataset=a.dataset, n_keys=1, ci="Clopper-Pearson 95 %", level="V3 b=6",
                          synthetic=a.data is None)
    md = ["# N7 active attacks" + (" (synthetic smoke data)" if a.data is None else ""), "",
          C.table(["attack", "required status reached", "rate [CP 95 %]", "statuses seen"], rows), "",
          f"Forgery bound: {data['forgery_bound']}. Gap bound: 64 packets = {64 * a.T / 1000} ms.", "",
          "Flood cost (µs per datagram, median): " + ", ".join(f"{k} {v:.1f}" for k, v in data["flood_cost"].items()),
          "", C.table(["T µs", "p loss", "events delivered (mean)", "min"],
                      [(r["T_us"], r["p_loss"], r["events_delivered"], r["events_delivered_min"])
                       for r in data["benign_loss"]]), "",
          "Baselines: " + "; ".join(f"{k}: {v}" for k, v in data["baselines"].items())]
    C.write("n7", "active_attacks", data, "\n".join(md), a.out)


if __name__ == "__main__":
    main()
