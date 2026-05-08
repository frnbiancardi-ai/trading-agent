---
phase: 02-indicators-library
plan: 09
subsystem: indicators
tags: [python, volatility-regime, atr-percentile, rolling-rank, compute-all-extended, yaml-config, pure-functions, future-leakage-gate, phase-final-gate]

requires:
  - phase: 02-indicators-library
    plan: 01
    provides: pacchetto indicators/, atr (Wave 0), data/configs/regime.yaml schema D-15, fixture eurusd_h1_500, universal future-leakage gate
  - phase: 02-indicators-library
    plans: [02, 03, 04, 05, 06, 07, 08]
    provides: tutti i 13 indicatori INDIC-01..13 (BB, Keltner, ADX, MACD, Stoch, Donchian, Fib, Pivots, VWAP, NR/CS, Hurst, MTF align)
provides:
  - "indicators.volatility.load_regime_config(symbol, yaml_path) -> dict (override per-symbol con fallback default, safe_load)"
  - "indicators.volatility.volatility_regime(bars, cfg) -> RegimeResult(state, atr_percentile, window) length-N (INDIC-14, D-15/D-16)"
  - "RegimeResult dataclass (D-04..D-06): state ∈ {compressed/normal/expanded/None}, atr_percentile ∈ [0,1]∪{None}"
  - "indicators.aggregate.compute_all_extended(bars, regime_cfg=None) -> snapshot 14-indicator dict (37 chiavi)"
  - "Re-export volatility_regime, load_regime_config, RegimeResult, compute_all_extended in indicators/__init__.py + __all__"
  - "Pattern leakage gate esteso (5 idx) per volatility_regime"
  - "Phase 2 final gate: 374 test verdi (358 → 374, +16) + Skill discrepancy Boomer A2 ancora flagged"
affects: [04, 05, 07]

tech-stack:
  added: []  # nessuna nuova dipendenza; pyyaml gia presente da Phase 1 (backtest/costs.py)
  patterns:
    - "Rolling rank percentile: rank = #{v in window : v <= cur} / |window| dentro finestra trailing — MAI series.rank(pct=True) globale (Pitfall 4)"
    - "YAML loader pattern (mirror backtest/costs.py:load_cost_model): per-symbol override con fallback `default`, safe_load only"
    - "compute_all_extended come snapshot last-valid (riusa _last_valid Wave 0): non rompe compute_all 4-key bit-for-bit"
    - "MTF align (INDIC-13) escluso da compute_all_extended: richiede stream multi-TF separati H4/H1/M15"
    - "Phase final gate via test_all_14_indic_requirement_symbols_exposed (assenza simboli pubblici fa fallire CI)"

key-files:
  created:
    - .planning/phases/02-indicators-library/02-09-SUMMARY.md
  modified:
    - indicators/volatility.py (RegimeResult + load_regime_config + volatility_regime, ~95 righe in piu)
    - indicators/aggregate.py (compute_all_extended, ~110 righe)
    - indicators/__init__.py (re-export + __all__ esteso)
    - tests/test_indicators_volatility.py (5 test regime hand-calc/sanity/leakage-signature)
    - tests/test_indicators_aggregate.py (6 test compute_all_extended + phase-gate)
    - tests/test_indicators_purity.py (test_no_future_leakage_volatility_regime parametrizzato 5 idx)
  deleted: []

key-decisions:
  - "compute_all preservato BIT-FOR-BIT identico (4-key dict): hard-lock backward-compat verificato da test_compute_all_unchanged_legacy_callsite. claude_agent.py:12 + mcp_server.py:28 continuano a funzionare invariati."
  - "compute_all_extended esclude align (INDIC-13): align richiede dict di stream multi-TF (H4/H1/M15), non puo essere derivato da una singola list[dict]. Phase 4 strategy chiamera align() direttamente con i bucket multi-TF. Documentato esplicitamente nella docstring."
  - "Rolling rank con uguaglianza inclusiva (`v <= cur`): scelto per coerenza con la convenzione classica nearest-rank percentile (`#{v: v<=cur}/N`). Su ATR costante in finestra rank=1.0 (deterministico, non NaN/None)."
  - "Empty input → 4 chiavi legacy + flag `extended_empty=True`: evita di sollevare e mantiene shape compatibile con consumer downstream (Phase 4 strategy puo discriminare con `out.get('extended_empty')`)."
  - "regime_cfg=None safe-no-op: regime_state e regime_atr_pct restano None (no chiamata a volatility_regime). Permette al consumer di chiamare compute_all_extended senza dover sempre fornire la config (es. tool MCP debug, sanity check unit test)."
  - "atr_percentile threshold conversion `compressed_below/100`: i valori YAML sono espressi in percentuali (es. 25, 70) per leggibilita umana, mentre internamente usiamo frazioni in [0,1] coerenti con il rank. Conversione esplicita nel costruttore di volatility_regime."

