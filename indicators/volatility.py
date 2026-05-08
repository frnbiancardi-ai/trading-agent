"""Indicatori di volatilità: ATR (Wave 0), Bollinger Bands + squeeze, Keltner (Wave 1).

Wave 1 aggiunge:
- `bollinger_bands(closes, length=20, std=2.0, squeeze_lookback_bars=180, squeeze_pct=25)`
  → BB classiche + bandwidth (BBW) + squeeze percentile (BBW < N-esimo percentile
  della finestra trailing) + squeeze_ttm (Carter: BB interamente dentro Keltner).
- `keltner(highs, lows, closes, length=20, scalar=2.0)` → canale EMA ± scalar·ATR.

Convenzioni (D-04..D-06):
- dataclass-of-lists per output multi-serie (BollingerResult, KeltnerResult);
- `list[T | None]` uniforme con warmup → None;
- co-location nello stesso file di dominio (volatility);
- nessun import di pandas_ta a runtime (verificato da test purity).
"""
from __future__ import annotations

from dataclasses import dataclass

from indicators.trend import ema, sma


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


@dataclass
class BollingerResult:
    """Output Bollinger Bands con squeeze percentile e squeeze TTM (Carter)."""

    upper: list[float | None]
    middle: list[float | None]
    lower: list[float | None]
    bbw: list[float | None]
    squeeze: list[bool | None]
    squeeze_ttm: list[bool | None]


@dataclass
class KeltnerResult:
    """Output canale di Keltner: middle = EMA(length), bands = middle ± scalar·ATR."""

    upper: list[float | None]
    middle: list[float | None]
    lower: list[float | None]


def keltner(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    length: int = 20,
    scalar: float = 2.0,
) -> KeltnerResult:
    """Canale di Keltner: middle = EMA(length, close); band = EMA(length, true_range).

    Parity con pandas-ta `kc(length=20, scalar=2, mamode='ema')` che usa EMA del true
    range (NON ATR di Wilder). Il true range alla bar 0 è `high[0] - low[0]` (non c'è
    chiusura precedente). Upper/lower = middle ± scalar·EMA(TR).

    Output dataclass `KeltnerResult` con tre liste di lunghezza len(closes), warmup→None.
    """
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows, closes devono avere la stessa lunghezza")
    if length <= 0:
        raise ValueError(f"length deve essere > 0, ricevuto {length}")
    n = len(closes)
    # True range con convenzione pandas-ta: bar 0 → high - low; bar i>0 → max delle
    # tre forme classiche (high-low, |high-prev_close|, |low-prev_close|).
    tr: list[float] = [highs[0] - lows[0]] if n > 0 else []
    for i in range(1, n):
        tr.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    middle = ema(closes, length)
    band = ema(tr, length)
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    for i in range(n):
        m = middle[i]
        b = band[i]
        if m is None or b is None:
            continue
        upper[i] = m + scalar * b
        lower[i] = m - scalar * b
    return KeltnerResult(upper=upper, middle=middle, lower=lower)


