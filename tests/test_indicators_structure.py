"""Test indicators.structure (INDIC-05/08/09) — hand-calc fixture tier per D-07.

Wave 2 indicators:
- Donchian (INDIC-05): rolling max highs / min lows / middle.
- Fibonacci retracements (INDIC-08): livelli sull'ultimo swing leg.
- Pivots (INDIC-09): classico + Camarilla, ancora NY-17 DST-aware.

Tutti i test sono hand-calc: fixture deterministica, valore atteso calcolato
a mano, asserito con tolleranza 1e-9.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from indicators._helpers import _session_id_ny17
from indicators.structure import (
    DonchianResult,
    FibonacciResult,
    PivotResult,
    donchian,
    fibonacci_retracements,
    pivots,
)


# ── Donchian (INDIC-05) ────────────────────────────────────────────────────────


def test_donchian_simple_5bar():
    """Donchian length=3 su highs=[2,4,3,5,1], lows=[1,2,2,3,0]:
    upper[2]=max(2,4,3)=4, lower[2]=min(1,2,2)=1, middle[2]=2.5.
    upper[4]=max(3,5,1)=5, lower[4]=min(2,3,0)=0, middle[4]=2.5.
    """
    highs = [2.0, 4.0, 3.0, 5.0, 1.0]
    lows = [1.0, 2.0, 2.0, 3.0, 0.0]
    r = donchian(highs, lows, length=3)
    assert isinstance(r, DonchianResult)
    assert r.upper[0] is None and r.upper[1] is None
    assert r.upper[2] == 4.0
    assert r.lower[2] == 1.0
    assert r.middle[2] == 2.5
    assert r.upper[4] == 5.0
    assert r.lower[4] == 0.0
    assert r.middle[4] == 2.5


def test_donchian_constant_series():
    """Su serie costante highs=[5]*30, lows=[3]*30 con length=10:
    upper[9]=5.0, lower[9]=3.0, middle[9]=4.0.
    """
    highs = [5.0] * 30
    lows = [3.0] * 30
    r = donchian(highs, lows, length=10)
    assert r.upper[9] == 5.0
    assert r.lower[9] == 3.0
    assert r.middle[9] == 4.0
    # E continua costante fino in fondo.
    assert r.upper[29] == 5.0
    assert r.middle[29] == 4.0


def test_donchian_first_n_minus_1_none():
    """Con length=20 i primi 19 indici devono essere None, il 20° float."""
    highs = [float(i) for i in range(30)]
    lows = [float(i) - 0.5 for i in range(30)]
    r = donchian(highs, lows, length=20)
    for i in range(19):
        assert r.upper[i] is None, f"idx {i} dovrebbe essere None"
        assert r.lower[i] is None
        assert r.middle[i] is None
    assert isinstance(r.upper[19], float)
    assert isinstance(r.lower[19], float)
    assert isinstance(r.middle[19], float)


def test_donchian_length_mismatch_raises():
    """ValueError italiano se highs/lows hanno lunghezza diversa."""
    with pytest.raises(ValueError, match="stessa lunghezza"):
        donchian([1.0, 2.0, 3.0], [1.0, 2.0], length=2)


# ── Pivots (INDIC-09) ──────────────────────────────────────────────────────────


def _bar(ts_utc_seconds: int, h: float, l: float, c: float) -> dict:
    """Helper costruttore bar minimale."""
    return {
        "time": ts_utc_seconds,
        "open": c,
        "high": h,
        "low": l,
        "close": c,
        "volume": 100,
        "tick_volume": 100,
    }


def test_pivot_camarilla_formula():
    """Camarilla hand-calc esatto: prev_h=110, prev_l=100, prev_c=105.

    Costruisce 24 bar orarie nella sessione NY del 2024-01-15 (winter,
    NY-17 == 22:00 UTC) — close finale = 105 → poi una bar nella nuova
    sessione (>=22:00 UTC del 2024-01-16). Verifica che la prima bar della
    nuova sessione abbia P=(110+100+105)/3=105.0, h1≈105.91666, h4=110.5,
    l4=99.5, e i livelli classici R1/S1.
    """
    # Sessione 1: 2024-01-15 09:00..2024-01-16 21:00 UTC.
    # NY-17 winter boundary = 22:00 UTC, quindi la sessione NY 2024-01-16
    # comprende bar dal 2024-01-15 22:00 UTC al 2024-01-16 21:00 UTC inclusi.
    bars: list[dict] = []
    base = int(datetime(2024, 1, 15, 22, 0, 0, tzinfo=timezone.utc).timestamp())
    # 24 bar orarie nella sessione.
    for i in range(24):
        ts = base + i * 3600
        # Pattern H/L/C per produrre H sessione=110, L=100, C ultima=105.
        if i == 5:
            h, l, c = 110.0, 104.0, 108.0  # high della sessione
        elif i == 12:
            h, l, c = 106.0, 100.0, 102.0  # low della sessione
        elif i == 23:
            h, l, c = 106.0, 104.0, 105.0  # last close = 105
        else:
            h, l, c = 106.0, 104.0, 105.5
        bars.append(_bar(ts, h, l, c))
    # Bar 25: prima della NUOVA sessione (al boundary o dopo).
    ts_new = base + 24 * 3600  # = 2024-01-16 22:00 UTC = nuova sessione NY-17
    bars.append(_bar(ts_new, 107.0, 105.0, 106.0))

    r = pivots(bars, anchor="daily")
    assert isinstance(r, PivotResult)

    new_idx = 24  # prima bar della nuova sessione
    P_expected = (110.0 + 100.0 + 105.0) / 3.0  # = 105.0
    rng = 110.0 - 100.0
    assert abs(r.p[new_idx] - P_expected) < 1e-9, (r.p[new_idx], P_expected)
    # Classico
    assert abs(r.r1[new_idx] - (2 * P_expected - 100.0)) < 1e-9  # 110.0
    assert abs(r.s1[new_idx] - (2 * P_expected - 110.0)) < 1e-9  # 100.0
    assert abs(r.r2[new_idx] - (P_expected + rng)) < 1e-9  # 115.0
    assert abs(r.s2[new_idx] - (P_expected - rng)) < 1e-9  # 95.0
    # Camarilla verbatim 1.1/{12,6,4,2}
    assert abs(r.camarilla["h1"][new_idx] - (105.0 + 10.0 * 1.1 / 12)) < 1e-9
    assert abs(r.camarilla["h1"][new_idx] - 105.91666666666667) < 1e-9
    assert abs(r.camarilla["h4"][new_idx] - (105.0 + 10.0 * 1.1 / 2)) < 1e-9
    assert abs(r.camarilla["h4"][new_idx] - 110.5) < 1e-9
    assert abs(r.camarilla["l4"][new_idx] - 99.5) < 1e-9


def test_pivot_first_session_all_none():
    """Bar nella prima sessione osservata → no prior → tutti None."""
    base = int(datetime(2024, 1, 15, 22, 0, 0, tzinfo=timezone.utc).timestamp())
    bars = [_bar(base + i * 3600, 1.10 + i * 0.001, 1.09 + i * 0.001, 1.095 + i * 0.001)
            for i in range(10)]
    r = pivots(bars, anchor="daily")
    for i in range(10):
        assert r.p[i] is None
        assert r.r1[i] is None
        assert r.s3[i] is None
        for k in ("h1", "h2", "h3", "h4", "l1", "l2", "l3", "l4"):
            assert r.camarilla[k][i] is None


def test_pivot_ny17_dst_boundary_winter_vs_summer():
    """Boundary NY-17 DST-aware: winter == 22:00 UTC, summer == 21:00 UTC.

    Verifica diretta su `_session_id_ny17` (l'helper usato internamente da
    `pivots` per la session-key).
    """
    # Winter (gennaio): boundary 22:00 UTC.
    win_before = datetime(2024, 1, 15, 21, 59, 59, tzinfo=timezone.utc)
    win_after = datetime(2024, 1, 15, 22, 0, 0, tzinfo=timezone.utc)
    assert _session_id_ny17(win_before) != _session_id_ny17(win_after), (
        "boundary winter dovrebbe essere 22:00 UTC"
    )
    assert _session_id_ny17(win_after) == _session_id_ny17(win_before) + timedelta(days=1)

    # Summer (luglio): boundary 21:00 UTC (DST avanti di un'ora).
    sum_before = datetime(2024, 7, 15, 20, 59, 59, tzinfo=timezone.utc)
    sum_after = datetime(2024, 7, 15, 21, 0, 0, tzinfo=timezone.utc)
    assert _session_id_ny17(sum_before) != _session_id_ny17(sum_after), (
        "boundary summer dovrebbe essere 21:00 UTC"
    )
    assert _session_id_ny17(sum_after) == _session_id_ny17(sum_before) + timedelta(days=1)


# ── Fibonacci retracements (INDIC-08) ──────────────────────────────────────────


def test_fib_retracement_up_leg():
    """Up-leg: low=1.0 a idx 5, high=2.0 a idx 25 (high più recente del low →
    direction='up'). Levels attesi: 0=2.0, 1.0=1.0, retracement scende dall'high.
    """
    bars: list[dict] = []
    for i in range(30):
        if i == 5:
            h, l, c = 1.5, 1.0, 1.4  # low = 1.0
        elif i == 25:
            h, l, c = 2.0, 1.7, 1.95  # high = 2.0 (più recente)
        else:
            h, l, c = 1.6, 1.3, 1.45  # filler all'interno del range
        bars.append(_bar(i * 3600, h, l, c))

    r = fibonacci_retracements(bars, lookback=30, window=2)
    assert isinstance(r, FibonacciResult)
    assert r.direction == "up"
    assert r.leg_low == 1.0
    assert r.leg_high == 2.0
    assert abs(r.levels["0"] - 2.0) < 1e-9
    assert abs(r.levels["0.382"] - (2.0 - 0.382 * 1.0)) < 1e-9  # 1.618
    assert abs(r.levels["0.5"] - 1.5) < 1e-9
    assert abs(r.levels["0.618"] - (2.0 - 0.618 * 1.0)) < 1e-9  # 1.382
    assert abs(r.levels["1.0"] - 1.0) < 1e-9


def test_fib_no_swing_returns_none_direction():
    """Bar costanti (H==L) → nessun swing rilevabile → direction='none'."""
    bars = [_bar(i * 3600, 1.10, 1.10, 1.10) for i in range(30)]
    r = fibonacci_retracements(bars, lookback=30, window=2)
    assert r.direction == "none"
    assert r.leg_high is None
    assert r.leg_low is None
    assert r.levels == {}
