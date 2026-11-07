"""v2e-lite: a small, deterministic frame-to-event converter (DESIGN.md §7.1, §2.3 geometry `cif`).

It follows the core idea of v2e [hu2021v2e] (log intensity, a per-pixel memorised level, an event each time
the log intensity moves one contrast threshold C away from that level, refractory period), with v2e's noise,
threshold-mismatch, leak and finite-bandwidth models switched OFF (`docs/neuro/notes/lit_formats_data.md` §7).
Output is labelled "simulated, no noise model" wherever it is used. It is run only at the clip's native size.

Exact rule implemented here (this module is its own specification, the referee for any later cross-check):

1. L_k = log(Y_k + eps) per pixel, Y_k the luma of frame k (float64), eps = 1.0 by default (luma 0 is valid).
2. The memory M starts at L_0. Frame k (k >= 1) covers the interval [t_{k-1}, t_k] with
   t_k = round(k * 1e6 / fps) µs. Inside it the log intensity is taken as linear from L_{k-1} to L_k.
3. n = floor(|L_k - M| / C) events of sign s = sign(L_k - M) are produced. Event i (1..n) is placed where the
   linear ramp crosses M + s*i*C, i.e. at fraction f_i = (M + s*i*C - L_{k-1}) / (L_k - L_{k-1}) of the
   interval, clipped to [0, 1], at t = t_{k-1} + round(f_i * (t_k - t_{k-1})) µs.
4. M <- M + s*n*C (the remainder is not added, as in v2e).
5. Refractory filter: an event of a pixel closer than `refractory_us` to the last *emitted* event of the same
   pixel is dropped from the output. The memory update of step 4 is not undone (the filter acts on the output
   only).
6. p = 1 for ON (s = +1), p = 0 for OFF. Events are sorted by (t, y, x, p) so the output is unique.

`seed` is accepted for API stability (DESIGN.md §7.1) and recorded by callers; with every noise source off the
output does not depend on it.
"""
from __future__ import annotations

import numpy as np

# Same literal as neuro.evt2.EVENT_DTYPE (DESIGN.md §7.1); tests/test_neuro_data.py checks they agree.
_EVENT_DTYPE_SPEC = [("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "u1")]


def event_dtype() -> np.dtype:
    """EVENT_DTYPE of neuro.evt2 when that module exists, else the identical §7.1 literal."""
    try:
        from neuro.evt2 import EVENT_DTYPE  # noqa: PLC0415 (optional sibling module)
        return np.dtype(EVENT_DTYPE)
    except ImportError:
        return np.dtype(_EVENT_DTYPE_SPEC)


def frames_to_events(y_frames, fps, C=0.2, refractory_us=500, seed=0, eps=1.0):
    """Convert luma frames (N, H, W) to events (structured array, EVENT_DTYPE), following the module rule."""
    del seed  # deterministic: no noise model (see module docstring)
    frames = np.asarray(y_frames, dtype=np.float64)
    if frames.ndim != 3:
        raise ValueError(f"y_frames must be (N, H, W), got shape {frames.shape}")
    if fps <= 0 or C <= 0 or refractory_us < 0:
        raise ValueError("fps and C must be > 0 and refractory_us >= 0")
    n_frames, H, W = frames.shape
    dt = np.dtype(event_dtype())
    if n_frames < 2:
        return np.zeros(0, dtype=dt)
    logf = np.log(frames.reshape(n_frames, -1) + eps)
    mem = logf[0].copy()
    last = np.full(H * W, -(1 << 62), dtype=np.int64)  # last emitted event time per pixel
    out_t, out_i, out_p = [], [], []
    for k in range(1, n_frames):
        t0 = int(round((k - 1) * 1e6 / fps))
        t1 = int(round(k * 1e6 / fps))
        lp, lc = logf[k - 1], logf[k]
        diff = lc - mem
        n = np.floor(np.abs(diff) / C).astype(np.int64)
        idx = np.nonzero(n)[0]
        if idx.size == 0:
            continue
        s = np.sign(diff[idx])
        span = lc[idx] - lp[idx]
        safe = np.where(span == 0, 1.0, span)
        for i in range(1, int(n[idx].max()) + 1):
            sel = n[idx] >= i
            pix = idx[sel]
            level = mem[pix] + s[sel] * i * C
            f = np.where(span[sel] == 0, 1.0, (level - lp[pix]) / safe[sel])
            t = t0 + np.rint(np.clip(f, 0.0, 1.0) * (t1 - t0)).astype(np.int64)
            ok = t - last[pix] >= refractory_us
            pix, t = pix[ok], t[ok]
            last[pix] = t
            out_t.append(t)
            out_i.append(pix)
            out_p.append((s[sel][ok] > 0).astype(np.uint8))
        mem[idx] += s * n[idx] * C
    if not out_t:
        return np.zeros(0, dtype=dt)
    t = np.concatenate(out_t)
    pix = np.concatenate(out_i)
    p = np.concatenate(out_p)
    ev = np.zeros(t.size, dtype=dt)
    ev["t"], ev["x"], ev["y"], ev["p"] = t, pix % W, pix // W, p
    order = np.lexsort((ev["p"], ev["x"], ev["y"], ev["t"]))
    return ev[order]
