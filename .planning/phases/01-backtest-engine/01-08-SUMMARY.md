---
phase: 01-backtest-engine
plan: 08
subsystem: backtest
tags: [backtest, smoke, cleanup, performance, sc-6, d-03, d-04]
requires: [01-05, 01-07]
provides:
  - "SC-6 verified: 12-month EUR/USD H1 backtest runs in 6.78s (8.85x margin under 60s budget)"
  - "tests/test_backtest_engine.py::test_smoke_12month_under_60s — real smoke test (replaces plan-05 skip)"
  - "tests/test_legacy_cleanup.py — regression guards for D-03 / D-04 / output-JSON gitignore"
  - "engine result dict: bars_processed field (additive)"
  - ".planning/archive/legacy-backtest/ — provenance-marked archive of pre-Phase-1 RSI/SMA grid output"
affects:
  - backtest/engine.py (additive bars_processed key)
  - tests/test_backtest_engine.py
  - tests/test_legacy_cleanup.py
  - .gitignore
tech-stack:
  added: []
  patterns:
    - "Time-budget assertion via time.perf_counter() (no pytest-timeout dependency)"
    - "Conditional skipif on data-file presence for CI portability"
key-files:
  created:
    - .planning/archive/legacy-backtest/README.md
    - .planning/archive/legacy-backtest/grid_search.json
    - .planning/archive/legacy-backtest/advanced_search.json
    - .planning/archive/legacy-backtest/walkforward_full.json
    - .planning/archive/legacy-backtest/verify_final.py
  modified:
    - backtest/engine.py
    - tests/test_backtest_engine.py
    - tests/test_legacy_cleanup.py
    - .gitignore
  deleted:
    - backtest_suite.py
    - ml_feedback/grid_search.json
    - ml_feedback/advanced_search.json
    - ml_feedback/walkforward_full.json
    - ml_feedback/verify_final.py
    - ml_feedback/ (directory)
decisions:
  - "All four legacy targets (backtest_suite.py + 4× ml_feedback contents) were untracked at plan start; used filesystem mv/rm rather than git mv/git rm. The archive itself is the first time these files enter version control."
  - "bars_processed exposed on engine result rather than relying on len(equity_curve) — equity_curve grows only on closed trades, so a no-trade run would falsely report 0 bars. bars_processed = len(self.bars) is unambiguous."
  - "gitignore entry placed near tail with explanatory comment referencing D-03 / plan 01-08 for traceability."
metrics:
  duration: ~15min
  completed: 2026-05-07
  smoke_elapsed_s: 6.78
  smoke_margin_x: 8.85
  bars_processed_12mo: ~6240 (12-month EURUSD H1 slice)
---

# Phase 1 Plan 08: Smoke Test + Legacy Cleanup Summary

Wave 3 closure for Phase 1. Three deliverables:

1. **SC-6 smoke test** — full 12-month EUR/USD H1 backtest verified at **6.78s** end-to-end (8.85× margin under the 60s budget). Replaces the `pytest.mark.skip` placeholder left by plan 05.
2. **D-03 executed** — `backtest_suite.py` removed (the file was untracked at plan start, so a plain `rm` was sufficient; D-03's intent — "no path forward depends on it" — is enforced by `tests/test_legacy_cleanup.py::test_backtest_suite_deleted`).
3. **D-04 executed** — `ml_feedback/{grid_search,advanced_search,walkforward_full}.json` + `verify_final.py` archived under `.planning/archive/legacy-backtest/` with a provenance `README.md`. The `ml_feedback/` directory itself is gone.

Output JSONs (`backtest_results.json`, `backtest_trades.json`, observed untracked in opening `git status`) added to `.gitignore` and confirmed gone from `git status --short` after the change.

## Smoke test result

```
tests/test_backtest_engine.py::test_smoke_12month_under_60s PASSED  [100%]
============================== 1 passed in 6.78s ==============================
```

| Metric                | Value                          |
| --------------------- | ------------------------------ |
| Window                | 2024-01-01 → 2025-01-01 UTC    |
| Symbol / TF           | EURUSD / H1                    |
| Bars processed        | ~6240 (12 months of H1, weekends excluded) |
| Wall-clock elapsed    | 6.78 s                         |
| SC-6 budget           | 60 s                           |
| Margin                | 8.85×                          |
| Trades produced       | 0 (production Config gates active — not synthetic-fixture loose gates) |
| Result dict keys      | `run_id`, `trades`, `equity_curve`, `bars_processed` |

Margin is well above 2× — no machine-spec note required (per VALIDATION.md Manual-Only row guidance reproduced in the test docstring).

The 0-trade outcome on real EURUSD H1 is consistent with production gates (default `MIN_TREND_STRENGTH=0.65`, full session/news/weekday filters disabled inside the engine but strategy-level confidence/RSI/ATR thresholds still active). The smoke test asserts the engine **completes** within budget after consuming **>=1000 bars**, not that any specific trade fires — that's the contract.

## Engine change (additive)

`backtest/engine.py:242-246` — added `bars_processed: len(self.bars)` to the result dict. Pure additive; existing tests (5-bar fixture, 260-bar uptrend, decision context, equity curve, run_id determinism) all continue to pass unchanged.

## Cleanup details

### D-03: `backtest_suite.py` deletion

```
$ ls backtest_suite.py
ls: cannot access 'backtest_suite.py': No such file or directory
```

The file was untracked (per opening `git status`) — an artifact of the prior project structure that had never been committed. `rm backtest_suite.py` removed it from the working tree. `tests/test_legacy_cleanup.py::test_backtest_suite_deleted` is the regression guard.

### D-04: `ml_feedback/` archive

Files moved to `.planning/archive/legacy-backtest/`:

| File                       | Bytes (approx) | Provenance |
| -------------------------- | -------------- | ---------- |
| `grid_search.json`         | tracked in archive | RSI×SMA hyperparameter grid output |
| `advanced_search.json`     | tracked in archive | extended grid + Monte-Carlo |
| `walkforward_full.json`    | tracked in archive | pre-Phase-1 walk-forward (superseded) |
| `verify_final.py`          | tracked in archive | verification script (no longer runnable) |
| `README.md` (new)          | created          | provenance + supersession note |

The `ml_feedback/` directory was removed (only `__pycache__` remained after the moves; that was deleted too).

### `.gitignore` additions

```diff
+
+# Output artifacts from the deleted backtest_suite.py (D-03, plan 01-08)
+backtest_results.json
+backtest_trades.json
```

Confirmed effective: `git status --short` no longer lists `backtest_results.json` or `backtest_trades.json` (which were untracked at plan start).

## Tests

| File                              | Count | Status |
| --------------------------------- | ----- | ------ |
| `tests/test_backtest_engine.py`   | 7     | all passing (was 6 + 1 skip; smoke is now real) |
| `tests/test_legacy_cleanup.py`    | 3     | all passing (was 2 module-skip stubs) |

Plan-scope verification:

```
$ pytest tests/test_backtest_engine.py tests/test_legacy_cleanup.py -x --tb=short
tests/test_backtest_engine.py .......     [ 70%]
tests/test_legacy_cleanup.py ...          [100%]
============================== 10 passed in 6.86s ==============================
```

Full collectable suite:

```
$ pytest --tb=short --ignore=tests/test_daily_orchestrator.py \
    --ignore=tests/test_mcp_tools_v2.py --ignore=tests/test_news_aggregator.py \
    --ignore=tests/test_pdf_to_markdown_ocr.py --ignore=tests/test_phase16.py \
    --ignore=tests/test_scheduler.py
======================= 125 passed, 4 skipped in 8.86s ========================
```

The 6 ignored modules fail at *collection* due to a pre-existing missing dependency (`apscheduler`, etc. — unrelated to this plan, observed in the same state in plan 01-07's session). Per the executor scope-boundary rule, these are logged-not-fixed: they are out-of-scope for plan 01-08.

## Phase 1 Success-Criteria Checklist

| # | Criterion | Status | Evidence |
| - | --------- | ------ | -------- |
| 1 | Italian-CSV loader correctness (DD/MM/YYYY, semicolon, GMT-6 → UTC) | ✓ | `tests/test_backtest_loader.py` (4/4) |
| 2 | Event-driven engine: bar-by-bar replay through real strategy code path | ✓ | `tests/test_backtest_engine.py::test_engine_with_synthetic_signals` |
| 3 | Cost realism: spread + slippage + commission deduct correct USD | ✓ | plan 01-03 `tests/test_backtest_costs.py` |
| 4 | Trade ledger persists with decision context | ✓ | `test_decision_context`, `test_engine_with_synthetic_signals` |
| 5 | Walk-forward harness with per-slice metrics (Sharpe / Sortino / MaxDD / hit rate / expectancy / profit factor / avg-R) | ✓ | `tests/test_backtest_walk_forward.py` (7/7) + `tests/test_backtest_metrics.py` (5/5) |
| 6 | 12-month EUR/USD H1 backtest <60s on dev laptop | ✓ | **6.78 s** (this plan, `test_smoke_12month_under_60s`) |

All six criteria satisfied. BACK-07 (full 23.5y × 3 pairs × 3 TFs perf budget) explicitly Phase 5 per CONTEXT §deferred.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Legacy targets were not git-tracked**

- **Found during:** Task 2.
- **Issue:** Plan called for `git mv` and `git rm`, but `git ls-files ml_feedback/ backtest_suite.py` returned empty — none of the targets were under version control. `git mv` / `git rm` would have failed with "did not match any files".
- **Fix:** Used filesystem `mv` + `rm -rf` + `rmdir` instead. End state is identical: legacy files gone from working tree, archive copies introduced via `git add` in the cleanup commit. Regression tests in `test_legacy_cleanup.py` pin the end state, so a future re-introduction (tracked or untracked) trips immediately.
- **Files modified:** none beyond the planned set.
- **Commit:** 487a381

### Architectural Changes

None — no Rule 4 issues encountered.

## TDD Gate Compliance

| Gate | Commit | Notes |
| ---- | ------ | ----- |
| RED (Task 1) | db7b028 | `test(01-08): add SC-6 smoke test for 12-month EURUSD H1 <60s` — failed on missing `bars_processed` key |
| GREEN (Task 1) | 6316dcd | `feat(01-08): expose bars_processed in engine result dict` — smoke passes in 6.78 s |
| RED (Task 2) | 9fa2005 | `test(01-08): add D-03/D-04 cleanup regression tests` — 3 failures (file present, archive missing, gitignore missing) |
| GREEN (Task 2) | 487a381 | `chore(01-08): delete backtest_suite.py, archive ml_feedback/, gitignore outputs` — 3/3 cleanup tests pass |

Strict RED → GREEN ordering preserved on both tasks. No REFACTOR commit needed.

## Self-Check: PASSED

- `tests/test_backtest_engine.py::test_smoke_12month_under_60s` — exists and passes (6.78s). FOUND.
- `backtest/engine.py` — contains `bars_processed`. FOUND.
- `backtest_suite.py` — `ls` reports "No such file". FOUND (absence verified).
- `.planning/archive/legacy-backtest/{README.md,grid_search.json,advanced_search.json,walkforward_full.json,verify_final.py}` — all 5 present. FOUND.
- `ml_feedback/` — `ls` reports "No such directory". FOUND (absence verified).
- `.gitignore` — contains both `backtest_results.json` and `backtest_trades.json`. FOUND.
- Commit hashes db7b028, 6316dcd, 9fa2005, 487a381 all present in `git log`. FOUND.
- Plan-scope: 10/10 passing. Collectable suite: 125 passed + 4 skipped. FOUND.
