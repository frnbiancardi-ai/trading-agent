"""Test suite per CrossAssetFilter (fase 18.4)."""
import pytest
from unittest.mock import MagicMock

from cross_asset_filter import CrossAssetFilter
from models import IntermarketContext, RegimeState


def _make_config(**overrides):
    cfg = MagicMock()
    cfg.ENABLE_CROSS_ASSET_FILTER = True
    cfg.CROSS_ASSET_VETO_ON_CONTRADICTION = True
    cfg.CROSS_ASSET_BOOST = 0.10
    cfg.CROSS_ASSET_PENALTY = 0.20
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _ctx(dollar="NEUTRAL", gold="FLAT", oil="FLAT"):
    return IntermarketContext(dollar_trend=dollar, gold_trend=gold, oil_trend=oil)


class TestEURUSD:
    def setup_method(self):
        self.f = CrossAssetFilter(_make_config())

    def test_buy_with_dollar_weak_confirms(self):
        v = self.f.check("EURUSD", "BUY", _ctx(dollar="WEAK"))
        assert v.confirmed is True
        assert v.confidence_adjustment == +0.10

    def test_buy_with_dollar_strong_contradicts(self):
        v = self.f.check("EURUSD", "BUY", _ctx(dollar="STRONG"))
        assert v.contradicts is True
        assert v.confidence_adjustment == -0.20

    def test_sell_with_dollar_strong_confirms(self):
        v = self.f.check("EURUSD", "SELL", _ctx(dollar="STRONG"))
        assert v.confirmed is True

    def test_neutral_dollar_no_signal(self):
        v = self.f.check("EURUSD", "BUY", _ctx(dollar="NEUTRAL"))
        assert v.confirmed is False
        assert v.contradicts is False


class TestGBPUSD:
    def setup_method(self):
        self.f = CrossAssetFilter(_make_config())

    def test_buy_with_oil_rising_dollar_weak_confirms(self):
        v = self.f.check("GBPUSD", "BUY", _ctx(dollar="WEAK", oil="RISING"))
        assert v.confirmed is True

    def test_buy_with_oil_falling_dollar_strong_contradicts(self):
        v = self.f.check("GBPUSD", "BUY", _ctx(dollar="STRONG", oil="FALLING"))
        assert v.contradicts is True

    def test_sell_with_oil_falling_confirms(self):
        v = self.f.check("GBPUSD", "SELL", _ctx(oil="FALLING"))
        assert v.confirmed is True


class TestAUDUSD:
    def setup_method(self):
        self.f = CrossAssetFilter(_make_config())

    def test_buy_gold_rising_dollar_weak_confirms(self):
        v = self.f.check("AUDUSD", "BUY", _ctx(dollar="WEAK", gold="RISING"))
        assert v.confirmed is True

    def test_buy_gold_falling_dollar_strong_contradicts(self):
        v = self.f.check("AUDUSD", "BUY", _ctx(dollar="STRONG", gold="FALLING"))
        assert v.contradicts is True


class TestUSDCAD:
    def setup_method(self):
        self.f = CrossAssetFilter(_make_config())

    def test_buy_oil_falling_dollar_strong_confirms(self):
        v = self.f.check("USDCAD", "BUY", _ctx(dollar="STRONG", oil="FALLING"))
        assert v.confirmed is True

    def test_sell_oil_rising_confirms(self):
        v = self.f.check("USDCAD", "SELL", _ctx(oil="RISING"))
        assert v.confirmed is True


class TestUSDJPY:
    def setup_method(self):
        self.f = CrossAssetFilter(_make_config())

    def test_buy_risk_on_confirms(self):
        regime = RegimeState(regime="RISK_ON", confidence=0.8)
        v = self.f.check("USDJPY", "BUY", _ctx(), regime)
        assert v.confirmed is True

    def test_buy_risk_off_contradicts(self):
        regime = RegimeState(regime="RISK_OFF", confidence=0.8)
        v = self.f.check("USDJPY", "BUY", _ctx(), regime)
        assert v.contradicts is True

    def test_sell_risk_off_confirms(self):
        regime = RegimeState(regime="RISK_OFF", confidence=0.8)
        v = self.f.check("USDJPY", "SELL", _ctx(), regime)
        assert v.confirmed is True

    def test_buy_gold_rising_contradicts(self):
        v = self.f.check("USDJPY", "BUY", _ctx(gold="RISING"))
        assert v.contradicts is True


class TestGold:
    def setup_method(self):
        self.f = CrossAssetFilter(_make_config())

    def test_buy_gold_dollar_weak_confirms(self):
        v = self.f.check("XAUUSD", "BUY", _ctx(dollar="WEAK"))
        assert v.confirmed is True

    def test_sell_gold_dollar_strong_confirms(self):
        v = self.f.check("XAUUSD", "SELL", _ctx(dollar="STRONG"))
        assert v.confirmed is True


class TestDisabledAndUnknown:
    def test_disabled_returns_no_signal(self):
        cfg = _make_config(ENABLE_CROSS_ASSET_FILTER=False)
        f = CrossAssetFilter(cfg)
        v = f.check("EURUSD", "BUY", _ctx(dollar="WEAK"))
        assert v.confirmed is False
        assert v.contradicts is False

    def test_unknown_symbol_no_rules(self):
        f = CrossAssetFilter(_make_config())
        v = f.check("XYZABC", "BUY", _ctx())
        assert v.confirmed is False
        assert "no_rules" in v.reason
