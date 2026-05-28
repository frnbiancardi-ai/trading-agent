---
phase: 02-indicators-library
plan: 01
subsystem: indicators
tags: [python, pure-functions, pandas-ta, zoneinfo, package-refactor]

requires:
  - phase: 01-backtest-engine
    provides: backtest.loader.load_bars (UTC-stamped Bar list, GMT-6→UTC) usato dallo script di build della fixture EURUSD H1 500-bar.
provides:
  - indicators/ pacchetto (10 submoduli: trend, momentum, volatility, structure, volume, bars, mtf, hurst, aggregate, _helpers)
  - _wilder_smooth (RMA generale per Wave 1 ADX/Stoch/Keltner)
  - _session_id_ny17 (DST-aware NY-17 bucketing per Wave 2 VWAP/Pivot)
  - data/configs/regime.yaml (schema D-15 per INDIC-14)
  - tests/conftest.py eurusd_h1_500 session-scoped fixture
  - tests/fixtures/eurusd_h1_last500.csv (500 barre snapshot)
  - tests/test_indicators_purity.py (universal future-leakage gate)
  - requirements-dev.txt (pandas-ta==0.4.71b0, dev-dep oracle)
affects: [02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08, 02-09, 03, 04, 05, 06, 07]

tech-stack:
  added: [pandas-ta==0.4.71b0 (dev-dep), llvmlite, numba, numpy 2.2.6 (downgrade da 2.4.4 per pandas-ta)]
  patterns:
    - "Pacchetto barrel con re-export espliciti per backward-compat"
    - "Wilder/RMA smoothing seeded con SMA del primo periodo (parity 1e-6 vs pandas-ta)"
    - "zoneinfo NY-17 session bucketing (winter 22:00 UTC, summer 21:00 UTC)"
    - "Universal future-leakage property test parametrizzato su 5 spot indices"
    - "pandas-ta come dev-dep oracolare, MAI importato a runtime"

key-files:
  created:
    - indicators/__init__.py
    - indicators/_helpers.py
    - indicators/trend.py
    - indicators/momentum.py
    - indicators/volatility.py
    - indicators/structure.py
    - indicators/volume.py
    - indicators/bars.py
    - indicators/mtf.py
    - indicators/hurst.py
    - indicators/aggregate.py
    - data/configs/regime.yaml
    - requirements-dev.txt
    - tests/fixtures/build_eurusd_h1_last500.py
    - tests/fixtures/eurusd_h1_last500.csv
    - tests/test_indicators_purity.py
    - tests/test_indicators_trend.py
    - tests/test_indicators_aggregate.py
  modified:
    - tests/conftest.py
  deleted:
    - indicators.py (flat module promosso a pacchetto)

key-decisions:
  - "Re-export espliciti in indicators/__init__.py invece di __all__-only, per garantire che le 4 callsite esistenti (claude_agent.py:12, mcp_server.py:28, scanner.py:10, strategy.py:11) continuino a funzionare invariate."
  - "compute_all bit-for-bit identico al legacy: 4-key dict {sma_20, ema_50, rsi_14, atr_14}. compute_all_extended (14 indicatori) arriva in Wave 3 (plan 02-09)."
  - "Script di build fixture committato (non solo CSV) per garantire riproducibilità del 500-bar snapshot."
  - "Conftest esteso (NON sostituito): preservato lo stub MetaTrader5 + fixture esistenti di Phase 1."

patterns-established:
  - "Pattern barrel: from indicators.<sub> import <name> con __all__ esplicito"
  - "Pattern Wilder seed: seed = sum(values[:period])/period (matches pandas-ta rma)"
  - "Pattern future-leakage gate: per ogni rolling indicator nuovo, parametrizzare test purity su 5 indici (warmup+1, 100, 250, 400, 499)"

requirements-completed: []  # Wave 0 scaffolding non completa direttamente INDIC-01..14; abilita Wave 1+

duration: 8min
completed: 2026-05-08
---

# Phase 2 Plan 01: Wave 0 Scaffolding Summary

**Pacchetto `indicators/` (10 submoduli + helpers) con backward-compat re-exports, dev-dep pandas-ta come oracolo, fixture EURUSD H1 500-bar + regime.yaml + universal future-leakage gate.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-08T08:46:40Z
- **Completed:** 2026-05-08T08:54:32Z
- **Tasks:** 3
- **Files created:** 18
- **Files modified:** 1 (`tests/conftest.py`)
- **Files deleted:** 1 (`indicators.py`)

