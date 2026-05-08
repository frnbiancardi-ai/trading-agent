"""Phase 5 baseline orchestrator: 27 run paralleli (BACK-07, INT-01).

Hybrid orchestration D-15: ProcessPoolExecutor(9) su (symbol, tf), 3 profile
sequenziali per worker riusando indicator cache (compute_all_extended UNA volta).
Wall-clock target <30 min su 8-core dev laptop (SC#1).

Source: PATTERNS.md §runner.py, RESEARCH.md §Pattern 1, CONTEXT.md §specifics.

NB: il worker `run_slice_3profiles` richiede `costs_cfg_path` (Path al costs.yaml),
NON un dict pre-caricato — vedi 05-06a-SUMMARY.md deviation #1 (load_cost_model
signature reale è (symbol, entry_price, yaml_path)).
"""
from __future__ import annotations

import logging
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from itertools import product
from pathlib import Path

import yaml
from tqdm import tqdm

from backtest.baseline.slice_worker import run_slice_3profiles
from backtest.baseline.wal_setup import enable_sqlite_wal
from backtest.baseline.dataset_writer import finalize_parquet_shards
from backtest.baseline.report_writer import write_baseline_report
from backtest.baseline.determinism import file_sha256

_log = logging.getLogger(__name__)

PAIRS = ("EURUSD", "GBPUSD", "USDJPY")
TFS = ("M15", "M30", "H1")


@dataclass(frozen=True)
class BaselineConfig:
    """Frozen config caricato da data/configs/baseline.yaml (D-15, D-17, D-19, D-20).

    Frozen → safe da pickle nei worker spawn (Windows ProcessPoolExecutor).
    """
    equity_initial_eur: float
    slippage_seed: int
    timeout_bars: dict          # {"M15": 96, "M30": 96, "H1": 120}
    warm_up_min_bars: int
    max_workers: int
    parquet_compression: str
    force_rerun: bool
    progress_bar: bool
    training_data_dir: str
    report_dir: str
    equity_curves_dir: str


def load_baseline_config(yaml_path: Path | None = None) -> BaselineConfig:
    """Carica baseline.yaml in dataclass frozen (pattern Phase 1 load_cost_model).

    Args:
        yaml_path: path al baseline.yaml. Default: `data/configs/baseline.yaml`.

    Returns:
        BaselineConfig frozen — pickle-safe per ProcessPoolExecutor.
    """
    path = yaml_path or Path("data/configs/baseline.yaml")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return BaselineConfig(
        equity_initial_eur=float(cfg["equity_initial_eur"]),
        slippage_seed=int(cfg["slippage_seed"]),
        timeout_bars={k: int(v) for k, v in cfg["timeout_bars"].items()},
        warm_up_min_bars=int(cfg["warm_up_min_bars"]),
        max_workers=int(cfg["max_workers"]),
        parquet_compression=str(cfg.get("parquet_compression", "snappy")),
        force_rerun=bool(cfg.get("force_rerun", False)),
        progress_bar=bool(cfg.get("progress_bar", True)),
        training_data_dir=str(cfg.get("training_data_dir", "data/training")),
        report_dir=str(cfg.get("report_dir", ".planning/research")),
        equity_curves_dir=str(cfg.get("equity_curves_dir",
                                       ".planning/research/baseline-equity-curves")),
    )


