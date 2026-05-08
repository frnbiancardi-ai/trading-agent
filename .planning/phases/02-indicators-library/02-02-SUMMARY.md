---
phase: 02-indicators-library
plan: 02
subsystem: indicators
tags: [python, volatility, bollinger, keltner, pandas-ta-parity, future-leakage-gate]

requires:
  - phase: 02-indicators-library
    plan: 01
    provides: pacchetto indicators/, _wilder_smooth, fixture eurusd_h1_500, universal future-leakage gate
provides:
  - "indicators.volatility.bollinger_bands(closes, length, std, squeeze_lookback_bars, squeeze_pct, ddof, highs?, lows?, keltner_length, keltner_scalar) -> BollingerResult(upper, middle, lower, bbw, squeeze, squeeze_ttm)"
  - "indicators.volatility.keltner(highs, lows, closes, length, scalar) -> KeltnerResult(upper, middle, lower)"
  - "BollingerResult, KeltnerResult dataclasses (D-04..D-06)"
  - "Re-export in indicators/__init__.py + __all__"
  - "Pattern parity 1e-6 vs pandas-ta confermato per BB e Keltner"
  - "Pattern leakage gate esteso (5 indici per indicatore)"
affects: [02-03, 02-04, 02-09, 04, 05]

tech-stack:
  added: []  # nessuna nuova dipendenza, riusa pandas-ta dev-dep di Wave 0
  patterns:
    - "dataclass-of-lists per output multi-serie (BollingerResult: 6 serie; KeltnerResult: 3 serie)"
    - "Standard deviation ddof=1 di default per parity con pandas-ta bbands (pandas .std default)"
    - "Keltner = EMA(close) ± scalar·EMA(true_range), NON Wilder ATR — parity pandas-ta kc"
    - "Squeeze percentile: nearest-rank su finestra trailing 180 bar (default A4 25-pct)"
    - "Squeeze TTM Carter: BB-inside-Keltner come boolean secondario su BollingerResult"
    - "True range bar 0 → (high - low) per allineare a pandas-ta true_range"

key-files:
  created:
    - tests/test_indicators_volatility.py
  modified:
    - indicators/volatility.py
    - indicators/__init__.py
    - tests/test_indicators_purity.py
  deleted: []

key-decisions:
  - "ddof=1 di default (campionaria) per Bollinger: pandas-ta bbands usa pandas .std(ddof=1) quando talib non installato; deviazione dal piano (che proponeva ddof=0 popolazionale) per soddisfare il must_have parity 1e-6. Esposto come parametro per futuri use-case che vogliano popolazionale (ddof=0 talib-style)."
  - "Keltner usa EMA(true_range) invece di Wilder ATR: il piano proponeva 'middle ± scalar·ATR(length)' ma pandas-ta kc(mamode='ema') calcola band = EMA(TR, length). Per soddisfare must_have parity 1e-6 ho allineato all'oracolo. La definizione Chester Keltner originale usa SMA(typical_price), Linda Bradford Raschke usa ATR; la convenzione TradingView/pandas-ta è EMA(TR) ed è quella che il backtest userà come ground-truth. Il modulo `atr` di Wave 0 resta intatto e disponibile per altri consumer (ADX/Stoch in Wave 2)."
  - "True range alla bar 0 convenzionato (high - low): pandas-ta `true_range` produce NaN alla bar 0 in alcune release ma EMA seed = SMA dei primi 20 valori; per parity 1e-6 a partire da i=40 abbiamo verificato che (high - low) come bar-0 funziona. La discrepanza alla bar 0 viene assorbita dal seed EMA su 20 bar."
  - "Test keltner_constant_series: il piano prescriveva 30 bar con assertion all'indice 19, ma ATR(period=20) richiede 21 bar prima del primo valore valido (out[period]=out[20]). Esteso a 40 bar e indice 25 — Rule 1 bug-fix nel test, intent originale (ATR=0 → upper=lower=middle) preservato."

patterns-established:
  - "Per ogni nuovo rolling indicator: aggiungere @pytest.mark.parametrize('idx', [warmup+1, 100, 250, 400, 499]) in test_indicators_purity.py"
  - "Per parity oracolare: importare pandas_ta DENTRO il test (non a module level) e gate via importlib.util.find_spec + pytest.mark.skipif"
  - "Per indicatori multi-output usare dataclass-of-lists, esportare il tipo + i campi via barrel"
  - "Tolerance 1e-6 sufficiente per parity pandas-ta a partire da idx=2*length (saltare il transient di seed)"

requirements-completed: [INDIC-01, INDIC-06]

duration: 5min
completed: 2026-05-08
---

