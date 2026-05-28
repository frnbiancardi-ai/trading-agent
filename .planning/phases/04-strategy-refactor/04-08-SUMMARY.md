---
phase: 04-strategy-refactor
plan: 08
subsystem: strategy
tags: [python, regression-replay, option-a, re-baseline, phase-gate-closed]

requires:
  - phase: 04-strategy-refactor
    provides: 04-01 strategy/ skeleton + 10 fixture baseline immutabili (poi re-baselined)
  - phase: 04-strategy-refactor
    provides: 04-02..04-06 confluence + 4 detector pure-fn
  - phase: 04-strategy-refactor
    provides: 04-07 IntradayStrategy shim + adapters live/backtest + risk_utils
provides:
  - tests/test_strategy_regression.py implementato (replay 10 scenari + tolleranze 1e-5/1e-4)
  - tests/fixtures/strategy_regression_baseline.json re-baselined su nuovo motore (8/10 fire)
  - tests/fixtures/strategy_regression_baseline.README.md (annotation header)
  - .planning/archive/strategy_legacy.py (archivio post-cutover, NON deletato)
  - .planning/archive/README.md (provenance + revert instructions)
  - 04-08-RECONCILIATION.md report drift severo + decisione finale option-a
affects:
  - Phase 4: CHIUSA — 8/8 plans complete (100%)
  - Phase 5 backtest: deve VALIDARE calibrazione 5-factor con metriche aggregate (PF, drawdown, hit-rate, expectancy) prima paper deploy
  - Phase 11 paper deploy: gate condizionale a Phase 5 validation positiva

tech-stack:
  added: []
  patterns:
    - "regression replay parametrizzato (pytest.mark.parametrize collect-time loaded da JSON fixture)"
    - "tolleranze esplicite 1e-5 prezzi / 1e-4 confidence per backward-compat verification"
    - "re-baseline procedure + provenance README quando architectural delta è intenzionale"
    - "archive vs delete pattern per codice sostituito ma da preservare per Phase N+1 validation"

key-files:
  created:
    - .planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md
    - tests/fixtures/strategy_regression_baseline.README.md
    - .planning/archive/README.md
  modified:
    - tests/test_strategy_regression.py (stub Wave 0 → 127 LOC implementati)
    - strategy/adapters/live.py (spread_baseline_pips defensive cast — Rule 1)
    - tests/fixtures/strategy_regression_baseline.json (re-baselined Phase 4 motore)
  moved:
    - strategy_legacy.py → .planning/archive/strategy_legacy.py (git mv, 100% similarity)

key-decisions:
  - "Task 1 implementato verbatim dal piano: 11 test collected (1 fixture loads + 10 parametrized), tolleranze 1e-5/1e-4 D-14"
  - "Task 2 CHECKPOINT: 8/10 scenari falliscono setup_type drift (NONE→FORMING/READY) + 2 confidence drift severi (0.70 e 0.55 vs baseline 0.0). User reply: option-a (ACCEPT calibration + re-baseline)"
  - "Re-baseline applicato: nuova fixture cattura 8/10 fire (2 NONE + 6 FORMING + 2 READY) attraverso strategy.IntradayStrategy shim post Wave 3"
  - "Regression replay 10/10 PASS contro nuovo baseline (entrambi setup_type, direction, prices 1e-5, confidence 1e-4)"
  - "strategy_legacy.py ARCHIVIATO (non deletato come prescriveva Plan Task 3) per safety: Phase 5 backtest deve validare calibrazione prima paper deploy. Archive preserva fallback option-b/c/d se la validazione invalida"
  - "Rule 1 bug separato fixato in commit 21abb91: SPREAD_BASELINE_PIPS MagicMock auto-attribute → defensive float cast in live.py"

requirements-completed: [STRAT-09]

duration: ~125 min totali (5 min Task 1 + 5 min Task 2 checkpoint + 15 min finalize post-decisione)
completed: 2026-05-08 (FINAL — option-a applied)
---

# Phase 4 Plan 08: Wave 4 Regression Gate — CLOSED (option-a applied)

