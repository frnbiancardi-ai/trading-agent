# Phase 8 Discussion Log

**Session:** 2026-05-12 via `/gsd-discuss-phase 8`
**Mode:** default (4 single-question turns per area max)
**Outcome:** 14 decisioni D-08-A1..D5 captured in 08-CONTEXT.md

## Areas presented (multiSelect)

User selected ALL 4 aree proposte:
1. train_ml_filter execution model
2. Data source per train_ml_filter
3. get_ml_calibration response shape
4. ML-on backtest report INT-02 scope

Aree omesse dalla presentazione (pre-cooked dalle Phase 6/7 decisions, no re-ask):
- `evaluate_trade_proposal` backward-compat (già: Phase 7 D-07-06-11 zero-impact rollout ENABLE_ML_FILTER=false default → response sempre include `ml_score=null` quando disabled, graceful, no error)
- MLFilter singleton riuso (già: Phase 7 Plan 07-05 ml/inference.py)
- mcp_tools/handlers/ml.py file convention (già: Phase 6 mcp_tools/handlers/ pattern)
- ErrorCodes envelope (già: Phase 6 mcp_tools/errors.py)
- Shadow-mode mandate (già: CLAUDE.md project-level)

---

## Area 1: train_ml_filter execution model

### Q1: Sync vs async execution
- **Options presented**: async via JobQueue Phase 6 (Recommended) / sync handler con timeout / hybrid dry-run+full
- **Answer**: "Async via JobQueue (Recommended)"
- **D-08-A1**: train_ml_filter ritorna `{ok, job_id, status}`, worker top-level picklable, status polling via `get_ml_training_status`

### Q2: JobQueue cap concorrenza
- **Options presented**: cap condiviso MCP_MAX_CONCURRENT_RUNS=1 (Recommended) / cap separato 1+1 / priority queue
- **User clarification request**: "quale opzione non invalida training E backtest"
- **Claude analysis**: il rischio reale NON è CPU, è file I/O contention. Training legge `data/training/baseline_decisions/part-0.parquet` che backtest scrive (Plan 05-09 dataset_writer). Due worker simultanei = read on truncated file → modello silently corrupt. Cap condiviso 1 = serializzazione naturale = zero race-by-construction.
- **Answer post-clarification**: "Sì, cap condiviso = 1 (Recommended)"
- **D-08-A2**: MCP_MAX_CONCURRENT_RUNS=1 shared per evitare race su parquet input

### Q3: cancel_ml_training tool
- **Options presented (revised post-clarification)**: cooperative cancel tra fold completati (safe) / no cancel fire-and-forget (Recommended, safer-by-construction)
- **User clarification request**: "quale opzione non invalida training, training priority assoluta su dati GIUSTI"
- **Claude analysis**: opzione 3 (terminate-worker hard) esclusa a priori — process.terminate mid bundle write = pickle truncated = silently corrupt model. Tra cooperative cancel e no-cancel: entrambi safe, ma no-cancel ha zero codice cancel = zero surface bug cancel-related. Per priority dati GIUSTI: safest-by-construction = no cancel.
- **Project memory saved**: `project_training_data_integrity_priority.md` — "Training ML data integrity = priority assoluta. Qualunque trade-off Phase 7+ va risolto a favore di training non invalidabile anche a costo di UX peggiore"
- **Answer post-clarification**: "No cancel, fire-and-forget (Recommended)"
- **D-08-A3**: training fire-and-forget, no cancel_ml_training tool exposed

---

## Area 2: Data source per train_ml_filter

