---
phase: 04-strategy-refactor
plan: 05
subsystem: strategy
tags: [python, pure-function, detector, breakout, pullback, atr-buffer, fib-retrace, hand-crafted-test]

requires:
  - phase: 04-strategy-refactor
    provides: 04-01 strategy/setups/{a_breakout,d_pullback}.py stub Wave 0 + tests/test_strategy_setups.py 10 stub
  - phase: 04-strategy-refactor
    provides: 04-02 score_factors / grade_for / compute_confidence (5-factor confluence)
  - phase: 04-strategy-refactor
    provides: 04-03 compute_levels_with_atr_cap + rr_meets_profile_floor + ProposalDraft
  - phase: 04-strategy-refactor
    provides: 04-04 AST purity gate (living invariant per i 7 moduli pure-fn)

provides:
  - strategy/setups/a_breakout.py (208 LOC) — detect_a_breakout READY/FORMING/NONE + _compute_levels_a (D-10)
  - strategy/setups/d_pullback.py (298 LOC) — detect_d_pullback trend-following + _compute_levels_d (D-10)
  - tests/test_strategy_setups.py (235 LOC) — 5 test no-skip A+D + helpers riusabili da plan-06

affects:
  - 04-06 (Wave 2 detector B+C): riusa _make_bars / _stub_ctx / pattern stub indicators (estendere a B+C)
  - 04-07 (Wave 3 evaluate_proposal_for_bar + IntradayStrategy shim): compone A_breakout + D_pullback in ALL_DETECTORS
  - 04-08 (Wave 4 regression replay): bit-for-bit parity vs legacy su 10 fixture (A breakout è il principale analog vs strategy_legacy.identify_entry_setup)

tech-stack:
  added: []   # zero nuove dipendenze
  patterns:
    - "getattr difensivo su tutti i campi indicators (Phase 2 contract resilience): ritorna NONE/FORMING graceful con campi mancanti"
    - "Helper _last(seq) duplicato consapevolmente in a_breakout.py e d_pullback.py (no shared utils import — preserva isolamento setup module)"
    - "_get_close/_get_low/_get_high con isinstance(bar, dict) fallback a getattr per supportare bar dict O bar oggetto"
    - "_compute_levels_a/_d delegano SL universale a strategy.proposal.compute_levels_with_atr_cap, aggiungono solo TP setup-specifico (D-10)"
    - "FORMING separa BUY (vicino a resistance) da SELL (vicino a support) — mirror legacy strategy_legacy.py:362-381"

key-files:
  created: []
  modified:
    - strategy/setups/a_breakout.py (Wave 0 stub 13 LOC → 208 LOC implementation)
    - strategy/setups/d_pullback.py (Wave 0 stub 13 LOC → 298 LOC implementation)
    - tests/test_strategy_setups.py (Wave 0 stub 49 LOC → 235 LOC: 5 test bodies + helpers; B/C/multi-match skip preservati)

key-decisions:
  - "Helper _last duplicato in a_breakout.py e d_pullback.py invece di shared util — preserva isolamento del setup module (zero cross-import fra detector); costo: 6 LOC duplicate, beneficio: cambi futuri in un detector non rompono l'altro"
  - "FORMING di Setup A separa BUY (close vicino a resistance) da SELL (close vicino a support) emettendo direction nel ProposalDraft anche se setup_type=FORMING — abilita follow-up scheduler verso il livello giusto, mirror legacy 362-381"
  - "Setup D NEVER counter-trend: direction = sign(ema50_slope). Mai BUY in down-trend né SELL in up-trend. Branch 'price_below_ema50_in_uptrend'/'price_above_ema50_in_downtrend' chiude la porta a counter-trend per costruzione — coerente con RESEARCH §Setup D 'Trend Pullback', no D-07 gate complexity richiesta qui"
  - "Pullback zone OR-logic: in_ema20_zone OR in_fib_zone. EMA20 sufficiente da sola → Setup D triggerable senza Fibonacci (resilience al gating Phase 2 dove fibonacci optional)"
  - "TP fallback Setup D usa leg_size = 1.618 × ATR quando fibonacci.leg_high/leg_low None — produce TP raggiungibile su backtest dove la lectura Fib non è ancora cached. Documentato come fallback path"
  - "_stub_indicators_d default closing_score=60 (banda neutrale 30-70) → setup_pattern D True automaticamente; test fib_38 lo eredita per coprire path Fib senza forzare manualmente. Coerente con RESEARCH Setup D continuation pattern"
  - "Boomer A2 carry-over: Setup A NON consuma `nr_detect` direttamente (è riservato a Setup C compression — vedi confluence.py:_check_setup_pattern C-branch). Quindi la decisione 'A2 verbatim CONTEXT.md (inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i]))' Phase 2 NON impatta Setup A in plan-05. Riconciliazione effettiva avviene in plan-06 (Setup C)"

