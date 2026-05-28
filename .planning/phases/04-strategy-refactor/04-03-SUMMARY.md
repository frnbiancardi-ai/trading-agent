---
phase: 04-strategy-refactor
plan: 03
subsystem: strategy
tags: [python, pure-function, dataclass-adapter, atr-cap, rr-floor, profile-filter, fp-epsilon, hand-calc-test]

requires:
  - phase: 04-strategy-refactor
    provides: 04-01 ProposalDraft frozen dataclass + config/strategy.yaml D-08 + RiskProfile alias
  - phase: 04-strategy-refactor
    provides: 04-02 load_strategy_config() cached + StrategyConfig.profile_filters (CONS/MOD/AGG)
provides:
  - strategy/proposal.py (217 LOC) — ProposalDraft + 4 funzioni: draft_to_trade_proposal, draft_to_technical_setup, rr_meets_profile_floor, compute_levels_with_atr_cap
  - tests/test_strategy_proposal.py (239 LOC, 25 test cases) — 6 test bodies + parametrize 3 profile + ATR cap symmetry
affects:
  - 04-04 (Wave 1 purity test AST): valida che strategy/proposal.py non importi mt5/logging/datetime.now (purity gate passerà — module pulito)
  - 04-05/06 (Wave 2 detectors A+D, B+C): chiamano compute_levels_with_atr_cap per SL universale + rr_meets_profile_floor per gate R:R prima di emettere READY
  - 04-07 (Wave 3 shim cutover): IntradayStrategy.build_trade_proposal sarà sostituito con draft_to_trade_proposal (path live) + draft_to_technical_setup (path scheduler)
  - 04-08 (Wave 4 regression gate): replay 10 fixture confronto bit-for-bit comment="python_strategy" preservato

tech-stack:
  added: []   # zero nuove dipendenze runtime
  patterns:
    - "epsilon FP 1e-9 sul confronto rr >= min_rr (mirror 1e-6 spread_tighter di confluence.py)"
    - "import locale di models.{TradeProposal,TechnicalSetup} dentro la funzione per evitare cicli (proposal.py non re-importato a livello modulo)"
    - "Field name mapping documentato (draft.stop_loss_price → ts.stop_loss; draft.take_profit_price → ts.take_profit)"
    - "TYPE_CHECKING guard per import-time-zero su models.* (annotazioni come stringhe forward-ref)"

key-files:
  created: []
  modified:
    - strategy/proposal.py (Wave 0 stub 32 LOC → 217 LOC: 4 funzioni Wave 1 aggiunte; ProposalDraft preservato)
    - tests/test_strategy_proposal.py (Wave 0 stub 27 LOC → 239 LOC: 19 test definitions, 25 cases con parametrize, 0 skip)

key-decisions:
  - "Epsilon FP 1e-9 sul confronto rr >= min_rr — necessario perché 0.001 * 1.3 produce 0.0012999... per arithmetic noise → rr=1.2999... falsamente sotto soglia 1.3 esatta. Stesso pattern del fix spread_tighter di confluence.py (vedi 04-02-SUMMARY §Deviations)"
  - "Import locale di models.TradeProposal/TechnicalSetup dentro le funzioni adapter — evita ciclo strategy.proposal → models → (eventuali) re-export, e riduce tempo di import package strategy/"
  - "comment='python_strategy' fissato literal — coerente con legacy IntradayStrategy.build_trade_proposal, garantisce bit-for-bit parity Wave 4 sul campo comment del TradeProposal"
  - "compute_levels_with_atr_cap NON calcola TP — TP è specifico per setup (Wave 2 detector). Centralizzare entry/SL universale qui mantiene detector code minimal (solo structural anchor + TP target)"
  - "rr_meets_profile_floor ritorna (False, 0.0) per risk≤0 o reward≤0 (prezzi incoerenti con direction) senza sollevare — fail-safe per Wave 2 detector che possono produrre draft con prezzi sbagliati durante esplorazione setup"

requirements-completed: []  # STRAT-07 in-progress; full complete dopo Wave 4 regression gate (mirror 04-02 STRAT-05/06)

duration: ~10min
completed: 2026-05-08
---

# Phase 4 Plan 03: Wave 1 ProposalDraft Adapter + R:R Floor + ATR Cap (STRAT-07) Summary