### Q1: Solo baseline vs +live trades
- **Options presented**: solo baseline (Recommended) / baseline+live merged / configurable env var
- **User clarification request**: "baseline+live addestra maggiormente, corretto? cosa succede se becca dati corrotti?"
- **Claude analysis**:
  - "Addestra maggiormente": quantitativo sì (più rows), qualitativo no. 3 problemi qualitativi: (1) label encoding diverge (USER_CLOSE ambiguity), (2) distribuzione skewed pre-filtered → overfit invisibile, (3) feature ricomputo richiede CSV immutability garantita altrimenti future leakage silenzioso.
  - "Cosa succede se becca dati corrotti": Classe A (crash rumoroso, gestibile: parquet truncated → pyarrow OSError → abort) vs Classe B (silently corrupt model, pericoloso: schema mismatch soft → NaN propagation → predict() ritorna numeri normali ma garbage; ricomputo on stale historical → future leakage invisibile; label ambiguity → modello non riproducibile). La priority dati GIUSTI mira a eliminare Classe B per costruzione.
  - Per "baseline+live" senza autosabotaggio serve schema bridge maturo (~200-400 LOC dedicated). Phase 8 non lo include.
- **Answer post-clarification**: "Solo baseline, MCP-04 contract extensible (Recommended)"
- **D-08-B1 + D-08-B2**: solo baseline parquet hardcoded path; MCP-04 schema arg `data_source: enum[baseline]` extensible per Phase 9+/11+

### Q2: Schema validation strictness
- **Options presented**: strict-fail + sha256 check (Recommended) / permissive + log warning / strict-fail senza sha256
- **Answer**: "Strict-fail + sha256 check (Recommended)"
- **D-08-B3**: pre-training validation (n_cols == 59, presence required cols, sha256 file fingerprint in metadata.json, n_rows >= MIN_TRAINING_ROWS=1000). Fail → ErrorCodes.validation_failed + abort.

---

## Area 3: get_ml_calibration response shape

### Q1: Aggregato vs per-fold vs hybrid
- **Options presented**: aggregato + reliability bins (Recommended) / per-fold breakdown completo / default aggregato + arg include_folds
- **User clarification request**: "aiutami a capire i vantaggi di ogni singola opzione tenendo in conto che non voglio la sufficienza"
- **Claude analysis**:
  - Identified 3 consumer (skill agentic, operator, Phase 9 drift); skill+operator are the real MCP clients.
  - "Sufficienza" risk: aggregato cross-fold MASCHERA fold-1 sballato (val=20 Platt-only forzato, Brier 0.45 mascherato da media 0.22). Final retrain include quei dati → fragilità feature-space silenziosa.
  - Opt 2 (per-fold) forza la trasparenza completa; opt 3 con default aggregato non ti dice di passare include_folds=true.
  - Variante "default audit-first, opt-out a aggregato" via `summary_only=true` ribalta semantica → trasparenza di default, brevity esplicita.
- **Answer post-clarification**: "Default audit-first, opt-out a aggregato"
- **D-08-C1 + D-08-C2**: response default = per-fold breakdown completo + aggregate section; arg `summary_only: bool = false` opt-out leggero per skill in tight loop
- **D-08-C3**: enumerati per-fold fields (fold_n, brier, ece, reliability_data, calibrator_winner, val_size, val_too_small_flag, n_train, n_val)

---

## Area 4: ML-on backtest report INT-02 scope

### Q1: Scope di esecuzione re-run
- **Options presented**: analysis-only su parquet esistente (Recommended) / full 27/27 re-run con engine + ML gate / subset 9/27 / hybrid analysis-now + full Plan 08-NN
- **Answer**: "Full 27/27 re-run con engine + ML gate"
- **D-08-D1**: PC secondario riesegue 10y 27 slice con ENABLE_ML_FILTER=true. Output: `data/training/baseline_ml_on/part-0.parquet` separato + report MD. Testa interazioni dinamiche (SL/TP/trail/risk capital sequenziale post-ML-rejection).

### Q2: Dove gira il re-run
- **Options presented**: PC secondario notturno post-Phase 7 execute (Recommended) / PC primario sessione Claude / decidi dopo
- **Answer**: "PC secondario notturno post-Phase 7 execute (Recommended)"
- **D-08-D2 + D-08-D3**: workflow analog Plan 05-09 STEP 3, PC secondario notturna ~14000s wall-clock + `scripts/run_ml_on_backtest.py` standalone wrapper (--smoke / --only-runs / --max-wall-clock / --no-time-gate)

