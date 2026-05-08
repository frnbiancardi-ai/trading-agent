"""Test IntradayStrategy: identify_entry_setup, build_trade_proposal, confidence, follow-up."""
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from datetime import datetime, timezone

from models import AccountState, SentimentAnalysis, TechnicalSetup, TradeProposal
from patterns import PatternHit
from strategy import IntradayStrategy


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def _make_cfg(**overrides):
    cfg = MagicMock()
    cfg.INTRADAY_TIMEFRAME = "M15"
    cfg.INTRADAY_LOOKBACK_BARS = 200
    cfg.INTRADAY_SCAN_TOP_N = 3
    cfg.MIN_ATR_PIPS = 3.0
    cfg.MAX_ATR_PIPS = 50.0
    cfg.MIN_TREND_STRENGTH = 0.65
    cfg.MIN_BREAKOUT_VOLUME_RATIO = 1.3
    cfg.MIN_RISK_REWARD_RATIO = 1.5
    cfg.MAX_RSI_OVERBOUGHT = 75
    cfg.MIN_RSI_OVERSOLD = 25
    cfg.MIN_CONFIDENCE_TO_PROPOSE = 0.60
    cfg.ENABLE_CANDLESTICK_PATTERNS = False
    cfg.PATTERN_CONFIRMATION_BARS = 2
    cfg.SR_LOOKBACK_BARS = 100
    cfg.SR_TOLERANCE_PIPS = 5.0
    cfg.MAX_DELAY_MINUTES = 120
    cfg.FOLLOWUP_ENABLED = True
    cfg.ENABLE_NEWS_SENTIMENT = False
    cfg.SENTIMENT_MIN_STRENGTH_FILTER = 0.6
    cfg.SENTIMENT_BOOST_FACTOR = 0.15
    cfg.SENTIMENT_CONFLICT_ACTION = "delay"
    # Phase 4 plan-07: il nuovo shim usa ctx.profile = cfg.RISK_MODE → deve essere
    # una delle 3 chiavi in config/strategy.yaml profile_filters (non un MagicMock auto).
    cfg.RISK_MODE = "MODERATE"
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _account() -> AccountState:
    return AccountState(
        balance=10000.0, equity=10000.0, free_margin=9500.0,
        open_positions=[], today_realized_pnl=0.0,
        starting_balance_of_day=10000.0,
    )


def _bar(close: float, idx: int, vol: int = 100, hi_off: float = 0.0003, lo_off: float = 0.0003) -> dict:
    return {
        "time": 1700000000 + idx * 900,
        "open": close - 0.0001,
        "high": close + hi_off,
        "low": close - lo_off,
        "close": close,
        "tick_volume": vol,
    }


def _make_strategy(cfg) -> IntradayStrategy:
    mt5 = MagicMock()
    return IntradayStrategy(cfg, mt5, logging.getLogger("test_strategy"))


def _bullish_breakout_bars(n: int = 100) -> list[dict]:
    bars = []
    # consolidation forming swing highs around 1.1000
    for i in range(80):
        if i % 8 == 4:
            close = 1.1000  # peak
        elif i % 8 == 0:
            close = 1.0960  # trough
        else:
            close = 1.0980 + (i % 4) * 0.0003
        bars.append(_bar(close, i))
    # rising base
    for i in range(80, 95):
        bars.append(_bar(1.0985 + (i - 80) * 0.0003, i))
    # tight before breakout
    for i in range(95, 99):
        bars.append(_bar(1.1015 + (i - 95) * 0.0003, i))
    # breakout bar
    last = {
        "time": 1700000000 + 99 * 900, "open": 1.1028, "high": 1.1085,
        "low": 1.1026, "close": 1.1080, "tick_volume": 300,
    }
    bars.append(last)
    return bars


