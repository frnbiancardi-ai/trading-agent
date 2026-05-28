"""Phase 6 Wave 1: BarSource D-D1 tests.

Verifica:
- Live path delega a Mt5Client.get_ohlc;
- Historical path con as_of_ts ISO8601 usa load_bars (Phase 1 D-08 GMT-6 -> UTC);
- Strict-< semantics: barra al timestamp esatto NON inclusa (no future leakage);
- Errori: warmup_insufficient + csv_missing.

Riferimento: .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md Pattern 3 (D-D1).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from mcp_tools.bar_source import BarSource


# ── Helper: costruisce Bar-like dict per i monkeypatch dei test historical ────

def _bar(ts: int, price: float = 1.0) -> dict:
    """Costruisce un Bar-like compatibile con BarSource (richiede solo 'time')."""
    return {
        "time": ts,
        "open": price,
        "high": price + 0.01,
        "low": price - 0.01,
        "close": price,
        "volume": 1,
        "symbol": "EURUSD",
        "timeframe": "M15",
    }


# ── Wave 1 — BarSource live path (D-D1) ──────────────────────────────────────

def test_live_path_calls_mt5():
    """Live mode delega get_ohlc al Mt5Client e ritorna il payload as-is."""
    mock = MagicMock()
    expected = [{"time": 1, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15}]
    mock.get_ohlc.return_value = expected
    out = BarSource.get("EURUSD", "M15", 1, as_of_ts=None, mt5_client=mock)
    mock.get_ohlc.assert_called_once_with("EURUSD", "M15", 1)
    assert out == expected


# ── Wave 1 — BarSource as_of_ts: slice strict-< (no future leak, D-D1) ──────

def test_as_of_strict_lt_no_future_leak(monkeypatch):
    """CRITICAL — D-D1: bar at exact as_of_unix must NOT be in result.

    bisect_left con valore esatto trovato nella lista ritorna l'indice dell'elemento
    (insertion point a sinistra), quindi bars[cutoff-n:cutoff] esclude la barra at-exact.
    """
    bars = [
        _bar(1700000000),
        _bar(1700000900),
        _bar(1700001800),  # exact as_of
        _bar(1700002700),
    ]
    monkeypatch.setattr("mcp_tools.bar_source.load_bars",
                        lambda path, symbol, tf: bars)
    as_of_iso = (
        datetime.fromtimestamp(1700001800, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    result = BarSource.get("EURUSD", "M15", 2,
                            as_of_ts=as_of_iso, mt5_client=None)
    # cutoff = bisect_left([t0,t1,t2,t3], 1700001800) = 2
    # bars[cutoff-2:cutoff] = bars[0:2] -> esclude bar a 1700001800
    assert len(result) == 2
    assert result[0]["time"] == 1700000000
    assert result[1]["time"] == 1700000900
    assert all(b["time"] < 1700001800 for b in result), (
        "No future leakage: nessuna barra >= as_of_unix"
    )


# ── Wave 1 — BarSource error: warmup insufficient (D-D1) ────────────────────

def test_as_of_warmup_insufficient(monkeypatch):
    """Se prima di cutoff non ci sono n barre, ValueError 'as_of_ts_warmup_insufficient'."""
    bars = [_bar(1700000000 + i * 900) for i in range(5)]
    monkeypatch.setattr("mcp_tools.bar_source.load_bars",
                        lambda path, symbol, tf: bars)
    # cutoff a ts=1700000900 -> idx 1; chiediamo 100 barre prima
    as_of_iso = (
        datetime.fromtimestamp(1700000900, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    with pytest.raises(ValueError, match="as_of_ts_warmup_insufficient"):
        BarSource.get("EURUSD", "M15", 100,
                       as_of_ts=as_of_iso, mt5_client=None)


# ── Wave 1 — BarSource boundary: as_of oltre fine CSV ───────────────────────

def test_as_of_out_of_range(monkeypatch):
    """as_of_ts oltre l'ultima barra del CSV: bisect_left = len(bars), ritorna ultime n.

    Decisione (vedi PLAN action note): semantica corretta e' 'return last n bars'.
    Il branch 'as_of_ts_out_of_range' originalmente nel PLAN e' dead-code: bisect_left
    non puo' ritornare > len(arr). Documentato in SUMMARY.
    """
    bars = [_bar(1700000000 + i * 900) for i in range(5)]
    monkeypatch.setattr("mcp_tools.bar_source.load_bars",
                        lambda path, symbol, tf: bars)
    far_future_iso = (
        datetime.fromtimestamp(2100000000, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    out = BarSource.get("EURUSD", "M15", 5,
                         as_of_ts=far_future_iso, mt5_client=None)
    # cutoff capped at len(bars)=5; bars[0:5] = all bars
    assert len(out) == 5


# ── Wave 1 — BarSource error: CSV mancante (D-D1) ────────────────────────────

def test_as_of_csv_missing(monkeypatch):
    """CSV non trovato -> FileNotFoundError (handler R1 converte in envelope)."""
    def raise_fnf(path, symbol, tf):
        raise FileNotFoundError(f"data/historical/{symbol}/{tf}.csv")
    monkeypatch.setattr("mcp_tools.bar_source.load_bars", raise_fnf)
    with pytest.raises(FileNotFoundError):
        BarSource.get("XXXYYY", "M15", 10,
                       as_of_ts="2024-01-01T00:00:00Z", mt5_client=None)
