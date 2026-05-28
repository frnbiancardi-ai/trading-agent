---
phase: 02-indicators-library
verified: 2026-05-08T17:30:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 2: Indicators Library — Verification Report

**Phase Goal:** Add the missing indicators required by the forex-trader-pro playbook (Bollinger, ADX, MACD, Stochastic, Donchian, Keltner, VWAP, Fibonacci, Pivot, NR4/7, Closing Score, Hurst, multi-TF alignment, volatility regime classifier) as pure functions consumable by both live and backtest paths.

**Verified:** 2026-05-08
**Status:** passed
**Re-verification:** No — initial verification
**HEAD commit:** `4ba4c6c`
**Suite:** 374 passed, 1 skipped (Mottl `hurst` parity — opt-dep), 1 warning (pandas4 dep)

---

## Goal Achievement

### Success Criteria (ROADMAP.md Phase 2)

| #   | Truth (SC)                                                                                                                  | Status     | Evidence                                                                                                                                                                                                                                                                                                                                          |
| --- | --------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Each indicator has a unit test against a known reference value (TradingView or manual calc).                                | ✓ VERIFIED | Reference-value tests presenti per ogni INDIC: BB+Keltner parity vs `pandas_ta.bbands/kc` 1e-6 (`tests/test_indicators_volatility.py:62,85`); ADX/MACD/Stoch parity 1e-6 (`tests/test_indicators_momentum.py:81,121,155`); Donchian/Pivot Camarilla/Fib hand-calc (`tests/test_indicators_structure.py:31,100,191`); VWAP session-reset NY-17 winter+summer (`tests/test_indicators_volume.py:36,62`); NR4/NR7/Inside/Boomer hand-calc 4-bar+5-bar+8-bar (`tests/test_indicators_bars.py:40-201`); Closing Score 3 canonical hand-calc (`tests/test_indicators_bars.py:230`); Hurst persistent/anti-persistent/white-noise + Mottl parity opt-skip (`tests/test_indicators_hurst.py:24,37,59,101`); MTF align 6 hand-crafted scenarios (`tests/test_indicators_mtf.py:45-112`); Volatility regime fixture EURUSD H1 500-bar distribution check (`tests/test_indicators_volatility.py:146`). 374 test verdi totali. |
| 2   | All indicators are pure: no side effects, deterministic, no future leakage (rolling uses past data only, expanding+shift1). | ✓ VERIFIED | Universal leakage gate `tests/test_indicators_purity.py` parametrizzato 5 idx per OGNI indicatore rolling — 14 funzioni × 5 spot indices = 70 leakage assertions: ATR, SMA/EMA/RSI, Bollinger, Keltner, ADX, MACD, Stochastic, Hurst, Donchian, Pivots, VWAP intraday, Narrow Range (nr4/nr7/inside/boomer), Closing Score, Volatility regime, MTF align (sintetico). Tutti PASS. Garanzia: `f(prefix)[i] == f(full)[i]` ⇒ no future leakage by construction. Inoltre `test_volatility_regime_no_full_series_rank_signature` guard esplicito contro `pandas.rank(pct=True)` globale (Pitfall 4). `grep -rE "^(import|from) pandas_ta" indicators/` → 0 match (purity runtime, D-07).                                                                                                                |
| 3   | Multi-TF alignment helper accepts (H4, H1, M15) bar streams and returns a coherence score in [0, 1].                        | ✓ VERIFIED | `indicators.mtf.align(streams, ema_period=50, slope_lookback=3)` (mtf.py:60-138) richiede dict con chiavi obbligatorie 'H4', 'H1', 'M15' (raise ValueError altrimenti — `test_align_missing_key_raises`). Score ∈ {None, 0.0, 0.33, 0.67, 1.0} verificato da 6 test: `test_align_full_coherence_uptrend` (1.0), `test_align_full_coherence_downtrend` (1.0), `test_align_partial_coherence` (0.67), `test_align_zero_score_disagreement` (0.0), `test_align_warmup_returns_none` (None warmup), `test_align_dead_zone_yields_zero_dir` (0.0). Esposto in `indicators/__init__.py:49` + `__all__`.                                                                                                                                                                |
| 4   | Volatility-regime classifier returns one of {compressed, normal, expanded} based on ATR percentile vs 200-bar window — verified on known regime samples. | ✓ VERIFIED | `indicators.volatility.volatility_regime(bars, cfg)` (volatility.py:272-319) implementa rolling-rank percentile su finestra trailing `window=200` di ATR(14). State ∈ {'compressed','normal','expanded',None}. Spot-check fixture EURUSD H1 500-bar (cfg EURUSD 25/75): 287 bar post-warmup, distribuzione **61 compressed (21%) / 155 normal (54%) / 71 expanded (25%)** — tutti e 3 gli stati osservati. `test_volatility_regime_states_present_after_warmup` PASS. `test_volatility_regime_warmup_none` valida warmup i<199 → None. Pitfall 4 (rolling vs global rank): `test_volatility_regime_no_full_series_rank_signature` + 5-idx leakage gate. YAML config `data/configs/regime.yaml` con per-symbol override (EURUSD 25/75, GBPUSD/USDJPY/default 30/70) caricato via `load_regime_config` (mirror Phase 1 `backtest/costs.py:load_cost_model`).                                                                          |