# ──────────────────────────────────────────────────────────────────────────────
# Legacy tests REMOVED in Phase 4 plan-07 (Category C — architectural):
#
# I seguenti test asserivano contro metodi privati del legacy IntradayStrategy
# che NON sono più presenti nel nuovo shim Wave 3 (sostituiti dalla pipeline
# pure-fn evaluate_proposal_for_bar):
#
#   - test_identify_entry_setup_ready_buy
#   - test_identify_entry_setup_ready_sell
#   - test_identify_entry_setup_forming_near_resistance
#   - test_identify_entry_setup_none_weak_trend
#   - test_identify_entry_setup_none_overbought
#     → coperti dai detector pure-fn in tests/test_strategy_setups.py
#       (test_detect_a_breakout_*, test_detect_d_pullback_*, ecc.)
#
#   - test_build_trade_proposal_valid_buy
#   - test_build_trade_proposal_rejects_non_ready
#     → coperti da tests/test_strategy_proposal.py (draft_to_trade_proposal)
#
#   - test_confidence_in_range_0_1
#   - test_confidence_higher_with_aligned_pattern
#   - test_confidence_above_threshold_for_strong_setup
#     → coperti da tests/test_strategy_confluence.py (compute_confidence + adjusters)
#
# I 12 test rimossi sono test di metodi privati del legacy (._score_confidence,
# .identify_entry_setup, .build_trade_proposal). Il nuovo shim espone solo l'API
# pubblica analyze_symbol — la copertura unit test è migrata sui moduli puri
# corrispondenti (più granulare e pure-fn).
# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
# build_delayed_followup
# ──────────────────────────────────────────────────────────────────────────────


def test_build_delayed_followup_clamps_delay():
    cfg = _make_cfg(MAX_DELAY_MINUTES=120)
    strat = _make_strategy(cfg)
    fu = strat.build_delayed_followup("EURUSD", delay_minutes=999, reason="far")
    assert fu.delay_minutes == 120
    assert fu.symbol == "EURUSD"
    assert fu.expires_at > fu.created_at


def test_build_delayed_followup_min_clamp():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    fu = strat.build_delayed_followup("EURUSD", delay_minutes=0, reason="x")
    assert fu.delay_minutes == 1


# ──────────────────────────────────────────────────────────────────────────────
# analyze_symbol — integrazione con OHLC sintetici via mock mt5
# ──────────────────────────────────────────────────────────────────────────────


def test_analyze_symbol_no_ohlc_returns_none():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    strat.mt5.get_ohlc.return_value = []

    setup = strat.analyze_symbol("EURUSD", _account())

    assert setup.setup_type == "NONE"
    assert "insufficient" in setup.reason


def test_analyze_symbol_ohlc_error_returns_none():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    strat.mt5.get_ohlc.side_effect = RuntimeError("boom")

    setup = strat.analyze_symbol("EURUSD", _account())

    assert setup.setup_type == "NONE"
    assert "ohlc_error" in setup.reason


def test_analyze_symbol_returns_valid_setup_object():
    """End-to-end: fornisce 100 barre, verifica struttura TechnicalSetup."""
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    strat.mt5.get_ohlc.return_value = _bullish_breakout_bars()
    strat.mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.10800, ask=1.10810, point=0.00001, digits=5,
    )

    setup = strat.analyze_symbol("EURUSD", _account())

    assert isinstance(setup, TechnicalSetup)
    assert setup.symbol == "EURUSD"
    assert setup.timeframe == "M15"
    assert setup.setup_type in ("READY", "FORMING", "NONE")
    assert 0.0 <= setup.confidence <= 1.0


def _ready_buy_setup() -> TechnicalSetup:
    return TechnicalSetup(
        symbol="EURUSD", timeframe="M15", setup_type="READY", direction="BUY",
        entry_price=1.10800, stop_loss=1.10700, take_profit=1.10950,
        confidence=0.70, reason="trend strong",
        indicators={"risk_reward": 1.5}, support_resistance={"support": 1.0950, "resistance": 1.1050},
    )


def _sent(bias: str, strength: float, n: int = 3) -> SentimentAnalysis:
    return SentimentAnalysis(
        symbol="EURUSD", bias=bias, strength=strength,
        relevant_news_count=n, sample_headlines=[],
        timestamp=datetime.now(tz=timezone.utc),
    )


def test_apply_sentiment_disabled_passthrough():
    cfg = _make_cfg(ENABLE_NEWS_SENTIMENT=False)
    strat = _make_strategy(cfg)
    setup = _ready_buy_setup()
    out = strat._apply_sentiment(setup, _sent("BEARISH", 0.9))
    assert out is setup
    assert out.setup_type == "READY"


