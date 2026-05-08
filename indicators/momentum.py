"""Indicatori di momentum: RSI e divergenza prezzo/RSI.

Wave 0 = lift-and-shift verbatim da `indicators.py`. Wave 1 aggiungerà
MACD, Stochastic, ADX/DMI con dataclass `<Indicator>Result` co-locati qui.
"""
from __future__ import annotations

from indicators._helpers import _wilder_rsi


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period + 1:
        return out

    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains[i] = diff
        elif diff < 0:
            losses[i] = -diff

    avg_gain = sum(gains[1:period + 1]) / period
    avg_loss = sum(losses[1:period + 1]) / period
    out[period] = _wilder_rsi(avg_gain, avg_loss)

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = _wilder_rsi(avg_gain, avg_loss)

    return out


def check_rsi_divergence(
    bars: list[dict],
    rsi_values: list[float | None],
    lookback: int = 20,
) -> str:
    """Divergenza classica price vs RSI sulle ultime `lookback` barre.

    Ritorna 'BULLISH_DIVERGENCE', 'BEARISH_DIVERGENCE', o 'NONE'.
    Bullish: lower low di prezzo + higher low di RSI.
    Bearish: higher high di prezzo + lower high di RSI.
    """
    if not bars or not rsi_values or len(bars) != len(rsi_values):
        return "NONE"
    n = len(bars)
    start = max(0, n - lookback)
    lows: list[tuple[int, float, float]] = []
    highs: list[tuple[int, float, float]] = []
    for i in range(start + 1, n - 1):
        if rsi_values[i] is None:
            continue
        if bars[i]["low"] < bars[i - 1]["low"] and bars[i]["low"] < bars[i + 1]["low"]:
            lows.append((i, bars[i]["low"], rsi_values[i]))  # type: ignore[arg-type]
        if bars[i]["high"] > bars[i - 1]["high"] and bars[i]["high"] > bars[i + 1]["high"]:
            highs.append((i, bars[i]["high"], rsi_values[i]))  # type: ignore[arg-type]

    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if b[1] < a[1] and b[2] > a[2]:
            return "BULLISH_DIVERGENCE"
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if b[1] > a[1] and b[2] < a[2]:
            return "BEARISH_DIVERGENCE"
    return "NONE"
