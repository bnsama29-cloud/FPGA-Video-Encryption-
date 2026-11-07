"""Test cases and vectors for the paper-2 RTL (DESIGN §7.2).

A case is a scenario for the sender: an initial configuration and a list of steps

    ("push", words)                          EVT 2.0 words into the encryptor
    ("commit", rel_at, changes)              CTRL.COMMIT for the packet open_ctr + rel_at with the changed fields
    ("flush",)                               CTRL.FLUSH

`run_model(case)` plays it on the golden model (neuro.sender.Encryptor) and returns the resolved steps (absolute
COMMIT_AT, the full shadow set and the expected refusal code of every commit), the expected output words with
tlast, and the expected counters. The cocotb top-level test (hardware/tb/neuro/test_nv_top.py) runs the same cases
from this module; `write_vectors` writes them as files for XSim and the board:

    hardware/vectors/neuro/<case>/config.json   initial set, resolved steps, model commit
    hardware/vectors/neuro/<case>/in.hex        input words (one per line; "# step" lines separate the steps)
    hardware/vectors/neuro/<case>/out.hex       output words, "L" after the word that carries tlast
    hardware/vectors/neuro/<case>/counters.json expected PKTS, WORDS_IN, WORDS_OUT, ERR_*

    python -m neuro.vectors --out hardware/vectors/neuro [--full]

Vectors are generated, never edited. The RTL is built with MAX_CD = MAX_CD_TB for these cases, so every padding
policy here uses max_cd = MAX_CD_TB.
"""
import argparse
import json
import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from . import evt2, keys
from .geometry import Geometry, SENSORS
from .pad import FLOOR, LADDER, PadPolicy
from .sender import CFG_NONE, ConfigError, Config, Encryptor

MASTER = bytes(range(16))
CAM, BOOT = 3, 5
MAX_CD_TB = 256
_G16 = Geometry("16x16", 16, 16)
_GWIDE = Geometry("1280x16", 1280, 16)     # the 16 x 1280 domain of §7.2 with H <= MAXH = 720


@dataclass
class Case:
    name: str
    geom: Geometry
    level: int
    ts_bits: int = 0
    T_us: int = 128
    pad: PadPolicy = None
    epoch: int = 0
    ctr0: int = 0
    max_gap_us: int = 1_000_000
    jump_mode: int = 0
    steps: list = field(default_factory=list)
    full_only: bool = False

    def config(self):
        return Config(self.level, self.ts_bits, self.T_us, self.geom, self.pad, self.max_gap_us, self.jump_mode)

    @property
    def sid(self):
        return keys.session_id(CAM, BOOT, self.epoch)


def events(geom, n, t0, span, seed, p_rate=0.5):
    rng = np.random.default_rng(seed)
    ev = np.zeros(n, dtype=evt2.EVENT_DTYPE)
    ev["t"] = np.sort(rng.integers(t0, t0 + span, n))
    ev["x"] = rng.integers(0, geom.W, n)
    ev["y"] = rng.integers(0, geom.H, n)
    ev["p"] = rng.random(n) < p_rate
    return ev


def stream(geom, n, t0, span, seed, T_us):
    return evt2.encode(events(geom, n, t0, span, seed), T_us)


def _th(v):
    return evt2.time_high(v)


def _cd(x, y, p=1, ts=0):
    return evt2.cd_word(x, y, p, ts)


