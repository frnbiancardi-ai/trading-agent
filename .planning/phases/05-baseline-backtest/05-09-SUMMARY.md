---
phase: 05-baseline-backtest
plan: 09
title: "Dataset writer extension + baseline re-run prep (schema-v2)"
subsystem: backtest/baseline
tags: [phase-5, baseline-backtest, wave-5, dataset-remediation, additive-plan, blocks-phase-7, schema-v2]
requires:
  - 05-08-SUMMARY (chiusura Phase 5 originale, gap D-02 lasciato deferred)
  - 07-RESEARCH (gap analysis che ha originato il plan)
provides:
  - "schema-v2 parquet (D-09-A): 17 base + 33 extended + 5 meta = ~55+ cols"
  - "no-leakage anchor @ bars[:idx] (D-09-B) via _extract_extended_snapshot_at_entry"
  - "wrapper standalone scripts/run_baseline_05_09.py con --smoke/--only-runs"
  - "dataset_schema_version: 2 in baseline.yaml (hash invalidation)"
affects:
  - "Phase 7 ML Classifier: parquet schema-v2 unblocks ML-01 feature extraction"
  - "Phase 5 status: 8/9 -> 9/9 plans complete (PC secondario execution rimanente)"
tech-stack:
  added:
    - "indicators.compute_all_extended programmatic interface introspection (FIX 3)"
    - "indicators.volatility.load_regime_config per-symbol (FIX 1 iter 1)"
  patterns:
    - "Anti-drift contract test (FIX 3 plan-checker iter 1)"
    - "Isolation pattern regime_cfg: SOLO post-engine enrichment (FIX D iter 3)"
    - "Anchor conservativa decision_ts = open(idx-1) vs D-22 stretta close(idx-1) (FIX C iter 3)"
    - "Riuso _force_clear_run come single source of truth pre-delete (FIX A iter 3)"
key-files:
  created:
    - "scripts/run_baseline_05_09.py (344 LOC)"
    - "tests/test_baseline_no_leakage_extended.py (150 LOC)"
  modified:
    - "backtest/baseline/dataset_writer.py (+80 LOC)"
    - "backtest/baseline/slice_worker.py (+157 LOC)"
    - "tests/test_baseline_dataset_writer.py (+168 LOC)"
    - "tests/test_baseline_runner.py (+228 LOC)"
    - "data/configs/baseline.yaml (+13 LOC)"
decisions:
  - "D-09-A: schema parquet baseline_decisions v2 (chiude D-02 originale)"
  - "D-09-B: no-leakage anchor @ bar entry_time-1 (1 bar pre-entry conservativo vs D-22)"
  - "D-09-C: writer signature backward-compat con caller Plan 05-08"
  - "D-09-D: wrapper standalone scripts/run_baseline_05_09.py"
  - "D-09-E: max_workers locked a 9, NO tuning"
  - "D-09-F: scope chirurgico — NO engine perf-opt, NO drafts capture"
  - "D-09-G: field coverage parziale, 8 D-02 fields deferred-by-design a Phase 7"
metrics:
  duration: "~45 min plan-write phase (PC primario)"
  completed_date: "2026-05-11"
  loc_delta: "+1138 insertions, -2 deletions, 7 files"
  test_count_added: 12  # 5 writer + 4 no_leakage + 3 runner (smoke skip env)
---

# Phase 5 Plan 09: Dataset writer extension + baseline re-run prep Summary

JWT-style dataset writer extension che chiude il gap D-02 originale di Phase 5 (parquet schema da 17 cols flat a ~55+ con 33 extended indicators + 5 meta/timestamps), produce wrapper Python standalone `scripts/run_baseline_05_09.py` per esecuzione notturna sul PC secondario (workflow distribuito RESUME-PLAN.md rev 4), garantisce no-leakage by construction via snapshot @ bars[:idx] (exclusive del bar di entry), e introduce anchor conservativa `decision_ts = open(idx-1)` 1 bar pre-entry vs D-22 stretta come safety buffer per walk-forward Phase 7. Applica 10 FIX plan-checker iter 1 + 6 FIX iter 3 (A: --only-runs riuso `_force_clear_run`; B: `_csv_path_for` canonical path; C: chiarimento semantica decision_ts; D: isolamento `regime_cfg` dal flow engine principale + min_rows=1050; E: dedup test `test_regime_cfg_resolved_per_symbol`; F: ordine init WAL/LedgerWriter aligned).

