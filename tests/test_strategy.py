"""Test IntradayStrategy: identify_entry_setup, build_trade_proposal, confidence, follow-up."""
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from datetime import datetime, timezone

from models import AccountState, SentimentAnalysis, TechnicalSetup, TradeProposal
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
    cfg.ENABLE_VOLATILITY_SQUEEZE_SETUP = False
    cfg.BB_PERIOD = 20
    cfg.BB_K = 2.0
    cfg.BB_SQUEEZE_LOOKBACK = 100
    cfg.BB_SQUEEZE_PERCENTILE = 0.2
    cfg.SQUEEZE_ENTRY_BUFFER_ATR = 0.1
    cfg.SQUEEZE_SL_BUFFER_ATR = 0.2
    cfg.ENABLE_PULLBACK_SETUP = False
    cfg.BREAKOUT_LOOKBACK_BARS = 20
    cfg.PULLBACK_TOLERANCE_ATR_MULTIPLE = 0.5
    cfg.PULLBACK_MIN_BARS_AFTER_BREAKOUT = 2
    cfg.PULLBACK_MAX_BARS_AFTER_BREAKOUT = 8
    cfg.PULLBACK_REQUIRE_VOLUME_CONTRACTION = True
    cfg.PULLBACK_ENTRY_BUFFER_ATR = 0.1
    cfg.PULLBACK_SL_BUFFER_ATR = 0.1
    # Phase 17.4 — divergence + MTF
    cfg.ENABLE_RSI_DIVERGENCE_VETO = False
    cfg.DIVERGENCE_LOOKBACK = 20
    cfg.RSI_PERIOD = 14
    cfg.MTF_TIMEFRAME = "H1"
    cfg.MTF_BARS = 100
    cfg.MTF_BIAS_WEIGHT = 0.10
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
# identify_entry_setup
# ──────────────────────────────────────────────────────────────────────────────


def test_identify_entry_setup_ready_buy():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)

    indicators = {
        "sma_20": 1.1010, "sma_50": 1.0980, "rsi_14": 60.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.80, "breakout": "CLEAN",
        "patterns": [], "last_close": 1.1080, "pip_size": 0.0001,
    }
    sr = {"support": 1.0950, "resistance": 1.1050}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] == "READY"
    assert decision["direction"] == "BUY"
    assert decision.get("subtype") == "breakout"


def test_identify_entry_setup_squeeze_long_takes_priority():
    cfg = _make_cfg(ENABLE_VOLATILITY_SQUEEZE_SETUP=True)
    strat = _make_strategy(cfg)

    indicators = {
        "sma_20": 1.1010, "sma_50": 1.0980, "rsi_14": 55.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.50, "breakout": "NONE",
        "patterns": [], "last_close": 1.1020, "pip_size": 0.0001,
        "squeeze": {
            "squeeze": True, "type": "NR7", "strength": 0.5,
            "signals": ["NR7", "BB_SQUEEZE"],
        },
    }
    sr = {"support": 1.0900, "resistance": 1.1100}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] == "READY"
    assert decision["direction"] == "BUY"
    assert decision.get("subtype") == "squeeze"


def test_identify_entry_setup_squeeze_disabled_falls_through():
    cfg = _make_cfg(ENABLE_VOLATILITY_SQUEEZE_SETUP=False)
    strat = _make_strategy(cfg)

    indicators = {
        "sma_20": 1.1010, "sma_50": 1.0980, "rsi_14": 55.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.50, "breakout": "NONE",
        "patterns": [], "last_close": 1.1020, "pip_size": 0.0001,
        "squeeze": {
            "squeeze": True, "type": "NR7", "strength": 0.5,
            "signals": ["NR7"],
        },
    }
    sr = {"support": 1.0900, "resistance": 1.1100}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] != "READY" or decision.get("subtype") != "squeeze"


def test_identify_entry_setup_squeeze_skipped_if_no_alignment():
    cfg = _make_cfg(ENABLE_VOLATILITY_SQUEEZE_SETUP=True)
    strat = _make_strategy(cfg)

    # last_close < sma20 < sma50 NON è bullish, MAs non allineate
    indicators = {
        "sma_20": 1.1010, "sma_50": 1.0980, "rsi_14": 55.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.40, "breakout": "NONE",
        "patterns": [], "last_close": 1.0950, "pip_size": 0.0001,
        "squeeze": {
            "squeeze": True, "type": "NR7", "strength": 0.5,
            "signals": ["NR7"],
        },
    }
    sr = {"support": 1.0900, "resistance": 1.1100}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision.get("subtype") != "squeeze"


