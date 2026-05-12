# Phase 9: Failure Analysis + Drift — Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 37 (4 packages × ~4 modules + 4 handlers + 2 server-ext + 1 CLI + 1 report-writer + 2 schema-migrations + ~12 test files + Wave 0 scaffolding)
**Analogs found:** 35 / 37 (2 "no-analog" Wave 0 deltas: `cluster/match.py` approximate_predict wrapper + `retrain/promotion.py` os.replace pair invalidator — both novel patterns Phase 9 introduces)

> Verifies & extends RESEARCH.md § "Implementation Patterns" + § "Cross-Phase Reuse Map" with actual codebase reads. Phase 7/8 modules (`ml/*`, `mcp_tools/handlers/ml.py`) are not yet on disk — they live in Phase 7 PATTERNS.md / Phase 8 PATTERNS.md as planned analogs; Phase 9 plans cite them as **planned-analog** (downstream waves must consume them as soon as Phase 7/8 execute lands code on disk).

---

## File Classification

### Area A — Failure clustering (`cluster/` package, ~600 LOC + ~350 LOC tests)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `cluster/__init__.py` | package barrel | re-export | `mcp_tools/__init__.py:1-8` + `backtest/baseline/__init__.py:1-2` | exact |
| `cluster/preprocessing.py` (~150 LOC) | pure-fn / transform | parquet read → row→inputs → build_feature_vector batch → ndarray | Phase 7 PATTERNS.md `ml/feature_extraction.py::build_feature_vector` (single-row builder) | role-match (batched extension) |
| `cluster/hdbscan_runner.py` (~200 LOC) | service / pure-fn | ndarray → HDBSCAN.fit → labels + probs + condensed_tree_ → exemplars + summary | RESEARCH § Area A skeleton (lines 96-186); no exact in-repo analog (new dep `hdbscan`) | partial (algorithm-new) |
| `cluster/artifact.py` (~100 LOC) | serialization (joblib + sidecar) | bundle dict → `.pkl` + `.metadata.json` sidecar | Phase 7 PATTERNS.md `ml/artifact.py::dump_bundle` (joblib+sidecar) | exact (mirror pattern) |
| `cluster/match.py` (~50 LOC, Wave 2) | pure-fn / inference wrapper | new sample feature_vec → `hdbscan.approximate_predict(clusterer, X)` → (label, strength) | RESEARCH § Pitfall 1 (P1 prediction_data=True) | no exact analog — Wave 2 novel |

### Area B — Drift monitor (`drift/` package, ~600 LOC + ~450 LOC tests)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `drift/__init__.py` | package barrel | re-export | `backtest/baseline/__init__.py:1-2` | exact |
| `drift/reference.py` (~100 LOC) | service / loader | `models/classifier_v{N}.metadata.json` JSON.load + parquet sha256 verify | Phase 7 PATTERNS.md `ml/artifact.py::load_bundle` (planned) + `backtest/baseline/determinism.py::file_sha256` (actual on disk) | role-match |
| `drift/compute.py` (~250 LOC) | pure-fn / transform | reference + current arrays → ks_2samp / calibration_curve / per-feature KS top-K | RESEARCH § Area B skeleton (lines 197-282); no existing scipy/sklearn caller in-repo | partial (new dep usage but stdlib pattern) |
| `drift/log_db.py` (~150 LOC) | db writer (SQLite WAL idempotent) | metric rows → INSERT INTO drift_log | `mcp_tools/trail_daemon.py::ensure_table` lines 34-46 + 76-84 + `logger.py:_TRADES_LOG_SCHEMA` lines 14-28 | **exact** (WAL + CREATE TABLE IF NOT EXISTS + idempotent CREATE INDEX) |
| `drift/alarm.py` (~80 LOC) | pure-fn / decision | metrics dict → breached: bool per metric → global ANY-breach + sources aggregation | `risk_engine.py::evaluate_trade` rule-aggregation pattern (planned read-only check) | role-match (threshold logic) |
| `drift/report_writer.py` (~150 LOC, INT-03 partner) | service / markdown writer | drift_log rows → markdown lines → `.planning/research/drift-report-{date}.md` | `backtest/baseline/report_writer.py::write_baseline_report` lines 80-176 | **exact** (mirror header+table+per-section+appendix structure) |

### Area C — Retrain trigger workflow (`retrain/` package, ~400 LOC + ~430 LOC tests)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `retrain/__init__.py` | package barrel | re-export | `mcp_tools/__init__.py:1-8` | exact |
| `retrain/scheduler.py` (~80 LOC) | scheduler hook (APScheduler BackgroundScheduler) | CronTrigger.from_crontab → `_fire_scheduled_retrain` → dedup → JobQueue.submit | `scheduler.py:293-313` (`build_scheduler` BlockingScheduler + CronTrigger + max_instances/coalesce/replace_existing/misfire_grace_time) | role-match (BackgroundScheduler vs BlockingScheduler, MemoryJobStore mandatory per P4) |
| `retrain/dedup.py` (~50 LOC) | pure-fn / decision | JobQueue state read → in-flight check → `already_pending` envelope OR enqueue | `mcp_tools/job_queue.py:97-122` (JobQueue.submit cap check + `run_in_progress` envelope) | **exact** (mirror cap-check pattern, return shape adapted) |
| `retrain/validation_gate.py` (~200 LOC) | service / orchestrator | candidate bundle + reference bundle → 3 checks (ECE / KS / expectancy) → validation_log.db row | `drift/log_db.py` (sibling, WAL writer) + Phase 7 PATTERNS.md `ml/artifact.py::load_bundle` (planned) | partial (composition of new checks) |
| `retrain/promotion.py` (~80 LOC) | pure-fn / state mutator | os.replace metadata.json FIRST + .pkl SECOND + invalidate singleton | RESEARCH § Pitfall P6+P7+P8 (lines 785-799); no in-repo Windows-atomic precedent | **no exact analog** (Phase 9 novel pattern — Wave 0 introduces `ml/inference._invalidate_singleton()`) |

### Area D — suggest_position_action (`position_action/` package, ~480 LOC + ~280 LOC tests)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `position_action/__init__.py` | package barrel | re-export | `mcp_tools/__init__.py:1-8` | exact |
| `position_action/rules.py` (~280 LOC) | pure-fn / decision | position state → 4 rule families → rule_outcome dict | `risk_engine.py::evaluate_trade` (rule-based primary, profile-aware lookup via cfg) | role-match (4-rule families new) |
| `position_action/ml_recheck.py` (~80 LOC) | service / ML wrapper | state → cached prob_at_entry OR recompute → MLFilter.predict NOW → signal classification | Phase 7 PATTERNS.md `ml/inference.py::MLFilter.predict` (singleton, planned) + Phase 8 PATTERNS.md `handle_predict_trade_quality` (planned, lines 209-258) | role-match (mid-trade OOD variant) |
| `position_action/orchestrator.py` (~120 LOC) | service / orchestrator | state + rule_outcome + ml_check → hybrid combine → structured rationale + summary_it | RESEARCH § Area D skeleton (lines 476-553) + `mcp_tools/handlers/position.py::handle_get_position_state` lines 258-318 (response-dict shape) | role-match |

### MCP handlers (`mcp_tools/handlers/*`, ~600 LOC + ~300 LOC tests)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `mcp_tools/handlers/cluster.py` (~150 LOC) | controller | args → load cluster bundle → top_n summary → dict response | `mcp_tools/handlers/backtest.py:309-336` `handle_run_backtest` (Tool definition + handler signature) | role-match (sync read-only vs async submit) |
| `mcp_tools/handlers/drift.py` (~150 LOC) | controller | args → drift/compute → drift/log_db append → response | `mcp_tools/handlers/backtest.py:309-336` + `mcp_tools/handlers/account.py:14-17` (sync read-only) | role-match |
| `mcp_tools/handlers/retrain.py` (~120 LOC) | controller (thin wrapper) | args → retrain/dedup.enqueue_or_dedup → JobQueue.submit Phase 8 worker | `mcp_tools/handlers/backtest.py:309-336` `handle_run_backtest` + Phase 8 PATTERNS.md `handle_train_ml_filter` (planned, lines 172-207) | **exact** (zero-duplication: same submit pattern, swap worker fn) |
| `mcp_tools/handlers/position_action.py` (~150 LOC) | controller | args → handle_get_position_state → orchestrator → rationale dict | `mcp_tools/handlers/position.py:258-318` `handle_get_position_state` (read-only response-dict) | **exact** (same handler signature + DRY_RUN-free since read-only) |

### Server + schemas (~80 LOC, modifications to existing files)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `mcp_tools/server.py` (extension ~40 LOC) | router / dispatch | list_tools append 4 Tool + call_tool dispatch bucket | `mcp_tools/server.py:53-62 + 285-289 + 348-375` (backtest bucket self-pattern) | **exact** (self-extension) |
| `mcp_tools/schemas.py` (extension ~40 LOC) | config / JSON-Schema | 4 new schemas | `mcp_tools/schemas.py:73-99` (MODIFY_POSITION_SCHEMA pattern) | **exact** (verbatim shape) |

### CLI + report writer (~350 LOC + ~100 LOC tests)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/show_drift.py` (~200 LOC) | CLI / batch orchestrator | argparse → drift/compute → report_writer → `.planning/research/drift-report-{date}.md` + exit code | `scripts/run_baseline_05_09.py:1-117` (argparse + smoke + exit codes 0/1/2/3/4) | **exact** (CLI structure + exit-code semantics) |
| `drift/report_writer.py` (~150 LOC) — see Area B above | service | drift_log rows → markdown | `backtest/baseline/report_writer.py` lines 80-176 | exact |

### Schema migrations + config (~60 LOC, modifications)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `logger.py` extension (~30 LOC) | migration (idempotent ALTER TABLE) + writer wire | trade_decision → trades_log.ml_calibrated_prob column | `mcp_tools/job_queue.py:60-72` `_ensure_error_column` (`PRAGMA table_info` + ALTER ADD COLUMN if missing) | **exact** |
| `config.py` extension (~30 LOC) | config / env-var declarations | os.getenv → typed class attr | `config.py:60-120` (Config class + `_get_bool`/`_get_int` helpers + `os.getenv` per attribute) | **exact** (mirror pattern) |
| `.env.example` extension | config mirror | declarative env-var listing | (existing `.env.example` style, lines variable) | exact |

### Test suite (~1500 LOC, NEW files)

