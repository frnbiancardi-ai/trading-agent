"""Pacchetto indicatori — math puro, niente pandas/ta-lib a runtime.

Convenzione: ogni serie restituita ha la stessa lunghezza dell'input.
Le posizioni iniziali insufficienti per il calcolo sono `None`.

Backward-compat (D-03): le 4 callsite esistenti
(`claude_agent.py:12`, `mcp_server.py:28`, `scanner.py:10`, `strategy.py:11`)
continuano a funzionare invariate grazie ai re-export sotto.
"""
from indicators.trend import sma, ema
from indicators.momentum import (
    rsi,
    check_rsi_divergence,
    adx,
    macd,
    stochastic,
    ADXResult,
    MACDResult,
    StochasticResult,
)
from indicators.volatility import (
    atr,
    bollinger_bands,
    keltner,
    BollingerResult,
    KeltnerResult,
)
from indicators.structure import (
    find_support_resistance,
    check_breakout_quality,
    donchian,
    fibonacci_retracements,
    pivots,
    DonchianResult,
    FibonacciResult,
    PivotResult,
)
from indicators.volume import avg_volume
from indicators.bars import calculate_risk_reward
from indicators.mtf import calculate_trend_strength
from indicators.aggregate import compute_all
from indicators.hurst import hurst_rs, HurstResult
from indicators._helpers import _last_valid, _wilder_rsi  # privati, retro-compat per test

__all__ = [
    "sma",
    "ema",
    "rsi",
    "atr",
    "bollinger_bands",
    "keltner",
    "BollingerResult",
    "KeltnerResult",
    "adx",
    "macd",
    "stochastic",
    "ADXResult",
    "MACDResult",
    "StochasticResult",
    "avg_volume",
    "calculate_trend_strength",
    "find_support_resistance",
    "check_breakout_quality",
    "calculate_risk_reward",
    "check_rsi_divergence",
    "compute_all",
    "hurst_rs",
    "HurstResult",
    "donchian",
    "fibonacci_retracements",
    "pivots",
    "DonchianResult",
    "FibonacciResult",
    "PivotResult",
]
