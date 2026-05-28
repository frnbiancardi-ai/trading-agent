"""Tests for backtest.baseline.plot_writer (D-19 PNG, D-20 Agg backend)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_plot_creates_png(tmp_path: Path) -> None:
    """D-19: PNG file >=1KB esistente dopo plot_equity_curve(equity_series, out_path)."""
    from backtest.baseline.plot_writer import plot_equity_curve

    equity = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
        "equity_eur": [10000.0 + i * 10 for i in range(100)],
        "drawdown_pct": [0.0] * 100,
    })
    out = tmp_path / "EURUSD_M15_MODERATE.png"
    plot_equity_curve(equity, out)
    assert out.exists()
    assert out.stat().st_size > 1000  # PNG sano >= 1KB


def test_equity_png_structure(tmp_path: Path) -> None:
    """D-19: figsize 12x6 inch x dpi 100 -> ~1200x600 px (2-subplot vertical layout)."""
    from backtest.baseline.plot_writer import plot_equity_curve

    equity = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10, freq="D"),
        "equity_eur": [10000.0] * 10,
        "drawdown_pct": [-1.0] * 10,
    })
    out = tmp_path / "USDJPY_H1_AGGRESSIVE.png"
    plot_equity_curve(equity, out)
    # Lazy PIL import -- solo per test
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL non disponibile -- skip image structure check")
    with Image.open(out) as img:
        w, h = img.size
    assert w >= 800
    assert h >= 300


def test_agg_backend_in_worker() -> None:
    """D-20: matplotlib backend == 'Agg' dopo import plot_writer (no GUI hang Windows multiprocess)."""
    import matplotlib

    # Forza re-import (nel test stesso processo, backend gia' settato dall'import di plot_writer)
    import backtest.baseline.plot_writer  # noqa: F401

    backend = matplotlib.get_backend().lower()
    assert backend == "agg", f"backend atteso 'agg', trovato '{backend}'"
