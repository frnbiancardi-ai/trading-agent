"""Stub Wave 0 per Phase 6 MCP Tools.

Tests xfail('MISSING — Wave N ...') finché Wave N non li implementa.
Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map.
"""
import pytest


# Wave 2 — JobQueue: submit (D-A1)
def test_submit_returns_started():
    pytest.xfail("MISSING — Wave 2 JobQueue D-A1")


# Wave 2 — JobQueue: concurrency cap (D-A4)
def test_submit_concurrent_rejected():
    pytest.xfail("MISSING — Wave 2 JobQueue D-A4")


# Wave 2 — JobQueue: status
def test_status_unknown_run_id():
    pytest.xfail("MISSING — Wave 2 JobQueue")


def test_status_running_done_failed_cancelled():
    pytest.xfail("MISSING — Wave 2 JobQueue D-A3")


# Wave 2 — JobQueue: cancel (D-A4)
def test_cancel_active():
    pytest.xfail("MISSING — Wave 2 JobQueue D-A4")


def test_cancel_no_active():
    pytest.xfail("MISSING — Wave 2 JobQueue D-A4")

# Nota: test_run_backtest_concurrency_cap è in test_mcp_handlers_backtest.py
# (handler level). Questo file testa il JobQueue come componente isolato.
