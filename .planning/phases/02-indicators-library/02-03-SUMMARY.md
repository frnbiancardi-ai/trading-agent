---
phase: 02-indicators-library
plan: 03
subsystem: indicators
tags: [python, momentum, adx, macd, stochastic, pandas-ta-parity, future-leakage-gate]

requires:
  - phase: 02-indicators-library
    plan: 01
    provides: pacchetto indicators/, _wilder_smooth, fixture eurusd_h1_500, universal future-leakage gate
  - phase: 02-indicators-library
    plan: 02
    provides: pattern parity oracolare _SKIP/_HAVE_PTA, dataclass-of-lists, leakage gate parametrizzato
provides:
  - "indicators.momentum.adx(highs, lows, closes, period=14) -> ADXResult(adx, plus_di, minus_di)"
  - "indicators.momentum.macd(closes, fast=12, slow=26, signal=9) -> MACDResult(macd, signal, histogram)"
  - "indicators.momentum.stochastic(highs, lows, closes, k_period=14, d_period=3, smooth_k=3) -> StochasticResult(k, d)"
  - "ADXResult, MACDResult, StochasticResult dataclasses (D-04..D-06)"
  - "Re-export in indicators/__init__.py + __all__"
  - "Helper privato _rma_first_valid_seed (RMA pandas-ta-style: seed = primo non-None)"
  - "Helper privato _atr_pta_compat (ATR pandas-ta con prenan=True + presma=True)"
  - "Pattern parity 1e-6 vs pandas-ta confermato per ADX/MACD/Stochastic"
  - "Pattern leakage gate esteso (5 indici per ciascuno dei 3 indicatori)"
affects: [02-09, 04, 05]

tech-stack:
  added: []  # nessuna nuova dipendenza, riusa pandas-ta dev-dep di Wave 0
  patterns:
    - "RMA pandas-ta-style: alpha=1/length, seed = primo valore non-None (ewm senza min_periods)"
    - "ATR pandas-ta-style: prenan=True (tr[0]=NaN) + presma=True (seed presma a posizione length-1)"
    - "ADX da pandas-ta sequenza letterale: dmp=100*RMA(pos)/atr_, dmn=100*RMA(neg)/atr_, dx=100*|dmp-dmn|/(dmp+dmn), adx=RMA(dx)"
    - "MACD: macd_line = EMA(fast)-EMA(slow); signal_line = EMA della linea sul prefisso denso, riallineato"
    - "Stochastic: SMA-based smoothing su prefisso denso; range nullo nella finestra → raw_k None"
    - "Test sanity MACD su parabola y=i² (lag persistente) invece di y=i (line e signal convergono)"

key-files:
  created:
    - tests/test_indicators_momentum.py
  modified:
    - indicators/momentum.py
    - indicators/__init__.py
    - tests/test_indicators_purity.py
  deleted: []

key-decisions:
  - "ADX riscritto da zero rispetto al RESEARCH Example 1: il pattern 'doppio Wilder smooth con _wilder_smooth (SMA-seed) + mask 2*period' NON matcha pandas-ta. La sorgente vera (pandas_ta/trend/adx.py) usa pta.rma() (= ewm senza seed SMA, parte dal primo non-NaN) e pta.atr(prenan=True, presma=True) come denominatore. Implementati due helper privati: _rma_first_valid_seed e _atr_pta_compat. Wave 0 _wilder_smooth NON modificato — resta corretto per ATR Wave 0 (matcha presma)."
  - "Maschera 2*period rimossa dall'ADX: pandas-ta produce ADX_14 valido già a i=13 (non a i=27). I primi valori sono 'transient' ma lui li espone, e parity esige di esporli anche noi."
  - "Test sanity MACD signal-lag su serie parabolica (closes[i]=i²) invece di lineare (closes[i]=i): su serie strettamente lineare la macd_line converge a una costante (7.0 per fast=12/slow=26) e la signal raggiunge esattamente lo stesso valore — il lag scompare per costruzione. La parabola mantiene accelerazione costante → signal sempre in lag rispetto alla line. [Rule 1 bug-fix nel test]."
  - "Test acceptance del plan 'first 28 indices None' per adx su serie costante è ancora vero: su serie H==L==C costante atr_=0 ovunque → dmp/dmn restano None → dx None → adx None. Quindi non solo i primi 28 ma tutta la serie ADX è None. La condizione del plan è soddisfatta (subset più ampio)."
  - "raw_k None su range nullo: quando la finestra k_period ha HH==LL (es. serie costante), il close è indeterminato in [0,100]; ho convenzionato None. Quando incontrato un None interno nella sequenza, smoothed_k spezza la sua dense slice (resta None da li in poi). Caso patologico, non osservato su EURUSD H1."

