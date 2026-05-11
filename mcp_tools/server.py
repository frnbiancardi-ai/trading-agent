"""
mcp_tools/server.py — Server MCP locale per trading-agent (Phase 6 D-E1).

Spostato da mcp_server.py (legacy) verso questo package.
mcp_server.py rimane come thin shim per retrocompatibilità CLI.

Compatibile con mcp >= 1.27.0 (SDK ufficiale Anthropic). API verificata su 1.27.0:
  from mcp.server import Server
  from mcp.server.stdio import stdio_server
  from mcp.types import Tool, TextContent
  @server.list_tools() / @server.call_tool()

NOTA IMPORT SDK: il package locale si chiama `mcp_tools/` (NON `mcp/`) proprio
per non oscurare il package SDK PyPI `mcp`. Pertanto le seguenti import
SDK funzionano normalmente senza conflitti:
  from mcp.server import Server
  from mcp.server.stdio import stdio_server
  from mcp.types import TextContent, Tool

IMPORTANTE: il protocollo MCP usa stdin/stdout per JSON-RPC.
Tutti i log devono finire su stderr o file (mai stdout) per non rompere il protocollo.
Il logger configurato in `logger.py` scrive solo su file (RotatingFileHandler) — sicuro.
"""
import asyncio
import dataclasses
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from config import Config
from logger import init_logger
from mt5_client import Mt5Client

from mcp_tools.errors import ErrorCodes, envelope
from mcp_tools.handlers.account import (
    handle_get_account_state,
    handle_get_risk_profile,
    handle_get_trade_history,
)
from mcp_tools.handlers.market import (
    handle_get_market_snapshot as _market_snapshot,
    handle_scan_symbol_candidates as _market_scan,
    handle_get_symbol_indicators as _market_symbol_indicators,
    handle_get_symbol_universe as _market_symbol_universe,
)
from mcp_tools.handlers.proposal import (
    handle_propose_trade as _proposal_propose,
    handle_evaluate_trade_proposal as _proposal_evaluate,
    handle_submit_order_if_approved as _proposal_submit,
)
from mcp_tools.handlers.backtest import (
    CANCEL_BACKTEST_TOOL,
    GET_BACKTEST_METRICS_TOOL,
    RUN_BACKTEST_TOOL,
    WALK_FORWARD_VALIDATE_TOOL,
    handle_cancel_backtest,
    handle_get_backtest_metrics,
    handle_run_backtest,
    handle_walk_forward_validate,
)

# Singleton globali — inizializzati al boot del server (e non al solo import del modulo,
# così i test possono importare mcp_tools.server senza far partire MT5).
cfg = Config()
log = init_logger(cfg)
mt5 = Mt5Client(cfg)
_mt5_ready: bool = False

# D-A1 / D-A4: registry async dei backtest. Inizializzato da _bootstrap_state(),
# NON al solo import del modulo (per non aprire ProcessPoolExecutor nei test).
job_queue: "Any | None" = None  # JobQueue tipato lazy per evitare import top-level


def _bootstrap_mt5() -> bool:
    """Inizializza MT5. Chiamato dal main, NON dall'import del modulo."""
    global _mt5_ready
    try:
        _mt5_ready = mt5.initialize() and mt5.login()
    except Exception as exc:
        log.exception("MCP server: errore durante inizializzazione MT5: %s", exc)
        _mt5_ready = False
    if not _mt5_ready:
        log.error(
            "MCP server: MT5 initialize/login fallito; le tool call falliranno "
            "finché MT5 non è disponibile (controlla credenziali in .env)."
        )
    return _mt5_ready


def _bootstrap_state() -> None:
    """D-F4 ordering: MT5 (già fatto in _bootstrap_mt5) → DB tables → JobQueue → stdio.

    Wave 2 (06-03): inizializza JobQueue su cfg.MCP_MAX_CONCURRENT_RUNS.
    Wave 3 (06-04) aggiungerà trail_daemon.ensure_table(db_path) prima del JobQueue.
    """
    global job_queue
    from logger import _trades_db_path
    db_path = str(_trades_db_path(cfg))
    # PRAGMA WAL una sola volta (Phase 5 D-16); poi LedgerWriter ensure_schema +
    # JobQueue _ensure_error_column applicano le migration idempotenti.
    import sqlite3
    with sqlite3.connect(db_path) as c:
        c.execute("PRAGMA journal_mode=WAL")
    # Garantisce schema backtest_runs/backtest_trades (idempotente)
    from backtest.ledger import LedgerWriter
    LedgerWriter(db_path)
    # JobQueue (lazy import per non rallentare module-load durante test)
    from mcp_tools.job_queue import JobQueue
    job_queue = JobQueue(
        max_workers=cfg.MCP_MAX_CONCURRENT_RUNS, db_path=db_path,
    )
    log.info(
        "MCP bootstrap state ready: db=%s max_workers=%d",
        db_path, cfg.MCP_MAX_CONCURRENT_RUNS,
    )