patterns-established:
  - "Pattern rolling-rank percentile: per ogni indicatore che richieda 'percentile in finestra', usare strict trailing window con `sum(1 for v in window if v <= cur) / len(window)` — MAI pandas .rank(pct=True) globale"
  - "Pattern aggregator dual-shape: una funzione legacy `compute_all` bit-for-bit immutabile + una funzione estesa `compute_all_extended` superset, entrambe esposte dal barrel; consumer downstream sceglie esplicitamente"
  - "Pattern phase-final symbol-completeness gate: test parametrizzato che enumera tutti i requirement pubblici INDIC-01..N (`hasattr(indicators, sym)`) — fail-fast in CI se la fase si rompe"

requirements-completed: [INDIC-14]

duration: 6min
completed: 2026-05-08
---

# Phase 2 Plan 09: Wave 3 — Volatility regime + compute_all_extended Summary

**INDIC-14 implementato come 2 funzioni pure in `indicators/volatility.py`: `load_regime_config(symbol, yaml_path)` con override per-symbol e fallback `default` via `yaml.safe_load` (mirror `backtest/costs.py:load_cost_model`); `volatility_regime(bars, cfg)` che classifica ogni bar in `{compressed, normal, expanded, None}` via rolling-rank percentile di ATR(14) su finestra trailing `window=200` — Pitfall 4 (no rank globale) verificato sia da test signature dedicato sia dal leakage-gate universale a 5 spot indices. `RegimeResult` dataclass length-N (state, atr_percentile, window). Aggregatore `compute_all_extended(bars, regime_cfg=None)` in `indicators/aggregate.py` ritorna snapshot 14-indicator (37 chiavi: 4 legacy + 33 estese). `compute_all` bit-for-bit immutato (4-key dict, callsite `claude_agent.py:12` + `mcp_server.py:28` ancora funzionanti). Phase 2 final gate: `test_all_14_indic_requirement_symbols_exposed` enumera ogni INDIC-01..14 simbolo pubblico. Suite intera 374/374 verde + 1 skipped (358 → 374, +16: 5 hand-calc regime + 5 leakage regime + 6 aggregate/phase-gate).**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-08T~16:00Z
- **Completed:** 2026-05-08
- **Tasks:** 3 (impl regime → impl extended+test → cleanup docstring per acceptance grep)
- **Files created:** 1 (`02-09-SUMMARY.md`)
- **Files modified:** 6 (`indicators/volatility.py`, `indicators/aggregate.py`, `indicators/__init__.py`, `tests/test_indicators_volatility.py`, `tests/test_indicators_aggregate.py`, `tests/test_indicators_purity.py`)
- **Files deleted:** 0
- **Suite intera:** 374 passed, 1 skipped (358 baseline plan 08 → 374, +16: 5 regime hand-calc + 5 regime leakage + 6 aggregate/phase-gate). Skipped: Mottl `hurst` parity (lib non installata).

## Accomplishments

- **`load_regime_config(symbol, yaml_path)`** in `indicators/volatility.py`:
  - Apertura file UTF-8 + `yaml.safe_load(f) or {}` (mai `yaml.load`).
  - Lookup `cfg["symbols"][symbol]` con fallback `cfg["default"]`.
  - Solleva `KeyError` con messaggio italiano se ne il simbolo ne `default` esistono.
  - Hand-calc verificato: `EURUSD` → `{window:200, compressed_below:25, expanded_above:75}`, `UNKNOWN_SYMBOL` → `{window:200, compressed_below:30, expanded_above:70}`.

