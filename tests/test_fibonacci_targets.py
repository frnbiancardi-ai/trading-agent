"""Test suite per FibonacciTargets (fase 18.6)."""
import pytest
from unittest.mock import MagicMock

from fibonacci_targets import (
    compute_fibonacci_targets,
    find_recent_swings,
    compute_partial_close_levels,
    FibonacciTargetEngine,
)
from models import FibonacciTargets


def _make_config(**overrides):
    cfg = MagicMock()
    cfg.ENABLE_FIBONACCI_TARGETS = True
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


class TestComputeTargetsBuy:
    def test_basic_buy_with_swings(self):
        # entry 1.1000, SL 1.0950, swing_low=1.0950, swing_high=1.1100
        t = compute_fibonacci_targets(
            entry=1.1000, stop_loss=1.0950, direction="BUY",
            recent_swing_high=1.1100, recent_swing_low=1.0950,
        )
        # range = 0.0150
        # tp_382 = 1.0950 + 0.0150 * 0.382 = 1.10073 → ma min entry+0.5*risk
        assert t.tp_382 > 1.1000
        assert t.tp_618 > t.tp_500
        assert t.tp_500 > t.tp_382
        assert t.tp_100 == 1.1100  # swing_high
        assert t.tp_161 > t.tp_100

    def test_buy_no_swings_uses_default(self):
        t = compute_fibonacci_targets(
            entry=1.1000, stop_loss=1.0950, direction="BUY",
        )
        # risk=0.0050, swing_high=entry+2*risk=1.1100, swing_low=SL=1.0950
        assert t.tp_382 > 1.1000
        assert t.tp_618 > 0
        assert t.recommended_primary_tp == t.tp_618

    def test_buy_zero_risk_returns_empty(self):
        t = compute_fibonacci_targets(
            entry=1.1000, stop_loss=1.1000, direction="BUY",
        )
        assert t.tp_382 == 0.0
        assert t.tp_618 == 0.0


class TestComputeTargetsSell:
    def test_basic_sell_with_swings(self):
        t = compute_fibonacci_targets(
            entry=1.1000, stop_loss=1.1050, direction="SELL",
            recent_swing_high=1.1050, recent_swing_low=1.0900,
        )
        # range = 0.0150
        assert t.tp_382 < 1.1000
        assert t.tp_618 < t.tp_500
        assert t.tp_500 < t.tp_382
        assert t.tp_100 == 1.0900  # swing_low
        assert t.tp_161 < t.tp_100

    def test_sell_no_swings_uses_default(self):
        t = compute_fibonacci_targets(
            entry=1.1000, stop_loss=1.1050, direction="SELL",
        )
        assert t.tp_382 < 1.1000
        assert t.tp_618 < t.tp_382


class TestRecentSwings:
    def test_finds_high_low(self):
        bars = [
            {"high": 1.10, "low": 1.05},
            {"high": 1.12, "low": 1.06},
            {"high": 1.11, "low": 1.04},
        ]
        sh, sl = find_recent_swings(bars)
        assert sh == 1.12
        assert sl == 1.04

    def test_empty_bars_returns_none(self):
        sh, sl = find_recent_swings([])
        assert sh is None
        assert sl is None

    def test_lookback_truncates(self):
        bars = [{"high": float(i), "low": float(i) - 1} for i in range(100)]
        sh, sl = find_recent_swings(bars, lookback=10)
        # ultimi 10: i=90..99
        assert sh == 99.0
        assert sl == 89.0


class TestPartialCloseLevels:
    def test_extracts_382_618(self):
        t = FibonacciTargets(tp_382=1.10, tp_500=1.11, tp_618=1.12, tp_100=1.13, tp_161=1.15)
        levels = compute_partial_close_levels(t, "0.382,0.618")
        assert levels == [1.10, 1.12]

    def test_extracts_all_known(self):
        t = FibonacciTargets(tp_382=1.10, tp_500=1.11, tp_618=1.12, tp_100=1.13, tp_161=1.15)
        levels = compute_partial_close_levels(t, "0.382,0.5,0.618,1.0,1.618")
        assert levels == [1.10, 1.11, 1.12, 1.13, 1.15]

    def test_unknown_token_skipped(self):
        t = FibonacciTargets(tp_382=1.10, tp_500=1.11, tp_618=1.12, tp_100=1.13, tp_161=1.15)
        levels = compute_partial_close_levels(t, "0.382,FOO,0.618")
        assert levels == [1.10, 1.12]


class TestFibonacciTargetEngine:
    def setup_method(self):
        self.eng = FibonacciTargetEngine(_make_config())

    def test_compute_with_bars(self):
        bars = [{"high": 1.105, "low": 1.095, "close": 1.100} for _ in range(50)]
        t = self.eng.compute(1.100, 1.095, "BUY", bars)
        assert t.tp_618 > 1.100
        assert t.recommended_primary_tp > 0

    def test_disabled_returns_fixed_2r(self):
        cfg = _make_config(ENABLE_FIBONACCI_TARGETS=False)
        eng = FibonacciTargetEngine(cfg)
        t = eng.compute(1.100, 1.095, "BUY")
        # risk=0.005, tp = 1.100 + 0.010 = 1.110
        assert t.recommended_primary_tp == pytest.approx(1.110, abs=1e-6)
        assert t.tp_618 == t.recommended_primary_tp

    def test_no_bars_uses_defaults(self):
        t = self.eng.compute(1.100, 1.095, "BUY", bars=None)
        assert t.tp_382 > 1.100
        assert t.tp_618 > t.tp_382
