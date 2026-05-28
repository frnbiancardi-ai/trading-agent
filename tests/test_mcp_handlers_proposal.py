"""Phase 6 Wave 1: proposal handler R3 additive tests (D-C1).

R3 (propose_trade):
- nuovo 'setup_type' (A/B/C/D/null) ereditato da Phase 4 strategy
- nuovo 'confluence_score' (0-1 / null) ereditato da Phase 4 D-08

Freeform manual proposals: i due nuovi campi sono null (no derivation).
Setup-driven proposals: i due campi sono valorizzati da args.context.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mcp_tools.handlers.proposal import handle_propose_trade


@pytest.fixture
def mock_cfg():
    """Mock Config minimale per handle_propose_trade."""
    c = MagicMock()
    c.TIMEFRAME = "M15"
    return c


@pytest.fixture
def mock_log():
    """Mock logger per evitare side-effect su file."""
    return MagicMock()


# ── Wave 1 — R3: propose_trade esteso (D-C1) ─────────────────────────────────

def test_propose_includes_setup_type(mock_log, mock_cfg):
    """args.context.{setup_type,confluence_score} valorizzati -> output li espone."""
    args = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": 1.10,
        "stop_loss_price": 1.095,
        "take_profit_price": 1.11,
        "confidence": 0.7,
        "rationale": "Setup A breakout 1.10 con RSI bullish",
        "context": {"setup_type": "A", "confluence_score": 0.85},
    }
    out = handle_propose_trade(args, mock_log, mock_cfg)
    assert out["setup_type"] == "A"
    assert out["confluence_score"] == 0.85
    # Sanity: status, executed, proposal preservati
    assert out["status"] == "proposed"
    assert out["executed"] is False
    assert "proposal" in out


def test_propose_freeform_null_setup(mock_log, mock_cfg):
    """args.context assente -> setup_type/confluence_score = null (freeform manual)."""
    args = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": 1.10,
        "stop_loss_price": 1.095,
        "take_profit_price": 1.11,
        "confidence": 0.7,
        "rationale": "Freeform manual proposal",
    }
    out = handle_propose_trade(args, mock_log, mock_cfg)
    assert out["setup_type"] is None
    assert out["confluence_score"] is None
