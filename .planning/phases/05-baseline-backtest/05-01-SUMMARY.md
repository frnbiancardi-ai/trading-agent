---
phase: 05-baseline-backtest
plan: 01
subsystem: backtest-baseline-scaffolding
tags: [phase-5, wave-0, scaffolding, preflight, schema-migration, warmup-adaptive]
requires:
  - backtest.ledger (Phase 1 D-07 schema base)
  - data/configs/costs.yaml convention (Phase 1 D-05)
  - .venv Anaconda Python 3.12 (memory: project_python_env.md)
provides:
  - data/configs/baseline.yaml (D-15/D-17/D-19 orchestration knobs)
  - backtest.baseline package marker (Phase 5 subpackage)
  - backtest.baseline.warmup.longest_lookback_required (D-07 adaptive helper)
  - backtest.ledger schema esteso 7 colonne (D-17 audit trail + Warning 12 fix)
  - scripts/preflight_phase5.py (BLOCKER 6 fix — contract probe Phase 1-4)
affects:
  - backtest_runs SQLite schema (additive migration; backwards-compat preservato)
  - requirements.txt (+pyarrow +matplotlib unpinned)
tech-stack:
  added:
    - pyarrow 24.0.0 (parquet writer Wave 1+ — D-01 dataset directory)
    - matplotlib 3.10.9 (equity PNG headless via Agg — D-19/D-20)
  patterns:
    - frozen dataclass + load_<name>_config() YAML loader (Phase 1 costs.py)
    - CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN idempotente
    - inspect.signature + hasattr contract probe (no in-repo analog prior)
key-files:
  created:
    - data/configs/baseline.yaml
    - backtest/baseline/__init__.py
    - backtest/baseline/warmup.py
    - scripts/preflight_phase5.py
  modified:
    - requirements.txt
    - backtest/ledger.py
decisions:
  - D-07 adaptive warm-up implementato via fallback chain (Phase 2 hook → dict parse → 200)
  - D-15 max_workers=9 lockato in baseline.yaml
  - D-17 audit trail: 4 colonne originali + 3 sha256 full-64 (Warning 12) coesistono con legacy cost_yaml_hash md5[:16]
  - Threat T-05-03 mitigato: ALTER TABLE f-string usa solo costanti hard-coded (no SQLI vector)
  - Threat T-05-24 mitigato: parser DFS limitato a _LOOKBACK_KEYS whitelist
metrics:
  duration: ~25 min (4 task atomici, sequential)
  completed: 2026-05-08
  tasks: 4
  commits: 4
  files_created: 4
  files_modified: 2
---

# Phase 5 Plan 01: Wave 0 Scaffolding + Preflight Probe Summary

Wave 0 di Phase 5 baseline backtest: installate dependency parquet/matplotlib, creato config YAML lockato, scaffold del subpackage `backtest.baseline`, helper warm-up adattivo D-07, esteso schema `backtest_runs` con 7 colonne D-17 audit trail (4 originali + 3 sha256 full-64 fix Warning 12), e creato preflight contract probe per gate Wave 4.

## Files Modified

| File | Tipo | LOC | Ruolo |
|------|------|-----|-------|
| `requirements.txt` | MOD | +2 | append `pyarrow` + `matplotlib` (unpinned, repo convention) |
| `data/configs/baseline.yaml` | NEW | 25 | orchestration knobs D-15/D-17/D-19/D-20 lockati |
| `backtest/baseline/__init__.py` | NEW | 2 | package marker, `__all__ = ["run_baseline"]` advance |
| `backtest/baseline/warmup.py` | NEW | 95 | `longest_lookback_required(strategy_cfg)` D-07 adaptive |
| `backtest/ledger.py` | MOD | +44 | `_DDL_BACKTEST_RUNS` + `_BT_RUNS_COLUMNS` + `_migrate_backtest_runs` |
| `scripts/preflight_phase5.py` | NEW | 189 | contract probe Phase 1-4 (6 funzioni `_check_*`) |

