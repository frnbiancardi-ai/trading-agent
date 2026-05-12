# Phase 8: MCP Tools (part 2) — Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 10 (4 NEW + 6 MODIFY)
**Analogs found:** 10 / 10 (5 exact in-codebase + 5 plan-specified per Phase 7 surface non ancora implementata)
**Codebase scope:** `mcp_tools/`, `backtest/baseline/`, `scripts/`, `tests/`, `config.py`
**Reference scope:** Phase 7 plan files (07-01/03/05/06) per ml/* API contract (Phase 7 NOT yet executed — questi file fungono da analog "specifica").

---

## File Classification

| File da produrre | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|------------------|---------|------|-----------|----------------|---------------|
| `mcp_tools/handlers/ml.py` | NEW | controller (MCP handler) | request-response + job-queue async | `mcp_tools/handlers/backtest.py` | **exact** (4 handler async + 1 sync identico modello a 3 ML handler + 1 worker) |
| `mcp_tools/server.py` | MODIFY | router | dispatch | `mcp_tools/server.py:285-289 + 348-375` (backtest bucket esistente) | **exact** (extension self-analog) |
| `mcp_tools/handlers/proposal.py` | MODIFY | controller (MCP handler) | request-response | `mcp_tools/handlers/proposal.py:92-102` (`handle_evaluate_trade_proposal`) — extension point già commentato | **exact** (self-extension) |
| `scripts/run_ml_on_backtest.py` | NEW | script (standalone CLI) | batch orchestrator | `scripts/run_baseline_05_09.py` | **exact** (analogo wrapper full+smoke+only-runs+wall-clock) |
| `backtest/baseline/ml_on_report_writer.py` | NEW | service (markdown writer) | transform | `backtest/baseline/report_writer.py` | **exact** (modulo puro results→MD, side-by-side delta + degraded slices = additive D-08-D4) |
| `config.py` | MODIFY | config | n/a | `config.py:100-107` (Phase 6 MCP block) | **exact** (additive env vars block analogo) |
| `.env.example` | MODIFY | config doc | n/a | `.env.example` esistente | **exact** (additive mirror) |
| `tests/test_mcp_handlers_ml.py` | NEW | test | unit + integration | `tests/test_mcp_handlers_backtest.py` | **exact** (3 ML handler analoghi 4 backtest handler) |
| `tests/test_ml_on_report_writer.py` | NEW | test | unit | `tests/test_baseline_report_writer.py` (esiste in test list — non letto in dettaglio) + `report_writer.py` shape | **role-match** (markdown writer unit) |
| `tests/test_mcp_evaluate_proposal_ml_extension.py` | NEW | test | unit (backward-compat) | `tests/test_mcp_handlers_proposal.py` | **exact** (stesso pattern Phase 6 R3 backward-compat test) |

**Analog di Phase 7 (plan-specified, NON ancora implementati in codebase):**
- `ml/inference.py::MLFilter.predict` + `MLFilter.load` → Plan 07-05 lines 218-272
- `ml/feature_extraction.py::build_feature_vector` → Plan 07-01 lines 1074-1100
- `ml/train.py::train_classifier` + `MLTrainingConfig` + `FoldResult` → Plan 07-03 lines 276-313
- `ml/artifact.py::dump_bundle/load_bundle` + `_file_sha256` → Plan 07-05 lines 278-322
- `strategy/__init__.py::evaluate_proposal_for_bar` con kwarg `ml_filter` + ProposalDraft `ml_*` fields → Plan 07-06 lines 244-308
- `risk_engine.evaluate_trade` Gate 8 ML threshold → Plan 07-06 lines 320-332

---

## Pattern Assignments

### `mcp_tools/handlers/ml.py` (NEW, controller, request-response + job-queue async)

**Analog:** `mcp_tools/handlers/backtest.py` (467 LOC, 4 handler + 2 worker top-level + 4 Tool registrations)

**1) Module docstring + header convention** (analog `backtest.py:1-21`)
```python
"""ML handlers per Phase 8 (MCP-04/05/06).

Tool inclusi:
- train_ml_filter (MCP-04) — D-08-A1 async submit, riusa JobQueue Phase 6
- predict_trade_quality (MCP-05) — D-12 wrapper read-only MLFilter.predict singleton
- get_ml_calibration (MCP-06) — D-08-C1 default per-fold, opt-out summary_only

Worker `_train_ml_filter_worker`:
- TOP-LEVEL (picklable per ProcessPoolExecutor cap=1 condiviso con backtest)
- NON importa MetaTrader5 (Phase 5 D-15 carry-forward)
- NON usa stdout (Pitfall 8 MCP JSON-RPC framing)
- Importa ml.train.train_classifier localmente (lazy import, picklability)
- Pre-validation parquet schema-v2 + sha256 (D-08-B3) PRIMA del submit
"""
```

**2) Tool registration shape** (copia `backtest.py:54-136` Tool object pattern, JSON-Schema draft-7 inline)
```python
from mcp.types import Tool

TRAIN_ML_FILTER_TOOL = Tool(
    name="train_ml_filter",
    description=(
        "Avvia training async del classificatore LightGBM su parquet baseline. "
        "Ritorna job_id immediato (non blocca); pollare get_ml_training_status "
        "(o get_backtest_metrics riuso, TBD wave-1) per status/result. "
        "Max 1 job concorrente (cap MCP_MAX_CONCURRENT_RUNS condiviso con backtest). "
        "Schema-v2 validation + sha256 check pre-training (D-08-B3)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "data_source": {"type": "string", "enum": ["baseline"], "default": "baseline"},
            # D-08-B2: enum extensible Phase 9/11 (logs/trades.db quando schema bridge maturo)
        },
        "required": [],   # D-08-A1: 0 required args (default tutto da cfg)
    },
)

PREDICT_TRADE_QUALITY_TOOL = Tool(
    name="predict_trade_quality",
    description=(
        "Wrapper read-only di MLFilter.predict(). Ritorna ml_score raw + calibrated_prob "
        "+ threshold_for_profile + would_pass_gate. NON e' un gate decisione (risk_engine "
        "rimane unico gate). Se ENABLE_ML_FILTER=false: tutti i campi null, ok:true."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol":      {"type": "string", "enum": ["EURUSD", "GBPUSD", "USDJPY"]},
            "timeframe":   {"type": "string", "enum": ["M15", "M30", "H1"]},
            "profile":     {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]},
            "direction":   {"type": "string", "enum": ["BUY", "SELL"]},
            "entry_price": {"type": "number"},
            "stop_loss":   {"type": "number"},
            "take_profit": {"type": "number"},
            "context":     {"type": "object"},   # optional; se mancante handler chiama MarketDataAdapter
        },
        "required": ["symbol", "timeframe", "profile", "direction",
                     "entry_price", "stop_loss", "take_profit"],
    },
)

GET_ML_CALIBRATION_TOOL = Tool(
    name="get_ml_calibration",
    description=(
        "Reliability data del classificatore corrente. Default: per-fold breakdown "
        "completo (10 fold, ~30-50KB) per audit-first (D-08-C1). Opt-out summary_only "
        "ritorna solo aggregate + threshold_by_profile + model_version + trained_at "
        "(~3-5KB, D-08-C2)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "summary_only": {"type": "boolean", "default": False},
        },
        "required": [],
    },
)
```

**3) Worker top-level picklable** (copia struttura `backtest.py:_backtest_worker` lines 146-223)
```python
def _train_ml_filter_worker(
    run_id: str,
    parquet_path: str,
    output_dir: str,
    ml_yaml_path: str,
    parquet_sha256: str,   # D-08-B3 audit trail nel metadata.json finale
) -> dict:
    """Worker process: training LightGBM, NO mt5.

    Lazy imports interni per picklability (Pitfall 1 carry-forward Phase 6).

    Pitfall 8: NO stdout. Logger su file via init_logger (RotatingFileHandler).
    D-08-A3: fire-and-forget, no cancel handling.
    """
    from logger import init_logger
    from config import Config
    cfg = Config()
    log = init_logger(cfg)   # ml_training.log via RotatingFileHandler (Claude's Discretion)

    from ml.train import train_classifier, load_ml_training_config

    log.info("ml worker start: run_id=%s parquet=%s", run_id, parquet_path)
    ml_cfg = load_ml_training_config(Path(ml_yaml_path))
    # Override dataset_path con quello passato (D-08-B1 baseline hardcoded)
    ml_cfg = dataclasses.replace(ml_cfg, dataset_path=parquet_path)

    fold_results = train_classifier(ml_cfg)
    # Final bundle prodotto da train_classifier in cfg.output_dir; il path
    # finale e' classifier_v1_{today}.pkl + .metadata.json (Plan 07-05 line 378).
    today = date.today().isoformat()
    bundle_path = Path(output_dir) / f"classifier_v1_{today}.pkl"

    # D-08-B3: registra parquet_sha256 nel metadata sidecar (audit trail)
    # NB: il sidecar e' gia' scritto da dump_bundle; qui solo verify presence.
    meta_path = bundle_path.with_suffix(".metadata.json")
    log.info("ml worker done: bundle=%s n_folds=%d", bundle_path, len(fold_results))
    return {
        "run_id": run_id,
        "bundle_path": str(bundle_path),
        "metadata_path": str(meta_path),
        "n_folds": len(fold_results),
        "parquet_sha256": parquet_sha256,
    }
```

**4) Handler `handle_train_ml_filter`** (copia `handle_run_backtest` lines 309-336)
```python
def handle_train_ml_filter(
    args: dict,
    job_queue,
    cfg,
) -> dict:
    """MCP-04 D-08-A1: async submit training.

    Pre-validation D-08-B3:
    1. data_source="baseline" (D-08-B2 only enum supported)
    2. parquet existence + n_cols=59 + required cols subset
    3. n_rows >= MIN_TRAINING_ROWS (1000, HANDOFF SC#3 hard gate)
    4. sha256 computed + registrato in metadata.json output (D-08-B3 audit)
    """
    data_source = args.get("data_source", "baseline")
    if data_source != "baseline":
        return envelope(
            ErrorCodes.VALIDATION_FAILED,
            f"data_source={data_source} non supportato (D-08-B2 enum: ['baseline'])",
        )
    parquet_path = Path(cfg.MCP_TRAINING_DATA_PATH)
    ok, msg, parquet_sha = _validate_parquet_schema_v2(parquet_path)
    if not ok:
        return envelope(ErrorCodes.VALIDATION_FAILED, msg)

    run_id = _build_ml_run_id()  # mcp_ml_{utc_ts}
    metadata = {"data_source": data_source, "parquet_sha256": parquet_sha}
    return job_queue.submit(
        run_id,
        _train_ml_filter_worker,
        metadata,
        run_id, str(parquet_path), str(cfg.ML_MODEL_PATH.parent),
        "data/configs/ml.yaml", parquet_sha,
    )
```

**5) Handler `handle_predict_trade_quality`** (NUOVO pattern — wrap MLFilter singleton; NO worker)
Riusa `evaluate_proposal_for_bar` analog Phase 7 Plan 07-06 lines 244-275 (try/except swallow → null fields):
```python
def handle_predict_trade_quality(
    args: dict,
    ml_filter_singleton,   # MLFilter instance or None
    mt5_client,
    cfg,
) -> dict:
    """MCP-05 D-12: wrapper read-only MLFilter.predict. NON un gate.

    Se ENABLE_ML_FILTER=false OR singleton None: ritorna {ok:true, ml_score:null,
    calibrated_prob:null, threshold_for_profile:null, would_pass_gate:null,
    warning:"ml_filter_disabled"}.
    """
    if not cfg.ENABLE_ML_FILTER or ml_filter_singleton is None:
        return {
            "ok": True,
            "ml_score": None,
            "calibrated_prob": None,
            "threshold_for_profile": None,
            "would_pass_gate": None,
            "warning": "ml_filter_disabled",
        }
    try:
        # Build minimal Draft/Indicators/Ctx mimick per build_feature_vector
        # (riuso shape Plan 07-06 lines 256-262)
        from ml.feature_extraction import build_feature_vector
        draft_like = _make_draft_from_args(args)
        ctx_like = _make_ctx_from_args(args)
        indicators_obj = _resolve_indicators(args, mt5_client, cfg)   # da args.context o MarketDataAdapter
        X = build_feature_vector(
            draft_like, indicators_obj, ctx_like,
            feature_list=ml_filter_singleton.features,
            cat_encodings=ml_filter_singleton.categorical_encodings,
        )
        raw, calibrated = ml_filter_singleton.predict(X)
        threshold = float(ml_filter_singleton.threshold_by_profile.get(
            args["profile"].upper(), 0.5,
        ))
        return {
            "ok": True,
            "ml_score": raw,
            "calibrated_prob": calibrated,
            "threshold_for_profile": threshold,
            "would_pass_gate": calibrated >= threshold,
        }
    except Exception as exc:
        return envelope(ErrorCodes.INTERNAL_ERROR, f"predict failed: {exc}")
```

**6) Handler `handle_get_ml_calibration`** (NUOVO pattern — JSON file reader)
```python
def handle_get_ml_calibration(args: dict, cfg) -> dict:
    """MCP-06 D-08-C1: per-fold breakdown default; summary_only opt-out D-08-C2."""
    meta_path = Path(cfg.ML_MODEL_PATH).with_suffix(".metadata.json")
    if not meta_path.exists():
        return envelope(
            ErrorCodes.NOT_FOUND,
            f"metadata.json mancante: {meta_path} (modello non addestrato?)",
        )
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    summary_only = bool(args.get("summary_only", False))

    common = {
        "model_version": metadata.get("version"),
        "trained_at": metadata.get("train_date"),
        "threshold_by_profile": metadata.get("threshold_by_profile", {}),
    }
    if summary_only:
        return {**common, "aggregate": metadata.get("aggregate_reliability", {})}
    # Default audit-first: per-fold full + aggregate
    return {
        **common,
        "folds": [_fold_to_payload(f) for f in metadata.get("fold_metrics", [])],
        "aggregate": metadata.get("aggregate_reliability", {}),
    }
```

**7) ErrorCodes envelope** (copia `errors.py` re-export pattern)
```python
from mcp_tools.errors import ErrorCodes, envelope
# Tutti gli error path passano da `envelope(ErrorCodes.<X>, msg, **ctx)`.
```

**8) `_validate_parquet_schema_v2` helper** (riuso pattern `run_baseline_05_09.py:49-117` + `_SCHEMA_V2_REQUIRED_KEYS` import diretto)
```python
def _validate_parquet_schema_v2(parquet_path: Path) -> tuple[bool, str, str]:
    """D-08-B3: ritorna (ok, msg, sha256_hex).

    Riuso pattern Plan 05-09 _validate_parquet_schema + computa sha256.
    Plan 05-09 lines 86-117 valida n_rows + _SCHEMA_V2_REQUIRED_KEYS + meta non-null.
    """
    import pyarrow.dataset as ds
    from backtest.baseline.dataset_writer import _SCHEMA_V2_REQUIRED_KEYS
    from backtest.baseline.determinism import file_sha256

    if not parquet_path.exists():
        return False, f"parquet mancante: {parquet_path}", ""
    try:
        dataset = ds.dataset(str(parquet_path), format="parquet")
    except Exception as exc:
        return False, f"pyarrow load fallito: {exc}", ""
    n_rows = dataset.count_rows()
    if n_rows < 1000:   # MIN_TRAINING_ROWS (HANDOFF SC#3 hard gate)
        return False, f"n_rows {n_rows} < MIN_TRAINING_ROWS 1000", ""
    schema_names = set(dataset.schema.names)
    missing = _SCHEMA_V2_REQUIRED_KEYS - schema_names
    if missing:
        return False, f"missing cols schema-v2: {sorted(missing)[:10]}...", ""
    # D-08-B3 audit: sha256 del file fisico
    sha = file_sha256(parquet_path)
    return True, f"OK schema-v2: {n_rows} rows, sha256={sha[:12]}...", sha
```

---

### `mcp_tools/server.py` (MODIFY, router, dispatch)

**Analog (self-extension):** `server.py:53-62 + 285-289 + 348-375` (backtest bucket pattern)

**Extension point 1 — Import block (after line 62, append)**
```python
from mcp_tools.handlers.ml import (
    TRAIN_ML_FILTER_TOOL,
    PREDICT_TRADE_QUALITY_TOOL,
    GET_ML_CALIBRATION_TOOL,
    handle_train_ml_filter,
    handle_predict_trade_quality,
    handle_get_ml_calibration,
)
```

**Extension point 2 — list_tools() append (after line 292, before `]`)**
```python
        # Phase 8 — ML control plane (MCP-04/05/06)
        TRAIN_ML_FILTER_TOOL,
        PREDICT_TRADE_QUALITY_TOOL,
        GET_ML_CALIBRATION_TOOL,
```

**Extension point 3 — Dispatch bucket (after line 375, before `return _text({"error": ...})`)**
Pattern copia `server.py:349-375` (backtest bucket condizionale):
```python
        # Phase 8 — ML control plane (MCP-04/05/06)
        if name in ("train_ml_filter", "predict_trade_quality", "get_ml_calibration"):
            if name == "train_ml_filter" and job_queue is None:
                return _text(envelope(
                    "internal_error",
                    "JobQueue non inizializzata: _bootstrap_state() prima",
                    tool=name,
                ))
            if name == "train_ml_filter":
                return _text(handle_train_ml_filter(arguments, job_queue, cfg))
            if name == "predict_trade_quality":
                return _text(handle_predict_trade_quality(
                    arguments, ml_filter_singleton, mt5, cfg,
                ))
            # get_ml_calibration
            return _text(handle_get_ml_calibration(arguments, cfg))
```

**Extension point 4 — Bootstrap MLFilter singleton** (analog `_bootstrap_state` lines 101-128, add after JobQueue init)
```python
ml_filter_singleton: "Any | None" = None  # MLFilter or None

def _bootstrap_state() -> None:
    # ... existing JobQueue init ...
    global ml_filter_singleton
    if cfg.ENABLE_ML_FILTER and Path(cfg.ML_MODEL_PATH).exists():
        try:
            from ml.inference import MLFilter
            ml_filter_singleton = MLFilter.load(cfg.ML_MODEL_PATH)
            log.info("MLFilter singleton caricato: %s", cfg.ML_MODEL_PATH)
        except Exception as exc:
            log.error("MLFilter load fallita (graceful): %s", exc)
            ml_filter_singleton = None
```

---

### `mcp_tools/handlers/proposal.py` (MODIFY ~30 LOC, controller, request-response)

**Extension point:** `proposal.py:92-102` (`handle_evaluate_trade_proposal`)

**Current code (verbatim)**
```python
def handle_evaluate_trade_proposal(args: dict, mt5_client, cfg) -> dict:
    """Wave 1: invariato vs legacy. Phase 7/8 aggiungera' ml_score/calibrated_prob.

    Spostato verbatim da mcp_server.py dispatch (evaluate_trade_proposal branch).
    """
    from risk_engine import evaluate_trade

    proposal = _build_proposal_from_args(args, cfg)
    account = mt5_client.get_account_state()
    decision = evaluate_trade(proposal, account, mt5_client, cfg)
    return dataclasses.asdict(decision)
```

**Phase 8 extension (additive, backward-compat per `<specifics>` lines 188-202)**
```python
def handle_evaluate_trade_proposal(
    args: dict, mt5_client, cfg,
    ml_filter_singleton=None,   # additive kwarg Phase 8
) -> dict:
    """Phase 8 D-08-D + MCP-R4: extension additive ml_score + calibrated_prob.

    Backward-compat:
    - ENABLE_ML_FILTER=false OR ml_filter_singleton=None ⇒ ml_* tutti null,
      ml_filter_active=false, NO error envelope (graceful).
    - Resto del payload (approved, reason, risk_decision, ...) invariato.
    """
    from risk_engine import evaluate_trade

    proposal = _build_proposal_from_args(args, cfg)
    account = mt5_client.get_account_state()
    decision = evaluate_trade(proposal, account, mt5_client, cfg)
    base = dataclasses.asdict(decision)

    # Phase 8 additive (Pattern Plan 07-06 lines 254-272: try/except swallow)
    ml_score = None
    calibrated_prob = None
    ml_threshold = None
    ml_filter_active = False
    if cfg.ENABLE_ML_FILTER and ml_filter_singleton is not None:
        ml_filter_active = True
        try:
            from ml.feature_extraction import build_feature_vector
            # Riuso pattern Plan 07-06 lines 256-268
            X = build_feature_vector(
                proposal, _resolve_indicators(args, mt5_client, cfg),
                _make_ctx_from_args(args, cfg),
                feature_list=ml_filter_singleton.features,
                cat_encodings=ml_filter_singleton.categorical_encodings,
            )
            ml_score, calibrated_prob = ml_filter_singleton.predict(X)
            ml_threshold = float(
                ml_filter_singleton.threshold_by_profile.get(
                    cfg.RISK_MODE.upper(), 0.5,
                )
            )
        except Exception:
            # Pattern Plan 07-06 line 269-272: swallow, ml_* restano None
            pass

    base.update({
        "ml_score": ml_score,
        "calibrated_prob": calibrated_prob,
        "ml_threshold": ml_threshold,
        "ml_filter_active": ml_filter_active,
    })
    return base
```

**NB dispatch site update:** `server.py:307-308` deve passare il nuovo kwarg:
```python
        if name == "evaluate_trade_proposal":
            return _text(_proposal_evaluate(arguments, mt5, cfg, ml_filter_singleton))
```

---

### `scripts/run_ml_on_backtest.py` (NEW, script, batch orchestrator)

**Analog:** `scripts/run_baseline_05_09.py` (344 LOC, full + smoke + only-runs + max-wall-clock + no-time-gate + schema validation)

**1) Shebang + module docstring + argparse pattern** (copia `run_baseline_05_09.py:1-46`)
```python
r"""Plan 08-06 ML-on backtest wrapper — INT-02 deliverable.

Eseguibile stand-alone sul PC secondario (no dipendenza da Claude Code).
Riusa backtest.baseline.runner.run_baseline come backend con override
ENABLE_ML_FILTER=true + ML_MODEL_PATH=models/classifier_v1_latest.pkl.

Output:
- data/training/baseline_ml_on/part-0.parquet (separato da baseline_decisions/ — D-08-D1)
- .planning/research/ml-on-{date}.md (report Opt 3 — D-08-D4)

Uso:
    # Smoke (1 slice mini-range ~30-60s):
    python scripts/run_ml_on_backtest.py --smoke

    # Full 27/27 (PC secondario notturno):
    python scripts/run_ml_on_backtest.py --force

    # Recovery dopo crash parziale:
    python scripts/run_ml_on_backtest.py --only-runs <id1>,<id2>

Exit code:
    0 = OK (full o smoke completati, schema validato)
    1 = errore generico
    2 = wall-clock superato (--max-wall-clock gate) o smoke CSV mancante
    3 = schema-validation KO (post-run)
    4 = SC#4 verdict NEGATIVE (< 4/5 criteria pass — non un fail, documented)
"""
from __future__ import annotations
import argparse, logging, sys, time as _time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_log = logging.getLogger("run_ml_on_backtest")
```

**2) Bundle sha256 validation pre-run** (analog `_validate_parquet_schema` + helper Plan 07-05 `_file_sha256`)
```python
def _validate_bundle_pre_run(bundle_path: Path) -> tuple[bool, str, dict]:
    """D-08-D3 pre-flight: bundle existence + sha256 + metadata.json parseable.

    Ritorna (ok, msg, meta_dict). Confronta sha256 con metadata['bundle_sha256']
    se presente (audit trail). Smoke test MLFilter.load + 10-sample predict
    su tests/fixtures/baseline_decisions_smoke.parquet (D-08-D2 coordinamento).
    """
    if not bundle_path.exists():
        return False, f"bundle mancante: {bundle_path}", {}
    from backtest.baseline.determinism import file_sha256
    bundle_sha = file_sha256(bundle_path)
    meta_path = bundle_path.with_suffix(".metadata.json")
    if not meta_path.exists():
        return False, f"metadata.json mancante: {meta_path}", {}
    import json
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return True, f"OK bundle: sha256={bundle_sha[:12]}...", {**meta, "bundle_sha256": bundle_sha}
```

**3) `_run_smoke` + `_run_full` + `_only_runs_pre_delete`** (copia 3 funzioni `run_baseline_05_09.py:120-303`)
- Riusa `slice_worker._force_clear_run` per `--only-runs` (lines 213-239 analog FIX A iter 3)
- Override env var `ENABLE_ML_FILTER=true` PRIMA di chiamare `run_baseline()`
- Output dir override → `data/training/baseline_ml_on/` (D-08-D1 separato da `baseline_decisions/`)

**4) Report writer invocation post-run**
```python
def _run_full(args, ROOT_PATH: Path) -> int:
    # ... copia pattern run_baseline_05_09.py:242-303 fino a results = run_baseline(force=args.force)
    # Override D-08-D1: training_data_dir → baseline_ml_on
    # Post-pool: chiama ml_on_report_writer invece di report_writer
    from backtest.baseline.ml_on_report_writer import write_ml_on_report
    from backtest.baseline.determinism import file_sha256
    meta = {
        "bundle_sha256": file_sha256(Path(cfg.ML_MODEL_PATH)),
        "threshold_by_profile": _load_thresholds_from_metadata(),
        "wall_clock_seconds": wall,
        "run_id": f"ml_on_{date.today().isoformat()}",
        "baseline_report_path": ".planning/research/baseline-2026-05-12.md",
    }
    report_path = Path(".planning/research") / f"ml-on-{date.today().isoformat()}.md"
    verdict = write_ml_on_report(results, baseline_results, report_path, meta)
    # D-08-D5: parse verdict per exit code
    return 0 if verdict["status"] == "NON_TRIVIAL_IMPROVEMENT" else 4
```

**5) argparse flag list** (copia `run_baseline_05_09.py:311-334`)
```python
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke 1 slice mini-range (~30-60s) per validation.")
    parser.add_argument("--force", action="store_true",
                        help="Re-run anche se run_id esiste (overwrite parquet + ledger).")
    parser.add_argument("--only-runs", default="",
                        help="Comma-separated whitelist (riuso _force_clear_run).")
    parser.add_argument("--max-wall-clock", type=int, default=14400,
                        help="Soft warning su wall-clock (default 14400s = 4h).")
    parser.add_argument("--no-time-gate", action="store_true",
                        help="Disabilita time-gate (debug).")
```

---

### `backtest/baseline/ml_on_report_writer.py` (NEW ~250 LOC, service, transform)

**Analog:** `backtest/baseline/report_writer.py` (176 LOC, module puro results→MD UTF-8, 5 sezioni Header/Table/Per-slice/Appendix)

**1) Module docstring + import block** (copia `report_writer.py:1-23`)
```python
"""ML-on backtest report writer (Phase 8 D-08-D4, INT-02).

Schema D-08-D4 (Opt 3 side-by-side + degraded slices):
  1. Header (bundle sha256, threshold per profile, wall-clock, run_id, baseline link)
  2. Aggregate Verdict (5 SC#4 criteria, automated assert — D-08-D5)
  3. Per-slice breakdown 27 rows (base vs ml side-by-side)
  4. Rejection rate per profile
  5. Degraded Slices Analysis automatica (per slice ml<base)
  6. Verdict block macchina-leggibile (parsed da gsd-verifier)

Output: file singolo `.planning/research/ml-on-{date}.md`. UTF-8 encoding.

Module puro: results + baseline_results + meta → file MD. Mock-friendly.
Riuso pattern report_writer.py per _TABLE_HEADER + _row + _per_slice_section.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)
```

**2) Side-by-side table header** (analog `report_writer.py:27-31`, esteso con `ml_*` colonne)
```python
_SIDE_BY_SIDE_HEADER = (
    "| symbol | tf | profile | base_n | ml_n | base_sharpe | ml_sharpe | "
    "base_hit | ml_hit | base_pf | ml_pf | rejection_rate |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|"
)
```

**3) `_row` formatter** (analog `report_writer.py:34-60` con dual-mode dict/dataclass access)
Pattern identico: `_g(obj, key, default)` helper per `dict.get` OR `getattr`.

**4) Verdict block (D-08-D5)** — NUOVO pattern, macchina-leggibile:
```python
def _compute_verdict(aggregate: dict) -> dict:
    """5 SC#4 criteria automated (D-08-D5).

    Criteria:
    - sharpe_delta >= +0.50
    - hit_rate_delta >= +0.05
    - trade_retention >= 30% (ml_n / base_n aggregato)
    - expectancy sign flip + delta >= +5
    - max_dd_delta <= -100 (less negative drawdown)
    """
    passes = 0
    criteria_results = {}
    if aggregate["sharpe_delta"] >= 0.50:
        passes += 1; criteria_results["sharpe_delta"] = "PASS"
    else:
        criteria_results["sharpe_delta"] = "FAIL"
    # ... ripeti per altri 4 criteri ...
    status = "NON_TRIVIAL_IMPROVEMENT" if passes >= 4 else "NEGATIVE_RESULT_DOCUMENTED"
    return {"status": status, "passes": passes, "total": 5, "criteria": criteria_results}
```

**5) Degraded Slices Analysis (D-08-D4 part 5)** — NUOVO pattern:
```python
def _degraded_slices_section(results: list[dict], baseline_results: list[dict],
                              threshold_margin_pct: float) -> str:
    """Per ogni slice con ml_sharpe < base_sharpe:
    - lista rejected trade marginali (calibrated_prob entro ±margin% threshold)
    - suggested threshold tuning per quella slice
    - recommendation Phase 9 calibration retune

    threshold_margin_pct: da cfg.MCP_ML_THRESHOLD_MARGIN_PCT (default 0.05).
    """
    lines = ["## Degraded Slices Analysis\n"]
    by_key = {(r["symbol"], r["timeframe"], r["profile"]): r for r in baseline_results}
    for r in results:
        key = (r["symbol"], r["timeframe"], r["profile"])
        base = by_key.get(key)
        if base is None or r.get("sharpe", 0) >= base.get("sharpe", 0):
            continue
        # Degraded: lista rejected marginali, suggest threshold
        # ...
    return "\n".join(lines)
```

**6) `write_ml_on_report(results, baseline_results, out_path, meta) → verdict_dict`** signature (analog `report_writer.write_baseline_report` lines 80-176, ritorna verdict per exit code parsing)

---

### `config.py` (MODIFY ~10 LOC, additive env vars)

**Extension point:** `config.py:100-107` (Phase 6 MCP block)

**Current block (verbatim)**
```python
    # Phase 6 MCP (D-C1, D-D1, D-A4)
    MCP_DEFAULT_BARS: int = int(os.getenv("MCP_DEFAULT_BARS", "200"))
    # D-A4 cap=1: massimo backtest concorrenti gestiti dal JobQueue (Wave 2).
    MCP_MAX_CONCURRENT_RUNS: int = int(os.getenv("MCP_MAX_CONCURRENT_RUNS", "1"))
```

**Phase 8 extension (after MCP_MAX_CONCURRENT_RUNS, analog block)**
```python
    # Phase 8 MCP ML (D-08-A1/B1/D3)
    # ML_MODEL_PATH: bundle joblib (Phase 7 Plan 07-05 D-15 path convention).
    # Symlink classifier_v1_latest.pkl → classifier_v1_{date}.pkl per swap rolling
    # senza restart MCP server (caricamento singleton a bootstrap).
    ML_MODEL_PATH: Path = Path(os.getenv("ML_MODEL_PATH", "models/classifier_v1_latest.pkl"))
    # MCP_TRAINING_DATA_PATH: parquet baseline (D-08-B1 hardcoded data source).
    MCP_TRAINING_DATA_PATH: Path = Path(os.getenv(
        "MCP_TRAINING_DATA_PATH", "data/training/baseline_decisions/part-0.parquet",
    ))
    # MCP_ML_THRESHOLD_MARGIN_PCT: margine entro cui un trade rejected dal ML
    # gate e' considerato "marginale" nella Degraded Slices Analysis (D-08-D4).
    MCP_ML_THRESHOLD_MARGIN_PCT: float = float(os.getenv(
        "MCP_ML_THRESHOLD_MARGIN_PCT", "0.05",
    ))
```

NB import `from pathlib import Path` (config.py line non lo ha attualmente — già necessario). Verificare con planner.

---

### `.env.example` (MODIFY, mirror env vars)

**Extension point:** trovare blocco `# Phase 6 MCP` o equivalente, aggiungere dopo:
```bash
# Phase 8 MCP ML (D-08-A1/B1/D3)
# ML_MODEL_PATH=models/classifier_v1_latest.pkl
# MCP_TRAINING_DATA_PATH=data/training/baseline_decisions/part-0.parquet
# MCP_ML_THRESHOLD_MARGIN_PCT=0.05
```

NB: ENABLE_ML_FILTER + ML_THRESHOLD_BY_PROFILE già documentati in Phase 7 .env.example (Plan 07-06 line 125).

---

### `tests/test_mcp_handlers_ml.py` (NEW ~300 LOC, unit + integration)

**Analog:** `tests/test_mcp_handlers_backtest.py` (219 LOC, 9 test functions su 4 handler + fixture `db_and_queue`)

**1) Module docstring + import + pytest.importorskip pattern** (copia lines 1-26)
```python
"""Phase 8: ML handler tests (MCP-04/05/06).

Riferimento: 08-04/05/06-PLAN.md Task 2.

train_ml_filter integration test: @pytest.mark.integration (slow ~30-60s).
"""
from __future__ import annotations
import sqlite3, time
from unittest.mock import MagicMock
import pytest

pytest.importorskip("mcp_tools.handlers.ml")
from mcp_tools.handlers.ml import (  # noqa: E402
    handle_train_ml_filter,
    handle_predict_trade_quality,
    handle_get_ml_calibration,
)
from mcp_tools.job_queue import JobQueue  # noqa: E402
```

**2) `_fast_worker` stub TOP-LEVEL picklable** (analog lines 30-44 `_fast_worker` + `_slow_worker`)
```python
def _fast_ml_worker(run_id, *args, **kwargs):
    """Stub TOP-LEVEL: scrive fake bundle + metadata.json minimo."""
    output_dir = args[1]   # cfg.ML_MODEL_PATH.parent
    bundle_path = Path(output_dir) / "classifier_v1_test.pkl"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_bytes(b"stub-bundle")
    meta_path = bundle_path.with_suffix(".metadata.json")
    meta_path.write_text('{"version":"v1","fold_metrics":[],"threshold_by_profile":{}}')
    return {"run_id": run_id, "bundle_path": str(bundle_path), "n_folds": 0,
            "parquet_sha256": args[3]}
```

**3) Fixture `db_and_queue`** (copia verbatim lines 56-66, sostituendo `_backtest_worker` → `_train_ml_filter_worker`)

**4) Test pattern** — replicare 5 test set:
| Test analog (backtest.py) | Test ML (ml.py) | Pattern |
|---------------------------|-----------------|---------|
| `test_run_backtest_returns_run_id` (line 71) | `test_train_ml_filter_returns_job_id` | submit happy path + run_id prefix check |
| `test_run_backtest_concurrency_cap` (line 91) | `test_train_ml_filter_concurrency_cap` | D-A4 cap=1 + run_in_progress envelope |
| `test_get_metrics_polymorphic` (line 110) | `test_get_ml_calibration_default_per_fold` | summary_only=false → per-fold breakdown |
| `test_get_metrics_unknown` (line 131) | `test_get_ml_calibration_metadata_missing` | not_found envelope |
| (nuovo) | `test_predict_trade_quality_disabled` | ENABLE_ML_FILTER=false → null fields + ok:true + warning |
| (nuovo) | `test_predict_trade_quality_enabled_pass_gate` | MagicMock singleton + calibrated_prob >= threshold |
| (nuovo) | `test_validate_parquet_schema_v2_strict_fail` | parquet missing → validation_failed |

---

### `tests/test_ml_on_report_writer.py` (NEW ~150 LOC, unit)

**Analog:** `tests/test_baseline_report_writer.py` (esiste nella lista test dir, role-match analog — write_baseline_report happy path + degraded handling)

Pattern: in-memory `results` + `baseline_results` mock, scrive in `tmp_path`, asserisce:
- Header contains bundle sha256, threshold dict, wall-clock
- Side-by-side table 27 rows present
- Verdict block presente + `status` valido enum
- Degraded Slices Analysis section presente quando `ml_sharpe < base_sharpe`
- D-08-D5 parse: `_compute_verdict` ritorna dict con `passes`, `status`, `criteria`

---

### `tests/test_mcp_evaluate_proposal_ml_extension.py` (NEW ~100 LOC, backward-compat)

**Analog:** `tests/test_mcp_handlers_proposal.py` (69 LOC, MagicMock cfg + log, fixture-based test)

**1) Fixture pattern** (copia lines 19-30)
```python
@pytest.fixture
def mock_cfg():
    c = MagicMock()
    c.TIMEFRAME = "M15"
    c.EXECUTION_MODE = "shadow"
    c.RISK_MODE = "MODERATE"
    return c

@pytest.fixture
def mock_mt5():
    m = MagicMock()
    m.get_account_state.return_value = {...}
    return m
```

**2) Test scenarios** (4 test minimum):
| Test name | Scenario | Assert |
|-----------|----------|--------|
| `test_evaluate_proposal_ml_disabled_returns_null_fields` | `cfg.ENABLE_ML_FILTER=False` | `ml_score is None and ml_filter_active is False` |
| `test_evaluate_proposal_ml_singleton_none_returns_null` | `cfg.ENABLE_ML_FILTER=True`, `singleton=None` | `ml_filter_active is False`, no error |
| `test_evaluate_proposal_ml_active_attaches_score` | `cfg.ENABLE_ML_FILTER=True`, mock singleton ritorna `(0.73, 0.68)` | `ml_score==0.73`, `calibrated_prob==0.68`, `ml_threshold` valorizzato |
| `test_evaluate_proposal_ml_exception_swallow_legacy_payload` | singleton.predict raises | response include `approved`/`reason` legacy + `ml_score is None` (graceful) |

Riusa pattern `handle_propose_trade` fixture (mock_log, mock_cfg), aggiunge `mock_mt5` + `mock_ml_filter` MagicMock.

---

## Shared Patterns

### Pattern A: Worker top-level picklable (NO mt5, NO stdout)

**Source:** `mcp_tools/handlers/backtest.py:146-223` (`_backtest_worker`)
**Apply to:** `mcp_tools/handlers/ml.py::_train_ml_filter_worker`

```python
# CRITICAL pattern (Pitfall 1 + Pitfall 8 carry-forward Phase 6):
def _train_ml_filter_worker(run_id: str, ...) -> dict:
    """TOP-LEVEL function (picklable per ProcessPoolExecutor).
    NON importa MetaTrader5 (Phase 5 D-15: lib non fork-safe).
    NON usa stdout (corromperebbe MCP JSON-RPC framing).
    Lazy imports interni (Pitfall 1 + perf module-load).
    """
    from logger import init_logger   # local import
    from config import Config
    cfg = Config()
    log = init_logger(cfg)   # RotatingFileHandler file-only — safe
    from ml.train import train_classifier   # lazy ml import
    # ...
```

### Pattern B: Tool registration JSON-Schema inline

**Source:** `mcp_tools/handlers/backtest.py:54-136` (4 `Tool(name=..., inputSchema={...})`)
**Apply to:** `mcp_tools/handlers/ml.py` 3 Tool entries

```python
from mcp.types import Tool

TRAIN_ML_FILTER_TOOL = Tool(
    name="train_ml_filter",
    description="...",
    inputSchema={
        "type": "object",
        "properties": {...},
        "required": [...],
    },
)
```

### Pattern C: ErrorCodes envelope

**Source:** `mcp_tools/errors.py:1-11` (re-export from `mcp.errors`)
**Apply to:** All ML handler error paths

```python
from mcp_tools.errors import ErrorCodes, envelope

# Pattern: ogni return-on-error
return envelope(ErrorCodes.VALIDATION_FAILED, f"detail: {x}", **ctx)
return envelope(ErrorCodes.NOT_FOUND, "metadata.json missing")
return envelope(ErrorCodes.INTERNAL_ERROR, str(exc))
```

### Pattern D: JobQueue submit (analog `handle_run_backtest`)

**Source:** `mcp_tools/job_queue.py:76-121` + `backtest.py:309-336`
**Apply to:** `handle_train_ml_filter`

```python
return job_queue.submit(
    run_id,            # mcp_ml_{utc_ts}
    _train_ml_filter_worker,
    metadata,          # {"data_source": ..., "parquet_sha256": ...}
    *worker_args,
)
# Ritorna: {"ok": True, "run_id", "status": "started", "started_at"}
# OR: {"ok": False, "error": "run_in_progress", "active_run_id"}
```

### Pattern E: Pre-validation parquet schema-v2 + sha256

**Source:** `scripts/run_baseline_05_09.py:49-117` (`_validate_parquet_schema`) + `backtest/baseline/determinism.py::file_sha256`
**Apply to:**
- `mcp_tools/handlers/ml.py::_validate_parquet_schema_v2` (D-08-B3 strict-fail)
- `scripts/run_ml_on_backtest.py::_validate_bundle_pre_run` (analog, ma su bundle .pkl invece di parquet)

```python
from backtest.baseline.dataset_writer import _SCHEMA_V2_REQUIRED_KEYS
from backtest.baseline.determinism import file_sha256
import pyarrow.dataset as ds

dataset = ds.dataset(str(parquet_path), format="parquet")
missing = _SCHEMA_V2_REQUIRED_KEYS - set(dataset.schema.names)
if missing or dataset.count_rows() < MIN_ROWS:
    return False, msg, ""
sha = file_sha256(parquet_path)
```

### Pattern F: MLFilter singleton thread-safe (Plan 07-05 lines 209-215)

**Source:** Phase 7 Plan 07-05 lines 209-215 (`get_ml_filter` double-check lock)
**Apply to:** `mcp_tools/server.py::_bootstrap_state` + `handle_predict_trade_quality`/`handle_evaluate_trade_proposal` dispatch

```python
# Bootstrap once at server start; never refresh mid-run (symlink swap requires restart)
ml_filter_singleton = None
if cfg.ENABLE_ML_FILTER and Path(cfg.ML_MODEL_PATH).exists():
    try:
        from ml.inference import MLFilter
        ml_filter_singleton = MLFilter.load(cfg.ML_MODEL_PATH)
    except Exception as exc:
        log.error("MLFilter load fallita (graceful): %s", exc)
```

### Pattern G: try/except swallow → null fields (Plan 07-06 lines 254-272)

**Source:** Plan 07-06 `evaluate_proposal_for_bar` extension
**Apply to:** `handle_evaluate_trade_proposal` ML extension + `handle_predict_trade_quality`

```python
ml_score = None; calibrated_prob = None; ml_threshold = None
if cfg.ENABLE_ML_FILTER and singleton is not None:
    try:
        X = build_feature_vector(...)
        ml_score, calibrated_prob = singleton.predict(X)
        ml_threshold = singleton.threshold_by_profile.get(...)
    except Exception:
        pass   # ml_* restano None; payload graceful
```

### Pattern H: `_force_clear_run` riuso per `--only-runs`

**Source:** `backtest/baseline/slice_worker.py:137-152` (DELETE backtest_trades + backtest_runs single connection busy_timeout=30s)
**Apply to:** `scripts/run_ml_on_backtest.py::_only_runs_pre_delete` (via wrapper analog `run_baseline_05_09.py:213-239`)

```python
from backtest.baseline.slice_worker import _force_clear_run

for rid in run_ids:
    _force_clear_run(ledger_db, rid)   # single source of truth con --force
```

### Pattern I: Markdown report writer puro (lines→file UTF-8)

**Source:** `backtest/baseline/report_writer.py:80-176` (`write_baseline_report`)
**Apply to:** `backtest/baseline/ml_on_report_writer.py::write_ml_on_report`

```python
def write_ml_on_report(results, baseline_results, out_path: Path, meta: dict) -> dict:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("## Header\n")
    # ...
    out_path.write_text("\n".join(lines), encoding="utf-8")
    _log.info("ML-on report scritto: %s (%d byte)", out_path, out_path.stat().st_size)
    return verdict   # NEW: ritorna verdict dict per exit code parsing
```

### Pattern J: Test fixture pytest.importorskip + MagicMock cfg/log

**Source:** `tests/test_mcp_handlers_backtest.py:18` + `tests/test_mcp_handlers_proposal.py:19-30`
**Apply to:** All 3 new test files

```python
pytest.importorskip("mcp_tools.handlers.ml")   # gate fino a GREEN
from mcp_tools.handlers.ml import ...

@pytest.fixture
def mock_cfg():
    c = MagicMock()
    c.ENABLE_ML_FILTER = False
    c.ML_MODEL_PATH = "models/classifier_v1_latest.pkl"
    return c
```

### Pattern K: Italiano log/comment/rationale (CLAUDE.md)

**Source:** Tutti i file MCP esistenti (`backtest.py`, `proposal.py`, `job_queue.py`)
**Apply to:** Tutti i NEW handler + script + report writer

```python
# ─── Pattern italiano (CLAUDE.md convention) ─────────────────
# - docstring tecnici/funzionali in italiano
# - log.info/log.warning in italiano
# - nomi tecnici/file paths/code identifier in inglese
log.info("ml worker start: run_id=%s parquet=%s", run_id, parquet_path)
log.error("MLFilter load fallita (graceful): %s", exc)
```

---

## No Analog Found

Nessun file Phase 8 senza analog. Tutti i 10 file hanno match esatto o role-match in codebase + Phase 7 plan specs:

| File | Analog primario | Note |
|------|-----------------|------|
| `mcp_tools/handlers/ml.py` | `backtest.py` (exact) + Plan 07-05/03 per ml.* surface | OK |
| `mcp_tools/server.py` (mod) | self (lines 285-289, 348-375) | OK |
| `mcp_tools/handlers/proposal.py` (mod) | self (lines 92-102) + Plan 07-06 lines 244-275 | OK |
| `scripts/run_ml_on_backtest.py` | `run_baseline_05_09.py` (exact) | OK |
| `backtest/baseline/ml_on_report_writer.py` | `report_writer.py` (exact, Verdict + Degraded NEW patterns documented) | OK |
| `config.py` (mod) | self (Phase 6 MCP block) | OK |
| `.env.example` (mod) | self | OK |
| `tests/test_mcp_handlers_ml.py` | `test_mcp_handlers_backtest.py` (exact, 5 test analoghi + 2 nuovi) | OK |
| `tests/test_ml_on_report_writer.py` | `test_baseline_report_writer.py` (role-match, NON letto in dettaglio — planner verifichi) | OK |
| `tests/test_mcp_evaluate_proposal_ml_extension.py` | `test_mcp_handlers_proposal.py` (exact, R3 backward-compat pattern) | OK |

---

## Cross-cutting note: Phase 7 dependency surface

I 6 file `ml/*` + `models/classifier_v1_*` + `risk_engine` Gate 8 + `ProposalDraft.ml_*` **non esistono ancora nel codebase** alla data di questo mapping (2026-05-12). Sono specificati nei Plan Phase 7 ma non implementati (Phase 7 plans completati 2026-05-11; execute pendente — vedi `.planning/STATE.md`).

Implicazione per planner Phase 8:
- **Wave dependency:** Phase 8 Wave 1 (`handle_predict_trade_quality`) NON può andare GREEN finché Phase 7 Wave 4 (`ml/inference.py`) non è completato. Plan 08-02 deve `pytest.importorskip("ml.inference")` fino a quel momento.
- **Test fixture:** `tests/fixtures/baseline_decisions_smoke.parquet` (Plan 07-01 200-row deterministic) idem — esiste post-Phase-7 only.
- **bundle path mock:** I test Phase 8 che validano `handle_get_ml_calibration` necessitano fixture `metadata.json` minimo (in `tests/fixtures/ml/classifier_v1_test.metadata.json` o creato in-memory tramite `tmp_path` come in `_fast_ml_worker` stub).

API contract da Phase 7 plan files (lock per Plan 08):
- `MLFilter.predict(X: pd.DataFrame) → tuple[float, float]` (raw, calibrated, entrambi [0,1]) — Plan 07-05 line 240
- `MLFilter.load(path) → MLFilter` raises `FeatureSchemaMismatchError` — Plan 07-05 line 232
- `MLFilter.features`, `.categorical_encodings`, `.threshold_by_profile`, `.version` — Plan 07-05 lines 224-228
- `build_feature_vector(draft, indicators, ctx, feature_list, cat_encodings) → pd.DataFrame` (1 riga) — Plan 07-01 line 1074
- `train_classifier(cfg: MLTrainingConfig) → list[FoldResult]` — Plan 07-03 + 07-05 line 350
- metadata.json schema 12+ keys (`version`, `train_date`, `git_sha`, `dataset_hash`, `n_features`, `features`, `categorical_features`, `categorical_encodings`, `fold_metrics`, `threshold_by_profile`, `calibrator_winner_aggregate`, `lightgbm_version`, `sklearn_version`) — Plan 07-05 lines 401-419

---

## Metadata

**Analog search scope:** `mcp_tools/`, `backtest/baseline/`, `scripts/`, `tests/`, `config.py`, `.planning/phases/07-ml-classifier/`
**Files scanned (full Read):** 9 (backtest.py, proposal.py, server.py, job_queue.py, errors.py, run_baseline_05_09.py, runner.py, report_writer.py, slice_worker.py partial, test_mcp_handlers_backtest.py, test_mcp_handlers_proposal.py, config.py)
**Files scanned (partial via grep + selective Read):** 4 Phase 7 plan files (07-01, 07-03, 07-05, 07-06)
**Pattern extraction date:** 2026-05-12
**Mapper compliance:** No source code modified; only PATTERNS.md written.
