---
phase: 04-strategy-refactor
verified: 2026-05-08T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 1
overrides:
  - must_have: "SC-5 — Existing live behavior unchanged on regression fixture (10 historical decisions replayed produce identical proposals to pre-refactor output)"
    reason: "Architectural delta intenzionale: motore quasi-binario legacy sostituito con confluence 5-factor (D-08). Drift severo (8/10 fire vs 10/10 NONE legacy) RCA documentato in 04-08-RECONCILIATION.md. Decisione utente option-a su CHECKPOINT human-verify in 04-08: ACCEPT calibration + re-baseline fixture sul nuovo motore. strategy_legacy.py archiviato in .planning/archive/ come fallback per option-b/c/d se Phase 5 backtest invalida la calibrazione. Validazione metriche aggregate (PF, drawdown, hit-rate, expectancy) demandata a Phase 5 plan-08 preflight gate."
    accepted_by: "frnbiancardi (user)"
    accepted_at: "2026-05-08T00:00:00Z"
gaps: []
human_verification: []
carry_over_flags:
  - flag: "Calibrazione 5-factor pendente validazione Phase 5 backtest"
    owner: "Phase 5 (plan 05-08 preflight gate)"
    blocking_for: "Phase 11 paper deploy"
    documented_in: "tests/fixtures/strategy_regression_baseline.README.md, .planning/archive/README.md"
  - flag: "Backtest smoke perf 63.5s vs budget 60s (~6% overshoot)"
    owner: "Phase 5 (plan 05-08 preflight gate)"
    origin: "Pre-existing da Plan 04-07 cutover, NON introdotto da 04-08"
    blocking_for: "non-blocker; deferred"
  - flag: "strategy_legacy.py archiviato (non deletato)"
    owner: "Phase 5 (post validation)"
    razionale: "Preserva fallback per option-b/c/d se Phase 5 invalida la nuova calibrazione"
---

# Phase 4: Strategy Refactor — Verification Report

**Phase Goal:** Refactor del modulo strategy in detector pure-function (Setup A/B/C/D), confluence scorer 5-factor, R:R proposal builder ATR-based, con lo *stesso* code path eseguito da live scheduler e backtest engine — no fork.

**Verificato:** 2026-05-08
**Status:** ✅ **PASSED** (5/5 must-haves verificati, 1 con override esplicito documentato)
**Re-verification:** No — verifica iniziale di chiusura phase.
**Final commit:** `d81a5c7` (`docs(04-08): chiudi Phase 4 — option-a applied (re-baseline + archive)`)

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #   | Truth (SC ROADMAP)                                                                                              | Status                  | Evidence                                                                                                                                                                                                                                                                                                                                                                       |
| --- | --------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SC-1 | Each setup detector è una pure function (no broker, no log/print, no DB writes).                                | ✓ VERIFIED              | `tests/test_strategy_purity.py` (AST gate, 5 test) PASS sui 7 moduli puri (`strategy/setups/{a,b,c,d}.py`, `strategy/confluence.py`, `strategy/proposal.py`, `strategy/context.py`). Detector lift 208/300/333/298 LOC ritornano `ProposalDraft` `(setup_type, direction, entry, sl, tp, factors, grade, confidence, reason)` — nessun callsite mt5/log/sqlite verificato.       |
| SC-2 | Confluence scorer ritorna 5 factor booleans + grade (A+/A/B/C/reject) + starting confidence; matches skill.    | ✓ VERIFIED              | `strategy/confluence.py` 316 LOC esporta `score_factors → dict[5 factors bool]`, `grade_for → Literal["A+","A","B","C","reject"]`, `compute_confidence(grade, ctx, setup_name, factors, indicators)`; calibratore con `base_confidence` + adjusters `±0.05` (spread_tighter, momentum_strong, volatility_compressed, …) clamp [0,1]. Test `test_strategy_confluence.py` PASS. |
| SC-3 | Strategy unit tests in <500ms (sub-millisecond per detector).                                                  | ✓ VERIFIED              | `pytest -q tests/test_strategy_purity.py tests/test_strategy_confluence.py tests/test_strategy_proposal.py tests/test_strategy_setups.py` → **52 passed in 0.46s** (= 460 ms < 500 ms). Test integration regression (CSV-bound) volutamente esclusi dal SC-3 budget (~111s con 10× CSV load).                                                                              |
| SC-4 | Backtest engine + live scheduler invocano lo *stesso* `evaluate_proposal_for_bar(bars, indicators, ctx)`.       | ✓ VERIFIED              | Single shared call site: `strategy/__init__.py:61` definisce `evaluate_proposal_for_bar`; `strategy/_shim.py:148` lo invoca dal path live; `backtest/engine.py:38,127` istanzia `IntradayStrategy` (shim) → stesso path. Adapters `build_ctx_live` / `build_ctx_backtest` producono lo stesso shape `StrategyContext` (D-05). Grep import-graph confermato.                  |
| SC-5 | Existing live behavior unchanged on regression fixture (10 historical decisions = identical proposals).        | ✓ PASSED (override option-a) | Replay regression in `tests/test_strategy_regression.py` 11 test (1 fixture loads + 10 parametrize) **11/11 PASS post re-baseline** (commit `575b484`). Drift severo `NONE → 8 fire (6 FORMING + 2 READY)` documentato in `04-08-RECONCILIATION.md`; decisione utente `option-a` ACCEPT calibration + re-baseline fixture su nuovo motore. Phase 5 valida con metriche aggregate. |

