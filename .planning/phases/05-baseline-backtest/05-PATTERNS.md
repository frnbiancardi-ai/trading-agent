# Phase 5: Baseline Backtest — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 18 (5 new modules + 1 new script + 1 new YAML + 3 modified + 8 new tests)
**Analogs found:** 17 / 18 (1 file — `report_writer.py` — has no direct repo analog; structure is dictated by CONTEXT D-18 schema)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/run_baseline_backtest.py` (new) | script (CLI orchestrator) | batch / fan-out | `scripts/dry_run_cycle.py` + `backtest/engine.py::run_backtest` | role-match (script bootstrap) + role-match (orchestrator) |
| `backtest/baseline/__init__.py` (new) | package init | n/a | `backtest/__init__.py` | exact |
| `backtest/baseline/runner.py` (new) | orchestrator (`ProcessPoolExecutor` fan-out) | batch / fan-out | `backtest/engine.py::run_backtest` (single-run convenience) | role-match (no existing parallel orchestrator in repo) |
| `backtest/baseline/slice_worker.py` (new) | worker function (per-slice 3-profile loop) | sequential transform inside process | `backtest/engine.py::BacktestEngine.run` | role-match |
| `backtest/baseline/dataset_writer.py` (new) | service (parquet shard writer + finalize) | batch / file-I/O | `backtest/ledger.py::LedgerWriter.insert_trades` (batched persistence) | role-match (different store: parquet vs sqlite) |
| `backtest/baseline/plot_writer.py` (new) | utility (matplotlib PNG) | file-I/O | (no analog — first matplotlib usage in repo) | no analog |
| `backtest/baseline/report_writer.py` (new) | service (Markdown report compose) | aggregation / file-I/O | (no analog) | no analog (template from CONTEXT D-18) |
| `backtest/baseline/determinism.py` (new) | utility (sha256 hashes + seed) | pure transform | `backtest/engine.py::_hash_cost_yaml` + `backtest/engine.py::_compute_run_id` | role-match (md5 → sha256 upgrade) |
| `backtest/baseline/wal_setup.py` (new) | utility (SQLite WAL + retry) | request-response (DB) | `mt5_client.py::_retry` + `logger.py::init_logger` (PRAGMA WAL block lines 61–63) | exact (retry pattern) + exact (WAL pragma) |
| `data/configs/baseline.yaml` (new) | config (YAML) | static | `data/configs/costs.yaml` + `backtest/costs.py::load_cost_model` | exact |
| `backtest/ledger.py` (modify) | model / DDL | CRUD | self (existing schema) — extend `_DDL_BACKTEST_RUNS` + `_BT_RUNS_COLUMNS` | self-extend |
| `backtest/engine.py` (modify) | controller (engine) | event-driven loop | self — accept `indicators_full`, `risk_profile`, `timeout_bars`, `equity_initial` | self-extend |
| `backtest/metrics.py` (modify) | service (pure math) | transform | self — extend `BacktestMetrics` with `longest_dd_days` (avg_R already present line 33) | self-extend |
| `requirements.txt` (modify) | config (deps) | static | self — append `pyarrow`, `matplotlib` | n/a |
| `tests/test_baseline_runner.py` (new) | test | pytest fixture | `tests/test_backtest_engine.py` | exact |
| `tests/test_baseline_dataset_writer.py` (new) | test | pytest tmp_path | `tests/test_backtest_ledger.py` | exact |
| `tests/test_baseline_no_future_leakage.py` (new) | test | pytest invariant | `tests/test_backtest_engine.py::test_engine_5bar_fixture` (warm-up gate) | role-match |
| `tests/test_baseline_determinism.py` (new) | test | pytest | (new pattern) | role-match |
| `tests/test_baseline_wal.py` (new) | test (multi-process) | pytest | `tests/test_backtest_ledger.py` + `multiprocessing` | role-match |
| `tests/test_baseline_plot_writer.py` (new) | test | pytest tmp_path | `tests/test_backtest_*.py` (file-output assertion) | role-match |
| `tests/test_baseline_report_writer.py` (new) | test | pytest tmp_path | `tests/test_backtest_*.py` | role-match |
| `tests/conftest.py` (new) | test fixture | pytest | (new) — share `tmp_db`, `tiny_bars`, `tiny_indicators` fixtures | no analog |

---

## Pattern Assignments

### `backtest/baseline/__init__.py` (package init)

**Analog:** `C:/trading-agent/backtest/__init__.py` (verbatim 2-line template)

**Copy verbatim** (line 1-2):
```python
"""Backtest baseline subpackage: 27-run pre-ML dataset + report (Phase 5)."""
__all__ = ["run_baseline"]
```

---

### `backtest/baseline/runner.py` (orchestrator)

**Analog:** `C:/trading-agent/backtest/engine.py::run_backtest` (lines 309–342) for the "convenience function that wires everything" shape; the `ProcessPoolExecutor` topology has no in-repo analog (use stdlib `concurrent.futures` per RESEARCH §Pattern 1).

**Module docstring + imports pattern** (mirror `backtest/engine.py:1-43`):
```python
"""Phase 5 baseline orchestrator: 27 run paralleli (BACK-07, INT-01).

Hybrid orchestration D-15: ProcessPoolExecutor(9) su (symbol, tf), 3 profile
sequenziali per worker riusando indicator cache (compute_all_extended UNA volta).
Wall-clock target <30 min su 8-core dev laptop (SC#1).
"""
from __future__ import annotations

