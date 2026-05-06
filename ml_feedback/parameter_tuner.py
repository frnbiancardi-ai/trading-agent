"""Parameter Tuner: suggerisce aggiustamenti parametri basati su analisi."""
from dataclasses import dataclass
from typing import Protocol


class ParameterTuner(Protocol):
    def suggest_params(self, trades, current_params: dict) -> list:
        ...


@dataclass
class ParamSuggestion:
    param_name: str
    current_value: float
    suggested_value: float
    confidence: float
    reason: str
    evidence: list


class HeuristicTuner:
    def __init__(self, min_samples: int = 30):
        self.min_samples = min_samples
    
    def suggest_params(self, trades, current_params: dict) -> list[ParamSuggestion]:
        suggestions = []
        
        buy_losses = [t for t in trades if t.direction == "BUY" and t.outcome.value == "LOSS"]
        sell_losses = [t for t in trades if t.direction == "SELL" and t.outcome.value == "LOSS"]
        
        session_losses = {}
        for t in trades:
            if t.outcome.value == "LOSS":
                session_losses[t.session] = session_losses.get(t.session, 0) + 1
        
        worst_session = max(session_losses, key=session_losses.get) if session_losses else None
        
        if worst_session == "ASIA":
            suggestions.append(ParamSuggestion(
                param_name="ENABLE_ASIA_SESSION",
                current_value=current_params.get("ENABLE_ASIA_SESSION", True),
                suggested_value=False,
                confidence=0.8,
                reason=f"Sessione ASIA: {session_losses.get('ASIA', 0)} perdite",
                evidence=[t.symbol for t in buy_losses[:5]]
            ))
        
        loss_hold_times = [t.hold_time_minutes for t in trades if t.outcome.value == "LOSS"]
        if loss_hold_times and sum(loss_hold_times) / len(loss_hold_times) < 30:
            suggestions.append(ParamSuggestion(
                param_name="MIN_HOLD_MINUTES",
                current_value=current_params.get("MIN_HOLD_MINUTES", 15),
                suggested_value=30,
                confidence=0.7,
                reason=f"Hold medio perdite: {sum(loss_hold_times)/len(loss_hold_times):.0f} min",
                evidence=[t.symbol for t in trades[:5]]
            ))
        
        loss_with_breakout = [
            t for t in trades 
            if t.outcome.value == "LOSS" and t.breakout_volume_ratio is not None
        ]
        if loss_with_breakout:
            total_ratio = sum(t.breakout_volume_ratio for t in loss_with_breakout)
            avg_vol_ratio = total_ratio / len(loss_with_breakout) if loss_with_breakout else 0
            
            if avg_vol_ratio < 1.5:
                suggestions.append(ParamSuggestion(
                    param_name="MIN_BREAKOUT_VOLUME_RATIO",
                    current_value=current_params.get("MIN_BREAKOUT_VOLUME_RATIO", 1.5),
                    suggested_value=2.0,
                    confidence=0.75,
                    reason=f"Volume medio perdite: {avg_vol_ratio:.2f}x",
                    evidence=[t.symbol for t in loss_with_breakout[:5]]
                ))
        
        return suggestions


class MLTuner:
    def __init__(self, min_samples: int = 100):
        self.min_samples = min_samples
        self.model = None
    
    def suggest_params(self, trades, current_params: dict) -> list[ParamSuggestion]:
        try:
            import xgboost as xgb
            from sklearn.ensemble import GradientBoostingClassifier
        except ImportError:
            tuner = HeuristicTuner(self.min_samples)
            return tuner.suggest_params(trades, current_params)
        
        return []


__all__ = ["HeuristicTuner", "MLTuner", "ParamSuggestion"]