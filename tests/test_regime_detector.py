"""Test suite per RegimeDetector (fase 18.2)."""
import pytest
from unittest.mock import MagicMock

from regime_detector import RegimeDetector
from models import IntermarketContext, RegimeState


def _make_config(**overrides):
    cfg = MagicMock()
    cfg.ENABLE_REGIME_DETECTION = True
    cfg.REGIME_RISK_OFF_VETO = True
    cfg.REGIME_CONFIDENCE_PENALTY = 0.15
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _ctx(dollar="NEUTRAL", gold="FLAT", oil="FLAT"):
    return IntermarketContext(
        dollar_trend=dollar, gold_trend=gold, oil_trend=oil
    )


class TestRegimeClassification:
    def setup_method(self):
        self.det = RegimeDetector(_make_config())

    def test_inflationary_gold_oil_rising(self):
        state = self.det.detect(_ctx(gold="RISING", oil="RISING"))
        assert state.regime == "INFLATIONARY"
        assert "inflation_pressure" in state.warning_signals

    def test_risk_off_gold_rising_dollar_strong(self):
        state = self.det.detect(_ctx(dollar="STRONG", gold="RISING", oil="FALLING"))
        assert state.regime == "RISK_OFF"
        assert state.confidence >= 0.8
        assert "flight_to_safety" in state.warning_signals

    def test_risk_off_gold_rising_oil_falling(self):
        state = self.det.detect(_ctx(dollar="NEUTRAL", gold="RISING", oil="FALLING"))
        assert state.regime == "RISK_OFF"

    def test_risk_on_oil_rising_dollar_weak_gold_falling(self):
        state = self.det.detect(_ctx(dollar="WEAK", gold="FALLING", oil="RISING"))
        assert state.regime == "RISK_ON"
        assert state.confidence >= 0.7

    def test_risk_on_weak_dollar_oil_rising(self):
        state = self.det.detect(_ctx(dollar="WEAK", gold="FLAT", oil="RISING"))
        assert state.regime == "RISK_ON"

    def test_risk_off_weak_dollar_dominance(self):
        state = self.det.detect(_ctx(dollar="STRONG", gold="FLAT", oil="FALLING"))
        assert state.regime == "RISK_OFF"
        assert "dollar_dominance" in state.warning_signals

    def test_neutral_default(self):
        state = self.det.detect(_ctx())
        assert state.regime == "NEUTRAL"

    def test_disabled_returns_neutral(self):
        cfg = _make_config(ENABLE_REGIME_DETECTION=False)
        det = RegimeDetector(cfg)
        state = det.detect(_ctx(gold="RISING", oil="RISING"))
        assert state.regime == "NEUTRAL"


class TestVetoLogic:
    def setup_method(self):
        self.det = RegimeDetector(_make_config())

    def test_veto_buy_risk_off_audusd(self):
        state = RegimeState(regime="RISK_OFF", confidence=0.8)
        assert self.det.should_veto_buy(state, "AUDUSD") is True

    def test_no_veto_buy_risk_off_eurusd(self):
        """EURUSD non è commodity ccy → no veto."""
        state = RegimeState(regime="RISK_OFF", confidence=0.8)
        assert self.det.should_veto_buy(state, "EURUSD") is False

    def test_veto_sell_risk_on_usdjpy(self):
        state = RegimeState(regime="RISK_ON", confidence=0.7)
        assert self.det.should_veto_sell(state, "USDJPY") is True

    def test_veto_sell_risk_on_usdchf(self):
        state = RegimeState(regime="RISK_ON", confidence=0.7)
        assert self.det.should_veto_sell(state, "USDCHF") is True

    def test_no_veto_neutral_regime(self):
        state = RegimeState(regime="NEUTRAL", confidence=0.3)
        assert self.det.should_veto_buy(state, "AUDUSD") is False
        assert self.det.should_veto_sell(state, "USDJPY") is False

    def test_veto_disabled(self):
        cfg = _make_config(REGIME_RISK_OFF_VETO=False)
        det = RegimeDetector(cfg)
        state = RegimeState(regime="RISK_OFF", confidence=0.8)
        assert det.should_veto_buy(state, "AUDUSD") is False


class TestConfidencePenalty:
    def setup_method(self):
        self.det = RegimeDetector(_make_config())

    def test_penalty_buy_audusd_risk_off(self):
        state = RegimeState(regime="RISK_OFF", confidence=0.8)
        pen = self.det.confidence_penalty(state, "BUY", "AUDUSD")
        assert pen == 0.15

    def test_penalty_sell_jpy_risk_on(self):
        state = RegimeState(regime="RISK_ON", confidence=0.7)
        pen = self.det.confidence_penalty(state, "SELL", "USDJPY")
        assert pen == 0.15

    def test_no_penalty_aligned_direction(self):
        state = RegimeState(regime="RISK_OFF", confidence=0.8)
        # SELL AUDUSD in RISK_OFF è allineato (commodity ccy down)
        pen = self.det.confidence_penalty(state, "SELL", "AUDUSD")
        assert pen == 0.0

    def test_no_penalty_neutral_regime(self):
        state = RegimeState(regime="NEUTRAL", confidence=0.3)
        pen = self.det.confidence_penalty(state, "BUY", "AUDUSD")
        assert pen == 0.0
