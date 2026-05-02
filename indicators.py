"""Indicatori tecnici in Python puro su array OHLC. Niente pandas/ta-lib.

Convenzione: ogni serie restituita ha la stessa lunghezza dell'input.
Le posizioni iniziali insufficienti per il calcolo sono `None`.
"""


def sma(values: list[float], period: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    cum = sum(values[:period])
    out[period - 1] = cum / period
    for i in range(period, n):
        cum += values[i] - values[i - period]
        out[i] = cum / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    alpha = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, n):
        prev = out[i - 1]
        out[i] = alpha * values[i] + (1.0 - alpha) * prev  # type: ignore[operator]
    return out


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


def _wilder_rsi(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


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


def _last_valid(series: list[float | None]) -> float | None:
    for v in reversed(series):
        if v is not None:
            return v
    return None


def compute_all(ohlc: list[dict]) -> dict:
    """Estrae closes/highs/lows dal list[dict] e ritorna l'ultimo valore valido
    di sma_20, ema_50, rsi_14, atr_14."""
    closes = [b["close"] for b in ohlc]
    highs = [b["high"] for b in ohlc]
    lows = [b["low"] for b in ohlc]
    return {
        "sma_20": _last_valid(sma(closes, 20)),
        "ema_50": _last_valid(ema(closes, 50)),
        "rsi_14": _last_valid(rsi(closes, 14)),
        "atr_14": _last_valid(atr(highs, lows, closes, 14)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helper analisi avanzata (fase 14)
# ─────────────────────────────────────────────────────────────────────────────


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


def avg_volume(bars: list[dict], period: int = 20) -> float:
    """Media tick_volume sulle ultime `period` barre. 0.0 se dati assenti."""
    if not bars or period <= 0:
        return 0.0
    sub = bars[-period:]
    vols = [b.get("tick_volume", b.get("volume", 0)) or 0 for b in sub]
    if not vols:
        return 0.0
    return sum(vols) / len(vols)


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


def calculate_risk_reward(entry: float, sl: float, tp: float) -> float:
    """Rapporto reward/risk. 0.0 se SL == entry (rischio nullo non valido)."""
    risk = abs(entry - sl)
    if risk == 0:
        return 0.0
    reward = abs(tp - entry)
    return round(reward / risk, 4)


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

