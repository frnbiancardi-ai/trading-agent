"""BacktestBroker — implements BrokerProtocol against in-memory bar window (BACK-02, D-01).

Plan 04 (Wave 1). Decouples strategy from MT5: same code path as Mt5Client via
BrokerProtocol structural typing. SL/TP fill semantics per RESEARCH §BacktestBroker
Fill Semantics — conservative SL-before-TP on same-bar conflict, gap-through fills
at bar.open with reason SL_GAP. Off-by-one Pitfall 1 mitigated via entry_bar_index
guard in _check_sl_tp.

No DB calls, no log output, no network — pure in-memory state.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from types import SimpleNamespace

from models import AccountState, OrderResult, PositionInfo
from backtest.costs import CostModel
from backtest.loader import Bar


@dataclass
class VirtualPosition:
    """In-memory open position tracked by BacktestBroker."""
    position_id: int
    symbol: str
    direction: str           # "BUY" | "SELL"
    lots: float
    entry_price: float
    sl: float
    tp: float
    entry_time: int          # UTC unix seconds
    entry_bar_index: int     # bar index at registration — prevents same-bar SL/TP (Pitfall 1)


class BacktestBroker:
    """In-memory broker satisfying BrokerProtocol structurally (no inheritance).

    Engine (Plan 05) drives this via advance(bar). Strategy reads via the four
    BrokerProtocol methods (get_ohlc, send_order, get_account_state, close_position).
    get_symbol_info is an off-Protocol stub used by strategy for pip-size derivation.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        initial_balance: float,
        cost_model: CostModel,
        max_window: int = 500,
    ) -> None:
        self._symbol = symbol
        self._timeframe = timeframe
        self._initial_balance = float(initial_balance)
        self._balance = float(initial_balance)
        self._equity = float(initial_balance)
        self._cost_model = cost_model
        self._window: deque[dict] = deque(maxlen=max_window)
        self._positions: dict[int, VirtualPosition] = {}
        self._closed_trades: list[dict] = []
        self._next_id: int = 1
        self._bar_index: int = 0  # 0 = no bars seen; first advance() makes it 1
        # Plan 05-10 FIX KILLSWITCH-PERMANENTE: traccia il giorno UTC corrente +
        # il balance di apertura giornata. risk_engine.evaluate_trade rifiuta
        # se balance <= starting_balance_of_day * (1 - MAX_DAILY_DRAWDOWN_PERCENT/100);
        # se starting_balance_of_day non viene resettato all'inizio di ogni giorno
        # il kill-switch resta inchiodato per il resto del backtest e nessun
        # trade successivo passa (bug che limitava i baseline a ~3 settimane su
        # finestra 10y/23y, vedi 05-10-PLAN VAL-3/VAL-4).
        self._current_utc_day: int | None = None
        self._starting_balance_of_day: float = float(initial_balance)

    # ── Engine-only API (NOT on BrokerProtocol) ────────────────────────────────

    def advance(self, bar: Bar) -> list[dict]:
        """Push next bar, monitor SL/TP on existing positions, return rows closed this bar.

        Plan 05-10 FIX KILLSWITCH-PERMANENTE: al primo bar di ogni nuovo giorno
        UTC, snapshot del balance corrente in `_starting_balance_of_day`. Replica
        il comportamento live in cui la giornata di trading si apre con un
        balance fresh e il kill-switch giornaliero riparte da quello — vedi
        risk_engine.evaluate_trade kill switch (riga 55-63).
        """
        # bar.time è unix UTC seconds; il quoziente per 86400 dà il giorno UTC.
        bar_day = int(bar.time) // 86400
        if self._current_utc_day is None or bar_day != self._current_utc_day:
            self._current_utc_day = bar_day
            self._starting_balance_of_day = self._balance
        self._window.append({
            "time": bar.time,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        })
        self._bar_index += 1
        return self._check_sl_tp(bar)

    def calc_order_margin(
        self, symbol: str, direction: str, lots: float, price: float,
    ) -> float:
        """Off-Protocol stub for risk_engine.evaluate_trade margin check.

        Standard 1:30 retail leverage approximation. Returns required USD
        margin so that risk_engine doesn't reject due to margin in backtest.
        Phase 1 simplification: assumes USD-quoted notional / 30.
        """
        notional = abs(lots) * 100_000.0 * max(price, 1e-9)
        if "JPY" in symbol:
            # Approximate JPY-quoted notional back to USD via current price
            notional = notional / max(price, 1e-9)
        return notional / 30.0

    def get_symbol_info(self, symbol: str) -> SimpleNamespace:
        """Off-Protocol stub per RESEARCH §Open Question 1.

        JPY pairs: 3-digit, point=0.001. Non-JPY: 5-digit, point=0.00001.
        filling_mode=2 (RETURN — TenTrade compatible per CLAUDE.md broker note).
        """
        if "JPY" in symbol:
            return SimpleNamespace(
                point=0.001,
                digits=3,
                trade_tick_value=1.0,
                trade_tick_size=0.001,
                filling_mode=2,
                volume_step=0.01,
            )
        return SimpleNamespace(
            point=0.00001,
            digits=5,
            trade_tick_value=1.0,
            trade_tick_size=0.00001,
            filling_mode=2,
            volume_step=0.01,
        )

    # ── BrokerProtocol API ─────────────────────────────────────────────────────

    def get_ohlc(self, symbol: str, timeframe: str, n_bars: int) -> list[dict]:
        """Return last n_bars from window. T-NoFutureLeak: only bars already pushed."""
        if symbol != self._symbol or timeframe != self._timeframe:
            return []
        if n_bars <= 0:
            return []
        # deque slicing requires list conversion
        snapshot = list(self._window)
        return snapshot[-n_bars:]

    def send_order(
        self,
        symbol: str,
        direction: str,
        lots: float,
        sl: float,
        tp: float,
        comment: str = "",
        context: dict | None = None,
    ) -> OrderResult:
        """Register a VirtualPosition at last bar's close (D-09: decision time = bar close).

        Pitfall 1: entry_bar_index = current _bar_index. _check_sl_tp skips positions
        whose entry_bar_index == self._bar_index (cannot close on entry bar).
        """
        if symbol != self._symbol:
            return OrderResult(success=False, error_message=f"symbol mismatch: {symbol}")
        if not self._window:
            return OrderResult(success=False, error_message="no bars in window — call advance() first")
        if direction not in ("BUY", "SELL"):
            return OrderResult(success=False, error_message=f"invalid direction: {direction}")

        last_bar = self._window[-1]
        entry_price = float(last_bar["close"])
        entry_time = int(last_bar["time"])

        pos_id = self._next_id
        self._next_id += 1
        self._positions[pos_id] = VirtualPosition(
            position_id=pos_id,
            symbol=symbol,
            direction=direction,
            lots=float(lots),
            entry_price=entry_price,
            sl=float(sl),
            tp=float(tp),
            entry_time=entry_time,
            entry_bar_index=self._bar_index,
        )
        return OrderResult(success=True, order_id=pos_id)

    def get_account_state(self) -> AccountState:
        """Snapshot of current balance/equity + open positions."""
        open_positions = [
            PositionInfo(
                symbol=pos.symbol,
                lots=pos.lots,
                direction=pos.direction,
                entry_price=pos.entry_price,
                stop_loss=pos.sl,
                take_profit=pos.tp,
                profit=0.0,  # MTM tracking not implemented in Phase 1 — engine computes on close
                ticket=pos.position_id,
            )
            for pos in self._positions.values()
        ]
        return AccountState(
            balance=self._balance,
            equity=self._equity,
            free_margin=self._balance,
            open_positions=open_positions,
            today_realized_pnl=0.0,
            # Plan 05-10 FIX KILLSWITCH-PERMANENTE: era _initial_balance hard-coded
            # → ora snapshot bar-rollover (vedi advance()) in modo che il kill
            # switch giornaliero di risk_engine si resetti a fine giornata.
            starting_balance_of_day=self._starting_balance_of_day,
        )

    # ── Phase 5 helpers (additive — D-05 timeout, slice_worker integration) ───

    @property
    def virtual_positions(self) -> list[VirtualPosition]:
        """Snapshot list delle posizioni aperte (Phase 5 D-05 introspection).

        Esposto come lista nuova ad ogni call → l'iterazione lato chiamante è
        sicura anche se il chiamante chiama force_close in loop (no mutation
        durante iteration sul dict interno).
        """
        return list(self._positions.values())

    def force_close(
        self,
        position_id: int,
        exit_price: float,
        exit_reason: str,
        exit_time: int | None = None,
    ) -> dict:
        """Chiude una posizione a prezzo e reason espliciti (Phase 5 D-05).

        Thin wrapper sopra ``_close_virtual``: serve a slice_worker /
        BacktestEngine timeout enforcement quando la chiusura non è
        triggerata da SL/TP intra-bar. ``exit_time`` opzionale → default a
        timestamp dell'ultima bar nel window (coerente con close_position).
        """
        if position_id not in self._positions:
            raise KeyError(f"unknown position_id: {position_id}")
        if exit_time is None:
            if not self._window:
                raise RuntimeError("no bars in window — call advance() first")
            exit_time = int(self._window[-1]["time"])
        return self._close_virtual(position_id, float(exit_price), exit_reason, int(exit_time))

    def close_position(self, position_id: int) -> OrderResult:
        """Manual close at last bar's close. Cost model deducted on close."""
        if position_id not in self._positions:
            return OrderResult(success=False, error_message=f"unknown position_id: {position_id}")
        if not self._window:
            return OrderResult(success=False, error_message="no bars in window")

        last_bar = self._window[-1]
        exit_price = float(last_bar["close"])
        exit_time = int(last_bar["time"])
        self._close_virtual(position_id, exit_price, "MANUAL", exit_time)
        return OrderResult(success=True, order_id=position_id)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _check_sl_tp(self, bar: Bar) -> list[dict]:
        """Check SL/TP on every open position. Returns closed-trade rows for this bar.

        D-09 conservative: SL before TP when both crossed in same bar.
        Gap-through: if bar.open is already beyond SL, fill at bar.open with reason SL_GAP.
        Pitfall 1: skip positions whose entry_bar_index == self._bar_index (entry bar).
        """
        to_close: list[tuple[int, float, str]] = []
        for pos_id, pos in self._positions.items():
            if pos.entry_bar_index == self._bar_index:
                # Pitfall 1: never close on entry bar — monitoring starts next bar.
                continue
            if pos.direction == "BUY":
                # Gap-through: open already at/below SL
                if bar.open <= pos.sl:
                    to_close.append((pos_id, bar.open, "SL_GAP"))
                elif bar.low <= pos.sl:
                    # D-09 conservative: SL before TP when both crossed in same bar.
                    to_close.append((pos_id, pos.sl, "SL"))
                elif bar.high >= pos.tp:
                    to_close.append((pos_id, pos.tp, "TP"))
            else:  # SELL
                if bar.open >= pos.sl:
                    to_close.append((pos_id, bar.open, "SL_GAP"))
                elif bar.high >= pos.sl:
                    to_close.append((pos_id, pos.sl, "SL"))
                elif bar.low <= pos.tp:
                    to_close.append((pos_id, pos.tp, "TP"))

        rows: list[dict] = []
        for pos_id, exit_price, reason in to_close:
            row = self._close_virtual(pos_id, exit_price, reason, bar.time)
            rows.append(row)
        return rows

    def _close_virtual(self, pos_id: int, exit_price: float, reason: str, exit_time: int) -> dict:
        """Close a virtual position, apply cost model, update balance, append to ledger."""
        pos = self._positions[pos_id]
        pip_size = self._cost_model.pip_size
        if pos.direction == "BUY":
            pnl_pips = (exit_price - pos.entry_price) / pip_size
        else:  # SELL
            pnl_pips = (pos.entry_price - exit_price) / pip_size
        gross_pnl_usd = pnl_pips * self._cost_model.pip_value_usd * pos.lots
        cost_usd = self._cost_model.cost_usd(pos.lots)
        net_pnl_usd = gross_pnl_usd - cost_usd

        row = {
            "position_id": pos.position_id,
            "symbol": pos.symbol,
            "direction": pos.direction,
            "lots": pos.lots,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "sl": pos.sl,
            "tp": pos.tp,
            "entry_time": pos.entry_time,
            "exit_time": exit_time,
            "pnl_pips": pnl_pips,
            "pnl_usd": net_pnl_usd,
            "gross_pnl_usd": gross_pnl_usd,
            "exit_reason": reason,
        }
        self._closed_trades.append(row)
        self._balance += net_pnl_usd
        self._equity = self._balance
        del self._positions[pos_id]
        return row
