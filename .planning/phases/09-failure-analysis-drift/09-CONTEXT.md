# Phase 9: Failure Analysis + Drift — Context

**Gathered:** 2026-05-12
**Status:** Ready for planning (`/gsd-plan-phase 9`)
**Source:** `/gsd-discuss-phase 9` interactive session — 4 aree discusse, 16 decisioni catturate (D-09-A1..A4, D-09-B1..B4, D-09-C1..C4, D-09-D1..D4)

<domain>
## Phase Boundary

Aggiungere alla pipeline ML post-Phase-7 quattro capability di monitoring + management:

1. **Failure clustering offline** (ML-07 + MCP-07): HDBSCAN su losing trade baseline dataset per identificare loss-mode pattern feature-space, esposti via `get_failure_clusters(top_n)`.
2. **Drift monitor 3-tier** (ML-08 + MCP-08 + INT-03): prediction-distribution KS + calibration ECE + top-K feature drift vs static training reference, con alarm threshold .env, persistenza `drift_log.db` SQLite, CLI dashboard `scripts/show_drift.py` produce `.planning/research/drift-report-{date}.md`.
3. **Retrain trigger workflow** (ML-09): drift breach automatic + APScheduler monthly cron + manual MCP `trigger_retrain()` — tutti idempotent dedup, tutti riusano Phase 8 `train_ml_filter` worker via JobQueue cap=1 condiviso, con auto-validation gate ECE-regression + KS-divergence + threshold-sweep prima di atomic promote.
4. **Suggest position action** (MCP-18): hybrid 4-rule (R-multiple BE+partial+full + Time stop) + ML re-evaluation thesis check con structured rationale + profile-aware .env thresholds. Read-only suggest — non muta posizione (skill chiama `handle_modify_position` Phase 6 Plan 06-04 se accetta).

**7 requirements coperti:** ML-07, ML-08, ML-09, MCP-07, MCP-08, MCP-18, INT-03.

**4 success criteria ROADMAP:**
1. Failure clustering identifica ≥3 distinct loss-mode cluster su baseline con feature-importance interpretation (HDBSCAN exemplar + feature-distribution summary)
2. Drift monitor logga prediction KS-stat + ECE per rolling window; alarm fires when threshold breached
3. Retrain trigger fires correttamente su simulated drift; new model versioned via auto-validation gate, loaded senza service interruption (atomic rename + MLFilter singleton hot-reload)
4. `suggest_position_action(position_id)` ritorna hold/move_sl/partial_close/full_close + structured rationale, integration-tested su demo positions

**Out of scope (deferred):**
- Delta clustering baseline vs ml_on parquet (Phase 9 v2 condizionale a Phase 8 D-08-D5 NON_TRIVIAL_IMPROVEMENT verdict)
- Rolling reference window drift comparison (Phase 11+ "diagnostic detail" ~100 LOC retroactive)
- Multi-tier severity alarm (warning/critical/breach) — Phase 11+ ~50 LOC retroactive
- Auto-disable ENABLE_ML_FILTER on N consecutive validation fail / exponential backoff / halt-auto-triggers — Phase 11+ informato da paper deploy ops data
- Manual override force/reject MCP tools per validation gate — Phase 11+ ~50 LOC
- Volatility shrink + MTF reversal + Spread expansion rules per suggest — Phase 9 v2 / Phase 10 (MTF latency + Phase 10 news dep)
- Failure cluster match integration in `suggest_position_action` modulazione severity — Wave 2 add-on ~50 LOC
- OS cron + script standalone (out-of-MCP retrain) — Phase 11+ se DEPLOY-02 emerge uptime-independence requirement

</domain>

<prior_decisions>
## Carry-forward decisions (NOT re-asked)

### From Phase 6 (MCP package conventions)
- **mcp_tools/handlers/ pattern**: handler signature `handle_<tool>(args: dict, deps..., cfg) → dict response`. Phase 9 aggiunge `mcp_tools/handlers/drift.py` + `mcp_tools/handlers/cluster.py` + `mcp_tools/handlers/position_action.py` (oppure unico `mcp_tools/handlers/ml_ops.py` da decidere in plan-phase).
- **ErrorCodes envelope**: `mcp_tools/errors.py` (validation_failed, internal_error, not_found).
- **JobQueue ProcessPoolExecutor**: cap=1 condiviso (`MCP_MAX_CONCURRENT_RUNS`, Phase 6 D-A4 + Phase 8 D-08-A2). Phase 9 retrain trigger riusa la stessa coda.
- **BarSource D-D1 strict-<**: per snapshot temporali NOW in `suggest_position_action`.
- **handle_modify_position + handle_get_position_state** (Phase 6 Plan 06-04 D-B1, D-B3, MCP-17): MCP-18 chiama `handle_get_position_state` per posizione corrente; non chiama mt5_client direttamente.
- **trades.db convention**: WAL mode, append-only tables, schema migration idempotent via `ALTER TABLE ADD COLUMN IF NOT EXISTS`.
- **EXECUTION_MODE=shadow mandate**: MCP-18 è read-only suggest, NON muta posizione.

### From Phase 7 (ML pipeline)
- **D-01 target encoding LOCKED**: `y=1 ⟺ exit_reason==TP_HIT`, everything else `y=0`. Phase 9 failure cluster usa stesso encoding (D-09-A2).
- **D-07 embargo per-TF**: già rispettato da training pipeline. Phase 9 drift monitor non re-applica (reference = static training distribution).
- **D-10 categorical features LOCKED**: `["symbol", "timeframe", "profile", "setup_name", "regime"]`. Failure cluster + feature drift escludono questi da KS-test (categorical → chi-square future add-on).
- **D-12 hybrid hook**: prediction in `evaluate_proposal_for_bar`, decision (threshold) in `risk_engine.evaluate_trade`. MCP-18 `suggest_position_action` chiama `MLFilter.predict()` mid-trade (OOD inference, caveat surfaced in rationale).
- **D-15 bundle schema**: `models/classifier_v{N}_{date}.pkl` + sidecar `.metadata.json` con `fold_metrics` (ECE per fold + aggregate), `threshold_by_profile`, `dataset_hash` (sha256), `git_sha`, `feature_importance_`. Phase 9 drift compute riusa metadata reference; auto-validation gate confronta candidate vs reference ECE.
- **D-17 no future leakage**: training set strictly precedente test set. Phase 9 drift reference = training distribution post-D-17 = audit-anchored.
- **D-20 inference latency <10ms**: MCP-18 + drift compute riusano stesso `MLFilter.predict` singleton — latenza preservata.
- **ENABLE_ML_FILTER=false default** (D-07-06-11): zero-impact rollout. MCP-18 funziona con ENABLE_ML_FILTER=false (rule-based component sufficiente, ML re-eval skipped, rationale.ml_check = null + flag `ml_filter_disabled: true`).
- **Telemetry source LOCKED** (Claude discretion + PROJECT.md L106): `logs/ml_inference.log` rotativo per ogni predict. Phase 9 drift monitor consuma per current-window prediction distribution.
- **ProposalDraft schema esteso** (D-13): include `ml_raw_score`, `ml_calibrated_prob`, `ml_model_version`. Phase 9 D-09-D4 persiste `ml_calibrated_prob` in trades_log a entry time.

