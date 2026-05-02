"""
mcp_server.py — Server MCP locale per trading-agent.

Compatibile con mcp >= 1.27.0 (SDK ufficiale Anthropic). API verificata su 1.27.0:
  from mcp.server import Server
  from mcp.server.stdio import stdio_server
  from mcp.types import Tool, TextContent
  @server.list_tools() / @server.call_tool()

IMPORTANTE: il protocollo MCP usa stdin/stdout per JSON-RPC.
Tutti i log devono finire su stderr o file (mai stdout) per non rompere il protocollo.
Il logger configurato in `logger.py` scrive solo su file (RotatingFileHandler) — sicuro.
"""
import asyncio
import dataclasses
import json
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from claude_agent import cheap_scan_symbol
from config import Config
from execution import run_once
from indicators import compute_all
from logger import init_logger
from models import TradeProposal
from mt5_client import Mt5Client
from risk_engine import evaluate_trade

# Singleton globali — inizializzati al boot del server (e non al solo import del modulo,
# così i test possono importare mcp_server senza far partire MT5).
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


server: Server = Server("trading-agent")


def _text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, default=str, ensure_ascii=False))]


def _build_proposal(args: dict) -> TradeProposal:
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


_PROPOSAL_SCHEMA = {
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

_PROPOSE_TRADE_SCHEMA = {
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
                "50 barre OHLC sul timeframe configurato + ultimo tick + indicatori "
                "(sma_20, ema_50, rsi_14, atr_14) per il symbol indicato."
            ),
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
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


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_account_state":
            state = mt5.get_account_state()
            return _text(dataclasses.asdict(state))

        if name == "get_market_snapshot":
            symbol = arguments["symbol"]
            ohlc = mt5.get_ohlc(symbol, cfg.TIMEFRAME, 50)
            sym_info = mt5.get_symbol_info(symbol)
            tick: dict = {}
            if sym_info is not None:
                tick = {
                    "bid": getattr(sym_info, "bid", None),
                    "ask": getattr(sym_info, "ask", None),
                    "point": getattr(sym_info, "point", None),
                    "digits": getattr(sym_info, "digits", None),
                }
            indicators = compute_all(ohlc) if ohlc else {}
            return _text({
                "symbol": symbol,
                "timeframe": cfg.TIMEFRAME,
                "ohlc": ohlc,
                "tick": tick,
                "indicators": indicators,
            })

        if name == "evaluate_trade_proposal":
            proposal = _build_proposal(arguments)
            account = mt5.get_account_state()
            decision = evaluate_trade(proposal, account, mt5, cfg)
            return _text(dataclasses.asdict(decision))

        if name == "submit_order_if_approved":
            proposal = _build_proposal(arguments)
            decision = run_once(proposal.symbol, proposal, cfg, mt5, log)
            return _text({
                "decision": dataclasses.asdict(decision) if decision is not None else None,
                "execution_mode": cfg.EXECUTION_MODE,
                "note": "send_order eseguito solo se approved AND EXECUTION_MODE != shadow",
            })

        if name == "get_risk_profile":
            return _text({
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
            })

        if name == "get_trade_history":
            n = int(arguments.get("n", 10))
            db_path = Path(cfg.LOG_FILE).parent / "trades.db"
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT id, timestamp, symbol, direction, size_lots, entry_price, "
                    "stop_loss, take_profit, decision_reason, approved, pnl_realized "
                    "FROM trades_log ORDER BY id DESC LIMIT ?",
                    (n,),
                )
                rows = [dict(r) for r in cur.fetchall()]
            return _text(rows)

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
        return _text({"error": str(exc), "tool": name})


async def _serve() -> None:
    log.info("MCP server starting (mt5_ready=%s)", _mt5_ready)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    _bootstrap_mt5()
    try:
        asyncio.run(_serve())
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass
