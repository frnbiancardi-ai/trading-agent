"""Shared fixtures for backtest test suite (Phase 1)."""
from __future__ import annotations
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


# ── Stub MetaTrader5 if not installed (Phase 1 dev-machine workaround) ─────────
# Live trading machine has the real package; backtest CI / dev laptops don't.
# Stubbing here lets backtest tests import strategy.py / risk_engine.py without
# the live broker dependency. Plan 01-05: required to collect tests.
if "MetaTrader5" not in sys.modules:
    try:
        import MetaTrader5  # noqa: F401
    except ModuleNotFoundError:
        _stub = ModuleType("MetaTrader5")
        # Minimal surface used by mt5_client at import time:
        for attr in (
            "TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_M30",
            "TIMEFRAME_H1", "TIMEFRAME_H4", "TIMEFRAME_D1",
            "ORDER_TYPE_BUY", "ORDER_TYPE_SELL",
            "TRADE_ACTION_DEAL", "TRADE_ACTION_SLTP",
            "ORDER_TIME_GTC", "ORDER_FILLING_FOK", "ORDER_FILLING_IOC",
            "ORDER_FILLING_RETURN", "ORDER_FILLING_BOC",
            "TRADE_RETCODE_DONE",
            "SYMBOL_FILLING_FOK", "SYMBOL_FILLING_IOC",
            "POSITION_TYPE_BUY", "POSITION_TYPE_SELL",
        ):
            setattr(_stub, attr, 0)
        # Functions called at import time on some builds — make them no-ops.
        for fn in (
            "initialize", "shutdown", "login", "last_error",
            "account_info", "symbol_info", "symbol_info_tick",
            "copy_rates_from_pos", "positions_get", "history_deals_get",
            "order_send", "order_check", "order_calc_margin",
        ):
            setattr(_stub, fn, lambda *a, **kw: None)
        sys.modules["MetaTrader5"] = _stub


@pytest.fixture
def fixture_5bars_path() -> Path:
    return Path(__file__).parent / "fixtures" / "eurusd_5bars.csv"


@pytest.fixture
def costs_yaml_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "configs" / "costs.yaml"
