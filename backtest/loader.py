"""Italian-CSV historical bar loader (BACK-01) — semicolon, DD/MM/YYYY, GMT-6 → UTC."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# D-08: source is GMT-6, add 6h to get UTC. Verified vs 3 NFP candles in research.
_GMT6_OFFSET = timedelta(hours=6)


@dataclass(frozen=True)
class Bar:
    time: int          # UTC unix timestamp (bar OPEN time, seconds)
    open: float
    high: float
    low: float
    close: float
    volume: int
    symbol: str
    timeframe: str


def load_bars(
    path: Path,
    symbol: str,
    timeframe: str,
    date_start: datetime | None = None,   # UTC, inclusive
    date_end: datetime | None = None,     # UTC, exclusive
) -> list[Bar]:
    """Load semicolon-separated Italian-format CSV bars and return UTC-stamped Bar list.

    Per RESEARCH §Pattern 1:
      - Strips leading whitespace from column headers (preserves names: Data, Ora, Open,
        High, low, Close, Volume — note the lowercase 'low').
      - Parses Data + ' ' + Ora with format='%d/%m/%Y %H:%M:%S'.
      - Adds timedelta(hours=6) to obtain UTC (D-08 GMT-6 source).
      - Filters by date_start (inclusive) and date_end (exclusive) if provided.
      - Sorts ascending by UTC time, drops duplicates on UTC time.
      - Iterates via itertuples (perf rule, see RESEARCH §Pitfalls).
      - Reads numeric values as dot-separated floats (Pitfall 5).
    """
    df = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str)
    df.columns = [c.strip() for c in df.columns]

    df["dt_source"] = pd.to_datetime(
        df["Data"] + " " + df["Ora"], format="%d/%m/%Y %H:%M:%S"
    )
    df["dt_utc"] = df["dt_source"] + _GMT6_OFFSET

    for col in ("Open", "High", "low", "Close"):
        df[col] = df[col].astype(float)
    df["Volume"] = df["Volume"].astype(int)

    if date_start is not None:
        ts_start = pd.Timestamp(date_start)
        if ts_start.tzinfo is not None:
            ts_start = ts_start.tz_convert("UTC").tz_localize(None)
        df = df[df["dt_utc"] >= ts_start]
    if date_end is not None:
        ts_end = pd.Timestamp(date_end)
        if ts_end.tzinfo is not None:
            ts_end = ts_end.tz_convert("UTC").tz_localize(None)
        df = df[df["dt_utc"] < ts_end]

    df = df.sort_values("dt_utc").drop_duplicates("dt_utc").reset_index(drop=True)

    bars: list[Bar] = []
    for row in df.itertuples(index=False):
        bars.append(
            Bar(
                time=int(row.dt_utc.timestamp()),
                open=float(row.Open),
                high=float(row.High),
                low=float(row.low),
                close=float(row.Close),
                volume=int(row.Volume),
                symbol=symbol,
                timeframe=timeframe,
            )
        )
    return bars