**Score:** 4/4 ROADMAP success criteria verificati.

---

### Required Artifacts (Phase 2 deliverables)

| Artifact                            | Expected                                                          | Status     | Details                                                                                                                                                                                          |
| ----------------------------------- | ----------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `indicators/__init__.py`            | Barrel re-export di 14 INDIC + 4 callsite legacy                  | ✓ VERIFIED | 97 righe, esporta tutti i simboli previsti (29 simboli verificati da `test_all_14_indic_requirement_symbols_exposed`). Re-export per claude_agent.py:12, mcp_server.py:28, scanner.py:10, strategy.py:11. |
| `indicators/trend.py`               | sma, ema (Wave 0 lift-and-shift)                                  | ✓ VERIFIED | 33 righe.                                                                                                                                                                                        |
| `indicators/momentum.py`            | rsi+divergence, adx, macd, stochastic                             | ✓ VERIFIED | 396 righe. ADX/MACD/Stoch parity 1e-6 vs pandas_ta.                                                                                                                                              |
| `indicators/volatility.py`          | atr, bollinger_bands+squeeze, keltner, volatility_regime, load_regime_config | ✓ VERIFIED | 319 righe. INDIC-01 + INDIC-06 + INDIC-14.                                                                                                                                                       |
| `indicators/structure.py`           | find_S/R, breakout_quality, donchian, fibonacci_retracements, pivots (classic+Camarilla NY-17) | ✓ VERIFIED | 370 righe. INDIC-05 + INDIC-08 + INDIC-09. Test DST winter/summer pivots NY-17.                                                                                                                  |
| `indicators/volume.py`              | avg_volume, vwap_intraday (NY-17 reset), vwap_anchored            | ✓ VERIFIED | 120 righe. INDIC-07. Test session reset winter+summer.                                                                                                                                            |
| `indicators/bars.py`                | calculate_risk_reward, narrow_range (nr4/nr7/inside/boomer A2), closing_score | ✓ VERIFIED | 119 righe. INDIC-10 + INDIC-11. Boomer A2 verbatim CONTEXT.md.                                                                                                                                   |
| `indicators/hurst.py`               | hurst_rs (R/S log-log regression rolling)                         | ✓ VERIFIED | 131 righe. INDIC-12. Persistent/anti-persistent/white-noise sanity tests.                                                                                                                         |
| `indicators/mtf.py`                 | align(H4/H1/M15) → score ∈ {0, 0.33, 0.67, 1.0}                   | ✓ VERIFIED | 177 righe. INDIC-13.                                                                                                                                                                              |
| `indicators/aggregate.py`           | compute_all (4-key legacy, hard-lock) + compute_all_extended (37-key)        | ✓ VERIFIED | 142 righe. compute_all bit-for-bit immutato (D-03 hard-lock); compute_all_extended fornisce snapshot 14-indicator per Phase 4 strategy + Phase 1 backtest ledger ctx.                            |
| `indicators/_helpers.py`            | _last_valid, _wilder_rsi (privati, retro-compat test)             | ✓ VERIFIED | 64 righe.                                                                                                                                                                                        |
| `data/configs/regime.yaml`          | Schema D-15: default + symbols (EURUSD/GBPUSD/USDJPY)             | ✓ VERIFIED | EURUSD override 25/75, GBPUSD/USDJPY/default 30/70, window=200.                                                                                                                                  |
| `tests/test_indicators_*.py` (9 file) | Coverage per ogni INDIC + universal leakage gate                | ✓ VERIFIED | 9 file test (purity, trend, momentum, volatility, structure, volume, bars, hurst, mtf, aggregate). 374 passed, 1 skipped.                                                                       |

