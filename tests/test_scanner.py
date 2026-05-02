"""Test MultiSymbolScanner: light_scan, scan_universe, deep_analyze_top_candidates."""
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from models import (
    AccountState,
    DelayedFollowUpRequest,
    ScanResult,
    StrategyOutcome,
    TechnicalSetup,
    TradeProposal,
)
from scanner import MultiSymbolScanner


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
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _account() -> AccountState:
    return AccountState(
        balance=10000.0, equity=10000.0, free_margin=9500.0,
        open_positions=[], today_realized_pnl=0.0,
        starting_balance_of_day=10000.0,
    )


def _bar(close: float, idx: int, vol: int = 100) -> dict:
    return {
        "time": 1700000000 + idx * 900,
        "open": close - 0.0001,
        "high": close + 0.0003,
        "low": close - 0.0003,
        "close": close,
        "tick_volume": vol,
    }


def _trending_bars(start: float, step: float, n: int = 60, vol: int = 100) -> list[dict]:
    return [_bar(start + i * step, i, vol) for i in range(n)]


def _flat_bars(level: float, n: int = 60) -> list[dict]:
    return [
        {
            "time": 1700000000 + i * 900,
            "open": level, "high": level + 0.00005, "low": level - 0.00005,
            "close": level, "tick_volume": 100,
        }
        for i in range(n)
    ]


def _make_scanner(cfg, mt5_mock=None, strategy_mock=None) -> MultiSymbolScanner:
    if mt5_mock is None:
        mt5_mock = MagicMock()
    if strategy_mock is None:
        strategy_mock = MagicMock()
    return MultiSymbolScanner(cfg, mt5_mock, strategy_mock, logging.getLogger("test_scanner"))


# ──────────────────────────────────────────────────────────────────────────────
# light_scan
# ──────────────────────────────────────────────────────────────────────────────


def test_light_scan_no_data_returns_none():
    cfg = _make_cfg()
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = []
    scanner = _make_scanner(cfg, mt5)

    result = scanner.light_scan("EURUSD")
    assert result is None


def test_light_scan_bullish_trend_classifies_correctly():
    cfg = _make_cfg()
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = _trending_bars(1.0900, 0.0005, n=60)
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.10000, ask=1.10010, point=0.00001, digits=5,
    )
    scanner = _make_scanner(cfg, mt5)

    result = scanner.light_scan("EURUSD")
    assert isinstance(result, ScanResult)
    assert result.symbol == "EURUSD"
    assert result.trend_bias in ("BULLISH", "NEUTRAL")
    assert result.spread_state == "ACCEPTABLE"
    assert result.candidate_score >= 0.0


def test_light_scan_wide_spread_penalizes_score():
    cfg = _make_cfg()
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = _trending_bars(1.0900, 0.0005, n=60)
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.10000, ask=1.10100, point=0.00001, digits=5,  # 10 pip spread
    )
    scanner = _make_scanner(cfg, mt5)

    result = scanner.light_scan("EURUSD")
    assert result.spread_state == "WIDE"
    assert any("spread_wide" in w for w in result.warnings)


def test_light_scan_low_volatility_flagged():
    cfg = _make_cfg()
    mt5 = MagicMock()
    # Flat bars → atr near zero
    mt5.get_ohlc.return_value = _flat_bars(1.1000, n=60)
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.10000, ask=1.10010, point=0.00001, digits=5,
    )
    scanner = _make_scanner(cfg, mt5)

    result = scanner.light_scan("EURUSD")
    assert result.volatility_state == "LOW"


# ──────────────────────────────────────────────────────────────────────────────
# scan_universe
# ──────────────────────────────────────────────────────────────────────────────


