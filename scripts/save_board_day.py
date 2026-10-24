"""Copy the board-day results from sim_out/ (git-ignored) into paper/data/board/<name>/ so they can be committed.

Run on the laptop, from the repo folder, after `py scripts\\pull_board_results.py`:

    py scripts\\save_board_day.py                          -> paper/data/board/board_day_24oct/
    py scripts\\save_board_day.py --name board_day_12nov   another day
    py scripts\\save_board_day.py --dry-run                only list what would be copied

What it copies (result files only: .json .md .csv .jsonl .txt):
  sim_out/board/<every run>/         first_contact, arm_baseline (copied from the board)
  sim_out/pq_kex/                    key-exchange cost on the board
  sim_out/runs/board_* and hw_tamper*  the live-link runs with the board as the sender (A6, tamper)
  future_work/baselines/power_template.{md,json,csv}  the energy table
It writes MANIFEST.md (file, bytes, SHA-256, source) next to them, skips files over 20 MB, and stops if any
file contains the demo key (configs/demo_key.txt) or the session key: those are never committed.
Then: git add paper/data/board/<name>, commit, push (HOW_TO_RUN.md, "Saving board results to git").
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "sim_out"
KEEP = {".json", ".md", ".csv", ".jsonl", ".txt"}
MAX_BYTES = 20 * 1024 * 1024


def sources(root=ROOT):
    """(source file, path inside the destination) for every result file to save."""
    sim = root / "sim_out"
    out = []

    def tree(base, under, pick=lambda p: True):
        if base.exists():
            for d in sorted(p for p in base.iterdir() if p.is_dir() and pick(p)):
                for f in sorted(d.rglob("*")):
                    if f.is_file() and f.suffix in KEEP:
                        out.append((f, Path(under) / f.relative_to(base)))
    tree(sim / "board", "board")
    if (sim / "pq_kex").exists():
        out += [(f, Path("pq_kex") / f.name) for f in sorted((sim / "pq_kex").glob("*")) if f.suffix in KEEP]
    tree(sim / "runs", "runs", lambda p: p.name.startswith(("board_", "hw_tamper")))
    for ext in (".md", ".json", ".csv"):
        f = root / "future_work" / "baselines" / f"power_template{ext}"
        if f.exists():
            out.append((f, Path("energy") / f.name))
    return out


def known_keys(root=ROOT):
    keys = []
    for f in (root / "configs" / "demo_key.txt", root / "configs" / "session_key.txt"):
        if f.exists():
            k = f.read_text(errors="ignore").strip()
            if len(k) >= 16:
                keys.append(k)
    return keys


def save(dest, root=ROOT, dry_run=False):
    files = sources(root)
    keys = known_keys(root)
    rows, skipped = [], []
    for src, rel in files:
        size = src.stat().st_size
        if size > MAX_BYTES:
            skipped.append(f"{rel} ({size / 1e6:.0f} MB, too big for git)")
            continue
        data = src.read_bytes()
        leak = [k for k in keys if k.encode() in data or k.lower().encode() in data]
        if leak:
            raise SystemExit(f"STOP: {src} contains your demo or session key; nothing was copied. "
                             "Tell Claude which file this is.")
        rows.append((src, rel, size, hashlib.sha256(data).hexdigest()))
    if not dry_run:
        for src, rel, _, _ in rows:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
        md = ["# Board-day results (copied by scripts/save_board_day.py)", "",
              "| File | Bytes | SHA-256 | Copied from |", "|---|---|---|---|"]
        md += [f"| `{rel.as_posix()}` | {size:,} | `{sha[:16]}…` | `{src.relative_to(root).as_posix()}` |"
               for src, rel, size, sha in rows]
        (dest / "MANIFEST.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return rows, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="board_day_24oct", help="folder under paper/data/board/")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    dest = ROOT / "paper" / "data" / "board" / a.name
    rows, skipped = save(dest, dry_run=a.dry_run)
    if not rows:
        print("nothing found in sim_out/: run py scripts\\pull_board_results.py first")
        return 1
    folders = sorted({r[1].parent.as_posix() for r in rows})
    total = sum(r[2] for r in rows)
    print(("would copy" if a.dry_run else "copied") + f" {len(rows)} files, {total / 1e6:.1f} MB, to "
          f"{dest.relative_to(ROOT).as_posix()}/:")
    for f in folders:
        print("  " + f)
    for s in skipped:
        print("  skipped " + s)
    if not a.dry_run:
        print(f"\nnext:  git add paper/data/board/{a.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
