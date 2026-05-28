"""Indicatori multi-timeframe: trend strength (Wave 0) + align H4/H1/M15 (Wave 3).

INDIC-13 (`align`): coerenza sign-agreement EMA50-slope su H4/H1/M15, score per barra
M15 in {0.0, 0.33, 0.66, 1.0} (D-13/D-14). Slope = sign(EMA50[i] - EMA50[i-N]) con
dead-zone |delta|/|EMA50| < 1e-5 → dir=0 (Pitfall 7). Caller responsabile dello
slicing di ciascuno stream a barre chiuse <= timestamp barra M15 corrente.

`calculate_trend_strength` (Wave 0) preservato verbatim — usato da `strategy.py:11`.
"""
from __future__ import annotations

from dataclasses import dataclass

from indicators.trend import ema


@dataclass
class MTFAlignmentResult:
    """Risultato `align()` length-N (N = len(streams['M15']))."""

    score: list[float | None]
    h4_dir: list[int | None]
    h1_dir: list[int | None]
    m15_dir: list[int | None]


def _compute_dirs(
    bars: list[dict],
    ema_period: int = 50,
    slope_lookback: int = 3,
    dead_zone: float = 1e-5,
) -> list[int | None]:
    """Direzione per barra: sign(EMA[i] - EMA[i-N]) con dead-zone (Pitfall 7).

    Ritorna `None` durante il warmup (i < ema_period-1+slope_lookback o EMA non disponibile),
    `0` se |delta|/|EMA[i]| < dead_zone (slope sostanzialmente nulla → no-trend),
    `+1` se delta > 0 (trend up), `-1` se delta < 0 (trend down).
    """
    if not bars:
        return []
    closes = [float(b["close"]) for b in bars]
    ema_vals = ema(closes, ema_period)
    n = len(bars)
    dirs: list[int | None] = [None] * n
    for i in range(slope_lookback, n):
        cur = ema_vals[i]
        prev = ema_vals[i - slope_lookback]
        if cur is None or prev is None or cur == 0:
            continue
        delta = cur - prev
        if abs(delta) / abs(cur) < dead_zone:
            dirs[i] = 0
        elif delta > 0:
            dirs[i] = 1
        else:
            dirs[i] = -1
    return dirs


def align(
    streams: dict[str, list[dict]],
    ema_period: int = 50,
    slope_lookback: int = 3,
) -> MTFAlignmentResult:
    """INDIC-13: coerenza multi-TF via sign-agreement EMA50-slope su H4/H1/M15.

    Args:
        streams: dict con chiavi obbligatorie 'H4', 'H1', 'M15' (D-13). Ciascun
            valore è una lista di bar dict con almeno chiavi 'time' (unix sec UTC) e
            'close'. Caller responsabile di passare bar chiuse <= timestamp barra
            M15 corrente (no future leakage — D-13).
        ema_period: periodo EMA per la stima del trend per stream (default 50).
        slope_lookback: bar di look-back N per la slope (default 3, Pitfall 7).

    Returns:
        MTFAlignmentResult length-len(streams['M15']):
        - `score[i]` ∈ {None, 0.0, 0.33, 0.67, 1.0}: frazione di accordi (D-14).
          M15 è l'ancora: agreements = numero di {h4_dir, h1_dir, m15_dir} == m15_dir.
        - `m15_dir[i]`, `h4_dir[i]`, `h1_dir[i]` ∈ {None, -1, 0, +1}: direzioni
          allineate al timestamp di m15[i] (per H4/H1, l'ultima barra con time <= m15[i].time).
        - Warmup: primi ~ema_period+slope_lookback indici tipicamente None.

    Raises:
        ValueError: se manca una delle chiavi richieste 'H4', 'H1', 'M15'.
    """
    for required in ("H4", "H1", "M15"):
        if required not in streams:
            raise ValueError(
                f"streams deve contenere chiave '{required}' (D-13)"
            )
    h4 = streams["H4"]
    h1 = streams["H1"]
    m15 = streams["M15"]

    h4_dirs = _compute_dirs(h4, ema_period, slope_lookback)
    h1_dirs = _compute_dirs(h1, ema_period, slope_lookback)
    m15_dirs = _compute_dirs(m15, ema_period, slope_lookback)

    n = len(m15)
    score: list[float | None] = [None] * n
    h4_at_m15: list[int | None] = [None] * n
    h1_at_m15: list[int | None] = [None] * n

    h4_times = [int(b["time"]) for b in h4]
    h1_times = [int(b["time"]) for b in h1]

    for i in range(n):
        t = int(m15[i]["time"])
        # Cerca all'indietro l'ultima barra H4/H1 con time <= t
        j4: int | None = None
        for j in range(len(h4_times) - 1, -1, -1):
            if h4_times[j] <= t:
                j4 = j
                break
        j1: int | None = None
        for j in range(len(h1_times) - 1, -1, -1):
            if h1_times[j] <= t:
                j1 = j
                break

        d_m15 = m15_dirs[i]
        d_h4 = h4_dirs[j4] if j4 is not None else None
        d_h1 = h1_dirs[j1] if j1 is not None else None
        h4_at_m15[i] = d_h4
        h1_at_m15[i] = d_h1

        if d_m15 is None or d_h4 is None or d_h1 is None:
            continue

        agree = sum(1 for d in (d_m15, d_h4, d_h1) if d == d_m15)
        score[i] = round(agree / 3.0, 2)

    return MTFAlignmentResult(
        score=score,
        h4_dir=h4_at_m15,
        h1_dir=h1_at_m15,
        m15_dir=m15_dirs,
    )


def calculate_trend_strength(
    bars: list[dict],
    sma_fast: float | None,
    sma_slow: float | None,
    coherence_window: int = 10,
) -> float:
    """Forza trend in [0.0, 1.0].

    Combina:
    - separazione normalizzata tra SMA veloce e SMA lenta (50%)
    - coerenza direzionale: frazione di close consecutivi che seguono la pendenza SMA (50%)
    """
    if sma_fast is None or sma_slow is None or sma_slow == 0:
        return 0.0
    if not bars:
        return 0.0

    separation = abs(sma_fast - sma_slow) / abs(sma_slow)
    sep_score = min(separation / 0.005, 1.0)

    closes = [b["close"] for b in bars[-coherence_window:]]
    if len(closes) < 2:
        coherence_score = 0.0
    else:
        direction = 1 if sma_fast > sma_slow else -1
        moves = 0
        aligned = 0
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            if diff == 0:
                continue
            moves += 1
            if (diff > 0 and direction > 0) or (diff < 0 and direction < 0):
                aligned += 1
        coherence_score = aligned / moves if moves else 0.0

    return round(0.5 * sep_score + 0.5 * coherence_score, 4)
