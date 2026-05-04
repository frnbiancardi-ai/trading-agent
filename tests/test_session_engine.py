"""Test suite per SessionEngine (fase 18.5)."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from session_engine import SessionEngine
from models import SessionInfo


def _make_config(**overrides):
    cfg = MagicMock()
    cfg.ENABLE_SESSION_FILTER = True
    cfg.SESSION_QUALITY_MIN = 0.3
    cfg.SESSION_LONDON_START = 8
    cfg.SESSION_LONDON_END = 16
    cfg.SESSION_NY_START = 14
    cfg.SESSION_NY_END = 22
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _dt(hour: int, tz: str = "Europe/Rome") -> datetime:
    return datetime(2025, 1, 15, hour, 0, 0, tzinfo=ZoneInfo(tz))


class TestSessionDetection:
    def setup_method(self):
        self.eng = SessionEngine(_make_config())

    def test_asian_at_4am(self):
        assert self.eng.get_current_session(_dt(4)) == "ASIAN"

    def test_asian_at_7am(self):
        assert self.eng.get_current_session(_dt(7)) == "ASIAN"

    def test_london_at_9am(self):
        assert self.eng.get_current_session(_dt(9)) == "LONDON"

    def test_london_at_13(self):
        assert self.eng.get_current_session(_dt(13)) == "LONDON"

    def test_overlap_at_14(self):
        assert self.eng.get_current_session(_dt(14)) == "OVERLAP"

    def test_overlap_at_15(self):
        assert self.eng.get_current_session(_dt(15)) == "OVERLAP"

    def test_ny_at_16(self):
        assert self.eng.get_current_session(_dt(16)) == "NEW_YORK"

    def test_ny_at_20(self):
        assert self.eng.get_current_session(_dt(20)) == "NEW_YORK"

    def test_off_hours_at_22(self):
        assert self.eng.get_current_session(_dt(22)) == "OFF_HOURS"

    def test_off_hours_at_23(self):
        assert self.eng.get_current_session(_dt(23)) == "OFF_HOURS"


class TestSymbolQuality:
    def setup_method(self):
        self.eng = SessionEngine(_make_config())

    def test_gbpusd_best_in_london(self):
        info = self.eng.get_session_info("GBPUSD", _dt(10))
        assert info.name == "LONDON"
        assert info.quality_for_symbol == 1.0

    def test_usdjpy_good_in_asian(self):
        info = self.eng.get_session_info("USDJPY", _dt(4))
        assert info.name == "ASIAN"
        assert info.quality_for_symbol >= 0.8

    def test_audusd_good_in_overlap(self):
        info = self.eng.get_session_info("AUDUSD", _dt(15))
        assert info.name == "OVERLAP"
        assert info.quality_for_symbol >= 0.9

    def test_unknown_symbol_default(self):
        info = self.eng.get_session_info("XYZABC", _dt(15))
        assert 0.5 <= info.quality_for_symbol <= 1.0


class TestOptimalSession:
    def setup_method(self):
        self.eng = SessionEngine(_make_config())

    def test_gbpusd_london_optimal(self):
        ok, q = self.eng.is_optimal_session("GBPUSD", _dt(10))
        assert ok is True
        assert q == 1.0

    def test_gbpusd_off_hours_not_optimal(self):
        ok, q = self.eng.is_optimal_session("GBPUSD", _dt(23))
        assert ok is False
        assert q < 0.3


class TestConfidenceBoost:
    def setup_method(self):
        self.eng = SessionEngine(_make_config())

    def test_max_boost_quality_1(self):
        boost = self.eng.confidence_boost("GBPUSD", _dt(10))
        assert boost == pytest.approx(0.10, abs=0.001)

    def test_no_boost_low_quality(self):
        boost = self.eng.confidence_boost("GBPUSD", _dt(23))
        assert boost == 0.0

    def test_disabled_returns_zero(self):
        cfg = _make_config(ENABLE_SESSION_FILTER=False)
        eng = SessionEngine(cfg)
        boost = eng.confidence_boost("GBPUSD", _dt(10))
        assert boost == 0.0


class TestVolatility:
    def setup_method(self):
        self.eng = SessionEngine(_make_config())

    def test_high_volatility_overlap(self):
        info = self.eng.get_session_info("EURUSD", _dt(15))
        assert info.expected_volatility == "HIGH"

    def test_normal_volatility_london(self):
        info = self.eng.get_session_info("EURUSD", _dt(10))
        assert info.expected_volatility == "NORMAL"

    def test_low_volatility_asian(self):
        info = self.eng.get_session_info("EURUSD", _dt(4))
        assert info.expected_volatility == "LOW"
