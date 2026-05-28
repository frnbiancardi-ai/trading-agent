---
phase: 02-indicators-library
plan: 06
subsystem: indicators
tags: [python, vwap, ny-17, dst, session-anchor, intraday, anchored, pure-functions, hand-calc-tests]

requires:
  - phase: 02-indicators-library
    plan: 01
    provides: pacchetto indicators/, _session_id_ny17, fixture eurusd_h1_500, universal future-leakage gate
provides:
  - "indicators.volume.vwap_intraday(bars) -> VWAPResult (reset NY-17 DST-aware)"
  - "indicators.volume.vwap_anchored(bars, anchor_ts) -> VWAPResult (semantica bar.ts >= anchor_ts)"
  - "VWAPResult dataclass length-N (vwap, cumulative_pv, cumulative_v) per D-04..D-06"
  - "_typical_price + _bar_volume helper privati in indicators/volume.py"
  - "Re-export in indicators/__init__.py + __all__"
affects: [02-09, 03, 04, 05, 06, 07]

tech-stack:
  added: []
  patterns:
    - "VWAP intraday cumulativo session-aware: reset al cambio di chiave _session_id_ny17 (loop O(n), pattern blueprint da plan 02-05 pivots)"
    - "VWAP anchored con flag binario `anchored`: skip silenzioso prima dell'ancora (campi None), cumulazione in-loop dopo"
    - "Volume preference tick_volume → volume → 0 (pattern verbatim da avg_volume Wave 0)"
    - "Hand-calc fixture per session reset: bar a 21:00 e 22:00 UTC del 2024-01-15 (winter), bar a 20:00 e 21:00 UTC del 2024-07-15 (summer)"
    - "ValueError fail-fast su anchor_ts naive (italiano, coerente con pattern atr/bollinger/keltner/donchian/pivots)"

key-files:
  created:
    - tests/test_indicators_volume.py
  modified:
    - indicators/volume.py
    - indicators/__init__.py
    - tests/test_indicators_purity.py
  deleted: []

key-decisions:
  - "Helper privati `_typical_price` e `_bar_volume` co-located in indicators/volume.py invece di promuovere a `indicators/_helpers.py`. Motivazione: sono usati solo da vwap_intraday/anchored; promuoverli al modulo helpers richiederebbe esporli a un'API più ampia senza beneficio. Coerente con il pattern (il modulo volume.py è autocontenuto)."
  - "Semantica anchor: barre con `bar.ts < anchor_ts` hanno `vwap=cumulative_pv=cumulative_v=None` (NON 0). Razionale Pitfall 3 RESEARCH: distinguere 'pre-anchor' (concetto: l'indicatore non si applica) da 'pre-volume' (concetto: c'è bar ma volume zero). Coerente col concetto di warmup degli altri indicatori (None = non calcolabile)."
  - "Validation `anchor_ts` tz-aware fail-fast: confrontiamo internamente con `datetime.fromtimestamp(..., tz=UTC)`. Un anchor naive solleverebbe TypeError silenzioso o produrrebbe risultati sbagliati per fuso orario. Italian message coerente con pattern Wave 1+."
  - "VWAP intraday gestisce zero-volume in-line: `vwap[i] = None if running_v == 0 else running_pv/running_v`. NON solleva exception (a differenza di bar list mismatch in altri indicatori) — bar legittime possono avere volume zero in mercato fermo, e None è il segnale corretto."
  - "Riuso `_session_id_ny17` da Wave 0: stesso pattern già verificato DST-aware in plan 02-05 (Pivots winter 22:00 UTC + summer 21:00 UTC). Hand-calc fixture replica i due boundary."

patterns-established:
  - "Pattern session-aware cumulativo: chiave `_session_id_ny17` + stato `running_pv/running_v` resettato al cambio di chiave → cumulativi della sessione corrente, leakage-free per costruzione"
  - "Pattern anchor-flag binario: `anchored=False` → skip silenzioso (campi None) → al primo `ts >= anchor_ts` setta True e procede. Più semplice di doppio loop (find anchor index, then accumulate)"
  - "Pattern leakage-gate VWAP intraday: 5 idx parametrizzati [50,100,250,400,499] verificano vwap+cumulative_pv+cumulative_v"

