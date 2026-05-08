---
phase: 05-baseline-backtest
plan: 06a
subsystem: baseline-slice-worker
tags: [phase-5, wave-2, slice-worker, idempotency, cache-reuse, audit-trail]
requires:
  - backtest.baseline.dataset_writer (Plan 05-04 — write_decisions_shard, write_drafts_shard)
  - backtest.baseline.plot_writer (Plan 05-04 — plot_equity_curve)
  - backtest.baseline.determinism (Plan 05-03 — seed_for_run_id, file_sha256)
  - backtest.baseline.wal_setup (Plan 05-03 — with_retry)
  - backtest.baseline.warmup (Plan 05-01 — longest_lookback_required, BLOCKER 3)
  - backtest.engine 4 kwargs Phase 5 (Plan 05-05 — indicators_full/risk_profile/timeout_bars/equity_initial)
  - backtest.broker virtual_positions + force_close (Plan 05-05)
  - backtest.metrics longest_dd_days (Plan 05-05)
provides:
  - backtest.baseline.slice_worker.run_slice_3profiles (entry-point per ProcessPoolExecutor)
  - _build_run_id, _run_id_exists, _force_clear_run, _audit_update_run, _git_sha helpers
  - PROFILES tuple costante module-level
affects:
  - tests/test_baseline_runner.py (4 stub skip → 4 test attivi)
  - tests/test_baseline_no_future_leakage.py (2 stub skip → 2 test attivi; 3/3 totali ora active)
tech-stack:
  added: []
  patterns:
    - matplotlib.use(Agg) ordering pre-import pyplot (Windows ProcessPool spawn compat)
    - functools.partial al posto di lambda per evitare truthiness bug WARNING 7
    - single-conn sqlite3.connect + busy_timeout interno (no with_retry wrapper) per DELETE atomic
    - per-worker shard write via write_decisions_shard + finalize cross-process
    - lazy import indicators (Phase 2 dependency) dentro la funzione worker
    - mock-heavy unit tests (BacktestEngine, load_bars, load_cost_model, compute_all_extended,
      write_*_shard, plot_equity_curve, _audit_update_run patchati) — safe da eseguire
      prima del completamento Phase 1-4
key-files:
  created:
    - backtest/baseline/slice_worker.py
  modified:
    - tests/test_baseline_runner.py
    - tests/test_baseline_no_future_leakage.py
decisions:
  - WARNING 7 fix risolto via functools.partial (NO lambda) → audit_call binding esplicito
  - WARNING 8 fix risolto: _force_clear_run usa single-connection sqlite3 con busy_timeout
    interno; NESSUN with_retry wrapper (riaprire conn rotturerebbe atomicity DELETE)
  - WARNING 12 fix risolto: cost_yaml_sha256/strategy_yaml_sha256/baseline_yaml_sha256
    scritti FULL 64-char nelle nuove colonne; legacy cost_yaml_hash[:16] mantenuto
  - load_cost_model signature reale è (symbol, entry_price, yaml_path) — slice_worker
    deduce entry_price da bars[0].close (1.0 fallback se bars vuoti); plan ipotizzava
    (symbol, costs_cfg) → adattato all'API reale di Phase 1
  - csv_path è kwarg opzionale del worker (runner Plan 05-07 lo passerà esplicito);
    default convenzione data/{symbol}_{tf}.csv come placeholder
  - test_entry_at_next_bar_open NON usa la fixture synthetic_bars (gap intra-bar troppo
    piccolo vs slippage_max — close[i] ≈ open[i+1]) → bar pair locale costruita ad-hoc
metrics:
  duration: ~25 min (1 task atomico, 3 sub-task: 1a slice_worker + 1b runner tests + 1c no_future_leakage tests)
  completed: 2026-05-08
  tasks: 1
  commits: 3
  files_created: 1
  files_modified: 2
  tests_unblocked: 6 (4 runner + 2 no_future_leakage)
  loc_added: 791 (slice_worker 279 + runner tests 418 + no_future_leakage tests 94)
