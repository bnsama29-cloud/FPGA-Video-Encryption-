"""Download the paper-2 event datasets with a SHA-256 manifest (DESIGN §8.3). Run on Kaggle by kaggle_neuro.py.

    python software/scripts/get_events.py --out /kaggle/working/data nmnist dvsgesture eventreid
    python software/scripts/get_events.py --out data eventreid --list        (sizes only, no download)

  nmnist      N-MNIST through Tonic 1.7.0 (tonic.datasets.NMNIST, train + test), into <out>/nmnist
  dvsgesture  DVS Gesture (official train/test files, Tonic 1.7.0 layout), into <out>/dvsgesture. The two archives
              ibmGestureTrain.tar.gz / ibmGestureTest.tar.gz are taken, in this order, from an attached Kaggle
              dataset (any folder under --inputs, default /kaggle/input), from the zip at --zip-url (only those
              members are read, by HTTP range requests), else from figshare (files 38022171, 38020584); either way
              checked against Tonic's MD5 and placed where Tonic looks, so Tonic never downloads itself (its own
              download failed on Kaggle, 7 Nov 2026). If Kaggle unpacked an uploaded archive, the unpacked
              ibmGestureTrain/ / ibmGestureTest/ folder (with .npy files) is linked instead
  eventreid   Event-ReId from Zenodo record 8256439 (doi 10.5281/zenodo.8256439), every file of the record,
              into <out>/eventreid; zip/tar archives are extracted. --max-gb refuses a record larger than that.
Each dataset is fetched on its own: a failure is reported and the others still run (exit code 1 at the end).

    python software/scripts/get_events.py --zip-url <Drive link> --extract firenet_1000.pth.tar --extract-to DIR
extracts single members of the zip at --zip-url (a Google Drive share link or any URL that serves byte ranges)
without downloading the rest.
Writes <out>/<name>/MANIFEST.json (neuro.datasets.manifest: SHA-256 and size per file) and prints the totals.
"""
import argparse
import io
import os
import hashlib
import json
import re
import time
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


def drive_url(link):
    """Direct-download URL for a Google Drive share link or file id (any other URL is returned as it is)."""
    m = re.search(r"/file/d/([A-Za-z0-9_-]{10,})", link) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", link)
    if m is None and re.fullmatch(r"[A-Za-z0-9_-]{20,}", link):
        fid = link
    elif m is None:
        return link
    else:
        fid = m.group(1)
    return f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"


class RangeReader(io.RawIOBase):
    """A remote file read by HTTP range requests (Google Drive serves them), so zipfile can read the central
    directory and single members without downloading the whole archive. Every request is retried 4 times."""

    def __init__(self, url, tries=4):
        self.url, self.tries, self.pos = url, tries, 0
        r = self._get(0, 0)
        cr = r.headers.get("Content-Range", "")
        if r.status != 206 or "/" not in cr:
            raise OSError(f"{url}: no byte-range support (HTTP {r.status}); is the file shared with 'anyone with the "
                          f"link'?")
        self.size = int(cr.rsplit("/", 1)[1])

    def _get(self, a, b):
        err = None
        for k in range(self.tries):
            try:
                r = urllib.request.urlopen(urllib.request.Request(self.url, headers={**UA, "Range": f"bytes={a}-{b}"}),
                                           timeout=180)
                if r.headers.get_content_type() == "text/html":      # Drive's sign-in / quota page, not the file
                    raise OSError(f"{self.url}: got an HTML page instead of the file (not shared, or quota exceeded)")
                return r
            except OSError as e:
                err = e
                time.sleep(2 ** k)
        raise OSError(f"{self.url}: bytes {a}-{b}: {err}")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, buf):
        if self.pos >= self.size:
            return 0
        end = min(self.size, self.pos + len(buf)) - 1
        data = self._get(self.pos, end).read()
        buf[:len(data)] = data
        self.pos += len(data)
        return len(data)


