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
import time
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from execution import run_once
from models import (
    AgentCycleOutcome,
    DailyRunState,
    DelayedFollowUpRequest,
    SchedulerCycleRecord,
)

if TYPE_CHECKING:
    from claude_agent import ClaudeAgent
    from config import Config
    from mt5_client import Mt5Client
    from scanner import MultiSymbolScanner
    from strategy import IntradayStrategy, StrategyEnvironment


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


# ─────────────────────────────────────────────────────────────────────────────
# Fase 16: scheduler H24 interno + heartbeat persistente
# ─────────────────────────────────────────────────────────────────────────────


class HeartbeatStore:
    """Persistenza SQLite di heartbeat e stato dello scheduler H24 (fase 16).

    Tabelle:
      - `heartbeat` (storico ciclo per ciclo)
      - `scheduler_state` (riga singleton con ultimo stato + contatori consecutivi)
    """

    _SCHEMA_HEARTBEAT = """
    CREATE TABLE IF NOT EXISTS heartbeat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        duration_ms INTEGER,
        outcome TEXT NOT NULL,
        error_type TEXT,
        error_message TEXT,
        note TEXT
    )
    """
    _SCHEMA_STATE = """
    CREATE TABLE IF NOT EXISTS scheduler_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_started_at TEXT,
        last_ended_at TEXT,
        last_outcome TEXT,
        last_duration_ms INTEGER,
        last_error_type TEXT,
        last_error_message TEXT,
        consecutive_no_trade INTEGER NOT NULL DEFAULT 0,
        consecutive_errors INTEGER NOT NULL DEFAULT 0
    )
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(self._SCHEMA_HEARTBEAT)
            conn.execute(self._SCHEMA_STATE)
            conn.execute("INSERT OR IGNORE INTO scheduler_state(id) VALUES (1)")

    def begin_cycle(self, started_at: datetime) -> int:
        iso = started_at.isoformat(timespec="seconds")
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO heartbeat(started_at, outcome) VALUES (?, ?)",
                (iso, "RUNNING"),
            )
            conn.execute(
                "UPDATE scheduler_state SET last_started_at = ? WHERE id = 1",
                (iso,),
            )
            return int(cur.lastrowid)

    def end_cycle(
        self,
        hb_id: int,
        started_at: datetime,
        ended_at: datetime,
        outcome: str,
        error_type: str | None = None,
        error_message: str | None = None,
        note: str = "",
    ) -> int:
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE heartbeat
                   SET ended_at = ?, duration_ms = ?, outcome = ?,
                       error_type = ?, error_message = ?, note = ?
                   WHERE id = ?""",
                (
                    ended_at.isoformat(timespec="seconds"),
                    duration_ms,
                    outcome,
                    error_type,
                    error_message,
                    note,
                    hb_id,
                ),
            )
            row = conn.execute(
                "SELECT consecutive_no_trade, consecutive_errors "
                "FROM scheduler_state WHERE id = 1"
            ).fetchone()
            cn, ce = (row[0], row[1]) if row else (0, 0)
            if outcome == "ERROR":
                ce += 1
                cn = 0
            elif outcome == "NO_TRADE":
                cn += 1
                ce = 0
            else:
                ce = 0
                cn = 0
            conn.execute(
                """UPDATE scheduler_state
                   SET last_ended_at = ?, last_outcome = ?, last_duration_ms = ?,
                       last_error_type = ?, last_error_message = ?,
                       consecutive_no_trade = ?, consecutive_errors = ?
                   WHERE id = 1""",
                (
                    ended_at.isoformat(timespec="seconds"),
                    outcome,
                    duration_ms,
                    error_type,
                    error_message,
                    cn,
                    ce,
                ),
            )
        return duration_ms

    def get_state(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM scheduler_state WHERE id = 1"
            ).fetchone()
            return dict(row) if row else {}

    def last_heartbeats(self, limit: int = 10) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM heartbeat ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]