**Esecuzione completata 2026-05-08 dopo decisione utente `option-a` (ACCEPT calibration + re-baseline fixture). 10/10 scenari ora PASS; strategy_legacy.py archiviato in `.planning/archive/`; STRAT-09 ✓ Complete; Phase 4 8/8 (100%); Phase 5 backtest comparativo richiesto come gate per paper deploy (documentato in fixture annotation + archive README).**

## Performance

- **Duration:** ~125 min totali (cumulativi inclusi i 5 min Task 1 + 5 min Task 2 fino al checkpoint il 2026-05-08)
- **Started:** 2026-05-08
- **Completed:** 2026-05-08 (post option-a decisione utente)
- **Tasks executed:** 3/3 (Task 1 ✓, Task 2 ✓ via re-baseline option-a, Task 3 ✓ via archive)
- **Files modified:** 3 (test, adapters/live.py, fixture JSON)
- **Files created:** 3 (RECONCILIATION.md, fixture README, archive README)
- **Files moved:** 1 (strategy_legacy.py → .planning/archive/)

## Accomplishments

### Task 1 — regression replay implementato (commit `5db3049`)

`tests/test_strategy_regression.py` 127 LOC: 11 test collected (1 fixture loads + 10 parametrizzati `scen_*_<symbol>`). Tolleranze D-14: 1e-5 sui prezzi, 1e-4 sulla confidence, exact match su `setup_type`/`direction`. Riusa `_mock_mt5_from_csv`/`_capture_cfg`/`_capture_account` da `tests/capture_regression_baseline.py` via sys.path injection.

### Rule 1 bug fix — defensive SPREAD_BASELINE_PIPS (commit `21abb91`)

Bug indipendente dal drift di gate: `getattr(cfg, "SPREAD_BASELINE_PIPS", None)` ritornava un MagicMock auto-attribute (capture script usa `MagicMock()` generico) propagato fino a `compute_confidence:289` come MagicMock → `TypeError: '<' not supported`. Fix: `_spread_raw = getattr(...); spread_baseline_pips = float(_spread_raw) if isinstance(_spread_raw, (int, float)) else None`. Difesa simmetrica anche per produzione su parsing futuro che ritorni stringa o None. Va mantenuto in qualunque scenario di reconciliation.

### Task 2 — checkpoint reached + RECONCILIATION report (commit `dd3e45d`)

8/10 scenari fail (6 setup_type drift NONE→FORMING + 2 NONE→READY con confidence 0.70/0.55). Solo 2/10 PASS (scen_2 e scen_9 — entrambi `no_breakout_detected`). RECONCILIATION.md scritto con tabella delta per-scenario, RCA (gate legacy quasi-binario sostituito da 5-factor confluence parallel detectors), 4 opzioni decisionali (option-a/b/c/d) + raccomandazione tecnica.

### User decision: option-a → re-baseline fixture (commit `575b484`)

`tests/capture_regression_baseline.py` re-eseguito contro `strategy.IntradayStrategy` shim (post Wave 3 cutover). Nuova distribuzione fixture (sostituisce baseline legacy):

| # | Symbol | setup_type | direction | confidence | reason                                |
|---|--------|------------|-----------|------------|---------------------------------------|
| 1 | EURUSD | FORMING    | None      | 0.0        | second_compression_bar_waiting_third  |
| 2 | EURUSD | NONE       | None      | 0.0        | no_breakout_detected                  |
| 3 | EURUSD | FORMING    | None      | 0.0        | second_compression_bar_waiting_third  |
| 4 | GBPUSD | FORMING    | SELL      | 0.0        | at_sr_zone_waiting_pattern            |
| 5 | GBPUSD | FORMING    | None      | 0.0        | second_compression_bar_waiting_third  |
| 6 | EURUSD | **READY**  | BUY       | **0.70**   | breakout_buy_level=1.17583            |
| 7 | USDJPY | FORMING    | SELL      | 0.0        | trend_ok_pullback_not_in_zone         |
| 8 | USDJPY | **READY**  | BUY       | **0.55**   | breakout_buy_level=159.78700          |
| 9 | GBPUSD | NONE       | None      | 0.0        | no_breakout_detected                  |
|10 | USDJPY | FORMING    | BUY       | 0.0        | trend_ok_pullback_not_in_zone         |

Aggiunto `tests/fixtures/strategy_regression_baseline.README.md` con storia + razionale + warning Phase 5 validation. Regression replay re-eseguita: **10/10 PASS** in 111s (integration test con 10× CSV load).