import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from pathlib import Path

from tqdm import tqdm

from backtest.baseline.slice_worker import run_slice_3profiles
from backtest.baseline.wal_setup import enable_sqlite_wal
from backtest.baseline.dataset_writer import finalize_parquet_shards
from backtest.baseline.report_writer import write_baseline_report

_log = logging.getLogger(__name__)
```

**Error handling pattern** (drop-in from `scheduler.run_forever` philosophy: never crash on per-slice failure):
```python
# All'interno del for-as_completed loop:
try:
    all_results.extend(fut.result())
except Exception as exc:
    slice_id = futures[fut]
    _log.error("slice %s fallita: %s", slice_id, exc, exc_info=True)
    all_results.append({"slice_id": slice_id, "status": "FAILED", "error": str(exc)})
```

**Italiano log format** (analog `risk_engine.py:45`, `mt5_client.py:36`): `_log.warning("skip %s: già esistente, usa --force", run_id)` — `%`-style lazy interpolation.

---

### `backtest/baseline/slice_worker.py` (worker)

**Analog:** `C:/trading-agent/backtest/engine.py::BacktestEngine` (lines 76–247) — same shape: load → loop → write.

**Imports pattern (must include `matplotlib.use("Agg")` BEFORE pyplot indirect import):**
```python
from __future__ import annotations

# CRITICO: setting backend deve precedere QUALSIASI import che catena a pyplot.
import matplotlib
matplotlib.use("Agg")

import logging
from pathlib import Path
from datetime import date

from backtest.loader import load_bars
from backtest.costs import load_cost_model
from backtest.ledger import LedgerWriter
from backtest.engine import BacktestEngine
from backtest.baseline.determinism import seed_for_run_id, file_sha256
from backtest.baseline.dataset_writer import write_decisions_shard, write_drafts_shard
from backtest.baseline.plot_writer import plot_equity_curve

_log = logging.getLogger(__name__)
```

**Idempotency / `--force` pattern** — mirror `backtest/ledger.py:137-142` `INSERT OR REPLACE` and add the `DELETE FROM backtest_trades WHERE run_id=?` step flagged in RESEARCH §Pitfall (line 535):
```python
def _run_id_exists(db_path: Path, run_id: str) -> bool:
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM backtest_runs WHERE run_id=?", (run_id,)
        ).fetchone()
    return row is not None