| New Test File | Role | Closest Analog | Match Quality |
|---------------|------|----------------|---------------|
| `tests/test_cluster_hdbscan.py` (~250 LOC) | unit + integration (HDBSCAN fit/persist round-trip) | `tests/test_baseline_dataset_writer.py` (tmp_path + pyarrow) | role-match |
| `tests/test_cluster_artifact.py` (~80 LOC) | unit (joblib persist + load + approximate_predict round-trip) | Phase 7 planned `tests/test_ml_artifact.py` | partial |
| `tests/test_drift_compute.py` (~250 LOC) | unit (KS/ECE/feature-drift determinism) | `tests/test_indicators_volatility.py` (numpy seed + assert tolerance) | role-match |
| `tests/test_drift_log_db.py` (~100 LOC) | unit (SQLite WAL + idempotent CREATE) | `tests/test_mcp_trail_daemon.py:14-42` (`ensure_table` idempotency + PRAGMA WAL check) | **exact** |
| `tests/test_drift_alarm.py` (~80 LOC) | unit (3-tier breach threshold) | `tests/test_risk.py` (rule-based isolated test) | role-match |
| `tests/test_drift_e2e.py` (~120 LOC) | integration (synthetic shift → forced breach) | `tests/test_baseline_runner.py` (E2E smoke) | role-match |
| `tests/test_retrain_dedup.py` (~80 LOC) | unit (3 concurrent triggers → 1 job + 2 already_pending) | `tests/test_mcp_handlers_backtest.py:69-87 + concurrency_cap` (D-A4 cap=1) | **exact** |
| `tests/test_retrain_scheduler.py` (~80 LOC) | unit (APScheduler config + restart safety) | `tests/test_scheduler.py` (scheduler builder + cron) | role-match |
| `tests/test_retrain_validation_gate.py` (~200 LOC) | integration (ECE + KS + expectancy → reject path) | Phase 7 planned `tests/test_ml_train.py` | partial |
| `tests/test_retrain_promotion.py` (~80 LOC) | integration (os.replace pair + singleton invalidation) | RESEARCH P6/P7/P8 tests (no in-repo) | no analog |
| `tests/test_position_action_rules.py` (~120 LOC) | unit (4-rule isolation per profile) | `tests/test_risk.py` (rule isolation) | role-match |
| `tests/test_position_action_ml_recheck.py` (~80 LOC) | unit (OOD caveat + cache lookup + fallback recompute) | Phase 8 planned `tests/test_mcp_handlers_ml.py` predict-trade-quality | role-match |
| `tests/test_position_action_orchestrator.py` (~80 LOC) | unit (hybrid + summary_it Italian markers) | `tests/test_mcp_handlers_position.py:54-80` (handler dict-response assert) | role-match |
| `tests/test_mcp_handlers_cluster_drift_retrain_position.py` (~200 LOC) | unit (4 handler response-shape) | `tests/test_mcp_handlers_backtest.py:1-66` (fixture + handler invoke + envelope assert) | **exact** |
| `tests/test_show_drift_cli.py` (~100 LOC) | integration (CLI round-trip + exit codes) | (no current CLI test; pattern bootstrap via subprocess.run + tmp_path) | partial |
| `tests/test_logger_ml_calibrated_prob_migration.py` (~40 LOC) | unit (ALTER COLUMN idempotent) | `tests/test_mcp_job_queue.py` `test_ensure_error_column_idempotent` | exact |

---

## Pattern Assignments

### Area A — Failure clustering

#### `cluster/__init__.py` (package barrel)

**Analog:** `mcp_tools/__init__.py` (in-repo)
```python
# mcp_tools/__init__.py:1-8 (verbatim style)
"""mcp_tools package — Phase 6 D-E1 split MCP server into handler modules."""
```

**Copy to `cluster/__init__.py`:**
```python
"""cluster package — Phase 9 Area A failure-mode HDBSCAN clustering.

Esporta API pubblica per:
- preprocessing: build_feature_matrix (riusa Phase 7 build_feature_vector)
- hdbscan_runner: fit_clusters, summarize_clusters, cluster_quality
- artifact: dump_cluster_bundle, load_cluster_bundle
- match: approximate_predict_wrapper (Wave 2 add-on)
"""
from cluster.hdbscan_runner import fit_clusters, summarize_clusters, cluster_quality  # noqa: F401
from cluster.preprocessing import build_feature_matrix  # noqa: F401
from cluster.artifact import dump_cluster_bundle, load_cluster_bundle  # noqa: F401
__all__ = [
    "build_feature_matrix", "fit_clusters", "summarize_clusters",
    "cluster_quality", "dump_cluster_bundle", "load_cluster_bundle",
]
```

#### `cluster/preprocessing.py` (~150 LOC, pure-fn batch transform)

**Analog (planned):** Phase 7 PATTERNS.md `ml/feature_extraction.py::build_feature_vector` (single-row builder; lines 83-156 of `07-PATTERNS.md`).
**Analog (on-disk now):** `backtest/baseline/dataset_writer.py` (Phase 5 parquet writer + `_SCHEMA_V2_REQUIRED_KEYS`).

**Skeleton (mirror RESEARCH § Area A lines 117-135):**
```python
from __future__ import annotations
import pandas as pd, numpy as np
from ml.feature_extraction import build_feature_vector  # Phase 7 planned

def build_feature_matrix(
    losing_trades_df: pd.DataFrame,
    feature_list: list[str],
    cat_encodings: dict[str, dict],
) -> tuple[np.ndarray, list[int]]:
    """Batch wrapper su Phase 7 build_feature_vector (D-09-A4 reuse totale).

    Filtro upstream: caller passa solo y=0 (D-09-A2 losing trades).
    Ritorna (X[N×D] float32, trade_ids alignment list).
    """
    rows, trade_ids = [], []
    for _, row in losing_trades_df.iterrows():
        draft, indicators, ctx = _row_to_phase7_inputs(row)  # decode parquet → Phase 7 inputs
        fv = build_feature_vector(draft, indicators, ctx, feature_list, cat_encodings)
        rows.append(fv.values[0])  # single-row DF → 1D
        trade_ids.append(int(row["trade_id"]))
    return np.asarray(rows, dtype=np.float32), trade_ids
```

**Deviation Phase 9 introduces:** batch loop over Phase 7 single-row builder. Categorical encoding map `cat_encodings` MUST come from `models/classifier_v{N}.metadata.json` (Phase 7 D-15) to maintain audit consistency (Phase 7 PATTERNS.md Pitfall 2 line 1107).

#### `cluster/hdbscan_runner.py` (~200 LOC)

**Analog:** RESEARCH § Area A skeleton lines 138-186 (no in-repo precedent for HDBSCAN — new dep `hdbscan>=0.8.40,<0.9.0`).

**Core fit pattern (verbatim from RESEARCH P1+P2 guards):**
```python
from hdbscan import HDBSCAN  # NOT sklearn.cluster.HDBSCAN — P2 guard

def fit_clusters(X: np.ndarray, cfg) -> HDBSCAN:
    clusterer = HDBSCAN(
        min_cluster_size=cfg.HDBSCAN_MIN_CLUSTER_SIZE,        # default 20 .env
        min_samples=cfg.HDBSCAN_MIN_SAMPLES,                  # default None
        cluster_selection_method=cfg.HDBSCAN_CLUSTER_SELECTION_METHOD,  # 'eom'
        prediction_data=True,                                  # P1 MANDATORY
        core_dist_n_jobs=1,                                    # determinism
    )
    clusterer.fit(X)
    return clusterer
```

**Cluster quality validation (D-09-A3 quality gate):**
```python
from sklearn.metrics import davies_bouldin_score, silhouette_score

def cluster_quality(X: np.ndarray, labels: np.ndarray) -> dict:
    mask = labels != -1  # exclude noise
    if mask.sum() < 10 or len(set(labels[mask])) < 2:
        return {"davies_bouldin": float("nan"), "silhouette": float("nan"), "quality": "insufficient"}
    db = davies_bouldin_score(X[mask], labels[mask])
    sil = silhouette_score(X[mask], labels[mask])
    quality = "good" if db < 1.5 and sil > 0.3 else ("acceptable" if db < 2.0 else "poor")
    return {"davies_bouldin": float(db), "silhouette": float(sil), "quality": quality}
```

**Deviation Phase 9 introduces:** explicit `prediction_data=True` (P1) + `core_dist_n_jobs=1` (determinism contract RESEARCH lines 700-702) + contrib-package pin (`hdbscan` not `sklearn.cluster.HDBSCAN`, RESEARCH P2).

#### `cluster/artifact.py` (~100 LOC, mirror joblib + sidecar)

**Analog (planned):** Phase 7 PATTERNS.md `ml/artifact.py::dump_bundle` (line 552-624 of `07-PATTERNS.md`).
**Analog (on-disk now):** `mcp_tools/trail_daemon.py::ensure_table` for the WAL-DDL idempotent pattern.

**Skeleton:**
```python
import joblib, json
from datetime import datetime, timezone
from pathlib import Path

def dump_cluster_bundle(
    clusterer, trade_ids, summaries, dataset_hash: str, out_path: Path,
) -> None:
    """Mirror Phase 7 ml/artifact.dump_bundle: joblib .pkl + .metadata.json sidecar."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {"clusterer": clusterer, "trade_ids": trade_ids, "summaries": summaries}
    joblib.dump(bundle, out_path)
    meta = {
        "model_version": "cluster_v1",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "dataset_hash": dataset_hash,           # sha256 baseline parquet (D-09-B2 anchor)
        "n_losing_trades_total": len(trade_ids),
        "n_clusters": len(summaries),
        "n_noise": sum(1 for l in clusterer.labels_ if l == -1),
        "quality_metrics": cluster_quality(...),
    }
    out_path.with_suffix(".metadata.json").write_text(json.dumps(meta, indent=2))
```

**Deviation:** `prediction_data=True` flag on the clusterer is preserved through joblib (verified hdbscan FAQ docs); test assertion `clusterer.prediction_data_ is not None` post `joblib.load` (P1 test guard).

#### `cluster/match.py` (~50 LOC, Wave 2 add-on)

**Analog:** RESEARCH § Area A § skeleton fragment + `hdbscan` API docs (`approximate_predict`).

**Skeleton (Wave 2 deferred — DO NOT plan in Wave 1):**
```python
from hdbscan import approximate_predict

def predict_cluster_membership(clusterer, X_new: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Wave 2 add-on (~50 LOC): new sample → (label, strength).

    Requires P1 guard: clusterer.prediction_data_ != None.
    """
    if clusterer.prediction_data_ is None:
        raise RuntimeError("Cluster bundle missing prediction_data — refit with prediction_data=True")
    labels, strengths = approximate_predict(clusterer, X_new)
    return labels, strengths
```

