"""Metrics from section 8 of the project document."""
import numpy as np
from skimage.metrics import structural_similarity

PSNR_CAP = 100.0     # identical images are reported as 100 dB instead of infinity


def psnr(a, b):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    if mse == 0:
        return PSNR_CAP
    return float(10 * np.log10(255.0 ** 2 / mse))


def ssim(a, b):
    return float(structural_similarity(a, b, channel_axis=2, data_range=255))


def gray(img):
    if img.ndim == 2:
        return img.astype(np.float64)
    return img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114


def npcr_uaci(a, b):
    """Number of Pixels Change Rate and Unified Average Changing Intensity, in %."""
    a = a.astype(np.int32)
    b = b.astype(np.int32)
    npcr = float(np.mean(a != b) * 100)
    uaci = float(np.mean(np.abs(a - b)) / 255 * 100)
    return npcr, uaci


def adjacent_correlation(img, n=5000, seed=0):
    """Correlation of horizontally, vertically and diagonally adjacent pixels (grey)."""
    g = gray(img)
    h, w = g.shape
    rng = np.random.default_rng(seed)
    ys = rng.integers(0, h - 1, n)
    xs = rng.integers(0, w - 1, n)
    out = {}
    for name, (dy, dx) in (("h", (0, 1)), ("v", (1, 0)), ("d", (1, 1))):
        a, b = g[ys, xs], g[ys + dy, xs + dx]
        out[name] = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
    return out


def entropy(img):
    """Shannon entropy of the grey-level histogram, bits/pixel (max 8)."""
    g = np.clip(np.round(gray(img)), 0, 255).astype(np.uint8)
    hist = np.bincount(g.ravel(), minlength=256).astype(np.float64)
    p = hist[hist > 0] / hist.sum()
    return float(-(p * np.log2(p)).sum())