requirements-completed: [INDIC-07]

duration: 4min
completed: 2026-05-08
---

# Phase 2 Plan 06: Wave 2 — VWAP Intraday + Anchored Summary

**INDIC-07 implementato come 2 funzioni pure in `indicators/volume.py`: `vwap_intraday(bars)` con reset cumulativo al boundary NY-17 (DST-aware: winter 22:00 UTC, summer 21:00 UTC) tramite `_session_id_ny17` riusato da Wave 0; `vwap_anchored(bars, anchor_ts)` con semantica `bar.ts >= anchor_ts` (Pitfall 3 RESEARCH) e ValueError fail-fast su anchor_ts naive. `VWAPResult` dataclass length-N (vwap, cumulative_pv, cumulative_v) per D-04..D-06. `avg_volume` Wave 0 preservato. Hand-calc test per session reset DST winter+summer + anchor before/at/raise + zero-volume safety + leakage-free a 5 spot indices su EURUSD H1.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-08T09:36:52Z
- **Completed:** 2026-05-08
- **Tasks:** 2
- **Files created:** 1 (`tests/test_indicators_volume.py`)
- **Files modified:** 3 (`indicators/volume.py`, `indicators/__init__.py`, `tests/test_indicators_purity.py`)
- **Files deleted:** 0
- **Suite intera:** 317 passed, 1 skipped (305 baseline plan 05 → 317: +12 = 7 hand-calc + 5 vwap_intraday leakage)

## Accomplishments

- **`vwap_intraday(bars: list[dict]) -> VWAPResult`** in `indicators/volume.py`:
  - Loop O(n) bar-by-bar.
  - Per ogni bar calcola `sid = _session_id_ny17(ts_utc)`; se cambia rispetto al precedente, reset `running_pv = running_v = 0.0`.
  - Cumula `tp = (high+low+close)/3 * volume` e `volume`; salva in `cum_pv[i]`, `cum_v[i]`.
  - `vwap[i] = (running_pv / running_v) if running_v > 0 else None` — zero-volume safe.
  - Reset NY-17 verificato hand-calc DST winter (22:00 UTC) e summer (21:00 UTC).

- **`vwap_anchored(bars: list[dict], anchor_ts: datetime) -> VWAPResult`**:
  - Validation fail-fast: `if anchor_ts.tzinfo is None: raise ValueError("anchor_ts deve essere tz-aware (es. timezone.utc)")`.
  - Flag `anchored = False` finché `bar.ts < anchor_ts` (campi None silenziosi).
  - Al primo `bar.ts >= anchor_ts` setta `True` e cumula. Coerente con Pitfall 3 RESEARCH (semantica "first bar at-or-after anchor").
  - Hand-calc test: anchor 1µs DOPO bar[1].time → bar[2] è il primo cumulato; anchor == bar[1].time esatto → bar[1] è il primo.

- **`VWAPResult` dataclass** (D-04..D-06): tre campi `list[float | None]` length-N, co-located in `indicators/volume.py`, re-exported da `indicators/__init__.py`.

- **Helper privati** `_typical_price(bar)` e `_bar_volume(bar)` co-located in `indicators/volume.py`. `_bar_volume` replica il pattern di `avg_volume` (preferisce `tick_volume`, fallback `volume`, fallback 0 con `or 0` per robustezza None-input).

- **`avg_volume` preservato invariato** (verbatim Wave 0): `grep -c "^def avg_volume" indicators/volume.py` → 1, signature identica.