### Task 3 — strategy_legacy.py archiviato (commit `a7a252a`)

**Disposition:** ARCHIVE (non delete) — diversione documentata dal piano. Plan Task 3 prescriveva `git rm`, ma la user instruction option-a richiede preservare il legacy come fallback se Phase 5 backtest comparativo invalida la nuova calibrazione (Phase 5 può tornare a option-b/c/d).

`git mv strategy_legacy.py .planning/archive/strategy_legacy.py` (100% similarity, blame trail preserved). Aggiunto `.planning/archive/README.md` con provenance + revert instructions + warning "no production import" + sys.path injection pattern per debug A/B testing.

Verificato `grep -rn "strategy_legacy"` su `--include="*.py"`: nessun callsite live (solo docstring/comment in `strategy/__init__.py`, `strategy/_shim.py`, `strategy/proposal.py`, `strategy/risk_utils.py`). Single shared call site `evaluate_proposal_for_bar` (D-09) invariato.

## Task Commits

| Task | Commit | Tipo | Note |
|------|--------|------|------|
| Task 1 — implementa regression replay | `5db3049` | test | 127 LOC, 11 test collected |
| Rule 1 fix — defensive SPREAD_BASELINE_PIPS | `21abb91` | fix | bug indipendente scoperto durante Task 2 |
| Task 2 — checkpoint reached + RECONCILIATION | `dd3e45d` | docs | drift documentato, 4 opzioni esposte |
| Task 2 — re-baseline (option-a applied) | `575b484` | test | nuovo fixture + annotation README |
| Task 3 — archive strategy_legacy.py | `a7a252a` | refactor | git mv + provenance README |

## Status complessivo Phase 4

| SC | Description | Status |
|----|-------------|--------|
| SC-1 | Each detector pure function | ✅ (purity gate verde, plan 04-04) |
| SC-2 | 5-factor confluence + grade + base_confidence per skill table | ✅ (plan 04-02) |
| SC-3 | Strategy unit tests under 500ms | ✅ unit; regression replay ~111s integration (10× CSV load) — interpretazione documentata |
| SC-4 | Same evaluate_proposal_for_bar called by live + backtest | ✅ (single shared call site verificato grep) |
| SC-5 | Existing live behavior unchanged on regression fixture | ✅ **post re-baseline** (architectural delta accettato → fixture aggiornato a nuovo motore; Phase 5 valida con metriche aggregate) |
| STRAT-01..08 | Pure modules + scoring | ✅ |
| STRAT-09 | Regression replay green | ✅ **Complete** (10/10 PASS) |

**Phase 4 CLOSED.** 8/8 plans complete (100%).

## Phase 4 final state

### Files in `strategy/` (delivered)

```
strategy/
├── __init__.py            (barrel + evaluate_proposal_for_bar D-09 single call site)
├── _shim.py               (IntradayStrategy backward-compat per scheduler/mcp/claude_agent)
├── confluence.py          (5-factor scorer + grade + compute_confidence — plan 04-02)
├── proposal.py            (ProposalDraft + draft adapters + R:R floor + ATR cap — plan 04-03)
├── risk_utils.py          (5 helper non-pure lift verbatim da legacy — plan 04-07)
├── adapters/
│   ├── live.py            (build_ctx_live MT5 fetch + single-compute SimpleNamespace)
│   └── backtest.py        (build_ctx_backtest da engine_state, stesso shape D-05)
└── setups/
    ├── a_breakout.py      (Setup A — plan 04-05, 208 LOC)
    ├── b_reversal.py      (Setup B — plan 04-06, 300 LOC, counter-trend gate D-07)
    ├── c_compression.py   (Setup C — plan 04-06, 333 LOC, NR4/NR7/squeeze trigger)
    └── d_pullback.py      (Setup D — plan 04-05, 298 LOC)
```

### Files removed dal top-level (archiviati)

- `strategy_legacy.py` → `.planning/archive/strategy_legacy.py` (28 KB, blame trail intatto)

### Files preserved unchanged

