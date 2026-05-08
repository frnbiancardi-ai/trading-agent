---
phase: 04-strategy-refactor
plan: 08
subsystem: strategy
tags: [python, regression-replay, checkpoint-pending, drift-detected, autonomous-false]

requires:
  - phase: 04-strategy-refactor
    provides: 04-01 strategy/ skeleton + 10 fixture baseline immutabili
  - phase: 04-strategy-refactor
    provides: 04-02..04-06 confluence + 4 detector pure-fn
  - phase: 04-strategy-refactor
    provides: 04-07 IntradayStrategy shim + adapters live/backtest + risk_utils
provides:
  - tests/test_strategy_regression.py implementato (replay 10 scenari + tolleranze 1e-5/1e-4)
  - 04-08-RECONCILIATION.md report drift severo (8/10 scenari fallimento, decisione umana richiesta)
  - strategy/adapters/live.py difeso da MagicMock SPREAD_BASELINE_PIPS (Rule 1 bug fix)
affects:
  - Phase 4 chiusura: BLOCCATA su decisione utente (option A/B/C/D — vedi reconciliation)
  - 04-09 (potenziale follow-up plan): a seconda della scelta utente, emette il piano di reconciliation
  - Phase 5 backtest: può comunque procedere su pure-engine se utente sceglie option-A/D (con strategy_legacy invariato come fallback)
  - Phase 11 paper deploy: BLOCCATO finché reconciliation non chiusa

tech-stack:
  added: []
  patterns:
    - "regression replay parametrizzato (pytest.mark.parametrize collect-time loaded da JSON fixture)"
    - "tolleranze esplicite 1e-5 prezzi / 1e-4 confidence per backward-compat verification"
    - "checkpoint-driven flow: autonomous=false impone STOP su drift, no auto-rebaseline"

key-files:
  created:
    - .planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md
  modified:
    - tests/test_strategy_regression.py (stub Wave 0 → 127 LOC implementati)
    - strategy/adapters/live.py (spread_baseline_pips defensive cast)

key-decisions:
  - "Task 1 implementato verbatim dal piano: 11 test collected (1 fixture loads + 10 parametrized), tolleranze 1e-5/1e-4 come da contratto D-14"
  - "Task 2 CHECKPOINT raggiunto: 8/10 scenari falliscono con setup_type drift (NONE→FORMING per 6, NONE→READY per 2), confidence drift su 2 scenari (0.70 e 0.55 vs baseline 0.0)"
  - "Rule 1 bug separato fixato: SPREAD_BASELINE_PIPS MagicMock auto-attribute tripping float comparison in compute_confidence — defensive cast in live.py"
  - "Task 3 NON eseguito: il piano specifica 'Do NOT proceed to re-baseline' su Case B. strategy_legacy.py PRESERVATO. STRAT-09 NON marcato Complete (in-progress in attesa di reconciliation)"

requirements-completed: []  # STRAT-09 BLOCKED su checkpoint user

duration: ~5 min (Task 1 + Task 2 partial; Task 3 non eseguito)
completed: 2026-05-08 (PARZIALE — checkpoint pending)
---

# Phase 4 Plan 08: Wave 4 Regression Gate — CHECKPOINT (drift severo, decisione utente richiesta)

**Esecuzione interrotta su checkpoint:human-verify (Plan Task 2). Il replay di 10 scenari baseline attraverso il NUOVO IntradayStrategy shim produce 8/10 fallimenti per setup_type drift NON tollerabile (NONE→FORMING/READY) + 2 confidence drift severi (0.70/0.55 vs 0.0 baseline). Il piano (Task 2 Case B) classifica questo come REGRESSION BUG — autonomous=false → STOP. SUMMARY documenta lo stato; strategy_legacy.py PRESERVATO; STRAT-09 NON Complete; reconciliation document `04-08-RECONCILIATION.md` con 4 opzioni esposte all'utente.**

## Performance

- **Duration:** ~5 min (esecuzione fino a checkpoint)
- **Started:** 2026-05-08
- **Stopped at checkpoint:** 2026-05-08
- **Tasks executed:** 1.5/3 (Task 1 ✓, Task 2 incomplete pending decision, Task 3 NOT executed)
- **Files modified:** 2 (test + adapters/live.py defensive)
- **Files created:** 1 (RECONCILIATION.md)

## Accomplishments

- **tests/test_strategy_regression.py implementato** (127 LOC): replay completo 10 scenari + tolleranze D-14. 11 test collected (1 fixture loads + 10 parametrized scen_1..10). Schema-check PASS, 2/10 replay PASS (scen_2, scen_9), 8/10 FAIL con drift documentato.
- **Rule 1 bug fix in live.py**: `SPREAD_BASELINE_PIPS` MagicMock auto-attribute era propagato come MagicMock fino a `compute_confidence` → `TypeError: '<' not supported between instances of float and MagicMock`. Defensive cast `float(_spread_raw) if isinstance(int, float) else None`. Bug indipendente dal drift di setup, va mantenuto in qualunque scenario di reconciliation.
- **04-08-RECONCILIATION.md scritto**: tabella delta per-scenario (10 righe), root cause analysis, 4 opzioni (accept+rebaseline / reject+gate / feature-flag / defer-to-Phase-5) con pro/contro/effort, raccomandazione tecnica.

