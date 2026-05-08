---
phase: 02-indicators-library
plan: 07
subsystem: indicators
tags: [python, narrow-range, nr4, nr7, inside-bar, boomer, closing-score, defendi, crabel, pure-functions, hand-calc-tests]

requires:
  - phase: 02-indicators-library
    plan: 01
    provides: pacchetto indicators/, fixture eurusd_h1_500, universal future-leakage gate, calculate_risk_reward (Wave 0) preservato verbatim
provides:
  - "indicators.bars.narrow_range(bars) -> NRResult (nr4, nr7, inside, boomer length-N)"
  - "indicators.bars.closing_score(bars) -> ClosingScoreResult (score length-N, None se high==low)"
  - "NRResult dataclass length-N (nr4, nr7, inside, boomer) per Crabel canonical + Assumption A2"
  - "ClosingScoreResult dataclass length-N (score) per Defendi formula"
  - "Re-export in indicators/__init__.py + __all__"
affects: [02-09, 03, 04, 05, 06, 07]

tech-stack:
  added: []
  patterns:
    - "NR4/NR7 canonical Crabel: range(i) < range(j) per j ∈ {i-1..i-k}, strettamente minore di TUTTI i priori"
    - "Inside bar: high[i] <= high[i-1] AND low[i] >= low[i-1] (estremi uguali contano come inside)"
    - "Boomer A2 (per CONTEXT.md §INDIC-10 + Open-Q4): inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])"
    - "Closing Score Defendi: (close - low) / (high - low) * 100; None su h==l (range nullo)"
    - "Warmup esplicito: nr4 None per i<3, nr7 None per i<6, inside None per i==0, boomer None per i<2 o warmup di inside/nr"
    - "Hand-calc fixture costruite ad hoc con range monotonicamente decrescenti per isolare singolo flag"

key-files:
  created:
    - tests/test_indicators_bars.py
  modified:
    - indicators/bars.py
    - indicators/__init__.py
    - tests/test_indicators_purity.py
  deleted: []

key-decisions:
  - "Boomer A2 (CONTEXT/RESEARCH) vs forex-trader-pro skill: la skill `references/price_action.md:43` definisce Boomer come 'today is both inside and an NR4. Two of these in a row' — rule più stretta che richiede inside AND nr4 su ENTRAMBI i bar (i e i-1) e ignora NR7. Il plan A2 (e CONTEXT.md §INDIC-10 line 153 'Boomer = 2+ consecutive inside-bars within NR4/7 sequence') richiede invece inside su entrambi ma NR4 OR NR7 solo sul bar corrente. Implementata A2 come da istruzione plan ('uses CONTEXT.md specifics verbatim'). Discrepanza segnalata sotto in 'Deviations / Skill check'."
  - "Boomer warmup: per i<2 boomer è None, NON False. Razionale: a i=0,1 non esiste un par di inside consecutivi possibili (inside[0]=None, inside[1] esiste solo per i=1 ma manca inside[0]). None comunica 'non calcolabile' coerente col warmup degli altri indicatori della libreria."
  - "Closing Score None su h==l (range nullo): scelta di ritornare None invece di 0.0, 50.0, o sollevare. Razionale: una doji con range 0 è un dato legittimo (pausa estrema, gap pre-aperta) ma la posizione del close non è definita matematicamente. None segnala il consumer downstream di gestire la condizione, coerente con la convenzione warmup → None."
  - "Output dataclass `NRResult` (4 liste) vs tuple di 4: dataclass per chiarezza (i campi nr4/nr7/inside/boomer hanno semantica distinta) e per estendibilità futura (Wave 3 può aggiungere `nr_count` o `compression_score` senza rompere consumer). Coerente con BollingerResult/KeltnerResult/ADXResult/etc Wave 1+."
  - "NRResult senza re-implement di range: ranges precomputed in lista esterna al loop principale per chiarezza e per evitare ricalcolo (range usato sia da NR4 che NR7). O(n) memoria addizionale, O(1) per i confronti."

