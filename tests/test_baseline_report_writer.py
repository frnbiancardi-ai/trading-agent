"""Tests for backtest.baseline.report_writer (D-18, INT-01).

Plan 05-06b — Wave 2 parte B (report_writer Markdown D-18).
Verifica:
  - Schema D-18 (header + tabella 27-row + per-slice + appendix)
  - INT-01: tutti i 27 run_id citati
  - WARNING 12 fix: appendix sha256 FULL 64-char (no truncation)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backtest.baseline.report_writer import write_baseline_report


def _mk_metrics():
    """Costruisce un mock BacktestMetrics-like per i 27 result OK."""
    m = MagicMock()
    m.sharpe = 1.2
    m.sortino = 1.5
    m.max_drawdown_pct = -8.0
    m.hit_rate = 0.55
    m.expectancy_usd = 0.5
    m.profit_factor = 1.3
    m.avg_r = 0.6
    m.longest_dd_days = 12.5
    return m


def _mk_results():
    """27 result dict (3 sym × 3 tf × 3 profile) tutti status=OK."""
    results = []
    for sym in ("EURUSD", "GBPUSD", "USDJPY"):
        for tf in ("M15", "M30", "H1"):
            for prof in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE"):
                results.append({
                    "run_id": f"baseline_2026-05-08_{sym}_{tf}_{prof}",
                    "symbol": sym, "timeframe": tf, "profile": prof,
                    "status": "OK", "metrics": _mk_metrics(),
                    "n_trades": 100, "n_drafts": 1000,
                    "equity_path": f".planning/research/baseline-equity-curves/{sym}_{tf}_{prof}.png",
                })
    return results


def _mk_meta():
    """Meta dict per appendix — WARNING 12 fix: tutti gli hash FULL 64-char sha256."""
    return {
        "cli_command": "python scripts/run_baseline_backtest.py",
        "git_sha": "abcdef1234567890",
        "total_wall_clock_seconds": 1234.5,
        "cost_yaml_sha256": "deadbeef" * 8,        # 64 char
        "strategy_yaml_sha256": "cafebabe" * 8,    # 64 char
        "baseline_yaml_sha256": "feedface" * 8,    # 64 char
        "slippage_seed": 42,
        "warm_up_bars": {"M15": 200, "M30": 200, "H1": 200},
        "longest_lookback": 200,
        "decision_count": 12345,
        "min_decisions_hard": 1000,
        "target_decisions_soft": 10000,
    }


def test_report_structure(tmp_path: Path) -> None:
    """D-18: header + tabella + per-slice + appendix presenti nel md."""
    out = tmp_path / "baseline-2026-05-08.md"
    write_baseline_report(_mk_results(), out, _mk_meta())
    text = out.read_text(encoding="utf-8")
    assert "## Header" in text
    assert "## Slice Metrics" in text
    assert "## Per-slice details" in text
    assert "## Appendix" in text


def test_report_contains_all_27_run_ids(tmp_path: Path) -> None:
    """INT-01: ogni run_id (27 totali) compare almeno 1× nel report markdown."""
    out = tmp_path / "baseline.md"
    results = _mk_results()
    assert len(results) == 27
    write_baseline_report(results, out, _mk_meta())
    text = out.read_text(encoding="utf-8")
    for r in results:
        assert r["run_id"] in text, f"missing {r['run_id']} in report"


def test_report_appendix_hashes(tmp_path: Path) -> None:
    """WARNING 12 fix: appendix contiene FULL 64-char sha256 (no truncation)."""
    out = tmp_path / "baseline.md"
    meta = _mk_meta()
    write_baseline_report(_mk_results(), out, meta)
    text = out.read_text(encoding="utf-8")
    # Hash FULL 64-char visibili nel report
    assert meta["cost_yaml_sha256"] in text
    assert meta["strategy_yaml_sha256"] in text
    assert meta["baseline_yaml_sha256"] in text
    # Length check: ognuno deve essere 64-char hex string
    assert len(meta["cost_yaml_sha256"]) == 64
    assert len(meta["strategy_yaml_sha256"]) == 64
    assert len(meta["baseline_yaml_sha256"]) == 64
    # Slippage seed presente
    assert "slippage_seed" in text
    assert "42" in text