### From Phase 8 (MCP ML tools + retrain coordination)
- **D-08-A1 worker top-level picklable**: `_train_ml_filter_worker(args, cfg_dict)`. Phase 9 retrain trigger (D-09-C1) enqueue lo stesso worker — zero duplication.
- **D-08-A2 cap=1 condiviso**: protegge race su `data/training/baseline_decisions/part-0.parquet`. Phase 9 retrain trigger eredita protezione by construction.
- **D-08-A3 no cancel, fire-and-forget**: Phase 9 dedup idempotent (D-09-C3) aderisce — niente cancel introdotto.
- **D-08-B1 baseline parquet input**: Phase 9 retrain usa stesso path. Phase 9 failure cluster (D-09-A1) input.
- **D-08-B3 sha256 strict-fail pre-training**: protezione data integrity ereditata; Phase 9 retrain non duplica.
- **D-08-D4 degraded slices analysis Phase 8 INT-02**: input strutturato per Phase 9 drift monitor + cluster (operator interpretation cross-phase).
- **D-08-D5 verdict NON_TRIVIAL_IMPROVEMENT vs NEGATIVE_RESULT_DOCUMENTED**: deferred ML-on-baseline delta clustering condizionato a verdict (D-09-A1 deferred).

### Project-level (PROJECT.md / CLAUDE.md / Memory)
- **`project_training_data_integrity_priority.md`** (memory hard rule): qualunque trade-off Phase 7+ va risolto a favore di "training non invalidabile" anche a costo di UX peggiore. Phase 9 applicazioni concrete:
  - D-09-C1: riuso Phase 8 (no new path) — minimo blast radius
  - D-09-C2: auto-validation gate — protezione silently-worse-model
  - D-09-C3: dedup idempotent (no cancel) — aderente Phase 8 D-08-A3
  - D-09-C4: alarm-only escalation — niente auto-action invisibile production-impacting
  - D-09-A1: baseline only — read-only, no concurrent write
- **EXECUTION_MODE=shadow default sempre** — MCP-18 suggest read-only; retrain auto-validation gate non commit broker.
- **risk_engine = unico gate approvazione trade** — MCP-18 NON è un gate, è suggestion. Skill/operator decide.
- **Italiano per log/comment/rationale**, English per nomi tecnici/code/file paths. D-09-D2 structured rationale include `summary_it` field.
- **Tutto da .env, zero magic numbers** — tutti i threshold Phase 9 in .env (drift thresholds, retrain cron schedule, profile-aware rule thresholds).

</prior_decisions>

<decisions>
## Implementation Decisions

### Area A: Failure clustering scope (4 decisioni)

- **D-09-A1 — Cluster input = baseline parquet only.** `data/training/baseline_decisions/part-0.parquet` (Phase 5, 1076 rows × 59 cols, certificato Plan 05-09 SCHEMA + commit `0410bf2`). ~778 losing trade attesi (y=0 = 73% baseline hit-rate 27.7%). **Why:** Phase 9 in parallelo Phase 8 execute (no critical-path serialization). Cluster output già actionable da solo (778 sample statisticamente densi per HDBSCAN). Phase 8 D-08-D4 degraded slices analysis copre delta-analysis a slice-granularity. Delta vs ml_on parquet = deferred condizionale a Phase 8 D-08-D5 verdict.

- **D-09-A2 — Losing trade definition = y=0 binary (Phase 7 D-01 align).** `exit_reason != 'TP_HIT'` include SL_HIT + TIMEOUT + BREAKEVEN. **Why:** stessa codifica classifier target = audit consistency cross-phase totale (training Phase 7 ↔ inference Phase 7 ↔ failure analysis Phase 9 ↔ drift monitor Phase 9 ↔ retrain Phase 9 ↔ paper deploy Phase 11). TIMEOUT-as-failure semanticamente corretto in trading (capitale bloccato 24h+ = opportunity cost reale). BREAKEVEN ~2% impact trascurabile. TIMEOUT-win edge case mitigato post-cluster verification (annotation se contamina cluster avg_pnl > 0).

- **D-09-A3 — Clustering algorithm = HDBSCAN.** Density-based, noise-aware (label `-1`). `min_cluster_size ∈ [15, 25]` da decidere in plan-phase via cluster-quality validation. Dep: `hdbscan` (~1MB cython package). **Why:** 4-properties match per dati forex correlati heavy-tailed mixed-type — (1) no k arbitrario, (2) densità variabile naturale (rare carry-trade USDJPY M15 vs common setup-A breakout compressed), (3) noise label esplicito per failure idiosincratici (CHF 2015, COVID 2020) — non inquinano cluster centroidi, (4) robusto non-sferico Euclidean fragile. Output exemplar-based (top-3 trade IDs con max condensed-tree weight + feature-distribution summary median+IQR) più informativo di centroidi astratti k-means.

- **D-09-A4 — Feature space = raw via `ml/feature_extraction.py:build_feature_vector` Phase 7.** ~50 numeric (StandardScaler) + 5 categorical (one-hot ~16 binary cols) post-preprocessing = ~66 dim totali su 778 sample. **Why:** consistency totale Phase 7 ↔ Phase 9 (stesso target encoding + stesso feature pipeline = audit invariato). Zero duplicazione code. HDBSCAN gestisce dimensionalità moderata bene. PCA fallback condizionale come Wave 2 add-on se cluster quality bassa (DB > 2.0 OR silhouette < 0.15).

### Area B: Drift monitor + CLI dashboard (4 decisioni)

- **D-09-B1 — 3-tier drift dimensions: prediction KS + calibration ECE + feature drift top-K.** Top-K = top 15 feature da `bundle.feature_importance_` Phase 7 metadata. Hit-rate/rejection-rate derivati da trades.db come CLI dashboard view-only (no endpoint separato, evita overlap con Phase 8 D-08-D4 backtest report). **Why:** REQ ML-08 MUST = prediction KS + ECE (literal spec). Feature drift top-K = early-warning standard MLOps (no label lag, cattura market regime shift PRIMA di calibration degradation che lag fino a 120 bar per H1 TF). ~600-800 LOC compute.