def bollinger_bands(
    closes: list[float],
    length: int = 20,
    std: float = 2.0,
    squeeze_lookback_bars: int = 180,
    squeeze_pct: float = 25.0,
    ddof: int = 1,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    keltner_length: int = 20,
    keltner_scalar: float = 2.0,
) -> BollingerResult:
    """Bande di Bollinger (length, std) + squeeze percentile + squeeze TTM (BB-inside-Keltner).

    Standard deviation: `ddof=1` (campionaria) di default per parity con pandas-ta
    `bbands` (che usa pandas `.std(ddof=1)` quando talib non è installato). `ddof=0`
    fornisce la varianza popolazionale (talib-style). Divisore = length - ddof.

    Squeeze percentile (primario): `bbw[i] < quantile_{squeeze_pct}` calcolato sulla
    finestra trailing di `squeeze_lookback_bars` valori BBW (richiesti tutti validi).
    Default 180 ≈ 6 mesi di H1 di sessione utile (A4: 25-esimo percentile, tunable).

    Squeeze TTM (secondario, Carter): `squeeze_ttm[i] = (bb.upper < kc.upper) and
    (bb.lower > kc.lower)` — BB interamente dentro il canale di Keltner. Richiede
    highs/lows; se assenti, `squeeze_ttm` è una serie di soli None.

    `[D-07: percentile squeeze + Carter TTM secondary; A4: 25-pct cut-off configurabile]`
    """
    if length <= 0:
        raise ValueError(f"length deve essere > 0, ricevuto {length}")
    if not (0 <= ddof < length):
        raise ValueError(f"ddof deve essere in [0, length), ricevuto {ddof}")
    if squeeze_lookback_bars <= 0:
        raise ValueError(
            f"squeeze_lookback_bars deve essere > 0, ricevuto {squeeze_lookback_bars}"
        )
    if not (0.0 < squeeze_pct < 100.0):
        raise ValueError(f"squeeze_pct deve essere in (0, 100), ricevuto {squeeze_pct}")

    n = len(closes)
    upper: list[float | None] = [None] * n
    middle: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    bbw: list[float | None] = [None] * n
    squeeze: list[bool | None] = [None] * n
    squeeze_ttm: list[bool | None] = [None] * n

    # Middle = SMA(length); std deviation con divisore (length - ddof) via somma
    # rolling cumulativa di valori e quadrati. Default ddof=1 → parity con pandas-ta.
    divisor = length - ddof
    if n >= length:
        sq = [c * c for c in closes]
        cum = sum(closes[:length])
        cum_sq = sum(sq[:length])
        for i in range(length - 1, n):
            if i > length - 1:
                cum += closes[i] - closes[i - length]
                cum_sq += sq[i] - sq[i - length]
            mean = cum / length
            # Sample/population var via formula spostata: somma_sq_residui / divisor.
            # Forma equivalente: (sum_sq - length·mean²) / divisor. Clamp a 0 per
            # evitare drift numerico negativo da catastrophic cancellation.
            ssr = cum_sq - length * mean * mean
            var = max(ssr / divisor, 0.0)
            sd = var ** 0.5
            middle[i] = mean
            upper[i] = mean + std * sd
            lower[i] = mean - std * sd
            if mean != 0:
                bbw[i] = (upper[i] - lower[i]) / mean  # type: ignore[operator]
            else:
                bbw[i] = None

    # Percentile-squeeze: BBW < squeeze_pct-esimo percentile della trailing window.
    # Richiede `squeeze_lookback_bars` valori validi nella finestra (tutti non-None).
    for i in range(n):
        if bbw[i] is None:
            continue
        if i < (length - 1) + (squeeze_lookback_bars - 1):
            continue
        window_vals = [
            v for v in bbw[i - squeeze_lookback_bars + 1 : i + 1] if v is not None
        ]
        if len(window_vals) < squeeze_lookback_bars:
            continue
        sorted_vals = sorted(window_vals)
        # Nearest-rank percentile (no interpolazione): cutoff = sorted[ceil(p/100·N) - 1].
        cutoff_idx = max(0, int(len(sorted_vals) * squeeze_pct / 100.0) - 1)
        cutoff = sorted_vals[cutoff_idx]
        squeeze[i] = bbw[i] < cutoff  # type: ignore[operator]

    # Squeeze TTM (Carter): BB interamente dentro Keltner. Richiede highs/lows.
    if highs is not None and lows is not None:
        kc = keltner(highs, lows, closes, length=keltner_length, scalar=keltner_scalar)
        for i in range(n):
            if upper[i] is None or kc.upper[i] is None:
                continue
            squeeze_ttm[i] = (upper[i] < kc.upper[i]) and (lower[i] > kc.lower[i])  # type: ignore[operator]

    return BollingerResult(
        upper=upper,
        middle=middle,
        lower=lower,
        bbw=bbw,
        squeeze=squeeze,
        squeeze_ttm=squeeze_ttm,
    )
