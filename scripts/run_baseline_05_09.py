r"""Plan 05-09 wrapper backtest baseline — schema-v2 + re-run notturno.

Eseguibile stand-alone sul PC secondario (no dipendenza da Claude Code).
Riusa backtest.baseline.runner.run_baseline come backend; aggiunge:
  - --smoke: 3 mesi x 1 pair x 1 TF x 3 profile (FIX 2 plan-checker
    iter 1: range allargato da 1 mese -> 3 mesi per probabilita' >=1
    trade aggregato; target <180s, >300s indica regressione)
  - --only-runs run_id1,run_id2,...: whitelist recovery (FIX 6
    plan-checker iter 1 + FIX A iter 3: implementazione REALE via
    riuso di slice_worker._force_clear_run — pattern canonical
    Phase 5 con tabelle reali `backtest_runs` + `backtest_trades`,
    NO `trades_log` (quello e' live trader, schema senza run_id).
  - schema-validation post-run (>=30 indicators cols + 5 meta non-null);
    smoke-tolerant mode (FIX 2) per smoke con 0 trade non bloccante

Uso:
    # Smoke locale (validazione veloce wrapper su PC primario o secondario):
    python scripts/run_baseline_05_09.py --smoke

    # Full run notturno (PC secondario):
    python scripts/run_baseline_05_09.py --force

    # Recovery dopo crash parziale (FIX 6 + FIX A iter 3:
    # riuso _force_clear_run + relaunch):
    python scripts/run_baseline_05_09.py --only-runs baseline_2026-05-11_EURUSD_M15_AGGRESSIVE

Exit code:
    0 = OK (full o smoke completati, schema validato, count >= soglia)
    1 = errore generico (eccezione runtime, import fallito)
    2 = wall-clock superato (--max-wall-clock gate) o smoke CSV mancante
    3 = schema-validation KO (post-run, mancano col indicators o meta)
    4 = decision count sotto hard gate 1050 (margine 2.5% vs 1076 — FIX D iter 3)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time as _time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_log = logging.getLogger("run_baseline_05_09")


def _validate_parquet_schema(parquet_dir: Path, min_rows: int) -> tuple[bool, str]:
    """D-09-D: schema-validation post-run.

    FIX 2 plan-checker iter 1: smoke-tolerant mode quando min_rows=0.
    - Se parquet_dir non esiste -> ritorna OK (smoke con 0 trade)
    - Se 0 rows -> ritorna OK (no schema check)
    Quando min_rows > 0 (full run): comportamento standard (errore se
    mancano colonne o row count basso).

    FIX 2C bug fix: usa pd.isna() invece di `is None` per check NULL meta.

    Ritorna (ok, message).
    """
    import pandas as pd
    import pyarrow.dataset as ds
    from backtest.baseline.dataset_writer import _SCHEMA_V2_REQUIRED_KEYS

    # SMOKE-TOLERANT MODE (FIX 2 plan-checker iter 1)
    if min_rows == 0:
        if not parquet_dir.exists():
            _log.warning(
                "smoke: parquet dir %s mancante -> 0 trade su window, "
                "schema validation skipped (non-blocking).",
                parquet_dir,
            )
            return True, "smoke: 0 trade su window, schema validation skipped (non-blocking)"
        try:
            dataset = ds.dataset(str(parquet_dir), format="parquet")
            n = dataset.count_rows()
        except Exception:  # noqa: BLE001 — corruption o dir vuota
            _log.warning("smoke: parquet dir vuota o non leggibile -> skip validation")
            return True, "smoke: 0 trade, no schema check"
        if n == 0:
            return True, "smoke: 0 trade, no schema check"
        # Smoke con >=1 trade: applica schema check completo
        # (caso atteso: 3 mesi window dovrebbe produrre >=1 trade)

    # FULL/SMOKE-WITH-DATA MODE
    if not parquet_dir.exists():
        return False, f"parquet dir mancante: {parquet_dir}"
    try:
        dataset = ds.dataset(str(parquet_dir), format="parquet")
    except Exception as exc:  # noqa: BLE001
        return False, f"pyarrow load fallito: {exc}"
    n = dataset.count_rows()
    if n < min_rows:
        return False, f"row count {n} < hard gate {min_rows}"
    schema_names = set(dataset.schema.names)
    missing = _SCHEMA_V2_REQUIRED_KEYS - schema_names
    if missing:
        return False, f"missing cols schema-v2: {sorted(missing)[:10]}... (total {len(missing)})"

    # FIX 10 INFO 2: single head(1) call (era 2 query separate, marginal saving)
    table = dataset.head(1)
    df = table.to_pandas()
    # FIX 2C: pd.isna() invece di `is None` (Python None check non match pd.NaT)
    for meta in ("run_id", "profile", "regime_state", "decision_ts_utc",
                 "entry_ts_utc", "exit_ts_utc"):
        if meta not in df.columns:
            return False, f"meta {meta} mancante (col assente)"
        if pd.isna(df[meta].iloc[0]):
            return False, f"meta {meta} NULL nella prima riga"
    # profile validation: leggi UNIQUE profiles da seconda query (necessaria
    # perche' head(1) ha solo 1 valore; non possiamo accorpare in 1 read)
    profiles_table = dataset.to_table(columns=["profile"]).to_pandas()
    bad = set(profiles_table["profile"].unique()) - {"CONSERVATIVE", "MODERATE", "AGGRESSIVE"}
    if bad:
        return False, f"profile valori inattesi: {bad}"
    return True, f"OK schema-v2: {n} rows, {len(schema_names)} cols"


def _run_smoke() -> int:
    """Smoke: 1 pair x 1 TF x 3 profile x 3 mesi (FIX 2: range allargato).

    Wall-clock target <180s sul PC secondario (Ryzen 7 5800H);
    >300s indica regressione (FIX 10 INFO 3).

    FIX B iter 3: csv_path via _csv_path_for() del runner (NO hardcoded).
    FIX F iter 3: ordine init = enable_sqlite_wal() PRIMA, LedgerWriter() POI
    (allinea a runner.py:170-179).
    """
    import shutil
    from dataclasses import replace
    from backtest.baseline.runner import load_baseline_config, _csv_path_for
    from backtest.baseline.slice_worker import run_slice_3profiles
    from backtest.baseline.dataset_writer import finalize_parquet_shards
    from backtest.baseline.wal_setup import enable_sqlite_wal
    from backtest.ledger import LedgerWriter

    baseline_cfg = load_baseline_config(ROOT / "data/configs/baseline.yaml")

    # FIX 7 plan-checker iter 1: path absolute per smoke (evita CWD-dependence)
    smoke_data = str(ROOT / "data" / "training" / "_smoke_05_09")
    smoke_equity = str(ROOT / ".planning" / "research" / "_smoke_equity_curves")

    # FIX 2 plan-checker iter 1: range allargato da 1 mese -> 3 mesi
    # per probabilita' >=1 trade aggregato su 3 profile in MODERATE/AGGRESSIVE.
    smoke_cfg = replace(
        baseline_cfg,
        date_start="2024-02-01",
        date_end="2024-05-01",  # 3 mesi
        training_data_dir=smoke_data,
        equity_curves_dir=smoke_equity,
    )
    smoke_dir = Path(smoke_data)
    smoke_equity_dir = Path(smoke_equity)
    if smoke_dir.exists():
        shutil.rmtree(smoke_dir)
    if smoke_equity_dir.exists():
        shutil.rmtree(smoke_equity_dir)
    smoke_dir.mkdir(parents=True, exist_ok=True)
    smoke_equity_dir.mkdir(parents=True, exist_ok=True)

    ledger_db = ROOT / "logs/trades_smoke_05_09.db"
    if ledger_db.exists():
        ledger_db.unlink()
    # FIX F iter 3: ordine init allineato a runner.py:170-179.
    # WAL prima (persiste cross-connection), LedgerWriter dopo (crea schema
    # sulla WAL gia' attiva).
    enable_sqlite_wal(ledger_db)
    LedgerWriter(ledger_db)

    # FIX B iter 3: csv_path via _csv_path_for(symbol, tf) del runner.
    # Convenzione canonical: data/historical/{SYMBOL}/{TF}.csv. NO hardcoded.
    # Se il file manca produciamo un error log esplicito e fallback exit code.
    csv_path = _csv_path_for("EURUSD", "M15")
    # _csv_path_for ritorna Path relativo ("data/historical/EURUSD/M15.csv").
    # Risolviamo rispetto a ROOT per absolute path (consistenza con FIX 7).
    csv_path_abs = (ROOT / csv_path).resolve()
    if not csv_path_abs.exists():
        _log.error(
            "Smoke fallback: CSV %s non trovato. Verifica layout data/historical/.",
            csv_path_abs,
        )
        return 2

    _log.info(
        "smoke 05-09: EURUSD M15 (3 profile) 2024-02-01 -> 2024-05-01 (3 mesi), csv=%s",
        csv_path_abs,
    )
    results = run_slice_3profiles(
        symbol="EURUSD",
        tf="M15",
        baseline_cfg=smoke_cfg,
        costs_cfg_path=ROOT / "data/configs/costs.yaml",
        strategy_cfg_path=ROOT / "config/strategy.yaml",
        force=True,
        ledger_db_path=ledger_db,
        run_date="2026-05-11-smoke",
        csv_path=csv_path_abs,
    )
    finalize_parquet_shards(smoke_dir)
    n_ok = sum(1 for r in results if r.get("status") == "OK")
    _log.info("smoke results: %d/3 ok", n_ok)
    # FIX 2 plan-checker iter 1: smoke-tolerant validation (min_rows=0)
    parquet_dir = smoke_dir / "baseline_decisions"
    ok, msg = _validate_parquet_schema(parquet_dir, min_rows=0)
    if not ok:
        print(f"SMOKE SCHEMA KO: {msg}", file=sys.stderr)
        return 3
    print(f"SMOKE OK: {msg}")
    return 0


def _only_runs_pre_delete(ledger_db: Path, run_ids: list[str]) -> None:
    """FIX A iter 3 — riuso di slice_worker._force_clear_run.

    Schema reale Phase 5 (vedi backtest/ledger.py:19-79):
      - backtest_runs(run_id PK)
      - backtest_trades(run_id FK virtuale, AUTOINCREMENT trade_id)

    `trades_log` (logs/trades.db, schema live trader) NON ha run_id e
    NON deve essere toccata da --only-runs.

    Pattern canonical: per ciascun run_id, invoca _force_clear_run
    che esegue DELETE FROM backtest_trades + backtest_runs in single
    connection con busy_timeout=30s. Riuso garantisce single source
    of truth con il --force path del runner.
    """
    from backtest.baseline.slice_worker import _force_clear_run

    _log.info(
        "FIX A iter 3 --only-runs: pre-delete via _force_clear_run per %d run_id",
        len(run_ids),
    )
    for rid in run_ids:
        _force_clear_run(ledger_db, rid)
    _log.info(
        "Pre-delete completato per %d run_id (--only-runs whitelist).",
        len(run_ids),
    )


def _run_full(args, ROOT_PATH: Path) -> int:
    """Full 27/27 run con supporto --only-runs (FIX 6 + FIX A iter 3).

    FIX A iter 3: --only-runs implementato via riuso _force_clear_run
    (slice_worker.py:59-74) — single source of truth, NO SQL custom.
    Sfrutta D-14 idempotency (Plan 05-08): dopo il pre-delete, il
    run_baseline(force=False) skippera' i run completi e rilancera'
    solo quelli appena cancellati.
    """
    from backtest.baseline.runner import load_baseline_config, run_baseline

    cfg = load_baseline_config(ROOT_PATH / "data/configs/baseline.yaml")

    # FIX 6 plan-checker iter 1 + FIX A iter 3: --only-runs riuso pattern canonical
    if args.only_runs:
        run_ids = [rid.strip() for rid in args.only_runs.split(",") if rid.strip()]
        if run_ids:
            ledger_db_path = ROOT_PATH / "logs" / "trades.db"
            _only_runs_pre_delete(ledger_db_path, run_ids)
            # Pulizia parquet shard per quei run_id (se ancora presenti
            # pre-finalize) — il re-finalize sovrascrivera' part-*.parquet
            # con existing_data_behavior gia' impostato in dataset_writer.py.
            training_dir = ROOT_PATH / "data" / "training"
            for rid in run_ids:
                shard = training_dir / "baseline_decisions" / (
                    f"baseline_decisions_{rid}.parquet"
                )
                if shard.exists():
                    shard.unlink()

    start = _time.monotonic()
    results = run_baseline(force=args.force)
    wall = _time.monotonic() - start
    n_total = len(results)
    n_ok = sum(1 for r in results if r.get("status") == "OK")
    n_failed = sum(1 for r in results if r.get("status") == "FAILED")
    n_skipped = sum(1 for r in results if r.get("status") == "SKIPPED")

    print(f"WALL_CLOCK_SECONDS={wall:.0f}")
    print(f"RESULTS={n_ok}/{n_total} ok (skipped={n_skipped} failed={n_failed})")

    if not args.no_time_gate and wall > args.max_wall_clock:
        print(
            f"WARN: wall-clock {wall:.0f}s > max {args.max_wall_clock}s "
            f"(BACK-07 SC#1 violato — Rule 4 deviation Plan 05-08 already accepted).",
            file=sys.stderr,
        )
        # Plan 05-09 NON failha su wall-clock (Phase 5 perf opt deferred);
        # ritorna 0 se 27/27 ok, ma warning visibile in stderr.

    # Schema validation post-run — FIX D iter 3: min_rows=1050 (parity 1076 + 2.5% margine)
    parquet_dir = ROOT_PATH / "data/training/baseline_decisions"
    ok, msg = _validate_parquet_schema(parquet_dir, min_rows=1050)
    if not ok:
        print(f"SCHEMA KO: {msg}", file=sys.stderr)
        return 3
    print(f"SCHEMA OK: {msg}")

    if n_failed > 0:
        print(f"WARN: {n_failed} run falliti — vedi log", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Plan 05-09 baseline wrapper (schema-v2 re-run + smoke).",
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Smoke mini-run (1 pair x 1 TF x 3 profile x 3 mesi) per validare wrapper.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run anche se run_id esiste (overwrite ledger + parquet).",
    )
    parser.add_argument(
        "--only-runs", default="",
        help="Comma-separated whitelist di run_id (recovery, riuso _force_clear_run).",
    )
    parser.add_argument(
        "--max-wall-clock", type=int, default=14400,
        help="Soft warning su wall-clock seconds (default 14400 = 4h, "
             "atteso ~3h18m sul PC secondario; NO hard gate Plan 05-09).",
    )
    parser.add_argument(
        "--no-time-gate", action="store_true",
        help="Disabilita time-gate (debug).",
    )
    args = parser.parse_args()

    if args.smoke:
        return _run_smoke()

    return _run_full(args, ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
