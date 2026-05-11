"""Handler di dominio per mcp_tools.

Struttura:
- account.py   → get_account_state, get_risk_profile, get_trade_history
- market.py    → get_market_snapshot (R1), scan_symbol_candidates (R2),
                 get_symbol_universe, get_symbol_indicators
- proposal.py  → propose_trade (R3), evaluate_trade_proposal, submit_order_if_approved
- position.py  → close_position + Wave 3: modify_position, partial_close (handle layer)
"""
