r"""Phase 5 perf profiler single-slice (BACK-07 SC#1 sanity).

Esegue 1 slice (symbol, tf, profile) e misura:
  - wall_clock totale
  - memory peak via psutil (RSS delta start->end)

Output: stampa stdout per audit Wave 1 (RESEARCH SC#1 sanity check).

Uso:
    .\.venv\Scripts\python.exe scripts\profile_baseline_slice.py EURUSD M15 MODERATE
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import psutil  # type: ignore
except ImportError:
    print("WARNING: psutil non installato — pip install psutil per memory profiling")
    psutil = None  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile single baseline slice")
    parser.add_argument("symbol", help="Pair symbol (EURUSD, GBPUSD, USDJPY, ...)")
    parser.add_argument("timeframe", help="Timeframe (M15, M30, H1)")
    parser.add_argument(
        "profile",
        choices=["CONSERVATIVE", "MODERATE", "AGGRESSIVE"],
        help="Risk profile (CONSERVATIVE | MODERATE | AGGRESSIVE)",
    )
    args = parser.parse_args()

    from backtest.baseline.runner import load_baseline_config
    from backtest.baseline.slice_worker import run_slice_3profiles

    baseline_cfg = load_baseline_config()
    costs_cfg_path = Path("data/configs/costs.yaml")
    strategy_cfg_path = Path("config/strategy.yaml")

    proc = psutil.Process() if psutil else None
    rss_start = proc.memory_info().rss if proc else 0
    t0 = time.time()
    results = run_slice_3profiles(
        args.symbol, args.timeframe, baseline_cfg, costs_cfg_path, strategy_cfg_path,
        force=False, ledger_db_path=Path("logs/trades.db"),
    )
    wall_clock = time.time() - t0
    rss_end = proc.memory_info().rss if proc else 0
    rss_delta_mb = (rss_end - rss_start) / 1e6 if proc else 0

    # Filtra solo profile richiesto.
    target = next((r for r in results if r["profile"] == args.profile), None)

    print(f"=== Profile {args.symbol} {args.timeframe} {args.profile} ===")
    print(f"wall_clock: {wall_clock:.2f}s")
    print(f"rss_delta_mb: {rss_delta_mb:.1f}")
    print(f"status: {target['status'] if target else 'N/A'}")
    if target and target.get("status") == "OK":
        print(f"n_trades: {target.get('n_trades', 0)}")
        print(f"n_drafts: {target.get('n_drafts', 0)}")
    elif target and target.get("status") == "FAILED":
        print(f"error: {target.get('error', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