## Task Commits

| Task | Commit | Tipo | Note |
|------|--------|------|------|
| Task 1 — implementa regression replay | `5db3049` | test | 127 LOC, 11 test collected |
| Rule 1 fix — defensive SPREAD_BASELINE_PIPS | `21abb91` | fix | bug indipendente scoperto durante Task 2 |
| Task 2 — checkpoint reached | (no commit, runtime-only) | — | drift documentato in RECONCILIATION |
| Task 3 — cleanup strategy_legacy | NOT EXECUTED | — | Plan dice "Do NOT proceed to re-baseline" su Case B |

## Drift summary (full table in RECONCILIATION.md)

| Scenarios | Pass rate | Drift type |
|-----------|-----------|------------|
| 2/10 PASS | scen_2, scen_9 | NONE/0.0 → NONE/0.0 (entrambi `no_breakout_detected`) |
| 6/10 FAIL FORMING | scen_1, 3, 4, 5, 7, 10 | NONE → FORMING (C_compression / B_reversal / D_pullback) |
| 2/10 FAIL READY | scen_6, scen_8 | NONE → READY con entry/sl/tp + confidence 0.70/0.55 (A_breakout grade A/B) |

**Confidence delta osservato:**
- scen_6: 0.0 → 0.70 (delta 0.70 = 7000× la tolleranza 1e-4)
- scen_8: 0.0 → 0.55 (delta 0.55 = 5500× la tolleranza)

Le delta sono enormemente fuori tolleranza — non è "calibration drift" sottile, è un cambio di filosofia di gating.

## Root cause (high-level)

Il legacy aveva un gate quasi-binario `trend_strength > 0.65 AND alignment SMA AND RSI band AND CLEAN breakout AND pattern`. Sui 10 fixture baseline (offset −500..−150 bar M15) questa AND-condition non si materializza mai → tutti NONE.

Il nuovo motore (Wave 1+2) sostituisce il gate binario con 5-factor confluence + 4 detector paralleli. C_compression e D_pullback osservano FORMING su narrow_range/pullback condizioni indipendenti dal trend, e A_breakout produce READY su CLEAN breakout SR senza trend_strength gate. Architetturalmente intenzionale (D-08), ma rompe SC-5 ("behavior unchanged").

Dettaglio completo: `.planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md` §Root cause.

## Status complessivo Phase 4

| SC | Description | Status |
|----|-------------|--------|
| SC-1 | Each detector pure function | ✅ (purity gate verde, plan 04-04) |
| SC-2 | 5-factor confluence + grade + base_confidence per skill table | ✅ (plan 04-02) |
| SC-3 | Strategy unit tests under 500ms | ✅ unit; ⚠️ regression replay ~96s (10× CSV load + indicator compute) — interpretazione integration |
| SC-4 | Same evaluate_proposal_for_bar called by live + backtest | ✅ (single shared call site verificato grep) |
| SC-5 | Existing live behavior unchanged on regression fixture | ❌ **8/10 scenari drift** — checkpoint pending |
| STRAT-01..08 | Pure modules + scoring | ✅ |
| STRAT-09 | Regression replay green | ❌ **BLOCKED su checkpoint** |

**Phase 4 NOT closed.** 7/8 plans complete (88%); plan 04-08 in checkpoint.

## CHECKPOINT — decisione richiesta

Il piano (`04-08-PLAN.md` Task 2) prescrive `autonomous: false` e definisce 4 esiti (Case A, B, C, D). Il replay osservato è **Case B (REGRESSION BUG)** per i 6 setup_type FORMING + un caso non previsto dal piano (NONE→READY) per i 2 scenari READY. Né Case A (parità) né Case D (pure confidence drift) si applicano.

Il documento `04-08-RECONCILIATION.md` espone 4 opzioni decisionali con pro/contro/effort:

- **option-a** — ACCEPT + re-baseline fixture (10 min)
- **option-b** — REJECT + add gate trend_strength sui detector (30-60 min)
- **option-c** — feature flag in config/strategy.yaml (60-90 min)
- **option-d** — Defer Phase 4 close, open 04-09 follow-up (raccomandato, 30 min)

