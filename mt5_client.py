import functools
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

import MetaTrader5 as mt5

from config import Config
from models import AccountState, OrderResult, PositionInfo

logger = logging.getLogger(__name__)

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

_TZ_ROME = ZoneInfo("Europe/Rome")


def _retry(n: int = 3):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(n):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    logger.warning("retry %d/%d for %s: %s", attempt + 1, n, fn.__name__, exc)
            raise last_exc
        return wrapper
    return decorator


class Mt5Client:
    def __init__(self, cfg: Config):
        self._cfg = cfg

    def initialize(self) -> bool:
        ok = mt5.initialize()
        if not ok:
            logger.error("mt5.initialize() failed: %s", mt5.last_error())
        return ok

    def login(self) -> bool:
        ok = mt5.login(
            login=self._cfg.MT5_LOGIN,
            password=self._cfg.MT5_PASSWORD,
            server=self._cfg.MT5_SERVER,
        )
        if not ok:
            logger.error("mt5.login() failed: %s", mt5.last_error())
        return ok

    def shutdown(self) -> None:
        mt5.shutdown()

    @_retry(3)
    def get_account_state(self) -> AccountState:
        info = mt5.account_info()
        if info is None:
            raise RuntimeError(f"account_info() failed: {mt5.last_error()}")

        positions_raw = mt5.positions_get() or []
        positions = [
            PositionInfo(
                symbol=p.symbol,
                lots=p.volume,
                direction="BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                entry_price=p.price_open,
                stop_loss=p.sl,
                take_profit=p.tp,
                profit=p.profit,
                ticket=int(getattr(p, "ticket", 0)),
            )
            for p in positions_raw
        ]

        now_rome = datetime.now(tz=_TZ_ROME)
        day_start = datetime.combine(now_rome.date(), time(0, 0), tzinfo=_TZ_ROME)
        deals = mt5.history_deals_get(day_start, now_rome) or []
        today_pnl = sum(
            d.profit for d in deals if d.entry == mt5.DEAL_ENTRY_OUT
        )

        return AccountState(
            balance=info.balance,
            equity=info.equity,
            free_margin=info.margin_free,
            open_positions=positions,
            today_realized_pnl=today_pnl,
            starting_balance_of_day=info.balance - today_pnl,
        )

    def get_symbol_info(self, symbol: str):
        info = mt5.symbol_info(symbol)
        if info is None or not info.visible:
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
        return info

    @_retry(3)
    def get_ohlc(self, symbol: str, timeframe: str, n_bars: int) -> list[dict]:
        tf = TIMEFRAME_MAP.get(timeframe.upper())
        if tf is None:
            raise ValueError(f"Unknown timeframe: {timeframe}")
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, n_bars)
        if rates is None:
            raise RuntimeError(f"copy_rates_from_pos failed: {mt5.last_error()}")
        return [
            {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "tick_volume": int(r["tick_volume"]),
            }
            for r in rates
        ]

    @_retry(3)
    def calc_order_margin(self, symbol: str, direction: str, lots: float, price: float) -> float:
        action = mt5.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        margin = mt5.order_calc_margin(action, symbol, lots, price)
        if margin is None:
            raise RuntimeError(f"order_calc_margin failed: {mt5.last_error()}")
        return margin

    @_retry(3)
    def send_order(
        self,
        symbol: str,
        direction: str,
        lots: float,
        sl: float,
        tp: float,
        comment: str = "",
    ) -> OrderResult:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(success=False, error_message=f"symbol_info_tick failed: {mt5.last_error()}")

        order_type = mt5.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lots,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "comment": comment,
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(success=False, error_message=f"order_send returned None: {mt5.last_error()}")
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return OrderResult(success=True, order_id=result.order)
        return OrderResult(success=False, error_message=f"order rejected retcode={result.retcode} comment={result.comment}")

    @_retry(3)
    def close_position(self, position_id: int) -> OrderResult:
        """Chiude esplicitamente la posizione con id dato senza aprirne una opposta.

        Usa mt5.order_send con action=TRADE_ACTION_DEAL e campo `position` valorizzato,
        type opposto alla direzione originale, volume = size residua, price = bid/ask
        corrente. Conforme alla doc ufficiale MetaTrader5 Python.
        """
        positions = mt5.positions_get(ticket=position_id) or []
        if not positions:
            return OrderResult(
                success=False,
                error_message=f"position {position_id} non trovata",
            )
        pos = positions[0]

        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return OrderResult(
                success=False,
                error_message=f"symbol_info_tick failed per {pos.symbol}: {mt5.last_error()}",
            )

        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": int(position_id),
            "price": price,
            "deviation": 20,
            "comment": "phase16_close",
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(
                success=False,
                error_message=f"order_send returned None: {mt5.last_error()}",
            )
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                "Close position OK ticket=%s symbol=%s volume=%.4f order=%s",
                position_id, pos.symbol, pos.volume, result.order,
            )
            return OrderResult(success=True, order_id=result.order)
        return OrderResult(
            success=False,
            error_message=(
                f"close rejected retcode={result.retcode} "
                f"comment={result.comment}"
            ),
        )
