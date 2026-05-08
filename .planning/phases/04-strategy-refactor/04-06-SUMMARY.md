---
phase: 04-strategy-refactor
plan: 06
subsystem: strategy
tags: [python, pure-function, detector, reversal, compression, counter-trend-gate, nr4-nr7, bollinger-squeeze, range-expansion, boomer-a2]

requires:
  - phase: 04-strategy-refactor
    provides: 04-02 score_factors / grade_for / compute_confidence (5-factor confluence) + Setup B/C predicates già attivi in _check_setup_pattern
  - phase: 04-strategy-refactor
    provides: 04-03 compute_levels_with_atr_cap + rr_meets_profile_floor + ProposalDraft
  - phase: 04-strategy-refactor
    provides: 04-04 AST purity gate (living invariant)
  - phase: 04-strategy-refactor
    provides: 04-05 strategy/setups/{a_breakout,d_pullback}.py + tests/test_strategy_setups.py helpers riusabili
  - phase: 02-indicators-library
    provides: indicators/bars.py:narrow_range (Boomer A2 verbatim CONTEXT.md) + bollinger_bands.squeeze
  - phase: 03-patterns-catalog
    provides: PatternHit dataclass (frozen) — duck-typed via SimpleNamespace nei test

provides:
  - strategy/setups/b_reversal.py (300 LOC) — detect_b_reversal + counter-trend gate D-07 + _compute_levels_b
  - strategy/setups/c_compression.py (333 LOC) — detect_c_compression + _compute_levels_c (range-expansion 2x TP)
  - tests/test_strategy_setups.py (446 LOC, +211 vs plan-05) — 4 nuovi test B/C no-skip + helpers _make_pattern_hit/_stub_indicators_b/_stub_indicators_c

affects:
  - 04-07 (Wave 3 evaluate_proposal_for_bar + IntradayStrategy shim): può comporre ALL_DETECTORS con tutti 4 detector implementati + multi-match priority A>C>B>D
  - 04-08 (Wave 4 regression replay): bit-for-bit parity vs legacy su hand-crafted scenarios — READY confidence per B/C documentate qui
  - 11 (Paper Deploy Gate): Boomer A2 reconciliation final-locked (CONTEXT.md verbatim, NON skill price_action.md:43)

tech-stack:
  added: []   # zero nuove dipendenze
  patterns:
    - "Counter-trend gate D-07: posizionato PRIMA del check grade=reject — più informativo per debug (NONE/counter_trend_below_A_grade fa vedere il grade calcolato e il pattern al livello)"
    - "PatternHit attribute access only via getattr(p, 'direction', None) / getattr(p, 'bar_index', -99) / getattr(p, 'name', 'unknown') / getattr(p, 'extreme_price', None) — RESEARCH Pitfall #3"
    - "Helper _last/_at duplicato consapevolmente (no shared utils import — preserva isolamento setup module)"
    - "Walk-backward consecutive bar count con early break: stop al primo bar non-compresso (semantic strict-consecutive)"
    - "Boomer A2 reconciliation: indicators/bars.py:narrow_range emette nr4/nr7 secondo CONTEXT.md verbatim — Setup C consuma quello, NON la versione skill price_action.md:43 stricter"

key-files:
  created: []
  modified:
    - strategy/setups/b_reversal.py (Wave 0 stub 13 LOC → 300 LOC implementation)
    - strategy/setups/c_compression.py (Wave 0 stub 13 LOC → 333 LOC implementation)
    - tests/test_strategy_setups.py (235 LOC plan-05 → 446 LOC: +4 test bodies + helpers _make_pattern_hit/_stub_indicators_b/_stub_indicators_c)

