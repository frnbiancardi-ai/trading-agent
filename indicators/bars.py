"""Indicatori bar-level: rapporto risk/reward + NR4/NR7/Inside/Boomer + Closing Score.

- `calculate_risk_reward` (Wave 0) preservato invariato.
- `narrow_range` (INDIC-10): NR4/NR7 canonici Crabel + Inside Bar + Boomer (A2:
  2+ inside consecutivi dentro una finestra NR4/NR7).
- `closing_score` (INDIC-11, Defendi): posizione del close nel range
  `(close - low) / (high - low) * 100`; `None` quando `high == low`.

Funzioni pure: niente pandas/ta-lib/pandas_ta a runtime; output length-N
con `None` per le posizioni di warmup.
"""
from __future__ import annotations

from dataclasses import dataclass


def calculate_risk_reward(entry: float, sl: float, tp: float) -> float:
    """Rapporto reward/risk. 0.0 se SL == entry (rischio nullo non valido)."""
    risk = abs(entry - sl)
    if risk == 0:
        return 0.0
    reward = abs(tp - entry)
    return round(reward / risk, 4)


@dataclass
class NRResult:
    """Risultato di `narrow_range`: 4 serie length-N di booleani con `None` warmup.

    - `nr4[i]`: True se la barra i ha range strettamente minore di ciascuna delle
      ultime 3 barre (Crabel canonical, finestra di 4). `None` per i<3.
    - `nr7[i]`: True se la barra i ha range strettamente minore di ciascuna delle
      ultime 6 barre. `None` per i<6.
    - `inside[i]`: True se `high[i] <= high[i-1] AND low[i] >= low[i-1]`.
      `None` per i==0.
    - `boomer[i]`: True se `inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])`
      (Assumption A2 RESEARCH). `None` per i<2 o per warmup di inside/nr.
    """

    nr4: list[bool | None]
    nr7: list[bool | None]
    inside: list[bool | None]
    boomer: list[bool | None]


@dataclass
class ClosingScoreResult:
    """Risultato di `closing_score`: serie length-N di float in [0,100] o `None`.

    `None` indica una barra degenere con `high == low` (range nullo) per cui la
    posizione del close non è definita.
    """

    score: list[float | None]


def narrow_range(bars: list[dict]) -> NRResult:
    """NR4/NR7 + Inside Bar + Boomer (Crabel canonical + Assumption A2).

    Definizioni (RESEARCH §Open-Q4):
    - NR4 a i: `range(i) < range(j)` per j ∈ {i-1, i-2, i-3}, dove `range = high - low`.
    - NR7 a i: `range(i) < range(j)` per j ∈ {i-1..i-6}.
    - Inside a i: `high[i] <= high[i-1] AND low[i] >= low[i-1]` (i.e. `<=` e `>=`).
    - Boomer a i: `inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])` (A2).

    Warmup: nr4 None per i<3, nr7 None per i<6, inside None per i==0,
    boomer None per i<2 o quando inside[i] o inside[i-1] sono None.

    Pura: leakage-free per costruzione (ogni bar usa solo bar precedenti).
    """
    n = len(bars)
    nr4: list[bool | None] = [None] * n
    nr7: list[bool | None] = [None] * n
    inside: list[bool | None] = [None] * n
    boomer: list[bool | None] = [None] * n
    if n == 0:
        return NRResult(nr4=nr4, nr7=nr7, inside=inside, boomer=boomer)
    ranges = [float(b["high"]) - float(b["low"]) for b in bars]
    # NR4: i confrontato con i-1, i-2, i-3
    for i in range(3, n):
        nr4[i] = all(ranges[i] < ranges[j] for j in range(i - 3, i))
    # NR7: i confrontato con i-1..i-6
    for i in range(6, n):
        nr7[i] = all(ranges[i] < ranges[j] for j in range(i - 6, i))
    # Inside bar
    for i in range(1, n):
        inside[i] = (
            float(bars[i]["high"]) <= float(bars[i - 1]["high"])
            and float(bars[i]["low"]) >= float(bars[i - 1]["low"])
        )
    # Boomer: inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])
    for i in range(2, n):
        if inside[i] is None or inside[i - 1] is None:
            continue
        nr_part = (nr4[i] is True) or (nr7[i] is True)
        boomer[i] = bool(inside[i] and inside[i - 1] and nr_part)
    return NRResult(nr4=nr4, nr7=nr7, inside=inside, boomer=boomer)


def closing_score(bars: list[dict]) -> ClosingScoreResult:
    """Closing Score (Defendi): `(close - low) / (high - low) * 100`.

    Range atteso ∈ [0, 100]. Per barre degeneri (`high == low`) il valore è
    `None` perché il rapporto non è definito (range nullo).

    Pura: ogni bar è indipendente dalle altre → leakage-free per costruzione.
    """
    n = len(bars)
    score: list[float | None] = [None] * n
    for i, b in enumerate(bars):
        h = float(b["high"])
        l = float(b["low"])
        c = float(b["close"])
        rng = h - l
        if rng == 0:
            score[i] = None
        else:
            score[i] = (c - l) / rng * 100.0
    return ClosingScoreResult(score=score)
