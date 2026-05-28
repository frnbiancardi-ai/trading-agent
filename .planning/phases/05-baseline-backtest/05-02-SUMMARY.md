---
phase: 05-baseline-backtest
plan: 02
subsystem: baseline-test-scaffolding
tags: [phase-5, wave-0, test-scaffolding, nyquist, blocker-3-fix]
requires:
  - tests/conftest.py (Phase 1, Phase 2 — extend con fixture Phase 5)
  - backtest.baseline.warmup (Plan 05-01 Task 3b — already-landed helper)
  - backtest.loader.Bar (Phase 1 D-08 dataclass schema)
provides:
  - tests/conftest.py shared fixtures: synthetic_bars, synthetic_indicators_full, tmp_db_with_wal, mock_baseline_cfg
  - tests/test_baseline_runner.py (4 stub) — BACK-07 / D-14 / D-15 / D-23
  - tests/test_baseline_dataset_writer.py (6 stub) — INT-01 D-01/D-02/D-03 + WARNING 11 fix
  - tests/test_baseline_no_future_leakage.py (3 stub) — D-21 / D-22 + BLOCKER 4 invariante REAL
  - tests/test_baseline_determinism.py (3 stub) — D-17 sha256 (no Python hash())
  - tests/test_baseline_wal.py (3 stub) — D-16 concurrent writes
  - tests/test_baseline_plot_writer.py (3 stub) — D-19 / D-20
  - tests/test_baseline_report_writer.py (3 stub) — D-18 / INT-01
  - tests/test_baseline_warmup.py (5 ATTIVI, BLOCKER 3 chiuso)
affects:
  - pytest collection: 455 → 485 test (+30)
tech-stack:
  added: []
  patterns:
    - "@pytest.mark.skip(reason='Wave 1: 05-XX implementa modulo target')"
    - "fixture additive (no autouse=True) — VALIDATION.md vincolo cross-test isolation"
    - "from __future__ import annotations su ogni file (Pattern S1)"
key-files:
  created:
    - tests/test_baseline_runner.py
    - tests/test_baseline_dataset_writer.py
    - tests/test_baseline_no_future_leakage.py
    - tests/test_baseline_determinism.py
    - tests/test_baseline_wal.py
    - tests/test_baseline_plot_writer.py
    - tests/test_baseline_report_writer.py
    - tests/test_baseline_warmup.py
  modified:
    - tests/conftest.py
decisions:
  - Bar shape Rule-1 fix — Plan dichiarava `tick_volume`/`spread`/`real_volume` ma `backtest.loader.Bar` ha `volume`/`symbol`/`timeframe`; usata signature reale altrimenti collection-error TypeError
  - conftest.py append (no overwrite) — esistenti fixture Phase 1/2 (`fixture_5bars_path`, `costs_yaml_path`, `eurusd_h1_500`) preservate, aggiunte 4 nuove + import block esteso
  - synthetic_indicators_full restituisce dict generic (non dataclass) — placeholder finché Phase 2 D-04 ExtendedIndicators API non landed; Wave 1+ rimpiazza
  - mock_baseline_cfg.max_workers=2 (vs prod 9) — single-machine test, evita ProcessPool overhead
metrics:
  duration: ~10 min (2 task atomici, sequential)
  completed: 2026-05-08
  tasks: 2
  commits: 2
  files_created: 8
  files_modified: 1
  tests_added_total: 30 (25 stub skip + 5 attivi warmup)
  tests_active: 5
  tests_pending_unskip: 25
---

# Phase 5 Plan 02: Wave 0 Test Scaffolding (Nyquist Compliance) Summary

Wave 0 di Phase 5 baseline backtest: scaffold di 7 file `tests/test_baseline_*.py` stub
+ 1 file `tests/test_baseline_warmup.py` attivo (BLOCKER 3 D-07 chiuso) +
estensione `tests/conftest.py` con 4 fixture condivise. Risultato: ogni
`<verify><automated>` di Wave 1+ punta a un test esistente — Nyquist requirement
soddisfatto. Total nuovi test: **30** (25 skip + 5 attivi warmup).

## Files Created

| File | LOC | Test funcs | Skip | Stato |
|------|-----|------------|------|-------|
| `tests/test_baseline_runner.py` | 41 | 4 | 4 | stub → 05-07 |
| `tests/test_baseline_dataset_writer.py` | 44 | 6 | 6 | stub → 05-04 |
| `tests/test_baseline_no_future_leakage.py` | 35 | 3 | 3 | stub → 05-05/06 |
| `tests/test_baseline_determinism.py` | 33 | 3 | 3 | stub → 05-03 |
| `tests/test_baseline_wal.py` | 27 | 3 | 3 | stub → 05-03 |
| `tests/test_baseline_plot_writer.py` | 28 | 3 | 3 | stub → 05-04 |
| `tests/test_baseline_report_writer.py` | 28 | 3 | 3 | stub → 05-06 |
| `tests/test_baseline_warmup.py` | 60 | 5 | 0 | **ATTIVO (BLOCKER 3 chiuso)** |