# Phase 2 Plan 02: Wave 1 — Bollinger Bands + Keltner Summary

**INDIC-01 (Bollinger Bands 20/2σ + BBW + squeeze percentile + squeeze TTM Carter) e INDIC-06 (Keltner EMA20 ± 2·EMA(TR)) implementati come funzioni pure con dataclass-of-lists, parity 1e-6 vs pandas-ta + leakage-free a 5 indici.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-08T08:57:45Z
- **Completed:** 2026-05-08T09:03:00Z
- **Tasks:** 2
- **Files created:** 1 (`tests/test_indicators_volatility.py`)
- **Files modified:** 3 (`indicators/volatility.py`, `indicators/__init__.py`, `tests/test_indicators_purity.py`)
- **Files deleted:** 0
- **Suite intera:** 252/252 verde (236 baseline Wave 0 + 16 nuovi: 6 volatility + 10 purity-leakage)

## Accomplishments

- `bollinger_bands(closes, length=20, std=2.0, squeeze_lookback_bars=180, squeeze_pct=25.0, ddof=1, highs=None, lows=None, keltner_length=20, keltner_scalar=2.0)` ritorna `BollingerResult(upper, middle, lower, bbw, squeeze, squeeze_ttm)`.
  - **Middle** = SMA(length); **upper/lower** = middle ± std·sd (sd campionaria ddof=1 di default).
  - **BBW** = (upper - lower) / middle (relativo, None se middle == 0).
  - **squeeze** (primario) = `bbw[i] < quantile_{squeeze_pct}` su finestra trailing di `squeeze_lookback_bars` (richiesti tutti valori validi).
  - **squeeze_ttm** (secondario, Carter) = `(bb.upper < kc.upper) and (bb.lower > kc.lower)` se highs/lows forniti, altrimenti `[None]*n`.
- `keltner(highs, lows, closes, length=20, scalar=2.0)` ritorna `KeltnerResult(upper, middle, lower)`.
  - **middle** = EMA(close, length); **band** = EMA(true_range, length); upper/lower = middle ± scalar·band.
  - True range alla bar 0 convenzionato come `high[0] - low[0]` (no chiusura precedente).
- `BollingerResult` e `KeltnerResult` dataclass co-locate in `indicators/volatility.py` (D-04..D-06).
- Re-export in `indicators/__init__.py`: `bollinger_bands`, `keltner`, `BollingerResult`, `KeltnerResult` aggiunti a imports + `__all__`.
- Test parity vs pandas-ta `bbands(length=20, std=2.0)` e `kc(length=20, scalar=2, mamode='ema')` PASS a tolerance 1e-6 a partire da `i=40` (skip transienti seed). Gate via `importlib.util.find_spec('pandas_ta')` + `pytest.mark.skipif`.
- Test sanity hand-calc: `bollinger_zero_variance` (serie costante → middle=upper=lower=1.0, bbw=0.0), `keltner_constant_series` (ATR=0 → upper=lower=middle=1.0), `bollinger_warmup_none`, `keltner_input_length_mismatch_raises`.
- Universal leakage gate esteso: 5 indici parametrizzati per `bollinger_bands` (upper/lower/bbw/squeeze) e 5 per `keltner` (upper/middle/lower). 10 nuovi PASS.
- `pandas_ta` NOT importato a runtime: confermato da `test_no_pandas_ta_at_runtime` (Wave 0) e `grep -rE "import pandas_ta|from pandas_ta" indicators/` → 0 match.

## Task Commits

1. **Task 1: Implementazione bollinger_bands + keltner + dataclasses** — `466fe97` (feat)
2. **Task 2: Parity pandas-ta + leakage gate esteso** — `e10e6d5` (test, include due Rule 1 bug-fix in volatility.py per parity)

## Files Created/Modified

### Created — test
- `tests/test_indicators_volatility.py` (109 righe): 4 sanity + 2 parity (gated `_HAVE_PTA`).

### Modified — runtime
- `indicators/volatility.py`: aggiunti `BollingerResult`, `KeltnerResult` dataclass + `bollinger_bands` e `keltner`. `atr` Wave 0 invariato. Imports interni `from indicators.trend import ema, sma`. Nessun import pandas_ta. **(+150 righe netto)**.
- `indicators/__init__.py`: appended `bollinger_bands, keltner, BollingerResult, KeltnerResult` a imports da `indicators.volatility` + `__all__`. Nessuna rimozione.

### Modified — test
- `tests/test_indicators_purity.py`: appesi `test_no_future_leakage_bollinger` e `test_no_future_leakage_keltner`, parametrizzati su `[50, 100, 250, 400, 499]` (10 PASS totali).

