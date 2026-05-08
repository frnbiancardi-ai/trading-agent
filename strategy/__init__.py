"""Strategy package — motore Python puro per generare ProposalDraft (Phase 4).

Wave 0 transitional state: re-esporta IntradayStrategy + StrategyEnvironment +
risk/utility helpers dal legacy strategy_legacy.py per non rompere
scheduler.py / mcp_server.py / scanner.py / backtest/engine.py / tests. Wave 3
sostituirà queste re-export con la versione shim pure-fn (analyze_symbol che
usa evaluate_proposal_for_bar).
"""
from strategy.context import StrategyContext
from strategy.proposal import ProposalDraft

# Wave 0: re-export legacy IntradayStrategy + utility risk dal modulo storico.
# Wave 3 sostituirà IntradayStrategy con shim che chiama evaluate_proposal_for_bar.
from strategy_legacy import (  # noqa: F401
    IntradayStrategy,
    StrategyEnvironment,
    _last_valid,
    _pip_size,
    _pip_value_amount,
    estimate_position_risk_amount,
    estimate_proposal_risk_amount,
    estimate_proposal_lots,
)

__all__ = [
    "IntradayStrategy",
    "StrategyEnvironment",
    "ProposalDraft",
    "StrategyContext",
    "estimate_position_risk_amount",
    "estimate_proposal_risk_amount",
    "estimate_proposal_lots",
    "_last_valid",
    "_pip_size",
]