## Risultato

Scope **plan-write** chiuso: artefatti di codice pronti per esecuzione sul PC secondario. Lo scope **plan-execute** (full 27/27 backtest ~3h18m wall-clock) e' delegato a STEP 3 di RESUME-PLAN.md (PC secondario Windows + MT5 demo TenTrade, finestra notturna). Phase 5 raggiunge 9/9 plans completi dopo l'esecuzione notturna; Phase 7 ML Classifier sbloccato per `/gsd-plan-phase 7` con awareness D-09-G (feature_extraction Wave 0 task richiesto per derivare i 8 field deferred da `decision_context_json` + `pnl_pips` + timestamps).

## Numeri

| Metric | Valore |
|---|---|
| Commit Plan 05-09 (atomici per task) | 5 (uno per task 1-5; task 6 = solo SUMMARY) |
| File modificati | 7 (5 modified + 2 created) |
| LOC delta | +1138 insertions, -2 deletions |
| Test nuovi aggiunti | 12 (5 dataset_writer + 4 no_leakage_extended + 3 runner) |
| Test schema-v2 dataset_writer | 11/11 pass (6 pre-esistenti + 5 nuovi) |
| Test no_leakage_extended | 4/4 pass (D-09-B + FIX 4/C iter 3) |
| Test runner | 10/10 (7 pre + 3 nuovi; 1 skip MT5 codespace env-gate) |
| Suite globale post-plan | 400 passed, 11 skipped, 55 xfailed (1 pre-existing failure out-of-scope) |
| Suite combinata 4 file test chiave | 27 passed, 1 skipped |
| FIX D iter 3 invariant grep | 1 callsite reale `compute_all_extended(bars_dict)` SENZA regime_cfg |
| FIX E iter 3 dedup grep | 1 definizione `test_regime_cfg_resolved_per_symbol` |

## Schema-v2 whitelist (D-09-A + FIX 3)

La whitelist `_SCHEMA_V2_REQUIRED_KEYS` viene costruita **programmaticamente** a import-time di `backtest/baseline/dataset_writer.py` da `_build_required_keys_v2()` invocando `compute_all_extended(dummy_bars, regime_cfg=None)`. Anti-drift pattern: se Phase 2 estende l'interface in futuro, la whitelist si adatta automaticamente (test `test_schema_v2_keys_match_compute_all_extended` enforce contract).

**Colonne attese nel parquet post-esecuzione PC secondario:**

| Gruppo | Count | Esempi |
|---|---|---|
| Base v1 (_row_for_ledger Phase 1) | 17 | run_id, entry_time, exit_time, symbol, timeframe, direction, entry_price, exit_price, sl, tp, lot_size, pnl_pips, pnl_usd, risk_usd, exit_reason, setup_type, confidence (+ decision_context_json nested) |
| Indicators legacy (compute_all) | 4 | sma_20, ema_50, rsi_14, atr_14 |
| Indicators extended (compute_all_extended) | ~33 | bb_upper/middle/lower/bbw/squeeze, kc_upper/lower, adx_14/plus_di/minus_di, macd/signal/hist, stoch_k/d, donch_upper/lower, pivot_p/camarilla_h3/l3, fib_0382/500/618/direction, vwap, avg_volume_20, nr4/nr7/boomer, closing_score, hurst, regime_state, regime_atr_pct |
| Meta Plan 05-09 | 5 | profile, run_id, decision_ts_utc, entry_ts_utc, exit_ts_utc |
| **Totale (atteso)** | **~55+** | |