def _force_clear_run(db_path: Path, run_id: str) -> None:
    """Critical: AUTOINCREMENT su backtest_trades duplica righe in --force se non puliamo prima."""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM backtest_trades WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM backtest_runs WHERE run_id=?", (run_id,))
        conn.commit()
```

**Engine invocation pattern** — mirror `backtest/engine.py::run_backtest` (lines 320–342):
```python
ledger = LedgerWriter(db_path)
eng = BacktestEngine(
    bars=bars,
    symbol=symbol,
    timeframe=tf,
    cost_model=cost,
    cfg=cfg_for_profile,                # profile-specific cfg clone (set RISK_MODE=profile)
    initial_balance=baseline_cfg.equity_initial_eur,
    ledger=ledger,
    cost_yaml_hash=file_sha256(Path("data/configs/costs.yaml"))[:16],
    run_id=run_id,                      # esplicito → bypass _compute_run_id default
)
result = eng.run()
```

---

### `backtest/baseline/dataset_writer.py` (parquet shard writer)

**Analog:** `C:/trading-agent/backtest/ledger.py::LedgerWriter.insert_trades` (lines 144-169) — same shape: list[dict] → batched persistence with parameter validation. The store changes (parquet vs sqlite) but the *contract* is identical.

**Module docstring pattern** (mirror `backtest/ledger.py:1-7`):
```python
"""Parquet shard writer per baseline run (D-01, D-02, D-03).

Per-worker shard prevent contention. Main process finalize via pyarrow.dataset
streaming (no full-load memory blow per i 65M righe baseline_drafts).
"""
```

**Batch insert shape** — analog `LedgerWriter.insert_trades:144-169`:
```python
def write_decisions_shard(rows: list[dict], run_id: str, shard_dir: Path) -> Path:
    """Worker scrive proprio file parquet — no contention con altri worker."""
    if not rows:
        return shard_dir / f"baseline_decisions_{run_id}.parquet"  # empty marker
    shard_dir.mkdir(parents=True, exist_ok=True)
    path = shard_dir / f"baseline_decisions_{run_id}.parquet"
    df = pd.DataFrame(rows)
    df.to_parquet(path, compression="snappy", index=False, engine="pyarrow")
    return path
```

**Error guard pattern** — empty-list early return mirrors `LedgerWriter.insert_trades:155-156`:
```python
if not trades:
    return
```

---

### `backtest/baseline/plot_writer.py` (matplotlib Agg)

**Analog:** None in repo (matplotlib is a NEW dep). Pattern source: RESEARCH §Pattern 4 (lines 426–465).

**Imports pattern (mandatory `Agg` ordering):**
```python
"""Equity curve PNG writer (D-19, D-20). Matplotlib Agg headless per ProcessPool."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # OBBLIGATORIO prima di import pyplot
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
```

**Plot pattern** (verbatim from RESEARCH §Pattern 4 lines 442-463):
```python
def plot_equity_curve(equity: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 6), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    ax1.plot(equity["timestamp"], equity["equity_eur"], color="steelblue", linewidth=1)
    ax1.set_ylabel("Equity (EUR)")
    ax1.set_title(out_path.stem.replace("_", " "))
    ax1.grid(True, alpha=0.3)

    ax2.fill_between(equity["timestamp"], equity["drawdown_pct"], 0,
                     color="indianred", alpha=0.5)
    ax2.set_ylabel("DD %")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)  # CRITICO — libera memoria, evita leak su 27 plot
```

---

### `backtest/baseline/report_writer.py` (Markdown report)

**Analog:** None in repo. Schema dictated by CONTEXT D-18 (lines 86–90 of CONTEXT.md). Use plain `pathlib.Path.write_text` + f-string template.

**Italiano comments + structure** (project convention CLAUDE.md §Convenzioni):
```python
"""Compose .planning/research/baseline-{date}.md report (D-18).

