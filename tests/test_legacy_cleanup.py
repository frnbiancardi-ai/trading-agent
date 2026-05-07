"""Regression guard: D-03/D-04 cleanup must remain in effect."""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_backtest_suite_deleted() -> None:
    """D-03: backtest_suite.py must NOT exist at repo root."""
    assert not (REPO / "backtest_suite.py").exists(), (
        "backtest_suite.py was reintroduced; D-03 prohibits it. Use backtest/ package."
    )


def test_ml_feedback_archived() -> None:
    """D-04: ml_feedback/ moved to .planning/archive/legacy-backtest/."""
    archive = REPO / ".planning" / "archive" / "legacy-backtest"
    assert archive.is_dir(), "archive directory missing"
    for fn in ("grid_search.json", "advanced_search.json",
               "walkforward_full.json", "verify_final.py"):
        assert (archive / fn).exists(), f"missing archived file: {fn}"
    # ml_feedback/ should be gone (or at minimum empty if git tracks the dir specially)
    ml = REPO / "ml_feedback"
    if ml.exists():
        # acceptable only if empty (or only has __pycache__)
        residual = [p for p in ml.iterdir() if p.name != "__pycache__"]
        assert not residual, f"ml_feedback/ still has contents: {residual}"


def test_backtest_outputs_gitignored() -> None:
    """Output JSONs from the deleted backtest_suite.py must be gitignored."""
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "backtest_results.json" in gitignore, "backtest_results.json not in .gitignore"
    assert "backtest_trades.json" in gitignore, "backtest_trades.json not in .gitignore"
