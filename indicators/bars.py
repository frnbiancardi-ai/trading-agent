"""Indicatori bar-level: rapporto risk/reward (Wave 0).

Wave 3 aggiungerà NR4/NR7 + Boomer e Closing Score (Defendi).
"""
from __future__ import annotations


def calculate_risk_reward(entry: float, sl: float, tp: float) -> float:
    """Rapporto reward/risk. 0.0 se SL == entry (rischio nullo non valido)."""
    risk = abs(entry - sl)
    if risk == 0:
        return 0.0
    reward = abs(tp - entry)
    return round(reward / risk, 4)
