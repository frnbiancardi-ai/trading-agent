"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


# Wave 3 — MCP-16: modify_position (D-B1)
def test_modify_sl_only():
    pytest.xfail("MISSING — Wave 3 MCP-16 D-B1")


def test_move_sl_to_breakeven():
    pytest.xfail("MISSING — Wave 3 MCP-16 D-B1")


def test_conflict_trail_and_manual():
    pytest.xfail("MISSING — Wave 3 MCP-16 D-B1")


def test_conflict_be_and_manual():
    pytest.xfail("MISSING — Wave 3 MCP-16 D-B1")


def test_partial_exceeds_volume():
    pytest.xfail("MISSING — Wave 3 MCP-16 D-B1")


# Wave 3 — MCP-16: stops_level_violation (D-B3)
def test_stops_level_violation_suggests():
    pytest.xfail("MISSING — Wave 3 MCP-16 D-B3")


# Wave 3 — MCP-16: EXECUTION_MODE=shadow
def test_modify_dry_run():
    pytest.xfail("MISSING — Wave 3 MCP-16 EXECUTION_MODE=shadow")


# Wave 3 — MCP-17: get_position_state
def test_position_state_full_payload():
    pytest.xfail("MISSING — Wave 3 MCP-17")
