"""Entry point del trading-agent in modalità daemon (fase 13 + 14).

Avvia un BlockingScheduler APScheduler che esegue cicli di mercato sugli slot
ordinari (cron) entro la finestra operativa configurata e gestisce follow-up
one-shot ritardati. Il signal layer è ora un motore Python puro
(IntradayStrategy + MultiSymbolScanner) senza dipendenza da Claude API.
Il processo resta vivo finché non riceve SIGINT/SIGTERM.
"""
from __future__ import annotations

import signal
import sys

from config import Config
from logger import init_logger
from mt5_client import Mt5Client
from news_aggregator import NewsAggregator
from scanner import MultiSymbolScanner, StrategyRunner
from scheduler import (
    DailyRunStateStore,
    Orchestrator,
    build_scheduler,
    daily_db_path,
    operating_slots,
)
from sentiment import SimpleSentiment
from strategy import IntradayStrategy


def main() -> int:
    cfg = Config()
    if cfg.STRATEGY_MODE == "intraday":
        cfg.SYMBOLS = list(cfg.INTRADAY_SYMBOLS)
        cfg.TIMEFRAME = cfg.INTRADAY_TIMEFRAME
    logger = init_logger(cfg)

    mt5 = Mt5Client(cfg)
    if not mt5.initialize() or not mt5.login():
        logger.error("MT5 initialization/login failed: controllare credenziali in .env")
        return 1

    scheduler = None
    try:
        strategy = IntradayStrategy(cfg, mt5, logger)
        news_aggregator = None
        sentiment_analyzer = None
        if cfg.ENABLE_NEWS_SENTIMENT and cfg.RSS_FEEDS:
            news_aggregator = NewsAggregator(cfg, logger)
            sentiment_analyzer = SimpleSentiment(cfg)
            logger.info(
                "News sentiment enabled: feeds=%d action=%s min_strength=%.2f boost=%.2f",
                len(cfg.RSS_FEEDS), cfg.SENTIMENT_CONFLICT_ACTION,
                cfg.SENTIMENT_MIN_STRENGTH_FILTER, cfg.SENTIMENT_BOOST_FACTOR,
            )
        scanner = MultiSymbolScanner(
            cfg, mt5, strategy, logger,
            news_aggregator=news_aggregator,
            sentiment_analyzer=sentiment_analyzer,
        )
        runner = StrategyRunner(cfg, strategy, scanner, logger)

        store = DailyRunStateStore(daily_db_path(cfg))
        orchestrator = Orchestrator(cfg, runner, mt5, logger, store)
        scheduler = build_scheduler(cfg, orchestrator)

        slots = operating_slots(cfg)
        weekdays = ",".join(str(d) for d in cfg.OPERATING_WEEKDAYS)
        logger.info(
            "Daemon start: tz=%s weekdays=%s slots=%s execution_mode=%s "
            "daily_target=%d max_delay_min=%d followup_enabled=%s "
            "strategy=python_pure timeframe=%s symbols=%s",
            cfg.OPERATING_TIMEZONE,
            weekdays,
            slots,
            cfg.EXECUTION_MODE,
            cfg.DAILY_TARGET_DECISIONS,
            cfg.MAX_DELAY_MINUTES,
            cfg.FOLLOWUP_ENABLED,
            cfg.INTRADAY_TIMEFRAME,
            cfg.INTRADAY_SYMBOLS,
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
