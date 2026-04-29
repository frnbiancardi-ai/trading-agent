"""Test E2E sul vero terminale MT5 (FP Markets demo).

Skippati automaticamente se MT5_LOGIN / MT5_PASSWORD non sono configurati
in `.env`, oppure se `Mt5Client.initialize()`/`login()` falliscono (es.
terminale MT5 non aperto).
"""
import os

import pytest

from config import Config
from mt5_client import Mt5Client

pytestmark = pytest.mark.skipif(
    not os.getenv("MT5_LOGIN") or not os.getenv("MT5_PASSWORD"),
    reason="MT5 credentials non configurate, skip test ambiente reale",
)


@pytest.fixture(scope="module")
def client():
    cfg = Config()
    c = Mt5Client(cfg)
    if not c.initialize() or not c.login():
        pytest.skip("MT5 initialize/login failed (terminale non aperto o credenziali errate)")
    yield c
    c.shutdown()


def test_get_account_state(client):
    state = client.get_account_state()
    assert state.balance >= 0
    assert state.equity >= 0
    assert isinstance(state.open_positions, list)


def test_get_symbol_info(client):
    info = client.get_symbol_info("EURUSD")
    assert info is not None
    assert info.point > 0
    assert info.digits in (3, 5)  # forex 5 digit (o 3 per JPY pairs, ma EURUSD = 5)


def test_get_ohlc_m15(client):
    bars = client.get_ohlc("EURUSD", "M15", 50)
    assert len(bars) == 50
    last = bars[-1]
    for key in ("time", "open", "high", "low", "close", "tick_volume"):
        assert key in last
    assert last["high"] >= last["low"]


def test_calc_order_margin(client):
    margin = client.calc_order_margin("EURUSD", "BUY", 0.01, 1.10)
    assert margin > 0
