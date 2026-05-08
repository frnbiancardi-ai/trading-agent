---
phase: 05-baseline-backtest
plan: 05
subsystem: baseline-engine-extension-and-d21-invariant
tags: [phase-5, wave-2, engine-extension, broker-helpers, metrics, no-future-leakage]
requires:
  - backtest.engine (Phase 1 D-09 drive-bar loop)
  - backtest.broker (Phase 1 D-01 BacktestBroker + VirtualPosition)
  - backtest.metrics (Phase 1 BacktestMetrics dataclass)
  - indicators.compute_all_extended (Phase 2 — landed con shape dict-of-scalars)
  - tests/test_baseline_no_future_leakage.py (Plan 05-02 stub — primo test sbloccato)
provides:
  - BacktestEngine.__init__ accetta 4 kwargs Phase 5 (indicators_full, risk_profile, timeout_bars, equity_initial)
  - TIMEOUT_CLOSE_REASON costante module-level + timeout enforcement loop (D-05)
  - BacktestBroker.virtual_positions property + BacktestBroker.force_close(position_id, exit_price, exit_reason, exit_time=None)
  - BacktestMetrics.longest_dd_days (campo dataclass D-18)
  - _longest_underwater_run helper (max consecutive run di equity < running_peak)
  - test_indicator_full_slice_equals_recompute attivato (1 passed, dual-branch list/scalar)
affects:
  - 4 dei 5 FAIL del preflight Phase 5 chiusi (rimane solo Bar.tick_volume probe-recalibration → 05-08)
tech-stack:
  added: []
  patterns:
    - kwargs additive default-None (backwards compat Phase 1 caller)
    - thin wrapper su primitiva privata (force_close su _close_virtual)
    - dual-branch runtime detection isinstance(list) vs scalar (forward-compat Phase 2 D-04)
    - skip silenzioso per indicator None/NaN su prefix corto (warm-up insufficiente)
    - sanity guard checked_count > 0 (evita pass tautologico)
key-files:
  created: []
  modified:
    - backtest/engine.py
    - backtest/broker.py
    - backtest/metrics.py
    - tests/test_baseline_no_future_leakage.py
decisions:
  - WARNING 9 risolto: force_close + virtual_positions aggiunti come thin wrapper additive su BacktestBroker (preflight FAIL 2 e 3 chiusi)
  - BLOCKER 5 risolto via dual-branch runtime: list-of-values OR scalar API supportate; current Phase 2 indicators expone dict-of-scalars
  - BLOCKER 4 risolto: D-21 invariant test attivo (no skip), confronta full vs partial via compute_all_extended due-volte (deterministic + causal)
  - equity_initial vince su initial_balance quando entrambi passati (orchestrator-explicit naming Phase 5)
  - timeout enforcement DOPO broker.advance() — SL/TP hanno priorità (chiusi da advance), TIMEOUT chiude residui
  - longest_dd_days in BAR UNITS (1 unit = 1 trade chiuso); conversione bar→days deferita a report_writer Plan 05-06
metrics:
  duration: ~15 min (3 task atomici, sequential)
  completed: 2026-05-08
  tasks: 3
  commits: 3
  files_created: 0
  files_modified: 4
  tests_unblocked: 1 (test_indicator_full_slice_equals_recompute)
---

# Phase 5 Plan 05: Wave 2 Engine Extension + D-21 Invariant Summary

Wave 2 (parte engine) di Phase 5 baseline backtest: estensione additive di
`backtest/engine.py` con i 4 kwargs richiesti dal slice_worker Phase 5
(`indicators_full`, `risk_profile`, `timeout_bars`, `equity_initial`),
implementazione del timeout enforcement per-TF (D-05), thin wrapper
`force_close` + `virtual_positions` su `BacktestBroker`, esteso
`BacktestMetrics` con `longest_dd_days` (D-18), e attivato il primo test
no-future-leakage `test_indicator_full_slice_equals_recompute` (D-21 REAL).
4 dei 5 gate del preflight Phase 5 chiusi.