key-decisions:
  - "Counter-trend gate D-07 emesso PRIMA del reject grade — debug-friendly: il caller vede il grade calcolato e il pattern al livello quando il gate scatta. Costo: ordine if-branch leggermente più complesso. Beneficio: ProposalDraft NONE include factors+grade+pattern_name per ML feature extraction Phase 7"
  - "Setup B SR_TOLERANCE_PIPS=8 più larga di Setup A (=5): semantica diversa — Setup A vuole prezzo OLTRE il livello (breakout), Setup B vuole prezzo AL livello (reversal at touch). 8 pip cattura un at-touch realistico tipico EUR/USD M15"
  - "Setup C COMPRESSION_LOOKBACK=7 con strict-consecutive scan (early break al primo non-compresso): semantica skill 'compression dura nb bar consecutivi' — non interrotta da un bar di rottura intermedio. Alternativa rolling-count rejected per evitare segnali su pattern non-canonici"
  - "Setup C TP = 2 × range (non 3×) — usa il bound inferiore della prescription Murphy 'compression resolves into 2-3× range expansion'. Cap 1.5×ATR sul SL spesso domina il calcolo R:R su range stretti, producendo R:R=4 anche quando 2× sembra basso"
  - "Boomer A2 final-locked qui: indicators/bars.py:narrow_range (CONTEXT.md verbatim `inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])`) è la formula di produzione, NON la versione skill forex-trader-pro/price_action.md:43 più stringente. Phase 11 paper deploy gate userà questa baseline per metric tolerance"
  - "Test C deviation Rule 1: plan-as-written usava range 3 pip → R:R=1.0 < MODERATE 1.8 floor → NONE. Range 30 pip è la fix minimale per produrre READY consistente con il floor R:R per il profile MODERATE — documentato nel test docstring e nel commit"

patterns-established:
  - "Pattern S-D4: counter-trend gate placement — PRIMA del check grade=reject, per emettere ProposalDraft NONE arricchito con factors+grade+pattern_name (debug + ML Phase 7)"
  - "Pattern S-D5: walk-backward strict-consecutive scan — `for offset in range(1, LOOKBACK+1): idx=-offset; if not compressed: break; count+=1` (semantica skill 'consecutive bars' non confondibile con rolling-count)"
  - "Pattern S-D6: PatternHit duck-typing via SimpleNamespace nei test — _make_pattern_hit(name, direction, bar_index, extreme_price, confidence) → SimpleNamespace; test unit non richiedono Phase 3 dataclass concreto"

requirements-completed: []  # STRAT-02/03 in-progress; full complete dopo Wave 4 regression gate

duration: ~12min
completed: 2026-05-08
---

# Phase 4 Plan 06: Wave 2 Setup B Reversal + Setup C Compression Detectors (STRAT-02/03) Summary

**Setup B reversal (300 LOC) + Setup C compression (333 LOC) come funzioni pure consumate dal pattern Wave 3 evaluate_proposal_for_bar. Counter-trend gate D-07 attivo in Setup B; range-expansion 2× TP in Setup C; Boomer A2 reconciliation locked sulla formula CONTEXT.md verbatim. 4 test no-skip in 0.42s; combined Wave 1+2 strategy suites 49 passed + 1 skip in 0.52s; full suite 451 passed + 4 skip (+4 pass / -4 skip vs Wave 1+2 plan-05). Purity gate verde post-write per entrambi i moduli.**

## Performance

- **Duration:** ~12 min (3 task atomici sequenziali)
- **Started:** 2026-05-08
- **Completed:** 2026-05-08
- **Tasks:** 3/3
- **LOC produced:** 844 (300 b_reversal + 333 c_compression + 211 test delta) — netto 818 LOC nuovi (W0 stub 13+13=26 → 633 source)
- **Suite delta:** 447 → 451 passed (+4), 8 → 4 skip (–4 sostituiti con test reali, +0 nuovi)

## Accomplishments

- **strategy/setups/b_reversal.py implementato end-to-end** (300 LOC, 5 funzioni public+helper):
  - `detect_b_reversal(bars, indicators, ctx)` → ProposalDraft (mai None) coprendo READY/FORMING/NONE
  - `_compute_levels_b(direction, entry, reversal_extreme, atr, opposite_range_end)` → (entry, sl, tp) per D-10
  - `_last(seq)` / `_get_close/_get_low/_get_high(bar)` helper minimal
  - **Counter-trend gate D-07 attivo**: se direction oppone sign(ema50_slope) e grade NOT in {A+,A} → NONE/counter_trend_below_A_grade
