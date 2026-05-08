"""Worker per-slice per ProcessPoolExecutor (Phase 5 D-15).

Ogni worker carica CSV, calcola warm-up adattivo (D-07 BLOCKER 3), calcola indicator
cache UNA volta, gira 3 profile sequenziali riusando cache. Idempotency D-14: skip se
run_id esiste, --force pulisce prima.

CRITICO: il backend Agg di matplotlib DEVE precedere QUALSIASI import che catena a pyplot.
Su Windows spawn ctx, il backend non si propaga dal main → re-set qui.

Source: PATTERNS.md §slice_worker.py, CONTEXT.md §specifics.
"""
from __future__ import annotations

# CRITICO: backend Agg PRIMA di import indiretti pyplot
import matplotlib

matplotlib.use("Agg")

import functools  # noqa: E402  -- ordine import vincolato dal backend setup
import logging  # noqa: E402
import sqlite3  # noqa: E402
import subprocess  # noqa: E402
from datetime import date  # noqa: E402
from pathlib import Path  # noqa: E402

from backtest.loader import load_bars  # noqa: E402
from backtest.costs import load_cost_model  # noqa: E402
from backtest.ledger import LedgerWriter  # noqa: E402
from backtest.engine import BacktestEngine  # noqa: E402
from backtest.baseline.determinism import seed_for_run_id, file_sha256  # noqa: E402
from backtest.baseline.dataset_writer import (  # noqa: E402
    write_decisions_shard,
    write_drafts_shard,
)
from backtest.baseline.plot_writer import plot_equity_curve  # noqa: E402
from backtest.baseline.wal_setup import with_retry  # noqa: E402
from backtest.baseline.warmup import longest_lookback_required  # noqa: E402  -- BLOCKER 3 D-07

_log = logging.getLogger(__name__)

PROFILES = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


def _build_run_id(symbol: str, tf: str, profile: str, run_date: str | None = None) -> str:
    """D-13: run_id = baseline_{date}_{symbol}_{tf}_{profile}."""
    d = run_date or date.today().isoformat()
    return f"baseline_{d}_{symbol}_{tf}_{profile}"


def _run_id_exists(db_path: Path, run_id: str) -> bool:
    """Check idempotency D-14 — esiste già un run con questo run_id?"""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM backtest_runs WHERE run_id=?", (run_id,)
        ).fetchone()
    return row is not None


def _force_clear_run(db_path: Path, run_id: str) -> None:
    """RESEARCH §Pitfall: AUTOINCREMENT su backtest_trades duplica righe in --force.

    DELETE FROM backtest_trades + backtest_runs PRIMA di re-insert. Single connection
    con busy_timeout — WARNING 8 fix: non wrappare con `with_retry` (riapre conn ogni
    retry); usa busy_timeout built-in.
    """
    # WARNING 8 fix: single connection, busy_timeout, no with_retry wrapper.
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("DELETE FROM backtest_trades WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM backtest_runs WHERE run_id=?", (run_id,))
        conn.commit()
    finally:
        conn.close()