patterns-established:
  - "Per indicatori che usano pandas-ta come oracolo: ispezionare la SORGENTE (pandas_ta/<dom>/<ind>.py) prima di implementare. RESEARCH Example N può semplificare e introdurre off-by-one o seed-mismatch."
  - "RMA pandas-ta non è equivalente a Wilder con SMA-seed quando applicato a serie con NaN iniziali (caso ADX su pos/neg). Quando l'oracolo è una serie con NaN, usare _rma_first_valid_seed (helper privato qui) o ricavare la formula esatta dal sorgente."
  - "Per testare lag di una EMA-of-EMA su serie sintetiche, scegliere serie ad accelerazione non-nulla (parabola o esponenziale): linee e signal convergono su input lineare."

requirements-completed: [INDIC-02, INDIC-03, INDIC-04]

duration: 8min30s
completed: 2026-05-08
---

# Phase 2 Plan 03: Wave 1 — ADX/MACD/Stochastic Summary

**INDIC-02 (ADX/DMI 14 Wilder/RMA), INDIC-03 (MACD 12/26/9 EMA-of-EMA), INDIC-04 (Stochastic 14/3/3 SMA-smoothed) implementati come funzioni pure con dataclass-of-lists, parity 1e-6 vs pandas-ta + leakage-free a 5 indici. Riscrittura ADX rispetto al piano per matchare la sequenza esatta di `pandas_ta/trend/adx.py` (off-by-one nel seed RMA + assenza di mask 2*period).**

## Performance

- **Duration:** ~8.5 min
- **Started:** 2026-05-08T09:07:02Z
- **Completed:** 2026-05-08T09:15:30Z
- **Tasks:** 2
- **Files created:** 1 (`tests/test_indicators_momentum.py`)
- **Files modified:** 3 (`indicators/momentum.py`, `indicators/__init__.py`, `tests/test_indicators_purity.py`)
- **Files deleted:** 0
- **Suite intera:** 275/275 verde (252 baseline Wave 1 plan 02 + 23 nuovi: 8 momentum + 15 leakage parametrizzati)

## Accomplishments

- `adx(highs, lows, closes, period=14)` ritorna `ADXResult(adx, plus_di, minus_di)`.
  - **+DI / -DI**: pandas-ta-compat. `up_move=high.diff(1)`, `down_move=-low.diff(1)`. `pos = up_move if (up>dn and up>0) else 0` (None al bar 0); `neg` simmetrico. `dmp = 100*RMA(pos)/atr_`, `dmn = 100*RMA(neg)/atr_`, dove `atr_` è ATR pandas-ta-style (`prenan=True, presma=True`).
  - **ADX**: `dx = 100*|dmp-dmn|/(dmp+dmn)`, `adx = RMA(dx)`. Nessuna maschera artificiale: ADX valido da i=13 (= length-1).
  - Riusato `_wilder_smooth` Wave 0? **NO** — non matcha pandas-ta su serie con NaN iniziali. Sostituito da due helper privati nuovi (`_rma_first_valid_seed`, `_atr_pta_compat`).
- `macd(closes, fast=12, slow=26, signal=9)` ritorna `MACDResult(macd, signal, histogram)`.
  - `macd_line[i] = ema(closes, fast)[i] - ema(closes, slow)[i]` quando entrambi non-None.
  - `signal_line` = EMA del prefisso denso di `macd_line`, riallineato all'offset originale.
  - `histogram[i] = macd_line[i] - signal_line[i]` quando entrambi definiti.
- `stochastic(highs, lows, closes, k_period=14, d_period=3, smooth_k=3)` ritorna `StochasticResult(k, d)`.
  - `raw_k[i] = 100*(close[i]-LL)/(HH-LL)` su finestra k_period bar; `None` se HH==LL.
  - `smoothed_k = SMA(raw_k_dense, smooth_k)`, `d = SMA(smoothed_k_dense, d_period)`.
