"""Copy the board's results to the laptop (a checkpoint), and show which board-day runs are done.

Run on the laptop, from the repo folder, after every board step (it only reads from the board, so it is safe
while a run is going):

    py scripts\\pull_board_results.py                       board at 192.168.2.99 (direct cable)
    py scripts\\pull_board_results.py --board 192.168.1.50  board on a router
    py scripts\\pull_board_results.py --status              no copy: only list what the laptop already has

What it does:
  * one ssh call (password xilinx) packs /home/xilinx/fpga/sim_out/board and sim_out/pq_kex on the board;
  * keeps that pack as sim_out/board_backups/board_<date>_<time>.tgz (every checkpoint, never overwritten);
  * unpacks it into sim_out/ here, so sim_out/board/<run>/ always holds the newest copy;
  * lists every run: done (with its bit-exact verdict), or stopped after N levels (rerun the same board command
    with --resume to continue), plus the laptop-side runs in sim_out/runs/.
A run that is still going shows as "stopped after N levels" until it finishes: that is its last saved level.
"""
import argparse
import io
import json
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "sim_out"
BACKUPS = SIM / "board_backups"
PULLED = ("sim_out/board", "sim_out/pq_kex")


def pull(board, user="xilinx", remote="/home/xilinx/fpga", ssh="ssh"):
    """Pack the board's result folders over ssh. Returns the bytes of the .tgz (empty if nothing there)."""
    cmd = (f"cd {remote} && d=$(ls -d {' '.join(PULLED)} 2>/dev/null); "
           f"[ -n \"$d\" ] && tar czf - $d || true")
    r = subprocess.run([ssh, f"{user}@{board}", cmd], stdout=subprocess.PIPE)
    if r.returncode:
        raise SystemExit(f"ssh {user}@{board} failed (exit {r.returncode}): is the board on, and the address right?")
    return r.stdout


def unpack(data, dest=ROOT):
    """Unpack only sim_out/board/... and sim_out/pq_kex/... files; returns how many files were written."""
    n = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            p = Path(m.name)
            if p.is_absolute() or ".." in p.parts or not m.name.startswith(PULLED) or not (m.isfile() or m.isdir()):
                continue
            target = dest / p
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tf.extractfile(m).read())
            n += 1
    return n


def board_rows(sim=SIM):
    """(folder, state, detail) for every run folder under sim_out/board."""
    rows = []
    base = sim / "board"
    for d in sorted(p for p in base.glob("*") if p.is_dir()) if base.exists() else []:
        fc, arm, prog = d / "first_contact.json", d / "arm_baseline.json", d / "bitexact_progress.json"
        if fc.exists():
            r = json.loads(fc.read_text())
            n = {x.get("frames") for x in r.get("exactness", [])}
            frames = n.pop() if len(n) == 1 else "?"
            verdict = ("bit-exact yes" if r.get("all_bit_exact") else "bit-exact NO") + f" ({frames} frames each)"
            if frames == 0:
                verdict = "timing only (0 frames checked)"
            rows.append((d.name, "done", f"{verdict}, {len(r.get('speed', []))} timing rows"))
        elif arm.exists():
            rows.append((d.name, "done", "ARM baseline"))
        elif prog.exists():
            r = json.loads(prog.read_text())
            ok = sum(x["bit_exact"] for x in r["rows"])
            bad = [f"{x['size']} E{x['mode']}" for x in r["rows"] if not x["bit_exact"]]
            rows.append((d.name, "stopped", f"after {len(r['rows'])} levels ({ok} bit-exact"
                         + (f", MISMATCH at {', '.join(bad)}" if bad else "") + "): same command + --resume"))
        else:
            rows.append((d.name, "empty", "no result file"))
    for f in sorted((sim / "pq_kex").glob("*.md")) if (sim / "pq_kex").exists() else []:
        rows.append((f"pq_kex/{f.name}", "done", "key-exchange cost"))
    return rows


def laptop_rows(sim=SIM):
    rows = []
    runs = sim / "runs"
    for d in sorted(p for p in runs.glob("*") if p.is_dir()) if runs.exists() else []:
        if (d / "hw_tamper.md").exists() or (d / "summary.json").exists():
            rows.append((f"runs/{d.name}", "done", "hw_tamper.md" if (d / "hw_tamper.md").exists() else "summary.json"))
        else:
            rows.append((f"runs/{d.name}", "unfinished", "no summary yet: run it again with the same --out"))
    if (ROOT / "system" / "baselines" / "power_template.md").exists():
        rows.append(("system/baselines/power_template.md", "done", "energy table"))
    return rows


def show(rows, title):
    print(title)
    if not rows:
        print("  (nothing yet)")
    w = max((len(r[0]) for r in rows), default=0)
    for name, state, detail in rows:
        print(f"  {state:<10} {name:<{w}}  {detail}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", default="192.168.2.99")
    ap.add_argument("--user", default="xilinx")
    ap.add_argument("--remote", default="/home/xilinx/fpga")
    ap.add_argument("--status", action="store_true", help="no copy, only list what is on the laptop")
    a = ap.parse_args(argv)
    if not a.status:
        print(f"copying sim_out/board and sim_out/pq_kex from {a.user}@{a.board} (password: xilinx) ...")
        data = pull(a.board, a.user, a.remote)
        if not data:
            print("nothing on the board yet (no sim_out/board or sim_out/pq_kex)")
        else:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            bk = BACKUPS / time.strftime("board_%Y%m%d_%H%M%S.tgz")
            bk.write_bytes(data)
            n = unpack(data)
            print(f"saved {n} files into {SIM}; checkpoint kept as {bk.relative_to(ROOT)}")
    show(board_rows(), "\nBoard runs (sim_out/board, copied from the board):")
    show(laptop_rows(), "\nLaptop runs:")
    return 0


if __name__ == "__main__":
    sys.exit(main())
