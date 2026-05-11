"""Job queue async per backtest control plane (Phase 6 D-A1, D-A3, D-A4).

Architettura:
- ProcessPoolExecutor(max_workers=cfg.MCP_MAX_CONCURRENT_RUNS) per evitare GIL.
- Registro in-memory `dict[run_id, JobRecord]` per status fast-path.
- Fallback DB (logs/trades.db backtest_runs.status) per recovery post-restart.
- Worker NON importa MetaTrader5 (Phase 5 D-15 carry-forward: MT5 lib non fork-safe).
- Worker NON scrive su stdout (Pitfall 8 RESEARCH §Pitfalls: corromperebbe MCP JSON-RPC framing).

Cancel semantics su Windows / Linux:
- Future.cancel() funziona solo pre-execution.
- Mid-execution → pool.shutdown(wait=False, cancel_futures=True) + ricreazione pool.
- Possibile zombie window di ~1s post-cancel (Pitfall 6).

Schema DB additivo (D-A1):
- `backtest_runs.status` (Wave 0 06-01 migration, default 'running')
- `backtest_runs.error_message` (Wave 2 migration idempotente in _ensure_error_column,
  popolata da _on_done quando worker solleva eccezione).
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable


def _utcnow_iso() -> str:
    """ISO8601 UTC con precisione al secondo."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class JobRecord:
    """Record in-memory di un job sottomesso.

    `status` segue il ciclo di vita D-A3: running → done | failed | cancelled.
    `metadata` contiene i kwargs persistiti al primo INSERT (symbol/tf/...).
    """
    run_id: str
    future: Future
    started_at: str
    status: str           # "running" | "done" | "failed" | "cancelled"
    metadata: dict        # symbol/timeframe/date_start/date_end/profile per insert


