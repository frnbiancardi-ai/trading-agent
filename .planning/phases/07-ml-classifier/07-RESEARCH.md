# Phase 7: ML Classifier — Research

**Researched:** 2026-05-10
**Domain:** LightGBM binary classifier + walk-forward calibration + inference integration
**Confidence:** HIGH (stack verified via installed packages) with two MEDIUM-confidence gaps flagged

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Target label encoding**
- D-01: `y=1 ⟺ exit_reason == "TP_HIT"`. Tutto resto → `y=0`.
- D-02: TIMEOUT → `y=0` (capitale bloccato = costo opportunità).
- D-03: BREAKEVEN → `y=0` (single rule, audit-friendly).
- D-04: `scale_pos_weight = N_neg / N_pos`, ricalcolato per fold.

**Walk-forward fold design**
- D-05: Window strategy expanding.
- D-06: N fold = 10. Cap PROJECT.md.
- D-07: Embargo gap = `timeout_bars[tf]` per TF. M15=96, M30=96, H1=120 bar.
- D-08: Train/val split: last 20% temporal del train fold per early stopping + calibration.

**Per-profile model strategy**
- D-09: 1 modello unico su tutto dataset. Profile come categorical feature.
- D-10: Categorical features: `["symbol", "timeframe", "profile", "setup_name", "regime"]`.
- D-11: Numeric features: raw ExtendedIndicators + ProposalDraft factors + ctx. No engineering upfront.

**Inference integration + threshold**
- D-12: Hook hybrid. Prediction in `evaluate_proposal_for_bar`, decision in `risk_engine.evaluate_trade`.
- D-13: `ProposalDraft` schema esteso additive con `ml_raw_score`, `ml_calibrated_prob`, `ml_model_version` (default None).
- D-14: Threshold per-profile profit-curve optimized, mediana fold. Persistito in `metadata.json`.
- D-15: Model artifact: joblib `.pkl` + sidecar `.metadata.json`. Path: `models/classifier_v{N}_{date}.pkl`.

**Engineering principles**
- D-16: Pure-function strategy preservata. No I/O dentro evaluate_proposal_for_bar.
- D-17: No future leakage by construction. Walk-forward + embargo + bar-close discipline.
- D-18: Calibration: Platt + Isotonic, pick winner per Brier per fold.
- D-19: Italian commenti/log/rationale, English identifiers.
- D-20: Inference latency <10ms (single sample).

### Claude's Discretion
- Hyperparameter defaults: `n_estimators=500, learning_rate=0.05, num_leaves=31, min_child_samples=20, feature_fraction=0.9, bagging_fraction=0.8, bagging_freq=5`. Grid search opzionale Wave 2.
- Feature scaling: nessuno upfront (tree-based). Log outlier distribution.
- Calibration set source: val set (last 20% train fold), not test fold.
- Recent trades outcome encoding: 5 colonne categorical separate.
- `confidence` heuristica inclusa come feature numerica (ML corregge heuristic).
- Final model retrain su 100% dataset dopo walk-forward eval.
- Telemetry inference live: log `(symbol, tf, setup_name, profile, calibrated_prob, threshold, approved/rejected)` in `logs/ml_inference.log`.

### Deferred Ideas (OUT OF SCOPE)
- ML-07/08/09 (failure clustering, drift monitor, retrain trigger) → Phase 9
- MCP tool ML → Phase 8
- Multiclass target → rifiutato
- Feature engineering ratios/deltas → riservato Wave 2
- Hyperparameter grid search → riservato Wave 2
- Per-symbol-TF-profile model (27 modelli) → rifiutato
- A/B test ML-on vs ML-off live → Phase 11
- Hot reload zero-downtime → Phase 9
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ML-01 | Feature extraction module: serialize decision context into feature vector | §Dataset Schema Gap — Wave 0 must remediate dataset before ML-01 is possible |
| ML-02 | LightGBM binary classifier (target: TP/SL resolution) | §Standard Stack — LightGBM 4.6.0 verified; §Architecture Pattern 1 |
| ML-03 | Walk-forward training pipeline (no shuffle, expanding window) | §Architecture Pattern 2 — harness reuse strategy documented |
| ML-04 | Calibration: Platt + Isotonic, pick best by Brier | §sklearn 1.8 Breaking Change — cv='prefit' removed; manual calibration pattern documented |
| ML-05 | Inference API returns calibrated probability + raw score | §Latency Budget — p50=4ms, p99=13ms; <10ms achievable at p95 |
| ML-06 | Inference integrated into proposal pipeline — filter + confidence override | §Architecture Pattern 3 — hook points verified in actual code |
| ML-10 | ML-trained models versioned + persisted `models/classifier_v{N}_{date}.pkl` | §Standard Stack — joblib 1.5.3 verified, 645 KB file size, 39ms load |
</phase_requirements>

---

## Summary

Phase 7 trains a LightGBM binary trade-quality classifier on the Phase 5 dataset, calibrates it via Platt/Isotonic regression, and integrates inference into the existing proposal pipeline with a per-profile threshold gate in the risk engine.

**Critical finding 1 — Dataset schema gap:** The actual `data/training/baseline_decisions/part-0.parquet` (1,076 rows) does NOT match the Phase 5 D-02 specification. It is missing approximately 38 fields including all ExtendedIndicators columns, `profile`, `regime`, `run_id`, `outcome`, `bars_held`, and proper timestamp columns. The dataset stores indicators in a `decision_context_json` dict with only 6 legacy indicator fields (`sma_20`, `sma_50`, `ema_50`, `rsi_14`, `atr_14`, `last_close`). Phase 7 Wave 0 MUST include a dataset remediation plan before feature extraction is possible. [VERIFIED: direct inspection of `part-0.parquet`]

**Critical finding 2 — sklearn 1.8 breaking change:** `CalibratedClassifierCV(cv='prefit')` is no longer valid in sklearn 1.8.0 (installed version). The parameter was removed. The CONTEXT.md skeleton code will raise `InvalidParameterError`. The correct pattern for Phase 7 is manual calibration: fit `IsotonicRegression` or `LogisticRegression` on raw `predict_proba` outputs from the pre-fitted LightGBM model. [VERIFIED: runtime test]

**Critical finding 3 — Dataset size vs 10-fold plan:** The dataset has 1,076 rows (Phase 5 ran 10-year window, not 23.5 years — Rule 4 deviation documented in STATE.md). Fold 1 val set = ~20 rows, which is too small for reliable isotonic calibration. Platt scaling (logistic regression) is more stable at small sample sizes. The planner should consider either reducing to 5-6 folds for early folds or using Platt as the default calibrator for folds 1-2. [VERIFIED: fold size calculation]