- `config/strategy.yaml` (D-08 schema 5-factor + grade + adjusters)
- `config/patterns.yaml` (Phase 3 calibration anchors)
- `tests/capture_regression_baseline.py` (riusato per re-baseline; resta come canonical capture script)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Defensive cast su SPREAD_BASELINE_PIPS in live.py**
- **Found during:** Task 2 esecuzione (scenari 6 e 8 trippavano TypeError)
- **Issue:** MagicMock auto-attribute propagato come MagicMock fino a `compute_confidence` → comparison failure
- **Fix:** `float(_spread_raw) if isinstance(_spread_raw, (int, float)) else None`
- **Files modified:** strategy/adapters/live.py (1 hunk, 6 LOC delta)
- **Commit:** `21abb91`

### Plan deviations (documented)

**1. [User instruction override] strategy_legacy.py disposition: ARCHIVE invece di DELETE**
- **Plan Task 3 prescriveva:** `git rm strategy_legacy.py`
- **User instruction option-a richiede:** ARCHIVE per safety Phase 5 backtest validation
- **Razionale:** Phase 5 baseline backtest deve validare la nuova calibrazione 5-factor con metriche aggregate (PF, drawdown, hit-rate, expectancy) prima del paper deploy (Phase 11). Se la validazione fallisce, è possibile revert a option-b/c/d, ognuna delle quali richiede il legacy come riferimento funzionante.
- **Implementazione:** `git mv strategy_legacy.py .planning/archive/` (100% similarity, blame preserved). Provenance README documentato.
- **Garanzie no-leak:** verificato grep `strategy_legacy` su `*.py` ritorna solo docstring/comment; nessun import live; archive non è sul Python path runtime.
- **Commit:** `a7a252a`

### Scope-bounded out-of-scope (deferred to Phase 5)

**1. Performance regression — backtest smoke 12-month 63.54s vs 60s budget (SC-6 Phase 1)**
- **Status:** PRE-EXISTING, not introduced by 04-08
- **Origin:** Plan 04-07 SUMMARY documentò +3-4s overshoot (~5-7% sopra budget) come deferred
- **Misura attuale:** 63.54s (vs 60s) → ~6% overshoot, stabile
- **Impact su 04-08:** ZERO (la regression test 04-08 è ~111s ma è esplicitamente integration, fuori dal SC-3 unit budget)
- **Punt to:** Phase 5 plan-08 (preflight gate already lives in 05-08-PLAN per dependency on Phase 1-4 completion). Phase 5 plan può:
  - Decidere relax budget a 70s
  - Ottimizzare adapter live caching tra bar consecutivi (bollinger/closing_score/narrow_range computation)
- **Action item Phase 5:** valutare a)budget relax vs b)single-compute caching in `strategy/adapters/live.py`

**2. Calibrazione 5-factor: backtest validation pendente prima paper deploy**
- **Status:** TRACKED, blocking gate per Phase 11
- **Documentato:** `tests/fixtures/strategy_regression_baseline.README.md` §"Validazione richiesta (Phase 5)" + `.planning/archive/README.md` §"Motivo archive"
- **Phase 5 deve:** confrontare metriche aggregate nuovo motore vs legacy su 23.5y × 3 pairs × 3 TFs. Soglia raccomandata: PF non degradato > 5%, drawdown non aumentato > 10%, hit-rate non degradato > 3pp.
- **Se Phase 5 invalida:** revert path documentato in archive README (re-import legacy via sys.path injection + feature flag in `config/strategy.yaml`)

## Files Created/Modified

### Created (3)
- `.planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md` — RCA + 4 opzioni + decisione finale option-a
- `tests/fixtures/strategy_regression_baseline.README.md` — annotation header + storia + Phase 5 validation note
- `.planning/archive/README.md` — provenance + revert instructions per legacy

### Modified (3)
- `tests/test_strategy_regression.py` — stub Wave 0 (2 pytest.skip, 11 LOC) → implementazione completa (127 LOC, 11 test)
- `strategy/adapters/live.py` — defensive cast su SPREAD_BASELINE_PIPS (1 hunk, 6 LOC delta)
- `tests/fixtures/strategy_regression_baseline.json` — re-baselined post option-a (10 scenari, sostituzione integrale)

### Moved (1)
- `strategy_legacy.py` → `.planning/archive/strategy_legacy.py` (28 KB, 100% similarity, git mv)

## Verification status

**Plan acceptance criteria (post option-a):**

