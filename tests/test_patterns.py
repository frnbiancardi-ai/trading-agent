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


def test_scan_patterns_respects_last_n(cfg):
    bars = [_bar(o=1.0, h=1.001, l=0.999, c=1.0005) for _ in range(10)]
    out = scan_patterns(bars, last_n=3, cfg=cfg)
    rels = {p.bar_index for p in out}
    assert all(r >= -3 for r in rels)


# ====================================================================
# 5 nuovi detector — positivi + near-miss
# ====================================================================

# ---------- Shooting Star (PATT-02) ----------

def test_is_shooting_star_classic(cfg):
    """Shooting star: lungo upper shadow, body piccolo, lower shadow trascurabile."""
    from patterns import is_shooting_star
    # range=30, body=2 (close > open per varietà), upper=24, lower=4 -> upper/body=12
    bar = _bar(o=1.1002, h=1.1030, l=1.0999, c=1.1004)
    m, r = is_shooting_star(bar, cfg.shooting_star)
    assert m is True
    assert r >= cfg.shooting_star.calibration.min


def test_is_shooting_star_rejects_large_body(cfg):
    """Near-miss PATT-02: body troppo grande."""
    from patterns import is_shooting_star
    bar = _bar(o=1.1000, h=1.1020, l=1.0998, c=1.1015)  # body grande
    m, r = is_shooting_star(bar, cfg.shooting_star)
    assert m is False
    assert r == 0.0


# ---------- Morning Star (PATT-04) ----------

def test_is_morning_star_classic(cfg):
    """Morning star: bearish trend -> small body -> bullish reversal con penetrazione."""
    from patterns import is_morning_star
    b1 = _bar(o=1.1050, h=1.1055, l=1.0990, c=1.1000)  # bearish, body=50pip su range=65
    b2 = _bar(o=1.0995, h=1.1005, l=1.0985, c=1.0998)  # small body, range=20
    b3 = _bar(o=1.1000, h=1.1060, l=1.0998, c=1.1055)  # bullish, close > mid_b1=1.1025, penetration=(1.1055-1.1025)/0.0050=0.6
    m, r = is_morning_star(b1, b2, b3, cfg.morning_star)
    assert m is True
    assert r >= cfg.morning_star.calibration.min


def test_is_morning_star_rejects_shallow_b3(cfg):
    """Near-miss PATT-04: b3 chiude SOTTO il midpoint di b1."""
    from patterns import is_morning_star
    b1 = _bar(o=1.1050, h=1.1055, l=1.0990, c=1.1000)
    b2 = _bar(o=1.0995, h=1.1005, l=1.0985, c=1.0998)
    b3 = _bar(o=1.1000, h=1.1020, l=1.0998, c=1.1010)  # close < mid_b1 = 1.1025
    m, r = is_morning_star(b1, b2, b3, cfg.morning_star)
    assert m is False
    assert r == 0.0


# ---------- Evening Star (PATT-04) ----------

def test_is_evening_star_classic(cfg):
    """Evening star: bullish trend -> small body -> bearish reversal."""
    from patterns import is_evening_star
    b1 = _bar(o=1.1000, h=1.1060, l=1.0995, c=1.1050)  # bullish, body=50 su range=65
    b2 = _bar(o=1.1055, h=1.1065, l=1.1045, c=1.1058)  # small body, range=20
    b3 = _bar(o=1.1050, h=1.1052, l=1.0990, c=1.0995)  # bearish, close < mid_b1=1.1025, penetration=(1.1025-1.0995)/0.0050=0.6
    m, r = is_evening_star(b1, b2, b3, cfg.evening_star)
    assert m is True
    assert r >= cfg.evening_star.calibration.min


def test_is_evening_star_rejects_shallow_b3(cfg):
    """Near-miss PATT-04: b3 chiude SOPRA il midpoint di b1."""
    from patterns import is_evening_star
    b1 = _bar(o=1.1000, h=1.1060, l=1.0995, c=1.1050)
    b2 = _bar(o=1.1055, h=1.1065, l=1.1045, c=1.1058)
    b3 = _bar(o=1.1050, h=1.1052, l=1.1030, c=1.1040)  # close > mid_b1
    m, r = is_evening_star(b1, b2, b3, cfg.evening_star)
    assert m is False
    assert r == 0.0


# ---------- Key Reversal (PATT-05) ----------

def test_is_key_reversal_bullish(cfg):
    """Key reversal bullish: outside break al ribasso, close sopra midpoint precedente."""
    from patterns import is_key_reversal
    prev = _bar(o=1.1010, h=1.1015, l=1.0995, c=1.1000)  # midpoint = 1.1005
    curr = _bar(o=1.0998, h=1.1020, l=1.0985, c=1.1018)  # low < prev.low, close > 1.1005
    m, r = is_key_reversal(prev, curr, "bullish", cfg.key_reversal)
    assert m is True
    assert r >= cfg.key_reversal.calibration.min


def test_is_key_reversal_rejects_no_penetration(cfg):
    """Near-miss PATT-05: outside break ma close sotto midpoint."""
    from patterns import is_key_reversal
    prev = _bar(o=1.1010, h=1.1015, l=1.0995, c=1.1000)  # midpoint = 1.1005
    curr = _bar(o=1.0998, h=1.1010, l=1.0985, c=1.1003)  # close < midpoint
    m, r = is_key_reversal(prev, curr, "bullish", cfg.key_reversal)
    assert m is False
    assert r == 0.0


