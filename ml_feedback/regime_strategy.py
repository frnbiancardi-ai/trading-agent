"""Regime-Based Strategy: strategia che si adatta al regime di mercato.

TREND -> pullback
RANGE -> mean reversion
VOLATILE -> no trade (wait for better conditions)
"""
from dataclasses import dataclass
from typing import Optional
import logging

from ml_feedback.regime_detector import RegimeDetector, MarketRegime, RegimeDetection


@dataclass
class StrategyConfig:
    trend_min_rsi: float = 30.0
    trend_max_rsi: float = 70.0
    trend_min_trend_strength: float = 0.6
    
    rsi_buy_extreme: float = 25.0
    rsi_sell_extreme: float = 75.0
    
    min_sl_pips: int = 15
    min_rr: float = 1.5
    
    enable_volatile_skip: bool = True


class RegimeStrategy:
    def __init__(
        self,
        config: Optional[StrategyConfig] = None,
        log: Optional[logging.Logger] = None,
    ):
        self.config = config or StrategyConfig()
        self.log = log or logging.getLogger(__name__)
        self.regime_detector = RegimeDetector()
    
    def analyze(
        self,
        bars: list[dict],
        rsi_values: list,
        sma_values: dict,
    ) -> dict:
        """Analizza e ritorna setup di trading basato su regime."""
        regime_detection = self.regime_detector.detect(bars)
        regime = regime_detection.regime
        cfg = self.config
        
        if regime == MarketRegime.UNKNOWN:
            return {
                "type": "NONE",
                "reason": "unknown_regime",
            }
        
        if regime == MarketRegime.VOLATILE:
            if cfg.enable_volatile_skip:
                return {
                    "type": "NONE",
                    "reason": "volatile_market",
                    "regime": "VOLATILE",
                }
        
        if regime == MarketRegime.RANGE:
            return self._range_strategy(bars, rsi_values, cfg)
        
        if regime == MarketRegime.TREND:
            return self._trend_strategy(bars, rsi_values, sma_values, cfg)
        
        return {
            "type": "NONE",
            "reason": "no_setup",
        }
    
    def _trend_strategy(
        self,
        bars: list[dict],
        rsi_values: list,
        sma_values: dict,
        cfg: StrategyConfig,
    ) -> dict:
        """Trend continuation - pullback su trend."""
        if not rsi_values or not sma_values:
            return {"type": "NONE", "reason": "no_indicators"}
        
        close = bars[-1]["close"]
        rsi = rsi_values[-1]
        sma_50 = sma_values.get("sma50", [0])[-1]
        sma_20 = sma_values.get("sma20", [0])[-1]
        
        rsi_ok = cfg.trend_min_rsi < rsi < cfg.trend_max_rsi
        if not rsi_ok:
            return {"type": "NONE", "reason": "rsi_out_of_range"}
        
        bullish = close > sma_20 > sma_50
        bearish = close < sma_20 < sma_50
        
        if not (bullish or bearish):
            return {"type": "NONE", "reason": "no_trend_alignment"}
        
        direction = "BUY" if bullish else "SELL"
        pip = 0.0001
        
        return {
            "type": "READY",
            "direction": direction,
            "entry": close,
            "sl": close - cfg.min_sl_pips * pip if direction == "BUY" else close + cfg.min_sl_pips * pip,
            "tp": close + cfg.min_sl_pips * cfg.min_rr * pip if direction == "BUY" else close - cfg.min_sl_pips * cfg.min_rr * pip,
            "regime": "TREND",
            "setup": "trend_pullback",
        }
    
    def _range_strategy(
        self,
        bars: list[dict],
        rsi_values: list,
        cfg: StrategyConfig,
    ) -> dict:
        """Mean reversion - RSI estremi."""
        if not rsi_values:
            return {"type": "NONE", "reason": "no_rsi"}
        
        close = bars[-1]["close"]
        rsi = rsi_values[-1]
        pip = 0.0001
        
        if rsi <= cfg.rsi_buy_extreme:
            return {
                "type": "READY",
                "direction": "BUY",
                "entry": close,
                "sl": close - cfg.min_sl_pips * pip,
                "tp": close + cfg.min_sl_pips * cfg.min_rr * pip,
                "regime": "RANGE",
                "setup": "mean_reversion_oversold",
            }
        
        if rsi >= cfg.rsi_sell_extreme:
            return {
                "type": "READY",
                "direction": "SELL",
                "entry": close,
                "sl": close + cfg.min_sl_pips * pip,
                "tp": close - cfg.min_sl_pips * cfg.min_rr * pip,
                "regime": "RANGE",
                "setup": "mean_reversion_overbought",
            }
        
        return {
            "type": "NONE",
            "reason": "rsi_not_extreme",
            "regime": "RANGE",
        }


def create_regime_strategy(config: dict = None) -> RegimeStrategy:
    """Factory function."""
    cfg = StrategyConfig(
        trend_min_rsi=config.get("trend_min_rsi", 30.0) if config else 30.0,
        trend_max_rsi=config.get("trend_max_rsi", 70.0) if config else 70.0,
        rsi_buy_extreme=config.get("rsi_buy_extreme", 25.0) if config else 25.0,
        rsi_sell_extreme=config.get("rsi_sell_extreme", 75.0) if config else 75.0,
    )
    return RegimeStrategy(config=cfg)


__all__ = ["RegimeStrategy", "StrategyConfig", "create_regime_strategy"]