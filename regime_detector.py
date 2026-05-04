"""Regime Detector (fase 18.2 — Murphy).

Determina regime di mercato corrente (RISK_ON / RISK_OFF / NEUTRAL / INFLATIONARY)
da IntermarketContext. Logica Murphy:

- RISK_ON: Dollar WEAK + Oil RISING + Gold FLAT/FALLING (economia in crescita)
- RISK_OFF: Dollar STRONG + Gold RISING + Oil FALLING (flight to safety)
- INFLATIONARY: Gold RISING + Oil RISING (commodity boom)
- NEUTRAL: segnali misti
"""
import logging

from config import Config
from models import IntermarketContext, RegimeState


class RegimeDetector:
    """Detector regime market da contesto intermarket."""

    def __init__(self, cfg: Config, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.log = logger or logging.getLogger(__name__)

    def detect(self, ctx: IntermarketContext) -> RegimeState:
        """Restituisce RegimeState con regime, confidence, warning_signals."""
        if not self.cfg.ENABLE_REGIME_DETECTION:
            return RegimeState(regime="NEUTRAL", confidence=0.0)

        warnings: list[str] = []
        regime, conf = self._classify(ctx, warnings)

        return RegimeState(
            regime=regime,
            confidence=conf,
            duration_bars=0,
            warning_signals=warnings,
        )

    def _classify(self, ctx: IntermarketContext, warnings: list[str]) -> tuple[str, float]:
        """Classifica regime e confidence (0-1)."""
        d = ctx.dollar_trend
        g = ctx.gold_trend
        o = ctx.oil_trend

        # INFLATIONARY: Gold + Oil entrambi rising
        if g == "RISING" and o == "RISING":
            warnings.append("inflation_pressure")
            conf = 0.8 if d == "WEAK" else 0.6
            return "INFLATIONARY", conf

        # RISK_OFF: Gold rising + (Dollar strong OR Oil falling)
        if g == "RISING" and (d == "STRONG" or o == "FALLING"):
            warnings.append("flight_to_safety")
            conf = 0.85 if (d == "STRONG" and o == "FALLING") else 0.65
            return "RISK_OFF", conf

        # RISK_ON: Oil rising + Dollar weak + Gold not rising
        if o == "RISING" and d == "WEAK" and g != "RISING":
            conf = 0.8 if g == "FALLING" else 0.65
            return "RISK_ON", conf

        # RISK_OFF debole: Dollar strong + Oil falling
        if d == "STRONG" and o == "FALLING":
            warnings.append("dollar_dominance")
            return "RISK_OFF", 0.55

        # RISK_ON debole: Dollar weak + Oil rising
        if d == "WEAK" and o == "RISING":
            return "RISK_ON", 0.55

        # Default neutral
        return "NEUTRAL", 0.3

    def should_veto_buy(self, regime_state: RegimeState, symbol: str) -> bool:
        """True se regime RISK_OFF + symbol risk-on asset (commodity ccy / equity proxy)."""
        if not self.cfg.REGIME_RISK_OFF_VETO:
            return False
        if regime_state.regime != "RISK_OFF":
            return False
        # Commodity currencies + EUR/GBP penalizzati in RISK_OFF
        risk_on_assets = ("AUD", "NZD", "CAD", "MXN", "ZAR", "TRY")
        return any(a in symbol.upper() for a in risk_on_assets)

    def should_veto_sell(self, regime_state: RegimeState, symbol: str) -> bool:
        """True se regime RISK_ON + symbol safe-haven (JPY, CHF, Gold)."""
        if not self.cfg.REGIME_RISK_OFF_VETO:
            return False
        if regime_state.regime != "RISK_ON":
            return False
        safe_havens = ("JPY", "CHF", "XAU")
        return any(s in symbol.upper() for s in safe_havens)

    def confidence_penalty(self, regime_state: RegimeState, direction: str, symbol: str) -> float:
        """Penalità confidence se direction non allineata col regime."""
        if regime_state.regime == "NEUTRAL":
            return 0.0
        penalty = self.cfg.REGIME_CONFIDENCE_PENALTY

        if direction == "BUY" and self.should_veto_buy(regime_state, symbol):
            return penalty
        if direction == "SELL" and self.should_veto_sell(regime_state, symbol):
            return penalty
        return 0.0
