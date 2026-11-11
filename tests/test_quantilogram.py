import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.quantilogram import cross_quantilogram, quantilogram_test  # noqa: E402


def test_hand_computed_median():
    rng = np.random.default_rng(1)
    x1, x2 = rng.standard_normal(501), rng.standard_normal(501)
    k = 1
    q1, q2 = np.sort(x1)[int(np.ceil(.5 * 501)) - 1], np.sort(x2)[int(np.ceil(.5 * 501)) - 1]
    p1 = (x1[k:] < q1) - .5
    p2 = (x2[:-k] < q2) - .5
    expected = (p1 * p2).sum() / np.sqrt((p1**2).sum() * (p2**2).sum())
    assert abs(cross_quantilogram(x1, x2, .5, .5, k) - expected) < 1e-12


def test_size_under_null():
    """Independent AR(1) pairs -> lag-1 rejection rate near 5%."""
    rng = np.random.default_rng(2)
    rej = 0
    sims = 200
    for s in range(sims):
        e1, e2 = rng.standard_normal((2, 800))
        x1, x2 = np.empty(800), np.empty(800)
        x1[0], x2[0] = e1[0], e2[0]
        for t in range(1, 800):
            x1[t] = .3 * x1[t - 1] + e1[t]
            x2[t] = .3 * x2[t - 1] + e2[t]
        r = quantilogram_test(x1, x2, .1, .1, lags=[1], B=199, seed=s)
        rej += bool(r["sig"][0])
    rate = rej / sims
    print("size:", rate)
    assert 0.01 <= rate <= 0.11


def test_power_planted_tail():
    """x1_t gets a negative shock whenever x2_{t-1} is in its lower decile."""
    rng = np.random.default_rng(3)
    x2 = rng.standard_normal(1500)
    x1 = rng.standard_normal(1500)
    x1[1:] -= 2.0 * (x2[:-1] < np.quantile(x2, .1))
    r = quantilogram_test(x1, x2, .1, .1, lags=[1, 2, 3], B=299, seed=0)
    assert r["sig"][0] and r["rho"][0] > .2
    assert abs(r["rho"][1]) < .1  # no spurious lag-2 effect


if __name__ == "__main__":
    test_hand_computed_median(); print("hand ok")
    test_power_planted_tail(); print("power ok")
    test_size_under_null()
