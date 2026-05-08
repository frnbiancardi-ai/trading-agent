# Phase 7: ML Classifier — Context

**Gathered:** 2026-05-08
**Status:** Ready for planning
**Source:** /gsd:discuss-phase 7 (interactive, 4 aree, mode=discuss, ~16 question)

<domain>
## Phase Boundary

Train un trade-quality binary classifier (LightGBM) sul dataset `data/training/baseline_decisions.parquet` (Phase 5 D-02). Walk-forward expanding 10 fold con embargo per-TF. Calibration Platt + Isotonic, vincitore per Brier score per fold. Persistenza `models/classifier_v{N}_{date}.pkl` (joblib bundle) + sidecar `.metadata.json`. Inference integrato nel pipeline: prediction in `evaluate_proposal_for_bar` (Phase 4), decision gate in `risk_engine.evaluate_trade` (CLAUDE.md "unico gate") con threshold per-profile profit-curve optimized.

Dataset locked = `baseline_decisions.parquet` (10k–50k trade attesi da Phase 5 baseline 23.5y × 3 pair × 3 TF × 3 profile). Schema columns Phase 5 D-02 invariato. Phase 7 NON modifica schema dataset né schema MCP. Phase 7 estende `ProposalDraft` (Phase 4) con campi `ml_raw_score`, `ml_calibrated_prob`, `ml_model_version`.

**In scope:** ML-01, ML-02, ML-03, ML-04, ML-05, ML-06, ML-10. ROADMAP SC#1..5.

**Out of scope (deferred):**
- ML-07/08/09 (failure clustering, drift monitor, retrain trigger) → Phase 9
- MCP tool ML (`train_ml_filter`, `predict_trade_quality`, `get_ml_calibration`, `evaluate_trade_proposal` ML extension) → Phase 8
- Multiclass target {WIN, LOSS, TIMEOUT} → rifiutato (REQ ML-04 Platt/isotonic binary-only)
- Per-symbol-tf-profile model (27 modelli) → rifiutato (N troppo basso, varianza alta)
- Sample weight per pnl_pips → riservato Phase 9 expectancy optimization
- Feature engineering ratios/deltas → LightGBM cattura via tree splits, no upfront engineering
- Cross-language model export (lgb native txt) → Phase 11+ se porting necessario

</domain>

<decisions>
## Implementation Decisions

### Target label encoding (Area 1)

- **D-01 — Single rule binary: `y=1 ⟺ exit_reason==TP_HIT`.** Tutto resto → `y=0`. Calibrated probability `P(y=1 | features)` interpretazione univoca: "probabilità trade raggiunge TP completo". Skill agentic threshold filtering semantica chiara.
- **D-02 — TIMEOUT → y=0.** Trade ancora aperto a cap Phase 5 D-05 (M15=96 bar, M30=96, H1=120) chiuso a market = loss. Modello impara "evita setup senza momentum" come failure mode reale (capitale bloccato 24h+ = costo opportunità). Coerente con D-01.
- **D-03 — BREAKEVEN → y=0.** Outcome `pnl_pips ≈ 0` rare nel baseline Phase 5 (no active management, BE residuale <2% dataset). Single rule audit-friendly. Coerente D-01/D-02.
- **D-04 — Class imbalance: `scale_pos_weight = N_neg / N_pos`, ricalcolato per fold.** Class balance atteso ~30/70 (WIN ~30%, LOSS+TIMEOUT+BE ~70%). LightGBM param `scale_pos_weight` standard binary imbalanced. Per fold walk-forward, ricalcolare spw da train set fold (class balance può shiftare nel tempo). Compatibile Platt/isotonic post-calibration (REQ ML-04). No `is_unbalance=true` (black box, no override). No sample_weight per pnl (distorce calibration semantics).

### Walk-forward fold design (Area 2)

- **D-05 — Window strategy: expanding.** Train fold k = `[t_0, t_split_k]`, cresce nel tempo. Forex regime non-stationary (forex-algo-dev skill) ma pattern long-term (carry trade flows USDJPY, DXY cycles) catturati da history più lunga. Phase 1 D-06 walk_forward harness compatibile (riusa, no fork ML-specific).
- **D-06 — N fold = 10.** Cap PROJECT.md. ROADMAP SC#2 "10 fold models". ~2.35y per fold span, ~1k trade per test fold (su 10k totali) = statistical power decente per Brier/ECE.
- **D-07 — Embargo gap = `timeout_bars[tf]` per TF.** M15=96, M30=96, H1=120 bar (Phase 5 D-05). Tight upper-bound matematico: ogni trade aperto a `train_end` ha tempo MAX di chiudersi (TIMEOUT cap) prima di `test_start`. Zero label leak. Dataset perso ~0.16% (trascurabile). Phase 9 retraining con active management (modify_position trail) riconsiderare embargo.
- **D-08 — Train/val split: last 20% temporal del train fold.** Train inner = primi 80% del train_window, val inner = ultimi 20%. Temporal split (no shuffle). Early stopping LightGBM su val Brier score (`stopping_rounds=50`). Test fold restante (resto del fold) intoccato per Brier/ECE/AUC-PR finale. forex-algo-dev pattern standard.

### Per-profile model strategy (Area 3)