def extract_from_zip(url, names, dest):
    """{name: path} for each member of the remote zip whose base name is in `names`, written to dest/<name> (skipped
    when a file of the same size is already there). zipfile checks each member's CRC-32 while reading it."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BufferedReader(RangeReader(drive_url(url)), 8 << 20)) as z:
        by_name = {Path(i.filename).name: i for i in z.infolist() if not i.is_dir()}
        got = {}
        for n in names:
            info = by_name.get(n)
            if info is None:
                continue
            p = dest / n
            if not (p.exists() and p.stat().st_size == info.file_size):
                print(f"{n}: extracting {info.file_size / 1e6:.1f} MB from {url}", flush=True)
                tmp = p.with_name(p.name + ".part")
                with z.open(info) as src, open(tmp, "wb") as f:
                    shutil.copyfileobj(src, f, 8 << 20)
                tmp.replace(p)
            got[n] = p
        return got


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
        done = d / p.stem / ".extracted"          # a re-run must not download and unpack the 0.67 GB again
        if done.exists() and done.read_text().strip() == str(f.get("checksum")):
            continue
        if not p.exists():
            download(f["url"], p)
        if p.suffix.lower() in (".zip", ".tar", ".gz", ".tgz") and safe_extract(p, d / p.stem):
            done.write_text(str(f.get("checksum")))
            p.unlink()
    return {"files": files, "total_bytes": total}


GESTURE_UNPACKED_GB = 16.1   # the two archives unpack to 16.1 GB (Tonic 1.7.0, measured 15 Nov 2026; archives 3.1 GB)


def _need_disk(path, gb, what):
    free = shutil.disk_usage(path).free / 1e9
    if free < gb:
        raise RuntimeError(f"{what} needs {gb:.1f} GB free at {path}, only {free:.1f} GB: attach DVS Gesture as a Kaggle "
                           f"dataset (Kaggle unpacks it outside the working disk), or free space")


def _verified(dst, want):
    """The archive was MD5-checked and unpacked by an earlier run, then emptied (see shrink_gesture)."""
    mark = dst.with_name(dst.name + ".md5ok")
    folder = dst.with_name(dst.name.replace(".tar.gz", ""))
    return mark.exists() and mark.read_text().strip() == want and folder.is_dir() and _has_npy(folder)


def shrink_gesture(out):
    """After Tonic unpacked DVS Gesture: replace each archive by an empty file (Tonic only checks that it exists)
    and a <archive>.md5ok marker, which frees 3.1 GB on Kaggle's working disk."""
    d = out / "dvsgesture" / "DVSGesture"
    for fname, _, want in GESTURE.values():
        dst, folder = d / fname, d / fname.replace(".tar.gz", "")
        if dst.exists() and dst.stat().st_size and folder.is_dir() and _has_npy(folder) and not folder.is_symlink():
            dst.with_name(fname + ".md5ok").write_text(want)
            dst.write_bytes(b"")


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


def _walk(root):
    """(dirpath, dirnames, filenames) under root, following symbolic links: Kaggle mounts attached datasets under
    /kaggle/input through links, which Path.rglob does not enter (first Kaggle run with the dataset, 7 Nov 2026)."""
    if not Path(root).exists():
        return []
    return list(os.walk(root, followlinks=True))


def _has_npy(d):
    return any(f.endswith(".npy") for _, _, fs in os.walk(d, followlinks=True) for f in fs)


def describe_inputs(root, depth=4, limit=60):
    """Short listing of what is attached under root (printed when DVS Gesture is not found)."""
    lines = []
    for dp, dn, fn in _walk(root):
        rel = Path(dp).relative_to(root)
        if len(rel.parts) > depth:
            continue
        lines.append(f"  {rel.as_posix() or '.'}/  ({len(dn)} dirs, {len(fn)} files: {', '.join(sorted(fn)[:4])})")
        if len(lines) >= limit:
            break
    return "\n".join(lines) or f"  (nothing under {root})"