def test_scan_universe_returns_top_n_sorted_desc():
    cfg = _make_cfg(INTRADAY_SCAN_TOP_N=2)
    scanner = _make_scanner(cfg)

    fake_results = [
        ScanResult(symbol="A", trend_bias="BULLISH", momentum_bias="BULLISH",
                   volatility_state="NORMAL", spread_state="ACCEPTABLE",
                   regime="TREND", candidate_score=0.5, warnings=[]),
        ScanResult(symbol="B", trend_bias="BULLISH", momentum_bias="BULLISH",
                   volatility_state="NORMAL", spread_state="ACCEPTABLE",
                   regime="TREND", candidate_score=0.9, warnings=[]),
        ScanResult(symbol="C", trend_bias="NEUTRAL", momentum_bias="NEUTRAL",
                   volatility_state="LOW", spread_state="ACCEPTABLE",
                   regime="RANGE", candidate_score=0.3, warnings=[]),
        ScanResult(symbol="D", trend_bias="BEARISH", momentum_bias="BEARISH",
                   volatility_state="NORMAL", spread_state="ACCEPTABLE",
                   regime="TREND", candidate_score=0.7, warnings=[]),
    ]
    iterator = iter(fake_results)
    scanner.light_scan = MagicMock(side_effect=lambda s: next(iterator))

    out = scanner.scan_universe(["A", "B", "C", "D"])
    assert len(out) == 2
    assert [r.symbol for r in out] == ["B", "D"]


def test_scan_universe_skips_none_results():
    cfg = _make_cfg(INTRADAY_SCAN_TOP_N=3)
    scanner = _make_scanner(cfg)
    valid = ScanResult(symbol="X", trend_bias="BULLISH", momentum_bias="BULLISH",
                       volatility_state="NORMAL", spread_state="ACCEPTABLE",
                       regime="TREND", candidate_score=0.6, warnings=[])
    scanner.light_scan = MagicMock(side_effect=[None, valid, None])

    out = scanner.scan_universe(["A", "B", "C"])
    assert [r.symbol for r in out] == ["X"]


# ──────────────────────────────────────────────────────────────────────────────
# deep_analyze_top_candidates
# ──────────────────────────────────────────────────────────────────────────────


def _scan(symbol: str, score: float = 0.7) -> ScanResult:
    return ScanResult(
        symbol=symbol, trend_bias="BULLISH", momentum_bias="BULLISH",
        volatility_state="NORMAL", spread_state="ACCEPTABLE",
        regime="TREND", candidate_score=score, warnings=[],
    )


def _ready_setup(symbol: str, conf: float) -> TechnicalSetup:
    return TechnicalSetup(
        symbol=symbol, timeframe="M15", setup_type="READY", direction="BUY",
        entry_price=1.10000, stop_loss=1.09900, take_profit=1.10200,
        confidence=conf, reason="strong",
        indicators={"risk_reward": 2.0}, support_resistance={"support": 1.0950, "resistance": 1.1050},
    )


def _none_setup(symbol: str) -> TechnicalSetup:
    return TechnicalSetup(
        symbol=symbol, timeframe="M15", setup_type="NONE", direction=None,
        entry_price=None, stop_loss=None, take_profit=None,
        confidence=0.0, reason="weak",
    )


def _forming_setup(symbol: str) -> TechnicalSetup:
    return TechnicalSetup(
        symbol=symbol, timeframe="M15", setup_type="FORMING", direction="BUY",
        entry_price=None, stop_loss=None, take_profit=None,
        confidence=0.55, reason="approaching resistance",
    )


def test_deep_analyze_empty_universe_returns_no_trade():
    cfg = _make_cfg()
    strategy = MagicMock()
    scanner = _make_scanner(cfg, strategy_mock=strategy)

    outcome = scanner.deep_analyze_top_candidates([], _account())
    assert outcome.outcome_type == "NO_TRADE"
    assert outcome.proposal is None