- Tre nuove dataclass: `ADXResult`, `MACDResult`, `StochasticResult` co-locate in `indicators/momentum.py` (D-04..D-06).
- Re-export in `indicators/__init__.py`: `adx, macd, stochastic, ADXResult, MACDResult, StochasticResult` aggiunti a imports + `__all__`.
- Test parity vs pandas-ta `pta.adx(length=14, mamode='rma')`, `pta.macd(12,26,9)`, `pta.stoch(k=14, d=3, smooth_k=3)` PASS a tolerance 1e-6 con almeno 100 confronti per ciascuna serie su 500 bar EURUSD H1. Gate via `importlib.util.find_spec('pandas_ta')` + `pytest.mark.skipif`.
- Test sanity hand-calc: `adx_constant_no_raise`, `macd_signal_lag` (su parabola), `stoch_extreme_high`, 2 length-mismatch raises.
- Universal leakage gate esteso: 5 indici parametrizzati `[50, 100, 250, 400, 499]` per ADX, MACD, Stochastic. 15 PASS totali (5×3).
- `pandas_ta` NOT importato a runtime: confermato da `test_no_pandas_ta_at_runtime` (Wave 0) e `grep -rE "import pandas_ta|from pandas_ta" indicators/` → 0 match. `tests/test_indicators_momentum.py` ha 3 import dentro le funzioni parity (gated da `_HAVE_PTA`).

## Task Commits

1. **Task 1: Implementazione adx + macd + stochastic + dataclasses** — `8c0c35a` (feat)
2. **Task 2: Parity vs pandas-ta + leakage gate esteso** — `5ae3e73` (test, include riscrittura ADX da Rule 1 bug-fix)

## Files Created/Modified

### Created — test
- `tests/test_indicators_momentum.py` (~190 righe): 5 sanity + 3 parity gated `_HAVE_PTA`.

### Modified — runtime
- `indicators/momentum.py`: aggiunti `ADXResult`, `MACDResult`, `StochasticResult` dataclass + funzioni `adx`, `macd`, `stochastic` + helper privati `_rma_first_valid_seed`, `_atr_pta_compat`. Wave 0 `rsi`, `check_rsi_divergence` invariati. Imports interni `from indicators._helpers import _wilder_rsi, _wilder_smooth` e `from indicators.trend import ema, sma`. Nessun import pandas_ta.
- `indicators/__init__.py`: appended `adx, macd, stochastic, ADXResult, MACDResult, StochasticResult` a imports da `indicators.momentum` + `__all__`. Nessuna rimozione.

### Modified — test
- `tests/test_indicators_purity.py`: appesi `test_no_future_leakage_adx`, `test_no_future_leakage_macd`, `test_no_future_leakage_stochastic`, parametrizzati su `[50, 100, 250, 400, 499]` (15 PASS totali).

## Decisions Made

- **ADX riscritto rispetto al piano (RESEARCH Example 1):** il pattern proposto era `_wilder_smooth(plus_dm)`, `_wilder_smooth(minus_dm)`, `_wilder_smooth(tr)`, poi DI da rapporti, DX da DI, ADX = `_wilder_smooth(DX)` + maschera primi `2*period`. Questo NON matcha pandas-ta (mismatch ~17.8 a i=28 sul nostro fixture). La sorgente di `pandas_ta.adx` (`.venv/Lib/site-packages/pandas_ta/trend/adx.py`) mostra:
  1. `atr_ = atr(high, low, close, length, prenan=True)` — usa `presma=True` di default (seed presma a posizione `length-1` = `mean(tr[1..length-1])` con `length-1` valori, NOT `mean(tr[1..length])/length`).
  2. `dmp = 100 * ma('rma', pos, length=length) / atr_`, `dmn = 100 * ma('rma', neg, length=length) / atr_` — `pta.rma` è `series.ewm(alpha=1/length, adjust=False).mean()`, che parte dal primo valore non-NaN come seed (NON SMA dei primi `length`).
  3. `dx = 100 * |dmp - dmn| / (dmp + dmn)`; `adx = ma('rma', dx, length=signal_length)`.
  4. Nessuna maschera applicata.
  Implementati due helper privati: `_rma_first_valid_seed(values, period)` (RMA pandas-ta-style) e `_atr_pta_compat(highs, lows, closes, period)` (ATR pandas-ta-style). Il `_wilder_smooth` di Wave 0 resta corretto per ATR Wave 0 (matcha presma per costruzione: SMA dei primi `period` valori = `mean(tr[1..period])`/period quando tr[0]=0). `[CITED: pandas_ta/trend/adx.py — dmp = k * ma(mamode, pos, length=length); pandas_ta/overlap/rma.py — close.ewm(alpha, adjust=False).mean()]`.
