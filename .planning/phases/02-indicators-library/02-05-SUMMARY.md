---
phase: 02-indicators-library
plan: 05
subsystem: indicators
tags: [python, donchian, fibonacci, pivots, camarilla, ny-17, dst, pure-functions, hand-calc-tests]

requires:
  - phase: 02-indicators-library
    plan: 01
    provides: pacchetto indicators/, _session_id_ny17, fixture eurusd_h1_500, universal future-leakage gate
provides:
  - "indicators.structure.donchian(highs, lows, length=20) -> DonchianResult"
  - "indicators.structure.fibonacci_retracements(bars, lookback=100, window=2) -> FibonacciResult"
  - "indicators.structure.pivots(bars, anchor='daily'|'weekly') -> PivotResult (classico + Camarilla 1.1/{12,6,4,2})"
  - "DonchianResult, FibonacciResult, PivotResult dataclass (D-04..D-06)"
  - "Re-export in indicators/__init__.py + __all__"
affects: [02-09, 03, 04, 05, 06, 07]

tech-stack:
  added: []
  patterns:
    - "Donchian naive O(n*length): max/min su slice rolling, accettabile per length=20 e n<=200k"
    - "Fibonacci leg-detection riusa find_support_resistance: estremo più recente determina direction (up/down)"
    - "Pivot session-aware: chiave session = _session_id_ny17 (daily) o (anno_iso, week_iso) (weekly)"
    - "Bar usa H/L/C della sessione PRECEDENTEMENTE chiusa → no future leakage by construction"
    - "Camarilla multipliers verbatim 1.1/{12,6,4,2} pre-calcolati in tupla _CAMARILLA_MULT con literal nel codice (review-friendly)"

key-files:
  created:
    - tests/test_indicators_structure.py
  modified:
    - indicators/structure.py
    - indicators/__init__.py
    - tests/test_indicators_purity.py
  deleted: []

key-decisions:
  - "Fibonacci direction tramite scansione reverse di sub=bars[-lookback:]: il primo match dell'estremo (high o low) trovato dal fondo è il più recente. Equality stretta float-vs-bar perché leg_high/leg_low provengono dai bar stessi (no drift numerico). Edge case 'estremo non trovato' (può capitare se find_support_resistance ritorna fallback min/max su sub piccoli): direction='none' e levels={}."
  - "Pivots usa H/L/C della sessione PRECEDENTEMENTE chiusa per ogni barra: la sessione corrente accumula H/L/C come stato in costruzione, e SOLO al cambio di session-key i valori 'cur' diventano 'prev' della nuova sessione. Questa convenzione è strict: la prima bar della sessione N usa il prior della sessione N-1, NON include la chiusura della stessa N. Risultato: bar nella prima sessione osservata → tutti None, e leakage-free per costruzione."
  - "Anchor 'weekly' usa la chiave (anno_iso, week_iso) calcolata sulla data NY-17 della bar (output di _session_id_ny17). Quindi una bar a Sunday 17:00 NY (= prima bar settimana FX standard) cade nella settimana ISO della data restituita da _session_id_ny17, che è il lunedì successivo per definizione del helper. Comportamento documentato e leakage-test verifica che pivots(prefix)[i]==pivots(full)[i] anche su anchor weekly."
  - "Camarilla literals: scelta di pre-calcolare i quattro multiplier in tupla _CAMARILLA_MULT = (1.1/12, 1.1/6, 1.1/4, 1.1/2) invece di calcolarli per-iter con _DENOM. Vantaggio: il literal `1.1/12` e `1.1/2` appare nel sorgente (acceptance criterion del plan + grep-friendly per audit) E perf marginalmente migliore. Verificato che 1.1/12 == 0.09166666666666667 e 1.1/2 == 0.55, quindi h1 = prev_c + (H-L)*0.09166... e h4 = prev_c + (H-L)*0.55."
  - "Donchian implementazione naive O(n*length) anziché monotonic deque O(n): per length=20 e n max 200k il costo totale è ~4M operazioni, sotto il budget Phase 1 (smoke <60s). La deque ottimizzata è dietro semplicità di lettura — Phase 5/7 può rivisitare se profiling lo richiede."
  - "Donchian solleva ValueError se highs/lows hanno lunghezza diversa (Italian message 'devono avere la stessa lunghezza' coerente con atr/bollinger/keltner/adx/macd)."
  - "Fibonacci ritorna FibonacciResult come SNAPSHOT (non serie) con `direction: str` 'up'/'down'/'none'. Diverso dagli altri Result che sono serie length-N: i livelli sono unici per la finestra di lookback. Convenzione coerente con D-06 (dict[str, float|None] per levels)."