- **D-09 — 1 modello unico su tutto dataset (~30k trade su 3 profile × 10k slice trade).** Profile come categorical feature LightGBM. Modello impara interazioni profile×regime×setup×symbol via tree splits. Pi`u dati = generalizzazione superiore vs 3 modelli separati. 1 file artifact + 1 audit trail. Drift Phase 9 non triplicato.
- **D-10 — Categorical features: `["symbol", "timeframe", "profile", "setup_name", "regime"]`.** LightGBM `categorical_feature` param nativo (no one-hot manuale). Encoding 0,1,2,... interno. Tree split categorical: prova partizioni `{A,B}` vs `{C,D}` ecc. (no ordering implicit). Forza modello a distinguere pattern symbol-specific (USDJPY safe-haven flow vs EURUSD), TF-specific (M15 noise-driven vs H1 trend-driven), setup-specific (A breakout vs C compression).
- **D-11 — Numeric features: raw ExtendedIndicators + ProposalDraft factors + ctx (Phase 5 D-02 schema), no engineering upfront.** Lista features: tutti campi Phase 5 D-02 numerici (`atr, ema20, ema50, ema200, ema50_slope, rsi, bb_upper, bb_lower, bb_squeeze, adx, dmi_plus, dmi_minus, macd_line, macd_signal, macd_hist, stoch_k, stoch_d, donchian_hi, donchian_lo, keltner_upper, keltner_lower, vwap, fib_levels..., pivot, nr4, nr7, closing_score, hurst, mtf_align, sr_dist_pips, spread_at_entry_pips, sentiment_proxy, recent_trades_outcome_5_encoded`) + ProposalDraft (`factors_trend_alignment, factors_setup_pattern, factors_momentum, factors_volatility_regime, factors_spread_session, confidence, rr, entry_price, stop_loss_price, take_profit_price`). LightGBM cattura interazioni via tree splits, no engineered ratios/deltas upfront (over-engineering rischia leakage). Feature selection top-K via importance riservato Wave 2 se Brier sotto-target.

### Inference integration + threshold (Area 4)

- **D-12 — Hook hybrid: prediction in `evaluate_proposal_for_bar`, decision in `risk_engine.evaluate_trade`.** Strategia:
  1. **Prediction step** (Phase 4 D-02 detector signature esteso): dopo che detectors producono `ProposalDraft`, in `evaluate_proposal_for_bar` aggiunto step finale `feature_vec = build_features(draft, indicators, ctx); raw_score, calibrated_prob = ml_filter.predict(feature_vec); draft.ml_raw_score = raw_score; draft.ml_calibrated_prob = calibrated_prob`. **Strategy NON filtra**, sempre ritorna draft (mai None per ML).
  2. **Decision step** (CLAUDE.md "risk_engine = unico gate"): `risk_engine.evaluate_trade(proposal, account_state, profile, cfg)` legge `proposal.ml_calibrated_prob`, applica `threshold = cfg.ML_THRESHOLD_BY_PROFILE[profile]`. Se `prob < threshold` → `RiskDecision(approved=False, reason="ml_prob_below_threshold: 0.32 < 0.45")`. Esistenti gate (SL distance, lot size, daily DD) invariati e applicati indipendentemente.
  
  **Vantaggi:** pure-function strategy preservata (Phase 4 SC#1), unico gate decisione (CLAUDE.md), same code path live + backtest (Phase 4 SC#4), audit trail unificato (RiskDecision.reason).
- **D-13 — `ProposalDraft` schema esteso (additive, default None).** Nuovi campi: `ml_raw_score: float | None = None`, `ml_calibrated_prob: float | None = None`, `ml_model_version: str | None = None` (es. "v1"). Backward-compat: se `ENABLE_ML_FILTER=false` o modello non disponibile, fields restano None, `risk_engine` skip ML gate. Phase 5 baseline backtest gira senza ML (ML non esiste ancora) → dataset prodotto pulito (no chicken-and-egg).
- **D-14 — Threshold per-profile: profit-curve optimized, mediana fold.** Su validation set di ogni fold, sweep `threshold ∈ [0.20, 0.70] step 0.01`, calcola `expectancy_pips(threshold)` per ogni profile. Threshold ottimale per profile = argmax expectancy. Threshold finale per profile (single value persistito) = mediana dei 10 fold-best (robusto a outlier). CONSERVATIVE tipicamente prob alta (sharpe priority), AGGRESSIVE prob bassa (volume priority). No magic number hardcoded. Persistito in `metadata.json` + caricato in `cfg.ML_THRESHOLD_BY_PROFILE`.
- **D-15 — Model artifact: joblib `.pkl` + sidecar `.metadata.json`.** Path REQ ML-10: `models/classifier_v{N}_{date}.pkl`. Bundle joblib contiene:
  ```python
  bundle = {
      "model": calibrated_classifier,  # CalibratedClassifierCV(LightGBM, method="isotonic" o "sigmoid")
      "features": [...],               # ordered list
      "categorical_features": ["symbol", "timeframe", "profile", "setup_name", "regime"],
      "threshold_by_profile": {"CONSERVATIVE": 0.55, "MODERATE": 0.45, "AGGRESSIVE": 0.35},
      "version": "v1",
  }
  joblib.dump(bundle, path, compress=3)
  ```
  Sidecar JSON `models/classifier_v{N}_{date}.metadata.json`:
  ```json
  {
    "version": "v1",
    "train_date": "2026-05-08",
    "git_sha": "...",
    "dataset_path": "data/training/baseline_decisions.parquet",
    "dataset_hash": "sha256:...",
    "n_train_rows": 9847,
    "n_features": 47,
    "fold_metrics": [{"fold": 1, "brier": 0.182, "ece": 0.041, "auc_pr": 0.521, "n_test": 985}, ...],
    "scale_pos_weight_per_fold": [2.31, 2.28, ...],
    "calibrator_winner_per_fold": ["isotonic", "isotonic", "sigmoid", ...],
    "threshold_by_profile": {...},
    "lightgbm_version": "4.3.0",
    "sklearn_version": "1.4.2"
  }
  ```
  Walk-forward fold models persistiti in `models/folds/v{N}_{date}/fold_{k}.pkl + .metadata.json` (10 fold × 2 file = 20 file) per drift Phase 9 ricalibration standalone. Final model = retrain su tutto dataset (post walk-forward eval) + calibrator vincitore aggregate.

### Engineering principles

- **D-16 — Pure-function strategy preservata.** `evaluate_proposal_for_bar` deterministica, no I/O dentro. Modello caricato 1 volta a bootstrap (singleton `strategy/ml_filter.py:_MODEL_CACHE`), passato come dipendenza esplicita o module-level cache. Process-safe (Phase 6 D-A1 ProcessPoolExecutor: ogni worker carica proprio singleton al primo predict).
- **D-17 — No future leakage by construction.** Walk-forward expanding + embargo per-TF (D-05/D-07) garantisce training set strictly precedente test set + buffer timeout. Feature snapshot a `decision_ts_utc` (Phase 5 D-22 bar-close discipline). Dataset `baseline_decisions.parquet` già garantisce no future (Phase 5 D-21).
- **D-18 — Calibration: Platt + Isotonic, pick winner per Brier per fold.** Per ogni fold: train `CalibratedClassifierCV(method="sigmoid")` (Platt) e `CalibratedClassifierCV(method="isotonic")` su val set. Brier score su test fold. Vincitore = min Brier. `metadata.json` registra winner per fold per audit. ECE (Expected Calibration Error) e reliability diagram generati per fold (REQ ML-04 SC#3).
- **D-19 — Italian commenti/log/rationale.** CLAUDE.md compliance. Function docstring + log message in italiano. Identifier code (variable, function, parameter) in inglese (convenzione Python).
- **D-20 — Inference latency <10ms (REQ ML-05 SC#4).** Single sample predict path: feature_vec build (numpy array) + `bundle.model.predict_proba(X)[:, 1]`. Benchmark obbligatorio in test (Phase 7 plan). Batch inference (Phase 8 MCP tool) non vincolato a 10ms.

### Claude's Discretion

- **Hyperparameter LightGBM tuning depth.** Default raccomandati (`n_estimators=500, learning_rate=0.05, num_leaves=31, min_child_samples=20, feature_fraction=0.9, bagging_fraction=0.8, bagging_freq=5`). Grid search opzionale Wave 2 se Brier sotto-target. No tuning iniziale (early stopping val gestisce overfitting).
- **Feature scaling.** LightGBM scale-invariant (tree-based) → no StandardScaler/MinMaxScaler upfront. Verificare comunque outlier handling (es. ATR estremi su flash crash USDJPY 2015 CHF event). Decisione: lasciare raw, log info distribution per fold.
- **Calibration set source.** Calibrator può fitness su val set (last 20% train) oppure su test fold (Lopez de Prado approach). Default: **val set** (semplice, no leak). Test fold solo per Brier/ECE/AUC-PR finali.
- **Recent trades outcome encoding.** Phase 5 D-02 ha `recent_trades_outcome_5 (encoded W/L/B/-)`. Possibile encoding: 5 colonne separate (`recent_trade_1, ..., recent_trade_5`) o singola string concat. Default: 5 colonne categorical (LightGBM gestisce nativo).
- **Feature `confidence` overlap con `calibrated_prob`.** Phase 4 D-08 emette `confidence` heuristica nel ProposalDraft. Phase 7 produce `calibrated_prob` ML-based che SOSTITUISCE `confidence` come signal primario. `confidence` resta come feature input per il modello (ML può imparare a correggere heuristic). Default: include `confidence` nelle feature numeriche.
- **Final model retrain on full dataset.** Dopo walk-forward eval (Brier/ECE per fold), retrain modello su 100% dataset per maximum data utilization in production. Calibrator finale = vincitore aggregate (mode tra 10 fold winner). Default: si, retrain finale post-eval.
- **Telemetry inference live.** Log per ogni predict: `(symbol, tf, setup_name, profile, calibrated_prob, threshold, approved/rejected, reason)`. File rotativo `logs/ml_inference.log`. Phase 9 drift monitor consuma. Default: si, attivo da Phase 7 deploy.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project locked specs
- `.planning/PROJECT.md` — milestone scope, LightGBM lock, walk-forward mandatory, calibration > confidence, Phase 9 drift Phase 11 paper deploy
- `.planning/REQUIREMENTS.md` §ML — ML-01 (feature extraction), ML-02 (LightGBM binary), ML-03 (walk-forward no shuffle), ML-04 (Platt + Isotonic + Brier winner), ML-05 (inference API raw + calibrated), ML-06 (filter + confidence override), ML-10 (versioned `models/classifier_v{N}_{date}.pkl`)
- `.planning/ROADMAP.md` §Phase 7 — goal, 5 success criteria, requirement mapping

### Prior phase carry-forward (MUST READ)
- `.planning/phases/01-backtest-engine/01-CONTEXT.md` — D-06 walk-forward harness (RIUSARE per ML walk-forward, no fork), D-07 SQLite schema (per replay_decision Phase 6 lookup compat se necessario), D-09 bar-close discipline
- `.planning/phases/02-indicators-library/02-CONTEXT.md` — D-04 ExtendedIndicators dataclass (FEATURE INPUT a ML), D-09 no future leakage (preservato in dataset Phase 5), D-15/16 regime classifier (categorical feature D-10)
- `.planning/phases/03-patterns-catalog/03-CONTEXT.md` — `PatternHit` dataclass (catturato da Phase 4 ProposalDraft factors)
- `.planning/phases/04-strategy-refactor/04-CONTEXT.md` — D-02 detector signature (ESTENDERE con ml_filter step), D-03 ProposalDraft (ESTENDERE schema D-13), D-08 5-factor + profile_filters (`min_grade`/`min_rr`/`min_confidence` complementari a ML threshold), D-13 drive-bar pattern, D-15 engineering principles
- `.planning/phases/05-baseline-backtest/05-CONTEXT.md` — D-02 baseline_decisions.parquet schema (DATASET INPUT), D-04 outcome multi-label (D-01/02/03 Phase 7 encoding), D-05 timeout_bars (D-07 embargo), D-11 profile matrix (D-09 single model con profile feature), D-13 run_id format
- `.planning/phases/06-mcp-tools-part-1/06-CONTEXT.md` — D-D2 replay_decision (riproduce ML prediction se modello attivo), D-A2 SQLite shared, D-F2 error envelope (per ML errors come `ml_model_unavailable`)

### Codebase maps
- `.planning/codebase/STRUCTURE.md` — flat root layout, package `strategy/` (Phase 4), `models/` directory NEW per artifact
- `.planning/codebase/ARCHITECTURE.md` — strategy/risk_engine/scheduler/broker layering, ML hook punti
- `.planning/codebase/STACK.md` — Python 3.12 (Anaconda), pandas, **lightgbm NEW dep**, **scikit-learn NEW dep** (CalibratedClassifierCV)
- `.planning/codebase/CONVENTIONS.md` — snake_case, dataclass, leading-underscore handler, italiano commenti/log
- `.planning/codebase/TESTING.md` — pytest, mock Mt5Client, fixture deterministica per ML test

### Existing code (touch / extend)
- `strategy/evaluator.py::evaluate_proposal_for_bar` (Phase 4) — ESTENDERE con ML prediction step (D-12, prediction-only, no filter)
- `strategy/models.py::ProposalDraft` (Phase 4 D-03) — ESTENDERE schema con `ml_raw_score, ml_calibrated_prob, ml_model_version` (D-13, additive, default None)
- `strategy/ml_filter.py` **NEW** — singleton model loader (`_MODEL_CACHE`), `predict(feature_vec) → (raw, calibrated)`, `build_features(draft, indicators, ctx) → np.ndarray`
- `strategy/training.py` **NEW** — script training pipeline: load dataset → walk-forward 10 fold → train fold k → calibrate Platt/Isotonic → eval Brier/ECE/AUC-PR → save fold artifacts → retrain final on full dataset → save final artifact + metadata.json
- `risk_engine.py::evaluate_trade` — ESTENDERE con ML threshold gate (D-12 decision step, dopo gate classici)
- `config.py::Config` — leggere new env: `ENABLE_ML_FILTER=true`, `ML_MODEL_PATH=models/classifier_v1_2026-05-08.pkl`, `ML_THRESHOLD_BY_PROFILE` (caricato runtime da metadata.json)
- `models.py::RiskDecision` — campo `reason` esistente cattura `ml_prob_below_threshold` (no schema change)
- `backtest/engine.py::BacktestEngine` (Phase 1) — constructor accetta `ml_filter` opzionale, default None (Phase 5 baseline gira senza ML)
- `data/training/baseline_decisions.parquet` (Phase 5 OUTPUT) — read-only INPUT a Phase 7 training
- `logger.py::init_logger` — nuovo logger `ml_inference` rotativo per telemetry D-claude (logs/ml_inference.log)

### Configs (estendere in questa fase)
- `.env.example` — aggiungere:
  ```
  # Phase 7 ML
  ENABLE_ML_FILTER=true
  ML_MODEL_PATH=models/classifier_v1_2026-05-08.pkl
  ML_INFERENCE_LATENCY_BUDGET_MS=10
  ```
- `data/configs/ml_training.yaml` **NEW** — orchestration knobs:
  ```yaml
  walk_forward:
    n_folds: 10
    window: expanding
    train_val_split_pct: 0.20
    embargo_bars_by_tf:
      M15: 96
      M30: 96
      H1: 120
  lightgbm:
    n_estimators: 500
    learning_rate: 0.05
    num_leaves: 31
    min_child_samples: 20
    feature_fraction: 0.9
    bagging_fraction: 0.8
    bagging_freq: 5
    early_stopping_rounds: 50
  calibration:
    methods: ["sigmoid", "isotonic"]
    winner_metric: "brier"
  threshold_optimization:
    sweep_min: 0.20
    sweep_max: 0.70
    sweep_step: 0.01
    objective: "expectancy_pips"
    aggregate: "median"
  output:
    models_dir: "models"
    fold_models_subdir: "folds"
  ```

### Output paths (creare in questa fase)
- `models/classifier_v1_{date}.pkl` (joblib bundle)
- `models/classifier_v1_{date}.metadata.json` (sidecar audit)
- `models/folds/v1_{date}/fold_{k}.pkl + .metadata.json` (10 fold × 2 file = 20 file)
- `.planning/research/ml-training-{date}.md` (training report: fold Brier/ECE/AUC-PR table, calibration plots, feature importance, threshold optimization curves)
- `.planning/research/ml-reliability-curves/fold_{k}.png` (10 reliability diagrams)
- `logs/ml_inference.log` (telemetry rotativo, da Phase 7 deploy)
- `tests/fixtures/ml/sample_decision_dataset.parquet` (mini dataset per unit test deterministico)

### Skills
- `forex-algo-dev` — bar boundary discipline, no future leakage, walk-forward, calibration over confidence, transaction-cost realism, regime awareness. Critico per validation D-05/06/07/17/18.
- `forex-trader-pro` — semantica feature columns (5-factor confluence, A/B/C/D setup type), threshold profile expectations.

### External libs (NEW deps Phase 7)
- `lightgbm >= 4.3.0` (binary classifier, `categorical_feature` native, early stopping callback)
- `scikit-learn >= 1.4.0` (`CalibratedClassifierCV` Platt/Isotonic, `brier_score_loss`, `precision_recall_curve` per AUC-PR)
- `joblib >= 1.3.0` (bundle serialize, compress)
- `pyarrow` (Phase 5) — read parquet dataset
- `numpy` (Phase 5) — feature vector
- Test: `pytest`, fixture deterministica seed lockato

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `strategy/evaluator.py::evaluate_proposal_for_bar` (Phase 4 D-02) — pattern detector + ProposalDraft pipeline. Phase 7 estende con ML prediction step finale prima del return (D-12).
- `strategy/models.py::ProposalDraft` (Phase 4 D-03) — dataclass mutabile, additive fields D-13 ok.
- `risk_engine.evaluate_trade(proposal, account_state, profile, cfg)` (existing) — gate decisione, già parameterizzato per profile. ML threshold gate aggiunto come ultimo check prima `approved=True`.
- `data/training/baseline_decisions.parquet` (Phase 5 OUTPUT) — 10k–50k righe, schema lockato D-02. Read-only Phase 7 training.
- `data/configs/baseline.yaml` (Phase 5) — pattern config YAML + load fn (Phase 1 D-05). Riusato per `ml_training.yaml`.
- `logger.py::init_logger(cfg, name=...)` — RotatingFileHandler. Pattern riusato per `ml_inference.log`.
- `backtest/engine.BacktestEngine` (Phase 1) — strategy invocation invariata, accetta `ml_filter` opzionale via constructor.

### Established Patterns
- **Pure-function strategy** (Phase 4 SC#1) — preservato in D-12: ML prediction-only, no decisione, no I/O.
- **Single code path live + backtest** (Phase 4 SC#4) — preservato: `evaluate_proposal_for_bar` chiamato identicamente da entrambi.
- **risk_engine = unico gate** (CLAUDE.md) — preservato: ML threshold check dentro `evaluate_trade`.
- **Walk-forward harness Phase 1 D-06** — riusato per ML walk-forward (no fork).
- **Config YAML + frozen dataclass + env override** (Phase 1 D-05, Phase 5) — `ml_training.yaml` segue stesso pattern.
- **Singleton module-level cache** — `strategy/ml_filter.py:_MODEL_CACHE` pattern stdlib.
- **CREATE TABLE IF NOT EXISTS** + WAL mode SQLite (Phase 5 D-16) — non applicabile Phase 7 (artifact = .pkl, no DB).

### Hot Spots / Risks
- **Memory peak walk-forward** — 10 fold × full dataset in memoria (10k–50k righe × 47 feature × float64 ≈ 30-150 MB). OK su 16GB dev laptop.
- **LightGBM determinism** — `random_state` lockato in cfg, ma `bagging_fraction` + `feature_fraction` con seed → reproducibility test obbligatorio.
- **Calibration overfitting** — calibrator fit su val set (last 20% train fold) può overfit se val piccolo. Mitig: cross-val 3-fold dentro val (CalibratedClassifierCV `cv=3` default).
- **Threshold optimization reverse-leak** — sweep su val set per profit-curve, applicato a test set. Standard ML practice ma threshold leakage possibile se val troppo piccolo. Mitig: persistere `threshold_per_fold` in metadata, mediana fold robusto.
- **Feature schema drift** — se Phase 2 aggiunge ExtendedIndicators field dopo Phase 7 train, dataset retraining fallisce su schema. Mitig: `metadata.json` registra `n_features` + `features_list`, model loader valida schema match a inference time → error chiaro `feature_schema_mismatch`.
- **Inference latency >10ms** (REQ SC#4 violazione) — joblib load + predict_proba single sample ~1-3ms su LightGBM medium model (500 trees × 31 leaves). Margine OK. Benchmark test obbligatorio.
- **ProcessPoolExecutor + LightGBM model** — Phase 6 D-A1 worker carica modello al primo predict (singleton). Modello fork-safe (joblib bundle è pickle-able). OK.
- **calibrated_prob NaN / out-of-distribution** — feature mai vista in train (es. ATR estremo flash crash) può produrre prob estrema ma calibrata = OK (calibrator monotonic). Mitig: sanity check prob in `[0, 1]` prima return, log warning se outlier.
- **forex-trader-pro skill backward compat** — skill consume `evaluate_trade_proposal` MCP (Phase 8 estende con ml_score). Phase 7 NON modifica MCP; cambio solo interno `evaluate_proposal_for_bar` + `risk_engine`. Skill flow invariato.

### Integration Points
- **Phase 4 detector pipeline** — entry point ML prediction step. Phase 4 D-02 signature `(bars, indicators, ctx) → ProposalDraft | None` invariato (return type stesso, fields aggiuntivi).
- **risk_engine.evaluate_trade** — entry point ML decision gate. Threshold lookup per profile, RiskDecision.reason cattura motivo rigetto.
- **Phase 5 dataset** — read-only INPUT training. Schema D-02 garantito stabile.
- **Phase 6 replay_decision** — riproduce ML prediction se modello disponibile. Phase 7 espone API `ml_filter.predict()` chiamabile da `mcp/handlers/backtest.py::handle_replay_decision`.
- **Phase 8 MCP ML tool** — Phase 7 fornisce stable `strategy.ml_filter` API. Phase 8 wrappa in MCP tool `train_ml_filter`, `predict_trade_quality`, `get_ml_calibration` senza modifiche Phase 7 internals.
- **Phase 9 drift monitor** — consuma `logs/ml_inference.log` + `metadata.json` fold_metrics. Retrain trigger su ECE/Brier breach.
- **Phase 11 paper deploy** — ML attivo, threshold per profile applicato, drift monitor live.

</code_context>

<specifics>
## Specific Ideas

### Pipeline training script skeleton (D-09, D-15, D-18)

```python
# strategy/training.py
import joblib, json, hashlib, subprocess, lightgbm as lgb
import pandas as pd
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, precision_recall_curve, auc
from datetime import date
from pathlib import Path

