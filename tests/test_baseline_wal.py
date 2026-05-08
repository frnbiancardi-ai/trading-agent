"""Tests for backtest.baseline.wal_setup (D-16 SQLite WAL + retry).

Wave 0 stub: scaffolding test-first. Sblocco al Plan 05-03 (wal_setup module).
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 1: 05-03 implementa wal_setup.enable_sqlite_wal")
def test_wal_pragma_enabled(tmp_db_with_wal) -> None:
    """D-16: `PRAGMA journal_mode` su DB inizializzato ritorna 'wal'."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-03 implementa wal_setup.enable_sqlite_wal")
def test_wal_concurrent_writes(tmp_db_with_wal) -> None:
    """D-16: 3 multiprocessing.Process insert N rows ognuno → final count == 3*N, no OperationalError."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-03 implementa wal_setup.with_retry")
def test_with_retry_on_locked() -> None:
    """D-16: mock sqlite3.OperationalError('database is locked') → retry decorator succeeds."""
    raise NotImplementedError
