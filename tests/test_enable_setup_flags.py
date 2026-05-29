"""Test meccanismo ENABLE_SETUP_* (2026-05-29).

Verifica il filtro enable/disable in evaluate_proposal_for_bar + il popolamento
di ctx.enabled_setups da build_ctx_live. B_reversal disabilitato di default.
"""
from __future__ import annotations

import math

from backtest.broker import BacktestBroker
from backtest.costs import CostModel
from backtest.loader import Bar
from config import Config
from strategy import evaluate_proposal_for_bar
from strategy.adapters.live import build_ctx_live
from strategy.context import StrategyContext


def _ctx(enabled):
    """StrategyContext minimale; bars vuoti → ogni detector ritorna NONE/insufficient_bars."""
    return StrategyContext(
        symbol="EURUSD", timeframe="H1", profile="MODERATE",
        sr={}, regime="normal", patterns=[], symbol_info=None, pip_size=0.0001,
        enabled_setups=enabled,
    )


def _all_setup_names(winner):
    """Nomi setup di winner + losers (i drafts prodotti in questo bar)."""
    losers = (winner.setup_specific or {}).get("losers", [])
    return [winner.setup_name] + [d.setup_name for d in losers]


def test_enabled_none_runs_all_four_backward_compat():
    """enabled_setups=None → tutti e 4 i detector girano (backward-compat)."""
    winner = evaluate_proposal_for_bar([], None, _ctx(None))
    losers = (winner.setup_specific or {}).get("losers", [])
    # 4 drafts totali = winner + 3 losers
    assert len(losers) == 3, f"attesi 3 losers (4 detector), trovati {len(losers)}"


def test_ctx_none_backward_compat_no_crash():
    """ctx=None (vecchie chiamate/test) → getattr ritorna None → tutti i detector."""
    winner = evaluate_proposal_for_bar([], None, None)
    losers = (winner.setup_specific or {}).get("losers", [])
    assert len(losers) == 3


def test_b_disabled_runs_only_three():
    """enabled senza B_reversal → solo 3 detector girano (2 losers, B assente)."""
    enabled = frozenset({"A_breakout", "C_compression", "D_pullback"})
    winner = evaluate_proposal_for_bar([], None, _ctx(enabled))
    losers = (winner.setup_specific or {}).get("losers", [])
    assert len(losers) == 2, f"attesi 2 losers (3 detector), trovati {len(losers)}"


def test_empty_enabled_set_returns_none_no_crash():
    """enabled_setups=frozenset() (tutti off) → NONE/no_enabled_setups, niente IndexError."""
    winner = evaluate_proposal_for_bar([], None, _ctx(frozenset()))
    assert winner.setup_type == "NONE"
    assert winner.reason == "no_enabled_setups"


# ── Integrazione: VERO build_ctx_live coi flag cfg ───────────────────────────


def _synthetic_broker(n: int = 320) -> BacktestBroker:
    cost = CostModel(
        spread_pips=0.5, slippage_pips=0.3, commission_pips_round_trip=0.5,
        pip_size=0.0001, pip_value_usd=10.0,
    )
    brk = BacktestBroker("EURUSD", "H1", 10_000.0, cost, max_window=500)
    px = 1.10
    t0 = 1_600_000_000
    for i in range(n):
        amp = 0.0003 + 0.0006 * (0.5 + 0.5 * math.sin(i / 23.0))
        px += 0.00015 * math.sin(i / 17.0)
        c = px + 0.4 * amp * math.sin(i / 5.0)
        brk.advance(Bar(
            time=t0 + i * 3600, open=px, high=px + amp, low=px - amp, close=c,
            volume=100, symbol="EURUSD", timeframe="H1",
        ))
        px = c
    return brk


def test_build_ctx_live_excludes_b_when_flag_false():
    """cfg.ENABLE_SETUP_B=False → 'B_reversal' assente da ctx.enabled_setups; altri 3 presenti."""
    cfg = Config()
    cfg.INTRADAY_TIMEFRAME = "H1"
    cfg.ENABLE_SETUP_B = False
    cfg.ENABLE_SETUP_A = True
    cfg.ENABLE_SETUP_C = True
    cfg.ENABLE_SETUP_D = True
    ctx = build_ctx_live("EURUSD", _synthetic_broker(), "MODERATE", cfg=cfg)
    assert ctx.enabled_setups is not None
    assert "B_reversal" not in ctx.enabled_setups
    assert {"A_breakout", "C_compression", "D_pullback"} <= ctx.enabled_setups


def test_evaluate_real_ctx_never_proposes_b_when_disabled():
    """Col context reale e B off, nessun draft (winner o loser) ha setup_name 'B_reversal'."""
    cfg = Config()
    cfg.INTRADAY_TIMEFRAME = "H1"
    cfg.ENABLE_SETUP_B = False
    ctx = build_ctx_live("EURUSD", _synthetic_broker(), "MODERATE", cfg=cfg)
    winner = evaluate_proposal_for_bar(ctx._bars, ctx._indicators, ctx)
    names = _all_setup_names(winner)
    assert "B_reversal" not in names, f"B_reversal non dovrebbe comparire: {names}"


def test_build_ctx_live_default_disables_b():
    """Default di config (ENABLE_SETUP_B=False) → B assente da ctx.enabled_setups."""
    cfg = Config()
    cfg.INTRADAY_TIMEFRAME = "H1"
    ctx = build_ctx_live("EURUSD", _synthetic_broker(), "MODERATE", cfg=cfg)
    assert "B_reversal" not in ctx.enabled_setups
    assert "A_breakout" in ctx.enabled_setups
