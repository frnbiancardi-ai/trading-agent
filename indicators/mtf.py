"""Indicatori multi-timeframe: trend strength (Wave 0).

Wave 3 aggiungerà `align(streams)` per INDIC-13 (sign-agreement EMA50-slope su H4/H1/M15)
con `MTFAlignmentResult`.
"""
from __future__ import annotations


def calculate_trend_strength(
    bars: list[dict],
    sma_fast: float | None,
    sma_slow: float | None,
    coherence_window: int = 10,
) -> float:
    """Forza trend in [0.0, 1.0].

    Combina:
    - separazione normalizzata tra SMA veloce e SMA lenta (50%)
    - coerenza direzionale: frazione di close consecutivi che seguono la pendenza SMA (50%)
    """
    if sma_fast is None or sma_slow is None or sma_slow == 0:
        return 0.0
    if not bars:
        return 0.0

    separation = abs(sma_fast - sma_slow) / abs(sma_slow)
    sep_score = min(separation / 0.005, 1.0)

    closes = [b["close"] for b in bars[-coherence_window:]]
    if len(closes) < 2:
        coherence_score = 0.0
    else:
        direction = 1 if sma_fast > sma_slow else -1
        moves = 0
        aligned = 0
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            if diff == 0:
                continue
            moves += 1
            if (diff > 0 and direction > 0) or (diff < 0 and direction < 0):
                aligned += 1
        coherence_score = aligned / moves if moves else 0.0

    return round(0.5 * sep_score + 0.5 * coherence_score, 4)
