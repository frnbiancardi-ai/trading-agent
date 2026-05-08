"""Test universali di purezza: nessun import oracolare a runtime, nessuna future leakage.

Le proprieta verificate qui valgono per OGNI indicatore rolling che il pacchetto
`indicators` esporra. Wave 1+ DEVONO aggiungere test parametrizzati analoghi per
i nuovi indicatori (BB, ADX, MACD, Stoch, Donchian, Keltner, regime, Hurst, ...).
"""
from __future__ import annotations

import sys

import pytest


def test_no_pandas_ta_at_runtime():
    """Pitfall 8: pandas_ta e dev-dep, mai importato dal pacchetto runtime."""
    if "pandas_ta" in sys.modules:
        del sys.modules["pandas_ta"]
    # Force a fresh import of the indicators package
    for mod in list(sys.modules):
        if mod == "indicators" or mod.startswith("indicators."):
            del sys.modules[mod]
    import indicators  # noqa: F401
    assert "pandas_ta" not in sys.modules, "pandas_ta importato a runtime — vietato (D-07)"


def test_backward_compat_callsite_imports():
    """Le 4 callsite esistenti devono continuare a risolvere."""
    # claude_agent.py:12 + mcp_server.py:28
    from indicators import compute_all  # noqa: F401
    # scanner.py:10
    from indicators import sma, ema, rsi, atr  # noqa: F401
    # strategy.py:11
    from indicators import (  # noqa: F401
        sma,
        ema,
        rsi,
        atr,
        avg_volume,
        calculate_trend_strength,
        find_support_resistance,
        check_breakout_quality,
        calculate_risk_reward,
    )


@pytest.mark.parametrize("idx", [50, 100, 200, 350, 499])
def test_no_future_leakage_atr(eurusd_h1_500, idx):
    """ATR(prefix)[i] == ATR(full)[i] per i fissato — assenza di future leakage."""
    from indicators import atr
    bars = eurusd_h1_500
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    full = atr(highs, lows, closes, 14)
    prefix = bars[: idx + 1]
    p_h = [b["high"] for b in prefix]
    p_l = [b["low"] for b in prefix]
    p_c = [b["close"] for b in prefix]
    partial = atr(p_h, p_l, p_c, 14)
    assert partial[idx] == full[idx], f"future leakage at i={idx}"


@pytest.mark.parametrize("idx", [25, 100, 250, 400, 499])
def test_no_future_leakage_sma_ema_rsi(eurusd_h1_500, idx):
    """SMA/EMA/RSI(prefix)[i] == (full)[i] per i fissato."""
    from indicators import sma, ema, rsi
    bars = eurusd_h1_500
    closes = [b["close"] for b in bars]
    prefix_closes = closes[: idx + 1]
    assert sma(closes, 20)[idx] == sma(prefix_closes, 20)[idx]
    assert ema(closes, 50)[idx] == ema(prefix_closes, 50)[idx]
    assert rsi(closes, 14)[idx] == rsi(prefix_closes, 14)[idx]
