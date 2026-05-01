"""IntradayStrategy: motore Python puro per generare TradeProposal e follow-up.

Sostituisce ClaudeAgent nel loop critico. Deterministico, testabile, < 500ms per simbolo.
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
    DelayedFollowUpRequest,
    SentimentAnalysis,
    TechnicalSetup,
    TradeProposal,
)
from mt5_client import Mt5Client
from patterns import scan_patterns


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


class IntradayStrategy:
    def __init__(self, cfg: Config, mt5_client: Mt5Client, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger or logging.getLogger(__name__)

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
        patterns = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS) if cfg.ENABLE_CANDLESTICK_PATTERNS else []

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
            p["direction"] == "bullish" for p in patterns
        )
        has_pattern_bear = any(
            p["direction"] == "bearish" for p in patterns
        )
        pattern_ok_bull = (not cfg.ENABLE_CANDLESTICK_PATTERNS) or has_pattern_bull
        pattern_ok_bear = (not cfg.ENABLE_CANDLESTICK_PATTERNS) or has_pattern_bear

        resistance = sr.get("resistance")
        support = sr.get("support")
        tol = cfg.SR_TOLERANCE_PIPS * pip_size if pip_size > 0 else 0.0

        if (
            bullish_align
            and trend_strength > cfg.MIN_TREND_STRENGTH
            and rsi_in_band
            and breakout == "CLEAN"
            and pattern_ok_bull
            and resistance is not None
            and last_close > resistance
        ):
            return {
                "type": "READY", "direction": "BUY",
                "reason": (
                    f"trend_strength={trend_strength:.2f}, MAs allineate, "
                    f"breakout CLEAN sopra resistance={resistance:.5f}"
                ),
            }

        if (
            bearish_align
            and trend_strength > cfg.MIN_TREND_STRENGTH
            and rsi_in_band
            and breakout == "CLEAN"
            and pattern_ok_bear
            and support is not None
            and last_close < support
        ):
            return {
                "type": "READY", "direction": "SELL",
                "reason": (
                    f"trend_strength={trend_strength:.2f}, MAs allineate al ribasso, "
                    f"breakdown CLEAN sotto support={support:.5f}"
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
        has_aligned = any(p["direction"] == wanted for p in patterns)
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
