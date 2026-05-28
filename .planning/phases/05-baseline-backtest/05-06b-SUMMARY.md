---
phase: 05-baseline-backtest
plan: 06b
subsystem: baseline-report-writer
tags: [phase-5, wave-2, report-writer, markdown, d-18, int-01, warning-12]
requires:
  - backtest.baseline.slice_worker.run_slice_3profiles (Plan 05-06a — produce result dict consumati qui)
  - backtest.metrics.BacktestMetrics (Plan 05-05 — sharpe/sortino/max_drawdown_pct/longest_dd_days)
provides:
  - backtest.baseline.report_writer.write_baseline_report (D-18 INT-01)
  - _row helper (formattazione riga tabella metrics)
  - _per_slice_section helper (mini-section per-slice D-18 part 3)
  - _TABLE_HEADER costante module-level
affects:
  - tests/test_baseline_report_writer.py (3 stub skip → 3 test attivi)
tech-stack:
  added: []
  patterns:
    - module puro: legge dict (result + meta) → produce file MD UTF-8
    - getattr(m, 'field', 0.0) per robustezza vs MagicMock + dataclass duck-type
    - sorted() deterministico (sym→tf→profile) per ordinamento tabella + per-slice
    - graceful handling FAILED/SKIPPED status (riga marker + error troncato 40 char)
    - timezone-aware datetime.now(timezone.utc) (no datetime.utcnow() deprecato Python 3.12+)
key-files:
  created:
    - backtest/baseline/report_writer.py
  modified:
    - tests/test_baseline_report_writer.py
decisions:
  - WARNING 12 fix risolto: appendix scrive cost_yaml_sha256/strategy_yaml_sha256/
    baseline_yaml_sha256 FULL 64-char; nessun truncation (no md5[:16]-style)
  - BLOCKER 2 hard/soft gates documentati nell'appendix (decision_count vs
    min_decisions_hard 1000 / target_decisions_soft 10000) — referenced da SC#3
  - Module puro: zero hard dep su Phase 1-4 (consume solo dict shape standardizzata)
    → testabile prima del completamento implementation chain (Phase 1-4 still pending)
  - Auto-fix Rule 1: datetime.utcnow() sostituito con datetime.now(timezone.utc)
    (DeprecationWarning in Python 3.12+)
metrics:
  duration: ~10 min (1 task atomico TDD: RED → GREEN, no REFACTOR)
  completed: 2026-05-08
  tasks: 1
  commits: 2
  files_created: 1
  files_modified: 1
  tests_unblocked: 3
  loc_added: 273 (report_writer 166 + tests 105 + 2 deletions skip stub)
---

# Phase 5 Plan 06b: Wave 2 Report Writer Summary

Wave 2 (parte report_writer — split B di WARNING 14 fix). Implementato il
Markdown report writer D-18 per il baseline backtest: `write_baseline_report(results, path, meta)`
compone `.planning/research/baseline-{date}.md` con schema rigido a 4 sezioni
(header + tabella 27-row + per-slice mini-section + appendix). WARNING 12
chiuso (sha256 FULL 64-char nelle 3 colonne audit). 3 test sbloccati.

## Files Created

| File | LOC | Funzioni pubbliche | Ruolo |
|------|-----|--------------------|-------|
| `backtest/baseline/report_writer.py` | 166 | `write_baseline_report` | Markdown report compose D-18 |

API pubblica primaria:

```python
def write_baseline_report(
    results: list[dict],   # 27 result dict da slice_worker.run_slice_3profiles
    out_path: Path,        # .planning/research/baseline-{date}.md
    meta: dict,            # cli_command, git_sha, *_sha256 (FULL 64), slippage_seed, ...
) -> None
```

Helpers privati (3):

| Nome | Ruolo |
|------|-------|
| `_TABLE_HEADER` | Costante module-level — header tabella 12-colonne D-18 part 2 |
| `_row(r)` | Formatta riga tabella metrics; gestisce FAILED/SKIPPED graceful |
| `_per_slice_section(r)` | Mini-section per-slice (link PNG + n_trades + n_drafts) |

## Files Modified

| File | Tipo | Δ | Ruolo |
|------|------|---|-------|
| `tests/test_baseline_report_writer.py` | REWRITE | +105/−27 | 3 stub skip → 3 test attivi |

## Tests Passing (3/3 nel target di plan)

