"""Phase 6 Wave 2: backtest handler tests (MCP-01/02/03 + cancel D-A4).

Riferimento: 06-03-PLAN.md Task 2.

I 3 test replay_decision restano xfail (Wave 4 li chiude).
"""
from __future__ import annotations

import sqlite3
import time

import pytest
from backtest.ledger import LedgerWriter
from unittest.mock import MagicMock


# Import lazy: il modulo non esiste finché Task 2 GREEN non lo crea.
pytest.importorskip("mcp_tools.handlers.backtest")
from mcp_tools.handlers.backtest import (  # noqa: E402
    handle_cancel_backtest,
    handle_get_backtest_metrics,
    handle_run_backtest,
    handle_walk_forward_validate,
)
from mcp_tools.job_queue import JobQueue  # noqa: E402


# ── Worker stub TOP-LEVEL per picklability ProcessPoolExecutor ──────────────────

def _fast_worker(run_id, *args, **kwargs):
    """Worker stub veloce: scrive una riga finalize 'done' con metrics dummy.

    args[-2] = db_path per convenzione handle_run_backtest argv.
    """
    db_path = args[-2]
    writer = LedgerWriter(db_path)
    writer.finalize_run(
        run_id, status="done",
        sharpe=1.5, sortino=2.0,
        max_dd_pct=5.0, hit_rate=0.55,
        expectancy_usd=10.0, profit_factor=1.3,
        avg_r=0.8, total_trades=42,
    )
    return {"run_id": run_id, "trades": 42}


def _slow_worker(*args, **kwargs):
    """Worker lento per test cancel + concurrency cap."""
    import time as _t
    _t.sleep(5.0)
    return {}


# ── Fixture ────────────────────────────────────────────────────────────────────

@pytest.fixture
def db_and_queue(tmp_path, monkeypatch):
    """Crea DB + LedgerWriter + JobQueue. Patcha worker su _fast_worker."""
    db = tmp_path / "trades.db"
    LedgerWriter(db)
    import mcp_tools.handlers.backtest as bt_mod
    monkeypatch.setattr(bt_mod, "_backtest_worker", _fast_worker)
    monkeypatch.setattr(bt_mod, "_walk_forward_worker", _fast_worker)
    q = JobQueue(max_workers=1, db_path=str(db))
    cfg = MagicMock()
    return db, q, cfg


# ── MCP-01: run_backtest (D-A1) ─────────────────────────────────────────────────

def test_run_backtest_returns_run_id(db_and_queue):
    db, q, cfg = db_and_queue
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "date_start": "2024-01-01T00:00:00Z",
        "date_end": "2024-01-02T00:00:00Z",
        "profile": "MODERATE",
    }
    out = handle_run_backtest(
        args, q, cfg, str(db), "data/configs/costs.yaml",
    )
    assert out["ok"] is True
    assert out["run_id"].startswith("mcp_")
    assert "EURUSD" in out["run_id"]
    assert "M15" in out["run_id"]
    assert "MODERATE" in out["run_id"]
    assert out["status"] == "started"
    assert "started_at" in out


def test_run_backtest_concurrency_cap(db_and_queue, monkeypatch):
    """D-A4 cap=1: secondo submit mentre primo gira ritorna run_in_progress."""
    db, q, cfg = db_and_queue
    import mcp_tools.handlers.backtest as bt_mod
    monkeypatch.setattr(bt_mod, "_backtest_worker", _slow_worker)
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "date_start": "2024-01-01T00:00:00Z",
        "date_end": "2024-01-02T00:00:00Z",
        "profile": "MODERATE",
    }
    handle_run_backtest(args, q, cfg, str(db), "data/configs/costs.yaml")
    out2 = handle_run_backtest(args, q, cfg, str(db), "data/configs/costs.yaml")
    assert out2["ok"] is False
    assert out2["error"] == "run_in_progress"


