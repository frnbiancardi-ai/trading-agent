---
phase: 02-indicators-library
plan: 08
subsystem: indicators
tags: [python, multi-timeframe, mtf-alignment, ema-slope, sign-agreement, dead-zone, pure-functions, synthetic-stream-tests]

requires:
  - phase: 02-indicators-library
    plan: 01
    provides: pacchetto indicators/, indicators.trend.ema, calculate_trend_strength (Wave 0) preservato verbatim, fixture eurusd_h1_500
provides:
  - "indicators.mtf.align(streams: dict) -> MTFAlignmentResult per INDIC-13 (D-13/D-14)"
  - "MTFAlignmentResult dataclass length-N (score/h4_dir/h1_dir/m15_dir)"
  - "_compute_dirs helper privato: sign(EMA[i]-EMA[i-N]) con dead-zone 1e-5 (Pitfall 7)"
  - "Re-export di align + MTFAlignmentResult in indicators/__init__.py + __all__"
affects: [02-09, 04, 05, 06, 07]

tech-stack:
  added: []
  patterns:
    - "Sign-agreement multi-TF: M15 ancora, score = agreements/3 ∈ {0/3, 1/3, 2/3, 3/3}"
    - "Slope EMA via differenza N-bar (default N=3) anziché diff consecutivo (Pitfall 7)"
    - "Dead-zone relativo |delta|/|EMA| < 1e-5 → dir=0 (no-trend), separato da +/-1"
    - "Lookup latest H4/H1 bar with time <= M15[i].time (caller-side slicing + defensive)"
    - "Stream sizing nei test: M15=1200 bar (dt=60s) per coprire warmup EMA50 H4 (dt=960s, idx>=52 → t>=49920s)"
    - "Test sintetici hand-calc (no oracle pandas-ta) — pattern coerente con NR/Closing Score plan 07"

key-files:
  created:
    - tests/test_indicators_mtf.py
  modified:
    - indicators/mtf.py
    - indicators/__init__.py
    - tests/test_indicators_purity.py
  deleted: []

key-decisions:
  - "Stream sizing nei test corretto rispetto al plan-as-written (Rule 1): plan prescriveva M15=200/H1=60/H4=20 bar; con ema_period=50 + slope_lookback=3 questo produce h4_dirs tutto None (20<53) e r.score tutto None — verifica embedded e test full-coherence falliscono. Fix: M15=1200, H1=300, H4=100 bar (margine ampio sopra il warmup minimo H4 di 52 indici × 960s = 49920s di copertura M15 richiesta). Implementazione di align corretta verbatim al plan; la deviation tocca solo le costanti dei test."
  - "Dead-zone test costruito su prezzo elevato (p0=10000) e slope minima (s=0.001): |delta_EMA|/|EMA| ≈ 3*s/p ≈ 3e-7 < 1e-5 → m15_dir=0 a steady state. Coerente con Pitfall 7."
  - "Score range ufficiale {0.0, 0.33, 0.67, 1.0} (round 2 decimali): 1/3=0.33 e 2/3=0.67 dopo `round(agree/3.0, 2)`. Plan citava {0.0, 0.33, 0.66, 1.0} ma `round(2/3, 2)=0.67` (non 0.66). Test verificano 0.67 esatto come prodotto da `round(2/3, 2)`."
  - "Warmup propagato esplicitamente: a i<52 m15_dir=None → score=None (mai 0.0 spurio). Coerente con la convenzione library-wide warmup → None (D-04..D-06)."
  - "MTFAlignmentResult con 4 campi (score, h4_dir, h1_dir, m15_dir) anziché tuple: chiarezza semantica ed estendibilità (Wave 3 può aggiungere `regime` per agreement-trend hybrid senza breaking change). Coerente con BollingerResult/ADXResult/MACDResult/etc."
  - "Lookup H4/H1 latest con scan all'indietro O(len(stream)): semplice, non bottleneck per stream tipici (200-1200 bar). Se diventa hot-path su Phase 7 ML feature engineering, riscrivere con bisect — ma per Phase 2 indicator surface basta."
  - "Caller responsabile dello slicing (D-13): align defensivamente cerca ancora l'ultima bar H4/H1 con time<=t, ma documentato in docstring che il caller deve passare bar gia chiuse. Niente future leakage by construction."

