"""Indicatori di momentum: RSI, divergenza prezzo/RSI, ADX/DMI, MACD, Stochastic.

Wave 0 = lift-and-shift verbatim (rsi, check_rsi_divergence).
Wave 1 plan 03 = aggiunti ADX/DMI 14, MACD 12/26/9, Stochastic 14/3/3 con
dataclass `<Indicator>Result` co-locati. Tutti parity 1e-6 vs pandas-ta
(`mamode='rma'` per ADX, EMA standard per MACD, SMA per smoothing Stoch).

Convenzione: serie di output stessa lunghezza dell'input, warmup → None.
Niente import di pandas/pandas_ta a runtime (D-07).
"""
from __future__ import annotations

from dataclasses import dataclass

from indicators._helpers import _wilder_rsi, _wilder_smooth
from indicators.trend import ema, sma


# --------------------------------------------------------------------------- #
# RSI (Wave 0)                                                                #
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Wave 1 plan 03 — Dataclasses                                                #
# --------------------------------------------------------------------------- #
@dataclass
class ADXResult:
    """Risultato ADX/DMI: ADX (trend strength) + DI+ / DI- (direzione).

    Tutte le serie hanno la stessa lunghezza dell'input. Le posizioni di
    warmup sono `None`. Per ADX i primi `2*period` valori sono mascherati
    a `None` (transient di doppio Wilder smoothing).
    """
    adx: list[float | None]
    plus_di: list[float | None]
    minus_di: list[float | None]


@dataclass
class MACDResult:
    """Risultato MACD: linea (EMA fast - EMA slow), signal (EMA della linea), istogramma."""
    macd: list[float | None]
    signal: list[float | None]
    histogram: list[float | None]


@dataclass
class StochasticResult:
    """Risultato Stochastic Oscillator: %K (smussato) e %D (SMA di %K)."""
    k: list[float | None]
    d: list[float | None]


# --------------------------------------------------------------------------- #
# ADX/DMI 14 — Wilder/RMA smoothing matching pandas-ta `mamode='rma'`         #
# --------------------------------------------------------------------------- #
def _rma_first_valid_seed(
    values: list[float | None], period: int
) -> list[float | None]:
    """RMA pandas-ta-style: alpha=1/period, seed = primo valore non-None.

    Differente da `_wilder_smooth` (Wave 0) che usa SMA-seed sui primi `period`
    valori. Necessario per parity con `pandas_ta.adx` che chiama
    `pos.ewm(alpha=1/length, adjust=False).mean()` su una serie con NaN al bar 0:
    EWM senza seed SMA, parte dal primo non-NaN.
    """
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n == 0:
        return out
    alpha = 1.0 / period
    one_minus_alpha = 1.0 - alpha
    prev: float | None = None
    for i, v in enumerate(values):
        if prev is None:
            if v is not None:
                prev = v
                out[i] = prev
            # else: rimani None
        else:
            if v is None:
                out[i] = prev  # propaga lo stato (analogo a pandas ewm su NaN)
            else:
                prev = one_minus_alpha * prev + alpha * v
                out[i] = prev
    return out


