"""Aggregatori snapshot.

`compute_all` (Wave 0) — 4-key dict bit-for-bit identico al legacy. Backward-compat
hard-lock: NON modificare. Le 4 callsite (claude_agent.py:12, mcp_server.py:28,
scanner.py:10, strategy.py:11) dipendono da questa shape esatta.

`compute_all_extended` (Wave 3 — INDIC-14 plan) — snapshot 14-indicator per backtest
e Phase 4 strategy refactor. Include i 4 valori legacy + i 30+ valori dei 13
indicatori Phase 2 (Bollinger, Keltner, ADX, MACD, Stoch, Donchian, Pivots,
Fibonacci, VWAP, NR/CS, Hurst, Volatility regime). MTF align (INDIC-13) e
escluso perche richiede streams multi-TF separati: Phase 4 lo invochera a parte.
"""
from __future__ import annotations

from indicators._helpers import _last_valid
from indicators.bars import closing_score, narrow_range
from indicators.hurst import hurst_rs
from indicators.momentum import adx, macd, rsi, stochastic
from indicators.structure import donchian, fibonacci_retracements, pivots
from indicators.trend import ema, sma
from indicators.volatility import (
    atr,
    bollinger_bands,
    keltner,
    volatility_regime,
)
from indicators.volume import avg_volume, vwap_intraday


def compute_all(ohlc: list[dict]) -> dict:
    """Estrae closes/highs/lows dal list[dict] e ritorna l'ultimo valore valido
    di sma_20, ema_50, rsi_14, atr_14.

    HARD-LOCK shape (D-03): le chiavi devono restare ESATTAMENTE
    {"sma_20", "ema_50", "rsi_14", "atr_14"}. Modificare significherebbe rompere
    `claude_agent.py:12` + `mcp_server.py:28`.
    """
    closes = [b["close"] for b in ohlc]
    highs = [b["high"] for b in ohlc]
    lows = [b["low"] for b in ohlc]
    return {
        "sma_20": _last_valid(sma(closes, 20)),
        "ema_50": _last_valid(ema(closes, 50)),
        "rsi_14": _last_valid(rsi(closes, 14)),
        "atr_14": _last_valid(atr(highs, lows, closes, 14)),
    }


def compute_all_extended(bars: list[dict], regime_cfg: dict | None = None) -> dict:
    """Snapshot 14-indicator per backtest + Phase 4 strategy.

    Ritorna un dict con tutte le chiavi di `compute_all` (4 valori legacy) PIU
    i valori last-valid di Bollinger Bands, Keltner, ADX, MACD, Stochastic,
    Donchian, Pivots (classico + Camarilla h3/l3), Fibonacci snapshot, VWAP
    intraday, avg_volume(20), Narrow Range (nr4/nr7/boomer), Closing Score,
    Hurst R/S, Volatility regime (se `regime_cfg` fornito).

    Note:
    - `regime_cfg=None` → `regime_state` e `regime_atr_pct` sono entrambi None.
    - MTF align (INDIC-13) NON e incluso: richiede stream multi-TF separati
      (H4/H1/M15) che non si possono dedurre da una sola list[dict]. Phase 4
      strategy chiamera `align()` direttamente con i bucket multi-TF.
    - Su input vuoto ritorna le 4 chiavi legacy + flag `extended_empty=True`.
    """
    if not bars:
        return {**compute_all(bars), "extended_empty": True}

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]

    classic = compute_all(bars)
    bb = bollinger_bands(
        closes,
        length=20,
        std=2.0,
        highs=highs,
        lows=lows,
        keltner_length=20,
        keltner_scalar=2.0,
    )
    kc = keltner(highs, lows, closes, length=20, scalar=2.0)
    adx_r = adx(highs, lows, closes, period=14)
    macd_r = macd(closes, fast=12, slow=26, signal=9)
    stoch_r = stochastic(highs, lows, closes, k_period=14, d_period=3, smooth_k=3)
    donch_r = donchian(highs, lows, length=20)
    pivot_r = pivots(bars, anchor="daily")
    fib_r = fibonacci_retracements(bars, lookback=100, window=2)
    vwap_r = vwap_intraday(bars)
    nr_r = narrow_range(bars)
    cs_r = closing_score(bars)
    hurst_r = hurst_rs(closes, window=100)
    regime_r = volatility_regime(bars, regime_cfg) if regime_cfg is not None else None

    return {
        **classic,
        # Bollinger
        "bb_upper": _last_valid(bb.upper),
        "bb_middle": _last_valid(bb.middle),
        "bb_lower": _last_valid(bb.lower),
        "bb_bbw": _last_valid(bb.bbw),
        "bb_squeeze": _last_valid(bb.squeeze),
        # Keltner
        "kc_upper": _last_valid(kc.upper),
        "kc_lower": _last_valid(kc.lower),
        # ADX
        "adx_14": _last_valid(adx_r.adx),
        "plus_di_14": _last_valid(adx_r.plus_di),
        "minus_di_14": _last_valid(adx_r.minus_di),
        # MACD
        "macd": _last_valid(macd_r.macd),
        "macd_signal": _last_valid(macd_r.signal),
        "macd_hist": _last_valid(macd_r.histogram),
        # Stochastic
        "stoch_k": _last_valid(stoch_r.k),
        "stoch_d": _last_valid(stoch_r.d),
        # Donchian
        "donch_upper": _last_valid(donch_r.upper),
        "donch_lower": _last_valid(donch_r.lower),
        # Pivots (P + Camarilla h3/l3 chiave per setup A breakout)
        "pivot_p": _last_valid(pivot_r.p),
        "pivot_camarilla_h3": _last_valid(pivot_r.camarilla.get("h3", [])),
        "pivot_camarilla_l3": _last_valid(pivot_r.camarilla.get("l3", [])),
        # Fibonacci snapshot (livelli + direction)
        "fib_0382": fib_r.levels.get("0.382"),
        "fib_0500": fib_r.levels.get("0.5"),
        "fib_0618": fib_r.levels.get("0.618"),
        "fib_direction": fib_r.direction,
        # VWAP intraday + volume context
        "vwap": _last_valid(vwap_r.vwap),
        "avg_volume_20": avg_volume(bars, 20),
        # Narrow Range + Closing Score
        "nr4": _last_valid(nr_r.nr4),
        "nr7": _last_valid(nr_r.nr7),
        "boomer": _last_valid(nr_r.boomer),
        "closing_score": _last_valid(cs_r.score),
        # Hurst
        "hurst": _last_valid(hurst_r.hurst),
        # Volatility regime (INDIC-14)
        "regime_state": _last_valid(regime_r.state) if regime_r else None,
        "regime_atr_pct": _last_valid(regime_r.atr_percentile) if regime_r else None,
    }
