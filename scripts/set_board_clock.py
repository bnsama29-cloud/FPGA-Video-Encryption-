"""Set the board's clock to the laptop's, to about a millisecond, so the link's latency is right.

Why: the receiver measures latency as (its clock) - (the sender's timestamp), and the dashboard's reaction time
compares a laptop event with a board event. Both need the two clocks to agree. The PYNQ-Z2 has no battery clock
and no internet on the direct cable, so it boots with an old date (May 2025): latency then reads ~4.6e10 ms and the
reaction time is negative. Run this after every board power-up, before the live link (BOARD_STEPS.md step 13).

Run on the laptop, from the repo folder (the board needs nothing new):

    py scripts\\set_board_clock.py                       board at 192.168.2.99 (direct cable)
    py scripts\\set_board_clock.py --board 192.168.1.50  board on a router
    py scripts\\set_board_clock.py --check               only measure the difference, change nothing

It asks for the ssh password (xilinx) and then sudo's password (xilinx) on the board. Running link programs keep
going: they read the clock on every frame.

How: the laptop answers time requests on UDP port 47008 (inside the firewall rule of step 12). Over ssh the
board runs this same file with --on-board: it asks 20 times, keeps the answer with the shortest round trip, and
sets its clock to laptop time + half that round trip (NTP's method). The error is at most half the round trip,
under 1 ms on the cable. Then it measures again and prints the difference that is left.
"""
import argparse
import base64
import socket
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

PORT = 47008
ASK = b"time?"


def serve(sock, stop, count, clock=time.time):
    """Laptop side: answer every request with this machine's time."""
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(64)
        except socket.timeout:
            continue
        except OSError:
            return
        if data == ASK:
            sock.sendto(repr(clock()).encode(), addr)
            count[0] += 1


def sample(sock, addr, n=20, wait=0.5):
    """Board side: n requests. Returns (round trip s, laptop time, local time at the reply), each request."""
    out = []
    for _ in range(n):
        t0, m0 = time.time(), time.monotonic()
        sock.sendto(ASK, addr)
        try:
            data, _ = sock.recvfrom(64)
        except socket.timeout:
            continue
        m1 = time.monotonic()
        out.append((m1 - m0, float(data), t0 + (m1 - m0)))
        time.sleep(0.01)
    if not out:
        raise SystemExit(f"no answer from the laptop at {addr[0]}:{addr[1]} (UDP). Is the firewall rule of "
                         "step 12 there, and the laptop's set_board_clock still running?")
    return out


def offset_ms(samples):
    """Median of laptop - board at the midpoint of each round trip, in ms (NTP offset)."""
    return statistics.median((lap - (t1 - rtt / 2)) * 1000 for rtt, lap, t1 in samples)


def on_board(laptop, port=PORT, check=False, settime=None):
    """Board side: measure, set the clock (unless check), measure again. Returns the offset left, in ms."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    addr = (laptop, port)
    before = sample(sock, addr)
    print(f"board clock was {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}, "
          f"{offset_ms(before) / 1000:+.3f} s from the laptop")
    if check:
        return offset_ms(before)
    rtt, lap, t1 = min(before, key=lambda s: s[0])
    target = lap + rtt / 2 + (time.time() - t1)       # laptop time at that reply, plus the time since
    (settime or (lambda t: time.clock_settime(time.CLOCK_REALTIME, t)))(target)
    left = offset_ms(sample(sock, addr))
    print(f"board clock set to {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}; "
          f"shortest round trip {rtt * 1000:.2f} ms, difference left {left:+.2f} ms")
    return left


def ssh_command(board, user="xilinx", check=False):
    """The ssh call that runs this file on the board. No quotes inside, so Windows, ssh and bash pass it as is."""
    code = base64.b64encode(Path(__file__).read_bytes()).decode()
    py = "python3" if check else "sudo python3"
    remote = (f"echo {code} | base64 -d > /tmp/set_board_clock.py && "
              f"{py} /tmp/set_board_clock.py --on-board ${{SSH_CLIENT%% *}}" + (" --check" if check else ""))
    return ["ssh", "-t", f"{user}@{board}", remote]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", default="192.168.2.99")
    ap.add_argument("--user", default="xilinx")
    ap.add_argument("--check", action="store_true", help="only measure the difference, do not set the clock")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--on-board", metavar="LAPTOP_IP", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.on_board:
        on_board(a.on_board, a.port, a.check)
        return 0
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", a.port))
    sock.settimeout(0.2)
    stop, count = threading.Event(), [0]
    threading.Thread(target=serve, args=(sock, stop, count), daemon=True).start()
    print(f"answering time requests on UDP {a.port}; connecting to {a.user}@{a.board} "
          "(ssh password xilinx, then sudo password xilinx)")
    try:
        rc = subprocess.run(ssh_command(a.board, a.user, a.check)).returncode
    finally:
        stop.set()
    print(f"answered {count[0]} requests" + ("" if rc == 0 else f"; ssh exit {rc}"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
