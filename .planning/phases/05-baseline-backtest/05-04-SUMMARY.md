---
phase: 05-baseline-backtest
plan: 04
subsystem: baseline-persistence-and-visualization
tags: [phase-5, wave-1, parquet, matplotlib, dataset-writer, plot-writer]
requires:
  - backtest.baseline package marker (Plan 05-01)
  - pyarrow 24.0.0 (Plan 05-01 requirements.txt)
  - matplotlib 3.10.9 (Plan 05-01 requirements.txt)
  - tests/test_baseline_dataset_writer.py stub (Plan 05-02)
  - tests/test_baseline_plot_writer.py stub (Plan 05-02)
provides:
  - backtest.baseline.dataset_writer (write_decisions_shard, write_drafts_shard, finalize_parquet_shards) -- D-01/D-02/D-03
  - backtest.baseline.plot_writer (plot_equity_curve) -- D-19/D-20
affects:
  - tests/test_baseline_dataset_writer.py (6 stub skip -> 6 test attivi)
  - tests/test_baseline_plot_writer.py (3 stub skip -> 3 test attivi)
tech-stack:
  added: []
  patterns:
    - "per-worker shard parquet snappy (no contention cross-process)"
    - "pyarrow.dataset.write_dataset directory layout (no full-load memory)"
    - "matplotlib.use(Agg) PRIMA di import pyplot (Windows ProcessPool spawn compat)"
    - "plt.close(fig) esplicito (T-05-10 handle leak mitigation)"
key-files:
  created:
    - backtest/baseline/dataset_writer.py
    - backtest/baseline/plot_writer.py
  modified:
    - tests/test_baseline_dataset_writer.py
    - tests/test_baseline_plot_writer.py
decisions:
  - D-01 layout: directory `<out_dir>/<prefix>/part-{i}.parquet` (CONTEXT update 2026-05-08, ROADMAP path letterale riletto come dataset name)
  - filtro `stat().st_size > 0` in finalize -- T-05-09 mitigation (shard zero-byte ignorati)
  - empty rows -> NO file scritto + warning log (path return value valido per chain consistency)
  - plt.close(fig) esplicito (passa il fig handle, non close global) -- T-05-10 multi-plot worker
metrics:
  duration: ~10 min (2 task atomici, sequential)
  completed: 2026-05-08
  tasks: 2
  commits: 2
  files_created: 2
  files_modified: 2
  tests_added_total: 9 (6 dataset_writer + 3 plot_writer)
  tests_active: 9
  tests_pending_unskip: 0
---

# Phase 5 Plan 04: Wave 1 Persistence + Visualization Summary

Wave 1 di Phase 5 baseline backtest, ramo persistence/visualization (parallelo a
05-03 determinism/wal). Implementati 2 moduli writer indipendenti dal motore
engine: parquet shard pattern (per-worker, finalize streaming via pyarrow.dataset)
+ matplotlib Agg headless plot. 9 test totali verdi (6 dataset_writer + 3
plot_writer). Tutti gli stub di Plan 05-02 sui due moduli sbloccati.

## Files Created

| File | LOC | Funzioni pubbliche | Ruolo |
|------|-----|--------------------|-------|
| `backtest/baseline/dataset_writer.py` | 84 | `write_decisions_shard`, `write_drafts_shard`, `finalize_parquet_shards` | D-01/D-02/D-03 parquet shard + concat |
| `backtest/baseline/plot_writer.py` | 59 | `plot_equity_curve` | D-19/D-20 equity PNG matplotlib Agg |

Totale: **2 file nuovi, 143 LOC** (entrambi sopra `min_lines` frontmatter -- 60 e 30).

## Files Modified

