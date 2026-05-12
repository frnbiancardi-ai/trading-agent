# Phase 9: Failure Analysis + Drift — Research

**Researched:** 2026-05-12
**Domain:** Density-based failure clustering (HDBSCAN), 3-tier drift detection (KS + ECE + feature drift), retrain orchestration (APScheduler + JobQueue cap=1 reuse), hybrid rule + ML position-action suggestion.
**Confidence:** HIGH on library choices and Phase 6/7/8 reuse pattern; MEDIUM on HDBSCAN params for 778-sample × 66-dim space (needs Wave 1 cluster-quality gate); HIGH on validation architecture from carry-forward.
**Project memory hard rule applied:** "Training data integrity = priority assoluta" → every recommendation below is sized against silently-corrupt-model failure class; UX cost accepted when audit reproducibility is at stake.

---

## Executive Summary

1. **HDBSCAN dependency choice is load-bearing.** Use the standalone `hdbscan` package (scikit-learn-contrib), NOT `sklearn.cluster.HDBSCAN`. Sklearn's class does not expose `approximate_predict` / `prediction_data` — required by D-09-A4 Wave 2 cluster-match add-on. Confirmed against sklearn 1.8 official docs. [VERIFIED: scikit-learn.org/stable HDBSCAN page lists only `fit`, `fit_predict`, `dbscan_clustering` — no `approximate_predict`.]
2. **No new drift library needed.** `scipy.stats.ks_2samp` + `sklearn.calibration.calibration_curve` (already Phase 7 dep) + 1 numpy loop for feature drift top-K = lean ~50 LOC core. Alibi-detect/evidently/nannyml add 50-200 MB transitive deps and audit-opacity for zero gain on our 3-tier ML-08 spec. [VERIFIED: scipy ks_2samp returns deterministic `(stat, pvalue)`; sklearn calibration_curve is one-liner for ECE.]
3. **APScheduler coexistence pattern.** `scheduler.py` already uses `BlockingScheduler` for `ordinary_cycle` (line 293) and `IntradayLoopScheduler` for H24. Phase 9 monthly retrain must use a SEPARATE `BackgroundScheduler` instance (in `retrain/scheduler.py`) running inside the same MCP server process — BlockingScheduler can have only one process owner. `max_instances=1` + `replace_existing=True` + `misfire_grace_time` prevent duplicate fires across cron miss. [VERIFIED: APScheduler 3.11 user guide.]
4. **Atomic rename on Windows requires `os.replace`, NOT `os.rename`.** Plain `os.rename` on Windows fails if target exists. `os.replace(candidate, final)` uses `MoveFileEx(MOVEFILE_REPLACE_EXISTING)` and is atomic at filesystem level. Same trap exists for the sidecar `.metadata.json` — must replace as pair. [VERIFIED: Python 3.12 os module docs.]
5. **HDBSCAN persistence trap for `approximate_predict`.** Must set `prediction_data=True` at fit time OR call `clusterer.generate_prediction_data()` BEFORE `joblib.dump`. Otherwise post-restart `approximate_predict` raises `AttributeError: No prediction data was generated`. [VERIFIED: hdbscan readthedocs prediction tutorial.] Phase 9 Wave 1 cluster artifact MUST persist with `prediction_data=True`.
6. **MLFilter singleton hot-reload after retrain.** Phase 7 D-07-05-E lock is `_MODEL_CACHE = None` + `threading.Lock()` double-check (`ml/inference.py:get_ml_filter`). Hot-reload pattern: `_MODEL_CACHE = None` (clear) before next predict OR explicit `get_ml_filter.cache_clear()` style invalidator. `ProcessPoolExecutor` workers (Phase 6 D-A1) fork-isolated → each worker reloads at next predict by construction. [VERIFIED via Phase 7 Plan 07-05 PLAN line 100-101 contract.]
7. **OOD inference for MCP-18 mid-trade ML re-eval is unavoidable.** Phase 7 D-17 trained on `features_at_decision_time` (bar-close discipline). `prob_now` is not strictly P(TP_HIT | features_now) — surface `ood_caveat: true` in rationale and DO NOT rank confidence on absolute prob_now value. Compare relatively: `prob_now / prob_at_entry` ratio + `prob_now vs threshold_profile` are safe. Absolute prob interpretation is NOT safe.
8. **Retrain workflow zero-duplication path confirmed.** Phase 8 Plan 08-04 `_train_ml_filter_worker(args, cfg_dict)` already top-level picklable + sha256 strict-fail + cap=1 JobQueue. Phase 9 retrain trigger handler is a thin `~80 LOC` wrapper enqueueing the SAME worker. Single code path → single audit surface → single failure mode.
9. **Validation gate ECE comparison requires per-fold reload.** Phase 7 metadata.json `fold_metrics` is the only ECE-reference anchor (D-15). Candidate ECE comes from candidate metadata.json (Phase 8 worker writes the same schema). Direct comparison via `meta_candidate.aggregate.ece - meta_reference.aggregate.ece <= MAX_ECE_REGRESSION_PCT * meta_reference.aggregate.ece`. No re-evaluation needed (cost preserved).
10. **Drift_log.db / validation_log.db follow trades.db convention.** WAL mode, `CREATE TABLE IF NOT EXISTS`, `INSERT OR REPLACE` idempotency where applicable. No new persistence library — `sqlite3` stdlib, same pattern as `mcp_tools/job_queue.py:60-72`, `logger.py:14-28`, `mcp_tools/trail_daemon.py:34-46`. ~150 LOC each writer.

**Primary recommendation:** Implement Areas in this order: Wave 0 scaffolding (4 packages + .env + schemas) → Wave 1 failure clustering (HDBSCAN with `prediction_data=True` upfront + cluster quality gate) → Wave 2 drift compute + drift_log.db (scipy KS + sklearn calibration + sqlite3) → Wave 3 retrain trigger (riusa Phase 8 worker + APScheduler BackgroundScheduler + validation_log.db + `os.replace` atomic) → Wave 4 suggest_position_action (rule library + ML re-eval con OOD caveat) → Wave 5 INT-03 CLI dashboard → Wave 6 integration smoke + phase gate. Order is dependency-driven: cluster artifact + drift reference are inputs to retrain validation gate.

---

## Library + Dependency Recommendations

### 1. `hdbscan` (scikit-learn-contrib) — failure clustering algorithm

| Property | Value |
|----------|-------|
| Package | `hdbscan` |
| Pinned version | `>=0.8.40,<0.9.0` (latest stable 0.8.42 released 2026-03-27; 0.8.41 2025-12-12) [VERIFIED: pypi.org/project/hdbscan] |
| Import | `from hdbscan import HDBSCAN, approximate_predict` |
| Why this and NOT sklearn's HDBSCAN | sklearn.cluster.HDBSCAN (added in sklearn 1.3, current in 1.8) does NOT expose `approximate_predict` / `prediction_data` / `generate_prediction_data()`. Required by D-09-A4 Wave 2 cluster-match add-on AND by closed-loop "match new failing trade to known loss-mode" pattern in MCP-18 future extension. Switching to sklearn at this point would lock out that Wave 2 entirely. [VERIFIED: WebFetch sklearn.org/stable HDBSCAN page lists only fit/fit_predict/dbscan_clustering.] |
| Pitfall #1 | `prediction_data=True` must be set at fit time OR `generate_prediction_data()` called BEFORE `joblib.dump`. Otherwise post-restart approximate_predict raises `AttributeError: No prediction data was generated`. [CITED: hdbscan readthedocs `prediction_tutorial.html`.] |
| Pitfall #2 | `cluster_selection_method='eom'` (excess of mass — default) vs `'leaf'` (more clusters, finer-grained). For 778-sample × 66-dim sparse-density forex feature space, `'eom'` is the safe default (fewer but more cohesive clusters). Plan-phase decision point: validate via DB-index + silhouette in Wave 1; flip to `'leaf'` only if DB > 2.0. |
| Install | `pip install "hdbscan>=0.8.40,<0.9.0"` |

