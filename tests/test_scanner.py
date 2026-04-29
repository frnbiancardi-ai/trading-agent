"""Test del workflow scanner multi-symbol di ClaudeAgent.

Mock di Anthropic client e Mt5Client: nessun network, nessun MT5 reale.
"""
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from claude_agent import ClaudeAgent, _MAX_ITERATIONS_SCANNER
from models import AccountState, TradeProposal


def _bar(close: float, idx: int = 0, atr_seed: float = 0.0010) -> dict:
    return {
        "time": 1700000000 + idx * 60,
        "open": close - 0.0001,
        "high": close + atr_seed / 2,
        "low": close - atr_seed / 2,
        "close": close,
        "tick_volume": 100,
    }


def _bullish_ohlc(n: int = 100) -> list[dict]:
    return [_bar(1.0900 + i * 0.0005, idx=i) for i in range(n)]


def _flat_ohlc(n: int = 100) -> list[dict]:
    return [_bar(1.1000, idx=i) for i in range(n)]


def _account_state() -> AccountState:
    return AccountState(
        balance=10000.0,
        equity=10000.0,
        free_margin=9500.0,
        open_positions=[],
        today_realized_pnl=0.0,
        starting_balance_of_day=10000.0,
    )


def _make_cfg() -> MagicMock:
    cfg = MagicMock()
    cfg.CLAUDE_API_KEY = "test-key"
    cfg.CLAUDE_MODEL = "claude-test"
    cfg.CLAUDE_MAX_TOKENS = 1024
    cfg.CLAUDE_TEMPERATURE = 0.2
    cfg.TIMEFRAME = "M15"
    cfg.EXECUTION_MODE = "shadow"
    cfg.MIN_SL_PIPS = 8
    cfg.MAX_SL_PIPS = 80
    cfg.MAX_LOTS_PER_TRADE = 0.3
    cfg.RISK_MODE = "CONSERVATIVE"
    cfg.MAX_SYMBOLS_TO_DEEPEN = 3
    return cfg


def _make_agent(cfg: MagicMock, mt5: MagicMock) -> ClaudeAgent:
    logger = logging.getLogger("test_scanner")
    agent = ClaudeAgent(cfg, mt5, logger)
    agent.client = MagicMock()
    return agent


def _tool_use_block(tool_id: str, name: str, input_: dict):
    block = SimpleNamespace()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_
    return block


def _text_block(text: str):
    block = SimpleNamespace()
    block.type = "text"
    block.text = text
    return block


def _make_response(stop_reason: str, content: list):
    resp = SimpleNamespace()
    resp.stop_reason = stop_reason
    resp.content = content
    return resp


@pytest.fixture
def cfg():
    return _make_cfg()


@pytest.fixture
def mt5(cfg):
    m = MagicMock()
    m.get_ohlc.return_value = _bullish_ohlc()
    m.get_symbol_info.return_value = SimpleNamespace(
        bid=1.10000, ask=1.10010, point=0.00001, digits=5,
    )
    return m


def test_cheap_scan_no_data_returns_zero_score(cfg):
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = []
    mt5.get_symbol_info.return_value = None
    agent = _make_agent(cfg, mt5)

    candidate = agent._cheap_scan_one("EURUSD")

    assert candidate.symbol == "EURUSD"
    assert candidate.candidate_score == 0.0
    assert "no_ohlc_data" in candidate.warnings


def test_cheap_scan_bullish_trend_yields_positive_score(cfg, mt5):
    agent = _make_agent(cfg, mt5)
    candidate = agent._cheap_scan_one("EURUSD")

    assert candidate.symbol == "EURUSD"
    assert candidate.candidate_score > 0.0
    assert candidate.trend_bias in ("BULLISH", "NEUTRAL")  # depends on EMA-50 init


def test_run_market_scan_empty_universe_returns_none(cfg, mt5):
    agent = _make_agent(cfg, mt5)

    proposal = agent.run_market_scan([], "M15", _account_state())

    assert proposal is None
    agent.client.messages.create.assert_not_called()


