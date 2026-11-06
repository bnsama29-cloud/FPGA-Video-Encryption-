"""Download the standard Xiph test sequences (journal experiment X6) and convert them for the experiments.

    python software/scripts/get_xiph.py                   # the default set into clips/xiph/
    python software/scripts/get_xiph.py --list            # what is available here, with sizes
    python software/scripts/get_xiph.py foreman_cif akiyo_cif --frames 300

Reviewers know these sequences (Foreman, Akiyo, News, Mobile, Crowd Run ...) from 25 years of video coding
papers; results on them can be compared with other work, unlike results on private clips. They come from
the Xiph.org Video Test Media collection ("derf's collection", https://media.xiph.org/video/derf/) as raw
YUV 4:2:0 in .y4m files. Each file is converted with ffmpeg into a lossless-enough MP4 (crf 0, so the
experiments see the original pixels) and a SHA-256 manifest of the downloaded .y4m files is written to
clips/xiph/manifest.md, so the results can name exactly which input they used.

Every experiment takes the MP4 (or the .y4m directly, if your OpenCV reads it) through --video / --source,
e.g.  python experiments/standard_metrics.py --video clips/xiph/foreman_cif.mp4 --size 352x288 --name foreman
The CIF sequences (352x288) are whole 16x16 MCUs; give the 1080p ones --size 1920x1072 or 1280x720.
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://media.xiph.org/video/derf/y4m/"
# name -> (resolution, what it shows); the CIF and 4:2:0 1080p classics most papers use
SEQUENCES = {
    "akiyo_cif": ("352x288", "news reader, static background (low motion)"),
    "foreman_cif": ("352x288", "face, hand-held camera, pan to a building site"),
    "news_cif": ("352x288", "two news readers, dancers in the background"),
    "hall_monitor_cif": ("352x288", "surveillance camera in a corridor (the CCTV case)"),
    "mobile_cif": ("352x288", "toy train, calendar: high detail and text"),
    "mother_daughter_cif": ("352x288", "two faces, low motion"),
    "crowd_run_1080p50": ("1920x1080", "crowd of runners (many people, high motion)"),
    "park_joy_1080p50": ("1920x1080", "people running past trees (high detail)"),
}
DEFAULT = ["akiyo_cif", "foreman_cif", "news_cif", "hall_monitor_cif", "mobile_cif", "mother_daughter_cif"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(name, out):
    y4m = out / f"{name}.y4m"
    if y4m.exists() and y4m.stat().st_size > 0:
        print(f"{name}: already downloaded")
        return y4m
    url = BASE + f"{name}.y4m"
    print(f"{name}: downloading {url}", flush=True)
    tmp = y4m.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.rename(y4m)
    return y4m


def to_mp4(y4m, frames=None):
    mp4 = y4m.with_suffix(".mp4")
    if mp4.exists():
        return mp4
    if shutil.which("ffmpeg") is None:
        print("  ffmpeg not on PATH: keeping the .y4m only")
        return None
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(y4m)]
    if frames:
        cmd += ["-frames:v", str(frames)]
    cmd += ["-c:v", "libx264", "-crf", "0", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(mp4)]
    subprocess.run(cmd, check=True)
    return mp4


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", default=DEFAULT, help=f"sequences (default: {' '.join(DEFAULT)})")
    ap.add_argument("--out", default=str(ROOT / "clips" / "xiph"))
    ap.add_argument("--frames", type=int, help="keep only the first N frames in the MP4")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for n, (res, what) in SEQUENCES.items():
            print(f"{n:<22}{res:<11}{what}")
        return
    unknown = [n for n in a.names if n not in SEQUENCES]
    if unknown:
        sys.exit(f"unknown sequence(s) {unknown}; --list shows the known ones")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in a.names:
        y4m = download(n, out)
        to_mp4(y4m, a.frames)
        rows.append(f"| {n} | {SEQUENCES[n][0]} | {SEQUENCES[n][1]} | {sha256(y4m)[:16]} |")
    md = ["# Xiph test sequences", "", f"From {BASE} (Xiph.org Video Test Media). Converted with "
          "software/scripts/get_xiph.py.", "", "| Sequence | Size | Content | sha256 of .y4m (first 16) |",
          "|---|---|---|---|"] + rows
    (out / "manifest.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
