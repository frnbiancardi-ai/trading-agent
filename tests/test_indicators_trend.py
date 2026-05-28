"""Test indicators.trend (SMA, EMA) — sanity post-lift-and-shift."""
from __future__ import annotations

from indicators.trend import sma, ema


def test_sma_constant_series():
    assert sma([1.0] * 30, 5)[4] == 1.0
    assert sma([1.0] * 30, 5)[0] is None


def test_ema_seed_equals_sma():
    # EMA seed = mean of first `period` values
    vals = [1.0, 2.0, 3.0, 4.0, 5.0] + [5.0] * 20
    out = ema(vals, 5)
    assert out[0] is None and out[3] is None
    assert abs(out[4] - 3.0) < 1e-12
