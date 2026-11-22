"""N2 power stimulus: a real DVS Gesture slice for the XSim run whose switching activity (SAIF) Vivado reads.

    python experiments/neuro_power_vectors.py --npy <ibmGestureTest/user24_fluorescent/0.npy> --level 2 --out sim_build/nv_power_v2

Takes one DVS Gesture test recording (--npy), keeps the --ms milliseconds that start --start-ms into it, encodes
them as canonical EVT 2.0 (neuro.evt2.encode, T_us = 1024, the default packet of DESIGN §2), plays them on the
golden model (neuro.vectors.run_model, the same path as hardware/tb/neuro/test_nv_top.py) and writes for
hardware/tb/neuro/tb_nv_power.v:
  script.hex   commands: 1 a d = AXI-Lite write, 2 n w1..wn = stream n words back to back (max rate),
               3 = wait until every word was accepted, 4 n = wait n clocks, 0 = end of script
  expect.hex   every output word with tlast in bit 32 (33-bit words), for the testbench's bit-exact check
  vectors.json level, events, input / output words, source file and its SHA-256
Two workloads are used: a real slice (sensor-rate activity, where the per-packet table fill dominates) and a
dense synthetic stream (--rate events per ms, where the datapath is busy every clock).
The testbench prints "RESULT nv_power mismatches=<m> words=<n> events=<e> cycles=<c>"; a run with mismatches is
not used for power (run_vivado_neuro.py --steps power).
"""
import argparse
import json
from pathlib import Path

import numpy as np

import neuro_common as C
from neuro import evt2
from neuro import vectors as V
from neuro.geometry import SENSORS

CTRL, MODE, GEOM, T_US = 0x04, 0x0C, 0x10, 0x14
SID_LO, SID_HI, CTR0_LO, CTR0_HI, PAD_MIN, PAD_CAP, MAX_GAP = 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30
K_BASE = {"tag": 0x40, "pol": 0x50, "perm": 0x60, "dum": 0x70, "aead": 0x80}
EN, FLUSH, COMMIT = 1, 4, 8
TS_BITS = {1: 0, 2: 0, 3: 6, 4: 0}                 # as neuro.vectors.cases(): V3 permutes 6 timestamp bits


def shadow_writes(s):
    """(address, value) AXI-Lite writes of one shadow set; the same encoding as test_nv_top.Dut.shadow."""
    mode = (s["level"] | (s["ts_bits"] << 4) | ((s["pad_kind"] != 0) << 8) | (s["pad_kind"] << 9)
            | (s["jump_mode"] << 12))
    w = [(MODE, mode), (GEOM, s["W"] | (s["H"] << 16)), (T_US, s["T_us"]), (SID_LO, s["sid"] & 0xFFFFFFFF),
         (SID_HI, s["sid"] >> 32), (CTR0_LO, s["ctr0"] & 0xFFFFFFFF), (CTR0_HI, s["ctr0"] >> 32),
         (PAD_MIN, s["pad_min"]), (PAD_CAP, s["pad_cap"]), (MAX_GAP, s["max_gap_us"])]
    sk = V.subkeys_for(s["epoch"])
    for name, base in K_BASE.items():
        k = int.from_bytes(getattr(sk, name), "little")
        w += [(base + 4 * i, (k >> (32 * i)) & 0xFFFFFFFF) for i in range(4)]
    return w


def script(ref):
    """Command words for tb_nv_power.v from a run_model result (push steps and a final flush only)."""
    cmd = []
    for a, v in shadow_writes(ref["initial"]):
        cmd += [1, a, v]
    cmd += [1, CTRL, COMMIT, 1, CTRL, EN]
    for st in ref["steps"]:
        if st["op"] == "push":
            cmd += [2, len(st["words"]), *st["words"], 3, 4, 4]
        elif st["op"] == "flush":
            cmd += [1, CTRL, EN | FLUSH]
        else:
            raise ValueError("power vectors use push and flush steps only")
    return cmd + [0]


def read_npy(path):
    """Events of one DVS Gesture .npy (float columns x, y, p, t in milliseconds; Tonic 1.7.0 multiplies t by 1000)."""
    a = np.load(path)
    ev = np.zeros(len(a), dtype=evt2.EVENT_DTYPE)
    ev["x"], ev["y"], ev["p"] = a[:, 0], a[:, 1], a[:, 2]
    ev["t"] = np.round(a[:, 3] * 1e3).astype(np.uint64)
    return np.sort(ev, order="t", kind="stable")


def window(ev, start_ms, ms):
    t0 = int(ev["t"].min()) + start_ms * 1000
    keep = (ev["t"] >= t0) & (ev["t"] < t0 + ms * 1000)
    w = ev[keep].copy()
    w["t"] -= t0 - (t0 % 1024)                     # keep the phase inside the 1024 us packet, start near 0
    return w


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npy", type=Path, default=None,
                    help="one DVS Gesture recording as unpacked from ibmGestureTest.tar.gz, e.g. "
                         "ibmGestureTest/user24_fluorescent/0.npy (columns x, y, p, t in ms); omit: synthetic")
    ap.add_argument("--level", type=int, choices=[1, 2, 3, 4], default=2)
    ap.add_argument("--rate", type=int, default=10000,
                    help="synthetic events per ms without --npy (uniform pixels: the dense, rate-bound case)")
    ap.add_argument("--start-ms", type=int, default=2000)
    ap.add_argument("--ms", type=int, default=64)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    g = SENSORS["dvsgesture"]
    if a.npy is None:
        ev = V.events(g, a.rate * a.ms, 0, a.ms * 1000, 0)
        src = f"synthetic: {a.rate} events/ms, uniform pixels (neuro.vectors.events, seed 0)"
    else:
        ev = window(read_npy(a.npy), a.start_ms, a.ms)
        src = f"{a.npy.parent.name}/{a.npy.name} (sha256 {C.sha256(a.npy)})"
    if len(ev) == 0:
        raise SystemExit("empty window: choose another --start-ms")
    words = evt2.encode(np.sort(ev, order="t"), 1024)
    case = V.Case(f"power_v{a.level}", g, a.level, TS_BITS[a.level], 1024,
                  steps=[("push", words), ("flush",)])
    ref = V.run_model(case)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "script.hex").write_text("".join(f"{w & 0xFFFFFFFF:08x}\n" for w in script(ref)))
    (a.out / "expect.hex").write_text("".join(f"{(l << 32) | w:09x}\n" for w, l in ref["out"]))
    info = {"level": a.level, "events": int(len(ev)), "words_in": int(len(words)), "words_out": len(ref["out"]),
            "packets": ref["packets"], "source": src, "start_ms": a.start_ms, "ms": a.ms, "T_us": 1024,
            "meta": C.meta(a)}
    (a.out / "vectors.json").write_text(json.dumps(info, indent=1))
    print(f"{a.out}: {info['events']} events, {info['words_in']} words in, {info['words_out']} out, "
          f"{info['packets']} packets")


if __name__ == "__main__":
    main()
