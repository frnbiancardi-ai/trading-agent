"""Pullback engine (Defendi cap 5).

Rileva ritorni dei prezzi su un livello statico precedentemente rotto:
- Long pullback: dopo un breakout rialzista, prezzi tornano verso ex-resistance
  (ora supporto). Entry su trigger di continuazione (Inside/NR7) con volume in
  contrazione.
- Short pullback: speculare, ritorno verso ex-support (ora resistance).

API principale: `detect_pullback(bars, atr_value, ...)` che ritorna un dict con
i dettagli se un setup di pullback è attivo.
"""

from indicators import avg_volume
from volatility_compression import is_inside_bar, is_narrow_range_bar


def _bar_volume(bar: dict) -> float:
    return bar.get("tick_volume", bar.get("volume", 0)) or 0


def _has_pullback_entry_trigger(bars: list[dict]) -> tuple[bool, str]:
    """Trigger di continuazione sull'ultima barra.

    Ritorna (trigger_attivo, nome_pattern).
    Pattern accettati: Inside Bar (vs barra precedente) o NR7.
    """
    if not bars or len(bars) < 7:
        return False, ""
    last = bars[-1]
    prev = bars[-2]
    if is_inside_bar(prev, last):
        return True, "INSIDE"
    if is_narrow_range_bar(bars, n=7):
        return True, "NR7"
    return False, ""


def _volume_in_contraction(
    bars: list[dict],
    avg_period: int = 5,
    ratio_max: float = 1.0,
) -> bool:
    """Volume ultima barra <= ratio_max * media volumi `avg_period` precedenti."""
    if not bars or len(bars) < avg_period + 1:
        return False
    last_vol = _bar_volume(bars[-1])
    if last_vol <= 0:
        return False
    avg = avg_volume(bars[-avg_period - 1:-1], avg_period)
    if avg <= 0:
        return False
    return last_vol <= ratio_max * avg


def _find_breakout_in_window(
    bars: list[dict],
    history_lookback: int,
    min_bars_after: int,
    max_bars_after: int,
) -> dict | None:
    """Cerca una barra di breakout fra `len(bars) - max_bars_after`
    e `len(bars) - min_bars_after`. Per ogni candidato:

    - prev_R = max high di `history_lookback` barre precedenti
    - prev_S = min low di `history_lookback` barre precedenti
    - se close[candidato] > prev_R → breakout rialzista (livello = prev_R)
    - se close[candidato] < prev_S → breakout ribassista (livello = prev_S)

    Ritorna il candidato più recente (ultimo trovato).
    """
    n = len(bars)
    upper_idx = n - min_bars_after - 1  # incluso
    lower_idx = max(history_lookback, n - max_bars_after - 1)
    if lower_idx > upper_idx:
        return None

    for i in range(upper_idx, lower_idx - 1, -1):
        history = bars[i - history_lookback:i]
        if not history:
            continue
        prev_R = max(b["high"] for b in history)
        prev_S = min(b["low"] for b in history)
        candle = bars[i]
        if candle["close"] > prev_R:
            return {
                "direction": "BUY",
                "level": prev_R,
                "index": i,
                "bars_since": n - 1 - i,
            }
        if candle["close"] < prev_S:
            return {
                "direction": "SELL",
                "level": prev_S,
                "index": i,
                "bars_since": n - 1 - i,
            }
    return None


def detect_pullback(
    bars: list[dict],
    atr_value: float | None,
    breakout_lookback_bars: int = 20,
    history_lookback: int = 20,
    tolerance_atr_multiple: float = 0.5,
    min_bars_after_breakout: int = 2,
    max_bars_after_breakout: int = 8,
    require_volume_contraction: bool = True,
) -> dict:
    """Rileva un setup di pullback.

    Ritorna:
    {
      'pullback': bool,
      'direction': 'BUY'|'SELL'|None,
      'breakout_level': float|None,
      'breakout_index': int|None,
      'bars_since_breakout': int|None,
      'trigger_pattern': str,
      'reason': str,
    }
    """
    out = {
        "pullback": False, "direction": None,
        "breakout_level": None, "breakout_index": None,
        "bars_since_breakout": None,
        "trigger_pattern": "", "reason": "",
    }
    if not bars or atr_value is None or atr_value <= 0:
        out["reason"] = "atr_invalid_or_no_bars"
        return out
    if breakout_lookback_bars <= 0 or history_lookback <= 0:
        out["reason"] = "lookback_invalid"
        return out

    breakout = _find_breakout_in_window(
        bars,
        history_lookback=history_lookback,
        min_bars_after=min_bars_after_breakout,
        max_bars_after=max_bars_after_breakout,
    )
    if breakout is None:
        out["reason"] = "no_recent_breakout"
        return out

    last = bars[-1]
    level = breakout["level"]
    tol = tolerance_atr_multiple * atr_value

    if breakout["direction"] == "BUY":
        # close ultima vicino al livello, ma ancora sopra (sano), oppure
        # leggermente sotto entro tol (test del livello)
        if not (level - tol <= last["close"] <= level + tol):
            out["reason"] = "price_far_from_breakout_level"
            return out
        if last["low"] < level - tol:
            out["reason"] = "low_broke_below_level"
            return out
    else:
        if not (level - tol <= last["close"] <= level + tol):
            out["reason"] = "price_far_from_breakout_level"
            return out
        if last["high"] > level + tol:
            out["reason"] = "high_broke_above_level"
            return out

    has_trigger, trigger_name = _has_pullback_entry_trigger(bars)
    if not has_trigger:
        out["reason"] = "no_continuation_trigger"
        return out

    if require_volume_contraction and not _volume_in_contraction(bars):
        out["reason"] = "volume_not_in_contraction"
        return out

    out["pullback"] = True
    out["direction"] = breakout["direction"]
    out["breakout_level"] = level
    out["breakout_index"] = breakout["index"]
    out["bars_since_breakout"] = breakout["bars_since"]
    out["trigger_pattern"] = trigger_name
    out["reason"] = (
        f"pullback {breakout['direction']} su livello={level:.5f} "
        f"trigger={trigger_name} bars_since_breakout={breakout['bars_since']}"
    )
    return out