- **D-09-B2 — Reference baseline = static training set** da `models/classifier_v{N}.metadata.json` (`dataset_hash` + reload `baseline_decisions` parquet). **Why:** unica opzione che cattura slow drift creeping (failure mode più probabile forex — regime shifts graduali). Day-1 operable Phase 11 paper deploy (rolling è blind primi 30d). Audit anchored via sha256 (project memory data integrity priority). Closed-loop self-healing con retrain trigger D-09-C: drift breach → retrain → nuovo metadata.json → reference shifta automaticamente → drift resolved by construction. Numero invariante nel tempo per longitudinal interpretation. Rolling diagnostic detail deferred Phase 11+ ~100 LOC.

- **D-09-B3 — Alarm threshold model = single-threshold per-metric .env.**
  - `DRIFT_KS_PVALUE_THRESHOLD=0.01` (prediction + per-feature KS)
  - `DRIFT_ECE_DELTA_THRESHOLD=0.02` (2pp absolute)
  - `DRIFT_FEATURE_FRACTION_THRESHOLD=0.30` (alarm se ≥30% top-K feature breached)
  - Global alarm = ANY 1 di 3 breached.
  **Why:** ML-08 spec literal "alarm when threshold breached" = single-threshold scope-fit. CLAUDE.md "tutto da .env, zero magic numbers" compliant. Defaults industry-standard MLOps (α=0.01 KS, ECE delta 2pp, fraction 30%). ~30 LOC alarm logic. Multi-tier severity retroactive Phase 11+.

- **D-09-B4 — Persistence drift_log.db SQLite + INT-03 markdown report CLI.** Tabella append-only `logs/drift_log.db` WAL mode (codebase pattern trades.db convention). CLI `scripts/show_drift.py` → `.planning/research/drift-report-{date}.md` (analog Phase 5 baseline + Phase 8 ml-on report convention). **Why:** codebase pattern match. Historical trend queryable via SQL Phase 11+. Audit reproducibile (ogni record include `reference_hash` per project memory data integrity). Markdown render-anywhere, agent skill `forex-trader-pro` consume uniformemente. ~350 LOC totali (drift_log writer + report writer).

### Area C: Retrain trigger workflow (4 decisioni)

- **D-09-C1 — Execution model = riusa Phase 8 `_train_ml_filter_worker` via JobQueue cap=1.** Tutti i 3 trigger ML-09 mandated (drift breach + scheduled monthly cron + manual MCP tool) enqueue stesso worker. APScheduler in `scheduler.py` per cron monthly (~50 LOC). `trigger_retrain(reason, force=false)` = thin MCP wrapper su `train_ml_filter`. **Why:** semanticamente è la stessa operazione (training LightGBM su baseline parquet → bundle). Phase 8 D-08-A2 cap=1 protegge race parquet già costruita+testata+audited (Phase 6 Plan 06-03 JobQueue tests + Phase 8 D-08-B3 sha256 strict-fail). Cross-queue race coordination strettamente più difficile della in-queue serialization by construction. 1 audit path / 1 test surface / 1 MCP tool family. Project memory data integrity: minimo numero di percorsi nuovi = minimo blast radius + minimo divergence risk codice nel tempo.

- **D-09-C2 — Auto-validation gate prima di atomic promote.** Retrain produce `classifier_v{N+1}_{date}.pkl.candidate`. Validation suite automatic:
  1. **ECE held-out fold check**: candidate ECE vs reference ECE da metadata.json — reject se regression > `MAX_ECE_REGRESSION_PCT` (default 10%, .env).
  2. **Prediction distribution KS-divergence**: candidate vs precedente — reject se KS > `KS_CANDIDATE_DIVERGENCE_THRESHOLD` (modello troppo diverso, sospetto overfit).
  3. **Threshold sweep expectancy**: per profile, reject se expectancy peggiore di `EXPECTANCY_REGRESSION_PCT`.
  
  Pass tutti → atomic `rename .candidate → .pkl` → MLFilter singleton hot-reload (cache invalidation). Fail → keep `.candidate` come audit + alarm operator + old model resta attivo. Audit ogni run in `validation_log.db` (analog drift_log.db pattern). **Why:** project memory data integrity literale include "silently corrupt model" — silently-worse-model è stessa classe failure. Validation gate = protezione by construction. Atomic rename pattern già required da project memory. ECE comparison vs metadata.json reference deterministic (Phase 7 D-15 fold_metrics). No operator burden (gate auto). Failure rollback safe: bundle precedente intoccato, MLFilter continua con model precedente. Manual override (force/reject) deferred Phase 11+ ~50 LOC.

- **D-09-C3 — Dedup idempotent: retrain in-flight → subsequent triggers no-op.** Se retrain già `running` OR `pending` → trigger ritorna `{ok: true, status: "already_pending", job_id: <existing>}`. Tutti i 3 trigger condividono stesso dedup check. Job record include `triggered_by_sources: array` (es. `["drift_breach", "scheduled_cron", "manual_mcp"]`) per audit completeness. ~30 LOC dedup logic. **Why:** aderente Phase 8 D-08-A3 no-cancel rule + Phase 8 D-08-A2 cap=1. Idempotent semantic = MCP tool contract standard (multiple calls = stesso effetto, no side effect duplicato). Audit pulito: per ogni "wave of triggers" un solo job record con sources array. Project memory data integrity: zero new race scenario introduced.

- **D-09-C4 — Failure escalation = alarm-only, old model attivo.** Validation gate fail → log `validation_log.db` con `reject_reason` + alarm operator (logger.error + telemetry). Old model resta attivo (atomic guarantee). `.candidate` kept come audit per investigation. Operator decide manualmente (eventuale force-promote retroactive via Phase 11+ MCP tool, eventuale disable ENABLE_ML_FILTER manuale). ~20 LOC alarm formatting. **Why:** ML-09 spec silent su escalation policy = scope-fit minimo. Phase 9 ship complexity bounded — operational experience Phase 11 paper deploy informerà la giusta escalation policy. Auto-disable ENABLE_ML_FILTER o backoff = production behavior change implicit = rischioso senza operator awareness. Project memory data integrity preferisce alarm visibile vs auto-action invisibile production-impacting. Deferred Phase 11+: auto-fallback ENABLE_ML_FILTER=false dopo N fail / exponential backoff / halt-auto-triggers — capture informato da paper deploy ops data.

### Area D: suggest_position_action logic (4 decisioni)

