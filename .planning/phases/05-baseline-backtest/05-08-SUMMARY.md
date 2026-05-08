---
phase: 05-baseline-backtest
plan: 08
status: complete
date: 2026-05-08
type: execute
wave: 4
requirements: [BACK-07, INT-01]
deviations: 5
hard_gates:
  back07_sc1_wallclock_under_30min: FAIL  # 11922s vs 1800s target
  back07_sc3_decisions_min_1000: PASS     # 1076 trade
  int01_27_runs: PASS                     # 27/27 ok
---

# Plan 05-08 SUMMARY — Smoke E2E + Deliverable (Wave 4)

## Risultato

Smoke baseline backtest end-to-end completato. Pipeline Phase 5 funzionalmente
verde. Wall-clock viola hard gate SC#1 ma SC#3 (decisions ≥1000) e INT-01
(27/27 run) PASSANO. Phase 7 ML bootstrap NON bloccato.

## Numeri

| Metrica | Valore | Target | Status |
|---------|--------|--------|--------|
| Run completati | 27/27 | 27 | ✓ |
| Run failed/skip | 0/0 | 0 | ✓ |
| PNG equity curves | 27 | 27 | ✓ |
| Parquet decisions | `data/training/baseline_decisions/part-0.parquet` | finalized | ✓ |
| Trade ledger SQLite | **1076** | ≥1000 hard gate | ✓ |
| Wall-clock totale | **11922s (3h18m)** | <1800s (30m) | ✗ |
| Decision count vs soft target | 1076 / 10000 | 10000 | ⚠ ~10% |

### Distribuzione trade

- **Per profile:** AGGRESSIVE 540, MODERATE 448, CONSERVATIVE 88
- **Per symbol:** USDJPY 775, EURUSD 168, GBPUSD 133
- **Per timeframe:** M15 841, M30 170, H1 65
- **Hit rate globale:** 298 win / 778 loss = 27.7%
- **Total PnL:** -$8596.33 (strategia baseline negative-edge come atteso, è
  proprio il senso del filter ML in Phase 7)

## Commit applicati

| SHA | Messaggio |
|-----|-----------|
| `d880474` | fix(05-08): recalibra probe preflight (Bar shape + dict-of-scalars + ASCII) |
| `ea678ba` | fix(05-08): preflight + smoke run blocker fixes (Rule 2/3) |
| `61c1ff9` | feat(05-08): scope reduction 10y option B (BaselineConfig.date_start/date_end + slice_worker filter) |
| `4011a35` | fix(05-08): bridge D-21 contract gap (engine.run() output → slice_worker) |
| `<HEAD>`  | feat(05-08): smoke E2E 10y baseline complete (1076 trade, 27/27 PNG, deliverable) |

## Deviation registrate (5)

### Rule 3 (architectural blocker) — D-21 contract gap engine ↔ slice_worker

`engine.run()` (Phase 1, plan 01-05) ritorna `{run_id, trades, equity_curve,
bars_processed}`. slice_worker (Phase 5, plan 05-06a) assumeva chiavi
`decisions_rows` / `drafts_rows` / `metrics`. Plan 05-05 (extension engine)
NON ha esteso l'output dict come implicitamente richiesto dal contratto
05-06a.

Bridge applicato in `slice_worker.run_slice_3profiles`:
- `decisions_rows ← engine_result["trades"]`
- `drafts_rows ← []` (DEFERRED a futuro plan: engine non cattura proposte
  FORMING/NONE; richiede hook in `engine.run()` su `strategy.evaluate_proposal_for_bar`)
- `metrics ← compute_metrics(trades, tf)` (calcolo locale via
  `backtest/metrics.py`)

Senza questo fix tutti i 27 run sarebbero rimasti 0-row in parquet (anche
con 207 trade reali in SQLite ledger).

### Rule 3 (architectural blocker) — equity_curve format mismatch

`engine.run()` ritorna `equity_curve: list[float]` (solo balance values
post-evento). `plot_writer.plot_equity_curve` aspetta
`pd.DataFrame[timestamp, equity_eur, drawdown_pct]`.

Bridge: helper `_build_equity_dataframe(balances, trades, initial, bars)`
in slice_worker. Sintetizza:
- timestamps da `trade.exit_time` (fallback `entry_time`)
- drawdown via running peak su balances

### Rule 1 (auto-fix) — Bug #5 report_writer dict access