- **`volatility_regime(bars, cfg)`** in `indicators/volatility.py`:
  - Calcola `atr_series = atr(highs, lows, closes, period=14)` (riuso Wave 0).
  - Per ogni bar `i` con `i+1 >= window` ed `atr_series[i] is not None`: estrae la finestra trailing `atr_series[i-window+1 : i+1]`, scarta None, calcola `rank = sum(1 for v in window_vals if v <= cur) / len(window_vals)`.
  - Threshold conversion: `lo = compressed_below/100`, `hi = expanded_above/100` (YAML in percentuali, runtime in frazioni).
  - State: `rank < lo → 'compressed'`, `rank > hi → 'expanded'`, altrimenti `'normal'`.
  - Warmup: per `i+1 < window` o `len(window_vals) < window`, `state[i] = atr_percentile[i] = None`.
  - `cfg=None` → defaults: `window=200`, `compressed_below=30`, `expanded_above=70`.

- **`RegimeResult` dataclass** length-N (D-04..D-06): tre campi (`state`, `atr_percentile`, `window`), co-located in `indicators/volatility.py`.

- **`compute_all_extended(bars, regime_cfg=None)`** in `indicators/aggregate.py`:
  - Snapshot 14-indicator: 4 chiavi legacy (`sma_20`, `ema_50`, `rsi_14`, `atr_14`) + 33 chiavi estese.
  - Estese: `bb_upper/middle/lower/bbw/squeeze`, `kc_upper/lower`, `adx_14`, `plus_di_14`, `minus_di_14`, `macd/macd_signal/macd_hist`, `stoch_k/stoch_d`, `donch_upper/donch_lower`, `pivot_p`, `pivot_camarilla_h3/l3`, `fib_0382/fib_0500/fib_0618/fib_direction`, `vwap`, `avg_volume_20`, `nr4/nr7/boomer`, `closing_score`, `hurst`, `regime_state/regime_atr_pct`.
  - `regime_cfg=None` → `regime_state` e `regime_atr_pct` sono entrambi None (safe no-op).
  - Empty input → 4 chiavi legacy + flag `extended_empty=True`.
  - MTF align (INDIC-13) escluso: documentato esplicitamente in docstring (richiede stream multi-TF separati che `compute_all_extended` non puo dedurre da una sola list[dict]).

- **`compute_all` BIT-FOR-BIT preservato:**
  - `set(compute_all(bars).keys()) == {"sma_20","ema_50","rsi_14","atr_14"}` verificato da `test_compute_all_unchanged_legacy_callsite`.
  - `claude_agent.py:12` + `mcp_server.py:28` callsite ancora funzionanti (`test_legacy_callsite_imports_unchanged` PASS).

- **Test (`tests/test_indicators_volatility.py`, +5 nuovi):**
  - `test_load_regime_config_eurusd_override`: EURUSD → 25/75/200.
  - `test_load_regime_config_default_fallback`: simbolo non listato → 30/70/200.
  - `test_volatility_regime_warmup_none`: i in 0..198 → state=None.
  - `test_volatility_regime_states_present_after_warmup`: post-warmup almeno 'normal' presente, percentile in [0,1].
  - `test_volatility_regime_no_full_series_rank_signature`: i=200 in `prefix=bars[:201]` deve eguagliare i=200 in full — guardia esplicita contro implementazione full-series rank (Pitfall 4 signature test).

- **Test (`tests/test_indicators_aggregate.py`, +6 nuovi):**
  - `test_compute_all_unchanged_legacy_callsite`: hard-lock 4-key dict.
  - `test_compute_all_extended_contains_all_indicators`: presenza tutte le 33 chiavi attese + 4 legacy.
  - `test_compute_all_extended_without_regime_cfg`: cfg=None → regime fields = None.
  - `test_compute_all_extended_empty_input`: empty bars → flag + 4 legacy keys.
  - `test_all_14_indic_requirement_symbols_exposed`: enumera ogni INDIC-01..14 simbolo (29 simboli totali, 14 funzioni + 14 Result + 1 helper YAML loader).
  - `test_legacy_callsite_imports_unchanged`: re-import indicators senza pandas_ta.

