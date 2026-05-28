# Phase 7: ML Classifier — Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 20 (8 new ml/ modules + 7 new tests + 5 modified)
**Analogs found:** 17 / 20 — 3 NEW patterns flagged honestly (LightGBM training loop, sklearn manual calibration, profit-curve sweep)

Reference style mirrors `.planning/phases/06-mcp-tools-part-1/06-PATTERNS.md`. Every cited line range was read directly from source during analog selection. Planner: when you copy from an analog, copy *shape* (imports, dataclass frozen, error path, italiano docstring) — semantics belong to RESEARCH.md Patterns 1-6.

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `ml/__init__.py` | package-init | re-export | `indicators/__init__.py:1-97` (barrel) + `backtest/baseline/__init__.py` (2-line template) | exact |
| `ml/feature_extraction.py` | pure-fn / transform | batch transform (parquet → X/y) | `backtest/baseline/slice_worker.py:68-119` (`_extract_extended_snapshot_at_entry`) + `strategy/confluence.py:81-89, 97-200` (pure factor predicates) | role-match (no upstream parquet→feature module exists yet) |
| `ml/walk_forward.py` | service / pure-fn | batch fan-out (DataFrame → fold tuples) | `backtest/walk_forward.py:14-59` (`walk_forward_slices` expanding) + `RESEARCH.md §Pattern 3` (per-TF embargo) | role-match (expanding shape exists; embargo logic NEW) |
| `ml/train.py` | service / orchestrator | batch / fan-out (CV loop + persist) | `backtest/baseline/runner.py:130-248` (`run_baseline` orchestrator shape) + RESEARCH.md §Pattern 1 (LightGBM training) | role-match (orchestration shape) + NEW pattern (LightGBM training loop) |
| `ml/calibration.py` | pure-fn | transform (proba → calibrated proba) | `backtest/baseline/determinism.py:20-40` (pure math module shape) + RESEARCH.md §Pattern 2 (manual Platt/Isotonic) | role-match (shape) + NEW pattern (sklearn 1.8 manual calibration replaces CalibratedClassifierCV cv='prefit') |
| `ml/threshold.py` | pure-fn | transform (proba+pnl → threshold) | `risk_engine.py:15-19` (`PROFILES` dict profile-aware) + RESEARCH.md §Pattern 6 (profit-curve sweep) | role-match (profile-aware) + NEW pattern (sweep solver) |
| `ml/inference.py` | service / singleton | request-response (X → raw_score, calibrated_prob) | `mt5_client.py:26-39` (`_retry` module-level wrapper) + `logger.py:30-66` (module-level cache pattern `_db_path: Path \| None = None`) + RESEARCH.md §Pattern 5 (double-check lock) | role-match (singleton shape) |
| `ml/artifact.py` | serialization | file-I/O (bundle + metadata.json) | `backtest/baseline/dataset_writer.py:87-118` (shard write + metadata sidecar) + `backtest/baseline/determinism.py:29-35` (`file_sha256`) | role-match (different store: joblib pkl vs parquet) |
| `data/configs/ml.yaml` | static-data | config | `data/configs/baseline.yaml` + `backtest/baseline/runner.py:39-89` (`BaselineConfig` frozen dataclass + loader) | exact |
| `tests/test_ml_feature_extraction.py` | test | deterministic snapshot | `tests/test_indicators_purity.py:46-72` (no-future-leakage parametrized) + `tests/test_strategy_regression.py` (snapshot pattern) | exact |
| `tests/test_ml_walk_forward.py` | test | invariant (no-shuffle + embargo) | `tests/test_backtest_walk_forward.py:1-62` (full file — overlap + temporal-order asserts) | exact |
| `tests/test_ml_train.py` | test | fixture + assertion | `tests/test_backtest_ledger.py:26-87` (tmp_path + round-trip) | role-match |
| `tests/test_ml_calibration.py` | test | numerical assertion (Platt + Isotonic) | `tests/test_indicators_purity.py:75-105` (parametrized math invariant) | role-match |
| `tests/test_ml_threshold.py` | test | unit (synthetic prob+pnl) | `tests/test_backtest_walk_forward.py:50-54` (synthetic-input shape) | role-match |
| `tests/test_ml_inference.py` | test | benchmark (p95 < 10ms × 1000 samples) | none in repo (first latency benchmark) | NEW pattern (RESEARCH.md §Latency Budget + §Pitfall 4) |
| `tests/test_ml_purity.py` | test (AST) | invariant | `tests/test_strategy_purity.py:1-232` (full file — AST forbidden imports + logging calls + print/open) | exact (verbatim AST gate shape) |
| `strategy/__init__.py` (modify `evaluate_proposal_for_bar`) | integration hook | request-response | self — `strategy/__init__.py:61-103` (existing function body) | self-extend |
| `strategy/proposal.py` (modify `ProposalDraft`) | model | static-data | self — `strategy/proposal.py:22-44` (frozen dataclass with `__post_init__`) | self-extend |
| `risk_engine.py` (ML gate) | gate | request-response | self — `risk_engine.py:32-156` (existing gates, especially `reject()` closure pattern 44-52) | self-extend |
| `config.py` (3 new env vars) | config | static-data | self — `config.py:60-175` (existing `Config` class with `os.getenv` + `_get_bool` helper) | self-extend |
| `.env.example` (3 new vars) | config | static-data | existing `.env.example` block layout | exact |

---

## Pattern Assignments

### `ml/__init__.py` (package-init, re-export)

**Analog 1 — barrel module:** `indicators/__init__.py:1-97` (large surface with `__all__` enumeration).
**Analog 2 — minimal package marker:** `backtest/baseline/__init__.py` (2-line template).

**Recommended shape (mirror `indicators/__init__.py:1-52`):**
```python
"""Pacchetto ML classifier (Phase 7) — LightGBM binary trade-quality filter.

Pure-API surface: feature extraction, walk-forward training, manual Platt/Isotonic
calibration, profit-curve threshold optimization, joblib artifact persistence,
singleton inference loader. Nessun broker call, nessun logging dentro i moduli
puri (tests/test_ml_purity.py gating).

Backward-compat: `strategy/__init__.py::evaluate_proposal_for_bar` carica
`MLFilter` come dipendenza opzionale (kwarg default None) — Phase 5 backtest
gira senza modello (chicken-and-egg risolto).
"""
from ml.feature_extraction import build_feature_vector, derive_d_09_g_fields
from ml.walk_forward import build_ml_folds
from ml.calibration import platt_fit, isotonic_fit, expected_calibration_error
from ml.threshold import profit_curve_optimal_threshold
from ml.inference import MLFilter, get_ml_filter
from ml.artifact import dump_bundle, load_bundle

__all__ = [
    "build_feature_vector",
    "derive_d_09_g_fields",
    "build_ml_folds",
    "platt_fit",
    "isotonic_fit",
    "expected_calibration_error",
    "profit_curve_optimal_threshold",
    "MLFilter",
    "get_ml_filter",
    "dump_bundle",
    "load_bundle",
]
```

---

### `ml/feature_extraction.py` (pure-fn / transform — D-09-G derivation + X/y build)

**Analog 1 — no-leakage snapshot at entry:** `backtest/baseline/slice_worker.py:68-119` (`_extract_extended_snapshot_at_entry`) — the canonical strict-`<` slice pattern.

**Analog 2 — pure factor predicates:** `strategy/confluence.py:81-200` (`_check_*` helpers — small, side-effect-free, dispatched by `score_factors`).

**Imports + module docstring (mirror `strategy/confluence.py:1-23`):**
```python
"""Feature extraction Phase 7 (ML-01).

Pure-function: legge data/training/baseline_decisions/part-0.parquet (1076 × 59
cols schema-v2), deriva 8 campi D-09-G mancanti dal parquet (setup_name,
pattern_name, confluence_factors_json, bias, sl_pips, tp_pips, r_to_r,
bars_to_outcome), costruisce X (numpy 2D) e y (numpy 1D binary), encoding
categoricals (symbol, timeframe, profile, setup_name, regime) via dict map
persistito per inference-time consistenza (RESEARCH.md §Pitfall 2).

Nessun broker call, nessun logging, nessun datetime.now() — testable in
isolamento (tests/test_ml_feature_extraction.py snapshot).

D-17 no-future-leakage by construction: il dataset Phase 5 e' gia' snapshot
@ bar idx-1 (Plan 05-09 D-09-B). Questo modulo NON re-fetcha bar data; legge
solo dal parquet read-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
```

**D-09-G derivation pattern** — mirror `_extract_extended_snapshot_at_entry:74-118` (defensive getattr + dict fallback):
```python
def derive_d_09_g_fields(row: pd.Series) -> dict:
    """Deriva 8 campi mancanti da decision_context_json + pnl_pips + timestamps.

    Plan 05-09 D-09-G deferred fields:
      - setup_name: row.decision_context_json["setup_name"]
      - pattern_name: row.decision_context_json.get("pattern_name", None)
      - confluence_factors_json: json.dumps(row.decision_context_json["factors"])
      - bias: row.decision_context_json.get("direction")  # BUY/SELL
      - sl_pips: abs(row.entry_price - row.sl) / pip_size_for(symbol)
      - tp_pips: abs(row.tp - row.entry_price) / pip_size_for(symbol)
      - r_to_r: tp_pips / sl_pips se sl_pips > 0 else None
      - bars_to_outcome: int((row.exit_ts_utc - row.entry_ts_utc).total_seconds() / tf_seconds[row.timeframe])

    Edge: ctx parse fail -> dict vuoto; row -> NaN nelle colonne derivate (defensive,
    pattern slice_worker.py:106-115 fallback no-raise).
    """
    ctx = row.get("decision_context_json")
    if isinstance(ctx, str):
        try:
            ctx = json.loads(ctx)
        except Exception:  # noqa: BLE001 — defensive parse
            ctx = {}
    elif not isinstance(ctx, dict):
        ctx = {}
    # ... derivare 8 campi con .get(key, None) e ritorno NaN se mancante
```

**Categorical encoding persistence (RESEARCH.md §Pitfall 2):** encoding map MUST be in `metadata.json` for inference-time consistency. Pattern mirrors `backtest/baseline/dataset_writer.py:43-80` (schema whitelist built at import time, frozen):
```python
def build_categorical_encodings(df: pd.DataFrame, cat_cols: list[str]) -> dict[str, dict[str, int]]:
    """Build encoding map persistito in metadata.json (RESEARCH.md §Pitfall 2)."""
    return {
        col: {val: idx for idx, val in enumerate(sorted(df[col].dropna().unique()))}
        for col in cat_cols
    }
```

**Feature vector builder (inference path, mirror RESEARCH.md §Code Examples lines 681-732):** signature `build_feature_vector(draft, indicators, ctx, feature_list, cat_encodings) -> pd.DataFrame` — single-row DataFrame preserves feature names (no sklearn UserWarning).

---

### `ml/walk_forward.py` (pure-fn — expanding + embargo per-TF)

**Analog (closest possible):** `backtest/walk_forward.py:1-59` (entire 59-line file — expanding mode lines 54-59 is the exact starting template).

**Verbatim shape to extend:**
```python
"""Walk-forward fold builder Phase 7 (ML-03, D-05/06/07).

Estende `backtest.walk_forward_slices` (Phase 1) con:
  - operazione su DataFrame ordinato per decision_ts_utc (vs sequenza bar Phase 1)
  - embargo per-TF (Phase 1 non aveva embargo — RESEARCH.md §Pattern 3)
  - train/val split temporale last-20% del train fold (D-08, no shuffle)
  - returns (train_idx, val_idx, test_idx) — 3 tupla vs 2 di Phase 1

D-17 no-future-leakage by construction: `df.sort_values("decision_ts_utc")` +
embargo = max(timeout_bars[tf]) garantisce zero label leak (D-07).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

_FOLD_CAP = 10  # D-06 (mirror Phase 1 _FOLD_CAP)
```

**Expanding mode template** (`backtest/walk_forward.py:54-59`):
```python
# expanding
test_size = max(1, total // (n_folds + train_ratio))
for i in range(n_folds):
    test_start = train_ratio * test_size + i * test_size
    test_end = test_start + test_size
    yield list(bars[:test_start]), list(bars[test_start:test_end])
```

**Phase 7 adaptation (mirror shape + 3 changes):**
1. Replace `bars` with `df` sorted by `decision_ts_utc`.
2. Insert embargo row count between `test_start` and `test_end`.
3. Add `val_idx` derivation as `int(train_end * 0.80)..train_end`.

Concrete snippet (from RESEARCH.md §Pattern 3 lines 324-388, already vetted):
```python
def build_ml_folds(
    df: pd.DataFrame,
    n_folds: int,
    embargo_bars_by_tf: dict[str, int],
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    df_sorted = df.sort_values("decision_ts_utc").reset_index(drop=True)
    total = len(df_sorted)
    slot = total // (n_folds + 1)
    embargo_rows = max(embargo_bars_by_tf.values())  # D-07 upper-bound conservativo

    folds = []
    for k in range(n_folds):
        train_end = slot + k * slot
        test_start = train_end + embargo_rows
        test_end = min(test_start + slot, total)
        if test_end <= test_start:
            continue
        val_start = int(train_end * 0.80)  # D-08
        folds.append((
            np.arange(0, val_start),
            np.arange(val_start, train_end),
            np.arange(test_start, test_end),
        ))
    return folds
```

**No-shuffle assertion** (test mirrors `tests/test_backtest_walk_forward.py:50-54`):
```python
def test_temporal_order_ml_folds():
    for train_idx, val_idx, test_idx in build_ml_folds(df, n_folds=10, embargo_bars_by_tf={"M15":96,"M30":96,"H1":120}):
        assert max(train_idx) < min(val_idx) < min(test_idx)
```

---

### `ml/train.py` (service / orchestrator — fold loop + final retrain)

**Analog (orchestration shape):** `backtest/baseline/runner.py:130-248` (`run_baseline` full function — fan-out + per-task error handling + post-pool aggregation + audit metadata write).

**Imports + module docstring (mirror `backtest/baseline/runner.py:1-33`):**
```python
"""Phase 7 ML training pipeline orchestrator (ML-02, ML-03, ML-04).

Carica baseline_decisions.parquet (1076 trade), costruisce X/y + categorical
encodings, 10 fold expanding walk-forward (D-05/06/07), per ogni fold:
  1. LightGBM fit con scale_pos_weight + early stopping su val Brier (D-04, D-08)
  2. Manual Platt + Isotonic su raw predict_proba (RESEARCH.md §Pattern 2 — NO
     CalibratedClassifierCV cv='prefit', rimosso sklearn 1.8.0)
  3. Brier winner selection; val<50 -> Platt-only (HANDOFF.json blocker #3)
  4. Threshold sweep per profile, profit-curve optimization (D-14, RESEARCH §Pattern 6)
  5. Save fold artifact + .metadata.json

Post-fold: retrain final su 100% dataset, calibrator winner aggregate (mode),
threshold mediana fold per profile, joblib bundle + metadata.json (D-15).

Source: PATTERNS.md §ml/train.py, RESEARCH.md §Architecture Pattern 1+2+6,
CONTEXT.md §specifics lines 259-415.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, precision_recall_curve, auc

_log = logging.getLogger(__name__)
```

**Frozen config dataclass** (mirror `backtest/baseline/runner.py:39-89`):
```python
@dataclass(frozen=True)
class MLTrainingConfig:
    """Frozen config da data/configs/ml.yaml. Pickle-safe per future ProcessPool."""
    n_folds: int
    embargo_bars_by_tf: dict[str, int]
    train_val_split_pct: float
    lightgbm: dict  # hyperparams
    threshold_sweep_min: float
    threshold_sweep_max: float
    threshold_sweep_step: float
    dataset_path: str
    output_dir: str
    fold_subdir: str

def load_ml_training_config(yaml_path: Path | None = None) -> MLTrainingConfig:
    """Mirror backtest/baseline/runner.py:62-89 (load + frozen dataclass)."""
```

**Per-fold loop body** — NEW pattern (LightGBM training is first usage in repo). Source canonical: RESEARCH.md §Pattern 1 lines 246-278:
```python
spw = (y_train == 0).sum() / max((y_train == 1).sum(), 1)  # D-04 per-fold recompute
model = lgb.LGBMClassifier(
    **cfg.lightgbm,
    scale_pos_weight=spw,
    objective="binary",
    random_state=42,
    verbose=-1,  # RESEARCH §State of the Art: 4.x defaults are noisy
)
model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(-1)],
    categorical_feature=cat_features,  # fit-time, NOT constructor (RESEARCH §Pattern 1)
)
```

**Fold loop error handling** — mirror `backtest/baseline/runner.py:206-218` (per-task try/except, never crash whole pipeline):
```python
fold_metrics, fold_models, fold_calibrators = [], [], []
for k, (tr, va, te) in enumerate(folds):
    try:
        m = _train_one_fold(df, tr, va, te, cfg, feature_cols, cat_features)
        fold_metrics.append(m["metrics"])
        fold_models.append(m["model"])
        fold_calibrators.append(m["calibrator"])
    except Exception as exc:  # noqa: BLE001
        _log.error("fold %d fallito: %s", k + 1, exc, exc_info=True)
        fold_metrics.append({"fold": k + 1, "status": "FAILED", "error": str(exc)})
```

**Italiano log format** (mirror `risk_engine.py:45` + `backtest/baseline/runner.py:247`):
```python
_log.info("fold %d/%d: Brier=%.4f ECE=%.4f winner=%s n_test=%d",
          k + 1, cfg.n_folds, brier, ece, winner, len(te))
```

---

### `ml/calibration.py` (pure-fn — manual Platt + Isotonic + ECE)

**Analog (shape only):** `backtest/baseline/determinism.py:1-40` (small pure-math module with `_log`-free signature). The actual sklearn calls are NEW.

**Imports + module docstring** (mirror `backtest/baseline/determinism.py:1-19`):
```python
"""Manual Platt + Isotonic calibration (ML-04, RESEARCH.md §Pattern 2).

sklearn 1.8.0 ha RIMOSSO `CalibratedClassifierCV(cv='prefit')` — il CONTEXT.md
skeleton lines 316-319 NON funziona piu' (InvalidParameterError). Pattern
sostitutivo: fit di LogisticRegression (Platt) o IsotonicRegression direttamente
sul `predict_proba` grezzo del LightGBM model pre-fittato.

Brier winner picking per fold; val<50 -> Platt-only (Isotonic unreliable, HANDOFF
blocker #3). ECE last-bin <= per includere y_prob == 1.0 (RESEARCH.md §Pitfall 5).

Modulo puro: nessun side effect, testable con seed lockato.
Source: sklearn 1.8 release notes, RESEARCH.md §Pattern 2 + §Pitfall 5.
"""
from __future__ import annotations
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
```

**Manual calibration core (NEW pattern — verbatim from RESEARCH.md §Pattern 2 lines 290-313):**
```python
def platt_fit(raw_val: np.ndarray, y_val: np.ndarray) -> LogisticRegression:
    """Platt scaling: LogisticRegression su raw proba (vs CalibratedClassifierCV cv='prefit' removed)."""
    cal = LogisticRegression(C=1.0)
    cal.fit(raw_val.reshape(-1, 1), y_val)
    return cal

def isotonic_fit(raw_val: np.ndarray, y_val: np.ndarray) -> IsotonicRegression:
    """Isotonic monotonic non-parametric. out_of_bounds='clip' safety per OOD."""
    cal = IsotonicRegression(out_of_bounds="clip")
    cal.fit(raw_val, y_val)
    return cal

def pick_brier_winner(
    raw_test: np.ndarray, y_test: np.ndarray,
    platt: LogisticRegression, iso: IsotonicRegression,
    val_size: int, val_size_threshold: int = 50,
) -> tuple[str, np.ndarray]:
    """Brier winner per fold; val < 50 -> Platt forzato (HANDOFF blocker #3)."""
    if val_size < val_size_threshold:
        return "sigmoid", platt.predict_proba(raw_test.reshape(-1, 1))[:, 1]
    prob_platt = platt.predict_proba(raw_test.reshape(-1, 1))[:, 1]
    prob_iso   = iso.transform(raw_test)
    brier_platt = brier_score_loss(y_test, prob_platt)
    brier_iso   = brier_score_loss(y_test, prob_iso)
    return ("isotonic", prob_iso) if brier_iso <= brier_platt else ("sigmoid", prob_platt)
```

**ECE last-bin fix (RESEARCH.md §Pattern 4 + §Pitfall 5):**
```python
def expected_calibration_error(y_true, y_prob, n_bins: int = 10) -> float:
    """ECE con last-bin <= per includere y_prob == 1.0. NON il `<` del CONTEXT skeleton."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        if i < n_bins - 1:
            mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
        else:
            mask = (y_prob >= bin_edges[i]) & (y_prob <= bin_edges[i + 1])  # FIX last bin
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / len(y_true)) * abs(y_true[mask].mean() - y_prob[mask].mean())
    return float(ece)
```

---

### `ml/threshold.py` (pure-fn — profit-curve sweep per profile)

**Analog 1 (profile shape):** `risk_engine.py:15-19` (`PROFILES` dict — CONS/MOD/AGG keys) and `risk_engine.py:32-42` (profile lookup).
**Analog 2 (math signature):** none in repo — first profit-curve solver. Source: RESEARCH.md §Pattern 6 lines 465-485.

**Imports + module docstring:**
```python
"""Profit-curve threshold optimizer per profile (ML, D-14, RESEARCH §Pattern 6).

Sweep threshold ∈ [0.20, 0.70] step 0.01 sul val set, max expectancy_pips
per profile (CONS/MOD/AGG). Final threshold = mediana 10-fold (robusto a
outlier).

Modulo puro: nessun side effect. Brier non involved qui (calibrazione e'
gia' fatta in ml.calibration). Threshold = decision-side optimization,
distinct dal calibrator winner.
"""
from __future__ import annotations
import numpy as np

PROFILES = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")  # mirror risk_engine.py:15
```

**Sweep + median pattern (verbatim RESEARCH.md §Pattern 6):**
```python
def profit_curve_optimal_threshold(
    prob_val: np.ndarray,
    pnl_pips: np.ndarray,
    sweep: np.ndarray,
) -> float:
    best_t, best_exp = float(sweep[0]), -np.inf
    for t in sweep:
        mask = prob_val >= t
        if mask.sum() == 0:
            continue
        exp = float(pnl_pips[mask].mean())
        if exp > best_exp:
            best_exp, best_t = exp, float(t)
    return best_t

def median_across_folds(fold_thresholds: list[float]) -> float:
    """Robust aggregator: mediana > media per resilienza a fold outlier."""
    return float(np.median(fold_thresholds)) if fold_thresholds else 0.5
```