- **D-09-D1 — Decision source = hybrid rule + ML re-evaluation.** Rule-based primary (R-multiple + Time stop) produce action; ML re-evaluation modula severity ("thesis still valid" check via `prob_now` vs `threshold_profile`). Rationale dichiara entrambi i signal. OOD caveat surface esplicitamente (`ml_check.ood_caveat: true`). ~300 LOC. **Why:** rule-based copre il caso comune (objective R-multiple management, time stop) deterministicamente audit-friendly. ML re-evaluation aggiunge "thesis check" — la domanda che classifier RISPONDE bene (`P(y=1 | features)` interpretata come "would I take this trade now?"). OOD caveat manageable: rationale documenta il problema semantico (classifier addestrato su `features_at_decision_time` Phase 7 D-17, NON mid-trade). No cluster dependency Phase 9 first-ship (funziona anche se Area A cluster artifact non ancora generato). Failure cluster match integration deferred Wave 2 (~50 LOC modulazione severity).

- **D-09-D2 — Output response shape = structured rationale.**
  ```json
  {
    "action": "move_sl" | "partial_close" | "full_close" | "hold",
    "params": {"new_sl_price": float, "method": "to_breakeven|atr_trail", "close_fraction": float},
    "confidence": float,
    "rationale": {
      "rules_triggered": [{"name": str, "condition": str, "value": float}],
      "ml_check": {
        "calibrated_prob_at_entry": float | null,
        "calibrated_prob_now": float | null,
        "threshold_profile": float | null,
        "signal": "above_threshold|below_threshold|above_but_decreasing|n/a",
        "ood_caveat": bool,
        "ml_filter_disabled": bool
      },
      "summary_it": "string italiano operator-readable"
    }
  }
  ```
  **Why:** API contract pattern Phase 6/8 (handler ritorna dict structured). Skill `forex-trader-pro` parsa `action` + `params` mechanical + mostra `summary_it` human-readable. Audit completo per investigation 6 mesi dopo. OOD caveat surfaced in-band. CLAUDE.md italiano-rationale compliant. Backward-extensible: add fields retroactive (es. Wave 2 `cluster_match` opzionale) senza breaking change consumer.

- **D-09-D3 — Rule library scope = Standard 4-rule + profile-aware .env.**
  - **R-multiple BE move**: `r_multiple ≥ T_be_profile` (default CONSERVATIVE=1.0, MODERATE=1.5, AGGRESSIVE=2.0) → `move_sl` to entry price.
  - **R-multiple partial close**: `r_multiple ≥ T_partial_profile` (default 1.5/2.0/2.5) → `partial_close` 50% (configurable `PARTIAL_CLOSE_FRACTION` .env).
  - **R-multiple full close**: `r_multiple ≥ T_full_profile` (default 2.5/3.0/3.5) → `full_close` lock profits.
  - **Time stop**: `bars_in_trade > MAX_HOLD_BARS_profile` (default 72/96/120 per CONSERVATIVE/MODERATE/AGGRESSIVE) AND `r_multiple ≤ 0.5` → `full_close` (opportunity cost protection).
  
  Tutti threshold via .env pattern `BE_R_THRESHOLD_{PROFILE}=...`. ~280 LOC rule logic + ~120 LOC test. **Why:** 80% professional management forex (forex-trader-pro skill playbook + Probo/Defendi). Time stop previene capital lockup pre-Phase-5-TIMEOUT (M15=96 bar = 24h) → earlier exit su flat trade libera capital. Profile-aware standard CLAUDE.md compliance. Volatility shrink + MTF reversal + Spread expansion deferred Phase 9 v2 (cross-phase coupling: MTF latency, Phase 10 news dep).

- **D-09-D4 — ML feature snapshot timing = hybrid: prefer cached + fallback recompute.** Schema extension idempotent: ALTER TABLE trades_log ADD COLUMN IF NOT EXISTS `ml_calibrated_prob REAL`. A `log_trade_decision` (Phase 7 Plan 07-06 hook): scrivi `proposal.ml_calibrated_prob` (già attached da Phase 7 D-13 ProposalDraft). MCP-18 lookup: `SELECT ml_calibrated_prob FROM trades_log WHERE position_id=?`. Se NULL (legacy trades pre-Phase-9) → fallback recompute via parse `decision_context_json` → `build_feature_vector` → `MLFilter.predict` deterministico. ~40 LOC totali (10 schema + 20 lookup + 10 fallback). **Why:** schema addition forward-compatible (Phase 9+ trades hanno il dato persistito → audit trail completo + zero recompute cost ongoing). Backward-compat con legacy trades via recompute (Phase 11 paper deploy mix old+new se schema migration parziale). Deterministic by construction (stesso modello + stesso input = stesso output). Project memory data integrity: `ml_calibrated_prob` persistito = riproducibilità 6 mesi dopo senza riprocessare JSON.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before research / planning / implementation.**

### Phase 7 ML pipeline (mandatory — target encoding + feature pipeline + bundle convention)
- `.planning/phases/07-ml-classifier/07-CONTEXT.md` — D-01..D-20 LOCKED (target, embargo, categorical, threshold, bundle schema, latency)
- `.planning/phases/07-ml-classifier/07-RESEARCH.md` — patterns + pitfalls (especially Pitfall 6 latent bug post-Phase-9 retraining)
- `.planning/phases/07-ml-classifier/07-PATTERNS.md` — 20 file mapped (especially `ml/inference.py` MLFilter singleton)
- `.planning/phases/07-ml-classifier/07-01-PLAN.md` — `ml/feature_extraction.py:build_feature_vector` + D-09-G derivation 8 fields (riusato da D-09-A4 + D-09-D4)
- `.planning/phases/07-ml-classifier/07-05-PLAN.md` — MLFilter.predict API + joblib bundle + metadata.json sidecar schema (riusato da D-09-B2 reference + D-09-C2 validation gate)
- `.planning/phases/07-ml-classifier/07-06-PLAN.md` — evaluate_proposal_for_bar + risk_engine ML gate + ENABLE_ML_FILTER (carry-forward D-09-D4 prob_at_entry persistence hook)

### Phase 8 MCP ML tools + retrain coordination (mandatory)
- `.planning/phases/08-mcp-tools-part-2/08-CONTEXT.md` — D-08-A1..D5 (train_ml_filter async via JobQueue, cap=1 condiviso, no cancel, sha256 strict-fail, audit-first calibration, degraded slices analysis, verdict assertion)
- `.planning/phases/08-mcp-tools-part-2/08-DISCUSSION-LOG.md` — discussion record per rationale chain trace
- Phase 8 PLAN.md files (post `/gsd-plan-phase 8`) — train_ml_filter worker + dedup pattern + validation hook precedent

### Phase 6 MCP package conventions (mandatory)
- `.planning/phases/06-mcp-tools-part-1/06-CONTEXT.md` — D-A/B/C/D/E/F decisions (JobQueue, BarSource, mcp_tools/ package split, handler pattern)
- `.planning/phases/06-mcp-tools-part-1/06-03-PLAN.md` — JobQueue ProcessPoolExecutor cap=1 + worker top-level picklable (analog per Phase 9 retrain trigger via D-09-C1)
- `.planning/phases/06-mcp-tools-part-1/06-04-PLAN.md` — handle_modify_position + handle_get_position_state + position_trails table (Phase 9 MCP-18 consume tramite handle_get_position_state)
- `.planning/phases/06-mcp-tools-part-1/06-PATTERNS.md` — handler shape analogs (handlers/backtest.py per drift handler structure)

