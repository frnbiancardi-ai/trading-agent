"""Trade Analyzer: estrae features da trade per analisi ML."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class TradeOutcome(Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


@dataclass
class TradeFeatures:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    outcome: TradeOutcome
    profit_pips: float
    hold_time_minutes: int

    session: str
    day_of_week: int
    hour: int
    atr_at_entry: float
    volatility_regime: str

    breakout_volume_ratio: Optional[float] = None
    confluence_score: Optional[float] = None
    trend_strength: Optional[float] = None
    rsi_at_entry: Optional[float] = None


def _determine_session(hour: int) -> str:
    if 0 <= hour < 8:
        return "ASIA"
    elif 8 <= hour < 13:
        return "LONDON"
    elif 13 <= hour < 21:
        return "NY"
    else:
        return "OVERNIGHT"


def _determine_outcome(profit: float, direction: str) -> TradeOutcome:
    if profit > 0:
        return TradeOutcome.WIN
    elif profit < 0:
        return TradeOutcome.LOSS
    else:
        return TradeOutcome.BREAKEVEN


def extract_trade_features(trade: dict) -> TradeFeatures:
    entry_time = trade["entry_time"]
    if isinstance(entry_time, str):
        entry_time = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
    
    exit_time = trade["exit_time"]
    if isinstance(exit_time, str):
        exit_time = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")
    
    hold_minutes = int((exit_time - entry_time).total_seconds() / 60)
    hour = entry_time.hour
    
    entry_price = trade["entry_price"]
    exit_price = trade["exit_price"]
    profit = exit_price - entry_price
    if trade.get("direction", "BUY") == "SELL":
        profit = entry_price - exit_price
    
    if profit >= 0:
        outcome = TradeOutcome.WIN if profit > 0 else TradeOutcome.BREAKEVEN
    else:
        outcome = TradeOutcome.LOSS
    
    return TradeFeatures(
        symbol=trade["symbol"],
        entry_time=entry_time,
        exit_time=exit_time,
        direction=trade.get("direction", "BUY"),
        entry_price=trade["entry_price"],
        exit_price=trade["exit_price"],
        sl=trade.get("sl", 0),
        tp=trade.get("tp", 0),
        outcome=outcome,
        profit_pips=profit,
        hold_time_minutes=hold_minutes,
        session=_determine_session(hour),
        day_of_week=entry_time.weekday(),
        hour=hour,
        atr_at_entry=trade.get("atr_at_entry", 0.001),
        volatility_regime=trade.get("volatility_regime", "MEDIUM"),
        breakout_volume_ratio=trade.get("breakout_volume_ratio"),
        confluence_score=trade.get("confluence_score"),
        trend_strength=trade.get("trend_strength"),
        rsi_at_entry=trade.get("rsi_at_entry"),
    )


__all__ = ["TradeFeatures", "TradeOutcome", "extract_trade_features"]