"""Post-quantum session key: one hybrid ML-KEM-768 + X25519 exchange at session start (link/keys.py).

    laptop (receiver side):   python -m link.kex --role receiver --set keys.master=<PSK>
    board  (sender side):     python3 -m link.kex --role sender --set keys.master=<PSK> --set link.host=<LAPTOP IP>
    then both:                ... --set keys.master_file=configs/session_key.txt

or simply `python -m link.run_all --pq-kex ...` on the laptop and `board_sender ... --pq-kex` on the board,
which run this exchange first and then start the link with the new key.

The pre-shared key (keys.master) only AUTHENTICATES the exchange; the session's master key comes from
the exchange, so a recorded session stays secret even if the pre-shared key leaks later or a quantum
computer breaks X25519 (ML-KEM-768, FIPS 203). The FPGA is unchanged: it just gets a different
128-bit key. The key is written to configs/session_key.txt (git-ignored, owner-only) and never printed.

UDP on link.kex (default 47006, receiver listens), directly between the two ends:
    sender   -> receiver  SVK0                (please start)
    receiver -> sender    M1                  (ML-KEM public key + X25519 share, authenticated)
    sender   -> receiver  M2                  (ciphertext + X25519 share, authenticated)
    receiver -> sender    SVK3 | confirm      (proof that both derived the same key)
Lost datagrams are retried; a forged or replayed message fails its HMAC and is ignored.
"""
import os
import socket
import time
from pathlib import Path

from . import config, keys

ROOT = Path(__file__).resolve().parents[1]
KEYFILE = ROOT / "configs" / "session_key.txt"


def _write_key(k, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(k.hex() + "\n")
    return path


def run_receiver(cfg, timeout=120.0, keyfile=KEYFILE, log=print):
    """Laptop side. Returns the 16-byte session master key (also written to keyfile)."""
    psk = bytes.fromhex(cfg["keys"]["master"])
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((config.bind_host(cfg), cfg["link"]["kex"]))
    s.settimeout(0.5)
    t_end = time.monotonic() + timeout
    state = m1 = peer = None
    done = None                                   # (m2, confirm) once finished: answer resent M2 again
    try:
        while time.monotonic() < t_end:
            try:
                d, addr = s.recvfrom(4096)
            except socket.timeout:
                if done:
                    return done[2]
                continue
            if d[:4] == b"SVK0" and done is None:
                state, m1 = keys.kex_init(psk)
                peer = addr
                s.sendto(m1, addr)
            elif d[:4] == keys.KEX_MAGIC2 and state is not None and addr == peer:
                if done and d == done[0]:
                    s.sendto(b"SVK3" + done[1], addr)          # our confirm got lost
                    continue
                try:
                    k = keys.kex_finish(psk, state, d)
                except keys.KexError as e:
                    log(f"kex: ignored M2 from {addr[0]}: {e}")
                    continue
                conf = keys.key_confirm(k, m1, d, "receiver")
                s.sendto(b"SVK3" + conf, addr)
                _write_key(k, keyfile)
                log(f"kex: session key established with {addr[0]} (ML-KEM-768 + X25519, "
                    f"{state['backend']}), written to {keyfile}")
                done = (d, conf, k)
                t_end = min(t_end, time.monotonic() + 3.0)   # linger: answer a retransmitted M2
        if done:
            return done[2]
        raise TimeoutError("kex: no sender completed the exchange")
    finally:
        s.close()


def run_sender(cfg, timeout=120.0, keyfile=KEYFILE, log=print):
    """Board side. Returns the 16-byte session master key (also written to keyfile)."""
    psk = bytes.fromhex(cfg["keys"]["master"])
    addr = (cfg["link"]["host"], cfg["link"]["kex"])
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.5)
    t_end = time.monotonic() + timeout
    k = m1 = m2 = None
    try:
        while time.monotonic() < t_end:
            s.sendto(m2 if m2 else b"SVK0", addr)
            try:
                d, _ = s.recvfrom(4096)
            except (socket.timeout, ConnectionRefusedError):
                continue
            if d[:4] == keys.KEX_MAGIC1 and m2 is None:
                try:
                    k, m2 = keys.kex_respond(psk, d)
                    m1 = d
                except keys.KexError as e:
                    log(f"kex: ignored M1: {e}")
            elif d[:4] == b"SVK3" and m2 is not None:
                if d[4:] == keys.key_confirm(k, m1, m2, "receiver"):
                    _write_key(k, keyfile)
                    log(f"kex: session key established with {addr[0]} (ML-KEM-768 + X25519), written to {keyfile}")
                    return k
                log("kex: key confirmation did not match (ignored)")
        raise TimeoutError(f"kex: no answer from the receiver at {addr[0]}:{addr[1]}")
    finally:
        s.close()


def main():
    import argparse
    ap = config.add_args(argparse.ArgumentParser(description=__doc__,
                                                 formatter_class=argparse.RawDescriptionHelpFormatter))
    ap.add_argument("--role", choices=["receiver", "sender"], required=True)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--keyfile", default=str(KEYFILE))
    a = ap.parse_args()
    cfg = config.load(a.config, a.set)
    (run_receiver if a.role == "receiver" else run_sender)(cfg, a.timeout, a.keyfile)
    print(f"next: start the link with --set keys.master_file={a.keyfile}")


if __name__ == "__main__":
    main()
