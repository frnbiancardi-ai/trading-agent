"""Cross-Asset Confirmation Filter (fase 18.4 — Probo + Murphy).

Verifica che setup tecnico sia confermato da contesto intermarket e cross-pair.
Esempi:
- BUY EUR/USD richiede USD/CHF bearish O Dollar weak
- BUY GBP/USD richiede Oil stable/rising + Dollar non strong
- BUY AUD/USD richiede Gold/commodities rising + Dollar weak
- BUY USD/JPY richiede risk-on (oil rising o gold flat)
"""
import logging

from config import Config
from models import CrossAssetVerdict, IntermarketContext, RegimeState


class CrossAssetFilter:
    """Filtro conferma cross-asset/cross-pair."""

    def __init__(self, cfg: Config, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.log = logger or logging.getLogger(__name__)

    def check(
        self,
        symbol: str,
        direction: str,
        context: IntermarketContext,
        regime: RegimeState | None = None,
    ) -> CrossAssetVerdict:
        """Valuta se contesto conferma o contraddice direction.

        Returns:
          CrossAssetVerdict(confirmed, contradicts, confidence_adjustment, reason)
        """
        if not self.cfg.ENABLE_CROSS_ASSET_FILTER:
            return CrossAssetVerdict(confirmed=False, contradicts=False, reason="filter_disabled")

        sym_up = symbol.upper()
        d = direction.upper()

        # Routing per simbolo
        if "EURUSD" in sym_up or "EUR/USD" in sym_up:
            return self._check_eurusd(d, context)
        if "GBPUSD" in sym_up or "GBP/USD" in sym_up:
            return self._check_gbpusd(d, context)
        if "AUDUSD" in sym_up or "AUD/USD" in sym_up:
            return self._check_audusd(d, context)
        if "NZDUSD" in sym_up:
            return self._check_audusd(d, context)  # stessa logica commodity ccy
        if "USDCAD" in sym_up:
            return self._check_usdcad(d, context)
        if "USDJPY" in sym_up:
            return self._check_usdjpy(d, context, regime)
        if "USDCHF" in sym_up:
            return self._check_usdchf(d, context)
        if "XAUUSD" in sym_up or "GOLD" in sym_up:
            return self._check_gold(d, context)

        # Default: nessun cross-check disponibile
        return CrossAssetVerdict(
            confirmed=False, contradicts=False, reason="no_rules_for_symbol"
        )

    # ── Per-symbol logic ────────────────────────────────────────────────────

    def _check_eurusd(self, direction: str, ctx: IntermarketContext) -> CrossAssetVerdict:
        """BUY EUR/USD: Dollar WEAK conferma. STRONG contraddice."""
        boost = self.cfg.CROSS_ASSET_BOOST
        penalty = self.cfg.CROSS_ASSET_PENALTY

        if direction == "BUY":
            if ctx.dollar_trend == "WEAK":
                return CrossAssetVerdict(True, False, +boost, "Dollar WEAK conferma BUY EURUSD")
            if ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(False, True, -penalty, "Dollar STRONG contraddice BUY EURUSD")
        else:  # SELL
            if ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(True, False, +boost, "Dollar STRONG conferma SELL EURUSD")
            if ctx.dollar_trend == "WEAK":
                return CrossAssetVerdict(False, True, -penalty, "Dollar WEAK contraddice SELL EURUSD")
        return CrossAssetVerdict(False, False, 0.0, "Dollar NEUTRAL")

    def _check_gbpusd(self, direction: str, ctx: IntermarketContext) -> CrossAssetVerdict:
        """GBP sensibile a Oil (UK 10% PIL energia) + Dollar."""
        boost = self.cfg.CROSS_ASSET_BOOST
        penalty = self.cfg.CROSS_ASSET_PENALTY

        if direction == "BUY":
            # Oil rising + Dollar weak → confirm
            if ctx.oil_trend == "RISING" and ctx.dollar_trend != "STRONG":
                return CrossAssetVerdict(True, False, +boost, "Oil rising + Dollar non-strong conferma BUY GBPUSD")
            if ctx.oil_trend == "FALLING" and ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(False, True, -penalty, "Oil falling + Dollar strong contraddice BUY GBPUSD")
        else:
            if ctx.oil_trend == "FALLING" or ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(True, False, +boost, "Oil falling/Dollar strong conferma SELL GBPUSD")
            if ctx.oil_trend == "RISING" and ctx.dollar_trend == "WEAK":
                return CrossAssetVerdict(False, True, -penalty, "Oil rising + Dollar weak contraddice SELL GBPUSD")
        return CrossAssetVerdict(False, False, 0.0, "GBPUSD: contesto neutro")

    def _check_audusd(self, direction: str, ctx: IntermarketContext) -> CrossAssetVerdict:
        """AUD/NZD = commodity ccy: Gold rising + Dollar weak conferma BUY."""
        boost = self.cfg.CROSS_ASSET_BOOST
        penalty = self.cfg.CROSS_ASSET_PENALTY

        if direction == "BUY":
            if ctx.gold_trend == "RISING" and ctx.dollar_trend == "WEAK":
                return CrossAssetVerdict(True, False, +boost, "Gold rising + Dollar weak conferma BUY commodity ccy")
            if ctx.gold_trend == "FALLING" and ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(False, True, -penalty, "Gold falling + Dollar strong contraddice BUY commodity ccy")
        else:
            if ctx.gold_trend == "FALLING" or ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(True, False, +boost, "Gold falling/Dollar strong conferma SELL commodity ccy")
            if ctx.gold_trend == "RISING" and ctx.dollar_trend == "WEAK":
                return CrossAssetVerdict(False, True, -penalty, "Gold rising + Dollar weak contraddice SELL commodity ccy")
        return CrossAssetVerdict(False, False, 0.0, "Commodity ccy: contesto neutro")

    def _check_usdcad(self, direction: str, ctx: IntermarketContext) -> CrossAssetVerdict:
        """USD/CAD: correlazione inversa con Oil. Oil rising = CAD strong = USDCAD down."""
        boost = self.cfg.CROSS_ASSET_BOOST
        penalty = self.cfg.CROSS_ASSET_PENALTY

        if direction == "BUY":
            # BUY USDCAD = USD up vs CAD: serve Dollar strong + Oil falling
            if ctx.oil_trend == "FALLING" and ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(True, False, +boost, "Oil falling + Dollar strong conferma BUY USDCAD")
            if ctx.oil_trend == "RISING" and ctx.dollar_trend == "WEAK":
                return CrossAssetVerdict(False, True, -penalty, "Oil rising + Dollar weak contraddice BUY USDCAD")
        else:  # SELL USDCAD
            if ctx.oil_trend == "RISING" and ctx.dollar_trend != "STRONG":
                return CrossAssetVerdict(True, False, +boost, "Oil rising + Dollar non-strong conferma SELL USDCAD")
            if ctx.oil_trend == "FALLING" and ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(False, True, -penalty, "Oil falling + Dollar strong contraddice SELL USDCAD")
        return CrossAssetVerdict(False, False, 0.0, "USDCAD: contesto neutro")

    def _check_usdjpy(
        self,
        direction: str,
        ctx: IntermarketContext,
        regime: RegimeState | None,
    ) -> CrossAssetVerdict:
        """USD/JPY = carry trade / risk barometer. Risk-on + stocks up = JPY weak = USDJPY up."""
        boost = self.cfg.CROSS_ASSET_BOOST
        penalty = self.cfg.CROSS_ASSET_PENALTY
        reg = regime.regime if regime else "NEUTRAL"

        if direction == "BUY":
            if reg == "RISK_ON":
                return CrossAssetVerdict(True, False, +boost, "RISK_ON conferma BUY USDJPY")
            if reg == "RISK_OFF" or ctx.gold_trend == "RISING":
                return CrossAssetVerdict(False, True, -penalty, "Risk-off/Gold rising contraddice BUY USDJPY")
        else:  # SELL USDJPY
            if reg == "RISK_OFF" or ctx.gold_trend == "RISING":
                return CrossAssetVerdict(True, False, +boost, "RISK_OFF/Gold rising conferma SELL USDJPY")
            if reg == "RISK_ON":
                return CrossAssetVerdict(False, True, -penalty, "RISK_ON contraddice SELL USDJPY")
        return CrossAssetVerdict(False, False, 0.0, "USDJPY: contesto neutro")

    def _check_usdchf(self, direction: str, ctx: IntermarketContext) -> CrossAssetVerdict:
        """USD/CHF = inverso EUR/USD. Dollar STRONG + Gold FLAT/FALLING = BUY USDCHF."""
        boost = self.cfg.CROSS_ASSET_BOOST
        penalty = self.cfg.CROSS_ASSET_PENALTY

        if direction == "BUY":
            if ctx.dollar_trend == "STRONG" and ctx.gold_trend != "RISING":
                return CrossAssetVerdict(True, False, +boost, "Dollar STRONG + Gold non-rising conferma BUY USDCHF")
            if ctx.dollar_trend == "WEAK" and ctx.gold_trend == "RISING":
                return CrossAssetVerdict(False, True, -penalty, "Dollar WEAK + Gold rising contraddice BUY USDCHF")
        else:
            if ctx.dollar_trend == "WEAK" or ctx.gold_trend == "RISING":
                return CrossAssetVerdict(True, False, +boost, "Dollar WEAK/Gold rising conferma SELL USDCHF")
            if ctx.dollar_trend == "STRONG" and ctx.gold_trend != "RISING":
                return CrossAssetVerdict(False, True, -penalty, "Dollar STRONG contraddice SELL USDCHF")
        return CrossAssetVerdict(False, False, 0.0, "USDCHF: contesto neutro")

    def _check_gold(self, direction: str, ctx: IntermarketContext) -> CrossAssetVerdict:
        """XAUUSD: Dollar inverso. Dollar WEAK = Gold UP."""
        boost = self.cfg.CROSS_ASSET_BOOST
        penalty = self.cfg.CROSS_ASSET_PENALTY

        if direction == "BUY":
            if ctx.dollar_trend == "WEAK":
                return CrossAssetVerdict(True, False, +boost, "Dollar WEAK conferma BUY Gold")
            if ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(False, True, -penalty, "Dollar STRONG contraddice BUY Gold")
        else:
            if ctx.dollar_trend == "STRONG":
                return CrossAssetVerdict(True, False, +boost, "Dollar STRONG conferma SELL Gold")
            if ctx.dollar_trend == "WEAK":
                return CrossAssetVerdict(False, True, -penalty, "Dollar WEAK contraddice SELL Gold")
        return CrossAssetVerdict(False, False, 0.0, "Gold: Dollar NEUTRAL")