**Deviation:** novel pattern Phase 9 introduces; no analog in repo. Wave 2 only.

---

### Area B — Drift monitor

#### `drift/__init__.py`

Same `backtest/baseline/__init__.py:1-2` pattern (barrel re-export of public surface).

#### `drift/reference.py` (~100 LOC)

**Analog (planned):** Phase 7 PATTERNS.md `ml/artifact.py::load_bundle`.
**Analog (on-disk now):** `backtest/baseline/determinism.py::file_sha256` (sha256 hex of file bytes).

**Skeleton:**
```python
import json, hashlib
from pathlib import Path

def load_reference(model_bundle_path: Path) -> dict:
    """Carica metadata.json sidecar + verifica sha256 baseline parquet.

    D-09-B2: reference = static training distribution.
    Audit-anchored via metadata.dataset_hash == sha256(part-0.parquet).
    """
    meta_path = model_bundle_path.with_suffix(".metadata.json")
    if not meta_path.exists():
        raise FileNotFoundError(f"metadata mancante: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    parquet_path = Path("data/training/baseline_decisions/part-0.parquet")
    actual_sha = _file_sha256(parquet_path)  # riuso backtest.baseline.determinism.file_sha256
    if actual_sha != meta.get("dataset_hash"):
        raise RuntimeError(
            f"reference baseline parquet drift: expected {meta['dataset_hash'][:12]}... "
            f"got {actual_sha[:12]}..."
        )
    return {"metadata": meta, "parquet_path": str(parquet_path), "sha256": actual_sha}
```

#### `drift/compute.py` (~250 LOC)

**Analog:** RESEARCH § Area B skeleton lines 197-282. No existing scipy/sklearn caller in repo (Phase 7 ECE module is planned).

**Three computes (RESEARCH §Area B lines 216-281):**
```python
from scipy.stats import ks_2samp
from sklearn.calibration import calibration_curve

def compute_prediction_ks(pred_ref, pred_cur) -> dict:
    stat, p = ks_2samp(pred_ref, pred_cur, method="auto")
    return {"ks_stat": float(stat), "ks_pvalue": float(p),
            "n_reference": len(pred_ref), "n_current": len(pred_cur)}

def compute_ece(y_true, y_prob, n_bins: int = 10) -> float:
    """P10 guard: n_bins MUST match Phase 7 training (default 10)."""
    if len(y_true) < n_bins:
        return float("nan")
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="uniform")
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.clip(np.searchsorted(bin_edges, y_prob, side="right") - 1, 0, n_bins - 1)
    bin_counts = np.bincount(bin_idx, minlength=n_bins)
    nonzero = bin_counts > 0
    weights = bin_counts[nonzero] / len(y_true)
    return float(np.sum(np.abs(prob_true - prob_pred) * weights))

def compute_feature_drift_topk(df_ref, df_cur, top_k_features, ks_threshold: float = 0.01):
    """P12 guard upstream: caller filtra feature_importance_ > 0 + esclude categorical."""
    out = []
    for feat in top_k_features:
        if feat not in df_ref.columns or feat not in df_cur.columns:
            continue
        ref = df_ref[feat].dropna().values
        cur = df_cur[feat].dropna().values
        if len(ref) < 10 or len(cur) < 10:
            continue
        stat, p = ks_2samp(ref, cur, method="auto")
        out.append({"feature": feat, "ks_stat": float(stat), "ks_pvalue": float(p),
                    "breached": bool(p < ks_threshold)})
    return out
```

**Deviation:** P12 filter (`feature_importance_ > 0` + drop categorical) applied BEFORE calling `compute_feature_drift_topk`. P10 n_bins read from `.env DRIFT_ECE_N_BINS` (default 10) — Phase 7 metadata.json MUST include `n_bins: 10` for audit invariance (RESEARCH determinism contract line 706).

#### `drift/log_db.py` (~150 LOC)

**Analog (exact, on-disk):** `mcp_tools/trail_daemon.py:34-46 + 76-84` (`_POSITION_TRAILS_DDL` + `ensure_table`).

**Excerpt to mirror verbatim** (trail_daemon.py:34-46):
```python
_POSITION_TRAILS_DDL = """
CREATE TABLE IF NOT EXISTS position_trails (
    position_id    INTEGER PRIMARY KEY,
    ...
)
"""

def ensure_table(db_path: str | Path) -> None:
    with sqlite3.connect(str(db_path)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(_POSITION_TRAILS_DDL)
```

**Copy to `drift/log_db.py`** (CONTEXT.md § specifics drift_log schema verbatim):
```python
import sqlite3
from pathlib import Path

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
_DRIFT_LOG_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_drift_log_ts ON drift_log(ts_utc, model_version, breached)"
)

def ensure_drift_log_db(db_path: str | Path) -> None:
    """Idempotente WAL — pattern verbatim mcp_tools/trail_daemon.ensure_table:82-83."""
    with sqlite3.connect(str(db_path)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(_DRIFT_LOG_DDL)
        c.execute(_DRIFT_LOG_INDEX)

def append_drift_row(db_path, row: dict) -> None:
    """Append-only insert. Riusa pattern logger.log_trade_decision lines 79-97."""
    with sqlite3.connect(str(db_path)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""
            INSERT INTO drift_log (
                ts_utc, model_version, reference_hash, metric_name, metric_value,
                threshold, breached, n_samples_current, n_samples_reference,
                window_days, computed_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["ts_utc"], row["model_version"], row["reference_hash"],
            row["metric_name"], row["metric_value"], row["threshold"],
            int(row["breached"]),
            row.get("n_samples_current"), row.get("n_samples_reference"),
            row.get("window_days"), row.get("computed_by"),
        ))
        c.commit()
```

**Deviation:** P11 WAL mandatory; parameterized SQL (no string concat) per security threat (RESEARCH § Security).

#### `drift/alarm.py` (~80 LOC)

**Analog:** `risk_engine.py::evaluate_trade` (rule-aggregation), but pure-fn threshold check.

**Skeleton:**
```python
def check_alarm(metrics: dict, cfg) -> dict:
    """3-tier alarm (D-09-B3): pred_KS + ECE_delta + feature_fraction breach.

    Global = ANY 1 of 3 breached. Returns {breached: bool, breaches: list[str], sources: list}.
    """
    breaches = []
    if metrics["prediction_drift"]["ks_pvalue"] < cfg.DRIFT_KS_PVALUE_THRESHOLD:
        breaches.append("prediction_ks")
    if metrics["calibration_drift"]["delta_ece"] > cfg.DRIFT_ECE_DELTA_THRESHOLD:
        breaches.append("calibration_ece")
    feature_breached = [f for f in metrics["feature_drift"] if f["breached"]]
    frac = len(feature_breached) / max(1, len(metrics["feature_drift"]))
    if frac >= cfg.DRIFT_FEATURE_FRACTION_THRESHOLD:
        breaches.append("feature_drift")
    return {
        "breached": len(breaches) > 0,
        "breaches": breaches,
        "alarm_status": "breach" if breaches else "ok",
    }
```

#### `drift/report_writer.py` (~150 LOC)

**Analog (exact):** `backtest/baseline/report_writer.py:80-176` (`write_baseline_report` — header + table + per-section + appendix structure).

**Excerpt to mirror (report_writer.py:128-138):**
```python
lines: list[str] = []
lines.append("## Header\n")
lines.append(f"- **Data run**: {datetime.now(timezone.utc).isoformat()}")
lines.append(f"- **Comando CLI**: `{meta.get('cli_command', 'n/a')}`")
lines.append(f"- **git_sha**: `{meta.get('git_sha', 'unknown')}`")
...
out_path.write_text("\n".join(lines), encoding="utf-8")
```

**Copy to `drift/report_writer.py`** with INT-03-specific sections:
1. Header (timestamp, model_version, reference_period, current_period, sources)
2. Prediction-drift KS table
3. Calibration ECE table (current vs reference + delta)
4. Feature-drift top-K table
5. Alarm status + breaches list (italiano `summary_it`)
6. Appendix: `reference_hash`, `n_samples_current/reference`, `.env thresholds` audit

---

### Area C — Retrain trigger workflow

#### `retrain/scheduler.py` (~80 LOC)

**Analog (in-repo):** `scheduler.py:293-313` (`build_scheduler` BlockingScheduler + CronTrigger + add_job with `max_instances=1 / coalesce=True / misfire_grace_time / replace_existing=True`).

**Excerpt scheduler.py:293-313:**
```python
def build_scheduler(cfg: "Config", orchestrator: Orchestrator) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=cfg.OPERATING_TIMEZONE)
    weekday_str = ",".join(str(d) for d in cfg.OPERATING_WEEKDAYS)
    hour_str = ",".join(str(h) for h in operating_slots(cfg))
    trigger = CronTrigger(day_of_week=weekday_str, hour=hour_str, minute=0,
                          timezone=cfg.OPERATING_TIMEZONE)
    scheduler.add_job(
        orchestrator.execute_ordinary_cycle, trigger=trigger,
        id="ordinary_cycle",
        max_instances=1, coalesce=True,
        misfire_grace_time=300, replace_existing=True,
    )
    orchestrator.attach_scheduler(scheduler)
    return scheduler
```

**Copy to `retrain/scheduler.py`** (mirror RESEARCH § Area C lines 315-365):
```python
from apscheduler.schedulers.background import BackgroundScheduler  # P4: BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

class RetrainScheduler:
    def __init__(self, job_queue, cfg, log) -> None:
        # P4: MemoryJobStore implicit default — DO NOT pass jobstore= arg
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._job_queue = job_queue
        self._cfg = cfg
        self._log = log

    def start(self) -> None:
        trigger = CronTrigger.from_crontab(self._cfg.RETRAIN_CRON_SCHEDULE)
        self._scheduler.add_job(
            self._fire_scheduled_retrain, trigger=trigger,
            id="retrain_monthly",
            replace_existing=True,        # P5 restart-safe
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,      # P13 1h grace su agent downtime
        )
        self._scheduler.start()
        self._log.info("RetrainScheduler started — cron=%s", self._cfg.RETRAIN_CRON_SCHEDULE)

    def _fire_scheduled_retrain(self) -> None:
        from retrain.dedup import enqueue_or_dedup
        result = enqueue_or_dedup(self._job_queue, source="scheduled_cron", cfg=self._cfg)
        self._log.info("RetrainScheduler tick — status=%s job_id=%s",
                       result.get("status"), result.get("job_id"))
```

