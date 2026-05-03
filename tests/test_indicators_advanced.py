"""Test indicatori avanzati (fase 17.1)."""

from indicators_advanced import (
    bandwidth_squeeze,
    bollinger_bands,
    macd,
    parabolic_sar,
    vhf,
    vortex,
)


# ─────────────────────────────────────────────────────────────────────────────
# Bollinger Bands
# ─────────────────────────────────────────────────────────────────────────────


def test_bollinger_bands_constant_series_zero_bandwidth():
    closes = [1.0] * 30
    bb = bollinger_bands(closes, period=20, k=2.0)
    assert bb["middle"][-1] == 1.0
    assert bb["upper"][-1] == 1.0
    assert bb["lower"][-1] == 1.0
    assert bb["bandwidth"][-1] == 0.0
    assert bb["percent_b"][-1] == 0.5


def test_bollinger_bands_short_series_returns_none():
    closes = [1.0, 1.1, 1.2]
    bb = bollinger_bands(closes, period=20)
    assert all(v is None for v in bb["middle"])
    assert all(v is None for v in bb["bandwidth"])


def test_bollinger_bands_known_values():
    closes = [float(i) for i in range(1, 21)]
    bb = bollinger_bands(closes, period=20, k=2.0)
    assert abs(bb["middle"][-1] - 10.5) < 1e-9
    assert bb["bandwidth"][-1] is not None
    assert bb["bandwidth"][-1] > 0
    assert bb["upper"][-1] > bb["middle"][-1] > bb["lower"][-1]


def test_bollinger_bands_length_matches_input():
    closes = [1.0 + 0.1 * i for i in range(50)]
    bb = bollinger_bands(closes, period=20)
    assert len(bb["middle"]) == 50
    assert len(bb["bandwidth"]) == 50
    assert bb["middle"][18] is None
    assert bb["middle"][19] is not None


def test_bollinger_bands_invalid_period():
    closes = [1.0] * 30
    bb = bollinger_bands(closes, period=0)
    assert all(v is None for v in bb["middle"])


# ─────────────────────────────────────────────────────────────────────────────
# MACD
# ─────────────────────────────────────────────────────────────────────────────


def test_macd_short_series_all_none():
    closes = [1.0, 1.1, 1.2, 1.3, 1.4]
    m = macd(closes)
    assert all(v is None for v in m["macd"])
    assert all(v is None for v in m["signal"])
    assert all(v is None for v in m["histogram"])


def test_macd_length_matches_input():
    closes = [1.0 + 0.01 * i for i in range(60)]
    m = macd(closes, fast=12, slow=26, signal=9)
    assert len(m["macd"]) == 60
    assert len(m["signal"]) == 60
    assert len(m["histogram"]) == 60


def test_macd_uptrend_macd_above_zero():
    closes = [10.0 + 0.5 * i for i in range(60)]
    m = macd(closes)
    last = m["macd"][-1]
    assert last is not None
    assert last > 0


def test_macd_downtrend_macd_below_zero():
    closes = [60.0 - 0.5 * i for i in range(60)]
    m = macd(closes)
    last = m["macd"][-1]
    assert last is not None
    assert last < 0


def test_macd_histogram_equals_macd_minus_signal():
    closes = [10.0 + 0.3 * i + (0.5 if i % 4 == 0 else 0) for i in range(80)]
    m = macd(closes)
    for i in range(len(closes)):
        if m["macd"][i] is not None and m["signal"][i] is not None:
            expected = m["macd"][i] - m["signal"][i]
            assert abs(m["histogram"][i] - expected) < 1e-9


# ─────────────────────────────────────────────────────────────────────────────
# Vortex
# ─────────────────────────────────────────────────────────────────────────────


def test_vortex_short_series_all_none():
    highs = [1.1, 1.2]
    lows = [1.0, 1.1]
    closes = [1.05, 1.15]
    v = vortex(highs, lows, closes, period=14)
    assert all(x is None for x in v["vi_plus"])
    assert all(x is None for x in v["vi_minus"])


def test_vortex_uptrend_vi_plus_dominates():
    highs = [1.0 + 0.05 * i for i in range(30)]
    lows = [0.95 + 0.05 * i for i in range(30)]
    closes = [0.98 + 0.05 * i for i in range(30)]
    v = vortex(highs, lows, closes, period=14)
    assert v["vi_plus"][-1] > v["vi_minus"][-1]


