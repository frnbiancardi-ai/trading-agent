# Phase 7: ML Classifier — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 07-ml-classifier
**Areas discussed:** Target label encoding, Walk-forward fold design, Per-profile model strategy, Inference integration + threshold

---

## Target label encoding

### Q1: Target binary positive class (y=1)?

| Option | Description | Selected |
|--------|-------------|----------|
| Win = TP_HIT only | y=1 iff exit_reason==TP_HIT; SL/TIMEOUT/BREAKEVEN → y=0. "Trade quality" come full TP. | ✓ |
| Win = pnl_pips > 0 | y=1 se pnl_pips > 0 (include parziali e BE positivi). Più segnale numerico ma rumoroso. | |
| Win = pnl_pips > +R_threshold | y=1 se pnl_pips > frazione del SL (es. >+0.5R). Filtra rumore micro-positivo, soglia arbitraria. | |

**User's choice:** Win = TP_HIT only (raccomandato).
**Notes:** Calibrated probability interpretazione univoca: P(TP_HIT). Skill agentic threshold filtering semantica chiara.

---

### Q2: TIMEOUT trades handling?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop dal training set | Escludere righe outcome=TIMEOUT. Label pulito ma N inferiore. | |
| Conta come loss (y=0) | TIMEOUT → y=0. Modello impara "evita setup senza momentum" come failure mode. | ✓ |
| Outcome multiclass | Target {WIN, LOSS, TIMEOUT}. Multiclass calibration complica Platt/isotonic (binary-only). | |

**User's choice:** TIMEOUT = loss (y=0).
**Notes:** Capitale bloccato 24h+ su trade morto = costo opportunità reale. Modello impara segnale momentum implicit.

---

### Q3: BREAKEVEN trades handling?

| Option | Description | Selected |
|--------|-------------|----------|
| Loss (y=0) | Coerente con Q2. Single rule "y=1 ⟺ TP_HIT". BE residuale <2% dataset baseline. | ✓ |
| Drop | BE = ambiguo. Esclude righe. Mantieni segnale binary puro TP vs SL+TIMEOUT. | |
| Win (y=1) | Capital preservation = win parziale. Distorce calibration semantics. | |

**User's choice:** BREAKEVEN = loss (y=0).
**Notes:** Single rule audit-friendly, calibration interpretabile univocamente.

---

### Q4: Class imbalance (y=1 ~30% / y=0 ~70%) gestione?

| Option | Description | Selected |
|--------|-------------|----------|
| scale_pos_weight = N_neg/N_pos | LightGBM standard binary imbalanced. Tunable, calibration post valida. | ✓ |
| is_unbalance=true | LightGBM auto-balance. Black box, no override. | |
| sample_weight per pnl | Pesa per |pnl_pips|. Distorce calibration semantics. | |
| Nessun rebalancing | 30/70 borderline. Threshold post-cal compensa. Sub-ottimale. | |

**User's choice:** scale_pos_weight = N_neg/N_pos, ricalcolato per fold walk-forward.
**Notes:** Standard industria binary imbalanced, REQ ML-04 calibration compatibile, audit chiaro.

---

## Walk-forward fold design

### Q5: Window strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Expanding window | Train cresce: fold k usa [t_0, t_split_k]. Pattern long-term catturati. | ✓ |
| Rolling fixed | Train fisso (5y) shifta. Reattivo a drift, N fold inferiore. | |
| Hybrid expanding capped 10y | Compromesso. Hyperparameter cap_years da tunare. | |

**User's choice:** Expanding window.
**Notes:** forex-algo-dev raccomandato per regime non-stationary FX. Phase 1 D-06 walk_forward harness compatibile.

---

### Q6: Numero fold (PROJECT cap=10)?

| Option | Description | Selected |
|--------|-------------|----------|
| 10 fold | Cap PROJECT, ROADMAP SC#2. ~1k trade per test fold, statistical power decente. | ✓ |
| 5 fold | Pi`u dati per fold ma temporal coverage scarso. | |
| 20 fold | Granularità alta ma Brier rumoroso. Sopra cap. | |

**User's choice:** 10 fold.

---

### Q7: Embargo gap train/test?

| Option | Description | Selected |
|--------|-------------|----------|
| timeout_bars[tf] per TF | M15=96, M30=96, H1=120 bar. Tight upper-bound TIMEOUT cap. | ✓ |
| Embargo = 0 | Train/test contigui. Look-ahead leakage. Viola REQ ML-03. | |
| Embargo = 1 settimana fissa | 168h uniforme. Conservativo, copre edge case. | |

**User's choice:** Embargo = timeout_bars[tf].
**Notes:** Tight upper-bound, dataset perso ~0.16% trascurabile, audit D-05 single source.

---

### Q8: Train/val split per fold?

| Option | Description | Selected |
|--------|-------------|----------|
| Last 20% train = val | Temporal split, early stopping su val Brier. forex-algo-dev pattern. | ✓ |
| No val split, fixed n_estimators | Pi`u dati ma rischio overfitting. | |
| Time-series CV interno (3 sub-fold) | Pi`u robusto ma 30 modelli totali, overkill Phase 7. | |

**User's choice:** Last 20% train = val, temporal, early stopping val Brier.

---

## Per-profile model strategy

### Q9: Quanti modelli per profili?

| Option | Description | Selected |
|--------|-------------|----------|
| 1 modello + profile feature | LightGBM categorical. Pi`u dati = generalizzazione migliore. 1 file. | ✓ |
| 3 modelli per profile | Specializzazione ma N=10k per modello, drift triplicato. | |
| 1 modello + per-profile threshold | Decoupling prediction/decision (catturato in hybrid Q12). | |
| 27 modelli per slice | Massima specializzazione ma N troppo basso. | |

