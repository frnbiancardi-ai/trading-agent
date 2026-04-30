"""Test riconoscimento pattern candlestick."""

from patterns import (
    is_doji,
    is_engulfing,
    is_hammer,
    is_inverted_hammer,
    is_pin_bar,
    scan_patterns,
)


def _bar(o, h, l, c, vol=100):
    return {"open": o, "high": h, "low": l, "close": c, "tick_volume": vol}


def test_is_hammer_classic():
    bar = _bar(o=1.1010, h=1.1015, l=1.0980, c=1.1012)
    assert is_hammer(bar) is True


def test_is_hammer_rejects_long_upper_shadow():
    bar = _bar(o=1.1000, h=1.1050, l=1.0995, c=1.1005)
    assert is_hammer(bar) is False


def test_is_hammer_rejects_zero_range():
    bar = _bar(o=1.1000, h=1.1000, l=1.1000, c=1.1000)
    assert is_hammer(bar) is False


def test_is_inverted_hammer():
    bar = _bar(o=1.1000, h=1.1030, l=1.0998, c=1.1002)
    assert is_inverted_hammer(bar) is True


def test_is_engulfing_bullish():
    prev = _bar(o=1.1010, h=1.1012, l=1.0995, c=1.1000)
    curr = _bar(o=1.0998, h=1.1025, l=1.0996, c=1.1015)
    assert is_engulfing(prev, curr, "bullish") is True
    assert is_engulfing(prev, curr, "bearish") is False


def test_is_engulfing_bearish():
    prev = _bar(o=1.1000, h=1.1015, l=1.0998, c=1.1010)
    curr = _bar(o=1.1012, h=1.1014, l=1.0995, c=1.0998)
    assert is_engulfing(prev, curr, "bearish") is True
    assert is_engulfing(prev, curr, "bullish") is False


def test_is_engulfing_invalid_direction():
    prev = _bar(o=1.1010, h=1.1012, l=1.0995, c=1.1000)
    curr = _bar(o=1.0998, h=1.1025, l=1.0996, c=1.1015)
    assert is_engulfing(prev, curr, "sideways") is False


def test_is_doji_classic():
    bar = _bar(o=1.1000, h=1.1010, l=1.0990, c=1.10005)
    assert is_doji(bar) is True


def test_is_doji_rejects_large_body():
    bar = _bar(o=1.1000, h=1.1015, l=1.0990, c=1.1012)
    assert is_doji(bar) is False


def test_is_pin_bar_bullish():
    bar = _bar(o=1.1010, h=1.1014, l=1.0980, c=1.1012)
    assert is_pin_bar(bar, "bullish") is True
    assert is_pin_bar(bar, "bearish") is False


def test_is_pin_bar_bearish():
    bar = _bar(o=1.1010, h=1.1040, l=1.1008, c=1.1006)
    assert is_pin_bar(bar, "bearish") is True


def test_scan_patterns_multiple():
    bars = [
        _bar(o=1.1000, h=1.1010, l=1.0990, c=1.1005),
        _bar(o=1.1010, h=1.1015, l=1.0980, c=1.1012),
        _bar(o=1.1010, h=1.1015, l=1.0995, c=1.1000),
        _bar(o=1.0998, h=1.1025, l=1.0996, c=1.1020),
    ]
    found = scan_patterns(bars, last_n=4)
    names = {p["pattern"] for p in found}
    assert "hammer" in names
    assert "engulfing" in names


def test_scan_patterns_empty():
    assert scan_patterns([], last_n=5) == []


def test_scan_patterns_respects_last_n():
    bars = [_bar(o=1.0, h=1.001, l=0.999, c=1.0005) for _ in range(10)]
    out = scan_patterns(bars, last_n=3)
    rels = {p["bar_index"] for p in out}
    assert all(r >= -3 for r in rels)
