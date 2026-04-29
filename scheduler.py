"""Scheduler e orchestratore continuo per trading-agent (fase 13).

Componenti:
- DailyRunStateStore: persistenza SQLite del contatore giornaliero
  (tabella daily_run_state in logs/trades.db).
- OperatingWindow: helper per verificare se l'istante è nella finestra
  operativa (giorni della settimana + ore).
- Orchestrator: coordina cycle ordinari e follow-up, applica daily
  target, lock anti-overlap, tracking di una sola opportunità ritardata
  per simbolo per giorno.
- build_scheduler / start: costruzione del BlockingScheduler APScheduler
  con CronTrigger per gli slot ordinari.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from execution import run_once
from models import AgentCycleOutcome, DailyRunState, DelayedFollowUpRequest

if TYPE_CHECKING:
    from claude_agent import ClaudeAgent
    from config import Config
    from mt5_client import Mt5Client


def operating_slots(cfg: "Config") -> list[int]:
    """Slot orari ordinari (cron hours) entro la finestra operativa."""
    return list(range(cfg.OPERATING_START_HOUR, cfg.OPERATING_END_HOUR, cfg.MAIN_CYCLE_HOURS))


class OperatingWindow:
    def __init__(self, cfg: "Config") -> None:
        self.weekdays: set[int] = set(cfg.OPERATING_WEEKDAYS)
        self.start_hour: int = cfg.OPERATING_START_HOUR
        self.end_hour: int = cfg.OPERATING_END_HOUR
        self.tz = ZoneInfo(cfg.OPERATING_TIMEZONE)

    def is_open(self, now: datetime | None = None) -> bool:
        if now is None:
            now = datetime.now(tz=self.tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=self.tz)
        else:
            now = now.astimezone(self.tz)
        return now.weekday() in self.weekdays and self.start_hour <= now.hour < self.end_hour


class DailyRunStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_run_state (
                    date            TEXT PRIMARY KEY,
                    decisions_count INTEGER NOT NULL DEFAULT 0,
                    trade_count     INTEGER NOT NULL DEFAULT 0,
                    no_trade_count  INTEGER NOT NULL DEFAULT 0,
                    updated_at      TEXT NOT NULL
                )
                """
            )

    def get_or_create(self, day: date) -> DailyRunState:
        key = day.isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT date, decisions_count, trade_count, no_trade_count "
                "FROM daily_run_state WHERE date = ?",
                (key,),
            ).fetchone()
            if row is None:
                now_iso = datetime.now().isoformat(timespec="seconds")
                conn.execute(
                    "INSERT INTO daily_run_state(date, decisions_count, trade_count, no_trade_count, updated_at) "
                    "VALUES (?, 0, 0, 0, ?)",
                    (key, now_iso),
                )
                return DailyRunState(date=day)
            return DailyRunState(
                date=day,
                decisions_count=row["decisions_count"],
                trade_count=row["trade_count"],
                no_trade_count=row["no_trade_count"],
            )

    def increment(self, day: date, outcome_type: str) -> DailyRunState:
        self.get_or_create(day)  # ensure row exists
        if outcome_type == "TRADE":
            sql = (
                "UPDATE daily_run_state "
                "SET decisions_count = decisions_count + 1, "
                "    trade_count = trade_count + 1, "
                "    updated_at = ? "
                "WHERE date = ?"
            )
        elif outcome_type == "NO_TRADE":
            sql = (
                "UPDATE daily_run_state "
                "SET decisions_count = decisions_count + 1, "
                "    no_trade_count = no_trade_count + 1, "
                "    updated_at = ? "
                "WHERE date = ?"
            )
        else:
            return self.get_or_create(day)

        now_iso = datetime.now().isoformat(timespec="seconds")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, (now_iso, day.isoformat()))
        return self.get_or_create(day)

    def is_target_reached(self, day: date, target: int) -> bool:
        return self.get_or_create(day).decisions_count >= target

    def reset_for_date(self, day: date) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM daily_run_state WHERE date = ?", (day.isoformat(),))