class IntradayLoopScheduler:
    """Loop H24 interno (fase 16): nessuna dipendenza da APScheduler/cron esterni.

    Ordine ciclo (allineato alla spec):
      1. heartbeat START
      2. read PAUSE_TRADING + finestra giornaliera + weekend + news_window
      3. account_state + posizioni aperte
      4. gestione posizioni aperte (CLOSE_PROTECT / CLOSE_END_OF_DAY)
      5. se PAUSED / fuori finestra / news → skip nuovi trade
      6. scan + deep_analyze top-N → StrategyOutcome
      7. se TRADE: risk_engine + execution.run_once (rispettando EXECUTION_MODE/DRY_RUN)
      8. heartbeat END (outcome, durata, errori)
      9. sleep fino al prossimo slot (skip overrun, nessun retry aggressivo)
    """

    def __init__(
        self,
        cfg: "Config",
        mt5_client: "Mt5Client",
        strategy: "IntradayStrategy",
        scanner: "MultiSymbolScanner",
        log: logging.Logger,
        heartbeat_store: HeartbeatStore,
        environment: "StrategyEnvironment | None" = None,
    ) -> None:
        self.cfg = cfg
        self.mt5 = mt5_client
        self.strategy = strategy
        self.scanner = scanner
        self.log = log
        self.hb = heartbeat_store
        self.env = environment if environment is not None else strategy.env
        self._stop = threading.Event()
        self._tz = ZoneInfo(cfg.OPERATING_TIMEZONE)

    def stop(self) -> None:
        self._stop.set()

    def is_stopped(self) -> bool:
        return self._stop.is_set()

    def run_forever(self) -> None:
        first_delay_s = self.cfg.INTRADAY_FIRST_CYCLE_DELAY_MINUTES * 60
        interval_s = self.cfg.INTRADAY_SCAN_INTERVAL_MINUTES * 60
        self.log.info(
            "Loop H24 avvio: first_delay=%ds interval=%ds dry_run=%s pause=%s",
            first_delay_s, interval_s, self.cfg.DRY_RUN, self.cfg.PAUSE_TRADING,
        )
        if first_delay_s > 0:
            self._stop.wait(first_delay_s)
        while not self._stop.is_set():
            cycle_start = time.monotonic()
            try:
                self.run_one_cycle()
            except Exception:
                self.log.exception("Eccezione non gestita nel loop, continuo")
            elapsed = time.monotonic() - cycle_start
            if elapsed > interval_s:
                self.log.warning(
                    "Ciclo overrun durata=%.1fs > intervallo=%ds, salto slot successivo",
                    elapsed, interval_s,
                )
                # salta avanti in multipli di interval finché non ci si rimette in linea
                slots_to_skip = int(elapsed // interval_s)
                sleep_for = max(0.0, interval_s * (slots_to_skip + 1) - elapsed)
            else:
                sleep_for = max(0.0, interval_s - elapsed)
            self._stop.wait(sleep_for)
        self.log.info("Loop H24 terminato")

    def run_one_cycle(self) -> SchedulerCycleRecord:
        cfg = self.cfg
        now = datetime.now(tz=self._tz)
        hb_id = self.hb.begin_cycle(now)
        outcome = "OK"
        err_type: str | None = None
        err_msg: str | None = None
        note = ""

        try:
            if self.env.is_weekend(now):
                outcome, note = "WEEKEND", "weekend_off"
                return self._finish(hb_id, now, outcome, err_type, err_msg, note)

            try:
                account_state = self.mt5.get_account_state()
            except Exception as exc:
                self.log.exception("get_account_state fallito")
                outcome = "ERROR"
                err_type = type(exc).__name__
                err_msg = str(exc)
                return self._finish(hb_id, now, outcome, err_type, err_msg, "account_state_fail")

            self._manage_open_positions(account_state, now)

            if cfg.PAUSE_TRADING:
                outcome, note = "PAUSED", "PAUSE_TRADING_attivo"
                return self._finish(hb_id, now, outcome, err_type, err_msg, note)

            if not self.env.is_intraday_window(now):
                outcome = "OUT_OF_WINDOW"
                note = (
                    f"hour={now.hour} window={cfg.INTRADAY_START_HOUR}-"
                    f"{cfg.INTRADAY_END_HOUR}"
                )
                return self._finish(hb_id, now, outcome, err_type, err_msg, note)

            news_blocked = self.env.is_news_window(now)
            if news_blocked:
                outcome, note = "NEWS_BLOCKED", "is_news_window=True"
                return self._finish(hb_id, now, outcome, err_type, err_msg, note)

            try:
                account_state = self.mt5.get_account_state()
            except Exception as exc:
                self.log.exception("get_account_state (refresh) fallito")
                outcome = "ERROR"
                err_type = type(exc).__name__
                err_msg = str(exc)
                return self._finish(hb_id, now, outcome, err_type, err_msg, "refresh_fail")

            scan_results = self.scanner.scan_universe(cfg.INTRADAY_SYMBOLS)
            outcome_obj = self.scanner.deep_analyze_top_candidates(
                scan_results, account_state,
                paused=False, news_blocked=False,
            )

            if (
                outcome_obj.outcome_type == "TRADE"
                and outcome_obj.proposal is not None
            ):
                if cfg.DRY_RUN:
                    self.log.info(
                        "DRY_RUN trade simulato symbol=%s direction=%s conf=%.2f addon=%s",
                        outcome_obj.proposal.symbol,
                        outcome_obj.proposal.direction,
                        outcome_obj.proposal.confidence,
                        outcome_obj.is_addon,
                    )
                    outcome, note = "DRY_RUN", outcome_obj.note
                else:
                    try:
                        run_once(
                            outcome_obj.proposal.symbol,
                            outcome_obj.proposal,
                            cfg, self.mt5, self.log,
                        )
                        outcome, note = "OK", outcome_obj.note
                    except Exception as exc:
                        self.log.exception("execution.run_once fallito")
                        outcome = "ERROR"
                        err_type = type(exc).__name__
                        err_msg = str(exc)
            elif outcome_obj.outcome_type == "WAIT_FOLLOW_UP":
                outcome = "OK"
                note = f"wait_followup_h24_inattivo: {outcome_obj.note}"
            else:
                if outcome_obj.drawdown_violation:
                    outcome = "DRAWDOWN_BLOCK"
                elif outcome_obj.news_blocked:
                    outcome = "NEWS_BLOCKED"
                elif outcome_obj.paused:
                    outcome = "PAUSED"
                else:
                    outcome = "NO_TRADE"
                note = outcome_obj.note
        except Exception as exc:
            self.log.exception("Eccezione ciclo H24")
            outcome = "ERROR"
            err_type = type(exc).__name__
            err_msg = str(exc)

        return self._finish(hb_id, now, outcome, err_type, err_msg, note)

    def _finish(
        self,
        hb_id: int,
        started_at: datetime,
        outcome: str,
        err_type: str | None,
        err_msg: str | None,
        note: str,
    ) -> SchedulerCycleRecord:
        ended_at = datetime.now(tz=self._tz)
        duration_ms = self.hb.end_cycle(
            hb_id, started_at, ended_at, outcome, err_type, err_msg, note,
        )
        rec = SchedulerCycleRecord(
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            outcome=outcome,  # type: ignore[arg-type]
            error_type=err_type,
            error_message=err_msg,
            note=note,
        )
        self.log.info(
            "Ciclo done outcome=%s duration_ms=%d note=%s",
            outcome, duration_ms, note or "-",
        )
        return rec

    def _manage_open_positions(
        self,
        account_state,
        now: datetime,
    ) -> None:
        cfg = self.cfg
        intraday = set(cfg.INTRADAY_SYMBOLS)
        for pos in list(account_state.open_positions):
            if pos.symbol not in intraday:
                continue
            try:
                verdict = self.strategy.evaluate_open_position(pos, account_state, now=now)
            except Exception:
                self.log.exception("evaluate_open_position fallito %s", pos.symbol)
                continue
            if verdict.action == "HOLD":
                continue
            ticket = verdict.ticket or int(getattr(pos, "ticket", 0) or 0)
            if ticket <= 0:
                self.log.warning(
                    "Verdetto %s su %s ma ticket non disponibile, salto",
                    verdict.action, pos.symbol,
                )
                continue
            if cfg.DRY_RUN:
                self.log.info(
                    "DRY_RUN chiusura simulata ticket=%d symbol=%s action=%s reason=%s",
                    ticket, pos.symbol, verdict.action, verdict.reason,
                )
                continue
            try:
                result = self.mt5.close_position(ticket)
                if result.success:
                    self.log.info(
                        "Chiusura OK ticket=%d symbol=%s action=%s reason=%s order=%s",
                        ticket, pos.symbol, verdict.action, verdict.reason,
                        result.order_id,
                    )
                else:
                    self.log.error(
                        "Chiusura fallita ticket=%d symbol=%s err=%s",
                        ticket, pos.symbol, result.error_message,
                    )
            except Exception:
                self.log.exception(
                    "close_position eccezione ticket=%d symbol=%s",
                    ticket, pos.symbol,
                )


def heartbeat_db_path(cfg: "Config") -> Path:
    """Heartbeat DB condivide il file con trades.db (stessa directory)."""
    return daily_db_path(cfg)