patterns-established:
  - "Pattern S-D1: detector pure-fn template — guard storia → guard ATR → guard setup-specifici → score_factors + grade → _compute_levels_X → R:R floor → confidence → ProposalDraft READY (riusabile per B/C in plan-06)"
  - "Pattern S-D2: getattr-difensivo a 2 livelli per nested namespace (es. getattr(indicators, 'fibonacci', None) poi getattr(fib, 'levels', None))"
  - "Pattern S-D3: helper test-stub _stub_indicators_X(close_ref, **kw) → SimpleNamespace con liste lunghe n=200 (≥ MIN_BARS) — riproducibile per B/C"

requirements-completed: []  # STRAT-01 / STRAT-04 in-progress; full complete dopo Wave 4 regression gate

duration: ~14min
completed: 2026-05-08
---

# Phase 4 Plan 05: Wave 2 Setup A Breakout + Setup D Pullback Detectors (STRAT-01/04) Summary

**Setup A breakout (208 LOC) + Setup D trend-pullback (298 LOC) come funzioni pure consumate dal pattern Wave 3 evaluate_proposal_for_bar. R:R floor + ATR cap + 5-factor confluence + grade A+/A/B/C/reject + confidence calibrata clampata. 5 test no-skip (3 A + 2 D) in 0.38s; combined Wave 1+2 in 0.61s; full suite 447 pass + 8 skip (+5 pass / -5 skip vs Wave 1). Purity gate verde post-write per entrambi i moduli.**

## Performance

- **Duration:** ~14 min (3 task atomici sequenziali)
- **Started:** 2026-05-08
- **Completed:** 2026-05-08
- **Tasks:** 3/3
- **LOC produced:** 741 (208 a_breakout + 298 d_pullback + 235 test) — netto 666 LOC nuovi (W0 stub 13+13+49=75 → 741)
- **Suite delta:** 442 → 447 passed (+5), 13 → 8 skip (–5 sostituiti con test reali, +0 nuovi)

## Accomplishments

- **strategy/setups/a_breakout.py implementato end-to-end** (208 LOC, 3 funzioni public+helper):
  - `detect_a_breakout(bars, indicators, ctx)` → ProposalDraft (mai None) coprendo READY/FORMING/NONE
  - `_compute_levels_a(direction, entry, broken_level, atr)` → (entry, sl, tp) per D-10
  - `_last(seq)` / `_get_close(bar)` helper minimal
- **strategy/setups/d_pullback.py implementato end-to-end** (298 LOC, 4 funzioni):
  - `detect_d_pullback(bars, indicators, ctx)` → ProposalDraft trend-following per costruzione
  - `_compute_levels_d(direction, entry, pullback_extreme, atr, prior_swing, leg_size)` → (entry, sl, tp) D-10
  - `_fib_level(fib, key_str, key_float)` lettura difensiva su Fibonacci.levels (string vs float key)
  - `_last` + `_get_close/_low/_high` helper