class Orchestrator:
    def __init__(
        self,
        cfg: "Config",
        agent: "ClaudeAgent",
        mt5: "Mt5Client",
        log: logging.Logger,
        daily_store: DailyRunStateStore,
        scheduler: BlockingScheduler | None = None,
    ) -> None:
        self.cfg = cfg
        self.agent = agent
        self.mt5 = mt5
        self.log = log
        self.daily_store = daily_store
        self.window = OperatingWindow(cfg)
        self.scheduler = scheduler
        self._lock = threading.Lock()
        self._cycle_active = False
        # Per simbolo, traccia il giorno in cui è stato concesso un follow-up.
        # Una opportunità (date, symbol) può essere ritardata al massimo una volta.
        self._followup_done: set[tuple[date, str]] = set()

    def attach_scheduler(self, scheduler: BlockingScheduler) -> None:
        self.scheduler = scheduler

    def execute_ordinary_cycle(self) -> AgentCycleOutcome | None:
        return self._execute(followup=None)

    def execute_followup_cycle(self, followup: DelayedFollowUpRequest) -> AgentCycleOutcome | None:
        marked = replace(followup, already_delayed=True)
        return self._execute(followup=marked)

    def _execute(self, followup: DelayedFollowUpRequest | None) -> AgentCycleOutcome | None:
        with self._lock:
            if self._cycle_active:
                self.log.info("Cycle skipped: another cycle is already active")
                return None
            self._cycle_active = True
        try:
            now = datetime.now(tz=self.window.tz)
            today = now.date()

            if not self.window.is_open(now):
                self.log.info(
                    "Cycle skipped: outside operating window (now=%s, weekday=%d, hour=%d)",
                    now.isoformat(timespec="seconds"), now.weekday(), now.hour,
                )
                return None

            if self.daily_store.is_target_reached(today, self.cfg.DAILY_TARGET_DECISIONS):
                state = self.daily_store.get_or_create(today)
                self.log.info(
                    "Cycle skipped: daily target reached (decisions_count=%d, target=%d)",
                    state.decisions_count, self.cfg.DAILY_TARGET_DECISIONS,
                )
                return None

            if followup is not None:
                candidate_symbols = [followup.symbol]
            else:
                candidate_symbols = list(self.cfg.SYMBOLS)

            account_state = self.mt5.get_account_state()
            outcome = self.agent.run_market_cycle(
                candidate_symbols,
                self.cfg.TIMEFRAME,
                account_state,
                followup=followup,
            )
            self._handle_outcome(outcome, today)
            return outcome
        finally:
            with self._lock:
                self._cycle_active = False

    def _handle_outcome(self, outcome: AgentCycleOutcome, today: date) -> None:
        if outcome.outcome_type == "TRADE" and outcome.proposal is not None:
            try:
                run_once(outcome.proposal.symbol, outcome.proposal, self.cfg, self.mt5, self.log)
            except Exception:
                self.log.exception("execution.run_once failed for %s", outcome.proposal.symbol)
            state = self.daily_store.increment(today, "TRADE")
            self.log.info(
                "Outcome TRADE counted; decisions_count=%d/%d trade_count=%d",
                state.decisions_count, self.cfg.DAILY_TARGET_DECISIONS, state.trade_count,
            )
            return

        if outcome.outcome_type == "NO_TRADE":
            state = self.daily_store.increment(today, "NO_TRADE")
            self.log.info(
                "Outcome NO_TRADE counted; decisions_count=%d/%d no_trade_count=%d",
                state.decisions_count, self.cfg.DAILY_TARGET_DECISIONS, state.no_trade_count,
            )
            return

        if outcome.outcome_type == "WAIT_FOLLOW_UP":
            req = outcome.follow_up
            if req is None or not self.cfg.FOLLOWUP_ENABLED:
                self.log.warning(
                    "WAIT_FOLLOW_UP without payload or feature disabled; downgrading to NO_TRADE",
                )
                self.daily_store.increment(today, "NO_TRADE")
                return
            key = (today, req.symbol)
            if key in self._followup_done:
                self.log.warning(
                    "Follow-up requested for %s already used today; downgrading to NO_TRADE",
                    req.symbol,
                )
                self.daily_store.increment(today, "NO_TRADE")
                return
            self._followup_done.add(key)
            self._register_followup_job(req)
            self.log.info(
                "Follow-up registered for %s @ %s (delay=%d min, reason=%s)",
                req.symbol,
                req.expires_at.isoformat(timespec="seconds"),
                req.delay_minutes,
                req.reason,
            )
            # WAIT_FOLLOW_UP non conta come decisione finale.
            return

    def _register_followup_job(self, req: DelayedFollowUpRequest) -> None:
        if self.scheduler is None:
            self.log.warning(
                "Follow-up requested but scheduler is not attached; "
                "cannot schedule one-shot job for %s",
                req.symbol,
            )
            return
        run_at = req.expires_at
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=self.window.tz)
        job_id = f"followup-{req.symbol}-{int(req.created_at.timestamp())}"
        self.scheduler.add_job(
            self.execute_followup_cycle,
            trigger=DateTrigger(run_date=run_at),
            args=[req],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=60,
        )


def build_scheduler(cfg: "Config", orchestrator: Orchestrator) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=cfg.OPERATING_TIMEZONE)
    weekday_str = ",".join(str(d) for d in cfg.OPERATING_WEEKDAYS)
    hour_str = ",".join(str(h) for h in operating_slots(cfg))
    trigger = CronTrigger(
        day_of_week=weekday_str,
        hour=hour_str,
        minute=0,
        timezone=cfg.OPERATING_TIMEZONE,
    )
    scheduler.add_job(
        orchestrator.execute_ordinary_cycle,
        trigger=trigger,
        id="ordinary_cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        replace_existing=True,
    )
    orchestrator.attach_scheduler(scheduler)
    return scheduler


def daily_db_path(cfg: "Config") -> Path:
    return Path(cfg.LOG_FILE).parent / "trades.db"