---

# Phase 5 Plan 06a: Wave 2 Slice Worker Summary

Wave 2 (parte slice_worker — split A di WARNING 14 fix). Implementato il
worker per-slice `run_slice_3profiles` per ProcessPoolExecutor, con D-15
cache reuse (compute_all_extended UNA volta su 3 profile sequenziali),
D-14 idempotency (skip + force con DELETE), D-07 BLOCKER 3 warm-up
adattivo, audit trail Phase 5 sha256 full-64. 6 test totali sbloccati
(4 in test_baseline_runner + 2 in test_baseline_no_future_leakage).

## Files Created

| File | LOC | Funzioni pubbliche | Ruolo |
|------|-----|--------------------|-------|
| `backtest/baseline/slice_worker.py` | 279 | `run_slice_3profiles` | Worker entry per ProcessPoolExecutor (D-15 hybrid orchestration) |

API pubblica primaria:

```python
def run_slice_3profiles(
    symbol: str,
    tf: str,
    baseline_cfg,             # frozen dataclass — Plan 05-07 definisce loader
    costs_cfg_path: Path,
    strategy_cfg_path: Path,
    force: bool = False,
    ledger_db_path: Path | None = None,
    run_date: str | None = None,
    csv_path: Path | None = None,
) -> list[dict]
```

Helpers privati (5):

| Nome | Ruolo |
|------|-------|
| `_build_run_id` | D-13 schema `baseline_{date}_{symbol}_{tf}_{profile}` |
| `_run_id_exists` | D-14 idempotency check (read-only su backtest_runs) |
| `_force_clear_run` | D-14 force overwrite (DELETE backtest_trades + backtest_runs) |
| `_audit_update_run` | D-17 audit trail UPDATE (slippage_seed_effective + 3 sha256 full-64) |
| `_git_sha` | Best-effort `git rev-parse HEAD` per audit |

Costante module-level: `PROFILES = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")`.

## Files Modified

| File | Tipo | Δ | Ruolo |
|------|------|---|-------|
| `tests/test_baseline_runner.py` | REWRITE | +418/−44 | 4 stub skip → 4 test attivi (cache reuse, idempotency, perf, cost) |
| `tests/test_baseline_no_future_leakage.py` | MOD | +94/−8 | 2 stub skip → 2 test attivi (D-21 row ordering + D-22 entry semantics) |

## Tests Passing (7/7 nel target di plan)

```
tests/test_baseline_runner.py::test_indicator_cache_reused_across_profiles  PASSED
tests/test_baseline_runner.py::test_idempotency_skip_and_force              PASSED
tests/test_baseline_runner.py::test_single_slice_perf_budget                PASSED
tests/test_baseline_runner.py::test_cost_deduction                          PASSED
tests/test_baseline_no_future_leakage.py::test_indicator_full_slice_equals_recompute  PASSED
tests/test_baseline_no_future_leakage.py::test_decision_dataset_temporal_ordering     PASSED
tests/test_baseline_no_future_leakage.py::test_entry_at_next_bar_open                 PASSED

============================== 7 passed in 2.40s ==============================
```

Regressione su Phase 1+5 (sweep di sicurezza, 24 test selected post-deselect smoke):

```
tests/test_backtest_engine.py            6 passed
tests/test_baseline_dataset_writer.py    6 passed
tests/test_baseline_plot_writer.py       3 passed
tests/test_baseline_determinism.py       4 passed
tests/test_baseline_wal.py               5 passed

==================== 24 passed, 1 deselected in 4.96s =====================
```

Zero regressioni introdotte dal plan.

## D-07 / D-14 / D-15 Verification

### D-15 Hybrid Orchestration (cache reuse)

Test `test_indicator_cache_reused_across_profiles`:

1. Stub di `indicators` modulo via `sys.modules` con spy che traccia call_count.
2. Esegue `run_slice_3profiles("EURUSD", "M15", ...)` → loop 3 profile.
3. Assert `spy["calls"] == 1`: l'indicator cache è ricalcolata UNA SOLA volta
   per slice, riusata sui 3 profile sequenziali.

Codice worker che garantisce l'invariante (riga 169 di slice_worker.py):

```python
# 3. Indicator cache UNA volta per slice (D-15)
from indicators import compute_all_extended  # lazy Phase 2 dep
indicators_full = compute_all_extended(bars)

# ... più sotto, dentro `for profile in PROFILES:`
engine = BacktestEngine(
    ...,
    indicators_full=indicators_full,   # stesso reference 3 volte
    risk_profile=profile,
    ...
)
```

### D-14 Idempotency (skip + force)

Test `test_idempotency_skip_and_force`:

1. Pre-popola backtest_runs + backtest_trades con run_id MODERATE.
2. Run senza `force=False` → MODERATE risulta `SKIPPED`, gli altri 2 `OK`.
3. Verifica che la riga pre-esistente di backtest_trades NON sia stata cancellata.
4. Re-run con `force=True` → tutti e 3 i profile `OK`.
5. Verifica che la riga seedata di backtest_trades sia stata CANCELLATA
   (DELETE FROM backtest_trades WHERE run_id=? eseguito con --force).

Implementazione (riga 64-79 di slice_worker.py):

```python
def _force_clear_run(db_path: Path, run_id: str) -> None:
    # WARNING 8 fix: single connection, busy_timeout, no with_retry wrapper.
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("DELETE FROM backtest_trades WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM backtest_runs WHERE run_id=?", (run_id,))
        conn.commit()
    finally:
        conn.close()
```

### D-07 BLOCKER 3 (adaptive warm-up)

Implementazione (riga 156-167 di slice_worker.py):

```python
try:
    import yaml
    with open(strategy_cfg_path, encoding="utf-8") as f:
        strategy_cfg = yaml.safe_load(f) or {}
except Exception:
    strategy_cfg = {}
warm_up = max(
    baseline_cfg.warm_up_min_bars,
    longest_lookback_required(strategy_cfg),
)
bars = bars[warm_up:]
```

`longest_lookback_required` (Plan 05-01) parsa il YAML per chiavi
`ema_period`, `atr_period`, `bb_period`, ecc. e ritorna `max(values, fallback=200)`.
Test runner usa monkeypatch a 50 (così `bars[50:]` ha contenuto sufficiente
per il loop dei 3 profile su 250 fake bars).

## BLOCKER 3 + WARNING 7/8/12 Closures

### WARNING 7: lambda truthiness bug → functools.partial

**Pattern proibito (verificato grep `with_retry(lambda` count == 0):**

```python
# BUG (NON usato): se _do_audit() ritorna None, `None and conn.commit()` non commit-a.
with_retry(lambda: _do_audit() and conn.commit())
```

**Pattern adottato (slice_worker.py riga 244-248):**

```python
audit_call = functools.partial(
    _audit_update_run,
    ledger_db, run_id, seed_eff,
    cost_sha256, strategy_sha256, baseline_sha256, git,
)
with_retry(audit_call)
```

Il commit avviene DENTRO `_audit_update_run` (helper esplicito), garantendo
atomicity indipendentemente dal return value.

### WARNING 8: with_retry su _force_clear_run = atomicity broken

`with_retry` ri-esegue `fn()` su `OperationalError 'locked'`, MA ogni call apre
una NUOVA `sqlite3.connect`. Wrappare `_force_clear_run` con `with_retry`
significherebbe che il primo tentativo ha già parzialmente eseguito `DELETE`
(commit interno) prima del retry, lasciando lo state inconsistente.

**Fix:** `_force_clear_run` ha la propria `sqlite3.connect(db_path, timeout=30.0)`
con `PRAGMA busy_timeout=30000` interno → SQLite stesso attende 30s sul lock
prima di sollevare BUSY. Nessun bisogno di retry esterno.

