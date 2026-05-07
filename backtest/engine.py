"""Event-driven backtest engine (BACK-02, BACK-04). Plan 01-05.

Drives IntradayStrategy through a bar stream from load_bars, with
BacktestBroker injected as the BrokerProtocol implementation. Persists
trade rows + run metadata to logs/trades.db (D-07).

Design decisions (per RESEARCH §Open Questions RESOLVED):
  - Bypass StrategyEnvironment gates: build a Config-shaped clone with
    INTRADAY_START_HOUR=0, INTRADAY_END_HOUR=24, OPERATING_WEEKDAYS=0..6,
    AVOID_MAJOR_NEWS_TIMES=False, USE_SESSION_FILTER=False (Open Q 2 hybrid:
    we DO inject a StrategyEnvironment but with always-open windows; risk_engine
    session filter is also disabled).
  - Call strategy.analyze_symbol directly per bar; do NOT route through
    run_cycle (Open Q 3 — run_cycle includes scheduler logic irrelevant here).
  - decision_context_json captured at signal time from setup.indicators
    (already a dict snapshot of indicators); stashed on BacktestBroker via the
    additive `context` kwarg added in Plan 04 stub. The broker carries it on
    VirtualPosition and emits it on the closed-trade row.

Idempotency (skill principle 4): run_id = MD5(symbol|tf|first.time|last.time|
cost_hash)[:16]. Re-running the same configuration produces the same run_id;
LedgerWriter.record_run is INSERT OR REPLACE so re-runs overwrite cleanly.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Config
from models import AccountState, TradeProposal
from risk_engine import evaluate_trade
from strategy import IntradayStrategy, StrategyEnvironment
from backtest.broker import BacktestBroker, VirtualPosition
from backtest.costs import CostModel, load_cost_model
from backtest.ledger import LedgerWriter
from backtest.loader import Bar, load_bars


_log = logging.getLogger(__name__)


def _always_open_cfg(base: Config | None = None) -> Config:
    """Return a Config with all time-of-day / weekday / news / session gates disabled."""
    cfg = copy.copy(base) if base is not None else Config()
    cfg.INTRADAY_START_HOUR = 0
    cfg.INTRADAY_END_HOUR = 24
    cfg.OPERATING_WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]
    cfg.AVOID_MAJOR_NEWS_TIMES = False
    cfg.USE_SESSION_FILTER = False
    return cfg


def _compute_run_id(
    symbol: str, timeframe: str, first_time: int, last_time: int, cost_hash: str,
) -> str:
    payload = f"{symbol}|{timeframe}|{first_time}|{last_time}|{cost_hash}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]


def _hash_cost_yaml(yaml_path: Path | None) -> str:
    if yaml_path is None or not Path(yaml_path).exists():
        return "nohash"
    return hashlib.md5(Path(yaml_path).read_bytes()).hexdigest()[:16]


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class BacktestEngine:
    """Event-driven engine: one bar at a time, no future leak.

    Order per bar:
      1. broker.advance(bar) → may close prior open positions (SL/TP/gap).
         Closed rows appended to closed_trades + equity_curve updated.
      2. If we have at least INTRADAY_LOOKBACK_BARS bars in window, call
         strategy.analyze_symbol(symbol, account_state).
      3. If setup is READY: build proposal → risk_engine.evaluate_trade →
         if approved, broker.send_order(...) with context = setup.indicators
         snapshot.
      4. After last bar, force-close any remaining open positions at last
         bar's close, exit_reason="CLOSE_END".
    """

    def __init__(
        self,
        bars: list[Bar],
        symbol: str,
        timeframe: str,
        cost_model: CostModel,
        cfg: Config | None = None,
        initial_balance: float = 10_000.0,
        run_id: str | None = None,
        ledger: LedgerWriter | None = None,
        fold_index: int | None = None,
        cost_yaml_hash: str = "nohash",
    ) -> None:
        if not bars:
            raise ValueError("BacktestEngine requires at least one bar")
        self.bars = bars
        self.symbol = symbol
        self.timeframe = timeframe
        self.cost_model = cost_model
        self.cfg = _always_open_cfg(cfg)
        self.initial_balance = float(initial_balance)
        self.fold_index = fold_index
        self.cost_yaml_hash = cost_yaml_hash
        self.ledger = ledger
        self.run_id = run_id or _compute_run_id(
            symbol, timeframe, bars[0].time, bars[-1].time, cost_yaml_hash,
        )

    def run(self) -> dict[str, Any]:
        broker = BacktestBroker(
            symbol=self.symbol,
            timeframe=self.timeframe,
            initial_balance=self.initial_balance,
            cost_model=self.cost_model,
        )
        env = StrategyEnvironment(self.cfg, _log)
        strat = IntradayStrategy(self.cfg, broker, _log, environment=env)

        lookback = max(50, int(getattr(self.cfg, "INTRADAY_LOOKBACK_BARS", 200)))
        equity_curve: list[float] = [self.initial_balance]
        # Track per-position pending decision context, keyed by position_id.
        pending_ctx: dict[int, dict] = {}

        started_at = datetime.now(tz=timezone.utc).isoformat()

        # Override strategy.timeframe so analyze_symbol uses our timeframe.
        # Strategy reads cfg.INTRADAY_TIMEFRAME — set to our timeframe.
        self.cfg.INTRADAY_TIMEFRAME = self.timeframe

        for idx, bar in enumerate(self.bars):
            # 1. Advance broker — collects any same-bar closes (from open positions
            #    registered on PRIOR bars; entry_bar_index gate prevents same-bar exit).
            closed_rows = broker.advance(bar)
            for row in closed_rows:
                equity_curve.append(broker._balance)
                # Attach decision context if we stashed one at entry.
                ctx = pending_ctx.pop(row["position_id"], None)
                if ctx is not None:
                    row["decision_context_json"] = ctx

            # Need enough warmup bars before strategy can run.
            if idx + 1 < lookback:
                continue

            # 2. Build account state and call strategy.
            account_state = broker.get_account_state()
            try:
                setup = strat.analyze_symbol(self.symbol, account_state)
            except Exception as exc:
                _log.warning("analyze_symbol failed at bar %d: %s", idx, exc)
                continue

            if setup.setup_type != "READY" or setup.direction is None:
                continue

            # 3. Build proposal.
            try:
                proposal = strat.build_trade_proposal(self.symbol, setup)
            except Exception as exc:
                _log.warning("build_trade_proposal failed at bar %d: %s", idx, exc)
                continue

            # 4. Risk evaluation (uses broker.get_symbol_info + calc_order_margin).
            try:
                decision = evaluate_trade(proposal, account_state, broker, self.cfg)
            except Exception as exc:
                _log.warning("evaluate_trade failed at bar %d: %s", idx, exc)
                continue

            if not decision.approved:
                continue

            # 5. Open virtual position with decision context attached.
            ctx_snapshot = self._build_ctx(setup, proposal, decision.size_lots)
            order = broker.send_order(
                symbol=proposal.symbol,
                direction=proposal.direction,
                lots=decision.size_lots,
                sl=decision.adjusted_stop_loss,
                tp=decision.adjusted_take_profit,
                comment="backtest",
                context=ctx_snapshot,
            )
            if order.success and order.order_id is not None:
                pending_ctx[order.order_id] = ctx_snapshot

        # 6. Force-close any remaining open positions at the last bar close.
        if broker._positions:
            last_bar = self.bars[-1]
            for pos_id in list(broker._positions.keys()):
                row = broker._close_virtual(
                    pos_id, last_bar.close, "CLOSE_END", last_bar.time,
                )
                equity_curve.append(broker._balance)
                ctx = pending_ctx.pop(pos_id, None)
                if ctx is not None:
                    row["decision_context_json"] = ctx

        # 7. Persist.
        finished_at = datetime.now(tz=timezone.utc).isoformat()
        rows_for_ledger = [self._row_for_ledger(r) for r in broker._closed_trades]

        run_meta = {
            "run_id": self.run_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "date_start": _iso(self.bars[0].time),
            "date_end": _iso(self.bars[-1].time),
            "cost_yaml_hash": self.cost_yaml_hash,
            "profile": getattr(self.cfg, "RISK_MODE", "CONSERVATIVE"),
            "n_folds": 1,
            "fold_mode": "rolling",
            "train_ratio": 4,
            "started_at": started_at,
            "finished_at": finished_at,
            "total_trades": len(rows_for_ledger),
            "sharpe": None,
            "sortino": None,
            "max_dd_pct": None,
            "hit_rate": None,
            "expectancy_usd": None,
            "profit_factor": None,
            "avg_r": None,
            "total_pnl_usd": round(broker._balance - self.initial_balance, 2),
        }

        if self.ledger is not None:
            self.ledger.record_run(run_meta)
            if rows_for_ledger:
                self.ledger.insert_trades(self.run_id, self.fold_index, rows_for_ledger)

        return {
            "run_id": self.run_id,
            "trades": rows_for_ledger,
            "equity_curve": equity_curve,
            "bars_processed": len(self.bars),
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_ctx(setup, proposal: TradeProposal, lots: float) -> dict:
        """Indicator snapshot at signal time, JSON-serializable."""
        indicators = setup.indicators or {}
        ctx = {
            "symbol": setup.symbol,
            "timeframe": setup.timeframe,
            "setup_type": setup.setup_type,
            "direction": setup.direction,
            "confidence": setup.confidence,
            "reason": setup.reason,
            "lots_proposed": lots,
        }
        # Copy known scalar indicator keys (skip non-serializable nested objects).
        for k, v in indicators.items():
            try:
                json.dumps(v, default=str)
                ctx[k] = v
            except (TypeError, ValueError):
                ctx[k] = repr(v)
        return ctx

    def _row_for_ledger(self, closed: dict) -> dict:
        """Translate BacktestBroker closed-trade dict into LedgerWriter row schema."""
        ctx = closed.get("decision_context_json")
        if isinstance(ctx, dict):
            setup_type = ctx.get("setup_type")
            confidence = ctx.get("confidence")
        else:
            setup_type = None
            confidence = None
        # Risk_usd: |entry-sl| in pips * pip_value * lots — approximate from costs.
        try:
            sl_dist_pips = abs(closed["entry_price"] - closed["sl"]) / self.cost_model.pip_size
            risk_usd = sl_dist_pips * self.cost_model.pip_value_usd * closed["lots"]
        except Exception:
            risk_usd = None
        return {
            "entry_time": _iso(int(closed["entry_time"])),
            "exit_time": _iso(int(closed["exit_time"])),
            "symbol": closed["symbol"],
            "timeframe": self.timeframe,
            "direction": closed["direction"],
            "entry_price": closed["entry_price"],
            "exit_price": closed["exit_price"],
            "sl": closed.get("sl"),
            "tp": closed.get("tp"),
            "lot_size": closed["lots"],
            "pnl_pips": closed.get("pnl_pips"),
            "pnl_usd": closed.get("pnl_usd"),
            "risk_usd": risk_usd,
            "exit_reason": closed.get("exit_reason"),
            "setup_type": setup_type,
            "confidence": confidence,
            "decision_context_json": ctx,
        }


def run_backtest(
    csv_path: Path,
    symbol: str,
    timeframe: str,
    costs_yaml: Path,
    cfg: Config | None = None,
    initial_balance: float = 10_000.0,
    date_start: datetime | None = None,
    date_end: datetime | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Convenience: load_bars + load_cost_model + BacktestEngine.run()."""
    bars = load_bars(csv_path, symbol, timeframe, date_start, date_end)
    if not bars:
        raise ValueError(f"no bars loaded from {csv_path} for {symbol} {timeframe}")
    cost = load_cost_model(symbol, bars[0].close, costs_yaml)
    cost_hash = _hash_cost_yaml(costs_yaml)

    if db_path is None:
        # Default to project logs/trades.db (mirrors logger._trades_db_path pattern).
        db_path = Path("logs/trades.db")
    ledger = LedgerWriter(db_path)

    eng = BacktestEngine(
        bars=bars,
        symbol=symbol,
        timeframe=timeframe,
        cost_model=cost,
        cfg=cfg,
        initial_balance=initial_balance,
        ledger=ledger,
        cost_yaml_hash=cost_hash,
    )
    return eng.run()