- **5 test no-skip in tests/test_strategy_setups.py** + helper module-level (`_make_bars`, `_stub_indicators_a`, `_stub_indicators_d`, `_stub_ctx`) riusabili da plan-06
- **Pure modules verificati**: purity gate (Wave 1 plan-04) verde post-write per entrambi i detector
- **Wave 4 reconciliation reference**: confidence values dei 2 READY test catturati (vedi §Confidence Reference sotto)

## Task Commits

1. **Task 1 — Setup A detector** — `69ad6cd` (feat) — 208 LOC, READY/FORMING/NONE branches, _compute_levels_a (buffer 0.4×ATR / cap 1.5×ATR / TP 2.5×ATR)
2. **Task 2 — Setup D detector** — `a963130` (feat) — 298 LOC, trend-following per costruzione, _compute_levels_d (buffer 0.3×ATR / cap 1.5×ATR / TP prior_swing OR 1.618×leg_size fallback)
3. **Task 3 — 5 test bodies + helper module-level** — `b52aff0` (test) — 235 LOC, B/C/multi-match skip preservati per plan-06/-07

## Files Modified

### `strategy/setups/a_breakout.py` (208 LOC)

```
Public API:
  - detect_a_breakout(bars, indicators, ctx) -> ProposalDraft   # READY/FORMING/NONE

Helper:
  - _compute_levels_a(direction, entry, broken_level, atr) -> (entry, sl, tp)   # D-10
  - _last(seq), _get_close(bar)

Costanti:
  - SR_TOLERANCE_PIPS = 5    # mirror legacy SR_TOLERANCE_PIPS
  - MIN_BARS = 50            # warmup ATR/EMA50 stabili

Branch reason codes:
  insufficient_bars / atr_not_ready / last_close_missing
  no_breakout_detected / confluence_below_2_factors
  rr_below_profile_min_<rr:.2f>
  prezzo_vicino_a_resistance_attendo_breakout (FORMING BUY)
  prezzo_vicino_a_support_attendo_breakdown   (FORMING SELL)
  breakout_buy_level=<lvl:.5f> / breakout_sell_level=<lvl:.5f>   (READY)
```

### `strategy/setups/d_pullback.py` (298 LOC)

```
Public API:
  - detect_d_pullback(bars, indicators, ctx) -> ProposalDraft   # trend-following

Helper:
  - _compute_levels_d(dir, entry, pullback_extreme, atr, prior_swing, leg_size) -> (entry, sl, tp)
  - _fib_level(fib, key_str, key_float)   # lettura difensiva Fibonacci.levels
  - _last(seq), _get_close/_get_low/_get_high

Costanti:
  - MIN_BARS = 50
  - SLOPE_THRESHOLD = 0.00005   # ~5 pip / bar EUR/USD M15
  - PULLBACK_ATR_MULT = 0.5     # raggio EMA20 zone
  - PULLBACK_LOOKBACK = 5
  - FIB_RETRACE_LO/HI = 0.382 / 0.618
  - FIB_EXTENSION = 1.618
  - TP_ATR_FALLBACK_MULT = 1.618

Branch reason codes:
  insufficient_bars / atr_not_ready / ema_not_ready / last_close_missing
  no_trend_slope_below_threshold
  price_below_ema50_in_uptrend / price_above_ema50_in_downtrend
  trend_ok_pullback_not_in_zone (FORMING)
  confluence_below_2_factors / rr_below_profile_min_<rr:.2f>
  pullback_<dir>_ema20=<ema20:.5f>_slope=<slope:.6f>           (READY)
```

### `tests/test_strategy_setups.py` (235 LOC, 10 test, 5 no-skip)

