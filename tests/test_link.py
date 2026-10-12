"""System-layer tests: transport, key schedule, feedback channel, defence policies,
and one end-to-end run of sender + channel + receiver over real UDP sockets.

    python -m pytest tests/test_link.py            (unit tests, ~2 s)
    RUN_SLOW=1 python -m pytest tests/test_link.py  (adds the end-to-end run, ~40 s)
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from link import config, keys, wire
from link.defence import BanditPolicy, ThresholdPolicy, Window, threat_score
from link.feedback import FeedbackReader, FeedbackWriter, ReplayWindow
from model.jpeg import encode_frame, receive_frame
from model.testimage import make_image

ROOT = Path(__file__).resolve().parents[1]
MASTER = bytes(range(16))


# ---------------------------------------------------------------- transport
def test_fragment_and_reassemble_out_of_order():
    payload = os.urandom(5000)
    frags = wire.fragment(wire.VIDEO, payload, 77, size=1200)
    assert len(frags) == 5
    r = wire.Reassembler()
    out = None
    for d in reversed(frags):
        out = r.add(d) or out
    assert out[0] == wire.VIDEO and out[2] == 77 and out[4] == payload


def test_missing_fragment_drops_frame():
    frags = wire.fragment(wire.VIDEO, os.urandom(3000), 1, size=1200)
    r = wire.Reassembler(timeout=0.0)
    assert r.add(frags[0]) is None and r.add(frags[2]) is None
    time.sleep(0.01)
    r.add(wire.fragment(wire.VIDEO, b"x", 2)[0])          # triggers expiry
    assert r.dropped >= 1


def test_junk_datagram_ignored():
    r = wire.Reassembler()
    assert r.add(os.urandom(40)) is None and r.add(b"") is None


# --------------------------------------------------------------- key schedule
def test_ratchet_is_one_way_and_deterministic():
    a = keys.Ratchet(MASTER)
    k0 = a.key
    k2 = a.peek(2)
    assert a.epoch == 0 and a.key == k0                 # peek does not commit
    a.forward()
    a.forward()
    assert a.key == k2 == keys.video_key(MASTER, 2)
    assert a.peek(1) is None                            # old keys are gone
    assert len({k0, k2, keys.feedback_key(MASTER)}) == 3


def test_session_id_layout():
    sid = keys.session_id(0xABCDEF123456, 7)
    assert keys.split_session(sid) == (0xABCDEF123456, 7)
    with pytest.raises(ValueError):
        keys.session_id(0, 1)                           # base 0 is reserved for the KDF


def test_frames_from_next_epoch_verify_with_ratcheted_key():
    img = make_image(32, 32)
    base = 0x1234
    jpg = encode_frame(img, keys.video_key(MASTER, 3), keys.session_id(base, 3), 1, "E2").jpeg
    r = keys.Ratchet(MASTER, 1)
    assert receive_frame(jpg, r.peek(3)).ok
    assert not receive_frame(jpg, r.key).ok


# ----------------------------------------------------------- feedback channel
def test_feedback_roundtrip_forgery_and_replay():
    kfb = keys.feedback_key(MASTER)
    w, rd = FeedbackWriter(kfb, 99), FeedbackReader(kfb)
    m1, m2 = w.pack({"type": "hb", "counts": {"ok": 10}}), w.pack({"type": "alert", "kind": "replay"})
    assert rd.unpack(m2) == ("ok", {"type": "alert", "kind": "replay"})
    assert rd.unpack(m1)[0] == "ok"                     # late but inside the window
    assert rd.unpack(m1)[0] == "replay"
    bad = bytearray(w.pack({"type": "hb"}))
    bad[-1] ^= 1
    assert rd.unpack(bytes(bad))[0] == "forged"
    assert FeedbackReader(bytes(16)).unpack(w.pack({"type": "hb"}))[0] == "forged"   # wrong key
    assert rd.unpack(b"FB" + os.urandom(10))[0] == "malformed"


def test_replay_window_edges():
    win = ReplayWindow(64)
    assert win.check(100) and not win.check(100)
    assert win.check(40) and not win.check(36)          # 36 is 64 behind -> outside the window
    assert win.check(99) and win.check(164) and not win.check(100)


# ------------------------------------------------------------------- defence
def cfg():
    return config.load(overrides=["defence.memory_file=''"])


def test_threshold_policy_escalates_holds_and_rekeys():
    c = cfg()
    p = ThresholdPolicy(c, "E2")
    calm = Window(ok=10, fb_ok=2)
    assert p.decide(calm, calm.features(3), 0).mode == "E2"
    atk = Window(ok=2, tag_fail=8, fb_ok=2)
    d = p.decide(atk, atk.features(3), 1)
    assert d.mode == "E4" and d.rekey
    d = p.decide(calm, calm.features(3), 2)
    assert d.mode == "E4" and not d.rekey               # holding, rekey rate-limited
    assert p.decide(calm, calm.features(3), 1 + c["defence"]["hold_s"] + 0.1).mode == "E2"


def test_deadman_rule():
    p = ThresholdPolicy(cfg(), "E2")
    w = Window(hb_age=5.0)
    d = p.decide(w, w.features(3.0), 10)
    assert d.mode == "E4" and d.rekey and "dead-man" in d.reason


def test_video_stall_counts_as_heavy_loss():
    f = Window(ok=0, fb_ok=2, sent=10, hb_age=0.3).features(3.0)
    assert f["loss_level"] == 2 and f["deadman"] == 0


def test_bandit_learns_to_escalate_under_attack_and_relax_when_calm():
    c = cfg()
    p = BanditPolicy(c, "E2", memory_file=None, seed=1)
    calm, atk = Window(ok=10, fb_ok=2), Window(ok=2, tag_fail=3, fb_ok=2)
    t = 0.0
    for episode in range(40):                           # alternate long calm / attack phases
        for _ in range(6):
            p.decide(calm, calm.features(3), t)
            t += 1
        for _ in range(6):
            p.decide(atk, atk.features(3), t)
            t += 1
    q_atk = p.q[p.context(atk.features(3), t)]
    q_calm = p.q[p.context(calm.features(3), t + 100)]
    assert max(q_atk, key=q_atk.get) in ("E3", "E4")
    assert max(q_calm, key=q_calm.get) == "E2"
    assert threat_score(atk.features(3)) == 1.0


# --------------------------------------------------------------- end to end
@pytest.mark.skipif(os.getenv("RUN_SLOW") != "1", reason="set RUN_SLOW=1 for the end-to-end run")
def test_end_to_end_link_detects_and_reacts():
    from link.buslog import BusLogger
    base_port = 47100
    sets = [f"link.video_in={base_port}", f"link.video_out={base_port + 1}", f"link.fb_in={base_port + 2}",
            f"link.fb_out={base_port + 3}", f"link.control={base_port + 4}",
            f"link.sender_control={base_port + 5}", f"link.bus=[{base_port + 10}]",
            "sender.width=160", "sender.height=128", "sender.policy=threshold",
            "defence.memory_file=''"]
    args = [x for s in sets for x in ("--set", s)]
    log = BusLogger(base_port + 10)
    c = config.load(overrides=sets)
    procs = [subprocess.Popen([sys.executable, "-m", f"link.{n}"] + args, cwd=ROOT,
                              stdout=subprocess.DEVNULL) for n in ("channel", "receiver", "sender")]
    try:
        time.sleep(6)
        wire.send_control(c, "control", cmd="attack", type="bitflip", duration=4)
        time.sleep(7)
        wire.send_control(c, "control", cmd="attack", type="replay", duration=4)
        time.sleep(7)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
        log.close()
    frames = log.take("frame", "receiver")
    verdicts = {f["verdict"] for f in frames}
    assert sum(f["verdict"] == "ok" for f in frames) > 50
    assert "tag-mismatch" in verdicts
    assert verdicts & {"replay", "stale-epoch"}
    windows = log.take("window", "sender")
    assert any(w["mode"] == "E4" for w in windows), "sender never escalated"
    assert log.take("rekey", "sender"), "sender never rekeyed"
    assert log.take("epoch", "receiver"), "receiver did not follow the rekey"