server: Server = Server("trading-agent")


def _text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, default=str, ensure_ascii=False))]


# ── Schema legacy ─────────────────────────────────────────────────────────────
# Importati da schemas.py (D-F1) — definiti lì per essere il punto canonico.
# I valori legacy (_PROPOSAL_SCHEMA, _PROPOSE_TRADE_SCHEMA) rimangono esposti
# per retrocompatibilità con test che accedono mcp_server._PROPOSAL_SCHEMA.
from mcp_tools.schemas import (
    PROPOSAL_SCHEMA as _PROPOSAL_SCHEMA,
    PROPOSE_TRADE_SCHEMA as _PROPOSE_TRADE_SCHEMA,
    GET_MARKET_SNAPSHOT_SCHEMA,
)


# NOTA Phase 6 D-E1: handler di dominio spostati nei moduli mcp_tools/handlers/.
# Vedi mcp_tools/handlers/market.py (R1/R2) e mcp_tools/handlers/proposal.py (R3).
# Le funzioni `_market_*` e `_proposal_*` sono importate sopra.


# ── Tool registrations ────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_account_state",
            description=(
                "Stato corrente del conto MT5: balance, equity, free_margin, "
                "posizioni aperte, P&L realizzato della giornata."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_market_snapshot",
            description=(
                "Snapshot mercato per il symbol indicato. Default 200 barre OHLC sul TF "
                "configurato + ultimo tick + indicatori legacy "
                "(sma_20/ema_50/rsi_14/atr_14) in `indicators` + ExtendedIndicators "
                "completo (Phase 2) in `indicators_extended` se disponibile. "
                "Override bar count con `bars` (50-500). "
                "Per replay point-in-time passare `as_of_ts` ISO8601 UTC (D-D1)."
            ),
            inputSchema=GET_MARKET_SNAPSHOT_SCHEMA,
        ),
        Tool(
            name="evaluate_trade_proposal",
            description=(
                "Valuta una TradeProposal nel risk engine SENZA inviare ordini. "
                "Ritorna la RiskDecision (approved/size_lots/reason)."
            ),
            inputSchema=_PROPOSAL_SCHEMA,
        ),
        Tool(
            name="submit_order_if_approved",
            description=(
                "Flow completo: TradeProposal → risk engine → "
                "(se approved e EXECUTION_MODE != shadow) → send_order. "
                "Ritorna decision + execution_mode."
            ),
            inputSchema=_PROPOSAL_SCHEMA,
        ),
        Tool(
            name="get_risk_profile",
            description="Parametri correnti del risk engine (RISK_MODE, soglie SL, drawdown, EXECUTION_MODE, ecc.).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_trade_history",
            description="Ultime N decisioni dal trades_log (default 10).",
            inputSchema={
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_symbol_universe",
            description=(
                "Restituisce l'universo dei simboli candidati dalla configurazione "
                "(cfg.SYMBOLS). Output compatto: lista, count, source."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_asset_class": {"type": "string"},
                },
                "required": [],
            },
        ),
        Tool(
            name="scan_symbol_candidates",
            description=(
                "Cheap scan multi-symbol. Per ogni simbolo: trend_bias, momentum_bias, "
                "volatility_state, spread_state, candidate_score, warnings. "
                "Niente OHLC completi."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {"type": "array", "items": {"type": "string"}},
                    "timeframe": {"type": "string"},
                },
                "required": ["symbols"],
            },
        ),
        Tool(
            name="get_symbol_indicators",
            description=(
                "Deep analysis su un singolo simbolo: SMA(20), EMA(50), RSI(14), ATR(14) "
                "calcolati su 100 barre. Tool dedicato alla shortlist."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string"},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="propose_trade",
            description=(
                "Formalizza la proposta finale dell'agente. NON esegue ordini e NON decide "
                "la size. Per eseguire usare submit_order_if_approved; per ottenere il "
                "verdetto del risk engine usare evaluate_trade_proposal."
            ),
            inputSchema=_PROPOSE_TRADE_SCHEMA,
        ),
        Tool(
            name="close_position",
            description=(
                "Chiude esplicitamente la posizione MT5 con il ticket dato, senza aprire "
                "una posizione opposta. Internamente usa Mt5Client.close_position "
                "(order_send con campo 'position' valorizzato). In modalità DRY_RUN "
                "non viene inviato alcun ordine reale."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "position_id": {
                        "type": "integer",
                        "description": "Ticket della posizione MT5 da chiudere",
                    },
                },
                "required": ["position_id"],
            },
        ),
        # Phase 6 Wave 2 — backtest control plane (MCP-01/02/03 + cancel D-A4)
        RUN_BACKTEST_TOOL,
        GET_BACKTEST_METRICS_TOOL,
        WALK_FORWARD_VALIDATE_TOOL,
        CANCEL_BACKTEST_TOOL,
    ]


