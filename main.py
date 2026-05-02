"""Entry point del trading-agent in modalità daemon (fase 13 → 16).

Fase 16: il signal layer è un motore Python puro (IntradayStrategy +
MultiSymbolScanner) e lo scheduler è un loop H24 interno
(`IntradayLoopScheduler`), senza dipendenze da cron/Task Scheduler/APScheduler.
Il processo resta vivo finché non riceve SIGINT/SIGTERM, gestendo
heart-beat e stato in SQLite.
"""
from __future__ import annotations

import signal
import sys

from config import Config
from logger import init_logger
from mt5_client import Mt5Client
from news_aggregator import NewsAggregator
from scanner import MultiSymbolScanner
from scheduler import (
    HeartbeatStore,
    IntradayLoopScheduler,
    heartbeat_db_path,
)
from sentiment import SimpleSentiment
from strategy import IntradayStrategy, StrategyEnvironment


def main() -> int:
    cfg = Config()
    if cfg.STRATEGY_MODE == "intraday":
        cfg.SYMBOLS = list(cfg.INTRADAY_SYMBOLS)
        cfg.TIMEFRAME = cfg.INTRADAY_TIMEFRAME
    logger = init_logger(cfg)

    mt5 = Mt5Client(cfg)
    if cfg.DRY_RUN:
        logger.info("DRY_RUN=true: nessun ordine reale verrà inviato a MT5")
    if not mt5.initialize() or not mt5.login():
        logger.error("MT5 initialization/login failed: controllare credenziali in .env")
        return 1

    loop = None
    try:
        environment = StrategyEnvironment(cfg, logger)
        strategy = IntradayStrategy(cfg, mt5, logger, environment=environment)
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

        hb_store = HeartbeatStore(heartbeat_db_path(cfg))
        loop = IntradayLoopScheduler(
            cfg=cfg,
            mt5_client=mt5,
            strategy=strategy,
            scanner=scanner,
            log=logger,
            heartbeat_store=hb_store,
            environment=environment,
        )

        logger.info(
            "Daemon H24 start: tz=%s weekdays=%s window=%02d-%02d "
            "scan_interval=%dmin first_delay=%dmin execution_mode=%s "
            "pause=%s dry_run=%s strategy=python_pure timeframe=%s symbols=%s",
            cfg.OPERATING_TIMEZONE,
            ",".join(str(d) for d in cfg.OPERATING_WEEKDAYS),
            cfg.INTRADAY_START_HOUR,
            cfg.INTRADAY_END_HOUR,
            cfg.INTRADAY_SCAN_INTERVAL_MINUTES,
            cfg.INTRADAY_FIRST_CYCLE_DELAY_MINUTES,
            cfg.EXECUTION_MODE,
            cfg.PAUSE_TRADING,
            cfg.DRY_RUN,
            cfg.INTRADAY_TIMEFRAME,
            cfg.INTRADAY_SYMBOLS,
        )

        def _graceful_shutdown(signum, _frame):
            logger.info("Signal %s received, stopping H24 loop", signum)
            if loop is not None:
                loop.stop()

        signal.signal(signal.SIGINT, _graceful_shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _graceful_shutdown)

        try:
            loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            logger.info("KeyboardInterrupt received, stopping daemon")
            loop.stop()
        return 0
    finally:
        try:
            mt5.shutdown()
        except Exception:
            logger.exception("Mt5Client shutdown failed")


if __name__ == "__main__":
    sys.exit(main())