## Accomplishments

- Promosso `indicators.py` flat (280 righe) a pacchetto `indicators/` con 10 submoduli per dominio (trend, momentum, volatility, structure, volume, bars, mtf, hurst, aggregate, _helpers).
- Tutte le 4 callsite esistenti (`claude_agent.py:12`, `mcp_server.py:28`, `scanner.py:10`, `strategy.py:11`) continuano a funzionare senza modifiche grazie ai re-export espliciti in `__init__.py`.
- `compute_all` ritorna il dict 4-key `{sma_20, ema_50, rsi_14, atr_14}` bit-for-bit identico al legacy (gate retro-compat verificato da test).
- `_helpers.py` aggiunge `_wilder_smooth` (RMA generalizzato) e `_session_id_ny17` (DST-aware) — primitives che Wave 1+ riusa per ADX/MACD/Stoch/Keltner/VWAP/Pivot.
- Dev-dep `pandas-ta==0.4.71b0` installato in venv (numpy downgrade 2.4.4 → 2.2.6, transitivo) per parity test future; pandas_ta NON importato dal pacchetto runtime (verificato da `test_no_pandas_ta_at_runtime`).
- `data/configs/regime.yaml` schema D-15 (default + override EURUSD/GBPUSD/USDJPY) pronto per INDIC-14.
- Fixture session-scoped `eurusd_h1_500` esposta via `tests/conftest.py` (esteso, non sostituito); CSV snapshot 500 righe + script di build riproducibile.
- Universal future-leakage property test (`tests/test_indicators_purity.py`): 12 test (parametrizzati su 5 indici per ATR e SMA/EMA/RSI) — gate che Wave 1+ deve estendere per ogni nuovo rolling indicator.
- Suite intera 236/236 verde (220 baseline Phase 1 + 16 nuovi).

## Task Commits

Tutti i task committati atomicamente sul branch `feature/update-pythono-pure-strategy`:

1. **Task 1: Promuovi `indicators.py` a pacchetto `indicators/`** — `4dab433` (feat)
2. **Task 2: Dev-dep + regime.yaml + conftest fixture + 500-bar snapshot** — `8e57012` (chore)
3. **Task 3: Universal purity + trend + aggregate tests** — `10dada8` (test)

## Files Created/Modified

### Created — pacchetto runtime
- `indicators/__init__.py` — barrel re-export per backward-compat (D-03).
- `indicators/_helpers.py` — `_wilder_rsi`, `_wilder_smooth`, `_last_valid`, `_session_id_ny17`.
- `indicators/trend.py` — `sma`, `ema` (lift verbatim).
- `indicators/momentum.py` — `rsi`, `check_rsi_divergence` (lift verbatim, import `_wilder_rsi` da helpers).
- `indicators/volatility.py` — `atr` (lift verbatim).
- `indicators/structure.py` — `find_support_resistance`, `check_breakout_quality` (lift; import `avg_volume` da volume).
- `indicators/volume.py` — `avg_volume` (lift verbatim).
- `indicators/bars.py` — `calculate_risk_reward` (lift verbatim).
- `indicators/mtf.py` — `calculate_trend_strength` (lift verbatim, signature invariata per `strategy.py:11`).
- `indicators/hurst.py` — stub vuoto (Wave 1).
- `indicators/aggregate.py` — `compute_all` (lift verbatim, dict 4-key invariato).

### Created — config + dev-deps + fixture
- `data/configs/regime.yaml` — D-15 schema.
- `requirements-dev.txt` — `pandas-ta==0.4.71b0`.
- `tests/fixtures/build_eurusd_h1_last500.py` — script one-off per riprodurre il CSV.
- `tests/fixtures/eurusd_h1_last500.csv` — snapshot 500 righe (header + 500 dati).

### Created — test
- `tests/test_indicators_purity.py` — 12 test (no_pandas_ta + callsite + 5+5 parametrizzati leakage).
- `tests/test_indicators_trend.py` — sanity SMA constant + EMA seed = SMA.
- `tests/test_indicators_aggregate.py` — `compute_all` 4-key shape + valori float finiti su 500 bar.

### Modified
- `tests/conftest.py` — aggiunta `eurusd_h1_500` session-scoped fixture; preservati MetaTrader5 stub + `fixture_5bars_path` + `costs_yaml_path`.

### Deleted
- `indicators.py` — flat module sostituito dal pacchetto omonimo.

## Decisions Made