def test_is_key_reversal_bearish(cfg):
    """Key reversal bearish: outside break al rialzo, close sotto midpoint precedente.

    prev bullish: o=1.1000, c=1.1010 -> midpoint=1.1005, range=0.0010
    curr: high=1.1020 > prev.high=1.1010 (outside break) AND close=1.0998 < 1.1005
    penetration = (1.1005 - 1.0998) / 0.0010 = 0.7 >= cfg.min_close_penetration_ratio=0.5
    """
    from patterns import is_key_reversal
    prev = _bar(o=1.1000, h=1.1010, l=1.1000, c=1.1010)  # bullish, midpoint=1.1005
    curr = _bar(o=1.1015, h=1.1020, l=1.0995, c=1.0998)  # high>prev.high, close<midpoint
    m, r = is_key_reversal(prev, curr, "bearish", cfg.key_reversal)
    assert m is True
    assert r >= cfg.key_reversal.calibration.min


# ---------- Inside Bar (PATT-06) ----------

def test_is_inside_bar_classic(cfg):
    """Inside bar: range corrente entro range precedente."""
    from patterns import is_inside_bar
    prev = _bar(o=1.1000, h=1.1050, l=1.0950, c=1.1010)  # range=100
    curr = _bar(o=1.1015, h=1.1030, l=1.0990, c=1.1020)  # range=40, contenuto
    m, r = is_inside_bar(prev, curr, cfg.inside_bar)
    assert m is True
    assert r > 0.0


def test_is_inside_bar_rejects_overflow(cfg):
    """Near-miss PATT-06: curr.high oltrepassa prev.high."""
    from patterns import is_inside_bar
    prev = _bar(o=1.1000, h=1.1050, l=1.0950, c=1.1010)
    curr = _bar(o=1.1015, h=1.1055, l=1.0990, c=1.1020)  # high > prev.high
    m, r = is_inside_bar(prev, curr, cfg.inside_bar)
    assert m is False
    assert r == 0.0


# ====================================================================
# scan_patterns + PatternHit schema (PATT-07)
# ====================================================================

def test_scan_patterns_returns_pattern_hit(cfg):
    """PATT-07: scan_patterns ritorna list[PatternHit] con tutti i 6 campi."""
    from patterns import PatternHit
    bars = [
        _bar(o=1.1000, h=1.1010, l=1.0990, c=1.1005),
        _bar(o=1.1010, h=1.1015, l=1.0980, c=1.1012),  # hammer
    ]
    out = scan_patterns(bars, last_n=2, cfg=cfg)
    assert all(isinstance(h, PatternHit) for h in out)
    if out:
        h = out[0]
        # Tutti i campi accessibili
        _ = h.name, h.bar_index, h.span_bars, h.extreme_price, h.confidence, h.direction


def test_confidence_in_unit_interval(cfg):
    """PATT-07: ogni hit ha confidence in [0, 1]."""
    bars = [
        _bar(o=1.1050, h=1.1055, l=1.0990, c=1.1000),
        _bar(o=1.0995, h=1.1005, l=1.0985, c=1.0998),
        _bar(o=1.1000, h=1.1050, l=1.0998, c=1.1045),  # morning star anchor
        _bar(o=1.1010, h=1.1015, l=1.0980, c=1.1012),  # hammer
    ]
    out = scan_patterns(bars, last_n=4, cfg=cfg)
    assert len(out) > 0, "expected at least one hit"
    for h in out:
        assert 0.0 <= h.confidence <= 1.0, f"{h.name} confidence {h.confidence} out of [0,1]"


def test_inside_and_pin_coexist(cfg):
    """PATT-06 Pitfall 4: una barra inside+pin emette 2 hit distinti."""
    # prev grande, curr piccolo (inside) ma con pin bullish
    prev = _bar(o=1.1000, h=1.1050, l=1.0950, c=1.1010)
    curr = _bar(o=1.1020, h=1.1024, l=1.0990, c=1.1022)  # inside + pin bullish
    bars = [prev, curr]
    out = scan_patterns(bars, last_n=2, cfg=cfg)
    names = {h.name for h in out}
    # entrambi devono comparire (geometria fissata sopra)
    assert "inside_bar" in names
    assert "pin_bar" in names


def test_morning_star_extreme_is_swing_low(cfg):
    """PATT-07: extreme_price = min low dei 3 bar dello star span."""
    bars = [
        _bar(o=1.1050, h=1.1055, l=1.0990, c=1.1000),  # b1 low=1.0990
        _bar(o=1.0995, h=1.1005, l=1.0985, c=1.0998),  # b2 low=1.0985 (minimo)
        _bar(o=1.1000, h=1.1060, l=1.0998, c=1.1055),  # b3 low=1.0998 (b2.low=1.0985 still min); penetration=0.6
    ]
    out = scan_patterns(bars, last_n=3, cfg=cfg)
    star_hits = [h for h in out if h.name == "morning_star"]
    assert len(star_hits) == 1
    h = star_hits[0]
    assert h.span_bars == 3
    assert h.extreme_price == 1.0985  # min low across 3 bars
    assert h.direction == "bullish"