Totale: **4 file nuovi + 2 modificati**. **355 LOC aggiunte**.

## Decisions Encoded

### D-07 — Adaptive warm-up helper (BLOCKER 3 fix)

`longest_lookback_required()` in `backtest/baseline/warmup.py` implementa fallback chain:

1. **Phase 2 hook** (lazy import): se `indicators.indicators_full.longest_lookback()` esiste e ritorna `>0` → usa quel valore. Try/except silent (modulo non ancora landed in Phase 5).
2. **Parsing dict** (DFS): walk ricorsivo su dict/list nested estraendo `int` da chiavi in `_LOOKBACK_KEYS` whitelist (`ema_period(s)`, `atr_period`, `bb_period`, `donchian_period`, `keltner_period`, `macd_slow`, `stoch_period`, `vwap_period`, `fib_lookback`, `hurst_window`, `longest_lookback`, `lookback`). Mitigation T-05-24: input malformati → fallback.
3. **Fallback 200**: log INFO, ritorna costante coerente con `baseline.yaml warm_up_min_bars=200`.

API tollerante: accetta `dict`, `Path`, `str`, `None`. Smoke verificato:

| Input | Output | Branch |
|-------|--------|--------|
| `None` | 200 | fallback |
| `{}` | 200 | fallback |
| `{'ema_periods':[20,50,200],'atr_period':14}` | 200 | parsing dict (max(20,50,200,14)) |
| `{'rsi_period':50,'adx_period':30}` | 50 | parsing dict |
| `{'indicators':{'donchian_period':300,'bb_period':20}}` | 300 | parsing nested DFS |

### D-15 — Orchestration knobs lockati

`data/configs/baseline.yaml` contiene tutti i parametri D-15/D-17/D-19/D-20:

```yaml
equity_initial_eur: 10000      # D-10
slippage_seed: 42              # D-17
timeout_bars: {M15: 96, M30: 96, H1: 120}   # D-05
warm_up_min_bars: 200          # D-07 floor
max_workers: 9                 # D-15 (3 symbol x 3 tf, 3 profile sequenziali per worker)
parquet_compression: snappy    # D-20
force_rerun: false             # D-14 (CLI --force override)
progress_bar: true             # tqdm
training_data_dir: "data/training"
report_dir: ".planning/research"
equity_curves_dir: ".planning/research/baseline-equity-curves"
```

### D-17 — Audit trail schema (Warning 12 fix applicata)

`backtest_runs` esteso con **7 colonne** (4 originali D-17 + 3 sha256 full-64):

| Colonna | Tipo | Scopo |
|---------|------|-------|
| `slippage_seed_effective` | INTEGER | per-run seed derivato (`sha256(run_id) & 0x7FFFFFFF`) |
| `strategy_yaml_hash` | TEXT | digest legacy (Phase 4 D-08 strategy.yaml) |
| `baseline_yaml_hash` | TEXT | digest legacy (D-15 baseline.yaml) |
| `git_sha` | TEXT | `git rev-parse HEAD` per audit trail |
| `cost_yaml_sha256` | TEXT | **NEW Warning 12 fix**: full-64 sha256 costs.yaml (coesiste con legacy `cost_yaml_hash` md5[:16]) |
| `strategy_yaml_sha256` | TEXT | **NEW Warning 12 fix**: full-64 sha256 strategy.yaml |
| `baseline_yaml_sha256` | TEXT | **NEW Warning 12 fix**: full-64 sha256 baseline.yaml |

`_BT_RUNS_COLUMNS` tuple esteso in ordine identico al DDL → `_INSERT_RUN_SQL` auto-aggiornato.

## Versions Installed

```
pyarrow 24.0.0
matplotlib 3.10.9
```

Smoke check `import pyarrow, matplotlib` → OK. Versioni unpinned in `requirements.txt` (repo convention: solo `MetaTrader5` e `pydantic` pinnati).

## Schema Migration

