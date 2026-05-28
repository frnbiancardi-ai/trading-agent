"""Backtest handlers per Phase 6 Wave 2 (MCP-01/02/03 + cancel_backtest D-A4).

Tool inclusi:
- run_backtest (MCP-01) — D-A1 async submit (1 backtest in 1 worker process)
- get_backtest_metrics (MCP-02) — D-A3 polymorphic poll (running/done/failed/cancelled)
- walk_forward_validate (MCP-03) — D-A1 N-fold serial in singolo job (Phase 1 D-06)
- cancel_backtest (D-A4 derivato) — non in REQUIREMENTS ma necessario per UX cancel

replay_decision (MCP-15) è ARRESTATO qui — implementato in Wave 4 (06-05).

Worker `_backtest_worker` / `_walk_forward_worker`:
- TOP-LEVEL (picklable per ProcessPoolExecutor)
- NON importa mt5_client (Phase 5 D-15: MetaTrader5 lib non fork-safe)
- NON usa stdout (Pitfall 8: corromperebbe MCP JSON-RPC framing)
- Importa backtest.* localmente (lazy import per pickle safety + perf module-load)

Convenzione argv worker (rispettata per coerenza con fixture test):
    _backtest_worker(run_id, symbol, timeframe, date_start, date_end, profile,
                     db_path, costs_yaml_path)
    → ultimi due sono db_path + costs_yaml_path (test stub accede via args[-2]).
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.types import Tool

from mcp_tools.errors import ErrorCodes, envelope


# ── run_id helpers ─────────────────────────────────────────────────────────────

def _sortable_utc_ts() -> str:
    """ISO8601 compresso, sortable lessicograficamente: YYYYMMDDTHHMMSSZ.

    D-A2: il run_id contiene questo timestamp come prefisso → ordinamento
    cronologico naturale per `ORDER BY run_id` su backtest_runs.
    """
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_run_id(symbol: str, tf: str, profile: str, suffix: str = "") -> str:
    """D-A2: mcp_{utc_ts}_{symbol}_{tf}_{profile}[_{suffix}].

    suffix=`wfv{N}` per walk_forward (es. mcp_20260511T..._EURUSD_M15_MODERATE_wfv3).
    """
    base = f"mcp_{_sortable_utc_ts()}_{symbol}_{tf}_{profile}"
    return f"{base}_{suffix}" if suffix else base


# ── Tool registrations (D-F1 rigoroso) ─────────────────────────────────────────

RUN_BACKTEST_TOOL = Tool(
    name="run_backtest",
    description=(
        "Avvia backtest async sullo storico CSV per (symbol, timeframe, date_range, "
        "profile). Ritorna run_id immediato (non blocca); pollare get_backtest_metrics"
        "(run_id) per status/metrics. Max 1 run concorrente (cap MCP_MAX_CONCURRENT_RUNS); "
        "nuovo run mentre uno gira → error run_in_progress. Run prefix: "
        "mcp_<utc_ts>_<symbol>_<tf>_<profile>."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol":     {"type": "string", "enum": ["EURUSD", "GBPUSD", "USDJPY"]},
            "timeframe":  {"type": "string", "enum": ["M15", "M30", "H1"]},
            "date_start": {"type": "string", "description": "ISO8601 UTC, es. 2024-01-01T00:00:00Z"},
            "date_end":   {"type": "string", "description": "ISO8601 UTC, esclusivo"},
            "profile":    {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]},
        },
        "required": ["symbol", "timeframe", "date_start", "date_end", "profile"],
    },
)


GET_BACKTEST_METRICS_TOOL = Tool(
    name="get_backtest_metrics",
    description=(
        "Polling status/metrics di un run avviato da run_backtest o walk_forward_validate. "
        "RESPONSE POLIMORFICO per `status` (D-A3):\n"
        " - running: {run_id, status, progress_pct, bars_processed, bars_total, trades_so_far, started_at}\n"
        " - done:    {run_id, status, metrics: {sharpe, sortino, max_dd_pct, hit_rate, "
        "expectancy_pips, profit_factor, avg_R, longest_dd_days, trade_count}, equity_curve_path, finished_at}\n"
        " - failed:  {run_id, status, error_message, started_at, failed_at}\n"
        " - cancelled: {run_id, status, started_at, cancelled_at}\n"
        "Polling consigliato >=5s (Pitfall 4 SQLite contention)."
    ),
    inputSchema={
        "type": "object",
        "properties": {"run_id": {"type": "string"}},
        "required": ["run_id"],
    },
)


WALK_FORWARD_VALIDATE_TOOL = Tool(
    name="walk_forward_validate",
    description=(
        "Walk-forward validation rolling train/test su N folds (no shuffle, no overlap, "
        "Phase 1 D-06 walk_forward_slices). N folds eseguiti IN SERIE in un singolo job; "
        "stesso modello async di run_backtest (poll via get_backtest_metrics). "
        "n_folds cap=10 (Phase 1)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol":     {"type": "string", "enum": ["EURUSD", "GBPUSD", "USDJPY"]},
            "timeframe":  {"type": "string", "enum": ["M15", "M30", "H1"]},
            "date_start": {"type": "string"},
            "date_end":   {"type": "string"},
            "profile":    {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]},
            "n_folds":    {"type": "integer", "minimum": 2, "maximum": 10, "default": 5},
            "fold_mode":  {"type": "string", "enum": ["rolling", "expanding"], "default": "rolling"},
        },
        "required": ["symbol", "timeframe", "date_start", "date_end", "profile"],
    },
)


CANCEL_BACKTEST_TOOL = Tool(
    name="cancel_backtest",
    description=(
        "Cancella un run attivo. Marca backtest_runs.status='cancelled'. "
        "Cancel mid-execution su Windows: termina worker (Future.cancel False) → "
        "shutdown pool + ricreazione (Pitfall 6, possibile zombie window ~1s). "
        "Tool extra Phase 6 (D-A4 derivato), non in REQUIREMENTS."
    ),
    inputSchema={
        "type": "object",
        "properties": {"run_id": {"type": "string"}},
        "required": ["run_id"],
    },
)


# ── Worker functions (TOP-LEVEL, no MT5 import — Pitfall 1) ─────────────────────

def _parse_iso_utc(s: str) -> datetime:
    """Parse ISO8601 UTC tollerante a suffisso Z."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _backtest_worker(
    run_id: str,
    symbol: str,
    timeframe: str,
    date_start: str,
    date_end: str,
    profile: str,
    db_path: str,
    costs_yaml_path: str,
) -> dict:
    """Worker process: backtest CSV-driven, NO mt5.

    Lazy imports interni per picklability (Pitfall 1) + perf module-load.

    Pitfall 8: NO stdout. Logger configurato in init_logger usa RotatingFileHandler
    (file only) — sicuro.

    NB sui parametri: gli ULTIMI DUE sono `db_path` + `costs_yaml_path` per
    convenzione argv (rispettata dai test stub che accedono via args[-2]).
    """
    from logger import init_logger
    from config import Config
    cfg = Config()
    cfg.RISK_MODE = profile  # Phase 5 D-11: profile controlla i filtri risk_engine
    log = init_logger(cfg)

    from backtest.loader import load_bars
    from backtest.engine import BacktestEngine
    from backtest.costs import load_cost_model
    from backtest.ledger import LedgerWriter
    from backtest.metrics import compute_metrics

    log.info("worker start: run_id=%s symbol=%s tf=%s", run_id, symbol, timeframe)

    csv_path = Path("data/historical") / symbol / f"{timeframe}.csv"
    ds_dt = _parse_iso_utc(date_start)
    de_dt = _parse_iso_utc(date_end)
    bars = load_bars(csv_path, symbol, timeframe, ds_dt, de_dt)
    if not bars:
        raise RuntimeError(
            f"no bars loaded from {csv_path} for {symbol} {timeframe} "
            f"in [{date_start}, {date_end})"
        )

    cost_model = load_cost_model(symbol, bars[0].close, Path(costs_yaml_path))
    ledger = LedgerWriter(Path(db_path))

    eng = BacktestEngine(
        bars=bars,
        symbol=symbol,
        timeframe=timeframe,
        cost_model=cost_model,
        cfg=cfg,
        ledger=ledger,
        run_id=run_id,
    )
    result = eng.run()
    trades = result["trades"]

    metrics = compute_metrics(trades, timeframe=timeframe)
    metrics_dict = dataclasses.asdict(metrics)
    # Mapping: BacktestMetrics.max_drawdown_pct -> backtest_runs.max_dd_pct
    metrics_dict["max_dd_pct"] = metrics_dict.pop("max_drawdown_pct", None)
    # finalize_run NON conosce 'longest_dd_days' (non è colonna backtest_runs);
    # è una BacktestMetrics-only feature → estraggo prima di passare a finalize.
    metrics_dict.pop("longest_dd_days", None)
    # total_trades è la chiave canonica nel DDL backtest_runs
    ledger.finalize_run(run_id, status="done", **metrics_dict)

    log.info(
        "worker done: run_id=%s trades=%d sharpe=%.2f",
        run_id, len(trades), metrics.sharpe,
    )
    return {
        "run_id": run_id,
        "trades": len(trades),
        "metrics": metrics_dict,
    }


