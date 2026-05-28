"""Helper privati condivisi dai sottomoduli del pacchetto indicators.

- `_wilder_rsi`: chiusura della formula RSI di Wilder a partire da avg_gain/loss.
- `_wilder_smooth`: smoothing RMA generalizzato (alpha=1/period, seed=SMA del primo periodo).
  Equivalente a pandas-ta `rma()` (mamode='rma') — parity 1e-6 garantita.
- `_last_valid`: estrae l'ultimo valore non-None da una serie con warmup iniziali a None.
- `_session_id_ny17`: bucketing di sessione FX ancorata alle 17:00 New York
  (DST-aware via `zoneinfo`). Bar a/dopo 17:00 NY appartengono al giorno successivo.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")


def _wilder_rsi(avg_gain: float, avg_loss: float) -> float:
    """Chiude la formula RSI di Wilder dato avg_gain/avg_loss correnti."""
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _wilder_smooth(values: list[float], period: int) -> list[float | None]:
    """Smoothing Wilder/RMA generalizzato.

    alpha = 1/period, seed = media (SMA) dei primi `period` valori.
    Posizioni < period-1 → None (warmup).
    Equivalente a pandas-ta `rma(length=period)` per garantire parity 1e-6 nei test.
    """
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, n):
        prev = out[i - 1]
        out[i] = (prev * (period - 1) + values[i]) / period  # type: ignore[operator]
    return out


def _last_valid(series: list[float | None]) -> float | None:
    """Ritorna l'ultimo valore non-None della serie, o None se tutto None."""
    for v in reversed(series):
        if v is not None:
            return v
    return None


def _session_id_ny17(ts_utc: datetime) -> date:
    """Bucket di sessione FX ancorato alle 17:00 New York.

    Una bar appartiene alla sessione che termina alle 17:00 NY del giorno restituito.
    Bar al-or-dopo 17:00 NY appartengono alla sessione del giorno successivo.
    DST gestito automaticamente da `zoneinfo` (winter NY-17 == 22:00 UTC,
    summer NY-17 == 21:00 UTC).
    """
    ny = ts_utc.astimezone(_NY)
    if ny.hour >= 17:
        return (ny + timedelta(days=1)).date()
    return ny.date()
