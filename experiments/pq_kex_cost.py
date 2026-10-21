"""Cost of the post-quantum session key (link/keys.py, link/kex.py) on this machine.

    python experiments/pq_kex_cost.py                 # laptop
    python3 experiments/pq_kex_cost.py --runs 20      # on the PYNQ-Z2 (ARM Cortex-A9): the number for the paper

Times (median of --runs, wall clock) each end's work: the receiver's M1 (ML-KEM-768 key generation +
X25519 key) and finish (decapsulation + X25519), the sender's answer (encapsulation + X25519), for every
ML-KEM implementation present, plus the bytes on the wire. It runs once per session, so the question is
only whether it is short against a session (seconds), not against a frame.
Writes sim_out/pq_kex/<machine>.json and .md.
"""
import argparse
import json
import platform
import socket
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from link import keys  # noqa: E402

PSK = bytes(range(16))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--out", default=str(ROOT / "sim_out" / "pq_kex"))
    a = ap.parse_args()
    machine = f"{platform.machine()}_{socket.gethostname()}"
    res = dict(machine=platform.machine(), host=socket.gethostname(), python=platform.python_version(),
               m1_bytes=keys.M1_LEN, m2_bytes=keys.M2_LEN, confirm_bytes=4 + 16, runs=a.runs, backends={})
    for b in ("cryptography", "kyber-py"):
        try:
            keys.mlkem_backend(b)
        except RuntimeError:
            continue
        t = dict(receiver_init=[], sender_respond=[], receiver_finish=[])
        for _ in range(a.runs):
            t0 = time.perf_counter(); st, m1 = keys.kex_init(PSK, b)
            t1 = time.perf_counter(); k, m2 = keys.kex_respond(PSK, m1, b)
            t2 = time.perf_counter(); k2 = keys.kex_finish(PSK, st, m2)
            t3 = time.perf_counter()
            assert k == k2
            t["receiver_init"].append(t1 - t0); t["sender_respond"].append(t2 - t1); t["receiver_finish"].append(t3 - t2)
        res["backends"][b] = {k: 1000 * statistics.median(v) for k, v in t.items()}
        res["backends"][b]["total_ms"] = sum(res["backends"][b].values())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{machine}.json").write_text(json.dumps(res, indent=1))
    md = [f"# Post-quantum session key on `{res['host']}` ({res['machine']}, Python {res['python']})", "",
          f"Hybrid ML-KEM-768 + X25519, authenticated by the pre-shared key; median of {a.runs} runs. "
          f"Wire: M1 {res['m1_bytes']} B, M2 {res['m2_bytes']} B, confirm {res['confirm_bytes']} B (one datagram each).", "",
          "| ML-KEM implementation | receiver M1 (ms) | sender answer (ms) | receiver finish (ms) | total (ms) |",
          "|---|---|---|---|---|"]
    for b, v in res["backends"].items():
        md.append(f"| {b} | {v['receiver_init']:.2f} | {v['sender_respond']:.2f} | {v['receiver_finish']:.2f} | {v['total_ms']:.2f} |")
    (out / f"{machine}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
