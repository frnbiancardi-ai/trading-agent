"""SQLite ledger writer for backtest_runs / backtest_trades (D-07).

Schema is additive: existing logs/trades.db tables (trades_log, daily_run_state,
heartbeat, scheduler_state) are NOT touched. CREATE TABLE IF NOT EXISTS gates
all DDL. All inserts are parameterized (T-SQLI mitigation per Plan 05 threat
model). Trade rows are batched into a single executemany transaction (Pitfall 4).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

# ── DDL ────────────────────────────────────────────────────────────────────────
# Verbatim from RESEARCH §Trade Ledger Schema. Order of columns in
# _BT_TRADES_COLUMNS MUST match _DDL_BACKTEST_TRADES.

_DDL_BACKTEST_RUNS = """
CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id      TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    date_start  TEXT NOT NULL,
    date_end    TEXT NOT NULL,
    cost_yaml_hash TEXT,
    profile     TEXT,
    n_folds     INTEGER,
    fold_mode   TEXT,
    train_ratio INTEGER,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    total_trades INTEGER,
    sharpe      REAL,
    sortino     REAL,
    max_dd_pct  REAL,
    hit_rate    REAL,
    expectancy_usd REAL,
    profit_factor REAL,
    avg_r       REAL,
    total_pnl_usd REAL,
    -- Phase 5 additions (D-17 audit trail) — additive, backwards-compat:
    slippage_seed_effective INTEGER,
    strategy_yaml_hash TEXT,
    baseline_yaml_hash TEXT,
    git_sha TEXT,
    -- Phase 5 sha256 full-64 (Warning 12 fix — coexist con legacy cost_yaml_hash md5[:16]):
    cost_yaml_sha256 TEXT,
    strategy_yaml_sha256 TEXT,
    baseline_yaml_sha256 TEXT
)
"""

_DDL_BACKTEST_TRADES = """
CREATE TABLE IF NOT EXISTS backtest_trades (
    trade_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES backtest_runs(run_id),
    fold_index   INTEGER,
    entry_time   TEXT NOT NULL,
    exit_time    TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    timeframe    TEXT NOT NULL,
    direction    TEXT NOT NULL,
    entry_price  REAL NOT NULL,
    exit_price   REAL NOT NULL,
    sl           REAL,
    tp           REAL,
    lot_size     REAL NOT NULL,
    pnl_pips     REAL,
    pnl_usd      REAL,
    risk_usd     REAL,
    exit_reason  TEXT,
    setup_type   TEXT,
    confidence   REAL,
    decision_context_json TEXT
)
"""

_DDL_IDX_RUN = (
    "CREATE INDEX IF NOT EXISTS idx_bt_trades_run "
    "ON backtest_trades(run_id, fold_index)"
)
_DDL_IDX_TIME = (
    "CREATE INDEX IF NOT EXISTS idx_bt_trades_time "
    "ON backtest_trades(symbol, timeframe, entry_time)"
)

# Column order MUST match the DDL above for the executemany row tuples.
_BT_RUNS_COLUMNS: tuple[str, ...] = (
    "run_id", "symbol", "timeframe", "date_start", "date_end",
    "cost_yaml_hash", "profile", "n_folds", "fold_mode", "train_ratio",
    "started_at", "finished_at", "total_trades", "sharpe", "sortino",
    "max_dd_pct", "hit_rate", "expectancy_usd", "profit_factor", "avg_r",
    "total_pnl_usd",
    # Phase 5 additions (D-17 audit trail) — additive, backwards-compat:
    "slippage_seed_effective", "strategy_yaml_hash", "baseline_yaml_hash", "git_sha",
    # Phase 5 sha256 full-64 (Warning 12 fix — coexist con legacy cost_yaml_hash md5[:16]):
    "cost_yaml_sha256", "strategy_yaml_sha256", "baseline_yaml_sha256",
)

_BT_TRADES_COLUMNS: tuple[str, ...] = (
    "run_id", "fold_index", "entry_time", "exit_time", "symbol", "timeframe",
    "direction", "entry_price", "exit_price", "sl", "tp", "lot_size",
    "pnl_pips", "pnl_usd", "risk_usd", "exit_reason", "setup_type",
    "confidence", "decision_context_json",
)


def _placeholders(n: int) -> str:
    return ",".join(["?"] * n)


def _migrate_backtest_runs(conn: sqlite3.Connection) -> None:
    """Additive migration: ALTER TABLE ADD COLUMN se mancante (Phase 5).

    SQLite ADD COLUMN richiede DEFAULT NULL — backwards-compatible con righe
    esistenti. Idempotente: ri-eseguire non duplica colonne. Le 7 colonne sono:
      - slippage_seed_effective, strategy_yaml_hash, baseline_yaml_hash, git_sha
        (D-17 audit trail originale)
      - cost_yaml_sha256, strategy_yaml_sha256, baseline_yaml_sha256
        (Warning 12 fix: full-64 sha256, coesistono con legacy cost_yaml_hash md5[:16])
    """
    existing = {r[1] for r in conn.execute("PRAGMA table_info(backtest_runs)")}
    additions = [
        ("slippage_seed_effective", "INTEGER"),
        ("strategy_yaml_hash", "TEXT"),
        ("baseline_yaml_hash", "TEXT"),
        ("git_sha", "TEXT"),
        # Warning 12 fix: full-64 sha256 columns
        ("cost_yaml_sha256", "TEXT"),
        ("strategy_yaml_sha256", "TEXT"),
        ("baseline_yaml_sha256", "TEXT"),
    ]
    for col, typ in additions:
        if col not in existing:
            # NB: f-string sicura — col/typ sono costanti hard-coded sopra, no SQLI vector
            # (vedi threat model T-05-03 in 05-01-PLAN.md).
            conn.execute(f"ALTER TABLE backtest_runs ADD COLUMN {col} {typ}")


_INSERT_RUN_SQL = (
    "INSERT OR REPLACE INTO backtest_runs ("
    + ",".join(_BT_RUNS_COLUMNS)
    + ") VALUES ("
    + _placeholders(len(_BT_RUNS_COLUMNS))
    + ")"
)

_INSERT_TRADE_SQL = (
    "INSERT INTO backtest_trades ("
    + ",".join(_BT_TRADES_COLUMNS)
    + ") VALUES ("
    + _placeholders(len(_BT_TRADES_COLUMNS))
    + ")"
)


class LedgerWriter:
    """Persists backtest_runs (single row per run) and backtest_trades (batch).

    All queries are parameterized; never f-string SQL values. Schema is created
    on __init__ via CREATE TABLE IF NOT EXISTS so re-instantiation is safe.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_DDL_BACKTEST_RUNS)
            # Phase 5 migration: additive ALTER TABLE per DB pre-esistenti
            # (CREATE TABLE IF NOT EXISTS non aggiunge colonne a tabelle già create).
            _migrate_backtest_runs(conn)
            conn.execute(_DDL_BACKTEST_TRADES)
            conn.execute(_DDL_IDX_RUN)
            conn.execute(_DDL_IDX_TIME)
            conn.commit()

    def record_run(self, run_meta: dict[str, Any]) -> None:
        """Insert or replace a backtest_runs row (idempotent on run_id)."""
        row = tuple(run_meta.get(col) for col in _BT_RUNS_COLUMNS)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_INSERT_RUN_SQL, row)
            conn.commit()

    def insert_trades(
        self,
        run_id: str,
        fold_index: int | None,
        trades: list[dict[str, Any]],
    ) -> None:
        """Batch INSERT closed-trade rows. Single transaction for performance.

        Each trade dict's `decision_context_json` may be a dict (json.dumps'd
        here) or already a str (passed through). Missing keys default to None.
        """
        if not trades:
            return

        rows: list[tuple] = []
        for trade in trades:
            ctx = trade.get("decision_context_json")
            if isinstance(ctx, (dict, list)):
                ctx = json.dumps(ctx, default=str)
            enriched = {**trade, "run_id": run_id, "fold_index": fold_index,
                        "decision_context_json": ctx}
            rows.append(tuple(enriched.get(col) for col in _BT_TRADES_COLUMNS))

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(_INSERT_TRADE_SQL, rows)
            conn.commit()
