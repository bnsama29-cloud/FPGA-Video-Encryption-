"""Hardware tamper experiment (experiments/hw_tamper.py): the matching of shots to rejected frames, and a
laptop rehearsal with the emulated board (board_sender --mock-lanes 2 --mock-e5 --mock-tamper).

    python -m pytest tests/test_hw_tamper.py               (~1 s)
    RUN_SLOW=1 python -m pytest tests/test_hw_tamper.py    (adds the rehearsal, ~40 s)
"""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import hw_tamper  # noqa: E402
import scenario  # noqa: E402

from future_work.board.board_sender import MockTamper  # noqa: E402


def ev(t, src, kind, **kw):
    return dict(t=t, src=src, kind=kind, **kw)


def test_analyse_matches_each_shot_once():
    events = [ev(10.0, "hw", "hw_shot"), ev(10.12, "receiver", "frame", verdict="tag-mismatch"),
              ev(10.2, "receiver", "frame", verdict="ok"),
              ev(20.0, "hw", "hw_shot"),                                   # missed
              ev(30.0, "hw", "hw_shot"), ev(30.3, "receiver", "frame", verdict="malformed"),
              ev(30.4, "receiver", "frame", verdict="tag-mismatch"),        # second frame for one shot
              ev(45.0, "receiver", "frame", verdict="tag-mismatch")]        # no shot explains it
    r = hw_tamper.analyse_hw(events, window_s=1.5)
    assert (r["shots"], r["detected"], r["missed"]) == (3, 2, 1)
    assert r["frames_rejected_per_shot"] == {"0": 1, "1": 1, "2": 1}
    assert r["unexplained_rejections"] == 1 and r["frames_ok"] == 1
    assert r["latency_ms_median"] == 300.0 and r["latency_ms_max"] == 300.0


def test_mock_tamper_flips_one_safe_bit_once():
    t = MockTamper(seed=1)
    scan = bytes([0x12, 0xFF, 0x00, 0x34] * 50 + [0xFF, 0xD3, 0x55, 0x66] * 10)
    assert t.apply(scan) == scan                       # nothing pending
    t.shot()
    out = t.apply(scan)
    d = [i for i in range(len(scan)) if scan[i] != out[i]]
    assert len(d) == 1 and bin(scan[d[0]] ^ out[d[0]]).count("1") == 1
    i = d[0]
    assert scan[i] != 0xFF and out[i] != 0xFF and scan[i - 1] != 0xFF
    assert t.apply(scan) == scan and t.applied == 1    # one shot, one frame


@pytest.mark.skipif(os.getenv("RUN_SLOW") != "1", reason="set RUN_SLOW=1 for the rehearsal run")
def test_rehearsal_every_shot_costs_exactly_one_frame(tmp_path):
    bp = 47600
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps({"name": "hw_short", "end_s": 26,
                              "steps": [{"at": t, "hw": "shot"} for t in (6, 10, 14, 18, 22)]}))
    cmd = scenario.board_command(bp, "threshold", laptop="127.0.0.1")
    toks = shlex.split(cmd)
    sets = [x for a, t in zip(toks, toks[1:]) if a == "--set" for x in ("--set", t)]
    sets += ["--set", "sender.width=160", "--set", "sender.height=128"]
    board = subprocess.Popen([sys.executable, "-m", "future_work.board.board_sender", "--mock-lanes", "2",
                              "--mock-e5", "--mock-tamper"] + sets, cwd=ROOT, stdout=subprocess.DEVNULL)
    try:
        scenario.run(sc, "threshold", tmp_path, bp, ["sender.width=160", "sender.height=128"], quiet=True,
                     external_sender="127.0.0.1", board_max_mode="E5", wait_s=60,
                     hw_trigger=hw_tamper.make_trigger("udp:127.0.0.1", bp + 5))
    finally:
        board.terminate()
        board.wait()
    events = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    r = hw_tamper.analyse_hw(events)
    assert r["shots"] == 5 and r["detected"] == 5, r
    assert r["frames_rejected_per_shot"] == {"1": 5}, r
    assert r["unexplained_rejections"] == 0 and r["frames_ok"] > 50, r
