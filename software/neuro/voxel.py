"""Voxel grid of an event window, the E2VID / FireNet input (DESIGN.md §7.1, N3/N4/N8-R).

Golden reference: `events_to_voxel_grid(events, num_bins, width, height)` of E2VID (Rebecq et al.,
github.com/uzh-rpg/rpg_e2vid, utils/inference_utils.py). The rule, restated so it can be checked here:

- polarity 0 -> -1, 1 -> +1;
- t' = (B - 1) * (t - t_first) / (t_last - t_first), with the denominator replaced by 1 when it is 0;
- each event adds p * (1 - (t' - floor t')) to bin floor(t') and p * (t' - floor t') to bin floor(t') + 1,
  where the bin exists (bilinear in time, nearest in space);
- the result is float32 of shape (B, H, W).

The cross-check against the upstream code runs in N3 (Kaggle), not here; `tests/test_neuro_data.py` checks the
rule on hand-computed cases. Events with x >= W or y >= H are rejected (ValueError), not silently dropped.
"""
from __future__ import annotations

import numpy as np


def _columns(events):
    """(t, x, y, p) float64/int64 columns from a structured array (fields t,x,y,p) or an (N, 4) array t,x,y,p."""
    ev = np.asarray(events)
    if ev.dtype.names:
        return (ev["t"].astype(np.float64), ev["x"].astype(np.int64), ev["y"].astype(np.int64),
                ev["p"].astype(np.float64))
    if ev.size == 0:
        z = np.zeros(0)
        return z, z.astype(np.int64), z.astype(np.int64), z
    if ev.ndim != 2 or ev.shape[1] != 4:
        raise ValueError(f"events must be structured (t,x,y,p) or (N, 4) [t, x, y, p], got shape {ev.shape}")
    return (ev[:, 0].astype(np.float64), ev[:, 1].astype(np.int64), ev[:, 2].astype(np.int64),
            ev[:, 3].astype(np.float64))


def voxel_grid(events, B=5, *, H, W):
    """E2VID voxel grid (B, H, W) float32, bilinear in time, polarity +-1 (rule in the module docstring)."""
    if B < 1:
        raise ValueError("B must be >= 1")
    grid = np.zeros(B * H * W, dtype=np.float32)
    t, x, y, p = _columns(events)
    if t.size == 0:
        return grid.reshape(B, H, W)
    if x.min() < 0 or y.min() < 0 or x.max() >= W or y.max() >= H:
        raise ValueError(f"event outside the {W} x {H} sensor")
    pol = np.where(p > 0, 1.0, -1.0).astype(np.float32)
    delta = t[-1] - t[0]
    if delta == 0:
        delta = 1.0
    ts = (B - 1) * (t - t[0]) / delta
    tis = ts.astype(np.int64)
    dts = (ts - tis).astype(np.float32)
    left = pol * (1.0 - dts)
    right = pol * dts
    base = x + y * W
    ok = tis < B
    np.add.at(grid, base[ok] + tis[ok] * W * H, left[ok])
    ok = (tis + 1) < B
    np.add.at(grid, base[ok] + (tis[ok] + 1) * W * H, right[ok])
    return grid.reshape(B, H, W)