patterns-established:
  - "Pattern Crabel canonical: precompute ranges → `all(ranges[i] < ranges[j] for j in range(i-k, i))` con strict less-than"
  - "Pattern Boomer warmup-aware: skip esplicito quando inside[i] o inside[i-1] sono None per evitare confusione None/False/True"
  - "Pattern leakage-gate per indicatori bar-only (non cumulativi): 5 idx parametrizzati [50,100,250,400,499] su nr4/nr7/inside/boomer + 5 idx [10,100,250,400,499] su closing_score (idx=10 ammesso perché closing_score non ha warmup)"
  - "Pattern hand-calc per Boomer: 4 bar con range monotonicamente decrescente E inside chain {bar1 inside bar0, bar2 inside bar1, bar3 inside bar2} per isolare boomer[3]=True"

requirements-completed: [INDIC-10, INDIC-11]

duration: 4min
completed: 2026-05-08
---

# Phase 2 Plan 07: Wave 2 — NR4/NR7 + Inside + Boomer + Closing Score Summary

**INDIC-10 (NR4/NR7+Inside+Boomer Crabel canonical + A2) e INDIC-11 (Closing Score Defendi) implementati come 2 funzioni pure in `indicators/bars.py`. `narrow_range(bars)` ritorna `NRResult(nr4, nr7, inside, boomer)` length-N: NR4 a i quando `range(i) < range(j)` ∀ j ∈ {i-1,i-2,i-3}; NR7 stessa regola su {i-1..i-6}; Inside via `high<=prev AND low>=prev`; Boomer A2 via `inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])`. `closing_score(bars)` ritorna `ClosingScoreResult(score)` con `(close-low)/(high-low)*100`, `None` su `high==low`. `calculate_risk_reward` Wave 0 preservato verbatim. 23 hand-calc test + 10 leakage test (5 NR + 5 CS). Suite intera 350/350 verde + 1 skipped (317 → 350, +33). Boomer rule discrepancy con skill `forex-trader-pro` segnalata: skill richiede inside+NR4 su ENTRAMBI bar; plan A2/CONTEXT richiede inside su entrambi ma NR4 OR NR7 solo sul corrente — implementato A2 verbatim come da istruzione plan.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-08T09:44:57Z
- **Completed:** 2026-05-08
- **Tasks:** 2
- **Files created:** 1 (`tests/test_indicators_bars.py`, 308 righe)
- **Files modified:** 3 (`indicators/bars.py`, `indicators/__init__.py`, `tests/test_indicators_purity.py`)
- **Files deleted:** 0
- **Suite intera:** 350 passed, 1 skipped (317 baseline plan 06 → 350: +33 = 23 hand-calc bars + 5 NR leakage + 5 CS leakage)

## Accomplishments

- **`narrow_range(bars: list[dict]) -> NRResult`** in `indicators/bars.py`:
  - Loop O(n) bar-by-bar dopo precompute `ranges = [high - low for b in bars]`.
  - NR4 a i (i>=3): `all(ranges[i] < ranges[j] for j in range(i-3, i))` — strict less-than vs TUTTI i 3 priori.
  - NR7 a i (i>=6): stesso pattern su {i-1..i-6}.
  - Inside a i (i>=1): `high[i] <= high[i-1] AND low[i] >= low[i-1]` (estremi uguali ammessi per definizione `<=`/`>=`).
  - Boomer a i (i>=2): `inside[i] AND inside[i-1] AND (nr4[i] is True OR nr7[i] is True)` — guard esplicito su `None` per evitare bool() di None.
  - Warmup uniforme: nr4[0..2]=None, nr7[0..5]=None, inside[0]=None, boomer[0..1]=None.

- **`closing_score(bars: list[dict]) -> ClosingScoreResult`**:
  - Loop O(n): per ciascun bar `(close - low) / (high - low) * 100`.
  - Edge case `high == low` (range nullo): `score[i] = None` (no div-by-zero, no exception). Documentato in docstring come "doji degenere".

- **`NRResult`, `ClosingScoreResult` dataclass** length-N (D-04..D-06): 4 e 1 campi `list[bool|None]` / `list[float|None]` rispettivamente, co-located in `indicators/bars.py`, re-exported da `indicators/__init__.py`.

- **`calculate_risk_reward` (Wave 0) preservato verbatim:** `grep -c "^def calculate_risk_reward" indicators/bars.py` → 1, signature e logica identiche al pre-plan (linea 17).