**4 funzioni pure per il path proposal (D-03/D-10): adapter ProposalDraft → models.TradeProposal/TechnicalSetup, gate R:R per profile_filters, helper SL universale livello strutturale ± buffer×ATR capato a 1.5×ATR. 25 test no-skip; suite 437 passed + 16 skipped (no regression).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-08
- **Completed:** 2026-05-08
- **Tasks:** 2/2 (TDD-backed: RED `cc2ef77` → GREEN `17c0504` → tests + bug-fix `d7e10bf`)
- **LOC produced:** 456 (217 source + 239 test) — netto 422 LOC nuovi (W0 stub: 32+27=59 → 456)
- **Suite delta:** 412 → 437 passed (+25), 22 → 16 skip (–6 sostituiti con test reali, +0 nuovi)

## Accomplishments

- **strategy/proposal.py implementato end-to-end Wave 1**: ProposalDraft (W0, preservato verbatim) + 4 funzioni:
  - `draft_to_trade_proposal(draft, symbol, tf) -> TradeProposal` — path live, fissa `comment="python_strategy"` per parity legacy
  - `draft_to_technical_setup(draft, symbol, tf) -> TechnicalSetup` — path scheduler, mappa field names + carica indicators dict con factors/grade/setup_name/rationale_parts
  - `rr_meets_profile_floor(entry, sl, tp, dir, profile) -> (bool, rr)` — gate STRAT-07 D-10, legge profile_filters[profile].min_rr da config/strategy.yaml via cached load
  - `compute_levels_with_atr_cap(dir, entry, level, atr, buffer_mult, cap_mult=1.5) -> (entry, sl)` — SL universale 4 setup
- **Test 25/25 pass in 0.41s, 0 skip**: 19 test definitions; 3 parametrize × 3 cases (boundary R:R per profile) + 1 SELL symmetric + 4 invalid-input + 6 adapter (READY/non-READY/missing-prices/preserves-fields/handles-NONE) + 5 ATR cap (BUY-buffer/BUY-cap/SELL-symmetric/SELL-cap/invalid-atr/invalid-direction).
- **Pure module garantito**: zero `import logging`/`getLogger`/`print(`/`mt5`/`datetime.now()`/I/O. L'unico load è il yaml.safe_load via `load_strategy_config` (già lru_cache-ato a monte da Plan 04-02).
- **Backward-compat parity**: nessuna modifica a strategy_legacy.py o models.py; suite legacy invariata 437 passed (–6 skip, +25 pass — solo per i nuovi test bodies).

## Task Commits

1. **Task 1 RED — smoke test import 4 simboli Wave 1** — `cc2ef77` (test) — TDD gate: smoke test fallisce con ImportError finché Wave 1 non implementa proposal.py
2. **Task 1 GREEN — adapter + R:R floor + ATR cap helper** — `17c0504` (feat) — 4 funzioni implementate, smoke test passa
3. **Task 2 — 25 test bodies + epsilon FP boundary R:R floor** — `d7e10bf` (test) — sostituiti i 6 stub `pytest.skip` con body reali; include bug-fix Rule 1 inline (epsilon 1e-9 su confronto rr ≥ min_rr)

## Field Name Mapping Table (per Wave 4 regression test reference)

| `ProposalDraft` field            | `models.TradeProposal` field | `models.TechnicalSetup` field    |
| -------------------------------- | ---------------------------- | -------------------------------- |
| `setup_type`                     | n/a (READY only)             | `setup_type`                     |
| `direction`                      | `direction`                  | `direction`                      |
| `entry_price`                    | `entry_price`                | `entry_price`                    |
| **`stop_loss_price`**            | `stop_loss_price`            | **`stop_loss`** (no `_price`)    |
| **`take_profit_price`**          | `take_profit_price`          | **`take_profit`** (no `_price`)  |
| `confidence`                     | `confidence`                 | `confidence`                     |
| `reason`                         | `rationale`                  | `reason`                         |
| `factors` (dict)                 | n/a                          | `indicators["factors"]`          |
| `grade`                          | n/a                          | `indicators["grade"]`            |
| `setup_name`                     | n/a                          | `indicators["setup_name"]`       |
| `rationale_parts` (dict)         | n/a                          | `indicators["rationale_parts"]`  |
| n/a (literal)                    | `comment="python_strategy"`  | n/a                              |
| (caller arg) `symbol`, `timeframe` | `symbol`, `timeframe`      | `symbol`, `timeframe`            |

