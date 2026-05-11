"""Phase 6 Wave 3 (Plan 06-04): position handler tests.

Test reali per `mcp_tools.handlers.position` (MCP-16 modify_position +
MCP-17 get_position_state, D-B1 conflict rules + D-B3 stops_level + DRY_RUN gate).
Sostituiscono gli 8 stub xfail Wave 0.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_mt5():
    """Mt5Client mock: posizione BUY EURUSD aperta a 1.10."""
    m = MagicMock()
    pos = SimpleNamespace(
        symbol="EURUSD", lots=0.5, direction="BUY",
        entry_price=1.10, stop_loss=1.0950, take_profit=1.11,
        profit=10.0, ticket=123,
    )
    m.get_position.return_value = pos
    m.get_symbol_info.return_value = SimpleNamespace(
        bid=1.1010, ask=1.1011, point=0.00001, trade_stops_level=10,
    )
    m.modify_position.return_value = SimpleNamespace(
        success=True, error_message=None, order_id=99,
    )
    m.partial_close.return_value = SimpleNamespace(
        success=True, error_message=None, order_id=98,
    )
    return m


@pytest.fixture
def mock_cfg(tmp_path):
    """Config mock: live mode + LOG_FILE su tmp per _trades_db_path."""
    return SimpleNamespace(
        DRY_RUN=False,
        EXECUTION_MODE="live",
        TRAIL_TICK_TIMEFRAME="M15",
        TRAIL_FAVORABLE_ONLY=True,
        LOG_FILE=str(tmp_path / "logs" / "agent.log"),
    )


@pytest.fixture
def mock_log():
    return MagicMock()


# ── Test 1: modify SL only — happy path ──────────────────────────────────────

def test_modify_sl_only(mock_mt5, mock_cfg, mock_log):
    from mcp_tools.handlers.position import handle_modify_position
    # current_price (BUY)=bid=1.1010; min_distance = 10pts*0.00001/0.0001 = 1 pip
    # SL=1.10 → distance=0.001=10 pips > 1 pip → ok
    out = handle_modify_position(
        {"position_id": 123, "new_sl": 1.10},
        mock_mt5, mock_cfg, mock_log,
    )
    assert out["ok"] is True
    assert out["dry_run"] is False
    assert any(a["action"] == "modify_sltp" for a in out["applied"])
    mock_mt5.modify_position.assert_called_once()


# ── Test 2: move SL to breakeven ─────────────────────────────────────────────

def test_move_sl_to_breakeven(mock_mt5, mock_cfg, mock_log):
    from mcp_tools.handlers.position import handle_modify_position
    out = handle_modify_position(
        {"position_id": 123, "move_sl_to_breakeven": True},
        mock_mt5, mock_cfg, mock_log,
    )
    assert out["ok"] is True
    # SL applicato = pos.entry_price = 1.10
    call = mock_mt5.modify_position.call_args
    assert call[1]["sl"] == 1.10


# ── Test 3: conflict trail + manual SL ────────────────────────────────────────

def test_conflict_trail_and_manual(mock_mt5, mock_cfg, mock_log, monkeypatch):
    from mcp_tools.handlers.position import handle_modify_position
    monkeypatch.setattr(
        "mcp_tools.handlers.position.register_trail",
        lambda *a, **k: None,
    )
    out = handle_modify_position(
        {"position_id": 123, "new_sl": 1.10, "trail_stop_atr_mult": 2.0},
        mock_mt5, mock_cfg, mock_log,
    )
    assert out["ok"] is False
    assert "trail_and_manual_sl" in out["error"]
    mock_mt5.modify_position.assert_not_called()


# ── Test 4: conflict breakeven + manual SL ───────────────────────────────────

def test_conflict_be_and_manual(mock_mt5, mock_cfg, mock_log):
    from mcp_tools.handlers.position import handle_modify_position
    out = handle_modify_position(
        {"position_id": 123, "new_sl": 1.10, "move_sl_to_breakeven": True},
        mock_mt5, mock_cfg, mock_log,
    )
    assert out["ok"] is False
    assert "be_and_manual_sl" in out["error"]
    mock_mt5.modify_position.assert_not_called()


# ── Test 5: partial_close_lots >= pos.volume ─────────────────────────────────

def test_partial_exceeds_volume(mock_mt5, mock_cfg, mock_log):
    from mcp_tools.handlers.position import handle_modify_position
    # pos.lots=0.5; partial_close_lots=0.6 ≥ 0.5
    out = handle_modify_position(
        {"position_id": 123, "partial_close_lots": 0.6},
        mock_mt5, mock_cfg, mock_log,
    )
    assert out["ok"] is False
    assert out["error"] == "partial_exceeds_volume"
    mock_mt5.partial_close.assert_not_called()


# ── Test 6: stops_level violation → suggested_sl ─────────────────────────────

def test_stops_level_violation_suggests(mock_mt5, mock_cfg, mock_log):
    """SL troppo vicino al current_price → reject + suggested_sl D-B3."""
    from mcp_tools.handlers.position import handle_modify_position
    # current_price (BUY) = bid = 1.1010
    # min_distance = 10 points * 0.00001 / 0.0001 = 1 pip = 0.0001
    # SL=1.10095 → distance = 1.1010 - 1.10095 = 0.00005 = 0.5 pip < 1 pip → violation
    out = handle_modify_position(
        {"position_id": 123, "new_sl": 1.10095},
        mock_mt5, mock_cfg, mock_log,
    )
    assert out["ok"] is False
    assert out["error"] == "stops_level_violation"
    assert "suggested_sl" in out
    assert out["suggested_sl"] < 1.1010
    mock_mt5.modify_position.assert_not_called()


# ── Test 7: DRY_RUN gate (EXECUTION_MODE=shadow) ─────────────────────────────

def test_modify_dry_run(mock_mt5, mock_cfg, mock_log):
    from mcp_tools.handlers.position import handle_modify_position
    mock_cfg.DRY_RUN = True
    mock_cfg.EXECUTION_MODE = "shadow"
    out = handle_modify_position(
        {"position_id": 123, "new_sl": 1.10},
        mock_mt5, mock_cfg, mock_log,
    )
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["execution_mode"] == "shadow"
    # GATE: nessun ordine inviato a broker (CLAUDE.md mandate)
    mock_mt5.modify_position.assert_not_called()
    mock_mt5.partial_close.assert_not_called()


# ── Test 8: get_position_state full payload ──────────────────────────────────

def test_position_state_full_payload(mock_mt5, mock_cfg):
    from mcp_tools.handlers.position import handle_get_position_state
    out = handle_get_position_state(
        {"position_id": 123}, mock_mt5, mock_cfg,
    )
    assert out["position_id"] == 123
    assert out["symbol"] == "EURUSD"
    assert out["direction"] == "BUY"
    assert "pnl_pips" in out
    assert "pnl_money" in out
    assert "distance_to_sl_pips" in out
    assert "distance_to_tp_pips" in out
    assert "holding_minutes" in out
    assert "mfe_pips" in out
    # BUY entry=1.10, current=bid=1.1010 → pnl_pips = (1.1010-1.10)/0.0001 = 10
    assert abs(out["pnl_pips"] - 10.0) < 0.01
