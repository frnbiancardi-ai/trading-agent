"""Confluence scorer + grade + confidence calibrator (Phase 4 STRAT-05/06).

Pure-function modulo: nessun broker call, nessun logging, nessun side effect.
Carica config/strategy.yaml UNA volta (lru_cache); espone:
  - load_strategy_config(path=None) -> StrategyConfig
  - score_factors(setup_name, indicators, ctx, direction) -> dict[str, bool]
  - grade_for(factors) -> Literal["A+", "A", "B", "C", "reject"]
  - compute_confidence(grade, ctx, setup_name, factors=None, indicators=None) -> float
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from strategy.context import StrategyContext

DEFAULT_STRATEGY_CONFIG_PATH = Path("config/strategy.yaml")
Grade = Literal["A+", "A", "B", "C", "reject"]


@dataclass(frozen=True)
class StrategyConfig:
    """Snapshot immutabile di config/strategy.yaml (D-08 schema)."""

    factors: dict
    grade_map: dict
    base_confidence: dict
    adjusters: dict
    bounds: dict
    profile_filters: dict


def _build_strategy_config(raw: dict) -> StrategyConfig:
    """Verifica chiavi obbligatorie e costruisce dataclass (mirror backtest/costs.py pattern)."""
    required = {
        "factors",
        "grade_map",
        "base_confidence",
        "adjusters",
        "bounds",
        "profile_filters",
    }
    missing = required - set(raw.keys())
    if missing:
        raise ValueError(f"strategy.yaml: chiavi mancanti {missing}")
    return StrategyConfig(
        factors=raw["factors"],
        grade_map=raw["grade_map"],
        base_confidence=raw["base_confidence"],
        adjusters=raw["adjusters"],
        bounds=raw["bounds"],
        profile_filters=raw["profile_filters"],
    )


@lru_cache(maxsize=4)
def _load_cached(path_str: str) -> StrategyConfig:
    """Cache per path-string: tmp_path nel test produce miss, no pollution."""
    with open(path_str, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return _build_strategy_config(raw)


def load_strategy_config(path: str | Path | None = None) -> StrategyConfig:
    """Carica config/strategy.yaml. Priorità: parametro > env STRATEGY_CONFIG_PATH > default."""
    if path is None:
        path = os.environ.get("STRATEGY_CONFIG_PATH") or DEFAULT_STRATEGY_CONFIG_PATH
    return _load_cached(str(Path(path)))


# ==========================================================================
# Helpers
# ==========================================================================


def _last_or_none(seq):
    """Estrae l'ultimo elemento da una sequenza, altrimenti None."""
    if seq is None:
        return None
    try:
        v = seq[-1]
    except (TypeError, IndexError, KeyError):
        return None
    return v


# ==========================================================================
# Factor predicates (5 fattori — D-08)
# ==========================================================================


def _check_trend_alignment(
    indicators, ctx: StrategyContext, direction: str, cfg: StrategyConfig
) -> bool:
    """Factor 1: EMA50 slope coerente con direction (D-08)."""
    slope = _last_or_none(getattr(indicators, "ema50_slope", None))
    if slope is None:
        return False
    if direction == "BUY":
        return slope > 0
    if direction == "SELL":
        return slope < 0
    return False


def _check_setup_pattern(
    setup_name: str,
    indicators,
    ctx: StrategyContext,
    direction: str,
    cfg: StrategyConfig,
) -> bool:
    """Factor 2: setup geometry completo (D-08, half_formed_rejected)."""
    # Per A_breakout: closing_score >75 (BUY) o <25 (SELL)
    if setup_name == "A_breakout":
        cs = _last_or_none(getattr(indicators, "closing_score", None))
        if cs is None:
            return False
        return cs > 75 if direction == "BUY" else cs < 25
    # Per B_reversal: PatternHit presente al livello con direction matching
    if setup_name == "B_reversal":
        patterns = ctx.patterns or []
        want_dir = "bullish" if direction == "BUY" else "bearish"
        for p in patterns:
            p_dir = getattr(p, "direction", None)
            bar_idx = getattr(p, "bar_index", -99)
            if p_dir == want_dir and abs(bar_idx) <= 3:
                return True
        return False
    # Per C_compression: NR4/NR7 confermato OPPURE BB squeeze
    if setup_name == "C_compression":
        nr = getattr(indicators, "nr_detect", None)
        nr7 = _last_or_none(getattr(nr, "nr7", None)) if nr else False
        nr4 = _last_or_none(getattr(nr, "nr4", None)) if nr else False
        bb = getattr(indicators, "bollinger_bands", None)
        squeeze = _last_or_none(getattr(bb, "squeeze", None)) if bb else False
        return bool(nr7 or nr4 or squeeze)
    # Per D_pullback: continuation pattern al pullback (closing_score banda neutrale)
    if setup_name == "D_pullback":
        cs = _last_or_none(getattr(indicators, "closing_score", None))
        if cs is None:
            return False
        return 30 <= cs <= 70
    return False


