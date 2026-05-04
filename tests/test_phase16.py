"""Test fase 16 — H24 strategy update.

Copre:
  - StrategyEnvironment (is_intraday_window, is_news_window, is_weekend)
  - IntradayStrategy.evaluate_open_position (HOLD / CLOSE_PROTECT / CLOSE_END_OF_DAY)
  - IntradayStrategy.would_proposal_exceed_drawdown + helper drawdown
  - MultiSymbolScanner: pause / news_window / drawdown_violation / addon flag
  - HeartbeatStore: begin/end cycle, contatori consecutivi
  - IntradayLoopScheduler.run_one_cycle: ordine ops, weekend, paused, fuori finestra,
    news_blocked, gestione posizioni aperte, errori MT5
  - Mt5Client.close_position: usa mt5.order_send con campo `position`
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from models import (
    AccountState,
    OpenPositionVerdict,
    OrderResult,
    PositionInfo,
    SchedulerCycleRecord,
    StrategyOutcome,
    TechnicalSetup,
    TradeProposal,
)
from scanner import MultiSymbolScanner
from scheduler import HeartbeatStore, IntradayLoopScheduler
from strategy import (
    IntradayStrategy,
    StrategyEnvironment,
    estimate_position_risk_amount,
    estimate_proposal_lots,
)


_TZ = ZoneInfo("Europe/Rome")


def _cfg(**overrides):
    cfg = MagicMock()
    cfg.OPERATING_TIMEZONE = "Europe/Rome"
    cfg.OPERATING_WEEKDAYS = [0, 1, 2, 3, 4]
    cfg.OPERATING_START_HOUR = 8
    cfg.OPERATING_END_HOUR = 22
    cfg.INTRADAY_TIMEFRAME = "M15"
    cfg.INTRADAY_LOOKBACK_BARS = 200
    cfg.INTRADAY_START_HOUR = 8
    cfg.INTRADAY_END_HOUR = 20
    cfg.INTRADAY_SYMBOLS = ["EURUSD", "GBPUSD"]
    cfg.INTRADAY_SCAN_TOP_N = 3
    cfg.INTRADAY_SCAN_INTERVAL_MINUTES = 15
    cfg.INTRADAY_FIRST_CYCLE_DELAY_MINUTES = 5
    cfg.PAUSE_TRADING = False
    cfg.DRY_RUN = False
    cfg.AVOID_MAJOR_NEWS_TIMES = True
    cfg.MIN_PROTECT_PROFIT_R_MULTIPLIER = 1.0
    cfg.MAX_DAILY_DRAWDOWN_PERCENT = 2.0
    cfg.ROLLING_DRAWDOWN_WINDOW_HOURS = 24
    cfg.ROLLING_DRAWDOWN_MAX_PERCENT = 3.0
    cfg.CLOSE_BEFORE_END_OF_WINDOW = True
    cfg.MIN_ATR_PIPS = 3.0
    cfg.MAX_ATR_PIPS = 50.0
    cfg.MIN_TREND_STRENGTH = 0.65
    cfg.MIN_BREAKOUT_VOLUME_RATIO = 1.3
    cfg.MIN_RISK_REWARD_RATIO = 1.5
    cfg.MAX_RSI_OVERBOUGHT = 75
    cfg.MIN_RSI_OVERSOLD = 25
    cfg.MIN_CONFIDENCE_TO_PROPOSE = 0.60
    cfg.ENABLE_CANDLESTICK_PATTERNS = False
    cfg.PATTERN_CONFIRMATION_BARS = 2
    cfg.SR_LOOKBACK_BARS = 100
    cfg.SR_TOLERANCE_PIPS = 5.0
    cfg.MAX_DELAY_MINUTES = 120
    cfg.FOLLOWUP_ENABLED = True
    cfg.ENABLE_NEWS_SENTIMENT = False
    cfg.RISK_AMOUNT_MODE = "PERCENT"
    cfg.RISK_PER_TRADE_PERCENT = 0.5
    cfg.RISK_PER_TRADE_AMOUNT = 100.0
    cfg.EXECUTION_MODE = "shadow"
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _account(positions=None, balance=10_000.0) -> AccountState:
    return AccountState(
        balance=balance,
        equity=balance,
        free_margin=balance * 0.95,
        open_positions=positions or [],
        today_realized_pnl=0.0,
        starting_balance_of_day=balance,
    )


def _sym_info(point=0.00001, digits=5, tick_value=1.0, tick_size=0.00001, bid=1.10000, ask=1.10010):
    info = SimpleNamespace()
    info.point = point
    info.digits = digits
    info.trade_tick_value = tick_value
    info.trade_tick_size = tick_size
    info.bid = bid
    info.ask = ask
    info.visible = True
    info.volume_step = 0.01
    return info


# ─────────────────────────────────────────────────────────────────────────────
# StrategyEnvironment
# ─────────────────────────────────────────────────────────────────────────────


def test_environment_intraday_window_inside():
    env = StrategyEnvironment(_cfg())
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)
    assert env.is_intraday_window(monday_10) is True


def test_environment_intraday_window_outside():
    env = StrategyEnvironment(_cfg())
    night_3 = datetime(2026, 4, 27, 3, 0, tzinfo=_TZ)
    end_20 = datetime(2026, 4, 27, 20, 0, tzinfo=_TZ)
    assert env.is_intraday_window(night_3) is False
    assert env.is_intraday_window(end_20) is False  # end_hour esclusivo


def test_environment_weekend_detection():
    env = StrategyEnvironment(_cfg())
    saturday = datetime(2026, 5, 2, 10, 0, tzinfo=_TZ)
    sunday = datetime(2026, 5, 3, 10, 0, tzinfo=_TZ)
    monday = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)
    assert env.is_weekend(saturday) is True
    assert env.is_weekend(sunday) is True
    assert env.is_weekend(monday) is False


def test_environment_news_window_default_false():
    env = StrategyEnvironment(_cfg())
    assert env.is_news_window(datetime(2026, 4, 27, 14, 30, tzinfo=_TZ)) is False


def test_environment_news_window_callable_invoked():
    calls: list[datetime] = []

    def cb(now):
        calls.append(now)
        return True

    env = StrategyEnvironment(_cfg(), news_window_callable=cb)
    now = datetime(2026, 4, 27, 14, 30, tzinfo=_TZ)
    assert env.is_news_window(now) is True
    assert len(calls) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Drawdown helpers
# ─────────────────────────────────────────────────────────────────────────────


def test_estimate_position_risk_amount_basic():
    pos = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=1.09800, take_profit=1.10500,
        profit=0.0, ticket=1,
    )
    info = _sym_info()
    risk = estimate_position_risk_amount(pos, info)
    # distance = 20 pips, lots=0.5, pip_value = 1.0 * 0.0001/0.00001 = 10 → 0.5*10*20=100
    assert risk == pytest.approx(100.0, rel=0.01)


def test_estimate_position_risk_amount_no_sl():
    pos = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=0.0, take_profit=1.10500,
        profit=0.0, ticket=1,
    )
    assert estimate_position_risk_amount(pos, _sym_info()) == 0.0


def test_would_proposal_exceed_drawdown_blocks_when_breaches():
    cfg = _cfg(MAX_DAILY_DRAWDOWN_PERCENT=1.0)
    mt5 = MagicMock()
    mt5.get_symbol_info.return_value = _sym_info()
    strategy = IntradayStrategy(cfg, mt5, logging.getLogger("test_dd"))

    existing = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=1.09800, take_profit=1.10500,
        profit=0.0, ticket=1,
    )  # rischio ~100
    account = _account(positions=[existing])

    proposal = TradeProposal(
        symbol="GBPUSD", direction="BUY",
        entry_price=1.30000, stop_loss_price=1.29800, take_profit_price=1.30500,
        timeframe="M15", comment="t", confidence=0.7, rationale="r",
    )
    exceeds, pct = strategy.would_proposal_exceed_drawdown(proposal, account)
    assert exceeds is True
    assert pct > 1.0


def test_would_proposal_exceed_drawdown_passes_under_threshold():
    cfg = _cfg(MAX_DAILY_DRAWDOWN_PERCENT=5.0)
    mt5 = MagicMock()
    mt5.get_symbol_info.return_value = _sym_info()
    strategy = IntradayStrategy(cfg, mt5, logging.getLogger("test_dd2"))

    account = _account()  # nessuna posizione esistente
    proposal = TradeProposal(
        symbol="EURUSD", direction="BUY",
        entry_price=1.10000, stop_loss_price=1.09800, take_profit_price=1.10500,
        timeframe="M15", comment="t", confidence=0.7, rationale="r",
    )
    exceeds, pct = strategy.would_proposal_exceed_drawdown(proposal, account)
    assert exceeds is False
    assert pct < 5.0


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_open_position
# ─────────────────────────────────────────────────────────────────────────────


def _patch_analyze_technical(strategy, setup_type, direction=None, indicators=None):
    def fake(symbol, account_state):
        return TechnicalSetup(
            symbol=symbol, timeframe="M15",
            setup_type=setup_type, direction=direction,
            entry_price=None, stop_loss=None, take_profit=None,
            confidence=0.7 if setup_type == "READY" else 0.0,
            reason="fake", indicators=indicators or {},
        )
    strategy._analyze_technical = fake


def test_evaluate_open_position_close_end_of_day_outside_window():
    cfg = _cfg()
    mt5 = MagicMock()
    mt5.get_symbol_info.return_value = _sym_info()
    strategy = IntradayStrategy(cfg, mt5, logging.getLogger("eop_eod"))

    pos = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=1.09800, take_profit=1.10500,
        profit=50.0, ticket=42,
    )
    account = _account(positions=[pos])
    monday_22 = datetime(2026, 4, 27, 22, 0, tzinfo=_TZ)  # fuori finestra 8-20
    verdict = strategy.evaluate_open_position(pos, account, now=monday_22)
    assert verdict.action == "CLOSE_END_OF_DAY"
    assert verdict.ticket == 42


def test_evaluate_open_position_close_protect_on_negative_context():
    cfg = _cfg(MIN_PROTECT_PROFIT_R_MULTIPLIER=1.0)
    mt5 = MagicMock()
    mt5.get_symbol_info.return_value = _sym_info()
    strategy = IntradayStrategy(cfg, mt5, logging.getLogger("eop_protect"))
    # contesto NEGATIVO per BUY: setup READY direction SELL
    _patch_analyze_technical(strategy, "READY", direction="SELL")

    pos = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=1.09800, take_profit=1.10500,
        profit=200.0, ticket=99,  # rischio = 100, profitto = 200 → 2R
    )
    account = _account(positions=[pos])
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)
    verdict = strategy.evaluate_open_position(pos, account, now=monday_10)
    assert verdict.action == "CLOSE_PROTECT"
    assert verdict.profit_r_multiple == pytest.approx(2.0, rel=0.05)


def test_evaluate_open_position_hold_when_profit_too_low():
    cfg = _cfg(MIN_PROTECT_PROFIT_R_MULTIPLIER=1.5)
    mt5 = MagicMock()
    mt5.get_symbol_info.return_value = _sym_info()
    strategy = IntradayStrategy(cfg, mt5, logging.getLogger("eop_hold"))
    _patch_analyze_technical(strategy, "READY", direction="SELL")

    pos = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=1.09800, take_profit=1.10500,
        profit=50.0, ticket=99,  # 0.5R di profitto, sotto 1.5R
    )
    account = _account(positions=[pos])
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)
    verdict = strategy.evaluate_open_position(pos, account, now=monday_10)
    assert verdict.action == "HOLD"


def test_evaluate_open_position_hold_when_context_aligned():
    cfg = _cfg(MIN_PROTECT_PROFIT_R_MULTIPLIER=1.0)
    mt5 = MagicMock()
    mt5.get_symbol_info.return_value = _sym_info()
    strategy = IntradayStrategy(cfg, mt5, logging.getLogger("eop_align"))
    # READY same direction → contesto allineato, NON chiudere
    _patch_analyze_technical(strategy, "READY", direction="BUY")

    pos = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=1.09800, take_profit=1.10500,
        profit=300.0, ticket=99,
    )
    account = _account(positions=[pos])
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)
    verdict = strategy.evaluate_open_position(pos, account, now=monday_10)
    assert verdict.action == "HOLD"


# ─────────────────────────────────────────────────────────────────────────────
# Scanner — paused / news / drawdown / addon
# ─────────────────────────────────────────────────────────────────────────────


def _scanner(cfg, strategy=None, mt5=None):
    return MultiSymbolScanner(
        cfg, mt5 or MagicMock(),
        strategy or MagicMock(),
        logging.getLogger("test_scan_p16"),
    )


def test_deep_analyze_respects_pause_flag():
    cfg = _cfg()
    s = _scanner(cfg)
    out = s.deep_analyze_top_candidates([], _account(), paused=True)
    assert out.outcome_type == "NO_TRADE"
    assert out.paused is True


def test_deep_analyze_respects_news_blocked_flag():
    cfg = _cfg()
    s = _scanner(cfg)
    out = s.deep_analyze_top_candidates([], _account(), news_blocked=True)
    assert out.outcome_type == "NO_TRADE"
    assert out.news_blocked is True


def test_deep_analyze_marks_addon_when_existing_position_same_dir():
    cfg = _cfg()
    strategy = MagicMock()
    setup = TechnicalSetup(
        symbol="EURUSD", timeframe="M15", setup_type="READY", direction="BUY",
        entry_price=1.10, stop_loss=1.098, take_profit=1.104,
        confidence=0.8, reason="ok", indicators={},
    )
    strategy.analyze_symbol.return_value = setup
    proposal = TradeProposal(
        symbol="EURUSD", direction="BUY",
        entry_price=1.10, stop_loss_price=1.098, take_profit_price=1.104,
        timeframe="M15", comment="x", confidence=0.8, rationale="r",
    )
    strategy.build_trade_proposal.return_value = proposal
    strategy.is_addon_for.return_value = True
    strategy.would_proposal_exceed_drawdown.return_value = (False, 0.5)

    s = _scanner(cfg, strategy=strategy)
    scan = [SimpleNamespace(symbol="EURUSD", candidate_score=0.9)]
    out = s.deep_analyze_top_candidates(scan, _account())
    assert out.outcome_type == "TRADE"
    assert out.is_addon is True
    assert out.proposal.comment == "python_strategy_addon"
    assert out.proposal.rationale.startswith("ADD-ON: ")


def test_deep_analyze_drawdown_violation_blocks_trade():
    cfg = _cfg()
    strategy = MagicMock()
    setup = TechnicalSetup(
        symbol="EURUSD", timeframe="M15", setup_type="READY", direction="BUY",
        entry_price=1.10, stop_loss=1.098, take_profit=1.104,
        confidence=0.8, reason="ok", indicators={},
    )
    strategy.analyze_symbol.return_value = setup
    proposal = TradeProposal(
        symbol="EURUSD", direction="BUY",
        entry_price=1.10, stop_loss_price=1.098, take_profit_price=1.104,
        timeframe="M15", comment="x", confidence=0.8, rationale="r",
    )
    strategy.build_trade_proposal.return_value = proposal
    strategy.is_addon_for.return_value = False
    strategy.would_proposal_exceed_drawdown.return_value = (True, 4.5)

    s = _scanner(cfg, strategy=strategy)
    scan = [SimpleNamespace(symbol="EURUSD", candidate_score=0.9)]
    out = s.deep_analyze_top_candidates(scan, _account())
    assert out.outcome_type == "NO_TRADE"
    assert out.drawdown_violation is True
    assert out.max_potential_drawdown_percent == pytest.approx(4.5)


# ─────────────────────────────────────────────────────────────────────────────
# HeartbeatStore
# ─────────────────────────────────────────────────────────────────────────────


def test_heartbeat_begin_and_end_cycle(tmp_path):
    store = HeartbeatStore(tmp_path / "hb.db")
    started = datetime.now(tz=_TZ)
    hb_id = store.begin_cycle(started)
    assert hb_id > 0
    ended = started + timedelta(seconds=2)
    duration = store.end_cycle(hb_id, started, ended, "OK", note="ok")
    assert duration == 2000

    state = store.get_state()
    assert state["last_outcome"] == "OK"
    assert state["consecutive_no_trade"] == 0
    assert state["consecutive_errors"] == 0


def test_heartbeat_consecutive_counters(tmp_path):
    store = HeartbeatStore(tmp_path / "hb2.db")
    base = datetime.now(tz=_TZ)
    for i in range(3):
        s = base + timedelta(seconds=i)
        e = s + timedelta(milliseconds=10)
        hb_id = store.begin_cycle(s)
        store.end_cycle(hb_id, s, e, "NO_TRADE")
    assert store.get_state()["consecutive_no_trade"] == 3

    s = base + timedelta(seconds=10)
    e = s + timedelta(milliseconds=10)
    hb_id = store.begin_cycle(s)
    store.end_cycle(hb_id, s, e, "ERROR", error_type="X", error_message="boom")
    state = store.get_state()
    assert state["consecutive_errors"] == 1
    assert state["consecutive_no_trade"] == 0


def test_heartbeat_last_heartbeats_sorted_desc(tmp_path):
    store = HeartbeatStore(tmp_path / "hb3.db")
    base = datetime.now(tz=_TZ)
    for i, oc in enumerate(["OK", "NO_TRADE", "ERROR"]):
        s = base + timedelta(seconds=i)
        e = s + timedelta(milliseconds=10)
        hb_id = store.begin_cycle(s)
        store.end_cycle(hb_id, s, e, oc)
    rows = store.last_heartbeats(limit=2)
    assert len(rows) == 2
    assert rows[0]["outcome"] == "ERROR"
    assert rows[1]["outcome"] == "NO_TRADE"


# ─────────────────────────────────────────────────────────────────────────────
# IntradayLoopScheduler.run_one_cycle
# ─────────────────────────────────────────────────────────────────────────────


def _build_loop(cfg, tmp_path, *, strategy=None, scanner_obj=None, mt5=None, env=None):
    strategy = strategy or MagicMock()
    if env is None:
        env = StrategyEnvironment(cfg)
    strategy.env = env
    scanner_obj = scanner_obj or MagicMock()
    mt5 = mt5 or MagicMock()
    mt5.get_account_state.return_value = _account()
    store = HeartbeatStore(tmp_path / "hb_loop.db")
    loop = IntradayLoopScheduler(
        cfg=cfg,
        mt5_client=mt5,
        strategy=strategy,
        scanner=scanner_obj,
        log=logging.getLogger("test_loop_p16"),
        heartbeat_store=store,
        environment=env,
    )
    return loop, mt5, scanner_obj, strategy, store


def test_loop_skips_on_weekend(tmp_path, monkeypatch):
    cfg = _cfg()
    saturday = datetime(2026, 5, 2, 10, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return saturday

    loop, mt5, scanner, strategy, store = _build_loop(cfg, tmp_path)
    monkeypatch.setattr("scheduler.datetime", FakeDT)
    rec = loop.run_one_cycle()
    assert rec.outcome == "WEEKEND"
    scanner.scan_universe.assert_not_called()
    mt5.get_account_state.assert_not_called()


def test_loop_skips_when_paused(tmp_path, monkeypatch):
    cfg = _cfg(PAUSE_TRADING=True)
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return monday_10

    loop, mt5, scanner, strategy, _ = _build_loop(cfg, tmp_path)
    monkeypatch.setattr("scheduler.datetime", FakeDT)
    rec = loop.run_one_cycle()
    assert rec.outcome == "PAUSED"
    scanner.scan_universe.assert_not_called()
    # account_state letto per gestire posizioni aperte
    mt5.get_account_state.assert_called()


def test_loop_skips_outside_window(tmp_path, monkeypatch):
    cfg = _cfg()
    monday_03 = datetime(2026, 4, 27, 3, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return monday_03

    loop, mt5, scanner, strategy, _ = _build_loop(cfg, tmp_path)
    monkeypatch.setattr("scheduler.datetime", FakeDT)
    rec = loop.run_one_cycle()
    assert rec.outcome == "OUT_OF_WINDOW"
    scanner.scan_universe.assert_not_called()


def test_loop_news_blocked_skips_trades(tmp_path, monkeypatch):
    cfg = _cfg()
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return monday_10

    env = StrategyEnvironment(cfg, news_window_callable=lambda now: True)
    loop, mt5, scanner, strategy, _ = _build_loop(cfg, tmp_path, env=env)
    monkeypatch.setattr("scheduler.datetime", FakeDT)
    rec = loop.run_one_cycle()
    assert rec.outcome == "NEWS_BLOCKED"
    scanner.scan_universe.assert_not_called()


def test_loop_runs_trade_via_run_once(tmp_path, monkeypatch):
    cfg = _cfg()
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return monday_10

    proposal = TradeProposal(
        symbol="EURUSD", direction="BUY",
        entry_price=1.10, stop_loss_price=1.098, take_profit_price=1.104,
        timeframe="M15", comment="t", confidence=0.8, rationale="r",
    )
    outcome_obj = StrategyOutcome(
        outcome_type="TRADE", proposal=proposal,
        timestamp=monday_10, note="ok",
    )

    loop, mt5, scanner, strategy, _ = _build_loop(cfg, tmp_path)
    scanner.scan_universe.return_value = [SimpleNamespace(symbol="EURUSD", candidate_score=0.9)]
    scanner.deep_analyze_top_candidates.return_value = outcome_obj

    fake_run_once = MagicMock()
    monkeypatch.setattr("scheduler.run_once", fake_run_once)
    monkeypatch.setattr("scheduler.datetime", FakeDT)

    rec = loop.run_one_cycle()
    assert rec.outcome == "OK"
    fake_run_once.assert_called_once()


def test_loop_dry_run_does_not_send_orders(tmp_path, monkeypatch):
    cfg = _cfg(DRY_RUN=True)
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return monday_10

    proposal = TradeProposal(
        symbol="EURUSD", direction="BUY",
        entry_price=1.10, stop_loss_price=1.098, take_profit_price=1.104,
        timeframe="M15", comment="t", confidence=0.8, rationale="r",
    )
    outcome_obj = StrategyOutcome(
        outcome_type="TRADE", proposal=proposal,
        timestamp=monday_10, note="ok",
    )

    loop, mt5, scanner, strategy, _ = _build_loop(cfg, tmp_path)
    scanner.scan_universe.return_value = [SimpleNamespace(symbol="EURUSD", candidate_score=0.9)]
    scanner.deep_analyze_top_candidates.return_value = outcome_obj

    fake_run_once = MagicMock()
    monkeypatch.setattr("scheduler.run_once", fake_run_once)
    monkeypatch.setattr("scheduler.datetime", FakeDT)

    rec = loop.run_one_cycle()
    assert rec.outcome == "DRY_RUN"
    fake_run_once.assert_not_called()


def test_loop_manages_open_positions_close_protect(tmp_path, monkeypatch):
    cfg = _cfg()
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return monday_10

    pos = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=1.09800, take_profit=1.10500,
        profit=200.0, ticket=777,
    )
    strategy = MagicMock()
    strategy.evaluate_open_position.return_value = OpenPositionVerdict(
        symbol="EURUSD", ticket=777, action="CLOSE_PROTECT",
        reason="contesto_neg", profit_r_multiple=2.0,
    )
    loop, mt5, scanner, _, _ = _build_loop(cfg, tmp_path, strategy=strategy)
    mt5.get_account_state.return_value = _account(positions=[pos])
    mt5.close_position.return_value = OrderResult(success=True, order_id=42)
    scanner.scan_universe.return_value = []
    scanner.deep_analyze_top_candidates.return_value = StrategyOutcome(
        outcome_type="NO_TRADE", note="empty",
    )

    monkeypatch.setattr("scheduler.datetime", FakeDT)
    rec = loop.run_one_cycle()
    mt5.close_position.assert_called_once_with(777)
    assert rec.outcome in ("NO_TRADE", "OK")


def test_loop_dry_run_skips_real_close(tmp_path, monkeypatch):
    cfg = _cfg(DRY_RUN=True)
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return monday_10

    pos = PositionInfo(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10000, stop_loss=1.09800, take_profit=1.10500,
        profit=200.0, ticket=777,
    )
    strategy = MagicMock()
    strategy.evaluate_open_position.return_value = OpenPositionVerdict(
        symbol="EURUSD", ticket=777, action="CLOSE_PROTECT",
        reason="contesto_neg",
    )
    loop, mt5, scanner, _, _ = _build_loop(cfg, tmp_path, strategy=strategy)
    mt5.get_account_state.return_value = _account(positions=[pos])
    scanner.scan_universe.return_value = []
    scanner.deep_analyze_top_candidates.return_value = StrategyOutcome(
        outcome_type="NO_TRADE", note="empty",
    )

    monkeypatch.setattr("scheduler.datetime", FakeDT)
    loop.run_one_cycle()
    mt5.close_position.assert_not_called()


def test_loop_handles_account_state_failure(tmp_path, monkeypatch):
    cfg = _cfg()
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return monday_10

    loop, mt5, scanner, _, store = _build_loop(cfg, tmp_path)
    mt5.get_account_state.side_effect = RuntimeError("MT5 down")
    monkeypatch.setattr("scheduler.datetime", FakeDT)

    rec = loop.run_one_cycle()
    assert rec.outcome == "ERROR"
    assert rec.error_type == "RuntimeError"
    assert "MT5 down" in (rec.error_message or "")
    scanner.scan_universe.assert_not_called()
    state = store.get_state()
    assert state["consecutive_errors"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Mt5Client.close_position
# ─────────────────────────────────────────────────────────────────────────────


def test_close_position_uses_position_field(monkeypatch):
    import mt5_client as mt5_module

    pos_obj = SimpleNamespace(
        ticket=12345, symbol="EURUSD", volume=0.5, type=0,  # 0 = POSITION_TYPE_BUY
        price_open=1.10, sl=1.098, tp=1.104, profit=10.0,
    )
    tick = SimpleNamespace(bid=1.09950, ask=1.09960)
    fake_result = SimpleNamespace(
        retcode=10009,  # TRADE_RETCODE_DONE
        order=99999, comment="ok",
    )

    sym_info = SimpleNamespace(visible=True, filling_mode=0)
    fake_mt5 = SimpleNamespace(
        positions_get=MagicMock(return_value=[pos_obj]),
        symbol_info=MagicMock(return_value=sym_info),
        symbol_select=MagicMock(return_value=True),
        symbol_info_tick=MagicMock(return_value=tick),
        order_send=MagicMock(return_value=fake_result),
        last_error=MagicMock(return_value=(0, "")),
        POSITION_TYPE_BUY=0,
        POSITION_TYPE_SELL=1,
        ORDER_TYPE_BUY=0,
        ORDER_TYPE_SELL=1,
        TRADE_ACTION_DEAL=1,
        ORDER_FILLING_FOK=0,
        ORDER_FILLING_IOC=1,
        ORDER_FILLING_RETURN=2,
        ORDER_TIME_GTC=0,
        TRADE_RETCODE_DONE=10009,
    )
    monkeypatch.setattr(mt5_module, "mt5", fake_mt5)

    cfg = _cfg()
    client = mt5_module.Mt5Client(cfg)
    result = client.close_position(12345)

    assert result.success is True
    assert result.order_id == 99999
    sent = fake_mt5.order_send.call_args.args[0]
    assert sent["action"] == 1
    assert sent["position"] == 12345
    assert sent["type"] == 1  # opposite (SELL) per chiudere BUY
    assert sent["price"] == pytest.approx(1.09950)  # bid
    assert sent["volume"] == 0.5


def test_close_position_position_not_found(monkeypatch):
    import mt5_client as mt5_module

    fake_mt5 = SimpleNamespace(
        positions_get=MagicMock(return_value=[]),
        symbol_info_tick=MagicMock(),
        order_send=MagicMock(),
        last_error=MagicMock(return_value=(0, "")),
        POSITION_TYPE_BUY=0, POSITION_TYPE_SELL=1,
        ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1,
        TRADE_ACTION_DEAL=1, ORDER_FILLING_RETURN=2,
        ORDER_TIME_GTC=0, TRADE_RETCODE_DONE=10009,
    )
    monkeypatch.setattr(mt5_module, "mt5", fake_mt5)
    client = mt5_module.Mt5Client(_cfg())
    result = client.close_position(99999)
    assert result.success is False
    assert "non trovata" in (result.error_message or "")
    fake_mt5.order_send.assert_not_called()