## Decisions Made

- **ddof=1 (campionaria) di default per Bollinger:** il piano prescriveva `var = max(cum_sq/length - mean*mean, 0.0)` (popolazionale, ddof=0). pandas-ta `bbands` invece usa `pandas.Series.std()` con default `ddof=1` quando talib non installato (verificato in `.venv` con `Imports['talib']==False`). Per soddisfare il must_have "parity 1e-6 vs pandas-ta" ho cambiato il default a ddof=1, esposto come parametro `ddof: int = 1`. Forma equivalente: `ssr = cum_sq - length·mean²`, `var = max(ssr/divisor, 0.0)` con `divisor = length - ddof`. Test parity PASS a tolerance 1e-6 dall'indice 40 in poi.
- **Keltner = EMA(close) ± scalar·EMA(true_range):** il piano prescriveva "middle ± scalar·ATR(length)" usando l'`atr` di Wave 0 (Wilder smoothing). Verifica empirica del sorgente `pandas_ta.kc` mostra che con `mamode='ema'` la banda è calcolata come `ma('ema', range_, length=length)` dove `range_ = true_range(...)` — NON Wilder ATR. Per parity 1e-6 ho rifattorizzato `keltner` per calcolare `band = EMA(tr, length)` direttamente. La funzione `atr` resta esportata e disponibile per ADX/Stoch (Wave 2). `[CITED: pandas_ta.kc source — band = ma(mamode, range_, length=length)]`.
- **True range bar 0 = high[0] - low[0]:** convenzione esplicita per evitare NaN-handling in EMA(TR). pandas-ta produce NaN alla bar 0 ma il seed EMA è SMA dei primi 20 valori, e i test parity partono da `i=40` (saltando il transient). Allineato.
- **Test keltner_constant_series indice 25 invece di 19:** ATR(period=20) richiede 21 bar (`out[period]=out[20]` è il primo valido per Wilder seed); con 30 bar e length=20, Keltner all'indice 19 è ancora None. Esteso a 40 bar / indice 25, intent preservato (Rule 1 bug-fix nel test).
- **Squeeze nearest-rank percentile (no interpolazione):** `cutoff = sorted_vals[max(0, int(N·p/100) - 1)]`. Più semplice, deterministica, e accettabile perché la finestra ha 180 valori (granularità 0.55%). Match con la convenzione "below the 25th percentile" letterale.
- **Squeeze warmup richiede tutti i valori validi nella finestra:** `if len(window_vals) < squeeze_lookback_bars: continue`. Equivale a partire dal primo bar in cui ci sono `length-1 + squeeze_lookback_bars - 1` BBW validi consecutivi. Test leakage usa `squeeze_lookback_bars=60` per assicurarsi che la finestra sia raggiungibile entro 500 bar.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Bollinger ddof: popolazionale → campionaria per parity pandas-ta**
- **Found during:** Task 2 (test parity bbands)
- **Issue:** Implementazione Task 1 seguiva alla lettera il piano (`var = cum_sq/length - mean²`, popolazionale). Test parity falliva con drift `~1e-4` su upper/lower (1.159874 vs 1.159977 atteso). Causa: pandas-ta `bbands` usa `pandas.Series.std()` con `ddof=1` di default (talib non installato in venv).
- **Fix:** Aggiunto parametro `ddof: int = 1`, formula generalizzata a `ssr = cum_sq - length·mean²; var = max(ssr/(length-ddof), 0.0)`. Default 1 (campionaria) per parity; esposto come param per consumer che vogliono popolazionale (ddof=0 talib-style).
- **Files modified:** `indicators/volatility.py`
- **Commit:** `e10e6d5`

**2. [Rule 1 - Bug] Keltner ATR di Wilder → EMA del true range per parity pandas-ta**
- **Found during:** Task 2 (test parity kc)
- **Issue:** Implementazione Task 1 usava `atr(highs, lows, closes, length)` (Wilder smoothing) come banda. Test parity falliva con drift `~1.7e-4` su upper. Causa: `pandas_ta.kc(mamode='ema')` calcola band = `ma('ema', true_range, length)` — NON Wilder ATR.
- **Fix:** Rifattorizzato `keltner` per calcolare `tr` esplicitamente, poi `band = ema(tr, length)`. La funzione `atr` Wave 0 resta esportata e disponibile (consumer Wave 2 ADX/Stoch).
- **Files modified:** `indicators/volatility.py`
- **Commit:** `e10e6d5`

