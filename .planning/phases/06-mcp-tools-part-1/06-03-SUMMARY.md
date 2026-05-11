---
phase: 06-mcp-tools-part-1
plan: 03
subsystem: backtest-async-control-plane-wave2
tags: [mcp, backtest, async, job-queue, process-pool, wave-2, tdd, mcp-01, mcp-02, mcp-03]
dependency_graph:
  requires:
    - mcp_tools/server.py (Wave 1 06-02)
    - mcp_tools/errors.py (Wave 1 06-02)
    - mcp/errors.py (Wave 0 06-01)
    - backtest_runs.status (Wave 0 06-01 migration)
    - backtest/engine.py (Phase 1 BACK-02)
    - backtest/walk_forward.py (Phase 1 BACK-05)
    - backtest/metrics.py (Phase 1 BACK-06)
    - backtest/ledger.py (Phase 1 BACK-07)
    - backtest/loader.py (Phase 1 BACK-01)
    - backtest/costs.py (Phase 1 BACK-03)
  provides:
    - mcp_tools/job_queue.py
    - mcp_tools/handlers/backtest.py
    - cfg.MCP_MAX_CONCURRENT_RUNS
    - backtest_runs.error_message (idempotent migration)
    - RUN_BACKTEST_TOOL, GET_BACKTEST_METRICS_TOOL, WALK_FORWARD_VALIDATE_TOOL, CANCEL_BACKTEST_TOOL
  affects:
    - Wave 3 (06-04 trail daemon + handle_modify_position): JobQueue indipendente, db_path bootstrap pronto
    - Wave 4 (06-05 correlation/session/multi_tf/replay_decision)
    - Phase 7 ML (replay_decision via BarSource Wave 1 + queue control plane)
tech_stack:
  added:
    - ProcessPoolExecutor (concurrent.futures) per worker isolation
    - dataclasses.asdict per BacktestMetrics → backtest_runs columns
    - sqlite3.Row factory per row→dict conversion
    - threading.Lock per submit/cancel race
  patterns:
    - process-pool-worker-isolation (Pitfall 1 no MT5 import)
    - top-level-picklable-worker
    - lazy-imports-inside-worker
    - in-memory + db-fallback registry
    - cancel-via-pool-shutdown-recreate (Pitfall 6 Windows zombie)
    - polymorphic-status-payload (D-A3)
    - idempotent-alter-table-add-column
    - tdd-red-green-handlers
key_files:
  created:
    - mcp_tools/job_queue.py
    - mcp_tools/handlers/backtest.py
  modified:
    - mcp_tools/server.py (bootstrap + list_tools + dispatch)
    - config.py (MCP_MAX_CONCURRENT_RUNS)
    - .env.example (MCP_MAX_CONCURRENT_RUNS=1)
    - tests/test_mcp_job_queue.py (6 stubs → real tests)
    - tests/test_mcp_handlers_backtest.py (8 stubs → real, 3 replay xfail preservati)
    - tests/test_mcp_smoke_round_trip.py (2 stubs → real, skipif gated)
decisions:
  - "Worker top-level picklable, lazy imports interni (backtest.* + Config + logger) per ProcessPool serialization; NO MT5/mt5_client import (Pitfall 1 Phase 5 D-15 carry-forward)."
  - "BacktestEngine signature reale richiede bars/symbol/timeframe/cost_model/cfg posizionali; plan-as-written assumeva broker=/profile= kwargs. Devio a Rule 3 architectural: cfg.RISK_MODE = profile (Phase 5 D-11), cost_model creato da load_cost_model(symbol, bars[0].close, yaml_path)."
  - "compute_metrics(trades, timeframe) ritorna BacktestMetrics dataclass; dataclasses.asdict + rename max_drawdown_pct → max_dd_pct e drop longest_dd_days (non in DDL backtest_runs) per finalize_run."
  - "expectancy_usd in DDL backtest_runs → payload UX expectancy_pips (alias D-A3 schema)."
  - "JobQueue.status() expone running_ghost per righe DB con status='running' ma worker non in memoria (post-restart agent); Wave 2 stub: nessun resume, solo signaling."
  - "Cancel mid-execution: pool.shutdown(wait=False, cancel_futures=True) + ricreazione (Pitfall 6 Windows zombie ~1s); rec.status='cancelled' impostato PRIMA del DB UPDATE per evitare race con _on_done callback."
  - "_on_done skip se rec.status già 'cancelled' (rispetta race con cancel()): il future può finire da solo nel zombie window ma noi non sovrascriviamo lo stato cancelled."
  - "Smoke round-trip skipif su data/historical/EURUSD/M15.csv + data/configs/costs.yaml: presenti su Codespace → entrambi PASS (31s wall-clock); assenti → SKIP cleanly."
  - "Dispatch backtest tool nel server: bucket condizionale name in (run_backtest, ...) per evitare 4 if separati + envelope internal_error se job_queue is None (modulo importato senza _bootstrap_state)."
