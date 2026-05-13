"""Tests for backtest.broker (BACK-02, D-01).

Covers:
- Protocol structural compliance (BacktestBroker + Mt5Client class surface)
- T-NoFutureLeak: get_ohlc only reveals pushed bars
- send_order registers VirtualPosition at last bar.close
- SL/TP conservative resolution (SL before TP same-bar)
- Gap-through fills at bar.open with reason SL_GAP
- Pitfall 1: no same-bar entry/close
- Cost model deducted on close
"""
from __future__ import annotations

import sys
import types

import pytest

# Stub MetaTrader5 so we can import Mt5Client class for the surface check
# (test must NOT instantiate Mt5Client — would attempt live MT5 connect).
if "MetaTrader5" not in sys.modules:
    sys.modules["MetaTrader5"] = types.SimpleNamespace(
        TIMEFRAME_M1=1, TIMEFRAME_M5=5, TIMEFRAME_M15=15, TIMEFRAME_M30=30,
        TIMEFRAME_H1=60, TIMEFRAME_H4=240, TIMEFRAME_D1=1440,
    )

from backtest.broker import BacktestBroker, VirtualPosition
from backtest.costs import CostModel
from backtest.loader import Bar
from models import BrokerProtocol


# ── Helpers ────────────────────────────────────────────────────────────────────

def _bar(time: int, o: float, h: float, l: float, c: float,
         symbol: str = "EURUSD", tf: str = "H1", vol: int = 100) -> Bar:
    return Bar(time=time, open=o, high=h, low=l, close=c, volume=vol,
               symbol=symbol, timeframe=tf)


def _cost_model() -> CostModel:
    # spread=1.0 / slippage=0.0 / commission_round_trip=0.0 / pip_size=0.0001 / pip_value=10.0
    # cost_usd(0.1) == 0.1 * 1.0 * 10.0 = $1.00
    return CostModel(
        spread_pips=1.0,
        slippage_pips=0.0,
        commission_pips_round_trip=0.0,
        pip_size=0.0001,
        pip_value_usd=10.0,
    )