**Deviations Phase 9 introduces:**
- `BackgroundScheduler` instead of `BlockingScheduler` (P4 — coexists with existing scheduler.py:294)
- `timezone="UTC"` hardcoded (not `cfg.OPERATING_TIMEZONE`) — RESEARCH Open Question #4 confirms decouple from DST
- `MemoryJobStore` (no `jobstore=` arg) — P4 race guard vs shared SQLite jobstore
- `misfire_grace_time=3600` explicit (P13)

#### `retrain/dedup.py` (~50 LOC)

**Analog (exact):** `mcp_tools/job_queue.py:97-122` (`JobQueue.submit` cap check + `run_in_progress` envelope).

**Excerpt job_queue.py:97-122:**
```python
def submit(self, run_id, fn, metadata, *args, **kwargs) -> dict:
    with self._lock:
        active = [j for j in self._jobs.values() if j.status == "running"]
        if len(active) >= self._max:
            return {
                "ok": False,
                "error": "run_in_progress",
                "active_run_id": active[0].run_id,
            }
        fut = self._pool.submit(fn, *args, **kwargs)
        ...
```

**Copy to `retrain/dedup.py`** (D-09-C3 idempotent — return `already_pending` shape):
```python
def enqueue_or_dedup(job_queue, source: str, cfg, reason: str = "") -> dict:
    """D-09-C3: 3 trigger sources condividono dedup check vs JobQueue cap=1.

    Riuso JobQueue.submit run_in_progress branch — solo cambio shape ritorno
    in `{ok: true, status: "already_pending"}` (idempotent contract MCP).
    """
    from mcp_tools.handlers.ml import _train_ml_filter_worker, _validate_parquet_schema_v2  # Phase 8 planned
    from logger import _trades_db_path

    parquet_path = Path(cfg.MCP_TRAINING_DATA_PATH)
    ok, msg, parquet_sha = _validate_parquet_schema_v2(parquet_path)
    if not ok:
        return {"ok": False, "error": "validation_failed", "msg": msg}

    run_id = _build_retrain_run_id(source)   # mcp_retrain_{utc_ts}_{source}
    metadata = {
        "source": source,
        "reason": reason,
        "parquet_sha256": parquet_sha,
        "triggered_by_sources": [source],
    }
    result = job_queue.submit(
        run_id, _train_ml_filter_worker, metadata,
        run_id, str(parquet_path), str(cfg.ML_MODEL_PATH.parent),
        "data/configs/ml.yaml", parquet_sha,
    )
    if result.get("error") == "run_in_progress":
        # D-09-C3 idempotent — append source to existing job's sources array
        active_id = result["active_run_id"]
        _append_source_to_active(job_queue, active_id, source)
        return {
            "ok": True, "status": "already_pending",
            "job_id": active_id,
            "triggered_by_sources": _read_sources(job_queue, active_id),
        }
    return {**result, "triggered_by_sources": [source]}
```

**Deviation:** dedup wraps `JobQueue.submit` to convert `run_in_progress` → `already_pending` (idempotent MCP contract). Append `triggered_by_sources` to existing `JobRecord.metadata` per audit completeness (CONTEXT.md D-09-C3).

#### `retrain/validation_gate.py` (~200 LOC)

**Analog:** RESEARCH § Area C lines 367-454 + sibling `drift/compute.py::compute_ece` (Area B) + sibling `drift/log_db.py` writer pattern.

**Core gate (mirror RESEARCH lines 392-436):**
```python
import os, json
from pathlib import Path
from scipy.stats import ks_2samp
from drift.compute import compute_ece
from ml.artifact import load_bundle  # Phase 7 planned

def run_validation_gate(candidate_path, reference_path, held_out_df, cfg) -> dict:
    cand_bundle, cand_meta = load_bundle(candidate_path)
    ref_bundle, ref_meta = load_bundle(reference_path)

    checks = []
    # CHECK 1 — ECE regression vs metadata.aggregate.ece (D-09-C2)
    cand_ece = cand_meta["aggregate"]["ece"]
    ref_ece = ref_meta["aggregate"]["ece"]
    regression_pct = ((cand_ece - ref_ece) / ref_ece) * 100 if ref_ece > 0 else 0
    checks.append({
        "name": "ece_regression", "metric_value": regression_pct,
        "threshold": cfg.MAX_ECE_REGRESSION_PCT,
        "passed": regression_pct <= cfg.MAX_ECE_REGRESSION_PCT,
    })

    # CHECK 2 — KS divergence candidate vs reference predictions
    pred_cand = cand_bundle["model"].predict_proba(held_out_df)[:, 1]
    pred_ref = ref_bundle["model"].predict_proba(held_out_df)[:, 1]
    ks_stat, _ = ks_2samp(pred_ref, pred_cand)
    checks.append({
        "name": "ks_divergence", "metric_value": float(ks_stat),
        "threshold": cfg.KS_CANDIDATE_DIVERGENCE_THRESHOLD,
        "passed": ks_stat <= cfg.KS_CANDIDATE_DIVERGENCE_THRESHOLD,
    })

    # CHECK 3 — threshold-sweep expectancy regression per profile
    # (riuso ml/threshold.py sweep helper Phase 7 Plan 07-04)
    ...

    all_passed = all(c["passed"] for c in checks)
    reject_reason = None if all_passed else f"validation_failed: {[c['name'] for c in checks if not c['passed']]}"
    _append_validation_log_rows(checks, candidate_path, cfg)  # mirror drift/log_db.append_drift_row
    return {"passed": all_passed, "checks": checks, "reject_reason": reject_reason}
```

**validation_log.db schema** (CONTEXT.md § specifics):
```python
_VALIDATION_LOG_DDL = """
CREATE TABLE IF NOT EXISTS validation_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  candidate_path TEXT NOT NULL,
  previous_version TEXT,
  check_name TEXT NOT NULL,
  metric_value REAL NOT NULL,
  threshold REAL NOT NULL,
  passed INTEGER NOT NULL,
  reject_reason TEXT,
  triggered_by_sources_json TEXT
)
"""
# Identical pattern to drift_log.db — WAL + idempotent CREATE + parameterized INSERT.
```

#### `retrain/promotion.py` (~80 LOC)

**Analog:** **NONE on disk** — Phase 9 novel pattern. Closest parallel: Phase 7 PATTERNS.md `ml/artifact.py::dump_bundle` (planned, lines 552-624) for the load-side. Wave 0 Phase 9 MUST add `_invalidate_singleton()` helper to `ml/inference.py` (planned, Phase 7 PATTERNS.md lines 488-500).

**Skeleton (verbatim RESEARCH lines 439-453):**
```python
import os
from pathlib import Path

def atomic_promote(candidate_path: Path, final_path: Path) -> None:
    """os.replace atomico (Windows MoveFileEx + POSIX rename) — P6 + P7.

    Order: metadata.json FIRST, .pkl SECOND. Pair-crash → FeatureSchemaMismatchError
    on next MLFilter.load (P7 designed failure mode).
    """
    cand_meta = candidate_path.with_suffix(".metadata.json")
    final_meta = final_path.with_suffix(".metadata.json")
    os.replace(str(cand_meta), str(final_meta))   # P6 MoveFileEx replace-existing
    os.replace(str(candidate_path), str(final_path))

    # P8 hot-reload MLFilter singleton (Wave 0 Phase 9 add _invalidate_singleton)
    from ml.inference import _invalidate_singleton
    _invalidate_singleton()
```

**Deviation:** novel pattern. Wave 0 task: add to `ml/inference.py` (planned):
```python
def _invalidate_singleton() -> None:
    """Phase 9 D-09-C2 hook: clear _MODEL_CACHE inside the existing module-level Lock."""
    global _MODEL_CACHE
    with _LOCK:
        _MODEL_CACHE = None
```

---

### Area D — suggest_position_action

#### `position_action/rules.py` (~280 LOC)

**Analog:** `risk_engine.py::evaluate_trade` (rule-based decision over cfg-threshold).

**Skeleton:**
```python
def evaluate_rules(state: dict, cfg) -> dict:
    """4 rule families per D-09-D3 con threshold profile-aware da .env."""
    profile = state["profile"].upper()
    r_mult = state["r_multiple"]
    bars = state["bars_in_trade"]

    be_threshold = getattr(cfg, f"BE_R_THRESHOLD_{profile}")
    partial_threshold = getattr(cfg, f"PARTIAL_R_THRESHOLD_{profile}")
    full_threshold = getattr(cfg, f"FULL_R_THRESHOLD_{profile}")
    max_bars = getattr(cfg, f"MAX_HOLD_BARS_{profile}")

    rules_triggered: list[dict] = []
    action = "hold"
    params = {}

    if r_mult >= full_threshold:
        action = "full_close"
        rules_triggered.append({"name": "r_multiple_full", "condition": f"r>={full_threshold}", "value": r_mult})
    elif r_mult >= partial_threshold:
        action = "partial_close"
        params = {"close_fraction": cfg.PARTIAL_CLOSE_FRACTION}
        rules_triggered.append({"name": "r_multiple_partial", "condition": f"r>={partial_threshold}", "value": r_mult})
    elif r_mult >= be_threshold:
        action = "move_sl"
        params = {"method": "to_breakeven", "new_sl_price": state["entry_price"]}
        rules_triggered.append({"name": "r_multiple_to_be", "condition": f"r>={be_threshold}", "value": r_mult})
    elif bars > max_bars and r_mult <= cfg.TIME_STOP_R_THRESHOLD:
        action = "full_close"
        rules_triggered.append({"name": "time_stop", "condition": f"bars>{max_bars} AND r<={cfg.TIME_STOP_R_THRESHOLD}", "value": bars})

    return {"action": action, "params": params, "rules_triggered": rules_triggered}


def modulate_with_ml(rule_outcome: dict, ml_check: dict, cfg) -> tuple[str, dict, float]:
    """D-09-D1 hybrid: ML modula severity. below_threshold → upgrade verso full_close."""
    action = rule_outcome["action"]
    if ml_check.get("signal") == "below_threshold":
        if action in ("hold", "move_sl"):
            action = "full_close"   # ML invalida thesis → close
    confidence = 0.5 + 0.2 * len(rule_outcome["rules_triggered"]) + (0.1 if ml_check.get("signal") == "above_threshold" else 0.0)
    return action, rule_outcome["params"], min(confidence, 1.0)
```

