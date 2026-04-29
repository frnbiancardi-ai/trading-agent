"""Test dei tool MCP v2 (fase 12).

Verifica:
- list_tools contiene i 6 tool legacy + i 4 nuovi;
- ogni handler nuovo restituisce payload JSON-serializzabile;
- scan_symbol_candidates produce un output compatto e stabile;
- propose_trade NON esegue ordini;
- i tool legacy continuano a essere esposti (no regressione).
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import mcp_server


_LEGACY_TOOLS = {
    "get_account_state",
    "get_market_snapshot",
    "evaluate_trade_proposal",
    "submit_order_if_approved",
    "get_risk_profile",
    "get_trade_history",
}

_NEW_TOOLS = {
    "get_symbol_universe",
    "scan_symbol_candidates",
    "get_symbol_indicators",
    "propose_trade",
}


def _bullish_ohlc(n: int = 100) -> list[dict]:
    return [
        {
            "time": 1700000000 + i * 60,
            "open": 1.0900 + i * 0.0005 - 0.0001,
            "high": 1.0900 + i * 0.0005 + 0.0005,
            "low": 1.0900 + i * 0.0005 - 0.0005,
            "close": 1.0900 + i * 0.0005,
            "tick_volume": 100,
        }
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def patch_mcp_singletons(monkeypatch):
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = _bullish_ohlc(100)
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.10000, ask=1.10010, point=0.00001, digits=5,
    )

    cfg = MagicMock()
    cfg.SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
    cfg.TIMEFRAME = "M15"
    cfg.MIN_SL_PIPS = 8
    cfg.MAX_SL_PIPS = 80
    cfg.MAX_LOTS_PER_TRADE = 0.3
    cfg.EXECUTION_MODE = "shadow"
    cfg.RISK_MODE = "CONSERVATIVE"

    monkeypatch.setattr(mcp_server, "mt5", mt5)
    monkeypatch.setattr(mcp_server, "cfg", cfg)
    yield


def test_list_tools_contains_legacy_and_new():
    tools = asyncio.run(mcp_server.list_tools())
    names = {t.name for t in tools}

    assert _LEGACY_TOOLS <= names, f"missing legacy: {_LEGACY_TOOLS - names}"
    assert _NEW_TOOLS <= names, f"missing new: {_NEW_TOOLS - names}"


def test_list_tools_each_has_input_schema():
    tools = asyncio.run(mcp_server.list_tools())
    for t in tools:
        assert t.name
        assert t.description
        assert isinstance(t.inputSchema, dict)
        assert t.inputSchema.get("type") == "object"


def test_handle_get_symbol_universe_returns_config_symbols():
    result = mcp_server.handle_get_symbol_universe()

    assert result["count"] == 3
    assert result["symbols"] == ["EURUSD", "GBPUSD", "USDJPY"]
    assert result["source"] == "config.SYMBOLS"
    json.dumps(result)


def test_handle_get_symbol_universe_with_filter():
    result = mcp_server.handle_get_symbol_universe(filter_asset_class="forex")
    assert result["filter_asset_class"] == "forex"


def test_handle_scan_symbol_candidates_returns_compact_payload():
    result = mcp_server.handle_scan_symbol_candidates(
        symbols=["EURUSD", "GBPUSD"], timeframe="M15"
    )

    assert result["timeframe"] == "M15"
    assert result["count"] == 2
    assert len(result["candidates"]) == 2

    for c in result["candidates"]:
        assert "symbol" in c
        assert "trend_bias" in c
        assert "momentum_bias" in c
        assert "volatility_state" in c
        assert "spread_state" in c
        assert "candidate_score" in c
        assert "warnings" in c
        assert "ohlc" not in c
        assert "open" not in c

    json.dumps(result)


def test_handle_scan_symbol_candidates_uses_default_timeframe_if_none():
    result = mcp_server.handle_scan_symbol_candidates(symbols=["EURUSD"])
    assert result["timeframe"] == "M15"


def test_handle_scan_symbol_candidates_empty_list():
    result = mcp_server.handle_scan_symbol_candidates(symbols=[])
    assert result["count"] == 0
    assert result["candidates"] == []


def test_handle_get_symbol_indicators_returns_indicators_block():
    result = mcp_server.handle_get_symbol_indicators(symbol="EURUSD", timeframe="M15")

    assert result["symbol"] == "EURUSD"
    assert result["timeframe"] == "M15"
    assert result["bars_used"] == 100
    assert "indicators" in result
    assert "last_close" in result
    json.dumps(result)


def test_handle_get_symbol_indicators_returns_error_when_no_data():
    mcp_server.mt5.get_ohlc.return_value = []
    result = mcp_server.handle_get_symbol_indicators(symbol="EURUSD")
    assert "error" in result
    assert result["symbol"] == "EURUSD"


def test_handle_propose_trade_does_not_execute():
    args = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": 1.10000,
        "stop_loss_price": 1.09800,
        "take_profit_price": 1.10400,
        "confidence": 0.7,
        "rationale": "trend rialzista coerente con EMA50, RSI > 60",
    }

    result = mcp_server.handle_propose_trade(args)

    assert result["status"] == "proposed"
    assert result["executed"] is False
    assert result["proposal"]["symbol"] == "EURUSD"
    assert result["proposal"]["direction"] == "BUY"
    assert result["proposal"]["confidence"] == pytest.approx(0.7)
    assert result["proposal"]["comment"] == "mcp_propose_trade"
    json.dumps(result)

    mcp_server.mt5.send_order.assert_not_called()


def test_handle_propose_trade_uses_default_timeframe():
    args = {
        "symbol": "EURUSD",
        "direction": "SELL",
        "entry_price": 1.10000,
        "stop_loss_price": 1.10200,
        "take_profit_price": 1.09600,
        "confidence": 0.65,
        "rationale": "scenario ribassista chiaro",
    }
    result = mcp_server.handle_propose_trade(args)
    assert result["proposal"]["timeframe"] == "M15"


def test_call_tool_dispatches_get_symbol_universe():
    result_blocks = asyncio.run(mcp_server.call_tool("get_symbol_universe", {}))
    assert len(result_blocks) == 1
    payload = json.loads(result_blocks[0].text)
    assert "symbols" in payload
    assert payload["count"] == 3


def test_call_tool_dispatches_scan_symbol_candidates():
    result_blocks = asyncio.run(mcp_server.call_tool(
        "scan_symbol_candidates", {"symbols": ["EURUSD"]}
    ))
    payload = json.loads(result_blocks[0].text)
    assert payload["count"] == 1
    assert payload["candidates"][0]["symbol"] == "EURUSD"


def test_call_tool_dispatches_propose_trade():
    args = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": 1.1,
        "stop_loss_price": 1.098,
        "take_profit_price": 1.104,
        "confidence": 0.7,
        "rationale": "ok",
    }
    result_blocks = asyncio.run(mcp_server.call_tool("propose_trade", args))
    payload = json.loads(result_blocks[0].text)
    assert payload["status"] == "proposed"
    assert payload["executed"] is False


def test_call_tool_unknown_tool_returns_error():
    result_blocks = asyncio.run(mcp_server.call_tool("does_not_exist", {}))
    payload = json.loads(result_blocks[0].text)
    assert "error" in payload
