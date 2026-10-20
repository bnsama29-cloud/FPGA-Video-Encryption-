"""Fresh pre-shared master key for a demo, and the exact commands that use it on both ends.

    python scripts/demo_key.py            # new key -> configs/demo_key.txt (git-ignored) + commands
    python scripts/demo_key.py --show     # print the commands for the key already saved

Why: configs/default.toml holds a PUBLIC example key (000102...0f, it is in the repository). For a demo
in front of judges, sender and receiver must share a key nobody else has. The design assumes a
pre-shared key (paper, Section IV); this script is how it gets "pre-shared": you run it once, and type
or paste the same key on the laptop and on the board. The key never goes through the dashboard, the
network or git.
"""
import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link.config import _parse_value   # noqa: E402

KEYFILE = ROOT / "configs" / "demo_key.txt"


def new_key():
    """32 hex digits that `--set keys.master=...` keeps as a string (never a TOML int or float)."""
    while True:
        k = secrets.token_hex(16)
        if _parse_value(k) == k:
            return k


def commands(k):
    s = f"--set keys.master={k}"
    return f"""Pre-shared key for this demo (keep it off the screen and out of git): {k}

Laptop only (simulated sender, receiver, attacker, dashboard):
  py -m link.run_all {s} --set dashboard.bind_host=0.0.0.0

Laptop + PYNQ-Z2 (board = camera/sender):
  laptop:  py -m link.run_all --no-sender {s} --set link.bind_host=0.0.0.0 --set link.sender_host=<BOARD IP> --set dashboard.bind_host=0.0.0.0
  board:   python3 -m future_work.board.board_sender --bitfile future_work/board/overlay/secure_jpeg_lanes.bit {s} --set link.host=<LAPTOP IP> --set link.bind_host=0.0.0.0

Wrong-key demo: start the receiver side with a different key (run this script again in another folder,
or change one hex digit). Every frame is then REJECTED (tag check fails) -- the receiver never shows a
wrongly decrypted picture. The 'On the wire' view and VLC still play the scrambled stream.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", action="store_true", help="reuse the saved key instead of making a new one")
    a = ap.parse_args()
    if a.show:
        if not KEYFILE.exists():
            raise SystemExit(f"no saved key: run without --show first ({KEYFILE})")
        k = KEYFILE.read_text().strip()
    else:
        k = new_key()
        KEYFILE.write_text(k + "\n")
    print(commands(k))
    print(f"saved in {KEYFILE} (git-ignored)")


if __name__ == "__main__":
    main()
