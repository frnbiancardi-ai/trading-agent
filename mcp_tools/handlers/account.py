"""Handler MCP per account/risk/trade-history.

Spostati da mcp_server.py senza change semantica (D-E1).
Tutti e tre i handler sono sincroni puri — il dispatch asincrono
è gestito in mcp_tools/server.py.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path


def handle_get_account_state(mt5_client) -> dict:
    """Stato corrente del conto MT5 (balance, equity, free_margin, posizioni, PnL)."""
    state = mt5_client.get_account_state()
    return dataclasses.asdict(state)


def handle_get_risk_profile(cfg) -> dict:
    """Parametri correnti del risk engine. Spostato da mcp_server.py:359-374."""
    return {
        "RISK_MODE": cfg.RISK_MODE,
        "RISK_AMOUNT_MODE": cfg.RISK_AMOUNT_MODE,
        "RISK_PER_TRADE_PERCENT": cfg.RISK_PER_TRADE_PERCENT,
        "RISK_PER_TRADE_AMOUNT": cfg.RISK_PER_TRADE_AMOUNT,
        "MAX_DAILY_DRAWDOWN_PERCENT": cfg.MAX_DAILY_DRAWDOWN_PERCENT,
        "MAX_LOTS_PER_TRADE": cfg.MAX_LOTS_PER_TRADE,
        "MIN_SL_PIPS": cfg.MIN_SL_PIPS,
        "MAX_SL_PIPS": cfg.MAX_SL_PIPS,
        "USE_SESSION_FILTER": cfg.USE_SESSION_FILTER,
        "SESSION_START_HOUR": cfg.SESSION_START_HOUR,
        "SESSION_END_HOUR": cfg.SESSION_END_HOUR,
        "EXECUTION_MODE": cfg.EXECUTION_MODE,
        "TIMEFRAME": cfg.TIMEFRAME,
    }


def handle_get_trade_history(cfg, n: int = 10) -> list[dict]:
    """Ultime N decisioni dal trades_log. Spostato da mcp_server.py:376-388."""
    db_path = Path(cfg.LOG_FILE).parent / "trades.db"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, timestamp, symbol, direction, size_lots, entry_price, "
            "stop_loss, take_profit, decision_reason, approved, pnl_realized "
            "FROM trades_log ORDER BY id DESC LIMIT ?",
            (int(n),),
        )
        return [dict(r) for r in cur.fetchall()]
