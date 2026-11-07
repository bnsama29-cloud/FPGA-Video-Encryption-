"""First contact with the paper-2 overlay: VERSION, then the default neuro.vectors cases bit-exact (DESIGN §8.2 N10).

    sudo -E python3 -m system.board.neuro.nv_first_contact --bitfile overlay/neuro/nv.bit
    python -m system.board.neuro.nv_first_contact --mock          (laptop: the same steps on the golden model)

For every default case of neuro.vectors (the cases test_nv_top runs in simulation) it configures the IP, streams the
words, issues the commits at the resolved COMMIT_AT, flushes, and compares every output packet with the model
(first mismatch: case, word, got, expected), then the counters. Prints PASS/FAIL per case and writes
sim_out/neuro/n10/first_contact.json.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from neuro import vectors as V
from neuro.geometry import Geometry
from neuro.pad import PadPolicy
from neuro.sender import Config

from .nv_driver import MockBackend, NvIP, build_of

ROOT = Path(__file__).resolve().parents[4]


def cfg_of(s):
    pad = PadPolicy(s["pad_kind"], s["pad_min"], s["pad_cap"], V.MAX_CD_TB) if s["pad_kind"] else None
    g = Geometry("%dx%d" % (s["W"], s["H"]), s["W"], s["H"])
    return Config(s["level"], s["ts_bits"], s["T_us"], g, pad, s["max_gap_us"], s["jump_mode"])


def run_case(ip, case):
    ref = V.run_model(case)
    s0 = ref["initial"]
    ip.configure(V.subkeys_for(s0["epoch"]), s0["sid"], cfg_of(s0), s0["ctr0"])
    got = []
    for st in ref["steps"]:
        if st["op"] == "push":
            got += ip.push(np.array(st["words"], np.uint32))
        elif st["op"] == "flush":
            got += ip.flush()
        else:
            sh = st["shadow"]
            code = ip.commit(st["at"], V.subkeys_for(sh["epoch"]), sh["sid"], cfg_of(sh), sh["ctr0"])
            if code != st["expect"]:
                return False, "commit at %d: code %d, model %d" % (st["at"], code, st["expect"])
            got += ip.b.drain()
    exp_words = [w for w, _ in ref["out"]]
    got_words = [int(x) for p in got for x in np.frombuffer(p, dtype="<u4")]
    for k, (g, e) in enumerate(zip(got_words, exp_words)):
        if g != e:
            return False, "first mismatch at output word %d: got %08x, expected %08x" % (k, g, e)
    if len(got_words) != len(exp_words):
        return False, "%d output words, expected %d" % (len(got_words), len(exp_words))
    c = ip.counters()
    for k, v in ref["counters"].items():
        if c.get(k) != v:
            return False, "counter %s = %s, model %s" % (k, c.get(k), v)
    return True, "%d packets, %d words" % (ref["packets"], len(exp_words))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bitfile", default=str(ROOT / "software/system/board/overlay/neuro/nv.bit"))
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "sim_out/neuro/n10"))
    a = ap.parse_args()
    if a.mock:
        ip = NvIP(MockBackend())
    else:
        from .nv_driver import PynqBackend
        ip = NvIP(PynqBackend(a.bitfile))
    ver = ip.version()
    build = build_of(ver)
    print("VERSION %08x -> %s" % (ver, build))
    if build is None:
        raise SystemExit("not a contract-n1 nv_top bitstream")
    res = {}
    for case in V.cases():
        ok, msg = run_case(ip, case)
        res[case.name] = {"pass": ok, "detail": msg}
        print("%s %s: %s" % ("PASS" if ok else "FAIL", case.name, msg))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "first_contact.json").write_text(json.dumps(
        {"version": "%08x" % ver, "build": build, "mock": a.mock, "cases": res}, indent=1), encoding="utf-8")
    if not all(r["pass"] for r in res.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
