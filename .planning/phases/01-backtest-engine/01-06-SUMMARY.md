---
phase: 01-backtest-engine
plan: 06
subsystem: backtest
tags: [backtest, walk-forward, BACK-05]
requires: [01-01]
provides: [walk_forward_slices]
affects: [phase-05-baseline, phase-07-ml]
tech_stack_added: []
patterns: [pure-generator, bar-count-boundaries, fold-cap]
key_files_created: []
key_files_modified:
  - backtest/walk_forward.py
  - tests/test_backtest_walk_forward.py
decisions: [D-06]
metrics:
  duration_min: 5
  completed: 2026-05-07
  tasks_completed: 1
  files_changed: 2
---

# Phase 1 Plan 06: Walk-Forward Slice Generator Summary

Pure-function `walk_forward_slices` yielding non-overlapping (train, test) bar
slices in `rolling` (default) or `expanding` mode, with fold cap 10 and default
4:1 train:test ratio per D-06. Implements BACK-05.

## What Was Built

- `backtest/walk_forward.py` — generator implementing both modes with
  bar-count boundaries (research recommendation), validation for `n_folds`
  (1..10), `train_ratio` (>=1), and `mode`.
- `tests/test_backtest_walk_forward.py` — 7 tests covering no-overlap,
  expanding train growth, both fold-cap edges, unknown-mode error, temporal
  ordering (T-WalkForwardLeak), and D-06 default values.

## Concrete Fold Sizes (n_folds=10, train_ratio=4, 148_900 bars)

Verifies the research §Pattern 5 numbers. Bars indexed 0..148_899.

### Rolling mode (default)

| Fold | train_size | test_size | train range | test range |
|------|-----------:|----------:|------------:|-----------:|
| 0    | 11_912     | 2_978     | 0..11_911       | 11_912..14_889  |
| 1    | 11_912     | 2_978     | 14_890..26_801  | 26_802..29_779  |
| 2    | 11_912     | 2_978     | 29_780..41_691  | 41_692..44_669  |
| 3    | 11_912     | 2_978     | 44_670..56_581  | 56_582..59_559  |
| 4    | 11_912     | 2_978     | 59_560..71_471  | 71_472..74_449  |
| 5    | 11_912     | 2_978     | 74_450..86_361  | 86_362..89_339  |
| 6    | 11_912     | 2_978     | 89_340..101_251 | 101_252..104_229|
| 7    | 11_912     | 2_978     | 104_230..116_141| 116_142..119_119|
| 8    | 11_912     | 2_978     | 119_120..131_031| 131_032..134_009|
| 9    | 11_912     | 2_978     | 134_010..145_921| 145_922..148_899|

`fold_size = 148_900 // 10 = 14_890`; `test_size = 14_890 // 5 = 2_978`;
`train_size = 4 × 2_978 = 11_912`. Test slices fully partition the trailing
4/5 of each fold; train slice is the immediately preceding 4× window. No
overlap, no future leak.

### Expanding mode

| Fold | train_size | test_size | test range |
|------|-----------:|----------:|-----------:|
| 0    | 42_540     | 10_635    | 42_540..53_174   |
| 1    | 53_175     | 10_635    | 53_175..63_809   |
| 2    | 63_810     | 10_635    | 63_810..74_444   |
| 3    | 74_445     | 10_635    | 74_445..85_079   |
| 4    | 85_080     | 10_635    | 85_080..95_714   |
| 5    | 95_715     | 10_635    | 95_715..106_349  |
| 6    | 106_350    | 10_635    | 106_350..116_984 |
| 7    | 116_985    | 10_635    | 116_985..127_619 |
| 8    | 127_620    | 10_635    | 127_620..138_254 |
| 9    | 138_255    | 10_635    | 138_255..148_889 |

`test_size = 148_900 // (10 + 4) = 10_635`. Train grows monotonically by
`test_size` each fold. Final fold leaves 11 unused tail bars (148_900 −
148_889 − 1 = 10) due to integer division — acceptable; downstream Phase 5
runs slice complete history.

## Verification

```
$ pytest tests/test_backtest_walk_forward.py -x --tb=short -v
7 passed in 0.07s
```

| Test | Validates |
|------|-----------|
| test_no_overlap_rolling | T-WalkForwardLeak: test slices disjoint |
| test_expanding_mode | train grows, test constant size |
| test_fold_cap_high | n_folds=11 → ValueError "1..10" |
| test_fold_cap_low | n_folds=0 → ValueError "1..10" |
| test_unknown_mode | mode="bogus" → ValueError "Unknown mode" |
| test_temporal_order_ints | max(train) < min(test) every fold |
| test_default_mode_and_ratio | D-06 defaults: rolling, train_ratio=4 |

## Decisions Honored

- **D-06**: rolling default, fold cap 10, train_ratio default 4, both modes
  exposed via `mode=` kwarg.
- **Bar-count boundaries** (research §Pattern 5) over calendar boundaries —
  simpler, deterministic, no calendar-edge ambiguity.

## Threat Mitigations Verified

- **T-WalkForwardLeak** (Tampering / data integrity): exclusive-range slicing
  by construction (`bars[train_start:test_start]` and
  `bars[test_start:test_end]`); `test_no_overlap_rolling` and
  `test_temporal_order_ints` assert no test-test overlap and
  max(train) < min(test).
- **T-1-09** (DoS via fold explosion): fold cap 10 enforced at both ends;
  `test_fold_cap_high` / `test_fold_cap_low` cover the boundary.

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Phase | Type | Hash | Message |
|-------|------|------|---------|
| RED   | test | 50cca8f | test(01-06): add failing tests for walk_forward_slices (BACK-05) |
| GREEN | feat | cac3220 | feat(01-06): implement walk_forward_slices generator (BACK-05) |

## Self-Check: PASSED

- `backtest/walk_forward.py` FOUND
- `tests/test_backtest_walk_forward.py` FOUND
- Commit `50cca8f` FOUND in git log
- Commit `cac3220` FOUND in git log
- 7/7 tests passing
- 0 `pytest.mark.skip` markers in test file
