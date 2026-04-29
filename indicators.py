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
