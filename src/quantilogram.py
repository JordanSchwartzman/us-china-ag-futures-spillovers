"""Cross-quantilogram (Han, Linton, Oka & Whang 2016) as used in Jiang et al. (2016).

Conventions
-----------
cross_quantilogram(x1, x2, a1, a2, k) measures whether x2 at time t-k being below its
a2-quantile predicts x1 at time t being below its a1-quantile (Eq. 2).
x1, x2 must already be aligned on a common index (same length, same dates).

Inference: stationary bootstrap (Politis & Romano 1994) of the lag-k pairs
(x1_t, x2_{t-k}) with circular wrap; quantiles re-estimated in every resample;
the 95% band "for no predictability" is the [2.5%, 97.5%] quantile of (rho* - rho_hat).
"""
from __future__ import annotations

import numpy as np
from numba import njit

# ----------------------------------------------------------------------------- core


@njit(cache=True)
def _q_type1(sorted_x, alpha):
    """inf{v : F_n(v) >= alpha} -- the paper's quantile definition."""
    n = sorted_x.shape[0]
    k = int(np.ceil(alpha * n)) - 1
    if k < 0:
        k = 0
    return sorted_x[k]


@njit(cache=True)
def _rho_pairs(y1, y2, a1, a2):
    """Eq. 2 on already-lagged pairs (y1_t = x1_t, y2_t = x2_{t-k})."""
    q1 = _q_type1(np.sort(y1), a1)
    q2 = _q_type1(np.sort(y2), a2)
    num = 0.0
    s1 = 0.0
    s2 = 0.0
    for t in range(y1.shape[0]):
        p1 = (1.0 if y1[t] < q1 else 0.0) - a1
        p2 = (1.0 if y2[t] < q2 else 0.0) - a2
        num += p1 * p2
        s1 += p1 * p1
        s2 += p2 * p2
    if s1 == 0.0 or s2 == 0.0:
        return np.nan
    return num / np.sqrt(s1 * s2)


@njit(cache=True)
def _rho_fixed_q(y1, y2, q1, q2, a1, a2):
    num = 0.0
    s1 = 0.0
    s2 = 0.0
    for t in range(y1.shape[0]):
        p1 = (1.0 if y1[t] < q1 else 0.0) - a1
        p2 = (1.0 if y2[t] < q2 else 0.0) - a2
        num += p1 * p2
        s1 += p1 * p1
        s2 += p2 * p2
    if s1 == 0.0 or s2 == 0.0:
        return np.nan
    return num / np.sqrt(s1 * s2)


@njit(cache=True)
def _sb_index(n, p, out):
    """Stationary bootstrap index: geometric blocks with mean 1/p, circular wrap."""
    i = np.random.randint(n)
    out[0] = i
    for t in range(1, n):
        if np.random.random() < p:
            i = np.random.randint(n)
        else:
            i = i + 1
            if i >= n:
                i = 0
        out[t] = i


@njit(cache=True)
def _boot_rho(y1, y2, a1, a2, p, B, seed):
    np.random.seed(seed)
    n = y1.shape[0]
    idx = np.empty(n, dtype=np.int64)
    z1 = np.empty(n)
    z2 = np.empty(n)
    out = np.empty(B)
    for b in range(B):
        _sb_index(n, p, idx)
        for t in range(n):
            z1[t] = y1[idx[t]]
            z2[t] = y2[idx[t]]
        out[b] = _rho_pairs(z1, z2, a1, a2)
    return out


# ----------------------------------------------------------------------------- API


def _lag_pairs(x1, x2, k):
    """Pairs (x1_t, x2_{t-k}) for k >= 0, (x1_t, x2_{t+|k|}) for k < 0."""
    x1 = np.asarray(x1, dtype=np.float64)
    x2 = np.asarray(x2, dtype=np.float64)
    if k > 0:
        y1, y2 = x1[k:], x2[:-k]
    elif k < 0:
        y1, y2 = x1[:k], x2[-k:]
    else:
        y1, y2 = x1, x2
    m = np.isfinite(y1) & np.isfinite(y2)
    return np.ascontiguousarray(y1[m]), np.ascontiguousarray(y2[m])


def cross_quantilogram(x1, x2, a1, a2, k=1, full_sample_quantiles=True):
    """Sample cross-quantilogram, Eq. 2.

    full_sample_quantiles=True uses the unconditional quantile of each full series (the
    paper's q_hat_i); False re-estimates on the lagged pair sample (what the bootstrap does).
    """
    y1, y2 = _lag_pairs(x1, x2, k)
    if full_sample_quantiles:
        f1 = np.asarray(x1, float)
        f2 = np.asarray(x2, float)
        q1 = _q_type1(np.sort(f1[np.isfinite(f1)]), a1)
        q2 = _q_type1(np.sort(f2[np.isfinite(f2)]), a2)
        return float(_rho_fixed_q(y1, y2, q1, q2, a1, a2))
    return float(_rho_pairs(y1, y2, a1, a2))


def block_prob(x1, x2):
    """gamma = 1 / mean block length from Patton-Politis-White (arch), on returns."""
    from arch.bootstrap import optimal_block_length

    m = np.isfinite(x1) & np.isfinite(x2)
    obl = optimal_block_length(np.column_stack([np.asarray(x1)[m], np.asarray(x2)[m]]))
    L = float(np.nanmax(obl["stationary"].values))
    L = max(L, 1.0)
    return 1.0 / L, L


def quantilogram_test(x1, x2, a1, a2, lags=range(1, 21), B=1000, seed=0, level=0.95, gamma=None):
    """rho_hat, null CI, and portmanteau Q (+ bootstrap p-value) for a set of lags.

    Returns a dict of numpy arrays indexed like `lags`.
    """
    lags = list(lags)
    x1 = np.asarray(x1, float)
    x2 = np.asarray(x2, float)
    if gamma is None:
        gamma, _ = block_prob(x1, x2)
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    rho = np.empty(len(lags))
    lo = np.empty(len(lags))
    hi = np.empty(len(lags))
    nobs = np.empty(len(lags), dtype=int)
    centered = np.empty((B, len(lags)))
    for j, k in enumerate(lags):
        y1, y2 = _lag_pairs(x1, x2, k)
        r = cross_quantilogram(x1, x2, a1, a2, k)
        bs = _boot_rho(y1, y2, a1, a2, gamma, B, seed + 7919 * j)
        d = bs - _rho_pairs(y1, y2, a1, a2)  # center on the statistic the bootstrap mimics
        rho[j] = r
        lo[j], hi[j] = np.nanquantile(d, [lo_q, hi_q])
        centered[:, j] = d
        nobs[j] = len(y1)
    # portmanteau (Eq. 3), cumulative over lags 1..p
    T = len(x1)
    lag_arr = np.asarray(lags, float)
    w = T * (T + 2) / (T - lag_arr)
    Q = np.cumsum(w * rho**2)
    Qb = np.cumsum(w * centered**2, axis=1)
    Q_crit = np.nanquantile(Qb, level, axis=0)
    Q_p = (Qb >= Q[None, :]).mean(axis=0)
    return {
        "lags": np.asarray(lags),
        "rho": rho,
        "lo": lo,
        "hi": hi,
        "sig": (rho < lo) | (rho > hi),
        "Q": Q,
        "Q_crit": Q_crit,
        "Q_p": Q_p,
        "n": nobs,
        "block_len": 1.0 / gamma,
    }


def auto_quantilogram(x, a, lags=range(1, 21), B=1000, seed=0):
    return quantilogram_test(x, x, a, a, lags=lags, B=B, seed=seed)
