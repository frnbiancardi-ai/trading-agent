---
phase: 07
slug: ml-classifier
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: 07-RESEARCH.md §Validation Architecture + 07-PATTERNS.md §Notes for planner.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, `pytest.ini` con `pythonpath = .`) |
| **Config file** | `pytest.ini` (no changes required) |
| **Quick run command** | `pytest tests/test_ml_*.py -x --tb=short -m 'not integration'` (~45s realistic — 1000-iter latency bench + fixture train + AST walks; era ~15s ottimistico pre-iter1) |
| **Plan-scope command** | `pytest tests/test_ml_<plan_module>.py tests/test_ml_purity.py -x --tb=short` (~5–10s) |
| **Full suite command** | `pytest -x --tb=short` (~120s incl. Phase 1–6 regression) |
| **Estimated runtime** | <2 min full suite, <30s per-plan |
| **Hardware target** | Latency test: WSL2/Linux container OK at p95<10ms; p99 expected 13ms (Pitfall 4). Windows bare-metal achieves p99<10ms. |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_ml_<module>.py tests/test_ml_purity.py -x --tb=short` (sub-15s per module, purity gate ALWAYS runs to catch drift)
- **After every plan wave merge:** `pytest tests/ -x --tb=short` (full suite, target <2 min)
- **Before `/gsd-verify-work`:** Full suite green AND held-out-month smoke `python -m ml.train --cfg data/configs/ml.yaml --dry-run` (Plan 07-03 produces fold metrics in tmp dir, Plan 07-06 runs E2E on real model)
- **Max feedback latency:** ~15s per-task, ~120s per-wave, ~5 min for held-out-month smoke

---

## Per-Task Verification Map

**NB (rev iter1):** I `Task ID` con pattern `7-NN-MM` enumerano le verification SCs / `gpt_test`
(gpt_test-level granularita'). NON sono in 1:1 con i task numerici dei PLAN file (i plan hanno
2-3 task per file; la mappa ne ha ~25 fra unit, integration, AST walk). Vedi i `PLAN.md` per il
breakdown effettivo dei task implementativi.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | ML-01, ML-10 | T-7-01-01 (validation V5) | Parquet open=read-only, no write back | unit (AST) | `pytest tests/test_ml_purity.py -x` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 0 | ML-01 | T-7-01-02 (defensive parse) | `decision_context_json` parse fail → empty dict, no exception leak | unit | `pytest tests/test_ml_feature_extraction.py::test_derive_d_09_g_fields_from_ctx_json -x` | ❌ W0 | ⬜ pending |
| 7-01-03 | 01 | 0 | ML-01 | T-7-01-03 (encoding integrity) | `categorical_encodings` persisted; unknown value → -1 not silent | unit | `pytest tests/test_ml_feature_extraction.py::test_build_categorical_encodings_stable_order -x` | ❌ W0 | ⬜ pending |
| 7-01-04 | 01 | 0 | ML-01 | — | Snapshot test: deterministic output for fixed input | unit (snapshot) | `pytest tests/test_ml_feature_extraction.py::test_build_feature_vector_deterministic -x` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | ML-03 | T-7-02-01 (no-future-leakage AST) | `train_test_split(shuffle=True)` AST-banned across `ml/*.py` | unit (AST) | `pytest tests/test_ml_walk_forward.py::test_no_shuffle_split_ast_guard -x` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | ML-03 | T-7-02-02 (temporal ordering) | `max(train) < max(val) < min(test)` per fold | unit | `pytest tests/test_ml_walk_forward.py::test_ml_folds_temporal_order -x` | ❌ W0 | ⬜ pending |
| 7-02-03 | 02 | 1 | ML-03 | T-7-02-03 (embargo enforcement) | `min(test) - max(train) >= max(embargo_bars_by_tf)` per D-07 | unit | `pytest tests/test_ml_walk_forward.py::test_ml_folds_embargo_respected -x` | ❌ W0 | ⬜ pending |
| 7-02-04 | 02 | 1 | ML-03 | — | 10 fold prodotti su dataset 1076-row (val₁ ~20, val₃ ~50+) | unit | `pytest tests/test_ml_walk_forward.py::test_ml_folds_count_and_sizes_on_real_parquet -x` | ❌ W0 | ⬜ pending |
| 7-03-01 | 03 | 2 | ML-02 | T-7-03-01 (LightGBM determinism) | `random_state=42` lockato; seed identico → output identico | unit | `pytest tests/test_ml_train.py::test_lgbm_trains_deterministic_on_fixture -x` | ❌ W0 | ⬜ pending |
| 7-03-02 | 03 | 2 | ML-04 | T-7-03-02 (sklearn 1.8 manual cal) | NO `CalibratedClassifierCV(cv='prefit')`; manual Platt/Isotonic only | unit | `pytest tests/test_ml_calibration.py::test_manual_calibration_no_prefit -x` | ❌ W0 | ⬜ pending |
| 7-03-03 | 03 | 2 | ML-04 | T-7-03-03 (val<50 isotonic guard) | `pick_brier_winner(val_size=20)` returns `"sigmoid"` forzato | unit | `pytest tests/test_ml_calibration.py::test_brier_winner_val_below_50_picks_platt -x` | ❌ W0 | ⬜ pending |
| 7-03-04 | 03 | 2 | ML-04 | T-7-03-04 (ECE last bin) | `ECE` includes `y_prob == 1.0` (last bin `<=`, NOT `<`) | unit | `pytest tests/test_ml_calibration.py::test_ece_includes_y_prob_eq_1 -x` | ❌ W0 | ⬜ pending |
| 7-03-05 | 03 | 2 | ML-02, ML-04 | — | `scale_pos_weight = N_neg/N_pos` ricalcolato per fold (D-04) | unit | `pytest tests/test_ml_train.py::test_scale_pos_weight_per_fold -x` | ❌ W0 | ⬜ pending |
| 7-04-01 | 04 | 3 | ML-04 | T-7-04-01 (threshold reverse-leak) | Threshold optimization on val set ONLY (never test fold) | unit | `pytest tests/test_ml_threshold.py::test_threshold_sweeps_val_not_test_ast_check -x` | ❌ W0 | ⬜ pending |
| 7-04-02 | 04 | 3 | ML-04 | T-7-04-02 (median aggregator) | `median_across_folds([0.45,...])` → mediana, NOT media | unit | `pytest tests/test_ml_threshold.py::test_median_across_folds_robust -x` | ❌ W0 | ⬜ pending |
| 7-04-03 | 04 | 3 | ML-04 | — | Profit-curve argmax expectancy_pips su sweep deterministico | unit | `pytest tests/test_ml_threshold.py::test_profit_curve_max_at_expected_threshold -x` | ❌ W0 | ⬜ pending |
| 7-05-01 | 05 | 4 | ML-05, ML-10 | T-7-05-01 (schema validation at load) | `MLFilter.load(path)` raises `FeatureSchemaMismatchError` if `n_features != len(features)` | unit | `pytest tests/test_ml_inference.py::test_bundle_load_schema_validation -x` | ❌ W0 | ⬜ pending |
| 7-05-02 | 05 | 4 | ML-05 | T-7-05-02 (range check) | `predict()` raises `ValueError` if calibrated_prob ∉ [0,1] | unit | `pytest tests/test_ml_inference.py::test_predict_returns_valid_proba -x` | ❌ W0 | ⬜ pending |
| 7-05-03 | 05 | 4 | ML-05 | T-7-05-03 (latency budget) | p95 < 10ms on 1000-sample benchmark; NOT p99 (OS jitter) | unit (benchmark) | `pytest tests/test_ml_inference.py::test_inference_latency_p95_under_10ms -x` | ❌ W0 | ⬜ pending |
| 7-05-04 | 05 | 4 | ML-05 | T-7-05-04 (singleton thread-safety) | Double-check lock; concurrent `get_ml_filter` returns same instance | unit | `pytest tests/test_ml_inference.py::test_get_ml_filter_singleton_thread_safe -x` | ❌ W0 | ⬜ pending |
| 7-05-05 | 05 | 4 | ML-10 | T-7-05-05 (metadata schema) | `metadata.json` contains version, git_sha, dataset_hash, fold_metrics, thresholds, lib versions | unit | `pytest tests/test_ml_artifact.py::test_metadata_schema_complete -x` | ❌ W0 | ⬜ pending |
| 7-06-01 | 06 | 5 | ML-06 | T-7-06-01 (gate enforcement) | `evaluate_trade(...calibrated_prob=0.30, threshold=0.45)` → `approved=False` reason="ml_prob_below_threshold" | integration | `pytest tests/test_risk.py::test_ml_gate_rejects_low_prob -x` | ❌ W0 | ⬜ pending |
| 7-06-02 | 06 | 5 | ML-06 | T-7-06-02 (backward-compat) | `ENABLE_ML_FILTER=false` OR `ml_calibrated_prob is None` → ML gate skipped, classic gates intact | integration | `pytest tests/test_risk.py::test_ml_gate_disabled_passthrough -x` | ❌ W0 | ⬜ pending |
| 7-06-03 | 06 | 5 | ML-06, STRAT-08 | T-7-06-03 (purity preservation) | `evaluate_proposal_for_bar` still passes existing AST purity gate (no broker, no logging) | unit (AST) | `pytest tests/test_strategy_purity.py -x` (existing) | ✅ existing | ⬜ pending |
| 7-06-04 | 06 | 5 | ML-06 | T-7-06-04 (single-callsite invariant) | ML attach happens ONCE in `strategy/__init__.py`; adapters live/backtest unchanged | unit (AST) | `pytest tests/test_ml_integration.py::test_ml_attached_at_single_callsite_ast_guard -x` | ❌ W0 | ⬜ pending |
| 7-06-05 | 06 | 5 | ML-06 | T-7-06-05 (held-out month E2E) | Real parquet held-out month: rejection rate within ±10pp of expected per profile | integration | `pytest tests/test_ml_held_out_month.py::test_held_out_e2e_rejection_rate -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 = Plan 07-01 task list. ALL new test files + AST purity gate ACTIVE FROM DAY 1.

- [ ] `ml/__init__.py` — package barrel
- [ ] `ml/feature_extraction.py` — D-09-G derivation + X/y build + categorical encoding map
- [ ] `data/configs/ml.yaml` — orchestration config (D-05/06/07/08/14)
- [ ] `tests/test_ml_purity.py` — clone of `tests/test_strategy_purity.py:1-232`, `PURE_MODULES` swap to `ml/*.py`
- [ ] `tests/test_ml_feature_extraction.py` — 4 tests (D-09-G derivation, encoding stability, snapshot, schema)
- [ ] `tests/fixtures/ml/sample_decision_dataset.parquet` — 200-row deterministic fixture (seed=42, 3 symbols × 3 TF × 3 profile, ~28% TP rate; post-iter-2 _N_ROWS bump)
- [ ] `pip install lightgbm>=4.6.0 scikit-learn>=1.8.0 joblib>=1.5.3` — verified available, only update `requirements.txt`

Subsequent waves' test infrastructure:

- [ ] Plan 02: `ml/walk_forward.py` + `tests/test_ml_walk_forward.py` (5 tests: temporal-order, embargo, no-shuffle AST, count/sizes, val-empty edge)
- [ ] Plan 03: `ml/calibration.py` + `ml/train.py` + `tests/test_ml_calibration.py` + `tests/test_ml_train.py` (5+5 tests)
- [ ] Plan 04: `ml/threshold.py` + `tests/test_ml_threshold.py` (3 tests: argmax, median, profile-specific)
- [ ] Plan 05: `ml/inference.py` + `ml/artifact.py` + `tests/test_ml_inference.py` + `tests/test_ml_artifact.py` (5+2 tests incl. latency benchmark)
- [ ] Plan 06: `strategy/__init__.py` + `strategy/proposal.py` + `risk_engine.py` extensions + `tests/test_risk.py` extension + `tests/test_ml_integration.py` + `tests/test_ml_held_out_month.py` (5 tests)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reliability diagrams visual sanity check (curve close to diagonal, no extreme bias) | ML-04 / SC#3 | Plot quality is qualitative — automated test only asserts file exists | Open `.planning/research/ml-reliability-curves/fold_{1..10}.png` after Plan 03 run — visually verify monotonic-ish points near the y=x diagonal; isolated outlier bins acceptable on val<50 folds |
| Training report `.planning/research/ml-training-{date}.md` review | ML-02/03/04 | Aggregate metrics interpretation requires trader intuition (Brier reasonable for FX trade-quality?) | Open the markdown after Plan 03 run — verify fold Brier ≤ ~0.20, ECE ≤ ~0.10, AUC-PR significantly above class-imbalance baseline (~0.28 = WIN rate). Outlier folds flagged in notes section. |
| Held-out month rejection rate per profile (P95<10ms latency observed live) | ML-06 / SC#5 | Realistic distribution of `calibrated_prob` per profile — automated asserts a sane range; trader confirms it's reasonable | After Plan 06 E2E run: review `logs/ml_inference.log` for the held-out month — confirm reject rate is **tipico 30%-60%** per profile (CONSERVATIVE highest, AGGRESSIVE lowest), **sanity range automated test 20%-80%** (rev iter1, allineato con `test_held_out_e2e_rejection_rate` post-tightening). `predict_latency_ms` p95 < 10 across 1000+ inferences |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies declared
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING test files
- [ ] No watch-mode flags (`pytest --watch` proibito in CI/local sampling)
- [ ] Feedback latency <15s per-task, <120s per-wave
- [ ] AST purity gate `tests/test_ml_purity.py` is ACTIVE FROM Wave 0 (prevents drift)
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 complete

**Approval:** pending
