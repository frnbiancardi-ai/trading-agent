"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


# Wave 1 — R1: get_market_snapshot esteso (200 bar default, indicators_extended)
def test_snapshot_default_200_bars():
    pytest.xfail("MISSING — Wave 1 R1: default 200 bars D-C1")


def test_snapshot_explicit_50_bars():
    pytest.xfail("MISSING — Wave 1 R1: bars=50 override D-C1")


def test_snapshot_legacy_and_extended():
    pytest.xfail("MISSING — Wave 1 R1: indicators + indicators_extended D-C1")


# Wave 1 — R2: scan_symbol_candidates con regime + correlation_warnings
def test_scan_includes_regime():
    pytest.xfail("MISSING — Wave 1 R2: regime field D-C1")


def test_scan_correlation_warnings():
    pytest.xfail("MISSING — Wave 1 R2: correlation_warnings D-C1")


# Wave 4 — MCP-09: get_correlation_matrix
def test_correlation_matrix_2symbols():
    pytest.xfail("MISSING — Wave 4 MCP-09")


def test_correlation_default_lookback():
    pytest.xfail("MISSING — Wave 4 MCP-09: default 100")


# Wave 4 — MCP-11: get_session_state
def test_session_state_london_open():
    pytest.xfail("MISSING — Wave 4 MCP-11")


def test_session_state_dst():
    pytest.xfail("MISSING — Wave 4 MCP-11 DST")


# Wave 4 — MCP-12: get_multi_tf_snapshot
def test_multi_tf_snapshot():
    pytest.xfail("MISSING — Wave 4 MCP-12 H4+H1+M15")


# Wave 4 — MCP-14: get_pattern_catalog
def test_pattern_catalog_50bars():
    pytest.xfail("MISSING — Wave 4 MCP-14")
