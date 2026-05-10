"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


@pytest.mark.integration
def test_real_broker_modify():
    pytest.xfail("MISSING — Wave 3 SC#2: requires demo MT5 + open position; runs MANUAL only")
