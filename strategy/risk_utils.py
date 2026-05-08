"""Utility risk + lot sizing — non-pure (consumano models/config), separate dal puro detector layer (D-15).

Wave 3 plan-07: lift verbatim da strategy_legacy.py delle 5 funzioni utility:
  - _pip_size(symbol_info)            (legacy linea 42)
  - _pip_value_amount(symbol_info, pip_size) (legacy linea 92)
  - estimate_position_risk_amount(position, symbol_info)
  - estimate_proposal_risk_amount(proposal, symbol_info, lots)
  - estimate_proposal_lots(proposal, account_state, cfg, symbol_info)

Modulo NON pure-fn (consuma models e cfg) → escluso dal purity gate (PURE_MODULES
in tests/test_strategy_purity.py). Le firme delle funzioni sono identiche al
legacy per backward-compat: scanner.py, scheduler.py, mcp_server.py, _shim.py
chiamano questi helper con la stessa convenzione.
"""
from __future__ import annotations
from typing import Any  # Config consumato come parametro non type-checked al modulo top

from models import AccountState, PositionInfo, TradeProposal


def _pip_size(symbol_info) -> float:
    """Ritorna la dimensione di 1 pip per il symbol (verbatim legacy 42-47).

    Convenzione MT5: digits 3 o 5 → pip = point × 10 (es. EUR/USD 0.0001 con
    point=0.00001). Altrimenti pip = point.
    """
    if symbol_info is None:
        return 0.0001
    point = getattr(symbol_info, "point", 0.0001) or 0.0001
    digits = getattr(symbol_info, "digits", 5)
    return point * 10 if digits in (3, 5) else point


def _pip_value_amount(symbol_info, pip_size: float) -> float:
    """Stima il valore di 1 pip per 1 lotto in account currency (verbatim legacy 92-99)."""
    if symbol_info is None or pip_size <= 0:
        return 0.0
    tick_value = getattr(symbol_info, "trade_tick_value", 0.0) or 0.0
    tick_size = getattr(symbol_info, "trade_tick_size", 0.0) or 0.0
    if tick_size <= 0 or tick_value <= 0:
        return 0.0
    return tick_value * pip_size / tick_size


def estimate_position_risk_amount(
    position: PositionInfo,
    symbol_info,
) -> float:
    """Stima la perdita potenziale (account currency) se il SL fosse colpito (verbatim legacy 102-113)."""
    if position is None or position.stop_loss in (0.0, None):
        return 0.0
    pip_size = _pip_size(symbol_info)
    pip_value = _pip_value_amount(symbol_info, pip_size)
    if pip_value <= 0 or pip_size <= 0:
        return 0.0
    distance_pips = abs(position.entry_price - position.stop_loss) / pip_size
    return position.lots * pip_value * distance_pips


def estimate_proposal_risk_amount(
    proposal: TradeProposal,
    symbol_info,
    lots: float,
) -> float:
    """Stima la perdita potenziale di una proposta a fronte di lots calcolati (verbatim legacy 116-126)."""
    if symbol_info is None or lots <= 0:
        return 0.0
    pip_size = _pip_size(symbol_info)
    pip_value = _pip_value_amount(symbol_info, pip_size)
    if pip_value <= 0 or pip_size <= 0:
        return 0.0
    distance_pips = abs(proposal.entry_price - proposal.stop_loss_price) / pip_size
    return lots * pip_value * distance_pips


def estimate_proposal_lots(
    proposal: TradeProposal,
    account_state: AccountState,
    cfg: Any,
    symbol_info,
) -> float:
    """Stima la size in lotti coerente col risk_engine, senza chiamare MT5 per il margin check (verbatim legacy 129-148).

    Usato solo per il drawdown potenziale.
    """
    pip_size = _pip_size(symbol_info)
    pip_value = _pip_value_amount(symbol_info, pip_size)
    if pip_value <= 0 or pip_size <= 0:
        return 0.0
    distance_pips = abs(proposal.entry_price - proposal.stop_loss_price) / pip_size
    if distance_pips <= 0:
        return 0.0
    if cfg.RISK_AMOUNT_MODE == "FIXED_AMOUNT":
        risk_amount = cfg.RISK_PER_TRADE_AMOUNT
    else:
        risk_amount = account_state.balance * cfg.RISK_PER_TRADE_PERCENT / 100.0
    if risk_amount <= 0:
        return 0.0
    return risk_amount / (pip_value * distance_pips)
