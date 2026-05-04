"""Test suite per CorrelationMonitor (fase 18.3)."""
import math
import pytest
from unittest.mock import MagicMock

from correlation_monitor import (
    compute_pearson,
    compute_rolling_correlation,
    detect_correlation_divergence,
    CorrelationMonitor,
    CorrelationStat,
)


def _make_config(**overrides):
    cfg = MagicMock()
    cfg.ENABLE_CORRELATION_MONITOR = True
    cfg.INTERMARKET_TIMEFRAME = "H4"
    cfg.CORRELATION_PERIOD = 20
    cfg.CORRELATION_DIVERGENCE_THRESHOLD = 0.5
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


class TestComputePearson:
    def test_perfect_positive(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert compute_pearson(a, b) == pytest.approx(1.0, abs=1e-6)

    def test_perfect_negative(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [50.0, 40.0, 30.0, 20.0, 10.0]
        assert compute_pearson(a, b) == pytest.approx(-1.0, abs=1e-6)

    def test_no_correlation(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [3.0, 1.0, 4.0, 1.0, 5.0]
        corr = compute_pearson(a, b)
        assert corr is not None
        assert -0.5 < corr < 0.5

    def test_constant_series_returns_none(self):
        a = [1.0, 1.0, 1.0, 1.0]
        b = [2.0, 3.0, 4.0, 5.0]
        assert compute_pearson(a, b) is None

    def test_mismatched_length_returns_none(self):
        assert compute_pearson([1.0, 2.0], [1.0, 2.0, 3.0]) is None

    def test_too_short_returns_none(self):
        assert compute_pearson([1.0], [1.0]) is None


class TestRollingCorrelation:
    def test_first_values_are_none(self):
        a = list(range(30))
        b = list(range(30))
        roll = compute_rolling_correlation([float(x) for x in a], [float(x) for x in b], period=10)
        assert roll[:9] == [None] * 9
        assert roll[9] is not None

    def test_perfect_correlation_throughout(self):
        a = [float(x) for x in range(30)]
        b = [float(x) * 2 for x in range(30)]
        roll = compute_rolling_correlation(a, b, period=10)
        for v in roll[9:]:
            assert v == pytest.approx(1.0, abs=1e-6)

    def test_mismatched_length(self):
        roll = compute_rolling_correlation([1.0, 2.0], [1.0, 2.0, 3.0], period=2)
        assert all(v is None for v in roll)


class TestDivergenceDetection:
    def test_strong_divergence_opposite_sign(self):
        # atteso -0.85, attuale +0.3 → segno opposto
        assert detect_correlation_divergence(0.3, -0.85, 0.5) is True

    def test_divergence_below_threshold(self):
        # atteso +0.7, attuale +0.2 → 0.2 < 0.5*0.7 = 0.35
        assert detect_correlation_divergence(0.2, 0.7, 0.5) is True

    def test_no_divergence(self):
        # atteso +0.7, attuale +0.5 → ok
        assert detect_correlation_divergence(0.5, 0.7, 0.5) is False

    def test_zero_expected_no_divergence(self):
        assert detect_correlation_divergence(0.5, 0.0, 0.5) is False


class TestCorrelationMonitor:
    def setup_method(self):
        self.cfg = _make_config()
        self.mt5 = MagicMock()
        self.mon = CorrelationMonitor(self.cfg, self.mt5)

    def test_disabled_returns_none(self):
        cfg = _make_config(ENABLE_CORRELATION_MONITOR=False)
        mon = CorrelationMonitor(cfg, self.mt5)
        assert mon.check_pair("EURUSD", "USDCHF") is None

    def test_known_pair_returns_stat(self):
        # EURUSD up, USDCHF down → strong negative correlation (atteso -0.85)
        a_bars = [{"close": 1.0 + i * 0.001} for i in range(60)]
        b_bars = [{"close": 0.95 - i * 0.001} for i in range(60)]

        def side_effect(symbol, *args, **kwargs):
            return a_bars if symbol == "EURUSD" else b_bars
        self.mt5.get_ohlc.side_effect = side_effect

        stat = self.mon.check_pair("EURUSD", "USDCHF")
        assert stat is not None
        assert stat.symbol_a == "EURUSD"
        assert stat.symbol_b == "USDCHF"
        assert stat.current_corr < -0.9
        assert stat.expected_corr == -0.85
        assert stat.is_diverging is False

    def test_divergence_detected(self):
        # EURUSD e USDCHF muovono insieme → divergenza (atteso negativo)
        a_bars = [{"close": 1.0 + i * 0.001} for i in range(60)]
        b_bars = [{"close": 0.95 + i * 0.001} for i in range(60)]

        def side_effect(symbol, *args, **kwargs):
            return a_bars if symbol == "EURUSD" else b_bars
        self.mt5.get_ohlc.side_effect = side_effect

        stat = self.mon.check_pair("EURUSD", "USDCHF")
        assert stat is not None
        assert stat.is_diverging is True
        assert "divergenza" in stat.note.lower()

    def test_fetch_error_returns_none(self):
        self.mt5.get_ohlc.side_effect = Exception("network down")
        assert self.mon.check_pair("EURUSD", "USDCHF") is None

    def test_insufficient_bars_returns_none(self):
        self.mt5.get_ohlc.return_value = [{"close": 1.0}] * 10
        assert self.mon.check_pair("EURUSD", "USDCHF") is None

    def test_check_all_known_pairs(self):
        bars = [{"close": 1.0 + i * 0.001} for i in range(60)]
        self.mt5.get_ohlc.return_value = bars
        results = self.mon.check_all_known_pairs()
        assert len(results) >= 1
        assert all(isinstance(r, CorrelationStat) for r in results)