---

### Key Link Verification (Wiring)

| From                | To                              | Via                                                                | Status   | Details                                                                                                                                                                                                                                                                |
| ------------------- | ------------------------------- | ------------------------------------------------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `claude_agent.py:12` | `indicators.compute_all`        | `from indicators import compute_all`                               | ✓ WIRED  | `test_legacy_callsite_imports_unchanged` PASS. compute_all 4-key shape immutato (D-03 hard-lock).                                                                                                                                                                       |
| `mcp_server.py:28`   | `indicators.compute_all`        | `from indicators import compute_all`                               | ✓ WIRED  | Stesso test sopra. Hard-lock backward-compat.                                                                                                                                                                                                                          |
| `scanner.py:10`      | `indicators.{sma,ema,rsi,atr}` | `from indicators import sma, ema, rsi, atr`                       | ✓ WIRED  | `test_backward_compat_callsite_imports` (purity.py:31) PASS.                                                                                                                                                                                                          |
| `strategy.py:11`     | indicators legacy bundle        | `from indicators import sma, ema, rsi, atr, avg_volume, calculate_trend_strength, find_support_resistance, check_breakout_quality, calculate_risk_reward` | ✓ WIRED  | `test_backward_compat_callsite_imports` (purity.py:33-43) PASS.                                                                                                                                                                                                       |
| `aggregate.py`       | tutti i moduli indicator        | import diretto da `indicators.{trend,momentum,volatility,...}`     | ✓ WIRED  | compute_all_extended chiama 13 indicator function in chain (test_compute_all_extended_contains_all_indicators verifica le 33 chiavi estese).                                                                                                                            |
| `volatility_regime` → `data/configs/regime.yaml` | YAML loader pattern | `load_regime_config(symbol, yaml_path)` con `yaml.safe_load` | ✓ WIRED  | `test_load_regime_config_eurusd_override` (25/75) + `test_load_regime_config_default_fallback` (30/70) PASS.                                                                                                                                                          |
| `compute_all_extended` → Phase 1 backtest ledger ctx | snapshot 14-indicator dict | 37-key shape (4 legacy + 33 extended) | ✓ WIRED (preflight) | Phase 1 backtest engine già completo (vedi context). compute_all_extended fornisce shape consumibile dal ledger; integrazione effettiva avverrà in Phase 4 strategy refactor (next phase). Documentato in 02-09-SUMMARY.md "Next Phase Readiness". |

---

### Data-Flow Trace (Level 4)