**Deviation:** profile-aware threshold lookup uses `getattr(cfg, f"BE_R_THRESHOLD_{profile}")` dynamic — mirror config.py pattern but per-profile suffix.

#### `position_action/ml_recheck.py` (~80 LOC)

**Analog (planned):** Phase 7 PATTERNS.md `ml/inference.py::MLFilter + get_ml_filter` (lines 488-552 of `07-PATTERNS.md`).
**Analog (planned):** Phase 8 PATTERNS.md `handle_predict_trade_quality` (lines 209-258 of `08-PATTERNS.md`).

**Excerpt to mirror (Phase 8 PATTERNS.md lines 220-232 — ENABLE_ML_FILTER=false fallback):**
```python
if not cfg.ENABLE_ML_FILTER or ml_filter_singleton is None:
    return {
        "ok": True, "ml_score": None,
        "calibrated_prob": None, "threshold_for_profile": None,
        "would_pass_gate": None, "warning": "ml_filter_disabled",
    }
```

**Copy to `position_action/ml_recheck.py`** (RESEARCH § Area D lines 556-608):
```python
def evaluate_ml_thesis(state: dict, pid: int, cfg) -> dict:
    """Mid-trade ML re-eval — OOD per costruzione (P9). Surface ood_caveat sempre."""
    if not cfg.ENABLE_ML_FILTER:
        return {
            "calibrated_prob_at_entry": None, "calibrated_prob_now": None,
            "threshold_profile": None, "signal": "n/a",
            "ood_caveat": False, "ml_filter_disabled": True,
        }

    # D-09-D4: prefer cached da trades_log; fallback recompute
    prob_at_entry = _lookup_cached_prob(pid)   # SELECT ml_calibrated_prob FROM trades_log
    if prob_at_entry is None:
        prob_at_entry = _recompute_prob_at_entry(pid)

    # Compute NOW
    from ml.inference import get_ml_filter
    from ml.feature_extraction import build_feature_vector
    draft_now, ind_now, ctx_now = _build_inputs_now(state)
    fv = build_feature_vector(draft_now, ind_now, ctx_now,
                              _feature_list(), _cat_encodings())
    ml_filter = get_ml_filter(cfg.ML_MODEL_PATH)
    _, prob_now = ml_filter.predict(fv)

    threshold = cfg.ML_THRESHOLD_BY_PROFILE[state["profile"].upper()]

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
        "ood_caveat": True,                # P9 MANDATORY when ML active
        "ml_filter_disabled": False,
    }
```

**Deviation:** `ood_caveat: true` MANDATORY whenever `signal != "n/a"` (P9 + RESEARCH § P9 line 803). Relative-only signal classification (never expose absolute `prob_now` interpretation).

#### `position_action/orchestrator.py` (~120 LOC)

**Analog:** `mcp_tools/handlers/position.py:258-318` `handle_get_position_state` (read-only response-dict shape) + RESEARCH § Area D skeleton lines 476-553.

**Skeleton:**
```python
def handle_suggest_position_action(args: dict, mt5_client, cfg, log) -> dict:
    pid = int(args["position_id"])
    state = handle_get_position_state({"position_id": pid}, mt5_client, cfg)
    if state.get("ok") is False:
        return state

    from position_action.rules import evaluate_rules, modulate_with_ml
    from position_action.ml_recheck import evaluate_ml_thesis

    rule_outcome = evaluate_rules(state, cfg)
    ml_check = evaluate_ml_thesis(state, pid, cfg)
    final_action, final_params, confidence = modulate_with_ml(rule_outcome, ml_check, cfg)

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
```

**`summary_it` Italian markers guard (P15):**
```python
def _format_summary_it(rule_outcome, ml_check, final_action) -> str:
    """CLAUDE.md italiano log. Verbi target: suggerisco|confermata|invalidata|raggiunto|caveat."""
    rules_part = ", ".join(r["name"] for r in rule_outcome["rules_triggered"])
    if ml_check.get("ml_filter_disabled"):
        ml_part = "ML filter disabilitato (solo regole)"
    elif ml_check.get("signal") == "below_threshold":
        ml_part = (f"thesis invalidata (prob {ml_check['calibrated_prob_now']:.2f} < "
                   f"soglia {ml_check['threshold_profile']:.2f})")
    elif ml_check.get("signal") == "above_but_decreasing":
        ml_part = (f"thesis in calo (entry {ml_check['calibrated_prob_at_entry']:.2f} → "
                   f"now {ml_check['calibrated_prob_now']:.2f}) — caveat OOD")
    else:
        ml_part = "thesis confermata ML"
    return f"Azione {final_action}: {rules_part}. {ml_part}."
```

---

### MCP handlers

#### `mcp_tools/handlers/cluster.py` (~150 LOC)

**Analog:** `mcp_tools/handlers/backtest.py:56-76 + 309-336` (Tool registration + handler signature pattern).

**Tool registration excerpt (verbatim style backtest.py:56-76):**
```python
from mcp.types import Tool
from mcp_tools.errors import ErrorCodes, envelope

GET_FAILURE_CLUSTERS_TOOL = Tool(
    name="get_failure_clusters",
    description=(
        "Top-N failure-mode cluster (HDBSCAN su losing trades baseline). "
        "Per ogni cluster: exemplar trade IDs, feature-distribution summary "
        "(median+IQR), avg_pnl_pips, hit_rate, summary_it italiano. "
        "Cluster quality metrics (DB index, silhouette)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "top_n": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
        "required": [],
    },
)

def handle_get_failure_clusters(args: dict, cfg) -> dict:
    """MCP-07 read-only — carica artifact cluster + ritorna top_n summary."""
    top_n = int(args.get("top_n", 5))
    bundle_path = Path(cfg.CLUSTER_ARTIFACT_PATH)
    if not bundle_path.exists():
        return envelope(ErrorCodes.NOT_FOUND, f"cluster artifact mancante: {bundle_path}")
    bundle = load_cluster_bundle(bundle_path)
    summaries = bundle["summaries"][:top_n]
    return {
        "model_version": bundle["metadata"]["model_version"],
        "computed_at": bundle["metadata"]["computed_at"],
        "n_losing_trades_total": bundle["metadata"]["n_losing_trades_total"],
        "n_noise_points": bundle["metadata"]["n_noise"],
        "clusters": summaries,
        "quality_metrics": bundle["metadata"]["quality_metrics"],
    }
```

#### `mcp_tools/handlers/drift.py` (~150 LOC)

**Analog:** `mcp_tools/handlers/backtest.py:79-96 + 389-456` (`GET_BACKTEST_METRICS_TOOL` + `handle_get_backtest_metrics` polymorphic response).

**Handler signature mirrors handle_get_backtest_metrics + polymorphic response shape:**
```python
GET_DRIFT_METRICS_TOOL = Tool(name="get_drift_metrics", ...)

def handle_get_drift_metrics(args: dict, cfg, drift_log_db_path: str) -> dict:
    """MCP-08 — compute drift current-window + persist + return polymorphic."""
    window_days = int(args.get("window_days", cfg.DRIFT_DEFAULT_WINDOW_DAYS))
    from drift.reference import load_reference
    from drift.compute import compute_prediction_ks, compute_ece, compute_feature_drift_topk
    from drift.alarm import check_alarm
    from drift.log_db import append_drift_row, ensure_drift_log_db

    ensure_drift_log_db(drift_log_db_path)
    ref = load_reference(Path(cfg.ML_MODEL_PATH))
    pred_cur, y_cur, df_cur = _load_current_window(window_days, cfg)   # ml_inference.log + trades.db join
    pred_ref, y_ref, df_ref = _load_reference_window(ref)

    metrics = {
        "window_days": window_days,
        "model_version": ref["metadata"]["model_version"],
        "reference_hash": ref["sha256"],
        "prediction_drift": compute_prediction_ks(pred_ref, pred_cur),
        "calibration_drift": {
            "current_ece": compute_ece(y_cur, pred_cur, cfg.DRIFT_ECE_N_BINS),
            "reference_ece": ref["metadata"]["aggregate"]["ece"],
            "delta_ece": ...,
            "threshold": cfg.DRIFT_ECE_DELTA_THRESHOLD,
            "breached": ...,
        },
        "feature_drift": compute_feature_drift_topk(df_ref, df_cur, _topk_features(ref), cfg.DRIFT_KS_PVALUE_THRESHOLD),
    }
    metrics.update(check_alarm(metrics, cfg))

    # Persist every metric as a row (audit)
    for m in _flatten_to_rows(metrics, computed_by="mcp_get_drift_metrics"):
        append_drift_row(drift_log_db_path, m)
    return metrics
```

#### `mcp_tools/handlers/retrain.py` (~120 LOC)

**Analog (exact):** `mcp_tools/handlers/backtest.py:309-336` (`handle_run_backtest` async submit + Phase 8 PATTERNS.md `handle_train_ml_filter` lines 172-207).

**Excerpt to mirror (Phase 8 PATTERNS.md lines 174-207):**
```python
def handle_train_ml_filter(args: dict, job_queue, cfg) -> dict:
    parquet_path = Path(cfg.MCP_TRAINING_DATA_PATH)
    ok, msg, parquet_sha = _validate_parquet_schema_v2(parquet_path)
    if not ok:
        return envelope(ErrorCodes.VALIDATION_FAILED, msg)
    run_id = _build_ml_run_id()
    metadata = {"data_source": "baseline", "parquet_sha256": parquet_sha}
    return job_queue.submit(
        run_id, _train_ml_filter_worker, metadata,
        run_id, str(parquet_path), str(cfg.ML_MODEL_PATH.parent),
        "data/configs/ml.yaml", parquet_sha,
    )
```

**Copy to `mcp_tools/handlers/retrain.py`** (D-09-C1 zero-duplication thin wrapper):
```python
TRIGGER_RETRAIN_TOOL = Tool(name="trigger_retrain", ...)

def handle_trigger_retrain(args: dict, job_queue, cfg, log) -> dict:
    """MCP-09 D-09-C1 — thin wrapper su retrain.dedup.enqueue_or_dedup.

    Zero new logic. Stesso worker Phase 8 (_train_ml_filter_worker).
    Idempotent dedup (D-09-C3) → multiple calls → stesso job + sources array.
    """
    from retrain.dedup import enqueue_or_dedup
    return enqueue_or_dedup(
        job_queue, source="manual_mcp",
        reason=args.get("reason", "manual"),
        cfg=cfg,
    )
```