def train_classifier(cfg_path: str = "data/configs/ml_training.yaml") -> Path:
    cfg = load_ml_training_config(cfg_path)
    df = pd.read_parquet(cfg.dataset_path)
    
    # Label encoding D-01/02/03
    df["y"] = (df["exit_reason"] == "TP_HIT").astype(int)
    
    # Feature schema D-10/11
    cat_features = ["symbol", "timeframe", "profile", "setup_name", "regime"]
    num_features = [c for c in df.columns if c not in cat_features + 
                    ["y", "exit_reason", "outcome", "pnl_pips", "pnl_money", 
                     "bars_held", "decision_ts_utc", "entry_ts_utc", "exit_ts_utc",
                     "run_id", "slice_id"]]
    feature_cols = num_features + cat_features
    
    # Walk-forward expanding 10 fold con embargo per-TF (D-05/06/07)
    folds = build_walk_forward_folds(df, n_folds=cfg.walk_forward.n_folds, 
                                      embargo_by_tf=cfg.walk_forward.embargo_bars_by_tf)
    
    fold_metrics = []
    fold_models = []
    fold_calibrators = []
    
    for k, (train_idx, val_idx, test_idx) in enumerate(folds):
        X_train = df.iloc[train_idx][feature_cols]
        y_train = df.iloc[train_idx]["y"]
        X_val = df.iloc[val_idx][feature_cols]
        y_val = df.iloc[val_idx]["y"]
        X_test = df.iloc[test_idx][feature_cols]
        y_test = df.iloc[test_idx]["y"]
        
        # Class imbalance D-04
        spw = (y_train == 0).sum() / (y_train == 1).sum()
        
        # LightGBM training con early stopping su val Brier (D-08)
        model = lgb.LGBMClassifier(
            **cfg.lightgbm,
            scale_pos_weight=spw,
            objective="binary",
            random_state=42,
        )
        model.fit(X_train, y_train,
                  eval_set=[(X_val, y_val)],
                  callbacks=[lgb.early_stopping(cfg.lightgbm.early_stopping_rounds)],
                  categorical_feature=cat_features)
        
        # Calibration Platt + Isotonic, vincitore per Brier (D-18)
        platt = CalibratedClassifierCV(model, method="sigmoid", cv="prefit")
        iso = CalibratedClassifierCV(model, method="isotonic", cv="prefit")
        platt.fit(X_val, y_val)
        iso.fit(X_val, y_val)
        
        prob_platt_test = platt.predict_proba(X_test)[:, 1]
        prob_iso_test = iso.predict_proba(X_test)[:, 1]
        brier_platt = brier_score_loss(y_test, prob_platt_test)
        brier_iso = brier_score_loss(y_test, prob_iso_test)
        winner = "isotonic" if brier_iso < brier_platt else "sigmoid"
        winner_cal = iso if winner == "isotonic" else platt
        winner_prob_test = prob_iso_test if winner == "isotonic" else prob_platt_test
        
        # Metrics
        ece = expected_calibration_error(y_test, winner_prob_test, n_bins=10)
        precision, recall, _ = precision_recall_curve(y_test, winner_prob_test)
        auc_pr = auc(recall, precision)
        
        # Threshold optimization profit-curve per profile (D-14)
        threshold_per_profile = {}
        for profile in ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]:
            mask = df.iloc[val_idx]["profile"] == profile
            if mask.sum() == 0: continue
            prob_val = winner_cal.predict_proba(df.iloc[val_idx][feature_cols])[:, 1]
            best_t = profit_curve_optimal_threshold(
                prob=prob_val[mask],
                pnl_pips=df.iloc[val_idx][mask]["pnl_pips"],
                sweep=np.arange(cfg.threshold_optimization.sweep_min,
                                cfg.threshold_optimization.sweep_max,
                                cfg.threshold_optimization.sweep_step)
            )
            threshold_per_profile[profile] = best_t
        
        fold_metrics.append({
            "fold": k + 1,
            "brier": float(min(brier_platt, brier_iso)),
            "ece": float(ece),
            "auc_pr": float(auc_pr),
            "n_test": len(test_idx),
            "calibrator_winner": winner,
            "scale_pos_weight": float(spw),
            "threshold_per_profile": threshold_per_profile,
        })
        fold_models.append(model)
        fold_calibrators.append(winner_cal)
        
        # Save fold artifact (D-15 folds subdir)
        save_fold_artifact(k + 1, model, winner_cal, fold_metrics[-1], cfg)
    
    # Final model retrain on full dataset (Claude discretion)
    spw_full = (df["y"] == 0).sum() / (df["y"] == 1).sum()
    final_model = lgb.LGBMClassifier(**cfg.lightgbm, scale_pos_weight=spw_full,
                                       objective="binary", random_state=42)
    final_model.fit(df[feature_cols], df["y"], categorical_feature=cat_features)
    
    # Final calibrator = winner aggregate (mode tra fold)
    winners = [m["calibrator_winner"] for m in fold_metrics]
    final_method = max(set(winners), key=winners.count)
    final_cal = CalibratedClassifierCV(final_model, method=final_method, cv=5)
    final_cal.fit(df[feature_cols], df["y"])
    
    # Threshold finale = mediana fold per profile (D-14)
    final_thresholds = {}
    for profile in ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]:
        ts = [m["threshold_per_profile"].get(profile) for m in fold_metrics 
              if profile in m["threshold_per_profile"]]
        final_thresholds[profile] = float(np.median(ts)) if ts else 0.5
    
    # Bundle joblib (D-15)
    version = "v1"
    today = date.today().isoformat()
    bundle_path = Path(cfg.output.models_dir) / f"classifier_{version}_{today}.pkl"
    bundle = {
        "model": final_cal,
        "features": feature_cols,
        "categorical_features": cat_features,
        "threshold_by_profile": final_thresholds,
        "version": version,
    }
    joblib.dump(bundle, bundle_path, compress=3)
    
    # Sidecar metadata.json (D-15)
    metadata = {
        "version": version,
        "train_date": today,
        "git_sha": _git_sha(),
        "dataset_path": cfg.dataset_path,
        "dataset_hash": _file_sha256(cfg.dataset_path),
        "n_train_rows": int(len(df)),
        "n_features": len(feature_cols),
        "fold_metrics": fold_metrics,
        "threshold_by_profile": final_thresholds,
        "calibrator_winner_aggregate": final_method,
        "lightgbm_version": lgb.__version__,
        "sklearn_version": sklearn.__version__,
    }
    metadata_path = bundle_path.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2))
    
    return bundle_path
