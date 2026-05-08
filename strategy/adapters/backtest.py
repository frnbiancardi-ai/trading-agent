"""Adapter backtest: build_ctx_backtest (Wave 3 STRAT-09).

Bridge non-pure tra il backtest engine (Phase 1+5) e StrategyContext consumato
dai detector pure-fn. ESCLUSO dal purity gate per design (I/O bridge).

Single-compute (D-12): si aspetta che engine_state esponga `bars_so_far` e
`current_indicators` (entrambi pre-calcolati dal backtest driver per evitare
ricomputazione per-bar). Phase 5 implementerà la EngineState concreta; questo
adapter Wave 3 contrattualizza i campi attesi e legge difensivamente con
getattr fallback.

Stessa shape di output di build_ctx_live (D-05 — single shared context).
"""
from __future__ import annotations

from typing import Callable

from strategy.context import StrategyContext


def build_ctx_backtest(
    symbol: str,
    engine_state,
    profile: str,
    intermarket_score_fn: Callable | None = None,
    news_blackout_fn: Callable | None = None,
) -> StrategyContext:
    """Costruisce StrategyContext leggendo da engine_state (defensive getattr).

    engine_state attesi (Phase 5 EngineState concreta):
      - bars_so_far: list[dict]                              (mandatory)
      - current_indicators: ExtendedIndicators-like namespace (mandatory)
      - sr: dict                                             (default {})
      - patterns: list                                       (default [])
      - symbol_info: object                                  (default None)
      - pip_size: float                                      (default 0.0001)
      - regime: str                                          (default "normal")
      - timeframe: str                                       (default "M15")
      - recent_trades_for(symbol) -> list                    (optional method)
      - spread_baseline_pips: float | None                   (default None)
    """
    bars = getattr(engine_state, "bars_so_far", None) or []
    indicators = getattr(engine_state, "current_indicators", None)

    sr = getattr(engine_state, "sr", None) or {}
    patterns = getattr(engine_state, "patterns", None) or []
    sym_info = getattr(engine_state, "symbol_info", None)
    pip_size = getattr(engine_state, "pip_size", 0.0001)
    regime = getattr(engine_state, "regime", "normal")
    timeframe = getattr(engine_state, "timeframe", "M15")
    spread_baseline_pips = getattr(engine_state, "spread_baseline_pips", None)

    if hasattr(engine_state, "recent_trades_for"):
        try:
            recent_trades = engine_state.recent_trades_for(symbol) or []
        except Exception:
            recent_trades = []
    else:
        recent_trades = []

    return StrategyContext(
        symbol=symbol,
        timeframe=timeframe,
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
