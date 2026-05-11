"""BarSource adapter (D-D1).

Single entry point per OHLC retrieval (R1 + MCP-09/12/14 + replay_decision):
- as_of_ts is None  -> live via Mt5Client.get_ohlc (default)
- as_of_ts ISO8601  -> CSV via Phase 1 load_bars, slice strict-<
                       (no future leakage by construction)

Decisione architetturale D-D1: strict-< via bisect_left(ts_arr, as_of_unix).
Se as_of_unix coincide con il timestamp di una barra, bisect_left ritorna
l'indice dell'elemento (insertion point a sinistra), quindi bars[cutoff-n:cutoff]
ESCLUDE la barra at-exact. Questo previene future-leakage in ML training.

Riferimento: 06-RESEARCH.md Pattern 3 + 06-CONTEXT.md D-D1.
"""
from __future__ import annotations

import dataclasses
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

# Phase 1 D-08: load_bars gestisce GMT-6 -> UTC, ritorna list[Bar] (dataclass time:int unix UTC).
from backtest.loader import load_bars


# Mapping convenzionale path: data/historical/{symbol}/{timeframe}.csv
_HISTORICAL_ROOT = Path("data/historical")


def _csv_path_for(symbol: str, timeframe: str) -> Path:
    """Risolve il path CSV storico per (symbol, timeframe) per convenzione D-08."""
    return _HISTORICAL_ROOT / symbol / f"{timeframe}.csv"


def _to_dict(bar) -> dict:
    """Normalizza Bar (dataclass) a dict per output omogeneo con live mode (list[dict])."""
    if dataclasses.is_dataclass(bar):
        return dataclasses.asdict(bar)
    if isinstance(bar, dict):
        return bar
    # Fallback per test: tuple namedtuple-like
    return {"time": int(getattr(bar, "time", 0)),
            "open": float(getattr(bar, "open", 0.0)),
            "high": float(getattr(bar, "high", 0.0)),
            "low": float(getattr(bar, "low", 0.0)),
            "close": float(getattr(bar, "close", 0.0))}


class BarSource:
    """Adapter live MT5 vs CSV historical (D-D1).

    Single entry point per tutti gli handler che hanno bisogno di OHLC
    (get_market_snapshot R1, run_backtest MCP-09, evaluate_walk_forward MCP-12,
    run_montecarlo MCP-14, replay_decision Wave 4).
    """

    @staticmethod
    def get(symbol: str, tf: str, n: int,
            as_of_ts: str | None = None,
            mt5_client=None) -> list[dict]:
        """Recupera n barre OHLC.

        Args:
            symbol: e.g. "EURUSD"
            tf: timeframe stringa (M15/M30/H1/H4)
            n: numero di barre desiderate
            as_of_ts: ISO8601 UTC; None -> live mode (default)
            mt5_client: richiesto se as_of_ts is None

        Returns:
            list[dict] di n barre OHLC con almeno il campo 'time' (int unix UTC).

        Raises:
            ValueError: as_of_ts_warmup_insufficient (meno di n barre prima di cutoff)
                        | mt5_client mancante in live mode.
            FileNotFoundError: CSV storico mancante (handler converte in
                               envelope 'historical_data_unavailable').
        """
        if as_of_ts is None:
            # Live mode: delega al Mt5Client
            if mt5_client is None:
                raise ValueError(
                    "mt5_client required for live mode (as_of_ts=None)"
                )
            return mt5_client.get_ohlc(symbol, tf, n)

        # Historical mode (Phase 1 D-08 loader gestisce GMT-6 -> UTC)
        path = _csv_path_for(symbol, tf)
        bars = load_bars(path, symbol, tf)
        # Normalizza a list[dict] per output omogeneo
        bars_dicts = [_to_dict(b) for b in bars]
        ts_arr = [int(b["time"]) for b in bars_dicts]

        # ISO8601 (con 'Z' o offset) -> unix UTC
        as_of_unix = int(
            datetime.fromisoformat(as_of_ts.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .timestamp()
        )

        # Strict-<: bisect_left ritorna insertion point a sinistra; se as_of_unix
        # coincide con un timestamp esatto, la barra at-exact e' ESCLUSA.
        cutoff = bisect_left(ts_arr, as_of_unix)

        if cutoff < n:
            raise ValueError(
                f"as_of_ts_warmup_insufficient: {as_of_ts}, need {n} bars, "
                f"available before cutoff {cutoff}"
            )
        # NB: cutoff > len(ts_arr) e' unreachable (bisect_left cap a len);
        # as_of_ts far-future ritorna naturalmente le ultime n barre.
        return bars_dicts[cutoff - n: cutoff]


__all__ = ["BarSource"]
