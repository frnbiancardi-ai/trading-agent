"""SQLite WAL setup + retry-with-jitter per 9-writer concorrenti (D-16).

Riusa pattern mt5_client._retry (lines 26-39) — decoratore generico → funzione
`with_retry(fn)` riapplicabile. Narrow exception class a sqlite3.OperationalError
"locked" per evitare retry su syntax error / corrupt DB.

Source: sqlite.org/wal.html, RESEARCH.md §Pattern 3.
"""
from __future__ import annotations

import logging
import random
import sqlite3
import time
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")
_log = logging.getLogger(__name__)


def enable_sqlite_wal(db_path: Path) -> None:
    """Una tantum dal main process. WAL mode persiste cross-connection.

    - journal_mode=WAL: N reader + 1 writer simultanei (vs default rollback journal)
    - busy_timeout=30000ms: SQLite attende lock fino a 30s prima di sollevare BUSY
    - synchronous=NORMAL: WAL-safe + ~3x faster di FULL (durabilità OS-crash invece
      di power-loss; accettabile per backtest non-prod)
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.commit()


def open_worker_connection(db_path: Path) -> sqlite3.Connection:
    """Per-worker connection. Ogni worker apre la propria — mai sharing cross-process."""
    conn = sqlite3.connect(db_path, timeout=30.0)  # 30s busy wait built-in
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def with_retry(fn: Callable[[], T], n: int = 5, base_delay: float = 0.05) -> T:
    """Riusa shape mt5_client._retry. Exponential backoff + jitter su SQLITE_BUSY.

    Narrow exception: solo `sqlite3.OperationalError` con messaggio contenente
    'locked'. Altri OperationalError (syntax, corrupt) propagati immediatamente.
    """
    last_exc: Exception | None = None
    for attempt in range(n):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_exc = exc
            delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
            _log.warning(
                "retry %d/%d sqlite locked: %s (sleep %.3fs)",
                attempt + 1, n, exc, delay,
            )
            time.sleep(delay)
    assert last_exc is not None  # unreachable: range(n) >= 1
    raise last_exc
