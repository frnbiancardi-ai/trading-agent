"""Detector Setup A breakout: rottura pulita di S/R orizzontale (Wave 2 STRAT-01)."""
from strategy.context import StrategyContext
from strategy.proposal import ProposalDraft


def detect_a_breakout(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    # Wave 2 TODO: implementazione completa (5-factor confluence + _compute_levels_a)
    return ProposalDraft(setup_type="NONE", reason="wave_2_pending")
