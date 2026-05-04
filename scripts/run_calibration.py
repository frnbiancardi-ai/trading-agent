#!/usr/bin/env python3
"""Calibration + Validation (fase 17.7): grid-search, backtest, comparison report.

Workflow:
1. Load historical dataset (6m EURUSD+GBPUSD M15)
2. Define parameter grid
3. Execute backtest per combo
4. Select Pareto-optimal (max expectancy + Sharpe - max_dd)
5. Compare v1.2.0 vs v2 (v1.2.0 replay + v2 new code)
6. Generate report: PHASE_17_VALIDATION.md
7. Decide: merge if v2 beats v1.2.0 on >=2 metrics
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from itertools import product
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Parameter grid definition
# ──────────────────────────────────────────────────────────────────────────────

PARAM_GRID = {
    "MIN_TREND_STRENGTH": [0.55, 0.60, 0.65, 0.70, 0.75],
    "MIN_BREAKOUT_VOLUME_RATIO": [1.1, 1.3, 1.5, 1.8],
    "MIN_RISK_REWARD_RATIO": [1.5, 2.0, 2.5],
    "BREAKEVEN_TRIGGER_R": [0.8, 1.0, 1.2],
    "BB_SQUEEZE_PERCENTILE": [0.15, 0.20, 0.25],
}


def generate_param_combos(grid: dict) -> list[dict]:
    """Generate all parameter combinations from grid."""
    keys = list(grid.keys())
    values = [grid[k] for k in keys]
    combos = []
    for combo_values in product(*values):
        combo = dict(zip(keys, combo_values))
        combos.append(combo)
    return combos


class CalibrationRunner:
    """Main calibration workflow orchestrator."""

    def __init__(
        self,
        dataset_path: str = "tests/data/backtest/",
        output_dir: str = ".orchestration/",
    ):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []

    def load_historical_data(self) -> Optional[dict]:
        """Load pre-downloaded historical dataset.

        Expect CSV files in dataset_path: EURUSD_M15.csv, GBPUSD_M15.csv
        Format: time,open,high,low,close,tick_volume
        """
        logger.info("Loading historical dataset from %s", self.dataset_path)

        if not self.dataset_path.exists():
            logger.error("Dataset path not found: %s", self.dataset_path)
            return None

        dataset = {}
        for symbol in ["EURUSD", "GBPUSD"]:
            csv_file = self.dataset_path / f"{symbol}_M15.csv"
            if not csv_file.exists():
                logger.warning("CSV file not found: %s", csv_file)
                continue

            # Parse CSV (simple approach)
            bars = []
            try:
                with open(csv_file, "r") as f:
                    next(f)  # Skip header
                    for line in f:
                        parts = line.strip().split(",")
                        if len(parts) < 5:
                            continue
                        bar = {
                            "time": int(float(parts[0])),
                            "open": float(parts[1]),
                            "high": float(parts[2]),
                            "low": float(parts[3]),
                            "close": float(parts[4]),
                            "tick_volume": int(float(parts[5])) if len(parts) > 5 else 100,
                        }
                        bars.append(bar)
                dataset[symbol] = bars
                logger.info("Loaded %d bars for %s", len(bars), symbol)
            except Exception as e:
                logger.error("Failed to parse %s: %s", csv_file, e)

        return dataset if dataset else None

    def run_grid_search(self, dataset: dict) -> list[dict]:
        """Execute backtest for each parameter combo.

        Returns list of result dicts: {params, report, score}
        """
        combos = generate_param_combos(PARAM_GRID)
        logger.info("Generated %d parameter combinations", len(combos))

        results = []
        for i, combo in enumerate(combos):
            logger.info(
                "Running backtest %d/%d with params: %s",
                i + 1,
                len(combos),
                combo,
            )

            # TODO: Execute backtest with this combo
            # mock_report = backtest_engine.run(dataset, combo)
            # score = compute_pareto_score(mock_report)
            # results.append({"params": combo, "report": ..., "score": score})

            logger.warning("Backtest execution not yet implemented (TODO phase 17.7)")

        return results

    def select_pareto_optimal(self, results: list[dict]) -> Optional[dict]:
        """Select Pareto-optimal combo on {expectancy, Sharpe, -max_dd}.

        Score = expectancy + Sharpe - max_dd (maximize).
        """
        if not results:
            return None

        # Sort by score descending
        sorted_results = sorted(
            results,
            key=lambda r: r.get("score", 0),
            reverse=True,
        )

        best = sorted_results[0]
        logger.info(
            "Best combo: params=%s score=%.4f",
            best.get("params"),
            best.get("score"),
        )
        return best

    def generate_report(self, best_combo: Optional[dict]) -> str:
        """Generate markdown report for PHASE_17_VALIDATION.md."""
        report_lines = [
            "# Phase 17 Validation Report",
            "",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Summary",
            "",
            "Status: **IN PROGRESS** (fase 17.7 TODO)",
            "",
            "Grid-search parameters:",
        ]

        for param, values in PARAM_GRID.items():
            report_lines.append(f"- {param}: {values}")

        report_lines.extend([
            "",
            "## Best Calibrated Parameters",
            "",
        ])

        if best_combo:
            report_lines.append(f"```json")
            report_lines.append(json.dumps(best_combo.get("params"), indent=2))
            report_lines.append(f"```")
        else:
            report_lines.append("(No calibration results available yet)")

        report_lines.extend([
            "",
            "## Comparison: v1.2.0 vs v2 Defendi",
            "",
            "| Metric | v1.2.0 | v2 Calibrated | Winner |",
            "|--------|--------|---------------|--------|",
            "| Expectancy | TBD | TBD | TBD |",
            "| Profit Factor | TBD | TBD | TBD |",
            "| Sharpe Ratio | TBD | TBD | TBD |",
            "| Max Drawdown | TBD | TBD | TBD |",
            "",
            "## Merge Decision",
            "",
            "- [ ] v2 beats v1.2.0 on >=2 metrics",
            "- [ ] User validation checklist signed",
            "- [ ] Ready for merge to main",
            "",
        ])

        return "\n".join(report_lines)

    def run(self) -> bool:
        """Execute full calibration workflow."""
        logger.info("=== Phase 17.7 Calibration + Validation ===")

        # 1. Load data
        dataset = self.load_historical_data()
        if not dataset:
            logger.error("Failed to load dataset. Cannot proceed.")
            return False

        # 2. Grid search
        results = self.run_grid_search(dataset)
        if not results:
            logger.warning("No backtest results generated")

        # 3. Select Pareto optimal
        best = self.select_pareto_optimal(results)

        # 4. Generate report
        report_md = self.generate_report(best)
        report_path = self.output_dir / "PHASE_17_VALIDATION.md"
        report_path.write_text(report_md)
        logger.info("Report written to %s", report_path)

        # 5. Summary
        logger.info("Calibration complete. Check %s for results.", report_path)
        return True


if __name__ == "__main__":
    runner = CalibrationRunner()
    success = runner.run()
    exit(0 if success else 1)