def _walk_forward_worker(
    run_id: str,
    symbol: str,
    timeframe: str,
    date_start: str,
    date_end: str,
    profile: str,
    n_folds: int,
    fold_mode: str,
    db_path: str,
    costs_yaml_path: str,
) -> dict:
    """Worker process: walk-forward N folds in serie (Phase 1 D-06).

    Stesso modello async di _backtest_worker; itera walk_forward_slices() e
    invoca BacktestEngine().run() per fold con fold_index attached.
    """
    from logger import init_logger
    from config import Config
    cfg = Config()
    cfg.RISK_MODE = profile
    log = init_logger(cfg)

    from backtest.walk_forward import walk_forward_slices
    from backtest.loader import load_bars
    from backtest.engine import BacktestEngine
    from backtest.costs import load_cost_model
    from backtest.ledger import LedgerWriter
    from backtest.metrics import compute_metrics

    csv_path = Path("data/historical") / symbol / f"{timeframe}.csv"
    ds_dt = _parse_iso_utc(date_start)
    de_dt = _parse_iso_utc(date_end)
    bars = load_bars(csv_path, symbol, timeframe, ds_dt, de_dt)
    if not bars:
        raise RuntimeError(
            f"no bars loaded for WF run {run_id} ({symbol} {timeframe})"
        )

    cost_model = load_cost_model(symbol, bars[0].close, Path(costs_yaml_path))
    ledger = LedgerWriter(Path(db_path))

    all_trades: list[dict] = []
    for fold_idx, (train_bars, test_bars) in enumerate(
        walk_forward_slices(bars, n_folds=n_folds, mode=fold_mode),
    ):
        if not test_bars:
            continue
        eng = BacktestEngine(
            bars=test_bars,
            symbol=symbol,
            timeframe=timeframe,
            cost_model=cost_model,
            cfg=cfg,
            ledger=ledger,
            run_id=f"{run_id}_fold{fold_idx}",
            fold_index=fold_idx,
        )
        result = eng.run()
        all_trades.extend(result["trades"])
        log.info(
            "WF fold %d/%d done: trades=%d",
            fold_idx + 1, n_folds, len(result["trades"]),
        )

    metrics = compute_metrics(all_trades, timeframe=timeframe)
    metrics_dict = dataclasses.asdict(metrics)
    metrics_dict["max_dd_pct"] = metrics_dict.pop("max_drawdown_pct", None)
    metrics_dict.pop("longest_dd_days", None)
    # Aggiungo n_folds + fold_mode al run row finale
    metrics_dict["n_folds"] = n_folds
    metrics_dict["fold_mode"] = fold_mode
    ledger.finalize_run(run_id, status="done", **metrics_dict)
    return {
        "run_id": run_id,
        "n_folds": n_folds,
        "trades": len(all_trades),
        "metrics": metrics_dict,
    }