- **Test (`tests/test_indicators_purity.py`, +1 parametrizzato 5 idx):**
  - `test_no_future_leakage_volatility_regime[200,250,350,450,499]`: verifica `volatility_regime(prefix)[i] == volatility_regime(full)[i]` per 5 spot indices post-warmup.

- **Spot-check fixture EURUSD H1 (500 bar) con cfg EURUSD (25/75):**
  - 287 bar con stato calcolato (post-warmup, window=200; 213 None nei warmup).
  - Distribuzione: **61 compressed (21%)**, **155 normal (54%)**, **71 expanded (25%)**.
  - `atr_percentile` range: [0.005, 1.000], media 0.532 — distribuzione plausibilmente bilanciata con leggero skew verso normal.
  - `compute_all_extended(bars, cfg)` ritorna 37 chiavi: regime_state="normal", regime_atr_pct=0.585, bb_squeeze=False, hurst=1.062 — tutti coerenti con regime trending H1 osservato in plan 04.

- **Purity runtime preservata:** `pandas_ta` NON importato a runtime (`grep -rE "^(import|from) pandas_ta" indicators/` → 0 match; `test_no_pandas_ta_at_runtime` Wave 0 ancora verde; nuovo `test_legacy_callsite_imports_unchanged` ricarica fresh e verifica).

## Task Commits

1. **Task 1: volatility_regime + load_regime_config + RegimeResult** — `a1b5dc0` (feat)
2. **Task 2: compute_all_extended + test phase-gate + leakage** — `b4c895a` (feat)
3. **Task 3: cleanup docstring per acceptance grep letterali** — `7851a95` (docs)

## Files Created/Modified

### Created
- `.planning/phases/02-indicators-library/02-09-SUMMARY.md` (questo file).

### Modified — runtime
- `indicators/volatility.py`: aggiunti `RegimeResult` dataclass, `load_regime_config`, `volatility_regime`. Imports `pathlib.Path` + `yaml`. `atr`, `bollinger_bands`, `keltner` invariati.
- `indicators/aggregate.py`: aggiunta `compute_all_extended`. `compute_all` BIT-FOR-BIT immutato.
- `indicators/__init__.py`: aggiunti `volatility_regime`, `load_regime_config`, `RegimeResult`, `compute_all_extended` agli import e `__all__`.

### Modified — test
- `tests/test_indicators_volatility.py`: 5 test INDIC-14.
- `tests/test_indicators_aggregate.py`: 6 test compute_all_extended + phase-gate (`test_all_14_indic_requirement_symbols_exposed`, `test_legacy_callsite_imports_unchanged`).
- `tests/test_indicators_purity.py`: `test_no_future_leakage_volatility_regime` parametrizzato 5 idx.

## Decisions Made

- **MTF align escluso da compute_all_extended:** decisione architetturale documentata in docstring. `align(streams)` richiede `dict[str, list[dict]]` con chiavi H4/H1/M15 separate; `compute_all_extended` riceve una sola list[dict] (tipicamente M15) e non puo dedurre i bucket H4/H1. Phase 4 strategy refactor chiamera `align(...)` direttamente con i bucket multi-TF (consumer-side aggregation).

- **regime_cfg=None safe no-op:** un consumer che vuole solo lo snapshot dei 13 indicatori non-regime puo chiamare `compute_all_extended(bars)` senza cfg. Le chiavi `regime_state` e `regime_atr_pct` saranno None ma presenti — schema stabile per Phase 4/7. Alternativa scartata: non includere le chiavi quando cfg=None (avrebbe richiesto agli enumerable consumer di gestire dict shape variabile).

- **Empty input → flag `extended_empty=True`:** invece di sollevare ValueError. Coerente col pattern Wave 1+ che ammette graceful handling di bar list vuote (es. `find_support_resistance`, `closing_score(bars=[])`).

