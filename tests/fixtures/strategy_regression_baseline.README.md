# strategy_regression_baseline.json — annotation

**Re-baselined:** 2026-05-08 (post Phase 4 refactor — D-08 5-factor confluence)

## Storia del file

| Versione | Data | Codice catturato | Distribuzione setup |
|----------|------|-------------------|---------------------|
| Wave 0 (legacy) | 2026-05-08 commit `8324d5f` | `strategy_legacy.IntradayStrategy` (gate quasi-binario `trend_strength > 0.65 AND alignment SMA AND RSI band AND CLEAN breakout AND pattern`) | 10/10 NONE confidence=0.0 |
| **Phase 4 cutover (corrente)** | 2026-05-08 (option-a) | `strategy.IntradayStrategy` shim (Wave 3) → `evaluate_proposal_for_bar` → 5-factor confluence + 4 detector paralleli A/B/C/D | 2/10 NONE, 6/10 FORMING, 2/10 READY |

## Razionale re-baseline (option-a)

Il refactor Phase 4 sostituisce il **gate quasi-binario** del legacy con un motore
5-factor confluence + 4 detector pure-fn (A_breakout, B_reversal, C_compression,
D_pullback). Architetturalmente intenzionale (D-08) ma **rompe SC-5 letterale**
("behavior unchanged on regression fixture").

Sui 10 scenari baseline il nuovo motore emette:
- **2/10 NONE** (scen_2, scen_9) — gli unici dove `no_breakout_detected` E nessun
  setup paralleo trigger.
- **6/10 FORMING** — C_compression `second_compression_bar_waiting_third` (scen_1, 3, 5),
  B_reversal `at_sr_zone_waiting_pattern` (scen_4), D_pullback `trend_ok_pullback_not_in_zone`
  (scen_7, 10).
- **2/10 READY** con entry/sl/tp + confidence — A_breakout grade A su scen_6
  (EURUSD bar_offset=-150, conf 0.70) e grade B su scen_8 (USDJPY bar_offset=-350,
  conf 0.55). Entrambi hanno `breakout=CLEAN` nel fixture legacy ma erano gated
  out da `trend_strength < 0.65`.

Decisione utente: **option-a** (ACCEPT calibration + re-baseline). Il fixture
diventa il nuovo ground truth post-Wave-3 e blocca regressioni *future* sul
nuovo motore (non più sul legacy).

## Validazione richiesta (Phase 5)

⚠️ **Prima di paper deploy (Phase 11):** Il backtest comparativo Phase 5 DEVE
validare che il nuovo motore non degradi metriche aggregate (PF, drawdown,
hit-rate, expectancy) vs legacy. Se il backtest invalida la calibrazione,
si può fare revert a `option-b` (gate trend_strength sui detector) o `option-c`
(feature flag in `config/strategy.yaml`).

Il file `strategy_legacy.py` è **archiviato** in `.planning/archive/strategy_legacy.py`
con README di provenienza (NON deletato). Permette ripristino o confronto
A/B durante Phase 5 tramite re-import esplicito.

## Riferimenti

- `.planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md` — RCA + 4 opzioni decisionali + tabella delta per-scenario
- `.planning/phases/04-strategy-refactor/04-08-SUMMARY.md` — esecuzione finale post option-a
- `.planning/phases/04-strategy-refactor/04-RESEARCH.md` §Confidence Delta Risk — predizione del drift
- `.planning/phases/04-strategy-refactor/04-CONTEXT.md` D-08 — skill table A+/A/B/C/reject + base_confidence
- `tests/test_strategy_regression.py` — replay harness (tolleranze D-14: 1e-5 prezzi, 1e-4 confidence)
- `tests/capture_regression_baseline.py` — script re-capture (esegue contro `strategy.IntradayStrategy` shim)

---

*Annotation file scritto al re-baseline 2026-05-08; sostituirebbe header JSON commenti se il formato lo permettesse.*