#### `mcp_tools/handlers/position_action.py` (~150 LOC)

**Analog (exact):** `mcp_tools/handlers/position.py:258-318` `handle_get_position_state` (read-only).

**Excerpt to mirror (position.py:258-267 — envelope + sym_info fetch):**
```python
def handle_get_position_state(args: dict, mt5_client, cfg) -> dict:
    pid = int(args["position_id"])
    pos = mt5_client.get_position(pid)
    if pos is None:
        return envelope(ErrorCodes.POSITION_NOT_FOUND, f"Posizione {pid} non trovata",
                        position_id=pid)
    ...
```

**Copy to `mcp_tools/handlers/position_action.py`:**
```python
SUGGEST_POSITION_ACTION_TOOL = Tool(
    name="suggest_position_action",
    description=(
        "Hybrid rule + ML re-evaluation: hold/move_sl/partial_close/full_close + rationale "
        "strutturato (rules_triggered, ml_check, summary_it). Read-only — NON muta posizione. "
        "Skill chiama modify_position se accetta. OOD caveat surface esplicitamente."
    ),
    inputSchema={
        "type": "object",
        "properties": {"position_id": {"type": "integer", "minimum": 1}},
        "required": ["position_id"],
    },
)

def handle_suggest_position_action(args: dict, mt5_client, cfg, log) -> dict:
    """MCP-18 — delega a position_action.orchestrator."""
    from position_action.orchestrator import handle_suggest_position_action as _orchestrate
    return _orchestrate(args, mt5_client, cfg, log)
```

**Deviation:** read-only (no DRY_RUN gate needed — handler does not mutate). The skill `forex-trader-pro` is responsible for calling `modify_position` Phase 6 Plan 06-04 if it accepts the suggestion.

---

### Server + schemas

#### `mcp_tools/server.py` (extension ~40 LOC)

**Analog (self-extension):** `mcp_tools/server.py:53-62 + 285-289 + 348-375` (backtest bucket pattern).

**Add to list_tools (mirror lines 285-292):**
```python
# Phase 9 Wave 2-5 — failure analysis + drift + retrain + position action
GET_FAILURE_CLUSTERS_TOOL,
GET_DRIFT_METRICS_TOOL,
TRIGGER_RETRAIN_TOOL,
SUGGEST_POSITION_ACTION_TOOL,
```

**Add to call_tool dispatch (mirror lines 349-375):**
```python
if name in ("get_failure_clusters", "get_drift_metrics",
            "trigger_retrain", "suggest_position_action"):
    if name == "get_failure_clusters":
        return _text(handle_get_failure_clusters(arguments, cfg))
    if name == "get_drift_metrics":
        from logger import _trades_db_path
        drift_db = str(_trades_db_path(cfg).parent / "drift_log.db")
        return _text(handle_get_drift_metrics(arguments, cfg, drift_db))
    if name == "trigger_retrain":
        if job_queue is None:
            return _text(envelope("internal_error", "JobQueue non inizializzata"))
        return _text(handle_trigger_retrain(arguments, job_queue, cfg, log))
    if name == "suggest_position_action":
        return _text(handle_suggest_position_action(arguments, mt5, cfg, log))
```

**Add to `_bootstrap_state()` (mirror line 119 `trail_ensure_table`):**
```python
# Phase 9 Wave 0: drift_log.db + validation_log.db DDL idempotent
from drift.log_db import ensure_drift_log_db
ensure_drift_log_db(str(Path(db_path).parent / "drift_log.db"))
from retrain.validation_gate import ensure_validation_log_db
ensure_validation_log_db(str(Path(db_path).parent / "validation_log.db"))

# Phase 9 Wave 3: RetrainScheduler (BackgroundScheduler MemoryJobStore)
from retrain.scheduler import RetrainScheduler
_retrain_scheduler = RetrainScheduler(job_queue, cfg, log)
_retrain_scheduler.start()
```

#### `mcp_tools/schemas.py` (extension ~40 LOC)

**Analog (exact):** `mcp_tools/schemas.py:73-99` (MODIFY_POSITION_SCHEMA pattern).

**Copy 4 new schemas (verbatim style):**
```python
# Phase 9 Wave 2-5
GET_FAILURE_CLUSTERS_SCHEMA = {
    "type": "object",
    "properties": {
        "top_n": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
    },
    "required": [],
}
GET_DRIFT_METRICS_SCHEMA = {
    "type": "object",
    "properties": {
        "window_days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 30},
    },
    "required": [],
}
TRIGGER_RETRAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "reason": {"type": "string", "default": "manual"},
        "force": {"type": "boolean", "default": False},
    },
    "required": [],
}
SUGGEST_POSITION_ACTION_SCHEMA = {
    "type": "object",
    "properties": {"position_id": {"type": "integer", "minimum": 1}},
    "required": ["position_id"],
}
```

---

### CLI

#### `scripts/show_drift.py` (~200 LOC)

**Analog (exact):** `scripts/run_baseline_05_09.py:1-117` (argparse + smoke flag + exit code semantics 0/1/2/3/4).

**Excerpt run_baseline_05_09.py:26-45:**
```python
"""
Exit code:
    0 = OK (drift compute success, no breach)
    1 = drift breach detected (for future cron integration)
    2 = wall-clock or input data missing
    3 = schema-validation KO
"""
import argparse, sys, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_log = logging.getLogger("show_drift")
```

**Copy to `scripts/show_drift.py`** (INT-03 deliverable):
```python
def main() -> int:
    parser = argparse.ArgumentParser(description="Drift dashboard CLI (INT-03)")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--out-path", type=Path,
                        default=Path(".planning/research") / f"drift-report-{date.today()}.md")
    parser.add_argument("--exit-on-breach", action="store_true")
    args = parser.parse_args()

    from config import Config
    from logger import init_logger, _trades_db_path
    cfg = Config()
    _ = init_logger(cfg)
    drift_db = str(_trades_db_path(cfg).parent / "drift_log.db")

    from mcp_tools.handlers.drift import handle_get_drift_metrics
    metrics = handle_get_drift_metrics({"window_days": args.window_days}, cfg, drift_db)

    from drift.report_writer import write_drift_report
    write_drift_report(metrics, args.out_path, meta={...})

    breached = metrics.get("alarm_status") == "breach"
    _log.info("drift report: %s — breach=%s", args.out_path, breached)
    if args.exit_on_breach and breached:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

---

### Schema migrations + config

#### `logger.py` extension (~30 LOC)

**Analog (exact):** `mcp_tools/job_queue.py:60-72` `_ensure_error_column`.

**Excerpt job_queue.py:60-72:**
```python
def _ensure_error_column(self) -> None:
    """Idempotente: aggiunge backtest_runs.error_message se manca."""
    with sqlite3.connect(self._db) as c:
        c.execute("PRAGMA journal_mode=WAL")
        cols = {r[1] for r in c.execute("PRAGMA table_info(backtest_runs)")}
        if "error_message" not in cols:
            c.execute("ALTER TABLE backtest_runs ADD COLUMN error_message TEXT")
```

**Copy to `logger.py` extension (D-09-D4 schema migration + write wire):**
```python
def _ensure_ml_calibrated_prob_column(db_path: Path) -> None:
    """D-09-D4 idempotent: ALTER trades_log ADD COLUMN ml_calibrated_prob."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cols = {r[1] for r in conn.execute("PRAGMA table_info(trades_log)")}
        if "ml_calibrated_prob" not in cols:
            conn.execute("ALTER TABLE trades_log ADD COLUMN ml_calibrated_prob REAL")
        conn.commit()

# Call from init_logger() after _TRADES_LOG_SCHEMA CREATE (line 63):
_ensure_ml_calibrated_prob_column(_db_path)
```

**Extend `log_trade_decision` (line 69-97) to write `proposal.ml_calibrated_prob`:**
```python
# Existing INSERT (verbatim style) extended with ml_calibrated_prob:
conn.execute(
    """INSERT INTO trades_log
       (timestamp, symbol, direction, size_lots, entry_price,
        stop_loss, take_profit, decision_reason, approved, pnl_realized,
        ml_calibrated_prob)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
    (
        _now_iso(), proposal.symbol, proposal.direction,
        decision.size_lots, proposal.entry_price,
        decision.adjusted_stop_loss, decision.adjusted_take_profit,
        decision.reason, int(decision.approved),
        getattr(proposal, "ml_calibrated_prob", None),  # Phase 7 D-13 attached if ENABLE_ML_FILTER
    ),
)
```

#### `config.py` extension (~30 LOC)

**Analog (exact):** `config.py:60-120` Config class env-var declarations.

**Add inside Config class** (mirror lines 100-107 style):
```python
# Phase 9 Area B — Drift monitor (D-09-B3 thresholds + ECE n_bins)
DRIFT_KS_PVALUE_THRESHOLD: float = float(os.getenv("DRIFT_KS_PVALUE_THRESHOLD", "0.01"))
DRIFT_ECE_DELTA_THRESHOLD: float = float(os.getenv("DRIFT_ECE_DELTA_THRESHOLD", "0.02"))
DRIFT_FEATURE_FRACTION_THRESHOLD: float = float(os.getenv("DRIFT_FEATURE_FRACTION_THRESHOLD", "0.30"))
DRIFT_TOP_K_FEATURES: int = int(os.getenv("DRIFT_TOP_K_FEATURES", "15"))
DRIFT_MIN_SAMPLES_CURRENT: int = int(os.getenv("DRIFT_MIN_SAMPLES_CURRENT", "30"))
DRIFT_DEFAULT_WINDOW_DAYS: int = int(os.getenv("DRIFT_DEFAULT_WINDOW_DAYS", "30"))
DRIFT_ECE_N_BINS: int = int(os.getenv("DRIFT_ECE_N_BINS", "10"))   # P10 invariant Phase 7 align

# Phase 9 Area C — Retrain trigger workflow (D-09-C2 validation gate thresholds)
RETRAIN_CRON_SCHEDULE: str = os.getenv("RETRAIN_CRON_SCHEDULE", "0 2 1 * *")
MAX_ECE_REGRESSION_PCT: float = float(os.getenv("MAX_ECE_REGRESSION_PCT", "10.0"))
KS_CANDIDATE_DIVERGENCE_THRESHOLD: float = float(os.getenv("KS_CANDIDATE_DIVERGENCE_THRESHOLD", "0.15"))
EXPECTANCY_REGRESSION_PCT: float = float(os.getenv("EXPECTANCY_REGRESSION_PCT", "5.0"))