**Score:** **5/5 truths verified** (1 con override esplicito accettato in CHECKPOINT 04-08).

---

### Required Artifacts

| Artifact                                                  | Atteso                                                          | Status     | Dettaglio                                                                                          |
| --------------------------------------------------------- | --------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------- |
| `strategy/__init__.py`                                    | Barrel + `evaluate_proposal_for_bar` D-09                       | ✓ VERIFIED | 128 LOC, esporta 18 simboli; `evaluate_proposal_for_bar` con D-06 priority/grade tie-break logic.   |
| `strategy/_shim.py`                                       | `IntradayStrategy` backward-compat scheduler/mcp/claude_agent   | ✓ VERIFIED | Firma legacy `analyze_symbol(symbol, account_state, sentiment=None) → TechnicalSetup` preservata.   |
| `strategy/confluence.py`                                  | 5-factor scorer + grade + compute_confidence                    | ✓ VERIFIED | 316 LOC, lru_cache su yaml load, factors/grade_map/base_confidence/adjusters/bounds/profile_filters. |
| `strategy/proposal.py`                                    | `ProposalDraft` + draft adapters + R:R floor + ATR cap          | ✓ VERIFIED | 217 LOC, frozen dataclass, `draft_to_trade_proposal`, `draft_to_technical_setup`, `rr_meets_profile_floor` 1e-9 epsilon, `compute_levels_with_atr_cap`. |
| `strategy/setups/a_breakout.py`                           | Setup A pure-fn (STRAT-01)                                      | ✓ VERIFIED | 208 LOC, READY/FORMING/NONE, `_compute_levels_a` D-10 buffer 0.4×ATR cap 1.5×ATR TP 2.5×ATR.       |
| `strategy/setups/b_reversal.py`                           | Setup B pure-fn + counter-trend gate D-07 (STRAT-02)            | ✓ VERIFIED | 300 LOC, gate D-07 attivo PRIMA reject grade.                                                       |
| `strategy/setups/c_compression.py`                        | Setup C pure-fn + Boomer A2 reconciliation (STRAT-03)           | ✓ VERIFIED | 333 LOC, NR4/NR7/squeeze trigger + range-expansion 2× TP D-10; Boomer A2 final-locked CONTEXT.md verbatim. |
| `strategy/setups/d_pullback.py`                           | Setup D pure-fn trend-following (STRAT-04)                      | ✓ VERIFIED | 298 LOC, `_compute_levels_d` D-10 prior_swing/leg_size fallback, mai counter-trend.                |
| `strategy/adapters/live.py`                               | `build_ctx_live` MT5 fetch + single-compute SimpleNamespace     | ✓ VERIFIED | Defensive cast su `SPREAD_BASELINE_PIPS` post Rule 1 fix commit `21abb91`.                          |
| `strategy/adapters/backtest.py`                           | `build_ctx_backtest` da engine_state, stesso shape D-05         | ✓ VERIFIED | Stessa shape di `build_ctx_live` verificata.                                                        |
| `strategy/risk_utils.py`                                  | 5 helper non-pure lift verbatim da legacy                       | ✓ VERIFIED | `_pip_size`, `_pip_value_amount`, `estimate_position_risk_amount`, `estimate_proposal_risk_amount`, `estimate_proposal_lots`. |
| `tests/test_strategy_regression.py`                       | Regression replay implementato 11 test                          | ✓ VERIFIED | 127 LOC, 11/11 PASS in 111s (integration). 1 `parametrize`, 1 `pytest.skip` (defensive _load_fixture). |
| `tests/fixtures/strategy_regression_baseline.json`        | Fixture re-baselined post option-a                              | ✓ VERIFIED | 10 scenari (2 NONE + 6 FORMING + 2 READY) sul nuovo motore 5-factor.                                |
| `tests/fixtures/strategy_regression_baseline.README.md`   | Annotation header con storia + Phase 5 validation note         | ✓ VERIFIED | Provenance + razionale + warning Phase 5 documentati.                                               |
| `.planning/archive/strategy_legacy.py`                    | Legacy archiviato (NON deletato — option-a cleanup)             | ✓ VERIFIED | 28 KB, git mv 100% similarity, blame trail intatto.                                                 |
| `.planning/archive/README.md`                             | Provenance + revert instructions per legacy                     | ✓ VERIFIED | Revert path documentato (sys.path injection + feature flag in `config/strategy.yaml`).             |
| `strategy_legacy.py` (top-level)                          | NON deve esistere                                                | ✓ VERIFIED | `ls strategy_legacy.py` → No such file. Archiviato correttamente.                                  |