Verifica grep: `with_retry(lambda: _force_clear_run` count == 0.

### WARNING 12: sha256 full-64 nelle nuove colonne backtest_runs

`_audit_update_run` (riga 89-117 di slice_worker.py):

```python
conn.execute(
    "UPDATE backtest_runs SET slippage_seed_effective=?, "
    "strategy_yaml_hash=?, baseline_yaml_hash=?, git_sha=?, "
    "cost_yaml_sha256=?, strategy_yaml_sha256=?, baseline_yaml_sha256=? "
    "WHERE run_id=?",
    (
        seed_eff,
        strategy_sha256[:16],   # legacy md5[:16]-style column (back-compat Phase 1)
        baseline_sha256[:16],
        git,
        cost_sha256,            # Phase 5 sha256 full-64 (WARNING 12)
        strategy_sha256,
        baseline_sha256,
        run_id,
    ),
)
```

Le 3 colonne nuove `cost_yaml_sha256`, `strategy_yaml_sha256`, `baseline_yaml_sha256`
ricevono il digest hex completo (64 char). Le legacy `strategy_yaml_hash`/
`baseline_yaml_hash` sono mantenute con format md5[:16]-style per backwards
compat con report writer Phase 1.

## Acceptance Criteria

| Criterio (frontmatter PLAN) | Stato |
|------------------------------|-------|
| File `backtest/baseline/slice_worker.py` esiste, ≥100 righe | OK (279 LOC) |
| `grep -c 'matplotlib.use("Agg")'` == 1 | OK (1) |
| `grep -c '_force_clear_run'` ≥ 2 | OK (3) |
| `grep -c '_run_id_exists'` ≥ 2 | OK (2) |
| `grep -c 'DELETE FROM backtest_trades'` ≥ 1 | OK (2) |
| `grep -c 'indicators_full'` ≥ 1 | OK (3) |
| `grep -c 'for profile in PROFILES'` == 1 | OK (1) |
| `grep -c 'longest_lookback_required'` ≥ 1 | OK (3) |
| `grep -c 'cost_yaml_sha256'` ≥ 1 | OK (1) |
| `grep -c 'strategy_yaml_sha256'` ≥ 1 | OK (1) |
| `grep -c 'baseline_yaml_sha256'` ≥ 1 | OK (1) |
| `grep -c 'with_retry(lambda'` == 0 (WARNING 7) | OK (0) |
| `grep -c 'with_retry(lambda: _force_clear_run'` == 0 (WARNING 8) | OK (0) |
| `pytest tests/test_baseline_runner.py -x` exit 0 | OK (4 passed) |
| `pytest tests/test_baseline_no_future_leakage.py -x` exit 0 | OK (3 passed; nessun skip) |

Tutti gli acceptance criteria soddisfatti.

## Mock Strategy for Phase 1-4 Pending

Il `phase1_dependency_risk` del frontmatter dichiara:

> slice_worker invoca BacktestEngine.run() (Phase 1 plan 01-05) +
> risk_engine.evaluate_trade + LedgerWriter (Phase 1 plan 01-05) +
> indicators.compute_all_extended (Phase 2) + strategy.evaluate_proposal_for_bar
> (Phase 4). I test di slice_worker MOCKANO TUTTO (test fast no-CSV no-engine),
> quindi sono safe da eseguire prima del completamento Phase 1-4.

**Tradotto in mock matrix per `_patch_worker_io` (test_baseline_runner.py):**

