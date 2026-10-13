"""Format compliance: do standard decoders open our protected frames? (paper table)

    python -m future_work.figures.format_compliance

For every mode E0..E5 it builds a frame and an MJPEG clip and tries each decoder
that is available on this machine:
  Pillow (libjpeg)          strict load of the JPEG
  OpenCV (libjpeg-turbo)    cv2.imdecode
  scikit-image / imageio    if installed
  ffmpeg / ffprobe          decode the MJPEG clip (what VLC uses underneath), if on PATH
  Chromium                  loads the JPEG in a real browser via Playwright, if installed
"yes" = decoded to the right size without error. Writes future_work/results/format_compliance.md.
"""
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from link.sources import open_source
from model.jpeg import analyse_frame, package_frame
from model.selective import MODES

OUT = Path(__file__).resolve().parents[1] / "results"
KEY = bytes(range(16))


def pillow(jpg, w, h):
    im = Image.open(io.BytesIO(jpg))
    im.load()
    return im.size == (w, h)


def opencv(jpg, w, h):
    import cv2
    a = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    return a is not None and a.shape[:2] == (h, w)


def skimage_io(jpg, w, h):
    from skimage import io as skio
    with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
        f.write(jpg)
        f.flush()
        return skio.imread(f.name).shape[:2] == (h, w)


def ffmpeg_mjpeg(clip, w, h):
    with tempfile.NamedTemporaryFile(suffix=".mjpeg") as f:
        f.write(clip)
        f.flush()
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "mjpeg", "-i", f.name, "-f", "null", "-"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and not r.stderr.strip()


def chromium(jpgs):
    """One browser session for all modes; returns {mode: ok}."""
    import base64
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        for m, (jpg, w, h) in jpgs.items():
            uri = "data:image/jpeg;base64," + base64.b64encode(jpg).decode()
            pg.set_content(f'<img id="i" src="{uri}">')
            pg.wait_for_function("document.getElementById('i').complete")
            nw = pg.evaluate("document.getElementById('i').naturalWidth")
            nh = pg.evaluate("document.getElementById('i').naturalHeight")
            res[m] = (nw, nh) == (w, h)
        b.close()
    return res


def available():
    dec = {"Pillow": pillow, "OpenCV": opencv}
    try:
        import skimage.io  # noqa: F401
        dec["scikit-image"] = skimage_io
    except ImportError:
        pass
    return dec


def main():
    w, h = 320, 240
    src = open_source("synthetic", w, h)
    frames = [src.read() for _ in range(5)]
    an = [analyse_frame(f) for f in frames]
    jpgs, clips = {}, {}
    for m in MODES:
        enc = [package_frame(a, KEY, 9, i + 1, m).jpeg for i, a in enumerate(an)]
        jpgs[m], clips[m] = enc[0], b"".join(enc)
    table = {m: {} for m in MODES}
    for name, fn in available().items():
        for m in MODES:
            try:
                table[m][name] = bool(fn(jpgs[m], w, h))
            except Exception as e:                               # report, never hide
                table[m][name] = f"error: {type(e).__name__}"
    if shutil.which("ffmpeg"):
        for m in MODES:
            table[m]["ffmpeg (MJPEG clip)"] = ffmpeg_mjpeg(clips[m], w, h)
    try:
        for m, ok in chromium({m: (jpgs[m], w, h) for m in MODES}).items():
            table[m]["Chromium"] = ok
    except Exception as e:
        print(f"Chromium check skipped: {type(e).__name__}: {e}")
    cols = list(next(iter(table.values())))
    fmt = lambda v: "yes" if v is True else ("NO" if v is False else str(v))
    lines = ["| Mode | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    lines += [f"| {m} | " + " | ".join(fmt(table[m].get(c)) for c in cols) + " |" for m in MODES]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "format_compliance.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines) + f"\n\nwritten {OUT}/format_compliance.md")
    return table


if __name__ == "__main__":
    main()
