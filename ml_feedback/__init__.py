"""
ML Feedback Loop per Forex Trading.

Usage:
    from ml_feedback import MLFeedbackLoop
    
    ml = MLFeedbackLoop()
    
    analysis = ml.analyze_trades(trades)
    quality = ml.predict_quality(bars, setup)
    suggestions = ml.suggest_parameters(trades, current_env_params)
"""
from .trade_analyzer import extract_trade_features, TradeFeatures, TradeOutcome
from .feature_quality import FeatureQualityModel, QualityPrediction
from .parameter_tuner import HeuristicTuner, MLTuner, ParamSuggestion


class MLFeedbackLoop:
    def __init__(
        self,
        historical_data_path: str = "C:\\trading-agent\\data\\historical"
    ):
        self.historical_data_path = historical_data_path
        self.quality_model = FeatureQualityModel()
        self.tuner = HeuristicTuner()
    
    def analyze_trades(self, trades: list[dict]) -> dict:
        features = [extract_trade_features(t) for t in trades]
        
        losses = [f for f in features if f.outcome == TradeOutcome.LOSS]
        wins = [f for f in features if f.outcome == TradeOutcome.WIN]
        
        analysis = {
            "total_trades": len(features),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(features) if features else 0,
            "by_session": {},
            "by_day": {},
            "avg_hold_time_loss": 0,
            "common_failure_patterns": [],
        }
        
        for f in features:
            if f.session not in analysis["by_session"]:
                analysis["by_session"][f.session] = {"wins": 0, "losses": 0}
            if f.outcome == TradeOutcome.WIN:
                analysis["by_session"][f.session]["wins"] += 1
            else:
                analysis["by_session"][f.session]["losses"] += 1
        
        if losses:
            analysis["avg_hold_time_loss"] = sum(
                f.hold_time_minutes for f in losses
            ) / len(losses)
        
        if len(losses) >= 5:
            for session, stats in analysis["by_session"].items():
                if stats["losses"] > stats["wins"]:
                    analysis["common_failure_patterns"].append(
                        f"Session {session}: {stats['losses']} losses vs {stats['wins']} wins"
                    )
        
        return analysis
    
    def predict_quality(
        self, 
        bars: list[dict], 
        setup: dict
    ) -> QualityPrediction:
        return self.quality_model.predict(bars, setup)
    
    def suggest_parameters(
        self, 
        trades: list[dict], 
        current_params: dict
    ) -> list[ParamSuggestion]:
        features = [extract_trade_features(t) for t in trades]
        return self.tuner.suggest_params(features, current_params)
    
    def train_quality_model(
        self, 
        X: list, 
        y: list
    ) -> dict:
        return self.quality_model.cross_validate(X, y)


__all__ = [
    "MLFeedbackLoop",
    "extract_trade_features",
    "TradeFeatures",
    "TradeOutcome",
    "QualityPrediction",
    "FeatureQualityModel",
    "ParamSuggestion",
    "HeuristicTuner",
]