```
Helpers module-level (riusabili da plan-06):
  _make_bars(closes, base_offset=0.0001) -> list[dict]
  _stub_indicators_a(close_ref, n=200) -> SimpleNamespace
  _stub_indicators_d(close_ref, ema20, ema50, slope=0.0001, fib_levels=None,
                     leg_high=None, leg_low=None, closing_score=60.0, n=200)
  _stub_ctx(profile='MODERATE', resistance=1.10500, support=1.09500,
            close_ref=1.10000, spread_pips=1.0) -> StrategyContext

5 test no-skip:
  test_detect_a_breakout_ready                      → READY/A_breakout/BUY (1.10510 oltre 1.10500)
  test_detect_a_breakout_none_no_breakout           → NONE/no_breakout_detected (1.10000 mid)
  test_detect_a_breakout_forming_near_resistance    → FORMING/A_breakout/BUY (1.10498, 0.2 pip sotto)
  test_detect_d_pullback_ema20_touch                → READY/D_pullback/BUY (close==ema20, slope+)
  test_detect_d_pullback_fib_38                     → path Fib esercitato (close in 0.382-0.618)

5 skip preservati per plan-06/-07:
  test_detect_b_reversal_ready_at_support
  test_detect_b_reversal_counter_trend_gate
  test_detect_c_compression_nr7
  test_detect_c_compression_squeeze
  test_evaluate_proposal_for_bar_multi_match_priority
```

## ATR Cap + TP Reference (Wave 4 regression bit-for-bit)

### Setup A (`_compute_levels_a`)

| Caso              | direction | entry  | broken | atr    | buffer (0.4×ATR) | cap (1.5×ATR) | SL formula                                | SL out  | TP (entry ± 2.5×ATR) |
|-------------------|-----------|--------|--------|--------|------------------|---------------|-------------------------------------------|---------|----------------------|
| BUY level vicino  | BUY       | 1.10000 | 1.09950 | 0.0010 | 0.0004           | 0.00150       | max(1.09950−0.0004, 1.10000−0.00150)      | 1.09910 | 1.10250              |
| BUY level lontano | BUY       | 1.10000 | 1.09000 | 0.0010 | 0.0004           | 0.00150       | max(1.09000−0.0004, 1.10000−0.00150)      | 1.09850 | 1.10250              |
| SELL level vicino | SELL      | 1.10000 | 1.10050 | 0.0010 | 0.0004           | 0.00150       | min(1.10050+0.0004, 1.10000+0.00150)      | 1.10090 | 1.09750              |

### Setup D (`_compute_levels_d`)

| Caso                            | direction | entry  | pullback_extreme | atr    | buffer (0.3×ATR) | cap (1.5×ATR) | TP source                               |
|---------------------------------|-----------|--------|------------------|--------|------------------|---------------|-----------------------------------------|
| BUY prior_swing valido          | BUY       | 1.10000 | 1.09800          | 0.0010 | 0.0003           | 0.00150       | prior_swing=1.10500 (lato corretto)     |
| BUY prior_swing wrong side      | BUY       | 1.10000 | 1.09800          | 0.0010 | 0.0003           | 0.00150       | fallback ext = 1.618 × leg_size         |
| BUY no fib                      | BUY       | 1.10000 | 1.09800          | 0.0010 | 0.0003           | 0.00150       | fallback ext = 1.618 × (1.618 × atr)    |

## Confidence Reference (Wave 4 reconciliation hand-crafted scenarios)

| Test                                  | Setup       | Direction | Grade | Confidence | Entry/SL/TP                              |
|---------------------------------------|-------------|-----------|-------|------------|-------------------------------------------|
| test_detect_a_breakout_ready          | A_breakout  | BUY       | A+    | **0.90**   | 1.1051 / 1.1046 / 1.1076                 |
| test_detect_d_pullback_ema20_touch    | D_pullback  | BUY       | A+    | **0.90**   | 1.101 / 1.1006 / 1.103617924             |
| test_detect_d_pullback_fib_38         | D_pullback  | BUY       | A+    | **0.90**   | (Fib path: prior_swing=1.10500 leg=0.01) |