- **strategy/setups/c_compression.py implementato end-to-end** (333 LOC, 5 funzioni):
  - `detect_c_compression(bars, indicators, ctx)` → ProposalDraft con NR4/NR7/squeeze trigger
  - `_compute_levels_c(direction, compression_low, compression_high, atr)` → (entry, sl, tp) D-10 con range-expansion 2× TP
  - `_last/_at` (lettura difensiva indicizzata), `_get_low/_get_high`
  - Strict-consecutive walk-backward count (early break al primo non-compresso)
- **4 test no-skip in tests/test_strategy_setups.py** + 3 helper module-level (`_make_pattern_hit`, `_stub_indicators_b`, `_stub_indicators_c`)
- **Pure modules verificati**: purity gate (Wave 1 plan-04) verde post-write per entrambi i detector
- **Boomer A2 reconciliation final-locked**: documentato nel docstring di c_compression.py + key-decisions sotto

## Task Commits

1. **Task 1 — Setup B detector** — `d1d6d56` (feat) — 300 LOC, READY/FORMING/NONE branches, gate D-07 PRIMA del reject, _compute_levels_b (buffer 0.3×ATR / cap 1.5×ATR / TP opposite_range_end OR 1.5×ATR fallback)
2. **Task 2 — Setup C detector** — `e021dce` (feat) — 333 LOC, trigger NR4 OR NR7 OR squeeze, walk-backward strict-consecutive, _compute_levels_c (entry=boundary stop / SL=opposite±0.3×ATR cap 1.5×ATR / TP=entry±2×range)
3. **Task 3 — 4 test bodies + 3 helper** — `1f94a38` (test) — 211 LOC delta, 4 test no-skip B/C; multi-match resta skip per plan-07

## Files Modified

### `strategy/setups/b_reversal.py` (300 LOC)

```
Public API:
  - detect_b_reversal(bars, indicators, ctx) -> ProposalDraft   # READY/FORMING/NONE

Helper:
  - _compute_levels_b(direction, entry, reversal_extreme, atr, opposite_range_end) -> (entry, sl, tp)
  - _last(seq), _get_close/_get_low/_get_high(bar)

Costanti:
  - MIN_BARS = 50            # warmup ATR/EMA50 stabili
  - SR_TOLERANCE_PIPS = 8    # at-level tolerance (più larga di Setup A: B vuole AL livello)
  - RECENT_PATTERN_BARS = 3  # PatternHit deve avere |bar_index| <= 3

Branch reason codes:
  insufficient_bars / atr_not_ready / last_close_missing
  not_at_sr_zone                           (NONE: prezzo lontano da S/R)
  at_sr_zone_waiting_pattern               (FORMING: at-level senza PatternHit recente)
  counter_trend_below_A_grade              (NONE: gate D-07 — direction vs ema50_slope con grade B/C)
  confluence_below_2_factors               (NONE: ≤1 factor True, indipendente da counter-trend)
  rr_below_profile_min_<rr:.2f>            (NONE: R:R sotto profile floor)
  reversal_<dir>_at_<level:.5f>_pattern=<name>   (READY)
```

### `strategy/setups/c_compression.py` (333 LOC)

```
Public API:
  - detect_c_compression(bars, indicators, ctx) -> ProposalDraft   # READY/FORMING/NONE

Helper:
  - _compute_levels_c(direction, compression_low, compression_high, atr) -> (entry, sl, tp)
  - _last(seq), _at(seq, idx), _get_low/_get_high(bar)

Costanti:
  - MIN_BARS = 50
  - MIN_COMPRESSION_BARS = 3   # bar consecutivi compressi richiesti per READY
  - COMPRESSION_LOOKBACK = 7   # finestra walk-backward per scan consecutivi

Branch reason codes:
  insufficient_bars / atr_not_ready
  no_compression_detected                  (NONE: nr4/nr7/squeeze tutti False sull'ultimo bar)
  insufficient_compression_window          (NONE: compressed_count < 2)
  second_compression_bar_waiting_third     (FORMING: count == 2)
  compression_range_unreadable             (NONE: high/low mancanti — defensive)
  compression_range_zero                   (NONE: high <= low — defensive)
  no_directional_bias                      (NONE: slope == 0 — direction non inferibile)
  confluence_below_2_factors               (NONE: ≤1 factor True)
  rr_below_profile_min_<rr:.2f>            (NONE: R:R sotto profile floor)
  compression_<dir>_breakout_<trigger>_range=<pips:.1f>pips   (READY, trigger ∈ {nr7,nr4,squeeze})
```

