"""Cattura snapshot pre-refactor di IntradayStrategy.analyze_symbol() su 10 scenari storici.

Eseguito UNA VOLTA prima del refactor Phase 4 (D-14). Output:
tests/fixtures/strategy_regression_baseline.json.

Lo script DEVE essere deterministico: re-eseguendolo, il JSON prodotto è
byte-identico (sorted keys, indent=2). Nessun accesso di rete, MT5 reale o
scrittura sotto logs/. Le bars provengono dai CSV storici via
backtest.loader.load_bars (BACK-01 già shippato), il broker è un MagicMock.

Uso:
    python tests/capture_regression_baseline.py
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Assicura che la root del repo sia sul sys.path quando si lancia da CLI.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Stub MetaTrader5 prima di importare strategy (mirror conftest.py:14-40).
# Necessario perché strategy.py importa indicators -> ... -> mt5_client.
import sys as _sys  # noqa: E402
from types import ModuleType  # noqa: E402

if "MetaTrader5" not in _sys.modules:
    _stub = ModuleType("MetaTrader5")
    for _attr in (
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
        setattr(_stub, _attr, 0)
    for _fn in (
        "initialize", "shutdown", "login", "last_error",
        "account_info", "symbol_info", "symbol_info_tick",
        "copy_rates_from_pos", "positions_get", "history_deals_get",
        "order_send", "order_check", "order_calc_margin",
    ):
        setattr(_stub, _fn, lambda *a, **kw: None)
    _sys.modules["MetaTrader5"] = _stub

from backtest.loader import load_bars  # noqa: E402
from models import AccountState  # noqa: E402
from strategy import IntradayStrategy  # noqa: E402,F401  legacy import — pre-refactor


# 10 scenari per regression fixture (D-14 + RESEARCH §10-Scenario Mix Design).
# `expected_mix` è solo etichetta intent — non enforced; lo script cattura
# qualunque output produca il codice attuale.
SCENARIOS = [
    {"scenario_id": 1,  "symbol": "EURUSD", "csv": "data/historical/EURUSD/M15.csv", "bar_offset": -200, "expected_mix": "READY"},
    {"scenario_id": 2,  "symbol": "EURUSD", "csv": "data/historical/EURUSD/M15.csv", "bar_offset": -350, "expected_mix": "READY"},
    {"scenario_id": 3,  "symbol": "EURUSD", "csv": "data/historical/EURUSD/M15.csv", "bar_offset": -500, "expected_mix": "READY"},
    {"scenario_id": 4,  "symbol": "GBPUSD", "csv": "data/historical/GBPUSD/M15.csv", "bar_offset": -200, "expected_mix": "FORMING"},
    {"scenario_id": 5,  "symbol": "GBPUSD", "csv": "data/historical/GBPUSD/M15.csv", "bar_offset": -400, "expected_mix": "FORMING"},
    {"scenario_id": 6,  "symbol": "EURUSD", "csv": "data/historical/EURUSD/M15.csv", "bar_offset": -150, "expected_mix": "NONE"},
    {"scenario_id": 7,  "symbol": "USDJPY", "csv": "data/historical/USDJPY/M15.csv", "bar_offset": -200, "expected_mix": "NONE"},
    {"scenario_id": 8,  "symbol": "USDJPY", "csv": "data/historical/USDJPY/M15.csv", "bar_offset": -350, "expected_mix": "NONE"},
    {"scenario_id": 9,  "symbol": "GBPUSD", "csv": "data/historical/GBPUSD/M15.csv", "bar_offset": -300, "expected_mix": "NONE"},
    {"scenario_id": 10, "symbol": "USDJPY", "csv": "data/historical/USDJPY/M15.csv", "bar_offset": -500, "expected_mix": "mixed"},
]


# Lookback richiesto da IntradayStrategy._analyze_technical (cfg.INTRADAY_LOOKBACK_BARS).
# Phase 4 D-14: usa 200 bars come default Config.
_LOOKBACK_BARS = 200


def _mock_mt5_from_csv(csv_path: str, symbol: str, cap_at_bar: int) -> MagicMock:
    """Crea un mock di Mt5Client che ritorna bars dal CSV troncate a cap_at_bar.

    cap_at_bar è negativo (es. -200 = "ferma 200 bars prima della fine del CSV").
    Restituisce solo le ultime _LOOKBACK_BARS bars come fa il broker reale.
    """
    repo_csv = _REPO_ROOT / csv_path
    bars_full = load_bars(repo_csv, symbol=symbol, timeframe="M15")
    if not bars_full:
        raise RuntimeError(f"Nessuna bar caricata da {csv_path}")
    # cap_at_bar è negativo: tronca dalla fine.
    truncated = bars_full[: len(bars_full) + cap_at_bar]
    if len(truncated) < _LOOKBACK_BARS:
        raise RuntimeError(
            f"Bars insufficienti dopo cap (cap={cap_at_bar}): "
            f"have={len(truncated)} need>={_LOOKBACK_BARS}"
        )
    window = truncated[-_LOOKBACK_BARS:]

    bar_dicts = [
        {
            "time": b.time,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "tick_volume": b.volume,
            "volume": b.volume,
        }
        for b in window
    ]

    last_close = bar_dicts[-1]["close"]
    # Pip / digits ragionevoli per i tre majors usati (EURUSD/GBPUSD digits=5,
    # USDJPY digits=3). Determinato da symbol per mantenere il pip_size coerente
    # con quello che IntradayStrategy._pip_size calcola dal symbol_info.
    if symbol.endswith("JPY"):
        digits = 3
        point = 0.001
        spread_offset = 0.01
        tick_size = 0.001
    else:
        digits = 5
        point = 0.00001
        spread_offset = 0.0001
        tick_size = 0.00001

    sym_info = SimpleNamespace(
        bid=last_close,
        ask=last_close + spread_offset,
        point=point,
        digits=digits,
        trade_tick_value=10.0,
        trade_tick_size=tick_size,
    )

    mt5 = MagicMock()
    mt5.get_ohlc.return_value = bar_dicts
    mt5.get_symbol_info.return_value = sym_info
    # AccountState reale è passato esternamente; questi due metodi non sono usati
    # da IntradayStrategy.analyze_symbol ma lasciati per safety.
    mt5.get_account_info.return_value = SimpleNamespace(balance=10000.0, equity=10000.0)
    mt5.get_open_positions.return_value = []
    mt5.get_trade_history.return_value = []
    return mt5


def _capture_cfg() -> MagicMock:
    """Config-shaped MagicMock con tutti gli attributi referenziati da strategy.py.

    Enumerati leggendo strategy.py: INTRADAY_TIMEFRAME, INTRADAY_LOOKBACK_BARS,
    SR_LOOKBACK_BARS, MIN_ATR_PIPS, MAX_ATR_PIPS, MIN_TREND_STRENGTH,
    MIN_BREAKOUT_VOLUME_RATIO, MIN_RISK_REWARD_RATIO, MAX_RSI_OVERBOUGHT,
    MIN_RSI_OVERSOLD, ENABLE_CANDLESTICK_PATTERNS, PATTERN_CONFIRMATION_BARS,
    SR_TOLERANCE_PIPS, RISK_MODE, ENABLE_NEWS_SENTIMENT (path sentiment).
    """
    cfg = MagicMock()
    cfg.INTRADAY_TIMEFRAME = "M15"
    cfg.INTRADAY_LOOKBACK_BARS = _LOOKBACK_BARS
    cfg.INTRADAY_SCAN_TOP_N = 3
    cfg.SR_LOOKBACK_BARS = 100
    cfg.SR_TOLERANCE_PIPS = 5.0
    cfg.MIN_ATR_PIPS = 3.0
    cfg.MAX_ATR_PIPS = 50.0
    cfg.MIN_TREND_STRENGTH = 0.65
    cfg.MIN_BREAKOUT_VOLUME_RATIO = 1.3
    cfg.MIN_RISK_REWARD_RATIO = 1.5
    cfg.MAX_RSI_OVERBOUGHT = 75
    cfg.MIN_RSI_OVERSOLD = 25
    cfg.MIN_CONFIDENCE_TO_PROPOSE = 0.60
    cfg.ENABLE_CANDLESTICK_PATTERNS = True
    cfg.PATTERN_CONFIRMATION_BARS = 3
    cfg.RISK_MODE = "MODERATE"
    cfg.ENABLE_NEWS_SENTIMENT = False
    cfg.SENTIMENT_MIN_STRENGTH_FILTER = 0.6
    cfg.SENTIMENT_BOOST_FACTOR = 0.15
    cfg.SENTIMENT_CONFLICT_ACTION = "delay"
    cfg.MAX_DELAY_MINUTES = 120
    cfg.FOLLOWUP_ENABLED = True
    cfg.AVOID_MAJOR_NEWS_TIMES = False
    cfg.INTRADAY_START_HOUR = 8
    cfg.INTRADAY_END_HOUR = 20
    cfg.OPERATING_WEEKDAYS = [0, 1, 2, 3, 4]
    cfg.RISK_AMOUNT_MODE = "PERCENT"
    cfg.RISK_PER_TRADE_PERCENT = 1.0
    cfg.RISK_PER_TRADE_AMOUNT = 100.0
    return cfg


def _capture_account() -> AccountState:
    """AccountState canonico per la cattura — saldo neutro, no posizioni aperte."""
    return AccountState(
        balance=10000.0,
        equity=10000.0,
        free_margin=10000.0,
        open_positions=[],
        today_realized_pnl=0.0,
        starting_balance_of_day=10000.0,
    )


def _bar_time_repr(value) -> str:
    """Serializza time bar in modo deterministico (int unix → str ISO non disponibile)."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def main() -> int:
    fixture = []
    for s in SCENARIOS:
        mt5 = _mock_mt5_from_csv(s["csv"], s["symbol"], s["bar_offset"])
        bars = mt5.get_ohlc.return_value
        strategy_obj = IntradayStrategy(_capture_cfg(), mt5)
        setup = strategy_obj.analyze_symbol(s["symbol"], _capture_account(), sentiment=None)
        fixture.append({
            "scenario_id": s["scenario_id"],
            "symbol": s["symbol"],
            "csv": s["csv"],
            "bar_offset": s["bar_offset"],
            "expected_mix": s["expected_mix"],
            "input": {
                "bar_count": len(bars),
                "last_bar_time": _bar_time_repr(bars[-1]["time"]),
            },
            "output": dataclasses.asdict(setup),
        })

    out_dir = _REPO_ROOT / "tests" / "fixtures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "strategy_regression_baseline.json"
    out_path.write_text(
        json.dumps(fixture, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    print(f"Captured {len(fixture)} scenarios -> {out_path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