### Q3: Report shape
- **Options presented**: side-by-side + delta + ML stats (Recommended) / aggregato globale solo / side-by-side + diagnostic deep-dive degraded slices
- **User clarification request**: "spiegami dettagliatamente le varie opzioni"
- **Claude analysis**: identified 3 consumer (operator one-shot, gsd-verifier automated SC closure, Phase 9 drift baseline). Mostrato mockup concreto per ogni opzione sui numeri reali del baseline-2026-05-12.md (USDJPY M15 AGGRESSIVE 415 trade, hit-rate 34.2%, ecc.). Opt 3 (degraded slices analysis) coerente con priority "no sufficienza" applicata anche al report: input strutturato per Phase 9 calibration retune senza manual investigation di 1076 rejected trade.
- **Answer post-clarification**: "Opt 3 — Side-by-side + diagnostic degraded slices (Recommended)"
- **D-08-D4 + D-08-D5**: report ~250 LOC writer logic con (1) header bundle sha256, (2) Aggregate Verdict 5 criteria automated SC#4 closure, (3) Per-slice breakdown 27 rows, (4) Rejection rate per profile, (5) Degraded Slices Analysis automatica con suggested threshold tuning + Phase 9 calibration retune recommendation. SC#4 closure via verdict block macchina-leggibile parsato da gsd-verifier.

---

## Decisions Captured Summary

| ID | Area | Decision |
|---|---|---|
| D-08-A1 | exec | async via JobQueue Plan 06-03 |
| D-08-A2 | exec | cap condiviso MCP_MAX_CONCURRENT_RUNS=1 |
| D-08-A3 | exec | no cancel fire-and-forget |
| D-08-B1 | data | data_source = baseline parquet hardcoded |
| D-08-B2 | data | MCP-04 schema enum extensible |
| D-08-B3 | data | strict-fail + sha256 + n_rows>=1000 |
| D-08-C1 | calibration | default per-fold breakdown completo |
| D-08-C2 | calibration | arg summary_only opt-out leggero |
| D-08-C3 | calibration | per-fold fields enumerati |
| D-08-D1 | backtest | full 27/27 re-run engine + ML gate |
| D-08-D2 | backtest | PC secondario notturno post-Phase 7 |
| D-08-D3 | backtest | scripts/run_ml_on_backtest.py wrapper |
| D-08-D4 | backtest | report Opt 3 degraded slices analysis |
| D-08-D5 | backtest | SC#4 automated verdict 5/5 criteria |

## Deferred Ideas (captured in CONTEXT.md `<deferred>`)

- Schema bridge baseline+live trades merge (Phase 9/11)
- Cancel_ml_training tool review (future scaling)
- Drift detection / retrain trigger (Phase 9)
- suggest_position_action MCP tool (Phase 9)
- Per-slice threshold override (Phase 11 calibration retune)
- Multi-model A/B champion/challenger (Phase 11+)
- Scheduled retraining (Phase 9/11)
- predict_trade_quality batch input (defer to hot-path evidence)

## Claude's Discretion (downstream agents decide)

- Logging conventions (ml_training.log)
- Test fixture reuse (Plan 07-01 200-row deterministic)
- Worker process error envelope
- predict_trade_quality latency budget (<50ms p95, optional benchmark)
- Schema JSON validation (draft-7 standard)
- Dispatch bucket order
- MCP tool args required vs optional enumeration
- Bundle path symlink convention
- Wave granularity (4-7 plans accettabili)

## Scope Creep Avoided

Nessuno emerso. User restato sempre nello scope Phase 8 (3 ML MCP tools + 1 refactor + 1 backtest report). Phase 9 scope (drift/retrain/suggest_position) e Phase 11 scope (paper deploy) referenziati ma redirected senza tentativi di anticipo.
