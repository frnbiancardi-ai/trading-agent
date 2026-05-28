"""Phase 6 Wave 3 (Plan 06-04): trail_daemon D-B2 tests.

Test reali per modulo `mcp_tools.trail_daemon` (sostituiscono gli stub xfail Wave 0).
Riferimento: 06-04-PLAN.md Task 1 + 06-CONTEXT D-B2 + 06-RESEARCH §Pattern 6 + Pitfall 2.
"""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """Crea un DB SQLite vuoto + applica position_trails DDL idempotente."""
    from mcp_tools.trail_daemon import ensure_table
    db = tmp_path / "trades.db"
    ensure_table(db)
    return db


# ── Test 1: ensure_table crea schema ──────────────────────────────────────────

def test_ensure_table_creates_schema(tmp_db):
    """ensure_table installa position_trails con tutte le colonne D-B2."""
    with sqlite3.connect(str(tmp_db)) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(position_trails)")}
    expected = {
        "position_id", "symbol", "direction", "timeframe", "atr_mult",
        "last_sl", "activated_at", "last_update_at", "active",
    }
    assert expected.issubset(cols), f"Missing cols: {expected - cols}"

    # Idempotenza: seconda call no-op
    from mcp_tools.trail_daemon import ensure_table
    ensure_table(tmp_db)  # non solleva
    with sqlite3.connect(str(tmp_db)) as c:
        cols2 = {r[1] for r in c.execute("PRAGMA table_info(position_trails)")}
    assert cols == cols2


# ── Test 2: register_trail inserisce riga ────────────────────────────────────

def test_register_trail_inserts_row(tmp_db):
    from mcp_tools.trail_daemon import register_trail
    register_trail(tmp_db, 1001, "EURUSD", "BUY", "M15", 2.0, 1.10000)

    with sqlite3.connect(str(tmp_db)) as c:
        c.row_factory = sqlite3.Row
        row = dict(c.execute(
            "SELECT * FROM position_trails WHERE position_id=1001"
        ).fetchone())

    assert row["symbol"] == "EURUSD"
    assert row["direction"] == "BUY"
    assert row["timeframe"] == "M15"
    assert row["atr_mult"] == 2.0
    assert row["last_sl"] == 1.10000
    assert row["active"] == 1
    assert row["activated_at"] is not None
    assert row["last_update_at"] is None


# ── Test 3: tick disattiva se posizione chiusa ────────────────────────────────

def test_tick_position_closed_deactivates(tmp_db):
    """get_position=None → row.active=0 (posizione chiusa lato broker)."""
    from mcp_tools.trail_daemon import register_trail, trail_tick
    register_trail(tmp_db, 2001, "EURUSD", "BUY", "M15", 2.0, 1.10000)

    mt5 = MagicMock()
    mt5.get_position.return_value = None  # posizione non esiste più
    cfg = SimpleNamespace(TRAIL_FAVORABLE_ONLY=True)

    trail_tick(mt5, tmp_db, cfg)

    with sqlite3.connect(str(tmp_db)) as c:
        row = c.execute(
            "SELECT active FROM position_trails WHERE position_id=2001"
        ).fetchone()
    assert row[0] == 0
    mt5.modify_position.assert_not_called()


# ── Helper: bars sintetiche per indicators.atr ────────────────────────────────

def _build_bullish_bars(n: int = 15, base: float = 1.1000) -> list[dict]:
    """Bar sintetiche con trend up — ATR non zero."""
    out = []
    for i in range(n):
        c = base + i * 0.0001
        out.append({
            "time": 1700000000 + i * 900,
            "open": c - 0.0001,
            "high": c + 0.0005,
            "low": c - 0.0005,
            "close": c,
            "tick_volume": 100,
        })
    return out


# ── Test 4: tick favorable → modify SL + update last_sl ──────────────────────

