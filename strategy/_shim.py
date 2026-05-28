"""IntradayStrategy shim — wrapper non-pure che preserva la firma legacy
(D-01: scheduler/scanner/mcp_server/claude_agent NON devono cambiare).

Wave 3 plan-07 (STRAT-09):
  - __init__: stessa firma del legacy (cfg, mt5_client, logger=None, environment=None)
  - analyze_symbol(symbol, account_state, sentiment=None) -> TechnicalSetup:
      route attraverso build_ctx_live → evaluate_proposal_for_bar →
      draft_to_technical_setup → _apply_sentiment (verbatim legacy).
  - Metodi non-pure preservati VERBATIM dal legacy (delegando alle utility
    in strategy.risk_utils):
      evaluate_open_position, compute_existing_potential_loss_amount,
      would_proposal_exceed_drawdown, is_addon_for, build_delayed_followup,
      _apply_sentiment, _is_context_negative_for_position, _none_setup.

Modulo NON pure-fn (logger + datetime.now + chiamate broker via mt5_client) →
ESCLUSO dal purity gate. È il bridge tra il vecchio scheduler-based runtime
e il nuovo motore puro `evaluate_proposal_for_bar`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from models import (
    AccountState,
    BrokerProtocol,
    DelayedFollowUpRequest,
    OpenPositionVerdict,
    PositionInfo,
    SentimentAnalysis,
    TechnicalSetup,
    TradeProposal,
)
from strategy.adapters.live import build_ctx_live
from strategy.proposal import draft_to_technical_setup
from strategy.risk_utils import (
    estimate_position_risk_amount,
    estimate_proposal_lots,
    estimate_proposal_risk_amount,
)


class StrategyEnvironment:
    """Verifica i gate di contesto (finestra intraday, weekday, news window).

    Lift verbatim da strategy_legacy.py — preservato come attributo del package
    per backward-compat con scheduler.py/main.py che lo importano da `strategy`.
    """

    def __init__(
        self,
        cfg,
        log: logging.Logger | None = None,
        news_window_callable=None,
    ) -> None:
        self.cfg = cfg
        self.log = log or logging.getLogger(__name__)
        self._news_window_callable = news_window_callable

    def is_intraday_window(self, now: datetime) -> bool:
        cfg = self.cfg
        return cfg.INTRADAY_START_HOUR <= now.hour < cfg.INTRADAY_END_HOUR

    def is_weekday(self, now: datetime) -> bool:
        return now.weekday() in set(self.cfg.OPERATING_WEEKDAYS)

    def is_weekend(self, now: datetime) -> bool:
        return not self.is_weekday(now)

    def is_news_window(self, now: datetime) -> bool:
        cfg = self.cfg
        if not getattr(cfg, "AVOID_MAJOR_NEWS_TIMES", True):
            return False
        if self._news_window_callable is not None:
            try:
                return bool(self._news_window_callable(now))
            except Exception as exc:
                self.log.warning("news_window_callable failed: %s", exc)
                return False
        return False


class IntradayStrategy:
    """Shim Wave 3: preserva firma legacy, internamente chiama evaluate_proposal_for_bar.

    Differenze vs legacy strategy_legacy.IntradayStrategy:
      - _analyze_technical / identify_entry_setup / build_trade_proposal /
        _compute_levels / _score_confidence: REMOVED. Sostituiti dal flusso
        evaluate_proposal_for_bar → draft_to_technical_setup → _apply_sentiment.
      - analyze_symbol: stessa firma + return type, comportamento riallineato
        al motore puro.
      - Tutti gli altri metodi pubblici (evaluate_open_position, ecc.): preservati.
    """

    def __init__(
        self,
        cfg,
        mt5_client: BrokerProtocol,
        logger: logging.Logger | None = None,
        environment: StrategyEnvironment | None = None,
    ):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger or logging.getLogger(__name__)
        self.env = environment or StrategyEnvironment(cfg, self.log)

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def analyze_symbol(
        self,
        symbol: str,
        account_state: AccountState,
        sentiment: SentimentAnalysis | None = None,
    ) -> TechnicalSetup:
        """Pipeline Wave 3:
          build_ctx_live → evaluate_proposal_for_bar → draft_to_technical_setup
          → _apply_sentiment (legacy).
        """
        from strategy import evaluate_proposal_for_bar  # lazy: evita ciclo all'import

        cfg = self.cfg
        timeframe = cfg.INTRADAY_TIMEFRAME

        # Costruzione StrategyContext (single-compute D-12 dentro l'adapter)
        try:
            ctx = build_ctx_live(
                symbol=symbol,
                mt5_client=self.mt5,
                profile=getattr(cfg, "RISK_MODE", "MODERATE"),
                cfg=cfg,
                intermarket_score_fn=None,
                news_blackout_fn=getattr(self.env, "is_news_window", None) if self.env else None,
            )
        except RuntimeError as exc:
            self.log.warning("build_ctx_live fallito per %s: %s", symbol, exc)
            return self._none_setup(symbol, timeframe, f"ohlc_error: {exc}")

        bars = ctx._bars
        indicators = ctx._indicators

        # Guard storia minima (lift dalla legacy 188-189)
        if not bars or len(bars) < 50:
            return self._none_setup(symbol, timeframe, "insufficient_bars")

        # Single shared call site (D-09)
        draft = evaluate_proposal_for_bar(bars, indicators, ctx)
        setup = draft_to_technical_setup(draft, symbol, timeframe)

        # Backward-compat: arricchisci setup.indicators con i campi legacy
        # (sma_20, rsi_14, atr_14, last_close, pip_size, risk_reward) usati da
        # backtest engine decision_context_json + _is_context_negative_for_position.
        self._enrich_legacy_indicators(setup, bars, indicators, ctx)

        # Sentiment overlay (verbatim legacy 642-723)
        setup = self._apply_sentiment(setup, sentiment)
        return setup

    def _enrich_legacy_indicators(
        self,
        setup: TechnicalSetup,
        bars: list,
        indicators,
        ctx,
    ) -> None:
        """Inserisce i campi indicator legacy (sma_20, rsi_14, atr_14, ema_50,
        last_close, pip_size, risk_reward) in setup.indicators per backward-compat
        con backtest engine decision_context_json + position-negative-check.
        """
        try:
            from indicators.trend import sma
            closes = [b["close"] for b in bars] if bars else []
            sma20 = None
            sma50 = None
            if closes:
                sma20_series = sma(closes, 20)
                sma50_series = sma(closes, 50)
                sma20 = sma20_series[-1] if sma20_series and sma20_series[-1] is not None else None
                sma50 = sma50_series[-1] if sma50_series and sma50_series[-1] is not None else None

            rsi_last = None
            atr_last = None
            ema50_last = None
            if indicators is not None:
                rsi_seq = getattr(indicators, "rsi_14", None)
                atr_seq = getattr(indicators, "atr_14", None)
                ema50_seq = getattr(indicators, "ema50", None)
                if rsi_seq:
                    for v in reversed(rsi_seq):
                        if v is not None:
                            rsi_last = v
                            break
                if atr_seq:
                    for v in reversed(atr_seq):
                        if v is not None:
                            atr_last = v
                            break
                if ema50_seq:
                    for v in reversed(ema50_seq):
                        if v is not None:
                            ema50_last = v
                            break

            last_close = closes[-1] if closes else None

            # Risk:reward derivato dai prezzi setup
            rr = 0.0
            if (
                setup.setup_type == "READY"
                and setup.entry_price is not None
                and setup.stop_loss is not None
                and setup.take_profit is not None
            ):
                if setup.direction == "BUY":
                    risk = setup.entry_price - setup.stop_loss
                    reward = setup.take_profit - setup.entry_price
                else:
                    risk = setup.stop_loss - setup.entry_price
                    reward = setup.entry_price - setup.take_profit
                rr = (reward / risk) if risk > 0 else 0.0

            if setup.indicators is None:
                setup.indicators = {}
            setup.indicators.setdefault("sma_20", sma20)
            setup.indicators.setdefault("sma_50", sma50)
            setup.indicators.setdefault("ema_50", ema50_last)
            setup.indicators.setdefault("rsi_14", rsi_last)
            setup.indicators.setdefault("atr_14", atr_last)
            setup.indicators.setdefault("last_close", last_close)
            setup.indicators.setdefault("pip_size", ctx.pip_size if ctx else 0.0001)
            setup.indicators["risk_reward"] = round(rr, 4)

            # support_resistance dal context (legacy lo popolava da find_support_resistance)
            if setup.support_resistance is None and ctx is not None and ctx.sr:
                setup.support_resistance = dict(ctx.sr)
        except Exception:
            # Enrichment è best-effort: errori non devono spezzare il flow.
            pass

    def _analyze_technical(
        self,
        symbol: str,
        account_state: AccountState,
    ) -> TechnicalSetup:
        """Alias backward-compat per evaluate_open_position (chiamata interna senza sentiment).

        Il legacy IntradayStrategy aveva _analyze_technical come metodo separato
        che _analyze_symbol_ chiamava internamente. tests/test_phase16.py patcha
        questo metodo via `strategy._analyze_technical = fake` per simulare
        contesti READY/NONE senza alimentare bars/indicators.
        """
        return self.analyze_symbol(symbol, account_state, sentiment=None)

    def build_trade_proposal(
        self,
        symbol: str,
        setup: TechnicalSetup,
        bars: list | None = None,
        indicators: dict | None = None,
        account_state: AccountState | None = None,
    ) -> TradeProposal:
        """Converte TechnicalSetup READY in TradeProposal (verbatim legacy 389-417).

        Preservato sul shim per backward-compat: backtest/engine.py:168 e altri
        caller esterni continuano a chiamarlo. Il `comment` è fissato a
        'python_strategy' per parity con la convenzione legacy.
        """
        if setup.setup_type != "READY" or setup.direction is None:
            raise ValueError(
                f"build_trade_proposal richiede setup READY, ricevuto {setup.setup_type}"
            )
        if setup.entry_price is None or setup.stop_loss is None or setup.take_profit is None:
            raise ValueError("setup READY senza entry/sl/tp")

        rr = (setup.indicators or {}).get("risk_reward", 0)
        rationale = (
            f"{setup.direction} {symbol} su {setup.timeframe}: {setup.reason}. "
            f"Confidence {setup.confidence:.2f}, R:R {rr:.2f}."
        )
        return TradeProposal(
            symbol=symbol,
            direction=setup.direction,
            entry_price=setup.entry_price,
            stop_loss_price=setup.stop_loss,
            take_profit_price=setup.take_profit,
            timeframe=setup.timeframe,
            comment="python_strategy",
            confidence=setup.confidence,
            rationale=rationale,
        )

    def evaluate_open_position(
        self,
        position: PositionInfo,
        account_state: AccountState,
        now: datetime | None = None,
    ) -> OpenPositionVerdict:
        """Decide se chiudere/mantenere una posizione esistente nel ciclo H24
        (verbatim legacy 419-479).
        """
        cfg = self.cfg
        now = now or datetime.now()
        ticket = int(getattr(position, "ticket", 0) or 0)

        if (
            getattr(cfg, "CLOSE_BEFORE_END_OF_WINDOW", True)
            and self.env.is_weekday(now)
            and not self.env.is_intraday_window(now)
            and position.symbol in cfg.INTRADAY_SYMBOLS
        ):
            return OpenPositionVerdict(
                symbol=position.symbol, ticket=ticket,
                action="CLOSE_END_OF_DAY",
                reason="fuori_finestra_intraday_no_overnight",
            )

        try:
            sym_info = self.mt5.get_symbol_info(position.symbol)
        except Exception as exc:
            self.log.warning("evaluate_open_position symbol_info fallito %s: %s", position.symbol, exc)
            sym_info = None

        risk_amount = estimate_position_risk_amount(position, sym_info)
        profit_r = (position.profit / risk_amount) if risk_amount > 0 else 0.0

        # Usa _analyze_technical (alias di analyze_symbol senza sentiment) per
        # consentire il monkeypatch test_phase16._patch_analyze_technical.
        setup = self._analyze_technical(position.symbol, account_state)
        is_negative = self._is_context_negative_for_position(position, setup)

        if is_negative and profit_r >= cfg.MIN_PROTECT_PROFIT_R_MULTIPLIER:
            return OpenPositionVerdict(
                symbol=position.symbol, ticket=ticket,
                action="CLOSE_PROTECT",
                reason=(
                    f"contesto_tecnico_negativo: setup={setup.setup_type} "
                    f"profitto={profit_r:.2f}R >= {cfg.MIN_PROTECT_PROFIT_R_MULTIPLIER:.2f}R"
                ),
                profit_r_multiple=profit_r,
            )

        return OpenPositionVerdict(
            symbol=position.symbol, ticket=ticket,
            action="HOLD",
            reason=(
                f"setup={setup.setup_type} negative={is_negative} "
                f"profit_r={profit_r:.2f}"
            ),
            profit_r_multiple=profit_r,
        )

    def compute_existing_potential_loss_amount(
        self, account_state: AccountState,
    ) -> float:
        """Verbatim legacy 481-496."""
        total = 0.0
        for pos in account_state.open_positions:
            try:
                sym_info = self.mt5.get_symbol_info(pos.symbol)
            except Exception:
                sym_info = None
            risk = estimate_position_risk_amount(pos, sym_info)
            unrealized = pos.profit
            net = max(0.0, risk - max(0.0, unrealized))
            total += net
        return total

    def would_proposal_exceed_drawdown(
        self,
        proposal: TradeProposal,
        account_state: AccountState,
    ) -> tuple[bool, float]:
        """Verbatim legacy 498-520."""
        cfg = self.cfg
        starting = account_state.starting_balance_of_day or account_state.balance
        if starting <= 0:
            return False, 0.0
        existing_loss = self.compute_existing_potential_loss_amount(account_state)
        try:
            sym_info = self.mt5.get_symbol_info(proposal.symbol)
        except Exception:
            sym_info = None
        lots = estimate_proposal_lots(proposal, account_state, cfg, sym_info)
        proposal_loss = estimate_proposal_risk_amount(proposal, sym_info, lots)
        total_loss = existing_loss + proposal_loss
        percent = total_loss / starting * 100.0
        return percent > cfg.MAX_DAILY_DRAWDOWN_PERCENT, percent

    def is_addon_for(
        self,
        proposal: TradeProposal,
        account_state: AccountState,
    ) -> bool:
        """Verbatim legacy 522-530."""
        return any(
            p.symbol == proposal.symbol and p.direction == proposal.direction
            for p in account_state.open_positions
        )

    def build_delayed_followup(
        self,
        symbol: str,
        delay_minutes: int,
        reason: str,
        timeframe: str | None = None,
    ) -> DelayedFollowUpRequest:
        """Verbatim legacy 549-568."""
        cfg = self.cfg
        clamped = max(1, min(int(delay_minutes), cfg.MAX_DELAY_MINUTES))
        now = datetime.now()
        return DelayedFollowUpRequest(
            symbol=symbol,
            timeframe=timeframe or cfg.INTRADAY_TIMEFRAME,
            delay_minutes=clamped,
            reason=reason,
            focus_prompt=f"Re-analizzare {symbol}: {reason}",
            created_at=now,
            expires_at=now + timedelta(minutes=clamped + 5),
            already_delayed=False,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Internals (lift verbatim legacy)
    # ─────────────────────────────────────────────────────────────────────

    def _is_context_negative_for_position(
        self,
        position: PositionInfo,
        setup: TechnicalSetup,
    ) -> bool:
        """Verbatim legacy 532-547. Adattato: il nuovo TechnicalSetup non
        riempie sempre indicators con sma_20/sma_50/last_close (quei campi
        erano specifici del path legacy _analyze_technical). Manteniamo la
        logica direzionale READY-vs-position invariata; il branch
        sma-based ricade su False quando i campi non ci sono.
        """
        if setup.setup_type == "READY" and setup.direction is not None:
            return setup.direction != position.direction
        indicators = setup.indicators or {}
        sma20 = indicators.get("sma_20")
        sma50 = indicators.get("sma_50")
        last_close = indicators.get("last_close")
        if sma20 is None or sma50 is None or last_close is None:
            return False
        if position.direction == "BUY":
            return last_close < sma20 < sma50
        return last_close > sma20 > sma50

    def _apply_sentiment(
        self,
        setup: TechnicalSetup,
        sentiment: SentimentAnalysis | None,
    ) -> TechnicalSetup:
        """Verbatim legacy 642-723. TechnicalSetup non frozen → mutate ok."""
        cfg = self.cfg
        if (
            sentiment is None
            or not getattr(cfg, "ENABLE_NEWS_SENTIMENT", False)
            or sentiment.bias == "NEUTRAL"
            or sentiment.strength < cfg.SENTIMENT_MIN_STRENGTH_FILTER
        ):
            return setup

        if setup.setup_type != "READY" or setup.direction is None:
            return setup

        aligned = (
            (setup.direction == "BUY" and sentiment.bias == "BULLISH")
            or (setup.direction == "SELL" and sentiment.bias == "BEARISH")
        )

        if aligned:
            boosted = min(
                0.95,
                setup.confidence + cfg.SENTIMENT_BOOST_FACTOR * sentiment.strength,
            )
            setup.confidence = round(boosted, 4)
            setup.reason += (
                f" | Sentiment {sentiment.bias.lower()} conferma "
                f"({sentiment.relevant_news_count} news, str={sentiment.strength:.2f})"
            )
            setup.indicators["sentiment"] = {
                "bias": sentiment.bias, "strength": sentiment.strength,
                "news": sentiment.relevant_news_count, "applied": "boost",
            }
            return setup

        action = cfg.SENTIMENT_CONFLICT_ACTION
        setup.indicators["sentiment"] = {
            "bias": sentiment.bias, "strength": sentiment.strength,
            "news": sentiment.relevant_news_count, "applied": action,
        }
        if action == "skip":
            return TechnicalSetup(
                symbol=setup.symbol, timeframe=setup.timeframe,
                setup_type="NONE", direction=None,
                entry_price=None, stop_loss=None, take_profit=None,
                confidence=0.0,
                reason=(
                    f"Tecnico {setup.direction} ma sentiment {sentiment.bias} "
                    f"strong (str={sentiment.strength:.2f}), skip"
                ),
                indicators=setup.indicators, support_resistance=setup.support_resistance,
            )
        if action == "delay":
            return TechnicalSetup(
                symbol=setup.symbol, timeframe=setup.timeframe,
                setup_type="FORMING", direction=setup.direction,
                entry_price=None, stop_loss=None, take_profit=None,
                confidence=min(setup.confidence, 0.6),
                reason=(
                    f"Tecnico {setup.direction} vs sentiment {sentiment.bias} "
                    f"(str={sentiment.strength:.2f}), attendo conferma"
                ),
                indicators=setup.indicators, support_resistance=setup.support_resistance,
            )
        # reduce_confidence
        setup.confidence = round(setup.confidence * (1 - sentiment.strength * 0.3), 4)
        setup.reason += (
            f" | Sentiment {sentiment.bias.lower()} contrario, "
            f"confidence ridotta (str={sentiment.strength:.2f})"
        )
        if setup.confidence < cfg.MIN_CONFIDENCE_TO_PROPOSE:
            return TechnicalSetup(
                symbol=setup.symbol, timeframe=setup.timeframe,
                setup_type="NONE", direction=None,
                entry_price=None, stop_loss=None, take_profit=None,
                confidence=setup.confidence, reason=setup.reason,
                indicators=setup.indicators, support_resistance=setup.support_resistance,
            )
        return setup

    def _none_setup(
        self,
        symbol: str,
        timeframe: str,
        reason: str,
        indicators: dict | None = None,
    ) -> TechnicalSetup:
        """Verbatim legacy 725-737."""
        return TechnicalSetup(
            symbol=symbol, timeframe=timeframe, setup_type="NONE",
            direction=None, entry_price=None, stop_loss=None, take_profit=None,
            confidence=0.0, reason=reason,
            indicators=indicators or {}, support_resistance=None,
        )