patterns-established:
  - "Pattern multi-TF align: streams dict con chiavi richieste → ValueError fail-fast → per-stream EMA → dirs via N-bar slope con dead-zone → score per M15-anchor agreement"
  - "Pattern dead-zone EMA-slope: |delta|/|cur| < threshold → dir=0; coerente con A3 (RESEARCH §Open-Q6) — N=3 default tunable"
  - "Pattern stream-test sizing: per ema_period+slope_lookback warmup, scegliere n>=warmup+margine ampio (es. 1200 vs minimo 53) per evitare flakiness"
  - "Pattern leakage gate per MTF: idx alti (900..1199) dove tutti e 3 stream sono warmed; slicing time-based di tutti e 3 stream + verifica score uguale"

requirements-completed: [INDIC-13]

duration: 5min
completed: 2026-05-08
---

# Phase 2 Plan 08: Wave 3 — MTF alignment H4/H1/M15 Summary

**INDIC-13 implementato come `indicators.mtf.align(streams)` puro Python: per ciascuna barra M15 calcola un coherence score in {0.0, 0.33, 0.67, 1.0} basato sull'accordo dei segni di slope EMA50 (look-back N=3 con dead-zone 1e-5, Pitfall 7) tra H4/H1/M15. M15 e l'ancora; H4 e H1 sono allineati cercando l'ultima bar con `time <= m15[i].time` (D-13). `MTFAlignmentResult` length-N espone score + h4_dir/h1_dir/m15_dir per debug/regime classifier downstream. `calculate_trend_strength` Wave 0 preservato verbatim (linea 152, signature invariata — `strategy.py:11` continua a funzionare). 7 test sintetici hand-calc + 1 leakage test universale. Suite intera 358/358 verde + 1 skipped (350 → 358, +8: 7 mtf hand-calc + 1 mtf leakage). Una deviation Rule 1 sulle costanti di stream sizing nei test (plan-as-written underspec'd il warmup H4).**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-08T~10:00Z
- **Completed:** 2026-05-08
- **Tasks:** 2
- **Files created:** 1 (`tests/test_indicators_mtf.py`, 132 righe)
- **Files modified:** 3 (`indicators/mtf.py`, `indicators/__init__.py`, `tests/test_indicators_purity.py`)
- **Files deleted:** 0
- **Suite intera:** 358 passed, 1 skipped (350 baseline plan 07 → 358: +8 = 7 mtf hand-calc + 1 mtf leakage)

## Accomplishments