Aggrega risultati 27 run dopo pool join. Schema: header + tabella 27-row +
per-slice mini-section + appendix (config hashes, slippage_seed, warm-up bars).
"""
```

**File write pattern** — mirror Phase 1 modules' Path-based I/O (`backtest/loader.py:45`):
```python
def write_baseline_report(results: list[dict], out_path: Path, meta: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render(results, meta), encoding="utf-8")
```

---

### `backtest/baseline/determinism.py` (sha256 hashes + seed)

**Analog:** `C:/trading-agent/backtest/engine.py::_hash_cost_yaml` (lines 66-69) and `::_compute_run_id` (lines 59-63) — same shape, MD5 → SHA256 upgrade per RESEARCH Pitfall 1.

**Existing pattern to upgrade** (engine.py:59-69):
```python
def _compute_run_id(symbol, timeframe, first_time, last_time, cost_hash):
    payload = f"{symbol}|{timeframe}|{first_time}|{last_time}|{cost_hash}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]

def _hash_cost_yaml(yaml_path):
    if yaml_path is None or not Path(yaml_path).exists():
        return "nohash"
    return hashlib.md5(Path(yaml_path).read_bytes()).hexdigest()[:16]
```

**Phase 5 module** (RESEARCH §Pattern 5 lines 474-493):
```python
"""Deterministic seed + config hash audit trail (D-17). SHA256 — Python hash() randomized."""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np

def seed_for_run_id(run_id: str) -> int:
    """31-bit seed deterministico cross-run, cross-machine."""
    digest = hashlib.sha256(run_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF

def file_sha256(path: Path) -> str:
    """Config hash per backtest_runs audit trail (D-17)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def make_rng(run_id: str) -> np.random.Generator:
    return np.random.default_rng(seed_for_run_id(run_id))
```

---

### `backtest/baseline/wal_setup.py` (SQLite WAL + retry)

**Analog 1 — WAL pragma block:** `C:/trading-agent/logger.py:61-63`:
```python
with sqlite3.connect(_db_path) as conn:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_TRADES_LOG_SCHEMA)
    conn.commit()
```

**Analog 2 — retry decorator:** `C:/trading-agent/mt5_client.py:26-39` (verbatim shape):
```python
def _retry(n: int = 3):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(n):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    logger.warning("retry %d/%d for %s: %s", attempt + 1, n, fn.__name__, exc)
            raise last_exc
        return wrapper
    return decorator
```

**Phase 5 adaptation** — narrow `Exception` to `sqlite3.OperationalError` "database is locked" + add jitter:
```python
import random, sqlite3, time
from typing import Callable, TypeVar

T = TypeVar("T")
_log = logging.getLogger(__name__)