**Adjuster firing pattern** (per A_breakout test): A+ base 0.85 + recent_winning_trade_same_pair=0 (no recent_trades) + spread_tighter +0.05 (current 1 pip < baseline 2 pip) + intermarket_score_fn=None (skip) + news_blackout_fn=None (skip) + last_2_trades_lost=N/A (no trades) + against_trend=False (factors trend_alignment=True) → 0.85 + 0.05 = **0.90** (entro bounds 0.10-0.95).

**Implicazione Wave 4**: la regression replay con tolleranza 1e-4 confidence DEVE preservare 0.90 esatto su questi 3 hand-crafted scenarios. Se il valore drift'a > 0.0001, indica regressione del path adjuster spread_tighter o del clamp bounds.

## Defensive `getattr(indicators, ..., None)` Patterns

Ogni accesso a campo di `indicators` usa `getattr` con default `None` per resilience al contract Phase 2 (campi possono essere assenti durante warmup o in fixture parziali):

| Detector       | Campi consumati con getattr-defensive                                                  |
|----------------|----------------------------------------------------------------------------------------|
| `a_breakout`   | `atr_14` (mandatory)                                                                   |
| `d_pullback`   | `atr_14` / `ema20` / `ema50` / `ema50_slope` (tutti mandatory) / `fibonacci` (optional) |
| (entrambi)     | Indirettamente via `score_factors` → `closing_score`, `rsi_14`, `volatility_regime`, `nr_detect`, `bollinger_bands` |

Quando un campo mandatory è `None`/missing, il detector ritorna `ProposalDraft(setup_type='NONE', reason=<spec>)` — **mai exception**. Questo pattern è verificato dai test:
- `test_detect_a_breakout_ready` ecc. costruiscono SimpleNamespace con campi tutti popolati → READY raggiungibile
- (acceptance criteria) `detect_a_breakout([], None, None)` → NONE/insufficient_bars (bars vuoto, indicators/ctx None)

## Decisions Made

- **Helper `_last(seq)` duplicato fra a_breakout.py e d_pullback.py** — invece di importarlo da un shared util. Preserva isolamento dei setup module: cambi futuri in un detector non possono rompere l'altro per accidente. Costo: 6 LOC duplicate. Beneficio: zero cross-import fra detector (pattern S-D1).
- **FORMING di Setup A separa BUY/SELL e include `direction`** anche se setup_type non è READY — il scheduler/follow-up può così sapere "stiamo aspettando un breakout SOPRA resistance verso BUY" invece di un FORMING ambiguo. Mirror del legacy strategy_legacy.py:362-381.
- **Setup D trend-following per costruzione, no D-07 gate** — RESEARCH §Setup D specifica "always trend-following". Rispetto a Setup B (counter-trend con D-07 gate Wave 2 plan-06), Setup D ha il branch `price_below_ema50_in_uptrend` / `price_above_ema50_in_downtrend` che chiude la porta a counter-trend a monte della 5-factor confluence. Più semplice e più robusto.
- **Pullback zone OR-logic** (`in_ema20_zone OR in_fib_zone`) — Setup D si attiva se ANCHE SOLO uno dei due path è soddisfatto. Resilience al gating Phase 2: `fibonacci` può essere `None` (es. fixture sintetica del test ema20_touch); EMA20 sufficiente da sola.
- **TP fallback Setup D 1.618×leg_size con default leg_size=1.618×ATR quando Fibonacci null** — produce TP raggiungibile anche su backtest fixture senza Fibonacci. Esempio: ATR=0.0010 → ext = 1.618 × (1.618×0.001) = 0.00261. Su EUR/USD M15 con entry=1.10100 → TP=1.10361 (test fib_38 senza prior_swing usabile).
- **`_stub_indicators_d` default `closing_score=60`** — banda neutrale 30-70 → `_check_setup_pattern("D_pullback")` ritorna True (continuation OK). I test fib_38 e ema20_touch lo ereditano automaticamente coprendo path setup_pattern senza forzare manualmente nei test.
- **Boomer A2 carry-over neutro per Setup A** — Setup A non consuma `nr_detect` (riservato a Setup C). La decisione "A2 verbatim CONTEXT.md (inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i]))" Phase 2 non impatta plan-05. Reconciliation effettiva in plan-06 (Setup C compression).