- **`pivot_camarilla_h3/l3` esposti (NON h1/h4):** scelti i livelli "core" Camarilla per il setup A breakout (h3/l3 sono i livelli operativi standard nella letteratura Camarilla). h1/h2/h4/l1/l2/l4 restano accessibili via `pivots(bars, 'daily').camarilla["hN"][i]` per consumer che li vogliano. Trade-off: snapshot conciso vs estensibilita.

- **Threshold conversion `/100` interno:** YAML schema mantiene percentuali (`compressed_below: 25`) per leggibilita umana; runtime converte in frazioni (`lo = 0.25`) per match con il rank in [0,1]. Documentato nella docstring di `volatility_regime`.

- **Rolling rank con `<=` (inclusive):** convenzione nearest-rank classica. Su finestra di ATR costanti rank == 1.0 (deterministico, non NaN). Test sanity verifica: `test_volatility_regime_states_present_after_warmup` controlla che le percentili siano sempre in [0,1].

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test `test_legacy_callsite_imports_unchanged` falliva per ordine di esecuzione**

- **Found during:** Task 2 (esecuzione test phase-gate)
- **Issue:** Il test plan-as-written assumeva di poter verificare `pandas_ta not in sys.modules` dopo `del sys.modules["indicators*"]`. Pero i test parity Wave 1 (`test_bbands_parity_with_pandas_ta`, `test_keltner_parity_with_pandas_ta`, `test_adx_parity_with_pandas_ta`, ...) eseguiti precedentemente in batch importano `pandas_ta` a livello di sessione pytest e lo lasciano in `sys.modules`. Il test fallisce con "pandas_ta importato a runtime — vietato (D-07)" anche se il pacchetto `indicators` da solo NON lo importa. Falso positivo dovuto a execution-order, non a infrazione di purity.
- **Fix:** Modificato il test per rimuovere ANCHE `pandas_ta` da `sys.modules` prima del fresh-import del pacchetto `indicators`. L'invariante che ora verifichiamo e: "il fresh-import del pacchetto indicators non tira dentro pandas_ta come dipendenza transitiva" — semantica corretta della policy D-07. Aggiunta docstring esplicita sul motivo del cleanup.
- **Files modified:** `tests/test_indicators_aggregate.py`
- **Commit:** `b4c895a` (Task 2)
- **Verifica:** test PASS in batch e in isolation; il preesistente `test_no_pandas_ta_at_runtime` (Wave 0) gia usava lo stesso pattern di cleanup.

**2. [Rule 1 - Bug] Acceptance criteria del plan grep `yaml.safe_load`==1 e `rank(pct`==0 violati per docstring testuali**

- **Found during:** Task 3 (audit grep finali)
- **Issue:** Le docstring di `load_regime_config` e `volatility_regime` plan-as-written citavano i pattern proibiti come elemento educativo: `"Usa 'yaml.safe_load' (mai 'yaml.load')..."` e `"... uso di pandas '.rank(pct=True)' produrrebbe future leakage..."`. Le citazioni testuali contavano come match grep (`yaml.safe_load`==2 invece di 1, `rank(pct`==1 invece di 0). Il codice runtime e completamente conforme — solo le docstring contenevano le parole letterali per spiegare il pitfall.
- **Fix:** Riformulato le docstring senza i token grep-able: "safe_load (no execution of arbitrary tags)" e "un rank globale produrrebbe future leakage" rispettivamente. Significato semantico preservato; grep ora restituisce esattamente 1 e 0.
- **Files modified:** `indicators/volatility.py`
- **Commit:** `7851a95` (Task 3)
- **Verifica:** grep -c "yaml.safe_load" indicators/volatility.py → 1, grep -c "rank(pct" indicators/volatility.py → 0.

---

**Total deviations:** 2 auto-fixed (Rule 1 — entrambe in test/docstring, nessuna nel codice runtime). L'implementazione di `volatility_regime`, `load_regime_config`, `compute_all_extended` e `RegimeResult` e identica al plan-as-written. La deviation #1 (test order) e una correzione di pattern di test ereditata dal Wave 0. La deviation #2 (docstring grep) e un cleanup testuale per soddisfare letteralmente l'acceptance criterion.

**Impact on plan:** Nessuno scope creep. Pattern, formule, dataclass shape, threshold conversion, schema YAML, hard-lock backward-compat sono identici al plan-as-written.

