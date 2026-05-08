"""Aggregatori snapshot: `compute_all` 4-key per backward-compat (Wave 0).

Wave 3 aggiungerà `compute_all_extended` con i 14 indicatori; `compute_all`
deve restare bit-for-bit identico per non rompere `claude_agent.py:12` e
`mcp_server.py:28`.
"""
from __future__ import annotations

from indicators._helpers import _last_valid
from indicators.momentum import rsi
from indicators.trend import ema, sma
from indicators.volatility import atr


def compute_all(ohlc: list[dict]) -> dict:
    """Estrae closes/highs/lows dal list[dict] e ritorna l'ultimo valore valido
    di sma_20, ema_50, rsi_14, atr_14."""
    closes = [b["close"] for b in ohlc]
    highs = [b["high"] for b in ohlc]
    lows = [b["low"] for b in ohlc]
    return {
        "sma_20": _last_valid(sma(closes, 20)),
        "ema_50": _last_valid(ema(closes, 50)),
        "rsi_14": _last_valid(rsi(closes, 14)),
        "atr_14": _last_valid(atr(highs, lows, closes, 14)),
    }