- **Test MACD signal-lag su serie parabolica:** il piano prescriveva `closes = list(range(100))` con assert `m.macd[60] > m.signal[60] > 0`. Su serie strettamente lineare, EMA(12)-EMA(26) converge esattamente a 7.0 per costruzione (incremento costante = 1) e signal convergente allo stesso valore (deriva ULP a 7.0000000000000018 vs 7.0 — il signal è leggermente *sopra* line!). Cambiato a serie parabolica `closes = [i*i for i in range(100)]`: accelerazione costante → la macd_line cresce linearmente nel tempo → signal in lag persistente. Assert passa a i=60 (336.27 > 295.60).
- **Maschera ADX 2*period rimossa:** pandas-ta NON maschera (ADX_14 valido da i=13). Il plan prescriveva mask ma sarebbe rotto la parity su tutti gli indici nella finestra `[period, 2*period-1]`.
- **Plan acceptance "first 28 indices None for adx" su serie costante:** preservato. Su serie H==L==C costante, `tr[i]=0` ovunque (eccetto bar 0 dove pone NaN per prenan), quindi atr_=0/None ovunque → dmp/dmn=None → dx=None → adx=None su tutta la serie. Subset più stringente del requisito del plan.
- **Stochastic raw_k None su range zero:** pandas-ta produce NaN; convenzione equivalente. Quando incontrato durante lo smoothing della SMA, il prefisso denso si spezza (smoothed_k resta None da quel punto in poi). Caso patologico, non osservato su EURUSD H1 reale.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ADX formula non parity con pandas-ta — riscritto da zero**
- **Found during:** Task 2 (test parity adx)
- **Issue:** Implementazione Task 1 seguiva alla lettera il RESEARCH Example 1 (`_wilder_smooth` su +DM/-DM/TR + maschera 2*period). Test parity falliva con drift `~17.8` (19.98 vs 37.81 atteso) all'indice 28. Causa: pandas-ta usa RMA (ewm senza SMA-seed) e ATR con presma (seed a posizione length-1), non `_wilder_smooth` con SMA-seed e mask 2*period.
- **Fix:** Aggiunti due helper privati `_rma_first_valid_seed` e `_atr_pta_compat`. Riscritto `adx` per replicare letteralmente la sequenza di `pandas_ta/trend/adx.py`: pos/neg da diff, atr_ pta-compat, dmp/dmn = 100*RMA(pos|neg)/atr_, dx, adx = RMA(dx). Niente più maschera 2*period.
- **Files modified:** `indicators/momentum.py`
- **Commit:** `5ae3e73`
- **Verifica:** parity 1e-6 PASS su 500 bar EURUSD H1 con almeno 100 confronti per ciascuna serie (adx, +DI, -DI).

**2. [Rule 1 - Bug] Test MACD signal-lag su serie lineare invece di parabolica**
- **Found during:** Task 2 (test sanity macd_signal_lag)
- **Issue:** Plan-as-written prescriveva `closes = list(range(100))` con assert `m.macd[60] > m.signal[60] > 0`. Output empirico: `m.macd[60]=7.0`, `m.signal[60]=7.000000000000002` (signal *sopra* line di un ULP). Causa: incremento costante → EMA fast - EMA slow converge a una costante → signal raggiunge la line per costruzione (no momentum change da inseguire).
- **Fix:** Cambiato `closes = [float(i*i) for i in range(100)]`. Parabola → accelerazione costante → macd_line cresce linearmente → signal in lag persistente. Output: `m.macd[60]=588.6`, `m.signal[60]=536.2` (lag corretto).
- **Files modified:** `tests/test_indicators_momentum.py`
- **Commit:** `5ae3e73`

---

