"""Test compressione volatilità (fase 17.2)."""

from volatility_compression import (
    detect_volatility_squeeze,
    is_atr_contraction,
    is_boomer,
    is_double_inside,
    is_doji_range_bar,
    is_inside_bar,
    is_narrow_range_bar,
)


def _bar(o, h, l, c, vol=100):
    return {"open": o, "high": h, "low": l, "close": c, "tick_volume": vol}


# ─────────────────────────────────────────────────────────────────────────────
# Narrow Range
# ─────────────────────────────────────────────────────────────────────────────


def test_nr7_true_when_last_smallest():
    bars = [_bar(1.0, 1.5, 0.5, 1.2) for _ in range(6)]
    bars.append(_bar(1.0, 1.05, 0.95, 1.0))
    assert is_narrow_range_bar(bars, n=7) is True


def test_nr7_false_when_last_not_smallest():
    bars = [_bar(1.0, 1.05, 0.95, 1.0) for _ in range(6)]
    bars.append(_bar(1.0, 1.5, 0.5, 1.2))
    assert is_narrow_range_bar(bars, n=7) is False


def test_nr_too_few_bars():
    bars = [_bar(1.0, 1.05, 0.95, 1.0) for _ in range(3)]
    assert is_narrow_range_bar(bars, n=7) is False


def test_nr4_smaller_window():
    bars = [_bar(1.0, 1.5, 0.5, 1.2) for _ in range(3)]
    bars.append(_bar(1.0, 1.05, 0.95, 1.0))
    assert is_narrow_range_bar(bars, n=4) is True


# ─────────────────────────────────────────────────────────────────────────────
# Inside Bar
# ─────────────────────────────────────────────────────────────────────────────


def test_inside_bar_true():
    prev = _bar(1.0, 1.5, 0.5, 1.2)
    curr = _bar(1.1, 1.4, 0.6, 1.2)
    assert is_inside_bar(prev, curr) is True


def test_inside_bar_false_high_outside():
    prev = _bar(1.0, 1.5, 0.5, 1.2)
    curr = _bar(1.1, 1.6, 0.6, 1.2)
    assert is_inside_bar(prev, curr) is False


def test_inside_bar_false_low_outside():
    prev = _bar(1.0, 1.5, 0.5, 1.2)
    curr = _bar(1.1, 1.4, 0.4, 1.2)
    assert is_inside_bar(prev, curr) is False


# ─────────────────────────────────────────────────────────────────────────────
# Boomer
# ─────────────────────────────────────────────────────────────────────────────


def test_boomer_true():
    b1 = _bar(1.0, 1.5, 0.5, 1.2)
    b2 = _bar(1.1, 1.4, 0.6, 1.2)
    b3 = _bar(1.15, 1.3, 0.7, 1.2)
    bars = [b1, b2, b3]
    assert is_boomer(bars) is True


def test_boomer_false_second_not_inside():
    b1 = _bar(1.0, 1.5, 0.5, 1.2)
    b2 = _bar(1.1, 1.4, 0.6, 1.2)
    b3 = _bar(1.15, 1.45, 0.7, 1.2)
    bars = [b1, b2, b3]
    assert is_boomer(bars) is False


def test_boomer_too_few_bars():
    bars = [_bar(1.0, 1.5, 0.5, 1.2)]
    assert is_boomer(bars) is False


# ─────────────────────────────────────────────────────────────────────────────
# Double Inside
# ─────────────────────────────────────────────────────────────────────────────


def test_double_inside_true_with_wide_range():
    history = [_bar(1.0, 1.05, 0.95, 1.02) for _ in range(5)]
    wide = _bar(1.0, 1.5, 0.5, 1.4)
    inside1 = _bar(1.05, 1.4, 0.6, 1.2)
    inside2 = _bar(1.1, 1.35, 0.7, 1.2)
    bars = history + [wide, inside1, inside2]
    assert is_double_inside(bars) is True


