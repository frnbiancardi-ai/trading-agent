"""Indicatori di volume: media tick_volume su finestra (Wave 0).

Wave 2 aggiungerà VWAP intraday (reset NY-17) e VWAP anchored.
"""
from __future__ import annotations


def avg_volume(bars: list[dict], period: int = 20) -> float:
    """Media tick_volume sulle ultime `period` barre. 0.0 se dati assenti."""
    if not bars or period <= 0:
        return 0.0
    sub = bars[-period:]
    vols = [b.get("tick_volume", b.get("volume", 0)) or 0 for b in sub]
    if not vols:
        return 0.0
    return sum(vols) / len(vols)
