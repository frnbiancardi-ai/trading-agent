"""Tests for backtest.baseline.wal_setup (D-16).

Wave 1 (Plan 05-03): WAL pragma + busy_timeout + retry-with-jitter su SQLITE_BUSY.
Concurrency test usa multiprocessing.Process (Windows spawn ctx) — pickle-safe top-level helper.
"""
from __future__ import annotations

import multiprocessing as mp
import sqlite3
from pathlib import Path

import pytest

from backtest.baseline.wal_setup import (
    enable_sqlite_wal,
    open_worker_connection,
    with_retry,
)


def test_wal_pragma_enabled(tmp_db_with_wal: Path) -> None:
    """D-16: PRAGMA journal_mode == 'wal' (persistente DB-wide) + busy_timeout >= 30000ms.

    NB: journal_mode è persistente cross-connection (WAL header nel file SQLite),
    busy_timeout è per-connection → verifica via open_worker_connection (helper Phase 5
    che applica entrambe le PRAGMA su ogni connection nuova).
    """
    # journal_mode persiste — leggibile da connection vanilla
    with sqlite3.connect(tmp_db_with_wal) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"

    # busy_timeout è per-connection → verifica via worker helper
    worker_conn = open_worker_connection(tmp_db_with_wal)
    try:
        timeout = worker_conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        worker_conn.close()
    assert timeout >= 30000


def _worker_insert(db_path: str, n_rows: int) -> None:
    """Top-level helper per multiprocessing spawn (Windows non picklerizza closures).

    Helper esplicito per evitare lambda con `expr and conn.commit()` (truthiness bug —
    Cursor.execute ritorna oggetto truthy ma semantica non documentata).
    """
    from backtest.baseline.wal_setup import open_worker_connection, with_retry

    conn = open_worker_connection(Path(db_path))
    try:
        for i in range(n_rows):
            def _do_insert(_conn=conn, _i=i):
                _conn.execute("INSERT INTO t(v) VALUES(?)", (_i,))
                _conn.commit()
            with_retry(_do_insert)
    finally:
        conn.close()


def test_wal_concurrent_writes(tmp_path: Path) -> None:
    """D-16: 3 mp.Process worker × 50 INSERT each → final count == 150, no OperationalError."""
    db = tmp_path / "trades.db"
    enable_sqlite_wal(db)
    # Init schema dal main per evitare race su CREATE
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v INTEGER)")
        conn.commit()
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=_worker_insert, args=(str(db), 50)) for _ in range(3)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert p.exitcode == 0, f"worker failed exit={p.exitcode}"
    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT count(*) FROM t").fetchone()[0]
    assert count == 150  # 3 worker × 50 row


def test_with_retry_on_locked() -> None:
    """D-16: fn fallisce 2× con 'database is locked' poi succede → with_retry ritorna ok."""
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    result = with_retry(fn, n=5, base_delay=0.001)
    assert result == "ok"
    assert attempts["n"] == 3


def test_with_retry_propagates_non_lock() -> None:
    """D-16: OperationalError non-lock (es. syntax error) propagato immediatamente, no retry."""
    def fn():
        raise sqlite3.OperationalError("syntax error near 'foo'")

    with pytest.raises(sqlite3.OperationalError, match="syntax"):
        with_retry(fn, n=5, base_delay=0.001)


def test_with_retry_max_attempts() -> None:
    """D-16: fn sempre 'locked' → with_retry(n=3) raise dopo 3 tentativi."""
    def fn():
        raise sqlite3.OperationalError("database is locked")

    with pytest.raises(sqlite3.OperationalError, match="locked"):
        with_retry(fn, n=3, base_delay=0.001)
