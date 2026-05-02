"""Dry-run di un ciclo H24 — fase 16.

Esegue un singolo ciclo dello scheduler H24 senza inviare ordini reali a MT5
(`send_order`/`close_position` sono saltati grazie al flag DRY_RUN=true).
Utile per validazione weekend o per smoke test dopo modifiche allo scheduler.

Uso:

    DRY_RUN=true ./.venv/Scripts/python.exe scripts/dry_run_cycle.py

Oppure su Windows PowerShell:

    $env:DRY_RUN='true'; .\.venv\Scripts\python.exe scripts\dry_run_cycle.py

Lo script:
  1. Forza DRY_RUN=true e PAUSE_TRADING=false in process env (no override del file .env).
  2. Inizializza Config, logger, Mt5Client, IntradayStrategy, MultiSymbolScanner,
     HeartbeatStore, IntradayLoopScheduler.
  3. Tenta MT5 initialize+login. Se fallisce (mercati chiusi/credenziali assenti),
     continua solo lo step di logging e termina con exit code 2 senza errore.
  4. Esegue `loop.run_one_cycle()` UNA VOLTA e stampa `SchedulerCycleRecord`.
  5. Termina con exit 0.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Forza DRY_RUN nel process env prima dell'import di Config (load_dotenv già fatto).
os.environ.setdefault("DRY_RUN", "true")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402
from logger import init_logger  # noqa: E402
from mt5_client import Mt5Client  # noqa: E402
from scanner import MultiSymbolScanner  # noqa: E402
from scheduler import HeartbeatStore, IntradayLoopScheduler, heartbeat_db_path  # noqa: E402
from strategy import IntradayStrategy, StrategyEnvironment  # noqa: E402


def main() -> int:
    cfg = Config()
    cfg.DRY_RUN = True  # forza anche se .env non lo aveva
    if cfg.STRATEGY_MODE == "intraday":
        cfg.SYMBOLS = list(cfg.INTRADAY_SYMBOLS)
        cfg.TIMEFRAME = cfg.INTRADAY_TIMEFRAME
    logger = init_logger(cfg)
    logger.info("=== DRY-RUN scheduler H24 (fase 16) ===")

    mt5 = Mt5Client(cfg)
    mt5_ok = False
    try:
        mt5_ok = mt5.initialize() and mt5.login()
    except Exception:
        logger.exception("MT5 initialize/login eccezione")
        mt5_ok = False
    if not mt5_ok:
        logger.warning(
            "MT5 non disponibile (mercati chiusi / credenziali assenti). "
            "Dry-run non può eseguire scan: termino con exit 2."
        )
        try:
            mt5.shutdown()
        except Exception:
            pass
        return 2

    try:
        environment = StrategyEnvironment(cfg, logger)
        strategy = IntradayStrategy(cfg, mt5, logger, environment=environment)
        scanner = MultiSymbolScanner(cfg, mt5, strategy, logger)
        store = HeartbeatStore(heartbeat_db_path(cfg))
        loop = IntradayLoopScheduler(
            cfg=cfg,
            mt5_client=mt5,
            strategy=strategy,
            scanner=scanner,
            log=logger,
            heartbeat_store=store,
            environment=environment,
        )
        rec = loop.run_one_cycle()
        logger.info(
            "DRY-RUN cycle complete: outcome=%s duration_ms=%s note=%s err=%s",
            rec.outcome, rec.duration_ms, rec.note or "-", rec.error_type or "-",
        )
        return 0
    finally:
        try:
            mt5.shutdown()
        except Exception:
            logger.exception("Mt5Client shutdown failed")


if __name__ == "__main__":
    sys.exit(main())
