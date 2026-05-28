# Phase 9: Failure Analysis + Drift — Discussion Log

**Session date:** 2026-05-12
**Mode:** `/gsd-discuss-phase 9` default mode (4 aree single-question turns)
**Areas discussed:** 4/4 (A failure clustering, B drift monitor + dashboard, C retrain trigger, D suggest_position_action)
**Decisions captured:** 16 (D-09-A1..A4, D-09-B1..B4, D-09-C1..C4, D-09-D1..D4)
**Deferred ideas:** 16 (vedi `09-CONTEXT.md` § deferred)

## Discussion Trace

### Pre-discuss area selection
**Q:** Quali aree di Phase 9 vuoi discutere?
**A:** Tutte e 4 selezionate (multiSelect): Failure clustering scope, Drift monitor + CLI dashboard (folded INT-03), Retrain trigger workflow, suggest_position_action logic

---

### Area A — Failure clustering scope (ML-07 + MCP-07)

**Q A-1:** Su quale dataset esegue il failure clustering Phase 9?
Options presentate: baseline only / baseline + ml_on Phase 8 / multi-source dinamico / ML feature vector only
**Clarification:** User chiese "il vantaggio di usare baseline e i test di phase 8 e' reale?" — Claude rispose con analisi onesta:
- Baseline + ml_on darebbe segnale "ML blind spot delta" ma è marginale perché (1) Phase 8 D-08-D4 già copre delta a slice granularity, (2) se Phase 8 D-08-D5 = NEGATIVE_RESULT, delta cluster è output vuoto, (3) critical path serialization Phase 9 dietro Phase 8 execute
**Riformulato:** baseline only (Recommended) / baseline + ml_on (serializza) / decido dopo verdict Phase 8
**A:** Baseline only (Recommended) — `data/training/baseline_decisions/part-0.parquet` (Phase 5, 1076 × 59). Delta vs ml_on deferred condizionale a Phase 8 D-08-D5 verdict.

**Q A-2:** Definizione 'losing trade' per cluster universe.
Options presentate: y=0 binary / pnl_pips<0 stretto / pnl_pips<-threshold / union dual
**Clarification:** User chiese "spiegami dettagliato tutto" — Claude fornì spiegazione esaustiva su:
- Cosa fa failure clustering (ML-07 + MCP-07 scope)
- Schema baseline parquet con breakdown exit_reason × pnl_pips
- 4 opzioni in profondità con pros/cons
- Collegamenti Phase 7 D-01 + Phase 11 USER_CLOSE label policy
- Disponibilità verifica empirica del breakdown reale parquet
- Raccomandazione Opzione 1 (y=0 binary) con 3 ragioni: audit consistency cross-phase, stability statistica ~778 trade, TIMEOUT-as-failure semanticamente corretto
**Riformulato:** y=0 Phase 7 align (Recommended) / pnl<0 / pnl<-threshold / verifica prima breakdown
**A:** y=0 binary, Phase 7 D-01 align (Recommended) — `exit_reason != TP_HIT`, ~778 trade universe.

**Q A-3:** Algoritmo clustering Phase 9.
Options presentate: k-means / HDBSCAN / both paralleli / k-means primary + HDBSCAN secondary outlier
**Clarification:** User chiese "dimmi perche mi raccomandi HDBSCAN e non le altre" — Claude rispose con analisi comparativa centrata sulle 4 proprietà che servono al nostro dataset:
1. No k arbitrario da decidere (problema metric divergence silhouette vs Calinski-Harabasz)
2. Cluster a densità variabile (rare carry-trade USDJPY M15 vs common setup-A breakout — k-means forza sferico)
3. Noise labeling (label -1 per failure idiosincratici CHF 2015, COVID 2020)
4. Robusto a feature non-sferica/non-Euclidean (forex feature heavy-tailed correlated)
Spiegato anche perché NON k-means alone, both paralleli, k-means+HDBSCAN secondary, DBSCAN, OPTICS, GMM, Ward, Spectral, SOM.
**Riformulato:** HDBSCAN (Recommended) / k-means / entrambi
**A:** HDBSCAN — density-based, noise-aware, 4-properties match. min_cluster_size ∈ [15,25] da decidere plan-phase.