def enable_sqlite_wal(db_path: Path) -> None:
    """Una tantum dal main process. WAL mode persiste cross-connection."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.commit()

def with_retry(fn: Callable[[], T], n: int = 5, base_delay: float = 0.05) -> T:
    """Riusa shape mt5_client._retry. Exponential backoff + jitter su SQLITE_BUSY."""
    last_exc = None
    for attempt in range(n):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_exc = exc
            delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
            _log.warning("retry %d/%d sqlite locked: %s", attempt + 1, n, exc)
            time.sleep(delay)
    raise last_exc
```

---

### `data/configs/baseline.yaml` (NEW config)

**Analog:** `C:/trading-agent/data/configs/costs.yaml` (per-symbol YAML) loaded by `backtest/costs.py::load_cost_model` (lines 42-59).

**costs.yaml header convention** (lines 1-3):
```yaml
# data/configs/baseline.yaml
# Phase 5 baseline backtest orchestration knobs (D-15, D-17, D-19).
# Loaded da backtest.baseline.runner via load_baseline_config().
```

**Loader pattern to implement** — mirror `backtest/costs.py::load_cost_model:42-59`:
```python
@dataclass(frozen=True)
class BaselineConfig:
    equity_initial_eur: float
    slippage_seed: int
    timeout_bars: dict[str, int]   # {"M15": 96, "M30": 96, "H1": 120}
    warm_up_min_bars: int
    max_workers: int
    parquet_compression: str
    force_rerun: bool
    progress_bar: bool
    training_data_dir: str
    report_dir: str
    equity_curves_dir: str

def load_baseline_config(yaml_path: Path) -> BaselineConfig:
    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return BaselineConfig(
        equity_initial_eur=float(cfg["equity_initial_eur"]),
        slippage_seed=int(cfg["slippage_seed"]),
        timeout_bars={k: int(v) for k, v in cfg["timeout_bars"].items()},
        warm_up_min_bars=int(cfg["warm_up_min_bars"]),
        max_workers=int(cfg["max_workers"]),
        parquet_compression=str(cfg.get("parquet_compression", "snappy")),
        force_rerun=bool(cfg.get("force_rerun", False)),
        progress_bar=bool(cfg.get("progress_bar", True)),
        training_data_dir=str(cfg.get("training_data_dir", "data/training")),
        report_dir=str(cfg.get("report_dir", ".planning/research")),
        equity_curves_dir=str(cfg.get("equity_curves_dir", ".planning/research/baseline-equity-curves")),
    )
```

---

### `backtest/ledger.py` (MODIFY — extend `backtest_runs`)

**Existing schema** (`backtest/ledger.py:19-43`): currently has `cost_yaml_hash` already. Phase 5 adds 4 columns:
- `slippage_seed_effective INTEGER`
- `strategy_yaml_hash TEXT`
- `baseline_yaml_hash TEXT`
- `git_sha TEXT`

**Migration pattern** — SQLite `CREATE TABLE IF NOT EXISTS` is idempotent for *creation* but does NOT add columns to existing tables. Use `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` (analog to `logger.py` schema-init style):

```python
def _migrate_backtest_runs(conn: sqlite3.Connection) -> None:
    """Additive migration: ALTER TABLE ADD COLUMN se mancante.

    SQLite ADD COLUMN richiede DEFAULT NULL — backwards-compatible con righe esistenti.
    """
    existing = {r[1] for r in conn.execute("PRAGMA table_info(backtest_runs)")}
    additions = [
        ("slippage_seed_effective", "INTEGER"),
        ("strategy_yaml_hash", "TEXT"),
        ("baseline_yaml_hash", "TEXT"),
        ("git_sha", "TEXT"),
    ]
    for col, typ in additions:
        if col not in existing:
            conn.execute(f"ALTER TABLE backtest_runs ADD COLUMN {col} {typ}")
```

**Update `_BT_RUNS_COLUMNS`** (line 80-86): append the 4 new columns at the end (column order MUST match `_INSERT_RUN_SQL`):
```python
_BT_RUNS_COLUMNS: tuple[str, ...] = (
    "run_id", "symbol", "timeframe", "date_start", "date_end",
    "cost_yaml_hash", "profile", "n_folds", "fold_mode", "train_ratio",
    "started_at", "finished_at", "total_trades", "sharpe", "sortino",
    "max_dd_pct", "hit_rate", "expectancy_usd", "profit_factor", "avg_r",
    "total_pnl_usd",
    # Phase 5 additions:
    "slippage_seed_effective", "strategy_yaml_hash", "baseline_yaml_hash", "git_sha",
)
```

Update `_DDL_BACKTEST_RUNS` (line 19-43) similarly so fresh DBs get the right schema; migration handles existing DBs.

---

### `backtest/engine.py` (MODIFY — accept Phase 5 kwargs)

**Existing signature** (`backtest/engine.py:91-103`):
```python
def __init__(self, bars, symbol, timeframe, cost_model, cfg=None,
             initial_balance=10_000.0, run_id=None, ledger=None,
             fold_index=None, cost_yaml_hash="nohash") -> None:
```

**Phase 5 additions** (additive, default-None to keep Phase 1 callers working):
```python
def __init__(
    self, bars, symbol, timeframe, cost_model, cfg=None,
    initial_balance=10_000.0, run_id=None, ledger=None,
    fold_index=None, cost_yaml_hash="nohash",
    # ── Phase 5 additions ────────────────────────────────────────
    indicators_full: dict | None = None,   # precomputed cache (D-15)
    risk_profile: str | None = None,        # CONSERVATIVE|MODERATE|AGGRESSIVE
    timeout_bars: int | None = None,        # M15=96, M30=96, H1=120 (D-05)
    equity_initial: float | None = None,    # alias di initial_balance per chiarezza Phase 5
) -> None:
```

**Profile injection pattern** — mirror existing `_always_open_cfg` (engine.py:48-56) but set `RISK_MODE`:
```python
if risk_profile is not None:
    self.cfg.RISK_MODE = risk_profile  # consumed by risk_engine.evaluate_trade:41
```

**Timeout enforcement pattern** — bar count counter inside main loop (engine.py:140 onwards). Track `entry_bar_index` already exists on `VirtualPosition` (broker.py:33) — add timeout check inside `BacktestBroker._check_sl_tp` or in engine before `_check_sl_tp` call. Recommended: extend `_check_sl_tp` with timeout logic (single source of close).

---

### `backtest/metrics.py` (MODIFY — add `longest_dd_days`)

**Existing dataclass** (`backtest/metrics.py:23-35`): `BacktestMetrics` already has `avg_r` (line 33). Phase 5 adds:
```python
@dataclass
class BacktestMetrics:
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    longest_dd_days: float          # NEW Phase 5 (D-18 tabella column)
    hit_rate: float
    expectancy_usd: float
    profit_factor: float
    avg_r: float
    total_trades: int
    total_pnl_usd: float
```

**Computation pattern** — extend the running peak loop already at lines 110–122:
```python
# In compute_metrics, dopo il blocco max_dd:
# longest_dd_days: numero massimo di "bar units" dove equity < peak.
# Approssimare come run-length massima dello stato underwater su pnl cumulativo.
```

---

### `requirements.txt` (MODIFY)

Append:
```
pyarrow
matplotlib
```
(no version pin — repo convention is unpinned for non-`MetaTrader5`/`pydantic` deps; verify versions in Wave 0 commit message per RESEARCH lines 142-147).

---

### `scripts/run_baseline_backtest.py` (CLI entry)

**Analog:** `C:/trading-agent/scripts/dry_run_cycle.py` (verbatim bootstrap structure: docstring, sys.path injection, main(), exit code).

**Bootstrap pattern** (mirror `scripts/dry_run_cycle.py:1-43`):
```python
r"""Phase 5 baseline backtest runner — 27 run paralleli (BACK-07, INT-01).