def test_tick_favorable_modifies(tmp_db, monkeypatch):
    """BUY, candidate > last_sl → modify_position chiamato, last_sl aggiornato."""
    from mcp_tools.trail_daemon import register_trail, trail_tick
    register_trail(tmp_db, 3001, "EURUSD", "BUY", "M15", 1.5, 1.0950)

    mt5 = MagicMock()
    mt5.get_position.return_value = SimpleNamespace(
        symbol="EURUSD", lots=0.1, direction="BUY",
        entry_price=1.10, stop_loss=1.0950, take_profit=1.11,
        profit=10.0, ticket=3001,
    )
    mt5.get_ohlc.return_value = _build_bullish_bars()
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.1100, ask=1.1101, point=0.00001, trade_stops_level=10,
    )
    mt5.modify_position.return_value = SimpleNamespace(
        success=True, error_message=None, order_id=99,
    )

    # Stub compute_atr → 0.001 (price units). candidate = 1.1100 - 0.001*1.5 = 1.1085
    monkeypatch.setattr(
        "mcp_tools.trail_daemon.compute_atr",
        lambda bars, period=14: 0.001,
    )
    cfg = SimpleNamespace(TRAIL_FAVORABLE_ONLY=True)

    trail_tick(mt5, tmp_db, cfg)

    mt5.modify_position.assert_called_once()
    call = mt5.modify_position.call_args
    # Position id arg 0
    assert call[0][0] == 3001
    new_sl = call[1]["sl"]
    assert new_sl > 1.0950
    assert abs(new_sl - 1.1085) < 1e-5, f"expected 1.1085, got {new_sl}"

    # last_sl persistito
    with sqlite3.connect(str(tmp_db)) as c:
        row = c.execute(
            "SELECT last_sl, last_update_at FROM position_trails "
            "WHERE position_id=3001"
        ).fetchone()
    assert row[0] > 1.0950
    assert row[1] is not None  # last_update_at popolato


# ── Test 5: tick non favorable → skip ─────────────────────────────────────────

def test_tick_non_favorable_skip(tmp_db, monkeypatch):
    """BUY, candidate <= last_sl → TRAIL_FAVORABLE_ONLY skip; nessuna modify."""
    from mcp_tools.trail_daemon import register_trail, trail_tick
    # last_sl alto → candidate (price_current - atr*mult) sarà < last_sl
    register_trail(tmp_db, 4001, "EURUSD", "BUY", "M15", 1.5, 1.1095)

    mt5 = MagicMock()
    mt5.get_position.return_value = SimpleNamespace(
        symbol="EURUSD", lots=0.1, direction="BUY",
        entry_price=1.10, stop_loss=1.1095, take_profit=1.12,
        profit=10.0, ticket=4001,
    )
    mt5.get_ohlc.return_value = _build_bullish_bars()
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.1100, ask=1.1101, point=0.00001, trade_stops_level=10,
    )
    monkeypatch.setattr(
        "mcp_tools.trail_daemon.compute_atr",
        lambda bars, period=14: 0.001,
    )
    cfg = SimpleNamespace(TRAIL_FAVORABLE_ONLY=True)

    trail_tick(mt5, tmp_db, cfg)

    mt5.modify_position.assert_not_called()


# ── Test 6: stops_level clamp (Pitfall 2) ─────────────────────────────────────

def test_tick_stops_level_clamp(tmp_db, monkeypatch):
    """Candidate troppo vicino al price → clamp a boundary broker."""
    from mcp_tools.trail_daemon import register_trail, trail_tick
    register_trail(tmp_db, 5001, "EURUSD", "BUY", "M15", 0.1, 1.0000)

    mt5 = MagicMock()
    mt5.get_position.return_value = SimpleNamespace(
        symbol="EURUSD", lots=0.1, direction="BUY",
        entry_price=1.10, stop_loss=1.0, take_profit=1.11,
        profit=0.0, ticket=5001,
    )
    mt5.get_ohlc.return_value = _build_bullish_bars()
    # stops_level = 100 points * 0.00001 = 0.001 price units → min distance da price
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.1100, ask=1.1101, point=0.00001, trade_stops_level=100,
    )
    mt5.modify_position.return_value = SimpleNamespace(
        success=True, error_message=None, order_id=99,
    )
    # atr * mult = 0.001 * 0.1 = 0.0001 → candidate raw = 1.1100 - 0.0001 = 1.1099
    # stops boundary BUY: max_sl = 1.1100 - 0.001 = 1.1090
    # candidate (1.1099) > max_sl (1.1090) → clamp a 1.1090
    monkeypatch.setattr(
        "mcp_tools.trail_daemon.compute_atr",
        lambda bars, period=14: 0.001,
    )
    cfg = SimpleNamespace(TRAIL_FAVORABLE_ONLY=True)

    trail_tick(mt5, tmp_db, cfg)

    mt5.modify_position.assert_called_once()
    call_sl = mt5.modify_position.call_args[1]["sl"]
    assert abs(call_sl - 1.1090) < 1e-6, (
        f"expected clamp to 1.1090, got {call_sl}"
    )