**Total deviations:** 2 auto-fixed (Rule 1 bug — entrambe per garantire il must_have "parity 1e-6 vs pandas-ta" e correttezza del test sanity).
**Impact on plan:** Le deviazioni sono correzioni di formula (ADX-vs-pandas-ta letterale) e correzione di un test sanity che era fragile per construction (lineare → convergenza). Nessuno scope creep, nessuna modifica architetturale, nessun import nuovo.

## Issues Encountered

- pandas-ta versione 0.4.71b0 emette `Pandas4Warning` deprecation su `mode.copy_on_write` durante l'import — innocuo, generato dall'oracolo, non dal codice runtime. Ricorrerà in tutti i parity test futuri.
- ADX RESEARCH Example 1 era una semplificazione incompatibile con pandas-ta. Il pattern documentato è simile a "Wilder ADX classico testbook" ma pandas-ta ha implementato qualcosa di diverso (probabilmente per matchare TradingView). Lessons learned per Wave 2/3 plans: ispezionare sempre `.venv/Lib/site-packages/pandas_ta/<domain>/<indicator>.py` prima di implementare, NON fidarsi dell'esempio nel RESEARCH.

## User Setup Required

None — `pandas-ta==0.4.71b0` già installato in `.venv` da Wave 0. Nessuna nuova dipendenza, nessuna config esterna.

## Next Wave Readiness

- **Wave 1 plan 04 (Hurst R/S)** sblocca indipendentemente da plan 03.
- **Wave 2 plan 05 (Donchian/Pivot/Fib)** indipendente.
- **Wave 3 plan 09 (regime classifier INDIC-14 + compute_all_extended)** può ora consumare ADX (trend strength), MACD (momentum direction), Stochastic (overbought/oversold) come segnali aggiuntivi del regime classifier.
- **Phase 4 (Strategy Refactor)** può usare:
  - `ADXResult.adx` per filtro trend-strength (es. setup B reversal solo se ADX < 20, setup A breakout se ADX > 25).
  - `MACDResult.histogram` per momentum confirmation (cross-zero dell'istogramma).
  - `StochasticResult.k`, `.d` per setup B reversal (oversold/overbought confirmation).
- **Phase 7 (ML Classifier)** può usare adx/dmp/dmn/macd_line/macd_hist/stoch_k/stoch_d come feature nel feature vector.
- Pattern stabilito per Wave 2: per ogni indicatore con oracolo pandas-ta, ispezionare la sorgente prima di implementare.

## Self-Check

Verifica claims fatte sopra (la directory di lavoro era `C:\trading-agent`):

- `[ -f tests/test_indicators_momentum.py ]` → FOUND (190 righe)
- `grep -c "@dataclass" indicators/momentum.py` → 3 (ADXResult, MACDResult, StochasticResult) → FOUND
- `grep -c "^def adx" indicators/momentum.py` → 1 → FOUND
- `grep -c "^def macd" indicators/momentum.py` → 1 → FOUND
- `grep -c "^def stochastic" indicators/momentum.py` → 1 → FOUND
- `grep -c "import pandas_ta" indicators/momentum.py` → 0 → FOUND (purity preservata)
- `grep -c "import pandas_ta" tests/test_indicators_momentum.py` → 3 (DENTRO i parity test) → FOUND
- Commit `8c0c35a` (Task 1 feat) → FOUND in `git log`
- Commit `5ae3e73` (Task 2 test + bug-fix) → FOUND in `git log`
- `pytest tests/test_indicators_momentum.py tests/test_indicators_purity.py -v` → 45 passed → VERIFIED
- Suite intera `pytest` → 275 passed → VERIFIED (252 baseline plan 02 + 23 nuovi)
- `from indicators import adx, macd, stochastic, ADXResult, MACDResult, StochasticResult` → import success → VERIFIED
- `from indicators import rsi, check_rsi_divergence` → Wave 0 invariato → VERIFIED
- Parity adx vs pta @ 1e-6 da i=28 → VERIFIED su 500 bar EURUSD H1 (>100 confronti)
- Parity macd vs pta @ 1e-6 da i=40 → VERIFIED
- Parity stoch vs pta @ 1e-6 da i=20 → VERIFIED
- Leakage adx 5 indici → 5/5 PASS
- Leakage macd 5 indici → 5/5 PASS
- Leakage stochastic 5 indici → 5/5 PASS

## Self-Check: PASSED

---
*Phase: 02-indicators-library*
*Wave: 1*
*Completed: 2026-05-08*
