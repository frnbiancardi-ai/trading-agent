import dataclasses
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from anthropic import Anthropic

from config import Config
from indicators import compute_all
from models import AccountState, TradeProposal
from mt5_client import Mt5Client

_TZ_ROME = ZoneInfo("Europe/Rome")
_MAX_ITERATIONS = 6
_OHLC_BARS_SNAPSHOT = 50
_OHLC_BARS_INDICATORS = 100


class ClaudeAgent:
    def __init__(self, cfg: Config, mt5_client: Mt5Client, logger: logging.Logger):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger
        self.client = Anthropic(api_key=cfg.CLAUDE_API_KEY or "missing-key")

        prompt_dir = Path("prompts")
        with open(prompt_dir / "system_prompt.txt", encoding="utf-8") as f:
            self.system_prompt = f.read()
        with open(prompt_dir / "context_template.txt", encoding="utf-8") as f:
            self.context_template = f.read()

        self.tools = self._build_tools()

    def _build_tools(self) -> list[dict]:
        return [
            {
                "name": "get_account_status",
                "description": "Restituisce lo stato corrente del conto MT5: balance, equity, free_margin, posizioni aperte, P&L realizzato della giornata.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_market_snapshot",
                "description": (
                    "Restituisce le ultime 50 barre OHLC sul timeframe configurato e l'ultimo tick "
                    "(bid, ask, point, digits) per il symbol indicato."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "get_indicators",
                "description": "Calcola SMA(20), EMA(50), RSI(14), ATR(14) sull'ultima barra OHLC del symbol.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "propose_trade",
                "description": (
                    "Proponi un trade al risk engine. Verrà valutato deterministicamente. "
                    "Chiama questo tool solo se confidence ≥ 0.6 e l'edge è chiaro."
                ),
                "input_schema": {
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
                },
            },
        ]

    def _dispatch_tool(self, name: str, input_: dict) -> dict:
        if name == "get_account_status":
            state = self.mt5.get_account_state()
            return dataclasses.asdict(state)

        if name == "get_market_snapshot":
            symbol = input_["symbol"]
            ohlc = self.mt5.get_ohlc(symbol, self.cfg.TIMEFRAME, _OHLC_BARS_SNAPSHOT)
            sym_info = self.mt5.get_symbol_info(symbol)
            last_tick = {}
            if sym_info is not None:
                last_tick = {
                    "bid": getattr(sym_info, "bid", None),
                    "ask": getattr(sym_info, "ask", None),
                    "point": getattr(sym_info, "point", None),
                    "digits": getattr(sym_info, "digits", None),
                }
            return {
                "symbol": symbol,
                "timeframe": self.cfg.TIMEFRAME,
                "ohlc": ohlc,
                "last_tick": last_tick,
            }

        if name == "get_indicators":
            symbol = input_["symbol"]
            ohlc = self.mt5.get_ohlc(symbol, self.cfg.TIMEFRAME, _OHLC_BARS_INDICATORS)
            return compute_all(ohlc)

        return {"error": f"unknown tool: {name}"}

    def run_cycle(self, symbol: str, account_state: AccountState) -> TradeProposal | None:
        now_local = datetime.now(tz=_TZ_ROME).strftime("%Y-%m-%d %H:%M:%S")
        context = self.context_template.format(
            symbol=symbol,
            timeframe=self.cfg.TIMEFRAME,
            execution_mode=self.cfg.EXECUTION_MODE,
            balance=account_state.balance,
            equity=account_state.equity,
            free_margin=account_state.free_margin,
            open_positions_count=len(account_state.open_positions),
            now_local=now_local,
        )

        messages: list[dict] = [{"role": "user", "content": context}]

        for iteration in range(_MAX_ITERATIONS):
            response = self.client.messages.create(
                model=self.cfg.CLAUDE_MODEL,
                max_tokens=self.cfg.CLAUDE_MAX_TOKENS,
                temperature=self.cfg.CLAUDE_TEMPERATURE,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                self.log.info(
                    "ClaudeAgent NO_TRADE symbol=%s stop_reason=%s iter=%d",
                    symbol, response.stop_reason, iteration,
                )
                return None

            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict] = []
            proposal: TradeProposal | None = None
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                if block.name == "propose_trade":
                    proposal = TradeProposal(
                        symbol=block.input["symbol"],
                        direction=block.input["direction"],
                        entry_price=block.input["entry_price"],
                        stop_loss_price=block.input["stop_loss_price"],
                        take_profit_price=block.input["take_profit_price"],
                        timeframe=self.cfg.TIMEFRAME,
                        comment="claude",
                        confidence=block.input["confidence"],
                        rationale=block.input["rationale"],
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"received": True}),
                    })
                else:
                    try:
                        result = self._dispatch_tool(block.name, block.input)
                    except Exception as exc:
                        self.log.warning(
                            "tool dispatch failed: name=%s err=%s", block.name, exc,
                        )
                        result = {"error": str(exc)}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

            messages.append({"role": "user", "content": tool_results})

            if proposal is not None:
                self.log.info(
                    "ClaudeAgent PROPOSAL symbol=%s direction=%s confidence=%.2f",
                    proposal.symbol, proposal.direction, proposal.confidence,
                )
                return proposal

        self.log.warning(
            "ClaudeAgent: max iterations (%d) reached without proposal for %s",
            _MAX_ITERATIONS, symbol,
        )
        return None

    def explain_last_trades(self, n: int = 5) -> str:
        db_path = Path(self.cfg.LOG_FILE).parent / "trades.db"
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT timestamp, symbol, direction, size_lots, entry_price, "
                "stop_loss, take_profit, decision_reason, approved, pnl_realized "
                "FROM trades_log ORDER BY id DESC LIMIT ?",
                (n,),
            )
            rows = [dict(r) for r in cur.fetchall()]

        prompt = (
            "Spiega in italiano queste ultime decisioni di trading prese dal sistema. "
            "Per ciascuna evidenzia simbolo, direzione, esito (approvata/rifiutata) e motivo. "
            "Sii conciso, una frase per decisione.\n\n"
            "Dati JSON:\n"
            + json.dumps(rows, ensure_ascii=False, indent=2, default=str)
        )

        response = self.client.messages.create(
            model=self.cfg.CLAUDE_MODEL,
            max_tokens=self.cfg.CLAUDE_MAX_TOKENS,
            temperature=self.cfg.CLAUDE_TEMPERATURE,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        return "\n".join(parts) if parts else ""
