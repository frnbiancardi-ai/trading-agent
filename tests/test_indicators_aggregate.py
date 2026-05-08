"""Test indicators.aggregate.compute_all — backward-compat shape."""
from __future__ import annotations

from indicators import compute_all


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
