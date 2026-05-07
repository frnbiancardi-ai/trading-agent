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
from config import Config
import strategy as strategy_mod


def _testing_cfg() -> Config:
    """Config tuned for synthetic-fixture tests.

    Loosens gates so a hand-crafted breakout deterministically passes:
      - patterns disabled (no need to forge candle shapes),
      - lowered MIN_TREND_STRENGTH (consolidation phase reduces coherence),
      - widened RSI band (a clean breakout pushes RSI ~80),
      - widened SL pip range to accommodate ATR-sized stops on synthetic data.
    """
    cfg = Config()
    cfg.ENABLE_CANDLESTICK_PATTERNS = False
    cfg.MIN_TREND_STRENGTH = 0.20
    cfg.MIN_RSI_OVERSOLD = 5
    cfg.MAX_RSI_OVERBOUGHT = 95
    cfg.MIN_SL_PIPS = 1
    cfg.MAX_SL_PIPS = 200
    cfg.MIN_ATR_PIPS = 1.0
    cfg.MIN_CONFIDENCE_TO_PROPOSE = 0.0
    return cfg


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
    """260+ bars engineered to trigger a BUY breakout setup at the LAST bar.

    Realistic 4-6 pip bar ranges to keep ATR > MIN_ATR_PIPS=3:
      - Phase A (0..199): noisy uptrend — net +1 pip/bar with ±5 pip swings.
      - Phase B (200..258): consolidation 59 bars below resistance, ~5 pip
        bar ranges, flat → resets RSI to ~50 by the time we breakout.
      - Phase D (259, last): a clean breakout — close 5 pip above resistance,
        volume 3× the 20-bar average → breakout="CLEAN".
    """
    import random
    rng = random.Random(42)
    bars: list[Bar] = []
    t0 = 1_700_000_000
    price = base

    # Phase A: warmup uptrend — stronger drift so SMA20 stays > SMA50.
    for i in range(240):
        net = 0.00020   # +2 pip net drift
        noise = rng.uniform(-0.00030, 0.00030)
        new_price = price + net + noise
        bar_range = rng.uniform(0.00040, 0.00060)
        high = max(price, new_price) + bar_range / 2
        low = min(price, new_price) - bar_range / 2
        bars.append(_make_bar(t0 + i * 3600, price, high, low, new_price, v=180))
        price = new_price

    # Phase B: short consolidation 19 bars (just enough to set resistance pivot).
    consolidation_top = price + 0.00010
    for i in range(240, 259):
        noise = rng.uniform(-0.00015, 0.00015)
        new_price = price + noise
        if new_price > consolidation_top - 0.00005:
            new_price = consolidation_top - rng.uniform(0.00005, 0.00012)
        bar_range = rng.uniform(0.00040, 0.00055)
        high = max(price, new_price) + bar_range / 2
        low = min(price, new_price) - bar_range / 2
        high = min(high, consolidation_top - 0.00001)
        bars.append(_make_bar(t0 + i * 3600, price, high, low, new_price, v=150))
        price = new_price

    # Phase D: single clean breakout bar (LAST bar)
    breakout_close = consolidation_top + 0.00050  # 5 pip above resistance
    breakout_high = breakout_close + 0.00010
    breakout_low = price - 0.00010
    bars.append(_make_bar(
        t0 + 259 * 3600, price, breakout_high, breakout_low, breakout_close, v=600,
    ))
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
        cost_model=cost, cfg=_testing_cfg(), ledger=ledger,
        initial_balance=10_000.0,
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
        cost_model=cost, cfg=_testing_cfg(), ledger=ledger,
        initial_balance=10_000.0,
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
        cost_model=cost, cfg=_testing_cfg(), ledger=ledger,
        initial_balance=10_000.0,
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