- **Hand-calc test (`tests/test_indicators_volume.py`, 7 test):**
  - `test_vwap_intraday_single_bar`: tp=(2+1+1.5)/3=1.5, vol=10 → vwap[0]=1.5, cum_pv=15.0, cum_v=10.0.
  - `test_vwap_intraday_session_reset_winter`: 3 bar (21h/22h/23h UTC del 2024-01-15) verifica reset esatto a 22:00 UTC. vwap[0]=1.5 (A solo), vwap[1]=3.0 (B solo nuova sessione), vwap[2]=110/30 (B+C).
  - `test_vwap_intraday_session_reset_summer`: 2 bar (20h/21h UTC del 2024-07-15) verifica reset summer a 21:00 UTC. vwap[0]=1.5, vwap[1]=3.0 (reset).
  - `test_vwap_intraday_zero_volume_yields_none`: bar con volume=0, tick_volume=0 → vwap[0]=None, cum_v[0]=0.0 (no div-by-zero, no exception).
  - `test_vwap_anchored_before_anchor_returns_none`: anchor 1µs dopo bar[1] → vwap[0]=vwap[1]=None, vwap[2]=5.0.
  - `test_vwap_anchored_at_exact_bar_ts_starts_cumulation`: anchor == bar[1].time esatto → vwap[1]=3.0 (single-bar), vwap[2]=110/30 (B+C).
  - `test_vwap_anchored_naive_datetime_raises`: ValueError con match "tz-aware" su `datetime(2024,1,1)` (no tzinfo).

- **Leakage gate (`tests/test_indicators_purity.py`):**
  - `test_no_future_leakage_vwap_intraday` parametrizzato su `[50, 100, 250, 400, 499]` → 5 PASS su vwap, cumulative_pv, cumulative_v. Reset session è funzione locale dei timestamp delle bar precedenti nella stessa sessione → leakage-free per costruzione, verificato.

- **Purity runtime:** `pandas_ta` NON importato dal modulo `indicators/volume.py` (`grep -c "pandas_ta" indicators/volume.py` → 0; `test_no_pandas_ta_at_runtime` Wave 0 ancora verde).

