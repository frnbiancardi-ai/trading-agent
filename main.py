"""Entry point del trading-agent in modalità daemon (fase 13).

Avvia un BlockingScheduler APScheduler che esegue cicli di mercato sugli slot
ordinari (cron) entro la finestra operativa configurata e gestisce follow-up
one-shot ritardati. Il processo resta vivo finché non riceve SIGINT/SIGTERM.
"""
from __future__ import annotations

import signal
import sys

from claude_agent import ClaudeAgent
from config import Config
from logger import init_logger
from mt5_client import Mt5Client
from scheduler import (
    DailyRunStateStore,
    Orchestrator,
    build_scheduler,
    daily_db_path,
    operating_slots,
)


def main() -> int:
    cfg = Config()
    logger = init_logger(cfg)

    mt5 = Mt5Client(cfg)
    if not mt5.initialize() or not mt5.login():
        logger.error("MT5 initialization/login failed: controllare credenziali in .env")
        return 1

    scheduler = None
    try:
        agent = ClaudeAgent(cfg, mt5, logger)
        store = DailyRunStateStore(daily_db_path(cfg))
        orchestrator = Orchestrator(cfg, agent, mt5, logger, store)
        scheduler = build_scheduler(cfg, orchestrator)

        slots = operating_slots(cfg)
        weekdays = ",".join(str(d) for d in cfg.OPERATING_WEEKDAYS)
        logger.info(
            "Daemon start: tz=%s weekdays=%s slots=%s execution_mode=%s "
            "daily_target=%d max_delay_min=%d followup_enabled=%s",
            cfg.OPERATING_TIMEZONE,
            weekdays,
            slots,
            cfg.EXECUTION_MODE,
            cfg.DAILY_TARGET_DECISIONS,
            cfg.MAX_DELAY_MINUTES,
            cfg.FOLLOWUP_ENABLED,
        )

        def _graceful_shutdown(signum, _frame):
            logger.info("Signal %s received, shutting down scheduler", signum)
            if scheduler is not None and scheduler.running:
                scheduler.shutdown(wait=False)

        signal.signal(signal.SIGINT, _graceful_shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _graceful_shutdown)

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("KeyboardInterrupt received, stopping daemon")
            if scheduler.running:
                scheduler.shutdown(wait=False)
        return 0
    finally:
        try:
            mt5.shutdown()
        except Exception:
            logger.exception("Mt5Client shutdown failed")


if __name__ == "__main__":
    sys.exit(main())
