"""N10: replay an EVT 2.0 recording through the PYNQ-Z2 encryptor (or the mock) and over UDP (DESIGN §8.2 N10).

    sudo -E python3 -m system.board.neuro.nv_replay --file rec.raw --udp 192.168.2.1:5600 --timed
    sudo -E python3 -m system.board.neuro.nv_replay --file rec.raw --max-rate
    python -m system.board.neuro.nv_replay --synthetic --mock --max-rate                (laptop)

Modes: --max-rate streams the recording in chunks (one per packet duration T) as fast as the DMA takes them;
--timed sends each chunk when the wall clock reaches its start time. The PL timer gate of DESIGN §8.2 (input gated by
timestamp inside the fabric) is not in contract n1's RTL; timed mode is therefore ARM-paced and labelled so.
Reported: bit-exact vs the golden model (first mismatch: packet, word, got, expected); PL throughput from the
snapshotted counters (WORDS_IN / CYCLES at FCLK) separately from the end-to-end (DMA + ARM + UDP) rate; IN_WAIT,
OUT_STALL, TABLE_WAIT, KS_WAIT; with --udp every packet is one link.wire message (type 6, 1200-byte fragments).
Uses the PSK experiment profile (master 0 of experiments/neuro_common.py unless --master-hex); the live system uses
the kex profile. Writes sim_out/neuro/n10/replay_<name>_<mode>.json.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from link import wire
from neuro import evt2, keys
from neuro.geometry import SENSORS
from neuro.sender import Config, Encryptor

from .nv_driver import NV_EVENTS, MockBackend, NvIP

ROOT = Path(__file__).resolve().parents[4]
CAM, BOOT = 1, 1


def load(a):
    if a.synthetic:
        rng = np.random.default_rng(0)
        g = SENSORS["dvsgesture"]
        n = 20000
        ev = np.zeros(n, dtype=evt2.EVENT_DTYPE)
        ev["t"] = np.sort(rng.integers(10_000, 10_000 + 200_000, n))
        ev["x"], ev["y"], ev["p"] = rng.integers(0, g.W, n), rng.integers(0, g.H, n), rng.integers(0, 2, n)
        return evt2.encode(ev, a.T), g, "synthetic"
    words, g = evt2.read_raw(a.file)
    return words, g, Path(a.file).stem


def chunks(words, T):
    """Split the word stream at the TIME_HIGH that starts each T-µs step: [(start µs, words)]."""
    th = np.nonzero((words >> 28) == 8)[0]
    if len(th) == 0:
        return [(0, words)]
    v = (words[th] & 0x0FFFFFFF).astype(np.int64) * 64
    k = (v - v[0]) // T
    cut = th[np.nonzero(np.diff(k))[0] + 1]
    parts = np.split(words, cut)
    starts = [int(v[0])] + [int(words[c] & 0x0FFFFFFF) * 64 for c in cut]
    return list(zip(starts, parts))


def first_mismatch(got, ref):
    for i, (g, e) in enumerate(zip(got, ref)):
        if g != e:
            gw, ew = np.frombuffer(g, "<u4"), np.frombuffer(e, "<u4")
            n = min(len(gw), len(ew))
            k = next((j for j in range(n) if gw[j] != ew[j]), n)
            return {"packet": i, "word": int(k), "got": "%08x" % gw[k] if k < len(gw) else None,
                    "expected": "%08x" % ew[k] if k < len(ew) else None}
    if len(got) != len(ref):
        return {"packets": len(got), "expected": len(ref)}
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file")
    src.add_argument("--synthetic", action="store_true")
    m = ap.add_mutually_exclusive_group()
    m.add_argument("--timed", action="store_true")
    m.add_argument("--max-rate", action="store_true")
    ap.add_argument("--level", type=int, default=3)
    ap.add_argument("--T", type=int, default=1024)
    ap.add_argument("--udp", default=None, help="host:port of the receiver")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--bitfile", default=str(ROOT / "software/system/board/overlay/neuro/nv.bit"))
    ap.add_argument("--master-hex", default=None)
    ap.add_argument("--fclk-mhz", type=float, default=100.0)
    ap.add_argument("--out", default=str(ROOT / "sim_out/neuro/n10"))
    a = ap.parse_args()
    words, geom, name = load(a)
    master = bytes.fromhex(a.master_hex) if a.master_hex else hashlib.sha256(b"neuro-exp-master-0").digest()[:16]
    sk = keys.subkeys(master, CAM, BOOT, 0)
    sid = keys.session_id(CAM, BOOT, 0)
    cfg = Config(a.level, 6 if a.level == 3 else 0, a.T, geom)
    if a.mock:
        ip = NvIP(MockBackend())
    else:
        from .nv_driver import PynqBackend
        ip = NvIP(PynqBackend(a.bitfile))
    ip.configure(sk, sid, cfg)
    sock = addr = None
    if a.udp:
        host, port = a.udp.rsplit(":", 1)
        sock, addr = wire.udp_socket(), (host, int(port))
    got, sent = [], 0

    def emit(pk):
        nonlocal sent
        got.extend(pk)
        if sock:
            for p in pk:
                wire.send_message(sock, addr, NV_EVENTS, p, sent)
                sent += 1

    t_wall0 = time.perf_counter()
    parts = chunks(words, a.T)
    t_rec0 = parts[0][0]
    for start, part in parts:
        if a.timed:
            delay = (start - t_rec0) / 1e6 - (time.perf_counter() - t_wall0)
            if delay > 0:
                time.sleep(delay)
        emit(ip.push(part))
    emit(ip.flush())
    wall = time.perf_counter() - t_wall0
    enc = Encryptor(sk, sid, cfg)
    ref = enc.push(words) + enc.flush()
    first = first_mismatch(got, ref)
    c = ip.counters()
    pl_s = c["CYCLES"] / (a.fclk_mhz * 1e6) if c["CYCLES"] else 0.0
    res = {"recording": name, "mode": "timed (ARM-paced)" if a.timed else "max-rate", "mock": a.mock,
           "level": a.level, "T_us": a.T, "words_in": int(len(words)), "packets": len(got),
           "bit_exact": first is None, "first_mismatch": first, "counters": c,
           "pl_words_per_s": (c["WORDS_IN"] / pl_s) if pl_s > 0 else None,
           "end_to_end_words_per_s": len(words) / wall, "wall_s": wall, "udp_messages": sent,
           "note": "PL rate from CYCLES (clocks since ENABLE: includes idle input time in timed mode); the mock's "
                   "CYCLES is host time, not a hardware number"}
    print(json.dumps({k: v for k, v in res.items() if k != "counters"}, indent=1))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    mode = "timed" if a.timed else "max"
    (Path(a.out) / ("replay_%s_%s.json" % (name, mode))).write_text(json.dumps(res, indent=1), encoding="utf-8")
    if first is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