**Punto chiave:** TechnicalSetup usa `stop_loss`/`take_profit` (no suffisso `_price`), TradeProposal usa `stop_loss_price`/`take_profit_price` (con `_price`). La discrepanza era nel codebase legacy (models.py rispecchia la convenzione storica) — gli adapter Wave 1 fanno la traduzione esplicita.

## ATR Cap Behavior Table (per Wave 2 detector reference)

Helper `compute_levels_with_atr_cap(direction, entry, structural_level, atr, buffer_atr_mult, cap_atr_mult=1.5)`:

| Caso                      | direction | entry | level   | atr    | buffer×ATR | cap×ATR | Calcolo SL                                              | Vincitore       |
| ------------------------- | --------- | ----- | ------- | ------ | ---------- | ------- | ------------------------------------------------------- | --------------- |
| BUY level vicino          | BUY       | 1.10000 | 1.09900 | 0.0010 | 0.0004     | 0.00150 | max(1.09900−0.0004, 1.10000−0.00150) = max(1.09860, 1.09850) | **buffer** (1.09860) |
| BUY level lontano         | BUY       | 1.10000 | 1.09000 | 0.0010 | 0.0004     | 0.00150 | max(1.09000−0.0004, 1.10000−0.00150) = max(1.08960, 1.09850) | **cap** (1.09850)    |
| SELL level vicino         | SELL      | 1.10000 | 1.10100 | 0.0010 | 0.0004     | 0.00150 | min(1.10100+0.0004, 1.10000+0.00150) = min(1.10140, 1.10150) | **buffer** (1.10140) |
| SELL level lontano        | SELL      | 1.10000 | 1.11000 | 0.0010 | 0.0004     | 0.00150 | min(1.11000+0.0004, 1.10000+0.00150) = min(1.11040, 1.10150) | **cap** (1.10150)    |

**Regola:** il cap (1.5×ATR) protegge sempre dal SL troppo lontano (rischio per trade > target). Il buffer (0.3–0.5×ATR per setup) protegge dal noise immediato attorno al livello. Cap > buffer per costruzione del cfg → entrambi i casi convergono a uno stop "ragionevole".

**TP non calcolato qui:** ogni detector Wave 2 calcola il TP secondo la sua tesi (D-10):
- A_breakout: TP = entry + extension_factor × ATR (proiezione momentum)
- B_reversal: TP = livello strutturale opposto (S/R che ha causato il reversal)
- C_compression: TP = entry + range×expansion_target (BB-width fattorizzato)
- D_pullback: TP = swing_high/low di trend precedente

## R:R Boundary Test Coverage

Tre profile validati a soglia ±0.1 (parametrize 3×3 = 9 cases):

| Profile        | min_rr (yaml) | Test case parametrize                       | rr=2.4 / 2.5 / 2.6 (CONS) o equiv |
| -------------- | ------------- | ------------------------------------------- | --------------------------------- |
| CONSERVATIVE   | 2.5           | `test_rr_floor_conservative[2.4/2.5/2.6]`   | False / True / True               |
| MODERATE       | 1.8           | `test_rr_floor_moderate[1.7/1.8/1.9]`       | False / True / True               |
| AGGRESSIVE     | 1.3           | `test_rr_floor_aggressive[1.2/1.3/1.5]`     | False / True / True               |

Più 4 test edge: SELL symmetric (rr=2.0 hand-calc), invalid direction (`FLAT`), invalid profile (`BALANCED`), prezzi invertiti (BUY con sl>entry → False/0.0).

## Decisions Made