**Tutti gli artifact: VERIFIED (level 1 exists + level 2 substantive + level 3 wired).**

---

### Key Link Verification

| Da                                  | A                                       | Via                                                                  | Status     | Dettaglio                                                                            |
| ----------------------------------- | --------------------------------------- | -------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------ |
| `main.py`                           | `strategy.IntradayStrategy`             | `from strategy import IntradayStrategy, StrategyEnvironment` (line 25) | ✓ WIRED    | Live scheduler entry-point usa lo shim Phase 4.                                       |
| `scheduler.py:43`                   | `strategy.IntradayStrategy`             | `from strategy import IntradayStrategy, StrategyEnvironment`          | ✓ WIRED    | Scheduler intraday route immutato (D-01).                                            |
| `scanner.py:25`                     | `strategy.{IntradayStrategy,_last_valid,_pip_size}` | `from strategy import …`                                              | ✓ WIRED    | Scanner Phase 13 backward-compat re-export.                                          |
| `backtest/engine.py:38,127`         | `strategy.IntradayStrategy`             | `from strategy import IntradayStrategy, StrategyEnvironment` + `IntradayStrategy(self.cfg, broker, _log, environment=env)` | ✓ WIRED    | Backtest engine usa lo *stesso* shim. Single shared call site via `analyze_symbol → evaluate_proposal_for_bar`. |
| `strategy/_shim.py:148`             | `strategy.evaluate_proposal_for_bar`    | `draft = evaluate_proposal_for_bar(bars, indicators, ctx)` (lazy import) | ✓ WIRED    | Shim chiama il pure-fn orchestrator post `build_ctx_live`.                            |
| `strategy/__init__.py:75`           | `strategy.setups.ALL_DETECTORS`         | `drafts = [detect(bars, indicators, ctx) for detect in ALL_DETECTORS]` | ✓ WIRED    | 4 detector eseguiti in parallelo, vincitore via D-06 (grade + priority).            |
| `tests/test_strategy_regression.py` | `tests/fixtures/strategy_regression_baseline.json` | `_load_fixture` JSON read + `pytest.parametrize` collect-time         | ✓ WIRED    | 11 test collected (1 fixture loads + 10 parametrized).                                |
| `tests/test_strategy_regression.py` | `strategy.IntradayStrategy`             | Replay attraverso shim post-Wave 3 cutover                            | ✓ WIRED    | 10/10 scenari PASS contro nuovo baseline.                                             |
| `strategy/confluence.py`            | `config/strategy.yaml`                  | `load_strategy_config` (lru_cache su yaml load)                       | ✓ WIRED    | Schema D-08 (factors, grade_map, base_confidence, adjusters, bounds, profile_filters). |
| `strategy/__init__.py`              | `_last_valid` (re-export per scanner)   | Definito inline + esportato in `__all__`                              | ✓ WIRED    | Scanner backward-compat preservato.                                                   |

---

### Requirements Coverage