| File | Tipo | Δ | Ruolo |
|------|------|---|-------|
| `tests/test_baseline_dataset_writer.py` | REWRITE | +147/−21 | 6 stub skip -> 6 test attivi (round-trip, schema D-02, schema D-03, finalize concat, empty rows, WARNING 11 fix) |
| `tests/test_baseline_plot_writer.py` | REWRITE | +57/−27 | 3 stub skip -> 3 test attivi (PNG ≥1KB, structure ≥800x300, Agg enforcement) |

## Tests Passing (9/9)

```
tests/test_baseline_dataset_writer.py::test_decisions_shard_round_trip      PASSED
tests/test_baseline_dataset_writer.py::test_decisions_schema                PASSED
tests/test_baseline_dataset_writer.py::test_drafts_schema                   PASSED
tests/test_baseline_dataset_writer.py::test_finalize_concatenates_shards    PASSED
tests/test_baseline_dataset_writer.py::test_empty_rows_no_crash             PASSED
tests/test_baseline_dataset_writer.py::test_finalize_handles_empty_shards   PASSED
tests/test_baseline_plot_writer.py::test_plot_creates_png                   PASSED
tests/test_baseline_plot_writer.py::test_equity_png_structure               PASSED
tests/test_baseline_plot_writer.py::test_agg_backend_in_worker              PASSED

============================== 9 passed in 2.91s ==============================
```

NB: il `<output>` del plan dichiara "8 test pass" (5 dataset + 3 plot) ma la
matrice `<behavior>` in Task 1 elenca **6 test** (T1..T6 inclusi `test_empty_rows_no_crash`
+ `test_finalize_handles_empty_shards`) e lo stub Plan 05-02 conteneva 6 test --
totale reale **9 test** (6 + 3). Plan 02 SUMMARY (riga 169) registra esattamente
"6 stub" per `tests/test_baseline_dataset_writer.py`, quindi il numero "8" del
`<output>` è una svista interna del plan; la matrice esplicita `<behavior>` è
fonte autoritativa. Vedi Deviations §1.

## D-01 Layout Resolution (directory pattern)

Il pattern `D-01` originale di CONTEXT.md `data/training/baseline_decisions.parquet`
era ambiguo (single file vs directory dataset). User decision 2026-05-08 fissa
**directory layout** per entrambi i dataset:

```
data/training/
├── baseline_decisions/
│   ├── part-0.parquet
│   ├── part-1.parquet
│   └── ...
└── baseline_drafts/
    ├── part-0.parquet
    └── ...
```

`pyarrow.dataset.write_dataset` produce naturalmente directory output --
`baseline_decisions.parquet` letto come "dataset name" non "file extension".

**Phase 7 ML reader compatibility**: `pd.read_parquet("data/training/baseline_decisions/")`
funziona trasparentemente -- pandas + pyarrow gestiscono directory dataset
con stesso call di single-file. Nessun branch lato reader.

**Verifica nel test**: `test_finalize_concatenates_shards` crea 3 shard, chiama
`finalize_parquet_shards(tmp_path)`, verifica:
1. `tmp_path / "baseline_decisions"` è directory
2. `tmp_path.glob("baseline_decisions_*.parquet")` empty (shard sorgente cancellati)
3. `ds.dataset(target).to_table().to_pandas()` ritorna 6 row totali (3 × 2)

## Must-Haves Truths Verification

| Truth (frontmatter PLAN) | Verifica |
|--------------------------|----------|
| `write_decisions_shard(rows, run_id, dir)` crea file parquet snappy leggibile da pyarrow | OK -- `test_decisions_shard_round_trip` |
| `write_drafts_shard(rows, run_id, dir)` crea file parquet snappy leggibile da pyarrow | OK -- `test_drafts_schema` |
| `finalize_parquet_shards(out_dir)` concatena shard via `pyarrow.dataset.write_dataset` (directory output) | OK -- `test_finalize_concatenates_shards` (target dir + 6 row + shard sorgente cancellati) |
| `plot_equity_curve(equity_df, path)` crea PNG ≥1KB con 2 subplot (equity steelblue + drawdown indianred) | OK -- `test_plot_creates_png` (size > 1000 byte) |
| `matplotlib.get_backend() == 'Agg'` dopo import plot_writer | OK -- `test_agg_backend_in_worker` (case-insensitive `'agg'`) |

