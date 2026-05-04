"""Position Manager: gestione attiva di posizioni aperte (fase 17.5).

Implementa logica per breakeven move, partial close, e trailing stop.
"""
import logging

from config import Config
from indicators import atr
from models import OpenPositionVerdict, PositionInfo


def _estimate_position_risk_amount(position: PositionInfo, symbol_info) -> float:
    """Stima perdita potenziale (account currency) se il SL fosse colpito."""
    if position is None or position.stop_loss in (0.0, None):
        return 0.0
    pip_size = _pip_size(symbol_info)
    pip_value = _pip_value_amount(symbol_info, pip_size)
    if pip_value <= 0 or pip_size <= 0:
        return 0.0
    distance_pips = abs(position.entry_price - position.stop_loss) / pip_size
    return position.lots * pip_value * distance_pips


def _pip_size(symbol_info) -> float:
    if symbol_info is None:
        return 0.0001
    point = getattr(symbol_info, "point", 0.0001) or 0.0001
    digits = getattr(symbol_info, "digits", 5)
    return point * 10 if digits in (3, 5) else point


def _pip_value_amount(symbol_info, pip_size: float) -> float:
    if symbol_info is None or pip_size <= 0:
        return 0.0
    tick_value = getattr(symbol_info, "trade_tick_value", 0.0) or 0.0
    tick_size = getattr(symbol_info, "trade_tick_size", 0.0) or 0.0
    if tick_size <= 0 or tick_value <= 0:
        return 0.0
    return tick_value * pip_size / tick_size


def _chandelier_exit(
    bars: list[dict],
    atr_value: float,
    multiplier: float = 3.0,
    lookback: int = 22,
) -> float | None:
    """Calcola Chandelier Exit: highest high - multiplier * ATR (long) o lowest low + multiplier * ATR (short).

    Implementazione semplificata: usa l'ultimo ATR value e lookback
    per trovare high/low recenti.
    """
    if not bars or len(bars) < lookback:
        return None

    recent = bars[-lookback:]
    highs = [b["high"] for b in recent]
    lows = [b["low"] for b in recent]

    highest = max(highs) if highs else None
    lowest = min(lows) if lows else None

    # Per long: stop = highest - multiplier * ATR
    # Per short: stop = lowest + multiplier * ATR
    # Qui ritorniamo entrambi e il caller sceglierà in base alla direzione
    return highest if highest is not None else None, lowest


def evaluate_active_management(
    position: PositionInfo,
    bars: list[dict],
    atr_value: float,
    cfg: Config,
    symbol_info,
    logger: logging.Logger,
) -> OpenPositionVerdict:
    """Valuta se applicare gestione attiva (BE move, partial close, trailing).

    Logica:
    - profit >= 1R e sl_at_breakeven=False → MOVE_TO_BREAKEVEN
    - profit >= 2R e partial_closed=False → PARTIAL_CLOSE_50
    - profit >= 2R e partial_closed=True → TRAIL_STOP
    - else → HOLD
    """
    risk_amount = _estimate_position_risk_amount(position, symbol_info)
    if risk_amount <= 0:
        return OpenPositionVerdict(
            symbol=position.symbol,
            ticket=position.ticket,
            action="HOLD",
            reason="risk_amount_invalid",
        )

    profit_r = position.profit / risk_amount if risk_amount > 0 else 0.0

    if not cfg.ENABLE_ACTIVE_POSITION_MGMT:
        return OpenPositionVerdict(
            symbol=position.symbol,
            ticket=position.ticket,
            action="HOLD",
            reason="active_mgmt_disabled",
            profit_r_multiple=profit_r,
        )

    # 1. Breakeven move
    if (
        profit_r >= cfg.BREAKEVEN_TRIGGER_R
        and not position.sl_at_breakeven
    ):
        return OpenPositionVerdict(
            symbol=position.symbol,
            ticket=position.ticket,
            action="MOVE_TO_BREAKEVEN",
            reason=(
                f"profit_r={profit_r:.2f} >= {cfg.BREAKEVEN_TRIGGER_R}, "
                "sposta SL a entry"
            ),
            new_stop_loss=position.entry_price,
            profit_r_multiple=profit_r,
        )

    # 2. Partial close
    if (
        profit_r >= cfg.PARTIAL_CLOSE_TRIGGER_R
        and not position.partial_closed
    ):
        return OpenPositionVerdict(
            symbol=position.symbol,
            ticket=position.ticket,
            action="PARTIAL_CLOSE_50",
            reason=(
                f"profit_r={profit_r:.2f} >= {cfg.PARTIAL_CLOSE_TRIGGER_R}, "
                f"chiudi {cfg.PARTIAL_CLOSE_FRACTION * 100:.0f}%"
            ),
            close_fraction=cfg.PARTIAL_CLOSE_FRACTION,
            profit_r_multiple=profit_r,
        )

    # 3. Trailing stop (dopo partial close)
    if profit_r >= cfg.PARTIAL_CLOSE_TRIGGER_R and position.partial_closed:
        highest, lowest = _chandelier_exit(
            bars,
            atr_value,
            multiplier=cfg.TRAIL_ATR_MULTIPLIER,
            lookback=22,
        )

        new_sl = None
        if position.direction == "BUY" and highest is not None:
            new_sl = highest - cfg.TRAIL_ATR_MULTIPLIER * atr_value
        elif position.direction == "SELL" and lowest is not None:
            new_sl = lowest + cfg.TRAIL_ATR_MULTIPLIER * atr_value

        if new_sl is not None and new_sl != position.stop_loss:
            return OpenPositionVerdict(
                symbol=position.symbol,
                ticket=position.ticket,
                action="TRAIL_STOP",
                reason=(
                    f"profit_r={profit_r:.2f}, "
                    f"trailing stop da {position.stop_loss:.5f} a {new_sl:.5f}"
                ),
                new_stop_loss=new_sl,
                profit_r_multiple=profit_r,
            )

    return OpenPositionVerdict(
        symbol=position.symbol,
        ticket=position.ticket,
        action="HOLD",
        reason=(
            f"profit_r={profit_r:.2f}: "
            f"sl_at_be={position.sl_at_breakeven}, "
            f"partial_closed={position.partial_closed}"
        ),
        profit_r_multiple=profit_r,
    )