| Requisito | Plan source | Description                                                                                | Status      | Evidenza                                                                                          |
| --------- | ----------- | ------------------------------------------------------------------------------------------ | ----------- | ------------------------------------------------------------------------------------------------- |
| STRAT-01  | 04-05       | Setup A (Breakout) detector pure-fn                                                        | ✓ SATISFIED | `strategy/setups/a_breakout.py` 208 LOC; AST purity gate verde; regression replay 11/11 PASS.      |
| STRAT-02  | 04-06       | Setup B (S/R Reversal) detector pure-fn + counter-trend gate D-07                          | ✓ SATISFIED | `strategy/setups/b_reversal.py` 300 LOC; gate D-07 verificato test.                                |
| STRAT-03  | 04-06       | Setup C (Compression Breakout) detector pure-fn                                            | ✓ SATISFIED | `strategy/setups/c_compression.py` 333 LOC; Boomer A2 reconciliation final-locked CONTEXT verbatim. |
| STRAT-04  | 04-05       | Setup D (Trend Pullback) detector pure-fn                                                  | ✓ SATISFIED | `strategy/setups/d_pullback.py` 298 LOC; trend-following mai counter-trend.                        |
| STRAT-05  | 04-02       | 5-factor confluence scorer (trend / setup / momentum / volatility / spread+session)        | ✓ SATISFIED | `strategy/confluence.py:score_factors` ritorna `dict[str, bool]` con 5 chiavi.                     |
| STRAT-06  | 04-02       | Confidence calibrator: grade → starting confidence + ±0.05 adjusters                       | ✓ SATISFIED | `compute_confidence` + `base_confidence` + adjusters clamp [0,1]; bug-fix Rule 1 epsilon `21abb91`. |
| STRAT-07  | 04-03       | ATR-based R:R proposal builder con profile-aware minimums                                  | ✓ SATISFIED | `strategy/proposal.py:rr_meets_profile_floor` epsilon 1e-9; `compute_levels_with_atr_cap` cap 1.5×ATR. |
| STRAT-08  | 04-04       | Strategy module side-effect-free — testable in millisecondi                                | ✓ SATISFIED | AST gate 5 test 0.16s; 7 moduli puri verificati no broker/log/print/db; adapters/ esclusi by design. |
| STRAT-09  | 04-07/08    | Stesso strategy module chiamato da live + backtest (no fork)                               | ✓ SATISFIED | Single shared call site `evaluate_proposal_for_bar` (D-09); regression replay 11/11 PASS via re-baseline option-a. |

**Coverage:** **9/9 STRAT-* SATISFIED** (REQUIREMENTS.md riga 51-59 tutti `[x] Complete`).

**Orphaned requirements:** Nessuno. REQUIREMENTS.md mappa esattamente STRAT-01..09 a Phase 4, tutti rappresentati.

---

### Anti-Pattern Scan

| File                              | Riga          | Pattern                              | Severità    | Impact                                                                |
| --------------------------------- | ------------- | ------------------------------------ | ----------- | --------------------------------------------------------------------- |
| `strategy/_shim.py`               | 121           | `from strategy import evaluate_…` lazy | ℹ️ INFO     | Lazy import documentato per evitare ciclo all'import package — corretto. |
| `tests/test_strategy_regression.py` | 30           | `pytest.skip` defensive _load_fixture | ℹ️ INFO     | Difensivo se fixture mancante; il fixture esiste e tutti i 11 test passano. |
| `tests/test_strategy.py`          | 106           | Comment `# pure-fn evaluate_proposal_for_bar` | ℹ️ INFO     | 12 test legacy Category C rimossi correttamente in 04-07.                |
| `_tmp_write_05.py` (root)         | varie         | Riferimenti a Phase 5 evaluate_…       | ℹ️ INFO     | File temporaneo Phase 5 PLAN scratch (non parte di Phase 4 deliverable). |

**Nessun blocker, nessun warning rilevato sui moduli Phase 4.** Le pure-fn rispettano il side-effect-free contract verificato dall'AST gate vivente (STRAT-08 living invariant).

---

### Behavioral Spot-Checks

| Behavior                                                  | Comando                                                                                                  | Risultato                                                       | Status |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------ |
| Strategy package importable                               | `.venv/Scripts/python.exe -c "from strategy import IntradayStrategy, evaluate_proposal_for_bar"`         | exit 0                                                          | ✓ PASS |
| Strategy unit tests under SC-3 budget                     | `pytest -q tests/test_strategy_purity.py tests/test_strategy_confluence.py tests/test_strategy_proposal.py tests/test_strategy_setups.py` | 52 passed in **0.46s** (< 500 ms)                              | ✓ PASS |
| Strategy full suite (unit + integration)                  | `pytest -q tests/test_strategy*.py`                                                                      | **81 passed in 119.35s** (no fail, no skip)                     | ✓ PASS |
| Regression replay green (post re-baseline option-a)       | `pytest -q tests/test_strategy_regression.py`                                                            | **11/11 PASS in 111s**                                          | ✓ PASS |
| Top-level legacy rimosso                                  | `ls strategy_legacy.py`                                                                                  | "No such file"                                                  | ✓ PASS |
| Legacy archiviato in `.planning/archive/`                 | `ls .planning/archive/strategy_legacy.py`                                                                | exists, 28 KB                                                   | ✓ PASS |
| Single shared call site (D-09)                            | grep `evaluate_proposal_for_bar` su `strategy/__init__.py` + `_shim.py` + `backtest/engine.py`           | live (`_shim.py:148`) + backtest (`backtest/engine.py:127`) → entrambi via `IntradayStrategy.analyze_symbol`. | ✓ PASS |

