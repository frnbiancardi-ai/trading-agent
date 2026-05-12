# Phase 8: MCP Tools (part 2) — Context

**Gathered:** 2026-05-12
**Status:** Ready for planning (`/gsd-plan-phase 8 --skip-research` after Phase 7 execute completes)
**Source:** `/gsd-discuss-phase 8` interactive session — 4 aree discusse, 14 decisioni catturate

<domain>
## Phase Boundary

Esponi attraverso MCP server i tre tool ML mancanti (`train_ml_filter`, `predict_trade_quality`, `get_ml_calibration`), estendi `evaluate_trade_proposal` response con `ml_score` + `calibrated_prob` (backward-compatible), e produci il post-ML backtest report comparativo (`.planning/research/ml-on-{date}.md`) come deliverable SC#3 + SC#4. Phase 8 NON addestra il classificatore ML (è Phase 7 scope) e NON aggiunge logica di drift / retrain trigger (Phase 9 scope) — è il "guscio MCP" che espone le capability ML al di fuori del processo e produce l'evidenza comparativa che il modello sblocca edge non-triviale.

**5 requisiti coperti:** MCP-04 (`train_ml_filter`), MCP-05 (`predict_trade_quality`), MCP-06 (`get_ml_calibration`), MCP-R4 (`evaluate_trade_proposal` extension), INT-02 (ML-on backtest report).

**4 success criteria ROADMAP:**
1. I 3 nuovi tool + 1 refactor registrati in `mcp_server.py` con JSON-Schema + pass integration test
2. `evaluate_trade_proposal` response include `ml_score` + `calibrated_prob` senza rompere consumer esistenti (forex-trader-pro skill, mcp_tools/handlers/proposal.py)
3. Post-ML backtest report committed a `.planning/research/ml-on-{date}.md` con per-slice delta vs baseline-2026-05-12.md (Sharpe, hit rate, expectancy, drawdown)
4. ML-on backtest dimostra non-trivial improvement vs baseline OR documented analysis (negative result acceptable signal)

</domain>

<prior_decisions>
## Carry-forward decisions (NOT re-asked)

### From Phase 6 (MCP package conventions)
- **mcp_tools/handlers/ pattern**: handler signature `handle_<tool>(args: dict, deps..., cfg) → dict response` (analog `backtest.py` 4 handler). Phase 8 aggiunge `mcp_tools/handlers/ml.py`.
- **ErrorCodes envelope**: tutti gli error response usano `mcp_tools/errors.py` ErrorCodes (validation_failed, internal_error, not_found). Già wired in handler pattern.
- **JobQueue ProcessPoolExecutor**: Plan 06-03 D-A1/A3/A4 — cap=1 hard via `MCP_MAX_CONCURRENT_RUNS`. Worker top-level picklable (no mt5_client / MetaTrader5 import dentro worker).
- **Shadow-mode mandate**: handler che toccano risk_engine verificano `EXECUTION_MODE=shadow` (CLAUDE.md regola fondamentale).
- **BarSource D-D1 strict-<**: per qualunque snapshot temporale.
- **Tool registration**: schema JSON in handler module, dispatch bucket in `mcp_tools/server.py` list_tools + dispatch refactor.

### From Phase 7 (ML pipeline)
- **D-07-12 hybrid hook**: prediction in `strategy/__init__.py evaluate_proposal_for_bar`, decision (threshold gate) in `risk_engine.evaluate_trade`. **`predict_trade_quality` MCP tool è un wrapper read-only di `MLFilter.predict()`, non duplica logica di gate decision.**
- **MLFilter singleton** (Phase 7 Plan 07-05): caricato 1 volta a bootstrap, riusato attraverso process-local cache. `predict_trade_quality` riusa lo stesso singleton.
- **ENABLE_ML_FILTER=false default** (Phase 7 D-07-06-11): zero-impact rollout. `evaluate_trade_proposal` response include `ml_score: null` + `calibrated_prob: null` quando ML disabled, senza error.
- **Threshold per-profile da metadata.json sidecar** (Phase 7 D-11 + Plan 07-05): `models/classifier_v{N}_{date}.metadata.json` letto al bootstrap; threshold dict in memoria; mai env-driven.
- **Bundle path convention**: `models/classifier_v{N}_{date}.pkl` + sidecar `.metadata.json` (Phase 7 D-19 + Plan 07-05).
- **D-09-G derivation 8 fields**: già implementato in Phase 7 `ml/feature_extraction.py`. `predict_trade_quality` riusa `build_feature_vector(ctx)` con stessa logica.

