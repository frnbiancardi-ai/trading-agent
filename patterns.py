"""Riconoscimento pattern candlestick base in Python puro.

Bar dict atteso: {'open': float, 'high': float, 'low': float, 'close': float, ...}
Tutte le funzioni gestiscono input degenere (open == close, range nullo) senza crash.
"""


def _body(bar: dict) -> float:
    return abs(bar["close"] - bar["open"])


def _range(bar: dict) -> float:
    return bar["high"] - bar["low"]


def _upper_shadow(bar: dict) -> float:
    return bar["high"] - max(bar["open"], bar["close"])


def _lower_shadow(bar: dict) -> float:
    return min(bar["open"], bar["close"]) - bar["low"]


def _is_bullish(bar: dict) -> bool:
    return bar["close"] > bar["open"]


def _is_bearish(bar: dict) -> bool:
    return bar["close"] < bar["open"]


def is_hammer(bar: dict) -> bool:
    """Hammer: long lower shadow (>=2x body), upper shadow <=20% range, body <=40% range."""
    rng = _range(bar)
    body = _body(bar)
    if rng <= 0 or body <= 0:
        return False
    lower = _lower_shadow(bar)
    upper = _upper_shadow(bar)
    return lower >= 2.0 * body and upper <= 0.2 * rng and body <= 0.4 * rng


def is_inverted_hammer(bar: dict) -> bool:
    """Inverted hammer: long upper shadow (>=2x body), lower shadow <=20% range, body <=40% range."""
    rng = _range(bar)
    body = _body(bar)
    if rng <= 0 or body <= 0:
        return False
    lower = _lower_shadow(bar)
    upper = _upper_shadow(bar)
    return upper >= 2.0 * body and lower <= 0.2 * rng and body <= 0.4 * rng


def is_engulfing(prev_bar: dict, current_bar: dict, direction: str) -> bool:
    """Engulfing: corpo corrente ingloba completamente corpo precedente.

    direction = 'bullish': prev bearish, curr bullish, curr.open <= prev.close, curr.close >= prev.open
    direction = 'bearish': prev bullish, curr bearish, curr.open >= prev.close, curr.close <= prev.open
    """
    direction = direction.lower()
    if _body(prev_bar) <= 0 or _body(current_bar) <= 0:
        return False

    if direction == "bullish":
        if not (_is_bearish(prev_bar) and _is_bullish(current_bar)):
            return False
        return current_bar["open"] <= prev_bar["close"] and current_bar["close"] >= prev_bar["open"]

    if direction == "bearish":
        if not (_is_bullish(prev_bar) and _is_bearish(current_bar)):
            return False
        return current_bar["open"] >= prev_bar["close"] and current_bar["close"] <= prev_bar["open"]

    return False


def is_doji(bar: dict, tolerance: float = 0.1) -> bool:
    """Doji: |close - open| <= tolerance * range."""
    rng = _range(bar)
    if rng <= 0:
        return False
    return _body(bar) <= tolerance * rng


def is_pin_bar(bar: dict, direction: str) -> bool:
    """Pin bar: long wick opposto alla direzione, body piccolo (<=1/3 range).

    direction = 'bullish': lower wick lungo (>= 2/3 range), close > open
    direction = 'bearish': upper wick lungo (>= 2/3 range), close < open
    """
    direction = direction.lower()
    rng = _range(bar)
    body = _body(bar)
    if rng <= 0:
        return False
    if body > rng / 3.0:
        return False

    if direction == "bullish":
        return _lower_shadow(bar) >= 2.0 / 3.0 * rng and _is_bullish(bar)
    if direction == "bearish":
        return _upper_shadow(bar) >= 2.0 / 3.0 * rng and _is_bearish(bar)
    return False


def scan_patterns(bars: list[dict], last_n: int = 5) -> list[dict]:
    """Scansiona ultime `last_n` candele e ritorna pattern riconosciuti.

    Each entry: {'pattern': str, 'bar_index': int (relativo a fine lista, -1 = ultima),
                 'direction': 'bullish'|'bearish'|'neutral'}
    """
    if not bars:
        return []
    n = len(bars)
    start = max(0, n - last_n)
    out: list[dict] = []
    for i in range(start, n):
        bar = bars[i]
        rel = i - n  # -1, -2, ...
        if is_hammer(bar):
            out.append({"pattern": "hammer", "bar_index": rel, "direction": "bullish"})
        if is_inverted_hammer(bar):
            out.append({"pattern": "inverted_hammer", "bar_index": rel, "direction": "bullish"})
        if is_doji(bar):
            out.append({"pattern": "doji", "bar_index": rel, "direction": "neutral"})
        if is_pin_bar(bar, "bullish"):
            out.append({"pattern": "pin_bar", "bar_index": rel, "direction": "bullish"})
        if is_pin_bar(bar, "bearish"):
            out.append({"pattern": "pin_bar", "bar_index": rel, "direction": "bearish"})
        if i > 0:
            prev = bars[i - 1]
            if is_engulfing(prev, bar, "bullish"):
                out.append({"pattern": "engulfing", "bar_index": rel, "direction": "bullish"})
            if is_engulfing(prev, bar, "bearish"):
                out.append({"pattern": "engulfing", "bar_index": rel, "direction": "bearish"})
    return out