## Acceptance Criteria

### Task 1 -- `dataset_writer.py`

| Criterio | Stato |
|----------|-------|
| File esiste, ≥60 righe | OK (84 LOC) |
| `def write_decisions_shard` count == 1 | OK |
| `def write_drafts_shard` count == 1 | OK |
| `def finalize_parquet_shards` count == 1 | OK |
| `compression="snappy"` count ≥ 2 | OK (2) |
| `pyarrow.dataset` count ≥ 1 | OK (3) |
| `write_dataset` count ≥ 1 | OK (1) |
| `pytest tests/test_baseline_dataset_writer.py -x` exit 0 | OK (6 passed) |

### Task 2 -- `plot_writer.py`

| Criterio | Stato |
|----------|-------|
| File esiste, ≥30 righe | OK (59 LOC) |
| `matplotlib.use("Agg")` count == 1 | OK |
| `matplotlib.use("Agg")` PRIMA di `import matplotlib.pyplot` | OK (line 14 < line 19) |
| `fill_between` count == 1 | OK |
| `steelblue` count == 1 | OK (line 43) |
| `indianred` count == 1 | OK (line 50) |
| `plt.close` count == 1 | OK (line 58) |
| `pytest tests/test_baseline_plot_writer.py -x` exit 0 (3 test) | OK (3 passed) |

Tutti gli acceptance criteria soddisfatti.

## Threat Model Compliance

Disposizioni del plan onorate:

| Threat | Disposition | Implementazione |
|--------|-------------|-----------------|
| T-05-09 Tampering parquet shard files | mitigate | `finalize_parquet_shards` filtra `stat().st_size > 0` -- shard corrotti zero-byte ignorati prima di passarli a `pyarrow.dataset.dataset(...)` |
| T-05-10 DoS matplotlib figure leak | mitigate | `plt.close(fig)` esplicito dopo `fig.savefig` -- handle liberato per worker che generano N plot consecutivi |
| T-05-11 Information disclosure parquet path traversal | accept | `shard_dir / f"baseline_decisions_{run_id}.parquet"` -- `run_id` formato controllato D-13 (`baseline_<date>_<symbol>_<tf>_<profile>`, costanti hard-coded) |

## Deviations from Plan

### 1. [Rule 1 - Bug] Test count mismatch nel `<output>` plan vs `<behavior>` matrice

- **Found during:** Task 1 lettura plan + verifica stub Plan 05-02.
- **Issue:** Il `<output>` del plan dichiara "Tests Passing (8/8)" e il `<verification>` "5 dataset + 3 plot = 8 test totali". Ma il `<behavior>` di Task 1 elenca **6 test** (Test 1..6: round-trip, schema D-02, schema D-03, finalize, empty rows, WARNING 11 fix). Lo stub di Plan 05-02 contiene già **6** funzioni `def test_*` (verificato in `05-02-SUMMARY.md` riga 169 -- `test_baseline_dataset_writer.py: 6 stub`). Il numero "5" è una svista interna del plan; la matrice `<behavior>` è la fonte autoritativa (più dettagliata, ogni test ha rationale + parametri specifici).
- **Fix:** Implementati tutti e 6 i test dichiarati nella matrice `<behavior>` (no test omessi, no test extra). Totale reale 9 (6+3) vs "8" dichiarato nel `<output>`.
- **Files modified:** `tests/test_baseline_dataset_writer.py`.
- **Commit:** `6727042`.
- **Nota per planner:** se Plan 05-04 verrà rivisto, riconciliare il conteggio `<output>` "8/8" con la matrice esplicita "5 dataset_writer + 3 plot_writer + 6 stub iniziali" -> **9** è il numero corretto.