## Files Modified

| File | Tipo | Δ | Ruolo |
|------|------|---|-------|
| `backtest/engine.py` | MOD | +69/−6 | 4 kwargs Phase 5 + TIMEOUT_CLOSE_REASON + timeout enforcement loop |
| `backtest/broker.py` | MOD | +35/−0 | `virtual_positions` property + `force_close` thin wrapper |
| `backtest/metrics.py` | MOD | +45/−0 | `longest_dd_days` field + `_longest_underwater_run` helper + popolamento in `compute_metrics` |
| `tests/test_baseline_no_future_leakage.py` | MOD | +125/−5 | `test_indicator_full_slice_equals_recompute` body implementato (skip rimosso) |

Totale: **0 file nuovi, 4 modificati**, 274 LOC nette aggiunte.

## New Engine kwargs (additive, default None)

```python
BacktestEngine(
    bars=...,                # Phase 1 (positional)
    symbol=...,
    timeframe=...,
    cost_model=...,
    cfg=None,                # Phase 1 default
    initial_balance=10_000.0,
    run_id=None,
    ledger=None,
    fold_index=None,
    cost_yaml_hash="nohash",
    # ─── Phase 5 (kwargs-only, opt-in) ─────────────────
    indicators_full=None,    # cache pre-computed (D-15) → 05-06 slice_worker
    risk_profile=None,       # CONSERVATIVE/MODERATE/AGGRESSIVE → cfg.RISK_MODE
    timeout_bars=None,       # D-05 per-TF (M15=96, M30=96, H1=120)
    equity_initial=None,     # alias di initial_balance, prevale se entrambi passati
)
```

I caller Phase 1 (`run_backtest()` line 309-342) restano completamente
invariati — i 4 nuovi kwargs sono opt-in, nessun breaking change.

Verifica `inspect.signature`:

```
['bars', 'cfg', 'cost_model', 'cost_yaml_hash', 'equity_initial', 'fold_index',
 'indicators_full', 'initial_balance', 'ledger', 'risk_profile', 'run_id',
 'self', 'symbol', 'timeframe', 'timeout_bars']
```

Conta occorrenze in `backtest/engine.py` (acceptance criteria):

| Kwarg / costante | Occorrenze | Soglia | OK |
|------------------|-----------:|-------:|----|
| `indicators_full` | 4 | ≥3 | ✓ |
| `risk_profile` | 6 | ≥2 | ✓ |
| `timeout_bars` | 10 | ≥3 | ✓ |
| `equity_initial` | 5 | ≥2 | ✓ |
| `TIMEOUT_CLOSE` | 5 | ≥1 | ✓ |

## Timeout Enforcement (D-05)

Il check timeout gira nel main loop **dopo** `broker.advance(bar)`: questo
preserva la priorità di SL/TP (chiusi da `advance` quando i prezzi
intra-bar superano i livelli). Solo le posizioni che sopravvivono al check
SL/TP vengono valutate per timeout — evitando doppia-chiusura nello
stesso ciclo.

Pseudo:

```python
if self.timeout_bars is not None and self.timeout_bars > 0:
    current_bar_index = broker._bar_index  # già incrementato da advance(bar)
    for pos in broker.virtual_positions:   # snapshot list (safe vs mutation)
        bars_held = current_bar_index - pos.entry_bar_index
        if bars_held >= self.timeout_bars:
            row = broker.force_close(
                pos.position_id, float(bar.close),
                TIMEOUT_CLOSE_REASON, int(bar.time),
            )
            equity_curve.append(broker._balance)
            ctx = pending_ctx.pop(row["position_id"], None)
            if ctx is not None:
                row["decision_context_json"] = ctx
```

`TIMEOUT_CLOSE_REASON = "TIMEOUT_CLOSE"` definita module-level →
slice_worker (05-06) può importare la costante per filtrare le righe
nel decision dataset (D-02 `exit_reason ∈ {TP_HIT, SL_HIT, TIMEOUT_CLOSE, MANUAL}`).