# ── Handlers ────────────────────────────────────────────────────────────────────

def handle_run_backtest(
    args: dict,
    job_queue,
    cfg,
    db_path: str,
    costs_yaml_path: str,
) -> dict:
    """MCP-01 D-A1: async submit di un backtest CSV-driven.

    Ritorna il payload di JobQueue.submit (started + run_id) oppure
    run_in_progress envelope (D-A4 cap).
    """
    run_id = _build_run_id(args["symbol"], args["timeframe"], args["profile"])
    metadata = {
        "symbol": args["symbol"],
        "timeframe": args["timeframe"],
        "date_start": args["date_start"],
        "date_end": args["date_end"],
        "profile": args["profile"],
    }
    return job_queue.submit(
        run_id,
        _backtest_worker,
        metadata,
        run_id, args["symbol"], args["timeframe"],
        args["date_start"], args["date_end"], args["profile"],
        db_path, costs_yaml_path,
    )


def handle_walk_forward_validate(
    args: dict,
    job_queue,
    cfg,
    db_path: str,
    costs_yaml_path: str,
) -> dict:
    """MCP-03 D-A1: async submit, N folds in serie nel worker.

    n_folds default=5 (RESEARCH §Pattern 1 inputSchema default).
    n_folds > 10 → invalid_n_folds envelope (Phase 1 D-06 cap).
    """
    n_folds = int(args.get("n_folds", 5))
    fold_mode = args.get("fold_mode", "rolling")
    if n_folds > 10:
        return envelope(
            "invalid_n_folds",
            f"n_folds={n_folds} > cap Phase 1 (max 10)",
            run_id=None,
        )
    if n_folds < 2:
        return envelope(
            "invalid_n_folds",
            f"n_folds={n_folds} < min 2 per walk-forward",
            run_id=None,
        )
    run_id = _build_run_id(
        args["symbol"], args["timeframe"], args["profile"],
        suffix=f"wfv{n_folds}",
    )
    metadata = {
        "symbol": args["symbol"],
        "timeframe": args["timeframe"],
        "date_start": args["date_start"],
        "date_end": args["date_end"],
        "profile": args["profile"],
        "n_folds": n_folds,
        "fold_mode": fold_mode,
    }
    return job_queue.submit(
        run_id,
        _walk_forward_worker,
        metadata,
        run_id, args["symbol"], args["timeframe"],
        args["date_start"], args["date_end"], args["profile"],
        n_folds, fold_mode,
        db_path, costs_yaml_path,
    )