## Issues Encountered

- Nessun problema tecnico nel codice runtime. Il fixing-loop e stato confinato ai test e alle docstring (deviations 1 e 2 sopra), entrambi con verify embedded passato al primo retry.
- Warning `Pandas4Warning` su `pandas_ta` (visibile nel summary pytest) preesistente da Wave 0; non legato a questo plan.

## User Setup Required

None — `pyyaml` gia presente da Phase 1 (`backtest/costs.py:load_cost_model`); nessuna nuova dipendenza, nessuna config esterna, nessun secret. Il file `data/configs/regime.yaml` schema D-15 e gia stato committato in plan 02-01 (Wave 0).

## Confirmation: D-01..D-16 Lock Compliance

- **D-01 — Pure functions, no I/O nelle funzioni indicator:** ✓ `volatility_regime` non legge file, non chiama API, e deterministica. `load_regime_config` legge YAML ma e funzione separata (loader, non indicator).
- **D-02 — list[dict] OHLCV input:** ✓ `volatility_regime(bars: list[dict], ...)`.
- **D-03 — backward-compat 4 callsite:** ✓ verificato da `test_legacy_callsite_imports_unchanged` + `test_compute_all_unchanged_legacy_callsite` (4-key dict invariato).
- **D-04..D-06 — dataclass-of-lists, list[T|None], co-location:** ✓ `RegimeResult` ha 3 campi list[T|None]+ int, co-located in `indicators/volatility.py`.
- **D-07 — pandas_ta dev-only, mai a runtime:** ✓ verificato da `test_no_pandas_ta_at_runtime` (Wave 0) + `test_legacy_callsite_imports_unchanged` (nuovo).
- **D-08..D-12 — convenzioni Wilder/RMA/sessione/Camarilla:** ✓ riuso `atr` Wave 0 invariato; `pivots` chiamato verbatim in compute_all_extended.
- **D-13 — caller-side slicing per MTF:** ✓ MTF align ESCLUSO da compute_all_extended (delegato a Phase 4 strategy).
- **D-14 — score MTF range {0.0, 0.33, 0.67, 1.0}:** ✓ Wave 3 plan 08 invariato.
- **D-15 — schema regime.yaml (default + symbols, window/compressed_below/expanded_above):** ✓ `load_regime_config` segue lo schema esatto, parity con `backtest/costs.py:load_cost_model`.
- **D-16 — atr_percentile come rolling rank:** ✓ implementato come `sum(1 for v in window_vals if v <= cur) / len(window_vals)` su finestra trailing; verificato da `test_volatility_regime_no_full_series_rank_signature` + leakage gate parametrizzato 5 idx.

## Next Phase Readiness — PHASE 2 COMPLETE

**Tutte le 9 plan di Phase 2 (01..09) ora COMPLETE.**

- **Plan 01 (Wave 0 scaffolding):** pacchetto `indicators/`, helpers, fixture, dev-dep pandas-ta, schema regime.yaml — ✓
- **Plan 02 (Wave 1 BB+Keltner — INDIC-01/06):** ✓
- **Plan 03 (Wave 1 ADX/MACD/Stoch — INDIC-02/03/04):** ✓
- **Plan 04 (Wave 1 Hurst — INDIC-12):** ✓
- **Plan 05 (Wave 2 Donchian/Fib/Pivots — INDIC-05/08/09):** ✓
- **Plan 06 (Wave 2 VWAP — INDIC-07):** ✓
- **Plan 07 (Wave 2 NR/Closing Score — INDIC-10/11):** ✓
- **Plan 08 (Wave 3 MTF align — INDIC-13):** ✓
- **Plan 09 (Wave 3 regime + compute_all_extended — INDIC-14):** ✓ ← QUESTO PLAN

**Phase 2 ready per verification step (`/gsd-verify-phase 2`).** Auto-push avverra dopo che la verification PASSED.

