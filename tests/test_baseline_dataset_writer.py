"""Tests for backtest.baseline.dataset_writer (D-01, D-02, D-03)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

from backtest.baseline.dataset_writer import (
    finalize_parquet_shards,
    write_decisions_shard,
    write_drafts_shard,
)

_DECISIONS_KEYS = {
    "run_id", "symbol", "timeframe", "profile", "decision_ts_utc",
    "setup_name", "grade", "confidence", "entry_price", "stop_loss_price",
    "take_profit_price", "rr", "atr", "ema20", "ema50", "regime",
    "outcome", "exit_reason", "pnl_pips", "bars_held",
}
_DRAFTS_KEYS = {
    "run_id", "symbol", "bar_ts_utc", "detector_name", "setup_type",
    "grade", "factor_trend", "factor_setup", "factor_momentum",
    "factor_vol", "factor_session", "confidence", "regime",
    "was_winner", "entered_ledger",
}


def test_decisions_shard_round_trip(tmp_path: Path) -> None:
    """D-01: round-trip write_decisions_shard -> pd.read_parquet conserva schema."""
    rows = [{"run_id": "r1", "symbol": "EURUSD", "outcome": "WIN", "pnl_pips": 12.3}]
    path = write_decisions_shard(rows, "r1", tmp_path)
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert df.iloc[0]["outcome"] == "WIN"
    assert df.iloc[0]["pnl_pips"] == 12.3


def _full_decision_row() -> dict:
    """Riga D-02 con tutti i campi obbligatori della whitelist."""
    numeric_keys = {
        "confidence", "entry_price", "stop_loss_price",
        "take_profit_price", "rr", "atr", "ema20", "ema50",
        "pnl_pips",
    }
    row: dict = {}
    for k in _DECISIONS_KEYS:
        if k in numeric_keys:
            row[k] = 0.0
        elif k == "bars_held":
            row[k] = 0
        else:
            row[k] = "x"
    return row


def test_decisions_schema(tmp_path: Path) -> None:
    """D-02: column set per-trade -- identita + ProposalDraft + ExtendedIndicators + ctx + outcome."""
    path = write_decisions_shard([_full_decision_row()], "r1", tmp_path)
    df = pd.read_parquet(path)
    assert _DECISIONS_KEYS.issubset(set(df.columns))


def _full_draft_row() -> dict:
    """Riga D-03 con factor_* bool + numeric confidence + string fields."""
    bool_keys = {"factor_trend", "factor_setup", "factor_momentum",
                 "factor_vol", "factor_session", "was_winner", "entered_ledger"}
    row: dict = {}
    for k in _DRAFTS_KEYS:
        if k in bool_keys:
            row[k] = True
        elif k == "confidence":
            row[k] = 0.0
        else:
            row[k] = "x"
    return row


def test_drafts_schema(tmp_path: Path) -> None:
    """D-03: column set per-bar per-detector -- A/B/C/D x {READY,FORMING,NONE}."""
    path = write_drafts_shard([_full_draft_row()], "r1", tmp_path)
    df = pd.read_parquet(path)
    assert _DRAFTS_KEYS.issubset(set(df.columns))


def test_finalize_concatenates_shards(tmp_path: Path) -> None:
    """D-01: pyarrow.dataset.write_dataset finalize concatena shards/, no full-load memory."""
    for rid in ("r1", "r2", "r3"):
        write_decisions_shard(
            [
                {"run_id": rid, "symbol": "EURUSD", "outcome": "WIN", "pnl_pips": 1.0},
                {"run_id": rid, "symbol": "EURUSD", "outcome": "LOSS", "pnl_pips": -1.0},
            ],
            rid, tmp_path,
        )
    finalize_parquet_shards(tmp_path)
    target = tmp_path / "baseline_decisions"
    assert target.is_dir()
    # tutti gli shard sorgente cancellati
    assert list(tmp_path.glob("baseline_decisions_*.parquet")) == []
    # 6 row totali (3 shard x 2 row)
    df = ds.dataset(target, format="parquet").to_table().to_pandas()
    assert len(df) == 6


def test_empty_rows_no_crash(tmp_path: Path) -> None:
    """Edge: shard con 0 righe non crasha (slice senza trade chiusi)."""
    path = write_decisions_shard([], "rid_empty", tmp_path)
    # File NON creato (warning emesso) -- ma return value path comunque valido
    assert path.parent == tmp_path
    assert not path.exists()


def test_finalize_handles_empty_shards(tmp_path: Path) -> None:
    """WARNING 11 fix: 1 shard empty + 1 shard 1-row, finalize round-trip preserva schema."""
    # Shard 1: empty (no file creato)
    write_decisions_shard([], "rid_empty", tmp_path)
    # Shard 2: 1 row
    write_decisions_shard(
        [{"run_id": "rid_one", "symbol": "EURUSD", "outcome": "WIN", "pnl_pips": 1.5}],
        "rid_one", tmp_path,
    )
    finalize_parquet_shards(tmp_path)
    target = tmp_path / "baseline_decisions"
    assert target.is_dir()
    df = ds.dataset(target, format="parquet").to_table().to_pandas()
    assert len(df) == 1  # solo lo shard non-empty contribuisce
