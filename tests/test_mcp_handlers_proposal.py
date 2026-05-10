"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


# Wave 1 — R3: propose_trade esteso (setup_type + confluence_score, D-C1)
def test_propose_includes_setup_type():
    pytest.xfail("MISSING — Wave 1 R3 D-C1")


def test_propose_freeform_null_setup():
    pytest.xfail("MISSING — Wave 1 R3 freeform")
