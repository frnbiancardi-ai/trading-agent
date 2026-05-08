"""Tests for backtest.baseline.plot_writer (D-19 PNG, D-20 Agg backend).

Wave 0 stub: scaffolding test-first. Sblocco al Plan 05-04 (plot_writer module).
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.skip(reason="Wave 1: 05-04 implementa plot_writer.plot_equity_curve")
def test_plot_creates_png(tmp_path: Path) -> None:
    """D-19: PNG file ≥1KB esistente dopo plot_equity_curve(equity_series, out_path)."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-04 implementa plot_writer.plot_equity_curve")
def test_equity_png_structure(tmp_path: Path) -> None:
    """D-19: 2-subplot vertical layout — equity curve top, drawdown shaded bottom."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-04 implementa plot_writer (Agg enforcement)")
def test_agg_backend_in_worker() -> None:
    """D-20: matplotlib backend == 'Agg' dopo import plot_writer (no GUI hang Windows multiprocess)."""
    raise NotImplementedError
