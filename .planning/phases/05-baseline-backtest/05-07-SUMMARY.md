---
phase: 05-baseline-backtest
plan: 07
subsystem: baseline-runner-orchestrator
tags: [phase-5, wave-3, runner, cli, profiler, process-pool, d-15, d-16, d-18]
requires:
  - backtest.baseline.slice_worker.run_slice_3profiles (Plan 05-06a — worker entry)
  - backtest.baseline.report_writer.write_baseline_report (Plan 05-06b — D-18 MD writer)
  - backtest.baseline.dataset_writer.finalize_parquet_shards (Plan 05-04 — pyarrow.dataset)
  - backtest.baseline.wal_setup.enable_sqlite_wal (Plan 05-03 — D-16 WAL pragma)
  - backtest.baseline.determinism.file_sha256 (Plan 05-03 — full 64-char audit)
  - data/configs/baseline.yaml (Plan 05-01 — orchestration knobs)
provides:
  - backtest.baseline.runner.run_baseline (orchestrator main entry)
  - backtest.baseline.runner.BaselineConfig (frozen dataclass, pickle-safe)
  - backtest.baseline.runner.load_baseline_config (YAML loader pattern Phase 1)
  - backtest.baseline.runner._make_pool_executor (factory injection point per test)
  - scripts/run_baseline_backtest.py (CLI entry --force/--max-wall-clock/--no-time-gate)
  - scripts/profile_baseline_slice.py (perf profiler psutil RSS + wall_clock)
affects:
  - tests/test_baseline_runner.py (4 test 05-06a → 7 test totali, +3 orchestrator)
tech-stack:
  added: []
  patterns:
    - frozen dataclass YAML loader (clone Phase 1 D-05 load_cost_model)
    - ProcessPoolExecutor mp_context=spawn (Windows + Agg-safe matplotlib in worker)
    - as_completed + tqdm progress bar (opt-in via baseline.yaml progress_bar)
    - per-future try/except → status=FAILED nei result (no pool kill)
    - executor factory injection point (_make_pool_executor) per test thread-pool
    - module-level functools-style argparse main (no globals; sys.path bootstrap)
    - psutil graceful fallback (warning + sentinel 0.0 se non installato)
key-files:
  created:
    - backtest/baseline/runner.py
    - scripts/run_baseline_backtest.py
    - scripts/profile_baseline_slice.py
  modified:
    - tests/test_baseline_runner.py
decisions:
  - costs.yaml passato come Path (NON dict) al worker — allinea con
    slice_worker.load_cost_model signature reale 05-06a deviation #1
  - _make_pool_executor factory: punto di iniezione monkeypatchabile per i test
    (mock locali non pickleable da spawn ProcessPoolExecutor)
  - meta dict include decision_count = sum(n_trades) per BLOCKER 2 SC#3 hard/soft gates
  - hard gate SC#1 implementato a livello CLI (--max-wall-clock 1800s default,
    exit 2 se sforato), bypass via --no-time-gate solo per debug
  - psutil graceful fallback: il profiler stampa warning ma non fallisce se psutil mancante
metrics:
  duration: ~20 min (2 task atomici, 1 RED + 1 GREEN + 1 CLI)
  completed: 2026-05-08
  tasks: 2
  commits: 3
  files_created: 3
  files_modified: 1
  tests_added: 3
  loc_added: 519 (runner 225 + scripts 155 + tests 124 + 15 di mock fix)
---

# Phase 5 Plan 07: Wave 3 Runner Orchestrator + CLI Summary

Wave 3 chiude la pipeline baseline backtest end-to-end: implementato l'orchestrator
top-level `run_baseline` (ProcessPoolExecutor 9-task con `mp_context=spawn`),
il loader frozen `BaselineConfig`, il CLI entry point `scripts/run_baseline_backtest.py`
con hard gate BACK-07 SC#1 (--max-wall-clock 1800s), e il perf profiler single-slice
`scripts/profile_baseline_slice.py` (psutil RSS + wall_clock). 3 nuovi test
orchestrator (load_config + 27_runs + worker_failure) verdi accanto ai 4 di 05-06a
→ totale 7 passed in test_baseline_runner.py.