Esegue baseline pre-ML completo: 23.5y × 3 pair × 3 TF × 3 profile = 27 run.
Output:
  - data/training/baseline_decisions/ (parquet directory)
  - data/training/baseline_drafts/    (parquet directory)
  - .planning/research/baseline-{date}.md
  - .planning/research/baseline-equity-curves/{symbol}_{tf}_{profile}.png (×27)
  - logs/trades.db tabelle backtest_trades + backtest_runs

Uso:
    .\.venv\Scripts\python.exe scripts\run_baseline_backtest.py
    .\.venv\Scripts\python.exe scripts\run_baseline_backtest.py --force
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.baseline.runner import run_baseline  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-run anche se run_id esiste")
    args = parser.parse_args()
    run_baseline(force=args.force)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

---

### Test files (8 test modules)

#### `tests/test_baseline_dataset_writer.py`
**Analog:** `tests/test_backtest_ledger.py` (verbatim — same `tmp_path` + round-trip-on-store shape).

**Imports + helper pattern** (mirror `tests/test_backtest_ledger.py:1-23`):
```python
"""Tests for backtest.baseline.dataset_writer (D-01, D-02, D-03)."""
from __future__ import annotations

import pandas as pd
from pathlib import Path

import pytest

from backtest.baseline.dataset_writer import write_decisions_shard, finalize_parquet_shards
```