- **Re-export espliciti vs `__all__`-only:** `backtest/__init__.py` usa solo `__all__` declarative, ma le 4 callsite di `indicators` sono già attive in produzione. Scelti import espliciti `from indicators.<sub> import <name>` per non rompere consumer esistenti.
- **`build_eurusd_h1_last500.py` con auto-`sys.path`:** lo script funziona sia da pytest (modulo importato) sia da CLI standalone (`python tests/fixtures/build_...py`) inserendo la repo root in `sys.path` se assente. Necessario per garantire la riproducibilità documentata nel docstring.
- **`indicators/structure.py` importa `avg_volume` da `indicators/volume.py`:** preservato il comportamento di `check_breakout_quality` originale (che chiamava `avg_volume` interno al file) senza dipendere dal barrel `__init__.py` (evita import circolari).
- **Numpy downgrade transitivo accettato:** `pandas-ta==0.4.71b0` richiede numpy<2.3, forzando 2.4.4 → 2.2.6. Suite Phase 1 (220 test) resta verde dopo il downgrade — confermato che nessun consumer dipende da feature numpy 2.3+.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `build_eurusd_h1_last500.py` non eseguibile standalone**
- **Found during:** Task 2 (build CSV snapshot)
- **Issue:** Il file plan-as-written `from backtest.loader import load_bars` falliva con `ModuleNotFoundError: No module named 'backtest'` quando lanciato come script CLI (la repo root non era in `sys.path`).
- **Fix:** Aggiunte 4 righe (`import sys` + `sys.path.insert(0, str(REPO))`) prima dell'import di `backtest.loader`. La docstring menziona esplicitamente l'esecuzione standalone come pattern d'uso.
- **Files modified:** `tests/fixtures/build_eurusd_h1_last500.py`
- **Verification:** `python tests/fixtures/build_eurusd_h1_last500.py` produce `wrote ... (500 rows)`.
- **Committed in:** `8e57012` (Task 2 commit).

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking).
**Impact on plan:** Fix essenziale per riproducibilità CLI senza modifiche al PYTHONPATH globale. No scope creep.

## Issues Encountered

- pandas-ta install ha richiesto numpy downgrade da 2.4.4 → 2.2.6 (vincolo transitivo). Acceptable: suite intera resta verde, e numpy è dev-only (parity oracle). Da monitorare se altri consumer Phase 1 esistenti dovessero richiedere feature numpy 2.3+.

## User Setup Required

None — `pandas-ta==0.4.71b0` già installato in `.venv` durante l'esecuzione del plan; nessuna config esterna o credenziale richiesta.

## Next Phase Readiness

- Wave 0 pronto: tutto lo skeleton del pacchetto `indicators/` esiste e i submoduli sono pronti ad accogliere le nuove implementazioni Wave 1-3 (BB+squeeze, Keltner, ADX/MACD/Stoch, Hurst R/S, Donchian/Pivot/Fib, VWAP, NR4/7+Closing Score, MTF align, regime classifier).
- `_wilder_smooth` e `_session_id_ny17` disponibili come building block per ADX (Wave 1) e VWAP/Pivot (Wave 2).
- Universal purity test deve essere esteso ad ogni nuovo rolling indicator: aggiungere `@pytest.mark.parametrize("idx", [warmup+1, 100, 250, 400, 499])` per ciascuno.
- pandas-ta dev-dep installato → Wave 1 può lanciare `pta.adx`, `pta.macd`, `pta.bbands`, `pta.kc` come oracoli a tolerance `1e-6`.
- Backward-compat verificata: nessun blocker per Wave 1 da retro-compat.

## Self-Check

Verifica claims fatte sopra:

- `[ -f indicators/__init__.py ]` → FOUND
- `[ -f indicators/_helpers.py ]` → FOUND
- `[ ! -f indicators.py ]` → FOUND (flat eliminato)
- `[ -f data/configs/regime.yaml ]` → FOUND
- `[ -f tests/fixtures/eurusd_h1_last500.csv ]` → FOUND (500 righe + header)
- `[ -f requirements-dev.txt ]` → FOUND (pin `pandas-ta==0.4.71b0`)
- Commit `4dab433` (Task 1) → FOUND in `git log`
- Commit `8e57012` (Task 2) → FOUND in `git log`
- Commit `10dada8` (Task 3) → FOUND in `git log`
- Suite pytest 236/236 verde → VERIFIED

## Self-Check: PASSED

---
*Phase: 02-indicators-library*
*Completed: 2026-05-08*