## Files Created

| File | LOC | Funzioni pubbliche | Ruolo |
|------|----:|---------------------|-------|
| `backtest/baseline/runner.py` | 225 | `run_baseline`, `BaselineConfig`, `load_baseline_config`, `_make_pool_executor` | Orchestrator hybrid D-15 ProcessPool 9-task + report writer post-pool |
| `scripts/run_baseline_backtest.py` | 84 | `main` | CLI entry --force/--max-wall-clock/--no-time-gate, hard gate SC#1 |
| `scripts/profile_baseline_slice.py` | 71 | `main` | Profiler single-slice psutil RSS delta + wall_clock |

API pubblica primaria (runner.py):

```python
def run_baseline(
    force: bool = False,
    baseline_yaml: Path | None = None,
    costs_yaml: Path | None = None,
    strategy_yaml: Path | None = None,
    ledger_db: Path | None = None,
) -> list[dict]
```

Returns: 27 result dict (9 sym/tf × 3 profile). Schema per result:
`run_id, symbol, timeframe, profile, status, metrics, n_trades, n_drafts, equity_path, error`.

Helper module-level (runner.py):

| Nome | Ruolo |
|------|-------|
| `BaselineConfig` | Frozen dataclass — pickle-safe per spawn ctx |
| `load_baseline_config` | YAML loader (pattern Phase 1 D-05 `load_cost_model`) |
| `_make_pool_executor` | Factory ProcessPoolExecutor → injection point per test (thread pool sostitutivo) |
| `_csv_path_for` | Convention `data/{symbol}_{tf}.csv` (placeholder Phase 1) |
| `_git_sha` | Best-effort `git rev-parse HEAD` (riusa pattern slice_worker) |

Costanti: `PAIRS = ("EURUSD", "GBPUSD", "USDJPY")`, `TFS = ("M15", "M30", "H1")`.

## Files Modified

| File | Tipo | Δ | Ruolo |
|------|------|---|-------|
| `tests/test_baseline_runner.py` | APPEND | +124/−1 | 3 nuovi test orchestrator (load_config, 27_runs, worker_failure); fix mock 1 riga (n_trades aggiunto al fake_worker test 2) |

## Tests Passing (7/7 target di plan)

```
tests/test_baseline_runner.py::test_indicator_cache_reused_across_profiles  PASSED  (05-06a)
tests/test_baseline_runner.py::test_idempotency_skip_and_force              PASSED  (05-06a)
tests/test_baseline_runner.py::test_single_slice_perf_budget                PASSED  (05-06a)
tests/test_baseline_runner.py::test_cost_deduction                          PASSED  (05-06a)
tests/test_baseline_runner.py::test_load_baseline_config                    PASSED  (NEW)
tests/test_baseline_runner.py::test_run_baseline_orchestrates_27_runs       PASSED  (NEW)
tests/test_baseline_runner.py::test_run_baseline_handles_worker_failure     PASSED  (NEW)

============================== 7 passed in 2.64s ==============================
```

Regressione su Phase 5 baseline package (sweep di sicurezza, 36 test):

```
tests/test_baseline_runner.py            7 passed (+3)
tests/test_baseline_report_writer.py     3 passed
tests/test_baseline_dataset_writer.py    6 passed
tests/test_baseline_plot_writer.py       3 passed
tests/test_baseline_determinism.py       4 passed
tests/test_baseline_wal.py               5 passed
tests/test_baseline_no_future_leakage.py 3 passed (3 active, 0 skip)
tests/test_baseline_warmup.py            5 passed

============================ 36 passed in 4.97s ==============================
```

Zero regressioni introdotte dal plan.

## CLI Surface

`scripts/run_baseline_backtest.py --help`:

