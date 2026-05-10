---
phase: 06-mcp-tools-part-1
plan: 01
subsystem: mcp-scaffolding
tags: [mcp, backtest, ledger, error-codes, test-stubs, wave-0]
dependency_graph:
  requires: [backtest/ledger.py, tests/conftest.py]
  provides: [mcp/errors.py, mcp/__init__.py, backtest_runs.status, test-scaffold-55-stubs]
  affects: [Wave 1-4 plans 06-02 to 06-04, replay_decision Wave 4]
tech_stack:
  added: [mcp/ package init]
  patterns: [idempotent-migration, xfail-nyquist-scaffold, error-envelope-constants]
key_files:
  created:
    - mcp/__init__.py
    - mcp/errors.py
    - tests/test_mcp_handlers_market.py
    - tests/test_mcp_handlers_position.py
    - tests/test_mcp_handlers_backtest.py
    - tests/test_mcp_handlers_proposal.py
    - tests/test_mcp_bar_source.py
    - tests/test_mcp_job_queue.py
    - tests/test_mcp_trail_daemon.py
    - tests/test_mcp_smoke_round_trip.py
    - tests/test_mcp_legacy_compat.py
    - tests/test_mcp_integration_modify.py
    - tests/fixtures/mcp/sample_position_trails.sql
    - tests/fixtures/mcp/sample_trades_log.json
  modified:
    - backtest/ledger.py
    - tests/conftest.py
decisions:
  - "TRADE_ACTION_SLTP stub impostato a 6 (valore reale MT5) invece di 0 generico — necessario per assert Phase 6 handler tests"
  - "mcp/errors.py usa 14 costanti (13 D-F2 + DECISION_NOT_FOUND) — DECISION_NOT_FOUND aggiunto per completezza D-D2"
  - "test_mcp_tools_v2.py pre-esistente fallisce per assenza SDK mcp nel CI — pre-existing, non regression Wave 0"
  - "pytest.mark.integration non registrato in pytest.ini — warning non bloccante, Wave 3 registrerà il mark"
metrics:
  duration_minutes: 35
  completed_date: "2026-05-10"
  tasks_completed: 4
  files_created: 14
  files_modified: 2
---

# Phase 6 Plan 01: Wave 0 Scaffolding Summary

**One-liner:** DB migration `backtest_runs.status` + `ErrorCodes` D-F2 constants + 55 xfail stubs per Nyquist sampling dei requisiti Wave 1-4.

## Tasks Completati

| # | Task | Commit | Stato |
|---|------|--------|-------|
| 1 | Add backtest_runs.status + idempotent migration | `6a6eb21` | OK |
| 2 | Create mcp/errors.py ErrorCodes D-F2 | `9ae0276` | OK |
| 3 | Verify deps + extend conftest.py MT5 stub | `69a6626` | OK |
| 4 | Create 11 stub test files + 2 fixture files | `3a63222` | OK |

## Deliverable 1: DB Migration backtest_runs.status

**Risultato:** Aggiunta colonna `status TEXT NOT NULL DEFAULT 'running'` in `backtest/ledger.py`.

- DDL aggiornato con `status` come ultima colonna (Phase 6 annotation in commento).
- `_migrate_status_column(conn)`: probe PRAGMA table_info → ALTER TABLE solo se assente. Idempotente su DB Phase 5 e precedenti.
- `ensure_schema()` chiama `_migrate_status_column` dopo `_migrate_backtest_runs`.
- `record_run()`: `setdefault('status', 'running')` per backward-compat con caller che non passano status.
- `start_run(run_id, **meta)`: helper MCP-01 che imposta status='running' esplicitamente.
- `finalize_run(run_id, status='done', **metrics)`: UPDATE con metriche + status (done/failed/cancelled).
- `_BT_RUNS_COLUMNS` aggiornato con "status" come ultimo elemento.
- **Verifica fresh DB:** `status` presente. **Verifica legacy DB:** ALTER TABLE aggiunge colonna, row esistente riceve default 'running'.
- **Zero regression:** tutti i 5 test `test_backtest_ledger.py` passano.