`_migrate_backtest_runs(conn)` in `backtest/ledger.py` esegue `ALTER TABLE ADD COLUMN` idempotente per le 7 colonne mancanti.

**Pattern verificato**:
- **Fresh DB**: `LedgerWriter(db)` su path nuovo → DDL crea tabella con tutte le 28 colonne (21 originali + 7 Phase 5).
- **Re-init idempotente**: re-instantiating `LedgerWriter` non duplica colonne (set di colonne identico al primo run).
- **Legacy DB migration**: DB pre-Phase-5 (21 colonne) → `LedgerWriter` rileva colonne mancanti via `PRAGMA table_info`, esegue 7 `ALTER TABLE ADD COLUMN`. Smoke verificato con DB sintetico in `tempfile.mkdtemp()`.

**Threat T-05-03 mitigation**: f-string in `ALTER TABLE ADD COLUMN {col} {typ}` riceve **solo** costanti hard-coded dalla lista `additions` interna — no user input vector → SQLI esclusa.

## Warmup Helper (D-07)

File: `backtest/baseline/warmup.py` (95 LOC, 1 funzione pubblica).

**Wiring atteso (Wave 2 — slice_worker)**:
```python
warm_up = max(baseline_cfg.warm_up_min_bars, longest_lookback_required(strategy_cfg))
bars = bars[warm_up:]
```

**Tolleranza**: l'helper non solleva mai eccezioni — qualunque input non-parseable cade su fallback 200 con log INFO. Adatto a chiamata in worker subprocess (no propagazione errori cross-process).

## Preflight Probe Status

`scripts/preflight_phase5.py` operativo. Run iniziale (Phase 1-4 chain ancora in formato pre-Phase-5):

```
=== Phase 5 Preflight Contract Probe ===
ROOT = C:\trading-agent

  OK    BacktestEngine.__init__ ha parametri base Phase 1
  FAIL  BacktestEngine.__init__ Phase 5 additions mancanti: {risk_profile, timeout_bars, equity_initial, indicators_full}
  FAIL  BacktestBroker non espone collezione di posizioni open (virtual_positions)
  FAIL  BacktestBroker.force_close MANCA — Plan 05-05 deve aggiungere il metodo
  OK    _BT_RUNS_COLUMNS contiene slippage_seed_effective (+6 altre colonne Phase 5)
  OK    BacktestMetrics.{sharpe,sortino,max_drawdown_pct,hit_rate,expectancy_usd,profit_factor,avg_r,total_pnl_usd}
  FAIL  BacktestMetrics manca campo: longest_dd_days
  OK    strategy.evaluate_proposal_for_bar callable=True
  OK    strategy.adapters.backtest.build_ctx_backtest callable=True
  OK    indicators.compute_all_extended callable=True
  FAIL  compute_all_extended shape probe: Bar.__init__() got an unexpected keyword argument 'tick_volume'

FAILED: 5 check non passati. Risolvi prima dello smoke run.
```

**Esito**: `exit 1` come atteso (frontmatter `phase1_dependency_risk` lo dichiara — Phase 1-4 chain incompleta per Wave 4).

I 5 FAIL sono **gate corretti per Plan 05-04/05-05/05-08**:

1. `BacktestEngine.__init__` Phase 5 additions → Plan 05-05 (engine kwargs `indicators_full`/`risk_profile`/`timeout_bars`/`equity_initial`)
2. `BacktestBroker.virtual_positions` → Plan 05-05 (broker exposure for force_close)
3. `BacktestBroker.force_close` → Plan 05-05 (timeout enforcement D-05)
4. `BacktestMetrics.longest_dd_days` → Plan 05-04 (metrics extension D-18)
5. `compute_all_extended` shape probe `Bar` kwarg mismatch → Plan 05-08 (probe-recalibration: il `Bar` shape vero di Phase 1 differisce da quello assunto dal probe; ricalibrare con introspezione `inspect.signature(Bar.__init__)` quando Phase 1-4 saranno landed)