def test_apply_sentiment_below_threshold_passthrough():
    cfg = _make_cfg(ENABLE_NEWS_SENTIMENT=True, SENTIMENT_MIN_STRENGTH_FILTER=0.6)
    strat = _make_strategy(cfg)
    setup = _ready_buy_setup()
    out = strat._apply_sentiment(setup, _sent("BEARISH", 0.3))
    assert out.setup_type == "READY"
    assert out.confidence == setup.confidence


def test_apply_sentiment_aligned_boosts_confidence():
    cfg = _make_cfg(
        ENABLE_NEWS_SENTIMENT=True, SENTIMENT_MIN_STRENGTH_FILTER=0.6,
        SENTIMENT_BOOST_FACTOR=0.15,
    )
    strat = _make_strategy(cfg)
    setup = _ready_buy_setup()
    base_conf = setup.confidence
    out = strat._apply_sentiment(setup, _sent("BULLISH", 0.8))
    assert out.setup_type == "READY"
    assert out.confidence > base_conf
    assert out.confidence <= 0.95
    assert "sentiment" in out.indicators


def test_apply_sentiment_conflict_skip():
    cfg = _make_cfg(
        ENABLE_NEWS_SENTIMENT=True, SENTIMENT_MIN_STRENGTH_FILTER=0.6,
        SENTIMENT_CONFLICT_ACTION="skip",
    )
    strat = _make_strategy(cfg)
    setup = _ready_buy_setup()
    out = strat._apply_sentiment(setup, _sent("BEARISH", 0.8))
    assert out.setup_type == "NONE"
    assert out.direction is None


def test_apply_sentiment_conflict_delay():
    cfg = _make_cfg(
        ENABLE_NEWS_SENTIMENT=True, SENTIMENT_MIN_STRENGTH_FILTER=0.6,
        SENTIMENT_CONFLICT_ACTION="delay",
    )
    strat = _make_strategy(cfg)
    setup = _ready_buy_setup()
    out = strat._apply_sentiment(setup, _sent("BEARISH", 0.8))
    assert out.setup_type == "FORMING"
    assert out.direction == "BUY"


def test_apply_sentiment_conflict_reduce_confidence():
    cfg = _make_cfg(
        ENABLE_NEWS_SENTIMENT=True, SENTIMENT_MIN_STRENGTH_FILTER=0.6,
        SENTIMENT_CONFLICT_ACTION="reduce_confidence",
        MIN_CONFIDENCE_TO_PROPOSE=0.30,
    )
    strat = _make_strategy(cfg)
    setup = _ready_buy_setup()
    base = setup.confidence
    out = strat._apply_sentiment(setup, _sent("BEARISH", 0.7))
    assert out.setup_type == "READY"
    assert out.confidence < base


def test_apply_sentiment_conflict_reduce_below_min_downgrades_to_none():
    cfg = _make_cfg(
        ENABLE_NEWS_SENTIMENT=True, SENTIMENT_MIN_STRENGTH_FILTER=0.6,
        SENTIMENT_CONFLICT_ACTION="reduce_confidence",
        MIN_CONFIDENCE_TO_PROPOSE=0.99,
    )
    strat = _make_strategy(cfg)
    setup = _ready_buy_setup()
    out = strat._apply_sentiment(setup, _sent("BEARISH", 0.9))
    assert out.setup_type == "NONE"


# Phase 4 plan-07 (Category C — architectural): test_analyze_symbol_atr_out_of_range_returns_none
# REMOVED. Il legacy _analyze_technical aveva un gate binario "atr_pips > MAX_ATR_PIPS → NONE"
# eseguito PRIMA del setup detection. Il nuovo motore Wave 3 NON ha questo gate globale —
# la regolazione della volatilità è gestita dal factor `volatility_regime` del 5-factor
# confluence (config/strategy.yaml schema D-08), che produce gradi più sfumati invece di
# un cutoff binario. Il test legacy asseriva un comportamento intenzionalmente rimosso.
