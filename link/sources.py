"""Video sources for the simulated camera: synthetic scene, video file, webcam or a folder of images."""
import time

import numpy as np


class Synthetic:
    """CCTV-like test scene (no files needed): a corridor, a person walking across,
    a door, a notice board and the usual timestamp overlay. Muted colours with real
    edges and texture, so the visual-security effect of each mode is easy to judge."""

    def __init__(self, width, height):
        import cv2
        self.cv2, self.w, self.h, self.n = cv2, width, height, 0
        w, h = width, height
        y, x = np.mgrid[0:h, 0:w]
        bg = np.zeros((h, w, 3), np.float32)
        bg[:] = (178, 182, 176)                                        # wall
        floor = y > h * 0.62
        bg[floor] = (112, 104, 96)
        bg[floor] += ((((x[floor] // max(4, w // 16)) + (y[floor] // max(3, h // 24))) % 2) * 14)[:, None]
        bg *= (0.75 + 0.25 * (1 - np.abs(x - w / 2) / (w / 2)))[..., None]   # vignetting
        bg = np.clip(bg + np.random.default_rng(3).normal(0, 3, bg.shape), 0, 255).astype(np.uint8)
        cv2.rectangle(bg, (int(w * .70), int(h * .22)), (int(w * .84), int(h * .62)), (92, 64, 44), -1)   # door
        cv2.circle(bg, (int(w * .815), int(h * .44)), max(1, w // 160), (210, 190, 90), -1)
        cv2.rectangle(bg, (int(w * .12), int(h * .18)), (int(w * .40), int(h * .40)), (60, 70, 86), -1)   # notice board
        for k in range(4):
            yy = int(h * (.22 + .045 * k))
            cv2.line(bg, (int(w * .14), yy), (int(w * (.30 + .02 * (k % 2))), yy), (230, 230, 225), 1)
        cv2.line(bg, (0, int(h * .62)), (w, int(h * .62)), (70, 66, 60), 2)
        self.bg = bg

    def read(self):
        cv2, w, h, n = self.cv2, self.w, self.h, self.n
        self.n += 1
        img = self.bg.copy()
        px = int((n * w / 120) % (w + w // 5)) - w // 10              # person walks left to right
        top, s = int(h * .30), max(4, h // 12)
        cv2.ellipse(img, (px, int(h * .86)), (s, s // 3), 0, 0, 360, (80, 74, 68), -1)        # shadow
        cv2.rectangle(img, (px - s // 2, top + s), (px + s // 2, int(h * .62) + s // 2), (40, 70, 120), -1)
        step = int(s * .45 * np.sin(n / 3.0))
        cv2.line(img, (px - s // 4, int(h * .62) + s // 2), (px - s // 4 + step, int(h * .85)), (35, 35, 40), max(2, s // 4))
        cv2.line(img, (px + s // 4, int(h * .62) + s // 2), (px + s // 4 - step, int(h * .85)), (35, 35, 40), max(2, s // 4))
        cv2.circle(img, (px, top + s // 2), int(s * .55), (196, 150, 120), -1)
        cv2.rectangle(img, (0, 0), (w, max(14, h // 14)), (20, 20, 20), -1)
        cv2.putText(img, f"CAM-01  CORRIDOR B  {time.strftime('%d-%m-%Y %H:%M:%S')}  #{n:05d}",
                    (4, max(10, h // 14) - 4), cv2.FONT_HERSHEY_SIMPLEX, max(0.28, w / 1100), (235, 235, 235), 1,
                    cv2.LINE_AA)
        return img


class VideoFile:
    def __init__(self, path, width, height, loop=True):
        import cv2
        self.cv2, self.path, self.size, self.loop = cv2, path, (width, height), loop
        self.cap = self._open()

    def _open(self):
        src = self.path
        if isinstance(src, str) and src.startswith("webcam:"):
            src = int(src.split(":", 1)[1])
        cap = self.cv2.VideoCapture(src)
        if not cap.isOpened():
            raise RuntimeError(f"cannot open video source {self.path!r}")
        return cap

    def read(self):
        ok, f = self.cap.read()
        if not ok and self.loop and not str(self.path).startswith("webcam:"):
            self.cap.release()
            self.cap = self._open()
            ok, f = self.cap.read()
        if not ok:
            return None
        f = self.cv2.resize(f, self.size, interpolation=self.cv2.INTER_AREA)
        return self.cv2.cvtColor(f, self.cv2.COLOR_BGR2RGB)


class ImageFolder:
    """Still images of a folder (e.g. the Kodak set) as frames, sorted by name. Each image is
    centre-cropped to the target aspect ratio, then resized, so nothing is stretched."""
    EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".ppm")

    def __init__(self, path, width, height, loop=True):
        import cv2
        from pathlib import Path
        self.cv2, self.size, self.loop = cv2, (width, height), loop
        self.files = sorted(p for p in Path(path).iterdir() if p.suffix.lower() in self.EXT)
        if not self.files:
            raise RuntimeError(f"no images in {path!r}")
        self.i = 0

    def read(self):
        if self.i >= len(self.files):
            if not self.loop:
                return None
            self.i = 0
        img = self.cv2.imread(str(self.files[self.i]))
        self.i += 1
        w, h = self.size
        H, W = img.shape[:2]
        if W * h > H * w:                       # too wide: crop the sides
            nw = H * w // h
            img = img[:, (W - nw) // 2:(W - nw) // 2 + nw]
        else:                                   # too tall: crop top and bottom
            nh = W * h // w
            img = img[(H - nh) // 2:(H - nh) // 2 + nh]
        img = self.cv2.resize(img, self.size, interpolation=self.cv2.INTER_AREA)
        return self.cv2.cvtColor(img, self.cv2.COLOR_BGR2RGB)


def open_source(spec, width, height, loop=True):
    """'synthetic' | a video file | 'webcam:N' | a folder of images."""
    from pathlib import Path
    if spec in ("synthetic", "", None):
        return Synthetic(width, height)
    if Path(str(spec)).is_dir():
        return ImageFolder(spec, width, height, loop)
    return VideoFile(spec, width, height, loop)