```
tests/test_baseline_report_writer.py::test_report_structure              PASSED
tests/test_baseline_report_writer.py::test_report_contains_all_27_run_ids PASSED
tests/test_baseline_report_writer.py::test_report_appendix_hashes        PASSED

============================== 3 passed in 0.21s ==============================
```

Regressione su Phase 5 baseline package (sweep di sicurezza, 25 test):

```
tests/test_baseline_runner.py            4 passed
tests/test_baseline_report_writer.py     3 passed (NEW)
tests/test_baseline_dataset_writer.py    6 passed
tests/test_baseline_plot_writer.py       3 passed
tests/test_baseline_determinism.py       4 passed
tests/test_baseline_wal.py               5 passed

============================= 25 passed in 4.17s ==============================
```

Zero regressioni introdotte dal plan.

## D-18 Verification

### Schema Markdown rigido

`write_baseline_report` produce un file MD con 4 sezioni in ordine:

1. **`## Header`** (D-18 part 1)
   - Data run (timezone-aware UTC ISO)
   - Comando CLI (`meta["cli_command"]`)
   - git_sha (`meta["git_sha"]`)
   - Total wall-clock seconds (1 decimale)
   - Run completed: `n_ok/n_total (skipped: x, failed: y)`

2. **`## Slice Metrics`** (D-18 part 2 — tabella 27-row)
   - Header: `symbol | tf | profile | n_trades | sharpe | sortino | max_dd_pct | hit_rate | expectancy_pips | profit_factor | avg_R | longest_dd_days`
   - Una riga per result, ordinato deterministicamente (sym → tf → profile)
   - Result FAILED/SKIPPED: marker `FAILED (error[:40])` con `-` nelle colonne metrics

3. **`## Per-slice details`** (D-18 part 3 — mini-section)
   - Header `### {run_id}`
   - Equity curve link (Markdown image syntax)
   - n_trades + n_drafts emitted
   - Result FAILED: `Status: **FAILED** — {error}`