- **Hand-calc test (`tests/test_indicators_bars.py`, 23 test):**
  - `test_nr4_basic`: ranges [10,8,6,4,2] → nr4[0..2]=None, nr4[3]=True, nr4[4]=True.
  - `test_nr4_not_narrowest_returns_false`: ranges [10,8,12,4] → nr4[3]=True (4 < tutti), nr4[0..2]=None (warmup).
  - `test_nr4_false_when_a_prior_is_smaller`: ranges [10,8,3,4] → nr4[3]=False (4 NOT < 3, prior più piccolo).
  - `test_nr7_basic`: 8 bar ranges [10,9,8,7,6,5,4,3] → nr7[0..5]=None, nr7[6]=True (4 < {10,9,8,7,6,5}), nr7[7]=True (3 < {9,8,7,6,5,4}).
  - `test_inside_bar`: bar0=(10,5), bar1=(9,6) → inside[1]=True; bar2=(10,5) → inside[2]=False (high non <=).
  - `test_inside_bar_equal_extremes`: bar0=(10,5)=bar1=(10,5) → inside[1]=True (estremi uguali contano).
  - `test_boomer_two_consecutive_inside_in_nr_window`: 4 bar h={20,18,15,14}, l={0,2,5,6} (range {20,16,10,8}) → inside[2]=True, inside[3]=True, nr4[3]=True (8 < {20,16,10}) → boomer[3]=True.
  - `test_boomer_requires_inside_pair`: bar2 NON inside (high 22 > prev 18) → inside[2]=False, ma inside[3]=True e nr4[3]=True → boomer[3]=False (manca pair).
  - `test_boomer_requires_nr_window`: bar3 inside ma nr4[3]=False (range pari al prior) → boomer[3]=False.
  - `test_closing_score_three_canonical`: bar (h=2,l=1,c={1.5,2.0,1.0}) + (h=l=1,c=1) → scores [50.0, 100.0, 0.0, None].
  - `test_closing_score_full_range`: 100 bar deterministiche (random.Random(42)) con range > 0 → tutti score in [0.0, 100.0], nessuno None.
  - `test_closing_score_empty`, `test_narrow_range_empty`: input vuoto → output vuoto.
  - `test_output_length_matches_input`: 10 bar → tutte le 4 serie NR + score length=10.
  - `test_nr4_warmup_none[0,1,2]` parametrizzati: nr4 None nei 3 warmup.
  - `test_nr7_warmup_none[0..5]` parametrizzati: nr7 None nei 6 warmup.

- **Leakage gate (`tests/test_indicators_purity.py`):**
  - `test_no_future_leakage_narrow_range[50,100,250,400,499]` → 5 PASS su nr4/nr7/inside/boomer (ognuno verificato individualmente). Per costruzione ogni flag a i dipende solo da bar j<=i.
  - `test_no_future_leakage_closing_score[10,100,250,400,499]` → 5 PASS. Idx=10 ammesso (no warmup, score per bar i dipende solo da high/low/close della bar i).

- **Purity runtime:** `pandas_ta` NON importato dal modulo `indicators/bars.py` (`grep -rE "import pandas_ta|from pandas_ta" indicators/` → exit 1, no match; `test_no_pandas_ta_at_runtime` Wave 0 ancora verde).

- **Spot-check fixture EURUSD H1 (500 bar):**
  - `narrow_range(bars)` ritorna 4 serie length-500. nr4[0..2]=None, nr7[0..5]=None, inside[0]=None, boomer[0..1]=None.
  - `closing_score(bars)` ritorna 500 score (nessun None nella fixture EURUSD H1, range sempre > 0).
  - Leakage gate verde a 5 spot indices.

## Task Commits

1. **Task 1: narrow_range + closing_score (impl)** — `c22df3d` (feat)
2. **Task 2: hand-calc tests + leakage gate** — `db76242` (test)

## Files Created/Modified

### Created
- `tests/test_indicators_bars.py` (308 righe): 23 test hand-calc INDIC-10/11.

### Modified — runtime
- `indicators/bars.py`: da 14 righe (Wave 0) a 119 righe. Aggiunte 2 dataclass (`NRResult`, `ClosingScoreResult`), 2 funzioni pubbliche (`narrow_range`, `closing_score`). Italian docstrings throughout. `calculate_risk_reward` preservato verbatim alla linea 17.
- `indicators/__init__.py`: aggiunto `narrow_range, closing_score, NRResult, ClosingScoreResult` agli import e a `__all__`.