### Phase 5 baseline dataset (mandatory for D-09-A1 cluster input + D-09-C1 retrain input)
- `.planning/phases/05-baseline-backtest/05-09-PLAN.md` — schema-v2 specifica + `_SCHEMA_V2_REQUIRED_KEYS` programmatic
- `.planning/phases/05-baseline-backtest/05-09-SUMMARY.md` — execution results PC secondario 2026-05-12 (parquet 1076 × 59 cert.)
- `.planning/research/baseline-2026-05-12.md` — baseline metrics 27 slice (Phase 9 drift reference indirect via metadata.json)
- `backtest/baseline/dataset_writer.py` + `backtest/baseline/slice_worker.py` — D-09-B no-leakage anchor

### Project-level
- `.planning/PROJECT.md` — milestone goals (Phase 9 drift monitor consume ml_inference.log L106, Phase 9 retrain trigger ML-08/09 L598-614)
- `.planning/REQUIREMENTS.md` — ML-07/08/09, MCP-07/08/18, INT-03 definitions
- `.planning/ROADMAP.md` Phase 9 section — Goal + 4 SC + Hint UI no
- `CLAUDE.md` — EXECUTION_MODE=shadow, risk_engine unico gate, italiano log, zero magic numbers
- `COMMIT_CONVENTIONS.md` — feat/fix/test/docs scope per commit Phase 9
- **User memory `project_training_data_integrity_priority.md`** (project memory hard rule) — informa D-09-A1, D-09-C1, D-09-C2, D-09-C3, D-09-C4 — MUST honor in plan-phase

### Code analogs (codebase scout)
- `mcp_tools/handlers/backtest.py:309-465` — `handle_run_backtest` async pattern (closest analog per D-09-C1 retrain trigger handler)
- `mcp_tools/handlers/position.py` (Phase 6 Plan 06-04) — handle_get_position_state + handle_modify_position (D-09-D output channel consumer)
- `mcp_tools/job_queue.py` (Phase 6 Plan 06-03) — JobQueue ProcessPoolExecutor cap=1 (Phase 9 retrain riusa)
- `mcp_tools/server.py` — Tool registration + dispatch bucket (Phase 9 aggiunge bucket cluster/drift/position_action)
- `mcp_tools/errors.py` — ErrorCodes envelope
- `mcp_tools/trail_daemon.py` (Phase 6 Plan 06-04) — analog scheduler hook pattern (Phase 9 drift hook + scheduled cron)
- `logger.py:_TRADES_LOG_SCHEMA` — pattern per drift_log.db + validation_log.db schema definition (WAL + idempotent CREATE)
- `scheduler.py` — APScheduler integration point per D-09-C1 monthly cron
- `scripts/run_baseline_05_09.py` (Plan 05-09) — closest analog per `scripts/show_drift.py` standalone CLI
- `backtest/baseline/report_writer.py` — Markdown report generation (analog per `drift_report_writer.py` D-09-B4)
- `tests/test_mcp_handlers_backtest.py` (Phase 6 Plan 06-03) — handler test pattern (analog Phase 9 handlers tests)

</canonical_refs>

<code_context>
## Reusable assets identified

### Already produced (Phase 5/6/7/8 dependencies)
- `data/training/baseline_decisions/part-0.parquet` (Phase 5 Plan 05-09): 1076 × 59 schema-v2 certified — input failure cluster + retrain
- `models/classifier_v{N}_{date}.pkl` + `.metadata.json` (Phase 7 Plan 07-05): bundle convention + fold_metrics + feature_importance_ + threshold_by_profile + dataset_hash — riusato drift reference + auto-validation gate
- `ml/inference.py:MLFilter + get_ml_filter` (Phase 7 Plan 07-05): singleton + predict API <10ms — riusato MCP-18 ML re-eval
- `ml/feature_extraction.py:build_feature_vector` (Phase 7 Plan 07-01): D-09-G derivation 8 fields — riusato cluster preprocessing (D-09-A4) + MCP-18 mid-trade ML re-eval (D-09-D1)
- `ml/train.py:train_classifier` (Phase 7 Plan 07-03): FoldArtifacts NamedTuple + walk_forward — invocato da Phase 9 retrain trigger
- `mcp_tools/job_queue.py` (Phase 6 Plan 06-03): JobQueue ProcessPoolExecutor cap=1 — riusato D-09-C1
- `mcp_tools/handlers/backtest.py` (Phase 6 Plan 06-03): 4 async handler + dispatch pattern — analog cluster/drift/retrain handler
- `mcp_tools/handlers/position.py` (Phase 6 Plan 06-04): handle_get_position_state + handle_modify_position — MCP-18 consume position state
- `mcp_tools/handlers/ml.py` (Phase 8 D-08-A1, post execute): `_train_ml_filter_worker` top-level picklable — Phase 9 retrain trigger ENQUEUE stesso worker
- `mcp_tools/errors.py`: ErrorCodes envelope — riusato cluster/drift/retrain handler
- `mcp_tools/server.py`: list_tools + dispatch bucket — extension Phase 9 (3 nuovi tool surface)
- `logger.py`: trades.db WAL mode + RotatingFileHandler + `ml_inference.log` (Phase 7 Claude discretion) — Phase 9 drift monitor consume
- `scheduler.py`: APScheduler IntradayLoopScheduler — extension point per RetrainScheduler cron monthly (D-09-C1)
- `risk_engine.py:evaluate_trade` (Phase 7 Plan 07-06): ML gate already wired ENABLE_ML_FILTER respect — invariato Phase 9
- `backtest/baseline/report_writer.py` (Phase 5): Markdown report generation pattern — analog drift_report_writer

### To produce in Phase 9
- `cluster/` package (~600-800 LOC):
  - `cluster/__init__.py`
  - `cluster/preprocessing.py` (~150 LOC): build_feature_matrix from baseline_decisions + StandardScaler + one-hot
  - `cluster/hdbscan_runner.py` (~200 LOC): fit_predict + exemplar selection + feature_distribution_summary + cluster_quality validation (DB index + silhouette)
  - `cluster/artifact.py` (~100 LOC): joblib persist + load pattern (analog Phase 7 `ml/artifact.py`)
  - `cluster/match.py` (~50 LOC): approximate_predict for new sample cluster membership (deferred Wave 2)