**Round-trip test pattern** (mirror `test_record_run_idempotent:40-54`):
```python
def test_decisions_shard_round_trip(tmp_path: Path) -> None:
    rows = [{"run_id": "r1", "symbol": "EURUSD", "outcome": "WIN", "pnl_pips": 12.3}]
    path = write_decisions_shard(rows, "r1", tmp_path)
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert df.iloc[0]["outcome"] == "WIN"
```

#### `tests/test_baseline_runner.py`
**Analog:** `tests/test_backtest_engine.py:130-151` (`test_engine_5bar_fixture` shape — fixture, run, assert ledger row).

**Pattern:** monkey-patch `run_slice_3profiles` to return synthetic results, then assert `ProcessPoolExecutor` orchestration completes. Use `multiprocessing.set_start_method("spawn")` explicit for determinism.

#### `tests/test_baseline_no_future_leakage.py`
**Analog:** `tests/test_backtest_engine.py::test_engine_5bar_fixture` (warm-up gate test).
**Pattern:** Build a synthetic indicator that returns `NaN` for the future portion of bars; assert detector at bar `i` never sees `bars[i+1:]`. Hook into `compute_all_extended` mock that records the slice length passed.

#### `tests/test_baseline_determinism.py`
**Analog:** None direct. **Pattern:** call `seed_for_run_id("baseline_2026-05-07_EURUSD_M15_MODERATE")` twice; assert identical. Subprocess test: spawn child Python `.venv/Scripts/python.exe -c "..."`, assert same digest cross-process.

#### `tests/test_baseline_wal.py`
**Analog:** `tests/test_backtest_ledger.py::test_insert_trades_batch:57-80`.
**Pattern:** spawn 3 `multiprocessing.Process` workers each calling `ledger.insert_trades` against shared `tmp_path / "trades.db"` (with WAL enabled in main first); assert no `OperationalError` and final row count == 3 × N.

#### `tests/test_baseline_plot_writer.py`
**Pattern:**
```python
def test_plot_creates_png(tmp_path: Path) -> None:
    equity = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=100),
        "equity_eur": [10000 + i for i in range(100)],
        "drawdown_pct": [0.0] * 100,
    })
    out = tmp_path / "EURUSD_M15_MODERATE.png"
    plot_equity_curve(equity, out)
    assert out.exists()
    assert out.stat().st_size > 1000  # PNG sano ≥1KB
```

#### `tests/test_baseline_report_writer.py`
**Pattern:** assert MD output contains all 27 slice_id strings + appendix hash row.

#### `tests/conftest.py`
**Pattern:** shared fixtures — `tmp_db_with_wal` (calls `enable_sqlite_wal`), `synthetic_bars` (mirror `tests/test_backtest_engine.py::_uptrend_bars`), `synthetic_indicators_full`.

---

## Shared Patterns

### Pattern S1: `from __future__ import annotations` + PEP 604 type hints
**Source:** Every Phase 1 module — `backtest/engine.py:24`, `backtest/broker.py:11`, `backtest/ledger.py:8`, `backtest/loader.py:1`, `backtest/walk_forward.py:6`.
**Apply to:** ALL new `.py` files in `backtest/baseline/`, `scripts/`, `tests/`.
**Rationale:** Project convention `T | None`, `list[dict]`, `dict[str, int]` (CONVENTIONS.md §Type Hints).

### Pattern S2: Module-level logger
**Source:** `backtest/engine.py:45`, `risk_engine.py:10`, `mt5_client.py:11`, `logger.py` (project convention CONVENTIONS.md §Logging).
**Apply to:** `runner.py`, `slice_worker.py`, `dataset_writer.py`, `wal_setup.py`, `report_writer.py`.
```python
import logging
_log = logging.getLogger(__name__)
```
Use `%`-style lazy interpolation: `_log.info("Run %s completato in %.1fs", run_id, elapsed)`. Italiano messages per CLAUDE.md §Convenzioni.