### Modified — test
- `tests/test_indicators_purity.py`: aggiunti `test_no_future_leakage_narrow_range` (5 idx) e `test_no_future_leakage_closing_score` (5 idx). Pattern coerente con i 11 leakage-test esistenti (atr, sma/ema/rsi, bollinger, keltner, adx, macd, stochastic, hurst, donchian, pivots, vwap_intraday).

## Decisions Made

- **Boomer A2 vs skill `forex-trader-pro`:** discrepanza identificata e flaggata (vedi 'Deviations / Skill check'). Implementata A2 verbatim come da istruzione plan ('uses CONTEXT.md specifics verbatim').

- **Boomer warmup `None` vs `False` per i<2:** scelta di propagare `None` (non calcolabile) invece di `False` (calcolato e negativo). Razionale concettuale: a i=0 e i=1 manca proprio il par di bar inside da valutare, quindi il flag non ha significato. Coerente con warmup di nr4/nr7/inside e con la convenzione library-wide.

- **Closing Score None su `h==l`:** scelta di ritornare None invece di 0.0/50.0/raise. Razionale: range nullo è un dato legittimo (doji estrema, gap pre-aperta, mercato fermo) ma la posizione del close nel range non è matematicamente definita. None segnala 'non applicabile' al consumer downstream, coerente con `vwap_intraday` su volume zero e con il warmup degli altri indicatori. Più sicuro di 50.0 (potrebbe indurre a credere a un valore neutro simulato) e più graceful di un raise (che farebbe esplodere la pipeline su input legittimo).

- **`NRResult` dataclass invece di tuple:** chiarezza dei campi e consistency con il pattern Wave 1+ (BollingerResult, KeltnerResult, ADXResult, MACDResult, StochasticResult, HurstResult, DonchianResult, FibonacciResult, PivotResult, VWAPResult). Estendibile in futuro (Wave 3 può aggiungere `nr_streak_count` o `compression_intensity`) senza rompere consumer esistenti.

- **Precompute `ranges` esterno al loop:** O(n) memoria addizionale ma evita ricalcolo `high-low` 4 volte (NR4) o 7 volte (NR7) per bar nel loop del confronto. Trade-off favorevole su 500+ bar tipici.

- **`closing_score` indipendente bar-per-bar:** non condivide stato con bar precedenti — purezza assoluta (leakage-free per costruzione, no cumulativi, no warmup, idx=0 è valido). Test leakage con idx=10 (vs minimo 50 per altri rolling) confermano.

## Deviations from Plan

### Auto-fixed Issues

Nessuna deviazione richiesta. Il plan è stato eseguito esattamente come scritto.

### Skill Check (output requirement del plan)

Il plan output specifica: *"documentando Boomer rule confirmation against forex-trader-pro skill (or flagging discrepancy)"*.

**Discrepancy flagged:**

- **Skill `references/price_action.md:43`:** *"Inside Narrow Range bar (Boomer constituent): today is both inside and an NR4. Two of these in a row = Boomer."* → richiede `(inside[i] AND nr4[i]) AND (inside[i-1] AND nr4[i-1])`. Più stretta. Ignora NR7.

- **Plan A2 + CONTEXT.md §INDIC-10 line 153:** *"Boomer = 2+ consecutive inside-bars within NR4/7 sequence."* → richiede `inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])`. Più larga. Ammette NR7.

- **Implementato:** versione A2/CONTEXT verbatim, come da istruzione plan ('if skill differs, executor flags via task summary and uses CONTEXT.md specifics verbatim').

- **Impatto downstream:** Phase 4 (Strategy Refactor) Setup C (volatility compression breakout) e Phase 7 (ML Classifier) feature `is_boomer` riceveranno una versione MENO stretta (più True positives su NR7 windows) di quanto la skill suggerisca. Se i backtest in Phase 5 mostrano edge basso su `is_boomer`, valutare in Wave 3 (plan 02-09 regime classifier) un parametro opzionale `strict_boomer=True` per attivare la regola della skill.

---

**Total deviations:** 0 auto-fixed; 1 skill discrepancy flagged (esplicitamente prevista dal plan).
**Impact on plan:** Nessuno scope creep. Pattern, formule, dataclass shape, warmup semantics sono identici al plan-as-written.

## Issues Encountered

