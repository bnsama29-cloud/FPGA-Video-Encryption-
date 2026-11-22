"""Copy one finished paper-2 Kaggle run (its neuro_results_*.zip) into results/neuro/<name>/ so it can be committed.

    python software/scripts/save_kaggle_neuro.py <zip> --name N6_dvs_v3 --kernel samarthium/neuro-paper2-n6-dvs-v3
    python software/scripts/save_kaggle_neuro.py <zip> --name ... --dry-run      only list what would be copied

What it copies, unchanged (result files only): sim_out/neuro/**/{*.json,*.md,*.csv}, run_log.md and logs/*.log.
It skips data_manifests/ (input listings, 9 MB each) and binary arrays (*.npz); files over 20 MB are refused.
It writes README.md (kernel, commits found in the result files) and MANIFEST.md (file, bytes, SHA-256) and adds a
row to results/neuro/README.md. Then: git add results/neuro/<name>, commit, push.
"""
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "results" / "neuro"
KEEP = {".json", ".md", ".csv"}
MAX_BYTES = 20 * 1024 * 1024
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def wanted(member):
    """Path inside the destination for a zip member, or None if it is not a result file."""
    p = Path(member)
    parts = p.parts
    if member.endswith("/") or ".." in parts or p.is_absolute():
        return None
    if "sim_out" in parts:
        i = parts.index("sim_out")
        if parts[i + 1:i + 2] == ("neuro",) and p.suffix in KEEP:
            return Path(*parts[i:])
        return None
    if p.name == "run_log.md":
        return Path("run_log.md")
    if len(parts) >= 2 and parts[-2] == "logs" and p.suffix == ".log":
        return Path("logs") / p.name
    return None


def commits(files):
    """Every meta.commit found in the copied JSON files (the code version each result came from)."""
    out = set()
    for rel, data in files:
        if rel.suffix == ".json":
            try:
                c = json.loads(data).get("meta", {}).get("commit")
            except (ValueError, AttributeError):
                continue
            if c:
                out.add(c)
    return sorted(out)


def collect(zip_path):
    """[(path inside destination, bytes)] of the result files in the zip."""
    files = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            rel = wanted(info.filename)
            if rel is None:
                continue
            if info.file_size > MAX_BYTES:
                raise SystemExit(f"{info.filename}: {info.file_size} bytes > 20 MB, refused")
            files.append((rel, z.read(info)))
    if not any(r.parts[:2] == ("sim_out", "neuro") for r, _ in files):
        raise SystemExit(f"{zip_path}: no sim_out/neuro result files")
    return sorted(files)


def save(zip_path, name, kernel, dest=DEST, dry=False):
    if not NAME_RE.match(name):
        raise SystemExit(f"--name {name!r}: letters, digits, _ . - only")
    files = collect(zip_path)
    out = dest / name
    if dry:
        for rel, data in files:
            print(f"{len(data):>10}  {rel}")
        return out
    if out.exists():
        raise SystemExit(f"{out} exists; results are snapshots, choose a new --name")
    for rel, data in files:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(data)
    cs = commits(files)
    (out / "MANIFEST.md").write_text("| file | bytes | SHA-256 |\n|---|---|---|\n" + "".join(
        f"| `{rel.as_posix()}` | {len(data)} | `{hashlib.sha256(data).hexdigest()}` |\n" for rel, data in files))
    (out / "README.md").write_text(
        f"# {name}\n\nKaggle kernel `{kernel}`, result zip `{Path(zip_path).name}`, copied unchanged by "
        f"`software/scripts/save_kaggle_neuro.py`.\n\nCode commit(s) in the result files: "
        f"{', '.join(f'`{c}`' for c in cs) or 'none recorded'}.\n\nFiles and hashes: `MANIFEST.md`.\n")
    idx = dest / "README.md"
    if not idx.exists():
        idx.write_text("# results/neuro: paper-2 Kaggle runs\n\nOne folder per finished run, copied unchanged by "
                       "`software/scripts/save_kaggle_neuro.py`.\n\n| Folder | Kaggle kernel | Commit(s) |\n|---|---|---|\n")
    with idx.open("a") as f:
        f.write(f"| `{name}/` | `{kernel}` | {', '.join(c[:7] for c in cs)} |\n")
    print(f"{len(files)} files -> {out}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip")
    ap.add_argument("--name", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    save(a.zip, a.name, a.kernel, dry=a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