metrics:
  duration_minutes: 35
  completed_date: "2026-05-11"
  tasks_completed: 3
  files_created: 2
  files_modified: 6
  commits: 5
  stubs_flipped: 14
  stubs_preserved_xfail: 3
  smoke_round_trip_status: "PASS (CSV+yaml presenti su Codespace)"
---

# Phase 6 Plan 03: Wave 2 Backtest Async Control Plane Summary

**One-liner:** Async backtest control plane (D-A1/A3/A4) — `JobQueue` su `ProcessPoolExecutor` (worker isolato senza MT5), 4 nuovi MCP tools (`run_backtest`, `get_backtest_metrics`, `walk_forward_validate`, `cancel_backtest`), polymorphic status payload, idempotent `backtest_runs.error_message` migration, smoke round-trip end-to-end con `BacktestEngine` parity verificata in 31s.

## Tasks Completati

| # | Task | Commit RED | Commit GREEN | TDD Gate |
|---|------|------------|--------------|----------|
| 1 | mcp_tools/job_queue.py + MCP_MAX_CONCURRENT_RUNS + bootstrap | `cf8aa00` | `07640ab` | RED → GREEN |
| 2 | mcp_tools/handlers/backtest.py + 4 tool registrations + dispatch | `c6338fd` | `1d06858` | RED → GREEN |
| 3 | tests/test_mcp_smoke_round_trip.py (SC#4) | — | `d2922f8` | non-TDD (e2e smoke) |

**TDD compliance:** Task 1 e Task 2 hanno commit `test(phase-6): TDD RED …` precedente al `feat(phase-6): … (GREEN)`. Gate sequence rispettata.

## Deliverable 1: JobQueue Infrastructure (`mcp_tools/job_queue.py`)

### API Summary

```python
class JobQueue:
    def __init__(self, max_workers: int, db_path: str)
    def submit(self, run_id: str, fn: Callable, metadata: dict, *args, **kwargs) -> dict
    def status(self, run_id: str) -> dict
    def cancel(self, run_id: str) -> dict
```

### Submit return shape (D-A1)

```python
# success:
{"ok": True, "run_id": "mcp_<utc_ts>_<sym>_<tf>_<profile>",
 "status": "started", "started_at": "<ISO8601>"}
# cap hit (D-A4):
{"ok": False, "error": "run_in_progress", "active_run_id": "<existing>"}
```

### Status polymorphic payload (D-A3)

| status | Payload Keys |
|--------|--------------|
| `running` | `{run_id, status, started_at, progress_pct=0.0, bars_processed=0, bars_total=0, trades_so_far}` |
| `done` | `{run_id, status, started_at, finished_at, _db_row}` (handler converte `_db_row` → metrics dict) |
| `failed` | `{run_id, status, error_message, started_at, failed_at}` |
| `cancelled` | `{run_id, status, started_at, cancelled_at}` |
| `running_ghost` | `{run_id, status, started_at, note}` (post-restart, status DB='running' ma no in-memory record) |
| `unknown` | `{ok: False, error: "unknown_run_id", run_id}` |

### Cancel return shape (D-A4)

```python
# success:
{"ok": True, "run_id": "<id>", "status": "cancelled"}
# no active:
{"ok": False, "error": "no_active_run", "run_id": "<id>"}
```

### Worker Picklability Check

| File | mt5_client import | mt5 import | MetaTrader5 import |
|------|------------------|-----------|---------------------|
| `mcp_tools/job_queue.py` | 0 | 0 | 0 |
| `mcp_tools/handlers/backtest.py` | 0 | 0 | 0 |

Worker `_backtest_worker` / `_walk_forward_worker` sono **TOP-LEVEL** e usano solo lazy imports interni (`backtest.loader`, `backtest.engine`, `backtest.costs`, `backtest.ledger`, `backtest.metrics`, `backtest.walk_forward` + `config.Config`, `logger.init_logger`).

### DB Migration (idempotente)

```sql
-- backtest_runs.status (Wave 0 06-01, già presente):
ALTER TABLE backtest_runs ADD COLUMN status TEXT NOT NULL DEFAULT 'running'

-- backtest_runs.error_message (Wave 2 06-03, nuovo):
ALTER TABLE backtest_runs ADD COLUMN error_message TEXT
```

Probe via `PRAGMA table_info(backtest_runs)`: ADD COLUMN solo se assente. Re-eseguibile senza side-effect.

## Deliverable 2: Backtest Handlers (`mcp_tools/handlers/backtest.py`)

### 4 Handlers + 4 Tool Registrations

#### `RUN_BACKTEST_TOOL` (MCP-01)

```python
inputSchema = {
    "type": "object",
    "properties": {
        "symbol":     {"type": "string", "enum": ["EURUSD", "GBPUSD", "USDJPY"]},
        "timeframe":  {"type": "string", "enum": ["M15", "M30", "H1"]},
        "date_start": {"type": "string", "description": "ISO8601 UTC"},
        "date_end":   {"type": "string", "description": "ISO8601 UTC, esclusivo"},
        "profile":    {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]},
    },
    "required": ["symbol", "timeframe", "date_start", "date_end", "profile"],
}
```

#### `GET_BACKTEST_METRICS_TOOL` (MCP-02 D-A3 polymorphic)

```python
inputSchema = {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]}
```

Payload `done` includes `metrics: {sharpe, sortino, max_dd_pct, hit_rate, expectancy_pips, profit_factor, avg_R, longest_dd_days, trade_count}` + `equity_curve_path` + `finished_at`.

#### `WALK_FORWARD_VALIDATE_TOOL` (MCP-03)

```python
inputSchema = {
    "type": "object",
    "properties": {
        "symbol":     {"type": "string", "enum": ["EURUSD", "GBPUSD", "USDJPY"]},
        "timeframe":  {"type": "string", "enum": ["M15", "M30", "H1"]},
        "date_start": {"type": "string"},
        "date_end":   {"type": "string"},
        "profile":    {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]},
        "n_folds":    {"type": "integer", "minimum": 2, "maximum": 10, "default": 5},
        "fold_mode":  {"type": "string", "enum": ["rolling", "expanding"], "default": "rolling"},
    },
    "required": ["symbol", "timeframe", "date_start", "date_end", "profile"],
}
```

Suffix run_id `_wfv{N}` (es. `mcp_20260511T..._EURUSD_M15_MODERATE_wfv3`). N folds in serie nel singolo worker process. Phase 1 D-06 cap=10 → `n_folds=11` ritorna `{"ok": False, "error": "invalid_n_folds"}`.

#### `CANCEL_BACKTEST_TOOL` (D-A4 derivato)

```python
inputSchema = {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]}
```

Tool extra Phase 6 (non in REQUIREMENTS ma necessario per UX cancel).

### Server Dispatch (mcp_tools/server.py)

```python
# Singleton lazy (None al module import, popolato da _bootstrap_state())
job_queue: "Any | None" = None

# Dispatch bucket per i 4 tool backtest:
if name in ("run_backtest", "get_backtest_metrics",
            "walk_forward_validate", "cancel_backtest"):
    if job_queue is None:
        return envelope("internal_error", "JobQueue non inizializzata")
    db_path = str(_trades_db_path(cfg))
    costs_yaml_path = "data/configs/costs.yaml"
    # ... handler dispatch
```

## Deliverable 3: Smoke Round-Trip (SC#4)

### Test gating

```python
@pytest.mark.skipif(not HISTORICAL_CSV.exists(),
                    reason="data/historical/EURUSD/M15.csv non presente: smoke skippato")
@pytest.mark.skipif(not COSTS_YAML.exists(),
                    reason="data/configs/costs.yaml non presente: smoke skippato")
```

### Verifica parity (Codespace Linux, CSV+yaml presenti)

| Test | Risultato | Note |
|------|-----------|------|
| `test_run_backtest_writes_db` | **PASS** (12.6s) | run_backtest async → poll → status='done' + backtest_runs row verificata |
| `test_round_trip_metrics` | **PASS** (~18s) | handler.metrics.trade_count == direct.total_trades (esatta), \|sharpe handler − sharpe direct\| < 0.01 |

Range: 1 settimana EURUSD M15, ~672 bar, backtest in ~5s per esecuzione (worker + in-process).

### Comportamento su CI senza dati storici

Entrambi i test ritornano **SKIPPED** con `reason` esplicativa. **Mai FAIL.**

## Test Results

### Wave 2 (scope diretto Plan 06-03)

| Test File | Total | Pass | Xfail | Note |
|-----------|-------|------|-------|------|
| `test_mcp_job_queue.py` | 6 | 6 | 0 | Tutti JobQueue green (4.1s) |
| `test_mcp_handlers_backtest.py` | 11 | 8 | 3 | 8 backtest green + 3 replay_decision xfail (Wave 4) |
| `test_mcp_smoke_round_trip.py` | 2 | 2 | 0 | SC#4 round-trip end-to-end (31s) |
| **TOTALE Wave 2 scope** | **19** | **16** | **3** | **84% pass / 16% xfail Wave 4** |

### Stub flipped: 14 / 17 (3 reserved per Wave 4)

```
- 6 JobQueue (test_mcp_job_queue.py)         : xfail → PASS
- 8 backtest handlers (non-replay)           : xfail → PASS
- 0 backtest handlers (replay_decision x3)   : xfail preservato per Wave 4 MCP-15
```

### Suite globale post-06-03 (Codespace Linux)

- **435 passed, 10 skipped, 25 xfailed, 1 failed** (5m wall-clock)
- 1 failed = `test_smoke_12month_under_60s` (Phase 1 perf SC-6 60s budget, **pre-esistente** verificato in 06-02 SUMMARY, deferred a Phase 1 plan-09 vectorization)
- Delta vs baseline 06-02 (428/11/41/1): +7 pass (-14 stub xfail Wave 0 chiusi + 7 nuovi test smoke/handlers; -16 xfailed; +0 new failures)

### Zero regressione (Wave 1 + Phase 5 legacy)

`pytest test_mcp_tools_v2 test_mcp_handlers_market test_mcp_handlers_proposal test_mcp_bar_source test_backtest_ledger`: **27 passed + 5 xfailed** (delta zero rispetto a 06-02).

## Wave 3 Prerequisites

- ✓ `_bootstrap_state()` ora inizializza `LedgerWriter` + `JobQueue`
- ✓ `_trades_db_path(cfg)` accessibile via logger module
- ✓ `cfg.MCP_MAX_CONCURRENT_RUNS` env-var pattern stabilito
- ✓ `JobQueue` indipendente da trail_daemon (Wave 3 può aggiungere `trail_daemon.ensure_table(db_path)` PRIMA di `JobQueue(...)` senza romperlo)
- ✓ Mt5Client wrappers `modify_position`/`partial_close`/`get_position` shipped in Wave 1 06-02

Wave 3 può procedere immediatamente: nessuna dipendenza inversa da Wave 2 oltre `cfg.MCP_MAX_CONCURRENT_RUNS` (config layer).

## Deviation dal Plan

### Rule 3 (architectural blocking — risolto inline)

**1. BacktestEngine signature reale vs plan-as-written**

- **Trigger:** Plan §Step A Task 2 mostrava `BacktestEngine(broker=broker, profile=profile, timeframe=timeframe, symbol=symbol)`. La signature reale di `backtest/engine.py:94-113` richiede `BacktestEngine(bars, symbol, timeframe, cost_model, cfg=, ledger=, run_id=, fold_index=, …)`.
- **Risoluzione:** worker chiama:
  ```python
  cfg.RISK_MODE = profile  # Phase 5 D-11
  cost_model = load_cost_model(symbol, bars[0].close, Path(yaml_path))
  eng = BacktestEngine(bars=bars, symbol=symbol, timeframe=timeframe,
                      cost_model=cost_model, cfg=cfg, ledger=ledger, run_id=run_id)
  result = eng.run()  # dict {run_id, trades, equity_curve, bars_processed}
  ```
- **Risultato:** parity verificata in test_round_trip_metrics — handler e in-process producono identici `trade_count` e Sharpe entro 0.01.

**2. `compute_metrics` ritorna `BacktestMetrics` dataclass (non dict)**

- **Trigger:** Plan §Step A Task 2 assumeva `metrics: dict`. La signature reale `compute_metrics(trades, timeframe="H1") -> BacktestMetrics`.
- **Risoluzione:** `dataclasses.asdict(metrics)` + rename `max_drawdown_pct → max_dd_pct` + pop `longest_dd_days` (non in DDL backtest_runs Wave 2). Mapping handler payload (D-A3) → `expectancy_usd → expectancy_pips` + `total_trades → trade_count` come alias UX.

**3. `LedgerWriter.append_trades` non esiste; uso `insert_trades` + `finalize_run`**

- **Trigger:** Plan §Step A Task 2 chiamava `writer.append_trades(run_id, result.trades)`. La signature reale `LedgerWriter.insert_trades(run_id, fold_index, trades)` + `finalize_run(run_id, status, **metrics)`.
- **Risoluzione:** worker NON chiama insert_trades direttamente (BacktestEngine.run() lo fa già via `self.ledger.insert_trades(...)`). Worker chiama solo `ledger.finalize_run(run_id, status="done", **metrics_dict)` post-engine.

**4. `walk_forward_slices` ritorna generator di tuple `(train, test)`**

- **Trigger:** Plan §Step A Task 2 assumeva `slices = walk_forward_slices(...)` con `sl["test_bars"]`. La signature reale `walk_forward_slices(bars, n_folds, train_ratio=4, mode="rolling") -> Generator[tuple[list, list], None, None]`.
- **Risoluzione:** `for fold_idx, (train_bars, test_bars) in enumerate(walk_forward_slices(bars, n_folds=n_folds, mode=fold_mode))`. Validation Phase 1 cap=10 nel walk_forward_slices solleva ValueError; handler intercetta prima del submit con `if n_folds > 10: return envelope("invalid_n_folds", ...)`.

### Rule 1 (auto-fix bug minor)

**5. `_walk_forward_worker` per-fold `run_id` univoco**

- **Trigger:** `BacktestEngine.run()` chiama `self.ledger.record_run(...)` con `self.run_id`. Se passiamo lo stesso `run_id` per N fold, INSERT OR REPLACE sovrascrive. Per evitare collisione, ogni fold usa `f"{run_id}_fold{fold_idx}"` come BacktestEngine.run_id (riga interna per persistenza trade); il `run_id` master resta quello JobQueue per status polling.
- **Risoluzione:** linea `run_id=f"{run_id}_fold{fold_idx}"` nel `BacktestEngine(...)` instantiation dentro il loop walk_forward.

### Rule 1 (auto-fix style)

**6. dispatch bucket condizionale invece di 4 if separati**

- **Trigger:** evita duplicazione del check `job_queue is None` + lookup db_path/costs_yaml.
- **Risoluzione:** `if name in (...): if job_queue is None: return ...; db_path = ...; if name == "run_backtest": ... elif ... return ...`. Riduce LOC dispatch da ~40 a ~25 LOC.

## Threat Model Compliance

Tutti i mitigation T-6-03-01..08 implementati come previsto:

- **T-6-03-01 Tampering run_id construction:** symbol/tf/profile enum-validated dal SDK MCP prima del handler (inputSchema); _build_run_id concatena solo enum values + UTC ts. ✓
- **T-6-03-02 Information Disclosure error_message:** worker exception str() salvata; no stack trace, no secrets. ✓
- **T-6-03-03 DoS concurrent run_backtest:** D-A4 cap=1 via `cfg.MCP_MAX_CONCURRENT_RUNS`; second submission ritorna `run_in_progress` senza spawnare worker. ✓
- **T-6-03-04 Repudiation backtest_runs mutation:** `_on_done`/`cancel`/worker_completion loggati via `init_logger` (RotatingFileHandler file-only); audit trail in `logs/trading-agent.log`. ✓
- **T-6-03-05 Tampering Worker integrity:** worker top-level in version-controlled `mcp_tools/handlers/backtest.py`; no eval/exec, pickled args sono solo str/int/float. ✓
- **T-6-03-06 Spoofing run_id collision:** `mcp_<utc_ts>_<sym>_<tf>_<profile>`; collision richiede 2 submissions nello stesso secondo con stessi enum values; cap=1 lo rende impossibile. ✓
- **T-6-03-07 DoS Worker memory:** Phase 5 D-15 measured 1.8GB peak; ProcessPool worker recycled via cancel teardown se serve. ✓
- **T-6-03-08 Tampering costs.yaml path:** `costs_yaml_path = "data/configs/costs.yaml"` hardcoded nel dispatch; non esposto via inputSchema. ✓

## Known Stubs / Limitations

- **`equity_curve_path` Wave 2:** `_equity_path()` ritorna path PNG se esiste in `.planning/research/baseline-equity-curves/<run_id>.png` (Phase 5 D-19 convention); altrimenti `None`. Wave 4 (06-05) potrà aggiungere generazione PNG on-demand.
- **Progress tracking Wave 2 minimo:** `_read_progress_from_db` ritorna solo `trades_so_far` (via COUNT su backtest_trades); `progress_pct/bars_processed/bars_total` restano `0.0/0/0`. Future plan (Phase 9 analisi failure) aggiungerà colonne dedicate al progress su backtest_runs popolate dal worker.
- **`running_ghost` recovery Wave 2:** segnalazione solo, no auto-resume. Restart del MCP server con righe DB `status='running'` ritorna `running_ghost` payload con `note` esplicativa; operatore deve cancellare manualmente o riavviare backtest. Phase 8 (MCP Tools part 2) può aggiungere reconcile-on-startup.
- **Walk-forward Phase 1 D-06 cap=10:** rispettato sia a handler-level (envelope `invalid_n_folds` su n_folds>10) sia a worker-level (`walk_forward_slices` solleva ValueError); doppia barriera.
- **Wave 4 xfail preservati** in `test_mcp_handlers_backtest.py`: 3 test (`test_replay_decision_live`, `test_replay_decision_baseline`, `test_replay_decision_regression_flag`) restano xfail come da plan (MCP-15 D-D2 owned by Wave 4 06-05).

## Deferred Issues (Out of Scope)

Aggiunti a `.planning/phases/06-mcp-tools-part-1/deferred-items.md` durante 06-02; nessuna nuova entry in 06-03:

- `test_backtest_engine.py::test_smoke_12month_under_60s` (Phase 1 perf, pre-esistente)
- 4 collection errors per moduli mancanti (`feedparser`, `apscheduler` — Phase 14-15)

## Next: Wave 3 + Wave 4

- **Wave 3 (Plan 06-04):** trail daemon in-process + `handle_modify_position` + `position_trails` table. Requires: `Mt5Client.modify_position/get_position` (shipped Wave 1 ✓), `TRAIL_TICK_TIMEFRAME` env, `_bootstrap_state` order (db_path già pronto da Wave 2 ✓).
- **Wave 4 (Plan 06-05):** `get_correlation_matrix`, `get_session_state`, `get_multi_tf_snapshot`, `get_pattern_catalog`, `replay_decision` (chiude i 3 xfail rimasti). Consumerà `BarSource.get(as_of_ts=...)` Wave 1 + `JobQueue` per replay async.

## Self-Check

### File created exist

- `mcp_tools/job_queue.py` → FOUND
- `mcp_tools/handlers/backtest.py` → FOUND
- `tests/test_mcp_smoke_round_trip.py` → FOUND (overwritten Wave 0 stub)
- `.planning/phases/06-mcp-tools-part-1/06-03-SUMMARY.md` → FOUND (questo file)

### Commit existing

- `cf8aa00` (Task 1 RED) → FOUND
- `07640ab` (Task 1 GREEN) → FOUND
- `c6338fd` (Task 2 RED) → FOUND
- `1d06858` (Task 2 GREEN) → FOUND
- `d2922f8` (Task 3 smoke) → FOUND

## Self-Check: PASSED