**User's choice:** Single model + profile come categorical feature.
**Notes:** Modello impara interazioni profile×regime×setup×symbol via tree splits.

---

### Q10: Symbol e timeframe come feature?

| Option | Description | Selected |
|--------|-------------|----------|
| Categorical features | LightGBM nativo. Distingue USDJPY safe-haven vs EURUSD, M15 vs H1. | ✓ |
| Solo profile, no symbol/TF | Modello cieco. Forza pattern universali. | |
| Symbol/TF + interaction esplicite | Over-engineering, LightGBM cattura interazioni nativo. | |

**User's choice:** Symbol + TF categorical.

---

### Q11: setup_name come feature?

| Option | Description | Selected |
|--------|-------------|----------|
| Categorical feature | LightGBM nativo, modello unico impara setup-specific patterns. | ✓ |
| 4 modelli per setup | Specializzazione ma N=2.5k borderline, drift quadruplicato. | |
| Drop setup_name | 5-factor breakdown cattura implicit, perde signal categoriale forte. | |

**User's choice:** setup_name categorical feature.

---

### Q12: Feature numeriche raw vs engineered?

| Option | Description | Selected |
|--------|-------------|----------|
| Raw ExtendedIndicators + ProposalDraft + ctx | LightGBM cattura interazioni, no engineering upfront. | ✓ |
| Raw + engineered ratios/deltas | bb_width_pct, rsi_minus_50, adx_x_atr. Over-engineering rischia. | |
| Feature selection top-K via importance | 2-step pipeline complica walk-forward. Wave 2 se necessario. | |

**User's choice:** Raw features only.

---

## Inference integration + threshold

### Q13: Hook ML nel pipeline?

| Option | Description | Selected (hybrid 1+3) |
|--------|-------------|----------|
| Inside evaluate_proposal_for_bar | Strategy filtra. Same code path live+backtest. | parziale |
| Wrapper in execution.run_once | Backtest bypassa ML. Asimmetria viola Phase 4 SC#4. | |
| Risk engine layer | ML come gate. Coerente "unico gate" CLAUDE.md. Rompe pure-function strategy. | parziale |

**User's choice:** **Hybrid opt 1 + opt 3** — prediction in `evaluate_proposal_for_bar` (attacca prob a ProposalDraft, NO filter), decision in `risk_engine.evaluate_trade` (threshold gate).
**Notes:** Pure-function strategy preservata, risk_engine = unico gate, same code path live+backtest, audit trail unificato in RiskDecision.reason.

---

### Q14: Threshold per profile?

| Option | Description | Selected |
|--------|-------------|----------|
| Profit-curve optimized per profile | Sweep [0.20, 0.70] step 0.01, max expectancy_pips. Mediana fold. | ✓ |
| Fixed 0.55/0.45/0.35 | Hardcoded. Magic number rischia drift. | |
| Quantile-based | q70/q50/q30. Stabile a calibration drift ma ignora expectancy. | |

**User's choice:** Profit-curve optimized per profile, mediana fold.
**Notes:** Dati-driven, no magic number. Persistito in metadata.json + caricato in cfg.ML_THRESHOLD_BY_PROFILE.

---

### Q15: Model artifact format?

| Option | Description | Selected |
|--------|-------------|----------|
| joblib + sidecar metadata.json | Standard sklearn. JSON greppable per audit/drift dashboard. | ✓ |
| lgb native + separate calibrator | Cross-language ma 3 file × 10 fold = 30 file, glue manuale. | |
| pickle puro singolo file | 1 file ma audit pessimo, joblib superior per ML payload. | |

**User's choice:** joblib `.pkl` + sidecar `.metadata.json`.
**Notes:** REQ ML-10 path conforme, walk-forward 10 fold gestibile (folds/ subdir), Phase 9 drift dashboard friendly.

---

## Claude's Discretion

- Hyperparameter LightGBM tuning: default raccomandati, no grid search iniziale.
- Feature scaling: LightGBM scale-invariant, no upfront StandardScaler.
- Calibration set source: val set (last 20% train), no leak.
- Recent trades outcome encoding: 5 colonne categorical separate.
- Feature `confidence` overlap: include come input ML (modello impara correggere heuristic).
- Final model retrain on full dataset post walk-forward eval.
- Telemetry ML inference: `logs/ml_inference.log` rotativo da Phase 7 deploy.

## Deferred Ideas

- ML-07/08/09 (failure clustering, drift monitor, retrain trigger) → Phase 9.
- MCP tool ML (`train_ml_filter`, `predict_trade_quality`, `get_ml_calibration`) → Phase 8.
- `evaluate_trade_proposal` MCP-R4 ML extension → Phase 8.
- Multiclass target — rifiutato (REQ ML-04 binary-only).
- 3 modelli per profile / 27 modelli per slice — rifiutato (N inferiore, drift esplosivo).
- Sample weight per pnl — rifiutato Phase 7 (distorce calibration). Riservato Phase 9.
- Feature engineering ratios/deltas — rifiutato upfront. Wave 2 se Brier sotto-target.
- Feature selection top-K — Wave 2 se overfitting o latency margine sottile.
- Hyperparameter grid search — Wave 2 se Brier sotto-target.
- Cross-language model export — Phase 11+ se porting.
- Recalibration standalone calibrator file — Phase 9 drift scenario.
- Hot reload zero-downtime — Phase 9 retrain trigger.
- A/B test attivazione ML — Phase 11 paper deploy.
- Model rollback policy — Phase 9.
- Telemetry dashboard — Phase 9 (Phase 7 produce log).
- Online learning / partial_fit — fuori scope v2.
