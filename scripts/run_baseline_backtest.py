r"""Phase 5 baseline backtest runner — 27 run paralleli (BACK-07, INT-01).

Esegue baseline pre-ML completo: 23.5y x 3 pair x 3 TF x 3 profile = 27 run.
Output:
  - data/training/baseline_decisions/  (parquet directory, pyarrow.dataset format)
  - data/training/baseline_drafts/     (parquet directory)
  - .planning/research/baseline-{date}.md
  - .planning/research/baseline-equity-curves/{symbol}_{tf}_{profile}.png (x27)
  - logs/trades.db tabelle backtest_trades + backtest_runs

Uso:
    .\.venv\Scripts\python.exe scripts\run_baseline_backtest.py
    .\.venv\Scripts\python.exe scripts\run_baseline_backtest.py --force
    .\.venv\Scripts\python.exe scripts\run_baseline_backtest.py --max-wall-clock 1800
    .\.venv\Scripts\python.exe scripts\run_baseline_backtest.py --no-time-gate
"""
from __future__ import annotations

import argparse
import logging
import sys
import time as _time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.baseline.runner import run_baseline  # noqa: E402


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Phase 5 baseline backtest (27 run, 23.5y x 3 pair x 3 TF x 3 profile)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="re-run anche se run_id esiste (overwrite ledger + parquet)",
    )
    parser.add_argument(
        "--max-wall-clock", type=int, default=1800,
        help="WARNING 10 fix: max wall-clock seconds (default 1800 = 30 min). "
             "Exit non-zero se wall > max (BACK-07 SC#1 hard gate).",
    )
    parser.add_argument(
        "--no-time-gate", action="store_true",
        help="Disabilita il time-gate di --max-wall-clock (debug only).",
    )
    args = parser.parse_args()

    start = _time.monotonic()
    results = run_baseline(force=args.force)
    wall = _time.monotonic() - start
    n_total = len(results)
    n_ok = sum(1 for r in results if r.get("status") == "OK")
    n_failed = sum(1 for r in results if r.get("status") == "FAILED")
    n_skipped = sum(1 for r in results if r.get("status") == "SKIPPED")

    print(f"WALL_CLOCK_SECONDS={wall:.0f}")
    print(f"RESULTS={n_ok}/{n_total} ok (skipped={n_skipped} failed={n_failed})")

    # WARNING 10 fix: hard gate su wall-clock (BACK-07 SC#1).
    if args.no_time_gate:
        print("(time-gate disabled via --no-time-gate)")
    elif wall > args.max_wall_clock:
        print(
            f"FAIL: wall-clock {wall:.0f}s > max {args.max_wall_clock}s "
            f"(BACK-07 SC#1 violato). Use --no-time-gate per bypass debug.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