### Pattern S3: SQLite `CREATE TABLE IF NOT EXISTS` + parameterized inserts
**Source:** `backtest/ledger.py:19-67`, `logger.py:14-28`, `scheduler.py` (HeartbeatStore).
**Apply to:** Any module touching `logs/trades.db`. Phase 5 reuses `LedgerWriter` — no new tables needed except optional `_migrate_backtest_runs` ALTER COLUMN block.

### Pattern S4: Frozen dataclass + YAML loader
**Source:** `backtest/costs.py:8-23` (frozen `CostModel`) + `backtest/costs.py:42-59` (`load_cost_model`).
**Apply to:** `backtest/baseline/runner.py` (declare `BaselineConfig`) + `data/configs/baseline.yaml`.
```python
@dataclass(frozen=True)
class BaselineConfig: ...
def load_baseline_config(yaml_path: Path) -> BaselineConfig: ...
```

### Pattern S5: Retry with `_retry` decorator shape
**Source:** `mt5_client.py:26-39` + `risk_engine.py:22-29` (`_call_retry`).
**Apply to:** `backtest/baseline/wal_setup.py::with_retry`. Narrow exception class to `sqlite3.OperationalError "locked"`. Add jitter (RESEARCH §Pattern 3).

### Pattern S6: pytest `tmp_path` for SQLite/file fixtures
**Source:** `tests/test_backtest_ledger.py:26-37`, `tests/test_backtest_engine.py:130-151`.
**Apply to:** All 8 new `tests/test_baseline_*.py` files. Never write to `logs/trades.db` from a test — always `tmp_path / "trades.db"`.

### Pattern S7: Italiano docstrings + comments
**Source:** CLAUDE.md §Convenzioni "Lingua commenti/log/rationale: italiano". Examples: `risk_engine.py:54-148` numbered Italian comments (`# 1. Kill switch giornaliero`), `scripts/dry_run_cycle.py:1-23` Italian docstring.
**Apply to:** All new modules. English allowed for type names and keyword args; user-facing logs and rationale comments in Italian.

### Pattern S8: Path-based config reading (no .env access in library code)
**Source:** `backtest/costs.py::load_cost_model:42-44`, `backtest/loader.py:45`.
**Apply to:** `runner.py`, `slice_worker.py` — never read `os.environ` directly. Pass `Path` objects from CLI/main.

---

## No Analog Found

| File | Role | Reason | Fallback |
|------|------|--------|----------|
| `backtest/baseline/plot_writer.py` | matplotlib utility | matplotlib is a NEW dep — no prior in-repo usage | RESEARCH §Pattern 4 lines 426-465 (verbatim source) |
| `backtest/baseline/report_writer.py` | Markdown composer | No prior repo Markdown-writer | CONTEXT D-18 schema (lines 86-90) |
| `tests/test_baseline_determinism.py` | cross-process hash test | Repo lacks subprocess-determinism test | RESEARCH §Pitfall 1 (lines 539-544); use `subprocess.run` of `.venv/Scripts/python.exe -c "..."` |
| `tests/conftest.py` | shared fixtures | Repo currently has no `conftest.py` (verified via Glob) | New file; PRO TIP — keep fixtures additive, no `autouse=True` to avoid test pollution |

---

## Metadata

**Analog search scope:**
- `C:/trading-agent/backtest/` (8 files, all read)
- `C:/trading-agent/tests/test_backtest_*.py` (7 test files surveyed; 2 read in detail)
- `C:/trading-agent/mt5_client.py` (retry pattern)
- `C:/trading-agent/risk_engine.py` (italiano commenti, profile constants, `_call_retry`)
- `C:/trading-agent/logger.py` (WAL pragma, SQLite schema init)
- `C:/trading-agent/scripts/dry_run_cycle.py` (script bootstrap)
- `C:/trading-agent/data/configs/costs.yaml` (YAML schema)

**Files scanned:** ~25 (full read of 9, partial/grep of 16)

**Pattern extraction date:** 2026-05-07

**Project convention sources:** `CLAUDE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STACK.md`, `.planning/codebase/CONVENTIONS.md`.

## PATTERN MAPPING COMPLETE
