"""Shared fixtures for backtest + indicators test suites (Phase 1, Phase 2, Phase 5)."""
from __future__ import annotations
import csv
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


# ── Stub MetaTrader5 if not installed (Phase 1 dev-machine workaround) ─────────
# Live trading machine has the real package; backtest CI / dev laptops don't.
# Stubbing here lets backtest tests import strategy.py / risk_engine.py without
# the live broker dependency. Plan 01-05: required to collect tests.
if "MetaTrader5" not in sys.modules:
    try:
        import MetaTrader5  # noqa: F401
    except ModuleNotFoundError:
        _stub = ModuleType("MetaTrader5")
        # Minimal surface used by mt5_client at import time:
        for attr in (
            "TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_M30",
            "TIMEFRAME_H1", "TIMEFRAME_H4", "TIMEFRAME_D1",
            "ORDER_TYPE_BUY", "ORDER_TYPE_SELL",
            "TRADE_ACTION_DEAL", "TRADE_ACTION_SLTP",
            "ORDER_TIME_GTC", "ORDER_FILLING_FOK", "ORDER_FILLING_IOC",
            "ORDER_FILLING_RETURN", "ORDER_FILLING_BOC",
            "TRADE_RETCODE_DONE",
            "SYMBOL_FILLING_FOK", "SYMBOL_FILLING_IOC",
            "POSITION_TYPE_BUY", "POSITION_TYPE_SELL",
        ):
            setattr(_stub, attr, 0)
        # Functions called at import time on some builds — make them no-ops.
        for fn in (
            "initialize", "shutdown", "login", "last_error",
            "account_info", "symbol_info", "symbol_info_tick",
            "copy_rates_from_pos", "positions_get", "history_deals_get",
            "order_send", "order_check", "order_calc_margin",
        ):
            setattr(_stub, fn, lambda *a, **kw: None)
        sys.modules["MetaTrader5"] = _stub


@pytest.fixture
def fixture_5bars_path() -> Path:
    return Path(__file__).parent / "fixtures" / "eurusd_5bars.csv"


@pytest.fixture
def costs_yaml_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "configs" / "costs.yaml"


@pytest.fixture(scope="session")
def eurusd_h1_500() -> list[dict]:
    """Snapshot 500-bar EURUSD H1 per D-08. Caricato una sola volta per session.

    Generato via `tests/fixtures/build_eurusd_h1_last500.py` (one-off) usando
    `backtest.loader.load_bars` con timestamp UTC (GMT-6 → UTC, Phase 1 D-08).
    Ogni dict ha le chiavi: time (int unix UTC), open, high, low, close (float),
    volume (int), tick_volume (int, alias di volume per consumer existing).
    """
    fpath = Path(__file__).parent / "fixtures" / "eurusd_h1_last500.csv"
    out: list[dict] = []
    with open(fpath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append({
                "time": int(row["time"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "tick_volume": int(row["volume"]),
            })
    return out


# ─── Phase 5 baseline fixtures (D-15, D-16, D-21) ──────────────────────────────
# Plan 05-02 Task 1: shared infra per test_baseline_*.py.
# Vincoli VALIDATION.md: nessun fixture autouse, ognuno additive (cross-test isolation).
#
# DEVIATION (Rule 1 bug fix): il plan dichiarava `tick_volume`, `spread`, `real_volume`
# come field di `Bar`, ma `backtest.loader.Bar` ha `volume`, `symbol`, `timeframe`
# (Phase 1 D-08 contract). Uso la signature reale → altrimenti fixture solleva
# `TypeError` su collection. Documentato in 05-02-SUMMARY.md.


@pytest.fixture
def synthetic_bars() -> list:
    """100 bar uptrend deterministico M15 EURUSD (mirror tests/test_backtest_engine.py::_uptrend_bars).

    Usato da test Wave 1+ per stub indicator/runner. NON è autouse — opt-in per test.
    """
    from backtest.loader import Bar  # import locale: evita side-effect collection
    bars: list = []
    base_price = 1.1000
    base_time = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    for i in range(100):
        bars.append(Bar(
            time=base_time + i * 900,  # M15 = 900s
            open=base_price + i * 0.0001,
            high=base_price + i * 0.0001 + 0.0002,
            low=base_price + i * 0.0001 - 0.0001,
            close=base_price + i * 0.0001 + 0.0001,
            volume=100 + i,
            symbol="EURUSD",
            timeframe="M15",
        ))
    return bars


@pytest.fixture
def synthetic_indicators_full(synthetic_bars):
    """Mock ExtendedIndicators dataclass-of-lists. Phase 2 D-04 schema placeholder.

    Restituisce dict con chiavi minime per detector A/B/C/D + risk_engine.
    Wave 1+ rimpiazza con vera istanza `ExtendedIndicators` quando Phase 2 landed.
    """
    n = len(synthetic_bars)
    return {
        "atr": [0.0010] * n,
        "ema20": [b.close for b in synthetic_bars],
        "ema50": [b.close for b in synthetic_bars],
        "ema200": [b.close for b in synthetic_bars],
        "ema50_slope": [0.0001] * n,
        "rsi": [55.0] * n,
        "adx": [25.0] * n,
        "regime": ["normal"] * n,
    }


@pytest.fixture
def tmp_db_with_wal(tmp_path: Path) -> Path:
    """Tmp SQLite con WAL mode già attivato. D-16 multi-writer test.

    Pragma applicati: journal_mode=WAL, busy_timeout=30000, synchronous=NORMAL.
    """
    db_path = tmp_path / "trades.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.commit()
    return db_path


@pytest.fixture
def mock_baseline_cfg(tmp_path: Path) -> Path:
    """Tmp baseline.yaml minimale per test runner (D-15 keys subset).

    `max_workers` ridotto a 2 vs prod 9 — i test sono single-machine.
    """
    path = tmp_path / "baseline.yaml"
    path.write_text(
        "equity_initial_eur: 10000\n"
        "slippage_seed: 42\n"
        "timeout_bars:\n"
        "  M15: 96\n"
        "  M30: 96\n"
        "  H1: 120\n"
        "warm_up_min_bars: 200\n"
        "max_workers: 2\n"
        "parquet_compression: snappy\n"
        "force_rerun: false\n"
        "progress_bar: false\n"
        'training_data_dir: "data/training"\n'
        'report_dir: ".planning/research"\n'
        'equity_curves_dir: ".planning/research/baseline-equity-curves"\n',
        encoding="utf-8",
    )
    return path
