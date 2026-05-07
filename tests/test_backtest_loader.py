"""Tests for backtest.loader (BACK-01) — covers D-08, D-10."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from backtest.loader import Bar, load_bars

REPO_ROOT = Path(__file__).resolve().parents[1]
EURUSD_H1 = REPO_ROOT / "data" / "historical" / "EURUSD" / "H1.csv"


def test_basic_load(fixture_5bars_path: Path) -> None:
    bars = load_bars(fixture_5bars_path, "EURUSD", "H1")
    assert len(bars) == 5
    assert all(isinstance(b, Bar) for b in bars)
    assert all(b.symbol == "EURUSD" and b.timeframe == "H1" for b in bars)
    # chronological
    assert bars == sorted(bars, key=lambda b: b.time)
    # frozen
    with pytest.raises(Exception):
        bars[0].open = 99.0  # type: ignore[misc]


def test_gmt6_utc_offset(fixture_5bars_path: Path) -> None:
    """D-08: source 07:00 GMT-6 -> UTC 13:00 (add 6h)."""
    bars = load_bars(fixture_5bars_path, "EURUSD", "H1")
    first = datetime.fromtimestamp(bars[0].time, tz=timezone.utc)
    assert first.hour == 13, f"expected 13:00 UTC, got {first.isoformat()}"
    assert first.year == 2024 and first.month == 1 and first.day == 5
    # consecutive hourly bars
    diffs = [bars[i + 1].time - bars[i].time for i in range(len(bars) - 1)]
    assert diffs == [3600, 3600, 3600, 3600]


def test_column_strip(tmp_path: Path) -> None:
    """Real CSV headers have leading spaces — loader must strip."""
    f = tmp_path / "leading_space.csv"
    f.write_text(
        "Data; Ora; Open; High; low; Close; Volume\n"
        "01/01/2024;00:00:00;1.10000;1.10100;1.09900;1.10050;100\n",
        encoding="utf-8",
    )
    bars = load_bars(f, "EURUSD", "H1")
    assert len(bars) == 1
    assert bars[0].open == 1.10000
    assert bars[0].volume == 100


@pytest.mark.skipif(not EURUSD_H1.exists(), reason="EURUSD H1 historical CSV missing")
def test_nfp_alignment() -> None:
    """D-10 regression: NFP 2018-02-02 13:30 UTC should align to a high-range bar.

    Researcher already verified 2024-01/02/03. We pick a different year (2018) as a
    fresh cross-check before locking the loader.
    """
    target_day = datetime(2018, 2, 2, tzinfo=timezone.utc)
    bars = load_bars(
        EURUSD_H1,
        "EURUSD",
        "H1",
        date_start=target_day,
        date_end=target_day + timedelta(days=1),
    )
    assert len(bars) > 0, "no bars for 2018-02-02"

    # Build a window +/-2h around 13:30 UTC = 11:30..15:30 UTC
    nfp_release = datetime(2018, 2, 2, 13, 30, tzinfo=timezone.utc).timestamp()
    window = [b for b in bars if abs(b.time - nfp_release) <= 2 * 3600]
    assert window, (
        "no bars near NFP release; bars: "
        f"{[(datetime.fromtimestamp(b.time, tz=timezone.utc).isoformat(), b.high - b.low) for b in bars]}"
    )

    # NFP bar should be among the top-2 ranges within the window
    ranges = sorted(((b.high - b.low, b) for b in window), key=lambda x: -x[0])
    top_bar_hours = {datetime.fromtimestamp(r[1].time, tz=timezone.utc).hour for r in ranges[:2]}
    # The 13:00 UTC bar (containing 13:30 release) should be a top-range candidate
    assert 13 in top_bar_hours or 14 in top_bar_hours, (
        f"NFP 2018-02-02 13:30 UTC misaligned. Window bars (hour, range): "
        f"{[(datetime.fromtimestamp(b.time, tz=timezone.utc).hour, round(b.high - b.low, 5)) for b in window]}"
    )
