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
    sl_at_breakeven: bool = False
    partial_closed: bool = False


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
    """Esito della valutazione di una posizione aperta nel ciclo H24 (fase 16+).

    `action` può essere:
      - HOLD: mantenere la posizione invariata.
      - CLOSE_PROTECT: chiudere per proteggere profitto su contesto tecnico negativo.
      - CLOSE_END_OF_DAY: chiudere a fine finestra operativa giornaliera (no overnight).
      - MOVE_TO_BREAKEVEN: spostare SL a entry quando profit >= 1R (fase 17.5).
      - PARTIAL_CLOSE_50: chiudere 50% posizione quando profit >= 2R (fase 17.5).
      - TRAIL_STOP: sposta SL secondo Chandelier Exit quando profit >= 2R + già parzialmente chiusa (fase 17.5).
    """
    symbol: str
    ticket: int
    action: Literal[
        "HOLD", "CLOSE_PROTECT", "CLOSE_END_OF_DAY",
        "MOVE_TO_BREAKEVEN", "PARTIAL_CLOSE_50", "TRAIL_STOP"
    ]
    reason: str
    profit_r_multiple: float | None = None
    new_stop_loss: float | None = None
    new_take_profit: float | None = None
    close_fraction: float | None = None


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


# ──────────────────────────────────────────────────────────────────────────────
# Phase 18 — Intermarket models (Murphy + Probo)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class IntermarketContext:
    """Contesto intermarket: trend di Dollar, Gold, Oil, Bond Yields."""
    dollar_trend: Literal["STRONG", "WEAK", "NEUTRAL"]
    gold_trend: Literal["RISING", "FALLING", "FLAT"]
    oil_trend: Literal["RISING", "FALLING", "FLAT"]
    bond_yield_trend: Literal["RISING", "FALLING", "FLAT"] = "FLAT"
    timestamp: datetime | None = None


@dataclass
class RegimeState:
    """Stato regime di mercato: Risk-On, Risk-Off, Neutral."""
    regime: Literal["RISK_ON", "RISK_OFF", "NEUTRAL", "INFLATIONARY"]
    confidence: float = 0.0
    duration_bars: int = 0
    warning_signals: list[str] = field(default_factory=list)


@dataclass
class SessionInfo:
    """Informazioni sulla sessione di trading corrente."""
    name: Literal["ASIAN", "LONDON", "NEW_YORK", "OVERLAP", "OFF_HOURS"]
    quality_for_symbol: float = 0.5  # 0.0–1.0
    expected_volatility: Literal["LOW", "NORMAL", "HIGH"] = "NORMAL"


@dataclass
class CrossAssetVerdict:
    """Verdetto filtro cross-asset confirmation."""
    confirmed: bool = False
    contradicts: bool = False
    confidence_adjustment: float = 0.0  # positivo=boost, negativo=penalty
    reason: str = ""


@dataclass
class FibonacciTargets:
    """Target Fibonacci multipli per presa profitto progressiva."""
    tp_382: float = 0.0
    tp_500: float = 0.0
    tp_618: float = 0.0
    tp_100: float = 0.0
    tp_161: float = 0.0
    recommended_primary_tp: float = 0.0