patterns-established:
  - "Pattern session-aware indicator: chiave _session_id_ny17 + stato 'cur' (in costruzione) + 'prev' (chiusa, leggibile dalle bar correnti) → leakage-free by construction"
  - "Pattern hand-calc fixture per indicatori senza pandas-ta oracolo: input deterministico, formula esplicita nel test (1.1/12), assertion abs(actual-expected) < 1e-9"
  - "Pattern DST-boundary test: chiamare _session_id_ny17 direttamente con due timestamp 1 secondo apart at boundary, in winter (22:00 UTC) e summer (21:00 UTC)"
  - "Pattern leakage-gate per session-aware: idx parametrizzati >= primo boundary (qui 100, perché fixture H1 cambia sessione entro ~24 bar)"

requirements-completed: [INDIC-05, INDIC-08, INDIC-09]

duration: 7min
completed: 2026-05-08
---

# Phase 2 Plan 05: Wave 2 — Donchian + Fibonacci + Pivots Summary

**INDIC-05/08/09 implementati come funzioni pure: Donchian length=20, Fibonacci 0/0.382/0.5/0.618/1.0 sull'ultimo swing leg (riusa `find_support_resistance`), Pivots classico + Camarilla daily/weekly con anchor NY-17 DST-aware (winter 22:00 UTC, summer 21:00 UTC). Camarilla multipliers verbatim 1.1/{12,6,4,2} (verificati LiteFinance/Babypips/Defcofx). Hand-calc test per ogni formula chiave + leakage-free a 5 spot indices su EURUSD H1.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-08T~10:30:00Z (approssimato)
- **Completed:** 2026-05-08
- **Tasks:** 2
- **Files created:** 1 (`tests/test_indicators_structure.py`)
- **Files modified:** 3 (`indicators/structure.py`, `indicators/__init__.py`, `tests/test_indicators_purity.py`)
- **Files deleted:** 0
- **Suite intera:** 305 passed, 1 skipped (286 baseline plan 04 → 305: +9 hand-calc + 5 donchian leakage + 5 pivots leakage)

## Accomplishments

- **`donchian(highs, lows, length=20)`** in `indicators/structure.py`:
  - Validazione fail-fast: `ValueError("highs e lows devono avere la stessa lunghezza")`, `ValueError("length deve essere > 0, ...")`.
  - Naive O(n*length) loop: `upper[i] = max(highs[i-length+1:i+1])`, `lower[i] = min(lows[...])`, `middle[i] = (upper+lower)/2`.
  - Primi `length-1` indici None.

- **`fibonacci_retracements(bars, lookback=100, window=2)`**:
  - Riusa `find_support_resistance(bars, lookback, window)` per estrarre `leg_low` (support) e `leg_high` (resistance).
  - Determina direzione scansionando bars[-lookback:] dal fondo: il primo match equality (bar.high == leg_high vs bar.low == leg_low) identifica l'estremo più recente. `last_high_idx > last_low_idx` → `direction="up"` (retracement scende dall'high), altrimenti `direction="down"`.
  - Levels dict con chiavi `"0"`, `"0.382"`, `"0.5"`, `"0.618"`, `"1.0"`.
  - Edge case (no bars / nessun pivot / leg_high == leg_low / estremo non riconducibile a un bar specifico) → `FibonacciResult(direction="none", levels={}, leg_high=None, leg_low=None)`.