**Q A-4:** Feature space per HDBSCAN clustering Phase 9.
Options presentate: raw via build_feature_vector Phase 7 (Recommended) / raw + PCA / LightGBM importance subset / hand-curated forex
**A:** Raw via build_feature_vector Phase 7 — ~66 dim post-preprocessing. Consistency totale Phase 7 ↔ Phase 9. PCA fallback condizionale Wave 2 add-on.

**Claude's discretion captured (Area A):** Re-cluster frequency (artifact persistito + auto re-compute on retrain trigger + manual MCP fire-and-forget analog Phase 8 D-08-A1), cluster output schema, cluster quality validation (Davies-Bouldin + silhouette), preprocessing pipeline order.

---

### Area B — Drift monitor + CLI dashboard (ML-08 + MCP-08 + INT-03)

**Carry-forward locked annotato:** data source `logs/ml_inference.log` rotativo (Phase 7 Claude discretion + PROJECT.md L106), reference snapshot da `models/classifier_v{N}.metadata.json` fold_metrics (Phase 7 D-15), bundle path convention.

**Q B-1:** Quali dimensioni di drift traccia il monitor Phase 9?
Options presentate: 3-tier prediction KS + ECE + feature drift top-K (Recommended) / solo 2 MUST / comprehensive 4-tier / custom
**A:** 3-tier — prediction KS + ECE + feature drift top-K (K=15 da LightGBM importance bundle). Hit-rate/rejection-rate derivati come CLI dashboard view-only.

**Q B-2:** Reference baseline per drift comparison Phase 9.
Options presentate: Static training set (Recommended) / Rolling N giorni / Hybrid static + rolling / spiega meglio re-predict vs OOF
**Clarification:** User chiese "spiegami perche mi stai raccomandando la static" — Claude rispose con 5 ragioni forti centrate sul fatto che static è l'unica opzione che risponde alla domanda che il drift monitor esiste per rispondere:
1. Rolling ha blind spot su slow drift creeping (failure mode più probabile forex — regime cycles graduali)
2. Cold-start: rolling è blind 30+ giorni Phase 11 day-1 deploy
3. Audit trail anchored via sha256 vs floating (project memory data integrity)
4. Closed loop self-healing con retrain trigger Area C: drift breach → retrain → reference shifts → drift resolved
5. Numero invariante nel tempo per longitudinal interpretation
Contro-argomento onesto: rolling sarebbe preferibile solo se (no retrain trigger / training non rep / goal=anomaly detection) — nessuno dei nostri pre-condition.
**Riformulato:** Static (Recommended) / Rolling / Hybrid
**A:** Static = training set — da metadata.json dataset_hash. Rolling diagnostic detail deferred Phase 11+ ~100 LOC.

**Q B-3:** Alarm threshold model Phase 9 drift monitor.
Options presentate: single-threshold per-metric .env (Recommended) / multi-tier severity / Bonferroni-corrected / fuse con Area C
**A:** Single-threshold per-metric .env — DRIFT_KS_PVALUE_THRESHOLD=0.01 + DRIFT_ECE_DELTA_THRESHOLD=0.02 + DRIFT_FEATURE_FRACTION_THRESHOLD=0.30. Global alarm = ANY 1 breached.

**Q B-4:** Persistence + CLI dashboard INT-03 Phase 9.
Options presentate: drift_log.db SQLite + markdown (Recommended) / JSON snapshots + tabulate / in-memory only / drift_log + watch-mode TUI
**A:** drift_log.db SQLite + scripts/show_drift.py → .planning/research/drift-report-{date}.md. Codebase pattern match trades.db convention.