# ── MCP-02: get_backtest_metrics (D-A3) ─────────────────────────────────────────

def test_get_metrics_polymorphic(db_and_queue):
    db, q, cfg = db_and_queue
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "date_start": "2024-01-01T00:00:00Z",
        "date_end": "2024-01-02T00:00:00Z",
        "profile": "MODERATE",
    }
    out = handle_run_backtest(
        args, q, cfg, str(db), "data/configs/costs.yaml",
    )
    run_id = out["run_id"]
    # Attendo worker
    time.sleep(1.0)
    m = handle_get_backtest_metrics({"run_id": run_id}, q, cfg)
    assert m["status"] == "done"
    assert "metrics" in m
    assert m["metrics"]["sharpe"] == 1.5
    assert m["metrics"]["trade_count"] == 42


def test_get_metrics_unknown(db_and_queue):
    db, q, cfg = db_and_queue
    out = handle_get_backtest_metrics({"run_id": "does_not_exist"}, q, cfg)
    assert out["ok"] is False
    assert out["error"] == "unknown_run_id"


# ── MCP-03: walk_forward_validate ──────────────────────────────────────────────

def test_walk_forward_3fold(db_and_queue):
    db, q, cfg = db_and_queue
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "date_start": "2024-01-01T00:00:00Z",
        "date_end": "2024-04-01T00:00:00Z",
        "profile": "MODERATE",
        "n_folds": 3,
    }
    out = handle_walk_forward_validate(
        args, q, cfg, str(db), "data/configs/costs.yaml",
    )
    assert out["ok"] is True
    assert "wfv3" in out["run_id"]
    assert out["status"] == "started"


def test_walk_forward_fold_cap(db_and_queue):
    """n_folds=11 > cap Phase 1 (10) → error envelope."""
    db, q, cfg = db_and_queue
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "date_start": "2024-01-01T00:00:00Z",
        "date_end": "2024-04-01T00:00:00Z",
        "profile": "MODERATE",
        "n_folds": 11,
    }
    out = handle_walk_forward_validate(
        args, q, cfg, str(db), "data/configs/costs.yaml",
    )
    assert out["ok"] is False
    assert out["error"] == "invalid_n_folds"


# ── cancel_backtest (D-A4) ──────────────────────────────────────────────────────

def test_cancel_unknown(db_and_queue):
    db, q, cfg = db_and_queue
    out = handle_cancel_backtest({"run_id": "does_not_exist"}, q, cfg)
    assert out["ok"] is False
    assert out["error"] == "no_active_run"


def test_cancel_active(db_and_queue, monkeypatch):
    db, q, cfg = db_and_queue
    import mcp_tools.handlers.backtest as bt_mod
    monkeypatch.setattr(bt_mod, "_backtest_worker", _slow_worker)
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "date_start": "2024-01-01T00:00:00Z",
        "date_end": "2024-01-02T00:00:00Z",
        "profile": "MODERATE",
    }
    out1 = handle_run_backtest(
        args, q, cfg, str(db), "data/configs/costs.yaml",
    )
    rid = out1["run_id"]
    time.sleep(0.1)  # lascia partire il pool
    out = handle_cancel_backtest({"run_id": rid}, q, cfg)
    assert out["ok"] is True
    assert out["status"] == "cancelled"
    with sqlite3.connect(str(db)) as c:
        row = c.execute(
            "SELECT status FROM backtest_runs WHERE run_id=?", (rid,),
        ).fetchone()
    assert row[0] == "cancelled"


# ── Wave 4 — MCP-15 replay_decision (xfail preservato) ─────────────────────────

def test_replay_decision_live():
    pytest.xfail("MISSING — Wave 4 MCP-15 D-D2")


def test_replay_decision_baseline():
    pytest.xfail("MISSING — Wave 4 MCP-15 D-D2")


def test_replay_decision_regression_flag():
    pytest.xfail("MISSING — Wave 4 MCP-15 D-D2")