```

### ML filter inference singleton (D-12, D-16, D-20)

```python
# strategy/ml_filter.py
import joblib, json, numpy as np
from pathlib import Path
from threading import Lock

_MODEL_CACHE = None
_CACHE_LOCK = Lock()

def get_ml_filter(cfg):
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        with _CACHE_LOCK:
            if _MODEL_CACHE is None:
                _MODEL_CACHE = MLFilter.load(cfg.ML_MODEL_PATH)
    return _MODEL_CACHE

class MLFilter:
    def __init__(self, bundle, metadata):
        self.model = bundle["model"]
        self.features = bundle["features"]
        self.categorical_features = bundle["categorical_features"]
        self.threshold_by_profile = bundle["threshold_by_profile"]
        self.version = bundle["version"]
        self.metadata = metadata
    
    @classmethod
    def load(cls, path: str) -> "MLFilter":
        bundle = joblib.load(path)
        meta_path = Path(path).with_suffix(".metadata.json")
        metadata = json.loads(meta_path.read_text())
        return cls(bundle, metadata)
    
    def predict(self, feature_vec: np.ndarray) -> tuple[float, float]:
        # raw_score = pre-calibration logit (LightGBM raw output)
        # calibrated_prob = post-calibration probability [0, 1]
        if isinstance(self.model, CalibratedClassifierCV):
            calibrated_prob = float(self.model.predict_proba(feature_vec.reshape(1, -1))[0, 1])
            raw_score = float(self.model.calibrated_classifiers_[0].estimator.predict(
                feature_vec.reshape(1, -1), raw_score=True)[0])
        else:
            raw_score = float(self.model.predict(feature_vec.reshape(1, -1), raw_score=True)[0])
            calibrated_prob = float(self.model.predict_proba(feature_vec.reshape(1, -1))[0, 1])
        
        # Sanity check
        assert 0.0 <= calibrated_prob <= 1.0, f"calibrated_prob out of range: {calibrated_prob}"
        return raw_score, calibrated_prob