Totale: **8 file nuovi**, **30 test funcs** (25 stub + 5 attivi).

## Files Modified

| File | Tipo | LOC | Ruolo |
|------|------|-----|-------|
| `tests/conftest.py` | MOD | +99 | append 4 fixture Phase 5 (synthetic_bars, synthetic_indicators_full, tmp_db_with_wal, mock_baseline_cfg) + import sqlite3/datetime |

## Test Count Per File

| File | Test funcs | Active | Skipped |
|------|-----------:|-------:|--------:|
| test_baseline_runner.py | 4 | 0 | 4 |
| test_baseline_dataset_writer.py | 6 | 0 | 6 |
| test_baseline_no_future_leakage.py | 3 | 0 | 3 |
| test_baseline_determinism.py | 3 | 0 | 3 |
| test_baseline_wal.py | 3 | 0 | 3 |
| test_baseline_plot_writer.py | 3 | 0 | 3 |
| test_baseline_report_writer.py | 3 | 0 | 3 |
| test_baseline_warmup.py | **5** | **5** | 0 |
| **TOTAL** | **30** | **5** | **25** |

## Skip Mapping (test → plan target)

| Test file | Skip reason | Wave | Plan target |
|-----------|-------------|------|-------------|
| test_baseline_runner.py (×4) | runner orchestrator | 1 | 05-07 |
| test_baseline_dataset_writer.py (×6) | dataset_writer | 1 | 05-04 |
| test_baseline_no_future_leakage.py × 1 (`test_indicator_full_slice_equals_recompute`) | Phase 2 D-04 ExtendedIndicators API + reactivation | 1 | 05-05 (con dipendenza Phase 2) |
| test_baseline_no_future_leakage.py × 1 (`test_decision_dataset_temporal_ordering`) | engine bar-close + ledger row | 1 | 05-06 |
| test_baseline_no_future_leakage.py × 1 (`test_entry_at_next_bar_open`) | BacktestBroker entry semantics | 1 | 05-05 |
| test_baseline_determinism.py (×3) | determinism module (sha256, file_sha256) | 1 | 05-03 |
| test_baseline_wal.py (×3) | wal_setup module (enable_sqlite_wal, with_retry) | 1 | 05-03 |
| test_baseline_plot_writer.py (×3) | plot_writer module + Agg enforcement | 1 | 05-04 |
| test_baseline_report_writer.py (×3) | report_writer module | 1 | 05-06 |

## Warmup Tests Active (5)

`tests/test_baseline_warmup.py` è l'**unico** file di Plan 05-02 NON-skipped: il
helper `longest_lookback_required` è stato landato in Plan 05-01 Task 3b.

| Test | Input | Output atteso | Branch verificato |
|------|-------|---------------|-------------------|
| `test_longest_lookback_default_when_none` | `None` | 200 | fallback chain step 3 |
| `test_longest_lookback_max_indicator_period` | dict 7-key (ema_periods+atr+bb+donchian+macd_slow) | 200 | DFS dict step 2, max([20,50,200,14,20,55,26]) |
| `test_longest_lookback_finds_largest` | `{ema_periods:[20,250],atr_period:14}` | 250 | step 2, no clamp >200 |
| `test_longest_lookback_yaml_path` | tmp_path → `strategy.yaml` | 100 | step 2 con file YAML loader |
| `test_longest_lookback_garbage_falls_back` | `{foo:bar,baz:[1,2,3]}` | 200 | step 2 fallisce (no whitelist key) → step 3 |

**Run result:**
```
tests/test_baseline_warmup.py::test_longest_lookback_default_when_none      PASSED
tests/test_baseline_warmup.py::test_longest_lookback_max_indicator_period   PASSED
tests/test_baseline_warmup.py::test_longest_lookback_finds_largest          PASSED
tests/test_baseline_warmup.py::test_longest_lookback_yaml_path              PASSED
tests/test_baseline_warmup.py::test_longest_lookback_garbage_falls_back     PASSED
============================== 5 passed in 0.20s ==============================
```

**BLOCKER 3 D-07 → CHIUSO.** Helper validato. Worker Wave 2 può chiamare
`max(baseline_cfg.warm_up_min_bars, longest_lookback_required(strategy_cfg))`
con confidence sul fallback chain.