**Claude's discretion captured (Area B):** drift_log.db schema details, INT-03 markdown report sections, feature drift compute (categorical excluded → chi-square future), ECE compute (rolling N predict outcome confirmed, 10-bin reliability sklearn), MCP-08 response shape (specified in CONTEXT.md § specifics), cold-start handling (MIN_DRIFT_SAMPLES=30 default).

---

### Area C — Retrain trigger workflow (ML-09)

**Carry-forward locked annotato:** ML-09 spec literal "drift breach OR scheduled monthly OR manual via tool" → tutti e 3 obbligatori (HOW non WHETHER). Cap=1 JobQueue condiviso Phase 6 D-A4 + Phase 8 D-08-A2. Project memory hard rule (bundle write atomic, no cancel mid-fold, no overwrite in-place).

**Q C-1:** Execution model per ML-09 retrain trigger Phase 9.
Options presentate: riusa Phase 8 train_ml_filter (Recommended) / dedicato retrain_queue / OS cron standalone
**Clarification:** User chiese "perche e' meglio usare quelli della fase 8 invece che crearne di nuovi dedicati?" — Claude rispose con architectural insight + 6 ragioni:
- Same operation different triggers (caller orthogonal to execution)
- Data integrity protection già costruita E provata
- Race cross-queue strettamente più difficile della in-queue serialization
- Audit surface unificato (1 audit path)
- Test surface dimezzato (~150 LOC vs ~750 LOC)
- Codice duplicato → divergenza futura
- MCP tool surface coerente
Steelman counter-arguments (logical separation / independent scaling / different lifecycle / different ownership) confutati uno-a-uno.
Unico caso dove dedicato avrebbe senso: Phase 11+ DEPLOY-02 uptime-independence (deferred).
**Riformulato:** riusa Phase 8 (Recommended) / dedicato / OS cron deferred Phase 11+
**A:** Riusa Phase 8 train_ml_filter via JobQueue — 3 trigger enqueue stesso worker. APScheduler in scheduler.py per cron monthly. trigger_retrain() thin wrapper.

**Q C-2:** Validation gate post-retrain Phase 9.
Options presentate: auto-validation gate (Recommended) / auto-promote / manual promotion / hybrid auto+manual override
**A:** Auto-validation gate — .pkl.candidate + 3 check (ECE regression / KS divergence / threshold sweep) + atomic rename if pass / kept candidate + alarm if fail. Old model atomicamente preserved.

**Q C-3:** Trigger coordination + dedup policy Phase 9 retrain.
Options presentate: dedup idempotent (Recommended) / all queued / LRU/source-priority
**A:** Dedup idempotent — retrain in-flight → subsequent triggers no-op con `status: already_pending` + job_id existing. triggered_by_sources array per audit.

**Q C-4:** Failure escalation policy Phase 9 retrain.
Options presentate: alarm-only (Recommended) / auto-disable ENABLE_ML_FILTER / halt auto-triggers / exponential backoff
**A:** Alarm-only — old model resta attivo (atomic guarantee). .candidate kept come audit. Operator decide manualmente. Auto-escalation deferred Phase 11+ informato da paper deploy ops experience.

**Claude's discretion captured (Area C):** Drift breach fire condition (ANY 1 di 3 metric → fire), APScheduler cron spec (CronTrigger month=*,day=1,hour=2,UTC default + .env configurable), manual MCP `trigger_retrain(reason, force)` semantics, validation_log.db schema, MLFilter singleton hot-reload mechanism (atomic rename + cache invalidation), trigger source = drift_breach with foreign key reference to drift_log row.

---

### Area D — suggest_position_action logic (MCP-18)

**Carry-forward locked annotato:** MCP-18 = suggest NOT mutate (Phase 6 handle_modify_position downstream), action enum REQ-locked (hold/move_sl/partial_close/full_close), EXECUTION_MODE=shadow mandate, position state via Phase 6 handle_get_position_state.