- `drift/` package (~600-800 LOC):
  - `drift/__init__.py`
  - `drift/reference.py` (~100 LOC): load training distribution from metadata.json + parquet hash check
  - `drift/compute.py` (~250 LOC): prediction KS + ECE rolling + feature drift top-K per LightGBM importance
  - `drift/log_db.py` (~150 LOC): drift_log.db schema + append-only writer
  - `drift/alarm.py` (~80 LOC): threshold breach check + sources aggregation
- `retrain/` package (~300-400 LOC):
  - `retrain/scheduler.py` (~80 LOC): APScheduler cron month trigger
  - `retrain/dedup.py` (~50 LOC): in-flight check vs JobQueue state
  - `retrain/validation_gate.py` (~200 LOC): ECE + KS + threshold sweep checks + validation_log.db writer
  - `retrain/promotion.py` (~80 LOC): atomic rename + MLFilter cache invalidation
- `position_action/` package (~300-400 LOC):
  - `position_action/rules.py` (~280 LOC): 4 rule families (BE/partial/full/time) + profile-aware threshold lookup .env
  - `position_action/ml_recheck.py` (~80 LOC): mid-trade feature vector build + MLFilter.predict + OOD signal classification
  - `position_action/orchestrator.py` (~120 LOC): hybrid combine rule + ML + structured rationale assembly
- `mcp_tools/handlers/`:
  - `cluster.py` (~150 LOC): handle_get_failure_clusters
  - `drift.py` (~150 LOC): handle_get_drift_metrics
  - `retrain.py` (~120 LOC): handle_trigger_retrain (thin wrapper su train_ml_filter)
  - `position_action.py` (~150 LOC): handle_suggest_position_action
- `mcp_tools/server.py` (extension): 4 nuovi Tool registration + dispatch bucket
- `mcp_tools/schemas.py` (extension): 4 nuovi JSON-Schema
- `scripts/show_drift.py` (~200 LOC): CLI INT-03 dashboard markdown report writer
- `logger.py` extension (~30 LOC): ALTER TABLE trades_log ADD COLUMN ml_calibrated_prob + log_trade_decision wire to write field
- `config.py` extension (~30 LOC): nuove env vars (DRIFT_*, RETRAIN_*, BE_R_THRESHOLD_*, MAX_HOLD_BARS_*, PARTIAL_CLOSE_FRACTION)
- `.env.example` (mirror env vars)
- Test suite (~1200 LOC):
  - `tests/test_cluster_hdbscan.py` (~250 LOC)
  - `tests/test_drift_compute.py` (~250 LOC)
  - `tests/test_drift_log_db.py` (~100 LOC)
  - `tests/test_retrain_dedup.py` (~80 LOC)
  - `tests/test_retrain_validation_gate.py` (~200 LOC)
  - `tests/test_position_action_rules.py` (~120 LOC)
  - `tests/test_position_action_ml_recheck.py` (~80 LOC)
  - `tests/test_mcp_handlers_cluster_drift_retrain_position.py` (~200 LOC)
  - `tests/test_show_drift_cli.py` (~100 LOC)

### Test fixture reuse
- `tests/fixtures/baseline_decisions_smoke.parquet` (Phase 7 Plan 07-01 200-row deterministic): riusato per smoke test cluster + drift compute
- `tests/conftest.py` Mt5Client stub: MCP-18 NON dipende da MT5 (chiama handle_get_position_state mocked); conftest unchanged

### What NOT to reproduce
- NO new MLFilter implementation — riusa Phase 7 `ml/inference.py`
- NO new feature extraction — riusa Phase 7 `ml/feature_extraction.py:build_feature_vector`
- NO new training logic — Phase 9 retrain riusa Phase 8 `_train_ml_filter_worker`
- NO new JobQueue — riusa Phase 6/8 JobQueue cap=1
- NO new BarSource — riusa Phase 6 D-D1
- NO new position state fetch — riusa Phase 6 Plan 06-04 handle_get_position_state
- NO new MCP package conventions — riusa Phase 6 handlers/ pattern + ErrorCodes envelope
- NO new bundle schema — riusa Phase 7 D-15 (estende solo metadata reference field per drift)

</code_context>

<spec_lock>
## Locked Requirements (from REQUIREMENTS.md)

Phase 9 chiude 7 requirement:
- **ML-07**: Failure analysis cluster losing trades (k-means or HDBSCAN), surface top failure modes → D-09-A1..A4
- **ML-08**: Drift monitor (KS-test prediction + calibration ECE) rolling window + alarm trigger → D-09-B1..B4
- **ML-09**: Retrain trigger (drift breach OR scheduled monthly OR manual via tool) → D-09-C1..C4
- **MCP-07**: `get_failure_clusters(top_n)` → handler consumes D-09-A artifact
- **MCP-08**: `get_drift_metrics(window_days)` → handler consumes D-09-B drift_log.db
- **MCP-18**: `suggest_position_action(position_id)` ML/rule-based hold/move-SL/partial/full-close → D-09-D1..D4
- **INT-03**: Drift dashboard CLI → D-09-B4 + `scripts/show_drift.py`

</spec_lock>

<specifics>
## Specific Ideas

### MCP-08 response shape (D-09-B1 implication)
```json
{
  "window_days": 30,
  "reference_period": "training set 2026-01-15 to 2026-05-12",
  "current_period": "2026-09-12 to 2026-10-12",
  "reference_hash": "sha256:abc...",
  "model_version": "v3",
  "n_predictions_current": 1450,
  "n_predictions_reference": 1076,
  "prediction_drift": {
    "ks_stat": 0.087,
    "ks_pvalue": 0.012,
    "threshold": 0.01,
    "breached": false
  },
  "calibration_drift": {
    "current_ece": 0.063,
    "reference_ece": 0.041,
    "delta_ece": 0.022,
    "threshold": 0.02,
    "breached": true,
    "n_with_outcome": 980,
    "n_pending_outcome": 470
  },
  "feature_drift": [
    {"feature": "atr", "ks_stat": 0.12, "ks_pvalue": 0.001, "breached": true},
    {"feature": "adx", "ks_stat": 0.05, "ks_pvalue": 0.34, "breached": false}
  ],
  "alarm_status": "breach"
}
```

### MCP-07 response shape (D-09-A3 exemplar-based)
```json
{
  "model_version": "v3",
  "computed_at": "2026-09-15T02:00:00Z",
  "n_losing_trades_total": 778,
  "n_noise_points": 47,
  "clusters": [
    {
      "cluster_id": 0,
      "n_trades": 180,
      "exemplar_trade_ids": [123, 456, 789],
      "feature_distribution_summary": {
        "atr": {"median": 0.0234, "iqr": [0.0198, 0.0276]},
        "adx": {"median": 18.4, "iqr": [16.2, 20.8]},
        "regime": {"mode": "compressed", "freq": 0.78},
        "setup_name": {"mode": "A", "freq": 0.88},
        "symbol": {"mode": "USDJPY", "freq": 0.71}
      },
      "avg_pnl_pips": -18.5,
      "hit_rate_within_cluster": 0.08,
      "summary_it": "Cluster A breakout regime compresso ADX basso, hit rate 8%"
    }
  ],
  "noise_trade_ids": [...],
  "quality_metrics": {
    "davies_bouldin": 1.42,
    "silhouette": 0.31,
    "quality": "good"
  }
}
```