- Nessun problema tecnico durante l'esecuzione. Sia RED (import fallito prima dell'impl) sia GREEN (33/33 PASS al primo run del test suite Task 2) sono andati lisci.
- Il warning `Pandas4Warning` su `pandas_ta` (visibile nel summary pytest) è preesistente e non legato a questo plan: deriva dalla versione pandas-ta dev-dep installata e dalla compatibilità futura con pandas 4.0. Non blocca, non degrada coverage.

## User Setup Required

None — nessuna nuova dipendenza, nessuna config esterna, nessun secret. Tutto il codice usa solo stdlib (`dataclasses`).

## Next Wave Readiness

- **Wave 2 plan 08 (MTF align — INDIC-13):** sblocca, indipendente da questo plan.
- **Wave 3 plan 09 (regime classifier + compute_all_extended — INDIC-14):** può ora consumare:
  - `narrow_range(bars).boomer[-1]` come flag binario per Setup C compression detection.
  - `narrow_range(bars).nr4` / `.nr7` come feature di compressione consecutiva (count rolling per ML).
  - `closing_score(bars)[-1]` come misura intra-bar dell'ultimo close (>80 = bullish absorption, <20 = bearish absorption — Defendi).
- **Phase 4 (Strategy Refactor):**
  - Setup C (volatility compression breakout): `narrow_range(...).boomer[-1] OR narrow_range(...).nr7[-1]` come trigger di compressione, da combinare con Bollinger squeeze (Wave 1) e VWAP intraday (Wave 2 plan 06).
  - Open Price Principle (Defendi rule 3): `closing_score >= 80` su un bar trend-direction conferma forte directional momentum.
- **Phase 5 (Baseline Backtest):** non blocca — preflight in 05-08 verificherà che le 9 plan di Phase 2 siano completate (6 → 7 dopo questo plan).
- **Phase 7 (ML Classifier):** features candidate da questo plan:
  - `is_boomer = narrow_range(bars).boomer[-1]` (binaria, compressione recente).
  - `is_nr4` / `is_nr7` (binarie, compressione del bar corrente).
  - `nr4_count_last_5 = sum(narrow_range(bars).nr4[-5:])` (count compressioni recenti — Defendi 'cause and effect': più cause = più effect).
  - `closing_score_last = closing_score(bars).score[-1]` (continua, posizione close 0-100).
  - `closing_score_dir_consistency = sign(close-open) * (closing_score - 50)` (positivo quando close direction allineata con range position — Open Price Principle).

## Self-Check

Verifica claims fatte sopra (working dir `C:\trading-agent`):

- `[ -f tests/test_indicators_bars.py ]` → FOUND
- `grep -c "@dataclass" indicators/bars.py` → 2 → FOUND (NRResult, ClosingScoreResult)
- `grep -c "^def narrow_range" indicators/bars.py` → 1 → FOUND
- `grep -c "^def closing_score" indicators/bars.py` → 1 → FOUND
- `grep -c "^def calculate_risk_reward" indicators/bars.py` → 1 → FOUND (Wave 0 preservato)
- `grep -rE "import pandas_ta|from pandas_ta" indicators/` → exit 1 (no match) → FOUND (purity)
- Commit `c22df3d` (Task 1 feat) → FOUND in `git log`
- Commit `db76242` (Task 2 test) → FOUND in `git log`
- `pytest tests/test_indicators_bars.py -x -v` → 23 passed → VERIFIED
- `pytest tests/test_indicators_purity.py::test_no_future_leakage_narrow_range` → 5 passed → VERIFIED
- `pytest tests/test_indicators_purity.py::test_no_future_leakage_closing_score` → 5 passed → VERIFIED
- Suite intera `pytest` → 350 passed, 1 skipped → VERIFIED (317 baseline plan 06 + 33 nuovi)
- `from indicators import narrow_range, closing_score, NRResult, ClosingScoreResult` → import success → VERIFIED
- Hand-calc canonical Closing Score: scores [50.0, 100.0, 0.0, None] → VERIFIED
- Hand-calc Boomer 4-bar: nr4[3]=True, inside[2]=True, inside[3]=True, boomer[3]=True → VERIFIED
- Skill discrepancy flagged: forex-trader-pro `price_action.md:43` (NR4 su entrambi bar) vs A2/CONTEXT.md:153 (NR4 OR NR7 sul corrente) → DOCUMENTED

## Self-Check: PASSED

---
*Phase: 02-indicators-library*
*Wave: 2*
*Completed: 2026-05-08*