# Phase 9 Area D — Position action rules (profile-aware per D-09-D3)
BE_R_THRESHOLD_CONSERVATIVE: float = float(os.getenv("BE_R_THRESHOLD_CONSERVATIVE", "1.0"))
BE_R_THRESHOLD_MODERATE: float = float(os.getenv("BE_R_THRESHOLD_MODERATE", "1.5"))
BE_R_THRESHOLD_AGGRESSIVE: float = float(os.getenv("BE_R_THRESHOLD_AGGRESSIVE", "2.0"))
PARTIAL_R_THRESHOLD_CONSERVATIVE: float = float(os.getenv("PARTIAL_R_THRESHOLD_CONSERVATIVE", "1.5"))
PARTIAL_R_THRESHOLD_MODERATE: float = float(os.getenv("PARTIAL_R_THRESHOLD_MODERATE", "2.0"))
PARTIAL_R_THRESHOLD_AGGRESSIVE: float = float(os.getenv("PARTIAL_R_THRESHOLD_AGGRESSIVE", "2.5"))
FULL_R_THRESHOLD_CONSERVATIVE: float = float(os.getenv("FULL_R_THRESHOLD_CONSERVATIVE", "2.5"))
FULL_R_THRESHOLD_MODERATE: float = float(os.getenv("FULL_R_THRESHOLD_MODERATE", "3.0"))
FULL_R_THRESHOLD_AGGRESSIVE: float = float(os.getenv("FULL_R_THRESHOLD_AGGRESSIVE", "3.5"))
MAX_HOLD_BARS_CONSERVATIVE: int = int(os.getenv("MAX_HOLD_BARS_CONSERVATIVE", "72"))
MAX_HOLD_BARS_MODERATE: int = int(os.getenv("MAX_HOLD_BARS_MODERATE", "96"))
MAX_HOLD_BARS_AGGRESSIVE: int = int(os.getenv("MAX_HOLD_BARS_AGGRESSIVE", "120"))
PARTIAL_CLOSE_FRACTION: float = float(os.getenv("PARTIAL_CLOSE_FRACTION", "0.5"))
TIME_STOP_R_THRESHOLD: float = float(os.getenv("TIME_STOP_R_THRESHOLD", "0.5"))

# Phase 9 Area A — Failure clustering (D-09-A3 HDBSCAN hyperparams)
HDBSCAN_MIN_CLUSTER_SIZE: int = int(os.getenv("HDBSCAN_MIN_CLUSTER_SIZE", "20"))
HDBSCAN_MIN_SAMPLES: int | None = (
    int(os.getenv("HDBSCAN_MIN_SAMPLES")) if os.getenv("HDBSCAN_MIN_SAMPLES") else None
)
HDBSCAN_CLUSTER_SELECTION_METHOD: str = os.getenv("HDBSCAN_CLUSTER_SELECTION_METHOD", "eom")
CLUSTER_ARTIFACT_PATH: str = os.getenv("CLUSTER_ARTIFACT_PATH", "models/failure_clusters_v1.pkl")
DRIFT_SYNTH_SEED: int = int(os.getenv("DRIFT_SYNTH_SEED", "42"))   # determinism contract RESEARCH line 705
```

---

### Test suite

#### `tests/test_drift_log_db.py` (~100 LOC)

**Analog (exact):** `tests/test_mcp_trail_daemon.py:14-42` (`ensure_table` idempotency + schema validation).

**Excerpt test_mcp_trail_daemon.py:14-42:**
```python
@pytest.fixture
def tmp_db(tmp_path):
    from mcp_tools.trail_daemon import ensure_table
    db = tmp_path / "trades.db"
    ensure_table(db)
    return db

def test_ensure_table_creates_schema(tmp_db):
    with sqlite3.connect(str(tmp_db)) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(position_trails)")}
    expected = {"position_id", "symbol", ..., "active"}
    assert expected.issubset(cols)
    # Idempotenza: seconda call no-op
    from mcp_tools.trail_daemon import ensure_table
    ensure_table(tmp_db)
    with sqlite3.connect(str(tmp_db)) as c:
        cols2 = {r[1] for r in c.execute("PRAGMA table_info(position_trails)")}
    assert cols == cols2
```

**Copy to `tests/test_drift_log_db.py`:**
```python
@pytest.fixture
def tmp_drift_db(tmp_path):
    from drift.log_db import ensure_drift_log_db
    db = tmp_path / "drift_log.db"
    ensure_drift_log_db(db)
    return db

def test_ensure_drift_log_db_creates_schema(tmp_drift_db):
    with sqlite3.connect(str(tmp_drift_db)) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(drift_log)")}
    expected = {"id", "ts_utc", "model_version", "reference_hash", "metric_name",
                "metric_value", "threshold", "breached", "n_samples_current",
                "n_samples_reference", "window_days", "computed_by"}
    assert expected.issubset(cols)
    # Idempotenza
    from drift.log_db import ensure_drift_log_db
    ensure_drift_log_db(tmp_drift_db)
    with sqlite3.connect(str(tmp_drift_db)) as c:
        cols2 = {r[1] for r in c.execute("PRAGMA table_info(drift_log)")}
    assert cols == cols2

def test_wal_mode_set(tmp_drift_db):
    """P11 WAL mode guard."""
    with sqlite3.connect(str(tmp_drift_db)) as c:
        mode = c.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
```

#### `tests/test_mcp_handlers_cluster_drift_retrain_position.py` (~200 LOC)

**Analog (exact):** `tests/test_mcp_handlers_backtest.py:1-66` (fixture + handler invoke + envelope assert).

**Excerpt test_mcp_handlers_backtest.py:55-66:**
```python
@pytest.fixture
def db_and_queue(tmp_path, monkeypatch):
    db = tmp_path / "trades.db"
    LedgerWriter(db)
    import mcp_tools.handlers.backtest as bt_mod
    monkeypatch.setattr(bt_mod, "_backtest_worker", _fast_worker)
    q = JobQueue(max_workers=1, db_path=str(db))
    cfg = MagicMock()
    return db, q, cfg
```

**Copy to Phase 9 test fixture (verbatim adapt):**
```python
@pytest.fixture
def db_and_queue_phase9(tmp_path, monkeypatch):
    """Riusa fixture Phase 6: JobQueue cap=1 + worker stub veloce."""
    db = tmp_path / "trades.db"
    LedgerWriter(db)
    # P9 dedup test riusa _train_ml_filter_worker stub Phase 8
    import mcp_tools.handlers.ml as ml_mod  # Phase 8 planned
    monkeypatch.setattr(ml_mod, "_train_ml_filter_worker", _fast_ml_worker)
    q = JobQueue(max_workers=1, db_path=str(db))
    cfg = MagicMock()
    return db, q, cfg

def test_trigger_retrain_idempotent_dedup(db_and_queue_phase9):
    """D-09-C3: 3 concurrent triggers → 1 job + 2 already_pending."""
    db, q, cfg = db_and_queue_phase9
    r1 = handle_trigger_retrain({"reason": "manual"}, q, cfg, MagicMock())
    r2 = handle_trigger_retrain({"reason": "drift_breach"}, q, cfg, MagicMock())
    r3 = handle_trigger_retrain({"reason": "scheduled_cron"}, q, cfg, MagicMock())
    statuses = [r["status"] for r in (r1, r2, r3)]
    assert statuses.count("started") == 1
    assert statuses.count("already_pending") == 2
```

---

## Shared Patterns (Cross-Cutting)

### Pattern A — Error envelope (apply to ALL 4 new handlers + CLI)

**Source:** `mcp_tools/errors.py` (re-exports `mcp.errors.ErrorCodes, envelope`)
**Apply to:** `mcp_tools/handlers/{cluster,drift,retrain,position_action}.py`, `scripts/show_drift.py`, `retrain/dedup.py`

```python
from mcp_tools.errors import ErrorCodes, envelope

# Pattern uniform per ogni error path:
return envelope(ErrorCodes.NOT_FOUND, f"artifact mancante: {path}")
return envelope(ErrorCodes.VALIDATION_FAILED, msg)
return envelope(ErrorCodes.INTERNAL_ERROR, str(exc))
```

### Pattern B — SQLite WAL + idempotent CREATE TABLE (apply to drift_log.db + validation_log.db)

**Source:** `mcp_tools/trail_daemon.py:34-46 + 76-84` + `mcp_tools/job_queue.py:60-72` + `logger.py:14-28`
**Apply to:** `drift/log_db.py`, `retrain/validation_gate.py`, `logger.py` extension

```python
_TABLE_DDL = "CREATE TABLE IF NOT EXISTS <name> (...)"