### MCP-18 response shape (D-09-D2 structured rationale)
```json
{
  "position_id": "pos_12345",
  "action": "move_sl",
  "params": {"new_sl_price": 1.2345, "method": "to_breakeven"},
  "confidence": 0.78,
  "rationale": {
    "rules_triggered": [
      {"name": "r_multiple_to_be", "condition": "r_multiple >= 1.5 (profile=MODERATE)", "value": 1.62}
    ],
    "ml_check": {
      "calibrated_prob_at_entry": 0.71,
      "calibrated_prob_now": 0.58,
      "threshold_profile": 0.55,
      "signal": "above_but_decreasing",
      "ood_caveat": true,
      "ml_filter_disabled": false
    },
    "summary_it": "R 1.62 raggiunto, suggerisco BE move. ML thesis ancora valida (prob 0.58 > soglia 0.55) ma in calo da 0.71 a entry — caveat OOD inference mid-trade."
  }
}
```

### Drift_log.db schema (D-09-B4)
```sql
CREATE TABLE IF NOT EXISTS drift_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  model_version TEXT NOT NULL,
  reference_hash TEXT NOT NULL,
  metric_name TEXT NOT NULL,     -- 'prediction_ks' | 'calibration_ece' | 'feature_drift_atr' | ...
  metric_value REAL NOT NULL,
  threshold REAL NOT NULL,
  breached INTEGER NOT NULL,     -- 0 | 1
  n_samples_current INTEGER,
  n_samples_reference INTEGER,
  window_days INTEGER,
  computed_by TEXT               -- 'mcp_get_drift_metrics' | 'scheduled_check' | 'cli_show_drift'
);
CREATE INDEX IF NOT EXISTS idx_drift_log_ts ON drift_log(ts_utc, model_version, breached);
```

### Validation_log.db schema (D-09-C2)
```sql
CREATE TABLE IF NOT EXISTS validation_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  candidate_path TEXT NOT NULL,
  previous_version TEXT,
  check_name TEXT NOT NULL,      -- 'ece_regression' | 'ks_divergence' | 'expectancy_regression'
  metric_value REAL NOT NULL,
  threshold REAL NOT NULL,
  passed INTEGER NOT NULL,        -- 0 | 1
  reject_reason TEXT,
  triggered_by_sources_json TEXT  -- '["drift_breach","scheduled_cron"]'
);
CREATE INDEX IF NOT EXISTS idx_validation_log_ts ON validation_log(ts_utc, candidate_path, passed);
```

### trades_log schema extension (D-09-D4)
```sql
ALTER TABLE trades_log ADD COLUMN IF NOT EXISTS ml_calibrated_prob REAL;
-- Backfill NULL for legacy trades pre-Phase-9
-- D-09-D4 fallback recompute via decision_context_json + MLFilter.predict
```

### .env additions (Phase 9 scope)
```bash
# Drift monitor (Area B)
DRIFT_KS_PVALUE_THRESHOLD=0.01
DRIFT_ECE_DELTA_THRESHOLD=0.02
DRIFT_FEATURE_FRACTION_THRESHOLD=0.30
DRIFT_TOP_K_FEATURES=15
DRIFT_MIN_SAMPLES_CURRENT=30
DRIFT_DEFAULT_WINDOW_DAYS=30

# Retrain trigger (Area C)
RETRAIN_CRON_SCHEDULE="0 2 1 * *"  # cron-style: 1st of month 02:00 UTC
MAX_ECE_REGRESSION_PCT=10.0
KS_CANDIDATE_DIVERGENCE_THRESHOLD=0.15
EXPECTANCY_REGRESSION_PCT=5.0

# Position action rules (Area D)
BE_R_THRESHOLD_CONSERVATIVE=1.0
BE_R_THRESHOLD_MODERATE=1.5
BE_R_THRESHOLD_AGGRESSIVE=2.0
PARTIAL_R_THRESHOLD_CONSERVATIVE=1.5
PARTIAL_R_THRESHOLD_MODERATE=2.0
PARTIAL_R_THRESHOLD_AGGRESSIVE=2.5
FULL_R_THRESHOLD_CONSERVATIVE=2.5
FULL_R_THRESHOLD_MODERATE=3.0
FULL_R_THRESHOLD_AGGRESSIVE=3.5
MAX_HOLD_BARS_CONSERVATIVE=72
MAX_HOLD_BARS_MODERATE=96
MAX_HOLD_BARS_AGGRESSIVE=120
PARTIAL_CLOSE_FRACTION=0.5
TIME_STOP_R_THRESHOLD=0.5
```

### APScheduler integration (D-09-C1 cron)
Estendere `scheduler.py` con:
```python
class RetrainScheduler:
    def __init__(self, job_queue: JobQueue, cfg: Config):
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._job_queue = job_queue
        self._cfg = cfg

    def start(self):
        trigger = CronTrigger.from_crontab(self._cfg.RETRAIN_CRON_SCHEDULE)
        self._scheduler.add_job(
            self._fire_scheduled_retrain,
            trigger=trigger,
            id="retrain_monthly",
            replace_existing=True
        )
        self._scheduler.start()

    def _fire_scheduled_retrain(self):
        # Dedup idempotent D-09-C3
        if _retrain_in_flight(self._job_queue):
            logger.info("Scheduled retrain skipped: already in-flight")
            return
        _enqueue_retrain(self._job_queue, source="scheduled_cron")
```

### MCP-18 OOD caveat boilerplate (D-09-D1)
Quando `ENABLE_ML_FILTER=true` E `MLFilter` loaded:
1. Build feature vector NOW da current bar + position state via `build_feature_vector(ctx_now)` (Phase 7 reuse)
2. Call `MLFilter.predict(feature_vec)` → `(raw_score, calibrated_prob_now)`
3. Lookup `calibrated_prob_at_entry` da trades_log (D-09-D4) o fallback recompute
4. Confronto vs `threshold_profile` da bundle metadata.json
5. Classify signal:
   - `above_threshold` (prob_now > threshold AND prob_now >= prob_at_entry * 0.9): thesis valida
   - `above_but_decreasing` (prob_now > threshold AND prob_now < prob_at_entry * 0.9): thesis crollando
   - `below_threshold` (prob_now <= threshold): thesis invalidata