---

### `ml/inference.py` (service / singleton — predict API)

**Analog 1 — module-level cache:** `logger.py:30-66` (`_db_path: Path | None = None` + lazy init in `init_logger`).
**Analog 2 — class+classmethod load:** `backtest/baseline/runner.py:39-89` (frozen dataclass + `load_*_config` classmethod-equivalent).
**Analog 3 — retry wrapper (defensive):** `mt5_client.py:26-39` (`_retry` decorator — same shape applicable to predict error handling, though predict itself shouldn't retry).

**Imports + module docstring** (mirror `logger.py:1-13`):
```python
"""ML inference singleton + predict API (ML-05, D-16 pure-fn preserved).

Pattern: module-level _MODEL_CACHE + threading.Lock double-check (RESEARCH §Pattern 5).
ProcessPoolExecutor worker fork-safe: ogni worker carica proprio singleton al primo
predict (joblib bundle pickle-able).

predict(X) -> (raw_score, calibrated_prob). Latenza target p95 < 10ms su 1000-sample
benchmark (RESEARCH §Latency Budget: p50=4ms, p95=9ms, p99=13ms in WSL2; p99 e' OS-jitter
in container — su Windows bare-metal p99 e' achievable).

Schema validation a load time: `len(bundle.features)` deve matchare feature vector
incoming, altrimenti FeatureSchemaMismatchError (RESEARCH §Pitfall 6).

CRITICO: NON usare logging dentro questo modulo (tests/test_ml_purity.py gating).
Logging della telemetry inference live -> caller scrive su logs/ml_inference.log.
"""
from __future__ import annotations
import json
from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import numpy as np
import pandas as pd

_MODEL_CACHE: "MLFilter | None" = None
_CACHE_LOCK = Lock()
```

**Double-check lock singleton (RESEARCH §Pattern 5, verbatim):**
```python
def get_ml_filter(model_path: str | Path) -> "MLFilter":
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        with _CACHE_LOCK:
            if _MODEL_CACHE is None:
                _MODEL_CACHE = MLFilter.load(model_path)
    return _MODEL_CACHE
```

**MLFilter class (mirror CONTEXT.md §specifics lines 437-466):**
```python
class MLFilter:
    def __init__(self, bundle, metadata):
        self.model = bundle["model"]
        self.platt = bundle.get("platt")
        self.isotonic = bundle.get("isotonic")
        self.calibrator_winner = bundle.get("calibrator_winner")  # "sigmoid" | "isotonic"
        self.features: list[str] = bundle["features"]
        self.categorical_features: list[str] = bundle["categorical_features"]
        self.categorical_encodings: dict = bundle["categorical_encodings"]  # RESEARCH §Pitfall 2
        self.threshold_by_profile: dict[str, float] = bundle["threshold_by_profile"]
        self.version: str = bundle["version"]
        self.metadata = metadata

    @classmethod
    def load(cls, path) -> "MLFilter":
        bundle = joblib.load(path)
        meta_path = Path(path).with_suffix(".metadata.json")
        metadata = json.loads(meta_path.read_text())
        # Schema validation (RESEARCH §Pitfall 6): MUST raise on mismatch
        if metadata["n_features"] != len(bundle["features"]):
            raise FeatureSchemaMismatchError(
                f"n_features mismatch: meta={metadata['n_features']} bundle={len(bundle['features'])}"
            )
        return cls(bundle, metadata)

    def predict(self, X: pd.DataFrame) -> tuple[float, float]:
        """Single-sample predict: raw_score (LightGBM raw_score=True) + calibrated_prob.

        Latency budget p95 < 10ms su 1000-sample (RESEARCH §Latency Budget).
        """
        raw = float(self.model.predict(X, raw_score=True)[0])  # logit pre-calibration
        if self.calibrator_winner == "sigmoid":
            calibrated = float(self.platt.predict_proba(np.array([[raw]]))[0, 1])
        else:
            calibrated = float(self.isotonic.transform(np.array([raw]))[0])
        # Sanity check (V5 ASVS input validation, RESEARCH §Security Domain)
        if not (0.0 <= calibrated <= 1.0):
            raise ValueError(f"calibrated_prob fuori range [0,1]: {calibrated}")
        return raw, calibrated


class FeatureSchemaMismatchError(Exception):
    """Inference riceve feature schema diverso da training (RESEARCH §Pitfall 6)."""
```

---

### `ml/artifact.py` (serialization — joblib bundle + metadata.json sidecar)

**Analog 1 (shard-write + finalize):** `backtest/baseline/dataset_writer.py:87-118` (`write_decisions_shard` — shard pattern).
**Analog 2 (sidecar sha256):** `backtest/baseline/determinism.py:29-35` (`file_sha256`).
**Analog 3 (git_sha capture):** `backtest/baseline/runner.py:92-102` (`_git_sha` best-effort).

**Imports + module docstring (mirror `backtest/baseline/dataset_writer.py:1-40`):**
```python
"""Artifact persistence Phase 7 (ML-10).

joblib `compress=3` bundle (~645 KB, 39ms load — RESEARCH §Standard Stack) +
sidecar `.metadata.json` con audit trail (D-15):
  - version, train_date, git_sha, dataset_hash (sha256 64-char)
  - n_train_rows, n_features, features list, categorical_encodings (Pitfall 2)
  - fold_metrics list, calibrator_winner_per_fold, scale_pos_weight_per_fold
  - threshold_by_profile, lightgbm_version, sklearn_version

Output paths (D-15):
  - models/classifier_v{N}_{date}.pkl + .metadata.json (final)
  - models/folds/v{N}_{date}/fold_{k}.pkl + .metadata.json (10×2 = 20 file)

Modulo I/O autorizzato: scrive file (legato a path resolved esternamente),
NON usa logging proprio (caller logga write success).
"""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

import joblib
import sklearn  # per __version__
import lightgbm as lgb  # per __version__
```

**Bundle write pattern (CONTEXT.md §specifics lines 384-413):**
```python
def dump_bundle(
    bundle: dict,
    metadata: dict,
    out_path: Path,
) -> Path:
    """joblib.dump compress=3 + metadata.json sidecar (D-15).

    Mirror backtest/baseline/dataset_writer.py:87-118: shard write con path
    explicit + parent.mkdir + return path scritto.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path, compress=3)
    meta_path = out_path.with_suffix(".metadata.json")
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return out_path


def _git_sha() -> str:
    """Mirror backtest/baseline/runner.py:92-102 — best-effort, fallback 'unknown'."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def _file_sha256(path: Path) -> str:
    """Mirror backtest/baseline/determinism.py:29-35 — full 64-char hex digest."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
```

---

### `data/configs/ml.yaml` (NEW config — orchestration knobs)

**Analog:** `data/configs/baseline.yaml` + `backtest/baseline/runner.py:39-89` (`BaselineConfig` frozen + loader).

**Schema (mirror CONTEXT.md §canonical_refs lines 155-186):**
```yaml
# data/configs/ml.yaml
# Phase 7 ML training orchestration knobs (D-05/06/07/08/14/15).
# Loaded da ml.train.load_ml_training_config().

walk_forward:
  n_folds: 10                       # D-06 cap PROJECT.md
  window: expanding                 # D-05
  train_val_split_pct: 0.20         # D-08 last 20%
  embargo_bars_by_tf:               # D-07
    M15: 96
    M30: 96
    H1: 120

lightgbm:                           # Claude discretion: default hyperparams
  n_estimators: 500
  learning_rate: 0.05
  num_leaves: 31
  min_child_samples: 20
  feature_fraction: 0.9
  bagging_fraction: 0.8
  bagging_freq: 5
  early_stopping_rounds: 50

calibration:
  val_size_threshold: 50            # HANDOFF blocker #3: val<50 -> Platt-only
  winner_metric: brier              # D-18

threshold_optimization:
  sweep_min: 0.20
  sweep_max: 0.70
  sweep_step: 0.01
  objective: expectancy_pips
  aggregate: median                 # D-14 robust

inference:
  latency_budget_ms_p95: 10         # RESEARCH §Latency Budget
  benchmark_n_samples: 1000

output:
  models_dir: models
  fold_models_subdir: folds
```

---

### Test Files

#### `tests/test_ml_purity.py` (AST gate — VERBATIM clone)

**Analog:** `tests/test_strategy_purity.py:1-232` (full file).

**Recommended approach:** copy the file structure, change `PURE_MODULES` list:
```python
PURE_MODULES = [
    "ml/__init__.py",
    "ml/feature_extraction.py",
    "ml/walk_forward.py",
    "ml/calibration.py",
    "ml/threshold.py",
    "ml/inference.py",  # NB: uses joblib + threading.Lock — OK, no broker
    "ml/artifact.py",   # NB: uses subprocess for git_sha — must exempt or allowlist
]

# `ml/artifact.py` calls subprocess.check_output for git_sha — must allowlist
# OR move _git_sha to ml/train.py (orchestrator allowed to do I/O).
# Recommended: move _git_sha to train.py to keep artifact.py pure.

FORBIDDEN_IMPORTS = {  # same as strategy purity gate
    "mt5", "MetaTrader5", "mt5_client",
    "requests", "urllib", "urllib2", "urllib3", "httpx", "aiohttp", "http",
    "sqlite3",
    "subprocess",
    "logging",
}
```

**Critical decision for planner:** `ml/inference.py` uses `joblib.load` (file I/O) and `Path.read_text` (json metadata load). Both are file reads at load time, NOT in the predict path. Options:
- (A) Add `ml/inference.py` to a separate `LOAD_EXEMPT_FILES` set (mirror `OPEN_EXEMPT_FILES = {"strategy/confluence.py"}` at line 57).
- (B) Move loading logic to `ml/artifact.py::load_bundle()` and keep `MLFilter` itself I/O-free.

Recommended **(B)** — symmetric with `dump_bundle`, keeps `inference.py` pure of I/O. Then `inference.py` only logging concern is `import joblib`/`import json` at module level, which the AST gate inspects but doesn't reject (joblib + json are stdlib-ish, not in FORBIDDEN_IMPORTS).

#### `tests/test_ml_walk_forward.py`

**Analog:** `tests/test_backtest_walk_forward.py:1-62` (entire file — overlap + temporal-order asserts).

**Verbatim shape pattern** (mirror lines 50-54):
```python
def test_ml_folds_temporal_order(synthetic_df_10y):
    folds = build_ml_folds(synthetic_df_10y, n_folds=10, embargo_bars_by_tf={"M15":96,"M30":96,"H1":120})
    for train, val, test in folds:
        assert max(train) < min(val), (max(train), min(val))
        assert max(val) < min(test), (max(val), min(test))


def test_ml_folds_embargo_respected(synthetic_df_10y):
    """min(test) - max(train) >= max(embargo_bars_by_tf) = 120 (D-07)."""
    folds = build_ml_folds(synthetic_df_10y, n_folds=10, embargo_bars_by_tf={"M15":96,"M30":96,"H1":120})
    for train, _val, test in folds:
        gap = min(test) - max(train)
        assert gap >= 120, f"embargo violated: gap={gap}"


def test_no_shuffle_split_ast_guard():
    """AST guard: train_test_split(shuffle=True) MUST NOT appear in ml/."""
    import ast
    for mod_path in Path("ml").glob("*.py"):
        tree = ast.parse(mod_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "train_test_split":
                for kw in node.keywords:
                    if kw.arg == "shuffle":
                        assert ast.literal_eval(kw.value) is False, f"{mod_path}: shuffle=True forbidden"
```

#### `tests/test_ml_calibration.py`

**Analog (numerical parametrized):** `tests/test_indicators_purity.py:46-105`.

**Pattern (per-fold seed-locked invariants):**
```python
def test_platt_monotonic_in_raw():
    """Logistic regression on raw proba is monotonic by construction."""
    rng = np.random.default_rng(42)
    raw = np.sort(rng.uniform(-3, 3, 200))
    y = (raw > 0).astype(int)
    cal = platt_fit(raw, y)
    out = cal.predict_proba(raw.reshape(-1, 1))[:, 1]
    assert np.all(np.diff(out) >= -1e-9), "Platt non monotonico"

def test_isotonic_monotonic_in_raw():
    """IsotonicRegression by definition monotonic."""
    # ... same pattern

def test_ece_includes_y_prob_eq_1():
    """RESEARCH §Pitfall 5: last bin <= per includere prob=1.0."""
    y_true = np.array([0, 1, 1, 1])
    y_prob = np.array([0.5, 1.0, 1.0, 1.0])
    ece = expected_calibration_error(y_true, y_prob, n_bins=10)
    assert ece > 0, "ECE deve includere prob=1.0 nel last bin"

def test_brier_winner_val_below_50_picks_platt():
    """HANDOFF blocker #3: val<50 -> Platt forzato."""
    # ... mock raw/y_test, assert winner == "sigmoid" for val_size=20
```

#### `tests/test_ml_threshold.py`

**Pattern:**
```python
def test_profit_curve_max_at_expected_threshold():
    """Sweep su prob/pnl sintetico, argmax in posizione attesa."""
    np.random.seed(42)
    prob = np.linspace(0, 1, 1000)
    pnl_pips = np.where(prob > 0.6, 5.0, -3.0)  # winning set sopra 0.6
    sweep = np.arange(0.2, 0.7, 0.01)
    t = profit_curve_optimal_threshold(prob, pnl_pips, sweep)
    assert 0.55 <= t <= 0.65, f"expected ~0.60, got {t}"
```

#### `tests/test_ml_inference.py` — NEW benchmark pattern (no analog)

**Source (RESEARCH §Pitfall 4 + §Latency Budget):**
```python
def test_inference_latency_p95_under_10ms(tmp_path):
    """SC#4: single-sample inference p95 < 10ms su 1000-sample benchmark.

    NB: in WSL2/Docker p99 puo' essere 13-14ms per OS scheduler jitter
    (RESEARCH §Pitfall 4). Su Windows bare-metal p99 e' achievable.
    Il test usa p95, NON p99.
    """
    import time
    # Carica modello deterministico fixture (tests/fixtures/ml/sample_model.pkl)
    flt = MLFilter.load(tmp_path / "sample_model.pkl")
    X = _build_sample_features(flt.features, flt.categorical_encodings)
    latencies = []
    for _ in range(1000):
        t0 = time.perf_counter()
        flt.predict(X)
        latencies.append((time.perf_counter() - t0) * 1000)
    p95 = np.percentile(latencies, 95)
    assert p95 < 10.0, f"p95={p95:.2f}ms > 10ms (latenza fuori budget)"


def test_predict_returns_raw_and_calibrated(sample_filter, sample_features):
    raw, calibrated = sample_filter.predict(sample_features)
    assert isinstance(raw, float)
    assert 0.0 <= calibrated <= 1.0
```

#### `tests/test_ml_feature_extraction.py`

**Pattern (snapshot + D-09-G derivation):**
```python
def test_derive_d_09_g_fields_from_ctx_json():
    """8 D-09-G fields derivati correttamente da ctx + pnl_pips + timestamps."""
    row = pd.Series({
        "decision_context_json": json.dumps({"setup_name": "A_breakout", "direction": "BUY", "factors": {...}}),
        "entry_price": 1.1000, "sl": 1.0980, "tp": 1.1040,
        "pnl_pips": 40.0,
        "entry_ts_utc": "2024-01-01T10:00:00+00:00",
        "exit_ts_utc":  "2024-01-01T14:00:00+00:00",
        "timeframe": "M15", "symbol": "EURUSD",
    })
    derived = derive_d_09_g_fields(row)
    assert derived["setup_name"] == "A_breakout"
    assert derived["bias"] == "BUY"
    assert abs(derived["sl_pips"] - 20.0) < 1e-6
    assert abs(derived["tp_pips"] - 40.0) < 1e-6
    assert abs(derived["r_to_r"] - 2.0) < 1e-6
    assert derived["bars_to_outcome"] == 16  # 4 hours × 4 M15 bar/hour
```

---

### `strategy/__init__.py` (MODIFY — ml_filter kwarg + prediction step)

**Analog:** self — `strategy/__init__.py:61-103` (existing `evaluate_proposal_for_bar`).

**Current shape (lines 61-65):**
```python
def evaluate_proposal_for_bar(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
```

**Phase 7 extension (D-12, additive kwarg, default None — backward compat):**
```python
def evaluate_proposal_for_bar(
    bars: list,
    indicators,
    ctx: StrategyContext,
    ml_filter: "MLFilter | None" = None,   # NEW Phase 7 (D-12, additive)
) -> ProposalDraft:
    """[... docstring esistente ...]

    Phase 7 (D-12): se `ml_filter` is not None, dopo la selezione del winner
    annota draft.ml_raw_score + draft.ml_calibrated_prob + draft.ml_model_version.
    Strategy NON filtra mai sul ML score (D-12 split): il filtering avviene in
    risk_engine.evaluate_trade (CLAUDE.md unico gate).
    """
    drafts = [detect(bars, indicators, ctx) for detect in ALL_DETECTORS]
    # ... existing winner selection (lines 77-103) invariato ...
    winner_with_losers = replace(winner, setup_specific=new_specific)

    # Phase 7 prediction step (no decision, no I/O nel happy path — solo lookup)
    if ml_filter is not None:
        try:
            from ml.feature_extraction import build_feature_vector
            X = build_feature_vector(
                winner_with_losers, indicators, ctx,
                feature_list=ml_filter.features,
                cat_encodings=ml_filter.categorical_encodings,
            )
            raw, calibrated = ml_filter.predict(X)
            winner_with_losers = replace(
                winner_with_losers,
                ml_raw_score=raw,
                ml_calibrated_prob=calibrated,
                ml_model_version=ml_filter.version,
            )
        except Exception:
            # Warning bubble (NB: nessun log dentro pure-fn — eccezione swallowata,
            # adapters live/backtest possono loggare). Drafts senza ml_* fields
            # passano dritti -> risk_engine skip ML gate per `ml_calibrated_prob is None`.
            pass

    return winner_with_losers
```

**Critical:** the ML predict exception swallow is NECESSARY per the purity gate (no logging in pure-fn). Adapters (`strategy/adapters/live.py`, `strategy/adapters/backtest.py`) wrap `evaluate_proposal_for_bar` and log the failure — this is the I/O bridge per design.

---

### `strategy/proposal.py` (MODIFY — additive `ProposalDraft` fields)

**Analog:** self — `strategy/proposal.py:22-44` (existing frozen dataclass + `__post_init__`).

**Add 3 fields (D-13, additive, default None — pure additive, backward-compat):**
```python
@dataclass(frozen=True)
class ProposalDraft:
    setup_type: Literal["READY", "FORMING", "NONE"]
    # ... 11 esistenti invariati ...
    setup_specific: dict | None = None
    # Phase 7 additions (D-13, additive, default None)
    ml_raw_score: float | None = None
    ml_calibrated_prob: float | None = None
    ml_model_version: str | None = None
```

`__post_init__` invariato (i nuovi field sono già `None`-safe primitive).

---

### `risk_engine.py` (MODIFY — ML threshold gate)

**Analog:** self — `risk_engine.py:32-156` (entire function). The closest pattern within is `reject()` closure (lines 44-52) + gate sequence numbering (lines 54, 65, 74, 96, ...).

**Phase 7 gate insertion** (D-12 decision step, AFTER classic gates 1-7, BEFORE final `approved=True`):
```python
def evaluate_trade(
    proposal: TradeProposal,
    account: AccountState,
    mt5_client: Mt5Client,
    cfg: Config | None = None,
) -> RiskDecision:
    # ... gates 1-7 esistenti invariati (risk_engine.py:54-146) ...

    # 8. ML threshold gate (Phase 7 D-12, additive — solo se modello attivo + score presente)
    ml_calibrated = getattr(proposal, "ml_calibrated_prob", None)
    if cfg.ENABLE_ML_FILTER and ml_calibrated is not None:
        # cfg.ML_THRESHOLD_BY_PROFILE caricato a bootstrap da metadata.json
        thresholds = cfg.ML_THRESHOLD_BY_PROFILE or {}
        threshold = float(thresholds.get(cfg.RISK_MODE.upper(), 0.5))
        if ml_calibrated < threshold:
            return reject(
                f"ml_prob_below_threshold: {ml_calibrated:.3f} < {threshold:.3f} "
                f"(profile={cfg.RISK_MODE})"
            )

    # 9. Approved (line 148-155 invariato)
    return RiskDecision(approved=True, ...)
```

**Key shape choices (mirror existing risk_engine.py patterns):**
- Uses `reject(reason: str)` closure (line 44) — preserves italiano log format `"Trade rifiutato: %s"` (line 45).
- Reason format `"ml_prob_below_threshold: <val> < <th> (profile=<P>)"` echoes existing `f"Kill switch giornaliero attivo: drawdown {actual_pct:.1f}% > {cfg.MAX_DAILY_DRAWDOWN_PERCENT:.1f}%"` (line 62) — same "code: detail" structure.
- `getattr(proposal, "ml_calibrated_prob", None)` defensive on existing `TradeProposal` — the field is on `ProposalDraft` (Phase 4), not on `models.TradeProposal` (Phase 1 dataclass). Planner: decide whether to add the 3 ml_* fields to `models.TradeProposal` as well, OR to pass them through `draft_to_trade_proposal` (Phase 4 adapter `strategy/proposal.py:52-91`) by extending the converter signature.

---

### `config.py` (3 new env vars)

**Analog:** self — `config.py:100-107` (existing Phase 6 MCP block — closest stylistic match).

**Phase 7 additions block (mirror lines 100-107):**
```python
class Config:
    # ... existing 100+ env vars ...

    # Phase 7 ML (D-12, D-14, D-20)
    ENABLE_ML_FILTER: bool = _get_bool("ENABLE_ML_FILTER", False)  # default False finché modello non disponibile
    ML_MODEL_PATH: str = os.getenv("ML_MODEL_PATH", "")            # vuoto -> ML filter disabilitato
    ML_INFERENCE_LATENCY_BUDGET_MS: int = int(os.getenv("ML_INFERENCE_LATENCY_BUDGET_MS", "10"))
    # ML_THRESHOLD_BY_PROFILE: dict caricato a bootstrap da metadata.json
    # (NON env-driven: i threshold sono training output, non config user-editable).
    # Es. {"CONSERVATIVE": 0.55, "MODERATE": 0.45, "AGGRESSIVE": 0.35}
    ML_THRESHOLD_BY_PROFILE: dict[str, float] = {}                 # popolato da bootstrap loader
```

**Bootstrap helper (NEW small fn in `config.py` o `main.py`):**
```python
def load_ml_thresholds_from_metadata(cfg: Config) -> None:
    """Una tantum a bootstrap: legge metadata.json e popola ML_THRESHOLD_BY_PROFILE."""
    if not cfg.ML_MODEL_PATH:
        return
    meta_path = Path(cfg.ML_MODEL_PATH).with_suffix(".metadata.json")
    if not meta_path.exists():
        return
    metadata = json.loads(meta_path.read_text())
    cfg.ML_THRESHOLD_BY_PROFILE = metadata.get("threshold_by_profile", {})
```

**Match quality:** exact — uses existing `_get_bool` helper (config.py:7-11) and `os.getenv` pattern (line 62).

---

### `.env.example` (3 new vars)

**Analog:** existing `.env.example` block layout — group by phase comment + key=value.

**Phase 7 block:**
```
# Phase 7 ML
ENABLE_ML_FILTER=false
ML_MODEL_PATH=
ML_INFERENCE_LATENCY_BUDGET_MS=10
```

---

## Shared Patterns (Cross-Cutting)

### Pattern A — `from __future__ import annotations` + PEP 604

**Source:** Every Phase 4/5 module — `strategy/__init__.py:20`, `backtest/baseline/runner.py:13`, `strategy/proposal.py:14`.
**Apply to:** ALL new `ml/*.py` and `tests/test_ml_*.py` files.

### Pattern B — Frozen dataclass + YAML loader

**Source:** `backtest/baseline/runner.py:39-89` (`BaselineConfig` + `load_baseline_config`).
**Apply to:** `ml/train.py::MLTrainingConfig` + `data/configs/ml.yaml` loader.

```python
@dataclass(frozen=True)
class MLTrainingConfig: ...
def load_ml_training_config(yaml_path: Path) -> MLTrainingConfig: ...
```

### Pattern C — Module-level logger, italiano log, `%`-style lazy interp

**Source:** `backtest/baseline/runner.py:33` (`_log = logging.getLogger(__name__)`), `risk_engine.py:10`, `backtest/baseline/slice_worker.py:39`.
**Apply to:** `ml/train.py`, `ml/artifact.py` (the I/O-allowed modules). NEVER inside `ml/feature_extraction.py`, `ml/walk_forward.py`, `ml/calibration.py`, `ml/threshold.py`, `ml/inference.py` — purity gate would reject.

### Pattern D — AST purity gate (verbatim from `tests/test_strategy_purity.py`)

**Source:** `tests/test_strategy_purity.py:1-232` (full file).
**Apply to:** `tests/test_ml_purity.py` — clone file, change `PURE_MODULES` list to `ml/*.py` (excluding `ml/train.py` which is the I/O-orchestrator, analog to `strategy/adapters/`).

The 4 test functions (`test_strategy_purity_no_forbidden_imports`, `test_strategy_purity_no_logging_calls`, `test_strategy_purity_no_print_calls`, `test_pure_modules_all_exist`) port one-to-one with module list swap.

### Pattern E — Italiano docstrings + commenti + log

**Source:** CLAUDE.md §Convenzioni. Reference: `risk_engine.py:54-148` numbered Italian comments, `strategy/__init__.py:66-74` Italian docstring with D-numbered decision references.
**Apply to:** All new modules. English allowed for type names/kwargs; user-facing log messages + module docstring + inline rationale in Italian.

### Pattern F — `sklearn`/`joblib` versioned in metadata for reproducibility

**Source:** `backtest/baseline/dataset_writer.py` style (programmatic schema introspection at import time). For ML: capture `lgb.__version__` + `sklearn.__version__` + `joblib.__version__` at training time, persist to metadata.json. RESEARCH §Pitfall 6 (feature schema drift) — same idea applied to library versions.

### Pattern G — `additive` schema extension (default None, backward-compat)

**Source:** `backtest/engine.py:91-103` (Phase 5 extended Phase 1 constructor with `indicators_full=None, risk_profile=None, timeout_bars=None, equity_initial=None` — all default None). `strategy/proposal.py:22-44` (frozen dataclass with optional fields).
**Apply to:**
- `ProposalDraft` (add 3 ml_* default None — Phase 5 backtest gira pre-ML senza problema).
- `evaluate_proposal_for_bar(ml_filter=None)` kwarg.
- `risk_engine.evaluate_trade` (ML gate behind `cfg.ENABLE_ML_FILTER and ml_calibrated is not None`).

### Pattern H — Single shared call site (Phase 4 D-09)

**Source:** `strategy/__init__.py:14-19` docstring "Single shared call site (D-09): build_ctx_live e build_ctx_backtest entrambi producono StrategyContext, evaluate_proposal_for_bar e' chiamato identicamente."
**Apply to:** ML predict integration happens ONCE in `evaluate_proposal_for_bar`. Adapters `strategy/adapters/live.py::build_ctx_live` and `strategy/adapters/backtest.py::build_ctx_backtest` (lines 21-76) need NO changes — they only build `StrategyContext`, not the ml_filter. The `ml_filter` is passed by the caller (scheduler for live, BacktestEngine for backtest) directly to `evaluate_proposal_for_bar`. Single integration site keeps live/backtest divergence at zero.

### Pattern I — `pytest tmp_path` for SQLite/file fixtures

**Source:** `tests/test_backtest_ledger.py:26-37`.
**Apply to:** `tests/test_ml_train.py` (dataset fixture → tmp_path artifact), `tests/test_ml_inference.py` (model file → tmp_path).

### Pattern J — JSON-serializable metadata (compat with downstream Phase 8/9 consumers)

**Source:** `backtest/baseline/runner.py:230-245` (`meta` dict with explicit `cli_command`, `git_sha`, `*_sha256` keys).
**Apply to:** `ml/artifact.py::dump_bundle` metadata dict. Phase 8 MCP tool `get_ml_calibration` will read this; Phase 9 drift monitor will consume `fold_metrics`. Both must remain JSON-parseable (no numpy floats — cast to Python `float`, no datetime — use ISO strings).

---

## No Analog Found (NEW Patterns)

Three areas have no in-repo analog. RESEARCH.md provides vetted source patterns for each — planner adopts those directly:

| File | Role | Why no analog | Source pattern |
|------|------|---------------|----------------|
| `ml/train.py` LightGBM fold body | service / training | First LightGBM usage in repo | RESEARCH §Pattern 1 lines 246-278 (verified verbatim) |
| `ml/calibration.py` sklearn manual calibration | pure-fn | sklearn 1.8 removed `cv='prefit'` — CONTEXT.md skeleton broken | RESEARCH §Pattern 2 lines 290-313 (verified runtime) |
| `ml/threshold.py` profit-curve sweep | pure-fn | First decision-time sweep solver in repo | RESEARCH §Pattern 6 lines 465-485 + CONTEXT.md §specifics lines 561-572 |
| `tests/test_ml_inference.py` latency benchmark | test (benchmark) | First p95-latency test in repo | RESEARCH §Pattern 4 + §Pitfall 4 lines 622-632 (verified WSL2 measurements) |

---

## Notes for planner

Surface these gotchas in plan files so Wave assignments reflect reality, not the CONTEXT.md skeleton:

1. **D-09-G derivation is a hard Wave 0 task.** The 8 fields `setup_name, pattern_name, confluence_factors_json, bias, sl_pips, tp_pips, r_to_r, bars_to_outcome` were DEFERRED from Plan 05-09 parquet (D-09-G). They are NOT raw columns — they MUST be derived in `ml/feature_extraction.py` from `decision_context_json` + `pnl_pips` + `entry_ts_utc`/`exit_ts_utc` + symbol pip_size lookup. The planner must allocate a Wave 0 / Wave 1 task BEFORE the train/calibrate tasks — without these 8 fields, the feature matrix is incomplete and ML-01 cannot be marked complete.

2. **Fold-1 val ≈ 20 rows on 1076 dataset / 10 folds.** Isotonic calibration on < 50 samples is unreliable (HANDOFF.json blocker #3 + RESEARCH §Pattern 2). `ml/calibration.py::pick_brier_winner` MUST force Platt (sigmoid) when `val_size < val_size_threshold` (default 50, in `ml.yaml::calibration.val_size_threshold`). Test `test_brier_winner_val_below_50_picks_platt` is mandatory.

3. **Latency p95 < 10ms locked.** Benchmark must be 1000-sample on `tests/test_ml_inference.py::test_inference_latency_p95_under_10ms`. RESEARCH measured p50=4ms, p95=9ms, p99=13ms in WSL2. Use p95, NOT p99 (RESEARCH §Pitfall 4 — OS scheduler jitter inflates p99 in Linux container). Add `num_threads=1` to LightGBM model config for deterministic single-sample latency.

4. **sklearn 1.8.0 removed `CalibratedClassifierCV(cv='prefit')`.** CONTEXT.md §specifics lines 316-319 will raise `InvalidParameterError` at runtime. RESEARCH.md §Pattern 2 has the manual replacement (verified). Planner MUST adopt manual `LogisticRegression`/`IsotonicRegression` fit on raw `predict_proba` outputs. Skeleton in CONTEXT is outdated — RESEARCH overrides.

5. **`ml/` package MUST pass AST purity gate.** No broker imports (`mt5`, `MetaTrader5`), no `sqlite3`, no `logging`, no `subprocess` in pure modules. Allowed I/O exceptions: `ml/train.py` (orchestrator, mirror `strategy/adapters/` exemption — exclude from gate's `PURE_MODULES`), `ml/artifact.py` (file I/O is its job — exclude OR allowlist `joblib`/`json`). `ml/inference.py` should delegate file loading to `ml/artifact.py::load_bundle` to remain in `PURE_MODULES`.

6. **Single integration point in `strategy/__init__.py::evaluate_proposal_for_bar`.** Both live (`adapters/live.py::build_ctx_live`) and backtest (`adapters/backtest.py::build_ctx_backtest`) call `evaluate_proposal_for_bar` identically. ML attach happens there ONCE (Phase 4 D-09 single shared call site preserved). `risk_engine.py::evaluate_trade` is the unique decision gate (CLAUDE.md "risk_engine = unico gate"). Do NOT add ML logic in adapters or in scheduler.

7. **Categorical encoding maps MUST be persisted in metadata.json** (RESEARCH §Pitfall 2). Training-time `pd.Categorical.cat.codes` ordering depends on insertion order — at inference time with a fresh DataFrame, codes could differ silently and produce wrong predictions. `ml/feature_extraction.py::build_categorical_encodings` builds the map; `ml/artifact.py::dump_bundle` writes it to metadata; `ml/inference.py::MLFilter.__init__` reads it and `build_feature_vector` applies it via `mapping.get(value, -1)` (unknown → -1 → LightGBM treats as NaN).

8. **Feature schema validation at load time** (RESEARCH §Pitfall 6). `MLFilter.load` MUST raise `FeatureSchemaMismatchError` if `len(bundle["features"]) != metadata["n_features"]` or if incoming feature list at predict time doesn't match `bundle["features"]`. Otherwise the latent bug surfaces only after Phase 9 retraining adds a new indicator.

9. **The `ml_filter` is loaded once at bootstrap, not per call.** Singleton + `threading.Lock` double-check pattern (RESEARCH §Pattern 5). ProcessPoolExecutor workers (Phase 6 D-A1 + future ML batch jobs) each fork with `_MODEL_CACHE = None` and load their own copy on first predict — fork-safe because joblib bundles are pickle-able.

10. **Threshold values are TRAINING OUTPUT, not env-driven config.** `ML_THRESHOLD_BY_PROFILE` in `config.py` is populated at bootstrap by reading `metadata.json` (RESEARCH §Standard Stack — pattern J above). User cannot edit thresholds via `.env`. Phase 9 drift monitor can trigger retrain → new metadata.json → bootstrap reloads new thresholds.

---

## Metadata

**Analog search scope:**
- `strategy/` (all 8 .py files: `__init__.py`, `confluence.py`, `proposal.py`, `context.py`, `_shim.py`, `risk_utils.py`, `adapters/{live,backtest}.py`)
- `backtest/` (`walk_forward.py`, `engine.py`, `loader.py`, `costs.py`, `ledger.py`, `metrics.py`) + `backtest/baseline/` (all 9 modules: `runner.py`, `slice_worker.py`, `dataset_writer.py`, `determinism.py`, `wal_setup.py`, `plot_writer.py`, `report_writer.py`, `warmup.py`, `__init__.py`)
- `indicators/__init__.py` + `indicators/momentum.py` (barrel pattern + dataclass result pattern)
- Root: `risk_engine.py`, `config.py`, `logger.py`, `mt5_client.py`, `models.py`
- Scripts: `scripts/run_baseline_backtest.py`, `scripts/run_baseline_05_09.py`, `scripts/dry_run_cycle.py`
- Tests: `tests/conftest.py`, `tests/test_strategy_purity.py`, `tests/test_indicators_purity.py`, `tests/test_backtest_walk_forward.py`, `tests/test_backtest_ledger.py`

**Files scanned in detail:** 18 (full read of 12, partial targeted of 6 large files via offset/limit).

**Pattern extraction date:** 2026-05-12

**Project convention sources:** `CLAUDE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONVENTIONS.md`, `.planning/phases/07-ml-classifier/07-CONTEXT.md` (locked decisions D-01..D-20), `.planning/phases/07-ml-classifier/07-RESEARCH.md` (verified patterns + pitfalls).

---

## PATTERN MAPPING COMPLETE

**Phase:** 7 - ml-classifier
**Files classified:** 20
**Analogs found:** 17 / 20

### Coverage
- Files with exact analog: 7 (init, proposal extend, walk_forward, walk_forward test, purity test, config extend, env.example, ml.yaml)
- Files with role-match analog: 10 (feature_extraction, train orchestration, calibration shape, threshold shape, inference singleton, artifact, evaluate_proposal_for_bar extend, risk_engine extend, train/threshold tests, feature_extraction test)
- Files with NEW patterns from RESEARCH: 3 (LightGBM training loop, sklearn manual calibration, profit-curve sweep) + 1 NEW test pattern (latency benchmark)

### Key Patterns Identified
- All `ml/*.py` pure-fn modules pass the AST purity gate cloned from `tests/test_strategy_purity.py:1-232` (no broker/log/IO).
- `ml.yaml` + `MLTrainingConfig` frozen dataclass + loader exactly mirror `data/configs/baseline.yaml` + `BaselineConfig` (Phase 5 pattern).
- Walk-forward fold builder extends `backtest/walk_forward.py:54-59` expanding mode with per-TF embargo (RESEARCH §Pattern 3).
- ML integration is single-site: `evaluate_proposal_for_bar` (prediction) + `risk_engine.evaluate_trade` (decision) — adapters live/backtest unchanged (Phase 4 D-09 preserved).
- sklearn 1.8 manual calibration replaces deprecated `CalibratedClassifierCV(cv='prefit')` — CONTEXT.md skeleton lines 316-319 outdated; RESEARCH.md §Pattern 2 overrides.

### File Created
`.planning/phases/07-ml-classifier/07-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files. The 10 notes-for-planner gotchas at the end surface the non-obvious traps (D-09-G derivation, fold-1 val<50, latency p95 not p99, sklearn 1.8 break, purity gate scope, single integration point, encoding maps persisted, schema validation at load, singleton fork-safety, thresholds-are-training-output).