def cases(full=False):
    out = []
    geoms = [SENSORS["dvsgesture"], SENSORS["nmnist"], _G16, _GWIDE]
    for gi, g in enumerate(geoms):
        for lvl in range(5):
            b = 6 if lvl == 3 else 0
            c = Case(f"{g.name}_v{lvl}", g, lvl, b, 128,
                     steps=[("push", stream(g, 120, 6400, 6 * 128, 10 * gi + lvl, 128)), ("flush",)],
                     full_only=not (gi == 0 or lvl == 3))
            out.append(c)
    g = SENSORS["dvsgesture"]
    # empty packets and a time gap (closing loop over skipped packets)
    gap = np.concatenate([stream(g, 40, 6400, 256, 1, 128), stream(g, 40, 6400 + 1500, 256, 2, 128)])
    out.append(Case("gap_v3", g, 3, 6, 128, steps=[("push", gap), ("flush",)]))
    out.append(Case("gap_pad_floor_v3", g, 3, 6, 128, PadPolicy(FLOOR, 2, 0, MAX_CD_TB),
                    steps=[("push", gap), ("flush",)]))
    # padding policies at V3 (b = 6) and V4
    s = stream(g, 150, 6400, 4 * 128, 7, 128)
    out.append(Case("pad_floor_v3", g, 3, 6, 128, PadPolicy(FLOOR, 3, 0, MAX_CD_TB), steps=[("push", s), ("flush",)]))
    out.append(Case("pad_ladder_v3", g, 3, 6, 128, PadPolicy(LADDER, 2, 8, MAX_CD_TB),
                    steps=[("push", s), ("flush",)]))
    out.append(Case("pad_floor_v4", g, 4, 0, 128, PadPolicy(FLOOR, 2, 0, MAX_CD_TB), steps=[("push", s), ("flush",)]))
    dense = stream(g, 400, 6400, 128, 8, 128)           # > MAX_CD_TB CD words in one packet: ERR_PADOVF
    out.append(Case("pad_overflow_v3", g, 3, 6, 128, PadPolicy(FLOOR, 4, 0, MAX_CD_TB),
                    steps=[("push", dense), ("flush",)]))
    # input rules: pre-TIME_HIGH, backwards TIME_HIGH, out-of-range CD, every non-CD type
    t = 100
    bad = [_cd(1, 1), 0xA0000101, _th(t), _cd(5, 6), _cd(200, 3), _cd(3, 200), _th(t - 1), _cd(7, 7, 0, 9),
           0xA0400301, 0xE0010002, 0xF1234567, 0x20000000, 0x50000000, _th(t + 1), _cd(8, 8), _th(t + 2),
           _th(t + 2), _cd(9, 9, 1, 63), _th(t + 5), _cd(10, 10)]
    for lvl in (1, 3):
        out.append(Case(f"input_rules_v{lvl}", g, lvl, 6 if lvl == 3 else 0, 128,
                        steps=[("push", np.array(bad, np.uint32)), ("flush",)]))
    # time jump: drop (mode 0) and halt (mode 1, resumed by a commit with a new epoch)
    j0 = [_th(100), _cd(1, 2), _th(101), _cd(3, 4), _th(100 + 100), _cd(5, 5), _cd(6, 6), _th(103), _cd(7, 7),
          _th(105), _cd(8, 8)]
    out.append(Case("jump_drop_v3", g, 3, 6, 128, max_gap_us=1000, jump_mode=0,
                    steps=[("push", np.array(j0, np.uint32)), ("flush",)]))
    j1 = [_th(100), _cd(1, 2), _th(102), _cd(3, 4), _th(100 + 100), _cd(5, 5), _cd(6, 6), _th(203), _cd(7, 7)]
    out.append(Case("jump_halt_v3", g, 3, 6, 128, max_gap_us=1000, jump_mode=1,
                    steps=[("push", np.array(j1, np.uint32)), ("commit", 0, {"epoch": 1, "ctr0": 0}),
                           ("flush",)]))
    # commits: same-SID level change, LATE then ok, new epoch (FIRST/FINAL/link), REWIND, PAD with b < 6 refused
    a = stream(g, 60, 6400, 4 * 128, 11, 128)
    b2 = stream(g, 60, 6400 + 4 * 128, 6 * 128, 12, 128)[1:]
    c2 = stream(g, 60, 6400 + 10 * 128, 4 * 128, 13, 128)[1:]
    out.append(Case("commit_level_change", g, 3, 6, 128, steps=[
        ("push", a), ("commit", 1, {"level": 2, "ts_bits": 0}), ("commit", 2, {"level": 2, "ts_bits": 0}),
        ("push", b2), ("commit", 3, {"level": 4, "ts_bits": 0, "pad": PadPolicy(FLOOR, 2, 0, MAX_CD_TB)}),
        ("push", c2), ("flush",)]))
    out.append(Case("commit_new_epoch", g, 3, 6, 128, steps=[
        ("push", a), ("commit", 2, {"epoch": 1, "ctr0": 0}), ("push", b2),
        ("commit", 3, {"epoch": 0, "ctr0": 0}),                       # older epoch: REWIND
        ("commit", 3, {"level": 3, "ts_bits": 3, "pad": PadPolicy(FLOOR, 2, 0, MAX_CD_TB)}),   # b < 6 + PAD: LEVEL
        ("commit", 2, {"epoch": 2, "ctr0": 5}), ("push", c2), ("flush",)]))
    for c in out:
        c.full_only = c.name not in DEFAULT_CASES
    return [c for c in out if full or not c.full_only]


# run by `make test` (time budget); FULL=1 runs every case
DEFAULT_CASES = {"dvsgesture_v0", "dvsgesture_v3", "dvsgesture_v4", "pad_floor_v3", "input_rules_v3",
                 "jump_halt_v3", "commit_new_epoch"}


SHADOW_FIELDS = ("level", "ts_bits", "T_us", "W", "H", "pad_kind", "pad_min", "pad_cap", "max_gap_us", "jump_mode",
                 "epoch", "ctr0")


