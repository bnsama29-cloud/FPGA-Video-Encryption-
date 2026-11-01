"""Deterministic synthetic test images (no downloads needed)."""
import numpy as np


def make_image(width=64, height=64, kind="scene", seed=1):
    """Returns an H x W x 3 uint8 numpy array.

    kind: 'scene' (gradients + shapes + text-like edges), 'noise', 'flat',
          'checker', 'bars' (pure R/G/B/black/white colour bars)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:height, 0:width]
    if kind == "noise":
        return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    if kind == "flat":
        return np.full((height, width, 3), 128, dtype=np.uint8)
    if kind == "checker":
        v = (((x // 4) + (y // 4)) % 2) * 255
        return np.stack([v, v, v], -1).astype(np.uint8)
    if kind == "bars":
        cols = np.array([[255, 255, 255], [255, 0, 0], [0, 255, 0], [0, 0, 255],
                         [0, 0, 0], [255, 255, 0], [0, 255, 255], [255, 0, 255]])
        return cols[(x * 8 // width) % 8].astype(np.uint8)
    img = np.zeros((height, width, 3), dtype=np.float64)
    img[..., 0] = 255 * x / max(width - 1, 1)
    img[..., 1] = 255 * y / max(height - 1, 1)
    img[..., 2] = 128 + 100 * np.sin(x / 5.0) * np.cos(y / 7.0)
    cy, cx, r = height * 0.5, width * 0.4, min(width, height) * 0.25
    disk = (y - cy) ** 2 + (x - cx) ** 2 < r * r
    img[disk] = [250, 220, 40]
    img[(y > height * 0.7) & (y < height * 0.8) & (x % 6 < 3)] = [20, 20, 20]
    img += rng.normal(0, 6, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def psnr(a, b):
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    mse = np.mean((a - b) ** 2)
    return float("inf") if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)
