"""ProposalDraft: output canonico dei detector (D-03). Wave 1 aggiunge gli adapter."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ProposalDraft:
    setup_type: Literal["READY", "FORMING", "NONE"]
    setup_name: Literal["A_breakout", "B_reversal", "C_compression", "D_pullback"] | None = None
    direction: Literal["BUY", "SELL"] | None = None
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    factors: dict | None = None
    grade: Literal["A+", "A", "B", "C", "reject"] | None = None
    confidence: float = 0.0
    reason: str = ""
    rationale_parts: dict | None = None
    setup_specific: dict | None = None

    def __post_init__(self):
        # Frozen dataclass: usa object.__setattr__ per inizializzare dict mutabili.
        if self.factors is None:
            object.__setattr__(self, "factors", {})
        if self.rationale_parts is None:
            object.__setattr__(self, "rationale_parts", {})
        if self.setup_specific is None:
            object.__setattr__(self, "setup_specific", {})

# Wave 1 aggiungerà draft_to_trade_proposal() e draft_to_technical_setup().
