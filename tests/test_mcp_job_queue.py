"""Phase 6 Wave 2: JobQueue D-A1/A3/A4 tests.

Riferimento: 06-03-PLAN.md Task 1, RESEARCH §Pattern 2.

I test sono "RED" finché Task 1 GREEN crea mcp_tools/job_queue.py.
"""
import sqlite3
import time

import pytest
from backtest.ledger import LedgerWriter

# import lazy: il modulo non esiste ancora in fase RED.
pytest.importorskip("mcp_tools.job_queue")
from mcp_tools.job_queue import JobQueue  # noqa: E402


def _bootstrap_db(db_path) -> None:
    """Crea schema backtest_runs (LedgerWriter ensure_schema)."""
    LedgerWriter(db_path)


def _short_job(seconds: float = 0.1, fail: bool = False) -> int:
    """Worker top-level picklable per ProcessPoolExecutor."""
    import time as _t
    _t.sleep(seconds)
    if fail:
        raise RuntimeError("boom")
    return 42


def _long_job(seconds: float = 5.0) -> int:
    """Worker top-level lento, per concorrenza + cancel."""
    import time as _t
    _t.sleep(seconds)
    return 99


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "trades.db"
    _bootstrap_db(p)
    return p


def test_submit_returns_started(db):
    q = JobQueue(max_workers=1, db_path=str(db))
    meta = {"symbol": "EURUSD", "timeframe": "M15",
            "date_start": "2024-01-01", "date_end": "2024-01-02"}
    out = q.submit("mcp_t1", _short_job, meta, 0.05)
    assert out["ok"] is True
    assert out["run_id"] == "mcp_t1"
    assert out["status"] == "started"
    assert "started_at" in out
    # Attendo che il worker finisca.
    time.sleep(1.0)
    final = q.status("mcp_t1")
    assert final["status"] == "done"


def test_submit_concurrent_rejected(db):
    q = JobQueue(max_workers=1, db_path=str(db))
    meta = {"symbol": "EURUSD", "timeframe": "M15",
            "date_start": "2024-01-01", "date_end": "2024-01-02"}
    q.submit("mcp_a", _long_job, meta, 2.0)
    out2 = q.submit("mcp_b", _long_job, meta, 2.0)
    assert out2["ok"] is False
    assert out2["error"] == "run_in_progress"
    assert out2["active_run_id"] == "mcp_a"
    q.cancel("mcp_a")  # cleanup


def test_status_unknown_run_id(db):
    q = JobQueue(max_workers=1, db_path=str(db))
    out = q.status("does_not_exist")
    assert out["ok"] is False
    assert out["error"] == "unknown_run_id"


def test_status_running_done_failed_cancelled(db):
    q = JobQueue(max_workers=1, db_path=str(db))
    meta = {"symbol": "EURUSD", "timeframe": "M15",
            "date_start": "2024-01-01", "date_end": "2024-01-02"}
    # done
    q.submit("done_id", _short_job, meta, 0.05)
    time.sleep(1.0)
    assert q.status("done_id")["status"] == "done"
    # failed
    q.submit("fail_id", _short_job, meta, 0.05, True)
    time.sleep(1.0)
    fail = q.status("fail_id")
    assert fail["status"] == "failed"
    assert fail.get("error_message") and "boom" in fail["error_message"]


def test_cancel_active(db):
    q = JobQueue(max_workers=1, db_path=str(db))
    meta = {"symbol": "EURUSD", "timeframe": "M15",
            "date_start": "2024-01-01", "date_end": "2024-01-02"}
    q.submit("cancel_id", _long_job, meta, 5.0)
    time.sleep(0.1)  # lascio partire il pool
    out = q.cancel("cancel_id")
    assert out["ok"] is True
    assert out["status"] == "cancelled"
    # Verifica DB
    with sqlite3.connect(str(db)) as c:
        row = c.execute(
            "SELECT status FROM backtest_runs WHERE run_id=?",
            ("cancel_id",),
        ).fetchone()
    assert row[0] == "cancelled"


def test_cancel_no_active(db):
    q = JobQueue(max_workers=1, db_path=str(db))
    out = q.cancel("does_not_exist")
    assert out["ok"] is False
    assert out["error"] == "no_active_run"