| Artifact                  | Data Variable                | Source                                          | Produces Real Data | Status     |
| ------------------------- | ---------------------------- | ----------------------------------------------- | ------------------ | ---------- |
| `compute_all`             | `{sma_20, ema_50, rsi_14, atr_14}` | sma/ema/rsi/atr su list[dict] OHLC bars        | ✓ Yes (4 finite floats) | ✓ FLOWING  |
| `compute_all_extended`    | 37-key dict                  | 13 indicator functions chained                  | ✓ Yes (dataset EURUSD H1 500-bar produce regime_state='normal', regime_atr_pct=0.585, bb_squeeze=False, hurst=1.062, tutti coerenti — vedi 02-09-SUMMARY self-check) | ✓ FLOWING  |
| `volatility_regime`       | `RegimeResult(state, atr_percentile)` | atr(highs,lows,closes,14) + rolling rank window=200 | ✓ Yes (61/155/71 distribuzione 3 stati su fixture 500-bar) | ✓ FLOWING  |
| `align`                   | `MTFAlignmentResult(score, h4/h1/m15 dirs)` | EMA50 slope-sign agreement via timestamp slicing | ✓ Yes (test sintetici uptrend score=1.0, disagreement score=0.0, partial 0.67) | ✓ FLOWING  |
| `narrow_range`            | `NRResult(nr4, nr7, inside, boomer)` | range comparison + inside-bar window           | ✓ Yes (hand-calc verificato 4-bar nr4[3]=True boomer[3]=True)                  | ✓ FLOWING  |
| `pivots(anchor='daily')` | `PivotResult(p, r1..r3, s1..s3, camarilla h1..h4/l1..l4)` | NY-17 session reset H/L/C precedente | ✓ Yes (hand-calc Camarilla formula, DST winter+summer)              | ✓ FLOWING  |

Tutti i 14 indicatori producono dati reali su fixture (no static returns, no hollow props). compute_all_extended è la single source of truth per Phase 4 strategy + Phase 1 backtest.

---

### Behavioral Spot-Checks