| Componente Phase 1-4 | Mock applicato | Tecnica |
|----------------------|----------------|---------|
| `backtest.loader.load_bars` | Lista `Bar` sintetica fissa (250 bar M15) | `monkeypatch.setattr(sw, "load_bars", ...)` |
| `backtest.costs.load_cost_model` | `SimpleNamespace` con campi `CostModel`-like | `monkeypatch.setattr(sw, "load_cost_model", ...)` |
| `backtest.engine.BacktestEngine` | Classe `_FakeEngine` con `.run()` deterministica | `monkeypatch.setattr(sw, "BacktestEngine", _FakeEngine)` |
| `backtest.ledger.LedgerWriter` | Classe `_FakeLedgerWriter` no-op | `monkeypatch.setattr(sw, "LedgerWriter", _FakeLedgerWriter)` |
| `indicators.compute_all_extended` | Funzione che traccia `call_count` e ritorna scalari fissi | Iniettato come modulo via `sys.modules["indicators"]` |
| `backtest.baseline.warmup.longest_lookback_required` | Costante 50 (warm-up basso → bars[50:] non vuoto) | `monkeypatch.setattr(sw, "longest_lookback_required", lambda: 50)` |
| `backtest.baseline.determinism.file_sha256` | Costante `"a" * 64` | `monkeypatch.setattr(sw, "file_sha256", ...)` |
| `_git_sha` | Costante `"deadbeef"` | `monkeypatch.setattr(sw, "_git_sha", ...)` |
| `write_decisions_shard` / `write_drafts_shard` | Touch dummy file + spy counter | `monkeypatch.setattr(sw, "write_*_shard", ...)` |
| `plot_equity_curve` | Touch dummy PNG + spy counter | `monkeypatch.setattr(sw, "plot_equity_curve", ...)` |
| `_audit_update_run` | Spy counter (no UPDATE su DB reale) | `monkeypatch.setattr(sw, "_audit_update_run", ...)` |

**SQLite reale**: l'unico componente NON mockato è la connessione SQLite per
`_run_id_exists` + `_force_clear_run` — usiamo `tmp_path / "trades.db"` con
schema seedato manualmente (`_seed_backtest_runs_table` helper). Permette di
verificare DELETE e SELECT su un DB reale ma temporaneo.

**End-to-end (E2E) verifica:** rimandata al Plan 05-08 smoke run con CSV
reali e Phase 1-4 completate.

## Threat Model Compliance

| Threat | Disposition | Implementazione |
|--------|-------------|-----------------|
| T-05-15 Tampering --force DELETE | mitigate | `DELETE WHERE run_id=?` parametrizzato (no SQL injection); `run_id` costruito da costanti hard-coded (`_build_run_id` riga 53-56) |
| T-05-17 DoS worker exception kills pool | mitigate | `try/except Exception` esplicito intorno a `engine.run()` + writer + plot (riga 195-235) → ritorna `status="FAILED"` invece di propagare |
| T-05-25 Tampering strategy.yaml warmup | mitigate | `longest_lookback_required` (Plan 05-01) usa whitelist di chiavi `_LOOKBACK_KEYS`, fallback `_DEFAULT_FALLBACK=200` se nessuna chiave parseable |

## Deviations from Plan

### 1. [Rule 1 - Bug] load_cost_model signature reale richiede entry_price

- **Found during:** Sub-task 1a, prima esecuzione test_baseline_runner.
- **Issue:** Il plan `<action>` di Task 1 ipotizza
  `load_cost_model(symbol, costs_cfg)` (2 args, dict-based). L'API reale di
  `backtest/costs.py:42` è `load_cost_model(symbol, entry_price, yaml_path)`
  (3 args), perché il pip-value di JPY pair richiede il prezzo runtime
  (`pip_value = 1000.0 / price`).
- **Fix:** Worker passa `bars[0].close` come `entry_price` hint (1.0 fallback
  se `bars` vuoto post-warmup). Signature del worker estesa con
  `costs_cfg_path: Path` invece di `costs_cfg: dict`.
- **Files modified:** `backtest/baseline/slice_worker.py` (riga 137, 178-179).
- **Commit:** `92859ab`.
- **Nota per runner Plan 05-07:** dovrà passare `costs_cfg_path` (Path al
  costs.yaml), non un dict pre-caricato.

### 2. [Rule 1 - Bug] synthetic_bars fixture inadatta per test_entry_at_next_bar_open