- **`pivots(bars, anchor="daily")`** (`anchor` ∈ `{"daily", "weekly"}`):
  - Sessione `daily`: chiave = output di `_session_id_ny17` (data NY del giorno di chiusura sessione).
  - Sessione `weekly`: chiave = `(anno_iso, week_iso)` derivata dalla stessa data NY-17 via `date.isocalendar()`.
  - Per ogni bar: aggiorna stato `cur_h/cur_l/cur_c` della sessione corrente (in costruzione). Al cambio di chiave, `cur_*` diventa `prev_*` della nuova sessione. Bar nella prima sessione osservata → tutti None.
  - Formule classiche: `P=(H+L+C)/3`, `R1=2P-L`, `S1=2P-H`, `R2=P+(H-L)`, `S2=P-(H-L)`, `R3=H+2(P-L)`, `S3=L-2(H-P)`.
  - Camarilla: `_CAMARILLA_MULT = (1.1/12, 1.1/6, 1.1/4, 1.1/2)` literal pre-calcolati. `h_k = prev_c + (H-L)*mult_k`, `l_k` specchiato.
  - Leakage-free by construction: ogni bar usa H/L/C della sessione PRECEDENTEMENTE chiusa, mai della corrente.

- **Hand-calc test (`tests/test_indicators_structure.py`, 9 test):**
  - Donchian: 5-bar simple, serie costante, warmup None su length=20, ValueError su length mismatch.
  - Pivot Camarilla esatto: prev_h/l/c=110/100/105 → P=105.0, h1≈105.91666, h4=110.5, l4=99.5 (sulla prima bar della nuova sessione costruita NY-17 winter).
  - Pivot first-session all-None (10 bar in unica sessione → tutti None).
  - Pivot NY-17 DST boundary: due timestamp 1 secondo apart attorno alle 21:59:59 / 22:00:00 UTC del 2024-01-15 (winter) e 20:59:59 / 21:00:00 UTC del 2024-07-15 (summer) — assert che cambino entrambi day-key.
  - Fibonacci up-leg: low=1.0 idx5, high=2.0 idx25 → `direction="up"`, 0.382=1.618, 0.5=1.5, 0.618=1.382.
  - Fibonacci no-swing (H==L costante) → `direction="none"`.

- **Leakage gate (`tests/test_indicators_purity.py`):**
  - `test_no_future_leakage_donchian` parametrizzato su `[50, 100, 250, 400, 499]` → 5 PASS (upper, lower, middle).
  - `test_no_future_leakage_pivots` parametrizzato su `[100, 200, 300, 400, 499]` → 5 PASS (P, R1, S3, camarilla.h1, camarilla.l4). Indici partono da 100 per garantire che la fixture H1 abbia già attraversato almeno un boundary di sessione (avviene entro le prime ~24 bar — la fixture inizia il 2026-04-06 e la prima nuova sessione cade il 2026-04-07 verso bar 18-22).

- **Existing helpers preservati:** `find_support_resistance` e `check_breakout_quality` invariati (verificato regression suite intera 305/305).

- **Purity runtime:** `pandas_ta` NON importato dal modulo `indicators/structure.py` (verificato `grep -c "import pandas_ta" indicators/structure.py` → 0 e `test_no_pandas_ta_at_runtime` Wave 0 ancora verde).

- **Spot-check fixture EURUSD H1 (500 bar):**
  - `pivots(bars, anchor="daily").p[-1]` ≈ 1.1708 (484 valori non-None su 500, gap = 16 bar di prima sessione).
  - `pivots(bars, anchor="weekly").p[-1]` ≈ 1.1729 (387 non-None — la prima settimana intera viene "consumata" come prior).
  - `donchian(highs, lows, 20).upper[-1]` ≈ 1.17383, `lower[-1]` ≈ 1.16811.
  - `fibonacci_retracements(bars, 100, 2)` → `direction="up"`, leg [1.16552, 1.17851].

