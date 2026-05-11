"""Phase 6 Wave 1: market handlers R1/R2 additive tests (D-C1).

R1 (get_market_snapshot):
- default 200 bars (override via 'bars' 50-500)
- legacy 'indicators' field (sma_20/ema_50/rsi_14/atr_14) preservato
- nuovo 'indicators_extended' field (Phase 2 ExtendedIndicators)

R2 (scan_symbol_candidates):
- nuovo 'regime' field per candidato (compressed/normal/expanded)
- nuovo 'correlation_warnings' array (popolato da Wave 4)

Wave 4 (MCP-09/-11/-12) tests preservati come xfail.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mcp_tools.handlers.market import (
    handle_get_market_snapshot,
    handle_scan_symbol_candidates,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _bullish_ohlc(n: int) -> list[dict]:
    """OHLC sintetico monotono crescente per testing deterministico."""
    return [
        {
            "time": 1700000000 + i * 900,
            "open": 1.10 + i * 0.0001,
            "high": 1.11 + i * 0.0001,
            "low": 1.09 + i * 0.0001,
            "close": 1.105 + i * 0.0001,
            "volume": 100,
        }
        for i in range(n)
    ]


@pytest.fixture
def mock_mt5():
    """Mock Mt5Client per test handler R1/R2."""
    m = MagicMock()
    m.get_ohlc.side_effect = lambda sym, tf, n: _bullish_ohlc(n)
    m.get_symbol_info.return_value = SimpleNamespace(
        bid=1.105, ask=1.1051, point=0.00001, digits=5,
    )
    return m


@pytest.fixture
def mock_cfg():
    """Mock Config con valori Phase 6 D-C1."""
    c = MagicMock()
    c.MCP_DEFAULT_BARS = 200
    c.TIMEFRAME = "M15"
    c.SYMBOLS = ["EURUSD", "GBPUSD"]
    return c


# ── Wave 1 — R1: get_market_snapshot esteso (D-C1) ──────────────────────────

def test_snapshot_default_200_bars(mock_mt5, mock_cfg):
    """Default 200 barre se 'bars' non specificato (D-C1)."""
    out = handle_get_market_snapshot({"symbol": "EURUSD"}, mock_mt5, mock_cfg)
    assert out["bars_used"] == 200
    assert out["symbol"] == "EURUSD"


def test_snapshot_explicit_50_bars(mock_mt5, mock_cfg):
    """Override bars=50 (legacy behavior preservato via parametro esplicito)."""
    out = handle_get_market_snapshot(
        {"symbol": "EURUSD", "bars": 50}, mock_mt5, mock_cfg,
    )
    assert out["bars_used"] == 50


def test_snapshot_legacy_and_extended(mock_mt5, mock_cfg):
    """Sia indicators (4 chiavi legacy) sia indicators_extended (Phase 2) presenti."""
    out = handle_get_market_snapshot({"symbol": "EURUSD"}, mock_mt5, mock_cfg)
    # Legacy 4 indicators
    assert "indicators" in out
    legacy = out["indicators"]
    assert all(k in legacy for k in ("sma_20", "ema_50", "rsi_14", "atr_14"))
    # Extended field (Phase 2)
    assert "indicators_extended" in out
    # Phase 2 esiste -> non None
    assert out["indicators_extended"] is not None


# ── Wave 1 — R2: scan_symbol_candidates con regime + correlation_warnings ───

def test_scan_includes_regime(mock_mt5, mock_cfg):
    """Ogni candidato ha campo 'regime' (compressed/normal/expanded) D-C1."""
    out = handle_scan_symbol_candidates(
        {"symbols": ["EURUSD", "GBPUSD"]}, mock_mt5, mock_cfg,
    )
    assert "candidates" in out
    for cand in out["candidates"]:
        assert "regime" in cand
        assert cand["regime"] in ("compressed", "normal", "expanded")


def test_scan_correlation_warnings(mock_mt5, mock_cfg):
    """Ogni candidato ha 'correlation_warnings' (array, vuoto in Wave 1)."""
    out = handle_scan_symbol_candidates(
        {"symbols": ["EURUSD"]}, mock_mt5, mock_cfg,
    )
    assert "candidates" in out
    for cand in out["candidates"]:
        assert "correlation_warnings" in cand
        assert isinstance(cand["correlation_warnings"], list)


# ── Wave 4 — tests xfail preservati ──────────────────────────────────────────


def test_correlation_matrix_2symbols():
    pytest.xfail("MISSING — Wave 4 MCP-09")


def test_correlation_default_lookback():
    pytest.xfail("MISSING — Wave 4 MCP-09: default 100")


def test_session_state_london_open():
    pytest.xfail("MISSING — Wave 4 MCP-11")


def test_session_state_dst():
    pytest.xfail("MISSING — Wave 4 MCP-11 DST")


def test_multi_tf_snapshot():
    pytest.xfail("MISSING — Wave 4 MCP-12")
