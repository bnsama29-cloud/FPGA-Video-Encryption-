"""Put the PYNQ-Z2 board images into git, so a fresh clone can run on the board.

Run it on the PC that built them (Vivado PC), from the repo root, after vivado/run_vivado_day.py:

    py scripts\\publish_bitstreams.py            check, write overlay/MANIFEST.md + .json, git add
    git commit -m "Board images of run 12 + 13"
    git push

    py scripts\\publish_bitstreams.py --check    only check (laptop, or on the board after copying)

What it checks, for every image in system/board/bitstreams.json:
  * the .bit is there with its .hwh (PYNQ needs both, same name, same folder);
  * the SHA-256 starts with the prefix recorded when the image was built (run 12 / run 13). A different hash
    means a different build: it stops, unless --force (say in the commit which run built it);
  * with --check, the files also match MANIFEST.json if one was published (a broken or partial copy).
Missing optional images are listed, not an error. It stages only the .bit/.hwh files and the manifest, never
the report folders (overlay/<design>/, ignored by .gitignore).
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "system" / "board" / "bitstreams.json"
OVERLAY = ROOT / "system" / "board" / "overlay"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def images(list_path=LIST):
    return json.loads(Path(list_path).read_text(encoding="utf-8"))["images"]


def check(overlay=OVERLAY, list_path=LIST, force=False, use_manifest=True):
    """One row per image: dict(file, status, problem, sha256, hwh_sha256, bytes, image). status is
    ok | missing | error; `problem` says why. MANIFEST.json (if there and use_manifest) wins over the prefixes."""
    overlay = Path(overlay)
    manifest = {}
    mpath = overlay / "MANIFEST.json"
    if use_manifest and mpath.exists():
        manifest = {m["file"]: m for m in json.loads(mpath.read_text(encoding="utf-8"))["images"]}
    rows = []
    for im in images(list_path):
        bit = overlay / im["file"]
        hwh = bit.with_suffix(".hwh")
        row = dict(file=im["file"], image=im, sha256=None, hwh_sha256=None, bytes=None, status="ok", problem="")
        if not bit.exists():
            row.update(status="missing" if not im.get("required") else "error",
                       problem="not here" + (" (required)" if im.get("required") else " (optional)"))
            rows.append(row)
            continue
        row.update(sha256=sha256(bit), bytes=bit.stat().st_size)
        if not hwh.exists():
            row.update(status="error", problem=f"no {hwh.name} next to it (PYNQ needs both)")
            rows.append(row)
            continue
        row["hwh_sha256"] = sha256(hwh)
        m = manifest.get(im["file"])
        if m:
            if (m["sha256"], m.get("hwh_sha256")) != (row["sha256"], row["hwh_sha256"]):
                row.update(status="error", problem="differs from MANIFEST.json (incomplete copy or another build)")
        elif im.get("sha256_prefix") and not row["sha256"].startswith(im["sha256_prefix"]):
            if force:
                row["problem"] = f"hash is not the {im['run']} build ({im['sha256_prefix']}...): accepted with --force"
            else:
                row.update(status="error", problem=f"hash {row['sha256'][:16]} is not the {im['run']} build "
                                                   f"({im['sha256_prefix']}...); --force to publish it anyway")
        rows.append(row)
    return rows


def manifest(rows, commit=""):
    ok = [r for r in rows if r["status"] == "ok"]
    js = dict(commit=commit, images=[dict(file=r["file"], bytes=r["bytes"], sha256=r["sha256"],
                                         hwh_sha256=r["hwh_sha256"], run=r["image"]["run"],
                                         clock_mhz=r["image"]["clock_mhz"], version=r["image"]["version"])
                                    for r in ok])
    md = ["# PYNQ-Z2 board images",
          "",
          "Written by `scripts/publish_bitstreams.py`" + (f" at commit `{commit[:10]}`" if commit else "") + ". "
          "Copy each `.bit` with its `.hwh` to the board (same folder). Check a copy with "
          "`python3 scripts/publish_bitstreams.py --check` (on the board: `cd /home/xilinx/fpga` first).",
          "",
          "| File | Purpose | Clock | VERSION | Built by | Bytes | SHA-256 |",
          "|---|---|---|---|---|---|---|"]
    for r in ok:
        im = r["image"]
        md.append(f"| `{r['file']}` | {im['purpose']} | {im['clock_mhz']} MHz | `{im['version']}` | {im['run']} "
                  f"(`--steps {im['step']}`) | {r['bytes']:,} | `{r['sha256']}` |")
    return js, "\n".join(md) + "\n"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def report(rows):
    for r in rows:
        tag = {"ok": "ok     ", "missing": "missing", "error": "ERROR  "}[r["status"]]
        h = r["sha256"][:16] if r["sha256"] else ""
        print(f"  {tag} {r['file']:<30} {h:<16} {r['problem']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="only check the files; write and stage nothing")
    ap.add_argument("--force", action="store_true", help="publish images whose hash is not the recorded build")
    ap.add_argument("--no-git", action="store_true", help="write the manifest but do not git add")
    ap.add_argument("--overlay", type=Path, default=OVERLAY, help=argparse.SUPPRESS)
    ap.add_argument("--list", type=Path, default=LIST, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    rows = check(a.overlay, a.list, force=a.force, use_manifest=a.check)
    print(f"Board images in {a.overlay}:")
    report(rows)
    errors = [r for r in rows if r["status"] == "error"]
    if a.check:
        n = sum(r["status"] == "ok" for r in rows)
        print(f"{n} of {len(rows)} images ok" + (f", {len(errors)} with errors" if errors else ""))
        return 1 if errors else 0
    if errors:
        print("Nothing published: fix the errors above (copy the run-12 / run-13 overlay folder here, "
              "or rebuild with vivado/run_vivado_day.py --steps <step>).")
        return 1
    commit = git("rev-parse", "HEAD").stdout.strip() if not a.no_git else ""
    js, md = manifest(rows, commit)
    (a.overlay / "MANIFEST.json").write_text(json.dumps(js, indent=1) + "\n", encoding="utf-8")
    (a.overlay / "MANIFEST.md").write_text(md, encoding="utf-8")
    files = [a.overlay / r["file"] for r in rows if r["status"] == "ok"]
    files += [f.with_suffix(".hwh") for f in files] + [a.overlay / "MANIFEST.json", a.overlay / "MANIFEST.md"]
    print(f"wrote {a.overlay / 'MANIFEST.md'}")
    if a.no_git:
        return 0
    r = git("add", "--", *[str(f) for f in files])
    if r.returncode:
        print(r.stderr.strip())
        return 1
    print(f"staged {len(files)} files. Now:\n  git commit -m \"Board images (run 12 + run 13)\"\n  git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