### Project-level (PROJECT.md / CLAUDE.md)
- **EXECUTION_MODE=shadow default sempre** — qualunque MCP tool che chiama `risk_engine.evaluate_trade` o `mt5_client.send_order` deve verificare e rispettare.
- **risk_engine = unico gate approvazione trade** — `predict_trade_quality` NON è un gate, è introspection. Il gate vero è in `risk_engine.evaluate_trade` esposto via `evaluate_trade_proposal`.
- **Italiano per log/comment/rationale**, English per nomi tecnici/code/file paths.
- **Tutto da .env, zero magic numbers**.

</prior_decisions>

<decisions>
## Implementation Decisions

### Area 1: train_ml_filter execution model (3 decisioni)

- **D-08-A1 — Async via JobQueue Plan 06-03.** `handle_train_ml_filter(args, job_queue, cfg)` registra il job, ritorna `{ok: true, job_id: <uuid>, status: "queued"|"running"}`. Worker top-level picklable `_train_ml_filter_worker(args, cfg_dict)` chiama `ml.train.train_classifier(cfg)` direttamente (Phase 7 Plan 07-03 + 07-05). Skill polling via `get_ml_training_status(job_id)` analog `get_backtest_metrics`. Coerente con MCP-01/02 pattern. **Why:** training ~30-60s wall-clock può superare Anthropic SDK tool timeout default; async UX è canonical MCP pattern.

- **D-08-A2 — Cap concorrenza condiviso `MCP_MAX_CONCURRENT_RUNS=1`.** Riusa lo stesso JobQueue di Phase 6 backtest, senza nuova env var. **Why:** training legge `data/training/baseline_decisions/part-0.parquet` che backtest può scrivere (Plan 05-* re-run). Due worker simultanei sul parquet = race condition reale (pyarrow read mid-finalize → file truncated → modello silently corrupt). Cap condiviso = serializzazione naturale, zero race-by-construction. Trade-off: training queued ~14000s se backtest gira; accettabile dato che baseline re-run è raro (one-shot per phase, non daily).

- **D-08-A3 — No cancel, fire-and-forget (no `cancel_ml_training` tool).** Training va sempre fino in fondo. **Why:** training ~30-60s vs backtest ~14000s: il valore del cancel è basso, il costo del cancel-bug è alto (process.terminate mid-bundle-write = pickle truncated = MLFilter.load silently corrupt). Zero codice cancel = zero surface bug cancel-related. Coerente con [project memory: Training ML data integrity = priority assoluta]. Trade-off UX: se lanci per errore, aspetti il completamento.

### Area 2: train_ml_filter data source (3 decisioni)

- **D-08-B1 — Data source = baseline parquet hardcoded.** Path fisso `data/training/baseline_decisions/part-0.parquet` (1076 rows × 59 cols, certificato da Plan 05-09 SCHEMA validation, commit `0410bf2`). Phase 7 D-09-G derivation già implementata in `ml/feature_extraction.py`. **Why:** baseline è l'unico dataset oggi con schema-v2 garantito + label encoding D-07-01 deterministic (TP_HIT only). `logs/trades.db` ha schema legacy + label ambiguity (USER_CLOSE) + distribuzione pre-filtered che produrrebbe overfit + indicators ricomputo richiede CSV immutability check. Coerente con priority dati GIUSTI: niente bridge schema maturo → niente merge live diretto.

