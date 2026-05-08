"""Detector Setup C compression: breakout da NR4/NR7 o BB squeeze (Wave 2 STRAT-03)."""
from strategy.context import StrategyContext
from strategy.proposal import ProposalDraft


def detect_c_compression(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    # Wave 2 TODO: implementazione completa (NR4/NR7 + BB squeeze + _compute_levels_c)
    return ProposalDraft(setup_type="NONE", reason="wave_2_pending")