def _atr_pta_compat(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int,
) -> list[float | None]:
    """ATR formula esatta di pandas-ta (`atr(prenan=True, presma=True, mamode='rma')`).

    1. true_range con `prenan=True, drift=1`: tr[0] = NaN, tr[i>0] = max(h-l, |h-pc|, |l-pc|).
    2. presma=True: tr[0..period-2] = NaN, tr[period-1] = mean(tr[0:period]) skipna
       = sum(tr[1..period-1]) / (period-1). Posizione: indice `period-1`.
    3. atr = ma('rma', tr, length=period) → ewm(alpha=1/period, adjust=False).mean()
       sulla serie modificata: parte da `period-1` come seed, poi recursive.
    """
    n = len(closes)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    # tr[0] = NaN-equivalent; tr[i>=1] standard.
    tr_full: list[float | None] = [None] * n
    for i in range(1, n):
        tr_full[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    # presma seed all'indice period-1: media skipna di tr[0:period] = somma di
    # tr[1..period-1] divisa per (period-1).
    seed_vals = [v for v in tr_full[0:period] if v is not None]
    if len(seed_vals) == 0:
        return out
    seed = sum(seed_vals) / len(seed_vals)
    # Costruisci la serie post-presma: None ovunque eccetto tr_modified[period-1]=seed
    # e tr[i] nativo per i >= period.
    tr_modified: list[float | None] = [None] * n
    tr_modified[period - 1] = seed
    for i in range(period, n):
        tr_modified[i] = tr_full[i]
    # RMA con seed = primo non-None (= seed presma, all'indice period-1).
    return _rma_first_valid_seed(tr_modified, period)


def adx(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> ADXResult:
    """ADX/DMI 14 — parity 1e-6 con `pta.adx(length=14, mamode='rma')`.

    Replica esattamente la sequenza pandas-ta (`pandas_ta/trend/adx.py`):

      - up_move[i]   = high[i] - high[i-1]   (NaN al bar 0)
      - down_move[i] = low[i-1] - low[i]     (NaN al bar 0)
      - pos[i] = up_move[i] se (up>dn and up>0) else 0  (NaN al bar 0)
      - neg[i] = down_move[i] se (dn>up and dn>0) else 0 (NaN al bar 0)
      - atr_ = atr(prenan=True, presma=True): seed presma all'indice period-1
      - dmp = 100 * RMA(pos, period) / atr_     (RMA = ewm senza seed SMA)
      - dmn = 100 * RMA(neg, period) / atr_
      - dx  = 100 * |dmp - dmn| / (dmp + dmn)
      - adx = RMA(dx, period)

    NOTE Wave 0 / RESEARCH Example 1: il pattern "doppio Wilder smooth con
    `_wilder_smooth` (SMA-seed) e mask 2*period" NON matcha pandas-ta perche'
    pandas-ta usa RMA con first-valid-seed (non SMA-seed) e atr con presma a
    posizione period-1. Questa implementazione segue la sorgente vera di
    pandas-ta (Rule 1 bug-fix vs RESEARCH Example 1).
    """
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows, closes devono avere la stessa lunghezza")

    n = len(closes)
    if n == 0 or period <= 0:
        return ADXResult(adx=[None] * n, plus_di=[None] * n, minus_di=[None] * n)

    # pos / neg con NaN-equivalent al bar 0 (pandas-ta: up=high.diff(1) → NaN al bar 0).
    pos: list[float | None] = [None] * n
    neg: list[float | None] = [None] * n
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        pos[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
        neg[i] = down_move if (down_move > up_move and down_move > 0) else 0.0

    # atr_ = ATR pandas-ta con prenan=True, presma=True, mamode='rma'
    atr_ = _atr_pta_compat(highs, lows, closes, period)

    # dmp = 100 * RMA(pos)/atr_  ;  dmn = 100 * RMA(neg)/atr_
    rma_pos = _rma_first_valid_seed(pos, period)
    rma_neg = _rma_first_valid_seed(neg, period)
    dmp: list[float | None] = [None] * n
    dmn: list[float | None] = [None] * n
    for i in range(n):
        a = atr_[i]
        if a is None or a == 0:
            continue
        rp = rma_pos[i]
        rn = rma_neg[i]
        if rp is not None:
            dmp[i] = 100.0 * rp / a
        if rn is not None:
            dmn[i] = 100.0 * rn / a

    # dx = 100 * |dmp - dmn| / (dmp + dmn) ; dove uno e' None -> dx None.
    dx: list[float | None] = [None] * n
    for i in range(n):
        p = dmp[i]
        m = dmn[i]
        if p is None or m is None:
            continue
        denom = p + m
        if denom <= 0:
            dx[i] = 0.0
        else:
            dx[i] = 100.0 * abs(p - m) / denom

    # adx = RMA(dx, period) — first-valid-seed, propaga lo stato sui None interni.
    adx_vals = _rma_first_valid_seed(dx, period)

    return ADXResult(adx=adx_vals, plus_di=dmp, minus_di=dmn)


# --------------------------------------------------------------------------- #
# MACD 12/26/9 — EMA standard (alpha=2/(N+1)), seed = SMA dei primi N valori #
# --------------------------------------------------------------------------- #
def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> MACDResult:
    """MACD 12/26/9.

    macd_line[i] = ema(closes, fast)[i] - ema(closes, slow)[i]
    signal_line  = ema della macd_line densa (senza None), riallineata
                   con offset = primo indice macd_line non-None.
    histogram[i] = macd_line[i] - signal_line[i]
    """
    n = len(closes)
    if n == 0:
        return MACDResult(macd=[], signal=[], histogram=[])

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)

    macd_line: list[float | None] = [None] * n
    for i in range(n):
        f = ema_fast[i]
        s = ema_slow[i]
        if f is not None and s is not None:
            macd_line[i] = f - s

    # Estrai prefisso denso (dal primo indice non-None in poi tutti i valori
    # sono validi: ema_slow comanda lo start, da li' in poi entrambi presenti).
    first_valid = next((i for i, v in enumerate(macd_line) if v is not None), None)
    signal_line: list[float | None] = [None] * n
    if first_valid is not None:
        dense = [v for v in macd_line[first_valid:] if v is not None]
        # Tutti i valori da first_valid in poi sono garantiti non-None
        # (ema_fast warmup << ema_slow warmup).
        sig_dense = ema(dense, signal)
        for j, v in enumerate(sig_dense):
            signal_line[first_valid + j] = v

    histogram: list[float | None] = [None] * n
    for i in range(n):
        m = macd_line[i]
        s = signal_line[i]
        if m is not None and s is not None:
            histogram[i] = m - s

    return MACDResult(macd=macd_line, signal=signal_line, histogram=histogram)


# --------------------------------------------------------------------------- #
# Stochastic Oscillator 14/3/3                                                #
# --------------------------------------------------------------------------- #
def stochastic(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    k_period: int = 14,
    d_period: int = 3,
    smooth_k: int = 3,
) -> StochasticResult:
    """Stochastic Oscillator 14/3/3.

    raw_k[i]  = 100 * (close[i] - LL) / (HH - LL)  con LL/HH su finestra k_period
    smoothed_k = SMA di raw_k su smooth_k bar
    %D         = SMA di smoothed_k su d_period bar

    Quando HH == LL (range nullo nella finestra), raw_k = None.
    """
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows, closes devono avere la stessa lunghezza")

    n = len(closes)
    if n == 0 or k_period <= 0 or smooth_k <= 0 or d_period <= 0:
        return StochasticResult(k=[None] * n, d=[None] * n)

    raw_k: list[float | None] = [None] * n
    for i in range(k_period - 1, n):
        window_h = highs[i - k_period + 1 : i + 1]
        window_l = lows[i - k_period + 1 : i + 1]
        hh = max(window_h)
        ll = min(window_l)
        rng = hh - ll
        if rng <= 0:
            raw_k[i] = None
        else:
            raw_k[i] = 100.0 * (closes[i] - ll) / rng

    # Smooth raw_k con SMA(smooth_k) sul prefisso denso.
    first_raw = next((i for i, v in enumerate(raw_k) if v is not None), None)
    smoothed_k: list[float | None] = [None] * n
    if first_raw is not None:
        # Costruisci prefisso denso a partire da first_raw; se incontri un None
        # interno (range nullo), tronca: la SMA non puo' continuare con buchi.
        # In pratica su dati reali (FX H1) i None interni sono rarissimi.
        dense_k: list[float] = []
        for v in raw_k[first_raw:]:
            if v is None:
                # Per robustezza spezza la sequenza: smoothed_k restera' None
                # da qui in poi (caso patologico: range nullo dopo un valido).
                break
            dense_k.append(v)
        if len(dense_k) >= smooth_k:
            sm_dense = sma(dense_k, smooth_k)
            for j, v in enumerate(sm_dense):
                smoothed_k[first_raw + j] = v

    # %D = SMA di smoothed_k su d_period
    first_sm = next((i for i, v in enumerate(smoothed_k) if v is not None), None)
    d: list[float | None] = [None] * n
    if first_sm is not None:
        dense_sm: list[float] = []
        for v in smoothed_k[first_sm:]:
            if v is None:
                break
            dense_sm.append(v)
        if len(dense_sm) >= d_period:
            d_dense = sma(dense_sm, d_period)
            for j, v in enumerate(d_dense):
                d[first_sm + j] = v

    return StochasticResult(k=smoothed_k, d=d)
