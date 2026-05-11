"""Schemi JSON-Schema centralizzati per ogni Tool MCP (D-F1).

Punto canonico unico per tutti gli inputSchema dei tool MCP.
Importati da mcp_tools/server.py e mcp_tools/handlers/*.
"""
from __future__ import annotations

# ── Schema proposta (verbatim da mcp_server.py:79-95) ─────────────────────────
PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "direction": {"type": "string", "enum": ["BUY", "SELL"]},
        "entry_price": {"type": "number"},
        "stop_loss_price": {"type": "number"},
        "take_profit_price": {"type": "number"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
    },
    "required": [
        "symbol", "direction", "entry_price",
        "stop_loss_price", "take_profit_price",
        "confidence", "rationale",
    ],
}
# Alias compat per test che accedono _PROPOSAL_SCHEMA via mcp_server o mcp_tools.server
_PROPOSAL_SCHEMA = PROPOSAL_SCHEMA


# ── Schema propose_trade (verbatim da mcp_server.py:97-114) ───────────────────
PROPOSE_TRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "timeframe": {"type": "string"},
        "direction": {"type": "string", "enum": ["BUY", "SELL"]},
        "entry_price": {"type": "number"},
        "stop_loss_price": {"type": "number"},
        "take_profit_price": {"type": "number"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
    },
    "required": [
        "symbol", "direction", "entry_price",
        "stop_loss_price", "take_profit_price",
        "confidence", "rationale",
    ],
}
_PROPOSE_TRADE_SCHEMA = PROPOSE_TRADE_SCHEMA


# ── Campi addizionali condivisi (R1, MCP-09/12/14, replay_decision D-D1) ─────
BARS_AS_OF_FIELDS = {
    "bars": {
        "type": "integer",
        "minimum": 50,
        "maximum": 500,
        "default": 200,
        "description": "Bar count (default 200; legacy 50 = pass bars=50 esplicitamente)",
    },
    "as_of_ts": {
        "type": "string",
        "description": "ISO8601 UTC timestamp; null/missing = live MT5 (D-D1)",
    },
    "timeframe": {
        "type": "string",
        "enum": ["M15", "M30", "H1", "H4"],
        "description": "Override cfg.TIMEFRAME",
    },
}

# ── R1: get_market_snapshot schema completo ───────────────────────────────────
GET_MARKET_SNAPSHOT_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        **BARS_AS_OF_FIELDS,
    },
    "required": ["symbol"],
}