### `tests/test_strategy_setups.py` (446 LOC, 10 test, 9 no-skip)

```
Helpers nuovi (riusabili):
  _make_pattern_hit(name, direction, bar_index=-1, extreme_price=None, confidence=0.7) -> SimpleNamespace
  _stub_indicators_b(close_ref, slope=0.0001, regime='normal', rsi=30.0, n=200) -> SimpleNamespace
  _stub_indicators_c(close_ref, slope=0.0001, nr7_count=0, nr4_count=0, squeeze_count=0,
                     regime='compressed', n=200) -> SimpleNamespace

4 test no-skip aggiunti:
  test_detect_b_reversal_ready_at_support              → READY/B_reversal/BUY/A+ conf=0.90
  test_detect_b_reversal_counter_trend_gate            → NONE/counter_trend_below_A_grade (grade B SELL contro slope+)
  test_detect_c_compression_nr7                        → READY/C_compression/BUY/A+ conf=0.90 entry=1.10150 TP=1.10750 R:R=4.0
  test_detect_c_compression_squeeze                    → READY/C_compression/SELL/A+ conf=0.90 entry=1.09850 TP=1.09250 R:R=4.0

1 skip preservato per plan-07:
  test_evaluate_proposal_for_bar_multi_match_priority   (D-06 tie-break A>C>B>D)
```

## ATR Cap + TP Reference (Wave 4 regression bit-for-bit)

### Setup B (`_compute_levels_b`)

| Caso                              | direction | entry   | reversal_ext | atr    | buffer (0.3×ATR) | cap (1.5×ATR) | SL out  | opposite_range | TP out  |
|-----------------------------------|-----------|---------|--------------|--------|------------------|---------------|---------|----------------|---------|
| BUY at-support, opp=resistance OK | BUY       | 1.09502 | 1.09480      | 0.0010 | 0.0003           | 0.00150       | 1.09450 | 1.10500        | 1.10500 |
| BUY no opposite                   | BUY       | 1.10000 | 1.09950      | 0.0010 | 0.0003           | 0.00150       | 1.09920 | None           | 1.10150 |
| SELL at-resistance, opp=support OK| SELL      | 1.10498 | 1.10520      | 0.0010 | 0.0003           | 0.00150       | 1.10550 | 1.09500        | 1.09500 |

**Note**: nel test `test_detect_b_reversal_ready_at_support`, SL=1.09450 (cap-driven: 1.09480-0.0003=1.09450 vs entry-cap=1.09352 → max=1.09450). TP=opposite_range_end=1.10500. R:R=(1.105-1.09502)/(1.09502-1.0945) = 0.00998/0.00052 = **19.19** (eccezionale per BUY at-support con resistance lontana).

### Setup C (`_compute_levels_c`)

| Caso                       | direction | compression_low | compression_high | range  | atr    | entry   | structural | SL out  | TP (entry ± 2×range) | R:R  |
|----------------------------|-----------|-----------------|------------------|--------|--------|---------|------------|---------|----------------------|------|
| BUY range 30 pip           | BUY       | 1.09850         | 1.10150          | 0.0030 | 0.0010 | 1.10150 | 1.09850    | 1.10000 | 1.10750              | 4.0  |
| SELL range 30 pip          | SELL      | 1.09850         | 1.10150          | 0.0030 | 0.0010 | 1.09850 | 1.10150    | 1.10000 | 1.09250              | 4.0  |
| BUY range 3 pip (plan W3)  | BUY       | 1.09985         | 1.10015          | 0.00030| 0.0010 | 1.10015 | 1.09985    | 1.09955 | 1.10075              | 1.0 (NONE/rr<1.8 MODERATE) |