def test_deep_analyze_selects_highest_confidence():
    cfg = _make_cfg()
    strategy = MagicMock()
    strategy.analyze_symbol.side_effect = [
        _ready_setup("A", 0.65),
        _ready_setup("B", 0.85),
        _ready_setup("C", 0.70),
    ]
    strategy.build_trade_proposal.side_effect = lambda sym, setup, account_state=None: TradeProposal(
        symbol=sym, direction=setup.direction,
        entry_price=setup.entry_price, stop_loss_price=setup.stop_loss,
        take_profit_price=setup.take_profit, timeframe="M15",
        comment="python_strategy", confidence=setup.confidence,
        rationale=setup.reason,
    )
    strategy.is_addon_for.return_value = False
    strategy.would_proposal_exceed_drawdown.return_value = (False, 0.0)
    scanner = _make_scanner(cfg, strategy_mock=strategy)

    outcome = scanner.deep_analyze_top_candidates(
        [_scan("A"), _scan("B"), _scan("C")], _account()
    )
    assert outcome.outcome_type == "TRADE"
    assert outcome.proposal.symbol == "B"
    assert outcome.proposal.confidence == 0.85


def test_deep_analyze_no_trade_if_all_none():
    cfg = _make_cfg()
    strategy = MagicMock()
    strategy.analyze_symbol.side_effect = [_none_setup("A"), _none_setup("B")]
    scanner = _make_scanner(cfg, strategy_mock=strategy)

    outcome = scanner.deep_analyze_top_candidates([_scan("A"), _scan("B")], _account())
    assert outcome.outcome_type == "NO_TRADE"
    assert outcome.proposal is None


def test_deep_analyze_wait_followup_when_only_forming():
    cfg = _make_cfg()
    strategy = MagicMock()
    strategy.analyze_symbol.side_effect = [_forming_setup("A"), _none_setup("B")]
    strategy.build_delayed_followup.return_value = DelayedFollowUpRequest(
        symbol="A", timeframe="M15", delay_minutes=30, reason="approaching",
        focus_prompt="re-analyze", created_at=__import__("datetime").datetime.now(),
        expires_at=__import__("datetime").datetime.now(),
    )
    scanner = _make_scanner(cfg, strategy_mock=strategy)

    outcome = scanner.deep_analyze_top_candidates([_scan("A"), _scan("B")], _account())
    assert outcome.outcome_type == "WAIT_FOLLOW_UP"
    assert outcome.follow_up.symbol == "A"


def test_deep_analyze_no_trade_below_min_confidence():
    cfg = _make_cfg(MIN_CONFIDENCE_TO_PROPOSE=0.80)
    strategy = MagicMock()
    strategy.analyze_symbol.side_effect = [_ready_setup("A", 0.65), _ready_setup("B", 0.70)]
    scanner = _make_scanner(cfg, strategy_mock=strategy)

    outcome = scanner.deep_analyze_top_candidates([_scan("A"), _scan("B")], _account())
    assert outcome.outcome_type == "NO_TRADE"
    assert "below_threshold" in outcome.note


def test_deep_analyze_followup_disabled_falls_to_no_trade():
    cfg = _make_cfg(FOLLOWUP_ENABLED=False)
    strategy = MagicMock()
    strategy.analyze_symbol.side_effect = [_forming_setup("A")]
    scanner = _make_scanner(cfg, strategy_mock=strategy)

    outcome = scanner.deep_analyze_top_candidates([_scan("A")], _account())
    assert outcome.outcome_type == "NO_TRADE"


# ──────────────────────────────────────────────────────────────────────────────
# calculate_scan_score
# ──────────────────────────────────────────────────────────────────────────────


def test_calculate_scan_score_trend_clarity():
    cfg = _make_cfg()
    scanner = _make_scanner(cfg)
    bars = _trending_bars(1.0900, 0.0005, n=60)
    score_strong = scanner.calculate_scan_score(
        bars, {"sma_20": 1.1010, "ema_50": 1.0950, "rsi_14": 60.0, "atr_pips": 10.0}
    )
    score_weak = scanner.calculate_scan_score(
        bars, {"sma_20": 1.1000, "ema_50": 1.1000, "rsi_14": 60.0, "atr_pips": 10.0}
    )
    assert score_strong > score_weak


def test_calculate_scan_score_zero_when_indicators_missing():
    cfg = _make_cfg()
    scanner = _make_scanner(cfg)
    score = scanner.calculate_scan_score([], {"sma_20": None, "ema_50": None, "rsi_14": None})
    assert score == 0.0