```
usage: run_baseline_backtest.py [-h] [--force]
                                [--max-wall-clock MAX_WALL_CLOCK]
                                [--no-time-gate]

Phase 5 baseline backtest (27 run, 23.5y x 3 pair x 3 TF x 3 profile)

options:
  -h, --help            show this help message and exit
  --force               re-run anche se run_id esiste (overwrite ledger + parquet)
  --max-wall-clock MAX_WALL_CLOCK
                        max wall-clock seconds (default 1800 = 30 min). Exit
                        non-zero se wall > max (BACK-07 SC#1 hard gate).
  --no-time-gate        Disabilita il time-gate di --max-wall-clock (debug only).
```

Exit codes:

| Code | Significato |
|-----:|-------------|
| 0    | Run completata, wall_clock entro budget |
| 2    | Run completata ma wall_clock > --max-wall-clock (BACK-07 SC#1 violato) |
| !=0  | Errore non catturato (eccezione propagata da Python) |

Output stdout (sempre):

```
WALL_CLOCK_SECONDS={float}
RESULTS={n_ok}/{n_total} ok (skipped={n_skipped} failed={n_failed})
```

`scripts/profile_baseline_slice.py --help`:

```
usage: profile_baseline_slice.py [-h]
                                 symbol timeframe
                                 {CONSERVATIVE,MODERATE,AGGRESSIVE}

Profile single baseline slice
```

Output (esempio):

```
=== Profile EURUSD M15 MODERATE ===
wall_clock: 12.34s
rss_delta_mb: 187.3
status: OK
n_trades: 142
n_drafts: 240000
```

Se `psutil` non installato: warning su stdout + `rss_delta_mb: 0.0`. Tutto il resto funziona.

## D-15 / D-16 / D-18 Verification

### D-15 Hybrid Orchestration

Implementato in `run_baseline`:

```python
ctx = mp.get_context("spawn")
pool_cm = _make_pool_executor(baseline_cfg.max_workers, ctx)
with pool_cm as pool:
    futures = {
        pool.submit(
            run_slice_3profiles,
            symbol, tf, baseline_cfg, costs_path, strategy_path,
            force, ledger_path, run_date, _csv_path_for(symbol, tf),
        ): (symbol, tf)
        for symbol, tf in tasks   # 9 (PAIRS × TFS)
    }
    iterator = as_completed(futures)
    if baseline_cfg.progress_bar:
        iterator = tqdm(iterator, total=len(futures), desc="slice")
    for fut in iterator:
        try:
            all_results.extend(fut.result())
        except Exception as exc:
            ...  # status=FAILED, no pool kill
```

`mp_context=spawn` esplicito: vincolo Windows + `matplotlib.use("Agg")` di slice_worker
(spawn ricarica il modulo backend-Agg-safe).

### D-16 SQLite WAL

`enable_sqlite_wal(ledger_path)` invocato UNA volta dal main process **prima** di
spawn worker. WAL persiste cross-connection → 9 worker concorrenti supportati senza
`database is locked`. Test 1 verifica `wal_calls["n"] == 1`.

### D-18 Report MD

Post-pool, costruito `meta` dict con tutti i campi richiesti dall'appendix
(D-18 part 4 + WARNING 12 sha256 full-64), poi `write_baseline_report(all_results,
report_path, meta)` produce `.planning/research/baseline-{date}.md`.

`meta` keys popolati:

```python
{
    "cli_command": "python scripts/run_baseline_backtest.py" + (" --force" if force else ""),
    "git_sha": _git_sha(),
    "total_wall_clock_seconds": wall_clock,
    "cost_yaml_sha256": file_sha256(costs_path),       # WARNING 12 fix: full 64-char
    "strategy_yaml_sha256": file_sha256(strategy_path) if strategy_path.exists() else "n/a",
    "baseline_yaml_sha256": file_sha256(baseline_path),
    "slippage_seed": baseline_cfg.slippage_seed,
    "warm_up_bars": {tf: baseline_cfg.warm_up_min_bars for tf in TFS},
    "longest_lookback": baseline_cfg.warm_up_min_bars,
    "decision_count": sum(int(r.get("n_trades", 0) or 0) for r in all_results),
    "min_decisions_hard": 1000,         # BLOCKER 2 SC#3 hard gate
    "target_decisions_soft": 10000,     # BLOCKER 2 SC#3 soft target
}
```

Test 1 verifica `(tmp_path / f"baseline-{today}.md").exists()` post-run.

## Acceptance Criteria

| Task 1 — runner.py | Stato |
|---------------------|-------|
| File `backtest/baseline/runner.py` esiste, ≥120 righe | OK (225 LOC) |
| `grep -c "ProcessPoolExecutor"` ≥ 1 | OK (8) |
| `grep -c 'mp.get_context("spawn")'` == 1 | OK (1) |
| `grep -c "as_completed"` ≥ 1 | OK (4) |
| `grep -c "@dataclass(frozen=True)"` == 1 | OK (1) |
| `grep -c "def load_baseline_config"` == 1 | OK (1) |
| `grep -c "def run_baseline"` == 1 | OK (1) |
| `grep -c "finalize_parquet_shards"` ≥ 1 | OK (3) |
| `grep -c "write_baseline_report"` ≥ 1 | OK (3) |
| `grep -c "enable_sqlite_wal"` ≥ 1 | OK (2) |
| 3 nuovi test pass + i 4 di 05-06a ancora verdi | OK (7/7 passed in 2.64s) |

| Task 2 — CLI scripts | Stato |
|----------------------|-------|
| File `scripts/run_baseline_backtest.py` esiste | OK |
| File `scripts/profile_baseline_slice.py` esiste | OK |
| `python scripts\run_baseline_backtest.py --help` exit 0, contiene `--force`, `--max-wall-clock`, `--no-time-gate` | OK (3/3 flag) |
| `python scripts\profile_baseline_slice.py --help` exit 0, contiene `symbol`, `timeframe`, `profile` | OK (3/3 positional) |
| `grep -c "from backtest.baseline.runner import run_baseline"` == 1 | OK (1) |
| `grep -c "argparse"` ≥ 1 in run_baseline_backtest.py | OK (2) |
| `grep -c "psutil"` ≥ 1 in profile_baseline_slice.py | OK (7) |
| `grep -c "wall_clock"` ≥ 1 in profile_baseline_slice.py | OK (4) |
| `grep -c "ROOT = Path(__file__).resolve()"` == 1 | OK (1) |

Tutti i criteri soddisfatti.

## Threat Model Compliance

| Threat | Disposition | Implementazione |
|--------|-------------|-----------------|
| T-05-18 DoS ProcessPool resource exhaustion | mitigate | `max_workers` letto da baseline.yaml (default 9). Test usa `max_workers: 2` ridotto. CLI hard gate `--max-wall-clock 1800s` exit-2 se sforato. |
| T-05-19 Tampering --force overwrite ledger | accept | User-driven flag (D-14). Default `force=False`. Logging warning quando si entra in branch force. |
| T-05-20 InfoDisclosure profile_baseline_slice.py stdout | accept | Stampa solo wall_clock + RSS delta + status + n_trades — no secret/PII. |

## Deviations from Plan

### 1. [Rule 1 - Bug] costs.yaml passato come Path al worker, non come dict pre-caricato

- **Found during:** Task 1 sub-task 1a, lettura signature reale di
  `slice_worker.run_slice_3profiles`.
- **Issue:** Il plan `<action>` ipotizza che il runner pre-carichi `costs.yaml` in
  un dict (`costs_cfg = yaml.safe_load(...)`) e passi il dict al worker. Ma
  `slice_worker.run_slice_3profiles` richiede `costs_cfg_path: Path` (non dict)
  perché internamente chiama `load_cost_model(symbol, entry_price, yaml_path)`
  — l'API Phase 1 richiede il Path per dedurre il pip-value JPY runtime.
- **Fix:** Runner passa `costs_path` (Path) al worker; il pre-load del YAML
  serve solo per validazione fail-fast del parsing (`with open... yaml.safe_load`)
  prima di spawn worker. Coerente con 05-06a-SUMMARY.md deviation #1 nota
  esplicita: "runner Plan 05-07 dovrà passare costs_cfg_path (Path), non un dict".
- **Files modified:** `backtest/baseline/runner.py`.
- **Commit:** `d0fd041`.

### 2. [Rule 3 - Blocker] Mock locali non pickleable da ProcessPoolExecutor spawn

- **Found during:** Task 1 GREEN, prima esecuzione `test_run_baseline_handles_worker_failure`.
- **Issue:** Il plan suggerisce di mockare `run_slice_3profiles` via
  `monkeypatch.setattr("backtest.baseline.runner.run_slice_3profiles", fake_worker)`.
  Ma `pool.submit(run_slice_3profiles, ...)` **pickles la funzione** in
  spawn ctx — il replacement locale (closure dentro la funzione test) non è
  raggiungibile da un processo figlio fresco. AttributeError:
  `Can't get local object 'test_run_baseline_handles_worker_failure.<locals>.flaky_worker'`.
- **Fix:** Aggiunto un punto di iniezione `_make_pool_executor(max_workers, ctx)`
  module-level che default-a `ProcessPoolExecutor`. I test lo monkeypatchano per
  ritornare un `ThreadPoolExecutor` in-process — i mock locali sono visibili
  perché tutto gira nello stesso process. La sostituzione resta limitata ai test
  (codice produzione invariato a ProcessPoolExecutor).
- **Files modified:** `backtest/baseline/runner.py` (factory module-level),
  `tests/test_baseline_runner.py` (monkeypatch nei 2 test orchestrator).
- **Commit:** `d0fd041`.
- **Nota:** Pattern consigliato per testabilità senza compromettere la prod path.
  ThreadPoolExecutor preserva la stessa interface `submit`/`as_completed` →
  il body di `run_baseline` è identico in dev/test/prod.

### 3. [Rule 1 - Bug] flaky_worker mock incompleto crashava report_writer

- **Found during:** Task 1 GREEN, dopo fix #2.
- **Issue:** Il `flaky_worker` di `test_run_baseline_handles_worker_failure` ritorna
  result OK con shape minima `{run_id, symbol, timeframe, profile, status: "OK"}`.
  Manca `n_trades`/`n_drafts`. Quando `run_baseline` chiama
  `write_baseline_report(...)` post-pool, `_per_slice_section(r)` accede direttamente
  `r['n_trades']` per i result OK → KeyError.
- **Fix:** Aggiunto `n_trades: 0, n_drafts: 0, metrics: None, equity_path: ""`
  al mock (1 riga modificata in test_run_baseline_handles_worker_failure).
  Allinea con shape del fake_worker di test 1 e dei result OK reali del worker.
- **Files modified:** `tests/test_baseline_runner.py`.
- **Commit:** `d0fd041`.
- **Nota:** Considerato tracking come miglioramento defensive di `report_writer`
  (`_per_slice_section` userebbe `r.get("n_trades", 0)`), ma `report_writer` è già
  committato Plan 05-06b e i test 05-06b passano: il problema è esclusivo del
  mock minimale → fix nel test è la scelta corretta (no churn cross-plan).

## Authentication Gates

None — task interamente locale (file write, pytest, no network/API/secrets).

## Self-Check

**Files created (verified):**
- `backtest/baseline/runner.py` ✓ (225 LOC, 7 funzioni pubbliche/helper + BaselineConfig)
- `scripts/run_baseline_backtest.py` ✓ (84 LOC, --help risponde con 3 flag)
- `scripts/profile_baseline_slice.py` ✓ (71 LOC, --help risponde con 3 positional)

**Files modified (verified):**
- `tests/test_baseline_runner.py` ✓ (+124 LOC, 7 test totali)

**Commits (verified via `git log --oneline -3`):**
- `edc4629` test(05-07): aggiungi 3 test orchestrator runner [RED]
- `d0fd041` feat(05-07): backtest/baseline/runner.py — orchestrator ProcessPoolExecutor [GREEN]
- `71d23e9` feat(05-07): scripts/run_baseline_backtest.py + profile_baseline_slice.py — CLI

**Smoke checks passed:**
- `pytest tests/test_baseline_runner.py -v` → 7 passed in 2.64s ✓
- `pytest tests/test_baseline_*.py` (sweep) → 36 passed, zero regressioni ✓
- `python scripts/run_baseline_backtest.py --help` exit 0, contiene 3 flag ✓
- `python scripts/profile_baseline_slice.py --help` exit 0, contiene 3 positional ✓
- `python -c "...; assert t.count('ProcessPoolExecutor')>=1"` (8) ✓
- `python -c "...; assert t.count('mp.get_context(\"spawn\")')==1"` (1) ✓
- `python -c "...; assert t.count('@dataclass(frozen=True)')==1"` (1) ✓

## Self-Check: PASSED

## TDD Gate Compliance

Plan 05-07 frontmatter `type: execute`, Task 1 ha `tdd="true"`. Sequenza
RED → GREEN verificata via commit log:

- **RED gate** (`edc4629`): `test(05-07): aggiungi 3 test orchestrator runner
  (load_config + 27_runs + worker_failure) [RED]` — i 3 test esistono ma
  falliscono al collection con `ModuleNotFoundError: No module named
  'backtest.baseline.runner'` (verificato pre-commit con pytest output).
- **GREEN gate** (`d0fd041`): `feat(05-07): backtest/baseline/runner.py —
  orchestrator ... [GREEN]` — implementazione modulo target; i 3 test passano.

Task 2 (CLI scripts) NON ha `tdd="true"` — è un wrapper argparse + bootstrap
sys.path; verification automatica via `--help` exit 0 + grep counts. Nessun
RED gate richiesto.

Nessuna fase REFACTOR necessaria — codice single-pass leggibile, helper estratti
nella prima implementazione (`_make_pool_executor`, `_csv_path_for`, `_git_sha`).

## D-15 / D-16 / D-18 / BLOCKER 2 Closure

| Item | Stato | Reference |
|------|-------|-----------|
| D-15 hybrid orchestration runner-side | green | `run_baseline` ProcessPoolExecutor 9-task + executor factory |
| D-16 enable_sqlite_wal pre-pool main process | green | `enable_sqlite_wal(ledger_path)` riga 137 |
| D-18 meta dict tutti i campi popolati | green | meta dict riga 195-211 (sha256 full-64, decision_count, hard/soft gates) |
| BLOCKER 2 SC#3 hard/soft gates | green | `decision_count`, `min_decisions_hard=1000`, `target_decisions_soft=10000` in meta |
| BACK-07 SC#1 hard gate CLI | green | `--max-wall-clock 1800` exit 2 in `run_baseline_backtest.py` main |

D-15, D-16, D-18 di `05-VALIDATION.md` possono essere consolidati `green`.

## Next Wave

**Wave 4: 05-08** — preflight gate close (5° gate `Bar.tick_volume`
probe-recalibration) + smoke E2E run reale con CSV reali + Phase 1-4 completate.
Bloccato da:

1. Phase 1 BacktestEngine implementation completion (Phase 1 plan 01-05 ancora in planning)
2. Phase 2 indicators.compute_all_extended landing (Phase 2 plan in planning)
3. Phase 4 strategy.evaluate_proposal_for_bar (Phase 4 in planning)
4. CSV reali in `data/{symbol}_{tf}.csv`
5. Probe-recalibration di `scripts/preflight_phase5.py` per la nuova signature `Bar`
   (no `tick_volume` kwarg) — task atomico Plan 05-08

Wave 3 chiusa: end-to-end pipeline pronta. Plan 05-08 eseguirà la run reale
con tempo di parete reale e verifica wall-clock < 30 min su 8-core (BACK-07 SC#1).