4. **`## Appendix`** (D-18 part 4 — audit + WARNING 12 fix)
   - `cost_yaml_sha256`: FULL 64-char hex
   - `strategy_yaml_sha256`: FULL 64-char hex
   - `baseline_yaml_sha256`: FULL 64-char hex
   - `slippage_seed`: int
   - `warm_up_bars`: dict tf → int (se presente)
   - `longest_lookback`: int
   - `decision_count` con hard/soft gates (BLOCKER 2 SC#3)

### Test 1: `test_report_structure`

Mock 27 result dict (3 sym × 3 tf × 3 profile, status=OK). Verifica che il
file MD contiene tutte e 4 le sezioni:

```python
assert "## Header" in text
assert "## Slice Metrics" in text
assert "## Per-slice details" in text
assert "## Appendix" in text
```

### Test 2: `test_report_contains_all_27_run_ids` (INT-01)

Genera 27 run_id distinti (`baseline_2026-05-08_{sym}_{tf}_{prof}`), verifica
che ognuno compaia almeno una volta nel file MD generato:

```python
assert len(results) == 27
for r in results:
    assert r["run_id"] in text, f"missing {r['run_id']} in report"
```

Pass: ogni run_id figura sia nella tabella `## Slice Metrics` (no, in realtà la
tabella usa solo sym/tf/profile) sia nella mini-section `### {run_id}` →
copertura garantita dalle sezioni per-slice.

### Test 3: `test_report_appendix_hashes` (WARNING 12 fix)

Verifica che i 3 hash sha256 figurano nel report con length esattamente 64:

```python
assert meta["cost_yaml_sha256"] in text
assert meta["strategy_yaml_sha256"] in text
assert meta["baseline_yaml_sha256"] in text
assert len(meta["cost_yaml_sha256"]) == 64
assert len(meta["strategy_yaml_sha256"]) == 64
assert len(meta["baseline_yaml_sha256"]) == 64
```

## WARNING 12 Closure

WARNING 12 (RESEARCH §Open Question 12) chiedeva: "audit trail integrity:
cost_yaml_sha256/strategy_yaml_sha256/baseline_yaml_sha256 vanno scritti
FULL 64-char nel report appendix, non md5[:16] truncato come legacy Phase 1
schema_runs."

Implementazione (riga 145-148 di `report_writer.py`):

```python
lines.append(f"- `cost_yaml_sha256`: `{meta.get('cost_yaml_sha256', 'n/a')}`")
lines.append(f"- `strategy_yaml_sha256`: `{meta.get('strategy_yaml_sha256', 'n/a')}`")
lines.append(f"- `baseline_yaml_sha256`: `{meta.get('baseline_yaml_sha256', 'n/a')}`")
```

Il valore `meta["*_sha256"]` arriva da `slice_worker._audit_update_run` (Plan
05-06a), che a sua volta lo riceve da `determinism.file_sha256()` (Plan 05-03):
`hashlib.sha256(...).hexdigest()` → 64 char hex.

Test verifica esplicitamente `len(meta["*_sha256"]) == 64` e `meta["*_sha256"]
in text` (substring match). Nessun truncation lungo il path → audit trail
integro per collision detection (probability practically 0).

Cross-reference Plan 05-06a 05-06a-SUMMARY.md §WARNING 12 closure:
"Le 3 colonne nuove `cost_yaml_sha256`, `strategy_yaml_sha256`,
`baseline_yaml_sha256` ricevono il digest hex completo (64 char)." → consistente
con quanto scritto qui nell'appendix del report.

## Acceptance Criteria

| Criterio (frontmatter PLAN) | Stato |
|------------------------------|-------|
| File `backtest/baseline/report_writer.py` esiste, ≥80 righe | OK (166 LOC) |
| `grep -c "def write_baseline_report"` == 1 | OK (1) |
| `grep -c "## Header"` ≥ 1 | OK (1) |
| `grep -c "## Appendix"` ≥ 1 | OK (1) |
| `grep -c "cost_yaml_sha256"` ≥ 1 (WARNING 12) | OK (4) |
| `grep -c "strategy_yaml_sha256"` ≥ 1 | OK (4) |
| `grep -c "baseline_yaml_sha256"` ≥ 1 | OK (4) |
| `pytest tests/test_baseline_report_writer.py -x` exit 0 (3 test pass) | OK (3 passed) |

Tutti gli acceptance criteria soddisfatti.

## Threat Model Compliance

| Threat | Disposition | Implementazione |
|--------|-------------|-----------------|
| T-05-16 InfoDisclosure (git_sha + paths) | accept | Report committato in `.planning/research/` (repo interno); paths `equity_path` sono relativi al repo root, no PII |
| T-05-26 Repudiation sha256 truncation | mitigate | Appendix scrive sha256 FULL 64-char (no `[:16]` truncation) → collision practically impossible per audit trail |

## Deviations from Plan

### 1. [Rule 1 - Bug] datetime.utcnow() deprecato in Python 3.12+

- **Found during:** Sub-task 1a, prima esecuzione `pytest tests/test_baseline_report_writer.py`.
- **Issue:** Il plan `<action>` usa `datetime.utcnow().isoformat()` per il
  campo "Data run" dell'header. Python 3.12 emette `DeprecationWarning`
  esplicito: "datetime.datetime.utcnow() is deprecated and scheduled for
  removal in a future version." (3 warning per i 3 test). Non rompe
  funzionalità ma sporca l'output e blocca eventuali `-W error::DeprecationWarning`.
- **Fix:** Sostituito con `datetime.now(timezone.utc).isoformat()` (timezone-aware,
  recommended replacement). Format ISO 8601 con offset `+00:00` invece del suffix
  `Z` manuale — equivalente semantico, more standard. Aggiunto `timezone` all'import.
- **Files modified:** `backtest/baseline/report_writer.py` (riga 23 import + riga 120 call site).
- **Commit:** `6618b40` (incluso nel commit GREEN, prima del commit a separato).
- **Nota:** Il test non valida il format della data, solo la struttura — quindi
  il fix è transparent ai 3 test esistenti.

## Authentication Gates

None — task interamente locale (file write + pytest, no network/API/secrets).

## Self-Check

**Files created (verified):**
- `backtest/baseline/report_writer.py` ✓ (166 LOC, write_baseline_report + 2 helpers + _TABLE_HEADER)

**Files modified (verified):**
- `tests/test_baseline_report_writer.py` ✓ (3 stub skip rimossi → 3 test attivi)

**Commits (verified via `git log --oneline -3`):**
- `6618b40` feat(05-06b): backtest/baseline/report_writer.py — D-18 Markdown report (INT-01, WARNING 12)
- `3098e29` test(05-06b): rimuovi skip + implementa 3 test report_writer (D-18, INT-01, WARNING 12)

**Smoke checks passed:**
- `pytest tests/test_baseline_report_writer.py -v` → 3 passed in 0.21s ✓
- `pytest tests/test_baseline_*.py` (sweep) → 25 passed in 4.17s, zero regressioni ✓
- `python -c "...; assert t.count('def write_baseline_report')==1"` ✓
- `python -c "...; assert t.count('## Header')>=1"` ✓
- `python -c "...; assert t.count('## Appendix')>=1"` ✓
- `python -c "...; assert t.count('cost_yaml_sha256')>=1"` (WARNING 12 fix) ✓

## Self-Check: PASSED

## TDD Gate Compliance

Plan 05-06b frontmatter `type: execute`, Task 1 ha `tdd="true"`. Sequenza
RED → GREEN verificata via commit log:

- **RED gate** (`3098e29`): `test(05-06b): rimuovi skip + implementa 3 test
  report_writer` — i 3 test esistono nel file ma falliscono al collection
  con `ModuleNotFoundError: No module named 'backtest.baseline.report_writer'`
  (verificato pre-commit con pytest output).
- **GREEN gate** (`6618b40`): `feat(05-06b): backtest/baseline/report_writer.py`
   — implementazione modulo target; i 3 test passano.

Nessuna fase REFACTOR necessaria — codice single-pass leggibile, helper
estratti già nella prima implementazione (`_row`, `_per_slice_section`,
`_TABLE_HEADER` module-level).

Auto-fix Rule 1 (datetime.utcnow → datetime.now(timezone.utc)) applicato
prima del commit GREEN, quindi il diff GREEN include il fix — nessun commit
separato necessario.

## D-18 / INT-01 / WARNING 12 Closure

| Item | Stato | Reference |
|------|-------|-----------|
| D-18 schema part 1 (Header) | green | `## Header` section in report_writer.py riga 117-126 |
| D-18 schema part 2 (Tabella 27-row) | green | `## Slice Metrics` + `_TABLE_HEADER` riga 30-34 |
| D-18 schema part 3 (Per-slice mini-section) | green | `## Per-slice details` + `_per_slice_section` riga 53-67 |
| D-18 schema part 4 (Appendix) | green | `## Appendix` riga 142-159 |
| INT-01 (tutti i 27 run_id citati) | green | `test_report_contains_all_27_run_ids` PASSED |
| WARNING 12 (sha256 full-64 in appendix) | green | `test_report_appendix_hashes` PASSED + length 64 assertion |

VALIDATION.md riga D-18 può essere spostata da `pending` → `green`.

## Phase 5 Wave 2 Closure (split fix WARNING 14)

WARNING 14 ha richiesto lo split di Plan 05-06 originale (~850 LOC) in due
plan atomici:

| Plan | Subsystem | LOC | Test sbloccati | Status |
|------|-----------|-----|----------------|--------|
| 05-06a | slice_worker | 791 (worker 279 + tests 512) | 6 (4 runner + 2 no_future_leakage) | DONE (commit 3b5f212) |
| 05-06b | report_writer | 273 (writer 166 + tests 105) | 3 (test_baseline_report_writer) | DONE (questo plan) |

Wave 2 chiusa: slice_worker + report_writer entrambi implementati e testati,
nessun blocker rimasto per Wave 3 (runner orchestrator).

## Next Wave

**Wave 3: 05-07** — `runner.py` (ProcessPoolExecutor orchestrator).
Consumerà i 2 moduli Wave 2 + tutti i moduli Wave 1:

```python
from backtest.baseline.slice_worker import run_slice_3profiles
from backtest.baseline.report_writer import write_baseline_report
from backtest.baseline.dataset_writer import finalize_parquet_shards
from backtest.baseline.wal_setup import enable_wal_mode

with ProcessPoolExecutor(max_workers=baseline_cfg.max_workers) as pool:
    futures = [
        pool.submit(run_slice_3profiles, sym, tf, ...)
        for sym in PAIRS for tf in TFS
    ]
    all_results = []
    for fut in as_completed(futures):
        all_results.extend(fut.result())  # 27 result totali
finalize_parquet_shards(out_dir)
meta = build_meta(...)  # cli_command, git_sha, *_sha256 full-64, ...
write_baseline_report(all_results, report_path, meta)
```

**Wave 4: 05-08** — preflight gate close (5° gate `Bar.tick_volume` probe-recalibration)
+ smoke E2E run con CSV reali + Phase 1-4 completate.

D-18 di `05-VALIDATION.md` può essere spostato da `pending` → `green`.