def _broker() -> BacktestBroker:
    return BacktestBroker(
        symbol="EURUSD",
        timeframe="H1",
        initial_balance=10_000.0,
        cost_model=_cost_model(),
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_protocol_compliance():
    """BacktestBroker satisfies BrokerProtocol structurally (isinstance check).

    Mt5Client compliance: structural Protocol checks via isinstance work on
    instances — but we cannot instantiate Mt5Client (would attempt live MT5 connect).
    Since BrokerProtocol is structural (typing.Protocol), verifying the class has
    all four methods as callables is sufficient: any instance will pass isinstance.
    """
    broker = _broker()
    assert isinstance(broker, BrokerProtocol), "BacktestBroker fails Protocol isinstance check"

    # Mt5Client class-level surface check (no instantiation)
    from mt5_client import Mt5Client
    for method in ("get_ohlc", "send_order", "get_account_state", "close_position"):
        assert hasattr(Mt5Client, method), f"Mt5Client missing {method}"
        assert callable(getattr(Mt5Client, method)), f"Mt5Client.{method} not callable"


def test_no_future_leak():
    """T-NoFutureLeak: get_ohlc only returns bars already pushed via advance()."""
    broker = _broker()
    # Push 5 bars
    for i in range(5):
        broker.advance(_bar(time=1_700_000_000 + i * 3600,
                            o=1.1000, h=1.1010, l=1.0990, c=1.1005))
    bars = broker.get_ohlc("EURUSD", "H1", n_bars=10)
    assert len(bars) == 5, f"expected 5 bars, got {len(bars)} — future leak"

    # Push 1 more — now 6 visible
    broker.advance(_bar(time=1_700_000_000 + 5 * 3600, o=1.1005, h=1.1015, l=1.1000, c=1.1010))
    bars = broker.get_ohlc("EURUSD", "H1", n_bars=10)
    assert len(bars) == 6


def test_send_order_registers_at_last_close():
    """send_order creates VirtualPosition at last bar.close."""
    broker = _broker()
    broker.advance(_bar(time=1_700_000_000, o=1.0950, h=1.0960, l=1.0940, c=1.0950))

    result = broker.send_order(
        symbol="EURUSD", direction="BUY", lots=0.1,
        sl=1.0900, tp=1.1050, comment="test",
    )
    assert result.success is True
    assert result.order_id == 1
    # Internal state check
    assert len(broker._positions) == 1
    pos = broker._positions[1]
    assert pos.entry_price == pytest.approx(1.0950)
    assert pos.direction == "BUY"
    assert pos.lots == 0.1
    assert pos.entry_bar_index == 1  # bar_index after first advance()


def test_sl_tp_priority_sl_first():
    """When same bar crosses BOTH SL and TP, SL fills first (D-09 conservative)."""
    broker = _broker()
    # Entry bar
    broker.advance(_bar(time=1_700_000_000, o=1.0945, h=1.0955, l=1.0940, c=1.0950))
    result = broker.send_order(
        symbol="EURUSD", direction="BUY", lots=0.1,
        sl=1.0900, tp=1.1000, comment="",
    )
    assert result.success is True

    # Next bar: high crosses TP (1.1000) AND low crosses SL (1.0900) — both touched
    closed = broker.advance(_bar(
        time=1_700_003_600,
        o=1.0950, h=1.1000, l=1.0850, c=1.0920,
    ))
    assert len(closed) == 1, f"expected 1 close, got {len(closed)}"
    row = closed[0]
    assert row["exit_reason"] == "SL", f"expected SL (conservative), got {row['exit_reason']}"
    assert row["exit_price"] == pytest.approx(1.0900)
    assert row["pnl_usd"] < 0, "SL hit should produce negative pnl"


def test_gap_fill_sl_gap_buy():
    """For BUY, next bar's open BELOW SL → close at bar.open with reason SL_GAP."""
    broker = _broker()
    broker.advance(_bar(time=1_700_000_000, o=1.0945, h=1.0955, l=1.0940, c=1.0950))
    broker.send_order(symbol="EURUSD", direction="BUY", lots=0.1,
                      sl=1.0900, tp=1.1000, comment="")

    # Next bar: opens at 1.0800 — gapped through SL=1.0900
    closed = broker.advance(_bar(
        time=1_700_003_600,
        o=1.0800, h=1.0810, l=1.0790, c=1.0795,
    ))
    assert len(closed) == 1
    row = closed[0]
    assert row["exit_reason"] == "SL_GAP"
    assert row["exit_price"] == pytest.approx(1.0800), \
        f"gap fill should be at bar.open=1.0800, got {row['exit_price']}"


def test_gap_fill_sl_gap_sell():
    """For SELL, next bar's open ABOVE SL → close at bar.open with reason SL_GAP."""
    broker = _broker()
    broker.advance(_bar(time=1_700_000_000, o=1.0945, h=1.0955, l=1.0940, c=1.0950))
    broker.send_order(symbol="EURUSD", direction="SELL", lots=0.1,
                      sl=1.1000, tp=1.0900, comment="")

    closed = broker.advance(_bar(
        time=1_700_003_600,
        o=1.1100, h=1.1110, l=1.1090, c=1.1095,
    ))
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "SL_GAP"
    assert closed[0]["exit_price"] == pytest.approx(1.1100)


def test_no_same_bar_close_pitfall_1():
    """Pitfall 1 regression guard: position cannot close on the entry bar itself.

    If the broker checks SL/TP on the entry bar, this test fails — phantom 1-bar TP
    fills would inflate hit rate to 100%.
    """
    broker = _broker()
    # Bar 1: high=1.1050. We send a BUY with TP=1.1050 immediately after this bar is pushed.
    # If broker checks SL/TP on entry bar, position would close at TP.
    broker.advance(_bar(time=1_700_000_000, o=1.0950, h=1.1050, l=1.0940, c=1.1000))
    broker.send_order(symbol="EURUSD", direction="BUY", lots=0.1,
                      sl=1.0900, tp=1.1050, comment="")
    assert len(broker._positions) == 1, "position should be open after send_order"

    # Critical: advancing the SAME bar context (next bar that does NOT cross TP/SL) — actually
    # the design is: advance() is called with the NEXT bar; here we mimic the engine pushing
    # bar 2 that does not cross. Position must remain open (no phantom close).
    closed = broker.advance(_bar(
        time=1_700_003_600,
        o=1.1000, h=1.1010, l=1.0990, c=1.1005,
    ))
    assert closed == [], f"position should still be open, got {closed}"
    assert len(broker._positions) == 1, "position must persist — Pitfall 1 guard"

    # Bar 3 crosses TP — now it should close.
    closed = broker.advance(_bar(
        time=1_700_007_200,
        o=1.1005, h=1.1060, l=1.1000, c=1.1055,
    ))
    assert len(closed) == 1, "TP cross on bar 3 must fire"
    assert closed[0]["exit_reason"] == "TP"


def test_cost_applied_on_close():
    """Flat trade (entry == exit) → net pnl_usd == -cost_usd(lots)."""
    broker = _broker()
    broker.advance(_bar(time=1_700_000_000, o=1.0950, h=1.0950, l=1.0950, c=1.0950))
    broker.send_order(symbol="EURUSD", direction="BUY", lots=0.1,
                      sl=1.0900, tp=1.1000, comment="")
    # Push another bar with same close — manual close
    broker.advance(_bar(time=1_700_003_600, o=1.0950, h=1.0950, l=1.0950, c=1.0950))
    result = broker.close_position(1)
    assert result.success is True

    # cost_usd(0.1) = 1.0 pip * 10.0 USD/pip * 0.1 lot = $1.00
    assert len(broker._closed_trades) == 1
    row = broker._closed_trades[0]
    assert row["gross_pnl_usd"] == pytest.approx(0.0)
    assert row["pnl_usd"] == pytest.approx(-1.0), \
        f"flat trade should net -$1.00 cost, got {row['pnl_usd']}"
    assert broker._balance == pytest.approx(10_000.0 - 1.0)


def test_get_account_state_reflects_positions():
    """get_account_state returns AccountState with current open positions."""
    broker = _broker()
    broker.advance(_bar(time=1_700_000_000, o=1.0950, h=1.0950, l=1.0950, c=1.0950))
    broker.send_order(symbol="EURUSD", direction="BUY", lots=0.1,
                      sl=1.0900, tp=1.1050, comment="")

    state = broker.get_account_state()
    assert state.balance == pytest.approx(10_000.0)
    assert len(state.open_positions) == 1
    assert state.open_positions[0].direction == "BUY"
    assert state.open_positions[0].ticket == 1


def test_get_symbol_info_jpy_vs_non_jpy():
    """Off-Protocol stub: JPY pairs → 3-digit, non-JPY → 5-digit."""
    broker = _broker()
    eur = broker.get_symbol_info("EURUSD")
    assert eur.point == 0.00001
    assert eur.digits == 5
    assert eur.filling_mode == 2

    jpy = broker.get_symbol_info("USDJPY")
    assert jpy.point == 0.001
    assert jpy.digits == 3


def test_get_ohlc_symbol_mismatch_returns_empty():
    """get_ohlc with wrong symbol/timeframe returns []."""
    broker = _broker()
    broker.advance(_bar(time=1_700_000_000, o=1.0950, h=1.0960, l=1.0940, c=1.0950))
    assert broker.get_ohlc("GBPUSD", "H1", 5) == []
    assert broker.get_ohlc("EURUSD", "M15", 5) == []


def test_starting_balance_of_day_resets_on_utc_day_rollover():
    """Plan 05-10 FIX KILLSWITCH-PERMANENTE.

    Pre-fix: get_account_state ritornava sempre initial_balance hard-coded
    -> risk_engine kill-switch giornaliero rimaneva attivo a vita
    appena la perdita cumulata superava MAX_DAILY_DRAWDOWN_PERCENT,
    troncando i baseline a ~3 settimane invece dei 10y/23y attesi.
    """
    broker = _broker()
    # bar a 00:00 UTC del 2024-01-01 (unix 1704067200)
    day1_open = 1_704_067_200
    broker.advance(_bar(time=day1_open, o=1.10, h=1.10, l=1.10, c=1.10))
    state0 = broker.get_account_state()
    assert state0.starting_balance_of_day == pytest.approx(10_000.0)

    # Simula una perdita riducendo direttamente il balance interno
    # (replica un trade chiuso a -300 USD nello stesso giorno).
    broker._balance = 9_700.0
    state_mid = broker.get_account_state()
    # Stesso giorno => starting_balance_of_day NON cambia
    assert state_mid.starting_balance_of_day == pytest.approx(10_000.0)

    # Avanza al giorno successivo (2024-01-02 00:00 UTC = day1 + 86400)
    day2_open = day1_open + 86_400
    broker.advance(_bar(time=day2_open, o=1.10, h=1.10, l=1.10, c=1.10))
    state_day2 = broker.get_account_state()
    # Nuovo giorno => starting_balance_of_day = balance corrente (9700)
    # cosi' il kill-switch giornaliero riparte su una base fresca.
    assert state_day2.starting_balance_of_day == pytest.approx(9_700.0)
    # Un altro bar nello stesso giorno (es. 12:00 UTC) NON deve resettare.
    broker.advance(_bar(time=day2_open + 43_200, o=1.10, h=1.10, l=1.10, c=1.10))
    state_day2b = broker.get_account_state()
    assert state_day2b.starting_balance_of_day == pytest.approx(9_700.0)