def test_identify_entry_setup_pullback_long_takes_priority_over_squeeze():
    cfg = _make_cfg(
        ENABLE_PULLBACK_SETUP=True,
        ENABLE_VOLATILITY_SQUEEZE_SETUP=True,
    )
    strat = _make_strategy(cfg)

    indicators = {
        "sma_20": 1.1010, "sma_50": 1.0980, "rsi_14": 58.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.50, "breakout": "NONE",
        "patterns": [], "last_close": 1.1020, "pip_size": 0.0001,
        "squeeze": {
            "squeeze": True, "type": "NR7", "strength": 0.5,
            "signals": ["NR7"],
        },
        "pullback": {
            "pullback": True, "direction": "BUY",
            "breakout_level": 1.1010, "breakout_index": 100,
            "bars_since_breakout": 4,
            "trigger_pattern": "INSIDE",
            "reason": "pullback_long_test",
        },
    }
    sr = {"support": 1.0900, "resistance": 1.1100}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] == "READY"
    assert decision["direction"] == "BUY"
    assert decision.get("subtype") == "pullback"


def test_identify_entry_setup_pullback_short_aligned():
    cfg = _make_cfg(ENABLE_PULLBACK_SETUP=True)
    strat = _make_strategy(cfg)

    indicators = {
        "sma_20": 1.0990, "sma_50": 1.1020, "rsi_14": 42.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.50, "breakout": "NONE",
        "patterns": [], "last_close": 1.0980, "pip_size": 0.0001,
        "squeeze": {"squeeze": False, "type": "NONE", "strength": 0.0, "signals": []},
        "pullback": {
            "pullback": True, "direction": "SELL",
            "breakout_level": 1.0995, "breakout_index": 100,
            "bars_since_breakout": 3,
            "trigger_pattern": "INSIDE",
            "reason": "pullback_short_test",
        },
    }
    sr = {"support": 1.0900, "resistance": 1.1100}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] == "READY"
    assert decision["direction"] == "SELL"
    assert decision.get("subtype") == "pullback"


def test_identify_entry_setup_pullback_skipped_if_misaligned():
    cfg = _make_cfg(ENABLE_PULLBACK_SETUP=True)
    strat = _make_strategy(cfg)

    # pullback BUY ma MAs allineate al ribasso → skip pullback
    indicators = {
        "sma_20": 1.0990, "sma_50": 1.1020, "rsi_14": 42.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.50, "breakout": "NONE",
        "patterns": [], "last_close": 1.0980, "pip_size": 0.0001,
        "squeeze": {"squeeze": False, "type": "NONE", "strength": 0.0, "signals": []},
        "pullback": {
            "pullback": True, "direction": "BUY",
            "breakout_level": 1.0995, "breakout_index": 100,
            "bars_since_breakout": 3,
            "trigger_pattern": "INSIDE",
            "reason": "pullback_long_test",
        },
    }
    sr = {"support": 1.0900, "resistance": 1.1100}
    decision = strat.identify_entry_setup([], indicators, sr, [])
    assert decision.get("subtype") != "pullback"


def test_compute_levels_pullback_uses_last_bar():
    cfg = _make_cfg(ENABLE_PULLBACK_SETUP=True)
    strat = _make_strategy(cfg)

    last_bar = {"open": 1.1010, "high": 1.1015, "low": 1.1008, "close": 1.1011}
    entry, sl, tp = strat._compute_levels(
        direction="BUY", last_close=1.1011, atr_val=0.0010,
        sr={"support": 1.0950, "resistance": 1.1100}, pip_size=0.0001,
        subtype="pullback", last_bar=last_bar,
    )
    # entry = 1.1015 + 0.0001 = 1.1016, sl = 1.1008 - 0.0001 = 1.1007
    assert abs(entry - 1.1016) < 1e-6
    assert abs(sl - 1.1007) < 1e-6
    assert tp > entry


def test_compute_levels_squeeze_uses_last_bar():
    cfg = _make_cfg(ENABLE_VOLATILITY_SQUEEZE_SETUP=True)
    strat = _make_strategy(cfg)

    last_bar = {"open": 1.1000, "high": 1.1020, "low": 1.0990, "close": 1.1010}
    entry, sl, tp = strat._compute_levels(
        direction="BUY", last_close=1.1010, atr_val=0.0020,
        sr={"support": 1.0950, "resistance": 1.1100}, pip_size=0.0001,
        subtype="squeeze", last_bar=last_bar,
    )
    # entry = high + 0.1*ATR = 1.1020 + 0.0002 = 1.1022
    # sl    = low  - 0.2*ATR = 1.0990 - 0.0004 = 1.0986
    assert abs(entry - 1.1022) < 1e-6
    assert abs(sl - 1.0986) < 1e-6
    assert tp > entry  # long TP sopra entry


def test_identify_entry_setup_ready_sell():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)

    indicators = {
        "sma_20": 1.0990, "sma_50": 1.1020, "rsi_14": 40.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.80, "breakout": "CLEAN",
        "patterns": [], "last_close": 1.0920, "pip_size": 0.0001,
    }
    sr = {"support": 1.0950, "resistance": 1.1050}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] == "READY"
    assert decision["direction"] == "SELL"