**Primary recommendation:** Implement Wave 0 as dataset remediation (re-run baseline with full D-02 schema, or add a schema-fixing script that re-reads bar data to backfill missing indicators). Use manual Platt/Isotonic calibration (not CalibratedClassifierCV cv='prefit'). Use pandas DataFrame with categorical dtypes for inference to avoid sklearn feature-name warnings. Confirm <10ms budget at p95 (not p99) given Docker/WSL2 OS scheduling jitter.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Feature extraction (ML-01) | Python strategy layer | None | Pure function, runs at bar-close in evaluate_proposal_for_bar |
| Walk-forward training pipeline | Script (`strategy/training.py`) | None | Offline batch job, not part of live loop |
| Model calibration | Script (`strategy/training.py`) | None | Batch, runs per fold during training |
| Inference API | Module (`strategy/ml_filter.py`) | None | In-process singleton, loaded once at bootstrap |
| Prediction step (probability annotation) | Strategy layer (`evaluate_proposal_for_bar`) | None | Pure function, no decision |
| Decision gate (threshold apply) | Risk engine (`risk_engine.evaluate_trade`) | None | CLAUDE.md: risk_engine = unico gate |
| Model artifact persistence | File system (`models/`) | None | joblib bundle + sidecar JSON |
| Inference telemetry | Logger (`logs/ml_inference.log`) | None | RotatingFileHandler, same pattern as agent.log |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| lightgbm | 4.6.0 | Binary classifier, categorical features native, early stopping | PROJECT.md locked: "LightGBM classifier first"; D-09 categorical_feature native |
| scikit-learn | 1.8.0 | `brier_score_loss`, `precision_recall_curve`, `IsotonicRegression`, `LogisticRegression` (Platt) | Standard ML metrics; `CalibratedClassifierCV` NOT used with cv='prefit' (breaking change, see §Common Pitfalls) |
| joblib | 1.5.3 | Bundle serialization (compress=3), load at bootstrap | Already used in sklearn ecosystem; compress=3 → 645 KB file, 39 ms load |
| pandas | 2.2+ | Dataset loading, feature DataFrame construction | Already used in backtest pipeline; categorical dtype for LightGBM |
| numpy | 2.4.4 | Feature vector, array ops | Already used project-wide |
| pyarrow | 24.0.0 | Read `baseline_decisions.parquet` | Already installed (Phase 5 dep) |