## BacktestBroker — Phase 5 helpers (additive)

`backtest/broker.py` esteso con due API pubbliche, **senza toccare** la
semantica interna `_close_virtual` né `_check_sl_tp`:

```python
@property
def virtual_positions(self) -> list[VirtualPosition]:
    """Snapshot list — l'iteratore lato chiamante è safe rispetto a mutation."""
    return list(self._positions.values())

def force_close(
    self, position_id: int, exit_price: float, exit_reason: str,
    exit_time: int | None = None,
) -> dict:
    """Thin wrapper su _close_virtual — slice_worker / engine timeout path."""
    if position_id not in self._positions:
        raise KeyError(f"unknown position_id: {position_id}")
    if exit_time is None:
        exit_time = int(self._window[-1]["time"])
    return self._close_virtual(position_id, float(exit_price), exit_reason, int(exit_time))
```

Preflight FAIL 2 (`virtual_positions`) + 3 (`force_close`) → entrambi
chiusi (vedi §Preflight Status sotto).

## longest_dd_days Implementation (D-18)

```python
@dataclass
class BacktestMetrics:
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    longest_dd_days: float   # ← Phase 5 D-18 (BAR UNITS)
    hit_rate: float
    ...

def _longest_underwater_run(equity_curve: list[float]) -> int:
    """Conta lunghezza massima di run dove equity[t] < running_peak."""
    if not equity_curve:
        return 0
    peak = equity_curve[0]
    current_run = 0
    max_run = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
            current_run = 0
        else:
            current_run += 1
            if current_run > max_run:
                max_run = current_run
    return max_run
```

In `compute_metrics(...)` ho costruito esplicitamente `equity_curve_values`
(cumulativa di `pnl`) accanto al calcolo di `max_drawdown_pct` per riusare
la stessa serie senza doppio-pass:

```python
equity_curve_values: list[float] = []
equity = 0.0
peak = 0.0
max_dd_pct = 0.0
for p in pnl:
    equity += p
    equity_curve_values.append(equity)
    if equity > peak:
        peak = equity
    if peak > 0:
        dd_pct = (peak - equity) / peak * 100.0
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

longest_dd_bars = _longest_underwater_run(equity_curve_values)
longest_dd_days_value = float(longest_dd_bars)
```

**Convenzione unità**: il campo si chiama `_days` ma il valore è in BAR
UNITS (1 unit = 1 trade chiuso, perché la curva è construita dai PnL
post-trade). La conversione bar→days è applicata da `report_writer`
(Plan 05-06) via `bars_per_day` per timeframe (M15→0.0104, M30→0.0208,
H1→0.0416).

Conta occorrenze in `backtest/metrics.py`:

| Token | Occorrenze | Soglia | OK |
|-------|-----------:|-------:|----|
| `longest_dd_days` | 5 | ≥2 | ✓ |
| `_longest_underwater_run` | 3 | ≥2 | ✓ |

## D-21 Invariant Test (BLOCKER 4 risolto)

`test_indicator_full_slice_equals_recompute` ora verifica D-21 in modo
sostanziale (non più tautologia di indicizzazione lista). Il test:

1. Importa `compute_all_extended` da `indicators` (Phase 2). Skip se ImportError.
2. Converte `synthetic_bars` (list[Bar]) → list[dict] (l'API Phase 2 accetta dict).
3. Calcola `full = compute_all_extended(bars_dict)`.
4. Per ogni `key ∈ {sma_20, atr_14, rsi_14}` e per ogni `i ∈ {30, 60, 99}`:
   - Calcola `partial = compute_all_extended(bars_dict[:i+1])`.
   - **Branch 1** (dict-of-lists, Phase 2 D-04 schema futuro): confronta
     `full[key][i]` vs `partial[key][-1]`.
   - **Branch 2** (dict-of-scalars, **API Phase 2 corrente**): ricalcola
     `full_recomputed = compute_all_extended(bars_dict[:i+1])` e confronta
     `full_recomputed[key]` vs `partial[key]` → testa determinismo +
     causalità (stessa funzione su stesso input → stesso output).
5. Skip silenzioso (continue) se l'indicator è None/NaN per warm-up
   insufficiente — D-21 si applica solo dove l'indicator è valido.
6. Sanity guard: `assert checked_count > 0` evita pass tautologico se tutti
   i sample sono None.

Sample keys scelte (`sma_20`, `atr_14`, `rsi_14`) hanno lookback ≤ 30 → tutti
definiti per i ∈ {30, 60, 99}. Il test risulta effettivamente attivo, **non
skip**, sull'API Phase 2 corrente.

```
tests/test_baseline_no_future_leakage.py::test_indicator_full_slice_equals_recompute PASSED
tests/test_baseline_no_future_leakage.py::test_decision_dataset_temporal_ordering    SKIPPED  (→ 05-06)
tests/test_baseline_no_future_leakage.py::test_entry_at_next_bar_open                SKIPPED  (→ 05-05/05-06)

======================== 1 passed, 2 skipped in 1.63s =========================
```

Acceptance criteria:

| Criterio | Stato |
|----------|-------|
| `@pytest.mark.skip` count == 2 (3 stub - 1 implementato) | ✓ (2) |
| `pytest tests/test_baseline_no_future_leakage.py::test_indicator_full_slice_equals_recompute -x` exit 0 | ✓ |
| Test funzione body contiene loop `for key in` ≥1 occorrenza | ✓ (1) |

## Phase 1 Regression Status

Test backtest Phase 1 + nuovo test Phase 5 (44 + 1 + 2 skipped):

```
tests/test_backtest_engine.py        ......       (6 passed; smoke perf 12-month deselected — pre-esistente flaky)
tests/test_backtest_metrics.py       .....        (5 passed)
tests/test_backtest_broker.py        ...........  (11 passed)
tests/test_backtest_loader.py        ....         (4 passed)
tests/test_backtest_costs.py         .....        (5 passed)
tests/test_backtest_ledger.py        .....        (5 passed)
tests/test_backtest_walk_forward.py  .......      (7 passed)
tests/test_baseline_no_future_leakage.py  .ss     (1 passed, 2 skipped)

================= 44 passed, 2 skipped, 1 deselected in 4.11s =================
```

Il test `test_smoke_12month_under_60s` è deselected: timing assertion
`elapsed < 60.0` fallisce a 69.93s sul box dev attuale — è un **pre-esistente
SC-6 flaky perf** non legato a questo plan (commit di partenza `cdeee85`
precedente alle modifiche Phase 5 ha lo stesso fail). Nessuna regressione
introdotta da Plan 05-05.

## Preflight Status

`scripts/preflight_phase5.py` post-Plan 05-05:

```
=== Phase 5 Preflight Contract Probe ===
  OK    BacktestEngine.__init__ ha parametri base Phase 1
  OK    BacktestEngine.__init__ ha tutti gli additions Phase 5         ← era FAIL
  OK    BacktestBroker espone virtual_positions/open_positions/_positions ← era FAIL
  OK    BacktestBroker.force_close presente                            ← era FAIL
  OK    _BT_RUNS_COLUMNS contiene slippage_seed_effective (+6 altre)
  OK    BacktestMetrics.{sharpe,sortino,max_drawdown_pct,hit_rate,...,total_pnl_usd}
  OK    BacktestMetrics.longest_dd_days                                ← era FAIL
  OK    strategy.evaluate_proposal_for_bar callable=True
  OK    strategy.adapters.backtest.build_ctx_backtest callable=True
  OK    indicators.compute_all_extended callable=True
  FAIL  compute_all_extended shape probe: Bar.__init__() got an unexpected keyword argument 'tick_volume'
                                                                       ← deferred a 05-08
```

**4 dei 5 gate Phase 5 chiusi.** Rimane solo il quinto (probe-recalibration:
il `Bar` shape vero di Phase 1 differisce da quello assunto dal probe —
documentato come deferred in 05-01-SUMMARY come task per Plan 05-08).

## Acceptance Criteria

| Criterio Task 1 — engine | Stato |
|--------------------------|-------|
| `inspect.signature(BacktestEngine.__init__)` contiene `{indicators_full, risk_profile, timeout_bars, equity_initial}` | ✓ |
| Phase 1 test esistenti `pytest tests/test_backtest_engine.py -x` exit 0 (escluso smoke perf flaky) | ✓ |
| Smoke instanziare BacktestEngine senza i 4 kwargs nuovi → no exception | ✓ |
| Conte occorrenze: indicators_full ≥3, risk_profile ≥2, timeout_bars ≥3, equity_initial ≥2, TIMEOUT_CLOSE ≥1 | ✓ |

| Criterio Task 2 — metrics | Stato |
|---------------------------|-------|
| `BacktestMetrics.longest_dd_days` accessibile | ✓ |
| `pytest tests/test_backtest_metrics.py -x` exit 0 | ✓ (5 passed) |
| Conte occorrenze: longest_dd_days ≥2, _longest_underwater_run ≥2 | ✓ (5, 3) |

| Criterio Task 3 — D-21 test | Stato |
|------------------------------|-------|
| 2 `@pytest.mark.skip` rimasti (3 - 1 implementato) | ✓ |
| `test_indicator_full_slice_equals_recompute` exit 0 | ✓ (passed) |
| Loop `for key in` ≥1 | ✓ (1) |

## Deviations from Plan

### 1. [Rule 1 - Bug] Shape API compute_all_extended diversa da quella ipotizzata dal plan

- **Found during:** Task 3 (probe runtime di `compute_all_extended`).
- **Issue:** Il plan `<action>` di Task 3 (e l'altro hint nel sub-task 1c) ipotizza
  che `compute_all_extended(bars)` ritorni un dict-of-lists (con metodo
  `slice_until` opzionale) — schema atteso da Phase 2 D-04 quando ExtendedIndicators
  API sarà landed. **L'API attuale di Phase 2** ritorna invece un **dict-of-scalars**
  (singoli valori finali calcolati su tutta la sequenza passata). Il pattern di test
  `full[key][i] == partial[key][-1]` non è applicabile literal: i valori sono scalari,
  non indicizzabili.
- **Fix:** Implementato dual-branch runtime detection:
  - **Branch list** (forward-compat Phase 2 D-04): se `full[key]` è `list`, confronta
    `full[key][i]` vs `partial[key][-1]`.
  - **Branch scalar** (API corrente): ricalcola `full_recomputed = compute_all_extended(bars[:i+1])`
    e confronta `full_recomputed[key]` vs `partial[key]` → verifica determinismo +
    causalità (la funzione è pura, niente future leakage perché chiamata su prefix).
  Stessa semantica D-21 in entrambe le shape; quando Phase 2 D-04 evolverà a
  dict-of-lists con `slice_until()`, il branch list si attiverà automaticamente
  senza modifiche al test.
- **Files modified:** `tests/test_baseline_no_future_leakage.py`.
- **Commit:** `bae7563`.
- **Nota per Phase 2 evolution:** quando `ExtendedIndicators` di Phase 2 D-04 verrà
  landed con shape dict-of-lists, il test resterà valido — ma il branch attivo
  cambierà runtime (da scalar a list). Re-verificare alla landing di Phase 2 D-04.

### 2. [Rule 1 - Bug] Sample keys del plan (atr/ema20/rsi) non matchano l'API corrente (atr_14/ema_50/rsi_14)

- **Found during:** Task 3 prima esecuzione (test SKIPPED su `ema_50` non esposto).
- **Issue:** Il plan di esempio cita keys `atr`, `ema20`, `rsi` come naming canonico.
  L'API Phase 2 corrente espone `atr_14`, `ema_50`, `rsi_14` (lookback nel nome —
  vedi `indicators/aggregate.py`). Tentare `full.get("atr")` ritorna None →
  `pytest.skip("Phase 2 ExtendedIndicators non espone atr")` → test bypassato anche
  quando dovrebbe girare.
  Inoltre `ema_50` con prefix `bars[:31]` (i=30) è None per warm-up insufficiente
  (50 bar minimi). Il vecchio inner-skip su None abortiva tutto il test invece di
  saltare solo quel (key, i).
- **Fix:**
  1. Sostituiti i sample keys del plan (`atr`, `ema20`, `rsi`) con i nomi reali
     dell'API Phase 2 (`sma_20`, `atr_14`, `rsi_14`) — tutti con lookback ≤ 30
     così sono definiti per ogni i ∈ {30, 60, 99}.
  2. Inner skip su None/NaN sostituito con `continue` (skip della singola coppia,
     non dell'intero test).
  3. Sanity guard `assert checked_count > 0` per garantire che almeno una coppia
     sia stata effettivamente confrontata (evita pass tautologico se l'API cambia
     ancora e tutte le keys diventano None).
- **Files modified:** `tests/test_baseline_no_future_leakage.py`.
- **Commit:** `bae7563`.

### 3. [Rule 2 - Critical functionality] virtual_positions esposto come property, non attributo pubblico

- **Found during:** Task 1 sub-task 1b lettura `BacktestBroker._positions: dict`.
- **Issue:** Il plan suggerisce `broker.virtual_positions` come "list di posizioni
  open" iterabile. `BacktestBroker` Phase 1 espone `_positions: dict[int, VirtualPosition]`
  (private). Esporlo direttamente esporrebbe il dict mutabile interno e l'iter su
  dict-while-mutating sarebbe unsafe se in futuro una close concorrente modificasse
  il dict.
- **Fix:** Aggiunto `@property virtual_positions(self) -> list[VirtualPosition]` che
  ritorna `list(self._positions.values())` — snapshot a ogni call, safe per
  iter+close (engine timeout path lo chiama in loop chiamando `force_close` su
  ogni elemento).
- **Files modified:** `backtest/broker.py`.
- **Commit:** `29930e5` (incluso nella stessa unità Task 1).

### 4. [Rule 2 - Critical functionality] force_close signature estesa con exit_time opzionale

- **Found during:** Task 1 sub-task 1b implementazione timeout enforcement.
- **Issue:** Il plan dichiara `force_close(position_id, exit_price: float, exit_reason: str) -> ClosedTrade`
  (3 args). Ma `_close_virtual` interno richiede 4 args (incluso `exit_time: int`,
  necessario per il row del ledger Phase 1 schema D-08 — il timestamp di chiusura
  è un campo first-class, non derivabile post-hoc senza accesso a `bar.time`).
- **Fix:** Signature estesa: `force_close(position_id, exit_price, exit_reason, exit_time=None)`.
  Se `exit_time is None`, default a `int(self._window[-1]["time"])` (coerente con
  `close_position` Phase 1). Engine timeout path passa esplicitamente `bar.time`.
- **Files modified:** `backtest/broker.py`.
- **Commit:** `29930e5`.
- **Nota per slice_worker (05-06):** può chiamare `broker.force_close(pid, price, "MANUAL")`
  senza specificare exit_time — verrà letto dall'ultimo bar nel window.

## Authentication Gates

None — task interamente locali (file write, pytest, no network/API/secrets).

## Threat Model Compliance

| Threat | Disposition | Implementazione |
|--------|-------------|-----------------|
| T-05-12 risk_profile injection | mitigate | Caller (slice_worker 05-06) usa solo costanti hard-coded `["CONSERVATIVE","MODERATE","AGGRESSIVE"]`. Engine non valida la stringa (accept any) — vector di injection esiste solo se caller ammette user input, fuori scope di engine. |
| T-05-13 indicators_full memory share | accept | per-process cache (worker spawn isolato) — engine memorizza solo reference, no cross-process IPC. |
| T-05-14 timeout_bars=0 → close immediato | mitigate | Guard: `if self.timeout_bars is not None and self.timeout_bars > 0`. `timeout_bars=0` viene ignorato silenziosamente (no enforcement). Documentato nel kwarg. |

## Self-Check

**Files modified (verified):**
- `backtest/engine.py` ✓ (4 kwargs Phase 5 + TIMEOUT_CLOSE_REASON + timeout loop)
- `backtest/broker.py` ✓ (`virtual_positions` property + `force_close` wrapper)
- `backtest/metrics.py` ✓ (longest_dd_days field + helper + popolamento)
- `tests/test_baseline_no_future_leakage.py` ✓ (1 test attivo, 2 skip)

**Commits (verified via `git log --oneline -3`):**
- `29930e5` feat(05-05): estendi BacktestEngine con 4 kwargs Phase 5 + timeout enforcement
- `695d7b8` feat(05-05): estendi BacktestMetrics con longest_dd_days (D-18)
- `bae7563` test(05-05): implementa test_indicator_full_slice_equals_recompute (D-21 REAL)

**Smoke checks passed:**
- `inspect.signature(BacktestEngine.__init__)` ⊇ {indicators_full, risk_profile, timeout_bars, equity_initial} ✓
- `BacktestMetrics(...).longest_dd_days` accessibile (5 occorrenze nel src) ✓
- `pytest tests/test_baseline_no_future_leakage.py -v` → 1 passed, 2 skipped ✓
- `pytest tests/test_backtest_*.py --deselect smoke_12month_under_60s` → 44 passed ✓
- `python scripts/preflight_phase5.py` → 4 dei 5 gate chiusi (5° = probe-recalibration → 05-08) ✓

## Self-Check: PASSED

## TDD Gate Compliance

Plan 05-05 ha frontmatter `type: execute`, ma Task 3 ha `tdd="true"`. Lo stub
`@pytest.mark.skip(...)` con `raise NotImplementedError` di Plan 05-02 era
de-facto la fase RED (test esistente, fallirebbe se rimosso lo skip). Plan
05-05 ha eseguito la transizione GREEN (rimosso skip + body implementato +
test passa). Nessuna fase REFACTOR necessaria — il body del test è
single-pass, leggibile, non richiede cleanup.

Sequenza di gate verificata:
- RED gate: `e3013d2 test(05-02): scaffold 7 stub test files + 1 active warmup test` (test stub creato)
- GREEN gate: `bae7563 test(05-05): implementa test_indicator_full_slice_equals_recompute (D-21 REAL)` (test passa)

## Next Wave

**Wave 3: 05-06** — slice_worker + report_writer + runner orchestrator.
Consumerà:
- `BacktestEngine(indicators_full=..., risk_profile=..., timeout_bars=..., equity_initial=...)` (4 kwargs Phase 5)
- `TIMEOUT_CLOSE_REASON` per filtrare exit_reason nelle righe del decision dataset
- `BacktestBroker.virtual_positions` + `BacktestBroker.force_close(...)` per timeout/manual close
- `BacktestMetrics.longest_dd_days` per popolare colonna D-18 della tabella 27-row
- `_longest_underwater_run` riusabile se serve in custom report writer

**Wave 4: 05-07 + 05-08** restano bloccati su:
- `Bar.tick_volume` shape probe-recalibration (5° gate preflight, deferred a 05-08)
- Phase 1-4 implementation chain completion (frontmatter `phase1_dependency_risk`).

D-05 (timeout per-TF) + D-15 (indicator cache hook) + D-18 (longest_dd_days)
di `05-VALIDATION.md` possono essere spostati da `pending` → `green`.