- **D-08-B2 — MCP-04 contract `data_source` enum extensible.** Schema JSON: `data_source: {"type": "string", "enum": ["baseline"], "default": "baseline"}`. Phase 8 supporta solo `baseline`; future Phase 9/11 estende enum quando logs/trades.db avrà dati live reali da Phase 11 paper deploy E schema bridge maturo sarà implementato (USER_CLOSE label policy, CSV immutability sha256 check, dedup re-entry policy locked, schema bridge ~200-400 LOC dedicated Wave/Plan). **Why:** future-proof tool contract senza prematuro codice di bridging.

- **D-08-B3 — Strict-fail + sha256 check pre-training.** `train_ml_filter` apre il parquet con pyarrow, verifica: (1) n_cols == 59, (2) presenza specifiche colonne required (D-09-G derivable + ML-01 baseline features per `_SCHEMA_V2_REQUIRED_KEYS` da Plan 05-09 importato + 8 D-09-G fields), (3) calcola sha256 del file e lo registra in metadata.json del bundle output, (4) `n_rows >= MIN_TRAINING_ROWS` (default 1000 da HANDOFF SC#3 hard gate). Fail check → `ErrorCodes.validation_failed` envelope + abort immediato senza touch a output. **Why:** elimina classe-B silently-corrupt-model failure mode per costruzione. Audit trail sha256 = riproducibilità post-hoc (dopo 6 mesi puoi sapere quale parquet ha addestrato il modello vN).

### Area 3: get_ml_calibration response shape (3 decisioni)

- **D-08-C1 — Default audit-first: per-fold breakdown completo.** Response default: `{model_version, trained_at, threshold_by_profile, folds: [10 fold ognuno con {fold_n, brier, ece, reliability_data, calibrator_winner, val_size, val_too_small_flag, n_train, n_val}], aggregate: {brier, ece, reliability_data: [20 bins]}}`. ~30-50KB payload. **Why:** coerente con priority "no sufficienza" — l'aggregato cross-fold MASCHERA fold-1 sballato (val=20 Platt-only forzato HANDOFF blocker #3), il bundle finale include quei dati nel final retrain (Plan 07-05 Task 3) quindi un Brier-1 cattivo segnala fragilità feature-space coperta da quel fold. Operator + Phase 9 drift entrambi serviti senza navigare metadata.json on-disk.

- **D-08-C2 — Opt-out leggero via arg `summary_only=true`.** `get_ml_calibration(summary_only=true)` ritorna solo `aggregate + threshold_by_profile + model_version + trained_at` (~3-5KB). Skill agentic in tight loop può richiedere brevity esplicita. **Why:** Reverse-semantics di "default aggregato + flag verbose" (Opt 3 originale) → forza chi vuole sufficienza a chiederla, default trasparente.

- **D-08-C3 — Per-fold fields enumerati**: `fold_n` (int 1-10), `brier` (float), `ece` (float), `reliability_data` (list of `{prob_bin_mid, observed_freq, count}` ~10-20 bins per fold), `calibrator_winner` (str enum `["sigmoid", "isotonic"]`), `val_size` (int), `val_too_small_flag` (bool, true if val < 50 → Platt-only forzato), `n_train` (int), `n_val` (int). Source: metadata.json fold sidecar (Plan 07-03 `_write_fold_metadata`).

### Area 4: ML-on backtest report INT-02 scope (5 decisioni)

- **D-08-D1 — Full 27/27 engine re-run con ML gate attivo.** PC secondario riesegue tutto il 10y window 27 slice (3 pair × 3 TF × 3 profile) con `ENABLE_ML_FILTER=true` in `risk_engine.evaluate_trade`. Output: nuovo parquet `data/training/baseline_ml_on/part-0.parquet` (separato da `baseline_decisions/` per non sovrascrivere il training input) + report MD. **Why:** testa interazioni dinamiche (SL/TP/trail under ML rejection, risk capital sequenziale liberato da ML-rejected trade, position management impact). Analysis-only offline su parquet baseline non catturerebbe queste interazioni. Trade-off costo: ~14000s wall-clock PC secondario notturno = accettabile come one-shot SC#4 closure.

- **D-08-D2 — Coordinamento PC secondario notturno post-Phase 7 execute.** Workflow analogo Plan 05-09 STEP 3. PC primario completa Phase 7 execute (Wave 0-5 + bundle.pkl + metadata.json), committa, push al remoto. PC secondario `git pull`, installa `lightgbm` + `sklearn` (verifica `SETUP-SECONDARY-PC.md` per dipendenze ML aggiuntive), pre-flight (smoke test MLFilter.predict su 10 samples), lancia `scripts/run_ml_on_backtest.py`. Notturna ~14000s. Push parquet+report back. PC primario pull + finalize INT-02. RESUME-PLAN.md aggiunge STEP dedicato (es. STEP 14) post Phase 7 STEP 13 execute.

- **D-08-D3 — Deliverable `scripts/run_ml_on_backtest.py` standalone.** Wrapper Python eseguibile senza Claude Code (analog `scripts/run_baseline_05_09.py`). Flag: `--smoke` (1 slice mini-range ~30-60s validation), `--only-runs <ids>` (riusa `_force_clear_run` da slice_worker), `--max-wall-clock <s>` (safety abort), `--no-time-gate` (override SC#1 wall-clock check). Auto-detect bundle path da `config.ML_MODEL_PATH`, validate sha256 metadata.json pre-run. Output: stdout tqdm progress + log strutturato + exit code 0 se 27/27 OK.

- **D-08-D4 — Report shape Opt 3: side-by-side per slice + diagnostic degraded slices.** `.planning/research/ml-on-{date}.md` contiene: (1) Header (bundle sha256, threshold per profile, wall-clock, run_id), (2) Aggregate Verdict table con automated SC#4 assertion criteria (Sharpe Δ ≥ +50, hit-rate Δ ≥ +0.05, trade retention ≥ 30%, expectancy sign flip + Δ ≥ +5, MaxDD Δ ≤ -100 — N/5 criteria pass), (3) Per-slice breakdown 27 rows con `base_n, ml_n, base_sharpe, ml_sharpe, base_hit, ml_hit, base_pf, ml_pf, rejection_rate`, (4) Rejection rate per profile, (5) **Degraded Slices Analysis automatica** per ogni slice dove `ml_sharpe < base_sharpe`: lista rejected trade marginali (calibrated_prob entro ±5% del threshold di profilo) + suggested threshold tuning per quella slice + recommendation Phase 9 calibration retune. ~250 LOC report writer logic. **Why:** coerente con priority "no sufficienza" applicata anche al report. Input strutturato per Phase 9 drift monitor.

- **D-08-D5 — SC#4 closure via automated verdict assertion.** Report include `## Verdict` section macchina-leggibile: 5 criteria pass/fail enumerati, status finale `NON_TRIVIAL_IMPROVEMENT` se ≥ 4/5 OR `NEGATIVE_RESULT_DOCUMENTED` se < 4/5 con sezione "Why negative" auto-generata dai Degraded Slices Analysis (NON un fail, è documented). `gsd-verifier` durante `/gsd-verify-work 8` parsa il verdict block per chiusura deterministica.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before research / planning / implementation.**

### Phase 7 ML pipeline (mandatory)
- `.planning/phases/07-ml-classifier/07-CONTEXT.md` — D-01..D-20 + 7 Claude discretion ML decisions, label encoding, fold design, threshold gate
- `.planning/phases/07-ml-classifier/07-RESEARCH.md` — 6 patterns + 7 pitfalls + validation architecture (Open Questions RESOLVED post-Phase-7 plan)
- `.planning/phases/07-ml-classifier/07-PATTERNS.md` — 20 file mapped, 17 analogs (specialmente `ml/inference.py` MLFilter singleton + `ml/feature_extraction.py` D-09-G derivation)
- `.planning/phases/07-ml-classifier/07-05-PLAN.md` — MLFilter.predict API + joblib bundle + metadata.json sidecar schema
- `.planning/phases/07-ml-classifier/07-06-PLAN.md` — evaluate_proposal_for_bar + ProposalDraft extension + risk_engine ML gate

### Phase 6 MCP package conventions (mandatory)
- `.planning/phases/06-mcp-tools-part-1/06-CONTEXT.md` — D-A/B/C/D/E/F decisions (JobQueue, BarSource, mcp_tools/ package split)
- `.planning/phases/06-mcp-tools-part-1/06-03-PLAN.md` — JobQueue Plan + handler pattern + worker top-level picklable rule (analog per `handle_train_ml_filter`)
- `.planning/phases/06-mcp-tools-part-1/06-02-PLAN.md` — mcp_tools/handlers/ + mcp_tools/server.py dispatch refactor
- `.planning/phases/06-mcp-tools-part-1/06-PATTERNS.md` — handler shape analogs (handlers/backtest.py per ML tool, handlers/proposal.py per evaluate_trade_proposal extension)

### Phase 5 baseline dataset (mandatory for training input)
- `.planning/phases/05-baseline-backtest/05-09-PLAN.md` — schema-v2 specifica + `_SCHEMA_V2_REQUIRED_KEYS` programmatic
- `.planning/phases/05-baseline-backtest/05-09-SUMMARY.md` — execution results PC secondario (sezione "Execution Results — PC secondario 2026-05-12")
- `.planning/research/baseline-2026-05-12.md` — baseline metrics 27 slice (input per delta computation in ML-on report)
- `backtest/baseline/dataset_writer.py` + `backtest/baseline/slice_worker.py` — D-09-B no-leakage anchor

### Project-level
- `.planning/PROJECT.md` — milestone goals, value prop, decision log
- `.planning/REQUIREMENTS.md` — MCP-04, MCP-05, MCP-06, MCP-R4, INT-02 definition
- `.planning/ROADMAP.md` Phase 8 section — Goal + 4 SC + Hint UI no
- `CLAUDE.md` — EXECUTION_MODE=shadow, risk_engine unico gate, italiano log
- `COMMIT_CONVENTIONS.md` — feat/fix/test/docs scope per commit Phase 8

### Code analogs (codebase scout)
- `mcp_tools/handlers/backtest.py:309-465` — `handle_run_backtest` + `handle_get_backtest_metrics` + `handle_cancel_backtest` (closest analog per ML tool surface)
- `mcp_tools/handlers/proposal.py:92` — `handle_evaluate_trade_proposal` (placeholder commento riga 5: "Phase 7/8 estendera' con ml_score/calibrated_prob") — extension point ufficiale
- `mcp_tools/job_queue.py` (Plan 06-03) — JobQueue ProcessPoolExecutor cap=1
- `mcp_tools/server.py` — Tool registration + dispatch bucket pattern
- `mcp_tools/errors.py` — ErrorCodes envelope
- `scripts/run_baseline_05_09.py` (Plan 05-09) — closest analog per `scripts/run_ml_on_backtest.py`
- `backtest/baseline/runner.py` — orchestrator pattern (ProcessPool + tqdm + report writer)
- `backtest/baseline/report_writer.py` — Markdown report generation (analog per `ml_on_report_writer.py`)

</canonical_refs>

<code_context>
## Reusable assets identified

### Already produced (Phase 6 + Phase 7 implicit dependencies)
- `mcp_tools/` package: handler convention, schema JSON inline, dispatch bucket, ErrorCodes envelope
- `mcp_tools/job_queue.py`: ProcessPoolExecutor + SQLite registry + DB fallback per status
- `mcp_tools/handlers/backtest.py`: 4 handler già pattern-matchable per ML 3 handler
- `ml/inference.py` (Phase 7 Plan 07-05): MLFilter singleton + predict API
- `ml/train.py` (Phase 7 Plan 07-03): `train_classifier` callable + FoldArtifacts NamedTuple
- `ml/feature_extraction.py` (Phase 7 Plan 07-01): `build_feature_vector(ctx)` + D-09-G derivation
- `models/classifier_v{N}_{date}.pkl` + `.metadata.json`: bundle path convention
- `risk_engine.evaluate_trade` (Phase 7 Plan 07-06): ML gate già wired, ENABLE_ML_FILTER respected
- `strategy/__init__.py:evaluate_proposal_for_bar`: ProposalDraft con `ml_raw_score, ml_calibrated_prob, ml_threshold` già attached

### To produce in Phase 8
- `mcp_tools/handlers/ml.py` (~400-500 LOC): 3 handler ML + worker top-level + helper sha256 validation
- `mcp_tools/server.py` (extension): tool registration list + dispatch bucket ml
- `mcp_tools/handlers/proposal.py` (modify ~30 LOC): extend `handle_evaluate_trade_proposal` response shape con `ml_score` + `calibrated_prob` letti da MLFilter singleton se ENABLE_ML_FILTER, altrimenti null
- `scripts/run_ml_on_backtest.py` (~350-400 LOC): standalone wrapper, analog `run_baseline_05_09.py`
- `backtest/baseline/ml_on_report_writer.py` (~250 LOC): Opt 3 report writer + degraded slices analysis
- `config.py` (extension ~10 LOC): `MCP_TRAINING_DATA_PATH`, `MCP_ML_THRESHOLD_MARGIN_PCT` (default 5%) per degraded slice analysis
- `.env.example`: mirror env vars
- `tests/test_mcp_handlers_ml.py` (~300 LOC): handler test analogs Plan 06-03 test_mcp_handlers_backtest.py
- `tests/test_ml_on_report_writer.py` (~150 LOC): report writer + degraded slices analysis
- `tests/test_mcp_evaluate_proposal_ml_extension.py` (~100 LOC): backward-compat verification, ENABLE_ML_FILTER=true/false branches

### Test fixture reuse
- `tests/fixtures/baseline_decisions_smoke.parquet` (Plan 07-01 200-row deterministic): riusato per smoke test MLFilter.predict in `predict_trade_quality` handler test
- `tests/conftest.py` Mt5Client stub: ML tool NON dipende da MT5; conftest unchanged

### What NOT to reproduce
- NO new MLFilter implementation — riusa Phase 7 `ml/inference.py`
- NO new feature extraction logic — riusa Phase 7 `ml/feature_extraction.py:build_feature_vector`
- NO new training logic — `train_ml_filter` worker chiama `ml/train.py:train_classifier` direttamente
- NO new threshold optimization — già in Phase 7 Plan 07-04, threshold_by_profile letto da metadata.json
- NO drift detection / retrain trigger logic — Phase 9 scope

</code_context>

<specifics>
## Specific Ideas

### evaluate_trade_proposal extension shape (MCP-R4)

Response esistente legacy (forex-trader-pro skill consumer):
```json
{
  "ok": true,
  "approved": true|false,
  "reason": "...",
  "risk_decision": {...},
  ...
}
```

Estensione Phase 8 (additive, backward-compatible):
```json
{
  "ok": true,
  "approved": true|false,
  "reason": "...",
  "risk_decision": {...},
  "ml_score": 0.73 | null,              // raw LightGBM predict_proba(X)[0,1]
  "calibrated_prob": 0.68 | null,       // calibrated via Platt or Isotonic
  "ml_threshold": 0.62 | null,          // threshold per profile from metadata.json
  "ml_filter_active": true | false      // true se ENABLE_ML_FILTER=true E bundle caricato
}
```

`null` quando `ENABLE_ML_FILTER=false` OR `MLFilter` singleton non caricato (errore bootstrap). Mai error envelope: extension è graceful.

### MCP tool registration (Phase 8 dispatch bucket)

In `mcp_tools/server.py`, aggiungere 3 nuovi Tool entries + dispatch bucket condizionale (analog Plan 06-03 backtest bucket):

```python
ML_TOOLS = [TRAIN_ML_FILTER_TOOL, PREDICT_TRADE_QUALITY_TOOL, GET_ML_CALIBRATION_TOOL]
# in list_tools(): tools.extend(ML_TOOLS) se job_queue not None
# dispatch:
elif name in ("train_ml_filter", "predict_trade_quality", "get_ml_calibration"):
    if job_queue is None and name == "train_ml_filter":
        return error_envelope(ErrorCodes.internal_error, "JobQueue not configured")
    handler = {"train_ml_filter": handle_train_ml_filter, ...}[name]
    return handler(args, ml_filter_singleton, job_queue, cfg)
```

### predict_trade_quality input shape (MCP-05)

Riusa shape del propose_trade payload (subset rilevante per feature extraction):
```json
{
  "symbol": "EURUSD",
  "timeframe": "M15",
  "profile": "MODERATE",
  "direction": "BUY",
  "entry_price": 1.0850,
  "stop_loss": 1.0830,
  "take_profit": 1.0900,
  "context": {                             // optional extended indicators snapshot
    "rsi_14": 65.2,
    "atr_14": 0.0012,
    "regime": "normal",
    ...                                    // resto delle 33 extended cols + 5 meta
  }
}
```

Response:
```json
{
  "ok": true,
  "ml_score": 0.73,
  "calibrated_prob": 0.68,
  "threshold_for_profile": 0.62,
  "would_pass_gate": true                 // calibrated_prob >= threshold
}
```

Se `context` mancante: handler chiama `MarketDataAdapter.get_extended_indicators(symbol, tf, as_of=now)` per popolare. Se ENABLE_ML_FILTER=false: ritorna `ml_score: null, calibrated_prob: null, threshold_for_profile: null, would_pass_gate: null` con `ok: true` + warning field.

### Bundle resolution (config.ML_MODEL_PATH)

`config.py` aggiunge:
```python
ML_MODEL_PATH: Path = Path(os.getenv("ML_MODEL_PATH", "models/classifier_v1_latest.pkl"))
MCP_TRAINING_DATA_PATH: Path = Path(os.getenv("MCP_TRAINING_DATA_PATH", "data/training/baseline_decisions/part-0.parquet"))
MCP_ML_THRESHOLD_MARGIN_PCT: float = float(os.getenv("MCP_ML_THRESHOLD_MARGIN_PCT", "0.05"))
```

Symlink `models/classifier_v1_latest.pkl → classifier_v1_{date}.pkl` permette swap rolling senza riavvio MCP server (caricamento singleton avviene a bootstrap; per refresh: restart MCP).

### Wave structure suggerita (gsd-planner decide)

- **Wave 0 (Plan 08-01)**: scaffolding `mcp_tools/handlers/ml.py` skeleton + schemas + ML_TOOLS list + dispatch bucket + 3 stub handler con `xfail` test + ErrorCodes envelope verified
- **Wave 1 (Plan 08-02)**: `handle_predict_trade_quality` GREEN (MLFilter singleton wrap + feature extraction reuse + threshold lookup) + tests + `predict_trade_quality` MCP integration test
- **Wave 2 (Plan 08-03)**: `handle_get_ml_calibration` GREEN (metadata.json reader + default per-fold + summary_only opt-out) + tests
- **Wave 3 (Plan 08-04)**: `handle_train_ml_filter` GREEN (worker top-level picklable + JobQueue wire + sha256 validation + ErrorCodes envelope) + smoke round-trip integration test
- **Wave 4 (Plan 08-05)**: `evaluate_trade_proposal` extension + backward-compat verification suite (forex-trader-pro skill mock consumer)
- **Wave 5 (Plan 08-06)**: `scripts/run_ml_on_backtest.py` + `backtest/baseline/ml_on_report_writer.py` + Opt 3 degraded slices analysis + tests
- **Wave 6 (Plan 08-07) phase gate**: SC#1..4 end-to-end verification, push branch al PC secondario per ML-on re-run notturno

Plan 08-07 chiude Phase 8 plan-write. PC secondario re-run è separato STEP RESUME-PLAN (analog Plan 05-09 STEP 3 → STEP 14 nuovo).

</specifics>

<deferred>
## Deferred Ideas (NOT Phase 8 scope)

- **Schema bridge baseline+live trades merge**: future Wave/Plan dedicated quando logs/trades.db ha dati live reali da Phase 11 paper deploy + USER_CLOSE label policy + CSV immutability sha256 check + dedup re-entry policy. ~200-400 LOC. Targets Phase 9 OR Phase 11.
- **Cancel_ml_training tool**: rejected per priority dati GIUSTI. Future review se training scaling supera 30-60s (es. 10k+ rows Phase 11) e cancel diventa UX-critical.
- **Drift detection / retrain trigger**: Phase 9 scope (ML-07/08/09 + MCP-07/08).
- **suggest_position_action MCP tool**: Phase 9 scope (MCP-18 + INT-03).
- **Per-slice threshold override**: emerso da Degraded Slices Analysis output. Future Phase 11 calibration retune può adottare per-slice (symbol, tf, profile) threshold dict in metadata.json. Phase 8 produce solo SUGGESTION nel report, non implementa override path.
- **Multi-model A/B (champion/challenger)**: Phase 11+ scope, fuori v2-ml-backtest milestone.
- **Scheduled retraining (APScheduler weekly)**: Phase 9/11 scope (richiede drift trigger + non-stale data window).
- **`predict_trade_quality` batch input (lista di N propose payload)**: ottimizzazione UX skill agentic; defer fino a evidenza di hot-path usage.

</deferred>

## Claude's Discretion (downstream agents decide implementation)

- **Logging conventions**: `ml_training.log` (RotatingFileHandler 5MB × 8 backups analog ml_inference.log Plan 07-06) per training stdout. Pattern italiano coerente CLAUDE.md.
- **Test fixture per train_ml_filter handler**: riusa Plan 07-01 200-row deterministic fixture + monkeypatch `train_classifier` per smoke test (handler test NON addestra modello reale, integration test sì con `@pytest.mark.integration`).
- **Worker process error envelope**: se `train_classifier` raises, worker cattura exception e ritorna structured error in JobQueue registry; `get_ml_training_status(job_id)` espone status `failed` + error_message via DB fallback (analog Plan 06-03 backtest_runs.status + error_message column).
- **predict_trade_quality latency budget**: <50ms p95 (più lasco di Phase 7 inference 10ms p95 perché include feature extraction + MarketDataAdapter call quando `context` mancante). Test benchmark optional.
- **Schema JSON validation**: standard JSON-Schema draft-7 per tool args (analog Plan 06-04 schemas modify_position).
- **Dispatch bucket order**: ML handler bucket dopo backtest bucket in `mcp_tools/server.py` dispatch chain (preserva LIFO recent-add convention).
- **MCP tool args required vs optional**: `train_ml_filter` ha 0 required args (default tutto da config); `predict_trade_quality` ha `symbol+timeframe+profile+direction+entry_price+stop_loss+take_profit` required + `context` optional; `get_ml_calibration` ha 0 required (default per-fold) + `summary_only` optional.
- **Bundle path symlink convention**: orchestrazione del symlink `classifier_v1_latest.pkl` rimandata a Phase 8 Plan o operator manual. Train_ml_filter NON aggiorna automaticamente il symlink al bundle nuovo (decisione manuale operator).
- **Phase 8 plan format**: planner libera scelta su Wave granularity (4-7 plans accettabili) purché dependency chain rispettata e SC coverage table chiusa nel last plan.

---

*Phase: 08-mcp-tools-part-2*
*Context gathered: 2026-05-12 via /gsd-discuss-phase 8 interactive (4 aree discusse, 14 decisioni D-08-A1..D5 + Claude's Discretion areas)*
