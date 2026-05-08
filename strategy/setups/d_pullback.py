"""Detector Setup D pullback: pullback su trend EMA20/EMA50 + Fib (Wave 2 STRAT-04)."""
from strategy.context import StrategyContext
from strategy.proposal import ProposalDraft


def detect_d_pullback(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    # Wave 2 TODO: implementazione completa (EMA20 touch + Fib 38.2/61.8 + _compute_levels_d)
    return ProposalDraft(setup_type="NONE", reason="wave_2_pending")
