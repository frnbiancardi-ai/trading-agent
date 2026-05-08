"""Indicatori di struttura: support/resistance, qualità breakout (Wave 0).

Wave 2 aggiungerà Donchian, Pivots (classico + Camarilla, daily/session/weekly),
Fibonacci sui swing leg.
"""
from __future__ import annotations

from indicators.volume import avg_volume


def find_support_resistance(bars: list[dict], lookback: int = 100, window: int = 2) -> dict:
    """Support e resistance dinamici via pivot swing high/low.

    Ritorna {'support': float|None, 'resistance': float|None}.
    Pivot: barra il cui high (low) è max (min) nella finestra ±window.
    """
    if not bars:
        return {"support": None, "resistance": None}

    sub = bars[-lookback:] if len(bars) > lookback else bars
    n = len(sub)
    if n < 2 * window + 1:
        return {
            "support": min(b["low"] for b in sub),
            "resistance": max(b["high"] for b in sub),
        }

    swing_highs: list[float] = []
    swing_lows: list[float] = []
    for i in range(window, n - window):
        hi = sub[i]["high"]
        lo = sub[i]["low"]
        is_high = all(sub[i]["high"] >= sub[j]["high"] for j in range(i - window, i + window + 1) if j != i)
        is_low = all(sub[i]["low"] <= sub[j]["low"] for j in range(i - window, i + window + 1) if j != i)
        if is_high:
            swing_highs.append(hi)
        if is_low:
            swing_lows.append(lo)

    resistance = max(swing_highs) if swing_highs else max(b["high"] for b in sub)
    support = min(swing_lows) if swing_lows else min(b["low"] for b in sub)
    return {"support": support, "resistance": resistance}


def check_breakout_quality(
    bars: list[dict],
    sr: dict,
    volume_threshold: float = 1.3,
    avg_period: int = 20,
) -> str:
    """Ritorna 'CLEAN', 'WEAK', 'NONE' valutando ultima barra rispetto a SR."""
    if not bars or not sr:
        return "NONE"
    last = bars[-1]
    support = sr.get("support")
    resistance = sr.get("resistance")
    if support is None and resistance is None:
        return "NONE"

    broke_up = resistance is not None and last["close"] > resistance
    broke_down = support is not None and last["close"] < support
    if not (broke_up or broke_down):
        return "NONE"

    avg_vol = avg_volume(bars[:-1], avg_period)
    if avg_vol <= 0:
        return "WEAK"
    last_vol = last.get("tick_volume", last.get("volume", 0)) or 0
    ratio = last_vol / avg_vol
    return "CLEAN" if ratio >= volume_threshold else "WEAK"