### 2. [Rule 2 - Critical functionality] noqa: E402 comments su import dopo `matplotlib.use("Agg")`

- **Found during:** Task 2 (potenziali pre-commit lint hook).
- **Issue:** Il pattern dell'`<action>` Task 2 fa `matplotlib.use("Agg")` PRIMA di `import logging`, `import pyplot`, `import pandas` -- corretto per il vincolo di ordering, ma viola PEP-8 E402 (module level import not at top). Senza `# noqa: E402` lint preventivi possono fallire (flake8/ruff E402 di default).
- **Fix:** Aggiunto `# noqa: E402  -- ordine import vincolato dal backend setup` su `import logging`, `import Path`, `import matplotlib.pyplot as plt`, `import pandas as pd`. Commento esplica la ragione dell'ordering (worker spawn Windows non eredita backend).
- **Files modified:** `backtest/baseline/plot_writer.py`.
- **Commit:** `52b6d70`.
- **Rationale:** funzionalità critica per il pattern Agg-first; senza `noqa` la pipeline CI può fallire su lint anche se il modulo è funzionalmente corretto.

## Authentication Gates

None -- task interamente locali (file write, parquet round-trip su tmp_path, matplotlib savefig, no network/API).

## Self-Check

**Files created (verified):**
- `backtest/baseline/dataset_writer.py` ✓ (84 LOC, 3 funzioni pubbliche)
- `backtest/baseline/plot_writer.py` ✓ (59 LOC, 1 funzione pubblica)

**Files modified (verified):**
- `tests/test_baseline_dataset_writer.py` ✓ (6 stub skip rimossi -> 6 test attivi)
- `tests/test_baseline_plot_writer.py` ✓ (3 stub skip rimossi -> 3 test attivi)

**Commits (verified via `git log --oneline -2`):**
- `6727042` feat(05-04): backtest/baseline/dataset_writer.py -- parquet shard + finalize (D-01/D-02/D-03)
- `52b6d70` feat(05-04): backtest/baseline/plot_writer.py -- equity PNG matplotlib Agg (D-19/D-20)

**Smoke checks passed:**
- `pytest tests/test_baseline_dataset_writer.py tests/test_baseline_plot_writer.py -v` → 9 passed in 2.91s ✓
- `grep -c "def write_decisions_shard\|def write_drafts_shard\|def finalize_parquet_shards" backtest/baseline/dataset_writer.py` → 3 ✓
- `grep -c 'compression="snappy"' backtest/baseline/dataset_writer.py` → 2 ✓
- `grep -c "matplotlib.use(\"Agg\")" backtest/baseline/plot_writer.py` → 1 ✓
- `grep -c "plt.close" backtest/baseline/plot_writer.py` → 1 ✓
- Ordering: `matplotlib.use("Agg")` line 14, `import matplotlib.pyplot` line 19 -> Agg first ✓

## Self-Check: PASSED

## Next Wave

**Wave 2: 05-05** -- engine extension + BacktestBroker (`force_close`, `virtual_positions`).
Consumerà:
- `write_decisions_shard(rows, run_id, dir)` per scrivere trade chiusi post-`engine.run()`
- `write_drafts_shard(rows, run_id, dir)` per scrivere tutti i Draft per-bar per-detector
- `plot_equity_curve(equity_series, png_path)` per generare equity curve PNG per ogni slice

**Wave 3: 05-06** -- runner orchestrator.
Consumerà:
- `finalize_parquet_shards(out_dir)` UNA VOLTA dal main process post-pool, per concatenare i 27 shard
- output directory layout `data/training/{baseline_decisions,baseline_drafts}/part-{i}.parquet`

`05-VALIDATION.md` rows INT-01 schema (D-02/D-03) + D-19/D-20 PNG/Agg possono
essere spostate da `pending` -> `green` (8/8 acceptance criteria task 1+2 OK,
9/9 test pass).