def test_identify_entry_setup_forming_near_resistance():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)

    # last_close just below resistance, within tolerance
    indicators = {
        "sma_20": 1.1010, "sma_50": 1.0980, "rsi_14": 58.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.70, "breakout": "NONE",
        "patterns": [], "last_close": 1.1048, "pip_size": 0.0001,
    }
    sr = {"support": 1.0950, "resistance": 1.1050}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] == "FORMING"
    assert decision["direction"] == "BUY"


def test_identify_entry_setup_none_weak_trend():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)

    indicators = {
        "sma_20": 1.1000, "sma_50": 1.1000, "rsi_14": 50.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.20, "breakout": "NONE",
        "patterns": [], "last_close": 1.1000, "pip_size": 0.0001,
    }
    sr = {"support": 1.0950, "resistance": 1.1050}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] == "NONE"


def test_identify_entry_setup_none_overbought():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)

    indicators = {
        "sma_20": 1.1010, "sma_50": 1.0980, "rsi_14": 80.0,
        "atr_14": 0.0010, "atr_pips": 10.0,
        "trend_strength": 0.80, "breakout": "CLEAN",
        "patterns": [], "last_close": 1.1080, "pip_size": 0.0001,
    }
    sr = {"support": 1.0950, "resistance": 1.1050}
    decision = strat.identify_entry_setup([], indicators, sr, [])

    assert decision["type"] == "NONE"
    assert "overbought" in decision["reason"]


# ──────────────────────────────────────────────────────────────────────────────
# build_trade_proposal
# ──────────────────────────────────────────────────────────────────────────────


def test_build_trade_proposal_valid_buy():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    setup = TechnicalSetup(
        symbol="EURUSD", timeframe="M15", setup_type="READY", direction="BUY",
        entry_price=1.10800, stop_loss=1.10700, take_profit=1.10950,
        confidence=0.72, reason="trend strong",
        indicators={"risk_reward": 1.5}, support_resistance={"support": 1.0950, "resistance": 1.1050},
    )
    proposal = strat.build_trade_proposal("EURUSD", setup, account_state=_account())

    assert isinstance(proposal, TradeProposal)
    assert proposal.symbol == "EURUSD"
    assert proposal.direction == "BUY"
    assert proposal.entry_price == 1.10800
    assert proposal.stop_loss_price == 1.10700
    assert proposal.take_profit_price == 1.10950
    assert proposal.comment == "python_strategy"
    assert proposal.confidence == 0.72


def test_build_trade_proposal_rejects_non_ready():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    setup = TechnicalSetup(
        symbol="EURUSD", timeframe="M15", setup_type="NONE", direction=None,
        entry_price=None, stop_loss=None, take_profit=None,
        confidence=0.0, reason="noop",
    )
    with pytest.raises(ValueError):
        strat.build_trade_proposal("EURUSD", setup)


# ──────────────────────────────────────────────────────────────────────────────
# Confidence
# ──────────────────────────────────────────────────────────────────────────────


def test_confidence_in_range_0_1():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    score = strat._score_confidence(
        trend_strength=0.8, patterns=[],
        breakout="CLEAN", rr=2.0, direction="BUY",
    )
    assert 0.0 <= score <= 1.0


def test_confidence_higher_with_aligned_pattern():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    base = strat._score_confidence(
        trend_strength=0.8, patterns=[], breakout="CLEAN", rr=2.0, direction="BUY",
    )
    boosted = strat._score_confidence(
        trend_strength=0.8,
        patterns=[{"pattern": "hammer", "bar_index": -1, "direction": "bullish"}],
        breakout="CLEAN", rr=2.0, direction="BUY",
    )
    assert boosted > base


def test_confidence_above_threshold_for_strong_setup():
    cfg = _make_cfg()
    strat = _make_strategy(cfg)
    score = strat._score_confidence(
        trend_strength=0.85,
        patterns=[{"pattern": "hammer", "bar_index": -1, "direction": "bullish"}],
        breakout="CLEAN", rr=2.5, direction="BUY",
    )
    assert score >= cfg.MIN_CONFIDENCE_TO_PROPOSE


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


def test_analyze_symbol_atr_out_of_range_returns_none():
    cfg = _make_cfg(MAX_ATR_PIPS=2.0)
    strat = _make_strategy(cfg)
    strat.mt5.get_ohlc.return_value = _bullish_breakout_bars()
    strat.mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.10800, ask=1.10810, point=0.00001, digits=5,
    )

    setup = strat.analyze_symbol("EURUSD", _account())
    assert setup.setup_type == "NONE"
    assert "atr_out_of_range" in setup.reason
