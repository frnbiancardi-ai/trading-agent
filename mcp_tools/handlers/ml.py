"""ML handlers per Phase 8 (MCP-04/05/06).

Tool inclusi:
- train_ml_filter (MCP-04) — D-08-A1 async submit via JobQueue Phase 6
  (cap=1 condiviso MCP_MAX_CONCURRENT_RUNS — D-08-A2).
- predict_trade_quality (MCP-05) — D-12 wrapper read-only MLFilter.predict
  (NON un gate; risk_engine resta unico gate decisione CLAUDE.md).
- get_ml_calibration (MCP-06) — D-08-C1 default per-fold breakdown;
  D-08-C2 opt-out summary_only.

Worker `_train_ml_filter_worker`:
- TOP-LEVEL (picklable per ProcessPoolExecutor cap=1 condiviso con backtest).
- NON importa MetaTrader5 (Phase 5 D-15 carry-forward).
- NON usa stdout (Pitfall 8 MCP JSON-RPC framing).
- Lazy imports interni di ml.train.train_classifier (picklability).
- Pre-validation parquet schema-v2 + sha256 (D-08-B3) PRIMA del submit.

Wave 0 (Plan 08-01): scaffolding stub NotImplementedError + Tool schemas.
Wave 1 (Plan 08-02): handle_predict_trade_quality GREEN.
Wave 2 (Plan 08-03): handle_get_ml_calibration GREEN.
Wave 3 (Plan 08-04): handle_train_ml_filter GREEN + _train_ml_filter_worker.
"""
from __future__ import annotations

from typing import Any

from mcp.types import Tool

from mcp_tools.errors import ErrorCodes, envelope  # noqa: F401

# ─── Tool schemas (D-08-A1/A2/B2/C1/C2) ─────────────────────────────────

TRAIN_ML_FILTER_TOOL = Tool(
    name="train_ml_filter",
    description=(
        "Avvia training async del classificatore LightGBM su parquet baseline. "
        "Ritorna job_id immediato (non blocca); pollare get_backtest_metrics(run_id) "
        "per status/result. Max 1 job concorrente (cap MCP_MAX_CONCURRENT_RUNS "
        "condiviso con backtest). Schema-v2 validation + sha256 check pre-training "
        "(D-08-B3 strict-fail)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "data_source": {
                "type": "string",
                "enum": ["baseline"],
                "default": "baseline",
                "description": (
                    "D-08-B1: solo 'baseline' parquet supportato in Phase 8. "
                    "D-08-B2 enum extensible Phase 9/11 (logs/trades.db quando "
                    "schema bridge maturo)."
                ),
            },
        },
        "required": [],
    },
)

PREDICT_TRADE_QUALITY_TOOL = Tool(
    name="predict_trade_quality",
    description=(
        "Wrapper read-only di MLFilter.predict(). Ritorna ml_score (raw LightGBM) "
        "+ calibrated_prob + threshold_for_profile + would_pass_gate. NON e' un "
        "gate decisione (risk_engine resta unico gate). Se ENABLE_ML_FILTER=false "
        "OR singleton non caricato: tutti i campi null, ok:true, warning='ml_filter_disabled'."
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
            "context":     {
                "type": "object",
                "description": (
                    "Optional extended indicators snapshot (33 cols Phase 2 + 5 meta). "
                    "Se assente: handler chiama MarketDataAdapter.get_extended_indicators "
                    "(deferred Wave 1 Plan 08-02)."
                ),
            },
        },
        "required": [
            "symbol", "timeframe", "profile", "direction",
            "entry_price", "stop_loss", "take_profit",
        ],
    },
)

GET_ML_CALIBRATION_TOOL = Tool(
    name="get_ml_calibration",
    description=(
        "Reliability data del classificatore corrente (metadata.json sidecar). "
        "Default: per-fold breakdown completo (10 fold, ~30-50KB) per audit-first "
        "(D-08-C1). Opt-out summary_only=true ritorna solo aggregate + "
        "threshold_by_profile + model_version + trained_at (~3-5KB, D-08-C2)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "summary_only": {
                "type": "boolean",
                "default": False,
                "description": "Se true: payload ridotto (~3-5KB). Default false: per-fold full.",
            },
        },
        "required": [],
    },
)


# ─── Handler stub (Wave 0 — raise NotImplementedError; GREEN nei Wave 1-3) ─

def handle_train_ml_filter(
    args: dict,
    job_queue: Any,
    cfg: Any,
) -> dict:
    """MCP-04 — D-08-A1 async submit training.

    Wave 0 STUB: raise NotImplementedError. Plan 08-04 implementa.
    """
    raise NotImplementedError(
        "handle_train_ml_filter Wave 3 — implementato in Plan 08-04",
    )


def handle_predict_trade_quality(
    args: dict,
    ml_filter_singleton: Any,
    mt5_client: Any,
    cfg: Any,
) -> dict:
    """MCP-05 — D-12 wrapper read-only MLFilter.predict.

    Wave 0 STUB: raise NotImplementedError. Plan 08-02 implementa.
    """
    raise NotImplementedError(
        "handle_predict_trade_quality Wave 1 — implementato in Plan 08-02",
    )


def handle_get_ml_calibration(
    args: dict,
    cfg: Any,
) -> dict:
    """MCP-06 — D-08-C1 default per-fold; D-08-C2 summary_only opt-out.

    Wave 0 STUB: raise NotImplementedError. Plan 08-03 implementa.
    """
    raise NotImplementedError(
        "handle_get_ml_calibration Wave 2 — implementato in Plan 08-03",
    )


__all__ = [
    "TRAIN_ML_FILTER_TOOL",
    "PREDICT_TRADE_QUALITY_TOOL",
    "GET_ML_CALIBRATION_TOOL",
    "handle_train_ml_filter",
    "handle_predict_trade_quality",
    "handle_get_ml_calibration",
]
