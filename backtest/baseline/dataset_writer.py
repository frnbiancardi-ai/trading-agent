"""Parquet shard writer per baseline run (D-01, D-02, D-03).

Per-worker shard prevent contention (no shared file lock cross-process).
Main process finalize via pyarrow.dataset streaming -- NO full-load memory blow per
i 65M righe baseline_drafts (M15 23.5y x 4 detector x 27 run).

Layout output: directory `<out_dir>/<dataset_name>/part-{i}.parquet` (pyarrow standard).
Phase 7 ML reader: `pyarrow.dataset.dataset(out_dir / 'baseline_decisions')` -- stesso API
indipendente dal numero di file part.

Source: arrow.apache.org/docs/python/parquet.html, RESEARCH.md Pattern 2.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

_log = logging.getLogger(__name__)


def write_decisions_shard(rows: list[dict], run_id: str, shard_dir: Path) -> Path:
    """Worker scrive proprio file parquet -- no contention con altri worker.

    D-01/D-02: 1 riga per trade chiuso (READY entrato nel ledger).
    Empty list -> nessun file scritto (warning log) per consistency con finalize
    che filtra file zero-byte.
    """
    shard_dir.mkdir(parents=True, exist_ok=True)
    path = shard_dir / f"baseline_decisions_{run_id}.parquet"
    if not rows:
        _log.warning("write_decisions_shard %s: 0 row, skip file", run_id)
        return path
    df = pd.DataFrame(rows)
    df.to_parquet(path, compression="snappy", index=False, engine="pyarrow")
    return path


def write_drafts_shard(rows: list[dict], run_id: str, shard_dir: Path) -> Path:
    """D-03: 1 riga per Draft ogni detector A/B/C/D ogni bar.

    ~2.4M righe per slice (M15 23.5y x 4 detector). Accettabile in worker memory
    (df pandas ~500 MB peak; piu' piccolo del buffer indicator cache).
    """
    shard_dir.mkdir(parents=True, exist_ok=True)
    path = shard_dir / f"baseline_drafts_{run_id}.parquet"
    if not rows:
        _log.warning("write_drafts_shard %s: 0 row, skip file", run_id)
        return path
    df = pd.DataFrame(rows)
    df.to_parquet(path, compression="snappy", index=False, engine="pyarrow")
    return path


def finalize_parquet_shards(out_dir: Path) -> None:
    """Main process post-pool: concatena shard via pyarrow.dataset streaming.

    Output: directory `out_dir / <prefix>/part-{i}.parquet` (NON single file --
    pyarrow.dataset.write_dataset shapes per definizione). Phase 7 reader
    usa `ds.dataset(out_dir / prefix)` -- pattern parquet idiomatico.

    Filtro `stat().st_size > 0` mitiga T-05-09: shard zero-byte (worker
    crash mid-write) ignorati per evitare ArrowInvalid su parquet corrotto.
    """
    for prefix in ("baseline_decisions", "baseline_drafts"):
        shards = sorted(out_dir.glob(f"{prefix}_*.parquet"))
        shards = [s for s in shards if s.stat().st_size > 0]  # filtro file vuoti / corrotti
        if not shards:
            _log.info("finalize: nessuno shard per %s, skip", prefix)
            continue
        dataset = ds.dataset([str(s) for s in shards], format="parquet")
        target_dir = out_dir / prefix
        ds.write_dataset(
            dataset,
            base_dir=str(target_dir),
            format="parquet",
            existing_data_behavior="overwrite_or_ignore",
            basename_template="part-{i}.parquet",
        )
        for s in out_dir.glob(f"{prefix}_*.parquet"):
            s.unlink()
        _log.info("finalize %s: %d shard concatenati in %s", prefix, len(shards), target_dir)
