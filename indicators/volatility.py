"""Indicatori di volatilità: ATR (Wave 0).

Wave 1 aggiungerà Bollinger Bands + squeeze, Keltner, classifier di regime
(INDIC-14) con dataclass `<Indicator>Result` e loader `regime.yaml`.
"""
from __future__ import annotations


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period + 1:
        return out
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, closes devono avere la stessa lunghezza")

    tr = [0.0] * n
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    seed = sum(tr[1:period + 1]) / period
    out[period] = seed
    for i in range(period + 1, n):
        prev = out[i - 1]
        out[i] = (prev * (period - 1) + tr[i]) / period  # type: ignore[operator]

    return out
