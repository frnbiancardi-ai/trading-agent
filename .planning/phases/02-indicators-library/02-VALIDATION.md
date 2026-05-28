---
phase: 2
slug: indicators-library
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 2 — Validation Strategy

> Per-phase validation contract. Source: `02-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already in `requirements.txt`, Phase 1) |
| **Config file** | `pytest.ini` (`pythonpath = .`) — existing |
| **Quick run command** | `pytest tests/test_indicators_<submodule>.py -x` |
| **Full suite command** | `pytest tests/test_indicators_*.py` |
| **Phase gate** | `pytest` (entire suite must remain green) |
| **Estimated runtime** | <30s for full indicator suite |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_indicators_<submodule>.py -x` (target <5s)
- **After every plan wave:** `pytest tests/test_indicators_*.py` (target <30s)
- **Before `/gsd-verify-work`:** Full `pytest` suite green
- **Max feedback latency:** 30 seconds

---

## Per-Requirement Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| INDIC-01 | Bollinger 20/2 + squeeze | unit + parity (pandas-ta) | `pytest tests/test_indicators_volatility.py::test_bbands_parity -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-02 | ADX/DMI 14 (Wilder/RMA) | unit + parity | `pytest tests/test_indicators_momentum.py::test_adx_parity -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-03 | MACD 12/26/9 | unit + parity | `pytest tests/test_indicators_momentum.py::test_macd_parity -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-04 | Stochastic 14/3/3 | unit + parity | `pytest tests/test_indicators_momentum.py::test_stoch_parity -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-05 | Donchian 20 | unit (manual fixture) | `pytest tests/test_indicators_structure.py::test_donchian -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-06 | Keltner | unit + parity | `pytest tests/test_indicators_volatility.py::test_keltner_parity -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-07 | VWAP intraday + anchored (NY-17 reset) | unit (manual fixture) | `pytest tests/test_indicators_volume.py::test_vwap_intraday_session_reset -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-08 | Fibonacci on swing leg | unit (manual fixture) | `pytest tests/test_indicators_structure.py::test_fib_levels -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-09 | Pivots classic + Camarilla (daily/session/weekly) | unit (manual fixture) | `pytest tests/test_indicators_structure.py::test_pivot_camarilla_formula -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-10 | NR4/NR7 + Boomer | unit (manual fixture) | `pytest tests/test_indicators_bars.py::test_nr_boomer -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-11 | Closing Score (Defendi) | unit (hand-calc) | `pytest tests/test_indicators_bars.py::test_closing_score -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-12 | Hurst rolling (R/S) | unit + parity | `pytest tests/test_indicators_hurst.py::test_hurst_rs_parity -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-13 | MTF alignment (H4/H1/M15 EMA50-slope) | unit (synthetic streams) | `pytest tests/test_indicators_mtf.py::test_align_full_coherence -x` | ❌ Wave 0 | ⬜ pending |
| INDIC-14 | Volatility regime (ATR-percentile) | unit + parity + leakage | `pytest tests/test_indicators_volatility.py::test_regime_no_future_leakage -x` | ❌ Wave 0 | ⬜ pending |
| — | No future leakage (universal property test) | unit | `pytest tests/test_indicators_purity.py -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — session-scoped fixture `eurusd_h1_500` loading `tests/fixtures/eurusd_h1_last500.csv`
- [ ] `tests/fixtures/eurusd_h1_last500.csv` — generated once via one-off script using Phase 1 loader (last 500 bars EURUSD H1, GMT-6→UTC)
- [ ] `tests/test_indicators_<submodule>.py` × 9 — all new (momentum, volatility, structure, volume, bars, mtf, hurst, trend, aggregate)
- [ ] `tests/test_indicators_purity.py` — universal "no future leakage" property test
- [ ] `requirements-dev.txt` — new file, pin `pandas-ta==0.4.71b0`
- [ ] `data/configs/regime.yaml` — INDIC-14 schema (D-15)
- [ ] Framework install: `pip install -r requirements-dev.txt`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TradingView spot-check Bollinger / ADX | INDIC-01, INDIC-02 | Belt-and-suspenders sanity vs external chart | Open EURUSD H1 on TradingView, pick a known bar timestamp present in `tests/fixtures/eurusd_h1_last500.csv`, compare BB upper/lower and ADX-14 to ±1e-3 tolerance |

---

## Notes

- pandas-ta is **dev-dep only** (`requirements-dev.txt`). Never imported at runtime — parity tests use it; production code never does. CI/test must `pip install -r requirements-dev.txt` separately.
- Property test (`test_indicators_purity.py`) asserts `f(bars[:i+1])[i] == f(bars)[i]` at 5 spot indices for every rolling indicator — catches future-leakage regressions universally.
- A1..A5 assumptions in RESEARCH.md drive tolerance choices (Hurst may need `1e-3` if pandas-ta uses DFA; ADX/Wilder parity test starts at `index = 2*period` to skip seed transient).