# ── Dispatch ──────────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_account_state":
            return _text(handle_get_account_state(mt5))

        if name == "get_market_snapshot":
            return _text(_market_snapshot(arguments, mt5, cfg))

        if name == "evaluate_trade_proposal":
            return _text(_proposal_evaluate(arguments, mt5, cfg))

        if name == "submit_order_if_approved":
            return _text(_proposal_submit(arguments, mt5, cfg))

        if name == "get_risk_profile":
            return _text(handle_get_risk_profile(cfg))

        if name == "get_trade_history":
            n = int(arguments.get("n", 10))
            return _text(handle_get_trade_history(cfg, n))

        if name == "get_symbol_universe":
            return _text(_market_symbol_universe(
                cfg,
                filter_asset_class=arguments.get("filter_asset_class"),
            ))

        if name == "scan_symbol_candidates":
            return _text(_market_scan(arguments, mt5, cfg))

        if name == "get_symbol_indicators":
            return _text(_market_symbol_indicators(
                arguments["symbol"], mt5, cfg,
                timeframe=arguments.get("timeframe"),
            ))

        if name == "propose_trade":
            return _text(_proposal_propose(arguments, log, cfg))

        if name == "close_position":
            position_id = int(arguments["position_id"])
            if cfg.DRY_RUN:
                log.info("MCP close_position DRY_RUN ticket=%d (nessun ordine reale)", position_id)
                return _text({
                    "success": True,
                    "order_id": None,
                    "error_message": None,
                    "execution_mode": cfg.EXECUTION_MODE,
                    "dry_run": True,
                    "note": "DRY_RUN: nessun ordine inviato a MT5",
                })
            result = mt5.close_position(position_id)
            return _text({
                **dataclasses.asdict(result),
                "execution_mode": cfg.EXECUTION_MODE,
                "dry_run": False,
            })

        # Phase 6 Wave 2 — backtest control plane (MCP-01/02/03 + cancel D-A4)
        if name in (
            "run_backtest", "get_backtest_metrics",
            "walk_forward_validate", "cancel_backtest",
        ):
            if job_queue is None:
                return _text(envelope(
                    "internal_error",
                    "JobQueue non inizializzata: chiamare _bootstrap_state() prima",
                    tool=name,
                ))
            from logger import _trades_db_path
            db_path = str(_trades_db_path(cfg))
            costs_yaml_path = "data/configs/costs.yaml"
            if name == "run_backtest":
                return _text(handle_run_backtest(
                    arguments, job_queue, cfg, db_path, costs_yaml_path,
                ))
            if name == "get_backtest_metrics":
                return _text(handle_get_backtest_metrics(
                    arguments, job_queue, cfg,
                ))
            if name == "walk_forward_validate":
                return _text(handle_walk_forward_validate(
                    arguments, job_queue, cfg, db_path, costs_yaml_path,
                ))
            # cancel_backtest
            return _text(handle_cancel_backtest(arguments, job_queue, cfg))

        return _text({"error": f"unknown tool: {name}"})

    except Exception as exc:
        log.exception("MCP tool error: name=%s", name)
        return _text(envelope("internal_error", str(exc), tool=name))


# ── Server lifecycle ──────────────────────────────────────────────────────────

async def _serve() -> None:
    log.info("MCP server starting (mt5_ready=%s)", _mt5_ready)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