def _shadow(cfg, epoch, ctr0):
    p = cfg.pad
    return {"level": cfg.level, "ts_bits": cfg.ts_bits, "T_us": cfg.T_us, "W": cfg.geom.W, "H": cfg.geom.H,
            "pad_kind": p.kind if p else 0, "pad_min": p.pad_min if p else 0, "pad_cap": p.pad_cap if p else 0,
            "max_gap_us": cfg.max_gap_us, "jump_mode": cfg.jump_mode, "epoch": epoch, "ctr0": ctr0,
            "sid": keys.session_id(CAM, BOOT, epoch)}


def run_model(case: Case):
    """Play the case on the golden model. Returns dict(steps, out, counters, initial)."""
    cfg, epoch, ctr0 = case.config(), case.epoch, case.ctr0
    enc = Encryptor(keys.subkeys(MASTER, CAM, BOOT, epoch), case.sid, cfg, ctr0)
    steps, out = [], []
    shadow = _shadow(cfg, epoch, ctr0)
    for st in case.steps:
        if st[0] == "push":
            w = np.asarray(st[1], dtype=np.uint32)
            pk = enc.push(w)
            steps.append({"op": "push", "words": [int(v) for v in w], "halts": bool(enc.halted)})
            out += pk
        elif st[0] == "flush":
            out += enc.flush()
            steps.append({"op": "flush"})
        else:
            _, rel, ch = st
            open_ctr = enc.pz.open_ctr if enc.pz.started else enc.active.ctr0
            at = open_ctr + rel
            ncfg = cfg
            fields = {k: v for k, v in ch.items() if k in ("level", "ts_bits", "T_us", "max_gap_us", "jump_mode")}
            if fields:
                ncfg = replace(ncfg, **fields)
            if "pad" in ch:
                ncfg = replace(ncfg, pad=ch["pad"])
            if "geom" in ch:
                ncfg = replace(ncfg, geom=ch["geom"])
            nep = ch.get("epoch", epoch)
            nctr0 = ch.get("ctr0", 0)
            sid = keys.session_id(CAM, BOOT, nep)
            sk = keys.subkeys(MASTER, CAM, BOOT, nep)
            code = CFG_NONE
            try:
                out += enc.commit(at, cfg=ncfg, subkeys=sk, sid=sid, ctr0=nctr0)
            except ConfigError as e:
                code = e.code
            shadow = _shadow(ncfg, nep, nctr0)
            steps.append({"op": "commit", "at": at, "shadow": shadow, "expect": code})
            if code == CFG_NONE:
                cfg, epoch = ncfg, nep
    words = []
    for p in out:
        w = np.frombuffer(p, dtype="<u4").tolist()
        words += [(int(v), int(i == len(w) - 1)) for i, v in enumerate(w)]
    return {"initial": _shadow(case.config(), case.epoch, case.ctr0), "steps": steps, "out": words,
            "packets": len(out), "counters": dict(enc.counters)}


def subkeys_for(epoch):
    return keys.subkeys(MASTER, CAM, BOOT, epoch)


def _git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).parent).stdout.strip()
    except OSError:
        return ""


def write_vectors(out_dir, case_list=None, full=False):
    out_dir = Path(out_dir)
    sha = _git_sha()
    written = []
    for c in case_list or cases(full):
        r = run_model(c)
        d = out_dir / c.name
        d.mkdir(parents=True, exist_ok=True)
        cfg = {"initial": r["initial"], "steps": [{k: v for k, v in s.items() if k != "words"} for s in r["steps"]],
               "master": MASTER.hex(), "cam_id": CAM, "boot_id": BOOT, "max_cd": MAX_CD_TB,
               "subkeys": {str(e): {k: getattr(subkeys_for(e), k).hex() for k in ("tag", "pol", "perm", "dum", "aead")}
                           for e in sorted({r["initial"]["epoch"]} | {s["shadow"]["epoch"] for s in r["steps"]
                                                                      if s["op"] == "commit"})},
               "model_commit": sha}
        (d / "config.json").write_text(json.dumps(cfg, indent=1))
        lines = []
        for i, s in enumerate(r["steps"]):
            lines.append(f"# step {i} {s['op']}")
            lines += [f"{w:08x}" for w in s.get("words", [])]
        (d / "in.hex").write_text("\n".join(lines) + "\n")
        (d / "out.hex").write_text("\n".join(f"{w:08x}" + (" L" if l else "") for w, l in r["out"]) + "\n")
        (d / "counters.json").write_text(json.dumps(r["counters"], indent=1))
        written.append(c.name)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="hardware/vectors/neuro")
    ap.add_argument("--full", action="store_true", help="every geometry x level (FULL=1 cases)")
    a = ap.parse_args()
    names = write_vectors(a.out, full=a.full)
    print(f"wrote {len(names)} cases to {a.out}: {', '.join(names)}")


if __name__ == "__main__":
    main()
