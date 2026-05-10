"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


# Wave 2 — SC#4: end-to-end round-trip run_backtest → get_backtest_metrics
def test_run_backtest_writes_db():
    pytest.xfail("MISSING — Wave 2 SC#4 round-trip")


def test_round_trip_metrics():
    pytest.xfail("MISSING — Wave 2 SC#4 round-trip")
