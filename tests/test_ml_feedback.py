"""Tests per ML Feedback Loop."""
import pytest
from datetime import datetime
from ml_feedback import (
    MLFeedbackLoop,
    extract_trade_features,
    TradeFeatures,
    TradeOutcome,
)


class TestTradeAnalyzer:
    def test_extract_trade_features_win(self):
        trade = {
            "symbol": "EURUSD",
            "entry_time": "2024-01-15 10:00:00",
            "exit_time": "2024-01-15 14:00:00",
            "direction": "BUY",
            "entry_price": 1.0900,
            "exit_price": 1.0920,
            "sl": 1.0880,
            "tp": 1.0940,
            "atr_at_entry": 0.0010,
            "volatility_regime": "MEDIUM",
        }
        
        features = extract_trade_features(trade)
        
        assert features.symbol == "EURUSD"
        assert features.outcome == TradeOutcome.WIN
        assert abs(features.profit_pips - 0.002) < 0.0001
        assert features.session == "LONDON"
        assert features.hold_time_minutes == 240
    
    def test_extract_trade_features_loss(self):
        trade = {
            "symbol": "GBPUSD",
            "entry_time": "2024-01-15 03:00:00",
            "exit_time": "2024-01-15 05:00:00",
            "direction": "BUY",  # BUY, price goes DOWN = loss
            "entry_price": 1.2700,
            "exit_price": 1.2680,
            "sl": 1.2720,
            "tp": 1.2680,
            "atr_at_entry": 0.0008,
            "volatility_regime": "LOW",
        }
        
        features = extract_trade_features(trade)
        
        assert features.symbol == "GBPUSD"
        assert features.outcome == TradeOutcome.LOSS
        assert features.session == "ASIA"
    
    def test_extract_trade_features_sell_win(self):
        trade = {
            "symbol": "USDJPY",
            "entry_time": "2024-01-15 14:00:00",
            "exit_time": "2024-01-15 18:00:00",
            "direction": "SELL",
            "entry_price": 148.00,
            "exit_price": 147.50,
            "sl": 148.20,
            "tp": 147.30,
        }
        
        features = extract_trade_features(trade)
        
        assert features.symbol == "USDJPY"
        assert features.outcome == TradeOutcome.WIN
        assert features.profit_pips == 0.50
        assert features.session == "NY"


class TestMLFeedbackLoop:
    @pytest.fixture
    def ml_loop(self):
        return MLFeedbackLoop()
    
    def test_analyze_trades(self, ml_loop):
        trades = [
            {
                "symbol": "EURUSD",
                "entry_time": "2024-01-15 10:00:00",
                "exit_time": "2024-01-15 14:00:00",
                "direction": "BUY",
                "entry_price": 1.0900,
                "exit_price": 1.0920,
                "sl": 1.0880,
                "tp": 1.0940,
            },
            {
                "symbol": "EURUSD",
                "entry_time": "2024-01-15 15:00:00",
                "exit_time": "2024-01-15 16:00:00",
                "direction": "BUY",
                "entry_price": 1.0920,
                "exit_price": 1.0900,
                "sl": 1.0900,
                "tp": 1.0940,
            },
        ]
        
        analysis = ml_loop.analyze_trades(trades)
        
        assert analysis["total_trades"] == 2
        assert analysis["wins"] == 1
        assert analysis["losses"] == 1
        assert analysis["win_rate"] == 0.5
    
    def test_predict_quality_no_model(self, ml_loop):
        bars = [
            {"open": 1.0900, "high": 1.0920, "low": 1.0890, "close": 1.0910}
        ] * 20
        setup = {"trend_strength": 0.5, "rsi": 45}
        
        quality = ml_loop.predict_quality(bars, setup)
        
        assert quality.recommendation in ["PROCEED", "SKIP", "REVIEW"]
        assert 0 <= quality.breakout_quality <= 1
    
    def test_suggest_parameters(self, ml_loop):
        trades = [
            {
                "symbol": "EURUSD",
                "entry_time": "2024-01-15 03:00:00",
                "exit_time": "2024-01-15 04:00:00",
                "direction": "BUY",
                "entry_price": 1.0900,
                "exit_price": 1.0880,
                "sl": 1.0880,
                "tp": 1.0940,
            },
        ] * 10
        
        current_params = {
            "ENABLE_ASIA_SESSION": True,
            "MIN_HOLD_MINUTES": 15,
            "MIN_BREAKOUT_VOLUME_RATIO": 1.5,
        }
        
        suggestions = ml_loop.suggest_parameters(trades, current_params)
        
        assert isinstance(suggestions, list)


class TestFeatureQuality:
    def test_quality_prediction_defaults(self):
        from ml_feedback.feature_quality import FeatureQualityModel, QualityPrediction
        
        model = FeatureQualityModel()
        quality = model.predict([], {})
        
        assert quality.recommendation == "REVIEW"
        assert quality.breakout_quality == 0.5
    
    def test_confluence_validation(self):
        from ml_feedback.feature_quality import FeatureQualityModel
        
        model = FeatureQualityModel()
        
        bars = [{"close": 1.09, "high": 1.092, "low": 1.088, "volume": 1000}] * 25
        
        setup_good = {"trend_strength": 0.6, "rsi": 50}
        quality = model.predict(bars, setup_good)
        assert quality.confluence_valid is True
        
        setup_bad = {"trend_strength": 0.1, "rsi": 80}
        quality = model.predict(bars, setup_bad)
        assert quality.confluence_valid is False