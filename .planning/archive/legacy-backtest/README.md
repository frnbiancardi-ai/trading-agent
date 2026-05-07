# Legacy Backtest Archive

Archived 2026-05-07 during Phase 1 (Backtest Engine) per CONTEXT D-04.

Source: `ml_feedback/` directory (RSI/SMA grid-search artifacts produced by the
now-deleted `backtest_suite.py`). Retained for historical reference only — no
code path consumes these files.

Files:
- `grid_search.json` — RSI×SMA hyperparameter grid results
- `advanced_search.json` — extended grid + Monte-Carlo
- `walkforward_full.json` — pre-Phase-1 walk-forward output (superseded by `backtest/walk_forward.py`)
- `verify_final.py` — verification script (no longer runnable; depends on deleted `backtest_suite.py`)

Superseded by: `backtest/` package (Phase 1).
