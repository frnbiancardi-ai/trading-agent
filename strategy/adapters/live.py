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

from pathlib import Path
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
    from indicators.trend import ema
    from indicators.momentum import rsi
    from indicators.volatility import atr, bollinger_bands
    from indicators.bars import closing_score, narrow_range

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

    # bollinger_bands con squeeze gate richiede keltner per il calcolo dello squeeze
    bb = bollinger_bands(
        closes, length=20, std=2.0,
        highs=highs, lows=lows,
        keltner_length=20, keltner_scalar=2.0,
    )
    cs = closing_score(bars)
    nr = narrow_range(bars)
    # Fibonacci computation è costosa per backtest per-bar (loop su 100 bar);
    # lasciato a None — Setup D ha fallback OR-logic in_ema20_zone che funziona
    # senza Fib (vedi 04-05-SUMMARY pullback zone OR-logic). Phase 5/8 backtest
    # potrà ricomputarlo a livello engine_state se necessario.
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

    # CRIT-1 (audit 2026-05-28): popola volatility_regime nella confluence.
    # Prima era hard-coded a None in _build_extended_indicators → fattore 4
    # (volatility_regime) SEMPRE False → grade ceiling B in backtest, A+
    # irraggiungibile ovunque. Il classificatore (indicators.volatility_regime)
    # è puro e anti-leakage (rolling rank trailing, Pitfall 4); qui ci limitiamo
    # a passargli i bar e a iniettarne la serie `state`.
    #
    # Perché un re-fetch dedicato: il classificatore richiede una finestra
    # trailing PIENA di ATR validi (regime_window valori), ma ATR ha ~14 bar di
    # warm-up None. Con INTRADAY_LOOKBACK_BARS == regime_window (200 == 200) il
    # bar corrente non ha mai una finestra piena → state[-1] resterebbe None.
    # Rifetchiamo una finestra più ampia SOLO per il regime: così le altre serie
    # indicatori restano IDENTICHE (nessun reseed EMA/RSI → nessun cambiamento
    # collaterale sugli altri 4 fattori). Il detector legge volatility_regime[-1],
    # che è allineato al bar corrente comune a entrambe le finestre.
    if bars:
        from indicators.volatility import load_regime_config, volatility_regime

        try:
            regime_cfg = load_regime_config(
                symbol,
                Path(getattr(cfg, "REGIME_CONFIG_PATH", "data/configs/regime.yaml")),
            )
        except (FileNotFoundError, KeyError):
            regime_cfg = None  # fallback: defaults interni di volatility_regime
        regime_window = int(regime_cfg.get("window", 200)) if regime_cfg else 200
        # +64: copre il warm-up ATR (14) + margine. Limitato implicitamente dalla
        # storia disponibile lato broker (deque maxlen=500 in backtest).
        regime_lookback = max(int(cfg.INTRADAY_LOOKBACK_BARS), regime_window + 64)
        try:
            regime_bars = (
                mt5_client.get_ohlc(symbol, cfg.INTRADAY_TIMEFRAME, regime_lookback)
                or bars
            )
        except Exception:
            regime_bars = bars
        try:
            regime_state = volatility_regime(regime_bars, regime_cfg).state
        except Exception:
            regime_state = None
        if regime_state is not None:
            # SimpleNamespace: override dell'attributo (la serie [-1] è il bar corrente).
            indicators.volatility_regime = regime_state

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

    # spread_baseline_pips: forziamo None se l'attributo non è numerico (es.
    # MagicMock auto-attr nei test fixture). Protegge il confronto float in
    # confluence.compute_confidence (adjuster spread_tighter_than_baseline).
    _spread_raw = getattr(cfg, "SPREAD_BASELINE_PIPS", None)
    spread_baseline_pips: float | None = (
        float(_spread_raw) if isinstance(_spread_raw, (int, float)) else None
    )

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
