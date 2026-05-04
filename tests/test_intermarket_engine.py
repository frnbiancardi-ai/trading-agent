"""Test suite per IntermarketEngine (fase 18.1)."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from intermarket_engine import IntermarketEngine, _compute_trend_from_sma, _last_valid
from models import IntermarketContext


# ── Helper fixtures ──────────────────────────────────────────────────────────

def _make_config(**overrides):
    """Config mock con default fase 18."""
    cfg = MagicMock()
    cfg.ENABLE_INTERMARKET_FILTER = True
    cfg.INTERMARKET_TIMEFRAME = "H4"
    cfg.INTERMARKET_LOOKBACK_BARS = 100
    cfg.INTERMARKET_SYMBOLS = ["XAUUSD", "USOIL"]
    cfg.DXY_PROXY_SYMBOL = "EURUSD"
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_bars_rising(n: int = 60, start: float = 1.0, step: float = 0.01):
    """Genera n barre con close in salita costante (trend RISING)."""
    return [{"close": start + i * step} for i in range(n)]


def _make_bars_falling(n: int = 60, start: float = 2.0, step: float = 0.01):
    """Genera n barre con close in discesa costante (trend FALLING)."""
    return [{"close": start - i * step} for i in range(n)]


def _make_bars_flat(n: int = 60, base: float = 1.5):
    """Genera n barre con close piatto (oscillazione minima)."""
    return [{"close": base + (0.001 if i % 2 == 0 else -0.001)} for i in range(n)]


# ── Test _last_valid ─────────────────────────────────────────────────────────

class TestLastValid:
    def test_returns_last_non_none(self):
        assert _last_valid([1.0, 2.0, None, 3.0]) == 3.0

    def test_skips_trailing_nones(self):
        assert _last_valid([1.0, 2.0, None]) == 2.0

    def test_all_none_returns_none(self):
        assert _last_valid([None, None, None]) is None

    def test_empty_returns_none(self):
        assert _last_valid([]) is None

    def test_single_value(self):
        assert _last_valid([42.0]) == 42.0


# ── Test _compute_trend_from_sma ────────────────────────────────────────────

class TestComputeTrendFromSma:
    def test_rising_trend(self):
        closes = _make_bars_rising(60)
        closes_vals = [b["close"] for b in closes]
        trend = _compute_trend_from_sma(closes_vals)
        assert trend == "RISING"

    def test_falling_trend(self):
        closes = _make_bars_falling(60)
        closes_vals = [b["close"] for b in closes]
        trend = _compute_trend_from_sma(closes_vals)
        assert trend == "FALLING"

    def test_flat_trend(self):
        closes = _make_bars_flat(60)
        closes_vals = [b["close"] for b in closes]
        trend = _compute_trend_from_sma(closes_vals)
        assert trend == "FLAT"

    def test_insufficient_data_returns_neutral(self):
        closes = [1.0] * 30  # < 50
        trend = _compute_trend_from_sma(closes)
        assert trend == "NEUTRAL"

    def test_custom_periods(self):
        closes = _make_bars_rising(80)
        closes_vals = [b["close"] for b in closes]
        trend = _compute_trend_from_sma(closes_vals, period_fast=10, period_slow=30)
        assert trend == "RISING"


# ── Test IntermarketEngine ──────────────────────────────────────────────────

class TestIntermarketEngine:
    def setup_method(self):
        self.cfg = _make_config()
        self.mt5 = MagicMock()
        self.engine = IntermarketEngine(self.cfg, self.mt5)

    def test_disabled_returns_neutral(self):
        """Filtro disabilitato → tutto NEUTRAL/FLAT."""
        self.cfg.ENABLE_INTERMARKET_FILTER = False
        ctx = self.engine.get_context()
        assert ctx.dollar_trend == "NEUTRAL"
        assert ctx.gold_trend == "FLAT"
        assert ctx.oil_trend == "FLAT"

    def test_dollar_strong_when_eurusd_falling(self):
        """EUR/USD falling = Dollar STRONG (proxy inverso)."""
        bars_falling = _make_bars_falling(60)
        self.mt5.get_ohlc.return_value = bars_falling
        ctx = self.engine.get_context()
        assert ctx.dollar_trend == "STRONG"

    def test_dollar_weak_when_eurusd_rising(self):
        """EUR/USD rising = Dollar WEAK (proxy inverso)."""
        bars_rising = _make_bars_rising(60)
        self.mt5.get_ohlc.return_value = bars_rising
        ctx = self.engine.get_context()
        assert ctx.dollar_trend == "WEAK"

    def test_dollar_neutral_on_fetch_error(self):
        """Errore fetch EURUSD → Dollar NEUTRAL."""
        self.mt5.get_ohlc.side_effect = Exception("connection lost")
        ctx = self.engine.get_context()
        assert ctx.dollar_trend == "NEUTRAL"

    def test_dollar_neutral_on_insufficient_bars(self):
        """Poche barre EURUSD → Dollar NEUTRAL."""
        self.mt5.get_ohlc.return_value = [{"close": 1.0}] * 30
        ctx = self.engine.get_context()
        assert ctx.dollar_trend == "NEUTRAL"

    def test_gold_rising(self):
        """XAUUSD rising → gold_trend RISING."""
        bars_rising = _make_bars_rising(60, start=1800.0, step=5.0)
        self.mt5.get_ohlc.return_value = bars_rising
        ctx = self.engine.get_context()
        assert ctx.gold_trend == "RISING"

    def test_oil_falling(self):
        """USOIL falling → oil_trend FALLING."""
        bars_falling = _make_bars_falling(60, start=80.0, step=0.5)
        self.mt5.get_ohlc.return_value = bars_falling
        ctx = self.engine.get_context()
        assert ctx.oil_trend == "FALLING"

    def test_asset_trend_flat_on_error(self):
        """Errore fetch Gold/Oil → trend FLAT."""
        self.mt5.get_ohlc.side_effect = Exception("timeout")
        ctx = self.engine.get_context()
        assert ctx.gold_trend == "FLAT"
        assert ctx.oil_trend == "FLAT"

    def test_asset_trend_flat_on_insufficient_bars(self):
        """Poche barre Gold/Oil → FLAT."""
        self.mt5.get_ohlc.return_value = [{"close": 1.0}] * 20
        ctx = self.engine.get_context()
        assert ctx.gold_trend == "FLAT"
        assert ctx.oil_trend == "FLAT"

    def test_context_has_timestamp(self):
        """Output ha timestamp valido."""
        self.mt5.get_ohlc.return_value = _make_bars_rising(60)
        ctx = self.engine.get_context()
        assert isinstance(ctx.timestamp, datetime)

    def test_find_oil_symbol_default(self):
        """Default oil symbol = USOIL."""
        self.cfg.INTERMARKET_SYMBOLS = ["XAUUSD"]
        sym = self.engine._find_oil_symbol()
        assert sym == "USOIL"

    def test_find_oil_symbol_wti(self):
        """Trova WTI nei simboli."""
        self.cfg.INTERMARKET_SYMBOLS = ["XAUUSD", "WTI.f"]
        sym = self.engine._find_oil_symbol()
        assert sym == "WTI.f"

    def test_find_oil_symbol_xtiusd(self):
        """Trova XTIUSD nei simboli."""
        self.cfg.INTERMARKET_SYMBOLS = ["XAUUSD", "XTIUSD"]
        sym = self.engine._find_oil_symbol()
        assert sym == "XTIUSD"

    def test_different_results_per_asset(self):
        """Ogni asset può avere trend diverso."""
        def side_effect(symbol, *args, **kwargs):
            if symbol == "EURUSD":
                return _make_bars_rising(60)  # EUR up = Dollar WEAK
            elif symbol == "XAUUSD":
                return _make_bars_falling(60, start=2000, step=5)  # Gold falling
            else:
                return _make_bars_rising(60, start=70, step=0.5)  # Oil rising
        self.mt5.get_ohlc.side_effect = side_effect
        ctx = self.engine.get_context()
        assert ctx.dollar_trend == "WEAK"
        assert ctx.gold_trend == "FALLING"
        assert ctx.oil_trend == "RISING"

    def test_context_is_dataclass_instance(self):
        """Output è IntermarketContext."""
        self.mt5.get_ohlc.return_value = _make_bars_flat(60)
        ctx = self.engine.get_context()
        assert isinstance(ctx, IntermarketContext)