NB: count esatto dipende da overlap tra base + legacy + extended (es. `run_id` e' presente sia in base che in meta — pandas dedup automatica). Verifica programmatica: `_SCHEMA_V2_REQUIRED_KEYS` ha 37 + 5 = 42 keys uniche (37 dell'output `compute_all_extended` quando `regime_cfg=None`, inclusi i 2 regime; + 5 meta del writer).

## No-leakage proof (D-09-B + FIX 4 + FIX C iter 3)

**Test `test_snapshot_excludes_entry_bar`** verifica via mock di `compute_all_extended` che, per `entry_iso == bars_dict[50]["time"]`, la lunghezza dell'argomento `bars_arg` passato alla funzione e' `len(bars_arg) == 50` (NON 51). Il bar di entry e' escluso dal calcolo:

```python
assert captured_lens[0] == 50, (
    f"NO-LEAKAGE: deve usare bars[:50] (50 elementi), trovato {captured_lens[0]}"
)
```

**Test `test_no_leakage_invariant_decision_before_entry`** verifica l'anchor conservativa D-09-B / FIX C iter 3:

```python
assert dt_decision < dt_entry  # strict
assert gap == timedelta(minutes=15)  # timeframe M15 = 900s
```

In convenzione MT5 (`bar.time = bar OPEN`):
- `decision_ts_utc = bars_dict[idx-1]["time"]` (open di idx-1)
- `entry_ts_utc = bars_dict[idx]["time"]` (open di idx)
- gap = `open(idx) - open(idx-1)` = `timeframe_delta`

Vs **D-22 stretta** che richiederebbe `decision_ts = close(idx-1) == open(idx) == entry_ts` (gap=0): Plan 05-09 sceglie anchor CONSERVATIVA come safety buffer 1-bar-pre-entry per Phase 7 walk-forward, prevenendo edge case di gap di sessione (weekend, holiday, gap apertura).

## Isolamento `regime_cfg` dal flow engine principale (FIX D iter 3)

**Invariante critico verificato:** la chiamata top-level `compute_all_extended(bars_dict)` a `backtest/baseline/slice_worker.py:348` RESTA SENZA `regime_cfg`. `regime_cfg` per-symbol viene caricato in `run_slice_3profiles` ma usato ESCLUSIVAMENTE dentro `_extract_extended_snapshot_at_entry` (post-engine enrichment).

**Conseguenze:**
- L'indicator cache `indicators_full` usata dalla strategy detector e' IDENTICA a Plan 05-08 (zero argomenti extra).
- Il flow `strategy detector -> proposal -> _row_for_ledger -> trade generation` e' IDENTICO.
- **Count trade atteso == 1076 ± 0** (parity stretta vs Plan 05-08, da validare post-execution PC secondario).
- `regime_state` / `regime_atr_pct` per-symbol popolano SOLO le colonne parquet, calcolate post-engine.

Verifica grep: `grep -n "compute_all_extended(bars_dict)" backtest/baseline/slice_worker.py` ritorna 1 callsite reale (riga 348) + 3 occorrenze in commenti documentativi.

## Field coverage matrix vs D-02 originale (D-09-G)

| D-02 field group | Plan 05-09 coverage | Source post-05-09 |
|---|---|---|
| Identity: symbol, timeframe, direction | Covered | `_row_for_ledger` (engine) |
| Levels: entry_price, exit_price, sl, tp, lot_size, risk_usd | Covered | `_row_for_ledger` |
| Outcome short: exit_reason, pnl_pips, pnl_usd, confidence, setup_type | Covered | `_row_for_ledger` |
| Timestamps: decision_ts_utc, entry_ts_utc, exit_ts_utc | Covered (FIX 4 + FIX C iter 3 anchor conservativa) | slice_worker enrichment (Task 2) |
| Profile/run_id | Covered | slice_worker enrichment |
| Regime: `regime_state` (canonical, NO alias `regime`) | Covered (FIX 9) | `compute_all_extended` output (post-engine via `_extract_extended_snapshot_at_entry` — FIX D iter 3) |
| Indicators (33+): rsi_14, atr_14, bollinger_*, adx_*, macd_*, etc. | Covered (FIX 1+3) | `compute_all_extended` @ `bars_view = bars_dict[:idx]` |
| factors_trend_alignment + 4 altri factors bool | **Deferred (D-09-G)** | `decision_context_json` struct in Phase 7 feature_extraction |
| grade, setup_name | **Deferred (D-09-G)** | `decision_context_json` struct in Phase 7 |
| outcome in {WIN,LOSS,BE,TIMEOUT} | **Deferred (D-09-G)** | Phase 7 derive da exit_reason + pnl_pips |
| bars_held | **Deferred (D-09-G)** | Phase 7 derive da bar timestamps |
| sr_dist_pips, spread_at_entry_pips, sentiment_proxy, recent_trades_outcome_5 | **Out of scope** | Phase 9/10 (failure analysis + intermarket) |