- **`align(streams: dict[str, list[dict]], ema_period=50, slope_lookback=3) -> MTFAlignmentResult`** in `indicators/mtf.py`:
  - Validazione `for required in ('H4','H1','M15')` → `ValueError` fail-fast con messaggio italiano e citazione D-13.
  - Per ciascuno stream calcola dirs via `_compute_dirs(bars, ema_period, slope_lookback)`.
  - Per ciascun M15 indice i: cerca all'indietro l'ultimo j4 con h4_times[j4] <= t e l'ultimo j1 con h1_times[j1] <= t (lookup O(stream_len), accettabile per stream tipici 200-1200 bar).
  - Se m15_dir, h4_dir o h1_dir e None → score=None (warmup propagato).
  - Altrimenti: agreements = `sum(1 for d in (d_m15, d_h4, d_h1) if d == d_m15)` → score = `round(agreements / 3.0, 2)` ∈ {0.33, 0.67, 1.0} (caso 0.0 impossibile per costruzione: m15 e sempre d'accordo con se stesso).

- **`_compute_dirs(bars, ema_period=50, slope_lookback=3, dead_zone=1e-5)`** privato:
  - EMA50 via `from indicators.trend import ema` (Wave 0 primitive).
  - Per i >= slope_lookback: `delta = ema[i] - ema[i-N]`. Se `cur=None or prev=None or cur==0` → resta None.
  - Dead-zone Pitfall 7: `abs(delta) / abs(cur) < 1e-5` → dir=0 (no-trend, slope sostanzialmente nulla).
  - Altrimenti: `delta > 0 → +1`, `delta < 0 → -1`.

- **`MTFAlignmentResult`** dataclass length-N (D-04..D-06):
  - `score: list[float | None]` — coherence in {None, 0.33, 0.67, 1.0} (0.0 impossibile per costruzione).
  - `h4_dir, h1_dir, m15_dir: list[int | None]` — direzioni allineate al timestamp M15 per debug/regime classifier.

- **`calculate_trend_strength` (Wave 0) preservato verbatim:**
  - `grep -c "^def calculate_trend_strength" indicators/mtf.py` → 1.
  - Signature `(bars, sma_fast, sma_slow, coherence_window=10) -> float` invariata.
  - `strategy.py:11` continua a importare senza modifiche.

- **Test sintetici (`tests/test_indicators_mtf.py`, 7 test):**
  - `test_align_missing_key_raises`: tre `pytest.raises(ValueError, match='H4'/'H1'/'M15')` per ciascuna chiave omessa.
  - `test_align_full_coherence_uptrend`: M15=1200/H1=300/H4=100 tutti slope positivo → ultime 100 score = 1.0.
  - `test_align_full_coherence_downtrend`: stessa shape con slope negativo → score=1.0, dirs verificati a -1.
  - `test_align_partial_coherence`: M15+H1 up, H4 down → score finale = round(2/3, 2) = 0.67.
  - `test_align_zero_score_disagreement`: M15 up, H1+H4 down → score finale = round(1/3, 2) = 0.33.
  - `test_align_warmup_returns_none`: primi 52 indici M15 → score=None, m15_dir[0]=None, m15_dir[51]=None.
  - `test_align_dead_zone_yields_zero_dir`: p0=10000 + slope=0.001 → 3*s/p ≈ 3e-7 < 1e-5 → m15_dir=0; tutti d=0 → score=1.0 a steady state.

- **Leakage gate (`tests/test_indicators_purity.py`):**
  - `test_no_future_leakage_align_synthetic`: stream M15/H1/H4 sintetici monotone-up; per idx ∈ {900, 1000, 1100, 1199} verifica `partial.score[idx] == full.score[idx]` dopo slicing time-based di tutti e 3 stream. PASS.

- **Purity runtime preservata:** `pandas_ta` NON importato da `indicators/mtf.py` (`grep` exit 1, no match). `test_no_pandas_ta_at_runtime` Wave 0 ancora verde.

- **Score range chiarito:** plan citava {0.0, 0.33, 0.66, 1.0} ma `round(2/3, 2) = 0.67` (non 0.66). Implementazione e test verificano 0.67 esatto come prodotto dal `round` (D-14 invariato; il valore 0.66 era una svista di rounding nel plan, non una specifica funzionale).

## Task Commits

1. **Task 1: align + MTFAlignmentResult + _compute_dirs** — `65464d9` (feat)
2. **Task 2: hand-calc tests + leakage gate** — `7c31e96` (test)

## Files Created/Modified

### Created
- `tests/test_indicators_mtf.py` (132 righe): 7 test hand-calc INDIC-13.

### Modified — runtime
- `indicators/mtf.py`: da 46 righe (Wave 0) a 159 righe. Aggiunti dataclass `MTFAlignmentResult`, helper privato `_compute_dirs`, funzione pubblica `align`. `calculate_trend_strength` preservato verbatim alla linea finale (152). Italian docstrings throughout.
- `indicators/__init__.py`: aggiunti `align, MTFAlignmentResult` agli import e a `__all__`.

### Modified — test
- `tests/test_indicators_purity.py`: aggiunto `test_no_future_leakage_align_synthetic`. Stream sintetici (M15=1200, H1=300, H4=100); 4 idx (900, 1000, 1100, 1199) tutti post-warmup. Pattern coerente con i 12 leakage-test esistenti.

## Decisions Made

- **Stream sizing nei test corretto (Rule 1 — bug nel plan-as-written):** plan prescriveva M15=200, H1=60, H4=20 bar. Con `ema_period=50` + `slope_lookback=3`, h4 ha bisogno di indice >=52 per `_compute_dirs` non-None — 20 bar non bastano. Conseguenza: r.score = tutti None, verifica embedded fallisce. Fix: scalare M15=1200, H1=300, H4=100 (M15 deve coprire 52*960=49920s = 832 bar al minimo). Implementazione `align` verbatim al plan; la deviation tocca solo costanti di test.

- **Dead-zone test su prezzo elevato:** scelto p0=10000 + slope=0.001 perche `|delta_EMA|/|EMA| ≈ 3*s/p`. Per dead-zone 1e-5: 3*0.001/10000 = 3e-7 < 1e-5. La condizione di test e robusta (non flakey al rounding). Alternativa scartata: forzare close costante (slope=0), ma EMA su close costante e identicamente costante e `delta=0` → la divisione `0/cur=0` e sempre < 1e-5, test sarebbe vacuo.

- **Score range {0.0, 0.33, 0.67, 1.0}:** plan diceva `0.66` ma `round(2/3, 2) = 0.67`. Implementazione produce 0.67 esatto, test asseriscono 0.67. La discrepanza nel plan e di rounding (la formula D-14 e `agreements/3` round 2 decimali — invariata).

- **Warmup esplicito a None:** a i<52 (con default ema_period=50, slope_lookback=3) m15_dir=None, quindi score=None. Niente 0.0 spurio durante il warmup. Coerente con tutti gli indicatori Phase 2 (D-04..D-06).

- **Lookup H4/H1 con scan O(stream_len) invece di bisect:** stream tipici 200-1200 bar; bisect aggiunge 1 dipendenza stdlib (`from bisect import bisect_right`) e cambia un loop semplice in API piu astratta. Trade-off: scegliamo semplicita dato che il caller del live runtime fa una sola align per cycle (5 min). Riscrivere se Phase 7 ML feature-engineering itera su 23.5 anni.

- **Caller-side slicing + defensive lookup:** D-13 dice "caller responsabile per slicing". `align` cerca comunque l'ultima bar H4/H1 con `time<=t` come safety: se il caller passa accidentalmente bar future, queste vengono ignorate. Niente future leakage by construction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stream sizing nei test verifications insufficiente per warmup H4**
- **Found during:** Task 1 embedded verify (e Task 2 test full-coherence).
- **Issue:** plan-as-written usava M15=200 bar, H1=60 bar, H4=20 bar. Con `ema_period=50` + `slope_lookback=3`, H4 richiede indice >= 52 per produrre dirs non-None (h4=20 bar → tutto None). r.score = [None]*200, verify `final == 1.0` fallisce con `expected 1.0, got None`.
- **Root cause:** plan ha sotto-specificato il warmup multi-TF: nel calcolo di sign-agreement ognuna delle 3 stream deve essere warmed (EMA50 + slope N=3 → 53 bar minimo per stream). M15 dt=60s deve coprire 52*960=49920s=832 bar minimi affinche H4 abbia >=53 bar al timestamp dell'ultima M15.
- **Fix:** rinforzato lo stream sizing in tutti i test e nella verify embedded:
  - M15: 1200 bar (era 200) dt=60s
  - H1: 300 bar (era 60) dt=240s
  - H4: 100 bar (era 20) dt=960s
  - Margine ampio (~2x) sopra il minimo per evitare flakiness.
- **Files modified:** `tests/test_indicators_mtf.py`, `tests/test_indicators_purity.py::test_no_future_leakage_align_synthetic`.
- **Verification:** tutti i 7 mtf test + 1 leakage test PASS al primo run dopo il fix; verify embedded `python -c "...assert final == 1.0..."` PASS.
- **Committed in:** `7c31e96` (Task 2 commit). L'implementazione runtime in `65464d9` (Task 1) e verbatim al plan — nessun fix di codice runtime necessario.

---

**Total deviations:** 1 auto-fixed (Rule 1 - test constants); 0 al codice runtime.
**Impact on plan:** nessuno scope creep. Pattern, formule, dataclass shape, warmup semantics, dead-zone threshold sono identici al plan-as-written. Solo le costanti dei test sono state scalate per rispettare il warmup multi-TF reale.

## Issues Encountered

- Nessun problema tecnico oltre la deviation Rule 1 sopra. Implementazione `align` verbatim al plan ha passato l'embedded verify dopo aver corretto le costanti dei test.
- Warning `Pandas4Warning` su `pandas_ta` (visibile nel summary pytest) e preesistente e non legato a questo plan.

## User Setup Required

None — nessuna nuova dipendenza, nessuna config esterna, nessun secret. Tutto il codice usa solo stdlib (`dataclasses`) + `indicators.trend.ema` (Wave 0).

## Next Wave Readiness

- **Wave 3 plan 09 (regime classifier + compute_all_extended — INDIC-14):** sblocca. Puo consumare:
  - `align(streams).score[-1]` come feature continua di MTF coherence (MTF-aligned regimes can override base regime).
  - `align(streams).m15_dir[-1]` come feature direzionale per regime trending/ranging.
- **Phase 4 (Strategy Refactor):**
  - Setup A (trend continuation): score==1.0 + m15_dir==+1/-1 come gate di entry.
  - Setup B (mean reversion): score==0.33 (M15 isolato) come compressione potenziale.
  - Setup C (volatility breakout): m15_dir==0 (dead-zone) come pre-breakout idle.
- **Phase 7 (ML Classifier):** features candidate da questo plan:
  - `mtf_align_score = align(...).score[-1]` (continua, 0.33-1.0).
  - `mtf_m15_dir = align(...).m15_dir[-1]` ∈ {-1, 0, +1} (categorical).
  - `mtf_h4_dir`, `mtf_h1_dir` (categorical).
  - `mtf_score_consistency_5 = mean(align(...).score[-5:])` (rolling stability).
- **Phase 5 (Baseline Backtest):** non blocca; preflight in 05-08 verifichera che le 9 plan di Phase 2 siano completate (7 → 8 dopo questo plan).

## Self-Check

Verifica claims fatte sopra (working dir `C:\trading-agent`):

- `[ -f tests/test_indicators_mtf.py ]` → FOUND
- `grep -c "@dataclass" indicators/mtf.py` → 1 → FOUND (MTFAlignmentResult)
- `grep -c "^def align" indicators/mtf.py` → 1 → FOUND
- `grep -c "^def _compute_dirs" indicators/mtf.py` → 1 → FOUND
- `grep -c "^def calculate_trend_strength" indicators/mtf.py` → 1 → FOUND (Wave 0 preservato)
- `grep -rE "import pandas_ta|from pandas_ta" indicators/mtf.py` → exit 1 (no match) → FOUND (purity)
- Commit `65464d9` (Task 1 feat) → FOUND in `git log`
- Commit `7c31e96` (Task 2 test) → FOUND in `git log`
- `pytest tests/test_indicators_mtf.py -x -v` → 7 passed → VERIFIED
- `pytest tests/test_indicators_purity.py::test_no_future_leakage_align_synthetic -x` → 1 passed → VERIFIED
- Suite intera `pytest` → 358 passed, 1 skipped → VERIFIED (350 baseline plan 07 + 8 nuovi)
- `from indicators import align, MTFAlignmentResult` → import success → VERIFIED
- `from indicators import calculate_trend_strength` → import success → VERIFIED (backward-compat)
- Hand-calc score levels {1.0, 0.67, 0.33} verificati su stream sintetici → VERIFIED
- Dead-zone (Pitfall 7): m15_dir=0 a slope 3e-7 < 1e-5 → VERIFIED
- Warmup primi 52 idx M15 → score=None → VERIFIED

## Self-Check: PASSED

---
*Phase: 02-indicators-library*
*Wave: 3*
*Completed: 2026-05-08*