def build_features(draft, indicators, ctx) -> np.ndarray:
    """Costruisce feature vector ordinato matching training schema."""
    # Lookup field-by-field, ordine = MLFilter.features
    # Returns 1D np.ndarray con dtype float64 (categorical encoded come int)
    ...
```

### Hook in evaluate_proposal_for_bar (D-12)

```python
# strategy/evaluator.py — Phase 4 esteso Phase 7
def evaluate_proposal_for_bar(bars, indicators, ctx, ml_filter=None) -> ProposalDraft | None:
    draft = run_detectors(bars, indicators, ctx)  # Phase 4 invariato
    if draft is None:
        return None
    
    # Phase 7 prediction step (no decision)
    if ml_filter is not None:
        feature_vec = build_features(draft, indicators, ctx)
        try:
            raw, calibrated = ml_filter.predict(feature_vec)
            draft.ml_raw_score = raw
            draft.ml_calibrated_prob = calibrated
            draft.ml_model_version = ml_filter.version
        except Exception as e:
            log.warning("ML predict failed: %s — proceeding without ML score", e)
            # draft.ml_* restano None, risk_engine skip ML gate
    
    return draft
```

### Hook in risk_engine (D-12, D-14)

```python
# risk_engine.py — Phase 7 esteso
def evaluate_trade(proposal, account_state, profile, cfg) -> RiskDecision:
    # Gate classici esistenti
    if not within_risk_limits(proposal, account_state, profile, cfg):
        return RiskDecision(approved=False, reason="risk_limit_violation", ...)
    
    # Phase 7 ML gate (additive)
    if cfg.ENABLE_ML_FILTER and proposal.ml_calibrated_prob is not None:
        threshold = cfg.ML_THRESHOLD_BY_PROFILE.get(profile.name, 0.5)
        if proposal.ml_calibrated_prob < threshold:
            log_ml_inference(proposal, profile, threshold, approved=False, 
                             reason="ml_prob_below_threshold")
            return RiskDecision(
                approved=False,
                reason=f"ml_prob_below_threshold: {proposal.ml_calibrated_prob:.3f} < {threshold:.3f}",
                ml_score=proposal.ml_raw_score,
                ml_calibrated_prob=proposal.ml_calibrated_prob,
            )
        log_ml_inference(proposal, profile, threshold, approved=True, reason="ml_pass")
    
    return RiskDecision(approved=True, ...)