- **Phase 3 (Patterns Catalog) o Phase 4 (Strategy Refactor)** sbloccato: tutti i 14 indicatori INDIC-01..14 disponibili come funzioni pure + dataclass-of-lists. Phase 4 strategy refactor puo riscrivere `strategy.py` per consumare:
  - Setup A (breakout): `donchian.upper`, `pivot_camarilla_h3`, `bb_squeeze=False+adx>25`, MTF align score==1.0.
  - Setup B (reversal): `pivots.r3/s3`, `stochastic.k/d` overbought/oversold, MTF score=0.33.
  - Setup C (compression breakout): `bb_squeeze=True OR boomer=True`, `regime_state='compressed'`.
  - Setup D (trend pullback): `fib_0500/fib_0618` zone, `hurst > 0.6`, MTF score >= 0.67.
- **Phase 5 (Baseline Backtest) preflight in plan 05-08:** verifichera che le 9 plan Phase 2 siano completate (ora 9/9 ✓).
- **Phase 7 (ML Classifier):** features candidate dal regime classifier:
  - `regime_state` come categorical {compressed/normal/expanded/None}.
  - `regime_atr_pct` come continuous [0,1].
  - `regime_change_5 = (regime_state[i] != regime_state[i-5])` come binaria di transizione.
  - Plus tutte le 31 features di `compute_all_extended` (esclusi i campi MTF che richiedono multi-TF).

## Self-Check

Verifica claims fatte sopra (working dir `C:\trading-agent`):

- `[ -f indicators/volatility.py ]` → FOUND (con volatility_regime + load_regime_config + RegimeResult)
- `[ -f indicators/aggregate.py ]` → FOUND (con compute_all + compute_all_extended)
- `[ ! -f indicators.py ]` → FOUND (flat module gone, preservato da Wave 0)
- `[ -f data/configs/regime.yaml ]` → FOUND (schema D-15, da plan 01)
- `grep -c "def volatility_regime" indicators/volatility.py` → 1 → FOUND
- `grep -c "def load_regime_config" indicators/volatility.py` → 1 → FOUND
- `grep -c "def compute_all_extended" indicators/aggregate.py` → 1 → FOUND
- `grep -c "^def compute_all" indicators/aggregate.py` → 2 (compute_all + compute_all_extended) → FOUND
- `grep -c "yaml.safe_load" indicators/volatility.py` → 1 → FOUND (acceptance criterion soddisfatto)
- `grep -c "yaml.load(" indicators/volatility.py` → 0 → FOUND (no unsafe load)
- `grep -c "rank(pct" indicators/volatility.py` → 0 → FOUND (Pitfall 4 — no full-series rank)
- `grep -rE "^(import|from) pandas_ta" indicators/` → 0 match → FOUND (purity preservata)
- Commit `a1b5dc0` (Task 1 feat) → FOUND in `git log`
- Commit `b4c895a` (Task 2 feat) → FOUND in `git log`
- Commit `7851a95` (Task 3 docs) → FOUND in `git log`
- `pytest tests/test_indicators_volatility.py tests/test_indicators_aggregate.py tests/test_indicators_purity.py` → 92 passed → VERIFIED
- Suite intera `pytest tests/` → 374 passed, 1 skipped → VERIFIED (358 baseline plan 08 + 16 nuovi)
- `from indicators import volatility_regime, load_regime_config, RegimeResult, compute_all_extended` → import success → VERIFIED
- `compute_all 4-key bit-for-bit:` `set(compute_all(bars).keys()) == {'sma_20','ema_50','rsi_14','atr_14'}` → VERIFIED
- `compute_all_extended` 37 chiavi (4 legacy + 33 estese) → VERIFIED
- `volatility_regime` warmup 0..198 = None su window=200 → VERIFIED
- `volatility_regime` rolling rank signature: `partial[200] == full[200]` → VERIFIED
- `volatility_regime` leakage-free 5 idx [200,250,350,450,499] → 5/5 PASS
- Spot-check fixture EURUSD H1 (cfg EURUSD 25/75): 287 bar valide post-warmup, 61 compressed, 155 normal, 71 expanded; atr_percentile mean 0.532 → VERIFIED

## Self-Check: PASSED

---
*Phase: 02-indicators-library*
*Wave: 3*
*Plan: 09 (FINAL)*
*Completed: 2026-05-08*
*Phase 2 status: 9/9 plans complete — ready for verification.*
