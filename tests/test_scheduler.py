"""Test dello scheduler e dei suoi componenti (fase 13).

Copre operating_slots, OperatingWindow, DailyRunStateStore, build_scheduler
(slot cron), Orchestrator (lock anti-overlap, follow-up one-per-day, target
giornaliero) e clamp del delay > 120 lato ClaudeAgent.

Niente network, niente MT5 reale: BlockingScheduler non viene mai start()ato,
quindi `add_job` è sicuro e non blocca.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

import scheduler as scheduler_module
from claude_agent import ClaudeAgent
from models import (
    AccountState,
    AgentCycleOutcome,
    DelayedFollowUpRequest,
    TradeProposal,
)
from scheduler import (
    DailyRunStateStore,
    OperatingWindow,
    Orchestrator,
    build_scheduler,
    operating_slots,
)


_TZ_ROME = ZoneInfo("Europe/Rome")


def _account_state() -> AccountState:
    return AccountState(
        balance=10000.0,
        equity=10000.0,
        free_margin=9500.0,
        open_positions=[],
        today_realized_pnl=0.0,
        starting_balance_of_day=10000.0,
    )


def _make_cfg(tmp_path) -> MagicMock:
    cfg = MagicMock()
    cfg.OPERATING_TIMEZONE = "Europe/Rome"
    cfg.OPERATING_START_HOUR = 8
    cfg.OPERATING_END_HOUR = 22
    cfg.OPERATING_WEEKDAYS = [0, 1, 2, 3, 4]
    cfg.MAIN_CYCLE_HOURS = 3
    cfg.DAILY_TARGET_DECISIONS = 5
    cfg.MAX_DELAY_MINUTES = 120
    cfg.MAX_SYMBOLS_TO_DEEPEN = 3
    cfg.FOLLOWUP_ENABLED = True
    cfg.SCHEDULER_POLL_SECONDS = 5
    cfg.SYMBOLS = ["EURUSD", "GBPUSD"]
    cfg.TIMEFRAME = "M15"
    cfg.EXECUTION_MODE = "shadow"
    cfg.LOG_FILE = str(tmp_path / "logs" / "agent.log")
    cfg.MIN_SL_PIPS = 8
    cfg.MAX_SL_PIPS = 80
    cfg.MAX_LOTS_PER_TRADE = 0.3
    cfg.RISK_MODE = "CONSERVATIVE"
    cfg.CLAUDE_API_KEY = "test-key"
    cfg.CLAUDE_MODEL = "claude-test"
    cfg.CLAUDE_MAX_TOKENS = 1024
    cfg.CLAUDE_TEMPERATURE = 0.2
    return cfg


def _make_orchestrator(cfg, tmp_path, *, scheduler=None):
    agent = MagicMock()
    mt5 = MagicMock()
    mt5.get_account_state.return_value = _account_state()
    log = logging.getLogger("test_scheduler")
    store = DailyRunStateStore(tmp_path / "trades.db")
    orch = Orchestrator(cfg, agent, mt5, log, store, scheduler=scheduler)
    # finestra operativa sempre aperta nei test, salvo override esplicito
    orch.window.is_open = MagicMock(return_value=True)
    return orch, agent, mt5, store


def _trade_proposal(symbol: str = "EURUSD") -> TradeProposal:
    return TradeProposal(
        symbol=symbol,
        direction="BUY",
        entry_price=1.10000,
        stop_loss_price=1.09800,
        take_profit_price=1.10400,
        timeframe="M15",
        comment="claude_scanner",
        confidence=0.7,
        rationale="trend rialzista coerente",
    )


def _followup(symbol: str = "EURUSD", delay: int = 30) -> DelayedFollowUpRequest:
    created = datetime.now(tz=_TZ_ROME)
    return DelayedFollowUpRequest(
        symbol=symbol,
        timeframe="M15",
        delay_minutes=delay,
        reason="attesa break",
        focus_prompt="ricontrollare break livello",
        created_at=created,
        expires_at=created + timedelta(minutes=delay),
        already_delayed=False,
    )


# ---------- operating_slots & OperatingWindow ----------


def test_operating_slots_default_window(tmp_path):
    cfg = _make_cfg(tmp_path)
    assert operating_slots(cfg) == [8, 11, 14, 17, 20]


def test_operating_window_open_during_business_hours(tmp_path):
    cfg = _make_cfg(tmp_path)
    win = OperatingWindow(cfg)
    monday_10 = datetime(2026, 4, 27, 10, 0, tzinfo=_TZ_ROME)  # lunedì
    assert win.is_open(monday_10) is True


def test_operating_window_closed_on_saturday(tmp_path):
    cfg = _make_cfg(tmp_path)
    win = OperatingWindow(cfg)
    saturday_10 = datetime(2026, 5, 2, 10, 0, tzinfo=_TZ_ROME)
    assert win.is_open(saturday_10) is False


def test_operating_window_closed_before_start_hour(tmp_path):
    cfg = _make_cfg(tmp_path)
    win = OperatingWindow(cfg)
    monday_07 = datetime(2026, 4, 27, 7, 30, tzinfo=_TZ_ROME)
    assert win.is_open(monday_07) is False


def test_operating_window_end_hour_is_exclusive(tmp_path):
    cfg = _make_cfg(tmp_path)
    win = OperatingWindow(cfg)
    monday_22 = datetime(2026, 4, 27, 22, 0, tzinfo=_TZ_ROME)
    assert win.is_open(monday_22) is False


# ---------- DailyRunStateStore ----------


def test_daily_store_initial_state_is_zero(tmp_path):
    store = DailyRunStateStore(tmp_path / "trades.db")
    state = store.get_or_create(date(2026, 4, 30))
    assert state.decisions_count == 0
    assert state.trade_count == 0
    assert state.no_trade_count == 0


def test_daily_store_increment_trade(tmp_path):
    store = DailyRunStateStore(tmp_path / "trades.db")
    today = date(2026, 4, 30)
    store.increment(today, "TRADE")
    state = store.get_or_create(today)
    assert state.decisions_count == 1
    assert state.trade_count == 1
    assert state.no_trade_count == 0


def test_daily_store_increment_no_trade(tmp_path):
    store = DailyRunStateStore(tmp_path / "trades.db")
    today = date(2026, 4, 30)
    store.increment(today, "NO_TRADE")
    state = store.get_or_create(today)
    assert state.decisions_count == 1
    assert state.no_trade_count == 1
    assert state.trade_count == 0


def test_daily_store_unknown_outcome_is_noop(tmp_path):
    store = DailyRunStateStore(tmp_path / "trades.db")
    today = date(2026, 4, 30)
    store.increment(today, "WAIT_FOLLOW_UP")
    state = store.get_or_create(today)
    assert state.decisions_count == 0


def test_daily_store_target_reached(tmp_path):
    store = DailyRunStateStore(tmp_path / "trades.db")
    today = date(2026, 4, 30)
    for _ in range(5):
        store.increment(today, "NO_TRADE")
    assert store.is_target_reached(today, 5) is True
    assert store.is_target_reached(today, 6) is False


# ---------- build_scheduler ----------


def test_build_scheduler_creates_cron_for_5_slots(tmp_path):
    cfg = _make_cfg(tmp_path)
    orch, _, _, _ = _make_orchestrator(cfg, tmp_path)
    sched = build_scheduler(cfg, orch)
    try:
        jobs = sched.get_jobs()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.id == "ordinary_cycle"
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)
        text = str(trigger)
        assert "day_of_week='0,1,2,3,4'" in text
        assert "hour='8,11,14,17,20'" in text
        assert "minute='0'" in text
    finally:
        if sched.running:
            sched.shutdown(wait=False)


def test_build_scheduler_attaches_scheduler_to_orchestrator(tmp_path):
    cfg = _make_cfg(tmp_path)
    orch, _, _, _ = _make_orchestrator(cfg, tmp_path)
    assert orch.scheduler is None
    sched = build_scheduler(cfg, orch)
    try:
        assert orch.scheduler is sched
    finally:
        if sched.running:
            sched.shutdown(wait=False)


# ---------- Orchestrator: gate ----------


def test_orchestrator_skips_when_window_closed(tmp_path):
    cfg = _make_cfg(tmp_path)
    orch, agent, _, _ = _make_orchestrator(cfg, tmp_path)
    orch.window.is_open = MagicMock(return_value=False)

    result = orch.execute_ordinary_cycle()

    assert result is None
    agent.run_market_cycle.assert_not_called()


def test_orchestrator_skips_when_cycle_already_active(tmp_path):
    cfg = _make_cfg(tmp_path)
    orch, agent, _, _ = _make_orchestrator(cfg, tmp_path)
    orch._cycle_active = True

    result = orch.execute_ordinary_cycle()

    assert result is None
    agent.run_market_cycle.assert_not_called()


def test_orchestrator_skips_when_target_reached(tmp_path):
    cfg = _make_cfg(tmp_path)
    orch, agent, _, store = _make_orchestrator(cfg, tmp_path)
    today = datetime.now(tz=_TZ_ROME).date()
    for _ in range(cfg.DAILY_TARGET_DECISIONS):
        store.increment(today, "NO_TRADE")

    result = orch.execute_ordinary_cycle()

    assert result is None
    agent.run_market_cycle.assert_not_called()


# ---------- Orchestrator: outcomes ----------


def test_orchestrator_trade_outcome_runs_execution_and_counts(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    orch, agent, _, store = _make_orchestrator(cfg, tmp_path)
    fake_run_once = MagicMock()
    monkeypatch.setattr(scheduler_module, "run_once", fake_run_once)

    proposal = _trade_proposal("EURUSD")
    agent.run_market_cycle.return_value = AgentCycleOutcome(
        outcome_type="TRADE",
        proposal=proposal,
    )

    result = orch.execute_ordinary_cycle()

    assert result is not None
    assert result.outcome_type == "TRADE"
    fake_run_once.assert_called_once()
    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == 1
    assert state.trade_count == 1


def test_orchestrator_no_trade_outcome_counts(tmp_path):
    cfg = _make_cfg(tmp_path)
    orch, agent, _, store = _make_orchestrator(cfg, tmp_path)
    agent.run_market_cycle.return_value = AgentCycleOutcome(outcome_type="NO_TRADE")

    orch.execute_ordinary_cycle()

    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == 1
    assert state.no_trade_count == 1


def test_orchestrator_wait_followup_does_not_count(tmp_path):
    cfg = _make_cfg(tmp_path)
    mock_sched = MagicMock()
    orch, agent, _, store = _make_orchestrator(cfg, tmp_path, scheduler=mock_sched)
    fu = _followup("EURUSD", delay=30)
    agent.run_market_cycle.return_value = AgentCycleOutcome(
        outcome_type="WAIT_FOLLOW_UP",
        follow_up=fu,
    )

    orch.execute_ordinary_cycle()

    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == 0
    mock_sched.add_job.assert_called_once()


def test_orchestrator_followup_one_shot_uses_date_trigger(tmp_path):
    cfg = _make_cfg(tmp_path)
    mock_sched = MagicMock()
    orch, agent, _, _ = _make_orchestrator(cfg, tmp_path, scheduler=mock_sched)
    fu = _followup("EURUSD", delay=45)
    agent.run_market_cycle.return_value = AgentCycleOutcome(
        outcome_type="WAIT_FOLLOW_UP",
        follow_up=fu,
    )

    orch.execute_ordinary_cycle()

    args, kwargs = mock_sched.add_job.call_args
    assert isinstance(kwargs["trigger"], DateTrigger)
    assert kwargs["id"].startswith("followup-EURUSD-")
    assert kwargs["replace_existing"] is True


def test_orchestrator_followup_only_once_per_opportunity_per_day(tmp_path):
    cfg = _make_cfg(tmp_path)
    mock_sched = MagicMock()
    orch, agent, _, store = _make_orchestrator(cfg, tmp_path, scheduler=mock_sched)
    fu = _followup("EURUSD", delay=30)
    agent.run_market_cycle.return_value = AgentCycleOutcome(
        outcome_type="WAIT_FOLLOW_UP",
        follow_up=fu,
    )

    orch.execute_ordinary_cycle()
    orch.execute_ordinary_cycle()

    assert mock_sched.add_job.call_count == 1
    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == 1
    assert state.no_trade_count == 1


def test_orchestrator_followup_disabled_downgrades_to_no_trade(tmp_path):
    cfg = _make_cfg(tmp_path)
    cfg.FOLLOWUP_ENABLED = False
    mock_sched = MagicMock()
    orch, agent, _, store = _make_orchestrator(cfg, tmp_path, scheduler=mock_sched)
    fu = _followup("EURUSD", delay=30)
    agent.run_market_cycle.return_value = AgentCycleOutcome(
        outcome_type="WAIT_FOLLOW_UP",
        follow_up=fu,
    )

    orch.execute_ordinary_cycle()

    mock_sched.add_job.assert_not_called()
    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == 1
    assert state.no_trade_count == 1


def test_orchestrator_followup_cycle_marks_already_delayed(tmp_path):
    cfg = _make_cfg(tmp_path)
    orch, agent, _, _ = _make_orchestrator(cfg, tmp_path)
    agent.run_market_cycle.return_value = AgentCycleOutcome(outcome_type="NO_TRADE")
    fu = _followup("GBPUSD", delay=30)

    orch.execute_followup_cycle(fu)

    call = agent.run_market_cycle.call_args
    candidate_symbols = call.args[0]
    assert candidate_symbols == ["GBPUSD"]
    followup_arg = call.kwargs.get("followup")
    assert followup_arg is not None
    assert followup_arg.already_delayed is True


# ---------- ClaudeAgent: clamp delay > 120 ----------


def _tool_use_block(tool_id: str, name: str, input_: dict):
    block = SimpleNamespace()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_
    return block


def _text_block(text: str):
    block = SimpleNamespace()
    block.type = "text"
    block.text = text
    return block


def _make_response(stop_reason: str, content: list):
    resp = SimpleNamespace()
    resp.stop_reason = stop_reason
    resp.content = content
    return resp


def test_agent_clamps_followup_delay_above_120(tmp_path):
    cfg = _make_cfg(tmp_path)
    cfg.MAX_DELAY_MINUTES = 120
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = []
    mt5.get_symbol_info.return_value = None
    agent = ClaudeAgent(cfg, mt5, logging.getLogger("test_clamp"))
    agent.client = MagicMock()

    fu_block = _tool_use_block(
        "tu_fu",
        "request_followup",
        {
            "symbol": "EURUSD",
            "delay_minutes": 999,
            "reason": "attesa break",
            "focus_prompt": "ricontrolla break livello",
        },
    )
    agent.client.messages.create.side_effect = [
        _make_response("tool_use", [fu_block]),
        _make_response("end_turn", [_text_block("done")]),
    ]

    outcome = agent._run_market_scan_internal(
        ["EURUSD"], "M15", _account_state(),
    )

    assert outcome.outcome_type == "WAIT_FOLLOW_UP"
    assert outcome.follow_up is not None
    assert outcome.follow_up.delay_minutes == 120


def test_agent_rejects_second_followup_when_already_delayed(tmp_path):
    cfg = _make_cfg(tmp_path)
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = []
    mt5.get_symbol_info.return_value = None
    agent = ClaudeAgent(cfg, mt5, logging.getLogger("test_already"))
    agent.client = MagicMock()

    fu_block = _tool_use_block(
        "tu_fu2",
        "request_followup",
        {
            "symbol": "EURUSD",
            "delay_minutes": 30,
            "reason": "second delay",
            "focus_prompt": "x",
        },
    )
    agent.client.messages.create.side_effect = [
        _make_response("tool_use", [fu_block]),
        _make_response("end_turn", [_text_block("NO_TRADE\nedge non confermato")]),
    ]

    existing_followup = _followup("EURUSD", delay=20)
    outcome = agent._run_market_scan_internal(
        ["EURUSD"], "M15", _account_state(), followup=existing_followup,
    )

    # In followup_mode l'agent NON deve produrre WAIT_FOLLOW_UP: la richiesta
    # viene rifiutata via tool_result e l'esito finale è NO_TRADE.
    assert outcome.outcome_type == "NO_TRADE"
