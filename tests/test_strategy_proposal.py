"""Test ProposalDraft → TradeProposal/TechnicalSetup adapter + R:R + profile filter (STRAT-07)."""
import pytest


def test_draft_to_trade_proposal_valid_ready():
    pytest.skip("Wave 1 pending — STRAT-07")


def test_draft_to_trade_proposal_rejects_non_ready():
    pytest.skip("Wave 1 pending — STRAT-07")


def test_draft_to_technical_setup_preserves_fields():
    pytest.skip("Wave 1 pending — STRAT-07")


def test_rr_floor_conservative():
    pytest.skip("Wave 1 pending — STRAT-07 (CONSERVATIVE min_rr=2.5)")


def test_rr_floor_moderate():
    pytest.skip("Wave 1 pending — STRAT-07 (MODERATE min_rr=1.8)")


def test_rr_floor_aggressive():
    pytest.skip("Wave 1 pending — STRAT-07 (AGGRESSIVE min_rr=1.3)")