**3. [Rule 1 - Bug] Test keltner_constant_series: 30 bar / idx 19 → 40 bar / idx 25**
- **Found during:** Task 2 (test sanity keltner)
- **Issue:** Plan-as-written prescriveva `h = [1.0]*30; ... assert r.upper[19] == 1.0`. ATR(period=20) richiede 21 bar (`out[period]=out[20]`); con 30 bar e length=20, Keltner all'indice 19 è ancora None.
- **Fix:** Esteso input a 40 bar e assertion all'indice 25. Intent originale preservato (ATR=0 su serie costante → upper=lower=middle=1.0). Docstring del test annota la ragione.
- **Files modified:** `tests/test_indicators_volatility.py`
- **Commit:** `e10e6d5`

---

**Total deviations:** 3 auto-fixed (Rule 1 bug — tutte per garantire il must_have "parity 1e-6 vs pandas-ta" e correttezza dei test sanity).
**Impact on plan:** Le deviazioni 1 e 2 sono correzioni di formula (ddof e ATR-vs-EMA-TR) per allineare all'oracolo pandas-ta che il piano stesso indica come ground-truth. La deviazione 3 è correzione di un off-by-one nella sample assertion del piano. Nessuno scope creep, nessuna modifica architetturale.

## Issues Encountered

- pandas-ta versione 0.4.71b0 emette `Pandas4Warning` deprecation su `mode.copy_on_write` durante l'import — innocuo, generato dall'oracolo, non dal codice runtime. Non bloccante. Ricomparirà in tutti i parity test futuri.
- Catastrophic cancellation potenziale in `var = ssr/divisor` per finestre con prezzi molto vicini: clamp `max(..., 0.0)` previene `sd=NaN` per derive numeriche. Non osservato in pratica su 500 bar EURUSD ma documentato come safeguard.

## User Setup Required

None — `pandas-ta==0.4.71b0` già installato in `.venv` da Wave 0. Nessuna nuova dipendenza, nessuna config esterna.

## Next Wave Readiness

- **Wave 1 plan 03 (ADX/MACD/Stoch)** sblocca: può lanciare `pta.adx`, `pta.macd`, `pta.stoch` come oracoli a tolerance 1e-6 con il pattern stabilito in `tests/test_indicators_volatility.py`. ADX userà `_wilder_smooth` da `_helpers.py`.
- **Wave 1 plan 04 (Hurst R/S)** sblocca indipendentemente.
- **Wave 2 plan 05 (Donchian/Pivot/Fib)** indipendente da Wave 1.
- **Wave 3 plan 09 (regime classifier INDIC-14 + compute_all_extended)** può consumare `bollinger_bands` per il segnale `squeeze` come uno dei cinque indicatori del regime.
- **Phase 4 (Strategy Refactor)** può usare `BollingerResult.squeeze` per setup C (compression) e `BollingerResult.upper/lower` per setup A (breakout) — esattamente i consumer indicati dal piano.

## Self-Check

Verifica claims fatte sopra (la directory di lavoro era `C:\trading-agent`):

- `[ -f tests/test_indicators_volatility.py ]` → FOUND
- `grep -c "@dataclass" indicators/volatility.py` → 2 (BollingerResult, KeltnerResult) → FOUND
- `grep -c "^def atr" indicators/volatility.py` → 1 (Wave 0 atr preservato) → FOUND
- `grep -c "import pandas_ta" indicators/` → 0 → FOUND (purity preservata)
- `grep -c "import pandas_ta" tests/test_indicators_volatility.py` → 2 (DENTRO i parity test) → FOUND
- Commit `466fe97` (Task 1 feat) → FOUND in `git log`
- Commit `e10e6d5` (Task 2 test + bug-fix) → FOUND in `git log`
- `pytest tests/test_indicators_volatility.py tests/test_indicators_purity.py -v` → 28 passed → VERIFIED
- Suite intera `pytest` → 252 passed → VERIFIED (236 baseline + 16 nuovi)
- `bollinger_bands([1.0]*30, length=20, std=2.0)` → middle[19]==1.0, upper[19]==1.0, lower[19]==1.0, bbw[19]==0.0 → VERIFIED
- `keltner([1.0]*40, [1.0]*40, [1.0]*40, length=20, scalar=2.0)` → middle[25]==upper[25]==lower[25]==1.0 → VERIFIED
- Parity bbands vs pta @ 1e-6 da i=40 → VERIFIED su 500 bar EURUSD H1
- Parity kc vs pta @ 1e-6 da i=40 → VERIFIED su 500 bar EURUSD H1
- Leakage bollinger 5 indici → 5/5 PASS
- Leakage keltner 5 indici → 5/5 PASS

## Self-Check: PASSED

---
*Phase: 02-indicators-library*
*Wave: 1*
*Completed: 2026-05-08*