def _check_momentum(indicators, direction: str, cfg: StrategyConfig) -> bool:
    """Factor 3: RSI non in zona esaurimento contro la direzione (D-08)."""
    rsi = _last_or_none(getattr(indicators, "rsi_14", None))
    if rsi is None:
        return False
    if direction == "BUY":
        return rsi < 75  # non overbought
    if direction == "SELL":
        return rsi > 25  # non oversold
    return False


def _check_volatility_regime(
    setup_name: str, indicators, cfg: StrategyConfig
) -> bool:
    """Factor 4: regime ATR appropriato per il setup (D-08)."""
    regime = _last_or_none(getattr(indicators, "volatility_regime", None))
    if regime is None:
        return False
    vol_cfg = cfg.factors["volatility_regime"]
    key_map = {
        "A_breakout": "breakout_required",
        "B_reversal": "reversal_required",
        "C_compression": "compression_required",
        "D_pullback": "pullback_required",
    }
    allowed = vol_cfg.get(key_map.get(setup_name, ""), [])
    return regime in allowed


def _check_spread_session(
    indicators, ctx: StrategyContext, cfg: StrategyConfig
) -> bool:
    """Factor 5: spread/atr <= max_spread_atr_ratio (D-08)."""
    atr = _last_or_none(getattr(indicators, "atr_14", None))
    if atr is None or atr <= 0:
        return False
    # Spread corrente: bid/ask da symbol_info se disponibile, altrimenti baseline_pips
    sym = ctx.symbol_info
    bid = getattr(sym, "bid", None) if sym is not None else None
    ask = getattr(sym, "ask", None) if sym is not None else None
    if bid is not None and ask is not None and ask > bid:
        spread = ask - bid
    elif ctx.spread_baseline_pips is not None and ctx.pip_size:
        spread = ctx.spread_baseline_pips * ctx.pip_size
    else:
        return False
    max_ratio = cfg.factors["spread_session"]["max_spread_atr_ratio"]
    return (spread / atr) <= max_ratio


# ==========================================================================
# Public API
# ==========================================================================


def score_factors(
    setup_name: str,
    indicators,
    ctx: StrategyContext,
    direction: str,
    cfg: StrategyConfig | None = None,
) -> dict[str, bool]:
    """Calcola i 5 fattori confluence per <setup_name> e <direction>.

    Ritorna dict[str, bool] con esattamente 5 chiavi (D-08):
      trend_alignment, setup_pattern, momentum, volatility_regime, spread_session.
    """
    cfg = cfg or load_strategy_config()
    return {
        "trend_alignment": _check_trend_alignment(indicators, ctx, direction, cfg),
        "setup_pattern": _check_setup_pattern(
            setup_name, indicators, ctx, direction, cfg
        ),
        "momentum": _check_momentum(indicators, direction, cfg),
        "volatility_regime": _check_volatility_regime(setup_name, indicators, cfg),
        "spread_session": _check_spread_session(indicators, ctx, cfg),
    }


_GRADE_FROM_COUNT = {5: "A+", 4: "A", 3: "B", 2: "C"}

# Ordinamento totale dei grade (CRIT-3, 2026-05-29): per confrontare un grade con
# profile_filters[profile].min_grade. reject < C < B < A < A+.
_GRADE_RANK = {"reject": 0, "C": 1, "B": 2, "A": 3, "A+": 4}


