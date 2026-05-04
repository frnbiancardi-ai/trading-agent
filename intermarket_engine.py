"""Intermarket Context Engine (fase 18.1 — Murphy).

Analizza Dollar, Gold, Oil e Bond Yields su H4/Daily per determinare
il contesto intermarket. Principi chiave:
- Dollar ↔ Commodities: correlazione inversa
- Bond Yields LEAD currencies/stocks
- Gold rising + Dollar falling = flight to safety (risk-off)
- Oil rising + Dollar falling = economic growth (risk-on)
"""
import logging
from datetime import datetime

from config import Config
from indicators import sma
from models import IntermarketContext


def _last_valid(series: list) -> float | None:
    for v in reversed(series):
        if v is not None:
            return v
    return None


def _compute_trend_from_sma(
    closes: list[float],
    period_fast: int = 20,
    period_slow: int = 50,
) -> str:
    """Determina trend da SMA20/SMA50 alignment.

    STRONG/RISING: close > SMA20 > SMA50
    WEAK/FALLING: close < SMA20 < SMA50
    NEUTRAL/FLAT: mixed
    """
    if len(closes) < period_slow:
        return "NEUTRAL"

    sma_fast = sma(closes, period_fast)
    sma_slow = sma(closes, period_slow)

    fast_val = _last_valid(sma_fast)
    slow_val = _last_valid(sma_slow)
    last_close = closes[-1] if closes else None

    if None in (fast_val, slow_val, last_close):
        return "NEUTRAL"

    if last_close > fast_val > slow_val:
        return "RISING"
    elif last_close < fast_val < slow_val:
        return "FALLING"
    return "FLAT"


class IntermarketEngine:
    """Engine per calcolo contesto intermarket (Murphy cap 1, 11-15)."""

    def __init__(
        self,
        cfg: Config,
        mt5_client,
        logger: logging.Logger | None = None,
    ):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger or logging.getLogger(__name__)

    def get_context(self) -> IntermarketContext:
        """Fetch e analizza tutti gli asset intermarket.

        Returns IntermarketContext con trend per Dollar, Gold, Oil.
        """
        cfg = self.cfg

        if not cfg.ENABLE_INTERMARKET_FILTER:
            return IntermarketContext(
                dollar_trend="NEUTRAL",
                gold_trend="FLAT",
                oil_trend="FLAT",
                timestamp=datetime.now(),
            )

        timeframe = cfg.INTERMARKET_TIMEFRAME
        lookback = cfg.INTERMARKET_LOOKBACK_BARS

        # Dollar trend (via proxy inverso EUR/USD: EUR up = Dollar weak)
        dollar_trend = self._compute_dollar_trend(timeframe, lookback)

        # Gold trend (XAUUSD)
        gold_trend = self._compute_asset_trend("XAUUSD", timeframe, lookback)

        # Oil trend (USOIL o primo simbolo in INTERMARKET_SYMBOLS)
        oil_symbol = self._find_oil_symbol()
        oil_trend = self._compute_asset_trend(oil_symbol, timeframe, lookback)

        return IntermarketContext(
            dollar_trend=dollar_trend,
            gold_trend=gold_trend,
            oil_trend=oil_trend,
            timestamp=datetime.now(),
        )

    def _compute_dollar_trend(self, timeframe: str, lookback: int) -> str:
        """Calcola trend Dollar via proxy inverso EUR/USD.

        EUR/USD rising = Dollar WEAK, EUR/USD falling = Dollar STRONG.
        """
        proxy = self.cfg.DXY_PROXY_SYMBOL
        try:
            bars = self.mt5.get_ohlc(proxy, timeframe, lookback)
        except Exception as exc:
            self.log.warning("Dollar proxy fetch failed (%s): %s", proxy, exc)
            return "NEUTRAL"

        if not bars or len(bars) < 50:
            return "NEUTRAL"

        closes = [b["close"] for b in bars]
        trend = _compute_trend_from_sma(closes)

        # Inversione: EUR rising = Dollar weak
        if trend == "RISING":
            return "WEAK"
        elif trend == "FALLING":
            return "STRONG"
        return "NEUTRAL"

    def _compute_asset_trend(self, symbol: str, timeframe: str, lookback: int) -> str:
        """Calcola trend generico per Gold/Oil/altro asset."""
        try:
            bars = self.mt5.get_ohlc(symbol, timeframe, lookback)
        except Exception as exc:
            self.log.warning("Asset trend fetch failed (%s): %s", symbol, exc)
            return "FLAT"

        if not bars or len(bars) < 50:
            return "FLAT"

        closes = [b["close"] for b in bars]
        return _compute_trend_from_sma(closes)

    def _find_oil_symbol(self) -> str:
        """Trova simbolo Oil dal config o default."""
        symbols = self.cfg.INTERMARKET_SYMBOLS
        oil_candidates = ["USOIL", "WTI", "XTIUSD", "CL"]
        for sym in symbols:
            if any(c in sym.upper() for c in oil_candidates):
                return sym
        return "USOIL"  # default
