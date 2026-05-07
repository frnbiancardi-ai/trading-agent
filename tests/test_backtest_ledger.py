"""Tests for backtest.ledger SQLite schema + insert pipeline (D-07)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backtest.ledger import LedgerWriter


def _full_run_meta(run_id: str = "test-run-1", symbol: str = "EURUSD") -> dict:
    return {
        "run_id": run_id, "symbol": symbol, "timeframe": "H1",
        "date_start": "2024-01-01T00:00:00", "date_end": "2024-02-01T00:00:00",
        "cost_yaml_hash": "abcd1234", "profile": "MODERATE",
        "n_folds": 1, "fold_mode": "rolling", "train_ratio": 4,
        "started_at": "2024-01-01T00:00:00", "finished_at": "2024-01-01T00:01:00",
        "total_trades": 5, "sharpe": 1.5, "sortino": 2.0, "max_dd_pct": 5.0,
        "hit_rate": 0.6, "expectancy_usd": 12.5, "profit_factor": 2.1,
        "avg_r": 1.1, "total_pnl_usd": 62.5,
    }


def test_schema_created(tmp_path: Path) -> None:
    db = tmp_path / "trades.db"
    LedgerWriter(db)  # ensure_schema runs in __init__
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        indexes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_bt_%'"
        )}
    assert {"backtest_runs", "backtest_trades"}.issubset(tables)
    assert {"idx_bt_trades_run", "idx_bt_trades_time"} == indexes


def test_record_run_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "trades.db"
    lw = LedgerWriter(db)
    meta = _full_run_meta()
    lw.record_run(meta)
    # Re-record with new total_pnl
    meta["total_pnl_usd"] = 99.99
    lw.record_run(meta)
    with sqlite3.connect(db) as conn:
        rows = list(conn.execute(
            "SELECT total_pnl_usd FROM backtest_runs WHERE run_id=?",
            ("test-run-1",),
        ))
    assert len(rows) == 1
    assert abs(rows[0][0] - 99.99) < 1e-9


def test_insert_trades_batch(tmp_path: Path) -> None:
    db = tmp_path / "trades.db"
    lw = LedgerWriter(db)
    lw.record_run(_full_run_meta(run_id="r1"))
    trades = [
        {
            "entry_time": "2024-01-01T00:00:00", "exit_time": "2024-01-01T01:00:00",
            "symbol": "EURUSD", "timeframe": "H1", "direction": "BUY",
            "entry_price": 1.10, "exit_price": 1.11, "sl": 1.09, "tp": 1.12,
            "lot_size": 0.1, "pnl_pips": 100.0, "pnl_usd": 100.0,
            "risk_usd": 100.0, "exit_reason": "TP",
            "setup_type": "READY", "confidence": 0.7,
            "decision_context_json": json.dumps({"sma20": 1.099}),
        }
        for _ in range(50)
    ]
    lw.insert_trades("r1", 0, trades)
    with sqlite3.connect(db) as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM backtest_trades WHERE run_id=?", ("r1",)
        ).fetchone()
        # Round-trip on first row
        row = conn.execute(
            "SELECT symbol, pnl_usd, decision_context_json FROM backtest_trades "
            "WHERE run_id=? LIMIT 1",
            ("r1",),
        ).fetchone()
    assert count == 50
    assert row[0] == "EURUSD"
    assert abs(row[1] - 100.0) < 1e-9
    assert json.loads(row[2])["sma20"] == 1.099


def test_insert_trades_accepts_dict_context(tmp_path: Path) -> None:
    """LedgerWriter must json.dumps a dict context if provided unserialized."""
    db = tmp_path / "trades.db"
    lw = LedgerWriter(db)
    lw.record_run(_full_run_meta(run_id="r2"))
    trades = [{
        "entry_time": "2024-01-01T00:00:00", "exit_time": "2024-01-01T01:00:00",
        "symbol": "EURUSD", "timeframe": "H1", "direction": "BUY",
        "entry_price": 1.10, "exit_price": 1.11, "sl": 1.09, "tp": 1.12,
        "lot_size": 0.1, "pnl_pips": 100.0, "pnl_usd": 100.0,
        "risk_usd": 100.0, "exit_reason": "TP",
        "setup_type": "READY", "confidence": 0.7,
        "decision_context_json": {"sma20": 1.099},  # raw dict, not JSON string
    }]
    lw.insert_trades("r2", 0, trades)
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT decision_context_json FROM backtest_trades WHERE run_id=?",
            ("r2",),
        ).fetchone()
    assert json.loads(row[0])["sma20"] == 1.099


def test_sql_injection_param_safety(tmp_path: Path) -> None:
    """Symbol names with SQL fragments must NOT execute as SQL (T-SQLI mitigation)."""
    db = tmp_path / "trades.db"
    lw = LedgerWriter(db)
    meta = _full_run_meta(run_id="rx", symbol="EURUSD'; DROP TABLE backtest_trades; --")
    lw.record_run(meta)
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        # The injected string was stored verbatim, table NOT dropped
        (sym,) = conn.execute(
            "SELECT symbol FROM backtest_runs WHERE run_id=?", ("rx",)
        ).fetchone()
    assert "backtest_trades" in tables
    assert sym == "EURUSD'; DROP TABLE backtest_trades; --"