def test_run_market_scan_returns_proposal_when_propose_trade_called(cfg, mt5):
    agent = _make_agent(cfg, mt5)
    propose_block = _tool_use_block(
        "tu_1", "propose_trade",
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry_price": 1.10000,
            "stop_loss_price": 1.09800,
            "take_profit_price": 1.10400,
            "confidence": 0.75,
            "rationale": "trend rialzista coerente con EMA50 e RSI > 60",
        },
    )
    end_block = _text_block("done")

    agent.client.messages.create.side_effect = [
        _make_response("tool_use", [propose_block]),
        _make_response("end_turn", [end_block]),
    ]

    proposal = agent.run_market_scan(["EURUSD", "GBPUSD"], "M15", _account_state())

    assert isinstance(proposal, TradeProposal)
    assert proposal.symbol == "EURUSD"
    assert proposal.confidence == pytest.approx(0.75)
    assert proposal.comment == "claude_scanner"
    assert agent.client.messages.create.call_count == 1


def test_run_market_scan_returns_none_when_end_turn_immediately(cfg, mt5):
    agent = _make_agent(cfg, mt5)
    agent.client.messages.create.return_value = _make_response(
        "end_turn", [_text_block("NO_TRADE\nuniverso ambiguo")]
    )

    proposal = agent.run_market_scan(["EURUSD"], "M15", _account_state())

    assert proposal is None


def test_run_market_scan_caps_at_max_iterations(cfg, mt5):
    agent = _make_agent(cfg, mt5)
    looping_block = _tool_use_block(
        "tu_loop", "scan_symbol_candidates", {"symbols": ["EURUSD"]},
    )
    agent.client.messages.create.return_value = _make_response(
        "tool_use", [looping_block]
    )

    proposal = agent.run_market_scan(["EURUSD"], "M15", _account_state())

    assert proposal is None
    assert agent.client.messages.create.call_count == _MAX_ITERATIONS_SCANNER


def test_run_market_scan_rejects_second_proposal_in_same_response(cfg, mt5):
    agent = _make_agent(cfg, mt5)
    first_propose = _tool_use_block(
        "tu_a", "propose_trade",
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry_price": 1.10000,
            "stop_loss_price": 1.09800,
            "take_profit_price": 1.10400,
            "confidence": 0.7,
            "rationale": "primo edge chiaro",
        },
    )
    second_propose = _tool_use_block(
        "tu_b", "propose_trade",
        {
            "symbol": "GBPUSD",
            "direction": "SELL",
            "entry_price": 1.25000,
            "stop_loss_price": 1.25200,
            "take_profit_price": 1.24600,
            "confidence": 0.65,
            "rationale": "secondo edge",
        },
    )
    agent.client.messages.create.return_value = _make_response(
        "tool_use", [first_propose, second_propose]
    )

    proposal = agent.run_market_scan(["EURUSD", "GBPUSD"], "M15", _account_state())

    assert isinstance(proposal, TradeProposal)
    assert proposal.symbol == "EURUSD"
    assert agent.client.messages.create.call_count == 1


def test_dispatch_scanner_tool_get_risk_profile(cfg, mt5):
    agent = _make_agent(cfg, mt5)

    result = agent._dispatch_scanner_tool("get_risk_profile", {})

    assert result["MIN_SL_PIPS"] == 8
    assert result["MAX_SL_PIPS"] == 80
    assert result["EXECUTION_MODE"] == "shadow"
    assert result["RISK_MODE"] == "CONSERVATIVE"


def test_dispatch_scanner_tool_scan_symbol_candidates(cfg, mt5):
    agent = _make_agent(cfg, mt5)

    result = agent._dispatch_scanner_tool(
        "scan_symbol_candidates", {"symbols": ["EURUSD", "GBPUSD"]}
    )

    assert "candidates" in result
    assert len(result["candidates"]) == 2
    assert all("symbol" in c for c in result["candidates"])
    assert all("candidate_score" in c for c in result["candidates"])


def test_dispatch_scanner_tool_unknown_returns_error(cfg, mt5):
    agent = _make_agent(cfg, mt5)

    result = agent._dispatch_scanner_tool("nonexistent_tool", {})

    assert "error" in result


def test_run_cycle_backward_compat_still_works(cfg, mt5):
    """run_cycle single-symbol non deve essere rotto dalle aggiunte scanner."""
    agent = _make_agent(cfg, mt5)
    agent.client.messages.create.return_value = _make_response(
        "end_turn", [_text_block("NO_TRADE\nfermo per trend incerto")]
    )

    proposal = agent.run_cycle("EURUSD", _account_state())

    assert proposal is None
    assert agent.client.messages.create.call_count == 1