- **Found during:** Sub-task 1c, prima esecuzione del test.
- **Issue:** La fixture `synthetic_bars` (conftest.py riga 92-113) genera 100
  bar uptrend smooth con `close[i] ≈ open[i+1]` (gap intra-bar di 1 pip,
  uguale al pip_size 0.0001). Il test D-22 confronta `simulated_entry_price`
  contro `bar_current.close` con tolleranza `slippage_max=0.5*pip=0.00005`,
  ma nei synthetic la differenza tra `bar[i].close` e `bar[i+1].open` è
  ANCHE 0.00005 → il test non riesce a distinguere.
- **Fix:** Il test costruisce localmente 2 `Bar` ad-hoc con un gap di 1 pip
  pieno tra `bar_current.close=1.1003` e `bar_next.open=1.1010` → distanza
  0.0007 > slippage_max → assertion D-22 ben definita.
- **Files modified:** `tests/test_baseline_no_future_leakage.py` (rimossa
  dipendenza dalla fixture, costruzione locale dei 2 Bar).
- **Commit:** `d92c2f0`.
- **Nota:** Il test non è una regressione del semantic check D-22 — usa il
  pattern testuale "simulated_entry_price selezionato dal broker", che è
  il vero invariante (la scelta del prezzo deve venire da bar_next.open,
  non da bar_current.close). Per E2E reale del broker rimanderebbe a
  Plan 05-08.

### 3. [Rule 2 - Critical functionality] _audit_update_run estratto come helper module-level

- **Found during:** Sub-task 1a, applicazione WARNING 7 fix.
- **Issue:** Il plan `<action>` annida `_do_audit_update` come closure dentro
  il loop dei profile, con default-args per il binding. WARNING 7 chiede
  esplicitamente "no lambda con `and conn.commit()` truthiness". Una closure
  con default-args ha la stessa fragilità (closure-state difficile da
  testare; `and`-chain in caller resta possibile).
- **Fix:** Estratto `_audit_update_run` come funzione module-level (riga 89-117
  di slice_worker.py). Caller usa `functools.partial` (riga 244-248) per il
  binding esplicito dei 7 parametri → `with_retry(audit_call)` invoca la
  partial-bound con zero args. Niente lambda, niente truthiness chain.
  **Bonus per i test**: poter `monkeypatch.setattr(sw, "_audit_update_run", ...)`
  con un fake per verificare invocazione senza toccare il DB reale (vedi
  `_patch_worker_io` in test_baseline_runner.py).
- **Files modified:** `backtest/baseline/slice_worker.py`.
- **Commit:** `92859ab`.

### 4. [Rule 2 - Critical functionality] csv_path kwarg opzionale del worker

- **Found during:** Sub-task 1a, scrivendo i test.
- **Issue:** Il plan signature è
  `run_slice_3profiles(symbol, tf, baseline_cfg, costs_cfg, strategy_cfg, force)`
  — ma `load_bars` Phase 1 richiede `csv_path` esplicito (non lo deduce dal
  `symbol` da solo). Senza csv_path il worker non sa quale file leggere.
- **Fix:** Aggiunto `csv_path: Path | None = None` come kwarg opzionale; se
  `None`, fallback alla convention `data/{symbol}_{tf}.csv` (placeholder per
  runner Plan 05-07 che lo passerà esplicito). I test passano `tmp_path / "fake.csv"`
  (mai aperto perché `load_bars` è mockato).
- **Files modified:** `backtest/baseline/slice_worker.py` (riga 132).
- **Commit:** `92859ab`.
- **Nota per runner Plan 05-07:** dovrà costruire csv_path esplicito tipo
  `Path("data") / f"{symbol}_{tf}.csv"` o leggere il path da baseline.yaml.

## Authentication Gates

None — task interamente locale (file write, pytest, sqlite3 in-memory/tmp,
no network/API/secrets).

## Self-Check

