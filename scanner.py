"""MultiSymbolScanner: orchestra light_scan + deep analysis su universo simboli.

Ranking veloce su tutti i simboli, poi deep analysis su top N candidati,
seleziona il setup READY con confidence massima oppure NO_TRADE / WAIT_FOLLOW_UP.
"""
import logging
from datetime import datetime

from config import Config
from indicators import (
    sma,
    ema,
    rsi,
    atr,
)
from models import (
    AccountState,
    DelayedFollowUpRequest,
    ScanResult,
    StrategyOutcome,
    TechnicalSetup,
)
from mt5_client import Mt5Client
from strategy import IntradayStrategy, _last_valid, _pip_size


_LIGHT_BARS = 50


class MultiSymbolScanner:
    def __init__(
        self,
        cfg: Config,
        mt5_client: Mt5Client,
        strategy: IntradayStrategy,
        logger: logging.Logger | None = None,
    ):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.strategy = strategy
        self.log = logger or logging.getLogger(__name__)

    # ─────────────────────────────────────────────────────────────────────

    def light_scan(self, symbol: str) -> ScanResult | None:
        cfg = self.cfg
        warnings: list[str] = []

        try:
            bars = self.mt5.get_ohlc(symbol, cfg.INTRADAY_TIMEFRAME, _LIGHT_BARS)
        except Exception as exc:
            self.log.warning("light_scan ohlc failed for %s: %s", symbol, exc)
            return None

        if not bars or len(bars) < 30:
            return None

        try:
            sym_info = self.mt5.get_symbol_info(symbol)
        except Exception:
            sym_info = None

        pip_size = _pip_size(sym_info)
        spread_state = "ACCEPTABLE"
        if sym_info is not None:
            bid = getattr(sym_info, "bid", 0.0) or 0.0
            ask = getattr(sym_info, "ask", 0.0) or 0.0
            spread_pips = (ask - bid) / pip_size if pip_size > 0 else 0.0
            if spread_pips > 5.0:
                spread_state = "WIDE"
                warnings.append(f"spread_wide={spread_pips:.1f}pip")

        closes = [b["close"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]

        sma20 = _last_valid(sma(closes, 20))
        ema50 = _last_valid(ema(closes, 50))
        rsi_val = _last_valid(rsi(closes, 14))
        atr_val = _last_valid(atr(highs, lows, closes, 14))

        if None in (sma20, rsi_val, atr_val):
            warnings.append("indicators_not_ready")
            return ScanResult(
                symbol=symbol, trend_bias="NEUTRAL", momentum_bias="NEUTRAL",
                volatility_state="LOW", spread_state=spread_state, regime="RANGE",
                candidate_score=0.0, warnings=warnings,
            )

        last_close = closes[-1]
        if ema50 is not None and last_close > sma20 > ema50:
            trend_bias = "BULLISH"
        elif ema50 is not None and last_close < sma20 < ema50:
            trend_bias = "BEARISH"
        else:
            trend_bias = "NEUTRAL"

        if rsi_val > 55:
            momentum_bias = "BULLISH"
        elif rsi_val < 45:
            momentum_bias = "BEARISH"
        else:
            momentum_bias = "NEUTRAL"

        atr_pips = atr_val / pip_size if pip_size > 0 else 0.0
        if atr_pips < cfg.MIN_ATR_PIPS:
            volatility_state = "LOW"
        elif atr_pips > cfg.MAX_ATR_PIPS:
            volatility_state = "HIGH"
        else:
            volatility_state = "NORMAL"

        if trend_bias != "NEUTRAL" and volatility_state == "NORMAL":
            regime = "TREND"
        elif volatility_state == "HIGH":
            regime = "BREAKOUT"
        else:
            regime = "RANGE"

        score = self.calculate_scan_score(
            bars, {"sma_20": sma20, "ema_50": ema50, "rsi_14": rsi_val, "atr_pips": atr_pips},
        )

        if spread_state == "WIDE":
            score *= 0.5

        return ScanResult(
            symbol=symbol, trend_bias=trend_bias, momentum_bias=momentum_bias,
            volatility_state=volatility_state, spread_state=spread_state,
            regime=regime, candidate_score=round(score, 4), warnings=warnings,
        )

    def scan_universe(self, symbols: list[str]) -> list[ScanResult]:
        results: list[ScanResult] = []
        for sym in symbols:
            r = self.light_scan(sym)
            if r is None:
                continue
            results.append(r)
        results.sort(key=lambda r: r.candidate_score, reverse=True)
        return results[: self.cfg.INTRADAY_SCAN_TOP_N]

    def deep_analyze_top_candidates(
        self,
        scan_results: list[ScanResult],
        account_state: AccountState,
    ) -> StrategyOutcome:
        cfg = self.cfg
        now = datetime.now()
        if not scan_results:
            return StrategyOutcome(
                outcome_type="NO_TRADE", proposal=None, follow_up=None,
                scan_results=[], timestamp=now, note="empty_universe",
            )

        ready_setups: list[TechnicalSetup] = []
        forming_setups: list[TechnicalSetup] = []

        for r in scan_results:
            setup = self.strategy.analyze_symbol(r.symbol, account_state)
            if setup.setup_type == "READY":
                ready_setups.append(setup)
            elif setup.setup_type == "FORMING":
                forming_setups.append(setup)

        if ready_setups:
            ready_setups.sort(key=lambda s: s.confidence, reverse=True)
            best = ready_setups[0]
            if best.confidence < cfg.MIN_CONFIDENCE_TO_PROPOSE:
                return StrategyOutcome(
                    outcome_type="NO_TRADE", proposal=None, follow_up=None,
                    scan_results=scan_results, timestamp=now,
                    note=f"best_confidence_below_threshold={best.confidence:.2f}",
                )
            proposal = self.strategy.build_trade_proposal(best.symbol, best, account_state=account_state)
            return StrategyOutcome(
                outcome_type="TRADE", proposal=proposal, follow_up=None,
                scan_results=scan_results, timestamp=now,
                note=f"selected={best.symbol} conf={best.confidence:.2f}",
            )

        if forming_setups and cfg.FOLLOWUP_ENABLED:
            forming_setups.sort(key=lambda s: s.confidence, reverse=True)
            best_forming = forming_setups[0]
            follow_up: DelayedFollowUpRequest = self.strategy.build_delayed_followup(
                symbol=best_forming.symbol,
                delay_minutes=30,
                reason=best_forming.reason,
                timeframe=best_forming.timeframe,
            )
            return StrategyOutcome(
                outcome_type="WAIT_FOLLOW_UP", proposal=None, follow_up=follow_up,
                scan_results=scan_results, timestamp=now,
                note=f"forming={best_forming.symbol}",
            )

        return StrategyOutcome(
            outcome_type="NO_TRADE", proposal=None, follow_up=None,
            scan_results=scan_results, timestamp=now, note="no_ready_or_forming",
        )

    def calculate_scan_score(self, bars: list[dict], indicators: dict) -> float:
        cfg = self.cfg
        sma20 = indicators.get("sma_20")
        ema50 = indicators.get("ema_50")
        rsi_val = indicators.get("rsi_14")
        atr_pips = indicators.get("atr_pips", 0.0)

        if not bars or sma20 is None or rsi_val is None:
            return 0.0

        # Trend clarity 0..0.4
        if ema50 is not None and ema50 != 0:
            sep = abs(sma20 - ema50) / abs(ema50)
            trend_score = min(sep / 0.005, 1.0) * 0.4
        else:
            trend_score = 0.0

        # RSI in band 0..0.3
        if cfg.MIN_RSI_OVERSOLD < rsi_val < cfg.MAX_RSI_OVERBOUGHT:
            mid = (cfg.MIN_RSI_OVERSOLD + cfg.MAX_RSI_OVERBOUGHT) / 2
            half = (cfg.MAX_RSI_OVERBOUGHT - cfg.MIN_RSI_OVERSOLD) / 2
            distance_from_extreme = 1.0 - abs(rsi_val - mid) / half
            rsi_score = max(0.0, distance_from_extreme) * 0.3
        else:
            rsi_score = 0.0

        # ATR in range 0..0.3
        if cfg.MIN_ATR_PIPS <= atr_pips <= cfg.MAX_ATR_PIPS:
            atr_score = 0.3
        else:
            atr_score = 0.0

        return round(trend_score + rsi_score + atr_score, 4)
