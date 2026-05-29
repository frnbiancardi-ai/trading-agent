"""Strategy package — motore Python puro per generare ProposalDraft (Phase 4).

Wave 3 plan-07 (cutover finale):
  - evaluate_proposal_for_bar: orchestrator pure-fn che esegue tutti e 4 i
    detector e ritorna il vincitore secondo D-06 (priorità + tie-break).
  - IntradayStrategy: shim non-pure (in strategy/_shim.py) che preserva la
    firma legacy analyze_symbol(symbol, account_state, sentiment=None) →
    TechnicalSetup. Scheduler / mcp_server / claude_agent / scanner non
    devono cambiare (D-01).
  - StrategyEnvironment: lift dal legacy, esposto al package level per
    backward-compat.
  - risk utility helpers re-esportati da strategy.risk_utils per scanner.py.

Single shared call site (D-09): build_ctx_live e build_ctx_backtest entrambi
producono StrategyContext, evaluate_proposal_for_bar è chiamato identicamente.

Dopo questo plan, strategy_legacy.py rimane nel tree ma è ORPHANED; il cleanup
finale è in plan 04-08 dopo che la regression replay (1e-4 confidence) passa.
"""
from __future__ import annotations

from dataclasses import replace

from strategy.context import StrategyContext
from strategy.proposal import (
    ProposalDraft,
    draft_to_technical_setup,
    draft_to_trade_proposal,
)
from strategy.confluence import (
    compute_confidence,
    grade_for,
    load_strategy_config,
    score_factors,
)
from strategy.setups import ALL_DETECTORS, DETECTOR_NAMES
from strategy.risk_utils import (
    _pip_size,
    _pip_value_amount,
    estimate_position_risk_amount,
    estimate_proposal_lots,
    estimate_proposal_risk_amount,
)
from strategy._shim import IntradayStrategy, StrategyEnvironment


# Re-export _last_valid per backward-compat con scanner.py (importava da strategy_legacy).
def _last_valid(series: list):
    """Ritorna l'ultimo elemento non-None di una lista, o None (verbatim legacy 35-39)."""
    for v in reversed(series or []):
        if v is not None:
            return v
    return None


# D-06 priority constants
GRADE_ORDER = {"A+": 0, "A": 1, "B": 2, "C": 3, "reject": 4}
PRIORITY = {"A_breakout": 0, "C_compression": 1, "B_reversal": 2, "D_pullback": 3}


def evaluate_proposal_for_bar(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    """Esegue tutti i detector sul bar corrente e ritorna il vincitore (D-06).

    Tie-break:
      1. setup_type READY > FORMING > NONE
      2. Tra READY: minimo (GRADE_ORDER, PRIORITY) — A+ prima, poi A>C>B>D
      3. Tra FORMING: minimo PRIORITY
      4. Se tutti NONE: ritorna il primo (Setup A) con i drafts perdenti in
         setup_specific.losers per ML feature extraction (Phase 7).
    """
    # Filtro enable/disable (2026-05-29): ctx.enabled_setups è un frozenset di nomi
    # canonici popolato da build_ctx_live dai flag cfg.ENABLE_SETUP_*. None =
    # backward-compat (tutti i detector). I flag NON sono letti qui (purezza STRAT-08):
    # arrivano solo via ctx.
    enabled = getattr(ctx, "enabled_setups", None)
    if enabled is None:
        active = ALL_DETECTORS
    else:
        active = [d for d in ALL_DETECTORS if DETECTOR_NAMES.get(d) in enabled]

    # Guard empty-set: se nessun setup è abilitato, evita il crash su drafts[0] a valle.
    if not active:
        return ProposalDraft(setup_type="NONE", reason="no_enabled_setups")

    drafts = [detect(bars, indicators, ctx) for detect in active]

    ready = [d for d in drafts if d.setup_type == "READY"]
    if ready:
        winner = min(
            ready,
            key=lambda d: (
                GRADE_ORDER.get(d.grade or "reject", 99),
                PRIORITY.get(d.setup_name or "", 99),
            ),
        )
        losers = [d for d in drafts if d is not winner]
        new_specific = dict(winner.setup_specific or {})
        new_specific["losers"] = losers
        return replace(winner, setup_specific=new_specific)

    forming = [d for d in drafts if d.setup_type == "FORMING"]
    if forming:
        winner = min(
            forming,
            key=lambda d: PRIORITY.get(d.setup_name or "", 99),
        )
    else:
        winner = drafts[0]

    losers = [d for d in drafts if d is not winner]
    new_specific = dict(winner.setup_specific or {})
    new_specific["losers"] = losers
    return replace(winner, setup_specific=new_specific)


__all__ = [
    "IntradayStrategy",
    "StrategyEnvironment",
    "evaluate_proposal_for_bar",
    "ProposalDraft",
    "StrategyContext",
    "draft_to_trade_proposal",
    "draft_to_technical_setup",
    "score_factors",
    "grade_for",
    "compute_confidence",
    "load_strategy_config",
    "estimate_position_risk_amount",
    "estimate_proposal_risk_amount",
    "estimate_proposal_lots",
    "_last_valid",
    "_pip_size",
    "_pip_value_amount",
    "ALL_DETECTORS",
    "GRADE_ORDER",
    "PRIORITY",
]
