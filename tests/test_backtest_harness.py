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


def test_backtest_mt5_client_get_ohlc_no_lookahead():
    """get_ohlc deve ritornare ULTIME n_bars terminanti a current_bar_index (inclusivo).
    Mirror di mt5.copy_rates_from_pos(0, n) live: zero look-ahead bias."""
    cfg = _make_cfg()
    eurusd_bars = _bars(n=50)
    dataset = {"EURUSD": eurusd_bars}
    client = BacktestMt5Client(cfg, dataset)

    # Caso 1: idx=0 → solo 1 barra disponibile (la corrente)
    client.current_bar_index["EURUSD"] = 0
    bars = client.get_ohlc("EURUSD", "M15", 10)
    assert len(bars) == 1
    assert bars[0] == eurusd_bars[0]

    # Caso 2: idx=20, n=10 → bars[11:21] = ultime 10 fino a idx incluso
    client.current_bar_index["EURUSD"] = 20
    bars = client.get_ohlc("EURUSD", "M15", 10)
    assert len(bars) == 10
    assert bars[0] == eurusd_bars[11]
    assert bars[-1] == eurusd_bars[20]

    # Caso 3: idx=5, n=10 → solo 6 disponibili (no future bars)
    client.current_bar_index["EURUSD"] = 5
    bars = client.get_ohlc("EURUSD", "M15", 10)
    assert len(bars) == 6
    assert bars[-1] == eurusd_bars[5]

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


# ──────────────────────────────────────────────────────────────────────────────
# Realistic cost modeling (fase 17.6.1)
# ──────────────────────────────────────────────────────────────────────────────


def test_pip_size_forex_jpy_metals():
    """Pip size corretto per categorie simboli."""
    from backtest import BacktestEngine
    cfg = _make_cfg(BACKTEST_SPREAD_PIPS=1.0, BACKTEST_COMMISSION_PER_LOT=5.0,
                    BACKTEST_SLIPPAGE_PIPS=0.5)
    engine = BacktestEngine(cfg=cfg, symbol_to_bars={"EURUSD": _bars()})

    assert engine._pip_size("EURUSD") == 0.0001
    assert engine._pip_size("GBPUSD") == 0.0001
    assert engine._pip_size("USDJPY") == 0.01
    assert engine._pip_size("XAUUSD") == 0.01
    assert engine._pip_size("USOIL") == 0.01


def test_pip_value_usd_forex_majors():
    """Valore pip USD per 1 lot forex maggiore = $10."""
    from backtest import BacktestEngine
    cfg = _make_cfg()
    engine = BacktestEngine(cfg=cfg, symbol_to_bars={"EURUSD": _bars()})

    assert engine._pip_value_usd("EURUSD", 1.0) == 10.0
    assert engine._pip_value_usd("EURUSD", 0.1) == 1.0
    assert engine._pip_value_usd("XAUUSD", 1.0) == 1.0
    assert engine._pip_value_usd("USOIL", 1.0) == 10.0


def test_execute_order_applies_spread_to_entry():
    """BUY entry = close + spread, SELL entry = close - spread."""
    from backtest import BacktestEngine
    from models import TradeProposal

    cfg = _make_cfg(BACKTEST_SPREAD_PIPS=2.0)
    cfg.MIN_SL_PIPS = 1
    cfg.MAX_SL_PIPS = 1000
    bars = _bars(start=1.1000, n=10)
    engine = BacktestEngine(cfg=cfg, symbol_to_bars={"EURUSD": bars})

    # BUY proposal
    prop_buy = TradeProposal(
        symbol="EURUSD", direction="BUY",
        entry_price=bars[5]["close"], stop_loss_price=1.0950,
        take_profit_price=1.1100, timeframe="M15", comment="test", confidence=0.7,
        rationale="test",
    )
    engine._execute_order(prop_buy, 0.1, 5)
    pos = list(engine.open_positions.values())[-1]
    # BUY: entry = close + 2pip × 0.0001 = close + 0.0002
    assert pos.entry_price == pytest.approx(bars[5]["close"] + 0.0002, abs=1e-6)

    # SELL proposal
    prop_sell = TradeProposal(
        symbol="EURUSD", direction="SELL",
        entry_price=bars[6]["close"], stop_loss_price=1.1050,
        take_profit_price=1.0900, timeframe="M15", comment="test", confidence=0.7,
        rationale="test",
    )
    engine._execute_order(prop_sell, 0.1, 6)
    pos = list(engine.open_positions.values())[-1]
    assert pos.entry_price == pytest.approx(bars[6]["close"] - 0.0002, abs=1e-6)


