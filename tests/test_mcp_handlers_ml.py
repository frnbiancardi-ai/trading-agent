"""Phase 8: ML handler tests (MCP-04/05/06) — Wave 0 scaffolding gate.

Wave 0 (Plan 08-01): 3 xfail test (stub raise NotImplementedError) +
4 green test (list_tools registration + 3 schema validation). Wave 1-3
(Plan 08-02/03/04) flippano gli xfail in green.

Pattern analog tests/test_mcp_handlers_backtest.py.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

pytest.importorskip("mcp_tools.handlers.ml")

from mcp_tools.handlers.ml import (  # noqa: E402
    GET_ML_CALIBRATION_TOOL,
    PREDICT_TRADE_QUALITY_TOOL,
    TRAIN_ML_FILTER_TOOL,
    handle_get_ml_calibration,
    handle_predict_trade_quality,
    handle_train_ml_filter,
)


# ─── Tool schema registration test (green Wave 0) ───────────────────────

def test_ml_tools_registered_in_list_tools():
    """Verifica che mcp_tools.server.list_tools() esponga i 3 nuovi tool ML.

    NB: importorskip su mcp_tools.server per graceful skip in ambienti senza
    anthropic (claude_agent.py dipendenza transitiva). In produzione e CI
    con tutte le dipendenze il test e' PASSED.
    """
    srv = pytest.importorskip("mcp_tools.server")
    tools = asyncio.run(srv.list_tools())
    names = {t.name for t in tools}
    assert "train_ml_filter" in names, f"train_ml_filter mancante, got {names}"
    assert "predict_trade_quality" in names
    assert "get_ml_calibration" in names


def test_train_ml_filter_tool_schema_data_source_enum():
    """D-08-B2: data_source enum locked a ['baseline'] in Phase 8."""
    assert TRAIN_ML_FILTER_TOOL.name == "train_ml_filter"
    props = TRAIN_ML_FILTER_TOOL.inputSchema["properties"]
    assert props["data_source"]["enum"] == ["baseline"]
    assert TRAIN_ML_FILTER_TOOL.inputSchema["required"] == []


def test_predict_trade_quality_tool_schema_required_fields():
    """MCP-05: 7 required fields + context optional."""
    required = set(PREDICT_TRADE_QUALITY_TOOL.inputSchema["required"])
    assert required == {
        "symbol", "timeframe", "profile", "direction",
        "entry_price", "stop_loss", "take_profit",
    }
    props = PREDICT_TRADE_QUALITY_TOOL.inputSchema["properties"]
    assert props["symbol"]["enum"] == ["EURUSD", "GBPUSD", "USDJPY"]
    assert props["profile"]["enum"] == ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]


def test_get_ml_calibration_tool_schema_summary_only_default_false():
    """D-08-C1: default per-fold (summary_only=False)."""
    props = GET_ML_CALIBRATION_TOOL.inputSchema["properties"]
    assert props["summary_only"]["type"] == "boolean"
    assert props["summary_only"]["default"] is False
    assert GET_ML_CALIBRATION_TOOL.inputSchema["required"] == []


# ─── Stub handler xfail (Wave 0; Plan 08-02/03/04 flippa in green) ──────

@pytest.mark.xfail(reason="Wave 1 Plan 08-02: handle_predict_trade_quality GREEN", strict=True)
def test_predict_trade_quality_stub_raises_not_implemented():
    """Wave 0: handler raise NotImplementedError (xfail).

    Plan 08-02 sostituisce raise con logica GREEN, e questo test flippa in
    PASS (strict=True → fail loud if green prima del tempo).
    """
    mock_cfg = MagicMock()
    mock_cfg.ENABLE_ML_FILTER = False
    handle_predict_trade_quality(
        args={"symbol": "EURUSD", "timeframe": "M15", "profile": "MODERATE",
              "direction": "BUY", "entry_price": 1.085,
              "stop_loss": 1.083, "take_profit": 1.090},
        ml_filter_singleton=None,
        mt5_client=MagicMock(),
        cfg=mock_cfg,
    )


@pytest.mark.xfail(reason="Wave 2 Plan 08-03: handle_get_ml_calibration GREEN", strict=True)
def test_get_ml_calibration_stub_raises_not_implemented():
    """Wave 0: handler raise NotImplementedError (xfail).

    Plan 08-03 sostituisce raise con logica GREEN (metadata.json reader).
    """
    mock_cfg = MagicMock()
    mock_cfg.ML_MODEL_PATH = "models/classifier_v1_latest.pkl"
    handle_get_ml_calibration(args={}, cfg=mock_cfg)


@pytest.mark.xfail(reason="Wave 3 Plan 08-04: handle_train_ml_filter GREEN", strict=True)
def test_train_ml_filter_stub_raises_not_implemented():
    """Wave 0: handler raise NotImplementedError (xfail).

    Plan 08-04 sostituisce raise con logica GREEN (worker + JobQueue.submit).
    """
    mock_cfg = MagicMock()
    mock_cfg.MCP_TRAINING_DATA_PATH = "data/training/baseline_decisions/part-0.parquet"
    mock_cfg.ML_MODEL_PATH = "models/classifier_v1_latest.pkl"
    mock_job_queue = MagicMock()
    handle_train_ml_filter(
        args={"data_source": "baseline"},
        job_queue=mock_job_queue,
        cfg=mock_cfg,
    )
