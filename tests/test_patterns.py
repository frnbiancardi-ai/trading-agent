"""Test riconoscimento pattern candlestick — firme calibrate (Phase 3)."""
from __future__ import annotations

import pytest

from patterns import (
    is_doji,
    is_engulfing,
    is_hammer,
    is_inverted_hammer,
    is_pin_bar,
    scan_patterns,
    load_pattern_config,
)


@pytest.fixture(scope="module")
def cfg():
    """Carica PatternConfig di default una volta per modulo."""
    return load_pattern_config()


def _bar(o, h, l, c, vol=100):
    return {"open": o, "high": h, "low": l, "close": c, "tick_volume": vol}


# ---------- Hammer ----------

def test_is_hammer_classic(cfg):
    bar = _bar(o=1.1010, h=1.1015, l=1.0980, c=1.1012)
    matched, raw = is_hammer(bar, cfg.hammer)
    assert matched is True
    assert raw >= cfg.hammer.calibration.min


def test_is_hammer_rejects_long_upper_shadow(cfg):
    bar = _bar(o=1.1000, h=1.1050, l=1.0995, c=1.1005)
    matched, raw = is_hammer(bar, cfg.hammer)
    assert matched is False
    assert raw == 0.0


def test_is_hammer_rejects_zero_range(cfg):
    bar = _bar(o=1.1000, h=1.1000, l=1.1000, c=1.1000)
    matched, raw = is_hammer(bar, cfg.hammer)
    assert matched is False
    assert raw == 0.0


# ---------- Inverted Hammer ----------

def test_is_inverted_hammer(cfg):
    bar = _bar(o=1.1000, h=1.1030, l=1.0998, c=1.1002)
    matched, raw = is_inverted_hammer(bar, cfg.inverted_hammer)
    assert matched is True
    assert raw >= cfg.inverted_hammer.calibration.min


def test_is_inverted_hammer_rejects_short_upper(cfg):
    """Near-miss PATT-01: upper shadow troppo corta vs body."""
    bar = _bar(o=1.1000, h=1.1005, l=1.0998, c=1.1003)
    matched, raw = is_inverted_hammer(bar, cfg.inverted_hammer)
    assert matched is False
    assert raw == 0.0


# ---------- Engulfing ----------

def test_is_engulfing_bullish(cfg):
    prev = _bar(o=1.1010, h=1.1012, l=1.0995, c=1.1000)
    curr = _bar(o=1.0998, h=1.1025, l=1.0996, c=1.1015)
    m, r = is_engulfing(prev, curr, "bullish", cfg.engulfing)
    assert m is True
    assert r >= cfg.engulfing.calibration.min  # ratio body_curr/body_prev >= 1.0
    m2, _ = is_engulfing(prev, curr, "bearish", cfg.engulfing)
    assert m2 is False


def test_is_engulfing_bearish(cfg):
    prev = _bar(o=1.1000, h=1.1015, l=1.0998, c=1.1010)
    curr = _bar(o=1.1012, h=1.1014, l=1.0995, c=1.0998)
    m, _ = is_engulfing(prev, curr, "bearish", cfg.engulfing)
    assert m is True
    m2, _ = is_engulfing(prev, curr, "bullish", cfg.engulfing)
    assert m2 is False


def test_is_engulfing_invalid_direction(cfg):
    prev = _bar(o=1.1010, h=1.1012, l=1.0995, c=1.1000)
    curr = _bar(o=1.0998, h=1.1025, l=1.0996, c=1.1015)
    m, r = is_engulfing(prev, curr, "sideways", cfg.engulfing)
    assert m is False
    assert r == 0.0


def test_is_engulfing_partial_negative(cfg):
    """Near-miss PATT-03: curr body non ingloba completamente prev body."""
    prev = _bar(o=1.1010, h=1.1015, l=1.0995, c=1.1000)  # bearish, body=10pip
    # curr bullish ma open SOPRA prev.close (no engulfment di apertura)
    curr = _bar(o=1.1003, h=1.1020, l=1.1002, c=1.1018)
    m, r = is_engulfing(prev, curr, "bullish", cfg.engulfing)
    assert m is False
    assert r == 0.0


# ---------- Doji (invariato — non calibrato) ----------

def test_is_doji_classic():
    bar = _bar(o=1.1000, h=1.1010, l=1.0990, c=1.10005)
    assert is_doji(bar) is True


def test_is_doji_rejects_large_body():
    bar = _bar(o=1.1000, h=1.1015, l=1.0990, c=1.1012)
    assert is_doji(bar) is False


# ---------- Pin Bar ----------

def test_is_pin_bar_bullish(cfg):
    bar = _bar(o=1.1010, h=1.1014, l=1.0980, c=1.1012)
    m, r = is_pin_bar(bar, "bullish", cfg.pin_bar)
    assert m is True
    assert r >= cfg.pin_bar.dominant_wick_ratio_min
    m2, _ = is_pin_bar(bar, "bearish", cfg.pin_bar)
    assert m2 is False


def test_is_pin_bar_bearish(cfg):
    bar = _bar(o=1.1010, h=1.1040, l=1.1008, c=1.1006)
    m, _ = is_pin_bar(bar, "bearish", cfg.pin_bar)
    assert m is True


# ---------- scan_patterns: stub Wave 2 — full coverage in plan 03 ----------

def test_scan_patterns_empty():
    assert scan_patterns([], last_n=5) == []


@pytest.mark.skip(reason="scan_patterns rebuilt in plan 03 (Wave 3)")
def test_scan_patterns_multiple(cfg):
    bars = [
        _bar(o=1.1000, h=1.1010, l=1.0990, c=1.1005),
        _bar(o=1.1010, h=1.1015, l=1.0980, c=1.1012),
        _bar(o=1.1010, h=1.1015, l=1.0995, c=1.1000),
        _bar(o=1.0998, h=1.1025, l=1.0996, c=1.1020),
    ]
    found = scan_patterns(bars, last_n=4, cfg=cfg)
    names = {p.name for p in found}
    assert "hammer" in names
    assert "engulfing" in names


@pytest.mark.skip(reason="scan_patterns rebuilt in plan 03 (Wave 3)")
def test_scan_patterns_respects_last_n(cfg):
    bars = [_bar(o=1.0, h=1.001, l=0.999, c=1.0005) for _ in range(10)]
    out = scan_patterns(bars, last_n=3, cfg=cfg)
    rels = {p.bar_index for p in out}
    assert all(r >= -3 for r in rels)
