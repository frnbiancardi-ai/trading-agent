"""Tests for backtest.baseline.warmup (D-07, BLOCKER 3 user-locked decision).

NON stub — helper `longest_lookback_required` già implementato in Plan 05-01 Task 3b.
Verifica unit del fallback chain: Phase 2 hook → DFS dict parsing → fallback 200.
"""
from __future__ import annotations

from pathlib import Path

import pytest  # noqa: F401 — caricato per coerenza pattern test_baseline_*.py

from backtest.baseline.warmup import longest_lookback_required


def test_longest_lookback_default_when_none() -> None:
    """D-07: cfg None → default fallback 200."""
    assert longest_lookback_required(None) == 200


def test_longest_lookback_max_indicator_period() -> None:
    """D-07 BLOCKER 3 fix: max(periods) across config block.

    Atteso: max([20, 50, 200, 14, 20, 55, 26]) == 200.
    """
    cfg = {
        "indicators": {
            "ema_periods": [20, 50, 200],
            "atr_period": 14,
            "bb_period": 20,
            "donchian_period": 55,
            "macd_slow": 26,
        },
    }
    assert longest_lookback_required(cfg) == 200


def test_longest_lookback_finds_largest() -> None:
    """D-07: lookback maggiore di 200 viene rispettato (no clamp)."""
    cfg = {"indicators": {"ema_periods": [20, 250], "atr_period": 14}}
    assert longest_lookback_required(cfg) == 250


def test_longest_lookback_yaml_path(tmp_path: Path) -> None:
    """D-07: legge config da Path verso strategy.yaml."""
    p = tmp_path / "strategy.yaml"
    p.write_text(
        "indicators:\n"
        "  ema_periods: [20, 50, 100]\n"
        "  atr_period: 14\n",
        encoding="utf-8",
    )
    assert longest_lookback_required(p) == 100


def test_longest_lookback_garbage_falls_back() -> None:
    """D-07: input non parseable → fallback 200, no exception."""
    # Dict senza alcuna chiave whitelisted
    assert longest_lookback_required({"foo": "bar", "baz": [1, 2, 3]}) == 200
