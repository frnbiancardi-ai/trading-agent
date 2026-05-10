"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


# Wave 2 — MCP-01: run_backtest (D-A1)
def test_run_backtest_returns_run_id():
    pytest.xfail("MISSING — Wave 2 MCP-01 D-A1")


def test_run_backtest_concurrency_cap():
    pytest.xfail("MISSING — Wave 2 MCP-01 D-A4")


# Wave 2 — MCP-02: get_backtest_metrics (D-A3)
def test_get_metrics_polymorphic():
    pytest.xfail("MISSING — Wave 2 MCP-02 D-A3")


def test_get_metrics_unknown():
    pytest.xfail("MISSING — Wave 2 MCP-02 unknown_run_id")


# Wave 2 — MCP-03: walk_forward_validate
def test_walk_forward_3fold():
    pytest.xfail("MISSING — Wave 2 MCP-03")


def test_walk_forward_fold_cap():
    pytest.xfail("MISSING — Wave 2 MCP-03 cap=10")


# Wave 2 — cancel_backtest (D-A4)
def test_cancel_unknown():
    pytest.xfail("MISSING — Wave 2 cancel_backtest D-A4")


def test_cancel_active():
    pytest.xfail("MISSING — Wave 2 cancel_backtest D-A4")


# Wave 4 — MCP-15: replay_decision (D-D2)
def test_replay_decision_live():
    pytest.xfail("MISSING — Wave 4 MCP-15 D-D2")


def test_replay_decision_baseline():
    pytest.xfail("MISSING — Wave 4 MCP-15 D-D2")


def test_replay_decision_regression_flag():
    pytest.xfail("MISSING — Wave 4 MCP-15 D-D2")