Header, REPORT list, exit-code mechanism: tutti operativi → Wave 4 può consumare il gate quando `Plan 05-08` lo invoca.

## Acceptance Criteria

| Criterio | Stato |
|----------|-------|
| `python -c "import pyarrow"` exit 0 | ✓ |
| `python -c "import matplotlib"` exit 0 | ✓ |
| `requirements.txt` contiene `pyarrow` e `matplotlib` | ✓ |
| `data/configs/baseline.yaml` carica via `yaml.safe_load` | ✓ |
| `cfg['slippage_seed'] == 42`, `timeout_bars` 3 chiavi, `max_workers == 9`, `force_rerun: false` | ✓ |
| `import backtest.baseline` riuscito | ✓ |
| `longest_lookback_required(None) == 200`, `(dict ema_periods+atr) == 200` | ✓ |
| `_BT_RUNS_COLUMNS` contiene 7 nuove colonne | ✓ |
| `_migrate_backtest_runs` definita + invocata in `ensure_schema` | ✓ |
| Migrazione legacy DB verificata via `PRAGMA table_info` | ✓ |
| `scripts/preflight_phase5.py` stampa header + exit ≠ 0 quando chain incompleta | ✓ |

Tutti gli acceptance criteria soddisfatti.

## Deviations from Plan

**None — plan eseguito verbatim.**

Tutti gli artifact, gli helper, i contract probe richiesti sono stati creati con la signature/contract specificati in `<action>` di ogni task. Le 5 FAIL del preflight non sono deviation: il frontmatter `phase1_dependency_risk` le **prevede** esplicitamente, e il frontmatter `<must_haves>.truths` ammette esplicitamente `exit ≠ 0 con error chiaro` come comportamento valido del preflight su chain incompleta.

## Authentication Gates

None — task interamente locali (pip install, file write, sqlite3 in-memory).

## Self-Check

**Files created (verified):**
- `data/configs/baseline.yaml` ✓
- `backtest/baseline/__init__.py` ✓
- `backtest/baseline/warmup.py` ✓
- `scripts/preflight_phase5.py` ✓

**Files modified (verified):**
- `requirements.txt` ✓ (pyarrow + matplotlib presenti)
- `backtest/ledger.py` ✓ (`_BT_RUNS_COLUMNS` + `_migrate_backtest_runs` + `_DDL_BACKTEST_RUNS` extended)

**Commits (verified via `git log --oneline -4`):**
- `4bf3b25` chore(05-01): add pyarrow + matplotlib deps
- `fbd6124` feat(05-01): add data/configs/baseline.yaml
- `e9b6100` feat(05-01): scaffold backtest.baseline package + warmup + ledger schema D-17
- `f073d15` feat(05-01): scripts/preflight_phase5.py — contract probe Phase 1-4

**Smoke checks passed:**
- `import backtest.baseline; import backtest.baseline.warmup as W; import backtest.ledger as L` → OK
- All 7 Phase 5 columns in `L._BT_RUNS_COLUMNS` → OK
- `W.longest_lookback_required(None) == 200` → OK
- Migrazione SQLite legacy DB → 28 colonne post-migrate, idempotente → OK
- Preflight script run → header + 18 OK + 5 FAIL + exit 1 → OK (atteso)

## Self-Check: PASSED

## Next Wave

**Wave 1: 05-03 + 05-04 paralleli** (per ROADMAP / `<output>` del plan):
- **05-03**: dataset writer + parquet shard pattern (consuma `pyarrow` 24.0.0 e `BaselineConfig.parquet_compression`)
- **05-04**: metrics extension (`BacktestMetrics.longest_dd_days` per D-18 tabella; sblocca preflight check 4/5)

Wave 4 (smoke 05-08) **ancora bloccata** fino a completamento Phase 1-4 implementation chain (`phase1_dependency_risk` frontmatter). Preflight probe pronto a essere consumato come gate appena la chain sarà completa.
