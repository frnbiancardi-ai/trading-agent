"""Indicatori tecnici avanzati per la strategia v2 (Defendi).

Tutti in Python puro, niente pandas/ta-lib.

Convenzione (come `indicators.py`): ogni serie restituita ha la stessa
lunghezza dell'input. Posizioni iniziali insufficienti per il calcolo
sono `None`.
"""

from math import sqrt

from indicators import ema, sma


def _population_std(values: list[float], mean: float) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / n
    return sqrt(var)


def bollinger_bands(
    closes: list[float],
    period: int = 20,
    k: float = 2.0,
) -> dict:
    """Bande di Bollinger su closes.

    Ritorna dict con liste della stessa lunghezza di `closes`:
    - middle: SMA(period)
    - upper:  middle + k * std
    - lower:  middle - k * std
    - bandwidth: (upper - lower) / middle * 100
    - percent_b: (close - lower) / (upper - lower)
    """
    n = len(closes)
    middle: list[float | None] = [None] * n
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    bandwidth: list[float | None] = [None] * n
    percent_b: list[float | None] = [None] * n

    if period <= 0 or n < period:
        return {
            "middle": middle, "upper": upper, "lower": lower,
            "bandwidth": bandwidth, "percent_b": percent_b,
        }

    sma_series = sma(closes, period)
    for i in range(period - 1, n):
        m = sma_series[i]
        if m is None:
            continue
        window = closes[i - period + 1:i + 1]
        std = _population_std(window, m)
        u = m + k * std
        l = m - k * std
        middle[i] = m
        upper[i] = u
        lower[i] = l
        if m != 0:
            bandwidth[i] = (u - l) / m * 100.0
        else:
            bandwidth[i] = 0.0
        if u != l:
            percent_b[i] = (closes[i] - l) / (u - l)
        else:
            percent_b[i] = 0.5

    return {
        "middle": middle, "upper": upper, "lower": lower,
        "bandwidth": bandwidth, "percent_b": percent_b,
    }


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    """MACD classico.

    macd = EMA(fast) - EMA(slow)
    signal = EMA(macd, signal)
    histogram = macd - signal
    """
    n = len(closes)
    macd_line: list[float | None] = [None] * n
    signal_line: list[float | None] = [None] * n
    histogram: list[float | None] = [None] * n

    if min(fast, slow, signal) <= 0 or n < slow:
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)

    for i in range(n):
        if ema_fast[i] is None or ema_slow[i] is None:
            continue
        macd_line[i] = ema_fast[i] - ema_slow[i]  # type: ignore[operator]

    macd_clean = [v if v is not None else 0.0 for v in macd_line]
    first_valid = next((i for i, v in enumerate(macd_line) if v is not None), None)
    if first_valid is None or n - first_valid < signal:
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    sub = macd_clean[first_valid:]
    sub_signal = ema(sub, signal)
    for j, val in enumerate(sub_signal):
        idx = first_valid + j
        if val is not None and macd_line[idx] is not None:
            signal_line[idx] = val
            histogram[idx] = macd_line[idx] - val  # type: ignore[operator]

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def vortex(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> dict:
    """Vortex Indicator.

    VM+ = |high[i] - low[i-1]|
    VM- = |low[i] - high[i-1]|
    TR  = max(high-low, |high - close[i-1]|, |low - close[i-1]|)
    VI+ = sum(VM+ ultime period) / sum(TR ultime period)
    VI- = sum(VM- ultime period) / sum(TR ultime period)
    """
    n = len(closes)
    vi_plus: list[float | None] = [None] * n
    vi_minus: list[float | None] = [None] * n
    if period <= 0 or n < period + 1:
        return {"vi_plus": vi_plus, "vi_minus": vi_minus}
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, closes devono avere stessa lunghezza")

    vm_plus = [0.0] * n
    vm_minus = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        vm_plus[i] = abs(highs[i] - lows[i - 1])
        vm_minus[i] = abs(lows[i] - highs[i - 1])
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    for i in range(period, n):
        sum_tr = sum(tr[i - period + 1:i + 1])
        if sum_tr == 0:
            continue
        vi_plus[i] = sum(vm_plus[i - period + 1:i + 1]) / sum_tr
        vi_minus[i] = sum(vm_minus[i - period + 1:i + 1]) / sum_tr

    return {"vi_plus": vi_plus, "vi_minus": vi_minus}


def vhf(closes: list[float], period: int = 28) -> list[float | None]:
    """Vertical Horizontal Filter.

    HCP = max close ultime period
    LCP = min close ultime period
    num = HCP - LCP
    den = sum(|close[i] - close[i-1]|) ultime period
    VHF = num / den

    Valori ~1 = trend forte, ~0 = mercato laterale.
    """
    n = len(closes)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period + 1:
        return out

    abs_diffs = [0.0] * n
    for i in range(1, n):
        abs_diffs[i] = abs(closes[i] - closes[i - 1])

    for i in range(period, n):
        window = closes[i - period + 1:i + 1]
        hcp = max(window)
        lcp = min(window)
        den = sum(abs_diffs[i - period + 1:i + 1])
        if den == 0:
            continue
        out[i] = (hcp - lcp) / den
    return out


def parabolic_sar(
    highs: list[float],
    lows: list[float],
    af_step: float = 0.02,
    af_max: float = 0.2,
) -> list[float | None]:
    """Parabolic SAR di Wilder.

    Convenzione: prima barra senza valore (None). Dalla seconda parte
    inizializzando il trend in base alla differenza close-vs-close.
    """
    n = len(highs)
    out: list[float | None] = [None] * n
    if n < 2 or af_step <= 0 or af_max <= 0:
        return out
    if len(lows) != n:
        raise ValueError("highs e lows devono avere stessa lunghezza")

    uptrend = highs[1] >= highs[0]
    if uptrend:
        sar = lows[0]
        ep = highs[1]
    else:
        sar = highs[0]
        ep = lows[1]
    af = af_step
    out[1] = sar

    for i in range(2, n):
        prev_sar = sar
        sar_new = prev_sar + af * (ep - prev_sar)

        if uptrend:
            sar_new = min(sar_new, lows[i - 1], lows[i - 2])
            if lows[i] < sar_new:
                uptrend = False
                sar = ep
                ep = lows[i]
                af = af_step
            else:
                sar = sar_new
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + af_step, af_max)
        else:
            sar_new = max(sar_new, highs[i - 1], highs[i - 2])
            if highs[i] > sar_new:
                uptrend = True
                sar = ep
                ep = highs[i]
                af = af_step
            else:
                sar = sar_new
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + af_step, af_max)

        out[i] = sar

    return out


def bandwidth_squeeze(
    bandwidth_series: list[float | None],
    lookback: int = 100,
    percentile: float = 0.2,
) -> bool:
    """True se l'ultimo bandwidth è nel `percentile` più basso degli ultimi
    `lookback` valori validi.
    """
    if not bandwidth_series:
        return False
    if not (0.0 < percentile < 1.0):
        return False
    valid = [v for v in bandwidth_series[-lookback:] if v is not None]
    if len(valid) < max(10, int(lookback * 0.2)):
        return False
    last = bandwidth_series[-1]
    if last is None:
        return False
    sorted_vals = sorted(valid)
    cutoff_idx = max(0, int(len(sorted_vals) * percentile) - 1)
    threshold = sorted_vals[cutoff_idx]
    return last <= threshold