```

### Walk-forward fold builder con embargo per-TF (D-05/06/07)

```python
def build_walk_forward_folds(df: pd.DataFrame, n_folds: int, 
                               embargo_by_tf: dict[str, int]) -> list[tuple]:
    """Expanding window con embargo per-TF.
    Ritorna lista di (train_idx, val_idx, test_idx) per ogni fold."""
    df_sorted = df.sort_values("decision_ts_utc").reset_index(drop=True)
    total = len(df_sorted)
    folds = []
    
    # Split point: ogni fold k usa train fino t_k, test in [t_k + embargo, t_{k+1}]
    test_size = total // (n_folds + 1)  # ~9% per test fold (1 fold riservato per train iniziale)
    
    for k in range(n_folds):
        train_end = test_size * (k + 1)  # cumulative
        # Embargo per row dipende da timeframe della row
        embargo_offset = compute_embargo_offset(df_sorted, train_end, embargo_by_tf)
        test_start = train_end + embargo_offset
        test_end = min(test_start + test_size, total)
        if test_end <= test_start:
            continue  # fold non producibile
        
        # Train/val split: last 20% of train = val (D-08)
        val_start = int(train_end * 0.80)
        train_idx = df_sorted.index[:val_start]
        val_idx = df_sorted.index[val_start:train_end]
        test_idx = df_sorted.index[test_start:test_end]
        folds.append((train_idx, val_idx, test_idx))
    
    return folds