def stage_gesture(out, inputs, zip_url=None):
    """Put both DVS Gesture archives, MD5-checked, into <out>/dvsgesture/DVSGesture/ (Tonic's location). `inputs` is
    a list of folders searched for the archives or for folders Kaggle unpacked from them."""
    if isinstance(inputs, (str, os.PathLike)):
        inputs = [inputs]
    dst_dir = out / "dvsgesture" / "DVSGesture"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for train, (fname, url, want) in GESTURE.items():
        dst = dst_dir / fname
        if dst.exists() and (_verified(dst, want) or md5(dst) == want):
            continue
        walk = [w for root in inputs for w in _walk(root)]
        found = sorted(Path(dp) / fname for dp, _, fn in walk if fname in fn)
        folder = fname.replace(".tar.gz", "")
        # Kaggle unpacks an uploaded .tar.gz, often as <archive name>/<folder>/user../*.npy: take the deepest folder
        # of that name that holds .npy files (its children are the userNN_<lighting> folders Tonic walks)
        unpacked = sorted((Path(dp) / d for dp, dn, _ in walk for d in dn if d == folder and _has_npy(Path(dp) / d)),
                          key=lambda p: len(p.parts), reverse=True)
        if not found and unpacked:
            # Kaggle can unpack an uploaded .tar.gz: link the unpacked folder where Tonic looks and leave an empty
            # file under the archive's name (Tonic only checks that the archive file exists, then uses the folder)
            print(f"DVS Gesture: using the unpacked folder {unpacked[0]} (no MD5 check possible on a folder)")
            link = dst_dir / folder
            if not link.exists():
                try:
                    link.symlink_to(unpacked[0].resolve(), target_is_directory=True)
                except OSError:          # Windows without the symlink privilege (WinError 1314): copy instead
                    shutil.copytree(unpacked[0], link)
            dst.touch()
            continue
        if found:
            print(f"DVS Gesture: using {found[0]}")
            shutil.copy(found[0], dst)
        elif zip_url and not _need_disk(dst_dir, GESTURE_UNPACKED_GB * (1 if train else 0.23) + 3.5,
                                        f"DVS Gesture ({fname} + unpacked)") \
                and fname in _zip_or_none(zip_url, [fname], dst_dir):
            print(f"DVS Gesture: {fname} taken from {zip_url}")
        else:
            print(f"DVS Gesture: neither {fname} nor an unpacked {folder}/ with .npy files under {inputs}"
                  f"{' nor in the zip' if zip_url else ''}. Attached inputs:\n"
                  f"{chr(10).join(describe_inputs(r) for r in inputs)}\nTrying the download {url}")
            try:
                download(url, dst)
            except OSError as e:
                raise RuntimeError(f"{fname}: not attached and the download failed ({e})") from e
        got = md5(dst)
        if got != want:
            dst.unlink()
            raise RuntimeError(f"{fname}: MD5 {got} != {want}. Download both archives in a browser from figshare "
                               f"(DVS Gesture, files 38022171 and 38020584) and attach them as a Kaggle dataset")


def _zip_or_none(zip_url, names, dest):
    """extract_from_zip, reporting (not raising) a failure, so the next source is tried."""
    try:
        return extract_from_zip(zip_url, names, dest)
    except (OSError, zipfile.BadZipFile, ValueError) as e:
        print(f"zip {zip_url}: {type(e).__name__}: {e}")
        return {}


def get_tonic(name, out, inputs=("/kaggle/input",), zip_url=None):
    if name == "dvsgesture":
        stage_gesture(out, list(inputs), zip_url)
    import tonic
    cls = {"nmnist": tonic.datasets.NMNIST, "dvsgesture": tonic.datasets.DVSGesture}[name]
    for train in (True, False):
        ds = cls(save_to=str(out / name), train=train)
        print(f"{name} {'train' if train else 'test'}: {len(ds)} samples")
    if name == "dvsgesture":
        shrink_gesture(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", choices=["nmnist", "dvsgesture", "eventreid"])
    ap.add_argument("--out", type=Path, default=ROOT / "data")
    ap.add_argument("--max-gb", type=float, default=40.0)
    ap.add_argument("--list", action="store_true", help="Event-ReId: print the record's files only")
    ap.add_argument("--inputs", action="append", help="where attached archives are looked for (repeatable; "
                    "default /kaggle/input)")
    ap.add_argument("--zip-url", help="a zip (Google Drive share link or byte-range URL) holding archives / checkpoints")
    ap.add_argument("--extract", nargs="+", metavar="NAME", help="only extract these members of --zip-url")
    ap.add_argument("--extract-to", type=Path, help="folder for --extract")
    a = ap.parse_args()
    a.inputs = a.inputs or ["/kaggle/input"]
    if a.extract:
        if not (a.zip_url and a.extract_to):
            ap.error("--extract needs --zip-url and --extract-to")
        got = extract_from_zip(a.zip_url, a.extract, a.extract_to)
        missing = [n for n in a.extract if n not in got]
        for n, p in got.items():
            print(f"{n}: {p} ({p.stat().st_size / 1e6:.1f} MB)")
        if missing:
            raise SystemExit(f"not in {a.zip_url}: {missing}")
        return
    if not a.names:
        ap.error("name at least one dataset (or use --extract)")
    a.out.mkdir(parents=True, exist_ok=True)
    failed = []
    for n in a.names:
        try:
            if n == "eventreid":
                get_eventreid(a.out, a.max_gb, a.list)
                if a.list:
                    continue
            else:
                get_tonic(n, a.out, a.inputs, a.zip_url)
        except (OSError, RuntimeError, ValueError, SystemExit) as e:   # report, go on with the next dataset
            print(f"FAILED {n}: {type(e).__name__}: {e}")
            failed.append(f"{n} ({type(e).__name__}: {e})")
            continue
        man = datasets.manifest(a.out / n)
        (a.out / n / "MANIFEST.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
        print(f"{n}: {len(man)} files, {sum(v['bytes'] for v in man.values()) / 1e9:.2f} GB, manifest written")
    if failed:
        raise SystemExit(f"datasets not fetched: {', '.join(failed)}")


if __name__ == "__main__":
    main()
