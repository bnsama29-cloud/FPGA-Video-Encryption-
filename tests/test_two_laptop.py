"""Two-laptop attack setup (docs/BOARD_DAY.html): board -> attacker laptop (link.channel) -> receiver laptop.

    python -m pytest tests/test_two_laptop.py                 (~5 s)
    RUN_SLOW=1 python -m pytest tests/test_two_laptop.py      (adds a three-address loopback run, ~20 s)

Checks the addressing (telemetry to the receiver while video goes to the attacker), the key-exchange relay
in the channel, the attack on the key exchange (every tampered message fails its HMAC; the session key is
only agreed once the attacker stops), and that the printed attacker / board commands use the receiver's ports.
"""
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from link import config, kex, wire
from link.channel import Channel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import scenario  # noqa: E402

PSK = bytes(range(16))


def test_bus_addrs_ports_and_ip_port_entries():
    c = config.load(overrides=["link.host=10.0.0.2", "link.bus=[47210, '10.0.0.9:47010']"])
    assert config.bus_addrs(c) == [("10.0.0.2", 47210), ("10.0.0.9", 47010)]
    c = config.load(overrides=["link.host=10.0.0.2", "link.bus_host=127.0.0.1", "link.bus=[47210]"])
    assert config.bus_addrs(c) == [("127.0.0.1", 47210)]
    assert wire.Bus(c, "t").addrs == [("127.0.0.1", 47210)]


def _sets(cmd):
    """The --set values of a printed command (cmd.exe style double quotes)."""
    toks = shlex.split(cmd)
    return dict(t.split("=", 1) for a, t in zip(toks, toks[1:]) if a == "--set")


def test_printed_commands_match_the_receiver_ports():
    bp = 47200
    atk = _sets(scenario.attacker_command(bp, "192.168.137.20", "192.168.137.99", kex_tamper_s=20))
    brd = _sets(scenario.board_command(bp, "threshold", laptop="192.168.137.1", bus_host="192.168.137.20"))
    # board -> attacker video, attacker -> board feedback
    assert brd["link.host"] == "192.168.137.1" and brd["link.video_in"] == atk["link.video_in"] == str(bp)
    assert brd["link.fb_out"] == atk["link.fb_out"] == str(bp + 3)
    assert atk["link.sender_host"] == "192.168.137.99"
    # attacker -> receiver video (video_out), receiver -> attacker feedback (fb_in), control from the receiver
    assert atk["link.host"] == "192.168.137.20"
    assert (atk["link.video_out"], atk["link.fb_in"], atk["link.control"]) == (str(bp + 1), str(bp + 2), str(bp + 4))
    # telemetry of both ends reaches the logger on the receiver laptop
    assert brd["link.bus_host"] == "192.168.137.20" and brd["link.bus"] == f"[{bp + 10}]"
    c = config.load(overrides=[f"link.bus={atk['link.bus']}", "link.host=192.168.137.20"])
    assert ("192.168.137.20", bp + 10) in config.bus_addrs(c)
    assert atk["channel.kex_relay"] == "true" and atk["channel.kex_tamper_s"] == "20"


def _channel(sets):
    ch = Channel(config.load(overrides=sets))
    threading.Thread(target=ch.run, daemon=True).start()
    return ch


def test_key_exchange_through_attacker_relay_survives_tampering(tmp_path):
    base = 47380
    ports = [f"link.video_in={base}", f"link.video_out={base + 1}", f"link.fb_in={base + 2}",
             f"link.fb_out={base + 3}", f"link.control={base + 4}", f"link.bus=[{base + 10}]"]
    ch = _channel(ports + ["link.host=127.0.0.1", f"link.kex={base + 6}", f"link.kex_rx={base + 7}",
                           "channel.kex_relay=true", "channel.kex_tamper_s=2.0"])
    rx_cfg = config.load(overrides=[f"keys.master={PSK.hex()}", "link.host=127.0.0.1", f"link.kex={base + 7}"])
    tx_cfg = config.load(overrides=[f"keys.master={PSK.hex()}", "link.host=127.0.0.1", f"link.kex={base + 6}"])
    got = {}
    t0 = time.monotonic()
    rx = threading.Thread(target=lambda: got.update(
        rx=kex.run_receiver(rx_cfg, 30, tmp_path / "rx.txt", log=lambda *_: None)))
    rx.start()
    got["tx"] = kex.run_sender(tx_cfg, 30, tmp_path / "tx.txt", log=lambda *_: None)
    took = time.monotonic() - t0
    rx.join(10)
    assert got["rx"] == got["tx"], "both ends must agree on the session key after the attack stops"
    assert ch.stats.get("kex_tampered", 0) >= 1, "the attacker never touched the exchange"
    assert took >= 1.5, f"exchange finished in {took:.2f} s, while every message was being corrupted"


@pytest.mark.skipif(os.getenv("RUN_SLOW") != "1" or not sys.platform.startswith("linux"),
                    reason="RUN_SLOW=1 on Linux (needs 127.0.0.2-4 loopback addresses)")
def test_three_addresses_board_attacker_receiver():
    """Board 127.0.0.4 -> attacker 127.0.0.2 -> receiver 127.0.0.3; attacks started from the receiver side."""
    from link.buslog import BusLogger
    bp = 47400
    B, A, R = "127.0.0.4", "127.0.0.2", "127.0.0.3"
    common = [f"link.video_in={bp}", f"link.video_out={bp + 1}", f"link.fb_in={bp + 2}", f"link.fb_out={bp + 3}",
              f"link.control={bp + 4}", f"link.sender_control={bp + 5}", f"link.bus=[{bp + 10}]",
              "sender.width=160", "sender.height=128", "sender.policy=threshold", "defence.memory_file=''"]
    role = {"sender": [f"link.host={A}", f"link.bind_host={B}", f"link.bus_host={R}"],
            "channel": [f"link.host={R}", f"link.sender_host={B}", f"link.bind_host={A}"],
            "receiver": [f"link.host={A}", f"link.bind_host={R}", f"link.bus_host={R}"]}
    log = BusLogger(bp + 10, host=R)
    procs = [subprocess.Popen([sys.executable, "-m", f"link.{n}"] + [x for s in common + role[n] for x in ("--set", s)],
                              cwd=ROOT, stdout=subprocess.DEVNULL) for n in ("channel", "receiver", "sender")]
    ctl = config.load(overrides=common + role["receiver"])
    try:
        time.sleep(6)
        wire.send_control(ctl, "control", cmd="attack", type="bitflip", duration=4)
        time.sleep(7)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
        log.close()
    frames = log.take("frame", "receiver")
    assert sum(f["verdict"] == "ok" for f in frames) > 20, "no video crossed board -> attacker -> receiver"
    assert "tag-mismatch" in {f["verdict"] for f in frames}, "attack started from the receiver laptop had no effect"
    assert log.take("window", "sender"), "board telemetry did not reach the receiver laptop"
    assert log.take("attack_start", "channel"), "attacker telemetry did not reach the receiver laptop"
