"""Test indicators.volume (INDIC-07) — fixture manuali per session reset + anchor."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from indicators import vwap_intraday, vwap_anchored, VWAPResult


def _bar(year: int, month: int, day: int, hour: int,
         h: float, l: float, c: float, v: int) -> dict:
    """Costruisce un bar OHLC con timestamp UTC unix-seconds e tick_volume=volume."""
    ts = int(datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc).timestamp())
    return {
        "time": ts,
        "open": (h + l) / 2,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "tick_volume": v,
    }


def test_vwap_intraday_single_bar() -> None:
    """Singola bar: tp=(2+1+1.5)/3=1.5, vol=10 → vwap[0]=1.5, cum_pv=15.0, cum_v=10.0."""
    bar = _bar(2024, 1, 15, 10, h=2.0, l=1.0, c=1.5, v=10)
    r = vwap_intraday([bar])
    assert isinstance(r, VWAPResult)
    assert abs(r.vwap[0] - 1.5) < 1e-12
    assert abs(r.cumulative_pv[0] - 15.0) < 1e-12
    assert abs(r.cumulative_v[0] - 10.0) < 1e-12


def test_vwap_intraday_session_reset_winter() -> None:
    """NY-17 boundary winter (DST inattivo): 22:00 UTC = nuovo session-id.

    Bar A 21:00 UTC del 2024-01-15 → session 2024-01-15 NY (16:00 NY, ancora old)
    Bar B 22:00 UTC del 2024-01-15 → NEW session (17:00 NY → session_id_ny17 → 2024-01-16)
    Bar C 23:00 UTC del 2024-01-15 → stessa nuova sessione di B
    """
    bar_a = _bar(2024, 1, 15, 21, h=2.0, l=1.0, c=1.5, v=10)   # tp=1.5
    bar_b = _bar(2024, 1, 15, 22, h=4.0, l=2.0, c=3.0, v=20)   # tp=3.0
    bar_c = _bar(2024, 1, 15, 23, h=6.0, l=4.0, c=5.0, v=10)   # tp=5.0
    r = vwap_intraday([bar_a, bar_b, bar_c])

    # vwap[0]: A da solo nella vecchia sessione → 1.5
    assert abs(r.vwap[0] - 1.5) < 1e-9
    # vwap[1]: reset alla nuova sessione, B da solo → 3.0
    assert abs(r.vwap[1] - 3.0) < 1e-9
    # vwap[2]: B+C nella nuova sessione → (3.0*20 + 5.0*10) / (20+10) = 110/30
    expected = (3.0 * 20 + 5.0 * 10) / (20 + 10)
    assert abs(r.vwap[2] - expected) < 1e-9

    # cumulative_v si resetta correttamente
    assert r.cumulative_v[0] == 10.0
    assert r.cumulative_v[1] == 20.0      # reset poi solo B
    assert r.cumulative_v[2] == 30.0      # B + C nella nuova sessione


def test_vwap_intraday_session_reset_summer() -> None:
    """NY-17 boundary summer (DST attivo): 21:00 UTC = nuovo session-id.

    Bar A 20:00 UTC del 2024-07-15 → session corrente (16:00 NY)
    Bar B 21:00 UTC del 2024-07-15 → NEW session (17:00 NY summer)
    """
    bar_a = _bar(2024, 7, 15, 20, h=2.0, l=1.0, c=1.5, v=10)   # tp=1.5
    bar_b = _bar(2024, 7, 15, 21, h=4.0, l=2.0, c=3.0, v=20)   # tp=3.0
    r = vwap_intraday([bar_a, bar_b])

    # vwap[0]: A da solo nella vecchia sessione → 1.5
    assert abs(r.vwap[0] - 1.5) < 1e-9
    # vwap[1]: reset al boundary summer (21:00 UTC) → B da solo nella nuova → 3.0
    assert abs(r.vwap[1] - 3.0) < 1e-9
    assert r.cumulative_v[1] == 20.0   # reset confermato


def test_vwap_intraday_zero_volume_yields_none() -> None:
    """volume=0 e tick_volume=0 → cumulative_v==0 → vwap=None (no div-by-zero)."""
    ts = int(datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp())
    bar = {
        "time": ts, "open": 1.5, "high": 2.0, "low": 1.0, "close": 1.5,
        "volume": 0, "tick_volume": 0,
    }
    r = vwap_intraday([bar])
    assert r.vwap[0] is None
    assert r.cumulative_v[0] == 0.0


def test_vwap_anchored_before_anchor_returns_none() -> None:
    """3 bar; anchor 1 microsecondo DOPO bar[1] → solo bar[2] cumulato."""
    bars = [
        _bar(2024, 1, 15, 10, h=2.0, l=1.0, c=1.5, v=10),
        _bar(2024, 1, 15, 11, h=4.0, l=2.0, c=3.0, v=20),
        _bar(2024, 1, 15, 12, h=6.0, l=4.0, c=5.0, v=10),
    ]
    # 1 microsecondo dopo bar[1].time
    anchor = datetime.fromtimestamp(bars[1]["time"], tz=timezone.utc).replace(microsecond=1)
    r = vwap_anchored(bars, anchor)
    assert r.vwap[0] is None
    assert r.cumulative_pv[0] is None
    assert r.cumulative_v[0] is None
    assert r.vwap[1] is None
    assert r.cumulative_pv[1] is None
    assert r.cumulative_v[1] is None
    # bar[2] è il primo con ts >= anchor → tp=(6+4+5)/3=5.0
    assert abs(r.vwap[2] - 5.0) < 1e-9
    assert r.cumulative_v[2] == 10.0


def test_vwap_anchored_at_exact_bar_ts_starts_cumulation() -> None:
    """anchor == bar[1].time esattamente → bar[1] è il primo cumulato."""
    bars = [
        _bar(2024, 1, 15, 10, h=2.0, l=1.0, c=1.5, v=10),
        _bar(2024, 1, 15, 11, h=4.0, l=2.0, c=3.0, v=20),
        _bar(2024, 1, 15, 12, h=6.0, l=4.0, c=5.0, v=10),
    ]
    anchor = datetime.fromtimestamp(bars[1]["time"], tz=timezone.utc)
    r = vwap_anchored(bars, anchor)
    assert r.vwap[0] is None
    # bar[1]: tp=3.0, vol=20 → vwap=3.0
    assert abs(r.vwap[1] - 3.0) < 1e-9
    assert r.cumulative_v[1] == 20.0
    # bar[2]: cumula bar[1]+bar[2]: (3.0*20 + 5.0*10) / 30 = 110/30
    expected = (3.0 * 20 + 5.0 * 10) / 30
    assert abs(r.vwap[2] - expected) < 1e-9
    assert r.cumulative_v[2] == 30.0


def test_vwap_anchored_naive_datetime_raises() -> None:
    """anchor_ts senza tzinfo → ValueError fail-fast (italiano)."""
    with pytest.raises(ValueError, match="tz-aware"):
        vwap_anchored([], datetime(2024, 1, 1))