def handle_get_backtest_metrics(args: dict, job_queue, cfg) -> dict:
    """MCP-02 D-A3: polymorphic per status (running/done/failed/cancelled).

    Mapping colonne backtest_runs → payload `metrics`:
    - sharpe/sortino/max_dd_pct/hit_rate/profit_factor/avg_r passthrough
    - expectancy_usd → expectancy_pips (alias UX)
    - total_trades → trade_count
    - longest_dd_days non in DDL backtest_runs Wave 2 → None
    """
    run_id = args["run_id"]
    s = job_queue.status(run_id)
    if s.get("error") == "unknown_run_id":
        return envelope(
            ErrorCodes.UNKNOWN_RUN_ID,
            f"run_id sconosciuto: {run_id}",
            run_id=run_id,
        )
    st = s.get("status")
    if st in ("running", "running_ghost"):
        # running shape per D-A3
        return {
            "run_id": run_id,
            "status": "running",
            "progress_pct": s.get("progress_pct", 0.0),
            "bars_processed": s.get("bars_processed", 0),
            "bars_total": s.get("bars_total", 0),
            "trades_so_far": s.get("trades_so_far", 0),
            "started_at": s.get("started_at"),
        }
    if st == "done":
        row = s.get("_db_row") or {}
        metrics = {
            "sharpe": row.get("sharpe"),
            "sortino": row.get("sortino"),
            "max_dd_pct": row.get("max_dd_pct"),
            "hit_rate": row.get("hit_rate"),
            # Phase 5 DDL: expectancy_usd; payload UX usa expectancy_pips come alias
            "expectancy_pips": row.get("expectancy_usd"),
            "profit_factor": row.get("profit_factor"),
            "avg_R": row.get("avg_r"),
            "trade_count": row.get("total_trades"),
            "longest_dd_days": None,  # Wave 2: non persistito in backtest_runs
        }
        return {
            "run_id": run_id,
            "status": "done",
            "metrics": metrics,
            "equity_curve_path": _equity_path(run_id, cfg),
            "finished_at": s.get("finished_at"),
        }
    if st == "failed":
        return {
            "run_id": run_id,
            "status": "failed",
            "error_message": s.get("error_message"),
            "started_at": s.get("started_at"),
            "failed_at": s.get("failed_at"),
        }
    if st == "cancelled":
        return {
            "run_id": run_id,
            "status": "cancelled",
            "started_at": s.get("started_at"),
            "cancelled_at": s.get("cancelled_at"),
        }
    return envelope(
        "unknown_status", f"status inatteso: {st}", run_id=run_id,
    )


def _equity_path(run_id: str, cfg) -> str | None:
    """Path PNG equity curve (Phase 5 D-19). Wave 2: ritorna path se esiste."""
    candidate = Path(".planning/research/baseline-equity-curves") / f"{run_id}.png"
    return str(candidate) if candidate.exists() else None


def handle_cancel_backtest(args: dict, job_queue, cfg) -> dict:
    """D-A4 derivato: cancel run attivo (delega a JobQueue.cancel)."""
    return job_queue.cancel(args["run_id"])