**Reply expected** dall'utente: `option-a` | `option-b` | `option-c` | `option-d` | `custom <descrizione>`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Defensive cast su SPREAD_BASELINE_PIPS in live.py**
- **Found during:** Task 2 esecuzione
- **Issue:** `getattr(cfg, "SPREAD_BASELINE_PIPS", None)` ritorna MagicMock auto-attribute quando cfg è un MagicMock generico (test fixture _capture_cfg). Il MagicMock viene propagato in `StrategyContext.spread_baseline_pips` e poi in `compute_confidence:289` → `TypeError: '<' not supported between instances of float and MagicMock`. Trippa scenari 6 e 8 prima di poter osservare il setup_type.
- **Fix:** `_spread_raw = getattr(cfg, "SPREAD_BASELINE_PIPS", None); spread_baseline_pips = float(_spread_raw) if isinstance(_spread_raw, (int, float)) else None`. Difesa simmetrica anche per produzione (cfg parsing futuro che ritorni stringa o None).
- **Files modified:** strategy/adapters/live.py (1 hunk)
- **Verification:** Re-eseguendo regression replay, scenari 6 e 8 ora passano la pipeline e producono READY (drift osservabile, non più TypeError).
- **Committed in:** `21abb91`

### Scope-bounded out-of-scope (deferred)

**1. Setup_type drift NONE→FORMING/READY su 8 scenari**
- **Status:** REPORTED, NOT FIXED — checkpoint pending decisione utente
- **Trigger:** Plan Task 2 Case B esplicita "Do NOT proceed to re-baseline" + `autonomous: false`
- **Document:** 04-08-RECONCILIATION.md §Tabella delta + §Decisione richiesta
- **Action item:** Reply utente con opzione, poi follow-up plan/fix

**2. Performance overshoot 04-07 (backtest smoke 63s vs 60s budget)**
- **Status:** NOT ASSESSED in plan 04-08 (Task 3 NOT eseguito)
- **Punt to:** Phase 5 baseline backtest plan-XX dovrà decidere se relax budget a 70s o ottimizzare adapter live caching tra bar consecutivi (bollinger/closing_score/narrow_range).

## Files Created/Modified

### Created (1)
- `.planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md` (200+ righe, tabella delta + 4 opzioni + RCA)

### Modified (2)
- `tests/test_strategy_regression.py` — stub Wave 0 (2 pytest.skip, 11 LOC) → implementazione completa (127 LOC, 11 test)
- `strategy/adapters/live.py` — defensive cast su SPREAD_BASELINE_PIPS (1 hunk, 6 LOC delta)

## Verification status

**Plan acceptance criteria:**

- [x] `pytest tests/test_strategy_regression.py::test_regression_fixture_loads -x -q` exits 0 ✅
- [x] `grep -c 'pytest.skip' tests/test_strategy_regression.py` returns 1 (defensive _load_fixture only) ✅
- [x] `grep -c 'parametrize' tests/test_strategy_regression.py` returns 1 ✅
- [x] `wc -l tests/test_strategy_regression.py` reports >= 80 (127 LOC) ✅
- [x] Test discovery shows 10 parametrized cases (`scen_*`) ✅
- [ ] All 10 scenarios PASS — **2/10 PASS (Case B drift)** ❌ checkpoint
- [ ] strategy_legacy.py removed — **NOT EXECUTED** (plan dice "Do NOT proceed" su Case B)
- [ ] Phase 4 SC-5 verified — ❌ blocked

## Self-Check: PASSED (relative to checkpoint scope)

- File `tests/test_strategy_regression.py`: FOUND (127 LOC)
- File `.planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md`: FOUND
- File `strategy/adapters/live.py`: FOUND (defensive cast presente)
- File `strategy_legacy.py`: PRESERVED (intenzionale per checkpoint)
- File `tests/fixtures/strategy_regression_baseline.json`: PRESERVED (NON re-baselined)
- Commit `5db3049` (Task 1): FOUND in git log
- Commit `21abb91` (Rule 1 fix): FOUND in git log
- `pytest tests/test_strategy_regression.py::test_regression_fixture_loads -x`: PASS
- Replay output: 8/10 FAIL drift documentato (output cattura in RECONCILIATION.md)
- Reconciliation document: 4 opzioni esposte + raccomandazione tecnica

## Next Phase Readiness

**Phase 4 NON chiusa.** Stato bloccante:
1. STRAT-09 in-progress (NOT Complete)
2. SC-5 (live behavior unchanged) NOT verified
3. strategy_legacy.py preservato (cleanup deferred)

**Per sbloccare:**
- Reply utente con `option-a/b/c/d/custom` su `04-08-RECONCILIATION.md`
- Spawn nuovo executor (continuation) con la decisione presa
- Esecuzione Task 3 (cleanup) condizionale all'opzione scelta

**Phase 5 baseline backtest:** può comunque iniziare in modalità "pure-engine experimental" perché:
- evaluate_proposal_for_bar è il single shared call site funzionante (D-09)
- build_ctx_backtest contract definito
- strategy_legacy.py invariato come fallback per qualsiasi confronto comparativo

**Phase 11 paper deploy:** BLOCKED finché reconciliation non chiusa (rischio runtime drift senza decisione esplicita).

---
*Phase: 04-strategy-refactor*
*Plan: 08 (Wave 4 — regression gate)*
*Status: PARTIAL — checkpoint:human-verify reached*
*Reconciliation: see `04-08-RECONCILIATION.md`*
*Completed: 2026-05-08 (parziale)*
