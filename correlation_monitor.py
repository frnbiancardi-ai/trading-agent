"""Correlation Monitor (fase 18.3 — Probo + Murphy).

Calcola rolling Pearson correlation tra coppie chiave e segnala divergenze.
Coppie monitorate (correlation storica attesa):
- EUR/USD vs USD/CHF: -0.85
- EUR/USD vs GBP/USD: +0.60
- AUD/USD vs Gold (XAUUSD): +0.70
- USD/CAD vs Oil (USOIL): -0.65
- USD/JPY vs Stock proxy: +0.50
"""
import logging
import math
from dataclasses import dataclass

from config import Config


# Correlazioni storiche attese (da Probo + Murphy)
EXPECTED_CORRELATIONS: dict[tuple[str, str], float] = {
    ("EURUSD", "USDCHF"): -0.85,
    ("EURUSD", "GBPUSD"): +0.60,
    ("AUDUSD", "XAUUSD"): +0.70,
    ("USDCAD", "USOIL"): -0.65,
    ("USDJPY", "SPX500"): +0.50,
}


@dataclass
class CorrelationStat:
    """Stato correlazione tra coppia di simboli."""
    symbol_a: str
    symbol_b: str
    current_corr: float
    expected_corr: float
    deviation: float  # |current - expected|
    is_diverging: bool
    note: str = ""


def compute_pearson(series_a: list[float], series_b: list[float]) -> float | None:
    """Pearson correlation coefficient. None se input invalido."""
    n = len(series_a)
    if n != len(series_b) or n < 2:
        return None

    mean_a = sum(series_a) / n
    mean_b = sum(series_b) / n

    cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(series_a, series_b))
    var_a = sum((a - mean_a) ** 2 for a in series_a)
    var_b = sum((b - mean_b) ** 2 for b in series_b)

    denom = math.sqrt(var_a * var_b)
    if denom == 0:
        return None
    return cov / denom


def compute_rolling_correlation(
    series_a: list[float],
    series_b: list[float],
    period: int = 20,
) -> list[float | None]:
    """Rolling Pearson correlation. Output stessa lunghezza input.

    Primi (period-1) valori = None.
    """
    n = len(series_a)
    if n != len(series_b):
        return [None] * n

    out: list[float | None] = []
    for i in range(n):
        if i < period - 1:
            out.append(None)
            continue
        window_a = series_a[i - period + 1 : i + 1]
        window_b = series_b[i - period + 1 : i + 1]
        out.append(compute_pearson(window_a, window_b))
    return out


def detect_correlation_divergence(
    current_corr: float,
    expected_corr: float,
    threshold: float = 0.5,
) -> bool:
    """True se |current_corr| < threshold * |expected_corr| OR segno opposto.

    threshold=0.5 → correlazione caduta di metà rispetto all'atteso.
    """
    if abs(expected_corr) < 0.01:
        return False
    # Segno opposto = divergenza forte
    if (expected_corr > 0 and current_corr < 0) or (expected_corr < 0 and current_corr > 0):
        return True
    return abs(current_corr) < threshold * abs(expected_corr)


class CorrelationMonitor:
    """Monitor correlazioni rolling tra coppie chiave."""

    def __init__(
        self,
        cfg: Config,
        mt5_client,
        logger: logging.Logger | None = None,
    ):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger or logging.getLogger(__name__)

    def check_pair(
        self,
        symbol_a: str,
        symbol_b: str,
        timeframe: str | None = None,
        period: int | None = None,
    ) -> CorrelationStat | None:
        """Calcola correlation per coppia. None se dati insufficienti."""
        if not self.cfg.ENABLE_CORRELATION_MONITOR:
            return None

        tf = timeframe or self.cfg.INTERMARKET_TIMEFRAME
        per = period or self.cfg.CORRELATION_PERIOD
        lookback = max(per * 3, 60)

        try:
            bars_a = self.mt5.get_ohlc(symbol_a, tf, lookback)
            bars_b = self.mt5.get_ohlc(symbol_b, tf, lookback)
        except Exception as exc:
            self.log.warning("Correlation fetch failed (%s/%s): %s", symbol_a, symbol_b, exc)
            return None

        if not bars_a or not bars_b:
            return None

        # Allinea lunghezza (prendi minimo)
        min_len = min(len(bars_a), len(bars_b))
        if min_len < per:
            return None

        closes_a = [b["close"] for b in bars_a[-min_len:]]
        closes_b = [b["close"] for b in bars_b[-min_len:]]

        current = compute_pearson(closes_a[-per:], closes_b[-per:])
        if current is None:
            return None

        key = (symbol_a, symbol_b)
        expected = EXPECTED_CORRELATIONS.get(key, 0.0)

        is_div = detect_correlation_divergence(
            current, expected, self.cfg.CORRELATION_DIVERGENCE_THRESHOLD
        )

        note = ""
        if is_div:
            note = f"divergenza_correlation (atteso={expected:.2f}, attuale={current:.2f})"

        return CorrelationStat(
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            current_corr=current,
            expected_corr=expected,
            deviation=abs(current - expected),
            is_diverging=is_div,
            note=note,
        )

    def check_all_known_pairs(self) -> list[CorrelationStat]:
        """Calcola correlation su tutte le coppie note."""
        results: list[CorrelationStat] = []
        for (a, b) in EXPECTED_CORRELATIONS.keys():
            stat = self.check_pair(a, b)
            if stat is not None:
                results.append(stat)
        return results