class JobQueue:
    """Registry async dei backtest in-flight + fallback DB per status persistente."""

    def __init__(self, max_workers: int, db_path: str):
        self._pool = ProcessPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._max = max_workers
        self._db = db_path
        self._ensure_error_column()

    def _ensure_error_column(self) -> None:
        """Idempotente: aggiunge backtest_runs.error_message se manca (D-A3 failed status).

        Usa lo stesso pattern di mcp/ledger _migrate_status_column (Wave 0 06-01).
        SQLite ADD COLUMN richiede DEFAULT NULL — backward-compat con righe esistenti.
        """
        with sqlite3.connect(self._db) as c:
            c.execute("PRAGMA journal_mode=WAL")
            cols = {r[1] for r in c.execute("PRAGMA table_info(backtest_runs)")}
            if "error_message" not in cols:
                c.execute(
                    "ALTER TABLE backtest_runs ADD COLUMN error_message TEXT"
                )

    # ── Submit / Status / Cancel ────────────────────────────────────────────────

    def submit(
        self,
        run_id: str,
        fn: Callable,
        metadata: dict,
        *args,
        **kwargs,
    ) -> dict:
        """Submette un job al pool (D-A1).

        Args:
            run_id: Identificativo univoco mcp_<utc_ts>_<symbol>_<tf>_<profile>.
            fn: Funzione TOP-LEVEL picklable (worker process).
            metadata: dict con chiavi {symbol, timeframe, date_start, date_end,
                profile, cost_yaml_hash?, n_folds?, fold_mode?, train_ratio?}.
            *args, **kwargs: Forwardati al worker fn.

        Returns:
            {ok: True, run_id, status: "started", started_at: <ISO>} on success.
            {ok: False, error: "run_in_progress", active_run_id} on cap hit (D-A4).
        """
        with self._lock:
            active = [j for j in self._jobs.values() if j.status == "running"]
            if len(active) >= self._max:
                return {
                    "ok": False,
                    "error": "run_in_progress",
                    "active_run_id": active[0].run_id,
                }
            fut = self._pool.submit(fn, *args, **kwargs)
            rec = JobRecord(
                run_id=run_id,
                future=fut,
                started_at=_utcnow_iso(),
                status="running",
                metadata=metadata,
            )
            self._jobs[run_id] = rec
            self._insert_run_row(run_id, metadata, started_at=rec.started_at)
        fut.add_done_callback(lambda f: self._on_done(run_id, f))
        return {
            "ok": True,
            "run_id": run_id,
            "status": "started",
            "started_at": rec.started_at,
        }

    def status(self, run_id: str) -> dict:
        """Status polymorphic per `run_id` (D-A3).

        - In-memory record `running`: legge progress da DB e ritorna shape running.
        - In-memory record terminale: rilegge riga DB e converte a payload typed.
        - Fuori memoria: fallback DB (post-restart) — `running_ghost` se status='running'.
        - Nessuna riga: error envelope `unknown_run_id`.
        """
        rec = self._jobs.get(run_id)
        if rec is None:
            row = self._load_run_row(run_id)
            if row is None:
                return {
                    "ok": False,
                    "error": "unknown_run_id",
                    "run_id": run_id,
                }
            return self._row_to_status(row)
        if rec.status == "running":
            progress = self._read_progress_from_db(run_id)
            return {
                "run_id": run_id,
                "status": "running",
                "started_at": rec.started_at,
                **progress,
            }
        # Stato terminale: rilegge DB per metrics aggiornati
        return self._row_to_status(self._load_run_row(run_id))

    def cancel(self, run_id: str) -> dict:
        """Cancella un run attivo (D-A4 derivato).

        - Future.cancel(): True solo se job NON è ancora partito (raro col pool=1).
        - Mid-execution: shutdown pool + ricreazione (Pitfall 6).
        - Aggiorna backtest_runs.status='cancelled' + finished_at.
        """
        rec = self._jobs.get(run_id)
        if rec is None or rec.status != "running":
            return {
                "ok": False,
                "error": "no_active_run",
                "run_id": run_id,
            }
        cancelled = rec.future.cancel()
        if not cancelled:
            # Mid-execution: kill pool + ricrea (Pitfall 6, possibile zombie ~1s).
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = ProcessPoolExecutor(max_workers=self._max)
        rec.status = "cancelled"
        self._update_run_row(
            run_id, status="cancelled", finished_at=_utcnow_iso(),
        )
        return {
            "ok": True,
            "run_id": run_id,
            "status": "cancelled",
        }

    # ── DB helpers ──────────────────────────────────────────────────────────────

    def _insert_run_row(
        self, run_id: str, metadata: dict, started_at: str,
    ) -> None:
        """INSERT iniziale su backtest_runs (status='running').

        INSERT OR REPLACE per idempotenza: rerun stesso run_id riusa la riga.
        """
        with sqlite3.connect(self._db) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""
                INSERT OR REPLACE INTO backtest_runs (
                    run_id, symbol, timeframe, date_start, date_end,
                    cost_yaml_hash, profile, n_folds, fold_mode, train_ratio,
                    started_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running')
            """, (
                run_id,
                metadata.get("symbol", ""),
                metadata.get("timeframe", ""),
                metadata.get("date_start", ""),
                metadata.get("date_end", ""),
                metadata.get("cost_yaml_hash"),
                metadata.get("profile"),
                metadata.get("n_folds"),
                metadata.get("fold_mode"),
                metadata.get("train_ratio"),
                started_at,
            ))

    def _update_run_row(self, run_id: str, **fields) -> None:
        """UPDATE backtest_runs SET <fields> WHERE run_id=?."""
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [run_id]
        with sqlite3.connect(self._db) as c:
            c.execute("PRAGMA journal_mode=WAL")
            # NB: f-string sicura — i nomi colonna provengono da **fields chiavi
            # controllate dallo stesso modulo, non da input utente (T-6-03-08).
            c.execute(
                f"UPDATE backtest_runs SET {cols} WHERE run_id=?",  # noqa: S608
                vals,
            )

    def _load_run_row(self, run_id: str) -> dict | None:
        with sqlite3.connect(self._db) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.row_factory = sqlite3.Row
            cur = c.execute(
                "SELECT * FROM backtest_runs WHERE run_id=?", (run_id,),
            )
            r = cur.fetchone()
        return dict(r) if r else None

    def _read_progress_from_db(self, run_id: str) -> dict:
        """Wave 2 minimo: trades_so_far via COUNT(*) su backtest_trades.

        Wave 2 stub: bars_processed/bars_total/progress_pct restano 0/0/0.0;
        future plan aggiungeranno colonne dedicate al progress (es. bars_processed,
        bars_total) sul backtest_runs row, popolate dal worker periodicamente.
        """
        with sqlite3.connect(self._db) as c:
            cur = c.execute(
                "SELECT COUNT(*) FROM backtest_trades WHERE run_id=?", (run_id,),
            )
            trades_count = cur.fetchone()[0]
        return {
            "progress_pct": 0.0,
            "bars_processed": 0,
            "bars_total": 0,
            "trades_so_far": int(trades_count),
        }

    def _row_to_status(self, row: dict | None) -> dict:
        """Converte una riga backtest_runs in payload D-A3 polymorphic."""
        if row is None:
            return {"ok": False, "error": "unknown_run_id"}
        st = row.get("status", "running")
        run_id = row["run_id"]
        if st == "done":
            return {
                "run_id": run_id,
                "status": "done",
                "started_at": row.get("started_at"),
                "finished_at": row.get("finished_at"),
                "_db_row": row,   # consumer interpreta metrics dalle colonne
            }
        if st == "failed":
            return {
                "run_id": run_id,
                "status": "failed",
                "error_message": row.get("error_message"),
                "started_at": row.get("started_at"),
                "failed_at": row.get("finished_at"),
            }
        if st == "cancelled":
            return {
                "run_id": run_id,
                "status": "cancelled",
                "started_at": row.get("started_at"),
                "cancelled_at": row.get("finished_at"),
            }
        # status='running' su DB ma non in memory → ghost run (post-restart agent).
        return {
            "run_id": run_id,
            "status": "running_ghost",
            "started_at": row.get("started_at"),
            "note": (
                "Run marcato running su DB ma worker non in memoria — "
                "agent restart probabile (Wave 2 stub: nessun resume)."
            ),
        }

    def _on_done(self, run_id: str, fut: Future) -> None:
        """Callback completion: aggiorna backtest_runs.status + error_message."""
        rec = self._jobs.get(run_id)
        if rec is None:
            return
        if rec.status == "cancelled":
            # cancel() ha già aggiornato DB; il future può finire da solo (Pitfall 6
            # zombie window) ma noi non sovrascriviamo lo stato cancelled.
            return
        try:
            fut.result()  # solleva eccezione del worker se ce n'è
            rec.status = "done"
            self._update_run_row(
                run_id, status="done", finished_at=_utcnow_iso(),
            )
        except Exception as exc:  # noqa: BLE001 — catch-all per cattura errori worker
            rec.status = "failed"
            self._update_run_row(
                run_id,
                status="failed",
                finished_at=_utcnow_iso(),
                error_message=str(exc),
            )
