"""Backtest harness: simulazione bar-by-bar su dati storici (fase 17.6).

Componenti:
- BacktestMt5Client: mock Mt5Client che serve barre da dataset pre-caricato
- BacktestEngine: engine principale che itera e applica strategia
- BacktestTrade: traccia singolo trade
- BacktestReport: metriche finali (expectancy, Sharpe, Max DD, profit factor, etc.)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from config import Config
from models import (
    AccountState,
    OrderResult,
    PositionInfo,
    TradeProposal,
)
from mt5_client import Mt5Client


@dataclass
class BacktestTrade:
    """Singolo trade eseguito nel backtest."""
    symbol: str
    direction: str
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    lots: float
    exit_time: datetime
    exit_price: float
    exit_reason: Literal["TP", "SL", "MANUAL"]
    profit_pct: float
    profit_r: float  # Risk multiple (profit / risk_amount)
    # Costi realistici (fase 17.6.1)
    spread_cost_usd: float = 0.0
    commission_usd: float = 0.0
    slippage_cost_usd: float = 0.0
    gross_profit_usd: float = 0.0  # P&L lordo prima costi
    net_profit_usd: float = 0.0    # P&L netto dopo costi


@dataclass
class BacktestReport:
    """Report finale con metriche."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    winrate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    total_profit_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_abs: float = 0.0
    sharpe_ratio: float = 0.0
    max_consecutive_losses: int = 0
    avg_trade_duration_hours: float = 0.0
    trades: list[BacktestTrade] = field(default_factory=list)
    start_balance: float = 0.0
    end_balance: float = 0.0
    # Aggregati costi realistici (fase 17.6.1)
    total_spread_cost_usd: float = 0.0
    total_commission_usd: float = 0.0
    total_slippage_cost_usd: float = 0.0
    total_gross_profit_usd: float = 0.0
    total_net_profit_usd: float = 0.0


