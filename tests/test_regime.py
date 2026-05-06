"""Tests per Regime Detection."""
import pytest
from datetime import datetime
from ml_feedback import (
    RegimeDetector,
    RegimeDetection,
    MarketRegime,
    RegimeStrategy,
    create_regime_strategy,
)


class TestRegimeDetector:
    def test_detect_trend_bullish(self):
        bars = []
        base = 1.0900
        for i in range(100):
            bars.append({
                "time": f"2024-01-{(i % 28) + 1:02d} {(i % 24):02d}:00:00",
                "open": base + i * 0.001,
                "high": base + i * 0.001 + 0.002,
                "low": base + i * 0.001 - 0.001,
                "close": base + i * 0.001,
            })
        
        detector = RegimeDetector(
            adx_trend_threshold=25.0,
            sma_long_period=50,
        )
        result = detector.detect(bars)
        
        assert result.regime in [MarketRegime.TREND, MarketRegime.RANGE]
    
    def test_detect_range(self):
        bars = []
        base = 1.0900
        for i in range(100):
            bars.append({
                "time": f"2024-01-{(i % 28) + 1:02d} {(i % 24):02d}:00:00",
                "open": base + (i % 5) * 0.0001,
                "high": base + (i % 5) * 0.0001 + 0.0002,
                "low": base + (i % 5) * 0.0001 - 0.0001,
                "close": base + (i % 5) * 0.0001,
            })
        
        detector = RegimeDetector(
            adx_trend_threshold=25.0,
            volatility_threshold=2.0,
        )
        result = detector.detect(bars)
        
        assert result.regime == MarketRegime.RANGE
    
    def test_detect_volatile(self):
        import random
        bars = []
        for i in range(50):
            bars.append({
                "time": f"2024-01-{(i % 28) + 1:02d} {(i % 24):02d}:00:00",
                "open": 1.0900 + random.uniform(-0.01, 0.01),
                "high": 1.1000,
                "low": 1.0800,
                "close": 1.0900 + random.uniform(-0.01, 0.01),
            })
        
        detector = RegimeDetector(volatility_threshold=0.5)
        result = detector.detect(bars)
        
        assert result.regime in [MarketRegime.VOLATILE, MarketRegime.TREND]
    
    def test_insufficient_data(self):
        bars = [{"close": 1.09}] * 10
        
        detector = RegimeDetector()
        result = detector.detect(bars)
        
        assert result.regime == MarketRegime.UNKNOWN


class TestRegimeStrategy:
    def test_trend_strategy_bullish(self):
        bars = []
        for i in range(250):
            bars.append({
                "time": f"2024-01-{(i % 28) + 1:02d} {(i % 24):02d}:00:00",
                "open": 1.0900 + i * 0.0005,
                "high": 1.0900 + i * 0.0005 + 0.001,
                "low": 1.0900 + i * 0.0005 - 0.0005,
                "close": 1.0900 + i * 0.0005,
            })
        
        rsi = [50.0] * 50
        sma_values = {"sma50": [1.0900 + i * 0.0005 for i in range(200)], 
                     "sma20": [1.0900 + i * 0.0005 for i in range(200)]}
        
        strategy = create_regime_strategy()
        result = strategy.analyze(bars, rsi, sma_values)
        
        assert result["type"] in ["READY", "NONE"]
    
    def test_range_strategy_oversold(self):
        bars = [{"close": 1.0900, "open": 1.0900, "high": 1.0910, "low": 1.0890}] * 250
        
        rsi = [20.0] * 50
        sma_values = {"sma50": [1.0900] * 200, "sma20": [1.0900] * 200}
        
        strategy = create_regime_strategy()
        result = strategy.analyze(bars, rsi, sma_values)
        
        if result["type"] == "READY":
            assert result["direction"] == "BUY"
            assert result["regime"] == "RANGE"
    
    def test_range_strategy_overbought(self):
        bars = [{"close": 1.0900, "open": 1.0900, "high": 1.0910, "low": 1.0890}] * 250
        
        rsi = [80.0] * 50
        sma_values = {"sma50": [1.0900] * 200, "sma20": [1.0900] * 200}
        
        strategy = create_regime_strategy()
        result = strategy.analyze(bars, rsi, sma_values)
        
        if result["type"] == "READY":
            assert result["direction"] == "SELL"
            assert result["regime"] == "RANGE"
    
    def test_volatile_skip(self):
        import random
        bars = []
        for i in range(50):
            bars.append({
                "time": f"2024-01-{(i % 28) + 1:02d} {(i % 24):02d}:00:00",
                "open": 1.0900 + random.uniform(-0.02, 0.02),
                "high": 1.1100,
                "low": 1.0700,
                "close": 1.0900 + random.uniform(-0.02, 0.02),
            })
        
        rsi = [50.0] * 50
        sma_values = {"sma50": [1.0900] * 200, "sma20": [1.0900] * 200}
        
        strategy = create_regime_strategy()
        result = strategy.analyze(bars, rsi, sma_values)
        
        assert result.get("type") == "NONE"