| Behavior                                                | Command                                                                                                                       | Result                                | Status |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------ |
| Suite intera (374 indicator + adjacent test)            | `.venv/Scripts/python.exe -m pytest -q`                                                                                       | `374 passed, 1 skipped in 19.96s`     | ✓ PASS |
| Universal future-leakage gate (14 indicator × 5 idx)    | `pytest tests/test_indicators_purity.py -q`                                                                                   | tutti PASS (incluso volatility_regime, hurst, donchian, pivots, vwap_intraday, narrow_range, closing_score, MTF align sintetico) | ✓ PASS |
| Phase final symbol-completeness gate                    | `pytest tests/test_indicators_aggregate.py::test_all_14_indic_requirement_symbols_exposed -q`                                  | PASS (29 simboli tutti presenti)      | ✓ PASS |
| Backward-compat callsite hard-lock                      | `pytest tests/test_indicators_aggregate.py::test_compute_all_unchanged_legacy_callsite tests/test_indicators_purity.py::test_backward_compat_callsite_imports -q` | PASS                                  | ✓ PASS |
| pandas_ta NOT importato a runtime (D-07)                | `pytest tests/test_indicators_purity.py::test_no_pandas_ta_at_runtime -q`                                                     | PASS                                  | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                                                              | Status      | Evidence                                                                                                                                                              |
| ----------- | ----------- | ---------------------------------------------------------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| INDIC-01    | 02-02       | Bollinger Bands (20, 2σ) + squeeze detector                                              | ✓ SATISFIED | `bollinger_bands` in volatility.py + `BollingerResult(upper,middle,lower,bbw,squeeze)`. Parity 1e-6 vs pandas_ta.                                                     |
| INDIC-02    | 02-03       | ADX/DMI (14)                                                                             | ✓ SATISFIED | `adx` in momentum.py + `ADXResult`. Parity 1e-6 vs pandas_ta.                                                                                                          |
| INDIC-03    | 02-03       | MACD (12/26/9)                                                                           | ✓ SATISFIED | `macd` in momentum.py + `MACDResult`. Parity 1e-6 vs pandas_ta.                                                                                                        |
| INDIC-04    | 02-03       | Stochastic (14/3/3)                                                                      | ✓ SATISFIED | `stochastic` in momentum.py + `StochasticResult`. Parity 1e-6 vs pandas_ta.                                                                                            |
| INDIC-05    | 02-05       | Donchian Channel (20)                                                                    | ✓ SATISFIED | `donchian` in structure.py + `DonchianResult`. Hand-calc 5-bar test.                                                                                                  |
| INDIC-06    | 02-02       | Keltner (EMA20 ± 2×ATR)                                                                  | ✓ SATISFIED | `keltner` in volatility.py + `KeltnerResult`. Parity 1e-6 vs pandas_ta (skip-marked se pandas_ta opt-out).                                                              |
| INDIC-07    | 02-06       | VWAP intraday + anchored                                                                 | ✓ SATISFIED | `vwap_intraday` (NY-17 reset) + `vwap_anchored` in volume.py. Test winter/summer DST.                                                                                  |
| INDIC-08    | 02-05       | Fibonacci retracements (38.2/50/61.8) su swing legs                                      | ✓ SATISFIED | `fibonacci_retracements` in structure.py + `FibonacciResult(levels, direction)`. Hand-calc up-leg.                                                                    |
| INDIC-09    | 02-05       | Pivot daily/session/weekly (classic + Camarilla)                                         | ✓ SATISFIED | `pivots(anchor='daily')` in structure.py + `PivotResult(p, r1..r3, s1..s3, camarilla h1..h4/l1..l4)`. Camarilla hand-calc + DST boundary winter/summer.                  |
| INDIC-10    | 02-07       | NR4/NR7 + Boomer (inside-narrow sequence)                                                | ✓ SATISFIED | `narrow_range` in bars.py + `NRResult(nr4,nr7,inside,boomer)`. Boomer A2 verbatim CONTEXT.md (vedi WARNING sotto re: skill discrepancy).                                |
| INDIC-11    | 02-07       | Closing Score (Defendi 0-100)                                                            | ✓ SATISFIED | `closing_score` in bars.py + `ClosingScoreResult`. 3 hand-calc canonical (close=high → 100, close=low → 0, mid → 50).                                                  |
| INDIC-12    | 02-04       | Hurst exponent rolling                                                                   | ✓ SATISFIED | `hurst_rs` in hurst.py + `HurstResult`. Persistent (linear ramp) ≈ 1.0, anti-persistent < 0.5, white-noise ≈ 0.5. Mottl parity opt-skip.                              |
| INDIC-13    | 02-08       | Multi-TF alignment (H4+H1+M15 trend coherence)                                           | ✓ SATISFIED | `align({H4,H1,M15})` in mtf.py + `MTFAlignmentResult(score, h4_dir, h1_dir, m15_dir)`. Score ∈ {0, 0.33, 0.67, 1.0, None}. 6 hand-crafted scenarios.                  |
| INDIC-14    | 02-09       | Volatility regime (compressed/normal/expanded ATR-percentile vs 200-bar)                 | ✓ SATISFIED | `volatility_regime(bars, cfg)` in volatility.py + `RegimeResult(state, atr_percentile, window)` + `load_regime_config(symbol, yaml)`. Distribuzione 3 stati su fixture. |

**Coverage:** 14/14 requirement INDIC-01..14 SATISFIED. Nessun requirement orfano (REQUIREMENTS.md mappa esattamente 14 INDIC a Phase 2, tutti coperti dalle 9 plan).

---

### Anti-Patterns Found

| File                                | Line | Pattern                                                                                            | Severity | Impact                                                                                                                                                                                                                                                                                            |
| ----------------------------------- | ---- | -------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `indicators/bars.py` (Boomer rule) | —    | Boomer A2 (CONTEXT verbatim) ≠ skill `forex-trader-pro/references/price_action.md:43` (più stretta) | ℹ️ Info  | Documentato esplicitamente in 02-07-SUMMARY.md sezione "Deviations / Skill check". Rule implementata: `inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])`. Rule skill: `(inside AND nr4) AND (inside AND nr4)` su entrambi bar (no NR7). **Da riconciliare in Phase 4 (Strategy Refactor)**. Non blocker per Phase 2 — il plan istruisce esplicitamente "uses CONTEXT.md specifics verbatim, executor flags via task summary". |
| Suite                               | —    | 1 test skipped: `test_hurst_parity_with_mottl`                                                     | ℹ️ Info  | Mottl `hurst` lib è dev-dep opzionale (parity check di sanity, non gate funzionale). Hurst stesso è coperto da 6 hand-calc/sanity test (persistent/anti-persistent/white-noise/warmup/window-too-small/constant-series).                                                                          |
| Suite                               | —    | 1 warning `Pandas4Warning` da pandas_ta                                                            | ℹ️ Info  | Dev-dep warning preesistente da Wave 0; non legato all'implementazione phase 2. pandas_ta NON è importato a runtime (D-07 verificato).                                                                                                                                                            |