## Task Commits

1. **Task 1: Implementazione Donchian + Fibonacci + Pivots** — `4bb0150` (feat)
2. **Task 2: Hand-calc tests + leakage gate** — `b0f4c88` (test)

## Files Created/Modified

### Created
- `tests/test_indicators_structure.py` (~210 righe): 9 test hand-calc.

### Modified — runtime
- `indicators/structure.py`: da 71 righe (Wave 0) a ~330 righe. Aggiunte 3 dataclass (`DonchianResult`, `FibonacciResult`, `PivotResult`), 3 funzioni pubbliche (`donchian`, `fibonacci_retracements`, `pivots`), 2 helper privati (`_iso_week_key`, `_empty_pivot_series`), tupla `_CAMARILLA_MULT`. Italian docstrings throughout. `find_support_resistance` + `check_breakout_quality` preservati invariati (grep verificato: 1 occorrenza ciascuno, signature identica).
- `indicators/__init__.py`: aggiunto `donchian, fibonacci_retracements, pivots, DonchianResult, FibonacciResult, PivotResult` agli import e a `__all__`.

### Modified — test
- `tests/test_indicators_purity.py`: aggiunti `test_no_future_leakage_donchian` (5 idx) e `test_no_future_leakage_pivots` (5 idx). Pattern coerente con i 6 leakage-test esistenti (atr, sma/ema/rsi, bollinger, keltner, adx, macd, stochastic, hurst).

## Decisions Made

- **Camarilla literal nel codice:** scelta di pre-calcolare in tupla `_CAMARILLA_MULT = (1.1/12, 1.1/6, 1.1/4, 1.1/2)`. Vantaggi: (a) i literal `1.1/12`, `1.1/2` appaiono nel sorgente — review-friendly, audit-friendly, grep-friendly per il plan acceptance criterion `grep -c "1.1 / 12\|1.1/12"`; (b) micro-perf: i quattro float pre-calcolati riusati in ogni iter. Alternativa scartata: `_DENOM = (12,6,4,2)` con `1.1/denom` per-iter — funzionalmente equivalente ma meno auditabile.
- **Fibonacci come snapshot, non serie:** scelta di ritornare `FibonacciResult(levels: dict, leg_high, leg_low, direction: str)` vs alternative `dict[str, list[float|None]]` length-N. Motivazione: i livelli Fibonacci hanno significato solo rispetto a uno SPECIFICO swing leg — calcolarli per ogni indice produce una serie pesante e fuorviante (i livelli che valgono "ora" sono solo gli ultimi). Se in futuro Phase 4 vuole tracciare l'evoluzione storica del leg può chiamare `fibonacci_retracements` su rolling slices, ma per il consumer canonico (strategia, classifier ML) lo snapshot dell'ultimo è sufficiente.
- **Pivots `anchor` parametro stringa con set chiuso:** validazione `if anchor not in ("daily", "weekly"): raise ValueError(...)` invece di Enum. Motivazione: API più liscia per chiamanti dinamici (config YAML, MCP tool args). Coerente con `bollinger_bands(squeeze_method=...)` Wave 1.
- **Weekly key via ISO calendar:** `date.isocalendar()` standard ISO 8601 (lunedì come primo giorno). Le sessioni FX iniziano domenica 17:00 NY ma la chiave ISO calcolata sulla data restituita da `_session_id_ny17` (che già anticipa di 1 giorno post-17:00) cade nel lunedì ISO della settimana successiva — comportamento intenzionale: una sessione FX "lunedì" (Sunday-17→Monday-17 NY) ha session_id_ny17 = Lunedì → ISO week = settimana che inizia quel lunedì. Coerente con la pratica industriale.
- **Donchian length validation:** `length<=0` solleva ValueError. `n<length` ritorna serie tutta None (non error) — coerente con `sma`, `ema` Wave 0.
- **Pivot anchor "session" non implementato:** plan front-matter menziona "daily/session/weekly", ma D-11 chiarisce che "session = same as daily" (entrambe usano NY-17 boundary). Implementati solo `"daily"` e `"weekly"` per evitare alias non documentato. Se un consumer richiederà esplicitamente `"session"`, basterà aggiungere l'alias in 1 riga.