```

### Profit-curve threshold optimization (D-14)

```python
def profit_curve_optimal_threshold(prob: np.ndarray, pnl_pips: np.ndarray, 
                                     sweep: np.ndarray) -> float:
    """Threshold ottimale = max expectancy_pips su sweep."""
    expectancies = []
    for t in sweep:
        accepted = prob >= t
        if accepted.sum() == 0:
            expectancies.append(-np.inf)
            continue
        exp_pips = pnl_pips[accepted].mean()
        expectancies.append(exp_pips)
    return float(sweep[np.argmax(expectancies)])
```

### Expected Calibration Error (D-18 SC#3)

```python
def expected_calibration_error(y_true, y_prob, n_bins=10) -> float:
    """ECE = Σ_b (|B_b|/N) × |acc(B_b) - conf(B_b)|"""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = y_prob[mask].mean()
        ece += (mask.sum() / len(y_true)) * abs(bin_acc - bin_conf)
    return ece
```

</specifics>

<deferred>
## Deferred Ideas

- **ML-07 Failure clustering** — Phase 9. Cluster losing trades by feature vector (k-means/HDBSCAN), surface failure modes via feature importance.
- **ML-08 Drift monitoring** — Phase 9. Prediction distribution KS-stat + calibration ECE rolling window. Consume `logs/ml_inference.log` + `metadata.json`.
- **ML-09 Retrain trigger** — Phase 9. Drift threshold breach OR scheduled monthly OR manual via tool.
- **MCP tool ML** (`train_ml_filter`, `predict_trade_quality`, `get_ml_calibration`) — Phase 8. Wrappa stable `strategy.ml_filter` API.
- **`evaluate_trade_proposal` MCP-R4 ML extension** — Phase 8 (response include `ml_score` + `calibrated_prob`).
- **Multiclass target {WIN, LOSS, TIMEOUT, BREAKEVEN}** — rifiutato (REQ ML-04 Platt/isotonic binary-only). Riconsiderare se calibration multiclass robusta in literature.
- **3 modelli per profile (CONS/MOD/AGG separati)** — rifiutato (1 modello + profile feature più dati, generalizzazione superiore).
- **27 modelli per slice (symbol×TF×profile)** — rifiutato (N troppo basso, varianza alta, drift Phase 9 esplosivo).
- **Sample weight per pnl_pips (magnitude weighting)** — rifiutato Phase 7 (distorce calibration semantics REQ ML-05). Riservato Phase 9 expectancy optimization se utile.
- **Feature engineering ratios/deltas (`bb_width_pct`, `rsi_minus_50`, ecc.)** — rifiutato upfront (LightGBM cattura via tree splits). Riconsiderare Wave 2 se Brier sotto-target.
- **Feature selection top-K via importance** — riservato Wave 2 se overfitting evidente o inference latency margine sottile.
- **Hyperparameter grid search LightGBM** — riservato Wave 2 se Brier sotto-target con default.
- **Cross-language model export (lgb native txt)** — Phase 11+ se porting Java/C++. Phase 7 solo Python.
- **Recalibration standalone (calibrator file separato)** — Phase 9 drift retraining scenario. Phase 7 bundle monolitico.
- **Hot reload zero-downtime** — Phase 9 retrain trigger fires. Phase 7 deploy: load 1 volta a bootstrap.
- **A/B test attivazione ML (vs heuristic confidence)** — Phase 11 paper deploy gate. Compare backtest ML-on vs ML-off (Phase 8 ROADMAP SC#3 fa la versione baseline vs ML, paper deploy estende live).
- **Model rollback policy** — Phase 9. Se nuovo classifier_v(N+1) peggiora drift, rollback a v(N). Per ora `ML_MODEL_PATH` env manuale.
- **Telemetry ML inference dashboard** — Phase 9. Phase 7 produce `logs/ml_inference.log` rotativo, dashboard consumer in Phase 9.
- **MT5 server-side ML inference** — fuori scope. Modello sempre Python-side.
- **Online learning / partial_fit** — fuori scope v2. LightGBM supporta `init_model` per warm-start ma dataset Phase 9 retraining è batch.

</deferred>

---

*Phase: 07-ml-classifier*
*Context gathered: 2026-05-08 via /gsd:discuss-phase*
*Mode: discuss (4 aree, ~16 question, 20 decisioni dirette + 7 Claude discretion)*