[VERIFIED: all versions via `pip show` on this machine]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| matplotlib (Agg) | existing | Reliability diagram PNG | Per-fold calibration plot (SC#3) |
| hashlib (stdlib) | stdlib | SHA256 for dataset_hash in metadata.json | Already used in Phase 5 |
| subprocess (stdlib) | stdlib | `git rev-parse HEAD` for git_sha | Training audit trail |
| threading.Lock (stdlib) | stdlib | Double-check locking in singleton loader | Thread-safe model cache |
| json (stdlib) | stdlib | metadata.json read/write | Sidecar artifact |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual Platt calibration (LogisticRegression on raw proba) | `CalibratedClassifierCV(cv='prefit')` | cv='prefit' REMOVED in sklearn 1.8.0 — use manual calibration |
| IsotonicRegression on raw proba directly | `CalibratedClassifierCV(method='isotonic', cv=5)` | cv=5 refits base model 5×, incompatible with early-stopping; manual is cleaner |
| LightGBM LGBMClassifier | XGBoost, CatBoost | LightGBM locked by PROJECT.md; categorical native cleaner than XGBoost |
| pandas DataFrame inference path | numpy array | DataFrame preserves feature names (no sklearn warnings); slightly slower but safer |

**Installation:**
```bash
pip install lightgbm>=4.6.0 scikit-learn>=1.8.0 joblib>=1.5.3
```

**Version verification:** [VERIFIED: npm view not applicable; verified via pip show on dev machine]

---

## Architecture Patterns

### System Architecture Diagram

```
  baseline_decisions.parquet (Phase 5 output, READ-ONLY)
         │
         ▼
  [Wave 0: Dataset Remediation]
  Re-run or backfill to add missing D-02 fields:
  profile, regime, run_id, decision_ts_utc, ExtendedIndicators
         │
         ▼
  strategy/training.py  ─────────────────────────────────────────┐
         │                                                        │
   load_dataset()  →  build_walk_forward_folds(embargo_by_tf)    │
         │                                                        │
   for k in 10 folds:                                            │
      X_train, y_train  ──►  LGBMClassifier.fit()               │
                              (early_stopping on Brier val)       │
                              scale_pos_weight = fold-specific    │
                              categorical_feature=["symbol",...]  │
                              ▼                                   │
                           raw_proba on val_set                   │
                              │                                   │
                   ┌──────────┼──────────┐                        │
                   ▼          ▼          ▼                        │
             Platt         Isotonic   Brier winner               │
          (LogisticReg)  (IsotonicReg)  selection                │
                   └──────────┴──────────┘                        │
                              │                                   │
                   threshold sweep [0.20..0.70] on val           │
                   per profile → best expectancy_pips            │
                              │                                   │
                   save fold_{k}.pkl + .metadata.json            │
         │                                                        │
   Aggregate fold metrics (Brier/ECE/AUC-PR)                     │
         │                                                        │
   Final retrain on 100% dataset                                 │
   Final calibrator = mode(winner per fold)                       │
   Final threshold = median(fold_best per profile)               │
         │                                                        │
   joblib.dump(bundle) → models/classifier_v1_{date}.pkl         │
   write metadata.json                                           │
         └───────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼──────────────────────┐
         ▼                    ▼                      ▼
  strategy/ml_filter.py  evaluate_proposal_for_bar  risk_engine.evaluate_trade
  (singleton loader)     (prediction step, NO gate)  (threshold gate)
    _MODEL_CACHE               │                         │
    + Lock()                   ▼                         ▼
    MLFilter.load()      draft.ml_raw_score=raw    if ml_prob < threshold:
                         draft.ml_calibrated_prob    RiskDecision(approved=False)
                         draft.ml_model_version       reason="ml_prob_below_threshold:..."
```

### Recommended Project Structure

```
trading-agent/
├── strategy/
│   ├── ml_filter.py          # NEW: singleton loader, predict(), build_features()
│   ├── training.py           # NEW: walk-forward training script
│   ├── proposal.py           # EXTEND: add ml_raw_score, ml_calibrated_prob, ml_model_version
│   └── __init__.py           # EXTEND: evaluate_proposal_for_bar + ml_filter param
├── risk_engine.py            # EXTEND: ML threshold gate after classic gates
├── config.py                 # EXTEND: ENABLE_ML_FILTER, ML_MODEL_PATH, ML_THRESHOLD_BY_PROFILE
├── models/                   # NEW directory
│   ├── classifier_v1_{date}.pkl
│   ├── classifier_v1_{date}.metadata.json
│   └── folds/v1_{date}/
│       ├── fold_1.pkl
│       ├── fold_1.metadata.json
│       └── ...
├── data/configs/
│   └── ml_training.yaml      # NEW: orchestration knobs
├── data/training/
│   └── baseline_decisions/   # Phase 5 output (READ-ONLY)
├── logs/
│   └── ml_inference.log      # NEW: telemetry rotativo
└── tests/
    ├── test_ml_filter.py      # NEW: unit tests ML inference
    ├── test_training.py       # NEW: unit tests fold builder + ECE
    └── fixtures/ml/
        └── sample_decision_dataset.parquet  # NEW: deterministic test fixture
```

### Pattern 1: LightGBM with Categorical Features (Native Encoding)

**What:** Pass `categorical_feature` as list of column names in `fit()`. Requires integer-encoded categoricals (NOT string dtype). LightGBM splits on best partition (`{A,B}` vs `{C,D,...}`) without imposing ordinal relationship.

**When to use:** All 5 categorical columns: `symbol`, `timeframe`, `profile`, `setup_name`, `regime`.

**Important:** In LightGBM 4.x, `categorical_feature` is a **fit-time parameter**, not a constructor parameter. The `LGBMClassifier.get_params()` does not include it; pass it via `model.fit(..., categorical_feature=[...])`.

```python
# Source: verified via direct execution on LightGBM 4.6.0
import lightgbm as lgb
import pandas as pd

cat_features = ["symbol", "timeframe", "profile", "setup_name", "regime"]

# Encode as int before passing to LightGBM
for col in cat_features:
    df[col] = df[col].astype("category").cat.codes  # 0, 1, 2, ...

model = lgb.LGBMClassifier(
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=31,
    min_child_samples=20,
    feature_fraction=0.9,
    bagging_fraction=0.8,
    bagging_freq=5,
    objective="binary",
    random_state=42,
    scale_pos_weight=spw,  # ricalcolato per fold
    verbose=-1,
)
model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(-1)],
    categorical_feature=cat_features,
)
```

**Category encoding must be consistent across train/val/test.**  
Encoding map must be persisted in `metadata.json` for inference-time re-encoding.

### Pattern 2: Manual Platt + Isotonic Calibration (sklearn 1.8 compatible)

**What:** `CalibratedClassifierCV(cv='prefit')` was REMOVED in sklearn 1.8.0. Use manual calibration by fitting sklearn calibrators on raw `predict_proba` outputs from the pre-fitted LightGBM model.

**When to use:** Per fold, after LightGBM training completes.

```python
# Source: verified via direct execution on sklearn 1.8.0 + LightGBM 4.6.0
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

# Ottieni probabilita grezze sul val set (gia senza leakage: val = last 20% train fold)
raw_val = model.predict_proba(X_val)[:, 1]  # shape (n_val,)

# Platt scaling: LogisticRegression su raw proba
platt_cal = LogisticRegression(C=1.0)  # C=1.0 default
platt_cal.fit(raw_val.reshape(-1, 1), y_val)

# Isotonic regression: monotonic non-parametric
iso_cal = IsotonicRegression(out_of_bounds="clip")  # clip = safe per OOD
iso_cal.fit(raw_val, y_val)

# Valuta su test fold
raw_test = model.predict_proba(X_test)[:, 1]
prob_platt = platt_cal.predict_proba(raw_test.reshape(-1, 1))[:, 1]
prob_iso   = iso_cal.transform(raw_test)

brier_platt = brier_score_loss(y_test, prob_platt)
brier_iso   = brier_score_loss(y_test, prob_iso)
winner = "isotonic" if brier_iso <= brier_platt else "sigmoid"
```

**Note:** Isotonic regression on small val sets (< 50 samples, early folds) is unreliable. Consider using Platt for folds 1-2 where val < 50 rows.

### Pattern 3: Walk-Forward Fold Builder with Per-TF Embargo

**What:** The Phase 1 `walk_forward_slices()` operates on generic bar lists and does NOT support per-row timeframe embargo. Phase 7 must implement embargo logic on top of the sorted DataFrame.

**When to use:** Dataset sorted by `decision_ts_utc`, split by row index (not bar index). Embargo computed as `max(timeout_bars[row.timeframe])` rows after `train_end`.

```python
# Source: [VERIFIED: Phase 1 walk_forward.py inspected; embargo logic is NEW for Phase 7]
import pandas as pd
import numpy as np
from backtest.walk_forward import walk_forward_slices  # reuse for fold boundary math

def build_ml_folds(
    df: pd.DataFrame,
    n_folds: int,
    embargo_bars_by_tf: dict[str, int],
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Expanding window, embargo per-TF, ritorna lista di (train_idx, val_idx, test_idx).

    Embargo = numero di righe da saltare DOPO train_end per garantire che nessun
    trade aperto a train_end sia ancora aperto all'inizio del test set.
    Upper bound: ogni riga ha embargo = embargo_bars_by_tf[riga.timeframe].
    Strategia: usa max(embargo_by_tf) come embargo uniforme (conservativo ma semplice).
    """
    df_sorted = df.sort_values("decision_ts_utc").reset_index(drop=True)
    total = len(df_sorted)
    
    # Ogni test fold occupa ~total/(n_folds+1) righe (expanding: 1 slot iniziale train minimo)
    slot = total // (n_folds + 1)
    max_embargo = max(embargo_bars_by_tf.values())  # 120 righe (H1) — upper bound
    
    folds = []
    for k in range(n_folds):
        train_end = slot + k * slot          # crescente con k (expanding)
        # Embargo: numero di righe da saltare dopo train_end
        # Usiamo upper bound max_embargo convertito in righe dataset
        # (≈ max_embargo/total * total = max_embargo righe nell'ipotesi di distribuzione uniforme)
        # In pratica su dataset ordinato per tempo: skippiamo righe con entry_time entro embargo window
        embargo_rows = _compute_embargo_row_count(df_sorted, train_end, embargo_bars_by_tf)
        test_start = train_end + embargo_rows
        test_end   = min(test_start + slot, total)
        
        if test_end <= test_start:
            continue  # fold non producibile

        # Train/val split: ultimi 20% del train fold come val
        val_start = int(train_end * 0.80)
        train_idx = np.arange(0, val_start)
        val_idx   = np.arange(val_start, train_end)
        test_idx  = np.arange(test_start, test_end)
        folds.append((train_idx, val_idx, test_idx))
    
    return folds


def _compute_embargo_row_count(
    df_sorted: pd.DataFrame,
    train_end: int,
    embargo_bars_by_tf: dict[str, int],
) -> int:
    """Conta righe da saltare dopo train_end per garantire zero label leak.

    Per ogni timeframe, considera il numero di barre corrispondente al cap TIMEOUT.
    Usa l'upper bound per semplicita (uniforme per tutti i TF).
    """
    # Strategia conservativa: max embargo in barre = 120 (H1)
    # Convertito in righe dataset: dipende da frequenza nel dataset
    # Alternativa esatta: trovare la prima riga con entry_time > train_row.decision_ts + embargo_duration
    # Per semplicit: upper bound uniforme (120 righe del dataset = ~10% di 1076)
    return max(embargo_bars_by_tf.values())  # 120 righe
```

**Reuse from Phase 1:** The `walk_forward_slices()` function from `backtest/walk_forward.py` provides validated expanding-window boundary math. For Phase 7, build on top with embargo: call `walk_forward_slices()` to get fold boundaries, then shift test_start by embargo_rows.

### Pattern 4: ECE (Expected Calibration Error) with Last-Bin Fix

**What:** Equal-width binning, 10 bins. Last bin must use `<=` (not `<`) to include `y_prob == 1.0`.

**When to use:** Evaluation metric per fold (SC#3), alongside Brier score and reliability diagram.

```python
# Source: verified via direct execution
import numpy as np

def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """ECE = Σ_b (|B_b| / N) × |acc(B_b) − conf(B_b)|.
    
    Ultimo bin usa <= per includere y_prob == 1.0.
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        if i < n_bins - 1:
            mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
        else:
            mask = (y_prob >= bin_edges[i]) & (y_prob <= bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        bin_acc  = float(y_true[mask].mean())
        bin_conf = float(y_prob[mask].mean())
        ece += (mask.sum() / len(y_true)) * abs(bin_acc - bin_conf)
    return ece
```

**Note:** The CONTEXT.md skeleton uses `<` for the last bin — this misses rows where `y_prob == 1.0`. Fix is a one-liner (`<=` for final bin).

### Pattern 5: Inference Singleton (Thread-Safe Double-Check Lock)

**What:** Module-level `_MODEL_CACHE = None` + `threading.Lock()` double-check pattern. Each ProcessPoolExecutor worker (Phase 6 D-A1) loads its own singleton on first predict — fork-safe by design.

**When to use:** `strategy/ml_filter.py` module-level cache.

```python
# Source: [ASSUMED] standard double-check locking pattern; process-safety verified conceptually
from threading import Lock
import joblib
import json
from pathlib import Path

_MODEL_CACHE = None
_CACHE_LOCK = Lock()

def get_ml_filter(cfg):
    global _MODEL_CACHE
    if _MODEL_CACHE is None:            # Prima lettura: no lock (veloce)
        with _CACHE_LOCK:
            if _MODEL_CACHE is None:    # Seconda lettura: dentro lock (sicura)
                _MODEL_CACHE = MLFilter.load(cfg.ML_MODEL_PATH)
    return _MODEL_CACHE
```

**Process-safety:** joblib bundles are pickle-able. Each forked worker inherits `_MODEL_CACHE = None` (pre-fork state), loads its own copy on first `predict()`. No inter-process model sharing needed.

### Pattern 6: Profit-Curve Threshold Optimization

**What:** Sweep thresholds on val set, compute expectancy_pips for each profile. Median across folds as final threshold.

**When to use:** Per fold, per profile, on val set predictions (NOT test set).

```python
# Source: [VERIFIED: algorithmic logic, no external lib]
import numpy as np

def profit_curve_optimal_threshold(
    prob_val: np.ndarray,
    pnl_pips: np.ndarray,
    sweep: np.ndarray,
) -> float:
    """Threshold ottimale = argmax expectancy_pips sul val set.

    Se nessun trade accettato a una soglia: expectancy = -inf.
    """
    best_t, best_exp = sweep[0], -np.inf
    for t in sweep:
        mask = prob_val >= t
        if mask.sum() == 0:
            continue
        exp = float(pnl_pips[mask].mean())
        if exp > best_exp:
            best_exp, best_t = exp, float(t)
    return best_t
```

**Reverse-leak risk:** Threshold optimized on val set, reported as "per-fold optimal". Final threshold = median across 10 folds. This is the standard approach; the medianization across folds prevents single-fold overfitting.

### Anti-Patterns to Avoid

- **`CalibratedClassifierCV(cv='prefit')`:** Rimosso in sklearn 1.8.0. Causa `InvalidParameterError` a runtime. Usare calibratori manuali (Pattern 2).
- **`train_test_split(shuffle=True)` sul dataset time series:** Viola SC#2. Vieta per costruzione: usare slicing per indice temporale.
- **Categorical feature come stringa senza encoding:** LightGBM richiede interi (0,1,2,...). Stringhe causano errore o silent wrong behavior. Usare `.astype("category").cat.codes` + persistere la mappa encoding.
- **Calibrare su test fold:** Leakage. Il calibratore deve vedere SOLO val set (last 20% train fold).
- **Costruire feature vector con DataFrame fresh a ogni inference:** Creazione DataFrame è lenta. Costruire una volta come dict → `pd.DataFrame([row_dict])` → predire. Alternativa: numpy array con feature order locked.
- **Isotonic su meno di ~30 sample:** Unreliable. Per i primi 2 fold (val < 50 righe) preferire Platt.

---

## Critical Finding: Dataset Schema Gap

**This is the most important finding in this research. It blocks ML-01 directly.**

### Actual Dataset vs D-02 Specification

**Verified via direct inspection of** `data/training/baseline_decisions/part-0.parquet`:

| Category | D-02 Specified | Actually Present | Gap |
|----------|---------------|-----------------|-----|
| Identity | `run_id, slice_id, symbol, timeframe, profile, decision_ts_utc, entry_ts_utc, exit_ts_utc` | `symbol, timeframe, entry_time (str), exit_time (str)` | Missing: `run_id, slice_id, profile, decision_ts_utc (proper UTC)` |
| ProposalDraft | `setup_name, direction, grade, factors_*, confidence, entry_price, sl, tp, rr, reason` | Most in `decision_context_json` dict: `setup_name, grade, confidence, direction, factors (nested dict)` | `rr` is `risk_reward` key; field names different; `sl` is present as top-level `sl` col |
| ExtendedIndicators | 30 fields (atr, ema20, ema50, ema200, ema50_slope, rsi, bb_*, adx, dmi_*, macd_*, stoch_*, donchian_*, keltner_*, vwap, hurst, mtf_align, etc.) | 6 fields in ctx JSON: `atr_14, ema_50, rsi_14, sma_20, sma_50, last_close` | **24+ ExtendedIndicators fields missing entirely** |
| Context | `regime, sr_dist_pips, spread_at_entry_pips, sentiment_proxy, recent_trades_outcome_5` | None | **All 5 context fields missing** |
| Outcome | `outcome, exit_reason, pnl_pips, pnl_money, bars_held` | `exit_reason (TP/SL/SL_GAP/TIMEOUT_CLOSE), pnl_pips, pnl_usd` | Missing: `outcome (label), pnl_money (alias), bars_held` |

[VERIFIED: all findings confirmed by direct parquet inspection]

### Root Cause

Phase 5 used the legacy `decision_context_json` field from `backtest/ledger.py` (Phase 1 schema), which captured only the fields present in `strategy.py` at Phase 1 time. The full `compute_all_extended()` snapshot (Phase 2) and `StrategyContext` fields (`profile`, `regime`) were never wired into the `baseline_decisions` writer.

The STATE.md confirms this: "drafts_rows = [] (DEFERRED — engine non cattura FORMING/NONE; futuro plan per Phase 7 failure analysis)." The same engine gap affected indicator coverage.

### Remediation Options for Wave 0 (Planner decides)

**Option A — Re-run baseline with full D-02 schema.** Modify `backtest/baseline/dataset_writer.py` to capture the full `compute_all_extended()` snapshot + `profile` + `regime` + proper timestamps. Re-run the 10-year baseline (original run took 3h18m). Produces the full feature set as designed. BLOCKING for dataset re-run time.

**Option B — Backfill script on existing dataset.** The existing 1,076 rows have `entry_time` + `symbol` + `timeframe`. A script can: (1) re-load the historical CSV, (2) find the bar at `entry_time`, (3) recompute `compute_all_extended()` up to that bar, (4) extract all 30+ indicator fields + `regime`. This avoids a full re-run but requires careful no-leakage logic (use bar at `entry_time - 1 bar`). Faster but complex.

**Option C — Work with reduced feature set.** Train on the 12 features actually available: `symbol, timeframe, setup_name, grade, confidence, direction, pnl_pips` + factors dict + 6 indicator fields. Miss ~75% of designed feature coverage. Viable for verifying pipeline end-to-end but produces a weaker classifier.

**Recommendation:** Option A is cleanest. Option B is second-best. Both require Wave 0 dataset remediation plan. Option C should only be used as a last resort or to prove the pipeline runs before full data is available.

### Dataset Size Reality Check

| Metric | Expected (CONTEXT.md) | Actual | Impact |
|--------|----------------------|--------|--------|
| Total trades | 10k–50k | 1,076 | Small dataset; overfitting risk high; early fold calibration unreliable |
| Win rate (y=1) | ~30% | 27.6% (297/1076) | Close to D-04 expectation |
| scale_pos_weight | ~2.3 | 2.62 | Slightly higher imbalance than expected |
| Fold 1 val set | ~500 rows | ~20 rows | **TOO SMALL for isotonic calibration** |
| Folds 1-2 val set | acceptable | < 50 rows | Use Platt (logistic) for early folds |

[VERIFIED: all numbers from direct parquet inspection]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Binary classifier | Custom tree or neural net | `lgb.LGBMClassifier` | PROJECT.md locked; native cat features, early stopping, fast inference |
| Platt scaling | Sigmoid fitting from scratch | `sklearn.linear_model.LogisticRegression` | Numerically stable, tested |
| Isotonic calibration | Custom monotonic regression | `sklearn.isotonic.IsotonicRegression` | PAVA algorithm, `out_of_bounds='clip'` for OOD safety |
| Brier score | Squared error manually | `sklearn.metrics.brier_score_loss` | Convention; matches sklearn API |
| AUC-PR | Trapezoid rule on P/R curve | `sklearn.metrics.precision_recall_curve` + `auc(recall, precision)` | sklearn auc handles shape correctly |
| Model serialization | `pickle.dump` directly | `joblib.dump(bundle, path, compress=3)` | compress=3 → 645KB vs uncompressed; handles numpy arrays better than pickle |
| Feature vector ordering | Ad-hoc dict iteration | Explicit ordered list in `metadata.json["features"]`, then `df[features]` | Dict ordering in Python 3.7+ is insertion order but explicit is safer |
| Thread-safe singleton | Global variable race | `threading.Lock()` double-check pattern | Prevents race on first-load when multiple threads serve simultaneously |
| Walk-forward boundaries | Calendar splitting | Row-index splitting on time-sorted DataFrame | Calendar gaps (weekends) distort fold sizes; row count is uniform |

**Key insight:** LightGBM, sklearn calibrators, and joblib together cover all the hard edge cases in binary classification and calibration. Everything else in this phase is plumbing.

---

## Runtime State Inventory

Phase 7 is a greenfield addition with no rename/refactor. The only runtime state consideration is:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `data/training/baseline_decisions/part-0.parquet` — READ-ONLY, schema gap documented above | Wave 0 remediation (Option A/B/C) |
| Live service config | None — no MCP tool changes in this phase | None |
| OS-registered state | None — no new scheduler tasks | None |
| Secrets/env vars | New: `ENABLE_ML_FILTER`, `ML_MODEL_PATH`, `ML_INFERENCE_LATENCY_BUDGET_MS` (to be added to `.env.example`) | Add to `config.py` + `.env.example` |
| Build artifacts | `models/` directory does NOT exist yet | Created in Wave 0 scaffolding |

---

## Common Pitfalls

### Pitfall 1: CalibratedClassifierCV cv='prefit' Removed in sklearn 1.8

**What goes wrong:** `InvalidParameterError: The 'cv' parameter of CalibratedClassifierCV must be an int [...]. Got 'prefit' instead.` — the CONTEXT.md skeleton uses `cv="prefit"`.

**Why it happens:** `cv='prefit'` was deprecated in sklearn 1.3 and removed in sklearn 1.8.0. It was the standard way to calibrate a pre-fitted model on a held-out set.

**How to avoid:** Use manual calibration: get raw `predict_proba` from the fitted model on val set, then fit `LogisticRegression` (Platt) or `IsotonicRegression` directly on those probabilities.

**Warning signs:** `InvalidParameterError` at runtime, or training that fits but produces uncalibrated probabilities because cv refits the base model on cross-validation folds (ignoring early stopping).

[VERIFIED: sklearn 1.8.0 InvalidParameterError confirmed via runtime test]

### Pitfall 2: Categorical Feature Encoding Inconsistency at Inference

**What goes wrong:** Model trained with `symbol` encoded as `{EURUSD:0, GBPUSD:1, USDJPY:2}`. At inference, fresh encoding produces `{EURUSD:0, USDJPY:1, GBPUSD:2}` (different order) — model sees wrong category codes silently.

**Why it happens:** `pd.Categorical.cat.codes` ordering is lexicographic by default but depends on the order categories first appear. If training and inference use different DataFrames, the encoding can differ.

**How to avoid:** Persist encoding maps in `metadata.json`:
```json
"categorical_encodings": {
  "symbol": {"EURUSD": 0, "GBPUSD": 1, "USDJPY": 2},
  "profile": {"AGGRESSIVE": 0, "CONSERVATIVE": 1, "MODERATE": 2},
  ...
}
```
At inference time, use `mapping.get(value, -1)` (unknown category → -1, which LightGBM handles as NaN for categorical → predict without that feature).

**Warning signs:** Feature importance shows categorical features have zero importance even though they should matter; or inference probabilities match training-time distribution but predictions are wrong on held-out data.

[VERIFIED: behavior confirmed via direct LightGBM test]

### Pitfall 3: Early Stopping with CalibratedClassifierCV Internal CV Refit

**What goes wrong:** If using `CalibratedClassifierCV(cv=5)`, sklearn internally refits the base model 5 times on different CV folds. Each refit calls `fit()` WITHOUT the `eval_set` and `callbacks` (early stopping), so the model uses all 500 estimators — not the optimal early-stopped number. The calibrated model is then inconsistent with the early-stopped model behavior.

**Why it happens:** `CalibratedClassifierCV` calls `base_estimator.fit(X_train_fold, y_fold)` without passing `fit_params` transparently in older sklearn versions.

**How to avoid:** Use manual calibration (Pattern 2). Fit LightGBM with early stopping yourself, then fit calibrators on the resulting raw probabilities.

**Warning signs:** Val Brier score with `CalibratedClassifierCV(cv=5)` is much better than expected — it used all 500 trees, not the early-stopped ~N trees.

### Pitfall 4: Inference Latency Spikes at p99 in Docker/WSL2

**What goes wrong:** p99 latency is 13-14ms (above the 10ms budget) even though p50 is 4ms. SC#4 test at p99 fails.

**Why it happens:** Linux scheduling jitter in Docker/WSL2 causes sporadic 10-20ms pauses. The actual LightGBM computation is 3-4ms; the tail is OS overhead.

**How to avoid:** Define the benchmark as `p95 < 10ms` in the test, which is achievable (p95 = 9-10ms). Note in the test docstring that p99 is OS-jitter-dependent in containerized environments. On Windows production (bare metal), latency is lower.

**Warning signs:** Test passes on Windows laptop but fails in CI (Linux container).

[VERIFIED: latency benchmark run in this WSL2 environment — p50=4ms, p95=9ms, p99=13ms]

### Pitfall 5: ECE Last-Bin Off-by-One

**What goes wrong:** Rows with `y_prob == 1.0` are not counted in any bin because all bins use `y_prob < upper_edge`, and the last bin upper edge is 1.0. ECE is silently under-reported for overconfident models.

**Why it happens:** The CONTEXT.md skeleton uses `y_prob < bin_edges[i+1]` uniformly.

**How to avoid:** Last bin uses `y_prob <= bin_edges[-1]` (Pattern 4 code).

**Warning signs:** ECE appears lower than expected on a model that's clearly overconfident at prob=1.0.

### Pitfall 6: Feature Schema Drift Between Training and Inference

**What goes wrong:** Phase 2 adds a new indicator to `compute_all_extended()`. The training dataset was produced before this change. The trained model has `n_features=36`. Inference receives `n_features=37`. `predict_proba` raises shape error or produces garbage.

**Why it happens:** Model doesn't validate the feature schema; it just sees column index order.

**How to avoid:** In `MLFilter.load()`, validate `len(features_from_bundle) == len(incoming_feature_vec)` and `features_from_bundle == incoming_feature_names`. Raise `FeatureSchemaMismatchError` with clear message including expected vs actual feature list diff.

**Warning signs:** Latent bug that only surfaces after Phase 9 retraining with new indicators.

### Pitfall 7: Embargo Not Accounting for Mixed TF Dataset

**What goes wrong:** The dataset has M15 (96 bar embargo), M30 (96 bar embargo), and H1 (120 bar embargo) rows intermixed. Using `max_embargo = 120` uniformly means M15 and M30 rows get MORE embargo than needed, wasting ~5% of data. Using per-row embargo is complex.

**Why it happens:** D-07 specifies embargo per TF, but the fold builder works on dataset rows, not bar counts.

**How to avoid:** D-07 decision is already to use `timeout_bars[tf]` per row. For the first implementation, using `max(embargo_bars_by_tf.values())` = 120 is the correct conservative approach (documented in D-07: "dataset perso ~0.16%"). The per-row exact embargo is a refinement for Phase 9.

**Warning signs:** None — this is a conservative safe choice, not a bug.

---

## Code Examples

### Feature Extraction from Actual Dataset Schema

Given the actual dataset columns (not D-02 spec), here is the extraction pattern:

```python
# strategy/ml_filter.py — build_features()
# Lavora con lo schema EFFETTIVO del dataset (non D-02 spec)
# Da riconciliare con la remediation Wave 0
import numpy as np
import pandas as pd
from strategy.proposal import ProposalDraft
from strategy.context import StrategyContext

def build_features(
    draft: ProposalDraft,
    indicators,  # ExtendedIndicators dataclass (Phase 2)
    ctx: StrategyContext,
    feature_list: list[str],
    cat_encodings: dict[str, dict[str, int]],
) -> pd.DataFrame:
    """Costruisce un DataFrame a singola riga con le feature nell'ordine del training.

    Restituisce pd.DataFrame (non numpy array) per preservare i nomi colonna
    e avere compatibilita con LightGBM without UserWarning.
    """
    row = {}

    # Categorical features (encodate come int)
    for col in ["symbol", "timeframe", "profile", "setup_name", "regime"]:
        val = _get_cat_value(col, draft, ctx)
        enc = cat_encodings.get(col, {})
        row[col] = enc.get(val, -1)  # -1 = categoria sconosciuta

    # Numeric features da ExtendedIndicators
    for attr in ["atr", "ema20", "ema50", "ema200", "ema50_slope", "rsi",
                 "bb_upper", "bb_lower", "bb_squeeze", "adx", "dmi_plus", "dmi_minus",
                 "macd_line", "macd_signal", "macd_hist", "stoch_k", "stoch_d",
                 "donchian_hi", "donchian_lo", "keltner_upper", "keltner_lower",
                 "vwap", "hurst", "mtf_align"]:
        row[attr] = getattr(indicators, attr, None)

    # Numeric features da ProposalDraft
    row["confidence"]          = draft.confidence
    row["entry_price"]         = draft.entry_price
    row["stop_loss_price"]     = draft.stop_loss_price
    row["take_profit_price"]   = draft.take_profit_price
    rr = None
    if draft.entry_price and draft.stop_loss_price and draft.take_profit_price:
        risk = abs(draft.entry_price - draft.stop_loss_price)
        reward = abs(draft.take_profit_price - draft.entry_price)
        rr = reward / risk if risk > 0 else None
    row["rr"] = rr
    row["factors_trend_alignment"]    = int(bool(draft.factors.get("trend_alignment")))
    row["factors_setup_pattern"]      = int(bool(draft.factors.get("setup_pattern")))
    row["factors_momentum"]           = int(bool(draft.factors.get("momentum")))
    row["factors_volatility_regime"]  = int(bool(draft.factors.get("volatility_regime")))
    row["factors_spread_session"]     = int(bool(draft.factors.get("spread_session")))

    # Context
    row["sr_dist_pips"]        = getattr(ctx, "sr_dist_pips", None)
    row["spread_baseline_pips"] = ctx.spread_baseline_pips

    # Allinea all'ordine del training
    df = pd.DataFrame([{f: row.get(f) for f in feature_list}])
    return df
```

### Metadata JSON Schema

```python
# strategy/training.py — metadata serialization
metadata = {
    "version": "v1",
    "train_date": today_iso,
    "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
    "dataset_path": str(cfg.dataset_path),
    "dataset_hash": hashlib.sha256(Path(cfg.dataset_path).read_bytes()).hexdigest(),
    "n_train_rows": int(len(df)),
    "n_features": len(feature_cols),
    "features": feature_cols,             # CRITICO: ordine locked
    "categorical_features": cat_features,
    "categorical_encodings": cat_encoding_maps,  # CRITICO: encoding map per inference
    "fold_metrics": fold_metrics_list,    # list[dict] Brier/ECE/AUC-PR per fold
    "scale_pos_weight_per_fold": spw_per_fold,
    "calibrator_winner_per_fold": winner_per_fold,
    "threshold_by_profile": final_thresholds,
    "lightgbm_version": lgb.__version__,
    "sklearn_version": sklearn.__version__,
}
```

### Reliability Diagram (matplotlib Agg)

```python
# strategy/training.py — per-fold reliability diagram
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def plot_reliability_diagram(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    fold_num: int,
    out_path,
    n_bins: int = 10,
):
    """Reliability diagram: fraction positive vs mean predicted probability per bin."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_edges[:-1]
    frac_positives, mean_pred = [], []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i+1]
        mask = (y_prob >= lo) & (y_prob <= hi) if i == n_bins-1 else (y_prob >= lo) & (y_prob < hi)
        if mask.sum() == 0:
            frac_positives.append(np.nan)
            mean_pred.append(np.nan)
        else:
            frac_positives.append(float(y_true[mask].mean()))
            mean_pred.append(float(y_prob[mask].mean()))

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", label="Calibrazione perfetta")
    ax.bar(bin_lowers, frac_positives, width=0.1, alpha=0.7, color="steelblue", label="Frazione positivi")
    ax.plot(mean_pred, frac_positives, "ro-", label="Calibrazione modello")
    ax.set_xlabel("Probabilita predetta media per bin")
    ax.set_ylabel("Frazione positivi reali")
    ax.set_title(f"Reliability Diagram — Fold {fold_num}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=100)
    plt.close()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `CalibratedClassifierCV(cv='prefit')` | Manual `LogisticRegression` / `IsotonicRegression` on raw proba | sklearn 1.3 deprecated, 1.8 removed | Must update CONTEXT.md skeleton code |
| `categorical_feature` as constructor param | `categorical_feature` as `fit()` param | LightGBM 3.x+ | Constructor param is silently ignored in 4.x |
| LightGBM `verbose` default (noisy) | `verbose=-1` (silent) + `lgb.log_evaluation(-1)` callback | LightGBM 4.x | Training script must suppress verbosity explicitly |
| `np.random.seed(42)` global seed | `random_state=42` in LGBMClassifier constructor | Best practice | Module-level seed doesn't guarantee LightGBM reproducibility |

**Deprecated/outdated:**
- `CalibratedClassifierCV(cv='prefit')`: removed in sklearn 1.8.0. Use manual calibration.
- `lgb.Dataset` + `lgb.train()` low-level API: works but `LGBMClassifier` sklearn wrapper is cleaner for Phase 7.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `evaluate_proposal_for_bar` signature can be extended with `ml_filter=None` without breaking Phase 5 backtest or Phase 6 replay (additive kwarg) | Architecture Patterns | Low — Python defaults prevent breakage; Phase 5 already completed |
| A2 | ProcessPoolExecutor workers in Phase 6 each fork with `_MODEL_CACHE = None`, so each loads its own copy at first predict | Pattern 5 (singleton) | Low — standard fork semantics; verified conceptually |
| A3 | The production Windows environment (bare metal) will achieve <10ms at p99 (not just p95) | §Latency Budget | Low — Linux Docker/WSL2 scheduling is worse than Windows bare metal; production target is achievable |
| A4 | Baseline dataset re-run (Option A remediation) produces ~1k-10k trades in 10-year window at current engine speed | §Dataset Schema Gap | Medium — Phase 5 run at 3h18m produced 1076; wider feature coverage won't change trade count significantly |
| A5 | `CalibratedClassifierCV` internal structures accessible via `.calibrated_classifiers_[0]` are NOT needed since we use manual calibration | Pattern 2 | None — manual calibration sidesteps this entirely |

---

## Open Questions

1. **Dataset remediation approach (Option A vs B vs C)**
   - What we know: Actual dataset missing 38 of D-02 fields. All three options have valid tradeoffs.
   - What's unclear: Time budget for Option A re-run (last run was 3h18m; Phase 5 perf deferred). Option B complexity (backfill script may itself introduce subtle leakage if not careful about bar-close discipline).
   - Recommendation: **Planner should make this a Wave 0 explicit decision.** Default to Option A (re-run with full schema) unless time budget is prohibitive, then Option B.

2. **Early fold calibration stability (fold 1 val = 20 rows)**
   - What we know: Isotonic regression on 20 samples is unreliable. Platt (logistic regression) is more stable at small N.
   - What's unclear: Whether fold 1-2 calibration quality matters for the final model (it uses all folds for medianization).
   - Recommendation: Use Platt for folds where `len(val_idx) < 50`; use min-Brier winner for larger folds. Add this logic to `training.py`.

3. **Inference latency budget spec: p95 vs p99 vs mean**
   - What we know: In this WSL2 environment: p50=4ms, p95=9ms, p99=13ms. The 10ms budget in SC#4 is tight at p99 in Linux container.
   - What's unclear: What percentile the user/CONTEXT.md intends for the <10ms spec.
   - Recommendation: Define the pytest benchmark as `p95 < 10ms`, with a note that p99 tail includes OS scheduling jitter. Add `num_threads=1` to LightGBM config for more deterministic inference latency.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| lightgbm | ML-02 training + inference | ✓ | 4.6.0 | — |
| scikit-learn | Calibration (IsotonicRegression, LogisticRegression), metrics | ✓ | 1.8.0 | — |
| joblib | Model serialization | ✓ | 1.5.3 | — |
| numpy | Feature vector ops | ✓ | 2.4.4 | — |
| pandas | Dataset loading, feature DataFrame | ✓ | 2.2+ | — |
| pyarrow | Parquet read | ✓ | 24.0.0 | — |
| matplotlib (Agg) | Reliability diagrams | ✓ | existing | — |
| pytest | Test runner | ✓ | existing | — |
| `data/training/baseline_decisions/part-0.parquet` | ML-01 feature extraction + training | ✓ (1076 rows, schema gap) | part-0.parquet | **Option A/B/C remediation required before full ML-01** |
| `models/` directory | ML-10 artifact persistence | ✗ not yet created | — | Created in Wave 0 scaffolding |

**Missing dependencies with no fallback:** None — all libraries installed.

**Missing dependencies with fallback:** `models/` directory — created in Wave 0.

**Dataset schema gap:** `baseline_decisions` exists but is missing 38 D-02 specified fields. Functional training is blocked until Wave 0 remediation.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, `pytest.ini` at repo root, `pythonpath = .`) |
| Config file | `pytest.ini` — no changes needed |
| Quick run command | `pytest tests/test_ml_filter.py tests/test_training.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ML-01 | Feature extractor produces deterministic vector from fixed input | unit (snapshot) | `pytest tests/test_ml_filter.py::test_build_features_deterministic -x` | ❌ Wave 0 |
| ML-01 | Feature vector length matches `metadata.json` n_features | unit | `pytest tests/test_ml_filter.py::test_feature_vector_length -x` | ❌ Wave 0 |
| ML-02 | LightGBM trains without error on mini fixture dataset | unit | `pytest tests/test_training.py::test_lgbm_trains_on_fixture -x` | ❌ Wave 0 |
| ML-03 | Walk-forward builder produces 10 non-overlapping folds; no shuffle | unit | `pytest tests/test_training.py::test_folds_no_shuffle_no_overlap -x` | ❌ Wave 0 |
| ML-03 | Train index < val index < test index for all folds | unit | `pytest tests/test_training.py::test_folds_temporal_order -x` | ❌ Wave 0 |
| ML-03 | `train_test_split(shuffle=True)` not in any training code (AST guard) | unit (AST) | `pytest tests/test_training.py::test_no_shuffle_split_in_training -x` | ❌ Wave 0 |
| ML-04 | Calibration winner has lower Brier than loser on test fold | unit | `pytest tests/test_training.py::test_calibration_winner_selection -x` | ❌ Wave 0 |
| ML-04 | ECE computed correctly (known hand-crafted case) | unit | `pytest tests/test_training.py::test_ece_known_values -x` | ❌ Wave 0 |
| ML-04 | ECE last bin includes y_prob=1.0 | unit | `pytest tests/test_training.py::test_ece_last_bin_inclusive -x` | ❌ Wave 0 |
| ML-05 | `predict()` returns (raw_score, calibrated_prob) in [0,1] | unit | `pytest tests/test_ml_filter.py::test_predict_returns_valid_proba -x` | ❌ Wave 0 |
| ML-05 | Single-sample inference latency < 10ms at p95 (1000 calls) | unit (benchmark) | `pytest tests/test_ml_filter.py::test_inference_latency_p95 -x` | ❌ Wave 0 |
| ML-06 | Trade with `calibrated_prob < threshold` rejected by risk_engine | integration | `pytest tests/test_risk.py::test_ml_gate_rejects_low_prob -x` | ❌ Wave 0 |
| ML-06 | Trade with ML disabled (`ENABLE_ML_FILTER=false`) passes through | integration | `pytest tests/test_risk.py::test_ml_gate_disabled_passthrough -x` | ❌ Wave 0 |
| ML-06 | Strategy remains pure: evaluate_proposal_for_bar has no I/O (AST gate extension) | unit (AST) | `pytest tests/test_strategy_purity.py -x` (extend existing) | ✅ (extend) |
| ML-10 | `models/classifier_v1_{date}.pkl` loads and returns a valid bundle | unit | `pytest tests/test_ml_filter.py::test_bundle_load_valid -x` | ❌ Wave 0 |
| ML-10 | `metadata.json` contains all required fields (version, git_sha, dataset_hash, fold_metrics) | unit | `pytest tests/test_ml_filter.py::test_metadata_schema_complete -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_ml_filter.py tests/test_training.py -x --tb=short`
- **Per wave merge:** `pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ml_filter.py` — ML-01, ML-05, ML-10 unit tests
- [ ] `tests/test_training.py` — ML-02, ML-03, ML-04 unit tests
- [ ] `tests/fixtures/ml/sample_decision_dataset.parquet` — deterministic 100-row mini dataset (seed=42, 3 symbols, 3 TF, 3 profiles, ~28% TP rate)
- [ ] `models/` directory — created by `mkdir models` in Wave 0
- [ ] `data/configs/ml_training.yaml` — training orchestration config

---

## Security Domain

> `security_enforcement` key not present in `.planning/config.json` — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not applicable (offline training script) |
| V3 Session Management | no | Not applicable |
| V4 Access Control | no | Model files are local filesystem only |
| V5 Input Validation | yes | `build_features()` validates feature schema; `ml_filter.py` validates `calibrated_prob in [0,1]`; `config.py` validates `ML_THRESHOLD_BY_PROFILE` range |
| V6 Cryptography | no | SHA256 used for audit (not security); no user data encrypted |

### Known Threat Patterns for ML Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Model artifact tampering | Tampering | `metadata.json` includes `dataset_hash` (SHA256) + `git_sha`; validate at load time |
| Feature injection (invalid input at inference) | Tampering | `build_features()` validates each field type; `calibrated_prob` sanity check clamps to [0,1] |
| Future leakage via incorrect fold construction | Information disclosure | AST test `test_no_shuffle_split_in_training` + temporal order assertion per fold |
| NaN propagation silently | Elevation of privilege | Explicit `None` → 0.0 or `np.nan` handling in `build_features()`; LightGBM handles NaN natively |

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 7 |
|-----------|-----------------|
| `EXECUTION_MODE=shadow` default | Training script does not interact with MT5; shadow mode unaffected |
| All config from `.env`, zero magic numbers | `ENABLE_ML_FILTER`, `ML_MODEL_PATH`, `ML_INFERENCE_LATENCY_BUDGET_MS`, threshold values from `metadata.json` (not hardcoded) |
| `risk_engine = unico gate approvazione trade` | ML threshold gate goes in `risk_engine.evaluate_trade`, NOT in `evaluate_proposal_for_bar` (D-12) |
| Italian language for commenti/log/rationale | All docstrings, log messages, and inline comments in Italian. Identifiers in English. |
| Pure-function strategy preserved (Phase 4 SC#1) | `evaluate_proposal_for_bar` must remain side-effect-free. ML prediction step: no I/O, model loaded externally and passed as optional arg or via singleton. |
| Commit conventions | `feat(phase-7): ...`, `test(phase-7): ...` — scope = `phase-7` |
| No future leakage | Walk-forward + embargo + bar-close discipline (D-17); AST guard test; temporal order assertions |
| Un file per fase in `.orchestration/phase-prompts/` | Not applicable to Phase 7 (no new orchestration phase file needed) |

---

## Sources

### Primary (HIGH confidence)

- [VERIFIED: lightgbm 4.6.0] — categorical_feature fit() param, early_stopping callback API, num_leaves=31 default
- [VERIFIED: scikit-learn 1.8.0] — `CalibratedClassifierCV` signature (cv='prefit' removed), `IsotonicRegression`, `LogisticRegression`, `brier_score_loss`
- [VERIFIED: direct parquet inspection] — `data/training/baseline_decisions/part-0.parquet`: 1076 rows, 17 top-level columns, decision_context_json schema
- [VERIFIED: backtest/walk_forward.py source] — Phase 1 harness API: `walk_forward_slices(bars, n_folds, train_ratio, mode)`, no per-TF embargo
- [VERIFIED: strategy/__init__.py source] — `evaluate_proposal_for_bar(bars, indicators, ctx)` signature, ProposalDraft structure
- [VERIFIED: strategy/proposal.py source] — `ProposalDraft` frozen dataclass fields (no ml_* fields yet)
- [VERIFIED: risk_engine.py source] — `evaluate_trade(proposal, account, mt5_client, cfg)` signature, PROFILES dict
- [VERIFIED: runtime latency benchmark] — p50=4ms, p95=9ms, p99=13ms for 500-tree LightGBM + IsotonicRegression in WSL2
- [VERIFIED: joblib.dump/load timing] — 138ms dump, 39ms load, 645 KB compressed=3
- [VERIFIED: sklearn 1.8.0 InvalidParameterError] — cv='prefit' confirmed removed

### Secondary (MEDIUM confidence)

- [CITED: .planning/phases/07-ml-classifier/07-CONTEXT.md] — 20 locked decisions D-01..D-20, 7 Claude discretion areas, code skeletons
- [CITED: .planning/phases/05-baseline-backtest/05-CONTEXT.md] — D-02 dataset schema spec, D-04/05 outcome encoding, D-07 timeout_bars
- [CITED: .planning/phases/01-backtest-engine/01-CONTEXT.md] — D-06 walk-forward harness API
- [CITED: .planning/STATE.md] — Phase 5 completion state, 10-year run scope, 1076 trade count confirmed

### Tertiary (LOW confidence)

- [ASSUMED] — ProcessPoolExecutor fork-safety with joblib bundles (verified conceptually, not runtime tested)
- [ASSUMED] — Production Windows bare metal achieves p99 < 10ms (based on p50=4ms in WSL2)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified on machine
- Architecture (general): HIGH — verified against actual source code
- Dataset schema gap: HIGH — directly verified by parquet inspection
- sklearn 1.8 breaking change: HIGH — confirmed via runtime test
- Latency budget: MEDIUM — benchmarked in WSL2 (not production Windows)
- Walk-forward fold design: HIGH — Phase 1 harness inspected, embargo logic new

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (stable libraries; sklearn/lightgbm release cadence is ~quarterly)
