"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


# Wave 1 — BarSource live path (D-D1)
def test_live_path_calls_mt5():
    pytest.xfail("MISSING — Wave 1 BarSource live D-D1")


# Wave 1 — BarSource as_of_ts: slice strict-< (no future leak, D-D1)
def test_as_of_strict_lt_no_future_leak():
    pytest.xfail("MISSING — Wave 1 BarSource strict-< D-D1")


# Wave 1 — BarSource error cases (D-D1)
def test_as_of_warmup_insufficient():
    pytest.xfail("MISSING — Wave 1 BarSource error D-D1")


def test_as_of_out_of_range():
    pytest.xfail("MISSING — Wave 1 BarSource error D-D1")


def test_as_of_csv_missing():
    pytest.xfail("MISSING — Wave 1 historical_data_unavailable D-D1")
