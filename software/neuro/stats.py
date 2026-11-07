"""Shared statistics for the paper-2 experiments (DESIGN §8.3): one copy, used by every experiments/neuro_*.py.

    bootstrap_ci(values, n, seed)                  percentile bootstrap CI of the mean
    mean_ci(values)                                 Student-t CI of the mean (N6 seeds)
    cluster_bootstrap_ci(values, groups, n, seed)   resamples whole groups (recordings / subjects)
    paired_bootstrap_diff(a, b, groups, n, seed)    CI of mean(a - b) on identical windows, cluster resampling
    clopper_pearson(k, n, alpha)                    exact binomial interval (N7, N10 proportions)
    mi_plugin_mm(x, y)                              plug-in mutual information (bits) with Miller-Madow correction
    mi_perm_null(x, y, n, seed)                     permutation null of the MI: (mi, null mean, p-value)

All intervals are two-sided 95 % by default and return (estimate, lo, hi). The number of clusters goes next to
every cluster CI in the experiment tables (`n_clusters`).
"""
import math

import numpy as np
from scipy import stats as _st


def _arr(v):
    a = np.asarray(v, dtype=float)
    if a.ndim != 1 or len(a) == 0:
        raise ValueError("need a non-empty 1-D sample")
    return a


def bootstrap_ci(values, n=2000, seed=0, alpha=0.05):
    a = _arr(values)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), (n, len(a)))
    m = a[idx].mean(axis=1)
    return float(a.mean()), float(np.quantile(m, alpha / 2)), float(np.quantile(m, 1 - alpha / 2))


def mean_ci(values, alpha=0.05):
    a = _arr(values)
    m = float(a.mean())
    if len(a) < 2:
        return m, float("nan"), float("nan")
    h = float(_st.t.ppf(1 - alpha / 2, len(a) - 1) * a.std(ddof=1) / math.sqrt(len(a)))
    return m, m - h, m + h


def _groups(values, groups):
    a = _arr(values)
    g = np.asarray(groups)
    if len(g) != len(a):
        raise ValueError("values and groups differ in length")
    keys = np.unique(g)
    return a, [np.nonzero(g == k)[0] for k in keys]


def cluster_bootstrap_ci(values, groups, n=2000, seed=0, alpha=0.05):
    """Mean over all items; CI by resampling whole clusters with replacement."""
    a, members = _groups(values, groups)
    rng = np.random.default_rng(seed)
    sums = np.array([a[m].sum() for m in members])
    cnts = np.array([len(m) for m in members])
    pick = rng.integers(0, len(members), (n, len(members)))
    boot = sums[pick].sum(axis=1) / cnts[pick].sum(axis=1)
    return float(a.mean()), float(np.quantile(boot, alpha / 2)), float(np.quantile(boot, 1 - alpha / 2))


def n_clusters(groups):
    return int(len(np.unique(np.asarray(groups))))


def paired_bootstrap_diff(a, b, groups=None, n=2000, seed=0, alpha=0.05):
    """Mean of a - b over identical windows; cluster bootstrap if groups is given, else item bootstrap."""
    d = _arr(a) - _arr(b)
    if groups is None:
        return bootstrap_ci(d, n, seed, alpha)
    return cluster_bootstrap_ci(d, groups, n, seed, alpha)


def clopper_pearson(k, n, alpha=0.05):
    if n <= 0 or not 0 <= k <= n:
        raise ValueError(f"clopper_pearson: need 0 <= k <= n, n > 0 (k={k}, n={n})")
    lo = 0.0 if k == 0 else float(_st.beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(_st.beta.ppf(1 - alpha / 2, k + 1, n - k))
    return k / n, lo, hi


def _codes(v):
    _, inv = np.unique(np.asarray(v), return_inverse=True)
    return inv


def mi_plugin_mm(x, y):
    """Plug-in mutual information I(X; Y) in bits of two discrete samples, Miller-Madow bias-corrected.

    MM correction per entropy: H_MM = H_plugin + (m - 1) / (2 N ln 2), m = number of non-empty bins.
    I = H(X) + H(Y) - H(X, Y), each corrected; clipped at 0.
    """
    xc, yc = _codes(x), _codes(y)
    N = len(xc)
    if N != len(yc) or N == 0:
        raise ValueError("mi_plugin_mm: x and y must be non-empty and of equal length")

    def h(c):
        _, cnt = np.unique(c, return_counts=True)
        p = cnt / N
        return float(-(p * np.log2(p)).sum() + (len(cnt) - 1) / (2 * N * math.log(2)))

    joint = xc.astype(np.int64) * (int(yc.max()) + 1) + yc
    return max(0.0, h(xc) + h(yc) - h(joint))


def mi_perm_null(x, y, n=200, seed=0):
    """(MI, mean of the permutation null, p-value with the +1 correction)."""
    mi = mi_plugin_mm(x, y)
    rng = np.random.default_rng(seed)
    yv = np.asarray(y)
    null = np.array([mi_plugin_mm(x, rng.permutation(yv)) for _ in range(n)])
    p = (1 + int((null >= mi).sum())) / (n + 1)
    return mi, float(null.mean()), p


def quantize(v, bins=8):
    """Equal-frequency discretisation of a continuous feature for the MI estimate."""
    a = np.asarray(v, dtype=float)
    qs = np.quantile(a, np.linspace(0, 1, bins + 1)[1:-1])
    return np.searchsorted(qs, a, side="right")
