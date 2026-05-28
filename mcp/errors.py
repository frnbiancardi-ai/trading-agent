"""Codici errore standardizzati per envelope MCP tool (D-F2).

Ogni handler che fallisce ritorna:
    {"ok": False, "error": <ErrorCodes.X>, "message": <human_it>, ...context}

I codici sono consumati da:
- mcp/handlers/backtest.py (run_in_progress, unknown_run_id, no_active_run, decision_not_found)
- mcp/handlers/position.py (stops_level_violation, partial_exceeds_volume, position_not_found, broker_rejected, conflict_*)
- mcp/handlers/market.py (historical_data_unavailable, as_of_ts_*)
- mcp/server.py (mt5_not_ready)
- mcp/handlers/ml.py (validation_failed, not_found, internal_error)

Convenzione: snake_case per codici flat, prefisso `conflict:` per conflitti
inter-arg di modify_position (D-B1).
"""
from __future__ import annotations


class ErrorCodes:
    """Costanti string-typed per error codes."""

    # Backtest control plane (D-A1, D-A4)
    RUN_IN_PROGRESS = "run_in_progress"
    UNKNOWN_RUN_ID = "unknown_run_id"
    NO_ACTIVE_RUN = "no_active_run"

    # BarSource / historical data (D-D1)
    HISTORICAL_DATA_UNAVAILABLE = "historical_data_unavailable"
    AS_OF_TS_OUT_OF_RANGE = "as_of_ts_out_of_range"
    AS_OF_TS_WARMUP_INSUFFICIENT = "as_of_ts_warmup_insufficient"

    # modify_position validation (D-B1, D-B3)
    STOPS_LEVEL_VIOLATION = "stops_level_violation"
    PARTIAL_EXCEEDS_VOLUME = "partial_exceeds_volume"
    POSITION_NOT_FOUND = "position_not_found"
    BROKER_REJECTED = "broker_rejected"
    CONFLICT_TRAIL_AND_MANUAL_SL = "conflict: trail_and_manual_sl"
    CONFLICT_BE_AND_MANUAL_SL = "conflict: be_and_manual_sl"

    # Server bootstrap
    MT5_NOT_READY = "mt5_not_ready"

    # replay_decision (D-D2)
    DECISION_NOT_FOUND = "decision_not_found"

    # Phase 8 ML (D-08-B3, D-08-C, D-08-A1) — generic error codes
    VALIDATION_FAILED = "validation_failed"
    NOT_FOUND = "not_found"
    INTERNAL_ERROR = "internal_error"


def envelope(error_code: str, message: str, **context) -> dict:
    """Helper per costruire envelope D-F2 uniforme.

    Returns: {ok: False, error: <code>, message: <it>, ...context}
    """
    base = {"ok": False, "error": error_code, "message": message}
    base.update(context)
    return base
