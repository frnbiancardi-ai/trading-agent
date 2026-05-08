"""Detector Setup B reversal: reversal a S/R con PatternHit confermante (Wave 2 STRAT-02)."""
from strategy.context import StrategyContext
from strategy.proposal import ProposalDraft


def detect_b_reversal(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    # Wave 2 TODO: implementazione completa (counter-trend gate D-07 + _compute_levels_b)
    return ProposalDraft(setup_type="NONE", reason="wave_2_pending")