def _git_sha() -> str:
    """Best-effort git rev-parse HEAD per audit trail (D-17). Riusa pattern slice_worker."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).resolve().parents[2]),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:  # noqa: BLE001 — best-effort
        return "unknown"


def _csv_path_for(symbol: str, tf: str) -> Path:
    """Convention Phase 1: data/{symbol}_{tf}.csv (placeholder coerente con slice_worker default)."""
    return Path(f"data/{symbol}_{tf}.csv")


def _make_pool_executor(max_workers: int, ctx):
    """Factory ProcessPoolExecutor + spawn ctx (D-15, default produzione).

    Punto di iniezione monkeypatchabile dai test: i mock di `run_slice_3profiles`
    sono closure locali (non pickleable da spawn). I test sostituiscono questa
    factory con `ThreadPoolExecutor` per girare i mock in-process pur restando
    sull'API as_completed/submit. NON modificare la firma — i test la
    dipendono.
    """
    return ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx)


def run_baseline(
    force: bool = False,
    baseline_yaml: Path | None = None,
    costs_yaml: Path | None = None,
    strategy_yaml: Path | None = None,
    ledger_db: Path | None = None,
) -> list[dict]:
    """Orchestrator main process. Hybrid orchestration D-15.

    - Carica configs (baseline + costs validation), abilita SQLite WAL una volta (D-16)
    - ProcessPoolExecutor(N=max_workers, mp_context=spawn) su (symbol, tf) cartesian = 9 task
    - tqdm progress bar su as_completed se progress_bar=True
    - Per-worker exception → status=FAILED in result list (no pool kill)
    - Post-pool: finalize_parquet_shards + write_baseline_report

    Args:
        force: re-run anche se run_id esiste (D-14 idempotency overwrite).
        baseline_yaml: override baseline.yaml path (default data/configs/baseline.yaml).
        costs_yaml: override costs.yaml path (default data/configs/costs.yaml).
        strategy_yaml: override strategy.yaml path (default config/strategy.yaml).
        ledger_db: override SQLite ledger path (default logs/trades.db).

    Returns:
        list[dict]: 27 result dict (9 sym/tf × 3 profile).
        Schema per ogni result: run_id, symbol, timeframe, profile, status, ...
    """
    t0 = time.time()
    baseline_cfg = load_baseline_config(baseline_yaml)
    costs_path = Path(costs_yaml) if costs_yaml else Path("data/configs/costs.yaml")
    strategy_path = Path(strategy_yaml) if strategy_yaml else Path("config/strategy.yaml")
    ledger_path = Path(ledger_db) if ledger_db else Path("logs/trades.db")
    baseline_path = Path(baseline_yaml) if baseline_yaml else Path("data/configs/baseline.yaml")

    # Validate costs.yaml è parseable PRIMA di spawn worker (fail-fast).
    # Il worker passerà costs_path (Path) — slice_worker richiede Path, non dict
    # (vedi 05-06a-SUMMARY.md deviation #1).
    with open(costs_path, encoding="utf-8") as f:
        _ = yaml.safe_load(f) or {}

    # Abilita WAL una tantum dal main process (D-16) — persiste cross-connection.
    enable_sqlite_wal(ledger_path)

    tasks = list(product(PAIRS, TFS))  # 9 (symbol, tf)
    run_date = date.today().isoformat()

    # Windows default è già spawn ma renderlo esplicito documenta il vincolo
    # e protegge da fork accidentale su Linux (matplotlib Agg richiede spawn).
    ctx = mp.get_context("spawn")
    all_results: list[dict] = []

    # Executor factory injection point: i test possono monkeypatchare
    # `_make_pool_executor` per sostituire ProcessPoolExecutor con un eseguitore
    # thread-based (i mock di run_slice_3profiles non sono pickleable
    # tra processi spawn — vedi deviation Rule 1 / Rule 3 su 05-07-SUMMARY).
    pool_cm = _make_pool_executor(baseline_cfg.max_workers, ctx)
    with pool_cm as pool:
        futures = {
            pool.submit(
                run_slice_3profiles,
                symbol, tf, baseline_cfg, costs_path, strategy_path,
                force, ledger_path, run_date, _csv_path_for(symbol, tf),
            ): (symbol, tf)
            for symbol, tf in tasks
        }
        iterator = as_completed(futures)
        if baseline_cfg.progress_bar:
            iterator = tqdm(iterator, total=len(futures), desc="slice")
        for fut in iterator:
            slice_id = futures[fut]
            try:
                all_results.extend(fut.result())
            except Exception as exc:  # noqa: BLE001 — NON relanciare, permetti agli altri di completare
                _log.error("slice %s fallita: %s", slice_id, exc, exc_info=True)
                sym, tf = slice_id
                for prof in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE"):
                    all_results.append({
                        "run_id": f"baseline_{run_date}_{sym}_{tf}_{prof}",
                        "symbol": sym, "timeframe": tf, "profile": prof,
                        "status": "FAILED", "error": str(exc),
                    })

    # Post-pool: finalize parquet shards (D-01/D-02/D-03 dataset directory).
    finalize_parquet_shards(Path(baseline_cfg.training_data_dir))

    # Post-pool: scrivi report MD (D-18).
    wall_clock = time.time() - t0
    report_path = Path(baseline_cfg.report_dir) / f"baseline-{run_date}.md"

    # Decision count totale per appendix (BLOCKER 2 SC#3).
    decision_count = sum(int(r.get("n_trades", 0) or 0) for r in all_results)

    meta = {
        "cli_command": "python scripts/run_baseline_backtest.py" + (" --force" if force else ""),
        "git_sha": _git_sha(),
        "total_wall_clock_seconds": wall_clock,
        # WARNING 12 fix: full 64-char sha256 keys
        "cost_yaml_sha256": file_sha256(costs_path),
        "strategy_yaml_sha256": file_sha256(strategy_path) if strategy_path.exists() else "n/a",
        "baseline_yaml_sha256": file_sha256(baseline_path),
        "slippage_seed": baseline_cfg.slippage_seed,
        "warm_up_bars": {tf: baseline_cfg.warm_up_min_bars for tf in TFS},
        "longest_lookback": baseline_cfg.warm_up_min_bars,
        "decision_count": decision_count,
        # SC#3 thresholds (BLOCKER 2)
        "min_decisions_hard": 1000,
        "target_decisions_soft": 10000,
    }
    write_baseline_report(all_results, report_path, meta)
    _log.info("baseline run completata: %.1fs, report=%s", wall_clock, report_path)
    return all_results