**Threat model T-6-01-01:** ALTER TABLE SQLite atomico, idempotente, zero distruzione dati. PRAGMA probe prima di ALTER.

## Deliverable 2: mcp/errors.py (D-F2)

**Risultato:** Package `mcp/` inizializzato con `__init__.py` + `errors.py`.

- **14 costanti** `ErrorCodes` (13 D-F2 + `DECISION_NOT_FOUND` per D-D2):
  - Backtest: `RUN_IN_PROGRESS`, `UNKNOWN_RUN_ID`, `NO_ACTIVE_RUN`
  - BarSource: `HISTORICAL_DATA_UNAVAILABLE`, `AS_OF_TS_OUT_OF_RANGE`, `AS_OF_TS_WARMUP_INSUFFICIENT`
  - Position: `STOPS_LEVEL_VIOLATION`, `PARTIAL_EXCEEDS_VOLUME`, `POSITION_NOT_FOUND`, `BROKER_REJECTED`, `CONFLICT_TRAIL_AND_MANUAL_SL`, `CONFLICT_BE_AND_MANUAL_SL`
  - Server: `MT5_NOT_READY`
  - Replay: `DECISION_NOT_FOUND`
- **`envelope(error_code, message, **context)`:** costruisce `{ok: False, error, message, ...context}` uniforme.
- Consumato da tutti i handler Wave 1-4 via `from mcp.errors import ErrorCodes`.

## Deliverable 3: conftest.py MetaTrader5 stub esteso (Phase 6)

**Risultato:** Stub MT5 aggiornato con valori reali invece di `0` generico.

**Costanti aggiornate con valori corretti:**

| Costante | Valore | Note |
|----------|--------|------|
| TRADE_ACTION_SLTP | 6 | CRITICO: modify_position D-B1 |
| TRADE_RETCODE_DONE | 10009 | Assert corretti nei test |
| ORDER_FILLING_RETURN | 2 | TenTrade filling mode |
| POSITION_TYPE_BUY | 0 | — |
| POSITION_TYPE_SELL | 1 | — |
| TIMEFRAME_M30 | 30 | Multi-TF tests |
| TIMEFRAME_H1 | 60 | — |
| TIMEFRAME_H4 | 240 | — |

**Callable stub** con implementazioni realistiche:
- `positions_get(*args, **kwargs)`: ritorna `()` di default (override via MagicMock per-test)
- `order_send(request)`: ritorna `_Result(retcode=10009, order=1)`
- `symbol_info_tick(symbol)`: ritorna `_Tick(bid=1.10000, ask=1.10010, time=0)`
- `last_error()`: ritorna `(0, "no error")`

**Verifica dep Phase 1-5:**

| Surface | Stato | Note |
|---------|-------|------|
| `backtest.ledger.LedgerWriter` | OK (via test) | Phase 1 |
| `backtest.engine.BacktestEngine` | SKIP (dotenv/MT5 deps mancanti senza pytest conftest) | Pre-existing gap — OK via pytest |
| `pyarrow` | OK v24.0.0 | Phase 5 parquet |
| `data/training/baseline_decisions.parquet` | ASSENTE | Wave 4 replay_decision degrada a live-only lookup |
| mcp SDK (`from mcp.server import Server`) | ASSENTE | Pre-existing — SDK non installato in CI; test_mcp_tools_v2.py già rotto prima di Wave 0 |

## Deliverable 4: Nyquist Test Scaffold (55 stub)

**Risultato:** 10 file di test stub creati (+ `test_mcp_integration_modify.py`) + 2 fixture data file.

**Distribuzione per wave:**

