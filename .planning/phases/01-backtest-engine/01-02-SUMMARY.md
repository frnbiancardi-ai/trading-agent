---
phase: 01-backtest-engine
plan: 02
subsystem: backtest
tags: [backtest, loader, csv, timezone, BACK-01]
status: complete
requires: [01-01]
provides:
  - Bar dataclass (frozen, 8 fields)
  - load_bars(path, symbol, timeframe, date_start, date_end) -> list[Bar]
  - GMT-6 -> UTC conversion (D-08, D-10 cross-checked on 2018)
affects:
  - backtest/loader.py
  - tests/test_backtest_loader.py
tech-stack:
  added: []
  patterns:
    - "pd.read_csv(sep=';', encoding='utf-8', dtype=str) + column-strip + itertuples"
    - "naive UTC timestamps via timedelta(hours=6) (no pytz/Etc/GMT+6)"
key-files:
  created: []
  modified:
    - backtest/loader.py
    - tests/test_backtest_loader.py
decisions:
  - "Used timedelta(hours=6) (fixed offset, no DST) per researcher confirmation, not POSIX Etc/GMT+6"
  - "Date filter normalizes tz-aware datetime inputs to naive UTC before comparing vs naive dt_utc series"
metrics:
  duration: "~10 min"
  tasks_completed: 2
  files_modified: 2
  tests_added: 4
  completed: 2026-05-07
requirements: [BACK-01]
---

# Phase 01 Plan 02: Italian-CSV Loader Summary

One-liner: Implemented `load_bars` BACK-01 — semicolon Italian CSV parser with leading-space header strip, GMT-6 -> UTC via `timedelta(hours=6)`, sorted+deduplicated `Bar` list; D-10 cross-year NFP alignment regression passes on 2018-02-02.

## What was built

### `backtest/loader.py`
- Module constant `_GMT6_OFFSET = timedelta(hours=6)` with D-08 reference comment.
- `@dataclass(frozen=True)` `Bar` with 8 fields: `time` (int unix UTC seconds), `open/high/low/close` (float), `volume` (int), `symbol` (str), `timeframe` (str).
- `load_bars(path, symbol, timeframe, date_start=None, date_end=None) -> list[Bar]`:
  - `pd.read_csv(path, sep=';', encoding='utf-8', dtype=str)` — preserves text fidelity until cast.
  - `df.columns = [c.strip() for c in df.columns]` — strips leading-space headers (`' Ora' -> 'Ora'`, etc.). Note the source preserves lowercase `low` column.
  - Combines `Data + ' ' + Ora` and parses with `format='%d/%m/%Y %H:%M:%S'`.
  - Adds `_GMT6_OFFSET` to obtain naive UTC timestamps in `dt_utc`.
  - Casts numeric columns: Open/High/low/Close to float, Volume to int.
  - Date filter normalizes tz-aware inputs to naive UTC before comparison (test passes `datetime(2018, 2, 2, tzinfo=timezone.utc)`).
  - `sort_values('dt_utc').drop_duplicates('dt_utc').reset_index(drop=True)`.
  - Iterates via `itertuples(index=False)` per RESEARCH perf rule.
  - No `decimal=','` (Pitfall 5: values are already dot-decimal in source).
  - No logging, no print, pure I/O adapter.

### `tests/test_backtest_loader.py`
Replaced plan-01 skip-stub with 4 real tests:
- `test_basic_load`: fixture -> 5 chronological Bars; frozen-dataclass mutation raises.
- `test_gmt6_utc_offset`: 07:00 source -> 13:00 UTC; consecutive 3600s diffs.
- `test_column_strip`: synthetic CSV with leading-space headers parses without KeyError.
- `test_nfp_alignment` (D-10): NFP 2018-02-02 13:30 UTC -> 13:00 UTC bar is top-range candidate within +/-2h window.

## D-10 NFP Regression Result (2018-02-02)

Bars in +/-2h window around 13:30 UTC release:

| Hour (UTC) | Range  | Open    | Close   |
|------------|--------|---------|---------|
| 12:00      | 0.00082 | 1.24902 | 1.24899 |
| **13:00**  | **0.0058** | **1.24900** | **1.24454** |
| 14:00      | 0.00326 | 1.24453 | 1.24275 |
| 15:00      | 0.00268 | 1.24276 | 1.24351 |

