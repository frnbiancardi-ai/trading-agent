"""Tests for backtest.baseline.dataset_writer (D-01, D-02, D-03 + Plan 05-09 D-09-A schema-v2)."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

from backtest.baseline.dataset_writer import (
    _SCHEMA_V2_REQUIRED_KEYS,
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


# ─── Plan 05-09 — schema-v2 (D-09-A + FIX 3 plan-checker iter 1) ────────────


def _full_decision_row_v2() -> dict:
    """Riga schema-v2 completa: 17 base + 33 extended + 5 meta.

    Materializza valori plausibili per ciascuna chiave della whitelist
    `_SCHEMA_V2_REQUIRED_KEYS` (costruita programmaticamente da
    compute_all_extended). Le 17 keys legacy vengono fornite a parte per
    backward-compat con Plan 05-08 reader.
    """
    # 17 keys base v1 (legacy, Plan 05-08)
    legacy_keys = {
        "run_id", "symbol", "timeframe", "setup_name", "grade", "confidence",
        "entry_price", "stop_loss_price", "take_profit_price", "rr", "atr",
        "ema20", "ema50", "outcome", "exit_reason", "pnl_pips", "bars_held",
    }
    numeric_legacy = {
        "confidence", "entry_price", "stop_loss_price", "take_profit_price",
        "rr", "atr", "ema20", "ema50", "pnl_pips",
    }
    row: dict = {}
    for k in legacy_keys:
        if k in numeric_legacy:
            row[k] = 0.0
        elif k == "bars_held":
            row[k] = 0
        else:
            row[k] = "x"
    # Schema-v2: tutte le keys da `_SCHEMA_V2_REQUIRED_KEYS`. Indicators -> float;
    # meta string. fib_direction puo' essere int o str (qui int).
    for k in _SCHEMA_V2_REQUIRED_KEYS:
        if k in row:
            continue
        if k in {"profile", "run_id", "decision_ts_utc", "entry_ts_utc",
                 "exit_ts_utc", "regime_state"}:
            row[k] = "x"
        elif k == "fib_direction":
            row[k] = 0
        else:
            # Indicators numerici (anche None ammessi su input edge ma qui forniamo 0.0)
            row[k] = 0.0
    return row


def test_decisions_schema_v2_round_trip(tmp_path: Path) -> None:
    """Plan 05-09 D-09-A: schema-v2 round-trip — 50+ colonne flat top-level."""
    rows = [_full_decision_row_v2()]
    path = write_decisions_shard(rows, "rid_v2", tmp_path)
    df = pd.read_parquet(path)
    assert _SCHEMA_V2_REQUIRED_KEYS.issubset(set(df.columns)), (
        f"colonne schema-v2 mancanti: {_SCHEMA_V2_REQUIRED_KEYS - set(df.columns)}"
    )
    # Sanity: la riga conserva i 5 meta
    assert df.iloc[0]["profile"] == "x"
    assert df.iloc[0]["run_id"] == "x"
    assert df.iloc[0]["decision_ts_utc"] == "x"


def test_schema_v2_required_keys_documented() -> None:
    """Plan 05-09 D-09-A: meta + sampling indicators presenti nella whitelist."""
    # 5 meta Plan 05-09
    for meta in ("profile", "run_id", "decision_ts_utc", "entry_ts_utc", "exit_ts_utc"):
        assert meta in _SCHEMA_V2_REQUIRED_KEYS, f"meta {meta} mancante dalla whitelist"
    # 6 indicators chiave sampled (estratti programmaticamente da compute_all_extended)
    for ind in ("atr_14", "ema_50", "rsi_14", "bb_upper", "adx_14", "macd"):
        assert ind in _SCHEMA_V2_REQUIRED_KEYS, f"indicator {ind} mancante dalla whitelist"


def test_schema_v2_keys_match_compute_all_extended() -> None:
    """Plan 05-09 FIX 3 plan-checker iter 1: anti-drift contract test.

    Invoca compute_all_extended con 200 bar sintetici + regime_cfg per-symbol
    da `data/configs/regime.yaml`. Asserisce che le keys dell'output coincidono
    ESATTAMENTE con `_SCHEMA_V2_REQUIRED_KEYS` meno i 5 meta aggiunti dal writer.
    """
    from indicators import compute_all_extended
    from indicators.volatility import load_regime_config

    regime_cfg = load_regime_config("EURUSD", "data/configs/regime.yaml")
    dummy_bars = [
        {
            "time": 1700000000 + i * 900,
            "open": 1.10 + i * 0.0001,
            "high": 1.10 + i * 0.0001 + 0.0005,
            "low": 1.10 + i * 0.0001 - 0.0005,
            "close": 1.10 + i * 0.0001 + 0.0002,
            "volume": 100,
        }
        for i in range(200)
    ]
    snapshot_keys = set(compute_all_extended(dummy_bars, regime_cfg=regime_cfg).keys())
    meta_writer = {"profile", "run_id", "decision_ts_utc",
                   "entry_ts_utc", "exit_ts_utc"}

    # Anti-drift: l'unione delle keys snapshot + meta_writer == whitelist v2
    expected = snapshot_keys | meta_writer
    assert expected == set(_SCHEMA_V2_REQUIRED_KEYS), (
        f"drift detected:\n  extra in whitelist: {set(_SCHEMA_V2_REQUIRED_KEYS) - expected}\n"
        f"  missing from whitelist: {expected - set(_SCHEMA_V2_REQUIRED_KEYS)}"
    )

    # Inoltre: subset relationship esplicito
    assert snapshot_keys.issubset(_SCHEMA_V2_REQUIRED_KEYS)
    # E la differenza e' esattamente i 5 meta del writer
    diff = set(_SCHEMA_V2_REQUIRED_KEYS) - snapshot_keys
    assert diff == meta_writer, (
        f"i 5 meta del writer attesi ({meta_writer}), trovata diff: {diff}"
    )


def test_legacy_v1_shard_emits_warning(tmp_path: Path, caplog) -> None:
    """Plan 05-09 D-09-C backward-compat: legacy 05-08 shard emette warning, no crash."""
    # Riga con SOLO le 17 keys legacy (NESSUNA key schema-v2 presente).
    legacy_row = {
        "symbol": "EURUSD",
        "timeframe": "M15",
        "setup_name": "A_breakout",
        "grade": "A+",
        "confidence": 0.85,
        "entry_price": 1.10,
        "stop_loss_price": 1.099,
        "take_profit_price": 1.105,
        "rr": 5.0,
        "atr": 0.001,
        "ema20": 1.10,
        "ema50": 1.10,
        "outcome": "WIN",
        "exit_reason": "TP_HIT",
        "pnl_pips": 50.0,
        "bars_held": 10,
    }
    # NB: rimuoviamo "run_id" (presente in v2 whitelist) per garantire disjoint.
    assert set(legacy_row.keys()).isdisjoint(_SCHEMA_V2_REQUIRED_KEYS), (
        "il dict di test deve essere disjoint dalla whitelist v2 per validare il warning"
    )

    with caplog.at_level(logging.WARNING, logger="backtest.baseline.dataset_writer"):
        path = write_decisions_shard([legacy_row], "rid_legacy", tmp_path)

    # Il file e' scritto comunque (no crash, D-09-C)
    assert path.exists()
    df = pd.read_parquet(path)
    assert len(df) == 1
    # Warning con prefisso "schema-v2 fields missing" presente
    assert any("schema-v2 fields missing" in r.getMessage() for r in caplog.records), (
        f"atteso warning 'schema-v2 fields missing', records: "
        f"{[r.getMessage() for r in caplog.records]}"
    )


def test_regime_none_no_crash(tmp_path: Path) -> None:
    """Plan 05-09 edge: regime_state=None + regime_atr_pct=None scritto senza crash."""
    row = _full_decision_row_v2()
    row["regime_state"] = None
    row["regime_atr_pct"] = None
    path = write_decisions_shard([row], "rid_regime_none", tmp_path)
    df = pd.read_parquet(path)
    assert len(df) == 1
    # pandas: None in colonna object -> NaN; usiamo pd.isna come check robusto.
    assert pd.isna(df.iloc[0]["regime_state"])
    assert pd.isna(df.iloc[0]["regime_atr_pct"])