**Files created (verified):**
- `backtest/baseline/slice_worker.py` ✓ (279 LOC, run_slice_3profiles + 5 helpers + PROFILES)

**Files modified (verified):**
- `tests/test_baseline_runner.py` ✓ (4 stub skip rimossi → 4 test attivi)
- `tests/test_baseline_no_future_leakage.py` ✓ (2 stub skip rimossi → 3 test attivi totali)

**Commits (verified via `git log --oneline -3`):**
- `92859ab` feat(05-06a): backtest/baseline/slice_worker.py — worker per ProcessPoolExecutor
- `1f521fc` test(05-06a): implementa 4 test slice_worker (D-14, D-15, perf, cost)
- `d92c2f0` test(05-06a): implementa test_decision_dataset_temporal_ordering + test_entry_at_next_bar_open

**Smoke checks passed:**
- `pytest tests/test_baseline_runner.py tests/test_baseline_no_future_leakage.py -v` → 7 passed in 2.40s ✓
- `pytest tests/test_backtest_engine.py tests/test_baseline_*.py --deselect smoke_12month_under_60s` → 24 passed in 4.96s (zero regressioni) ✓
- `python -c "from pathlib import Path; t=Path('backtest/baseline/slice_worker.py').read_text(encoding='utf-8'); assert t.count('matplotlib.use(\"Agg\")')==1"` ✓
- `python -c "... assert t.count('with_retry(lambda')==0"` (WARNING 7 fix) ✓
- `python -c "... assert t.count('_force_clear_run')>=2"` ✓
- `python -c "... assert t.count('cost_yaml_sha256')>=1"` (WARNING 12 fix) ✓

## Self-Check: PASSED

## TDD Gate Compliance

Plan 05-06a frontmatter `type: execute`, Task 1 ha `tdd="true"`. Stub
`@pytest.mark.skip` di Plan 05-02 era de-facto la fase RED (test esistenti
con `raise NotImplementedError`, fallirebbero se rimosso lo skip). Plan
05-06a ha eseguito la transizione GREEN (rimosso skip + body implementato +
test passa).

Sequenza di gate verificata:
- RED gate: `e3013d2 test(05-02): scaffold 7 stub test files + 1 active warmup test`
- GREEN gate (tre commit atomici per separazione responsabilità):
  - `92859ab feat(05-06a)`: implementazione modulo target
  - `1f521fc test(05-06a)`: implementazione 4 runner test (cache reuse + idempotency + perf + cost)
  - `d92c2f0 test(05-06a)`: implementazione 2 no_future_leakage test (D-21 row + D-22 entry)

Nessuna fase REFACTOR necessaria — codice single-pass leggibile, helper
estratti già nella prima implementazione (`_audit_update_run` module-level).

## Next Wave

**Wave 2 parte B: 05-06b** — `report_writer.py` (Markdown report compose dei
27 result dict). Consumerà:
- `results = run_slice_3profiles(...)` (lista di dict con keys
  `run_id, profile, status, metrics, n_trades, n_drafts, equity_path, ...`)
- Aggregazione 27-row tabella + per-slice mini-section + appendix audit hashes

**Wave 3: 05-07** — `runner.py` (ProcessPoolExecutor orchestrator).
Consumerà:
- `from backtest.baseline.slice_worker import run_slice_3profiles`
- `pool.submit(run_slice_3profiles, sym, tf, baseline_cfg, costs_cfg_path,
   strategy_cfg_path, force, db_path, run_date, csv_path)` × 9 task
- Finalize via `dataset_writer.finalize_parquet_shards(out_dir)` post-pool

**Wave 4: 05-08** — preflight gate close (5° gate `Bar.tick_volume` probe-recalibration)
+ smoke E2E run con CSV reali + Phase 1-4 completate.

D-07 BLOCKER 3 + D-14 + D-15 + D-21 row + D-22 di `05-VALIDATION.md` possono
essere spostati da `pending` → `green`.