## Deviations from Plan

### Auto-fixed Issues

Nessuna deviazione richiesta. Il plan è stato eseguito come scritto, con due piccole estensioni difensive non in scope contestate dall'autore:

**1. [Rule 2 - Critical] ValueError esplicito su `length<=0` in `donchian`**
- **Found during:** Task 1 (implementazione)
- **Issue:** Il plan specificava solo "Validate equal lengths". Senza guardia su length<=0, una chiamata `donchian([1,2,3], [0,1,2], length=0)` ritornava lista tutta None silenziosamente — comportamento ambiguo per consumer downstream.
- **Fix:** Aggiunto `if length <= 0: raise ValueError(f"length deve essere > 0, ricevuto {length}")` coerente con il pattern atr/bollinger/keltner Wave 1.
- **Files modified:** `indicators/structure.py`
- **Commit:** `4bb0150`

**2. [Rule 2 - Critical] Validation `anchor` in `pivots`**
- **Found during:** Task 1
- **Issue:** Il plan specificava `anchor ∈ {"daily", "weekly"}` ma senza validation: passare `anchor="hourly"` produrrebbe risultati silenziosamente sbagliati (chiave ISO settimanale comunque calcolata).
- **Fix:** Aggiunto `if anchor not in ("daily", "weekly"): raise ValueError(...)` italiano.
- **Files modified:** `indicators/structure.py`
- **Commit:** `4bb0150`

---

**Total deviations:** 2 auto-fixed (Rule 2 — guardie di input, non logiche). Nessuna deviazione di logica nell'implementazione runtime: dataclasses, formule, anchor handling, leakage-free, Camarilla multipliers sono identici al plan-as-written.

**Impact on plan:** Nessuno scope creep, nessuna modifica all'API pubblica, nessuna nuova dipendenza. Le due guardie sono coerenti con il pattern fail-fast italiano già stabilito in Wave 0/1.

## Issues Encountered

- **Camarilla literal grep precision:** la versione iniziale aveva `_CAMARILLA_DENOM = (12.0, 6.0, 4.0, 2.0)` con calcolo `rng * 1.1 / denom` per-iter. `grep -c "1.1 / 12\|1.1/12"` ritornava 0 (la `1.1` non era inline accanto al `12`). Refactored a `_CAMARILLA_MULT = (1.1/12, ..., 1.1/2)` per soddisfare l'acceptance criterion E migliorare auditabilità. Bug-fix interno fatto entro Task 1 (no commit separato), funzionalità identica (verificato hand-calc 105.91666 e 110.5).

## User Setup Required

None — nessuna nuova dipendenza, nessuna config esterna, nessun secret. Tutto il codice usa solo stdlib (`dataclasses`, `datetime`, `zoneinfo`) + helper interni (`_session_id_ny17`).

## Next Wave Readiness

- **Wave 2 plan 06 (VWAP intraday + anchored — INDIC-07):** sblocca. Riuserà `_session_id_ny17` per il reset intraday (stesso pattern usato qui in `pivots`). Pattern di riferimento: il loop bar-by-bar con stato `cur_*` resettato al cambio session-key è la blueprint per VWAP cumulative.
- **Wave 2 plan 07 (NR4/NR7 + Closing Score — INDIC-10/11):** sblocca, indipendente da questo plan.
- **Wave 2 plan 08 (MTF align — INDIC-13):** sblocca, indipendente.
- **Wave 3 plan 09 (regime classifier + compute_all_extended — INDIC-14):** può ora consumare:
  - `donchian(highs, lows, 20).upper[-1] / lower[-1]` come feature di breakout-distance.
  - `pivots(bars, "daily").camarilla["h3"][-1]` come livello chiave intraday (h3/l3 sono il "pivot point Camarilla canonico" per setup A breakout).
  - `fibonacci_retracements(bars).levels["0.618"]` come zona di entry in setup B/D pullback.
