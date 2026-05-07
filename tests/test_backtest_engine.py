"""Tests for backtest.engine (BACK-02, BACK-04). Plan 05.

The smoke test for SC-6 (12-month <60s) is intentionally skipped here — plan 08.
"""
from __future__ import annotations

import inspect
import json
import math
import sqlite3
from pathlib import Path

import pytest

from backtest.engine import BacktestEngine, run_backtest
from backtest.costs import CostModel, _pip_params
from backtest.ledger import LedgerWriter
from backtest.loader import Bar
import strategy as strategy_mod


_COSTS_YAML = Path("data/configs/costs.yaml")


def _cost_model_eurusd(price: float = 1.10000) -> CostModel:
    pip_size, pip_value = _pip_params("EURUSD", price)
    return CostModel(
        spread_pips=0.5, slippage_pips=0.3, commission_pips_round_trip=0.5,
        pip_size=pip_size, pip_value_usd=pip_value,
    )


def _make_bar(t: int, o: float, h: float, l: float, c: float, v: int = 100) -> Bar:
    return Bar(time=t, open=o, high=h, low=l, close=c, volume=v,
               symbol="EURUSD", timeframe="H1")


def _flat_bars(n: int = 5, base: float = 1.10000) -> list[Bar]:
    """Tiny fixture: not enough bars (< INTRADAY_LOOKBACK_BARS=200)."""
    bars: list[Bar] = []
    t0 = 1_700_000_000
    for i in range(n):
        bars.append(_make_bar(t0 + i * 3600, base, base + 0.0001, base - 0.0001, base))
    return bars


def _uptrend_bars(n: int = 260, base: float = 1.10000) -> list[Bar]:
    """250+ bars engineered to trigger a BUY breakout setup near the end.

    First 220 bars: gentle uptrend (5 pips/bar) keeping price above SMAs and
    consolidating below resistance. Last 40 bars: accelerated breakout
    (15 pips/bar) above prior swing high → breakout="CLEAN", trend_strength
    high, RSI in band.
    """
    bars: list[Bar] = []
    t0 = 1_700_000_000
    price = base
    for i in range(n):
        if i < 200:
            step = 0.00005   # 0.5 pip — keeps trend mild, RSI in band
        elif i < 230:
            # Pull-back / consolidation just below resistance to set up a clean breakout
            step = -0.00002
        else:
            step = 0.00020   # 2 pip — strong breakout
        new_price = price + step
        # tiny intra-bar range
        high = max(price, new_price) + 0.00010
        low = min(price, new_price) - 0.00010
        bars.append(_make_bar(t0 + i * 3600, price, high, low, new_price, v=200))
        price = new_price
    return bars


# ─── Tests ───────────────────────────────────────────────────────────────────


def test_strategy_annotation() -> None:
    """D-02: IntradayStrategy.__init__ mt5_client annotation must be BrokerProtocol."""
    sig = inspect.signature(strategy_mod.IntradayStrategy.__init__)
    ann = sig.parameters["mt5_client"].annotation
    assert "BrokerProtocol" in str(ann), f"expected BrokerProtocol, got {ann!r}"


def test_engine_5bar_fixture(tmp_path: Path) -> None:
    """Engine runs without crashing on a 5-bar fixture and produces no trades
    (insufficient bars for indicators)."""
    bars = _flat_bars(5)
    cost = _cost_model_eurusd()
    db = tmp_path / "trades.db"
    ledger = LedgerWriter(db)
    eng = BacktestEngine(
        bars=bars, symbol="EURUSD", timeframe="H1",
        cost_model=cost, ledger=ledger, initial_balance=10_000.0,
    )
    result = eng.run()
    assert result["trades"] == []
    # Equity curve has the initial balance only
    assert result["equity_curve"] == [10_000.0]
    # Run row recorded
    with sqlite3.connect(db) as conn:
        rows = list(conn.execute(
            "SELECT total_trades FROM backtest_runs WHERE run_id=?",
            (result["run_id"],),
        ))
    assert rows == [(0,)]


def test_engine_with_synthetic_signals(tmp_path: Path) -> None:
    """260-bar uptrend triggers at least one BUY → ledger row with decision context."""
    bars = _uptrend_bars(260)
    cost = _cost_model_eurusd()
    db = tmp_path / "trades.db"
    ledger = LedgerWriter(db)
    eng = BacktestEngine(
        bars=bars, symbol="EURUSD", timeframe="H1",
        cost_model=cost, ledger=ledger, initial_balance=10_000.0,
    )
    result = eng.run()
    assert len(result["trades"]) >= 1, (
        f"synthetic uptrend should fire at least one trade; got {result['trades']}"
    )
    # Ledger persisted the same number of rows
    with sqlite3.connect(db) as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM backtest_trades WHERE run_id=?",
            (result["run_id"],),
        ).fetchone()
    assert count == len(result["trades"])


def test_decision_context(tmp_path: Path) -> None:
    """Each trade must carry decision_context_json parseable into a dict with
    at least one of sma_20 / rsi_14 / atr_14 keys."""
    bars = _uptrend_bars(260)
    cost = _cost_model_eurusd()
    db = tmp_path / "trades.db"
    ledger = LedgerWriter(db)
    eng = BacktestEngine(
        bars=bars, symbol="EURUSD", timeframe="H1",
        cost_model=cost, ledger=ledger, initial_balance=10_000.0,
    )
    result = eng.run()
    if not result["trades"]:
        pytest.skip("no trades — fixture did not trigger; covered by other test")
    for trade in result["trades"]:
        ctx_raw = trade.get("decision_context_json")
        assert ctx_raw, f"missing decision_context_json on {trade}"
        ctx = json.loads(ctx_raw) if isinstance(ctx_raw, str) else ctx_raw
        assert isinstance(ctx, dict)
        assert any(k in ctx for k in ("sma_20", "rsi_14", "atr_14")), ctx


def test_equity_curve(tmp_path: Path) -> None:
    """equity_curve length == n_closed_trades + 1 (initial + one per close)."""
    bars = _uptrend_bars(260)
    cost = _cost_model_eurusd()
    db = tmp_path / "trades.db"
    ledger = LedgerWriter(db)
    eng = BacktestEngine(
        bars=bars, symbol="EURUSD", timeframe="H1",
        cost_model=cost, ledger=ledger, initial_balance=10_000.0,
    )
    result = eng.run()
    assert len(result["equity_curve"]) == len(result["trades"]) + 1
    assert math.isclose(result["equity_curve"][0], 10_000.0)


def test_run_id_deterministic(tmp_path: Path) -> None:
    """Same inputs → same run_id (skill principle 4: idempotent observability)."""
    bars = _flat_bars(5)
    cost = _cost_model_eurusd()
    db1 = tmp_path / "a.db"
    db2 = tmp_path / "b.db"
    r1 = BacktestEngine(bars=bars, symbol="EURUSD", timeframe="H1",
                        cost_model=cost, ledger=LedgerWriter(db1)).run()
    r2 = BacktestEngine(bars=bars, symbol="EURUSD", timeframe="H1",
                        cost_model=cost, ledger=LedgerWriter(db2)).run()
    assert r1["run_id"] == r2["run_id"]


@pytest.mark.skip(reason="implemented in plan 08")
def test_smoke_12month_under_60s() -> None:
    pass
