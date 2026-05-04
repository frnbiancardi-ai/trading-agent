"""Test backtest harness: BacktestMt5Client, BacktestEngine, report metrics."""
import logging
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from backtest import (
    BacktestMt5Client,
    BacktestTrade,
    _calculate_metrics,
)
from config import Config


def _make_cfg(**overrides):
    cfg = MagicMock(spec=Config)
    cfg.INTRADAY_TIMEFRAME = "M15"
    cfg.INTRADAY_LOOKBACK_BARS = 200
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _bars(start: float = 1.0900, step: float = 0.0005, n: int = 100) -> list[dict]:
    """Generate trending bars."""
    return [
        {
            "time": 1700000000 + i * 900,
            "open": start + i * step - 0.0001,
            "high": start + i * step + 0.0003,
            "low": start + i * step - 0.0003,
            "close": start + i * step,
            "tick_volume": 100,
        }
        for i in range(n)
    ]


# ──────────────────────────────────────────────────────────────────────────────
# BacktestMt5Client
# ──────────────────────────────────────────────────────────────────────────────


def test_backtest_mt5_client_initialization():
    cfg = _make_cfg()
    dataset = {"EURUSD": _bars()}
    client = BacktestMt5Client(cfg, dataset)

    assert client.initialize() is True
    assert client.login() is True
    assert client.symbol_to_bars == dataset


def test_backtest_mt5_client_get_ohlc():
    cfg = _make_cfg()
    eurusd_bars = _bars(n=50)
    dataset = {"EURUSD": eurusd_bars}
    client = BacktestMt5Client(cfg, dataset)

    # First call: get 10 bars starting from idx 0
    bars = client.get_ohlc("EURUSD", "M15", 10)
    assert len(bars) == 10
    assert bars[0] == eurusd_bars[0]

    # Symbol not in dataset
    bars = client.get_ohlc("GBPUSD", "M15", 10)
    assert bars == []


def test_backtest_mt5_client_get_symbol_info():
    cfg = _make_cfg()
    client = BacktestMt5Client(cfg, {})
    info = client.get_symbol_info("EURUSD")

    assert info.point == 0.00001
    assert info.digits == 5


# ──────────────────────────────────────────────────────────────────────────────
# Metrics calculation
# ──────────────────────────────────────────────────────────────────────────────


def test_calculate_metrics_no_trades():
    trades = []
    report = _calculate_metrics(trades, 10000.0)

    assert report.total_trades == 0
    assert report.winrate == 0.0
    assert report.end_balance == 10000.0


def test_calculate_metrics_single_winning_trade():
    now = datetime.now()
    trades = [
        BacktestTrade(
            symbol="EURUSD",
            direction="BUY",
            entry_time=now,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            lots=1.0,
            exit_time=now,
            exit_price=1.1100,
            exit_reason="TP",
            profit_pct=0.909,  # 100 pips profit on 11000 entry ≈ 0.909%
            profit_r=2.0,
        )
    ]
    report = _calculate_metrics(trades, 10000.0)

    assert report.total_trades == 1
    assert report.winning_trades == 1
    assert report.losing_trades == 0
    assert report.winrate == 1.0
    assert report.avg_win_pct == pytest.approx(0.909, abs=0.01)
    assert report.profit_factor > 1.0


def test_calculate_metrics_mixed_trades():
    now = datetime.now()
    trades = [
        BacktestTrade(
            symbol="EURUSD",
            direction="BUY",
            entry_time=now,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            lots=1.0,
            exit_time=now,
            exit_price=1.1100,
            exit_reason="TP",
            profit_pct=0.909,
            profit_r=2.0,
        ),
        BacktestTrade(
            symbol="EURUSD",
            direction="SELL",
            entry_time=now,
            entry_price=1.1100,
            stop_loss=1.1150,
            take_profit=1.1000,
            lots=1.0,
            exit_time=now,
            exit_price=1.1050,  # Loss: exit above entry
            exit_reason="SL",
            profit_pct=-0.450,
            profit_r=-0.9,
        ),
    ]
    report = _calculate_metrics(trades, 10000.0)

    assert report.total_trades == 2
    assert report.winning_trades == 1
    assert report.losing_trades == 1
    assert report.winrate == pytest.approx(0.5, abs=0.01)
    assert report.profit_factor > 0


def test_calculate_metrics_expectancy():
    """Expectancy = winrate * avg_win - (1 - winrate) * avg_loss."""
    now = datetime.now()
    trades = [
        BacktestTrade(
            symbol="EURUSD",
            direction="BUY",
            entry_time=now,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            lots=1.0,
            exit_time=now,
            exit_price=1.1100,
            exit_reason="TP",
            profit_pct=1.0,
            profit_r=2.0,
        ),
    ] * 5  # 5 winning trades
    trades += [
        BacktestTrade(
            symbol="EURUSD",
            direction="SELL",
            entry_time=now,
            entry_price=1.1000,
            stop_loss=1.1050,
            take_profit=1.0900,
            lots=1.0,
            exit_time=now,
            exit_price=1.1025,  # Loss
            exit_reason="SL",
            profit_pct=-0.5,
            profit_r=-1.0,
        ),
    ] * 5  # 5 losing trades

    report = _calculate_metrics(trades, 10000.0)

    assert report.total_trades == 10
    assert report.winrate == pytest.approx(0.5, abs=0.01)
    assert report.expectancy > 0  # Should be positive (wins > losses)