- [x] `pytest tests/test_strategy_regression.py::test_regression_fixture_loads -x -q` exits 0 ✅
- [x] `grep -c 'pytest.skip' tests/test_strategy_regression.py` returns 1 (defensive _load_fixture only) ✅
- [x] `grep -c 'parametrize' tests/test_strategy_regression.py` returns 1 ✅
- [x] `wc -l tests/test_strategy_regression.py` reports >= 80 (127 LOC) ✅
- [x] Test discovery shows 10 parametrized cases (`scen_*`) ✅
- [x] **All 10 scenarios PASS** ✅ (post re-baseline option-a)
- [x] strategy_legacy.py rimosso da top-level — ✅ (archiviato in `.planning/archive/`)
- [x] Phase 4 SC-5 verified — ✅ (architectural delta accettato; baseline aggiornato)
- [x] `python -c "from strategy import IntradayStrategy, evaluate_proposal_for_bar"` ✅
- [x] Single shared call site verificato (grep `evaluate_proposal_for_bar` su `strategy/__init__.py` + `strategy/_shim.py`) ✅

**Full pytest run (escludendo 5 file con missing optional deps preexisting):** 353 passed + 10 skipped + 1 failed (pre-existing 04-07 backtest perf overshoot, deferred a Phase 5).

## Self-Check: PASSED

- File `tests/test_strategy_regression.py`: FOUND (127 LOC)
- File `tests/fixtures/strategy_regression_baseline.json`: FOUND (re-baselined, 8/10 fire)
- File `tests/fixtures/strategy_regression_baseline.README.md`: FOUND
- File `.planning/archive/strategy_legacy.py`: FOUND (28 KB, ex-top-level)
- File `.planning/archive/README.md`: FOUND
- File `.planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md`: FOUND (final outcome line da aggiungere in commit successivo)
- Top-level `strategy_legacy.py`: NOT FOUND ✅ (correttamente archiviato)
- Commit `5db3049` (Task 1 test): FOUND in git log
- Commit `21abb91` (Rule 1 fix): FOUND in git log
- Commit `dd3e45d` (checkpoint docs): FOUND in git log
- Commit `575b484` (re-baseline option-a): FOUND in git log
- Commit `a7a252a` (archive legacy): FOUND in git log
- `pytest tests/test_strategy_regression.py -v`: 11/11 PASS
- Strategy suite (75 test): 75 PASS in 109.76s
- Full suite (excluding missing-deps): 353 passed + 10 skipped + 1 pre-existing fail (backtest perf, deferred)

## Next Phase Readiness

**Phase 4 CHIUSA ✅** (8/8 plans, 100%). Tutti i 9 STRAT-* requirements completati o promoted a "Complete":
- STRAT-01 (Setup A) ✅
- STRAT-02 (Setup B) ✅
- STRAT-03 (Setup C) ✅
- STRAT-04 (Setup D) ✅
- STRAT-05 (5-factor confluence) ✅
- STRAT-06 (confidence calibrator) ✅
- STRAT-07 (R:R proposal builder) ✅
- STRAT-08 (purity gate) ✅
- STRAT-09 (regression replay green via re-baseline) ✅

**Phase 5 (Baseline Backtest) — pronta a partire:**
- Tutti i prerequisiti Phase 4 soddisfatti
- `evaluate_proposal_for_bar` single shared call site funzionante
- `build_ctx_backtest` adapter contract definito
- `strategy_legacy.py` archiviato come fallback per A/B comparativo
- **Action item Phase 5 plan-08 (preflight gate):** validare metriche aggregate nuovo motore vs legacy. Soglie raccomandate: PF non degradato >5%, drawdown non aumentato >10%, hit-rate non degradato >3pp.

**Phase 11 (Paper Deploy) — gate condizionale:**
- Sblocca solo dopo Phase 5 validation positiva
- Se Phase 5 invalida calibrazione: revert path documentato in `.planning/archive/README.md`

---
*Phase: 04-strategy-refactor*
*Plan: 08 (Wave 4 — regression gate, FINAL)*
*Status: ✅ COMPLETE — option-a applied (re-baseline + archive)*
*Reconciliation: see `04-08-RECONCILIATION.md`*
*Completed: 2026-05-08*
