"""Indicatori di volume: avg_volume (Wave 0) + VWAP intraday/anchored (Wave 2 — INDIC-07).

VWAP intraday: cumula `(high+low+close)/3 * volume` per sessione FX (NY-17 reset)
e divide per il volume cumulato. DST-aware via `_session_id_ny17` (winter
22:00 UTC, summer 21:00 UTC).

VWAP anchored: cumula da prima barra con `bar.ts >= anchor_ts` (Pitfall 3 di RESEARCH).
`anchor_ts` MUST essere tz-aware; barre prima dell'ancora hanno tutti i campi None.

Convenzione (D-04..D-06): ritorna `VWAPResult` dataclass-of-list lunghezza N.
`vwap[i] = None` quando `cumulative_v[i] == 0` (no div-by-zero).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from indicators._helpers import _session_id_ny17


@dataclass
class VWAPResult:
    """Risultato VWAP: serie length-N di vwap, cumulative_pv, cumulative_v."""
    vwap: list[float | None]
    cumulative_pv: list[float | None]
    cumulative_v: list[float | None]


def avg_volume(bars: list[dict], period: int = 20) -> float:
    """Media tick_volume sulle ultime `period` barre. 0.0 se dati assenti."""
    if not bars or period <= 0:
        return 0.0
    sub = bars[-period:]
    vols = [b.get("tick_volume", b.get("volume", 0)) or 0 for b in sub]
    if not vols:
        return 0.0
    return sum(vols) / len(vols)


def _bar_volume(bar: dict) -> float:
    """Estrae il volume della bar: preferisce tick_volume, fallback volume, default 0.

    Coerente con il pattern di `avg_volume` (handles None via `or 0`).
    """
    return float(bar.get("tick_volume", bar.get("volume", 0)) or 0)


def _typical_price(bar: dict) -> float:
    """Prezzo tipico di bar = (high + low + close) / 3 (formula VWAP standard)."""
    return (float(bar["high"]) + float(bar["low"]) + float(bar["close"])) / 3.0


def vwap_intraday(bars: list[dict]) -> VWAPResult:
    """VWAP intraday con reset al boundary NY-17 (D-10).

    Per ogni bar:
      - calcola session-id via `_session_id_ny17(ts_utc)` (DST-aware)
      - se cambia rispetto al precedente, resetta i cumulativi a 0
      - accumula `tp * v` e `v`, poi vwap = cum_pv / cum_v

    `vwap[i] = None` quando `cumulative_v[i] == 0` (es. tutta la sessione a volume zero).
    """
    n = len(bars)
    vwap: list[float | None] = [None] * n
    cum_pv: list[float | None] = [None] * n
    cum_v: list[float | None] = [None] * n
    current_session = None
    running_pv = 0.0
    running_v = 0.0
    for i, b in enumerate(bars):
        ts = datetime.fromtimestamp(int(b["time"]), tz=timezone.utc)
        sid = _session_id_ny17(ts)
        if sid != current_session:
            current_session = sid
            running_pv = 0.0
            running_v = 0.0
        tp = _typical_price(b)
        v = _bar_volume(b)
        running_pv += tp * v
        running_v += v
        cum_pv[i] = running_pv
        cum_v[i] = running_v
        vwap[i] = (running_pv / running_v) if running_v > 0 else None
    return VWAPResult(vwap=vwap, cumulative_pv=cum_pv, cumulative_v=cum_v)


def vwap_anchored(bars: list[dict], anchor_ts: datetime) -> VWAPResult:
    """VWAP ancorato: cumula dalla prima bar con `bar.ts >= anchor_ts`.

    Semantica D-10 + Pitfall 3 di RESEARCH: barre con timestamp < anchor_ts
    hanno `vwap[i] = cumulative_pv[i] = cumulative_v[i] = None`. La prima bar
    con `ts >= anchor_ts` inizia la cumulazione (single-bar vwap = tp).

    Solleva `ValueError` se `anchor_ts` è naive (no tzinfo). Necessario perché
    confrontiamo con timestamp UTC tz-aware costruiti via `datetime.fromtimestamp(..., tz=UTC)`.
    """
    if anchor_ts.tzinfo is None:
        raise ValueError("anchor_ts deve essere tz-aware (es. timezone.utc)")
    n = len(bars)
    vwap: list[float | None] = [None] * n
    cum_pv: list[float | None] = [None] * n
    cum_v: list[float | None] = [None] * n
    running_pv = 0.0
    running_v = 0.0
    anchored = False
    for i, b in enumerate(bars):
        ts = datetime.fromtimestamp(int(b["time"]), tz=timezone.utc)
        if not anchored:
            if ts >= anchor_ts:
                anchored = True
            else:
                continue
        tp = _typical_price(b)
        v = _bar_volume(b)
        running_pv += tp * v
        running_v += v
        cum_pv[i] = running_pv
        cum_v[i] = running_v
        vwap[i] = (running_pv / running_v) if running_v > 0 else None
    return VWAPResult(vwap=vwap, cumulative_pv=cum_pv, cumulative_v=cum_v)