def ensure_table(db_path: str | Path) -> None:
    with sqlite3.connect(str(db_path)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(_TABLE_DDL)
        c.execute("CREATE INDEX IF NOT EXISTS ...")

# Idempotent ALTER ADD COLUMN:
cols = {r[1] for r in c.execute("PRAGMA table_info(<name>)")}
if "<new_col>" not in cols:
    c.execute("ALTER TABLE <name> ADD COLUMN <new_col> <type>")
```

### Pattern C — Tool registration + dispatch (apply to server.py extension)

**Source:** `mcp_tools/server.py:53-62 + 285-289 + 348-375`
**Apply to:** `mcp_tools/server.py` extension Wave 5

```python
# 1. Import block (top of file)
from mcp_tools.handlers.cluster import GET_FAILURE_CLUSTERS_TOOL, handle_get_failure_clusters
# 2. list_tools() append
GET_FAILURE_CLUSTERS_TOOL,  # Phase 9 Wave 2
# 3. call_tool() dispatch
if name == "get_failure_clusters":
    return _text(handle_get_failure_clusters(arguments, cfg))
```

### Pattern D — Worker reuse (apply to retrain handler)

**Source:** Phase 8 PATTERNS.md `_train_ml_filter_worker` (planned)
**Apply to:** `retrain/dedup.py` enqueue_or_dedup

D-09-C1 zero-duplication: enqueue Phase 8 `_train_ml_filter_worker` directly. No new worker fn. No new picklability surface.

### Pattern E — Atomic os.replace pair (apply to retrain/promotion.py)

**Source:** RESEARCH § P6+P7 + Python stdlib `os.replace` docs
**Apply to:** `retrain/promotion.py::atomic_promote`

```python
# Order MANDATORY: metadata FIRST, .pkl SECOND
os.replace(cand_meta, final_meta)   # Windows MoveFileEx replace-existing
os.replace(cand_pkl, final_pkl)
# Crash mid-pair → P7 FeatureSchemaMismatchError on next MLFilter.load
```

### Pattern F — Singleton invalidation (apply to retrain/promotion.py)

**Source:** Phase 7 PATTERNS.md `ml/inference.py:_MODEL_CACHE + threading.Lock` (planned, lines 488-500)
**Apply to:** Wave 0 add `_invalidate_singleton()` to `ml/inference.py`; called from `retrain/promotion.py`

```python
# ml/inference.py addition (Wave 0 task):
def _invalidate_singleton() -> None:
    global _MODEL_CACHE
    with _LOCK:
        _MODEL_CACHE = None

# retrain/promotion.py usage:
from ml.inference import _invalidate_singleton
_invalidate_singleton()   # P8 hot-reload
```

### Pattern G — APScheduler add_job uniform options (apply to retrain/scheduler.py)

**Source:** `scheduler.py:303-311` (build_scheduler.add_job)
**Apply to:** `retrain/scheduler.py::RetrainScheduler.start`

```python
scheduler.add_job(
    fn, trigger=trigger, id="<unique_id>",
    max_instances=1, coalesce=True,
    misfire_grace_time=3600,        # P13 1h grace (DIFFERS from scheduler.py: 300s)
    replace_existing=True,          # P5 restart-safe
)
```

**Deviation Phase 9 introduces:** `misfire_grace_time=3600` (not 300 like scheduler.py) — RESEARCH P13 +1h grace per agent downtime acceptable for monthly cron. `BackgroundScheduler(timezone="UTC")` (not BlockingScheduler + Europe/Rome) — P4 + RESEARCH Open Question #4.

### Pattern H — Italian rationale + log (apply to position_action/orchestrator.py + drift/report_writer.py + summary fields)

**Source:** CLAUDE.md "Lingua commenti/log/rationale: italiano" + RESEARCH P15
**Apply to:** ALL `summary_it` fields + log strings in `cluster/`, `drift/`, `retrain/`, `position_action/`

Forbidden phrases in `summary_it` (P9 OOD guard): `"probabilità che vinca"`, `"P(TP_HIT)"`, `"odds of TP"`.
Required Italian markers (regex test): `suggerisco|confermata|invalidata|raggiunto|caveat`.

### Pattern I — pytest tmp_path + MagicMock cfg/log (apply to ALL Phase 9 tests)

**Source:** `tests/test_mcp_handlers_position.py:14-52` + `tests/test_mcp_trail_daemon.py:14-22`
**Apply to:** All 16 new test files

```python
@pytest.fixture
def mock_cfg(tmp_path):
    return SimpleNamespace(
        DRY_RUN=False, EXECUTION_MODE="live",
        LOG_FILE=str(tmp_path / "logs" / "agent.log"),
        # Phase 9 env-vars:
        DRIFT_KS_PVALUE_THRESHOLD=0.01, DRIFT_ECE_DELTA_THRESHOLD=0.02,
        BE_R_THRESHOLD_MODERATE=1.5, ML_THRESHOLD_BY_PROFILE={"MODERATE": 0.55},
        # ...
    )

@pytest.fixture
def mock_log():
    return MagicMock()
```

### Pattern J — pytest.importorskip per Phase-7/8 planned deps (apply to ALL Phase 9 tests citing ml.*)

**Source:** `tests/test_mcp_handlers_backtest.py:17-25` (`pytest.importorskip("mcp_tools.handlers.backtest")`)
**Apply to:** `tests/test_drift_compute.py`, `tests/test_retrain_validation_gate.py`, `tests/test_position_action_ml_recheck.py`, `tests/test_mcp_handlers_cluster_drift_retrain_position.py`

```python
pytest.importorskip("ml.inference")     # Phase 7 dep — skip if not on disk yet
pytest.importorskip("hdbscan")           # Phase 9 Wave 0 install gate
```

### Pattern K — Markdown report writer (apply to drift/report_writer.py)

**Source:** `backtest/baseline/report_writer.py:80-176` (write_baseline_report)
**Apply to:** `drift/report_writer.py::write_drift_report`

Sections: header (timestamp + git_sha + cli_command), metric tables (KS + ECE + feature drift top-K), per-section detail, appendix (reference_hash + thresholds + sample counts).

---

## No Analog Found (Phase 9 novel patterns)

| File | Role | Data Flow | Reason | Wave |
|------|------|-----------|--------|------|
| `cluster/match.py` | inference wrapper | feature_vec → `hdbscan.approximate_predict` → (label, strength) | Wave 2 add-on; no in-repo HDBSCAN consumer; novel API surface | Wave 2 deferred |
| `retrain/promotion.py::atomic_promote` | state mutator (Windows-atomic pair) | candidate pair → final pair via `os.replace` order-mandatory + `_invalidate_singleton()` | Phase 9 introduces Windows-atomic pair pattern. Wave 0 prereq: add `_invalidate_singleton()` to `ml/inference.py` Phase 7 planned module | Wave 3 |

Both follow concrete skeletons from RESEARCH.md (lines 758-799 for promotion P6/P7/P8; lines 758-768 for cluster match P1/P2). Plan-phase should treat these as RESEARCH-anchored, not codebase-anchored.

---

## Notes for planner

1. **Wave 0 scaffolding mandatory before Wave 1+:**
   - `requirements.txt` add `hdbscan>=0.8.40,<0.9.0   # DO NOT switch to sklearn.cluster.HDBSCAN — lacks approximate_predict (P2)`
   - `config.py` 26 new env-var declarations (Phase 9 § Area B/C/D + HDBSCAN cluster)
   - `.env.example` mirror
   - `logger.py::_ensure_ml_calibrated_prob_column` + wire to `log_trade_decision`
   - `ml/inference.py::_invalidate_singleton()` helper (Phase 7 planned module extension)
   - 4 empty package barrels (`cluster/__init__.py`, `drift/__init__.py`, `retrain/__init__.py`, `position_action/__init__.py`)

2. **Wave order (matches CONTEXT.md § Next Steps suggested 8 waves):**
   - W0: scaffolding (above)
   - W1: Area A failure clustering (cluster/* + mcp_tools/handlers/cluster.py + tests)
   - W2: Area B drift monitor (drift/* + mcp_tools/handlers/drift.py + tests)
   - W3: Area C retrain (retrain/* + mcp_tools/handlers/retrain.py + scheduler integration + tests)
   - W4: Area D suggest_position_action (position_action/* + mcp_tools/handlers/position_action.py + tests)
   - W5: INT-03 CLI (scripts/show_drift.py + drift/report_writer.py + tests)
   - W6: server.py + schemas.py extension + 4 Tool dispatch + bootstrap_state wiring + E2E smoke
   - W7 (optional): validation_log.db migration test + trades_log ml_calibrated_prob test (can fold in W0)

3. **Cross-phase analog dependency chain:** Phase 7 PATTERNS.md modules (`ml/feature_extraction.py`, `ml/inference.py::MLFilter`, `ml/artifact.py::dump_bundle`, `ml/calibration.py::compute_ece`) and Phase 8 PATTERNS.md `mcp_tools/handlers/ml.py::_train_ml_filter_worker` are **planned but not yet on disk**. Phase 9 PLAN.md files MUST cite them as cross-phase dependencies + add `pytest.importorskip(...)` to tests so Phase 9 tests are skip-tolerant until Phase 7/8 execute commits land.

4. **Determinism enforcement uniform:**
   - HDBSCAN: `core_dist_n_jobs=1` (Phase 9 § Area A)
   - Synthetic fixtures: `np.random.seed(cfg.DRIFT_SYNTH_SEED)` default 42
   - LightGBM: `num_threads=1` (Phase 7 D-07-05 carry, no Phase 9 deviation)
   - ECE n_bins: `DRIFT_ECE_N_BINS=10` MUST equal Phase 7 training n_bins (P10 + metadata.json invariant)

5. **CLAUDE.md compliance hard rules:**
   - EXECUTION_MODE=shadow respected (MCP-18 read-only by construction; retrain validation gate doesn't commit broker; cluster/drift never touch broker)
   - Zero magic numbers: 26 .env vars added (Pattern in config.py)
   - Italiano log/rationale: Pattern H uniform
   - risk_engine = unico gate: MCP-18 NON è gate, è suggestion; ENABLE_ML_FILTER=false fallback drops ML to rule-only

6. **Project memory `project_training_data_integrity_priority.md` honored:**
   - D-09-A1 baseline-only read-only (no concurrent write)
   - D-09-C1 zero new path (reuse Phase 8 worker)
   - D-09-C2 validation gate protects silently-worse-model
   - D-09-C3 idempotent dedup (no new race)
   - D-09-C4 alarm-only (no silent auto-action)
   - audit anchors uniformly applied: `reference_hash` per drift row, `dataset_hash` per cluster bundle, `parquet_sha256` per retrain run, `triggered_by_sources_json` per validation row

---

## Metadata

**Analog search scope:**
- `/workspaces/trading-agent/mcp_tools/` (all 13 files)
- `/workspaces/trading-agent/backtest/baseline/` (all 9 files)
- `/workspaces/trading-agent/scheduler.py`, `logger.py`, `config.py`, `risk_engine.py`
- `/workspaces/trading-agent/scripts/run_baseline_05_09.py`
- `/workspaces/trading-agent/tests/test_mcp_handlers_backtest.py`, `test_mcp_handlers_position.py`, `test_mcp_trail_daemon.py`
- Phase 7 PATTERNS.md + Phase 7 Plan 07-05 + Phase 8 PATTERNS.md + Phase 8 Plan 08-04 (planned-analog references)
- Phase 9 RESEARCH.md § Implementation Patterns + § Cross-Phase Reuse Map (skeletons + pitfalls)

**Files scanned:** ~22 source + ~6 plan/research + ~5 test → 33 reads total, no duplicate range re-reads.

**Pattern extraction date:** 2026-05-12

**Phase 9 LOC totals confirmed from CONTEXT.md § code_context:**
- Source: ~2850 LOC (cluster 600 + drift 600 + retrain 400 + position_action 480 + 4 handlers 570 + CLI 200 + report_writer 150)
- Tests: ~1500 LOC (~14 files)
- Config/migration: ~80 LOC (.env + logger + config extensions)
- **Total Phase 9: ~4430 LOC** (matches RESEARCH § Cross-Phase Reuse Map confirmation, line 637)

---

## PATTERN MAPPING COMPLETE
