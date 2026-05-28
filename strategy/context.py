"""StrategyContext: side-input bundle passato a tutti i detector pure-fn (D-04)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timeframe: str
    profile: str                          # "CONSERVATIVE" | "MODERATE" | "AGGRESSIVE"
    sr: dict
    regime: str                           # "compressed" | "normal" | "expanded"
    patterns: list                        # list[PatternHit] from Phase 3 scan_patterns()
    symbol_info: object
    pip_size: float
    intermarket_score_fn: Callable | None = None  # Phase 10 hook
    news_blackout_fn: Callable | None = None      # Phase 10 hook
    recent_trades: list = field(default_factory=list)
    spread_baseline_pips: float | None = None
    # Campi privati per adapter (esclusi da compare/hash/repr)
    _bars: list = field(default_factory=list, compare=False, hash=False, repr=False)
    _indicators: object = field(default=None, compare=False, hash=False, repr=False)
