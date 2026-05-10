"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


# Wave 1 — D-E1: shim mcp_server.py → mcp.server
def test_legacy_entrypoint_imports():
    pytest.xfail("MISSING — Wave 1 D-E1 shim")


# Wave 4 — tools/list totale 25 tool dopo tutti i wave
def test_list_tools_count():
    pytest.xfail("MISSING — Wave 4 — total 25 tools after all waves")


# Wave 4 — skill regression: forex-trader-pro compat
def test_skill_compat_reads():
    pytest.xfail("MISSING — Wave 4 skill regression check")