## Deviations from Plan

**Nessuna deviazione.** Plan eseguito verbatim:
- Tutti i branch READY/FORMING/NONE sono raggiungibili come da `<behavior>` block.
- 5-factor confluence + R:R floor + confidence wired identico al plan.
- Helper `_last` e `_get_close` mirror del PATTERNS skeleton.
- Costanti modulo (`SR_TOLERANCE_PIPS`, `MIN_BARS`, `SLOPE_THRESHOLD`, `PULLBACK_ATR_MULT`) verbatim.
- Test bodies allineati al plan `<action>` block (5 test richiesti, 5 implementati).
- Skip preservati per B/C/multi-match (plan esplicitamente: "leave B/C/multi-match skips intact").

**Total deviations:** 0. Nessun blocker, nessun architectural change, nessun bug Rule 1 (i moduli upstream Wave 1 plan-02/03 hanno gia' assorbito i FP-epsilon fix → non ci sono boundary FP da fixare qui).

## PATTERNS.md Compliance

Implementazione segue verbatim §strategy/setups/a_breakout.py e §strategy/setups/d_pullback.py:
- Skeleton funzione (signature, branch order) 1:1 col plan `<action>` block
- Costanti modulo verbatim
- _compute_levels_a/_d delegano a `compute_levels_with_atr_cap` (plan-03) — riuso 1:1
- score_factors / grade_for / compute_confidence (plan-02) — riuso 1:1
- Test helpers schema 1:1 col plan `<action>` block (n=200, SimpleNamespace, fields lista intera)

Aggiunte rispetto a verbatim:
- Italian docstring estesi sulle 2 funzioni public e sui 4 helper (CLAUDE.md compliance)
- `_fib_level(fib, key_str, key_float)` esplicitato come funzione (plan inline; ho refactorato per leggibilità)
- `setup_specific` arricchito con `pullback_extreme`/`leg_size`/`prior_swing` per debug/Wave 4 ispezione

## Issues Encountered

- **CRLF warnings su Windows**: `git add` ha mostrato avvisi LF→CRLF su tutti i 3 file. Comportamento normale del repo Windows (autocrlf=true), nessuna azione.
- **Nessun bug FP boundary**: a differenza dei plan 02/03 di questa phase, qui la matematica era "consume" — i livelli ATR/EMA/Fib arrivano già calcolati da Phase 2/3, e i confronti `last_close > resistance` / `abs(slope) < SLOPE_THRESHOLD` non hanno boundary critici esposti dai 5 test.
- **Confidence 0.90 vs ipotesi 0.85**: durante writing del SUMMARY ho rilevato che il test_detect_a_breakout_ready produce confidence=0.90 (non 0.85 base A+) perché l'adjuster `spread_tighter_than_baseline` fires (current spread 1 pip < baseline 2 pip → +0.05). Documentato in §Confidence Reference per Wave 4 reconciliation.

## Known Stubs

Nessuno stub introdotto da questo plan. I 2 detector A+D sono completamente implementati. Wave-pending stubs altri moduli non toccati restano:

| File                                          | Stato                                                              | Wave target |
|-----------------------------------------------|--------------------------------------------------------------------|-------------|
| `strategy/setups/b_reversal.py`               | Wave 0 stub `setup_type='NONE' reason='wave_2_pending'`            | plan-06     |
| `strategy/setups/c_compression.py`            | Wave 0 stub `setup_type='NONE' reason='wave_2_pending'`            | plan-06     |
| `strategy/risk_utils.py`                      | Stub vuoto                                                         | Wave 3 plan-07 |
| `strategy/adapters/{live,backtest}.py`        | NotImplementedError("Wave 3 ...")                                  | Wave 3 plan-07 |

## Self-Check: PASSED

- File `strategy/setups/a_breakout.py`: FOUND (208 LOC, 2 funzioni `def detect_a_breakout`/`def _compute_levels_a`)
- File `strategy/setups/d_pullback.py`: FOUND (298 LOC, 2 funzioni `def detect_d_pullback`/`def _compute_levels_d`)
- File `tests/test_strategy_setups.py`: FOUND (235 LOC, 10 test definitions: 5 implementati + 5 skip)
- Commit `69ad6cd` (Task 1 a_breakout): FOUND in git log
- Commit `a963130` (Task 2 d_pullback): FOUND in git log
- Commit `b52aff0` (Task 3 test bodies): FOUND in git log
- `grep -c "def detect_a_breakout" strategy/setups/a_breakout.py` = 1: PASS
- `grep -c "def _compute_levels_a" strategy/setups/a_breakout.py` = 1: PASS
- `grep -c "def detect_d_pullback" strategy/setups/d_pullback.py` = 1: PASS
- `grep -c "def _compute_levels_d" strategy/setups/d_pullback.py` = 1: PASS
- Forbidden patterns su a_breakout/d_pullback (`import logging|getLogger|print\(|import mt5|import strategy_legacy`) = 0: PASS (purity)
- `pytest tests/test_strategy_purity.py -x -q` = 5 passed in 0.14s: PASS (gate verde post-write)
- `pytest tests/test_strategy_setups.py -k "a_breakout or d_pullback" -v` = 5 passed in 0.38s, 0 skip: PASS
- `pytest tests/test_strategy_setups.py -k "b_reversal or c_compression or multi_match" -v` = 5 skipped: PASS (preservati per plan-06/-07)
- Combined Wave 1+2 runtime: `pytest tests/test_strategy_purity.py tests/test_strategy_confluence.py tests/test_strategy_proposal.py tests/test_strategy_setups.py -q` = 45 passed + 5 skip in **0.61s** (sotto budget 1s)
- Full suite `pytest -q` = **447 passed, 8 skipped** (delta vs Wave 1-04: +5 pass, –5 skip, +0 fail)

## Next Phase Readiness

**Wave 2 plan-06 (Setup B reversal + Setup C compression) può iniziare**:
- Helper test riusabili: `_make_bars`, `_stub_ctx` direttamente da `tests/test_strategy_setups.py` modulo level
- Pattern S-D1 (template detector) replicabile: guard storia → guard ATR → guard setup-specifici → score_factors → _compute_levels_X → R:R floor → confidence
- Setup B richiederà gate D-07 counter-trend (più complesso di Setup A/D); Setup C consumerà `nr_detect.nr4/nr7` + `bollinger_bands.squeeze` (carry-over Boomer A2 da CONTEXT.md verbatim — quella decision si applica al `_check_setup_pattern("C_compression")` predicate in `strategy/confluence.py:136-142`, già implementato)
- Estensione helper consigliata in plan-06: `_stub_indicators_b(close_ref, ...)` e `_stub_indicators_c(close_ref, nr7=True, squeeze=False, ...)` mirroring di `_stub_indicators_a/d`

**Wave 3 plan-07 (evaluate_proposal_for_bar + IntradayStrategy shim)**:
- ALL_DETECTORS già registrato in `strategy/setups/__init__.py` con i 4 detector — A_breakout + D_pullback ora completi, B/C ancora stub. Plan-07 dipende da plan-06 per essere completo.

**Wave 4 plan-08 (regression replay + reconciliation)**:
- Confidence values di riferimento (0.90 per A_breakout/D_pullback A+ con spread_tighter firing) documentati in §Confidence Reference — Wave 4 deve preservare bit-for-bit con tolleranza 1e-4

**Nessun blocker per i Wave successivi.**

---
*Phase: 04-strategy-refactor*
*Plan: 05 (Wave 2 Setup A breakout + Setup D pullback)*
*Completed: 2026-05-08*