`report_writer._row_for_metrics_table` usava `getattr(m, ...)` su `m`
dict (asdict di BacktestMetrics). Restituiva sempre 0 default. Prima del
fix: tutto report con metric=0. Dopo: helper `_g(obj, key, default)` con
isinstance check dual-mode dict/dataclass — supporta anche mock dataclass
nei test legacy.

Report rigenerato a posteriori via `scripts/regen_baseline_report.py` (no
re-run engine 3h18m).

### Rule 2 (critical) — load_bars filter wiring per scope reduction

Plan 05-08 Option B (user decision: 10y vs full 23.5y). Aggiunti campi
`date_start` / `date_end` a `baseline.yaml` + `BaselineConfig` + passaggio
a `load_bars(csv_path, symbol, tf, date_start=..., date_end=...)` in
slice_worker. Range applicato PRIMA del warm_up slicing (engine O(N²)
non viene risolto, ma dataset più piccolo).

### Rule 4 (architectural — accepted) — wall-clock SC#1 violato

Engine Phase 1 ha bottleneck O(N²) o peggio (single-slice EURUSD M15
~78min su laptop ASUS 2014, 4-core Haswell). Anche su Nitro 5/Probook
i7-12gen lo speedup stimato è 2-3× → comunque fuori budget 30min.

**Decision (user-locked Option A):** chiudere Plan 05-08 con SC#1 fail
documentato, defer perf optimization a futuro plan 01-09 (engine
vectorization, indicator cache reuse intra-bar). Phase 7 ML bootstrap
e Phase 5 INT-01 deliverable NON dipendono da SC#1 — i parquet shard
+ ledger SQLite + PNG sono prodotti completi.

## File creati/modificati

**Nuovi:**
- `data/training/baseline_decisions/part-0.parquet` — dataset 1076 trade
- `.planning/research/baseline-2026-05-08.md` — report markdown D-18
  (rigenerato con metrics reali post Bug #5 fix)
- `.planning/research/baseline-equity-curves/{SYMBOL}_{TF}_{PROFILE}.png`
  — 27 equity curve PNG (D-19/D-20)
- `scripts/regen_baseline_report.py` — utility rigenera report da ledger
  (evita re-run engine post hot-fix)
- `logs/trades.db` — SQLite ledger committato per audit reproducibility

**Modificati:**
- `backtest/baseline/runner.py` — BaselineConfig.date_start/date_end +
  yaml loading + ledger schema pre-init + csv_path layout fix
- `backtest/baseline/slice_worker.py` — D-21 bridge + equity DataFrame
  helper + load_bars date filter
- `backtest/baseline/report_writer.py` — _g() dual-mode dict/dataclass
- `data/configs/baseline.yaml` — date_start/date_end (10y window)
- `tests/test_baseline_runner.py` — test_cost_deduction adattato
  contratto reale post-bridge

## Equity curves visual inspection

User ha aperto 2-3 PNG random. Tendenza generale: **equity verso 0** (NEGATIVE
trend). Coerente con strategia baseline senza filter ML — è il **dataset
input** per Phase 7, non un risultato finale.

Le 27 PNG sono in `.planning/research/baseline-equity-curves/`.

## Hard gate SC#3 (BACK-07) — analisi closure

| Hard gate | Threshold | Actual | Status |
|-----------|-----------|--------|--------|
| SC#1 wall-clock <30min | 1800s | 11922s | ✗ FAIL (Rule 4 accepted) |
| SC#3 decisions ≥1000 | 1000 | 1076 | ✓ PASS |
| INT-01 27 run | 27 | 27 | ✓ PASS |
| Soft target 10000 decisions | 10000 | 1076 | ⚠ ~11% (atteso senza
  detector D-04 + scope 10y vs 23.5y) |

## Phase 7 ML readiness

Dataset training pronto:
- `data/training/baseline_decisions/part-0.parquet` (1076 row, 19+ colonne
  — vedi `_row_for_ledger` schema engine.py)
- `logs/trades.db.backtest_trades` (audit duplicato)
- 27 PNG per qualitative inspection / debugging

Drafts dataset (FORMING/NONE) NON disponibile (deferred). Phase 7 può
partire con solo `decisions` (executed trades) per training v1; failure
analysis Phase 9 richiede drafts → futuro plan 05-09.

## Self-Check: PASSED (con deviation Rule 4 documentata)