def test_evaluate_open_positions_sl_includes_slippage():
    """SL hit: exit_price = SL - slippage (per BUY) → costo extra reportato."""
    from backtest import BacktestEngine
    from models import PositionInfo

    cfg = _make_cfg(BACKTEST_SPREAD_PIPS=0.0, BACKTEST_COMMISSION_PER_LOT=0.0,
                    BACKTEST_SLIPPAGE_PIPS=1.0)
    bars = [
        {"time": 1700000000 + i*900, "open": 1.1000, "high": 1.1010,
         "low": 1.0980, "close": 1.1005, "tick_volume": 100}
        for i in range(5)
    ]
    # Bar 2 ha low=1.0980 → SL @ 1.0990 viene hit
    engine = BacktestEngine(cfg=cfg, symbol_to_bars={"EURUSD": bars})
    pos = PositionInfo(
        symbol="EURUSD", lots=1.0, direction="BUY",
        entry_price=1.1000, stop_loss=1.0990, take_profit=1.1100,
        profit=0.0, ticket=999,
    )
    engine.open_positions[999] = pos

    engine._evaluate_open_positions(2)

    assert len(engine.trades) == 1
    trade = engine.trades[0]
    assert trade.exit_reason == "SL"
    # exit = 1.0990 - 1pip × 0.0001 = 1.0989
    assert trade.exit_price == pytest.approx(1.0989, abs=1e-6)
    assert trade.slippage_cost_usd > 0


def test_evaluate_open_positions_commission_deducted_from_net():
    """Net profit = gross - commission (round-trip)."""
    from backtest import BacktestEngine
    from models import PositionInfo

    cfg = _make_cfg(BACKTEST_SPREAD_PIPS=0.0, BACKTEST_COMMISSION_PER_LOT=5.0,
                    BACKTEST_SLIPPAGE_PIPS=0.0)
    bars = [
        {"time": 1700000000 + i*900, "open": 1.1000, "high": 1.1110,
         "low": 1.0995, "close": 1.1005, "tick_volume": 100}
        for i in range(5)
    ]
    engine = BacktestEngine(cfg=cfg, symbol_to_bars={"EURUSD": bars})
    pos = PositionInfo(
        symbol="EURUSD", lots=1.0, direction="BUY",
        entry_price=1.1000, stop_loss=1.0900, take_profit=1.1100,
        profit=0.0, ticket=999,
    )
    engine.open_positions[999] = pos

    engine._evaluate_open_positions(2)  # bar.high=1.1110 → TP @ 1.1100 hit

    assert len(engine.trades) == 1
    trade = engine.trades[0]
    assert trade.exit_reason == "TP"
    # Gross: 100 pip × $10 = $1000
    # Commission: $5 × 1.0 lot × 2 (round-trip) = $10
    # Net: $990
    assert trade.gross_profit_usd == pytest.approx(1000.0, abs=1.0)
    assert trade.commission_usd == pytest.approx(10.0, abs=0.01)
    assert trade.net_profit_usd == pytest.approx(990.0, abs=1.0)


def test_calculate_metrics_aggregates_costs():
    """Report aggrega total_spread/commission/slippage/gross/net."""
    now = datetime.now()
    trades = [
        BacktestTrade(
            symbol="EURUSD", direction="BUY",
            entry_time=now, entry_price=1.1000,
            stop_loss=1.0950, take_profit=1.1100, lots=1.0,
            exit_time=now, exit_price=1.1100, exit_reason="TP",
            profit_pct=0.5, profit_r=2.0,
            spread_cost_usd=10.0, commission_usd=10.0, slippage_cost_usd=0.0,
            gross_profit_usd=1000.0, net_profit_usd=980.0,
        ),
        BacktestTrade(
            symbol="EURUSD", direction="SELL",
            entry_time=now, entry_price=1.1000,
            stop_loss=1.1050, take_profit=1.0900, lots=1.0,
            exit_time=now, exit_price=1.1050, exit_reason="SL",
            profit_pct=-0.3, profit_r=-1.0,
            spread_cost_usd=10.0, commission_usd=10.0, slippage_cost_usd=10.0,
            gross_profit_usd=-500.0, net_profit_usd=-520.0,
        ),
    ]
    report = _calculate_metrics(trades, 10000.0)

    assert report.total_spread_cost_usd == 20.0
    assert report.total_commission_usd == 20.0
    assert report.total_slippage_cost_usd == 10.0
    assert report.total_gross_profit_usd == 500.0
    assert report.total_net_profit_usd == 460.0
