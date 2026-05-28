"""Indicatori di trend: SMA ed EMA in Python puro.

Convenzione: serie di output stessa lunghezza dell'input, warmup → None.
Loop cumulativo-incrementale O(n).
"""
from __future__ import annotations


def sma(values: list[float], period: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    cum = sum(values[:period])
    out[period - 1] = cum / period
    for i in range(period, n):
        cum += values[i] - values[i - period]
        out[i] = cum / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    alpha = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, n):
        prev = out[i - 1]
        out[i] = alpha * values[i] + (1.0 - alpha) * prev  # type: ignore[operator]
    return out
