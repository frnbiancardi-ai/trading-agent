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
    ticket: int = 0


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


@dataclass
class TechnicalSetup:
    symbol: str
    timeframe: str
    setup_type: Literal["READY", "FORMING", "NONE"]
    direction: str | None
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    confidence: float
    reason: str
    indicators: dict = field(default_factory=dict)
    support_resistance: dict | None = None


@dataclass
class ScanResult:
    symbol: str
    trend_bias: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    momentum_bias: str
    volatility_state: Literal["LOW", "NORMAL", "HIGH"]
    spread_state: Literal["ACCEPTABLE", "WIDE"]
    regime: Literal["TREND", "RANGE", "BREAKOUT"]
    candidate_score: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class StrategyOutcome:
    outcome_type: Literal["TRADE", "NO_TRADE", "WAIT_FOLLOW_UP"]
    proposal: TradeProposal | None = None
    follow_up: DelayedFollowUpRequest | None = None
    scan_results: list[ScanResult] = field(default_factory=list)
    timestamp: datetime | None = None
    note: str = ""
    max_potential_drawdown_percent: float | None = None
    drawdown_violation: bool = False
    is_addon: bool = False
    news_blocked: bool = False
    paused: bool = False


@dataclass
class OpenPositionVerdict:
    """Esito della valutazione di una posizione aperta nel ciclo H24 (fase 16).

    `action` può essere:
      - HOLD: mantenere la posizione invariata.
      - CLOSE_PROTECT: chiudere per proteggere profitto su contesto tecnico negativo.
      - CLOSE_END_OF_DAY: chiudere a fine finestra operativa giornaliera (no overnight).
    """
    symbol: str
    ticket: int
    action: Literal["HOLD", "CLOSE_PROTECT", "CLOSE_END_OF_DAY"]
    reason: str
    profit_r_multiple: float | None = None


@dataclass
class SchedulerCycleRecord:
    """Riga heartbeat scritta in SQLite ad ogni ciclo dello scheduler H24."""
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    outcome: Literal[
        "OK", "NO_TRADE", "ERROR", "PAUSED", "NEWS_BLOCKED",
        "OUT_OF_WINDOW", "WEEKEND", "DRAWDOWN_BLOCK", "DRY_RUN"
    ] = "OK"
    error_type: str | None = None
    error_message: str | None = None
    consecutive_no_trade: int = 0
    consecutive_errors: int = 0
    note: str = ""


@dataclass
class NewsItem:
    source: str
    title: str
    summary: str
    link: str
    published: datetime


@dataclass
class SentimentAnalysis:
    symbol: str
    bias: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    strength: float
    relevant_news_count: int
    sample_headlines: list[str] = field(default_factory=list)
    timestamp: datetime | None = None
