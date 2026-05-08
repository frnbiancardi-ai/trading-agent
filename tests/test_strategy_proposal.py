"""Test ProposalDraft adapter + R:R floor + ATR cap (STRAT-07). Mock-free.

RED: smoke test su import — fallisce finché Wave 1 non implementa le 4 funzioni.
GREEN: Task 2 sostituisce con i 6 body di test completi (parametrize per i 3 profile).
"""
import pytest


def test_smoke_import_wave1_adapters_and_helpers():
    """RED: import dei 4 simboli Wave 1; fallisce finché proposal.py è solo stub."""
    from strategy.proposal import (  # noqa: F401
        ProposalDraft,
        compute_levels_with_atr_cap,
        draft_to_technical_setup,
        draft_to_trade_proposal,
        rr_meets_profile_floor,
    )


def test_draft_to_trade_proposal_valid_ready():
    pytest.skip("Wave 1 pending — STRAT-07 (Task 2 fill)")


def test_draft_to_trade_proposal_rejects_non_ready():
    pytest.skip("Wave 1 pending — STRAT-07 (Task 2 fill)")


def test_draft_to_technical_setup_preserves_fields():
    pytest.skip("Wave 1 pending — STRAT-07 (Task 2 fill)")


def test_rr_floor_conservative():
    pytest.skip("Wave 1 pending — STRAT-07 (CONSERVATIVE min_rr=2.5)")


def test_rr_floor_moderate():
    pytest.skip("Wave 1 pending — STRAT-07 (MODERATE min_rr=1.8)")


def test_rr_floor_aggressive():
    pytest.skip("Wave 1 pending — STRAT-07 (AGGRESSIVE min_rr=1.3)")