class BacktestMt5Client(Mt5Client):
    """Mock Mt5Client che serve barre storiche da dataset pre-caricato.

    Sostituisce Mt5Client reale durante backtest.
    """

    def __init__(
        self,
        cfg: Config,
        symbol_to_bars: dict[str, list[dict]],
        intermarket_bars: dict[str, list[dict]] | None = None,
    ):
        """
        Args:
            cfg: Config object
            symbol_to_bars: simboli trading principali (TF main, es. M15). Chiavi=simboli,
                valori=liste bar OHLC ordinate per time.
            intermarket_bars: simboli intermarket (TF diverso, es. D1 XAUUSD/USOIL).
                Lookup time-based: get_ohlc ritorna ultime n_bars con time <= current_time.
        """
        self.cfg = cfg
        self.symbol_to_bars = symbol_to_bars
        self.intermarket_bars = intermarket_bars or {}
        self.log = logging.getLogger(__name__)
        self.current_bar_index = {sym: 0 for sym in symbol_to_bars.keys()}
        # Timestamp current bar (main loop). Engine lo aggiorna ad ogni step.
        self.current_time: int = 0

    def initialize(self) -> bool:
        """No-op: backtest non richiede MT5 initialization."""
        return True

    def login(self) -> bool:
        """No-op."""
        return True

    def shutdown(self) -> None:
        """No-op."""
        pass

    def get_account_state(self) -> AccountState:
        """Ritorna stato account al momento (mock)."""
        return AccountState(
            balance=10000.0,
            equity=10000.0,
            free_margin=9500.0,
            open_positions=[],
            today_realized_pnl=0.0,
            starting_balance_of_day=10000.0,
        )

    def get_symbol_info(self, symbol: str):
        """Mock symbol info — campi minimi richiesti da risk_engine + execution."""
        import types
        # Default forex 5-digit; override per metalli/oil
        if symbol.upper() in ("XAUUSD", "GOLD"):
            point = 0.01
            digits = 2
            tick_value = 1.0
            tick_size = 0.01
        elif symbol.upper() in ("USOIL", "WTI", "UKOIL"):
            point = 0.01
            digits = 2
            tick_value = 10.0
            tick_size = 0.01
        else:
            point = 0.00001
            digits = 5
            tick_value = 10.0
            tick_size = 0.00001
        return types.SimpleNamespace(
            point=point,
            digits=digits,
            trade_tick_value=tick_value,
            trade_tick_size=tick_size,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            trade_contract_size=100000.0,
            margin_initial=0.0,
            margin_rate=1.0,
            spread=10,
            currency_profit="USD",
            currency_margin="USD",
        )

    def get_ohlc(self, symbol: str, timeframe: str, n_bars: int) -> list[dict]:
        """Ritorna fino a n_bars barre dal dataset per il symbol/timeframe.

        Trading symbols (symbol_to_bars): index-based, mirror copy_rates_from_pos live.
        Intermarket symbols (intermarket_bars): time-based lookup, ritorna ultime
        n_bars con time <= current_time per evitare look-ahead.
        """
        # Trading symbol path: index-based
        if symbol in self.symbol_to_bars:
            bars = self.symbol_to_bars[symbol]
            idx = self.current_bar_index.get(symbol, 0)
            end = idx + 1
            start = max(0, end - n_bars)
            return bars[start:end]

        # Intermarket symbol path: time-based lookup
        if symbol in self.intermarket_bars:
            bars = self.intermarket_bars[symbol]
            if not bars or self.current_time == 0:
                # Pre-loop: ritorna tutte (engine fallback NEUTRAL su dati insufficienti)
                return bars[-n_bars:] if bars else []
            # Binary search: ultimo bar con time <= current_time
            t = self.current_time
            lo, hi = 0, len(bars)
            while lo < hi:
                mid = (lo + hi) // 2
                if bars[mid]["time"] <= t:
                    lo = mid + 1
                else:
                    hi = mid
            end = lo  # primo index con time > t
            start = max(0, end - n_bars)
            return bars[start:end]

        return []

    def calc_order_margin(self, symbol: str, direction: str, lots: float, price: float) -> float:
        """Mock margin calc."""
        return lots * price * 0.02  # 2% margin requirement

    def send_order(self, request: dict) -> OrderResult:
        """Nel backtest, ordini sono always executed al prezzo richiesto."""
        return OrderResult(success=True, order_id=1)

    def close_position(self, position_id: int) -> OrderResult:
        """Nel backtest, chiusure sempre riuscite."""
        return OrderResult(success=True, order_id=1)

    def modify_position(
        self, position_id: int, sl: float | None = None, tp: float | None = None
    ) -> OrderResult:
        """Nel backtest, modifiche sempre riuscite."""
        return OrderResult(success=True, order_id=1)

    def partial_close(self, position_id: int, lots: float) -> OrderResult:
        """Nel backtest, chiusure parziali sempre riuscite."""
        return OrderResult(success=True, order_id=1)