def test_double_inside_false_inside1_breaks_high():
    history = [_bar(1.0, 1.05, 0.95, 1.02) for _ in range(5)]
    wide = _bar(1.0, 1.5, 0.5, 1.4)
    inside1 = _bar(1.05, 1.6, 0.6, 1.2)
    inside2 = _bar(1.1, 1.4, 0.7, 1.2)
    bars = history + [wide, inside1, inside2]
    assert is_double_inside(bars) is False


def test_double_inside_false_no_wide_range():
    history = [_bar(1.0, 1.5, 0.5, 1.2) for _ in range(5)]
    notwide = _bar(1.0, 1.55, 0.45, 1.4)
    inside1 = _bar(1.05, 1.4, 0.6, 1.2)
    inside2 = _bar(1.1, 1.35, 0.7, 1.2)
    bars = history + [notwide, inside1, inside2]
    assert is_double_inside(bars) is False


# ─────────────────────────────────────────────────────────────────────────────
# Doji Range
# ─────────────────────────────────────────────────────────────────────────────


def test_doji_range_bar_true():
    bar = _bar(1.0, 1.1, 0.9, 1.005)
    assert is_doji_range_bar(bar, threshold=0.2) is True


def test_doji_range_bar_false_big_body():
    bar = _bar(1.0, 1.1, 0.9, 1.08)
    assert is_doji_range_bar(bar, threshold=0.2) is False


def test_doji_range_bar_zero_range():
    bar = _bar(1.0, 1.0, 1.0, 1.0)
    assert is_doji_range_bar(bar) is False


# ─────────────────────────────────────────────────────────────────────────────
# ATR contraction
# ─────────────────────────────────────────────────────────────────────────────


def test_atr_contraction_true():
    atrs = [1.0] * 19 + [0.5]
    assert is_atr_contraction(atrs, lookback=20, contraction_ratio=0.7) is True


def test_atr_contraction_false_when_high():
    atrs = [1.0] * 19 + [0.95]
    assert is_atr_contraction(atrs, lookback=20, contraction_ratio=0.7) is False


def test_atr_contraction_too_few_valid():
    atrs = [None] * 18 + [1.0, 0.5]
    assert is_atr_contraction(atrs, lookback=20) is False


# ─────────────────────────────────────────────────────────────────────────────
# Aggregator
# ─────────────────────────────────────────────────────────────────────────────


def test_squeeze_detect_no_signals_in_volatile_market():
    bars = []
    for i in range(10):
        rng = 1.0 + 0.5 * (i % 2)
        bars.append(_bar(1.0, 1.0 + rng / 2, 1.0 - rng / 2, 1.0))
    res = detect_volatility_squeeze(bars)
    assert res["squeeze"] is False
    assert res["type"] == "NONE"
    assert res["strength"] == 0.0
    assert res["signals"] == []


def test_squeeze_detect_nr7_only():
    bars = [_bar(1.0, 1.5, 0.5, 1.2) for _ in range(6)]
    bars.append(_bar(1.0, 1.05, 0.95, 1.0))
    res = detect_volatility_squeeze(bars)
    assert res["squeeze"] is True
    assert "NR7" in res["signals"]


def test_squeeze_detect_boomer_combined_with_bb_squeeze():
    history = [_bar(1.0, 1.05, 0.95, 1.0) for _ in range(8)]
    b1 = _bar(1.0, 1.5, 0.5, 1.2)
    b2 = _bar(1.1, 1.4, 0.6, 1.2)
    b3 = _bar(1.15, 1.3, 0.7, 1.2)
    bars = history + [b1, b2, b3]
    bandwidth = [10.0] * 80 + [1.0]
    res = detect_volatility_squeeze(bars, bb_bandwidth_series=bandwidth)
    assert res["squeeze"] is True
    assert "BOOMER" in res["signals"]
    assert "BB_SQUEEZE" in res["signals"]
    assert res["strength"] >= 0.5


def test_squeeze_detect_atr_contraction_signal():
    bars = [_bar(1.0, 1.5, 0.5, 1.2) for _ in range(10)]
    atrs = [1.0] * 19 + [0.4]
    res = detect_volatility_squeeze(bars, atr_series=atrs)
    assert "ATR_CONTRACTION" in res["signals"]