- **Epsilon FP 1e-9 sul confronto `rr >= min_rr`** — scoperto durante test_rr_floor_aggressive[1.3-True]: `0.001 * 1.3` produce un float `0.0013000000000000002` perché 0.001 e 0.1 non sono rappresentabili esattamente in IEEE-754. Quando dividi `(0.0013000... / 0.001)` ottieni `1.299999...`. Il confronto `1.299999... >= 1.3` ritorna False, falsamente al boundary. Soluzione: tolleranza `rr >= min_rr - 1e-9` (1e-9 è 100× più piccolo della granularità min_rr usata in cfg, 1e+8× più grande del rumore FP tipico ~1e-16). Mirror dello stesso pattern già visto in 04-02 confluence.py (`spread_tighter` con epsilon 1e-6).
- **Import locale di models.{TradeProposal,TechnicalSetup}** dentro le funzioni adapter — evita ciclo strategy.proposal → models → strategy_legacy (transitive via models che non importa direttamente strategy ma molti caller esterni mescolano i due namespace), e mantiene il livello-modulo di strategy.proposal totalmente non-side-effect. `TYPE_CHECKING` guard espone i type hint come forward-ref string.
- **`comment="python_strategy"` literal** — coerente con `IntradayStrategy.build_trade_proposal` di strategy_legacy.py (riga 414). Cambiarlo romperebbe la parity Wave 4 sul TradeProposal.comment field. Documentato in test (`assert prop.comment == "python_strategy"`).
- **`compute_levels_with_atr_cap` non calcola TP** — TP è specifico per setup (D-10): centralizzare entry/SL universale qui mantiene il detector code minimo. Il detector Wave 2 chiama il helper e poi aggiunge il TP secondo la tesi di setup, prima di chiamare `rr_meets_profile_floor` per filtrare.
- **`rr_meets_profile_floor` ritorna (False, 0.0) per risk≤0 o reward≤0** — non solleva, è fail-safe. Wave 2 detector durante esplorazione possono temporaneamente produrre draft con prezzi incoerenti rispetto a direction (es. SELL con sl<entry) prima di filtrarli; questa tolleranza permette al detector di chiamare il gate senza guard preventivi su ogni singolo branch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Floating-point boundary su `rr >= min_rr` esatto**
- **Found during:** Task 2 (`test_rr_floor_aggressive[1.3-True]` failed)
- **Issue:** Test atteso `True`, ottenuto `False`. Debug: con entry=1.10000, sl=1.09900 (risk=0.001) e rr=1.3 → tp = 1.10130. Calcolo R:R: `(1.10130 - 1.10000) / (1.10000 - 1.09900) = 0.00130000... / 0.001000... = 1.2999999...`. Il confronto `1.2999... >= 1.3` ritorna False per arithmetic FP noise.
- **Fix:** Tolleranza `rr >= min_rr - 1e-9` in `rr_meets_profile_floor`. Epsilon 1e-9 enormemente più grande del rumore FP tipico (~1e-16), enormemente più piccolo della granularità min_rr usata nel cfg (0.1).
- **Files modified:** strategy/proposal.py (3 righe: commento + condizione)
- **Verification:** Tutti 25 test passano. Re-run produce 25/25 deterministico.
- **Committed in:** `d7e10bf` (Task 2 commit, atomico col completamento test)

**2. [Rule 2 - Missing Critical] Test extra non-prescritti dal plan ma necessari per coverage**
- **Found during:** Task 2 (durante stesura test bodies)
- **Issue:** Il piano prescriveva 6 test (con 3 parametrize). Mancavano: SELL direction (la matematica risk=sl-entry/reward=entry-tp è speculare ma non testata, rischio bug regressione Wave 4), invalid profile (raise per profile non in profile_filters, fondamentale per detector che passa cfg risolto), invalid direction (sia per `rr_meets_profile_floor` sia per `compute_levels_with_atr_cap`), inverted prices (fail-safe documentato in decision sopra), missing-prices su READY (READY senza tp deve sollevare anche se direction/entry/sl ci sono), handle_NONE per draft_to_technical_setup, smoke import.
- **Fix:** Aggiunti 7 test extra (`test_rr_floor_sell_direction`, `test_rr_floor_invalid_direction`, `test_rr_floor_invalid_profile`, `test_rr_floor_returns_false_on_inverted_prices`, `test_compute_levels_atr_cap_sell_cap_overrides_far_buffer`, `test_compute_levels_atr_cap_invalid_direction`, `test_draft_to_trade_proposal_rejects_missing_prices`, `test_draft_to_technical_setup_handles_NONE`, `test_smoke_import_wave1_adapters_and_helpers`). Coverage totale 19 test definitions × 25 cases.
- **Files modified:** tests/test_strategy_proposal.py
- **Verification:** Coverage R:R floor → 3 profile × 2 direzioni × invalid paths; ATR cap → 4 quadranti BUY/SELL × buffer/cap × 2 invalid paths.
- **Committed in:** `d7e10bf`

---