def _calculate_metrics(trades: list[BacktestTrade], start_balance: float) -> BacktestReport:
    """Calcola metriche finali dal list di trades."""
    report = BacktestReport(trades=trades, start_balance=start_balance)

    if not trades:
        report.end_balance = start_balance
        return report

    report.total_trades = len(trades)
    winning = [t for t in trades if t.profit_pct > 0]
    losing = [t for t in trades if t.profit_pct <= 0]

    # Aggrega costi realistici
    report.total_spread_cost_usd = sum(t.spread_cost_usd for t in trades)
    report.total_commission_usd = sum(t.commission_usd for t in trades)
    report.total_slippage_cost_usd = sum(t.slippage_cost_usd for t in trades)
    report.total_gross_profit_usd = sum(t.gross_profit_usd for t in trades)
    report.total_net_profit_usd = sum(t.net_profit_usd for t in trades)

    report.winning_trades = len(winning)
    report.losing_trades = len(losing)
    report.winrate = report.winning_trades / report.total_trades if report.total_trades > 0 else 0.0

    if winning:
        report.avg_win_pct = sum(t.profit_pct for t in winning) / len(winning)
    if losing:
        report.avg_loss_pct = sum(t.profit_pct for t in losing) / len(losing)

    total_profit = sum(t.profit_pct for t in trades)
    report.total_profit_pct = total_profit
    report.end_balance = start_balance * (1 + total_profit / 100.0)

    gross_profit = sum(t.profit_pct for t in winning) if winning else 0
    gross_loss = abs(sum(t.profit_pct for t in losing)) if losing else 0
    # No losses + at least one win = profit_factor effettivamente infinito.
    # Convenzione: float('inf') per essere semanticamente corretto.
    if gross_loss > 0:
        report.profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        report.profit_factor = float("inf")
    else:
        report.profit_factor = 0.0

    report.expectancy = (
        report.winrate * report.avg_win_pct - (1 - report.winrate) * abs(report.avg_loss_pct)
    ) if report.total_trades > 0 else 0.0

    # Max drawdown
    cumulative = start_balance
    peak = start_balance
    max_dd = 0.0
    for trade in trades:
        cumulative *= (1 + trade.profit_pct / 100.0)
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak * 100.0 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    report.max_drawdown_pct = max_dd
    report.max_drawdown_abs = peak - (peak - max_dd / 100.0 * peak)

    # Sharpe (semplificato: assume daily returns, 252 trading days)
    if len(trades) > 1:
        returns = [t.profit_pct for t in trades]
        avg_ret = sum(returns) / len(returns)
        variance = sum((r - avg_ret) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5 if variance > 0 else 1e-6
        sharpe = (avg_ret / std_dev * (252 ** 0.5)) if std_dev > 0 else 0
        report.sharpe_ratio = sharpe
    else:
        report.sharpe_ratio = 0.0

    # Max consecutive losses
    max_consec = 0
    current_consec = 0
    for trade in trades:
        if trade.profit_pct <= 0:
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0
    report.max_consecutive_losses = max_consec

    # Avg trade duration
    if trades:
        total_duration = sum(
            (t.exit_time - t.entry_time).total_seconds() / 3600.0 for t in trades
        )
        report.avg_trade_duration_hours = total_duration / len(trades)

    return report


class BacktestEngine:
    """Engine principale: itera bar-by-bar, applica strategia, traccia trades."""

    def __init__(
        self,
        cfg: Config,
        symbol_to_bars: dict[str, list[dict]] | None = None,
        strategy_module=None,  # IntradayStrategy istanziata
        risk_engine_module=None,  # modulo risk_engine (espone evaluate_trade)
        mt5_client: BacktestMt5Client | None = None,
        initial_balance: float = 10000.0,
        logger: logging.Logger | None = None,
    ):
        """Inizializza engine.

        Modi di uso:
            (1) Passare symbol_to_bars → engine costruisce BacktestMt5Client interno e
                istanzia IntradayStrategy + risk_engine se non forniti.
            (2) Passare mt5_client già pronto + strategy_module + risk_engine_module.
        """
        self.cfg = cfg
        self.log = logger or logging.getLogger(__name__)

        # mt5_client e symbol_to_bars
        if mt5_client is not None:
            self.mt5_client = mt5_client
            self.symbol_to_bars = mt5_client.symbol_to_bars
        else:
            if symbol_to_bars is None:
                raise ValueError("Devi passare symbol_to_bars o mt5_client")
            self.symbol_to_bars = symbol_to_bars
            self.mt5_client = BacktestMt5Client(cfg, symbol_to_bars)

        # strategy: istanzia se non fornito
        if strategy_module is None:
            from strategy import IntradayStrategy
            strategy_module = IntradayStrategy(cfg, self.mt5_client, self.log)
        self.strategy = strategy_module

        # risk_engine: usa modulo default se non fornito
        if risk_engine_module is None:
            import risk_engine as _re
            risk_engine_module = _re
        self.risk_engine = risk_engine_module

        self.trades: list[BacktestTrade] = []
        self.open_positions: dict[int, PositionInfo] = {}
        self.position_counter = 1000
        self.account_state = AccountState(
            balance=initial_balance,
            equity=initial_balance,
            free_margin=initial_balance * 0.95,
            open_positions=[],
            today_realized_pnl=0.0,
            starting_balance_of_day=initial_balance,
        )

    def run(self, symbols: list[str]) -> BacktestReport:
        """Esegui backtest su tutti i simboli nel dataset.

        Logica:
        1. Itera su bar comuni (assume stesso numero di bar per tutti i simboli)
        2. Per ogni bar: analizza simboli, genera proposte, esegui ordini
        3. Traccia P&L, chiudi trade su SL/TP hit
        4. Ritorna report finale con metriche
        """
        # Determina numero massimo di bar
        max_bars = min(
            len(bars) for bars in self.symbol_to_bars.values()
        ) if self.symbol_to_bars else 0

        for bar_idx in range(max_bars):
            # Avanza indice bar per tutti i simboli
            for symbol in symbols:
                self.mt5_client.current_bar_index[symbol] = bar_idx

            # Aggiorna current_time per intermarket lookup (time-based).
            # Usa primo simbolo trading come reference.
            if symbols:
                ref_bars = self.symbol_to_bars.get(symbols[0], [])
                if bar_idx < len(ref_bars):
                    self.mt5_client.current_time = int(ref_bars[bar_idx]["time"])

            # Valuta posizioni aperte: SL/TP hit?
            self._evaluate_open_positions(bar_idx)

            # Analizza simboli e genera proposte
            for symbol in symbols:
                bars = self.symbol_to_bars.get(symbol, [])
                if bar_idx >= len(bars):
                    continue

                setup = self.strategy.analyze_symbol(symbol, self.account_state)
                if setup.setup_type != "READY" or setup.direction is None:
                    continue

                # Confidence gate: mirror live behavior (scanner gate-keeps su MIN_CONFIDENCE_TO_PROPOSE)
                min_conf = getattr(self.cfg, "MIN_CONFIDENCE_TO_PROPOSE", 0.60)
                if setup.confidence < min_conf:
                    continue

                proposal = self.strategy.build_trade_proposal(symbol, setup)

                # Risk engine approval — usa evaluate_trade (signature reale)
                if hasattr(self.risk_engine, "evaluate_trade"):
                    decision = self.risk_engine.evaluate_trade(
                        proposal, self.account_state, self.mt5_client, self.cfg
                    )
                    approved = decision.approved
                    size = decision.size_lots
                else:
                    # Fallback: modulo custom con .evaluate(proposal, account)
                    approved, size, _ = self.risk_engine.evaluate(
                        proposal, self.account_state
                    )
                if not approved:
                    continue

                # Execute order
                self._execute_order(proposal, size, bar_idx)

        # Genera report
        return _calculate_metrics(self.trades, self.account_state.starting_balance_of_day)

    def _pip_size(self, symbol: str) -> float:
        """Dimensione pip per simbolo. Forex 5-digit: 0.0001. JPY: 0.01. Metalli: 0.01."""
        s = symbol.upper()
        if "JPY" in s:
            return 0.01
        if s in ("XAUUSD", "GOLD", "USOIL", "WTI", "UKOIL", "XAGUSD"):
            return 0.01
        return 0.0001

    def _pip_value_usd(self, symbol: str, lots: float) -> float:
        """Valore monetario di 1 pip per N lots. Approx forex maggiori: $10/pip per 1 lot."""
        s = symbol.upper()
        if "JPY" in s:
            return 9.0 * lots  # ~$9/pip per 1 lot USDJPY (varia con prezzo)
        if s in ("XAUUSD", "GOLD"):
            return 1.0 * lots  # 0.01 mossa × 100 oz = $1
        if s in ("USOIL", "WTI", "UKOIL"):
            return 10.0 * lots  # 0.01 mossa × 1000 barrels = $10
        return 10.0 * lots  # forex maggiori 0.0001 × 100k = $10

    def _evaluate_open_positions(self, bar_idx: int) -> None:
        """Valuta posizioni aperte: check SL/TP hit con slippage realistico."""
        closed_tickets = []
        slippage_pips = float(getattr(self.cfg, "BACKTEST_SLIPPAGE_PIPS", 0.5))
        commission_per_lot = float(getattr(self.cfg, "BACKTEST_COMMISSION_PER_LOT", 5.0))

        for ticket, pos in list(self.open_positions.items()):
            bars = self.symbol_to_bars.get(pos.symbol, [])
            if bar_idx >= len(bars):
                continue

            bar = bars[bar_idx]
            exit_price = None
            exit_reason = "MANUAL"
            pip = self._pip_size(pos.symbol)

            # Check SL/TP hit. Convenzione conservativa: se entrambi toccati
            # nello stesso bar, SL hit prima (worst case).
            # Slippage: SL hit a prezzo PEGGIORE (oltre SL), TP hit a prezzo limit esatto.
            if pos.direction == "BUY":
                if bar["low"] <= pos.stop_loss:
                    exit_price = pos.stop_loss - slippage_pips * pip  # peggio per BUY
                    exit_reason = "SL"
                elif bar["high"] >= pos.take_profit:
                    exit_price = pos.take_profit  # TP = limit, no slip avverso
                    exit_reason = "TP"
            else:  # SELL
                if bar["high"] >= pos.stop_loss:
                    exit_price = pos.stop_loss + slippage_pips * pip  # peggio per SELL
                    exit_reason = "SL"
                elif bar["low"] <= pos.take_profit:
                    exit_price = pos.take_profit
                    exit_reason = "TP"

            if exit_price is not None:
                # Profit lordo in price points, poi conversione USD
                price_diff = (exit_price - pos.entry_price) * (
                    1 if pos.direction == "BUY" else -1
                )
                pip_units = price_diff / pip
                gross_usd = pip_units * self._pip_value_usd(pos.symbol, pos.lots)

                # Costi: commission round-trip (open+close) + slippage già nel exit_price
                commission_usd = commission_per_lot * pos.lots * 2.0
                # Slippage cost separato per reporting (già scontato in exit_price)
                slippage_cost_usd = (
                    slippage_pips * self._pip_value_usd(pos.symbol, pos.lots)
                    if exit_reason == "SL" else 0.0
                )
                # Spread cost già scontato in entry_price (vedi _execute_order)
                spread_pips = float(getattr(self.cfg, "BACKTEST_SPREAD_PIPS", 1.0))
                spread_cost_usd = spread_pips * self._pip_value_usd(pos.symbol, pos.lots)

                net_usd = gross_usd - commission_usd

                # profit_pct = net_usd / starting_balance × 100 (per consistency con metric calc)
                start_bal = self.account_state.starting_balance_of_day
                profit_pct = (net_usd / start_bal * 100.0) if start_bal > 0 else 0.0

                # R multiple: profit_net / risk_iniziale_usd
                risk_pips = abs(pos.entry_price - pos.stop_loss) / pip
                risk_usd = risk_pips * self._pip_value_usd(pos.symbol, pos.lots)
                profit_r = (net_usd / risk_usd) if risk_usd > 0 else 0.0

                entry_time = self._bar_to_datetime(bars, 0)
                exit_time = self._bar_to_datetime(bars, bar_idx)

                self.trades.append(
                    BacktestTrade(
                        symbol=pos.symbol,
                        direction=pos.direction,
                        entry_time=entry_time,
                        entry_price=pos.entry_price,
                        stop_loss=pos.stop_loss,
                        take_profit=pos.take_profit,
                        lots=pos.lots,
                        exit_time=exit_time,
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                        profit_pct=profit_pct,
                        profit_r=profit_r,
                        spread_cost_usd=spread_cost_usd,
                        commission_usd=commission_usd,
                        slippage_cost_usd=slippage_cost_usd,
                        gross_profit_usd=gross_usd,
                        net_profit_usd=net_usd,
                    )
                )

                # Aggiorna account in USD reali
                self.account_state.balance += net_usd
                self.account_state.equity = self.account_state.balance

                closed_tickets.append(ticket)

        for ticket in closed_tickets:
            del self.open_positions[ticket]

    def _execute_order(self, proposal: TradeProposal, size: float, bar_idx: int) -> None:
        """Esegui ordine (apri posizione) con spread realistico applicato a entry."""
        bars = self.symbol_to_bars.get(proposal.symbol, [])
        if bar_idx >= len(bars):
            return

        bar = bars[bar_idx]
        spread_pips = float(getattr(self.cfg, "BACKTEST_SPREAD_PIPS", 1.0))
        pip = self._pip_size(proposal.symbol)

        # Entry: BUY paga spread (entry @ ask = close + spread/2 lato bid-ask).
        # Approssimazione conservativa: full spread sulla direzione adversa.
        # BUY entry @ close + spread, SELL entry @ close - spread.
        base_price = bar["close"]
        if proposal.direction == "BUY":
            entry_price = base_price + spread_pips * pip
        else:
            entry_price = base_price - spread_pips * pip

        ticket = self.position_counter
        self.position_counter += 1

        pos = PositionInfo(
            symbol=proposal.symbol,
            lots=size,
            direction=proposal.direction,
            entry_price=entry_price,
            stop_loss=proposal.stop_loss_price,
            take_profit=proposal.take_profit_price,
            profit=0.0,
            ticket=ticket,
        )

        self.open_positions[ticket] = pos
        self.account_state.open_positions.append(pos)

    def _bar_to_datetime(self, bars: list[dict], idx: int) -> datetime:
        """Converte bar index a datetime."""
        if idx < 0 or idx >= len(bars):
            return datetime.now()
        return datetime.fromtimestamp(bars[idx].get("time", 0))

