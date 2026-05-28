"""Tests for backtest.metrics (BACK-06, success criterion 5)."""
from __future__ import annotations

import math

from backtest.metrics import BARS_PER_YEAR, BacktestMetrics, compute_metrics


FIXTURE_TRADES = [
    {"pnl_usd": 20.0, "risk_usd": 10.0, "entry_time": 1, "exit_time": 2},   # +2R
    {"pnl_usd": -10.0, "risk_usd": 10.0, "entry_time": 3, "exit_time": 4},  # -1R
    {"pnl_usd": 20.0, "risk_usd": 10.0, "entry_time": 5, "exit_time": 6},   # +2R
    {"pnl_usd": 20.0, "risk_usd": 10.0, "entry_time": 7, "exit_time": 8},   # +2R
    {"pnl_usd": 5.0,  "risk_usd": 10.0, "entry_time": 9, "exit_time": 10},  # +0.5R
]
# Expected (verified by hand): hit_rate=0.8, expectancy=11.0, profit_factor=6.5, avg_r=1.1


def test_known_fixture() -> None:
    m = compute_metrics(FIXTURE_TRADES, "H1")
    assert m.total_trades == 5
    assert abs(m.hit_rate - 0.8) < 1e-4
    assert abs(m.expectancy_usd - 11.0) < 1e-4
    assert abs(m.profit_factor - 6.5) < 1e-4
    assert abs(m.avg_r - 1.1) < 1e-4
    assert abs(m.total_pnl_usd - 55.0) < 1e-4


def test_empty_ledger() -> None:
    m = compute_metrics([], "H1")
    assert m.total_trades == 0
    assert m.sharpe == 0.0
    assert m.profit_factor == 0.0  # zero, not nan or inf
    assert m.max_drawdown_pct == 0.0


def test_annualization() -> None:
    assert BARS_PER_YEAR == {"H1": 6048, "M30": 12096, "M15": 24192}
    m_h1 = compute_metrics(FIXTURE_TRADES, "H1")
    m_m15 = compute_metrics(FIXTURE_TRADES, "M15")
    # M15 has larger N → larger sqrt → larger |sharpe|
    assert abs(m_m15.sharpe) > abs(m_h1.sharpe)


def test_max_drawdown() -> None:
    trades = [
        {"pnl_usd": 10.0, "risk_usd": 10.0, "entry_time": 1, "exit_time": 2},
        {"pnl_usd": 10.0, "risk_usd": 10.0, "entry_time": 3, "exit_time": 4},
        {"pnl_usd": -25.0, "risk_usd": 10.0, "entry_time": 5, "exit_time": 6},
        {"pnl_usd": 10.0, "risk_usd": 10.0, "entry_time": 7, "exit_time": 8},
    ]
    m = compute_metrics(trades, "H1")
    # peak after second trade = 20; trough after third = -5; dd = (20 - (-5))/20 = 1.25 = 125%
    assert abs(m.max_drawdown_pct - 125.0) < 1e-4


def test_profit_factor_all_winners() -> None:
    trades = [
        {"pnl_usd": 5.0, "risk_usd": 10.0, "entry_time": 1, "exit_time": 2},
        {"pnl_usd": 7.0, "risk_usd": 10.0, "entry_time": 3, "exit_time": 4},
    ]
    m = compute_metrics(trades, "H1")
    assert math.isinf(m.profit_factor)
    assert isinstance(m, BacktestMetrics)