**Tutti i behavioral check: PASS.**

---

### Human Verification Required

**Nessuno.** Tutti i must-have sono verificati programmaticamente. Il CHECKPOINT umano richiesto dal piano 04-08 (Task 2 `autonomous: false`) è già stato eseguito e risolto con la decisione `option-a` (commit `575b484` re-baseline + `a7a252a` archive) — documentato in `04-08-RECONCILIATION.md`.

---

### Gaps Summary

**Nessun gap bloccante per Phase 4.** Phase 4 raggiunge il goal:

1. **SC-1..SC-4 PASSED** in modo netto (purity gate + confluence + 500ms budget + single shared call site verificato per import-graph).
2. **SC-5 PASSED via override option-a accettato esplicitamente in CHECKPOINT human-verify del 04-08:**
   - Drift osservato (8/10 fire vs 10/10 NONE legacy) **NON è un regression bug** ma una **delta architetturale intenzionale**: il gate quasi-binario legacy è stato sostituito dal motore confluence 5-factor (D-08).
   - Decisione utente `option-a`: ACCEPT calibration + re-baseline fixture sul nuovo motore. Nuova fixture cattura 8 fire (2 NONE + 6 FORMING + 2 READY) con confidence 0.70 / 0.55 sui 2 READY.
   - Nuova baseline → regression replay 11/11 PASS in 111s (commit `575b484`).
   - Provenance + razionale documentati in `tests/fixtures/strategy_regression_baseline.README.md` + `.planning/archive/README.md`.

### Carry-over flags (non-blocker, owner Phase 5)

| Flag                                                                                | Owner                                | Tracking                                                                                          |
| ----------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Calibrazione 5-factor pendente validazione metriche aggregate                       | Phase 5 plan-08 (preflight gate)     | Soglia raccomandata: PF non degradato >5%, drawdown non aumentato >10%, hit-rate non degradato >3pp. Se invalida → revert option-b/c/d via legacy archiviato. Blocking gate per Phase 11 paper deploy. |
| Backtest smoke perf 63.5s vs budget 60s (~6% overshoot)                            | Phase 5 plan-08 (preflight gate)     | Pre-existing da Plan 04-07 cutover, NON introdotto da 04-08. Phase 5 può scegliere a) relax budget 70s o b) single-compute caching in `strategy/adapters/live.py`. NON blocker Phase 4. |
| `strategy_legacy.py` archiviato (non deletato)                                      | Phase 5 (post validazione)           | Disposition diversa dal piano 04-08 Task 3 (prescriveva delete). Razionale: preserva fallback per option-b/c/d se Phase 5 invalida. Nessun import live verificato grep. |

### Calibration delta (rimando a Phase 5)

Il nuovo motore 5-factor è più "aggressive" del legacy quasi-binario: fire più spesso (8/10 sui scenari di replay catturati pre-refactor). Questo è atteso e desiderato per consentire a) generazione di `≥10k labeled trades` per il dataset di training Phase 5 (BACK-07 SC#3) e b) classificazione ML downstream Phase 7 che farà da gate calibrato su `calibrated_prob`. La validazione finale prima del paper deploy Phase 11 dipende dal report Phase 5 baseline.

---

### Boomer A2 reconciliation (Phase 2 carry-over) — RESOLVED

Final-locked tramite Setup C compression in plan 04-06 (CONTEXT.md verbatim variant). Nessuna ulteriore azione richiesta. Documentato in `04-06-SUMMARY.md`.

---

## Conclusione

**Phase 4 ✅ PASSED — 5/5 must-haves verificati, 1 con override option-a esplicitamente accettato in CHECKPOINT umano.**

**Plan completion:** 8/8 (100%) — `04-01..04-08` tutti chiusi con SUMMARY committed.
**Test status:** Strategy suite **81/81 PASS** (di cui regression replay 11/11 PASS post re-baseline). Unit subset 52/52 in 0.46s (sotto budget SC-3 500ms).
**Architectural delta:** documentato e accettato. Validazione metriche aggregate demandata a Phase 5 (gate condizionale per Phase 11 paper deploy).
**Phase 5 prerequisiti:** tutti soddisfatti — `evaluate_proposal_for_bar` single shared call site, `build_ctx_backtest` adapter contract definito, legacy archiviato come fallback A/B comparativo.

---

_Verified: 2026-05-08_
_Verifier: Claude (gsd-verifier)_
_Goal-backward verification methodology applied._