def grade_for(factors: dict[str, bool]) -> Grade:
    """Mappa numero fattori True → grade (D-08 grade_map).

    5 → A+, 4 → A, 3 → B, 2 → C, ≤1 → reject.
    """
    n = sum(1 for v in factors.values() if v)
    return _GRADE_FROM_COUNT.get(n, "reject")


def grade_meets_min(grade: str, min_grade: str) -> bool:
    """True se grade >= min_grade nell'ordine reject<C<B<A<A+ (CRIT-3)."""
    return _GRADE_RANK.get(grade, 0) >= _GRADE_RANK.get(min_grade, 0)


def grade_excluding_spread(factors: dict[str, bool]) -> Grade:
    """Grade ricalcolato ignorando spread_session (SOLO diagnostica backtest, CRIT-3).

    In backtest spread_session è True ~100% (baseline 1.0 pip < ATR) → 1 fattore
    "regalato". Questa utility conta i fattori veri escludendo spread_session, per
    misurare quanto il grade è "gonfiato". NON è un gate di produzione.
    """
    n = sum(1 for k, v in factors.items() if v and k != "spread_session")
    return _GRADE_FROM_COUNT.get(n, "reject")


def compute_confidence(
    grade: Grade,
    ctx: StrategyContext,
    setup_name: str,
    factors: dict[str, bool] | None = None,
    indicators=None,
    cfg: StrategyConfig | None = None,
) -> float:
    """Calibra confidence: base[grade] + Σ adjusters, clampato a [min,max] bounds (D-08, D-11).

    grade='reject' o non in base_confidence → ritorna 0.0 (no min_confidence floor).
    """
    cfg = cfg or load_strategy_config()
    if grade == "reject" or grade not in cfg.base_confidence:
        return 0.0
    base = float(cfg.base_confidence[grade])
    adj = cfg.adjusters
    delta = 0.0

    # Adjuster 1: intermarket_confirmation (D-09 stub: callable opzionale)
    if ctx.intermarket_score_fn is not None:
        try:
            if ctx.intermarket_score_fn(ctx.symbol) > 0:
                delta += float(adj["intermarket_confirmation"])
        except Exception:
            pass  # stub safety: zero-impact se chiamata fallisce

    # Adjuster 2: recent_winning_trade_same_pair (ultime 5 da ctx.recent_trades)
    rt = ctx.recent_trades or []
    last5 = rt[-5:] if len(rt) > 5 else rt
    if last5 and any(getattr(t, "outcome", None) == "WIN" for t in last5):
        delta += float(adj["recent_winning_trade_same_pair"])

    # Adjuster 3: spread_tighter_than_baseline (epsilon per evitare drift FP)
    if (
        ctx.spread_baseline_pips is not None
        and ctx.symbol_info is not None
        and ctx.pip_size
    ):
        sym = ctx.symbol_info
        bid = getattr(sym, "bid", None)
        ask = getattr(sym, "ask", None)
        if bid is not None and ask is not None:
            cur_pips = (ask - bid) / ctx.pip_size
            # Strictly tighter: 1e-6 epsilon contro float arithmetic noise
            if cur_pips < ctx.spread_baseline_pips - 1e-6:
                delta += float(adj["spread_tighter_than_baseline"])

    # Adjuster 4: macro_event_within_60min (D-09 stub callable)
    if ctx.news_blackout_fn is not None:
        try:
            from datetime import datetime, timezone

            if ctx.news_blackout_fn(datetime.now(timezone.utc)):
                delta += float(adj["macro_event_within_60min"])
        except Exception:
            pass

    # Adjuster 5: last_2_trades_lost_same_pair
    last2 = rt[-2:] if len(rt) >= 2 else rt
    if len(last2) == 2 and all(
        getattr(t, "outcome", None) == "LOSS" for t in last2
    ):
        delta += float(adj["last_2_trades_lost_same_pair"])

    # Adjuster 6: proposing_against_medium_term_trend (factors snapshot)
    if factors is not None and not factors.get("trend_alignment", True):
        delta += float(adj["proposing_against_medium_term_trend"])

    raw = base + delta
    lo = float(cfg.bounds["min_confidence"])
    hi = float(cfg.bounds["max_confidence"])
    return round(max(lo, min(hi, raw)), 4)
