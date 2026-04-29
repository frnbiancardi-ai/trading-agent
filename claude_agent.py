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
from models import AccountState, ScannerDecision, SymbolScanCandidate, TradeProposal
from mt5_client import Mt5Client

_TZ_ROME = ZoneInfo("Europe/Rome")
_MAX_ITERATIONS = 6
_MAX_ITERATIONS_SCANNER = 8
_OHLC_BARS_SNAPSHOT = 50
_OHLC_BARS_INDICATORS = 100
_OHLC_BARS_SCAN = 30
_DEFAULT_MAX_SYMBOLS_TO_DEEPEN = 5


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
        with open(prompt_dir / "system_prompt_scanner.txt", encoding="utf-8") as f:
            self.system_prompt_scanner = f.read()
        with open(prompt_dir / "context_template_scanner.txt", encoding="utf-8") as f:
            self.context_template_scanner = f.read()

        self.tools = self._build_tools()
        self.scanner_tools = self.build_scanner_tools()

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
            min_sl_pips=self.cfg.MIN_SL_PIPS,
            max_sl_pips=self.cfg.MAX_SL_PIPS,
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

    def build_scanner_tools(self) -> list[dict]:
        return [
            {
                "name": "get_account_status",
                "description": "Stato corrente del conto MT5: balance, equity, free_margin, posizioni aperte, P&L realizzato della giornata.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "get_risk_profile",
                "description": "Parametri correnti del risk engine (MIN_SL_PIPS, MAX_SL_PIPS, MAX_LOTS_PER_TRADE, EXECUTION_MODE, RISK_MODE).",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "scan_symbol_candidates",
                "description": (
                    "Cheap scan multi-symbol: per ogni simbolo della lista, calcola metriche sintetiche "
                    "(trend_bias, momentum_bias, volatility_state, spread_state, candidate_score, warnings). "
                    "Output compatto, niente OHLC completi."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbols": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["symbols"],
                },
            },
            {
                "name": "get_symbol_indicators",
                "description": "Deep analysis su un singolo simbolo: SMA(20), EMA(50), RSI(14), ATR(14) sulla finestra di analisi configurata.",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            },
            {
                "name": "propose_trade",
                "description": (
                    "Proponi UN trade al risk engine. Verrà valutato deterministicamente. "
                    "Chiama solo se confidence >= 0.60 e l'edge è chiaro su un solo simbolo."
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

    def _cheap_scan_one(self, symbol: str) -> SymbolScanCandidate:
        ohlc = self.mt5.get_ohlc(symbol, self.cfg.TIMEFRAME, _OHLC_BARS_SCAN)
        if not ohlc:
            return SymbolScanCandidate(
                symbol=symbol,
                trend_bias="UNKNOWN",
                momentum_bias="UNKNOWN",
                volatility_state="UNKNOWN",
                spread_state="UNKNOWN",
                candidate_score=0.0,
                warnings=["no_ohlc_data"],
            )

        indicators = compute_all(ohlc)
        last_close = ohlc[-1]["close"]
        sma_20 = indicators.get("sma_20")
        ema_50 = indicators.get("ema_50")
        rsi = indicators.get("rsi_14")
        atr = indicators.get("atr_14")

        sym_info = self.mt5.get_symbol_info(symbol)
        bid = getattr(sym_info, "bid", None) if sym_info is not None else None
        ask = getattr(sym_info, "ask", None) if sym_info is not None else None
        point = getattr(sym_info, "point", None) if sym_info is not None else None

        warnings: list[str] = []

        if sma_20 is not None and ema_50 is not None:
            if last_close > sma_20 and sma_20 > ema_50:
                trend = "BULLISH"
            elif last_close < sma_20 and sma_20 < ema_50:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
        else:
            trend = "UNKNOWN"
            warnings.append("missing_ma")

        if rsi is not None:
            if rsi >= 60:
                momentum = "STRONG_BULL"
            elif rsi <= 40:
                momentum = "STRONG_BEAR"
            elif 45 <= rsi <= 55:
                momentum = "NEUTRAL"
            else:
                momentum = "WEAK"
        else:
            momentum = "UNKNOWN"
            warnings.append("missing_rsi")

        if atr is not None and last_close:
            atr_pct = atr / last_close * 100.0
            if atr_pct >= 0.5:
                vol = "HIGH"
            elif atr_pct <= 0.1:
                vol = "LOW"
            else:
                vol = "NORMAL"
        else:
            vol = "UNKNOWN"
            warnings.append("missing_atr")

        if bid is not None and ask is not None and point:
            spread_pips = (ask - bid) / point / 10.0
            if spread_pips < 1.0:
                spread_state = "TIGHT"
            elif spread_pips < 3.0:
                spread_state = "NORMAL"
            else:
                spread_state = "WIDE"
                warnings.append("wide_spread")
        else:
            spread_state = "UNKNOWN"
            warnings.append("missing_spread")

        score = 0.3
        if trend == "BULLISH" and momentum == "STRONG_BULL":
            score = 0.8
        elif trend == "BEARISH" and momentum == "STRONG_BEAR":
            score = 0.8
        elif trend in ("BULLISH", "BEARISH") and momentum == "WEAK":
            score = 0.5
        elif trend == "NEUTRAL":
            score = 0.2

        if vol == "HIGH":
            score *= 0.9
        if spread_state == "WIDE":
            score *= 0.6
        if "no_ohlc_data" in warnings:
            score = 0.0

        return SymbolScanCandidate(
            symbol=symbol,
            trend_bias=trend,
            momentum_bias=momentum,
            volatility_state=vol,
            spread_state=spread_state,
            candidate_score=round(score, 3),
            warnings=warnings,
        )

    def _dispatch_scanner_tool(self, name: str, input_: dict) -> dict:
        if name == "get_account_status":
            return self._dispatch_tool(name, input_)

        if name == "get_risk_profile":
            return {
                "MIN_SL_PIPS": self.cfg.MIN_SL_PIPS,
                "MAX_SL_PIPS": self.cfg.MAX_SL_PIPS,
                "MAX_LOTS_PER_TRADE": self.cfg.MAX_LOTS_PER_TRADE,
                "EXECUTION_MODE": self.cfg.EXECUTION_MODE,
                "RISK_MODE": self.cfg.RISK_MODE,
            }

        if name == "scan_symbol_candidates":
            symbols = input_.get("symbols") or []
            candidates = [
                dataclasses.asdict(self._cheap_scan_one(s))
                for s in symbols
            ]
            return {"candidates": candidates}

        if name == "get_symbol_indicators":
            symbol = input_["symbol"]
            ohlc = self.mt5.get_ohlc(symbol, self.cfg.TIMEFRAME, _OHLC_BARS_INDICATORS)
            return compute_all(ohlc) if ohlc else {"error": "no ohlc data", "symbol": symbol}

        return {"error": f"unknown scanner tool: {name}"}

    def run_market_scan(
        self,
        candidate_symbols: list[str],
        timeframe: str,
        account_state: AccountState,
    ) -> TradeProposal | None:
        decision = self._run_market_scan_internal(candidate_symbols, timeframe, account_state)
        return decision.proposal

    def _run_market_scan_internal(
        self,
        candidate_symbols: list[str],
        timeframe: str,
        account_state: AccountState,
    ) -> ScannerDecision:
        if not candidate_symbols:
            self.log.warning("ClaudeAgent scanner: empty candidate_symbols")
            return ScannerDecision(proposal=None, stop_reason="no_candidates")

        max_to_deepen = getattr(self.cfg, "MAX_SYMBOLS_TO_DEEPEN", _DEFAULT_MAX_SYMBOLS_TO_DEEPEN)
        now_local = datetime.now(tz=_TZ_ROME).strftime("%Y-%m-%d %H:%M:%S")
        context = self.context_template_scanner.format(
            candidate_symbols=", ".join(candidate_symbols),
            timeframe=timeframe,
            now_local=now_local,
            execution_mode=self.cfg.EXECUTION_MODE,
            min_sl_pips=self.cfg.MIN_SL_PIPS,
            max_sl_pips=self.cfg.MAX_SL_PIPS,
            max_symbols_to_deepen=max_to_deepen,
            balance=account_state.balance,
            equity=account_state.equity,
            free_margin=account_state.free_margin,
            open_positions_count=len(account_state.open_positions),
        )

        messages: list[dict] = [{"role": "user", "content": context}]
        proposal: TradeProposal | None = None

        for iteration in range(_MAX_ITERATIONS_SCANNER):
            response = self.client.messages.create(
                model=self.cfg.CLAUDE_MODEL,
                max_tokens=self.cfg.CLAUDE_MAX_TOKENS,
                temperature=self.cfg.CLAUDE_TEMPERATURE,
                system=self.system_prompt_scanner,
                tools=self.scanner_tools,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                self.log.info(
                    "ClaudeAgent scanner NO_TRADE stop_reason=%s iter=%d",
                    response.stop_reason, iteration,
                )
                return ScannerDecision(
                    proposal=None,
                    iterations_used=iteration + 1,
                    stop_reason=response.stop_reason or "end_turn",
                )

            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict] = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                if block.name == "propose_trade" and proposal is None:
                    proposal = TradeProposal(
                        symbol=block.input["symbol"],
                        direction=block.input["direction"],
                        entry_price=block.input["entry_price"],
                        stop_loss_price=block.input["stop_loss_price"],
                        take_profit_price=block.input["take_profit_price"],
                        timeframe=timeframe,
                        comment="claude_scanner",
                        confidence=block.input["confidence"],
                        rationale=block.input["rationale"],
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"received": True}),
                    })
                elif block.name == "propose_trade":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": "max one proposal per scan"}),
                    })
                else:
                    try:
                        result = self._dispatch_scanner_tool(block.name, block.input)
                    except Exception as exc:
                        self.log.warning(
                            "scanner tool dispatch failed: name=%s err=%s", block.name, exc,
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
                    "ClaudeAgent scanner PROPOSAL symbol=%s direction=%s confidence=%.2f iter=%d",
                    proposal.symbol, proposal.direction, proposal.confidence, iteration,
                )
                return ScannerDecision(
                    proposal=proposal,
                    iterations_used=iteration + 1,
                    stop_reason="proposal_received",
                )

        self.log.warning(
            "ClaudeAgent scanner: max iterations (%d) reached without proposal",
            _MAX_ITERATIONS_SCANNER,
        )
        return ScannerDecision(
            proposal=None,
            iterations_used=_MAX_ITERATIONS_SCANNER,
            stop_reason="max_iterations",
        )

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