def test_vortex_downtrend_vi_minus_dominates():
    highs = [3.0 - 0.05 * i for i in range(30)]
    lows = [2.95 - 0.05 * i for i in range(30)]
    closes = [2.97 - 0.05 * i for i in range(30)]
    v = vortex(highs, lows, closes, period=14)
    assert v["vi_minus"][-1] > v["vi_plus"][-1]


def test_vortex_mismatched_lengths_raises():
    import pytest
    highs = [1.0 + 0.05 * i for i in range(20)]
    lows = [0.95 + 0.05 * i for i in range(19)]
    closes = [0.98 + 0.05 * i for i in range(20)]
    with pytest.raises(ValueError):
        vortex(highs, lows, closes, period=14)


# ─────────────────────────────────────────────────────────────────────────────
# VHF
# ─────────────────────────────────────────────────────────────────────────────


def test_vhf_short_series_all_none():
    closes = [1.0] * 5
    out = vhf(closes, period=28)
    assert all(v is None for v in out)


def test_vhf_strong_trend_high_value():
    closes = [1.0 + 0.5 * i for i in range(40)]
    out = vhf(closes, period=28)
    last = out[-1]
    assert last is not None
    assert last > 0.9


def test_vhf_choppy_market_low_value():
    closes = []
    for i in range(40):
        closes.append(1.0 + 0.05 * (i % 2))
    out = vhf(closes, period=28)
    last = out[-1]
    assert last is not None
    assert last < 0.5


def test_vhf_invalid_period():
    closes = [1.0] * 30
    out = vhf(closes, period=0)
    assert all(v is None for v in out)


# ─────────────────────────────────────────────────────────────────────────────
# Parabolic SAR
# ─────────────────────────────────────────────────────────────────────────────


def test_parabolic_sar_too_short():
    out = parabolic_sar([1.0], [0.9])
    assert all(v is None for v in out)


def test_parabolic_sar_uptrend_sar_below_price():
    highs = [1.0 + 0.05 * i for i in range(20)]
    lows = [0.98 + 0.05 * i for i in range(20)]
    out = parabolic_sar(highs, lows)
    valid_sars_below = [
        out[i] for i in range(2, len(out))
        if out[i] is not None and out[i] <= lows[i]
    ]
    assert len(valid_sars_below) >= 10


def test_parabolic_sar_downtrend_sar_above_price():
    highs = [3.0 - 0.05 * i for i in range(20)]
    lows = [2.98 - 0.05 * i for i in range(20)]
    out = parabolic_sar(highs, lows)
    valid_sars_above = [
        out[i] for i in range(2, len(out))
        if out[i] is not None and out[i] >= highs[i]
    ]
    assert len(valid_sars_above) >= 10


def test_parabolic_sar_length_matches_input():
    n = 50
    highs = [1.0 + 0.05 * i for i in range(n)]
    lows = [0.98 + 0.05 * i for i in range(n)]
    out = parabolic_sar(highs, lows)
    assert len(out) == n
    assert out[0] is None
    assert out[1] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Bandwidth squeeze
# ─────────────────────────────────────────────────────────────────────────────


def test_bandwidth_squeeze_true_when_low():
    series = [10.0] * 80 + [1.0]
    assert bandwidth_squeeze(series, lookback=100, percentile=0.2) is True


def test_bandwidth_squeeze_false_when_high():
    series = [1.0] * 80 + [10.0]
    assert bandwidth_squeeze(series, lookback=100, percentile=0.2) is False


def test_bandwidth_squeeze_empty_series():
    assert bandwidth_squeeze([], lookback=100, percentile=0.2) is False


def test_bandwidth_squeeze_too_few_valid():
    series = [None] * 90 + [1.0, 2.0, 3.0]
    assert bandwidth_squeeze(series, lookback=100, percentile=0.2) is False


def test_bandwidth_squeeze_invalid_percentile():
    series = [1.0] * 100
    assert bandwidth_squeeze(series, lookback=100, percentile=0.0) is False
    assert bandwidth_squeeze(series, lookback=100, percentile=1.5) is False


def test_bandwidth_squeeze_last_none():
    series = [1.0] * 99 + [None]
    assert bandwidth_squeeze(series, lookback=100, percentile=0.2) is False
