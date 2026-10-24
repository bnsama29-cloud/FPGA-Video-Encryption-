"""BTN1..BTN3 of the tamper overlay -> protection level (system/board/board_sender.py :: ButtonLevels,
RTL system/board/axil_buttons.v, checked in tb/test_axil_buttons.py).

Checks, on a real link Sender with the emulated 2-lane bitstream: BTN1 steps down to E0 and no further, BTN2
steps up to what the bitstream offers (E5, or E4 without E5), BTN3 returns to the automatic policy, presses
before the start and 8-bit counter wrap are handled, the level reaches the frames at the next defence window,
and the rehearsal path (control port -> MockButtons -> poller) works. With --buttons attacks (ButtonAttacks)
the same buttons send the dashboard's attack command to the laptop's attack node instead.
"""
import json
import socket
import threading
import time

import pytest

from system.board.board_sender import ButtonAttacks, ButtonLevels, MockButtons, make_board_sender
from link import config


def sender(base, e5=True, buttons=False):
    cfg = config.load(overrides=[f"link.video_in={base}", f"link.fb_out={base + 3}",
                                 f"link.sender_control={base + 5}", f"link.bus=[{base + 10}]",
                                 "link.host=127.0.0.1", "sender.policy=threshold", "sender.mode=E2",
                                 "defence.max_mode=E5", "sender.width=64", "sender.height=48"])
    return make_board_sender(cfg, mock_lanes=2, mock_e5=e5, mock_buttons=buttons)


def test_levels_step_clamp_and_auto():
    s = sender(47520)
    mb = MockButtons()
    mb.press({"n": 1})                                # before the start: must not count
    bl = ButtonLevels(s, mb.read_count, s.cfg["defence"]["max_mode"], log=lambda *a, **k: None)
    seq = [(1, "E1"), (1, "E0"), (1, "E0"), (2, "E1"), (2, "E2"), (2, "E3"), (2, "E4"), (2, "E5"), (2, "E5"),
           (3, None), (2, "E3")]                      # after BTN3 the step starts from the policy's level (E2)
    for i, (b, want) in enumerate(seq):
        mb.press({"n": b})
        bl.poll()
        assert s.manual_mode == want, f"press {i} (BTN{b}): manual level {s.manual_mode}, expected {want}"
    s.measured_fps = 0.0                              # set by Sender.run(), which this test does not start
    s.defence_step()
    assert s.mode == "E3", f"after the defence window the frames use {s.mode}, expected the manual E3"


def test_top_is_e4_without_e5_and_counter_wrap():
    s = sender(47540, e5=False)
    assert s.cfg["defence"]["max_mode"] == "E4"
    mb = MockButtons()
    mb.n[1] = 250                                     # BTN2 counter about to wrap
    bl = ButtonLevels(s, mb.read_count, s.cfg["defence"]["max_mode"], log=lambda *a, **k: None)
    for _ in range(10):
        mb.press({"n": 2})
    bl.poll()                                         # 10 presses across the wrap, seen in one poll
    assert mb.n[1] == 4 and s.manual_mode == "E4", f"counter {mb.n[1]}, level {s.manual_mode} (expected E4)"


def test_rehearsal_over_the_control_port():
    s = sender(47560, buttons=True)                   # starts the 50 ms poller
    threading.Thread(target=s.control_loop, daemon=True).start()
    c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        c.sendto(json.dumps({"cmd": "button", "n": 2}).encode(), ("127.0.0.1", 47565))
        t_end = time.monotonic() + 3
        while s.manual_mode is None and time.monotonic() < t_end:
            time.sleep(0.02)
        assert s.manual_mode == "E3", f"BTN2 over the control port gave {s.manual_mode}, expected E3"
    finally:
        s.running = False
        c.close()


def test_attack_buttons_send_the_dashboards_attack_commands():
    s = sender(47580)
    mb, sent = MockButtons(), []
    ba = ButtonAttacks(s.cfg, mb.read_count, ("replay", "splice", "flood"), 6.0,
                       send=lambda cfg, port, **cmd: sent.append((port, cmd)), log=lambda *a, **k: None)
    for b in (1, 3, 2, 2):
        mb.press({"n": b})
    ba.poll()
    kinds = sorted(c["type"] for _, c in sent)
    assert kinds == ["flood", "replay", "splice", "splice"], f"sent {sent}"
    assert all(p == "control" and c["cmd"] == "attack" and c["duration"] == 6.0 for p, c in sent)
    assert s.manual_mode is None, "attack buttons must not change the protection level"
    with pytest.raises(ValueError, match="needs 3 of"):
        ButtonAttacks(s.cfg, mb.read_count, ("replay", "nonsense", "flood"))


def test_attack_button_reaches_the_attack_node_over_udp():
    base = 47600
    listen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen.bind(("127.0.0.1", base + 4))                # the laptop channel's control port
    listen.settimeout(3)
    cfg = config.load(overrides=[f"link.video_in={base}", f"link.fb_out={base + 3}", f"link.control={base + 4}",
                                 f"link.sender_control={base + 5}", f"link.bus=[{base + 10}]",
                                 "link.host=127.0.0.1", "sender.width=64", "sender.height=48"])
    s = make_board_sender(cfg, mock_lanes=2, mock_e5=True, mock_buttons=True,
                          button_attacks=("bitflip", "replay", "flood"), attack_s=4.0)
    threading.Thread(target=s.control_loop, daemon=True).start()
    c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        c.sendto(json.dumps({"cmd": "button", "n": 2}).encode(), ("127.0.0.1", base + 5))
        got = json.loads(listen.recvfrom(4096)[0])
        assert got == {"cmd": "attack", "type": "replay", "duration": 4.0, "rate": 1.0}, got
    finally:
        s.running = False
        c.close()
        listen.close()