**Q D-1:** Decision source per MCP-18 suggest_position_action Phase 9.
Options presentate: hybrid rule + ML re-eval (Recommended) / pure rule-based / pure ML re-eval / full hybrid + failure cluster
**Pre-question semantic caveat surfaced:** Phase 7 D-17 — classifier addestrato su features_at_decision_time, NON mid-trade. Using classifier mid-trade = OOD inference (interpretation: "se proponessi questo trade ADESSO con condizioni correnti, lo prenderei?").
**A:** Hybrid rule + ML re-evaluation — rule-based primary (R-multiple + Time stop), ML modula severity ("thesis still valid" check), OOD caveat surface esplicitamente. No cluster dependency Phase 9 first-ship.

**Q D-2:** Output response shape MCP-18 suggest_position_action.
Options presentate: structured rationale (Recommended) / simple flat / multi-action ranked top-K / decision tree explainer
**A:** Structured rationale — `{action, params, confidence, rationale: {rules_triggered, ml_check, summary_it}}`. CLAUDE.md italian-rationale compliant. Backward-extensible.

**Q D-3:** Rule library scope per Phase 9 suggest_position_action rule-based component.
Options presentate: Standard 4-rule (Recommended) / Minimal 2-rule / Extended 5-rule / Comprehensive 7+ rule
**A:** Standard 4-rule + profile-aware .env — R-multiple BE + partial + full + Time stop. Volatility shrink + MTF reversal + Spread expansion deferred Phase 9 v2 / Phase 10.

**Q D-4:** ML feature snapshot timing per MCP-18 prob_at_entry source.
Options presentate: hybrid cached + fallback recompute (Recommended) / persist only / recompute only / skip prob_at_entry
**A:** Hybrid prefer cached + fallback recompute — schema add ml_calibrated_prob a trades_log + write at log_trade_decision + recompute via decision_context_json fallback per legacy. Forward+backward compatible.

---

## Areas NOT discussed (Claude's discretion explicitly captured in CONTEXT.md)

- Re-cluster frequency artifact (Area A — derived from Phase 7/8 patterns)
- HDBSCAN distance metric scelta (gower vs euclidean post-preprocessing) — plan-phase decision
- min_cluster_size HDBSCAN exact value — cluster-quality validation in plan-phase
- drift_log.db schema details — codebase pattern trades.db
- INT-03 markdown report sections layout — analog Phase 5/8 report writer
- feature drift compute mechanism (categorical excluded) — plan-phase
- ECE compute window N samples — plan-phase
- APScheduler cron Default value (1° giorno mese 02:00 UTC) — Claude's discretion .env configurable
- MLFilter singleton hot-reload mechanism — plan-phase
- validation_log.db schema — derivato da drift_log pattern

## Scope creep redirected to deferred ideas

User non ha proposto scope creep esplicito. 16 deferred ideas captured proattivamente da Claude per (a) Phase 9 v2 retrofit (cluster match integration, volatility shrink), (b) Phase 11+ ops-informed enhancement (auto-disable filter, exponential backoff, halt-auto-triggers), (c) cross-phase deferral (MTF reversal, spread expansion → Phase 10).

## User patterns observed (for future sessions)

- User chiede frequentemente "perché raccomandi X" (3 occorrenze): HDBSCAN, static reference, riuso Phase 8 train_ml_filter. Expected: receiving honest comparative justification, not just option list. Feedback memory may apply: when recommending, lead with reasons-and-trade-offs, not labels.
- User vuole spiegazioni dettagliate (1 occorrenza): "spiegami dettagliato tutto" — well-received exhaustive 6-section response. Useful pattern when complexity is high.
- User non ha richiesto verifica empirica del parquet anche se offerta (Area A loss definition). Indica tolleranza per ragionamento basato su stime ben-grounded.
