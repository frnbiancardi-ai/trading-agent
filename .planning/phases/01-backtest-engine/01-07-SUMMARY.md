---
phase: 01-backtest-engine
plan: 07
subsystem: backtest
tags: [backtest, metrics, statistics]
requires: [01-01]
provides: [backtest.metrics.compute_metrics, backtest.metrics.BacktestMetrics, backtest.metrics.BARS_PER_YEAR]
affects: []
tech-stack:
  added: []
  patterns: [pure-function, dataclass, running-peak-drawdown]
key-files:
  created: []
  modified:
    - backtest/metrics.py
    - tests/test_backtest_metrics.py
decisions:
  - Population std (not sample) for sharpe/sortino — matches RESEARCH §Pattern 6.
  - profit_factor encoded as float('inf') for all-winners; 0.0 only when ledger has no winners and no losers (empty-style fallback).
  - max_drawdown_pct expressed as percent (0–∞), running-peak subtraction on cumulative PnL.
  - risk_usd missing/zero falls back to 1.0 in r_multiples (per research code).
metrics:
  duration_min: 5
  completed: 2026-05-07
requirements: [BACK-06]
---

# Phase 01 Plan 07: Metrics Module Summary

One-liner: Pure `compute_metrics(trades, timeframe)` returning a `BacktestMetrics` dataclass; SC-5 fixture verified to 4 decimals.

## What Was Built

`backtest/metrics.py` exposes:
- `BARS_PER_YEAR = {"H1": 6048, "M30": 12096, "M15": 24192}` (24*252, 24*2*252, 24*4*252).
- `@dataclass BacktestMetrics` with 9 fields: `sharpe, sortino, max_drawdown_pct, hit_rate, expectancy_usd, profit_factor, avg_r, total_trades, total_pnl_usd`.
- `compute_metrics(trades, timeframe="H1") -> BacktestMetrics`:
  - Empty ledger short-circuits to `_empty_metrics()` (all zeros, no exception).
  - Sharpe/Sortino computed on R-multiples, annualized by `sqrt(BARS_PER_YEAR[tf])`.
  - Profit factor = `gross_win / gross_loss`, `inf` if `gross_loss == 0` and any win.
  - MaxDD% via running-peak subtraction on cumulative PnL.
  - All divisions guarded (std=0, gross_loss=0, risk_usd=0 → fallback 1.0).

## SC-5 Fixture Math (5-trade hand calculation)

```
trades pnl_usd  = [+20, -10, +20, +20, +5]
trades risk_usd = [ 10,  10,  10,  10, 10]
r_multiples     = [+2,  -1,  +2,  +2,  +0.5]

n            = 5
wins         = 4 (everything except -10)
hit_rate     = 4/5         = 0.8
total_pnl    = 20-10+20+20+5 = 55
expectancy   = 55/5        = 11.0
gross_win    = 20+20+20+5  = 65
gross_loss   = |-10|       = 10
profit_factor= 65/10       = 6.5
avg_r        = (2-1+2+2+0.5)/5 = 5.5/5 = 1.1
```

All four hit assert tolerances < 1e-4. ✓

## Tests (5 passed)

- `test_known_fixture` — SC-5 hand-verified fixture, 4-decimal precision.
- `test_empty_ledger` — `compute_metrics([], "H1")` returns all zeros, no `ZeroDivisionError`.
- `test_annualization` — `BARS_PER_YEAR` exact; M15 → larger sharpe than H1 (sqrt scaling).
- `test_max_drawdown` — pnl=[+10,+10,-25,+10] → equity=[10,20,-5,5]; peak=20; trough=-5; max_dd=125%.
- `test_profit_factor_all_winners` — all-positive PnL → `math.isinf(profit_factor)`.

```
5 passed in 0.07s
```

Full regression `pytest tests/` (excluding unrelated untracked `test_pdf_to_markdown_ocr.py` and pre-existing MT5 stub-namespace errors): 201 passed, 7 skipped.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-1-10 (DoS / div-by-zero) | All three division paths guarded: `_std()` returns 0 on n<2; `gross_loss==0` returns `inf`; `risk_usd or 1.0` fallback. Tests `test_empty_ledger` and `test_profit_factor_all_winners` exercise edges. |

## Commits

- `99d3802` — test(01-07): add failing tests for compute_metrics (BACK-06)
- `4c20e80` — feat(01-07): implement compute_metrics + BacktestMetrics (BACK-06)

## Self-Check: PASSED

- backtest/metrics.py: FOUND
- tests/test_backtest_metrics.py: FOUND
- Commit 99d3802: FOUND
- Commit 4c20e80: FOUND