| Wave | File | Stubs | Requisiti coperti |
|------|------|-------|-------------------|
| Wave 1 | test_mcp_handlers_market.py | 5 | R1, R2 |
| Wave 1 | test_mcp_bar_source.py | 5 | D-D1 |
| Wave 1 | test_mcp_handlers_proposal.py | 2 | R3 |
| Wave 2 | test_mcp_handlers_backtest.py | 8 | MCP-01/02/03/cancel |
| Wave 2 | test_mcp_job_queue.py | 6 | D-A1/A3/A4 |
| Wave 2 | test_mcp_smoke_round_trip.py | 2 | SC#4 |
| Wave 3 | test_mcp_handlers_position.py | 8 | MCP-16/17 |
| Wave 3 | test_mcp_trail_daemon.py | 6 | D-B2 |
| Wave 3 | test_mcp_integration_modify.py | 1 @integration | SC#2 |
| Wave 4 | test_mcp_handlers_market.py | 6 | MCP-09/11/12/14 |
| Wave 4 | test_mcp_handlers_backtest.py | 3 | MCP-15 D-D2 |
| Wave 4 | test_mcp_legacy_compat.py | 3 | D-E1, tool count |
| **Totale** | | **55** | — |

**Fixture data:**
- `tests/fixtures/mcp/sample_position_trails.sql`: 3 seed row (2 active + 1 closed) per trail daemon tests
- `tests/fixtures/mcp/sample_trades_log.json`: 1 decision `live_42` EURUSD M15 BUY per replay_decision lookup

**Verifica raccolta:** `pytest --collect-only` → 55 tests raccolti. Tutti passano come `xfail` (exit 0).

## Deviazioni dal Piano

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Costanti MT5 stub valorizzate correttamente**
- **Found during:** Task 3
- **Issue:** Il piano diceva di aggiungere costanti alla lista `for attr in (...)` come le precedenti, ma il codice esistente impostava TUTTI gli attributi a `0` via `setattr(_stub, attr, 0)`. `TRADE_ACTION_SLTP == 0` (invece di 6) avrebbe causato assert failure in test Phase 6 D-B1.
- **Fix:** Sostituito con dict `_MT5_CONSTANTS` con valori reali per ciascuna costante.
- **Files modified:** tests/conftest.py
- **Commit:** 69a6626

### Pre-existing Gaps (non regressioni Wave 0)

**1. mcp SDK non installato in CI**
- `test_mcp_tools_v2.py` fallisce collection con `ModuleNotFoundError: No module named 'mcp.server'`.
- Verificato: falliva identicamente PRIMA della creazione di `mcp/` package.
- Wave 0 non peggiora la situazione. Wave 1 D-E1 crea `mcp/server.py` che risolverà il problema.

**2. baseline_decisions.parquet assente**
- `data/training/baseline_decisions.parquet` non esiste nel worktree.
- Wave 4 `replay_decision` dovrà degradare a live-only lookup (logica già prevista in D-D2).

**3. pytest.mark.integration non registrato**
- Warning non bloccante: `PytestUnknownMarkWarning`. Wave 3 aggiungerà il mark a `pytest.ini`.

## Threat Surface Scan

Nessuna nuova superficie di sicurezza rilevante non già nel threat model del piano:
- `mcp/errors.py`: solo costanti, nessun I/O.
- `backtest/ledger.py`: migration idempotente coperta da T-6-01-01.
- `tests/conftest.py`: stub senza secrets.

## Self-Check

- [x] backtest/ledger.py modificato con status DDL + migration + finalize_run
- [x] mcp/__init__.py creato
- [x] mcp/errors.py creato con 14 costanti + envelope()
- [x] tests/conftest.py aggiornato con costanti MT5 corrette
- [x] 10 file stub test creati (+ test_mcp_integration_modify.py)
- [x] tests/fixtures/mcp/sample_position_trails.sql creato
- [x] tests/fixtures/mcp/sample_trades_log.json creato
- [x] Commit 6a6eb21, 9ae0276, 69a6626, 3a63222 presenti

## Self-Check: PASSED