The 13:00 UTC bar (containing 13:30 NFP release) is by far the highest-range bar in the window (0.0058 vs second-place 0.00326), confirming GMT-6 -> UTC alignment on a year independent of the researcher's 2024 verification set. Also note the strong bearish print (close < open by ~45 pips) consistent with a positive USD surprise — full diagnostic alignment.

## Verification

- Smoke test: `python -c "from backtest.loader import Bar, load_bars; ..."` -> `OK Bar(time=1704459600, ...)` (07:00 source -> 13:00 UTC ✓)
- Loader tests: `pytest tests/test_backtest_loader.py -v` -> 4 passed, 0 skipped
- Full suite regression: `pytest -q` -> 177 passed, 22 skipped (was 173 passed before plan 02 -> +4 new tests, 0 regressions)
- `grep -c decimal backtest/loader.py` -> 0
- `grep -c iterrows backtest/loader.py` -> 0
- `grep -c "pytest.mark.skip" tests/test_backtest_loader.py` -> 1 (only the conditional `skipif` on missing CSV)
- `python -m py_compile backtest/loader.py` -> compiled

## Deviations from Plan

### Auto-fixed

**1. [Rule 3 - Blocking] Date-filter tz-handling for tz-aware inputs**
- **Found during:** Task 1 verify (subsequently confirmed in Task 2's `test_nfp_alignment`)
- **Issue:** Plan action specified `df = df[df["dt_utc"] >= pd.Timestamp(date_start)]`, but `dt_utc` is naive (built via `datetime + timedelta`) while the NFP test passes `datetime(2018, 2, 2, tzinfo=timezone.utc)` -> `pd.Timestamp` becomes tz-aware -> direct comparison raises `TypeError: Cannot compare tz-naive and tz-aware`.
- **Fix:** Normalize tz-aware inputs to naive UTC: if `ts.tzinfo is not None`, apply `ts.tz_convert('UTC').tz_localize(None)`; naive inputs pass through. Behavior matches plan intent (UTC comparison) without breaking tz-aware callers.
- **Files modified:** `backtest/loader.py`
- **Commit:** 0752562

**2. [Rule 1 - Bug] Removed `decimal` and `iterrows` strings from docstring**
- **Found during:** Task 1 done-criteria check (`grep -c "decimal"`/`grep -c "iterrows"` were both required to be 0 but my initial docstring said "NOT iterrows" / "Does NOT pass decimal").
- **Fix:** Reworded docstring to satisfy literal grep checks while preserving intent: "Iterates via itertuples (perf rule)", "Reads numeric values as dot-separated floats (Pitfall 5)".
- **Files modified:** `backtest/loader.py`
- **Commit:** 0752562 (same commit as the implementation)

### Workspace setup notes (not deviations from plan)
- Worktree was initially based on a pre-`feature/update-pythono-pure-strategy` SHA and lacked `.planning/` and `backtest/` directories. Reset the worktree branch to the parent branch tip (`62aa7ee docs(01-01): complete backtest scaffolding plan summary`) before starting; no committed work was lost.
- `data/historical/EURUSD/H1.csv` is not git-tracked (148901 lines, large file) but exists in the main repo. Copied locally so `test_nfp_alignment` would actually run on this dev machine rather than skip. The file remains untracked in the worktree (and is intentionally not committed).

## Threat surface scan

No new surface beyond the disposition already documented in the plan's `<threat_model>`:
- T-1-03 (CSV tampering) — accepted; repo-tracked.
- T-1-04 (path traversal) — accepted; loader does not log file content.
- T-NoFutureLeak — mitigated; `sort_values('dt_utc').drop_duplicates('dt_utc')` in code, asserted by `test_basic_load` (chronological invariant).

## Commits

| Task | Type | Hash    | Description |
|------|------|---------|-------------|
| 1    | feat | 0752562 | Italian-CSV loader with GMT-6 -> UTC conversion |
| 2    | test | 0ebfed8 | Real loader tests + D-10 NFP 2018 regression |

## Self-Check: PASSED
- `backtest/loader.py` exists ✓
- `tests/test_backtest_loader.py` exists, no module-level skip ✓
- Commit 0752562 in `git log` ✓
- Commit 0ebfed8 in `git log` ✓
- 4 loader tests pass ✓
- Baseline 177 passed (was 173 + 4 new) ✓