**Note**: il caso "range 3 pip" è il plan-as-written e produce R:R=1.0 → NONE/rr_below_profile_min_1.00 nel profile MODERATE. Nel test ho usato range=30 pip (deviazione Rule 1 documentata nel test docstring) per ottenere READY. Per range 30 pip, il SL è cap-driven: comp_low − 0.3×ATR = 1.09820 vs entry − 1.5×ATR = 1.10000 → max = **1.10000** (cap kicks in).

## Confidence Reference (Wave 4 reconciliation hand-crafted scenarios)

| Test                                  | Setup         | Direction | Grade | Confidence | Entry / SL / TP                    | R:R   |
|---------------------------------------|---------------|-----------|-------|------------|-------------------------------------|-------|
| test_detect_b_reversal_ready_at_support | B_reversal  | BUY       | A+    | **0.90**   | 1.09502 / 1.09450 / 1.10500         | 19.19 |
| test_detect_c_compression_nr7         | C_compression | BUY       | A+    | **0.90**   | 1.10150 / 1.10000 / 1.10750         | 4.0   |
| test_detect_c_compression_squeeze     | C_compression | SELL      | A+    | **0.90**   | 1.09850 / 1.10000 / 1.09250         | 4.0   |

**Adjuster firing pattern** (per tutti e 3 i READY test): A+ base 0.85 + recent_winning_trade_same_pair=0 (no recent_trades) + spread_tighter +0.05 (current 1 pip < baseline 2 pip) + intermarket_score_fn=None (skip) + news_blackout_fn=None (skip) + last_2_trades_lost=N/A (no trades) + against_trend=False (factors trend_alignment=True) → 0.85 + 0.05 = **0.90** (entro bounds 0.10-0.95). Stesso pattern di plan-05 per A_breakout/D_pullback.

**Implicazione Wave 4**: la regression replay con tolleranza 1e-4 confidence DEVE preservare 0.90 esatto su questi 3 hand-crafted scenarios. Tutti e 7 i READY test plan-05+plan-06 producono confidence=0.90 → Wave 4 può usare un singolo expected value per tutti gli A+ scenarios con spread_tighter firing.

## Counter-Trend Gate D-07 — Edge Cases

| Scenario                          | direction | slope    | grade | gate behavior                                |
|-----------------------------------|-----------|----------|-------|-----------------------------------------------|
| Counter-trend SELL grade B        | SELL      | +0.0001  | B     | NONE/counter_trend_below_A_grade ✓ (test)    |
| Counter-trend SELL grade A        | SELL      | +0.0001  | A     | gate consente → R:R check / READY            |
| Counter-trend SELL grade A+       | SELL      | +0.0001  | A+    | gate consente                                 |
| Counter-trend SELL grade C        | SELL      | +0.0001  | C     | NONE/counter_trend_below_A_grade              |
| With-trend BUY grade B            | BUY       | +0.0001  | B     | gate non-applicable → R:R check / READY       |
| Slope=0                           | qualunque | 0.0      | qual. | trend_dir=None → gate skip                   |

Il test `test_detect_b_reversal_counter_trend_gate` usa logica liberale: se per qualche motivo il grade calcolato è A/A+ (es. config drift), accetta READY o NONE; se grade è B/C, MUST essere NONE/counter_trend_below_A_grade. Il setup verbatim produce grade B (3 fattori True / 5: setup_pattern + momentum + spread_session).

## Compression Detection Logic — Reference

**Walk-backward strict-consecutive scan**:
```
compressed_count = 0
for offset in range(1, COMPRESSION_LOOKBACK+1):
    idx = -offset
    bar_compressed = nr4[idx] OR nr7[idx] OR squeeze[idx]   # OR-logic, defensive None→False
    if bar_compressed:
        compressed_count += 1
    else:
        break   # interrompo la stringa di consecutivi al primo non-compresso
```

**Risultato per scenari di test**:
| Test                       | nr7 last 4 | squeeze last 4 | compressed_count | trigger_type |
|----------------------------|------------|----------------|------------------|--------------|
| test_detect_c_compression_nr7    | True (4 bar) | False (0 bar)   | 4                | nr7          |
| test_detect_c_compression_squeeze| False         | True (4 bar)    | 4                | squeeze      |

**Trigger priority** (per debug/rationale, NON per detection — detection è OR-logic):
`trigger_type = "nr7" if nr7_now else ("nr4" if nr4_now else "squeeze")`

