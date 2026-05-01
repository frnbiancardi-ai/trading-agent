"""Test StrategyRunner: adapter run_market_cycle per Orchestrator fase 13."""
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from models import (
    AccountState,
    DelayedFollowUpRequest,
    ScanResult,
    StrategyOutcome,
    TechnicalSetup,
    TradeProposal,
)
from scanner import StrategyRunner


def _make_cfg(**overrides):
    cfg = MagicMock()
    cfg.MIN_CONFIDENCE_TO_PROPOSE = 0.60
    cfg.INTRADAY_TIMEFRAME = "M15"
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _account() -> AccountState:
    return AccountState(
        balance=10000.0, equity=10000.0, free_margin=9500.0,
        open_positions=[], today_realized_pnl=0.0,
        starting_balance_of_day=10000.0,
    )


def _ready_setup(symbol: str = "EURUSD", conf: float = 0.75) -> TechnicalSetup:
    return TechnicalSetup(
        symbol=symbol, timeframe="M15", setup_type="READY", direction="BUY",
        entry_price=1.10000, stop_loss=1.09900, take_profit=1.10200,
        confidence=conf, reason="strong",
        indicators={"risk_reward": 2.0},
    )


def _none_setup(symbol: str = "EURUSD") -> TechnicalSetup:
    return TechnicalSetup(
        symbol=symbol, timeframe="M15", setup_type="NONE", direction=None,
        entry_price=None, stop_loss=None, take_profit=None,
        confidence=0.0, reason="weak",
    )


def _proposal(symbol: str = "EURUSD") -> TradeProposal:
    return TradeProposal(
        symbol=symbol, direction="BUY", entry_price=1.10000,
        stop_loss_price=1.09900, take_profit_price=1.10200,
        timeframe="M15", comment="python_strategy", confidence=0.75,
        rationale="strong",
    )


def _followup(symbol: str = "EURUSD") -> DelayedFollowUpRequest:
    now = datetime.now()
    return DelayedFollowUpRequest(
        symbol=symbol, timeframe="M15", delay_minutes=30, reason="approaching",
        focus_prompt="re-analyze", created_at=now,
        expires_at=now + timedelta(minutes=30), already_delayed=True,
    )


def test_run_market_cycle_ordinary_returns_trade():
    cfg = _make_cfg()
    strategy = MagicMock()
    scanner = MagicMock()
    scanner.scan_universe.return_value = [
        ScanResult(symbol="EURUSD", trend_bias="BULLISH", momentum_bias="BULLISH",
                   volatility_state="NORMAL", spread_state="ACCEPTABLE",
                   regime="TREND", candidate_score=0.8, warnings=[]),
    ]
    scanner.deep_analyze_top_candidates.return_value = StrategyOutcome(
        outcome_type="TRADE", proposal=_proposal(), follow_up=None,
        scan_results=[], timestamp=datetime.now(), note="ok",
    )
    runner = StrategyRunner(cfg, strategy, scanner, logging.getLogger("t"))

    outcome = runner.run_market_cycle(["EURUSD", "GBPUSD"], "M15", _account())

    assert outcome.outcome_type == "TRADE"
    assert outcome.proposal.symbol == "EURUSD"
    scanner.scan_universe.assert_called_once_with(["EURUSD", "GBPUSD"])


def test_run_market_cycle_ordinary_returns_no_trade():
    cfg = _make_cfg()
    strategy = MagicMock()
    scanner = MagicMock()
    scanner.scan_universe.return_value = []
    scanner.deep_analyze_top_candidates.return_value = StrategyOutcome(
        outcome_type="NO_TRADE", proposal=None, follow_up=None,
        scan_results=[], timestamp=datetime.now(), note="empty",
    )
    runner = StrategyRunner(cfg, strategy, scanner, logging.getLogger("t"))

    outcome = runner.run_market_cycle(["EURUSD"], "M15", _account())
    assert outcome.outcome_type == "NO_TRADE"


def test_run_market_cycle_followup_ready_returns_trade():
    cfg = _make_cfg()
    strategy = MagicMock()
    strategy.analyze_symbol.return_value = _ready_setup("GBPUSD", conf=0.80)
    strategy.build_trade_proposal.return_value = _proposal("GBPUSD")
    scanner = MagicMock()
    runner = StrategyRunner(cfg, strategy, scanner, logging.getLogger("t"))

    outcome = runner.run_market_cycle(["GBPUSD"], "M15", _account(), followup=_followup("GBPUSD"))

    assert outcome.outcome_type == "TRADE"
    assert outcome.proposal.symbol == "GBPUSD"
    scanner.scan_universe.assert_not_called()
    strategy.analyze_symbol.assert_called_once_with("GBPUSD", _account())


def test_run_market_cycle_followup_low_confidence_no_trade():
    cfg = _make_cfg(MIN_CONFIDENCE_TO_PROPOSE=0.80)
    strategy = MagicMock()
    strategy.analyze_symbol.return_value = _ready_setup("EURUSD", conf=0.65)
    scanner = MagicMock()
    runner = StrategyRunner(cfg, strategy, scanner, logging.getLogger("t"))

    outcome = runner.run_market_cycle(["EURUSD"], "M15", _account(), followup=_followup())

    assert outcome.outcome_type == "NO_TRADE"
    strategy.build_trade_proposal.assert_not_called()


def test_run_market_cycle_followup_none_setup_returns_no_trade():
    cfg = _make_cfg()
    strategy = MagicMock()
    strategy.analyze_symbol.return_value = _none_setup("EURUSD")
    scanner = MagicMock()
    runner = StrategyRunner(cfg, strategy, scanner, logging.getLogger("t"))

    outcome = runner.run_market_cycle(["EURUSD"], "M15", _account(), followup=_followup())

    assert outcome.outcome_type == "NO_TRADE"


def test_run_market_cycle_propagates_wait_followup():
    cfg = _make_cfg()
    strategy = MagicMock()
    scanner = MagicMock()
    fu = _followup("EURUSD")
    scanner.scan_universe.return_value = []
    scanner.deep_analyze_top_candidates.return_value = StrategyOutcome(
        outcome_type="WAIT_FOLLOW_UP", proposal=None, follow_up=fu,
        scan_results=[], timestamp=datetime.now(), note="forming",
    )
    runner = StrategyRunner(cfg, strategy, scanner, logging.getLogger("t"))

    outcome = runner.run_market_cycle(["EURUSD"], "M15", _account())

    assert outcome.outcome_type == "WAIT_FOLLOW_UP"
    assert outcome.follow_up is fu
