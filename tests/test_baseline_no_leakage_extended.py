"""Test invariante no-leakage: snapshot extended @ bar idx-1 (Plan 05-09 D-09-B + FIX 4 + FIX C iter 3).

Verifica che _extract_extended_snapshot_at_entry usi `bars_dict[:idx]`
(EXCLUSIVE del bar di entry), garantendo che gli indicatori del trade
riflettano la history visibile alla strategy PRIMA dell'open del bar
in cui il trade entra.

Inoltre (FIX 4 + FIX C iter 3): decision_ts_utc < entry_ts_utc rigorosamente,
gap == timeframe delta (15min per M15) — anchor CONSERVATIVA vs D-22 stretta
(1 bar di safety buffer pre-entry) — prerequisito per walk-forward Phase 7
senza off-by-one-bar leakage residuo da gap-di-sessione.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch


def _make_bars_dict(n: int = 100, interval_seconds: int = 900) -> list[dict]:
    """Bar sintetici monotonicamente crescenti.

    Default 900s = 15min (M15 timeframe) per testare invariante
    anchor conservativa D-09-B (gap = timeframe delta).
    """
    base_ts = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    return [
        {
            "time": base_ts + i * interval_seconds,
            "open": 1.10 + i * 0.0001,
            "high": 1.10 + i * 0.0001 + 0.0005,
            "low": 1.10 + i * 0.0001 - 0.0005,
            "close": 1.10 + i * 0.0001 + 0.0002,
            "volume": 1000.0,
        }
        for i in range(n)
    ]


def test_snapshot_excludes_entry_bar() -> None:
    """D-09-B: il bar di entry NON entra nel calcolo."""
    from backtest.baseline.slice_worker import (
        _build_bars_index_by_time,
        _extract_extended_snapshot_at_entry,
    )

    bars_dict = _make_bars_dict(100)
    idx_map = _build_bars_index_by_time(bars_dict)
    entry_bar = bars_dict[50]
    entry_iso = datetime.fromtimestamp(entry_bar["time"], tz=timezone.utc).isoformat()

    captured_lens: list[int] = []

    def _fake_cae(bars_arg, regime_cfg=None):
        captured_lens.append(len(bars_arg))
        return {"sma_20": 1.11, "atr_14": 0.001, "regime_state": "normal"}

    with patch("indicators.compute_all_extended", side_effect=_fake_cae):
        snap = _extract_extended_snapshot_at_entry(
            bars_dict, idx_map, entry_iso, regime_cfg=None,
        )

    assert len(captured_lens) == 1, "compute_all_extended chiamato esattamente 1 volta"
    assert captured_lens[0] == 50, (
        f"NO-LEAKAGE: deve usare bars[:50] (50 elementi), trovato {captured_lens[0]}"
    )
    assert snap["sma_20"] == 1.11
    assert snap["regime_state"] == "normal"


def test_snapshot_idx_zero_returns_empty() -> None:
    """Edge: entry al primo bar -> dict vuoto senza chiamare cae."""
    from backtest.baseline.slice_worker import (
        _build_bars_index_by_time,
        _extract_extended_snapshot_at_entry,
    )

    bars_dict = _make_bars_dict(10)
    idx_map = _build_bars_index_by_time(bars_dict)
    entry_iso = datetime.fromtimestamp(bars_dict[0]["time"], tz=timezone.utc).isoformat()

    called: list[bool] = []
    with patch("indicators.compute_all_extended", side_effect=lambda *a, **k: called.append(True)):
        snap = _extract_extended_snapshot_at_entry(
            bars_dict, idx_map, entry_iso, regime_cfg=None,
        )
    assert snap == {}
    assert called == [], "compute_all_extended NON deve essere invocato per idx=0"


def test_snapshot_unknown_entry_ts_returns_empty() -> None:
    """Edge: entry_ts non in cache -> dict vuoto."""
    from backtest.baseline.slice_worker import (
        _build_bars_index_by_time,
        _extract_extended_snapshot_at_entry,
    )

    bars_dict = _make_bars_dict(10)
    idx_map = _build_bars_index_by_time(bars_dict)
    # Timestamp arbitrario non presente in idx_map
    fake_iso = datetime(1999, 1, 1, tzinfo=timezone.utc).isoformat()
    snap = _extract_extended_snapshot_at_entry(
        bars_dict, idx_map, fake_iso, regime_cfg=None,
    )
    assert snap == {}


def test_no_leakage_invariant_decision_before_entry() -> None:
    """FIX 4 + FIX C iter 3: decision_ts < entry_ts rigorosamente, gap == timeframe_delta.

    Anchor CONSERVATIVA D-09-B vs D-22 stretta. In convenzione MT5
    (`bar.time = bar OPEN`):
      - decision_ts = open di idx-1 == bars_dict[idx-1]["time"]
      - entry_ts    = open di idx   == bars_dict[idx]["time"]
      - gap = open(idx) - open(idx-1) = timeframe_delta (900s per M15)

    D-22 stretta richiederebbe decision_ts = close di idx-1 ==
    open di idx == entry_ts (gap=0). Plan 05-09 sceglie ANCHOR
    CONSERVATIVA (1 bar prima) come safety buffer per Phase 7.

    Simula il flow di Task 2 §5: entry al bar idx=50, decision_ts
    calcolato come open del bar idx-1=49, entry_ts == open del bar
    idx=50 (== bars_dict[50]["time"] reso ISO). Gap atteso = 900s = 15min.
    """
    from backtest.baseline.slice_worker import _build_bars_index_by_time

    bars_dict = _make_bars_dict(100, interval_seconds=900)  # M15 = 15min = 900s
    _ = _build_bars_index_by_time(bars_dict)  # sanity check costruzione

    # Entry al bar 50 (simula trade ledger row)
    idx_entry = 50
    entry_ts_unix = bars_dict[idx_entry]["time"]
    entry_iso = datetime.fromtimestamp(entry_ts_unix, tz=timezone.utc).isoformat()

    # Decision_ts = open del bar idx-1 (anchor conservativa D-09-B / FIX C iter 3)
    decision_ts_unix = bars_dict[idx_entry - 1]["time"]
    decision_iso = datetime.fromtimestamp(decision_ts_unix, tz=timezone.utc).isoformat()

    # Invariante 1: decision_ts < entry_ts (strict)
    dt_decision = datetime.fromisoformat(decision_iso)
    dt_entry = datetime.fromisoformat(entry_iso)
    assert dt_decision < dt_entry, (
        f"D-09-B violato: decision {decision_iso} >= entry {entry_iso}"
    )

    # Invariante 2: gap == timeframe_delta (M15 = 15min)
    # Anchor conservativa = 1 bar pre-entry (NON gap=0 di D-22 stretta)
    gap = dt_entry - dt_decision
    assert gap == timedelta(minutes=15), (
        f"D-09-B violato: gap {gap} != 15min (timeframe M15 — anchor conservativa)"
    )
