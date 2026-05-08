"""Plan 05-08 Rule 3 follow-up: rigenera baseline-{date}.md dal ledger SQLite
post-fix Bug #5 (report_writer dict access). Evita re-run engine 3h18m.

Legge:
- backtest_runs (audit trail)
- backtest_trades (1076 trade reali)

Calcola metrics via compute_metrics + asdict, ricostruisce result list nello
stesso shape che slice_worker emette, riusa write_baseline_report.
"""
from __future__ import annotations

import sqlite3
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backtest.metrics import compute_metrics  # noqa: E402
from backtest.baseline.report_writer import write_baseline_report  # noqa: E402
from backtest.baseline.determinism import file_sha256  # noqa: E402


def main() -> None:
    db = REPO / "logs" / "trades.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    runs = conn.execute(
        "SELECT run_id, symbol, timeframe, profile FROM backtest_runs WHERE run_id LIKE 'baseline_%'"
    ).fetchall()
    print(f"runs trovate: {len(runs)}")

    results: list[dict] = []
    decision_count = 0
    for r in runs:
        trades = conn.execute(
            "SELECT entry_time, exit_time, pnl_usd, risk_usd FROM backtest_trades WHERE run_id=?",
            (r["run_id"],),
        ).fetchall()
        trades_list = [dict(t) for t in trades]
        m = compute_metrics(trades_list, r["timeframe"])
        results.append({
            "run_id": r["run_id"],
            "symbol": r["symbol"],
            "timeframe": r["timeframe"],
            "profile": r["profile"],
            "status": "OK",
            "metrics": asdict(m),
            "n_trades": len(trades_list),
            "n_drafts": 0,
            "equity_path": str(
                REPO / ".planning" / "research" / "baseline-equity-curves"
                / f"{r['symbol']}_{r['timeframe']}_{r['profile']}.png"
            ),
        })
        decision_count += len(trades_list)

    conn.close()

    run_date = date.today().isoformat()
    report_path = REPO / ".planning" / "research" / f"baseline-{run_date}.md"
    costs_path = REPO / "data" / "configs" / "costs.yaml"
    strat_path = REPO / "config" / "strategy.yaml"
    base_path = REPO / "data" / "configs" / "baseline.yaml"

    meta = {
        "cli_command": "python scripts/regen_baseline_report.py",
        "git_sha": "regen-post-bug5-fix",
        "total_wall_clock_seconds": 11922.3,  # original smoke run
        "cost_yaml_sha256": file_sha256(costs_path),
        "strategy_yaml_sha256": file_sha256(strat_path) if strat_path.exists() else "n/a",
        "baseline_yaml_sha256": file_sha256(base_path),
        "slippage_seed": 42,
        "warm_up_bars": {"M15": 200, "M30": 200, "H1": 200},
        "longest_lookback": 200,
        "decision_count": decision_count,
        "min_decisions_hard": 1000,
        "target_decisions_soft": 10000,
    }

    write_baseline_report(results, report_path, meta)
    print(f"report rigenerato: {report_path} (decisions={decision_count})")


if __name__ == "__main__":
    main()