**Sklearn-contrib hdbscan vs sklearn.cluster.HDBSCAN differences (active 2025-2026):**
- `min_samples` semantics differ by 1 (sklearn includes the point itself, contrib doesn't). [VERIFIED: scikit-learn issue #27829.] Locks Phase 9 to contrib package — switching at later phase requires retuning min_samples.
- `cluster_selection_epsilon` produces different cluster labels between the two implementations. [VERIFIED: same issue.]

### 2. `scipy` — KS-test for prediction-distribution + per-feature drift

| Property | Value |
|----------|-------|
| Package | `scipy` (already transitive dep via Phase 7 sklearn) |
| Pinned version | `>=1.13,<2.0` (sklearn 1.8 requires scipy >=1.8.0) |
| Import | `from scipy.stats import ks_2samp` |
| API | `ks_2samp(sample_ref, sample_curr, method='auto') → (statistic: float, pvalue: float)` [CITED: scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html] |
| Pitfall | `method='auto'` switches to asymptotic on N>10000 — fine for our scale (1076 ref + ~1000-1500 curr). Determinism: KS-test on identical samples returns identical stat (numpy-level reproducibility). Use `method='exact'` ONLY if you need bit-exact across scipy minor versions — but `'auto'` is the documented default and works deterministically for our sample sizes. |
| Install | (no new install — comes with sklearn) |

### 3. `sklearn.calibration.calibration_curve` — ECE compute

| Property | Value |
|----------|-------|
| Package | `scikit-learn` (Phase 7 dep, already pinned) |
| Version | `>=1.8.0` (Phase 7 D-07-03-B requires manual Platt+Isotonic without `CalibratedClassifierCV(cv='prefit')` which was removed in 1.8) |
| Import | `from sklearn.calibration import calibration_curve` |
| API | `calibration_curve(y_true, y_prob, n_bins=10, strategy='uniform') → (prob_true: ndarray, prob_pred: ndarray)`. Bins with no samples are dropped (returned arrays may be shorter than n_bins). [VERIFIED: scikit-learn.org/stable/.../calibration_curve.html] |
| ECE one-liner | `ece = float(np.sum(np.abs(prob_true - prob_pred) * (bin_counts / len(y_true))))` where `bin_counts` reconstructed via `np.bincount` on `np.searchsorted` (same pattern sklearn uses internally). |
| Pitfall | `n_bins` sensitivity: n_bins=10 (Phase 7 fold_metrics default) vs 15 vs 20 can shift ECE by ±0.005. Phase 9 drift comparison MUST use the SAME n_bins as Phase 7 training. Read `n_bins` from metadata.json if available; default to 10 (project convention). Locking n_bins to a `.env` `DRIFT_ECE_N_BINS=10` removes ambiguity. |
| Install | (no new install) |

### 4. `APScheduler` — monthly cron trigger

| Property | Value |
|----------|-------|
| Package | `apscheduler` (already in requirements.txt — used by `scheduler.py`) |
| Pinned version | `~=3.11` (project current; 3.11.2.post1 latest 3.x line) [VERIFIED: pypi.org/project/APScheduler] |
| Import | `from apscheduler.schedulers.background import BackgroundScheduler; from apscheduler.triggers.cron import CronTrigger` |
| Pattern | Phase 9 instantiates a NEW `BackgroundScheduler` (NOT reuses the BlockingScheduler) in `retrain/scheduler.py`. Reason: scheduler.py:294 `BlockingScheduler(timezone=cfg.OPERATING_TIMEZONE)` is the main loop owner (blocks process). BackgroundScheduler is thread-based and starts immediately without blocking. They coexist in the same process safely (no shared persistent jobstore = no inter-process race). [VERIFIED: APScheduler 3.11 userguide on coexistence.] |
| Pitfall #1 | Sharing a persistent job store between schedulers leads to incorrect behavior (duplicate execution OR missed jobs). Phase 9 RetrainScheduler MUST use the default `MemoryJobStore` (no persistence) — drift breach + cron + manual paths are idempotent by dedup (D-09-C3), so post-restart re-firing is harmless. [VERIFIED: APScheduler FAQ.] |
| Pitfall #2 | `misfire_grace_time` controls how long after the scheduled trigger fire the job is still eligible to run. Cron monthly = if process restarts > grace_time after the scheduled hour, the job is dropped silently. Recommend `misfire_grace_time=3600` (1h) for monthly retrain — gives operator 1h to start the agent after a maintenance restart. |
| Pitfall #3 | `max_instances=1` + `coalesce=True` + `replace_existing=True` mandatory. Without `replace_existing=True`, scheduler restart raises `ConflictingIdError`. Same triple is already used in `scheduler.py:303-311` for the ordinary cycle — same pattern. |

### 5. Standard library: `sqlite3` (drift_log.db, validation_log.db)

No new dep. Pattern lifted verbatim from `mcp_tools/job_queue.py:60-72` (`_ensure_error_column`) + `logger.py:14-28` (`_TRADES_LOG_SCHEMA`). WAL mode mandatory. `CREATE TABLE IF NOT EXISTS` idempotent.

### 6. Standard library: `os.replace` (atomic rename Windows + POSIX)

Confirmed via Python 3.12 docs and atomicwrites issue tracker that `os.rename` on Windows FAILS if target exists, while `os.replace` uses `MoveFileEx(MOVEFILE_REPLACE_EXISTING)` and is atomic. Use `os.replace(candidate_pkl, final_pkl)` followed by `os.replace(candidate_metadata, final_metadata)` (pair operation; the .pkl + .metadata.json must move together). Pitfall: if process crashes between the two replaces, you have new .pkl with old .metadata.json — schema mismatch on next MLFilter.load (Phase 7 D-07-05-D enforces). Mitigation: rename metadata FIRST (smaller, faster), then .pkl. If crash after metadata rename, MLFilter.load will fail FeatureSchemaMismatchError → operator alerted → manual reconciliation → no silent corruption.

---

## Implementation Patterns

### Area A — Failure clustering HDBSCAN

**Closest existing analog:** `ml/feature_extraction.py:build_feature_vector` (Phase 7 Plan 07-01 line 109) — single-row pd.DataFrame builder. Phase 9 cluster preprocessing batches the same builder over 778 losing-trade rows.

**Skeleton (`cluster/hdbscan_runner.py`):**
```python
"""Phase 9 Area A: HDBSCAN failure-mode clustering su losing-trade baseline.

Riusa Phase 7 ml/feature_extraction.build_feature_vector per costruire la matrice
feature; produce label per-trade + exemplar IDs + feature-distribution summary
per cluster. Audit-anchored via bundle.metadata.dataset_hash.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
from hdbscan import HDBSCAN

from ml.feature_extraction import build_feature_vector

# tutte le costanti via cfg .env: HDBSCAN_MIN_CLUSTER_SIZE, HDBSCAN_MIN_SAMPLES,
# HDBSCAN_CLUSTER_SELECTION_METHOD ('eom' default), HDBSCAN_PREDICTION_DATA=True


def build_feature_matrix(
    losing_trades_df: pd.DataFrame,
    feature_list: list[str],
    cat_encodings: dict[str, dict],
) -> tuple[np.ndarray, list[int]]:
    """Costruisce matrice (N×D) da `build_feature_vector` Phase 7 — D-09-A4.

    Riuso totale del pipeline Phase 7 (consistency target encoding D-01 ↔ feature
    pipeline D-10/D-11). Ritorna ndarray + lista di trade_id allineati.
    """
    rows = []
    trade_ids = []
    for _, row in losing_trades_df.iterrows():
        # Ricostruisce draft+indicators+ctx da row Phase 5 schema-v2 parquet
        draft, indicators, ctx = _row_to_phase7_inputs(row)
        fv = build_feature_vector(draft, indicators, ctx, feature_list, cat_encodings)
        rows.append(fv.values[0])  # single-row DataFrame → 1D ndarray
        trade_ids.append(int(row["trade_id"]))
    return np.asarray(rows, dtype=np.float32), trade_ids


def fit_clusters(X: np.ndarray, cfg) -> HDBSCAN:
    """Fit HDBSCAN con prediction_data=True (pitfall #1 documented).

    Senza prediction_data=True, approximate_predict post-load fallisce con
    AttributeError 'No prediction data was generated'.
    """
    clusterer = HDBSCAN(
        min_cluster_size=cfg.HDBSCAN_MIN_CLUSTER_SIZE,        # default 20 per .env
        min_samples=cfg.HDBSCAN_MIN_SAMPLES,                  # default None (=min_cluster_size)
        cluster_selection_method=cfg.HDBSCAN_CLUSTER_SELECTION_METHOD,  # 'eom'
        prediction_data=True,                                  # MANDATORY Wave 1
        core_dist_n_jobs=1,                                    # determinism: single-thread
    )
    clusterer.fit(X)
    return clusterer


def summarize_clusters(
    clusterer: HDBSCAN,
    trade_ids: list[int],
    losing_trades_df: pd.DataFrame,
    top_n_exemplars: int = 3,
) -> list[dict]:
    """Per ogni cluster (label != -1): exemplar IDs (max condensed-tree weight),
    feature-distribution summary (median + IQR), avg_pnl_pips, hit_rate, summary_it.

    Output shape spec MCP-07 D-09-A3 § specifics — schema rendering 1:1.
    """
    out = []
    labels = clusterer.labels_
    probs = clusterer.probabilities_  # in-cluster membership strength
    for cid in sorted(set(labels) - {-1}):
        mask = labels == cid
        cluster_ids = [trade_ids[i] for i in np.where(mask)[0]]
        # top-N exemplar: massima probabilità membership intra-cluster
        top_idx = np.argsort(-probs[mask])[:top_n_exemplars]
        exemplars = [cluster_ids[i] for i in top_idx]
        sub = losing_trades_df.loc[losing_trades_df["trade_id"].isin(cluster_ids)]
        out.append({
            "cluster_id": int(cid),
            "n_trades": int(mask.sum()),
            "exemplar_trade_ids": exemplars,
            "feature_distribution_summary": _summarize_numeric(sub),
            "avg_pnl_pips": float(sub["pnl_pips"].mean()),
            "hit_rate_within_cluster": float((sub["exit_reason"] == "TP_HIT").mean()),
            "summary_it": _autoformat_it(sub),  # italiano per CLAUDE.md
        })
    return out
```

**Persist contract (`cluster/artifact.py`):** Mirror `ml/artifact.py` (Phase 7 D-07-05-A):
- `dump_cluster_bundle(clusterer, trade_ids, summaries, metadata, out_path)` → joblib `.pkl` + `.metadata.json` sidecar.
- Metadata: `{ "model_version": v3, "computed_at": iso, "dataset_hash": sha256, "n_losing_trades_total": int, "n_clusters": int, "n_noise": int, "quality_metrics": { "davies_bouldin": float, "silhouette": float, "quality": "good|acceptable|poor" } }`.
- `prediction_data=True` is preserved through joblib serialization (verified via hdbscan FAQ docs).

### Area B — Drift monitor 3-tier

**Closest existing analog:** `mcp_tools/job_queue.py:60-72` `_ensure_error_column` (idempotent ALTER TABLE) + `logger.py:69-90` `log_trade_decision` (writer pattern).

**Skeleton (`drift/compute.py`):**
```python
"""Phase 9 Area B: 3-tier drift compute — prediction KS + calibration ECE + feature drift top-K.

Reference: static training distribution da models/classifier_v{N}.metadata.json
(D-09-B2 lock). No re-train, no rolling — closed loop con retrain trigger
risolve drift by construction.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.calibration import calibration_curve


def compute_prediction_ks(
    pred_reference: np.ndarray,
    pred_current: np.ndarray,
) -> dict:
    """KS-test su distribuzione prediction (calibrated_prob)."""
    stat, pvalue = ks_2samp(pred_reference, pred_current, method="auto")
    return {
        "ks_stat": float(stat),
        "ks_pvalue": float(pvalue),
        "n_reference": len(pred_reference),
        "n_current": len(pred_current),
    }


def compute_ece(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """ECE via sklearn.calibration_curve + numpy weighted sum.

    Pitfall: n_bins MUST match Phase 7 training (default 10). Read da .env
    DRIFT_ECE_N_BINS per consistency cross-phase.
    """
    if len(y_true) < n_bins:
        return float("nan")  # cold-start: troppi pochi outcome confermati
    prob_true, prob_pred = calibration_curve(
        y_true, y_prob, n_bins=n_bins, strategy="uniform",
    )
    # Bin count per ognuno dei bin che ha campioni
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.clip(np.searchsorted(bin_edges, y_prob, side="right") - 1, 0, n_bins - 1)
    bin_counts = np.bincount(bin_idx, minlength=n_bins)
    # calibration_curve drop-na bin: re-align
    nonzero = bin_counts > 0
    weights = bin_counts[nonzero] / len(y_true)
    return float(np.sum(np.abs(prob_true - prob_pred) * weights))


def compute_feature_drift_topk(
    df_reference: pd.DataFrame,
    df_current: pd.DataFrame,
    top_k_features: list[str],
    ks_threshold: float = 0.01,
) -> list[dict]:
    """Per-feature KS top-K (D-09-B1 top 15 da bundle.feature_importance_).

    Categorical features (Phase 7 D-10: symbol/timeframe/profile/setup_name/regime)
    ESCLUSI — KS valido solo per numeric. Chi-square deferred Phase 11+.
    """
    out = []
    for feat in top_k_features:
        if feat not in df_reference.columns or feat not in df_current.columns:
            continue
        ref = df_reference[feat].dropna().values
        cur = df_current[feat].dropna().values
        if len(ref) < 10 or len(cur) < 10:
            continue
        stat, pvalue = ks_2samp(ref, cur, method="auto")
        out.append({
            "feature": feat,
            "ks_stat": float(stat),
            "ks_pvalue": float(pvalue),
            "breached": bool(pvalue < ks_threshold),
        })
    return out
```

**Persistence (`drift/log_db.py`)** — schema spec già locked in CONTEXT.md § specifics. Pattern verbatim da `logger.py:14-28`:
```python
_DRIFT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS drift_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  model_version TEXT NOT NULL,
  reference_hash TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value REAL NOT NULL,
  threshold REAL NOT NULL,
  breached INTEGER NOT NULL,
  n_samples_current INTEGER,
  n_samples_reference INTEGER,
  window_days INTEGER,
  computed_by TEXT
)
"""

def ensure_drift_log_db(db_path: str | Path) -> None:
    """Idempotente, WAL mode — analog mcp_tools/trail_daemon.ensure_table."""
    with sqlite3.connect(str(db_path)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(_DRIFT_LOG_DDL)
        c.execute("CREATE INDEX IF NOT EXISTS idx_drift_log_ts ON drift_log(ts_utc, model_version, breached)")
```

### Area C — Retrain trigger workflow

**Closest existing analog:** `mcp_tools/handlers/backtest.py:309-336` `handle_run_backtest` (handler signature) + Phase 8 Plan 08-04 line 17-25 (`_train_ml_filter_worker` reuse).

**Skeleton (`retrain/scheduler.py` — APScheduler cron):**
```python
"""Phase 9 Area C: monthly cron retrain trigger via APScheduler BackgroundScheduler.

Coesiste con scheduler.py BlockingScheduler ordinary cycle (process owner) —
BackgroundScheduler è thread-based, no shared persistent jobstore (D-09-C3
dedup idempotent via JobQueue cap=1 condivisa, no race).
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from logger import init_logger
from config import Config


class RetrainScheduler:
    def __init__(self, job_queue, cfg: Config) -> None:
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._job_queue = job_queue
        self._cfg = cfg
        self._log = init_logger(cfg)

    def start(self) -> None:
        trigger = CronTrigger.from_crontab(
            self._cfg.RETRAIN_CRON_SCHEDULE,  # default "0 2 1 * *" — 1° mese 02:00 UTC
        )
        self._scheduler.add_job(
            self._fire_scheduled_retrain,
            trigger=trigger,
            id="retrain_monthly",
            replace_existing=True,        # pitfall #3 — restart-safe
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,      # 1h grace su agent restart
        )
        self._scheduler.start()

    def _fire_scheduled_retrain(self) -> None:
        # D-09-C3 dedup idempotent: check JobQueue stato in-flight
        from retrain.dedup import enqueue_or_dedup
        result = enqueue_or_dedup(
            self._job_queue, source="scheduled_cron", cfg=self._cfg,
        )
        self._log.info(
            "RetrainScheduler tick — status=%s job_id=%s sources=%s",
            result.get("status"), result.get("job_id"),
            result.get("triggered_by_sources"),
        )
```

**Validation gate (`retrain/validation_gate.py`):**
```python
"""Phase 9 Area C D-09-C2: auto-validation gate prima di atomic promote.

3 check:
1. ECE held-out fold regression vs reference metadata.json
2. Prediction-distribution KS divergence candidate vs reference (sospetto overfit)
3. Threshold sweep expectancy regression per profile

Pass tutti → os.replace candidate → final (Windows-atomic via MoveFileEx).
Fail → keep .candidate + log validation_log.db + alarm operator.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from scipy.stats import ks_2samp

from ml.artifact import load_bundle
from drift.compute import compute_ece


def run_validation_gate(
    candidate_path: Path,
    reference_path: Path,
    held_out_df,           # held-out fold data
    cfg,
) -> dict:
    """Ritorna {passed: bool, checks: [...], reject_reason: str|None}."""
    cand_bundle, cand_meta = load_bundle(candidate_path)
    ref_bundle, ref_meta = load_bundle(reference_path)

    checks = []

    # CHECK 1 — ECE regression
    cand_ece = cand_meta["aggregate"]["ece"]
    ref_ece = ref_meta["aggregate"]["ece"]
    regression_pct = ((cand_ece - ref_ece) / ref_ece) * 100 if ref_ece > 0 else 0
    ece_passed = regression_pct <= cfg.MAX_ECE_REGRESSION_PCT
    checks.append({
        "name": "ece_regression",
        "metric_value": regression_pct,
        "threshold": cfg.MAX_ECE_REGRESSION_PCT,
        "passed": ece_passed,
    })

    # CHECK 2 — Prediction-distribution KS divergence
    pred_cand = cand_bundle["model"].predict_proba(held_out_df)[:, 1]
    pred_ref = ref_bundle["model"].predict_proba(held_out_df)[:, 1]
    ks_stat, _ = ks_2samp(pred_ref, pred_cand)
    ks_passed = ks_stat <= cfg.KS_CANDIDATE_DIVERGENCE_THRESHOLD
    checks.append({
        "name": "ks_divergence",
        "metric_value": float(ks_stat),
        "threshold": cfg.KS_CANDIDATE_DIVERGENCE_THRESHOLD,
        "passed": ks_passed,
    })

    # CHECK 3 — Threshold-sweep expectancy regression per profile (cfg.EXPECTANCY_REGRESSION_PCT)
    # ... (riusa logica Phase 7 Plan 07-04 sweep helper, no duplicate)

    all_passed = all(c["passed"] for c in checks)
    reject_reason = (
        None if all_passed
        else f"validation_failed: {[c['name'] for c in checks if not c['passed']]}"
    )
    return {"passed": all_passed, "checks": checks, "reject_reason": reject_reason}


def atomic_promote(candidate_path: Path, final_path: Path) -> None:
    """os.replace atomico (Windows: MoveFileEx replace-existing; POSIX: rename).

    Ordine: metadata.json PRIMA, .pkl DOPO. Se crash inter-pair, MLFilter.load
    fallisce FeatureSchemaMismatchError (Phase 7 D-07-05-D) → alarm visibile,
    NO silent corruption.
    """
    cand_meta = candidate_path.with_suffix(".metadata.json")
    final_meta = final_path.with_suffix(".metadata.json")
    os.replace(str(cand_meta), str(final_meta))   # PRIMA metadata
    os.replace(str(candidate_path), str(final_path))  # POI .pkl

    # Hot-reload MLFilter singleton (Phase 7 D-07-05-E)
    from ml.inference import _invalidate_singleton  # to-be-added Wave 0 Phase 9
    _invalidate_singleton()
```

**Handler (`mcp_tools/handlers/retrain.py`):**
```python
def handle_trigger_retrain(args: dict, job_queue, cfg, log) -> dict:
    """MCP-09 wrapper su Phase 8 _train_ml_filter_worker — D-09-C1.

    No duplicate training logic. Dedup idempotent D-09-C3.
    """
    from retrain.dedup import enqueue_or_dedup
    return enqueue_or_dedup(
        job_queue,
        source="manual_mcp",
        reason=args.get("reason", "manual"),
        cfg=cfg,
    )
```

### Area D — suggest_position_action

**Closest existing analog:** `mcp_tools/handlers/position.py:258-318` `handle_get_position_state` (read-only handler) + `risk_engine.py` (rule-based gate pattern).

**Skeleton (`position_action/orchestrator.py`):**
```python
"""Phase 9 Area D: hybrid rule + ML re-evaluation con OOD caveat surfacing.

D-09-D1: rule-based primary (R-multiple + Time stop); ML re-eval modula severity.
D-09-D2: structured rationale + summary_it (CLAUDE.md italiano).
D-09-D4: prefer cached ml_calibrated_prob da trades_log; fallback recompute.
"""
from __future__ import annotations

from mcp_tools.errors import ErrorCodes, envelope
from mcp_tools.handlers.position import handle_get_position_state


def handle_suggest_position_action(
    args: dict, mt5_client, cfg, log,
) -> dict:
    """MCP-18: hold/move_sl/partial_close/full_close + rationale strutturato.

    READ-ONLY suggest (NOT a gate, NOT mutates position). Skill chiama
    handle_modify_position Phase 6 Plan 06-04 se accetta.
    """
    pid = int(args["position_id"])

    # Step 1: posizione corrente via Phase 6 handler (no direct mt5)
    state = handle_get_position_state({"position_id": pid}, mt5_client, cfg)
    if state.get("ok") is False:
        return state  # propaga error envelope

    # Step 2: rule-based primary (D-09-D3)
    from position_action.rules import evaluate_rules
    rule_outcome = evaluate_rules(state, cfg)

    # Step 3: ML re-evaluation (D-09-D1 — OOD caveat)
    from position_action.ml_recheck import evaluate_ml_thesis
    ml_check = evaluate_ml_thesis(state, pid, cfg)

    # Step 4: hybrid combine — ML modula severity rule
    from position_action.rules import modulate_with_ml
    final_action, final_params, confidence = modulate_with_ml(
        rule_outcome, ml_check, cfg,
    )

    # Step 5: structured rationale — D-09-D2
    rationale = {
        "rules_triggered": rule_outcome["rules_triggered"],
        "ml_check": ml_check,
        "summary_it": _format_summary_it(rule_outcome, ml_check, final_action),
    }

    return {
        "position_id": pid,
        "action": final_action,
        "params": final_params,
        "confidence": confidence,
        "rationale": rationale,
    }


def _format_summary_it(rule_outcome, ml_check, final_action) -> str:
    """Italiano operator-readable summary — CLAUDE.md regola fondamentale."""
    rules_part = ", ".join(r["name"] for r in rule_outcome["rules_triggered"])
    if ml_check.get("ml_filter_disabled"):
        ml_part = "ML filter disabilitato (solo regole)"
    elif ml_check.get("signal") == "below_threshold":
        ml_part = (
            f"thesis invalidata (prob {ml_check['calibrated_prob_now']:.2f} < "
            f"soglia {ml_check['threshold_profile']:.2f})"
        )
    elif ml_check.get("signal") == "above_but_decreasing":
        ml_part = (
            f"thesis in calo (entry {ml_check['calibrated_prob_at_entry']:.2f} → "
            f"now {ml_check['calibrated_prob_now']:.2f}) — caveat OOD"
        )
    else:
        ml_part = "thesis confermata ML"
    return f"Azione {final_action}: {rules_part}. {ml_part}."
```

**ML re-eval con OOD caveat (`position_action/ml_recheck.py`):**
```python
def evaluate_ml_thesis(state: dict, pid: int, cfg) -> dict:
    """Mid-trade ML re-evaluation — OOD per costruzione (Phase 7 D-17).

    Phase 7 classifier trainato su features_at_decision_time. Mid-trade input
    distribution è OOD: NON interpretare prob_now come P(TP_HIT | features_now).
    Use solo: (a) prob_now vs threshold_profile (relative), (b) prob_now vs
    prob_at_entry ratio (trend signal). MAI absolute interpretation.
    """
    if not cfg.ENABLE_ML_FILTER:
        return {
            "calibrated_prob_at_entry": None,
            "calibrated_prob_now": None,
            "threshold_profile": None,
            "signal": "n/a",
            "ood_caveat": False,
            "ml_filter_disabled": True,
        }

    # D-09-D4: prefer cached da trades_log
    prob_at_entry = _lookup_cached_prob(pid)  # SELECT ml_calibrated_prob FROM trades_log
    if prob_at_entry is None:
        # Fallback recompute da decision_context_json + MLFilter
        prob_at_entry = _recompute_prob_at_entry(pid)

    # Compute prob NOW via build_feature_vector + MLFilter.predict
    from ml.inference import get_ml_filter
    from ml.feature_extraction import build_feature_vector

    draft_now, indicators_now, ctx_now = _build_inputs_now(state)
    fv_now = build_feature_vector(draft_now, indicators_now, ctx_now,
                                   _feature_list(), _cat_encodings())
    ml_filter = get_ml_filter(cfg.ML_MODEL_PATH)
    _, prob_now = ml_filter.predict(fv_now)

    threshold = cfg.ML_THRESHOLD_BY_PROFILE[state["profile"]]

    # Signal classification (D-09 specifics § OOD caveat boilerplate step 5)
    if prob_now <= threshold:
        signal = "below_threshold"
    elif prob_at_entry and prob_now < prob_at_entry * 0.9:
        signal = "above_but_decreasing"
    else:
        signal = "above_threshold"

    return {
        "calibrated_prob_at_entry": float(prob_at_entry) if prob_at_entry else None,
        "calibrated_prob_now": float(prob_now),
        "threshold_profile": float(threshold),
        "signal": signal,
        "ood_caveat": True,                # MANDATORY when ML active
        "ml_filter_disabled": False,
    }
```

---

## Cross-Phase Reuse Map

Validates D-09-C1 + D-09-A4 + D-09-D zero-duplication claims.

| Phase 9 Module | Reuses From | Reused Asset | Purpose |
|----------------|-------------|--------------|---------|
| `cluster/preprocessing.py::build_feature_matrix` | Phase 7 Plan 07-01 | `ml/feature_extraction.build_feature_vector` | D-09-A4 consistency Phase 7 ↔ Phase 9 feature pipeline |
| `cluster/preprocessing.py` | Phase 5 Plan 05-09 | `data/training/baseline_decisions/part-0.parquet` | D-09-A1 cluster input (read-only) |
| `cluster/artifact.py::dump_cluster_bundle` | Phase 7 Plan 07-05 | `ml/artifact.py::dump_bundle` (pattern only — not import) | Mirror joblib+sidecar.json schema |
| `drift/reference.py::load_reference` | Phase 7 Plan 07-05 | `ml/artifact.py::load_bundle` + `models/classifier_v{N}.metadata.json` | D-09-B2 audit-anchored sha256 reference |
| `drift/compute.py::compute_ece` | Phase 7 Plan 07-03 | `sklearn.calibration.calibration_curve` (already dep) | No new dep — riuso transitive |
| `drift/log_db.py::ensure_drift_log_db` | Phase 6 Plan 06-04 + Phase 6 Plan 06-03 | `mcp_tools/trail_daemon.ensure_table` + `mcp_tools/job_queue._ensure_error_column` | Pattern verbatim (WAL + idempotent CREATE) |
| `retrain/scheduler.py::RetrainScheduler` | Phase 1 + Phase 16 | `scheduler.py:293-313` (BlockingScheduler cron pattern) | Pattern only — separate BackgroundScheduler instance |
| `retrain/dedup.py::enqueue_or_dedup` | Phase 6 Plan 06-03 + Phase 8 Plan 08-04 | `mcp_tools/job_queue.JobQueue.submit` (cap=1 already enforced) + Phase 8 dedup pattern | D-09-C3 — JobQueue cap=1 IS the dedup |
| `retrain/validation_gate.py::run_validation_gate` | Phase 7 Plan 07-04 | `ml/train.py` threshold sweep helper (~50 LOC reused) | D-09-C2 check 3 expectancy regression |
| `retrain/promotion.py::atomic_promote` | (new — uses stdlib os.replace) | — | Windows-atomic + MLFilter singleton invalidation |
| `mcp_tools/handlers/retrain.py::handle_trigger_retrain` | Phase 8 Plan 08-04 | `_train_ml_filter_worker(args, cfg_dict)` top-level picklable + sha256 strict-fail | D-09-C1 zero duplication — SAME worker |
| `mcp_tools/handlers/retrain.py` | Phase 6 Plan 06-03 | `mcp_tools/job_queue.JobQueue` (shared cap=1) | D-09-C1 race protezione condivisa |
| `position_action/orchestrator.py` | Phase 6 Plan 06-04 | `mcp_tools/handlers/position.handle_get_position_state` | D-09-D consumer — no direct mt5 call |
| `position_action/ml_recheck.py` | Phase 7 Plan 07-01 + Plan 07-05 | `ml/feature_extraction.build_feature_vector` + `ml/inference.get_ml_filter` | D-09-D1 ML re-eval reuse — singleton + feature builder |
| `position_action/ml_recheck.py` (cache lookup) | Phase 7 Plan 07-06 + Phase 9 D-09-D4 schema migration | `trades_log.ml_calibrated_prob` column | D-09-D4 prefer cached |
| `mcp_tools/handlers/{cluster,drift,retrain,position_action}.py` | Phase 6 Plan 06-02 + 06-03 + 06-04 | `mcp_tools/errors.py::ErrorCodes,envelope` + handler signature pattern | API contract uniformità |
| All Phase 9 handlers | Phase 6 D-A1 | `ProcessPoolExecutor` worker isolation | MLFilter singleton fork-safe — each worker reloads at next predict |

**Net new Phase 9 code:** `cluster/` (~600 LOC) + `drift/` (~600 LOC) + `retrain/` (~400 LOC) + `position_action/` (~400 LOC) + 4 handlers (~570 LOC) + 1 CLI script (~200 LOC) + .env + logger + config extensions (~80 LOC) ≈ **~2850 LOC source** + ~1200 LOC tests. Reuse ratio: ~70% of dependencies come from Phase 5/6/7/8 — confirms D-09-C1 audit-path-singularity claim.

---

## Validation Architecture

**Required by Nyquist Dimension 8 (workflow.nyquist_validation enabled — config absent = enabled).**

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest >= 8.0` (project standard, Phase 1-8 baseline) |
| Config file | `pytest.ini` (existing) — no Phase 9-specific config |
| Quick run command | `pytest tests/test_cluster_hdbscan.py tests/test_drift_compute.py tests/test_retrain_dedup.py tests/test_position_action_rules.py -x -q` |
| Full suite command | `pytest tests/ -x` (NB: Phase 1 perf test `test_smoke_12month_under_60s` is pre-existing fail — deferred per Plan 01-09; do not gate on it) |
| Phase gate | All Phase 9 tests green + zero regression on Phase 1-8 suite (delta from current 458 passed baseline) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ML-07 | Failure clustering identifies ≥3 distinct loss-mode clusters on baseline with feature-importance | unit + integration | `pytest tests/test_cluster_hdbscan.py::test_baseline_fits_at_least_3_clusters -x` | ❌ Wave 1 |
| ML-07 | HDBSCAN noise label `-1` populated for idiosyncratic failures | unit | `pytest tests/test_cluster_hdbscan.py::test_noise_label_populated -x` | ❌ Wave 1 |
| ML-07 | Cluster quality DB index < 2.0 OR fallback PCA recommendation | unit | `pytest tests/test_cluster_hdbscan.py::test_cluster_quality_gate -x` | ❌ Wave 1 |
| ML-07 | `approximate_predict` round-trip post joblib persist (pitfall #1) | integration | `pytest tests/test_cluster_artifact.py::test_persist_then_approximate_predict -x` | ❌ Wave 1 |
| ML-08 | Prediction KS-stat computed correctly on fixed reference vs fixed current | unit | `pytest tests/test_drift_compute.py::test_ks_2samp_determinism -x` | ❌ Wave 2 |
| ML-08 | ECE computed correctly (1e-6 tolerance vs hand-calc) | unit | `pytest tests/test_drift_compute.py::test_ece_hand_calc -x` | ❌ Wave 2 |
| ML-08 | Feature drift top-K (K=15) per LightGBM importance order | unit | `pytest tests/test_drift_compute.py::test_feature_drift_topk_ordering -x` | ❌ Wave 2 |
| ML-08 | Alarm fires when ANY of 3 thresholds breached | unit | `pytest tests/test_drift_alarm.py::test_alarm_fires_on_any_breach -x` | ❌ Wave 2 |
| ML-08 | Synthetic distribution-shift forced breach detected end-to-end | integration | `pytest tests/test_drift_e2e.py::test_synthetic_shift_breach -x` | ❌ Wave 2 |
| ML-09 | 3 trigger sources (drift_breach, scheduled_cron, manual_mcp) all enqueue same worker | unit | `pytest tests/test_retrain_dedup.py::test_all_sources_same_worker -x` | ❌ Wave 3 |
| ML-09 | Concurrent 3 triggers → 1 job + 2 `already_pending` (D-09-C3 idempotent) | unit | `pytest tests/test_retrain_dedup.py::test_idempotent_dedup -x` | ❌ Wave 3 |
| ML-09 | Validation gate ECE-regression rejects candidate; old model atomically preserved | integration | `pytest tests/test_retrain_validation_gate.py::test_ece_regression_rejects -x` | ❌ Wave 3 |
| ML-09 | Atomic promote round-trip: candidate→final via os.replace (Windows-safe) | integration | `pytest tests/test_retrain_promotion.py::test_os_replace_atomic_pair -x` | ❌ Wave 3 |
| ML-09 | MLFilter singleton hot-reload post promote (cache invalidated) | integration | `pytest tests/test_retrain_promotion.py::test_singleton_invalidation -x` | ❌ Wave 3 |
| ML-09 | APScheduler cron parsed correctly + max_instances=1 + replace_existing=True | unit | `pytest tests/test_retrain_scheduler.py::test_cron_config -x` | ❌ Wave 3 |
| MCP-07 | `get_failure_clusters(top_n)` returns N exemplars per cluster + summary_it Italian | unit | `pytest tests/test_mcp_handlers_cluster.py::test_response_shape -x` | ❌ Wave 1 |
| MCP-08 | `get_drift_metrics(window_days)` response shape matches spec | unit | `pytest tests/test_mcp_handlers_drift.py::test_response_shape -x` | ❌ Wave 2 |
| MCP-08 | Cold-start handling: n_samples_current < MIN_DRIFT_SAMPLES → NaN ECE + flag | unit | `pytest tests/test_mcp_handlers_drift.py::test_cold_start -x` | ❌ Wave 2 |
| MCP-18 | Hybrid rule + ML hold/move_sl/partial_close/full_close | unit | `pytest tests/test_position_action_rules.py::test_4_rules_isolated -x` | ❌ Wave 4 |
| MCP-18 | OOD caveat surfaced when ML active | unit | `pytest tests/test_position_action_ml_recheck.py::test_ood_caveat_always_true -x` | ❌ Wave 4 |
| MCP-18 | ENABLE_ML_FILTER=false fallback: ml_filter_disabled=true, signal=n/a, action from rules only | unit | `pytest tests/test_position_action_ml_recheck.py::test_disabled_fallback -x` | ❌ Wave 4 |
| MCP-18 | `summary_it` field Italian rendering (CLAUDE.md) | unit | `pytest tests/test_position_action_orchestrator.py::test_summary_it_italian -x` | ❌ Wave 4 |
| MCP-18 | `prob_at_entry` cached lookup + fallback recompute (D-09-D4) | unit | `pytest tests/test_position_action_ml_recheck.py::test_cache_lookup_fallback -x` | ❌ Wave 4 |
| INT-03 | CLI `scripts/show_drift.py` produces markdown report `.planning/research/drift-report-{date}.md` | integration | `pytest tests/test_show_drift_cli.py::test_cli_round_trip -x` | ❌ Wave 5 |
| INT-03 | CLI exit code 0 on no breach, 1 on breach (for future cron integration) | unit | `pytest tests/test_show_drift_cli.py::test_exit_codes -x` | ❌ Wave 5 |

### Sample Density

| Tier | Sample density | Source |
|------|----------------|--------|
| Unit (cluster) | 200-row synthetic fixture (Phase 7 reuse `tests/fixtures/baseline_decisions_smoke.parquet`) | Tight TDD loop sub-second |
| Unit (drift) | 50-100 synthetic samples generated via numpy seed=42 | Deterministic + fast |
| Integration (cluster) | 778-row real losing-trade subset from baseline parquet | Validate cluster count + quality on real data |
| Integration (drift) | Full 1076-row parquet as reference + synthetic shift current | E2E breach detection |
| Integration (retrain) | Real Phase 7 fold metadata.json + synthetic candidate metadata | Validation gate end-to-end |
| Integration (MCP-18) | Mock Mt5Client position state + real MLFilter singleton on bundle.pkl | OOD caveat surfaced + structured rationale validated |
| Smoke (INT-03) | Real drift_log.db with 3 rows seeded → markdown roundtrip | CLI deliverable |

### Determinism Contracts

| Component | Contract | Enforcement |
|-----------|----------|-------------|
| HDBSCAN cluster labels | Bit-for-bit identical on repeated fit with same X + same hyperparams (`core_dist_n_jobs=1`) | `test_hdbscan_determinism_seed_invariant` |
| KS-stat | `scipy.stats.ks_2samp` deterministic on identical input arrays | `test_ks_determinism_idempotent` |
| ECE | `sklearn.calibration_curve` + numpy weighted sum deterministic | `test_ece_idempotent` |
| Feature vector | `build_feature_vector(draft, indicators, ctx)` Phase 7 idempotent (D-07-01-C) | Phase 7 already enforces via `test_build_feature_vector_deterministic` |
| MLFilter.predict | Phase 7 D-07-05 deterministic single-thread `num_threads=1` | Phase 7 already enforces |
| RNG seeding | `np.random.seed(42)` in every synthetic-data test fixture; HDBSCAN `core_dist_n_jobs=1` | Locked by .env `DRIFT_SYNTH_SEED=42` |
| Validation gate ECE comparison | Both candidate + reference read SAME n_bins from `.env DRIFT_ECE_N_BINS` (default 10) | `test_ece_n_bins_invariant_across_phases` |

### Cross-Phase Audit Invariants

| Invariant | Mechanism |
|-----------|-----------|
| Cluster artifact tied to specific dataset | `cluster.metadata.dataset_hash == ref_bundle.metadata.dataset_hash` (sha256 baseline parquet) |
| Drift reference tied to specific model | `drift_log.reference_hash == ref_bundle.metadata.dataset_hash` per row |
| Retrain candidate tied to specific input parquet | Phase 8 D-08-B3 sha256 strict-fail propagates `training_data_sha256` to candidate metadata.json |
| Validation gate input traceability | `validation_log.candidate_path` + `validation_log.previous_version` + `triggered_by_sources_json` array |
| MCP-18 prob_at_entry → trades_log row | `trades_log.id == position_id` lookup deterministic; fallback recompute uses `decision_context_json` (immutable post log) |
| MLFilter model_version stamping | Every drift_log row + validation_log row + suggest_position_action response includes `model_version` from bundle.version |
| RetrainScheduler firing audit | APScheduler internal `job.next_run_time` logged via init_logger; misfire logged with grace_time delta |

### Failure Mode Coverage

| Failure Mode | Test | Detection |
|--------------|------|-----------|
| Drift breach simulation | `test_synthetic_distribution_shift_triggers_breach` | Inject N(0,1) → N(0,2) sample → KS p-value < 0.01 → breached=True |
| Validation gate rejection | `test_validation_gate_ece_regression_rejects` | Candidate ECE 0.063 vs ref 0.041 → reject + validation_log row |
| Atomic promote crash inter-pair | `test_promote_crash_recovery` | Simulate failure between metadata.json os.replace and .pkl os.replace; assert next MLFilter.load raises FeatureSchemaMismatchError (not silent corruption) |
| Retrain dedup race | `test_retrain_3_concurrent_triggers` | 3 concurrent calls → 1 job submitted + 2 `already_pending` + sources array contains all 3 |
| HDBSCAN no-prediction-data load | `test_load_without_prediction_data_fails_explicit` | Persist bundle without `prediction_data=True`; load + approximate_predict → raises AttributeError (clear) |
| MLFilter singleton stale post-retrain | `test_singleton_serves_new_bundle_after_promote` | Promote v2 → next predict returns prob from v2 (not cached v1) |
| OOD caveat absent when ML disabled | `test_disabled_ml_yields_filter_disabled_flag` | ENABLE_ML_FILTER=false → ml_filter_disabled=true + ood_caveat=false + signal=n/a |
| Cold-start drift compute | `test_drift_cold_start_below_min_samples` | n_current < MIN_DRIFT_SAMPLES → ECE=NaN + breached=False + soft warning |
| Markdown report regression | `test_show_drift_cli_markdown_stable` | Same drift_log.db seeded rows → identical markdown bytes (diff-friendly) |
| APScheduler restart safety | `test_retrain_scheduler_replace_existing` | Stop+restart RetrainScheduler → no ConflictingIdError |

### Wave 0 Gaps

- [ ] `tests/test_cluster_hdbscan.py` — Wave 1 (covers ML-07 + MCP-07)
- [ ] `tests/test_cluster_artifact.py` — Wave 1 (HDBSCAN persistence pitfall coverage)
- [ ] `tests/test_drift_compute.py` — Wave 2 (covers ML-08 KS + ECE + feature drift)
- [ ] `tests/test_drift_log_db.py` — Wave 2 (SQLite schema + idempotency)
- [ ] `tests/test_drift_alarm.py` — Wave 2 (3-tier threshold breach logic)
- [ ] `tests/test_drift_e2e.py` — Wave 2 (synthetic shift integration)
- [ ] `tests/test_retrain_dedup.py` — Wave 3 (idempotent dedup D-09-C3)
- [ ] `tests/test_retrain_scheduler.py` — Wave 3 (APScheduler cron)
- [ ] `tests/test_retrain_validation_gate.py` — Wave 3 (ECE + KS + expectancy checks)
- [ ] `tests/test_retrain_promotion.py` — Wave 3 (os.replace atomic + singleton invalidation)
- [ ] `tests/test_position_action_rules.py` — Wave 4 (4-rule isolation)
- [ ] `tests/test_position_action_ml_recheck.py` — Wave 4 (OOD caveat + cache + recompute)
- [ ] `tests/test_position_action_orchestrator.py` — Wave 4 (hybrid combine + summary_it)
- [ ] `tests/test_mcp_handlers_cluster_drift_retrain_position.py` — Wave 4-5 (response shapes)
- [ ] `tests/test_show_drift_cli.py` — Wave 5 (INT-03 CLI round-trip)
- [ ] Framework install: `pip install "hdbscan>=0.8.40,<0.9.0"` — Wave 0 .env + requirements.txt update

---

## Pitfalls + Gotchas

### P1 — HDBSCAN without prediction_data=True is a one-way trip
**What goes wrong:** Persist clusterer without `prediction_data=True` at fit OR without `generate_prediction_data()` before `joblib.dump`. Post-restart, `approximate_predict` raises `AttributeError: No prediction data was generated`. There is no fix-after-the-fact — must refit.
**Guard:** `cluster/hdbscan_runner.py:fit_clusters` MUST set `prediction_data=True`. Wave 1 add AST guard or pytest assertion: `clusterer.prediction_data_ is not None` post-fit.
**Test:** `test_persist_then_approximate_predict_succeeds` (load → call approximate_predict on a row → asserts no AttributeError).
[Source: hdbscan readthedocs prediction_tutorial.html.]

### P2 — sklearn.cluster.HDBSCAN cannot do approximate_predict — DO NOT switch to sklearn
**What goes wrong:** Plan author sees sklearn 1.8 ships HDBSCAN and "consolidates dep" by switching from `hdbscan` package to `sklearn.cluster.HDBSCAN`. Wave 2 cluster-match add-on then cannot be implemented — sklearn's class lacks `approximate_predict`, `prediction_data`, `generate_prediction_data()`.
**Guard:** Pin `hdbscan>=0.8.40,<0.9.0` in requirements.txt with comment `# DO NOT switch to sklearn.cluster.HDBSCAN — lacks approximate_predict (Phase 9 Wave 2 needs it)`. Add AST gate `test_imports_hdbscan_not_sklearn` in `tests/test_cluster_hdbscan.py` asserting `from hdbscan import HDBSCAN` (not `from sklearn.cluster import HDBSCAN`).
[Source: WebFetch sklearn.org/stable HDBSCAN page.]

### P3 — sklearn HDBSCAN and contrib hdbscan have different min_samples semantics
**What goes wrong:** Following sklearn docs to set `min_samples=20`, then later switching to contrib package, gives different cluster boundaries. sklearn includes the query point itself in the count; contrib does not. Difference: 1 sample.
**Guard:** Document in `.env.example` next to `HDBSCAN_MIN_SAMPLES`: `# scikit-learn-contrib/hdbscan semantics (NOT sklearn.cluster.HDBSCAN — differs by 1)`.
[Source: scikit-learn issue #27829.]

### P4 — APScheduler shared persistent jobstore = race
**What goes wrong:** Adding RetrainScheduler with a SQLite persistent jobstore alongside the existing `scheduler.py` BlockingScheduler creates inter-scheduler race (APScheduler has no IPC sync) → duplicate retrain fires OR missed cron.
**Guard:** `BackgroundScheduler(timezone="UTC")` with DEFAULT MemoryJobStore (no `jobstore=` arg). Document in `retrain/scheduler.py` docstring. Dedup D-09-C3 + JobQueue cap=1 already protect against duplicate fires.
**Test:** `test_retrain_scheduler_uses_memory_jobstore` asserts `_scheduler._jobstores['default'].__class__.__name__ == 'MemoryJobStore'`.
[Source: APScheduler 3.11 FAQ.]

### P5 — APScheduler ConflictingIdError on restart without replace_existing=True
**What goes wrong:** Process restart, scheduler re-adds same `id="retrain_monthly"`. Without `replace_existing=True`, raises `ConflictingIdError`. Same trap killed Phase 1 plans before existing scheduler.py:303-311 mitigated.
**Guard:** Always pass `replace_existing=True` + `max_instances=1` + `coalesce=True` + `misfire_grace_time=3600`. Pattern verbatim from `scheduler.py:303-311`.
**Test:** `test_retrain_scheduler_restart_idempotent` starts + stops + restarts → no exception.

### P6 — `os.rename` on Windows fails if target exists
**What goes wrong:** Atomic promote uses `os.rename(candidate, final)` on Windows. If `final` exists (always the case post-Phase-7 first deploy), `os.rename` raises `FileExistsError`. POSIX-only mental model. Promote fails silently in production (logged but operator misses); validation_log row written; nothing promoted; user thinks model updated but it didn't.
**Guard:** Use `os.replace` exclusively. Documented in `retrain/promotion.py:atomic_promote` with comment `# Windows-atomic via MoveFileEx(MOVEFILE_REPLACE_EXISTING); POSIX rename — DO NOT use os.rename`.
**Test:** `test_atomic_promote_overwrites_existing` creates both `final.pkl` and `final.metadata.json`, then promotes candidate → both replaced atomically.
[Source: Python 3.12 os module docs + atomicwrites issue #25.]

### P7 — Pair-rename crash → schema mismatch (intended-by-design)
**What goes wrong:** Process crashes between `os.replace(metadata)` and `os.replace(pkl)`. Result: final.metadata.json describes v3 features, final.pkl is v2 model.
**Guard:** Order is `metadata FIRST, .pkl SECOND`. On next MLFilter.load, Phase 7 D-07-05-D `FeatureSchemaMismatchError` raises explicitly → operator alarmed → manual reconciliation. **This is NOT a bug, it's a designed failure mode.** Phase 7 already enforces.
**Test:** `test_promote_crash_between_pair_raises_on_load` (mock `os.replace` to fail on second call; assert subsequent `get_ml_filter()` raises `FeatureSchemaMismatchError`).

### P8 — MLFilter singleton stale after retrain
**What goes wrong:** Phase 7 D-07-05-E `_MODEL_CACHE` not invalidated after `os.replace`. Next predict call returns v2 result from cached singleton instead of new v3 bundle.
**Guard:** `retrain/promotion.py:atomic_promote` calls `_invalidate_singleton()` (to be added Wave 0 Phase 9 in `ml/inference.py`). Implementation: `_MODEL_CACHE = None` inside the existing module-level lock.
**Test:** `test_singleton_serves_new_bundle_after_promote` — load → predict → atomic_promote new bundle → predict → assert model_version returned is v(N+1).

### P9 — OOD inference for mid-trade ML re-eval
**What goes wrong:** Phase 7 D-17 trained on `features_at_decision_time` (bar-close strict-< discipline). MCP-18 `evaluate_ml_thesis` calls predict on `features_now` (mid-bar OR open position state). Distribution shift is real: `r_multiple` is non-zero, `bars_in_trade > 0`, `pnl_pips != 0` — these features were always ~0 at training time (decision = pre-entry). The model has never seen these inputs.
**Guard:** Always set `ml_check.ood_caveat: true` when ML active. NEVER expose absolute `prob_now` interpretation as "P(TP_HIT now)" in any user-facing string. Only relative signals are safe: `prob_now vs threshold_profile`, `prob_now / prob_at_entry` ratio.
**Test:** `test_ood_caveat_always_true_when_ml_active` + `test_summary_it_never_uses_absolute_prob_now_word` (regex check on summary_it text for forbidden phrases like "probabilità che vinca", "P(TP_HIT)").

### P10 — n_bins drift between training (ECE) and Phase 9 (ECE re-compute)
**What goes wrong:** Phase 7 trains with sklearn calibration_curve `n_bins=10` (default). Phase 9 drift compute defaults to `n_bins=15`. ECE values not comparable → false-positive ECE drift alarm.
**Guard:** Single `.env DRIFT_ECE_N_BINS=10` (Phase 7 mirror). Both Phase 7 ECE in `metadata.json.aggregate.ece` and Phase 9 current-window ECE computed with same n_bins. Document in Phase 7 metadata.json: store `n_bins: 10` alongside `ece: 0.041` as audit anchor.
**Test:** `test_ece_n_bins_invariant_across_phases` reads metadata.n_bins == cfg.DRIFT_ECE_N_BINS.

### P11 — Drift_log.db / validation_log.db WAL writer + concurrent reader
**What goes wrong:** Plan 09 standalone CLI `scripts/show_drift.py` reads `logs/drift_log.db` while MCP server (different process) writes drift events. Without WAL mode, reader blocks writer (or vice versa) under SQLite default rollback journal.
**Guard:** All DDL include `PRAGMA journal_mode=WAL` (pattern verbatim Phase 6 `mcp_tools/trail_daemon.ensure_table:82-83`). Test: `test_drift_log_db_wal_mode` post-create checks pragma.
**Test:** `pytest tests/test_drift_log_db.py::test_wal_mode_set`.

### P12 — feature_importance_ may be empty for `categorical_feature=` LightGBM models with low data
**What goes wrong:** D-09-B1 top-K drift uses `bundle.feature_importance_` from Phase 7. If Phase 7 model trained on 1076 rows × ~66 features with sparse data, some features may have zero importance — top-K list contains zero-importance features → KS noise.
**Guard:** Filter `feature_importance_ > 0` before taking top-K. Drop categorical features (Phase 7 D-10) from drift comparison (chi-square Phase 11+). Document: top-K is `top_k_among_numeric_with_nonzero_importance`.
**Test:** `test_feature_drift_excludes_categorical_and_zero_importance`.

### P13 — APScheduler misfire on long process downtime drops monthly cron silently
**What goes wrong:** Agent process down on day 1 of month 02:00 UTC. Comes back online at 03:30 → misfire_grace_time default = None → APScheduler may execute (Cron behavior) OR may skip. Operator-visibility nil.
**Guard:** Explicit `misfire_grace_time=3600` (1h). Document in `.env.example` next to `RETRAIN_CRON_SCHEDULE`: `# Job missed by more than 1h after scheduled fire is dropped silently; force-trigger via MCP if needed.`. Log via init_logger every cron tick (fire OR skip-missed).
**Test:** `test_retrain_scheduler_misfire_grace_time_set`.

### P14 — Race: backtest writing baseline_decisions parquet + Phase 9 cluster reading
**What goes wrong:** Operator triggers `/baseline run` while cluster artifact generation is reading the same parquet. pyarrow read mid-write → IOError or truncated DataFrame.
**Guard:** Same protection as Phase 8 D-08-A2: cap=1 JobQueue serializes. Phase 9 cluster compute is currently a one-shot at Wave 1 execute, NOT a JobQueue worker. **Plan-phase decision:** if cluster artifact regeneration becomes a recurring trigger (Wave 2 add-on `recompute_failure_clusters` MCP tool), it MUST enqueue via same JobQueue.
**Test:** None Wave 1 (one-shot); Wave 2 add-on test required.

### P15 — Italian rationale rendering — guard against missing summary_it
**What goes wrong:** Plan author forgets `summary_it` field in MCP-18 response, or returns English text accidentally.
**Guard:** AST/regex test `test_mcp18_response_has_summary_it_field` + content check for known Italian markers (verbi: `suggerisco`, `confermata`, `invalidata`, `raggiunto`, `caveat`).
**Test:** `pytest tests/test_position_action_orchestrator.py::test_summary_it_italian_markers`.

---

## Open Questions

None blocking — all decisions are locked in CONTEXT.md (16 decisions D-09-A1..D4) and carry-forward Phase 6/7/8 provides remaining technical constraints. Plan-phase should resolve the following Claude's-discretion items via PATTERNS.md:

1. **HDBSCAN `min_cluster_size` exact value** — CONTEXT.md states "∈ [15, 25] da decidere in plan-phase via cluster-quality validation". Wave 1 should benchmark min_cluster_size ∈ {15, 20, 25} on real 778-row losing-trade subset, pick value that maximizes (DB-index minimization + clusters ≥3 + noise ≤10%). Default starting point: 20 (gives ~39 cluster max if perfectly even; expect 3-7 in practice).

2. **HDBSCAN distance metric** — default `euclidean` post-StandardScaler is the safe default (66-dim numeric + one-hot categorical). Plan-phase: confirm OR consider `gower` distance via `gower>=0.1` package for mixed-type without preprocessing (~50MB dep). Recommend: stick with `euclidean` post-Phase-7-feature-pipeline (zero new dep + consistency Phase 7 ↔ Phase 9).

3. **`MIN_DRIFT_SAMPLES_CURRENT` default** — CONTEXT.md says "30 default" in .env additions. Plan-phase: validate this against ECE compute stability — with 10 bins and 30 samples, average 3 samples per bin → ECE noisy. Recommend ramp: cold-start (n<30) → soft warning, no breach; warm (30 ≤ n < 100) → flag `low_confidence: true`; hot (n ≥ 100) → fully trust.

4. **APScheduler timezone for cron** — CONTEXT.md default `"0 2 1 * *"` in cron syntax. RetrainScheduler is `BackgroundScheduler(timezone="UTC")`. Confirm: cron expression interpreted as UTC (NOT Europe/Rome), to decouple from DST shifts. Document in .env.example: `# CRON in UTC — 1° giorno mese 02:00 UTC = 03:00 CET / 04:00 CEST`.

5. **`get_failure_clusters(top_n)` default for top_n** — CONTEXT.md MCP-07 response schema lists clusters array; plan-phase decides default top_n (suggest 5, capped at all clusters found). Skill `forex-trader-pro` consumer is the primary client.

These are all plan-phase decisions, not research blockers.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `hdbscan` (contrib) | Area A failure clustering | ✗ (not in Codespace; expected on Windows PC via Phase 7/8 install) | — | NONE — Phase 9 blocked without it; pip install required Wave 0 |
| `scipy` | Area B drift KS | ✗ (transitively via sklearn) | — | NONE — sklearn (Phase 7 dep) brings scipy |
| `scikit-learn>=1.8` | Area B drift ECE + Phase 7 carry | ✗ (Phase 7 dep, not installed in Codespace) | — | NONE — Phase 7 install required |
| `apscheduler~=3.11` | Area C cron | ✗ Codespace; available in requirements.txt | — | None — already pinned |
| `sqlite3` (stdlib) | drift_log.db + validation_log.db | ✓ | Python 3.12 builtin | — |
| `joblib` | cluster + ml artifact persistence | ✗ Codespace; via Phase 7 sklearn transitive | — | None |
| `pyarrow` | parquet read | ✓ | already pinned | — |
| `lightgbm` | Phase 7 dep used in retrain validation gate | ✗ Codespace; Phase 7 install required | — | Phase 7 install |

**Missing dependencies with no fallback:** `hdbscan`, `scipy`, `sklearn`, `joblib`, `lightgbm` — all expected on Windows PC where Phase 7/8/9 executes. Codespace Linux is research-only env for this phase.

**requirements.txt addition required (Wave 0):**
```
hdbscan>=0.8.40,<0.9.0   # DO NOT switch to sklearn.cluster.HDBSCAN — lacks approximate_predict
```

---

## Security Domain

`security_enforcement` not explicitly set in `.planning/config.json` — treat as ENABLED.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | MCP stdio channel inside trusted boundary (CLAUDE Code subprocess); no remote auth |
| V3 Session Management | no | No sessions |
| V4 Access Control | partial | EXECUTION_MODE=shadow gate enforced by handler pattern (Phase 6 carry); MCP-18 read-only by design |
| V5 Input Validation | yes | JSON-Schema on every MCP tool input (Phase 6 D-F1); enum locks (Phase 8 D-08-B2 path-traversal guard); window_days/top_n bounded integer |
| V6 Cryptography | yes | sha256 audit anchoring (Phase 8 D-08-B3 + D-09-B2 reference_hash). No new crypto — stdlib `hashlib`. Never hand-roll |
| V11 Business Logic | yes | Validation gate D-09-C2 = business-logic protection against silently-worse-model |

### Known Threat Patterns for Phase 9 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Validation gate bypass via malformed metadata.json | Tampering | strict schema validation (raise FileNotFoundError + schema check) Phase 7 D-07-05-D pattern |
| Retrain DoS via repeated trigger | DoS | dedup D-09-C3 + JobQueue cap=1 condivisa |
| Path traversal via `ML_MODEL_PATH` env | Tampering | `Path.resolve().is_relative_to(Path("models").resolve())` guard (Phase 8 T-8-04-04 pattern) |
| Silently corrupt drift_log.db | Tampering | WAL mode + parameterized SQL (no string concat); reference_hash in every row |
| HDBSCAN deserialization arbitrary code via joblib | Tampering | joblib uses pickle — UNTRUSTED bundles MUST NOT be loaded. Document in `cluster/artifact.py`: bundles loaded only from `models/` path validated relative-to. Same as Phase 7 D-07-05-A. |
| OOD prediction misinterpretation → wrong position action | Information disclosure | `ood_caveat: true` always surfaced; relative-only signal classification (signal enum, not absolute prob) |
| MCP-18 response includes `position_id` in error envelope (PII?) | Information disclosure | position_id is broker ticket — non-PII per CLAUDE.md trust boundary |

---

## Sources

### Primary (HIGH confidence)
- `.planning/phases/09-failure-analysis-drift/09-CONTEXT.md` — 16 LOCKED decisions D-09-A1..D4 (scope contract)
- `.planning/phases/09-failure-analysis-drift/09-DISCUSSION-LOG.md` — rationale chain trace
- `.planning/REQUIREMENTS.md` lines 70-72, 83-84, 94 — ML-07/08/09, MCP-07/08/18, INT-03
- `.planning/ROADMAP.md` Phase 9 section lines 273-287 — Goal + 4 Success Criteria
- `.planning/phases/07-ml-classifier/07-CONTEXT.md` — D-01..D-20 LOCKED carry-forward
- `.planning/phases/07-ml-classifier/07-01-PLAN.md` — `ml/feature_extraction.build_feature_vector` interface
- `.planning/phases/07-ml-classifier/07-05-PLAN.md` lines 22-72 — D-07-05-A..G LOCKED (MLFilter singleton, artifact, latency, schema validation, hot-reload, final retrain)
- `.planning/phases/07-ml-classifier/07-06-PLAN.md` — strategy + risk_engine ML gate + ENABLE_ML_FILTER + init_ml_inference_logger
- `.planning/phases/08-mcp-tools-part-2/08-CONTEXT.md` — D-08-A1..D5 LOCKED carry-forward
- `.planning/phases/08-mcp-tools-part-2/08-04-PLAN.md` lines 17-66 — `_train_ml_filter_worker` top-level picklable + sha256 strict-fail + path-traversal mitigation
- `.planning/phases/06-mcp-tools-part-1/06-03-PLAN.md` — JobQueue ProcessPoolExecutor cap=1 + handler signature
- `.planning/phases/06-mcp-tools-part-1/06-04-PLAN.md` — handle_modify_position + handle_get_position_state + trail_daemon analog scheduler hook
- `mcp_tools/job_queue.py` — JobQueue actual implementation (cap=1 + WAL + DB fallback)
- `mcp_tools/handlers/backtest.py:309-465` — handle_run_backtest async pattern (analog Phase 9 retrain handler)
- `mcp_tools/handlers/position.py:258-318` — handle_get_position_state (Phase 9 MCP-18 consumer)
- `mcp_tools/trail_daemon.py:34-100` — ensure_table + WAL + idempotent DDL pattern
- `mcp_tools/errors.py` — ErrorCodes + envelope re-export
- `logger.py:14-90` — _TRADES_LOG_SCHEMA + init_logger + log_trade_decision (analog drift_log + validation_log writer)
- `scheduler.py:293-313` — APScheduler BlockingScheduler + CronTrigger pattern (process owner; Phase 9 RetrainScheduler uses BackgroundScheduler separate instance)
- `config.py:60-200` — Config class .env-driven loader pattern
- `/home/vscode/.claude/projects/-workspaces-trading-agent/memory/project_training_data_integrity_priority.md` — project memory hard rule

### Secondary (HIGH-MEDIUM confidence — verified against official docs)
- scipy.stats.ks_2samp official docs (latest v1.17): https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html — KS-test API, method=auto/exact/asymp, deterministic return
- sklearn.calibration.calibration_curve docs (1.8): https://scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html — n_bins, strategy='uniform', drop-empty-bins behavior
- sklearn.cluster.HDBSCAN docs (1.8): https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html — confirms NO approximate_predict / NO prediction_data attribute (load-bearing for D-09-A4 Wave 2 add-on)
- hdbscan readthedocs prediction_tutorial.html: https://hdbscan.readthedocs.io/en/latest/prediction_tutorial.html — `prediction_data=True` required at fit OR `generate_prediction_data()` post-fit
- hdbscan PyPI: https://pypi.org/project/hdbscan/ — latest stable 0.8.42 (March 2026), active maintenance
- scikit-learn issue #27829: sklearn HDBSCAN vs contrib hdbscan differences (min_samples semantics, cluster_selection_epsilon results differ)
- APScheduler 3.11 user guide: https://apscheduler.readthedocs.io/en/3.x/userguide.html — BlockingScheduler vs BackgroundScheduler; shared persistent jobstore = race
- APScheduler 3.11 FAQ: https://apscheduler.readthedocs.io/en/3.x/faq.html — misfire_grace_time, replace_existing, MemoryJobStore default
- Python 3.12 os module docs (os.replace): atomicwrites issue #25 https://github.com/untitaker/python-atomicwrites/issues/25 — os.replace uses MoveFileEx(REPLACE_EXISTING) on Windows, atomic
- rapidsai/cuml issue #4986: HDBScan joblib/pickle persistence pitfall (prediction_data corruption on restart)

### Tertiary (informational — not load-bearing claims)
- Bart Broere blog "Sneakily giving HDBSCAN a predict method" (2024): https://bartbroere.eu/2024/05/27/sneakily-giving-hdbscan-a-predict-method/ — confirms hdbscan-contrib API surface

## Metadata

**Confidence breakdown:**
- Library + Dependency Recommendations: HIGH — every package verified against official docs + pypi current versions
- Implementation Patterns: HIGH — every skeleton lifts directly from Phase 6/7/8 verified analogs (cited line numbers)
- Cross-Phase Reuse Map: HIGH — every reuse path traced to specific Plan.md + line number
- Validation Architecture: HIGH — built from Phase 7 VALIDATION.md pattern + Phase 9 CONTEXT.md test_hooks section
- Pitfalls + Gotchas: HIGH for P1-P6, P8-P11 (sourced from official docs); HIGH for P7, P9 (designed-failure-mode from Phase 7 carry); MEDIUM for P12-P15 (informed by Phase 7/8 patterns)
- Open Questions: HIGH — all resolved within research; plan-phase has clear next-step inputs

**Research date:** 2026-05-12
**Valid until:** 2026-06-11 (30 days — library versions stable, no breaking releases expected in hdbscan 0.8.x line or scipy 1.x line)

## RESEARCH COMPLETE