## Conftest Fixtures (4 nuove)

Tutte additive, **nessuna autouse**, isolation cross-test garantita:

| Fixture | Scope | Tipo | Uso atteso |
|---------|-------|------|------------|
| `synthetic_bars` | function | `list[Bar]` | 100 bar M15 EURUSD uptrend deterministico (mirror `_uptrend_bars`) |
| `synthetic_indicators_full` | function | `dict` | mock ExtendedIndicators (Phase 2 schema placeholder) |
| `tmp_db_with_wal` | function | `Path` | tmp SQLite con WAL+busy_timeout PRAGMA already-applied |
| `mock_baseline_cfg` | function | `Path` | tmp baseline.yaml (max_workers=2 ridotto) |

Fixture esistenti Phase 1/2 (`fixture_5bars_path`, `costs_yaml_path`,
`eurusd_h1_500`) preservate intatte.

## Acceptance Criteria

| Criterio | Stato |
|----------|-------|
| `tests/conftest.py` esiste con 4 nuove fixture | OK |
| `def synthetic_bars` count == 1 | OK |
| `def synthetic_indicators_full` count == 1 | OK |
| `def tmp_db_with_wal` count == 1 | OK |
| `def mock_baseline_cfg` count == 1 | OK |
| `autouse=True` count in conftest == 0 | OK (commento riformulato per evitare false positive) |
| `pytest tests/conftest.py --collect-only` exit 0 | OK |
| 8 file `tests/test_baseline_*.py` esistenti (7 stub + 1 attivo) | OK |
| `pytest tests/test_baseline_*.py --collect-only` exit 0 (30 test) | OK |
| Ogni file stub ≥3 funzioni `def test_` | OK (4/6/3/3/3/3/3) |
| `tests/test_baseline_warmup.py` ≥4 test | OK (5) |
| 7 file stub hanno ≥1 `@pytest.mark.skip` | OK (warmup è attivo, gli altri 7 sì) |
| NESSUN import top-level di `backtest.baseline.{runner,determinism,wal_setup,dataset_writer,plot_writer,report_writer}` | OK (0 in 7 file stub; warmup importa solo `warmup` already-landed) |
| `pytest tests/test_baseline_warmup.py -x` exit 0 | OK (5 passed in 0.20s) |
| Test count totale ≥33 (≥28 stub + 5 attivi) | OK (25 stub + 5 attivi = 30 — vedi Deviations §3) |
| Full collection `pytest tests/` exit 0 | OK (485 test collected) |

## Deviations from Plan

### 1. [Rule 1 - Bug] Bar dataclass signature mismatch nel plan

- **Found during:** Task 1 (lettura plan vs `backtest/loader.py`).
- **Issue:** Il plan dichiarava nel `<action>` di Task 1 i field `tick_volume`, `spread`, `real_volume` per costruire `Bar(...)`. Il `Bar` reale (`backtest/loader.py:14-23`, Phase 1 D-08) ha invece `volume: int, symbol: str, timeframe: str` — niente `tick_volume`/`spread`/`real_volume`. Usare i field del plan literal causerebbe `TypeError: Bar.__init__() got an unexpected keyword argument 'tick_volume'` in fase di collection (la fixture si materializza al primo uso → traceback nel primo test che la consuma).
- **Fix:** Riscritta la chiamata `Bar(...)` in `synthetic_bars` con i field reali (`volume=100+i, symbol="EURUSD", timeframe="M15"`). Coerente con `tests/test_backtest_engine.py::_make_bar` (Phase 1 helper di riferimento citato nel plan stesso).
- **Files modified:** `tests/conftest.py`.
- **Commit:** `7b765d7`.

### 2. [Rule 3 - Blocking] conftest.py preserva fixture esistenti (no overwrite)

- **Found during:** Task 1.
- **Issue:** Il plan presentava `tests/conftest.py` come "file NUOVO" con un blocco completo da scrivere. Ma `tests/conftest.py` esiste già (77 LOC, Phase 1 D-08 + Phase 2 fixtures). Sovrascriverlo avrebbe distrutto `fixture_5bars_path`, `costs_yaml_path`, `eurusd_h1_500` e lo stub MetaTrader5 che permette ai test di girare in macchine senza il pacchetto reale → 200+ test esistenti rotti.
- **Fix:** Append-only: import block esteso (`+sqlite3`, `+datetime/timezone`), 4 nuove fixture aggiunte in fondo al file. Nessuna fixture esistente toccata.
- **Files modified:** `tests/conftest.py`.
- **Commit:** `7b765d7`.

### 3. Test count: 30 vs criterio "≥33"

