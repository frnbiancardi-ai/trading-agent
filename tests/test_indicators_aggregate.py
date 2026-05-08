"""Test indicators.aggregate.compute_all — backward-compat shape + compute_all_extended (INDIC-14 plan)."""
from __future__ import annotations

from indicators import compute_all, compute_all_extended


def test_compute_all_keys_unchanged(eurusd_h1_500):
    out = compute_all(eurusd_h1_500)
    assert set(out.keys()) == {"sma_20", "ema_50", "rsi_14", "atr_14"}, (
        "compute_all shape MUST stay 4-key (claude_agent.py:12 + mcp_server.py:28)"
    )


def test_compute_all_returns_finite_floats(eurusd_h1_500):
    out = compute_all(eurusd_h1_500)
    for k, v in out.items():
        assert v is not None, f"{k} e None su 500 barre — atteso valore valido"
        assert isinstance(v, float), f"{k} non e float: {type(v)}"


# ── INDIC-14 plan: compute_all_extended ──────────────────────────────────────


def test_compute_all_unchanged_legacy_callsite(eurusd_h1_500):
    """Hard-lock backward-compat: claude_agent.py:12 + mcp_server.py:28 attendono 4 chiavi esatte."""
    out = compute_all(eurusd_h1_500)
    assert set(out.keys()) == {"sma_20", "ema_50", "rsi_14", "atr_14"}, (
        "compute_all keys MUST stay 4 — backward compat"
    )


def test_compute_all_extended_contains_all_indicators(eurusd_h1_500):
    """compute_all_extended deve contenere le 4 chiavi legacy + l'intero snapshot esteso."""
    cfg = {"window": 200, "compressed_below": 30, "expanded_above": 70}
    out = compute_all_extended(eurusd_h1_500, regime_cfg=cfg)
    # Legacy 4 keys ancora presenti
    for k in ("sma_20", "ema_50", "rsi_14", "atr_14"):
        assert k in out, f"chiave legacy {k} mancante in compute_all_extended"
    # Nuove chiavi (sample completo)
    expected = {
        "bb_upper", "bb_middle", "bb_lower", "bb_bbw", "bb_squeeze",
        "kc_upper", "kc_lower",
        "adx_14", "plus_di_14", "minus_di_14",
        "macd", "macd_signal", "macd_hist",
        "stoch_k", "stoch_d",
        "donch_upper", "donch_lower",
        "pivot_p", "pivot_camarilla_h3", "pivot_camarilla_l3",
        "fib_0382", "fib_0500", "fib_0618", "fib_direction",
        "vwap", "avg_volume_20",
        "nr4", "nr7", "boomer", "closing_score",
        "hurst", "regime_state", "regime_atr_pct",
    }
    missing = expected - set(out.keys())
    assert not missing, f"compute_all_extended missing keys: {missing}"


def test_compute_all_extended_without_regime_cfg(eurusd_h1_500):
    """regime_cfg=None → regime_state e regime_atr_pct devono essere None (no-op safe)."""
    out = compute_all_extended(eurusd_h1_500, regime_cfg=None)
    assert out["regime_state"] is None
    assert out["regime_atr_pct"] is None


def test_compute_all_extended_empty_input():
    """Input vuoto → 4 chiavi legacy (None) + flag extended_empty=True."""
    out = compute_all_extended([], regime_cfg=None)
    assert out.get("extended_empty") is True
    for k in ("sma_20", "ema_50", "rsi_14", "atr_14"):
        assert k in out


def test_all_14_indic_requirement_symbols_exposed():
    """Verifica che ogni INDIC-01..14 abbia almeno una funzione pubblica esposta."""
    import indicators
    required = {
        # INDIC-01 Bollinger
        "bollinger_bands", "BollingerResult",
        # INDIC-02 ADX
        "adx", "ADXResult",
        # INDIC-03 MACD
        "macd", "MACDResult",
        # INDIC-04 Stochastic
        "stochastic", "StochasticResult",
        # INDIC-05 Donchian
        "donchian", "DonchianResult",
        # INDIC-06 Keltner
        "keltner", "KeltnerResult",
        # INDIC-07 VWAP
        "vwap_intraday", "vwap_anchored", "VWAPResult",
        # INDIC-08 Fibonacci
        "fibonacci_retracements", "FibonacciResult",
        # INDIC-09 Pivots
        "pivots", "PivotResult",
        # INDIC-10 Narrow Range
        "narrow_range", "NRResult",
        # INDIC-11 Closing Score
        "closing_score", "ClosingScoreResult",
        # INDIC-12 Hurst
        "hurst_rs", "HurstResult",
        # INDIC-13 MTF align
        "align", "MTFAlignmentResult",
        # INDIC-14 Volatility regime
        "volatility_regime", "RegimeResult", "load_regime_config",
    }
    missing = [s for s in required if not hasattr(indicators, s)]
    assert not missing, f"symbols missing from indicators package: {missing}"


def test_legacy_callsite_imports_unchanged():
    """Le 4 callsite legacy DEVONO continuare a funzionare invariate.

    Verifica anche che il fresh-reimport del pacchetto `indicators` non
    importi `pandas_ta` (D-07). Rimuove pandas_ta da sys.modules prima del
    check perche test parity pandas-ta precedenti (bbands/kc/adx/macd/...) lo
    hanno gia caricato a livello di sessione pytest — quello che vogliamo
    verificare e che `import indicators` da solo non lo tira dentro.
    """
    import sys
    # Rimuovi pandas_ta + indicators per partire da uno stato pulito
    for m in list(sys.modules):
        if m.startswith("indicators") or m == "pandas_ta" or m.startswith("pandas_ta."):
            del sys.modules[m]
    # claude_agent.py:12 + mcp_server.py:28
    from indicators import compute_all  # noqa: F401
    # scanner.py:10
    from indicators import sma, ema, rsi, atr  # noqa: F401
    # strategy.py:11 (full tuple)
    from indicators import (  # noqa: F401
        sma, ema, rsi, atr, avg_volume,
        calculate_trend_strength, find_support_resistance,
        check_breakout_quality, calculate_risk_reward,
    )
    assert "pandas_ta" not in sys.modules, "pandas_ta importato a runtime — vietato (D-07)"
