"""Test della policy giornaliera dell'Orchestrator (fase 13).

Verifica end-to-end (con agent mockato) che:
- trade + no-trade finali arrivano al target di 5 entro la giornata simulata;
- una decisione con WAIT_FOLLOW_UP seguita da follow-up conta 1 sola volta;
- una volta raggiunto il target, i cicli ordinari successivi non partono;
- il follow-up cycle è focalizzato sul simbolo e sul focus prompt salvati;
- se il follow-up non produce edge, l'esito finale è NO_TRADE;
- ogni ciclo verifica sempre lo stato del conto prima della decisione.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

import scheduler as scheduler_module
from models import (
    AccountState,
    AgentCycleOutcome,
    DelayedFollowUpRequest,
    PositionInfo,
    TradeProposal,
)
from scheduler import DailyRunStateStore, Orchestrator


_TZ_ROME = ZoneInfo("Europe/Rome")


def _account_state(*, with_open: bool = False) -> AccountState:
    open_positions: list[PositionInfo] = []
    if with_open:
        open_positions.append(
            PositionInfo(
                symbol="EURUSD",
                lots=0.10,
                direction="BUY",
                entry_price=1.10000,
                stop_loss=1.09800,
                take_profit=1.10400,
                profit=0.0,
            )
        )
    return AccountState(
        balance=10000.0,
        equity=10000.0,
        free_margin=9500.0,
        open_positions=open_positions,
        today_realized_pnl=0.0,
        starting_balance_of_day=10000.0,
    )


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
        rationale="trend coerente",
    )


def _followup(symbol: str, delay: int = 30, focus: str = "ricontrolla break") -> DelayedFollowUpRequest:
    created = datetime.now(tz=_TZ_ROME)
    return DelayedFollowUpRequest(
        symbol=symbol,
        timeframe="M15",
        delay_minutes=delay,
        reason="attesa setup",
        focus_prompt=focus,
        created_at=created,
        expires_at=created + timedelta(minutes=delay),
        already_delayed=False,
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
    cfg.SYMBOLS = ["EURUSD", "GBPUSD"]
    cfg.TIMEFRAME = "M15"
    cfg.EXECUTION_MODE = "shadow"
    cfg.LOG_FILE = str(tmp_path / "logs" / "agent.log")
    return cfg


@pytest.fixture
def setup(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    agent = MagicMock()
    mt5 = MagicMock()
    mt5.get_account_state.return_value = _account_state(with_open=True)
    log = logging.getLogger("test_daily_orchestrator")
    store = DailyRunStateStore(tmp_path / "trades.db")
    sched = MagicMock()
    orch = Orchestrator(cfg, agent, mt5, log, store, scheduler=sched)
    orch.window.is_open = MagicMock(return_value=True)
    monkeypatch.setattr(scheduler_module, "run_once", MagicMock())
    return cfg, agent, mt5, store, orch, sched


def test_five_decisions_reach_daily_target(setup):
    cfg, agent, _, store, orch, _ = setup
    proposal = _trade_proposal("EURUSD")
    agent.run_market_cycle.side_effect = [
        AgentCycleOutcome(outcome_type="TRADE", proposal=proposal),
        AgentCycleOutcome(outcome_type="NO_TRADE"),
        AgentCycleOutcome(outcome_type="NO_TRADE"),
        AgentCycleOutcome(outcome_type="TRADE", proposal=proposal),
        AgentCycleOutcome(outcome_type="NO_TRADE"),
    ]

    for _ in range(5):
        orch.execute_ordinary_cycle()

    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == cfg.DAILY_TARGET_DECISIONS
    assert state.trade_count == 2
    assert state.no_trade_count == 3
    assert store.is_target_reached(today, cfg.DAILY_TARGET_DECISIONS) is True


def test_target_reached_blocks_subsequent_ordinary_cycles(setup):
    _, agent, _, store, orch, _ = setup
    today = datetime.now(tz=_TZ_ROME).date()
    for _ in range(5):
        store.increment(today, "NO_TRADE")
    agent.run_market_cycle.reset_mock()

    result = orch.execute_ordinary_cycle()

    assert result is None
    agent.run_market_cycle.assert_not_called()


def test_wait_followup_then_no_trade_counts_once(setup):
    _, agent, _, store, orch, sched = setup
    fu = _followup("EURUSD", delay=20)

    # Ciclo 1: agent chiede WAIT_FOLLOW_UP
    agent.run_market_cycle.return_value = AgentCycleOutcome(
        outcome_type="WAIT_FOLLOW_UP",
        follow_up=fu,
    )
    orch.execute_ordinary_cycle()

    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == 0
    sched.add_job.assert_called_once()

    # Follow-up cycle: agent ritorna NO_TRADE (no edge)
    agent.run_market_cycle.return_value = AgentCycleOutcome(outcome_type="NO_TRADE")
    orch.execute_followup_cycle(fu)

    state = store.get_or_create(today)
    assert state.decisions_count == 1
    assert state.no_trade_count == 1
    assert state.trade_count == 0


def test_followup_cycle_focuses_on_saved_symbol_and_focus_prompt(setup):
    _, agent, _, _, orch, _ = setup
    agent.run_market_cycle.return_value = AgentCycleOutcome(outcome_type="NO_TRADE")
    fu = _followup("GBPUSD", delay=15, focus="conferma break 1.2500")

    orch.execute_followup_cycle(fu)

    call = agent.run_market_cycle.call_args
    candidate_symbols = call.args[0]
    assert candidate_symbols == ["GBPUSD"]
    timeframe_arg = call.args[1]
    assert timeframe_arg == "M15"
    followup_arg = call.kwargs.get("followup")
    assert followup_arg is not None
    assert followup_arg.symbol == "GBPUSD"
    assert followup_arg.focus_prompt == "conferma break 1.2500"
    assert followup_arg.already_delayed is True


def test_followup_with_no_edge_results_in_no_trade(setup):
    _, agent, _, store, orch, _ = setup
    agent.run_market_cycle.return_value = AgentCycleOutcome(outcome_type="NO_TRADE")
    fu = _followup("EURUSD", delay=10)

    outcome = orch.execute_followup_cycle(fu)

    assert outcome is not None
    assert outcome.outcome_type == "NO_TRADE"
    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == 1
    assert state.no_trade_count == 1


def test_each_cycle_reads_account_state(setup):
    _, agent, mt5, _, orch, _ = setup
    agent.run_market_cycle.side_effect = [
        AgentCycleOutcome(outcome_type="NO_TRADE"),
        AgentCycleOutcome(outcome_type="NO_TRADE"),
        AgentCycleOutcome(outcome_type="NO_TRADE"),
    ]

    for _ in range(3):
        orch.execute_ordinary_cycle()

    assert mt5.get_account_state.call_count == 3
    # Ogni ciclo passa l'account_state (con posizioni aperte) all'agent.
    for call in agent.run_market_cycle.call_args_list:
        account_arg = call.args[2]
        assert isinstance(account_arg, AccountState)
        assert len(account_arg.open_positions) == 1


def test_followup_cycle_also_reads_account_state(setup):
    _, agent, mt5, _, orch, _ = setup
    agent.run_market_cycle.return_value = AgentCycleOutcome(outcome_type="NO_TRADE")
    fu = _followup("EURUSD", delay=10)

    orch.execute_followup_cycle(fu)

    assert mt5.get_account_state.call_count == 1
    call = agent.run_market_cycle.call_args
    account_arg = call.args[2]
    assert isinstance(account_arg, AccountState)


def test_target_reached_blocks_followup_cycle_too(setup):
    cfg, agent, _, store, orch, _ = setup
    today = datetime.now(tz=_TZ_ROME).date()
    for _ in range(cfg.DAILY_TARGET_DECISIONS):
        store.increment(today, "NO_TRADE")
    agent.run_market_cycle.reset_mock()
    fu = _followup("EURUSD", delay=10)

    result = orch.execute_followup_cycle(fu)

    assert result is None
    agent.run_market_cycle.assert_not_called()


def test_mixed_day_with_followup_reaches_target(setup):
    cfg, agent, _, store, orch, _ = setup
    proposal = _trade_proposal("EURUSD")
    fu = _followup("GBPUSD", delay=20)

    # 4 cicli ordinari finali + 1 follow-up
    agent.run_market_cycle.side_effect = [
        AgentCycleOutcome(outcome_type="TRADE", proposal=proposal),     # 1
        AgentCycleOutcome(outcome_type="NO_TRADE"),                     # 2
        AgentCycleOutcome(outcome_type="WAIT_FOLLOW_UP", follow_up=fu), # 0 (deferred)
        AgentCycleOutcome(outcome_type="NO_TRADE"),                     # 3
        AgentCycleOutcome(outcome_type="TRADE", proposal=proposal),     # 4
    ]
    for _ in range(5):
        orch.execute_ordinary_cycle()

    today = datetime.now(tz=_TZ_ROME).date()
    state = store.get_or_create(today)
    assert state.decisions_count == 4

    # Follow-up arriva e chiude la quinta decisione
    agent.run_market_cycle.side_effect = None
    agent.run_market_cycle.return_value = AgentCycleOutcome(
        outcome_type="TRADE", proposal=proposal,
    )
    orch.execute_followup_cycle(fu)

    state = store.get_or_create(today)
    assert state.decisions_count == cfg.DAILY_TARGET_DECISIONS
    assert state.trade_count == 3
    assert state.no_trade_count == 2
