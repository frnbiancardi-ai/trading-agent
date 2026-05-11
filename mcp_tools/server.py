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

# Singleton globali — inizializzati al boot del server (e non al solo import del modulo,
# così i test possono importare mcp_tools.server senza far partire MT5).
cfg = Config()
log = init_logger(cfg)
mt5 = Mt5Client(cfg)
_mt5_ready: bool = False


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
    """Phase 6 Wave 1: placeholder. Wave 2 aggiunge JobQueue init; Wave 3 aggiunge trail_table.ensure."""
    # IMPLEMENTATO in Wave 2 (06-03-PLAN) e Wave 3 (06-04-PLAN)
    pass


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


# ── Handler legacy ancora inline (verranno spostati in Wave 1 handlers) ──────

def _build_proposal(args: dict):
    """Costruisce TradeProposal dagli args del tool. Usato da evaluate e submit."""
    from models import TradeProposal
    return TradeProposal(
        symbol=args["symbol"],
        direction=args["direction"],
        entry_price=args["entry_price"],
        stop_loss_price=args["stop_loss_price"],
        take_profit_price=args["take_profit_price"],
        timeframe=cfg.TIMEFRAME,
        comment="mcp",
        confidence=args["confidence"],
        rationale=args["rationale"],
    )


def handle_get_symbol_universe(filter_asset_class: str | None = None) -> dict:
    """Restituisce l'universo dei simboli candidati dalla configurazione."""
    symbols = list(getattr(cfg, "SYMBOLS", []) or [])
    return {
        "symbols": symbols,
        "count": len(symbols),
        "source": "config.SYMBOLS",
        "filter_asset_class": filter_asset_class,
    }


def handle_scan_symbol_candidates(symbols: list[str], timeframe: str | None = None) -> dict:
    """Cheap scan multi-symbol. Output compatto: nessun OHLC completo."""
    from claude_agent import cheap_scan_symbol
    tf = timeframe or cfg.TIMEFRAME
    candidates = [
        dataclasses.asdict(cheap_scan_symbol(mt5, tf, sym))
        for sym in symbols
    ]
    return {
        "timeframe": tf,
        "count": len(candidates),
        "candidates": candidates,
    }


def handle_get_symbol_indicators(symbol: str, timeframe: str | None = None) -> dict:
    """Indicatori approfonditi per un singolo simbolo. SMA(20), EMA(50), RSI(14), ATR(14)."""
    from indicators import compute_all
    tf = timeframe or cfg.TIMEFRAME
    ohlc = mt5.get_ohlc(symbol, tf, 100)
    if not ohlc:
        return {"error": "no ohlc data", "symbol": symbol, "timeframe": tf}
    indicators = compute_all(ohlc)
    return {
        "symbol": symbol,
        "timeframe": tf,
        "bars_used": len(ohlc),
        "last_close": ohlc[-1]["close"],
        "indicators": indicators,
    }


def handle_propose_trade(args: dict) -> dict:
    """Formalizza una proposta finale dell'agente. NON esegue ordini, NON decide size."""
    from models import TradeProposal
    timeframe = args.get("timeframe") or cfg.TIMEFRAME
    proposal = TradeProposal(
        symbol=args["symbol"],
        direction=args["direction"],
        entry_price=float(args["entry_price"]),
        stop_loss_price=float(args["stop_loss_price"]),
        take_profit_price=float(args["take_profit_price"]),
        timeframe=timeframe,
        comment="mcp_propose_trade",
        confidence=float(args["confidence"]),
        rationale=args["rationale"],
    )
    log.info(
        "MCP propose_trade formalized: symbol=%s direction=%s confidence=%.2f",
        proposal.symbol, proposal.direction, proposal.confidence,
    )
    return {
        "status": "proposed",
        "executed": False,
        "proposal": dataclasses.asdict(proposal),
        "next_step": "call evaluate_trade_proposal or submit_order_if_approved to act on it",
    }


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
    ]


# ── Dispatch ──────────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_account_state":
            return _text(handle_get_account_state(mt5))

        if name == "get_market_snapshot":
            from mcp_tools.handlers.market import handle_get_market_snapshot as _snap
            return _text(_snap(arguments, mt5, cfg))

        if name == "evaluate_trade_proposal":
            from risk_engine import evaluate_trade
            proposal = _build_proposal(arguments)
            account = mt5.get_account_state()
            decision = evaluate_trade(proposal, account, mt5, cfg)
            return _text(dataclasses.asdict(decision))

        if name == "submit_order_if_approved":
            from execution import run_once
            proposal = _build_proposal(arguments)
            decision = run_once(proposal.symbol, proposal, cfg, mt5, log)
            return _text({
                "decision": dataclasses.asdict(decision) if decision is not None else None,
                "execution_mode": cfg.EXECUTION_MODE,
                "note": "send_order eseguito solo se approved AND EXECUTION_MODE != shadow",
            })

        if name == "get_risk_profile":
            return _text(handle_get_risk_profile(cfg))

        if name == "get_trade_history":
            n = int(arguments.get("n", 10))
            return _text(handle_get_trade_history(cfg, n))

        if name == "get_symbol_universe":
            return _text(handle_get_symbol_universe(
                filter_asset_class=arguments.get("filter_asset_class"),
            ))

        if name == "scan_symbol_candidates":
            return _text(handle_scan_symbol_candidates(
                symbols=arguments.get("symbols") or [],
                timeframe=arguments.get("timeframe"),
            ))

        if name == "get_symbol_indicators":
            return _text(handle_get_symbol_indicators(
                symbol=arguments["symbol"],
                timeframe=arguments.get("timeframe"),
            ))

        if name == "propose_trade":
            return _text(handle_propose_trade(arguments))

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

        return _text({"error": f"unknown tool: {name}"})

    except Exception as exc:
        log.exception("MCP tool error: name=%s", name)
        return _text(envelope("internal_error", str(exc), tool=name))


# ── Server lifecycle ──────────────────────────────────────────────────────────

async def _serve() -> None:
    log.info("MCP server starting (mt5_ready=%s)", _mt5_ready)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