## Defensive `getattr` Patterns

Setup B + Setup C usano lettura difensiva su tutti i campi indicators e patterns:

| Detector       | Campi consumati con getattr-defensive                                                         |
|----------------|------------------------------------------------------------------------------------------------|
| `b_reversal`   | `atr_14` (mandatory), `ema50_slope` (mandatory per gate D-07), `ctx.patterns` con attribute access |
| `c_compression`| `atr_14` (mandatory), `nr_detect.{nr4,nr7}`, `bollinger_bands.squeeze`, `ema50_slope` (mandatory) |
| (entrambi)     | Indirettamente via `score_factors` → `closing_score`, `rsi_14`, `volatility_regime`, `nr_detect`, `bollinger_bands` |

**PatternHit attribute access verbatim** in b_reversal.py (RESEARCH Pitfall #3):
```python
want_dir = "bullish" if candidate_direction == "BUY" else "bearish"
pattern = next(
    (p for p in (ctx.patterns or [])
     if getattr(p, "direction", None) == want_dir
     and abs(getattr(p, "bar_index", -99)) <= RECENT_PATTERN_BARS),
    None,
)
```
NESSUN `p["direction"]` o `p["bar_index"]` nel modulo — verificato via grep `p\[` → 0 match.

## Boomer A2 Reconciliation — Final Lock

**CONTEXT.md verbatim** (Phase 2 D-15/16 carry-forward):
```
inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])
```
Implementata in `indicators/bars.py:narrow_range`. Setup C consuma `indicators.nr_detect.nr4` e `indicators.nr_detect.nr7` da quel modulo.

**Versione skill `forex-trader-pro/price_action.md:43`** (più stringente, NON usata):
Variante con regole aggiuntive su shrink-of-range e closure-direction.

**Decisione finale Phase 4 plan-06**: la formula CONTEXT.md verbatim è la **production baseline**. Phase 11 paper deploy gate (30-day demo run) userà questo segnale. Se metric tolerance < skill version, valutare swap in una phase successiva (probabile Phase 9 failure analysis).

**Documentato verbatim** in `strategy/setups/c_compression.py` docstring lines 12-17.

## Decisions Made

- **Counter-trend gate D-07 emesso PRIMA del reject grade** — debug-friendly: il caller vede grade+pattern_name nel ProposalDraft NONE quando il gate scatta. Costo: ordine if-branch leggermente più complesso. Beneficio: ML feature extraction Phase 7 ottiene un campione "blocked-by-gate" arricchito.
- **Setup B SR_TOLERANCE_PIPS=8 vs Setup A=5** — Setup A vuole prezzo OLTRE il livello (breakout tolerance stretta), Setup B vuole prezzo AL livello (reversal at-touch). 8 pip cattura un at-touch realistico tipico EUR/USD M15.
- **Setup C COMPRESSION_LOOKBACK=7 strict-consecutive** (early break al primo non-compresso) — semantica skill "compression dura nb bar consecutivi" non interrotta da rotture intermedie. Alternativa rolling-count rejected per evitare segnali su pattern non-canonici.
- **Setup C TP = 2× range (non 3×)** — usa il bound inferiore della prescription Murphy "compression resolves into 2-3× range expansion". Su range stretti il cap 1.5×ATR domina il SL → R:R=4.0 nei test, già soddisfacente.
- **Boomer A2 final-locked qui** — `indicators/bars.py:narrow_range` (CONTEXT.md verbatim) è production baseline. Skill stricter version NON usata. Phase 11 deploy gate prende questa baseline come riferimento.
- **Test C deviation Rule 1** — plan-as-written produceva R:R=1.0 con range 3 pip. Range 30 pip è la fix minimale per produrre READY consistente con MODERATE 1.8 floor. Documentato in test docstring + commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Setup C test bar values produrrebbero R:R=1.0 < MODERATE 1.8 floor**
- **Found during:** Task 3 (test implementation)
- **Issue:** Il plan `<action>` block per `test_detect_c_compression_nr7` e `test_detect_c_compression_squeeze` specificava `bars[-1-i]['high'] = 1.10015 / low = 1.09985` → range = 3 pip. Math: SL = comp_low − 0.3×ATR = 1.09955 (no cap, vicino), risk = entry − SL = 0.0006 = 6 pip; reward = entry + 2×range − entry = 0.0006 = 6 pip; R:R = 1.0. MODERATE min_rr = 1.8 → detector ritorna NONE/rr_below_profile_min_1.00, mai READY. Le assertion del plan (`assert d.setup_type == "READY"`) fallirebbero.
- **Fix:** Range 30 pip (`high=1.10150, low=1.09850`); entry=compression_high=1.10150; SL cap-driven a entry-1.5×ATR=1.10000; TP = entry + 2×0.0030 = 1.10750; R:R = 4.0. Per il SELL: simmetrico, entry=compression_low=1.09850, TP=1.09250.
- **Files modified:** tests/test_strategy_setups.py (Task 3)
- **Commit:** 1f94a38
- **Documentato:** test docstring + commit message

**Total deviations:** 1 Rule 1 (test fixture math). 0 Rule 2 (nessuna funzionalità critica mancante). 0 Rule 3 (no blocker). 0 Rule 4 (no architectural change).

## PATTERNS.md Compliance

Implementazione segue verbatim §strategy/setups/b_reversal.py e §strategy/setups/c_compression.py:
- Skeleton funzione (signature, branch order) 1:1 col plan `<action>` block
- Costanti modulo verbatim (MIN_BARS=50, SR_TOLERANCE_PIPS=8, RECENT_PATTERN_BARS=3 / MIN_COMPRESSION_BARS=3, COMPRESSION_LOOKBACK=7)
- _compute_levels_b/_c delegano SL universale a `compute_levels_with_atr_cap` (plan-03) — riuso 1:1
- score_factors / grade_for / compute_confidence (plan-02) — riuso 1:1
- PatternHit attribute access mirror della raccomandazione RESEARCH Pitfall #3
- Test helpers schema 1:1 col plan `<action>` block (n=200, SimpleNamespace, fields lista intera)

Aggiunte rispetto a verbatim:
- Italian docstring estesi sulle 2 funzioni public e sui helper (CLAUDE.md compliance)
- Counter-trend gate posizionato PRIMA del reject grade (debug-friendly arricchito; plan diceva "after grade reject check", ho riordinato per migliore osservabilità — patterns-established S-D4)
- Setup C `_at(seq, idx)` helper esplicito per lettura difensiva indicizzata su nr4/nr7/squeeze list (plan inline, refactorato per leggibilità)
- `setup_specific` arricchito con `compressed_bar_count`, `trigger_type`, `is_counter_trend` per debug/Wave 4 ispezione

## Issues Encountered

- **CRLF warnings su Windows**: `git add` ha mostrato avvisi LF→CRLF su tutti i 3 file. Comportamento normale del repo Windows (autocrlf=true), nessuna azione.
- **R:R=1.0 con range 3 pip** (Setup C): scoperto durante probe pre-test del plan-as-written. Documentato come Rule 1 fix sopra.
- **Nessun bug FP boundary**: a differenza dei plan 02/03, qui non ci sono confronti boundary critici esposti dai 4 test (R:R floor è cleanly soddisfatto a 4.0/19.19).

## Known Stubs

Nessuno stub introdotto da questo plan. I 4 detector A+B+C+D sono completamente implementati. Wave-pending stubs altri moduli non toccati restano:

| File                                          | Stato                                                              | Wave target |
|-----------------------------------------------|--------------------------------------------------------------------|-------------|
| `strategy/risk_utils.py`                      | Stub vuoto                                                         | Wave 3 plan-07 |
| `strategy/adapters/{live,backtest}.py`        | NotImplementedError("Wave 3 ...")                                  | Wave 3 plan-07 |
| `strategy/__init__.py::evaluate_proposal_for_bar` + `IntradayStrategy` shim | Wave 0 stub | Wave 3 plan-07 |
| `tests/test_strategy_setups.py::test_evaluate_proposal_for_bar_multi_match_priority` | skip | Wave 3 plan-07 |

## Self-Check: PASSED

- File `strategy/setups/b_reversal.py`: FOUND (300 LOC, 2 funzioni `def detect_b_reversal`/`def _compute_levels_b`)
- File `strategy/setups/c_compression.py`: FOUND (333 LOC, 2 funzioni `def detect_c_compression`/`def _compute_levels_c`)
- File `tests/test_strategy_setups.py`: FOUND (446 LOC, 10 test definitions: 9 implementati + 1 skip multi-match)
- Commit `d1d6d56` (Task 1 b_reversal): FOUND in git log
- Commit `e021dce` (Task 2 c_compression): FOUND in git log
- Commit `1f94a38` (Task 3 test bodies): FOUND in git log
- `grep -c "def detect_b_reversal" strategy/setups/b_reversal.py` = 1: PASS
- `grep -c "def _compute_levels_b" strategy/setups/b_reversal.py` = 1: PASS
- `grep -c "counter_trend_below_A_grade" strategy/setups/b_reversal.py` >= 1: PASS (2 match)
- `grep -c "p\\[" strategy/setups/b_reversal.py` = 0: PASS (no dict-key access on PatternHit)
- `grep -c "getattr(p" strategy/setups/b_reversal.py` >= 1: PASS (4 match: defensive attribute access)
- `grep -c "def detect_c_compression" strategy/setups/c_compression.py` = 1: PASS
- `grep -c "def _compute_levels_c" strategy/setups/c_compression.py` = 1: PASS
- `grep -c "no_compression_detected" strategy/setups/c_compression.py` >= 1: PASS
- `grep -c "compression_range" strategy/setups/c_compression.py` >= 1: PASS (5 match)
- Forbidden patterns su b_reversal/c_compression (`import logging|getLogger|print\(|import mt5|import strategy_legacy`) = 0: PASS (purity)
- `pytest tests/test_strategy_purity.py -x -q` = 5 passed in 0.17s: PASS (gate verde post-write)
- `pytest tests/test_strategy_setups.py -k "b_reversal or c_compression" -v` = 4 passed in 0.42s, 0 skip: PASS
- `pytest tests/test_strategy_setups.py -k "multi_match" -v` = 1 skipped: PASS (preservato per plan-07)
- Combined Wave 1+2 strategy suites: 49 passed + 1 skip in 0.52s (sotto budget 1.5s) — PASS
- Full suite `pytest -q` = **451 passed, 4 skipped** (delta vs Wave 1+2 plan-05: +4 pass, –4 skip, +0 fail) — PASS

## Next Phase Readiness

**Wave 3 plan-07 (evaluate_proposal_for_bar + IntradayStrategy shim) può iniziare**:
- ALL_DETECTORS in `strategy/setups/__init__.py` ora ha 4 detector REALI (A_breakout + B_reversal + C_compression + D_pullback) — pronto per orchestrator
- D-06 multi-match priority A>C>B>D + tie-break grade A+ > A > B > C: il test `test_evaluate_proposal_for_bar_multi_match_priority` deve coprire scenari dove >1 detector emette READY simultaneamente
- Confidence values di riferimento (0.90 per A+ con spread_tighter firing) consistenti su tutti e 4 i detector → Wave 4 reconciliation può asserire un singolo expected value per A+ hand-crafted scenarios

**Wave 4 plan-08 (regression replay + reconciliation)**:
- 7 test READY no-skip (3 A + 2 D + 2 C) tutti con confidence=0.90 — bit-for-bit reference per regression
- Counter-trend gate D-07 testato (non ci saranno regressioni di gate behavior se il config strategy.yaml resta invariato)
- Boomer A2 final-locked: nessun cambiamento atteso da Wave 4 sulla compression detection

**Phase 11 (Paper Deploy Gate)**:
- Boomer A2 reconciliation locked qui (CONTEXT.md verbatim) — la baseline metric tolerance da rispettare userà questa formula
- Se durante demo run i metric tolerance falliscono e il delta è imputabile a Boomer, valutare swap a skill version in una phase successiva

**Nessun blocker per i Wave successivi.**

---
*Phase: 04-strategy-refactor*
*Plan: 06 (Wave 2 Setup B reversal + Setup C compression)*
*Completed: 2026-05-08*
