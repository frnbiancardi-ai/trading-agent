"""Regime Detector: identifica market regime (trend/range/volatile).

Basato su Murphy - Trading Intermarket Analysis.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class MarketRegime(Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeDetection:
    regime: MarketRegime
    confidence: float
    indicators: dict
    timestamp: str


class RegimeDetector:
    def __init__(
        self,
        adx_period: int = 14,
        adx_trend_threshold: float = 25.0,
        sma_long_period: int = 200,
        atr_period: int = 14,
        volatility_threshold: float = 2.0,
        log: Optional[logging.Logger] = None,
    ):
        self.adx_period = adx_period
        self.adx_trend_threshold = adx_trend_threshold
        self.sma_long_period = sma_long_period
        self.atr_period = atr_period
        self.volatility_threshold = volatility_threshold
        self.log = log or logging.getLogger(__name__)
    
    def _calculate_adx(self, highs: list, lows: list, closes: list) -> tuple[float, float, float]:
        """Calcola ADX, +DI, -DI."""
        period = self.adx_period
        if len(closes) < period + 1:
            return 0.0, 0.0, 0.0
        
        plus_dm = []
        minus_dm = []
        tr = []
        
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i - 1]
            low_diff = lows[i - 1] - lows[i]
            
            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)
            
            tr.append(
                max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
            )
        
        if len(tr) < period:
            return 0.0, 0.0, 0.0
        
        tr = np.array(tr[-period:])
        plus_dm = np.array(plus_dm[-period:])
        minus_dm = np.array(minus_dm[-period:])
        
        atr = np.mean(tr)
        if atr == 0:
            return 0.0, 0.0, 0.0
        
        plus_di = 100 * np.mean(plus_dm) / atr
        minus_di = 100 * np.mean(minus_dm) / atr
        
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 0.0, plus_di, minus_di
        
        dx = 100 * abs(plus_di - minus_di) / di_sum
        adx = dx
        
        return adx, plus_di, minus_di
    
    def _calculate_atr_ratio(self, highs: list, lows: list, closes: list) -> float:
        """Calcola ATR come ratio del prezzo."""
        period = self.atr_period
        if len(closes) < period + 1:
            return 0.0
        
        atr_values = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            atr_values.append(tr)
        
        if len(atr_values) < period:
            return 0.0
        
        atr = np.mean(atr_values[-period:])
        price = closes[-1]
        
        if price == 0:
            return 0.0
        
        return atr / price * 100
    
    def detect(
        self,
        bars: list[dict],
    ) -> RegimeDetection:
        """Identifica il regime di mercato."""
        if len(bars) < 50:
            return RegimeDetection(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                indicators={},
                timestamp="",
            )
        
        closes = [b["close"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        
        close = closes[-1]
        
        adx, plus_di, minus_di = self._calculate_adx(highs, lows, closes)
        atr_ratio = self._calculate_atr_ratio(highs, lows, closes)
        
        sma_long = self._sma(closes, self.sma_long_period)
        sma_value = sma_long[-1] if sma_long else None
        
        above_sma = close > sma_value if sma_value else False
        below_sma = close < sma_value if sma_value else False
        
        indicators = {
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di,
            "atr_ratio": atr_ratio,
            "close": close,
            "sma200": sma_value,
            "above_sma": above_sma,
            "below_sma": below_sma,
        }
        
        regime = MarketRegime.UNKNOWN
        confidence = 0.0
        
        if adx >= self.adx_trend_threshold:
            if plus_di > minus_di and above_sma:
                regime = MarketRegime.TREND
                confidence = min(adx / 50, 1.0)
            elif minus_di > plus_di and below_sma:
                regime = MarketRegime.TREND
                confidence = min(adx / 50, 1.0)
        
        elif atr_ratio >= self.volatility_threshold:
            regime = MarketRegime.VOLATILE
            confidence = min(atr_ratio / (self.volatility_threshold * 2), 1.0)
        
        else:
            regime = MarketRegime.RANGE
            confidence = 0.7
        
        return RegimeDetection(
            regime=regime,
            confidence=confidence,
            indicators=indicators,
            timestamp=bars[-1].get("time", ""),
        )
    
    def _sma(self, values: list, period: int) -> list:
        """Simple moving average."""
        if len(values) < period:
            return []
        return [sum(values[i - period:i]) / period for i in range(period, len(values) + 1)]


def detect_regime(bars: list[dict], config: dict = None) -> RegimeDetection:
    """Convenience function per quick detection."""
    config = config or {}
    detector = RegimeDetector(
        adx_period=config.get("adx_period", 14),
        adx_trend_threshold=config.get("adx_trend_threshold", 25.0),
        sma_long_period=config.get("sma_long_period", 200),
        atr_period=config.get("atr_period", 14),
        volatility_threshold=config.get("volatility_threshold", 2.0),
    )
    return detector.detect(bars)


__all__ = ["RegimeDetector", "RegimeDetection", "MarketRegime", "detect_regime"]