6. Modula rule action: se `below_threshold` AND rule action == `hold` → upgrade a `full_close`; se `below_threshold` AND rule action == `move_sl` → upgrade a `full_close`; etc.
7. Surface `ood_caveat: true` in rationale ml_check field.

</specifics>

<deferred>
## Deferred Ideas

Capture per evitare scope creep — NON in scope Phase 9.

- **Delta clustering baseline vs ml_on parquet** (Phase 9 v2 / Phase 11): condizionale a Phase 8 D-08-D5 verdict NON_TRIVIAL_IMPROVEMENT. ~50-100 LOC retrofit riusando stesso HDBSCAN engine.
- **Rolling reference window drift comparison** (Phase 11+ diagnostic): ~100 LOC retroactive. Aggiunge rolling delta a MCP-08 response come `rolling_drift` field aggiuntivo.
- **Multi-tier severity alarm** (Phase 11+): warning/critical/breach con routing differenziato (warning=log, critical=scheduled retrain, breach=immediate retrain). ~50 LOC.
- **Auto-disable ENABLE_ML_FILTER dopo N validation fail consecutive** (Phase 11+): failsafe automatico, ~80 LOC + state persistence. Capture informato da paper deploy ops data.
- **Exponential backoff su retrain storm** (Phase 11+): ~80 LOC. Reduce retrain attempt frequency dopo fail patologico.
- **Halt automatic triggers dopo N fail** (Phase 11+): force manual investigation, ~100 LOC.
- **Manual override force/reject MCP tools per validation gate** (Phase 11+): `promote_model_candidate(version_id, force=true)` + `reject_model_candidate(version_id, reason)`. ~50 LOC.
- **Volatility shrink rule per suggest_position_action** (Phase 9 v2): `ATR_now < 0.5 × ATR_entry AND r_multiple ≤ 0` → `full_close`. ~50 LOC.
- **MTF reversal rule per suggest_position_action** (Phase 9 v2): H1 trend flips against position → `full_close`. Richiede mid-trade multi-TF bar fetch via BarSource Phase 6 D-D1, latency added.
- **Spread expansion rule per suggest_position_action** (cross-phase Phase 10): spread_now > N × spread_entry → `full_close` (news event protection). Dipende news_aggregator integration Phase 10.
- **Failure cluster match integration in suggest_position_action** (Wave 2): build feature vector NOW → `approximate_predict` via HDBSCAN cluster artifact → se matcha cluster basso hit-rate (<15%) modula severity. ~50 LOC.
- **OS cron + script standalone (out-of-MCP retrain)** (Phase 11+): se DEPLOY-02 emerge uptime-independence requirement. Introduce cron daemon dep + cross-process lock + perde `trigger_retrain` MCP tool surface.
- **Categorical feature drift via chi-square test** (Phase 11+): KS valido solo per numeric; categorical (symbol/tf/profile/setup_name/regime) richiede chi-square. ~80 LOC add-on a feature_drift compute.
- **Decision tree explainer per MCP-18 response** (Phase 9 v3): explicit decision path showing why action X vs alternatives. ~150 LOC.
- **Multi-action ranked top-K alternative per MCP-18** (Phase 9 v3): operator vede alternative oltre raccomandata. Over-engineering vs current spec.
- **PCA pre-cluster fallback** (Wave 2 conditional): se HDBSCAN cluster quality bassa (DB > 2.0 OR silhouette < 0.15) → add PCA pre-process. ~80 LOC.

</deferred>

<test_hooks>
## Test Strategy Anchors

- **HDBSCAN smoke test** (`tests/test_cluster_hdbscan.py`): fit_predict su 200-row fixture parquet, asserta n_cluster ≥ 3 + cluster_quality DB < 2.0.
- **Drift compute determinism** (`tests/test_drift_compute.py`): fixed reference + fixed current → fixed KS-stat (1e-6 tolerance).
- **Drift alarm threshold test**: synthetic distribution shift forced breach → assert `breached=true`.
- **Retrain dedup idempotency**: 3 concurrent trigger → 1 job submitted, 2 ritornano `already_pending`.
- **Validation gate ECE-regression**: stage candidate con ECE 0.063 vs ref 0.041 → reject + validation_log entry.
- **Validation gate atomic rename**: candidate pass → file system check `.pkl` exists AND `.candidate` removed.
- **Position action rule isolation**: 4 rule families testate one-by-one con synthetic position state.
- **Position action hybrid orchestration**: rule + ML signal combinati → assert action upgrade severity quando `below_threshold`.
- **MCP-18 OOD caveat**: response ml_check.ood_caveat === true sempre quando ml_check.signal != n/a.
- **MCP-18 ENABLE_ML_FILTER=false fallback**: assert ml_check.ml_filter_disabled === true + ml_check.signal === "n/a" + action derivata solo da rules.
- **trades_log schema migration idempotent**: ALTER multiple times safe.
- **MLFilter singleton cache invalidation**: post atomic rename → next predict ricarica from disk.
- **CLI show_drift smoke**: SC#3 markdown report generation, parse round-trip.

</test_hooks>

---

## Next Steps

1. **`/clear`** per resettare context window
2. **`/gsd-plan-phase 9`** per generare PLAN.md (multi-wave breakdown)
3. Plan-phase researcher consumerà questo CONTEXT.md + canonical_refs per RESEARCH.md
4. Plan-phase pattern-mapper userà code_context per PATTERNS.md mapping nuovi file su analoghi esistenti
5. Plan-phase produrrà ~6-8 PLAN.md (suggested wave structure):
   - **09-01 Wave 0**: scaffolding (cluster/ + drift/ + retrain/ + position_action/ packages + .env vars + config.py extension)
   - **09-02 Wave 1**: failure clustering (ML-07 + MCP-07) — D-09-A1..A4 implementation
   - **09-03 Wave 2**: drift monitor + drift_log.db (ML-08 + MCP-08) — D-09-B1..B4 implementation
   - **09-04 Wave 3**: retrain trigger workflow (ML-09) — D-09-C1..C4 implementation (riusa Phase 8 worker)
   - **09-05 Wave 4**: suggest_position_action (MCP-18) — D-09-D1..D4 implementation
   - **09-06 Wave 5**: INT-03 CLI dashboard `scripts/show_drift.py` + markdown report writer
   - **09-07 Wave 6**: integration + E2E smoke test + phase gate verification (SC#1..4)
   - **09-08 Wave 7 optional**: validation_log.db schema + trades_log ml_calibrated_prob migration (può essere folded in Wave 0)

**Estimated execute total:** ~15-20h wall-clock (HDBSCAN compute ~secondi, drift compute ~secondi, retrain riusa Phase 8 ~30-60s, suggest synchronous ~ms — la maggior parte è plan + test).