- **Phase 4 (Strategy Refactor):** Setup A (breakout) può usare `donchian.upper` come livello breakout; setup B (S/R reversal) può usare `pivots.r3/s3` come confluence; setup D (trend pullback) può usare `fibonacci_retracements.levels["0.5"]` o `"0.618"` come zona pullback.
- **Phase 5 (Baseline Backtest):** non blocca — il preflight in 05-08 verificherà che le 9 plan di Phase 2 siano tutte completate (4 → 5 dopo questo plan).
- **Phase 7 (ML Classifier):** features candidate da questo plan:
  - `dist_to_donchian_upper = (donchian_upper - close) / atr` (proxy distanza-da-breakout-level).
  - `position_in_fib = (close - leg_low) / (leg_high - leg_low)` per leg corrente.
  - `dist_to_pivot_p = (close - pivot_p) / atr` (distanza dal pivot daily).
  - `dist_to_camarilla_h3 = (close - camarilla_h3) / atr`.

## Self-Check

Verifica claims fatte sopra (working dir `C:\trading-agent`):

- `[ -f tests/test_indicators_structure.py ]` → FOUND
- `grep -c "@dataclass" indicators/structure.py` → 3 → FOUND
- `grep -c "^def donchian" indicators/structure.py` → 1 → FOUND
- `grep -c "^def fibonacci_retracements" indicators/structure.py` → 1 → FOUND
- `grep -c "^def pivots" indicators/structure.py` → 1 → FOUND
- `grep -c "^def find_support_resistance" indicators/structure.py` → 1 → FOUND (preservato)
- `grep -c "^def check_breakout_quality" indicators/structure.py` → 1 → FOUND (preservato)
- `grep -c "1.1 ?/ ?12|1.1 ?/ ?2" indicators/structure.py` → 2 → FOUND (Camarilla literal)
- `grep -c "import pandas_ta" indicators/structure.py` → 0 → FOUND (purity)
- `grep -c "1.1" tests/test_indicators_structure.py` → 5 → FOUND (Camarilla referenced in test)
- `grep -c "_session_id_ny17" tests/test_indicators_structure.py` → 6 → FOUND (DST boundary asserted)
- Commit `4bb0150` (Task 1 feat) → FOUND in `git log`
- Commit `b0f4c88` (Task 2 test) → FOUND in `git log`
- `pytest tests/test_indicators_structure.py` → 9 passed → VERIFIED
- `pytest tests/test_indicators_purity.py::test_no_future_leakage_donchian` → 5 passed → VERIFIED
- `pytest tests/test_indicators_purity.py::test_no_future_leakage_pivots` → 5 passed → VERIFIED
- Suite intera `pytest` → 305 passed, 1 skipped → VERIFIED (286 baseline plan 04 + 19 nuovi: 9 hand-calc + 5 donchian leakage + 5 pivots leakage)
- `from indicators import donchian, fibonacci_retracements, pivots, DonchianResult, FibonacciResult, PivotResult` → import success → VERIFIED
- Camarilla hand-calc: prev_h/l/c=110/100/105 → h1=105.91666 (1e-9), h4=110.5 (1e-9) → VERIFIED
- NY-17 DST winter (22:00 UTC) e summer (21:00 UTC) → VERIFIED via `_session_id_ny17` direct call
- Fib up-leg: low=1.0/high=2.0 → 0.382=1.618, 0.5=1.5, 0.618=1.382 → VERIFIED
- Spot-check EURUSD H1 fixture: pivots last P ≈ 1.1708, weekly P ≈ 1.1729, donchian upper ≈ 1.17383 → VERIFIED

## Self-Check: PASSED

---
*Phase: 02-indicators-library*
*Wave: 2*
*Completed: 2026-05-08*
