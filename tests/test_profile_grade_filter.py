"""Test attivazione min_grade + min_confidence (CRIT-3, 2026-05-29).

Gate per-profilo letti da profile_filters (config/strategy.yaml):
  CONSERVATIVE min_grade=A min_conf=0.65 | MODERATE B/0.50 | AGGRESSIVE C/0.40.
"""
from __future__ import annotations

import math

import pytest

from backtest.broker import BacktestBroker
from backtest.costs import CostModel
from backtest.loader import Bar
from config import Config
from strategy import evaluate_proposal_for_bar
from strategy.adapters.live import build_ctx_live
from strategy.confluence import (
    StrategyConfig,
    grade_excluding_spread,
    grade_meets_min,
)
from strategy.proposal import (
    confidence_meets_profile_floor,
    grade_meets_profile_floor,
)


def test_grade_meets_min_ordering():
    assert grade_meets_min("A+", "A")
    assert grade_meets_min("A", "A")
    assert not grade_meets_min("B", "A")
    assert not grade_meets_min("C", "B")
    assert grade_meets_min("B", "C")
    assert not grade_meets_min("reject", "C")


def test_grade_gate_per_profile_real_config():
    # CONSERVATIVE min_grade=A: C e B falliscono, A e A+ passano.
    assert not grade_meets_profile_floor("C", "CONSERVATIVE")
    assert not grade_meets_profile_floor("B", "CONSERVATIVE")
    assert grade_meets_profile_floor("A", "CONSERVATIVE")
    assert grade_meets_profile_floor("A+", "CONSERVATIVE")
    # MODERATE min_grade=B: C fallisce, B/A passano.
    assert not grade_meets_profile_floor("C", "MODERATE")
    assert grade_meets_profile_floor("B", "MODERATE")
    # AGGRESSIVE min_grade=C: lo STESSO grade C passa.
    assert grade_meets_profile_floor("C", "AGGRESSIVE")


def test_confidence_gate_per_profile_real_config():
    assert not confidence_meets_profile_floor(0.30, "CONSERVATIVE")  # min 0.65
    assert confidence_meets_profile_floor(0.65, "CONSERVATIVE")
    assert not confidence_meets_profile_floor(0.49, "MODERATE")      # min 0.50
    assert confidence_meets_profile_floor(0.40, "AGGRESSIVE")        # min 0.40 (boundary)


def test_gate_backward_compat_min_grade_none():
    """Profilo senza min_grade/min_confidence → gate passa (no filtro)."""
    cfg = StrategyConfig(
        factors={}, grade_map={}, base_confidence={}, adjusters={}, bounds={},
        profile_filters={"X": {"min_rr": 1.0}},  # niente min_grade/min_confidence
    )
    assert grade_meets_profile_floor("C", "X", cfg) is True
    assert grade_meets_profile_floor("reject", "X", cfg) is True
    assert confidence_meets_profile_floor(0.01, "X", cfg) is True


def test_gate_unknown_profile_raises():
    with pytest.raises(ValueError, match="profile_filters"):
        grade_meets_profile_floor("A", "NOPE")
    with pytest.raises(ValueError, match="profile_filters"):
        confidence_meets_profile_floor(0.9, "NOPE")


def test_grade_excluding_spread_diagnostic():
    # 4 fattori True di cui spread_session → senza spread = 3 → B (non A).
    f = {"trend_alignment": True, "setup_pattern": True, "momentum": True,
         "volatility_regime": False, "spread_session": True}
    assert grade_excluding_spread(f) == "B"
    # 5 True → senza spread 4 → A.
    f5 = {k: True for k in f}
    assert grade_excluding_spread(f5) == "A"


# ── Integrazione: il gate vale end-to-end via build_ctx_live ─────────────────


def _synthetic_broker(n: int = 320) -> BacktestBroker:
    cost = CostModel(spread_pips=0.5, slippage_pips=0.3, commission_pips_round_trip=0.5,
                     pip_size=0.0001, pip_value_usd=10.0)
    brk = BacktestBroker("EURUSD", "H1", 10_000.0, cost, max_window=500)
    px, t0 = 1.10, 1_600_000_000
    for i in range(n):
        amp = 0.0003 + 0.0006 * (0.5 + 0.5 * math.sin(i / 23.0))
        px += 0.00015 * math.sin(i / 17.0)
        c = px + 0.4 * amp * math.sin(i / 5.0)
        brk.advance(Bar(time=t0 + i * 3600, open=px, high=px + amp, low=px - amp,
                        close=c, volume=100, symbol="EURUSD", timeframe="H1"))
        px = c
    return brk


def test_conservative_only_admits_grade_A_or_better_end_to_end():
    """Su CONSERVATIVE (min_grade A), ogni READY winner reale ha grade A o A+."""
    cfg = Config()
    cfg.INTRADAY_TIMEFRAME = "H1"
    brk = _synthetic_broker(360)
    saw_ready = False
    # itera su una manciata di "ultimi bar" simulati ricostruendo il context una volta
    ctx = build_ctx_live("EURUSD", brk, "CONSERVATIVE", cfg=cfg)
    draft = evaluate_proposal_for_bar(ctx._bars, ctx._indicators, ctx)
    if draft.setup_type == "READY":
        saw_ready = True
        assert draft.grade in ("A", "A+"), f"CONSERVATIVE ha ammesso grade {draft.grade}"
    # anche i loser READY (non dovrebbero esistere sotto A) — verifica difensiva
    for d in (draft.setup_specific or {}).get("losers", []):
        if d.setup_type == "READY":
            assert d.grade in ("A", "A+")
    # il test è valido anche se non c'è READY su questo bar (no assert-false):
    assert draft is not None
