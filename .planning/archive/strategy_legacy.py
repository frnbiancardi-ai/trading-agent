"""IntradayStrategy: motore Python puro per generare TradeProposal e follow-up.

Sostituisce ClaudeAgent nel loop critico. Deterministico, testabile, < 500ms per simbolo.
Fase 16: aggiunge StrategyEnvironment (finestra intraday + news window hook),
evaluate_open_position (chiusura protettiva) e helper drawdown potenziale.
"""
import logging
from datetime import datetime, timedelta

from config import Config
from indicators import (
    sma,
    ema,
    rsi,
    atr,
    avg_volume,
    calculate_trend_strength,
    find_support_resistance,
    check_breakout_quality,
    calculate_risk_reward,
)
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
from patterns import scan_patterns, load_pattern_config


def _last_valid(series: list) -> float | None:
    for v in reversed(series):
        if v is not None:
            return v
    return None


def _pip_size(symbol_info) -> float:
    if symbol_info is None:
        return 0.0001
    point = getattr(symbol_info, "point", 0.0001) or 0.0001
    digits = getattr(symbol_info, "digits", 5)
    return point * 10 if digits in (3, 5) else point


class StrategyEnvironment:
    """Verifica i gate di contesto (finestra intraday, weekday, news window).

    Hook esposto dalla fase 16: l'integrazione reale di RSS/calendar per le
    blackout window news arriverà in una fase successiva. Per ora `is_news_window`
    ritorna False di default (no blackout) e può essere sostituito iniettando un
    `news_window_callable` esterno.
    """

    def __init__(
        self,
        cfg: Config,
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


def _pip_value_amount(symbol_info, pip_size: float) -> float:
    if symbol_info is None or pip_size <= 0:
        return 0.0
    tick_value = getattr(symbol_info, "trade_tick_value", 0.0) or 0.0
    tick_size = getattr(symbol_info, "trade_tick_size", 0.0) or 0.0
    if tick_size <= 0 or tick_value <= 0:
        return 0.0
    return tick_value * pip_size / tick_size


def estimate_position_risk_amount(
    position: PositionInfo, symbol_info,
) -> float:
    """Stima la perdita potenziale (account currency) se il SL fosse colpito."""
    if position is None or position.stop_loss in (0.0, None):
        return 0.0
    pip_size = _pip_size(symbol_info)
    pip_value = _pip_value_amount(symbol_info, pip_size)
    if pip_value <= 0 or pip_size <= 0:
        return 0.0
    distance_pips = abs(position.entry_price - position.stop_loss) / pip_size
    return position.lots * pip_value * distance_pips


def estimate_proposal_risk_amount(
    proposal: TradeProposal, symbol_info, lots: float,
) -> float:
    if symbol_info is None or lots <= 0:
        return 0.0
    pip_size = _pip_size(symbol_info)
    pip_value = _pip_value_amount(symbol_info, pip_size)
    if pip_value <= 0 or pip_size <= 0:
        return 0.0
    distance_pips = abs(proposal.entry_price - proposal.stop_loss_price) / pip_size
    return lots * pip_value * distance_pips


def estimate_proposal_lots(
    proposal: TradeProposal, account_state: AccountState, cfg: Config, symbol_info,
) -> float:
    """Stima della size in lotti coerente col risk_engine, senza chiamare MT5
    per il margin check. Usato solo per il drawdown potenziale.
    """
    pip_size = _pip_size(symbol_info)
    pip_value = _pip_value_amount(symbol_info, pip_size)
    if pip_value <= 0 or pip_size <= 0:
        return 0.0
    distance_pips = abs(proposal.entry_price - proposal.stop_loss_price) / pip_size
    if distance_pips <= 0:
        return 0.0
    if cfg.RISK_AMOUNT_MODE == "FIXED_AMOUNT":
        risk_amount = cfg.RISK_PER_TRADE_AMOUNT
    else:
        risk_amount = account_state.balance * cfg.RISK_PER_TRADE_PERCENT / 100.0
    if risk_amount <= 0:
        return 0.0
    return risk_amount / (pip_value * distance_pips)


class IntradayStrategy:
    def __init__(
        self,
        cfg: Config,
        mt5_client: BrokerProtocol,
        logger: logging.Logger | None = None,
        environment: StrategyEnvironment | None = None,
    ):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger or logging.getLogger(__name__)
        self.env = environment or StrategyEnvironment(cfg, self.log)
        self._pattern_cfg = load_pattern_config()  # Phase 3: carica catalog cfg una volta a startup

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def analyze_symbol(
        self,
        symbol: str,
        account_state: AccountState,
        sentiment: SentimentAnalysis | None = None,
    ) -> TechnicalSetup:
        setup = self._analyze_technical(symbol, account_state)
        return self._apply_sentiment(setup, sentiment)

    def _analyze_technical(self, symbol: str, account_state: AccountState) -> TechnicalSetup:
        cfg = self.cfg
        timeframe = cfg.INTRADAY_TIMEFRAME

        try:
            bars = self.mt5.get_ohlc(symbol, timeframe, cfg.INTRADAY_LOOKBACK_BARS)
        except Exception as exc:
            self.log.warning("get_ohlc failed for %s: %s", symbol, exc)
            return self._none_setup(symbol, timeframe, f"ohlc_error: {exc}")

        if not bars or len(bars) < 50:
            return self._none_setup(symbol, timeframe, "insufficient_bars")

        try:
            sym_info = self.mt5.get_symbol_info(symbol)
        except Exception as exc:
            self.log.warning("get_symbol_info failed for %s: %s", symbol, exc)
            sym_info = None

        pip_size = _pip_size(sym_info)

        closes = [b["close"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]

        sma20_series = sma(closes, 20)
        sma50_series = sma(closes, 50)
        rsi_series = rsi(closes, 14)
        atr_series = atr(highs, lows, closes, 14)

        sma20 = _last_valid(sma20_series)
        sma50 = _last_valid(sma50_series)
        rsi_val = _last_valid(rsi_series)
        atr_val = _last_valid(atr_series)

        if None in (sma20, sma50, rsi_val, atr_val):
            return self._none_setup(symbol, timeframe, "indicators_not_ready")

        atr_pips = atr_val / pip_size if pip_size > 0 else 0.0
        if atr_pips < cfg.MIN_ATR_PIPS or atr_pips > cfg.MAX_ATR_PIPS:
            return self._none_setup(
                symbol, timeframe,
                f"atr_out_of_range: {atr_pips:.1f} pip",
                indicators={"atr_pips": atr_pips, "rsi_14": rsi_val, "sma_20": sma20, "sma_50": sma50},
            )

        trend_strength = calculate_trend_strength(bars, sma20, sma50)
        sr = find_support_resistance(bars, lookback=cfg.SR_LOOKBACK_BARS)
        breakout = check_breakout_quality(
            bars, sr,
            volume_threshold=cfg.MIN_BREAKOUT_VOLUME_RATIO,
        )
        patterns = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS, cfg=self._pattern_cfg) if cfg.ENABLE_CANDLESTICK_PATTERNS else []

        last_close = closes[-1]

        indicators_snapshot = {
            "sma_20": sma20,
            "sma_50": sma50,
            "rsi_14": rsi_val,
            "atr_14": atr_val,
            "atr_pips": atr_pips,
            "trend_strength": trend_strength,
            "breakout": breakout,
            "patterns": patterns,
            "last_close": last_close,
            "pip_size": pip_size,
        }

        decision = self.identify_entry_setup(bars, indicators_snapshot, sr, patterns)

        setup_type = decision["type"]
        direction = decision.get("direction")
        reason = decision.get("reason", "")

        if setup_type == "READY":
            entry, sl, tp = self._compute_levels(
                direction=direction, last_close=last_close, atr_val=atr_val,
                sr=sr, pip_size=pip_size,
            )
            rr = calculate_risk_reward(entry, sl, tp)
            indicators_snapshot["risk_reward"] = rr
            if rr < cfg.MIN_RISK_REWARD_RATIO:
                return TechnicalSetup(
                    symbol=symbol, timeframe=timeframe, setup_type="NONE",
                    direction=None, entry_price=None, stop_loss=None, take_profit=None,
                    confidence=0.0,
                    reason=f"rr_below_min: {rr:.2f} < {cfg.MIN_RISK_REWARD_RATIO}",
                    indicators=indicators_snapshot, support_resistance=sr,
                )
            confidence = self._score_confidence(
                trend_strength=trend_strength, patterns=patterns,
                breakout=breakout, rr=rr, direction=direction,
            )
            return TechnicalSetup(
                symbol=symbol, timeframe=timeframe, setup_type="READY",
                direction=direction, entry_price=entry, stop_loss=sl, take_profit=tp,
                confidence=confidence, reason=reason,
                indicators=indicators_snapshot, support_resistance=sr,
            )

        if setup_type == "FORMING":
            return TechnicalSetup(
                symbol=symbol, timeframe=timeframe, setup_type="FORMING",
                direction=direction, entry_price=None, stop_loss=None, take_profit=None,
                confidence=min(trend_strength, 0.6), reason=reason,
                indicators=indicators_snapshot, support_resistance=sr,
            )

        return TechnicalSetup(
            symbol=symbol, timeframe=timeframe, setup_type="NONE",
            direction=None, entry_price=None, stop_loss=None, take_profit=None,
            confidence=0.0, reason=reason or "no_setup",
            indicators=indicators_snapshot, support_resistance=sr,
        )

    def identify_entry_setup(
        self,
        bars: list[dict],
        indicators: dict,
        sr: dict,
        patterns: list[dict],
    ) -> dict:
        cfg = self.cfg
        sma20 = indicators["sma_20"]
        sma50 = indicators["sma_50"]
        rsi_val = indicators["rsi_14"]
        trend_strength = indicators["trend_strength"]
        breakout = indicators["breakout"]
        last_close = indicators["last_close"]
        pip_size = indicators["pip_size"]

        bullish_align = last_close > sma20 > sma50
        bearish_align = last_close < sma20 < sma50

        rsi_in_band = cfg.MIN_RSI_OVERSOLD < rsi_val < cfg.MAX_RSI_OVERBOUGHT

        has_pattern_bull = any(
            p.direction == "bullish" for p in patterns
        )
        has_pattern_bear = any(
            p.direction == "bearish" for p in patterns
        )
        pattern_ok_bull = (not cfg.ENABLE_CANDLESTICK_PATTERNS) or has_pattern_bull
        pattern_ok_bear = (not cfg.ENABLE_CANDLESTICK_PATTERNS) or has_pattern_bear

        resistance = sr.get("resistance")
        support = sr.get("support")
        tol = cfg.SR_TOLERANCE_PIPS * pip_size if pip_size > 0 else 0.0

        breakout_ok = (breakout == "CLEAN") or (not cfg.REQUIRE_BREAKOUT_FOR_READY)

        if (
            bullish_align
            and trend_strength > cfg.MIN_TREND_STRENGTH
            and rsi_in_band
            and breakout_ok
            and pattern_ok_bull
            and (resistance is None or last_close > resistance - tol)
        ):
            ref = f"resistance={resistance:.5f}" if resistance is not None else "no_resistance"
            mode = "breakout" if breakout == "CLEAN" else "trend_continuation"
            return {
                "type": "READY", "direction": "BUY",
                "reason": (
                    f"trend_strength={trend_strength:.2f}, MAs allineate, "
                    f"{mode} vicino/sopra {ref} (tol={cfg.SR_TOLERANCE_PIPS}p)"
                ),
            }

        if (
            bearish_align
            and trend_strength > cfg.MIN_TREND_STRENGTH
            and rsi_in_band
            and breakout_ok
            and pattern_ok_bear
            and (support is None or last_close < support + tol)
        ):
            ref = f"support={support:.5f}" if support is not None else "no_support"
            mode = "breakdown" if breakout == "CLEAN" else "trend_continuation"
            return {
                "type": "READY", "direction": "SELL",
                "reason": (
                    f"trend_strength={trend_strength:.2f}, MAs allineate al ribasso, "
                    f"{mode} vicino/sotto {ref} (tol={cfg.SR_TOLERANCE_PIPS}p)"
                ),
            }

        if (
            trend_strength > 0.6
            and resistance is not None
            and 0 < (resistance - last_close) <= tol
            and bullish_align
        ):
            return {
                "type": "FORMING", "direction": "BUY",
                "reason": "prezzo vicino a resistance, attendo conferma breakout",
            }
        if (
            trend_strength > 0.6
            and support is not None
            and 0 < (last_close - support) <= tol
            and bearish_align
        ):
            return {
                "type": "FORMING", "direction": "SELL",
                "reason": "prezzo vicino a support, attendo conferma breakdown",
            }

        if rsi_val >= cfg.MAX_RSI_OVERBOUGHT:
            return {"type": "NONE", "direction": None, "reason": f"rsi_overbought={rsi_val:.1f}"}
        if rsi_val <= cfg.MIN_RSI_OVERSOLD:
            return {"type": "NONE", "direction": None, "reason": f"rsi_oversold={rsi_val:.1f}"}
        return {"type": "NONE", "direction": None, "reason": "trend_or_alignment_weak"}

    def build_trade_proposal(
        self,
        symbol: str,
        setup: TechnicalSetup,
        bars: list[dict] | None = None,
        indicators: dict | None = None,
        account_state: AccountState | None = None,
    ) -> TradeProposal:
        if setup.setup_type != "READY" or setup.direction is None:
            raise ValueError(f"build_trade_proposal richiede setup READY, ricevuto {setup.setup_type}")
        if setup.entry_price is None or setup.stop_loss is None or setup.take_profit is None:
            raise ValueError("setup READY senza entry/sl/tp")

        rationale = (
            f"{setup.direction} {symbol} su {setup.timeframe}: {setup.reason}. "
            f"Confidence {setup.confidence:.2f}, "
            f"R:R {setup.indicators.get('risk_reward', 0):.2f}."
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
        """Decide se chiudere/mantenere una posizione esistente nel ciclo H24.

        - CLOSE_END_OF_DAY: fuori finestra intraday + giorno feriale (no overnight)
          se CLOSE_BEFORE_END_OF_WINDOW=true.
        - CLOSE_PROTECT: contesto tecnico negativo + profit ≥ MIN_PROTECT_PROFIT_R_MULTIPLIER * R.
        - HOLD: altrimenti.
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
        total = 0.0
        for pos in account_state.open_positions:
            try:
                sym_info = self.mt5.get_symbol_info(pos.symbol)
            except Exception:
                sym_info = None
            risk = estimate_position_risk_amount(pos, sym_info)
            unrealized = pos.profit
            # Worst-case loss = SL distance, ridotta dell'eventuale profitto già maturato
            # (un trade in profitto a SL invariato non perde l'intero R, ma R - profit).
            net = max(0.0, risk - max(0.0, unrealized))
            total += net
        return total

    def would_proposal_exceed_drawdown(
        self,
        proposal: TradeProposal,
        account_state: AccountState,
    ) -> tuple[bool, float]:
        """Ritorna (violation, percent) usando MAX_DAILY_DRAWDOWN_PERCENT come soglia.

        percent = (perdita_potenziale_existing + perdita_potenziale_proposal) / starting_balance_of_day * 100.
        """
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
        return any(
            p.symbol == proposal.symbol and p.direction == proposal.direction
            for p in account_state.open_positions
        )

    def _is_context_negative_for_position(
        self,
        position: PositionInfo,
        setup: TechnicalSetup,
    ) -> bool:
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

    def build_delayed_followup(
        self,
        symbol: str,
        delay_minutes: int,
        reason: str,
        timeframe: str | None = None,
    ) -> DelayedFollowUpRequest:
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
    # Internals
    # ─────────────────────────────────────────────────────────────────────

    def _compute_levels(
        self,
        direction: str,
        last_close: float,
        atr_val: float,
        sr: dict,
        pip_size: float,
    ) -> tuple[float, float, float]:
        cfg = self.cfg
        entry = last_close
        atr_buffer = atr_val
        rr = max(cfg.MIN_RISK_REWARD_RATIO, 1.5)

        if direction == "BUY":
            support = sr.get("support")
            if support is not None and support < entry:
                sl = min(support - 0.5 * atr_val, entry - atr_buffer)
            else:
                sl = entry - atr_buffer
            risk = entry - sl
            tp = entry + rr * risk
        else:
            resistance = sr.get("resistance")
            if resistance is not None and resistance > entry:
                sl = max(resistance + 0.5 * atr_val, entry + atr_buffer)
            else:
                sl = entry + atr_buffer
            risk = sl - entry
            tp = entry - rr * risk

        digits = 5 if pip_size <= 0.001 else 3
        return round(entry, digits), round(sl, digits), round(tp, digits)

    def _score_confidence(
        self,
        trend_strength: float,
        patterns: list[dict],
        breakout: str,
        rr: float,
        direction: str,
    ) -> float:
        cfg = self.cfg
        # Trend 0..0.3
        trend_score = min(trend_strength, 1.0) * 0.3

        # Pattern 0..0.2
        wanted = "bullish" if direction == "BUY" else "bearish"
        has_aligned = any(p.direction == wanted for p in patterns)
        pattern_score = 0.2 if has_aligned else (0.05 if patterns else 0.0)

        # Volume / breakout 0..0.2
        if breakout == "CLEAN":
            vol_score = 0.2
        elif breakout == "WEAK":
            vol_score = 0.1
        else:
            vol_score = 0.0

        # R:R 0..0.2
        target = max(cfg.MIN_RISK_REWARD_RATIO, 1.5)
        rr_score = min(rr / (target * 2), 1.0) * 0.2

        # Multi-timeframe alignment placeholder 0.1
        mtf_score = 0.1

        total = trend_score + pattern_score + vol_score + rr_score + mtf_score
        return round(min(max(total, 0.0), 1.0), 4)

    def _apply_sentiment(
        self,
        setup: TechnicalSetup,
        sentiment: SentimentAnalysis | None,
    ) -> TechnicalSetup:
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
        return TechnicalSetup(
            symbol=symbol, timeframe=timeframe, setup_type="NONE",
            direction=None, entry_price=None, stop_loss=None, take_profit=None,
            confidence=0.0, reason=reason,
            indicators=indicators or {}, support_resistance=None,
        )
