"""Pattern di compressione di volatilità (Defendi cap 4).

Tutte le funzioni operano su list[dict] con chiavi 'open', 'high', 'low',
'close' e (opzionale) 'tick_volume'/'volume'.

Pattern rilevati:
- Narrow Range (NR4/NR7): barra con range più piccolo delle precedenti N-1
- Inside Bar: high/low inscritti nella barra precedente
- Boomer: due Inside Bar consecutive
- Double Inside: Wide Range Bar seguita da 2 Inside Bar
- Doji Range Bar: |close-open| <= 20% del range
- Volatility Squeeze: aggregatore che combina i pattern + Bollinger BandWidth
  basso + ATR contraction
"""


def _bar_range(bar: dict) -> float:
    return bar["high"] - bar["low"]


def _bar_body(bar: dict) -> float:
    return abs(bar["close"] - bar["open"])


def is_narrow_range_bar(bars: list[dict], n: int = 7) -> bool:
    """Ultima barra ha range strettamente minore di tutte le precedenti n-1.

    NR7: n=7 → range più piccolo delle ultime 6 barre.
    NR4: n=4 → range più piccolo delle ultime 3 barre.
    """
    if not bars or n <= 1 or len(bars) < n:
        return False
    last_range = _bar_range(bars[-1])
    if last_range <= 0:
        return False
    for prev in bars[-n:-1]:
        if _bar_range(prev) <= last_range:
            return False
    return True


def is_inside_bar(prev: dict, curr: dict) -> bool:
    return curr["high"] < prev["high"] and curr["low"] > prev["low"]


def is_boomer(bars: list[dict]) -> bool:
    """Due Inside Bar consecutive: bars[-2] inside di bars[-3] e
    bars[-1] inside di bars[-2].
    """
    if not bars or len(bars) < 3:
        return False
    return is_inside_bar(bars[-3], bars[-2]) and is_inside_bar(bars[-2], bars[-1])


def is_double_inside(bars: list[dict]) -> bool:
    """Wide Range Bar in bars[-3] + bars[-2] e bars[-1] entrambe inside di bars[-3].

    Wide Range Bar definita come range > 1.5x del range medio precedente
    (calcolato su bars[-8:-3], se disponibile).
    """
    if not bars or len(bars) < 3:
        return False
    wide = bars[-3]
    b2 = bars[-2]
    b1 = bars[-1]
    if not (b2["high"] < wide["high"] and b2["low"] > wide["low"]):
        return False
    if not (b1["high"] < wide["high"] and b1["low"] > wide["low"]):
        return False
    if len(bars) >= 8:
        prev_window = bars[-8:-3]
        avg_range = sum(_bar_range(b) for b in prev_window) / len(prev_window)
        if avg_range > 0 and _bar_range(wide) < 1.5 * avg_range:
            return False
    return True


def is_doji_range_bar(bar: dict, threshold: float = 0.2) -> bool:
    rng = _bar_range(bar)
    if rng <= 0:
        return False
    return _bar_body(bar) <= threshold * rng


def is_atr_contraction(
    atr_series: list[float | None],
    lookback: int = 20,
    contraction_ratio: float = 0.7,
) -> bool:
    """ATR ultimo significativamente sotto la media degli ultimi `lookback`.

    True se atr[-1] <= contraction_ratio * mean(atr ultimi lookback validi).
    """
    if not atr_series or lookback <= 0:
        return False
    valid = [v for v in atr_series[-lookback:] if v is not None]
    if len(valid) < max(5, lookback // 2):
        return False
    last = atr_series[-1]
    if last is None or last <= 0:
        return False
    mean_atr = sum(valid) / len(valid)
    if mean_atr <= 0:
        return False
    return last <= contraction_ratio * mean_atr


def detect_volatility_squeeze(
    bars: list[dict],
    atr_series: list[float | None] | None = None,
    bb_bandwidth_series: list[float | None] | None = None,
    bb_squeeze_lookback: int = 100,
    bb_squeeze_percentile: float = 0.2,
) -> dict:
    """Rilevatore unificato. Ritorna:

    {
      'squeeze': bool,           # True se almeno un pattern attivo
      'type': str,               # 'NR7'|'NR4'|'BOOMER'|'DOUBLE_INSIDE'|'BB_SQUEEZE'|'ATR_CONTRACTION'|'NONE'
      'strength': float,         # 0..1, somma normalizzata segnali attivi
      'signals': list[str],      # tutti i pattern attivi
    }
    """
    from indicators_advanced import bandwidth_squeeze

    signals: list[str] = []
    if is_narrow_range_bar(bars, n=7):
        signals.append("NR7")
    elif is_narrow_range_bar(bars, n=4):
        signals.append("NR4")
    if is_boomer(bars):
        signals.append("BOOMER")
    if is_double_inside(bars):
        signals.append("DOUBLE_INSIDE")
    if bb_bandwidth_series is not None and bandwidth_squeeze(
        bb_bandwidth_series,
        lookback=bb_squeeze_lookback,
        percentile=bb_squeeze_percentile,
    ):
        signals.append("BB_SQUEEZE")
    if atr_series is not None and is_atr_contraction(atr_series):
        signals.append("ATR_CONTRACTION")

    primary = signals[0] if signals else "NONE"
    strength = min(1.0, len(signals) * 0.25)

    return {
        "squeeze": bool(signals),
        "type": primary,
        "strength": round(strength, 4),
        "signals": signals,
    }