Nessun blocker, nessun warning bloccante. 0 TODO/FIXME/PLACEHOLDER nei file `indicators/`. 0 stub: tutti i file hanno implementazioni complete con docstring italiane + reference a Pitfall/Decision lock.

---

### Human Verification Required

Nessuna. Tutti i 4 success criteria sono verificabili programmaticamente via test suite + grep + reference-value parity. La phase produce una libreria di funzioni pure (no UI, no real-time behavior, no external service), interamente testabile in CI.

---

## Phase Goal Assessment

**Goal achieved.** I 14 indicatori INDIC-01..14 sono implementati come funzioni pure in 9 sub-moduli del pacchetto `indicators/`, esposti via barrel `__init__.py`, consumabili sia dalle 4 callsite legacy live (claude_agent, mcp_server, scanner, strategy) — backward-compat hard-lock verificato bit-for-bit — sia dal Phase 1 backtest engine via `compute_all_extended` (snapshot 37-key). I 4 success criteria della ROADMAP sono verificati:

1. **Reference-value tests:** parity 1e-6 vs `pandas_ta` per BB/Keltner/ADX/MACD/Stoch + hand-calc per Donchian/Fib/Pivots(Camarilla)/VWAP(NY-17 DST)/NR/CS/Hurst/MTF/Regime. 374 test verdi.
2. **Purity + no future leakage:** universal leakage gate parametrizzato 5 spot indices per ogni indicatore rolling (14 funzioni testate). `pandas_ta` NON importato a runtime. Volatility regime usa rolling rank (mai `pandas.rank(pct=True)` globale — Pitfall 4 verificato).
3. **MTF alignment H4/H1/M15:** `align(streams)` accetta dict con chiavi obbligatorie, restituisce score ∈ {0, 0.33, 0.67, 1.0, None}.
4. **Volatility regime classifier:** `volatility_regime(bars, cfg)` ritorna `{compressed, normal, expanded}` via ATR percentile rolling vs 200-bar; distribuzione 3 stati osservata su fixture EURUSD H1 500-bar (61/155/71).

### Known follow-up (NOT a Phase 2 blocker)

- **Boomer rule reconciliation:** Phase 4 (Strategy Refactor) deve decidere se mantenere A2 verbatim CONTEXT.md (più larga, ammette NR7) oppure adottare la rule più stretta del skill `forex-trader-pro` (solo NR4 su entrambi bar). Decisione documentata in 02-07-SUMMARY.md + 02-CONTEXT.md. Non incide sull'achievement del Phase 2 goal (l'indicatore è implementato, testato, esposto — la scelta semantica fra le due varianti è una decisione di strategia, non di indicatore).

### Suite output

```
374 passed, 1 skipped, 1 warning in 19.96s
```

(1 skipped = `test_hurst_parity_with_mottl` opt-dep; 1 warning = `Pandas4Warning` da `pandas_ta` dev-dep)

---

## Recommendation

**PROCEED** alla phase successiva. Phase 2 goal achieved, 14/14 INDIC complete, 4/4 ROADMAP success criteria verificati, 374 test verdi, 0 blocker, 0 warning bloccanti. Boomer A2 vs skill discrepancy è un known-item per Phase 4 strategy refactor — già documentato + tracciato nel SUMMARY plan 02-07.

Phase 4 (Strategy Refactor) e Phase 1 backtest engine integration sono entrambi sbloccati: tutti gli indicatori sono pure functions consumabili dal medesimo path live + backtest (no fork — `compute_all_extended` è la single snapshot source).

---

_Verified: 2026-05-08T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
_HEAD commit: 4ba4c6c_
