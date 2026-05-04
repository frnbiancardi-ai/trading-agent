"""Test position manager: breakeven move, partial close, trailing stop."""
import logging
from unittest.mock import MagicMock

import pytest

from models import PositionInfo
from position_manager import evaluate_active_management


def _make_cfg(**overrides):
    cfg = MagicMock()
    cfg.ENABLE_ACTIVE_POSITION_MGMT = True
    cfg.BREAKEVEN_TRIGGER_R = 1.0
    cfg.PARTIAL_CLOSE_TRIGGER_R = 2.0
    cfg.PARTIAL_CLOSE_FRACTION = 0.5
    cfg.TRAIL_ATR_MULTIPLIER = 3.0
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _position(
    symbol: str = "EURUSD",
    direction: str = "BUY",
    entry: float = 1.1000,
    sl: float = 1.0950,
    tp: float = 1.1100,
    profit: float = 0.0,
    ticket: int = 123,
    sl_at_breakeven: bool = False,
    partial_closed: bool = False,
) -> PositionInfo:
    return PositionInfo(
        symbol=symbol,
        lots=1.0,
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        profit=profit,
        ticket=ticket,
        sl_at_breakeven=sl_at_breakeven,
        partial_closed=partial_closed,
    )


def _bars(start: float = 1.0900, step: float = 0.0005, n: int = 100) -> list[dict]:
    """Generate trending bars."""
    return [
        {
            "time": 1700000000 + i * 900,
            "open": start + i * step - 0.0001,
            "high": start + i * step + 0.0003,
            "low": start + i * step - 0.0003,
            "close": start + i * step,
            "tick_volume": 100,
        }
        for i in range(n)
    ]


def _symbol_info_mock(point: float = 0.0001, tick_value: float = 1.0):
    """Mock symbol info 4-digit EURUSD: point=pip_size=0.0001.

    Con digits=4 _pip_size non moltiplica × 10. pip_value = tick_value * point / point = 1.0.
    distance_pips = |1.1000 - 1.0950| / 0.0001 = 50. risk = 1 lot × 1 × 50 = $50.
    Quindi profit=$50 → profit_r=1.0 (1R), $100 → 2R, $125 → 2.5R.
    """
    info = MagicMock()
    info.point = point
    info.digits = 4
    info.trade_tick_value = tick_value
    info.trade_tick_size = point
    return info


# ──────────────────────────────────────────────────────────────────────────────
# Breakeven move
# ──────────────────────────────────────────────────────────────────────────────


def test_move_to_breakeven_at_1r():
    cfg = _make_cfg()
    pos = _position(entry=1.1000, sl=1.0950, profit=55.0)  # ~1.1R profit (margine float)
    bars = _bars()
    sym_info = _symbol_info_mock()

    verdict = evaluate_active_management(
        pos, bars, atr_value=0.0050, cfg=cfg, symbol_info=sym_info,
        logger=logging.getLogger("test"),
    )

    assert verdict.action == "MOVE_TO_BREAKEVEN"
    assert verdict.new_stop_loss == pos.entry_price


def test_move_to_breakeven_skipped_if_already_at_be():
    cfg = _make_cfg()
    pos = _position(entry=1.1000, sl=1.0950, profit=55.0, sl_at_breakeven=True)
    bars = _bars()
    sym_info = _symbol_info_mock()

    verdict = evaluate_active_management(
        pos, bars, atr_value=0.0050, cfg=cfg, symbol_info=sym_info,
        logger=logging.getLogger("test"),
    )

    # Profit is 1R but sl_at_breakeven=True, so skip BE move
    # This should fall through to partial close check at 2R
    assert verdict.action == "HOLD"


# ──────────────────────────────────────────────────────────────────────────────
# Partial close
# ──────────────────────────────────────────────────────────────────────────────


def test_partial_close_at_2r():
    cfg = _make_cfg()
    # sl_at_breakeven=True per saltare BE check e arrivare a partial close
    pos = _position(entry=1.1000, sl=1.0950, profit=105.0, sl_at_breakeven=True)
    bars = _bars()
    sym_info = _symbol_info_mock()

    verdict = evaluate_active_management(
        pos, bars, atr_value=0.0050, cfg=cfg, symbol_info=sym_info,
        logger=logging.getLogger("test"),
    )

    assert verdict.action == "PARTIAL_CLOSE_50"
    assert verdict.close_fraction == 0.5


def test_partial_close_skipped_if_already_closed():
    cfg = _make_cfg()
    pos = _position(
        entry=1.1000, sl=1.0950, profit=105.0,
        sl_at_breakeven=True, partial_closed=True,
    )
    bars = _bars()
    sym_info = _symbol_info_mock()

    verdict = evaluate_active_management(
        pos, bars, atr_value=0.0050, cfg=cfg, symbol_info=sym_info,
        logger=logging.getLogger("test"),
    )

    # Profit is 2R, partial_closed=True, so don't partial close again
    # Falls through to trailing stop logic
    assert verdict.action in ("TRAIL_STOP", "HOLD")


# ──────────────────────────────────────────────────────────────────────────────
# Trailing stop
# ──────────────────────────────────────────────────────────────────────────────


def test_trailing_stop_after_partial_close():
    cfg = _make_cfg(TRAIL_ATR_MULTIPLIER=3.0)
    pos = _position(
        direction="BUY",
        entry=1.1000,
        sl=1.0950,
        profit=130.0,  # ~2.6R
        sl_at_breakeven=True,
        partial_closed=True,
    )
    bars = _bars(start=1.0900, step=0.0005, n=30)  # Trending up
    sym_info = _symbol_info_mock()

    verdict = evaluate_active_management(
        pos, bars, atr_value=0.0050, cfg=cfg, symbol_info=sym_info,
        logger=logging.getLogger("test"),
    )

    # With profit >= 2R and partial_closed=True, should attempt trailing
    # (verdict.action might be TRAIL_STOP if new_sl differs from current sl)
    assert verdict.profit_r_multiple >= 2.0


# ──────────────────────────────────────────────────────────────────────────────
# Hold
# ──────────────────────────────────────────────────────────────────────────────


def test_hold_profit_below_1r():
    cfg = _make_cfg()
    pos = _position(entry=1.1000, sl=1.0950, profit=20.0)  # < 1R
    bars = _bars()
    sym_info = _symbol_info_mock()

    verdict = evaluate_active_management(
        pos, bars, atr_value=0.0050, cfg=cfg, symbol_info=sym_info,
        logger=logging.getLogger("test"),
    )

    assert verdict.action == "HOLD"


def test_hold_active_mgmt_disabled():
    cfg = _make_cfg(ENABLE_ACTIVE_POSITION_MGMT=False)
    pos = _position(entry=1.1000, sl=1.0950, profit=105.0)  # >= 2R
    bars = _bars()
    sym_info = _symbol_info_mock()

    verdict = evaluate_active_management(
        pos, bars, atr_value=0.0050, cfg=cfg, symbol_info=sym_info,
        logger=logging.getLogger("test"),
    )

    assert verdict.action == "HOLD"
    assert "active_mgmt_disabled" in verdict.reason
