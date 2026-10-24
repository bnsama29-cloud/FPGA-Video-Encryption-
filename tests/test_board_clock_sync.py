"""scripts/set_board_clock.py: the board takes the laptop's time over UDP (NTP's method), so the link's latency
and the dashboard's reaction time are right although the board boots with an old date."""
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import set_board_clock as sbc          # noqa: E402


def _laptop(offset_s):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(0.05)
    stop, count = threading.Event(), [0]
    threading.Thread(target=sbc.serve, args=(sock, stop, count, lambda: time.time() + offset_s),
                     daemon=True).start()
    return sock.getsockname()[1], stop, count


def test_board_sets_its_clock_to_the_laptops():
    offset = 46539323.062                                   # the board was ~539 days behind on 24 Oct 2026
    port, stop, count = _laptop(offset)
    got = []
    try:
        sbc.on_board("127.0.0.1", port, settime=lambda t: got.append((t - (time.time() + offset)) * 1000))
        assert sbc.on_board("127.0.0.1", port, check=True) == \
            __import__("pytest").approx(offset * 1000, abs=20)
    finally:
        stop.set()
    assert len(got) == 1, "the clock must be set once"
    err_ms = got[0]
    assert abs(err_ms) < 20, f"set {err_ms:+.1f} ms away from the laptop's time"
    assert count[0] >= 40


def test_ssh_command_has_no_quotes_and_runs_this_file():
    cmd = sbc.ssh_command("192.168.2.99")
    assert cmd[:3] == ["ssh", "-t", "xilinx@192.168.2.99"]
    remote = cmd[3]
    assert '"' not in remote and "'" not in remote, "quotes get mangled between Windows, ssh and bash"
    assert "sudo python3 /tmp/set_board_clock.py --on-board ${SSH_CLIENT%% *}" in remote
    assert "sudo" not in sbc.ssh_command("b", check=True)[3]
