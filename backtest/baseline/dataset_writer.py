"""Parquet shard writer per baseline run (D-01, D-02, D-03).

Per-worker shard prevent contention (no shared file lock cross-process).
Main process finalize via pyarrow.dataset streaming -- NO full-load memory blow per
i 65M righe baseline_drafts (M15 23.5y x 4 detector x 27 run).

Layout output: directory `<out_dir>/<dataset_name>/part-{i}.parquet` (pyarrow standard).
Phase 7 ML reader: `pyarrow.dataset.dataset(out_dir / 'baseline_decisions')` -- stesso API
indipendente dal numero di file part.

Source: arrow.apache.org/docs/python/parquet.html, RESEARCH.md Pattern 2.

Plan 05-09 — schema-v2 (D-09-A + FIX 3 plan-checker iter 1):
- Estende lo schema parquet da 17 colonne flat (v1, Plan 05-08) a ~55+ colonne
  (v2): 17 base + 33 indicators extended (compute_all_extended) + 5 meta
  (profile, run_id, decision_ts_utc, entry_ts_utc, exit_ts_utc).
- La whitelist `_SCHEMA_V2_REQUIRED_KEYS` viene costruita PROGRAMMATICAMENTE
  a import-time via `_build_required_keys_v2()` invocando
  `compute_all_extended(dummy_bars, regime_cfg=None)`. Previene drift: se Phase 2
  estende l'interface di `compute_all_extended` in futuro, la whitelist si
  aggiorna automaticamente.
- Backward-compat (D-09-C): la signature di `write_decisions_shard` resta
  invariata. Chiamanti legacy 05-08 (17 keys flat) continuano a funzionare;
  emettiamo solo un warning per-shard se NESSUNA key v2 e' presente.
- I 5 meta sono colonne TOP-LEVEL (NON nested in `decision_context_json`):
  `profile`, `run_id`, `decision_ts_utc` (bar idx-1 open, anchor conservativa
  D-09-B vs D-22), `entry_ts_utc` (bar idx open), `exit_ts_utc` (variable).
- `regime_state` e' canonical (NON alias `regime` — FIX 9 plan-checker iter 1)
  e fa gia' parte dell'output di `compute_all_extended` (non viene aggiunta
  manualmente nella whitelist).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

_log = logging.getLogger(__name__)


def _build_required_keys_v2() -> frozenset[str]:
    """Costruisce whitelist v2 dinamicamente da compute_all_extended() interface.

    Eseguito UNA VOLTA a import-time del modulo per evitare drift se
    Phase 2 estende compute_all_extended in futuro (FIX 3 plan-checker
    iter 1 Plan 05-09). regime_cfg=None ammesso (vedi
    indicators/aggregate.py:93 ternary).

    Aggiunge i 5 meta/timestamps Plan 05-09 (profile, run_id,
    decision_ts_utc, entry_ts_utc, exit_ts_utc). `regime_state`
    e' gia' presente in compute_all_extended output, qui idempotent.
    """
    # Import lazy per evitare circular-import + permettere a tests/CI
    # di non spawnare l'intero stack indicators a livello modulo.
    from indicators import compute_all_extended

    dummy_bars = [
        {
            "time": 1700000000 + i * 60,
            "open": 1.10,
            "high": 1.11,
            "low": 1.09,
            "close": 1.10,
            "volume": 100,
        }
        for i in range(200)
    ]
    snapshot_keys = set(compute_all_extended(dummy_bars, regime_cfg=None).keys())
    meta_keys = {
        "profile",          # CONSERVATIVE|MODERATE|AGGRESSIVE
        "run_id",           # baseline_{date}_{symbol}_{tf}_{profile}
        "decision_ts_utc",  # bar idx-1 open (anchor conservativa vs D-22 — D-09-B)
        "entry_ts_utc",     # bar idx open
        "exit_ts_utc",      # variable per exit_reason
    }
    # regime_state e' gia' in snapshot_keys (compute_all_extended la include
    # come None se regime_cfg=None). NON aggiungiamo "regime" alias (FIX 9).
    return frozenset(snapshot_keys | meta_keys)


# Whitelist schema-v2 costruita programmaticamente a import-time (FIX 3).
_SCHEMA_V2_REQUIRED_KEYS: frozenset[str] = _build_required_keys_v2()


def write_decisions_shard(rows: list[dict], run_id: str, shard_dir: Path) -> Path:
    """Worker scrive proprio file parquet -- no contention con altri worker.

    D-01/D-02: 1 riga per trade chiuso (READY entrato nel ledger).
    Empty list -> nessun file scritto (warning log) per consistency con finalize
    che filtra file zero-byte.

    Plan 05-09 — schema-v2 (D-09-A): le righe possono includere ~50+ keys
    (17 base + 33 extended + 5 meta). pandas.DataFrame materializza le colonne
    automaticamente. Se la prima riga manca COMPLETAMENTE delle keys v2
    (chiamante legacy Plan 05-08), emettiamo un warning per-shard ma
    proseguiamo (D-09-C backward-compat).
    """
    shard_dir.mkdir(parents=True, exist_ok=True)
    path = shard_dir / f"baseline_decisions_{run_id}.parquet"
    if not rows:
        _log.warning("write_decisions_shard %s: 0 row, skip file", run_id)
        return path

    # Plan 05-09 D-09-C: backward-compat warning se nessuna key schema-v2
    # presente nella prima riga (indicatore di chiamante legacy 05-08).
    first_keys = set(rows[0].keys())
    if first_keys.isdisjoint(_SCHEMA_V2_REQUIRED_KEYS):
        _log.warning(
            "schema-v2 fields missing: nessuna key v2 nella prima riga del run %s "
            "(chiamante legacy 05-08?). Le colonne extended saranno NaN.",
            run_id,
        )

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
