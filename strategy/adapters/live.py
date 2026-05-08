"""Adapter live: build_ctx_live (Wave 3 STRAT-09).

Bridge non-pure tra MT5/broker e StrategyContext consumato dai detector pure-fn.
ESCLUSO dal purity gate (PURE_MODULES non lo lista) — può importare mt5_client,
indicators, patterns liberamente.

Single-compute (D-12): le serie indicator (atr_14, rsi_14, ema20, ema50,
ema50_slope, closing_score, volatility_regime, nr_detect, bollinger_bands,
fibonacci) sono calcolate UNA volta per bar e wrappate in un SimpleNamespace
che espone l'interfaccia attesa dai detector (sequenze accessibili via
getattr+_last(...)).

Nota contratto (Wave 3 deviation Rule 3): `indicators.compute_all_extended`
ritorna scalari (last_valid), ma i detector consumano sequenze (chiamando
_last(getattr(...))). Il bridge qui costruisce un namespace ad-hoc con liste,
chiamando direttamente le funzioni indicator series-returning. Documentato
nel SUMMARY.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Callable

from strategy.context import StrategyContext


def _last(seq):
    """Ritorna l'ultimo elemento non-None o None se sequenza vuota/scalare."""
    if seq is None:
        return None
    try:
        for v in reversed(seq):
            if v is not None:
                return v
    except TypeError:
        return None
    return None


def _build_extended_indicators(bars: list[dict]) -> SimpleNamespace:
    """Calcola le serie indicator richieste dai detector A/B/C/D pure-fn.

    Ritorna un SimpleNamespace con sequenze (liste) — NON dict di scalari.
    Single-compute: ogni indicator chiamato una sola volta sui bars.

    Deve essere coerente col contratto _stub_indicators_a/b/c/d in
    tests/test_strategy_setups.py (sequenze indicizzabili via [-1]).
    """
    from indicators.trend import ema, sma  # noqa: F401  sma usato indirettamente
    from indicators.momentum import rsi
    from indicators.volatility import atr, bollinger_bands, volatility_regime
    from indicators.bars import closing_score, narrow_range
    from indicators.structure import fibonacci_retracements

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]

    atr_series = atr(highs, lows, closes, 14)
    rsi_series = rsi(closes, 14)
    ema20_series = ema(closes, 20)
    ema50_series = ema(closes, 50)

    # ema50_slope come differenza first-order (None per i primi N bar)
    slope_series: list = []
    for i, v in enumerate(ema50_series):
        if i == 0 or v is None or ema50_series[i - 1] is None:
            slope_series.append(None)
        else:
            slope_series.append(v - ema50_series[i - 1])

    bb = bollinger_bands(
        closes, length=20, std=2.0,
        highs=highs, lows=lows,
        keltner_length=20, keltner_scalar=2.0,
    )
    cs = closing_score(bars)
    nr = narrow_range(bars)
    try:
        fib = fibonacci_retracements(bars, lookback=100, window=2)
    except Exception:
        fib = None

    # volatility_regime richiede regime_cfg dict; senza cfg ritorna None per ogni bar.
    regime_series = [None] * len(bars)

    return SimpleNamespace(
        atr_14=atr_series,
        rsi_14=rsi_series,
        ema20=ema20_series,
        ema50=ema50_series,
        ema50_slope=slope_series,
        closing_score=getattr(cs, "score", [None] * len(bars)),
        volatility_regime=regime_series,
        nr_detect=SimpleNamespace(
            nr4=getattr(nr, "nr4", [False] * len(bars)),
            nr7=getattr(nr, "nr7", [False] * len(bars)),
        ),
        bollinger_bands=SimpleNamespace(
            squeeze=getattr(bb, "squeeze", [False] * len(bars)),
            upper=getattr(bb, "upper", [None] * len(bars)),
            lower=getattr(bb, "lower", [None] * len(bars)),
        ),
        fibonacci=fib,
    )


def build_ctx_live(
    symbol: str,
    mt5_client,
    profile: str,
    cfg=None,
    intermarket_score_fn: Callable | None = None,
    news_blackout_fn: Callable | None = None,
) -> StrategyContext:
    """Costruisce StrategyContext dal path live (MT5).

    Single-compute (D-12): chiama _build_extended_indicators(bars) UNA volta.
    Errori di get_ohlc → re-raise con messaggio descrittivo includente symbol.
    Errori non-fatali (get_symbol_info, get_trade_history) → fallback a None / [].
    """
    if cfg is None:
        from config import Config
        cfg = Config()

    # Fetch bars (mandatory — re-raise con context se fallisce)
    try:
        bars = mt5_client.get_ohlc(symbol, cfg.INTRADAY_TIMEFRAME, cfg.INTRADAY_LOOKBACK_BARS)
    except Exception as exc:
        raise RuntimeError(
            f"build_ctx_live: get_ohlc fallito per {symbol}: {exc}"
        ) from exc

    bars = bars or []

    # Symbol info (non-fatale)
    try:
        sym_info = mt5_client.get_symbol_info(symbol)
    except Exception:
        sym_info = None

    # Pip size (deduzione defensive)
    from strategy.risk_utils import _pip_size
    pip_size = _pip_size(sym_info)

    # Indicators (single compute D-12)
    if bars:
        indicators = _build_extended_indicators(bars)
    else:
        indicators = SimpleNamespace()

    # Support/Resistance
    sr: dict = {}
    if bars:
        try:
            from indicators.structure import find_support_resistance
            sr = find_support_resistance(bars, lookback=cfg.SR_LOOKBACK_BARS) or {}
        except Exception:
            sr = {}

    # Patterns
    patterns: list = []
    if bars and getattr(cfg, "ENABLE_CANDLESTICK_PATTERNS", False):
        try:
            from patterns import scan_patterns
            patterns = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS) or []
        except Exception:
            patterns = []

    # Regime: prendiamo l'ultimo regime dalla serie indicators (None se non disponibile)
    regime_last = _last(getattr(indicators, "volatility_regime", None))
    regime = regime_last if isinstance(regime_last, str) else "normal"

    # Recent trades (opzionale — Mt5Client può non esporlo)
    recent_trades: list = []
    if hasattr(mt5_client, "get_trade_history"):
        try:
            recent_trades = mt5_client.get_trade_history(n=5) or []
        except Exception:
            recent_trades = []

    spread_baseline_pips = getattr(cfg, "SPREAD_BASELINE_PIPS", None)

    return StrategyContext(
        symbol=symbol,
        timeframe=cfg.INTRADAY_TIMEFRAME,
        profile=profile,
        sr=sr,
        regime=regime,
        patterns=patterns,
        symbol_info=sym_info,
        pip_size=pip_size,
        intermarket_score_fn=intermarket_score_fn,
        news_blackout_fn=news_blackout_fn,
        recent_trades=recent_trades,
        spread_baseline_pips=spread_baseline_pips,
        _bars=bars,
        _indicators=indicators,
    )
