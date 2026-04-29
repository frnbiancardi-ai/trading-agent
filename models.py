from dataclasses import dataclass, field
from datetime import date as _date, datetime
from typing import Literal


@dataclass
class TradeProposal:
    symbol: str
    direction: str
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    timeframe: str
    comment: str
    confidence: float
    rationale: str


@dataclass
class PositionInfo:
    symbol: str
    lots: float
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    profit: float


@dataclass
class AccountState:
    balance: float
    equity: float
    free_margin: float
    open_positions: list[PositionInfo] = field(default_factory=list)
    today_realized_pnl: float = 0.0
    starting_balance_of_day: float = 0.0


@dataclass
class RiskDecision:
    approved: bool
    size_lots: float
    reason: str
    adjusted_stop_loss: float
    adjusted_take_profit: float


@dataclass
class OrderResult:
    success: bool
    order_id: int | None = None
    error_message: str | None = None


@dataclass
class SymbolScanCandidate:
    symbol: str
    trend_bias: str
    momentum_bias: str
    volatility_state: str
    spread_state: str
    candidate_score: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class ScannerDecision:
    proposal: TradeProposal | None
    shortlist: list[str] = field(default_factory=list)
    candidates: list[SymbolScanCandidate] = field(default_factory=list)
    iterations_used: int = 0
    stop_reason: str = ""


@dataclass
class DelayedFollowUpRequest:
    symbol: str
    timeframe: str
    delay_minutes: int
    reason: str
    focus_prompt: str
    created_at: datetime
    expires_at: datetime
    already_delayed: bool = False


@dataclass
class AgentCycleOutcome:
    outcome_type: Literal["TRADE", "NO_TRADE", "WAIT_FOLLOW_UP"]
    proposal: TradeProposal | None = None
    follow_up: DelayedFollowUpRequest | None = None
    note: str = ""
    decided_at: datetime | None = None


@dataclass
class DailyRunState:
    date: _date
    decisions_count: int = 0
    trade_count: int = 0
    no_trade_count: int = 0
