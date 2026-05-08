"""Tests for backtest.baseline.report_writer (D-18 Markdown report).

Wave 0 stub: scaffolding test-first. Sblocco al Plan 05-06 (report_writer module).
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.skip(reason="Wave 1: 05-06 implementa report_writer.write_baseline_report")
def test_report_structure(tmp_path: Path) -> None:
    """D-18: header + tabella 27-row + per-slice mini-section + appendix presenti nel md."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-06 implementa report_writer.write_baseline_report")
def test_report_contains_all_27_run_ids(tmp_path: Path) -> None:
    """INT-01: ogni run_id (27 totali) compare almeno 1× nel report markdown."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-06 implementa report_writer appendix")
def test_report_appendix_hashes(tmp_path: Path) -> None:
    """D-17: appendix contiene cost_yaml_sha256, strategy_yaml_sha256, baseline_yaml_sha256, slippage_seed."""
    raise NotImplementedError