**Total deviations:** 2 auto-fixed (1 Rule 1 - FP boundary bug, 1 Rule 2 - missing critical test coverage). Nessun blocker, nessun architectural decision.
**Impact on plan:** Nessuno negativo. La deviazione Rule 1 ha rilevato un boundary bug che sarebbe esploso al primo backtest reale con rr esatto al min (raro ma plausibile su dati storici). La deviazione Rule 2 ha aumentato il test count da 12 minimo richiesto a 25 totali — ben sopra acceptance criteria.

## PATTERNS.md Compliance

Implementazione segue verbatim §strategy/proposal.py per:
- ProposalDraft frozen dataclass W0 preservato senza modifiche (1:1 col PATTERNS verbatim).
- draft_to_trade_proposal/draft_to_technical_setup signature 1:1 col plan `<action>` block.
- Body verbatim col `<action>` block per le 4 funzioni; uniche aggiunte: docstring più descrittive in italiano e l'epsilon 1e-9 (Rule 1 bug-fix non previsto in PATTERNS).

## Issues Encountered

- **CRLF warnings su Windows**: `git add` ha mostrato avvisi LF→CRLF su `strategy/proposal.py` e `tests/test_strategy_proposal.py`. Comportamento normale del repo Windows (autocrlf=true), nessuna azione.
- **FP boundary debug** (cf. Deviation #1 sopra): scoperto al primo run pytest. Lezione confermata: ovunque ci sia comparison `>=` su float ottenuto via moltiplicazione/divisione, usare epsilon. Già applicato in confluence.py (W1-02), ora replicato qui.

## Known Stubs

Nessuno stub residuo introdotto da questo plan. proposal.py è completamente implementato per Wave 1. Wave-pending stubs altri moduli non toccati restano (risk_utils Wave 3, 4 setups detector Wave 2, adapter live/backtest Wave 3).

## Self-Check: PASSED

- File `strategy/proposal.py`: FOUND (217 LOC, 4 funzioni Wave 1 + ProposalDraft preservato)
- File `tests/test_strategy_proposal.py`: FOUND (239 LOC, 19 test def, 25 cases con parametrize, 0 pytest.skip)
- Commit `cc2ef77` (Task 1 RED smoke test): FOUND in git log
- Commit `17c0504` (Task 1 GREEN feat): FOUND in git log
- Commit `d7e10bf` (Task 2 test + bug-fix Rule 1): FOUND in git log
- `grep -c "def draft_to_trade_proposal" strategy/proposal.py` = 1: PASS
- `grep -c "def draft_to_technical_setup" strategy/proposal.py` = 1: PASS
- `grep -c "def rr_meets_profile_floor" strategy/proposal.py` = 1: PASS
- `grep -c "def compute_levels_with_atr_cap" strategy/proposal.py` = 1: PASS
- `grep -c "class ProposalDraft" strategy/proposal.py` = 1: PASS (W0 preservato)
- Forbidden patterns su non-comment lines (`import logging|getLogger|print\(`) = 0: PASS (purity)
- `pytest tests/test_strategy_proposal.py -v` = 25 passed in 0.41s, 0 skip: PASS
- Full suite `pytest -q` = **437 passed, 16 skipped** (delta vs Wave 1-02: +25 pass, –6 skip, +0 fail)
- Verify command da plan eseguito con success: `OK 3.0` printed

## Next Phase Readiness

**Wave 1 plan-04 (purity test AST) può iniziare**:
- `strategy/proposal.py` è già pure (zero broker/logging/print/datetime.now/I/O eccetto yaml load cached) → AST gate passerà.
- `tests/test_strategy_purity.py` (W0 stub) può ora iterare su tutti i moduli `strategy/*.py` (incluso proposal.py + confluence.py, entrambi completi).

**Wave 2 detector setups (Plan 04-05/06) può iniziare**:
- `compute_levels_with_atr_cap` disponibile per tutti e 4 i setup (universal SL math centralizzato).
- `rr_meets_profile_floor` disponibile come gate post-detection: detector calcola entry/SL/TP poi chiama il helper per filtrare se R:R sotto soglia profile.
- `score_factors`/`grade_for`/`compute_confidence` (Plan 04-02) + `draft_to_trade_proposal`/`draft_to_technical_setup` (questo plan) compongono la pipeline: detector → ProposalDraft → adapter → modelli legacy.

**Nessun blocker per i Wave successivi.**

---
*Phase: 04-strategy-refactor*
*Plan: 03 (Wave 1 proposal.py adapters + R:R floor + ATR cap)*
*Completed: 2026-05-08*