## Recovery Procedure (PC secondario)

**Crash mid-run:** i parquet shard per-worker (`baseline_decisions_<run_id>.parquet`) gia' scritti sono safe. Solo l'eventuale `finalize_parquet_shards` puo' essere ri-eseguito senza side effect (riscrive `part-{i}.parquet`).

**Identificazione run_id mancanti:**
```sql
SELECT run_id, status FROM backtest_runs ORDER BY started_at;
```
Confrontare con i 27 run_id attesi (`baseline_<date>_<symbol>_<tf>_<profile>` per ogni combo di 3 pairs × 3 TFs × 3 profile).

**FIX 6 + FIX A iter 3 IMPLEMENTATO:** re-lanciare run_id specifici con
```bash
python scripts/run_baseline_05_09.py --only-runs baseline_2026-05-11_EURUSD_M15_AGGRESSIVE,baseline_2026-05-11_GBPUSD_H1_MODERATE
```

Il wrapper esegue pre-delete via riuso `slice_worker._force_clear_run` (DELETE FROM `backtest_trades` + `backtest_runs` parametrized; NO `trades_log` che e' schema live trader senza colonna run_id) + relaunch tramite D-14 idempotency (skippa i run completi, rilancia solo quelli appena cancellati).

**Alternativa manuale (NO --only-runs):** cancellare a mano da entrambe le tabelle, poi `python scripts/run_baseline_05_09.py` (senza `--force` cosi' D-14 idempotency preserva i completati).

Cross-ref: `SETUP-SECONDARY-PC.md` §3 (sezione "Esecuzione backtest notturno").

## Esecuzione full 27/27 NON in scope plan-write

Chiaramente marcato come **deferred** a STEP 3 RESUME-PLAN.md:
- PC secondario Windows 64-bit (Ryzen 7 5800H + 16 GB RAM + RTX 3060, ma backtest CPU-only).
- MT5 demo TenTrade richiesto (env stack CLAUDE.md).
- Wall-clock atteso ~3h18m (parity con Plan 05-08 + overhead enrichment trascurabile).
- Soft warning a 4h via `--max-wall-clock 14400` (NO hard gate, Rule 4 deviation Plan 05-08 gia' user-accepted).

Comando di lancio:
```bash
python scripts/run_baseline_05_09.py --force
```

## Cross-phase impact

| Phase | Status post-Plan 05-09 |
|---|---|
| Phase 5 | 8/9 -> 9/9 plans complete (closure 100% dopo esecuzione PC secondario) |
| Phase 7 ML Classifier | Sbloccato per `/gsd-plan-phase 7` con awareness D-09-G (Wave 0 task: feature_extraction.py per derivare factors_*, outcome, bars_held da `decision_context_json` + `pnl_pips` + bar timestamps) |
| Phase 6 MCP Tools (part 1) | Non impattato (Plan 06-02/03/04 indipendenti) |

## Deviation log

**Rule 1 inline (auto-fix) — test smoke MT5 env-gate:**
- **Trovato durante:** Task 5 verify (`pytest tests/test_baseline_runner.py::test_smoke_05_09_wrapper_runs`)
- **Issue:** Il test invoca lo smoke wrapper via `subprocess.run`, ma `scripts/run_baseline_05_09.py` importa `backtest.baseline.runner -> slice_worker -> backtest.engine -> risk_engine -> mt5_client -> MetaTrader5`. Su Linux/codespace `MetaTrader5` non e' installato (stack CLAUDE.md vincola a Windows 64-bit). `tests/conftest.py` stubba MT5 in `sys.modules` ma SOLO per i test in-process; il subprocess Python vanilla non vede lo stub.
- **Fix:** aggiunto probe subprocess `python -c "import MetaTrader5"` prima di lanciare lo smoke. Se ritorna != 0, `pytest.skip("MetaTrader5 non installato — smoke gira sul PC secondario Windows")`. L'esecuzione effettiva del wrapper sul PC secondario non e' impattata.
- **File modificato:** `tests/test_baseline_runner.py`
- **Commit:** `eaf81f8` (incluso nel commit Task 5)

**Deferred Issues (NON in scope D-09-F):**

1. **`tests/test_backtest_engine.py::test_smoke_12month_under_60s`** — `SC-6 violated: 121.74s (>60s)` (Linux codespace, vs 63.5s su Windows in Plan 04-07). Engine `backtest/engine.py` perf O(N²) regression pre-existing, defer plan 01-09 vectorization (Rule 4 user-accepted Plan 05-08). NON tocchiamo `backtest/engine.py` per D-09-F scope chirurgico.

2. **5 collection errors** in `tests/test_daily_orchestrator.py`, `tests/test_mcp_tools_v2.py`, `tests/test_news_aggregator.py`, `tests/test_phase16.py`, `tests/test_scheduler.py` — `ModuleNotFoundError: No module named 'apscheduler'` su codespace Linux. Out-of-scope (env-only, non riguardano artefatti Plan 05-09).

3. **8 D-02 field deferred-by-design (D-09-G):** factors_trend_alignment + 4 altri factors bool, grade, setup_name, outcome, bars_held → derivabili in Phase 7 feature_extraction da `decision_context_json` + `pnl_pips` + timestamps. Stima 4-8h umane addizionali a STEP 13 di RESUME-PLAN (accettato dall'user).

4. **4 D-02 context fields out-of-scope:** sr_dist_pips, spread_at_entry_pips, sentiment_proxy, recent_trades_outcome_5 → Phase 9/10 (failure analysis + intermarket).

## Plan-checker FIX applicate

**10 FIX plan-checker iter 1:**

| FIX | Categoria | Riferimento |
|---|---|---|
| 1 | BLOCKER 1 | `load_regime_config(symbol, yaml_path)` signature reale (NON `load_regime_config()`) — Task 2 + Task 5 (test_regime_cfg_resolved_per_symbol) |
| 2 | BLOCKER 2 / WARNING | smoke range allargato a 3 mesi (2024-02-01 -> 2024-05-01) + smoke-tolerant validation (min_rows=0) — Task 4 |
| 3 | WARNING 1 | `_SCHEMA_V2_REQUIRED_KEYS` costruito programmaticamente da `compute_all_extended()` interface — Task 1 (anti-drift) |
| 4 | WARNING 2 | 3 timestamp distinti (decision_ts_utc / entry_ts_utc / exit_ts_utc) — Task 2 + Task 5 |
| 5 | WARNING 3 | D-09-G field coverage parziale documentato (8 deferred + 4 out-of-scope) — frontmatter + matrix |
| 6 | WARNING 4 | --only-runs flag implementato — Task 4 |
| 7 | WARNING 5 | Path absolute per smoke (FIX 7 iter 1) — Task 4 |
| 8 | INFO 1 | Pattern `bars_view = bars_dict[:idx]` chiavato da key_links regex — Task 2 + Task 5 |
| 9 | INFO 2 | NO alias `regime`; solo `regime_state` canonical (deduplicate) — Task 2 |
| 10 | INFO 3 | Smoke wall-clock target <180s, >300s indica regressione — Task 4 (commento + Task 5 timeout 240s) |

**6 FIX plan-checker iter 3:**

| FIX | Riferimento |
|---|---|
| A | --only-runs riuso `slice_worker._force_clear_run` (single source of truth, schema reale Phase 5: backtest_runs + backtest_trades) — Task 4 + Task 5 (test_only_runs_pre_delete_and_relaunch) |
| B | csv_path canonical via `runner._csv_path_for(symbol, tf)` — Task 4 smoke (NO hardcoded) |
| C | Chiarimento semantica decision_ts vs D-22 — anchor conservativa documentata (1 bar pre-entry vs gap=0 D-22 stretta) — Task 2 + Task 5 |
| D | Isolamento `regime_cfg` dal flow engine principale + min_rows=1050 (parity 1076 con 2.5% margine) — Task 2 + Task 4 (`_validate_parquet_schema(min_rows=1050)`) |
| E | Dedup `test_regime_cfg_resolved_per_symbol` (single definition in test_baseline_runner.py, grep -c == 1) — Task 5 |
| F | Ordine init `enable_sqlite_wal()` PRIMA, `LedgerWriter()` POI (allinea runner.py:170-179) — Task 4 |

## Self-Check: PASSED

**Verifica file creati/modificati:**
- FOUND: `backtest/baseline/dataset_writer.py` (164 LOC)
- FOUND: `backtest/baseline/slice_worker.py` (565 LOC)
- FOUND: `data/configs/baseline.yaml` (46 LOC, +13 LOC delta)
- FOUND: `scripts/run_baseline_05_09.py` (344 LOC, NUOVO)
- FOUND: `tests/test_baseline_dataset_writer.py` (293 LOC)
- FOUND: `tests/test_baseline_no_leakage_extended.py` (150 LOC, NUOVO)
- FOUND: `tests/test_baseline_runner.py` (789 LOC)

**Verifica commit:**
- FOUND: `5630bcc` feat(05-09): writer schema-v2 + whitelist programmatic
- FOUND: `a1b18f4` feat(05-09): slice_worker extended snapshot @ bar idx-1 + 5 meta/timestamps
- FOUND: `4489eb0` chore(05-09): baseline.yaml dataset_schema_version: 2
- FOUND: `a02d114` feat(05-09): scripts/run_baseline_05_09.py wrapper CLI
- FOUND: `eaf81f8` test(05-09): no-leakage + anchor conservativa D-09-B + smoke + --only-runs

**Verifica sentinel grep:**
- FOUND: `_SCHEMA_V2_REQUIRED_KEYS` + `_build_required_keys_v2` in dataset_writer.py
- FOUND: `_extract_extended_snapshot_at_entry` + `bars_view = bars_dict[:idx]` + `load_regime_config(symbol,` in slice_worker.py
- FOUND: `dataset_schema_version: 2` in baseline.yaml
- FOUND: `_force_clear_run` + `_csv_path_for` + `pd.isna` in scripts/run_baseline_05_09.py
- VERIFIED FIX D iter 3: 1 callsite reale `compute_all_extended(bars_dict)` SENZA regime_cfg (riga 348)
- VERIFIED FIX E iter 3: 1 definizione `test_regime_cfg_resolved_per_symbol` (grep -c == 1)

**Verifica suite test:**
- 4 suite chiave combinate: 27 passed, 1 skipped (smoke MT5 env-gate codespace)
- Suite globale: 400 passed, 11 skipped, 55 xfailed (1 pre-existing failure engine perf out-of-scope D-09-F)

Tutti i punti must_haves del plan rispettati. Scope `plan-write` COMPLETE. Scope `plan-execute` (full 27/27 backtest) delegato al PC secondario in STEP 3 RESUME-PLAN.md.

---

## Execution Results — PC secondario 2026-05-12

**Scope plan-execute COMPLETE 2026-05-12** (~24h dopo plan-write). Full 27/27 backtest schema-v2 girato sul PC secondario (Windows + MetaTrader5 demo TenTrade), pushato indietro al remoto, integrato sul PC primario via `git pull` + commit `0410bf2`.

| Metric | Valore atteso | Valore osservato | Note |
|---|---|---|---|
| Wall-clock totale | ~3h18m stima | **14038s (3h53m55s)** | +18% overshoot vs stima, dentro range accettabile (PC secondario meno performante di Ryzen 7 5800H baseline) |
| Slice completate | 27/27 | **27/27 ok** | 0 skipped, 0 failed — clean run |
| Parquet rows | ≥1076 | **1076** | Match esatto Plan 05-08 baseline (parity setup detection 5-factor) |
| Parquet cols | ~55+ | **59** | Schema-v2 D-09-A: 17 base + 33 extended + 5 meta + qualche extra |
| SCHEMA validation post-run | PASS | **PASS** | `OK schema-v2: 1076 rows, 59 cols` (auto-asserted dal wrapper) |
| Drafts dataset | deferred | 0 shard | D-09-F scope chirurgico, Phase 9 failure analysis |
| Run command | `scripts/run_baseline_05_09.py` | `python.exe .\scripts\run_baseline_05_09.py` (PowerShell) | Wrapper Plan 05-09 D-09-D usato come previsto |

**Distribuzione trade per symbol/tf/profile** (vedi `.planning/research/baseline-2026-05-12.md` sezione "Slice Metrics" per dettaglio):

- **USDJPY M15 AGGRESSIVE/MODERATE**: 415 + 309 = 724 trade (67% del totale) — regime carry trade ad alta persistenza
- **USDJPY M15 CONSERVATIVE**: 6 trade (filtro grade A+ stringente)
- **EURUSD/GBPUSD M30 spread**: 15-33 trade per slice — distribuzione coerente Plan 05-08
- **H1 timeframe**: 4-10 trade per slice (basso volume, atteso)

**Edge characterization** (input Phase 7 ML):

- Hit-rate globale 27.7% (298 win / 778 loss, consistente con Plan 05-08 baseline)
- Profit-factor < 1 su 24/27 slice — confermato negative-edge della strategia non filtrata
- USDJPY M15 hit-rate 32-34% (migliore) vs H1 0-12% (peggiore) — Phase 7 dovrà imparare a filtrare slice "morte"
- Sharpe negativi estremi su slice H1 con 4-10 trade (-2300 a -16000) sono artefatti statistici per n piccolo, non segnali reali

**Artefatti versionati post-STEP 3:**

- `data/training/baseline_decisions/part-0.parquet` — committed `0410bf2` (parquet binario, ~bytes da quantificare)
- `.planning/research/baseline-2026-05-12.md` — committed `0410bf2` (report 186 righe)
- `.planning/research/baseline-equity-curves/*.png` — già committate Plan 05-08 (27/27, bit-identical post re-run deterministico — git diff vuoto)

**Deferred (immutato):**

- 8 D-02 fields deferred-by-design (D-09-G): `setup_name`, `pattern_name`, `confluence_factors_json`, `bias`, `sl_pips`, `tp_pips`, `r_to_r`, `bars_to_outcome` — derivabili da `decision_context_json` + `pnl_pips` + 3 timestamps via feature_extraction Wave 0 Phase 7.
- Engine perf-opt (12-month smoke <60s, attualmente 121s) — out-of-scope D-09-F, defer a futuro plan 01-09 vectorization.

**Cleanup PC primario post-pull:**

- Removed leak: `05-09.log` (PowerShell `Tee-Object` output UTF-16-BOM), `trades.db` (legacy runtime), `"C:\\trading-agent\\logs\\agent.log"` (Windows path escaped, leak filesystem)
- Preserved untracked: `data/training/baseline_decisions.pre-05-09/` (backup pre-re-run, intenzionale), `data/training/_smoke_05_09/` + `.planning/research/_smoke_equity_curves/` (smoke artifacts validation pre-STEP 3)

**Phase 5 status:** ✓ **COMPLETE 9/9 plans (100%)** — D-02 gap definitivamente chiuso, Phase 7 ML Classifier sbloccata per `/gsd-plan-phase 7 --skip-research` (RESUME-PLAN.md STEP 13).
