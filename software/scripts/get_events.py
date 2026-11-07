"""Download the paper-2 event datasets with a SHA-256 manifest (DESIGN §8.3). Run on Kaggle by kaggle_neuro.py.

    python software/scripts/get_events.py --out /kaggle/working/data nmnist dvsgesture eventreid
    python software/scripts/get_events.py --out data eventreid --list        (sizes only, no download)

  nmnist      N-MNIST through Tonic 1.7.0 (tonic.datasets.NMNIST, train + test), into <out>/nmnist
  dvsgesture  DVS Gesture (official train/test files, Tonic 1.7.0 layout), into <out>/dvsgesture. The two archives
              ibmGestureTrain.tar.gz / ibmGestureTest.tar.gz are taken from an attached Kaggle dataset when present
              (any folder under --inputs, default /kaggle/input), else downloaded from figshare (files 38022171,
              38020584); either way checked against Tonic's MD5 and placed where Tonic looks, so Tonic never
              downloads itself (its own download failed on Kaggle, 7 Nov 2026)
  eventreid   Event-ReId from Zenodo record 8256439 (doi 10.5281/zenodo.8256439), every file of the record,
              into <out>/eventreid; zip/tar archives are extracted. --max-gb refuses a record larger than that.
Each dataset is fetched on its own: a failure is reported and the others still run (exit code 1 at the end).
Writes <out>/<name>/MANIFEST.json (neuro.datasets.manifest: SHA-256 and size per file) and prints the totals.
"""
import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "software"), str(ROOT)]
from neuro import datasets  # noqa: E402

ZENODO = "https://zenodo.org/api/records/8256439"
UA = {"User-Agent": "neuro-event-fetch/1 (research; python urllib)"}


def zenodo_files():
    with urllib.request.urlopen(urllib.request.Request(ZENODO, headers=UA), timeout=60) as r:
        rec = json.load(r)
    out = []
    for f in rec.get("files", []):
        link = f.get("links", {}).get("self") or f.get("links", {}).get("download")
        out.append({"key": f["key"], "size": int(f.get("size", 0)), "url": link, "checksum": f.get("checksum")})
    return out


def download(url, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.replace(dst)


def safe_extract(archive, dest):
    """Extract zip/tar without letting a member escape dest (path traversal guard)."""
    dest = dest.resolve()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for m in z.namelist():
                if not (dest / m).resolve().is_relative_to(dest):
                    raise ValueError(f"{archive}: member {m} escapes the target folder")
            z.extractall(dest)
        return True
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="data")
        return True
    return False


def get_eventreid(out, max_gb, list_only):
    files = zenodo_files()
    total = sum(f["size"] for f in files)
    print(f"Event-ReId (Zenodo 8256439): {len(files)} files, {total / 1e9:.2f} GB")
    for f in files:
        print(f"  {f['key']}  {f['size'] / 1e6:.1f} MB  {f['checksum']}")
    if list_only:
        return {"files": files, "total_bytes": total}
    if total > max_gb * 1e9:
        raise SystemExit(f"Event-ReId is {total / 1e9:.1f} GB > --max-gb {max_gb}: not downloaded")
    d = out / "eventreid"
    for f in files:
        p = d / f["key"]
        if not p.exists():
            download(f["url"], p)
        if p.suffix.lower() in (".zip", ".tar", ".gz", ".tgz") and safe_extract(p, d / p.stem):
            p.unlink()
    return {"files": files, "total_bytes": total}


GESTURE = {  # Tonic 1.7.0 tonic/datasets/dvsgesture.py
    True: ("ibmGestureTrain.tar.gz", "https://figshare.com/ndownloader/files/38022171", "3a8f0d4120a166bac7591f77409cb105"),
    False: ("ibmGestureTest.tar.gz", "https://figshare.com/ndownloader/files/38020584", "56070e45dadaa85fff82e0fbfbc06de5"),
}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def stage_gesture(out, inputs):
    """Put both DVS Gesture archives, MD5-checked, into <out>/dvsgesture/DVSGesture/ (Tonic's location)."""
    dst_dir = out / "dvsgesture" / "DVSGesture"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for train, (fname, url, want) in GESTURE.items():
        dst = dst_dir / fname
        if dst.exists() and md5(dst) == want:
            continue
        found = sorted(Path(inputs).rglob(fname)) if Path(inputs).exists() else []
        if found:
            print(f"DVS Gesture: using {found[0]}")
            shutil.copy(found[0], dst)
        else:
            print(f"DVS Gesture: {fname} not under {inputs}; downloading {url}")
            download(url, dst)
        got = md5(dst)
        if got != want:
            dst.unlink()
            raise RuntimeError(f"{fname}: MD5 {got} != {want}. Download both archives in a browser from figshare "
                               f"(DVS Gesture, files 38022171 and 38020584) and attach them as a Kaggle dataset")


def get_tonic(name, out, inputs="/kaggle/input"):
    if name == "dvsgesture":
        stage_gesture(out, inputs)
    import tonic
    cls = {"nmnist": tonic.datasets.NMNIST, "dvsgesture": tonic.datasets.DVSGesture}[name]
    for train in (True, False):
        ds = cls(save_to=str(out / name), train=train)
        print(f"{name} {'train' if train else 'test'}: {len(ds)} samples")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+", choices=["nmnist", "dvsgesture", "eventreid"])
    ap.add_argument("--out", type=Path, default=ROOT / "data")
    ap.add_argument("--max-gb", type=float, default=40.0)
    ap.add_argument("--list", action="store_true", help="Event-ReId: print the record's files only")
    ap.add_argument("--inputs", default="/kaggle/input", help="where attached archives are looked for")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    failed = []
    for n in a.names:
        try:
            if n == "eventreid":
                get_eventreid(a.out, a.max_gb, a.list)
                if a.list:
                    continue
            else:
                get_tonic(n, a.out, a.inputs)
        except (OSError, RuntimeError, ValueError, SystemExit) as e:   # report, go on with the next dataset
            print(f"FAILED {n}: {type(e).__name__}: {e}")
            failed.append(n)
            continue
        man = datasets.manifest(a.out / n)
        (a.out / n / "MANIFEST.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
        print(f"{n}: {len(man)} files, {sum(v['bytes'] for v in man.values()) / 1e9:.2f} GB, manifest written")
    if failed:
        raise SystemExit(f"datasets not fetched: {', '.join(failed)}")


if __name__ == "__main__":
    main()
