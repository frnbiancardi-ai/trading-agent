"""Fibonacci Multi-Target System (fase 18.6 — Probo).

Calcola target multipli Fibonacci (38.2%, 50%, 61.8%, 100%, 161.8%) basati su
recent swing high/low. Sostituzione/integrazione del TP fisso.

Logica Probo:
- Estensione 1.0 = 1:1 of swing (target principale)
- Estensione 1.618 = target esteso
- Retracement 38.2% / 50% / 61.8% per partial close progressivi
"""
import logging

from config import Config
from models import FibonacciTargets


# Livelli Fibonacci canonici
FIB_RETRACEMENTS = {
    "382": 0.382,
    "500": 0.500,
    "618": 0.618,
    "786": 0.786,
}

FIB_EXTENSIONS = {
    "100": 1.000,
    "127": 1.272,
    "161": 1.618,
    "200": 2.000,
    "261": 2.618,
}


def compute_fibonacci_targets(
    entry: float,
    stop_loss: float,
    direction: str,
    recent_swing_high: float | None = None,
    recent_swing_low: float | None = None,
) -> FibonacciTargets:
    """Calcola target Fibonacci.

    Args:
        entry: prezzo entrata
        stop_loss: prezzo SL (definisce risk = |entry - sl|)
        direction: "BUY" o "SELL"
        recent_swing_high: massimo recente (swing). Se None usa entry+2*risk
        recent_swing_low: minimo recente. Se None usa entry-2*risk

    Returns:
        FibonacciTargets con tp_382, tp_500, tp_618, tp_100, tp_161, recommended_primary_tp
    """
    direction = direction.upper()
    risk = abs(entry - stop_loss)

    if risk <= 0:
        return FibonacciTargets()

    # Default swing range = 2x risk se non fornito
    if direction == "BUY":
        swing_high = recent_swing_high if recent_swing_high else entry + 2 * risk
        swing_low = recent_swing_low if recent_swing_low else stop_loss
        swing_range = swing_high - swing_low
        if swing_range <= 0:
            swing_range = 2 * risk
            swing_low = entry - risk
            swing_high = entry + risk

        # Per BUY: targets sopra entry, calcolati da swing_low
        tp_382 = swing_low + swing_range * FIB_RETRACEMENTS["382"]
        tp_500 = swing_low + swing_range * FIB_RETRACEMENTS["500"]
        tp_618 = swing_low + swing_range * FIB_RETRACEMENTS["618"]
        tp_100 = swing_high
        tp_161 = swing_low + swing_range * FIB_EXTENSIONS["161"]

        # Filtra targets sopra entry (sotto entry = già passati)
        tp_382 = max(tp_382, entry + 0.5 * risk)
        tp_500 = max(tp_500, entry + 1.0 * risk)
        tp_618 = max(tp_618, entry + 1.5 * risk)

    else:  # SELL
        swing_high = recent_swing_high if recent_swing_high else stop_loss
        swing_low = recent_swing_low if recent_swing_low else entry - 2 * risk
        swing_range = swing_high - swing_low
        if swing_range <= 0:
            swing_range = 2 * risk
            swing_high = entry + risk
            swing_low = entry - risk

        # Per SELL: targets sotto entry, calcolati da swing_high
        tp_382 = swing_high - swing_range * FIB_RETRACEMENTS["382"]
        tp_500 = swing_high - swing_range * FIB_RETRACEMENTS["500"]
        tp_618 = swing_high - swing_range * FIB_RETRACEMENTS["618"]
        tp_100 = swing_low
        tp_161 = swing_high - swing_range * FIB_EXTENSIONS["161"]

        tp_382 = min(tp_382, entry - 0.5 * risk)
        tp_500 = min(tp_500, entry - 1.0 * risk)
        tp_618 = min(tp_618, entry - 1.5 * risk)

    # Primary TP raccomandato = tp_618 (Probo: livello migliore reward/probability)
    primary = tp_618

    return FibonacciTargets(
        tp_382=tp_382,
        tp_500=tp_500,
        tp_618=tp_618,
        tp_100=tp_100,
        tp_161=tp_161,
        recommended_primary_tp=primary,
    )


def find_recent_swings(
    bars: list[dict],
    lookback: int = 50,
) -> tuple[float | None, float | None]:
    """Estrae swing high/low recenti da bars OHLC.

    Returns: (swing_high, swing_low)
    """
    if not bars:
        return None, None
    window = bars[-lookback:] if len(bars) > lookback else bars
    highs = [b.get("high", b.get("close")) for b in window]
    lows = [b.get("low", b.get("close")) for b in window]
    if not highs or not lows:
        return None, None
    return max(highs), min(lows)


def compute_partial_close_levels(
    targets: FibonacciTargets,
    levels_csv: str = "0.382,0.618",
) -> list[float]:
    """Mappa CSV livelli (es. '0.382,0.618') a prezzi target."""
    out: list[float] = []
    for token in levels_csv.split(","):
        token = token.strip()
        if token in ("0.382", "0.38", "382"):
            out.append(targets.tp_382)
        elif token in ("0.5", "0.50", "0.500", "500"):
            out.append(targets.tp_500)
        elif token in ("0.618", "0.62", "618"):
            out.append(targets.tp_618)
        elif token in ("1.0", "1.00", "100"):
            out.append(targets.tp_100)
        elif token in ("1.618", "1.62", "161"):
            out.append(targets.tp_161)
    return out


class FibonacciTargetEngine:
    """Wrapper engine con config flag."""

    def __init__(self, cfg: Config, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.log = logger or logging.getLogger(__name__)

    def compute(
        self,
        entry: float,
        stop_loss: float,
        direction: str,
        bars: list[dict] | None = None,
    ) -> FibonacciTargets:
        """Calcola targets usando swings da bars se forniti."""
        if not self.cfg.ENABLE_FIBONACCI_TARGETS:
            # Fallback: target singolo a 2:1 RR
            risk = abs(entry - stop_loss)
            if direction.upper() == "BUY":
                tp = entry + 2 * risk
            else:
                tp = entry - 2 * risk
            return FibonacciTargets(
                tp_382=tp, tp_500=tp, tp_618=tp,
                tp_100=tp, tp_161=tp, recommended_primary_tp=tp,
            )

        swing_high = swing_low = None
        if bars:
            swing_high, swing_low = find_recent_swings(bars, lookback=50)

        return compute_fibonacci_targets(
            entry, stop_loss, direction, swing_high, swing_low
        )