- **Spot-check fixture EURUSD H1 (500 bar):**
  - `vwap_intraday(bars)` ritorna 500/500 valori non-None (ogni sessione ha volume > 0 nella fixture). `vwap[-1] ≈ 1.16909` (close finale ≈ 1.1709, vwap leggermente più basso → bar finale leggermente sopra vwap di sessione).
  - `cumulative_v[-1] = 12480.0` (volume totale dell'ultima sessione H1, coerente con tick_volume EURUSD demo).
  - `vwap_anchored(bars, anchor=bar[100].time)`: vwap[99]=None, vwap[100]≈1.16844 (single-bar tp), vwap[499]≈1.17357 (cumulato 400 bar), cumulative_v[499]=5117435 (volume cumulato post-anchor).

## Task Commits

1. **Task 1: Implementazione vwap_intraday + vwap_anchored** — `ad5ed9a` (feat)
2. **Task 2: Hand-calc tests + leakage gate** — `78f85e5` (test)

## Files Created/Modified

### Created
- `tests/test_indicators_volume.py` (~140 righe): 7 test hand-calc INDIC-07.

### Modified — runtime
- `indicators/volume.py`: da 17 righe (Wave 0) a ~110 righe. Aggiunte 1 dataclass (`VWAPResult`), 2 funzioni pubbliche (`vwap_intraday`, `vwap_anchored`), 2 helper privati (`_typical_price`, `_bar_volume`). Italian docstrings throughout. `avg_volume` preservato verbatim.
- `indicators/__init__.py`: aggiunto `vwap_intraday, vwap_anchored, VWAPResult` agli import e a `__all__`.

### Modified — test
- `tests/test_indicators_purity.py`: aggiunto `test_no_future_leakage_vwap_intraday` (5 idx). Pattern coerente con i 9 leakage-test esistenti (atr, sma/ema/rsi, bollinger, keltner, adx, macd, stochastic, hurst, donchian, pivots).

## Decisions Made

- **Helper privati co-located in volume.py vs `_helpers.py`:** scelta di tenere `_typical_price` e `_bar_volume` in `indicators/volume.py` perché usati solo da vwap_intraday/anchored (e potenzialmente da estensioni future di volume.py come `mvwap`). Promuoverli a `_helpers.py` esporrebbe API a moduli che non hanno motivo di calcolare typical_price o di gestire la fallback chain volume. Motivazione coerente con `_camarilla_levels` co-located in `structure.py` (plan 02-05).

- **Semantica `vwap_anchored` pre-anchor = None vs 0:** distinzione concettuale tra "indicatore non applicabile" (None) e "indicatore = 0" (numero). Una bar prima dell'ancora non ha vwap definito (l'ancora delimita l'inizio), NON ha vwap zero. Coerente con il warmup degli altri indicatori della libreria (sma[0..period-2] = None). Il consumer downstream (es. strategia) può discriminare con `if vwap[i] is not None` invece di `if vwap[i] != 0`.

- **`vwap_intraday` zero-volume in-line vs raise:** scelta di ritornare `vwap[i] = None` invece di sollevare ValueError. Razionale: una sessione FX con un'unica bar di chiusura banca a volume zero (es. festività non standard, gap di liquidity) è un evento legittimo del data feed, non un errore di input. Coerente con la convenzione "warmup → None" e con `find_support_resistance` che gestisce graceful bar list piccole. Le bar list mismatch (input invalido) restano fail-fast, ma volume zero è dato valido.

- **Validazione `anchor_ts` tz-aware tramite ValueError italiano:** scelta di sollevare ValueError invece di TypeError. Razionale: ValueError esprime "il valore di un parametro è invalido" (anchor_ts naive è semanticamente sbagliato per FX session), mentre TypeError esprimerebbe "il tipo è sbagliato" (sarebbe corretto se accettassimo solo `aware datetime` come tipo distinto, ma Python non differenzia naive/aware al type system). Coerente con pattern fail-fast Wave 1+ (`atr` length mismatch, `bollinger_bands` ddof, `donchian` length<=0, `pivots` anchor non valido).

- **Pattern del flag binario `anchored` vs find-anchor-index:** scelta di un loop singolo con flag invece di due passaggi (1° passaggio: `anchor_idx = next(i for i,b in enumerate(bars) if ts(b) >= anchor_ts)`; 2° passaggio: cumulazione da `anchor_idx`). Vantaggi: (a) un solo passaggio O(n); (b) gestisce naturalmente il caso `anchor_ts > tutti i bar` (ritorna tutti None senza eccezioni o branch separato); (c) leggibilità: il flag esprime lo stato della macchina iterando.

## Deviations from Plan

### Auto-fixed Issues

Nessuna deviazione richiesta. Il plan è stato eseguito esattamente come scritto.

L'unico chiarimento implementativo è stato la scelta dell'estrazione `_typical_price` come helper privato (il plan-as-written aveva la formula inline; estrarla in helper migliora leggibilità e consistenza con `_bar_volume` — ma la formula matematica è identica). Cambio cosmetico, non funzionale.

---

**Total deviations:** 0.
**Impact on plan:** Nessuno scope creep. Pattern, formule, validation messages, dataclass shape, anchor semantics, reset NY-17 sono identici al plan-as-written.

## Issues Encountered

- Nessun problema tecnico durante l'esecuzione. Sia RED (test prima → ImportError) sia GREEN (impl → 7/7 PASS al primo run) sia leakage gate (5/5 PASS al primo run) sono andati lisci.

- Il warning `Pandas4Warning` su `pandas_ta` (visibile nel summary pytest) è preesistente e non legato a questo plan: deriva dalla versione di pandas-ta dev-dep installata e dalla compatibilità futura con pandas 4.0. Non blocca, non degrada coverage.

## User Setup Required

None — nessuna nuova dipendenza, nessuna config esterna, nessun secret. Tutto il codice usa solo stdlib (`dataclasses`, `datetime`, `zoneinfo` già presente in `_helpers.py`).

## Next Wave Readiness

- **Wave 2 plan 07 (NR4/NR7 + Closing Score — INDIC-10/11):** sblocca, indipendente da questo plan.
- **Wave 2 plan 08 (MTF align — INDIC-13):** sblocca, indipendente.
- **Wave 3 plan 09 (regime classifier + compute_all_extended — INDIC-14):** può ora consumare:
  - `vwap_intraday(bars).vwap[-1]` come livello chiave intraday (proxy "fair price" della sessione corrente).
  - `(close - vwap_intraday) / atr` come feature distanza-da-vwap normalizzata.
- **Phase 4 (Strategy Refactor):**
  - Setup A (breakout): conferma direzione = breakout sopra/sotto vwap della sessione corrente.
  - Setup B (S/R reversal): vwap come livello dinamico di mean-reversion.
  - Setup D (trend pullback): pullback verso vwap intraday come zona di rientro low-risk.
- **Phase 5 (Baseline Backtest):** non blocca — preflight in 05-08 verificherà che le 9 plan di Phase 2 siano completate (5 → 6 dopo questo plan).
- **Phase 7 (ML Classifier):** features candidate da questo plan:
  - `vwap_intraday_dist = (close - vwap_intraday) / atr` (posizione vs valore medio sessione, normalizzata).
  - `vwap_anchored_dist_from_swing = (close - vwap_anchored_from_last_swing) / atr` (distanza dal vwap dall'ultimo swing high/low).
  - `cumulative_v_normalized = cumulative_v / avg_volume(20)` (volume cumulato della sessione corrente vs media bar — proxy di interesse istituzionale).

## Self-Check

Verifica claims fatte sopra (working dir `C:\trading-agent`):

- `[ -f tests/test_indicators_volume.py ]` → FOUND
- `grep -c "@dataclass" indicators/volume.py` → 1 → FOUND (VWAPResult)
- `grep -c "^def vwap_intraday" indicators/volume.py` → 1 → FOUND
- `grep -c "^def vwap_anchored" indicators/volume.py` → 1 → FOUND
- `grep -c "^def avg_volume" indicators/volume.py` → 1 → FOUND (preservato Wave 0)
- `grep -c "pandas_ta" indicators/volume.py` → 0 → FOUND (purity)
- `grep -c "21" tests/test_indicators_volume.py` → 5+ → FOUND (DST summer 21:00 UTC asserted)
- `grep -c "22" tests/test_indicators_volume.py` → 1+ → FOUND (DST winter 22:00 UTC asserted)
- `grep -c "_session_id_ny17" indicators/volume.py` → 2 → FOUND (import + chiamata in vwap_intraday)
- Commit `ad5ed9a` (Task 1 feat) → FOUND in `git log`
- Commit `78f85e5` (Task 2 test) → FOUND in `git log`
- `pytest tests/test_indicators_volume.py -x -v` → 7 passed → VERIFIED
- `pytest tests/test_indicators_purity.py::test_no_future_leakage_vwap_intraday` → 5 passed → VERIFIED
- Suite intera `pytest` → 317 passed, 1 skipped → VERIFIED (305 baseline plan 05 + 12 nuovi)
- `from indicators import vwap_intraday, vwap_anchored, VWAPResult` → import success → VERIFIED
- Hand-calc single-bar: tp=1.5, vol=10 → vwap=1.5, cum_pv=15.0, cum_v=10.0 → VERIFIED
- Hand-calc reset winter (22:00 UTC): vwap[0]=1.5, vwap[1]=3.0, vwap[2]=110/30 → VERIFIED
- Hand-calc reset summer (21:00 UTC): vwap[0]=1.5, vwap[1]=3.0 (reset) → VERIFIED
- `vwap_anchored` ValueError su `datetime(2024,1,1)` naive → VERIFIED
- Spot-check EURUSD H1 fixture: vwap_intraday last ≈ 1.16909, 500/500 non-None, anchored idx100 last ≈ 1.17357 → VERIFIED

## Self-Check: PASSED

---
*Phase: 02-indicators-library*
*Wave: 2*
*Completed: 2026-05-08*