def _git_sha() -> str:
    """Best-effort git rev-parse HEAD per audit trail (D-17)."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).resolve().parents[2]),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:  # noqa: BLE001 -- best-effort, no propagation
        return "unknown"


def _audit_update_run(
    db_path: Path,
    run_id: str,
    seed_eff: int,
    cost_sha256: str,
    strategy_sha256: str,
    baseline_sha256: str,
    git: str,
) -> None:
    """Update backtest_runs con audit trail Phase 5 (D-17 + WARNING 12 sha256 full-64).

    WARNING 7 fix: helper esplicito (NO lambda con `and conn.commit()` truthiness bug).
    Single connection con busy_timeout — il caller può wrappare con `with_retry`.
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(
            "UPDATE backtest_runs SET slippage_seed_effective=?, "
            "strategy_yaml_hash=?, baseline_yaml_hash=?, git_sha=?, "
            "cost_yaml_sha256=?, strategy_yaml_sha256=?, baseline_yaml_sha256=? "
            "WHERE run_id=?",
            (
                seed_eff,
                strategy_sha256[:16],   # legacy md5[:16]-style column
                baseline_sha256[:16],
                git,
                cost_sha256,            # Phase 5 sha256 full-64 (WARNING 12 fix)
                strategy_sha256,
                baseline_sha256,
                run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def run_slice_3profiles(
    symbol: str,
    tf: str,
    baseline_cfg,             # BaselineConfig (frozen dataclass — Plan 05-07 definisce loader)
    costs_cfg_path: Path,     # Path al costs.yaml (load_cost_model lo richiede)
    strategy_cfg_path: Path,  # Path al strategy.yaml
    force: bool = False,
    ledger_db_path: Path | None = None,
    run_date: str | None = None,
    csv_path: Path | None = None,
) -> list[dict]:
    """Worker entry per ProcessPoolExecutor. Esegue 3 run sequenziali su (symbol, tf).

    Returns: list[dict] di 3 result, ciascuno con keys: run_id, profile, status,
    metrics, n_trades, n_drafts, equity_path, error (se status=FAILED).
    """
    ledger_db = Path(ledger_db_path) if ledger_db_path else Path("logs/trades.db")

    # 1. Load CSV (Phase 1 loader). csv_path opzionale — se None, runner lo deduce.
    if csv_path is None:
        # Convention Phase 1: data/{symbol}_{tf}.csv (placeholder; runner lo passa esplicito).
        csv_path = Path(f"data/{symbol}_{tf}.csv")
    # Plan 05-08 Option B (scope reduction 10y): filtra date_start/date_end dal
    # baseline_cfg PRIMA del warm_up slicing per evitare il full-history 23.5y
    # (engine O(N^2) → smoke fuori budget BACK-07 SC#1 <30min). load_bars
    # supporta datetime|None inclusive/exclusive (backtest/loader.py:30-31).
    from datetime import datetime  # noqa: E402 -- lazy import per evitare cost top-level
    ds = (
        datetime.fromisoformat(baseline_cfg.date_start)
        if getattr(baseline_cfg, "date_start", None) else None
    )
    de = (
        datetime.fromisoformat(baseline_cfg.date_end)
        if getattr(baseline_cfg, "date_end", None) else None
    )
    bars = load_bars(csv_path, symbol, tf, date_start=ds, date_end=de)

    # 2. Warm-up adaptive (D-07 BLOCKER 3 fix): max(warm_up_min_bars, longest_lookback)
    # Reads strategy.yaml indicator config; fallback 200 se non parseable.
    try:
        import yaml
        with open(strategy_cfg_path, encoding="utf-8") as f:
            strategy_cfg = yaml.safe_load(f) or {}
    except Exception:  # noqa: BLE001
        strategy_cfg = {}
    warm_up = max(
        baseline_cfg.warm_up_min_bars,
        longest_lookback_required(strategy_cfg),
    )
    bars = bars[warm_up:]
    _log.info(
        "slice %s %s warm_up=%d (cfg=%d, longest_lookback=%d)",
        symbol, tf, warm_up, baseline_cfg.warm_up_min_bars,
        longest_lookback_required(strategy_cfg),
    )

    # 3. Indicator cache UNA volta per slice (D-15)
    # Plan 05-08 deviation Rule 3 — Blocker: indicators.compute_all_extended
    # accetta list[dict] (Phase 2 API reale, indicators/aggregate.py:68
    # accede `b["close"]`), MA backtest.engine.BacktestEngine accetta
    # list[Bar] (dataclass). Convertiamo Bar->dict SOLO per il calcolo
    # indicatori, lasciando bars come list[Bar] per il resto del worker.
    from indicators import compute_all_extended  # noqa: E402  -- lazy import Phase 2 dep
    bars_dict = [
        {
            "time": b.time,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
    indicators_full = compute_all_extended(bars_dict)

    # 4. Cost model (Phase 1 contract richiede entry_price per pip-value JPY)
    entry_price_hint = float(bars[0].close) if bars else 1.0
    cost = load_cost_model(symbol, entry_price_hint, costs_cfg_path)

    # 5. Hashes audit trail (D-17 + WARNING 12 fix: full 64-char sha256)
    cost_sha256 = file_sha256(Path(costs_cfg_path))
    strategy_sha256 = file_sha256(strategy_cfg_path)
    baseline_sha256 = file_sha256(Path("data/configs/baseline.yaml"))
    git = _git_sha()

    results: list[dict] = []
    timeout = baseline_cfg.timeout_bars[tf]  # D-05 per-TF cap

    for profile in PROFILES:
        run_id = _build_run_id(symbol, tf, profile, run_date)

        # Idempotency D-14
        if _run_id_exists(ledger_db, run_id):
            if not force:
                _log.warning(
                    "skip %s: già esistente, usa --force per overwrite", run_id,
                )
                results.append({
                    "run_id": run_id,
                    "profile": profile,
                    "symbol": symbol,
                    "timeframe": tf,
                    "status": "SKIPPED",
                })
                continue
            _log.info("force: pulisco run_id %s prima di re-insert", run_id)
            # WARNING 8 fix: NO with_retry wrapper — _force_clear_run ha busy_timeout interno.
            _force_clear_run(ledger_db, run_id)

        try:
            seed_eff = seed_for_run_id(run_id)
            ledger = LedgerWriter(ledger_db)
            engine = BacktestEngine(
                bars=bars,
                symbol=symbol,
                timeframe=tf,
                cost_model=cost,
                initial_balance=baseline_cfg.equity_initial_eur,
                run_id=run_id,
                ledger=ledger,
                cost_yaml_hash=cost_sha256[:16],  # legacy md5[:16]-style backwards compat Phase 1
                indicators_full=indicators_full,
                risk_profile=profile,
                timeout_bars=timeout,
                equity_initial=baseline_cfg.equity_initial_eur,
            )
            engine_result = engine.run()

            # Persist parquet shards (D-01/D-02/D-03)
            shard_dir = Path(baseline_cfg.training_data_dir)
            n_trades = len(engine_result.get("decisions_rows", []))
            n_drafts = len(engine_result.get("drafts_rows", []))
            write_decisions_shard(
                engine_result.get("decisions_rows", []), run_id, shard_dir,
            )
            write_drafts_shard(
                engine_result.get("drafts_rows", []), run_id, shard_dir,
            )

            # Plot equity (D-19)
            png_path = (
                Path(baseline_cfg.equity_curves_dir)
                / f"{symbol}_{tf}_{profile}.png"
            )
            plot_equity_curve(engine_result["equity_curve"], png_path)

            # Audit trail extra: aggiorna backtest_runs con campi Phase 5
            # WARNING 7 fix: NO lambda — uso functools.partial (no truthiness bug,
            # binding esplicito dei parametri).
            # WARNING 12 fix: scrivi sha256 FULL 64-char nelle nuove colonne; legacy
            # cost_yaml_hash mantiene formato md5[:16] per backwards compat Phase 1.
            audit_call = functools.partial(
                _audit_update_run,
                ledger_db, run_id, seed_eff,
                cost_sha256, strategy_sha256, baseline_sha256, git,
            )
            with_retry(audit_call)

            results.append({
                "run_id": run_id,
                "profile": profile,
                "status": "OK",
                "metrics": engine_result.get("metrics"),
                "n_trades": n_trades,
                "n_drafts": n_drafts,
                "equity_path": str(png_path),
                "symbol": symbol,
                "timeframe": tf,
            })
        except Exception as exc:  # noqa: BLE001 -- worker boundary, errori serializzabili al main
            _log.error("run_id=%s fallito: %s", run_id, exc, exc_info=True)
            results.append({
                "run_id": run_id,
                "profile": profile,
                "status": "FAILED",
                "error": str(exc),
                "symbol": symbol,
                "timeframe": tf,
            })

    return results
