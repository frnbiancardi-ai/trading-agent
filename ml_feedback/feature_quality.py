"""ML Feature Quality: classifier per valutare qualità entry."""
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class QualityPrediction:
    breakout_quality: float
    entry_timing_score: float
    confluence_valid: bool
    recommendation: str


class FeatureQualityModel:
    def __init__(self):
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.preprocessing import StandardScaler
            
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                random_state=42
            )
            self.scaler = StandardScaler()
            self._is_fitted = False
            self._sklearn_available = True
        except ImportError:
            self._sklearn_available = False
            self._is_fitted = False
    
    def _extract_features(self, bars: list, setup: dict) -> np.ndarray:
        closes = np.array([b["close"] for b in bars])
        volumes = np.array([b.get("volume", 0) for b in bars])
        
        if len(closes) < 10:
            return np.array([0.5, 1.0, 0.001, 0.0, 50.0])
        
        returns = np.diff(closes) / closes[:-1]
        momentum = np.mean(returns[-5:]) / np.std(returns[-10:]) if len(returns) >= 10 else 0
        
        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else volumes[-1]
        vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1.0
        
        atr = bars[-1]["high"] - bars[-1]["low"] if "high" in bars[-1] else 0.001
        
        return np.array([
            momentum,
            vol_ratio,
            atr / closes[-1] if closes[-1] > 0 else 0.001,
            setup.get("trend_strength", 0),
            setup.get("rsi", 50),
        ])
    
    def fit(self, X: list, y: list) -> "FeatureQualityModel":
        if not self._sklearn_available:
            return self
        
        X_arr = np.array(X)
        y_arr = np.array(y)
        
        X_scaled = self.scaler.fit_transform(X_arr)
        self.model.fit(X_scaled, y_arr)
        self._is_fitted = True
        
        return self
    
    def predict(self, bars: list, setup: dict) -> QualityPrediction:
        breakout_quality = 0.5
        
        if self._sklearn_available and self._is_fitted:
            features = self._extract_features(bars, setup)
            features_scaled = self.scaler.transform([features])
            
            try:
                proba = self.model.predict_proba(features_scaled)[0]
                breakout_quality = float(proba[1]) if len(proba) > 1 else 0.5
            except Exception:
                breakout_quality = 0.5
        
        entry_timing_score = min(breakout_quality + 0.1, 1.0)
        
        trend = setup.get("trend_strength", 0)
        rsi = setup.get("rsi", 50)
        confluence_valid = bool(trend > 0.4 and 30 < rsi < 70)
        
        if breakout_quality > 0.7 and confluence_valid:
            recommendation = "PROCEED"
        elif breakout_quality < 0.3:
            recommendation = "SKIP"
        else:
            recommendation = "REVIEW"
        
        return QualityPrediction(
            breakout_quality=breakout_quality,
            entry_timing_score=entry_timing_score,
            confluence_valid=confluence_valid,
            recommendation=recommendation
        )
    
    def cross_validate(self, X: list, y: list, cv: int = 5) -> dict:
        if not self._sklearn_available:
            return {"error": "sklearn not available"}
        
        from sklearn.model_selection import cross_val_score
        
        X_arr = np.array(X)
        y_arr = np.array(y)
        
        try:
            scores = cross_val_score(self.model, X_arr, y_arr, cv=cv, scoring="accuracy")
            return {
                "mean_accuracy": float(np.mean(scores)),
                "std_accuracy": float(np.std(scores)),
                "cv_scores": scores.tolist()
            }
        except Exception as e:
            return {"error": str(e)}


__all__ = ["FeatureQualityModel", "QualityPrediction"]