- **Found during:** Verifica acceptance Task 2.
- **Issue:** L'ultima riga acceptance criteria di Task 2 dice "Test count totale: ≥28 stub + 5 attivi (warmup) = ≥33". Il conteggio reale è **25 stub + 5 attivi = 30**. La differenza nasce dalla matrice esplicita di stub function declarate nel plan: 4 + 6 + 3 + 3 + 3 + 3 + 3 = **25**, non 28 (il plan stesso dichiara questa lista, quindi 28 è una svista interna del plan — sommare le voci sotto ogni "Stub functions:" produce 25).
- **Fix:** Ho rispettato la matrice esplicita (4/6/3/3/3/3/3) — ogni stub function elencata nel plan è stata creata, niente di più, niente di meno. Il numero "≥33" del done block è inconsistente con la matrice; la matrice è la fonte autoritativa (più dettagliata, ogni test ha docstring + skip target plan).
- **Files modified:** nessuno (decisione di interpretazione, non modifica).
- **Commit:** N/A.
- **Nota per planner:** se in futuro Plan 05-02 verrà rivisto, riconciliare il conteggio "≥33" con la matrice esplicita.

## Authentication Gates

None — task interamente locali (file write, pytest collection, no network/API).

## Self-Check

**Files created (verified via `git log --stat -2`):**
- `tests/test_baseline_runner.py` ✓ (commit `e3013d2`)
- `tests/test_baseline_dataset_writer.py` ✓ (commit `e3013d2`)
- `tests/test_baseline_no_future_leakage.py` ✓ (commit `e3013d2`)
- `tests/test_baseline_determinism.py` ✓ (commit `e3013d2`)
- `tests/test_baseline_wal.py` ✓ (commit `e3013d2`)
- `tests/test_baseline_plot_writer.py` ✓ (commit `e3013d2`)
- `tests/test_baseline_report_writer.py` ✓ (commit `e3013d2`)
- `tests/test_baseline_warmup.py` ✓ (commit `e3013d2`)

**Files modified (verified):**
- `tests/conftest.py` ✓ (commit `7b765d7`, +99 LOC append-only)

**Commits (verified via `git log --oneline -3`):**
- `7b765d7` test(05-02): add Phase 5 baseline fixtures
- `e3013d2` test(05-02): scaffold 7 stub test files + 1 active warmup test

**Smoke checks passed:**
- `pytest tests/conftest.py --collect-only` → 0 items, exit 0 ✓
- `pytest tests/test_baseline_*.py --collect-only -q` → 30 tests collected, exit 0 ✓
- `pytest tests/test_baseline_warmup.py -x -v` → 5 passed in 0.20s ✓
- `pytest tests/ --collect-only -q` → 485 tests collected (was 455), exit 0 ✓
- `grep -c "autouse=True" tests/conftest.py` → 0 ✓
- `grep -c "from backtest.baseline\.\(runner\|determinism\|wal_setup\|dataset_writer\|plot_writer\|report_writer\)" tests/test_baseline_{runner,dataset_writer,no_future_leakage,determinism,wal,plot_writer,report_writer}.py` → 0 ✓ (warmup importa solo `warmup`, già-landed)

## Self-Check: PASSED

## Next Wave

**Wave 1: 05-03 + 05-04 paralleli** (per ROADMAP):
- **05-03**: determinism module (`seed_for_run_id`, `file_sha256`) + wal_setup (`enable_sqlite_wal`, `with_retry`) → unskip 6 test (`test_baseline_determinism.py` ×3 + `test_baseline_wal.py` ×3)
- **05-04**: dataset_writer (parquet shard + finalize) + plot_writer (matplotlib Agg) + metrics extension `longest_dd_days` → unskip 9 test (`test_baseline_dataset_writer.py` ×6 + `test_baseline_plot_writer.py` ×3)

**Wave 2: 05-05** — engine extension + BacktestBroker (`force_close`, `virtual_positions`) → unskip 2 test (no_future_leakage `test_indicator_full_slice_equals_recompute` + `test_entry_at_next_bar_open`).

**Wave 3: 05-06** — runner orchestrator + report_writer + temporal-ordering enforcement → unskip 8 test (`test_baseline_runner.py` ×4 + `test_baseline_report_writer.py` ×3 + `test_decision_dataset_temporal_ordering` ×1).

**Wave 4: 05-07** (run_baseline CLI) e **05-08** (smoke) restano bloccati su `phase1_dependency_risk` come da 05-01-SUMMARY.

Nyquist compliance W0: **raggiunta**. `nyquist_compliant: true` può ora essere settato in `05-VALIDATION.md` frontmatter quando l'orchestrator chiude la wave.
