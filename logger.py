import logging
import logging.handlers
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import Config
from models import AccountState, OrderResult, RiskDecision, TradeProposal

_TZ_ROME = ZoneInfo("Europe/Rome")
_LOGGER_NAME = "trading_agent"

_TRADES_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  size_lots REAL,
  entry_price REAL,
  stop_loss REAL,
  take_profit REAL,
  decision_reason TEXT,
  approved INTEGER NOT NULL,
  pnl_realized REAL
)
"""

_db_path: Path | None = None


def _trades_db_path(cfg: Config) -> Path:
    return Path(cfg.LOG_FILE).parent / "trades.db"


def _now_iso() -> str:
    return datetime.now(tz=_TZ_ROME).isoformat()


def init_logger(cfg: Config) -> logging.Logger:
    log_file = Path(cfg.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    global _db_path
    _db_path = _trades_db_path(cfg)
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_TRADES_LOG_SCHEMA)
        conn.commit()

    return logger


def log_trade_decision(
    proposal: TradeProposal,
    decision: RiskDecision,
    account: AccountState,
) -> None:
    if _db_path is None:
        raise RuntimeError("init_logger() must be called before log_trade_decision()")

    logger = logging.getLogger(_LOGGER_NAME)

    with sqlite3.connect(_db_path) as conn:
        conn.execute(
            """INSERT INTO trades_log
               (timestamp, symbol, direction, size_lots, entry_price,
                stop_loss, take_profit, decision_reason, approved, pnl_realized)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
            (
                _now_iso(),
                proposal.symbol,
                proposal.direction,
                decision.size_lots,
                proposal.entry_price,
                decision.adjusted_stop_loss,
                decision.adjusted_take_profit,
                decision.reason,
                int(decision.approved),
            ),
        )
        conn.commit()

    logger.info(
        "DECISION symbol=%s direction=%s approved=%s size_lots=%.4f reason=%s balance=%.2f",
        proposal.symbol,
        proposal.direction,
        decision.approved,
        decision.size_lots,
        decision.reason,
        account.balance,
    )


def log_order_result(order_result: OrderResult, proposal: TradeProposal) -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    if order_result.success:
        logger.info(
            "ORDER OK symbol=%s direction=%s order_id=%s",
            proposal.symbol,
            proposal.direction,
            order_result.order_id,
        )
    else:
        logger.error(
            "ORDER FAIL symbol=%s direction=%s error=%s",
            proposal.symbol,
            proposal.direction,
            order_result.error_message,
        )
