"""Backtest engine per strategie forex.

Use: python backtest.py [--strategy pullback|mean_reversion] [--symbol EURUSD] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Generator


def parse_csv_bars(path: Path, symbol: str) -> Generator[dict, None, None]:
    """Parse CSV storico in bar dict."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        fieldnames = [fn.strip() for fn in reader.fieldnames]
        for row in reader:
            try:
                date_str = row["Data"].strip()
                time_str = row[" Ora"].strip()
                dt_str = f"{date_str} {time_str}"
                dt = datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S")
                yield {
                    "time": dt,
                    "open": float(row[" Open"].strip()),
                    "high": float(row[" High"].strip()),
                    "low": float(row[" low"].strip()),
                    "close": float(row[" Close"].strip()),
                    "volume": int(row[" Volume"].strip()) if row.get(" Volume") else 0,
                }
            except (KeyError, ValueError) as e:
                continue


def load_bars(
    symbol: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    """Carica bar da CSV storico."""
    base = Path("data/historical")
    tf_map = {"M15": "M15", "M30": "M30", "H1": "H1"}
    tf = tf_map.get(timeframe, "M15")
    fpath = base / symbol / f"{tf}.csv"

    if not fpath.exists():
        print(f"File non trovato: {fpath}", file=sys.stderr)
        return []

    bars = list(parse_csv_bars(fpath, symbol))

    if start:
        bars = [b for b in bars if b["time"] >= start]
    if end:
        bars = [b for b in bars if b["time"] <= end]

    print(f"Caricati {len(bars)} bar {symbol} {tf} ({start or 'inizio'} -> {end or 'fine'})")
    return bars


class BacktestResult:
    def __init__(self):
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.profit_total = 0.0
        self.max_drawdown = 0.0
        self.win_rate = 0.0
        self.avg_r = 0.0

    def add_trade(self, r: float):
        self.total_trades += 1
        if r > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        self.profit_total += r
        if self.total_trades > 1:
            self.max_drawdown = min(self.max_drawdown, r)
        if r != 0:
            self.avg_r = (self.avg_r * (self.total_trades - 1) + r) / self.total_trades

    def finalize(self):
        if self.total_trades > 0:
            self.win_rate = self.winning_trades / self.total_trades
        return self

    def __repr__(self):
        return (
            f"Trades: {self.total_trades} | "
            f"W: {self.winning_trades} L: {self.losing_trades} | "
            f"WR: {self.win_rate:.1%} | "
            f"Profit: {self.profit_total:.2f}R | "
            f"AvgR: {self.avg_r:.2f}"
        )


def run_backtest(
    strategy_fn,
    bars: list[dict],
    config: dict,
) -> BacktestResult:
    """Esegue backtest generico."""
    from indicators import bollinger_bands, rsi, sma

    result = BacktestResult()

    period_ma = config.get("ma_period", 50)
    period_rsi = config.get("rsi_period", 14)
    period_atr = config.get("atr_period", 14)

    pip_size = 0.0001 if "JPY" not in config.get("symbol", "EURUSD") else 0.01

    for i in range(period_ma + period_rsi + 10, len(bars) - 1):
        window = bars[: i + 1]
        last = window[-1]

        closes = [b["close"] for b in window]
        highs = [b["high"] for b in window]
        lows = [b["low"] for b in window]

        sma_val = sma(closes, period_ma)
        sma20 = sma(closes, 20)
        rsi_val = rsi(closes, period_rsi)

        last_close = last["close"]
        last_sma = sma_val[-1] if sma_val else None
        last_sma20 = sma20[-1] if sma20 else None
        last_rsi = rsi_val[-1] if rsi_val else None

        if last_sma is None or last_sma20 is None or last_rsi is None:
            continue

        setup = strategy_fn(
            close=last_close,
            sma=last_sma,
            sma20=last_sma20,
            rsi=last_rsi,
            pip_size=pip_size,
            config=config,
        )

        if setup["type"] == "NONE":
            continue

        next_bar = bars[i + 1]
        entry = setup.get("entry", last_close)
        direction = setup["direction"]

        if direction == "BUY":
            sl = setup.get("sl", entry - config["min_sl_pips"] * pip_size)
            tp = setup.get("tp", entry + config["min_tp_pips"] * pip_size)

            if next_bar["low"] <= sl:
                result.add_trade(-1.0)
            elif next_bar["high"] >= tp:
                r_mult = (tp - entry) / (entry - sl)
                result.add_trade(r_mult)
        else:
            sl = setup.get("sl", entry + config["min_sl_pips"] * pip_size)
            tp = setup.get("tp", entry - config["min_tp_pips"] * pip_size)

            if next_bar["high"] >= sl:
                result.add_trade(-1.0)
            elif next_bar["low"] <= tp:
                r_mult = (entry - tp) / (sl - entry)
                result.add_trade(r_mult)

    return result.finalize()


def strategy_pullback(close, sma, sma20, rsi, pip_size, config) -> dict:
    """Strategia pullback/trend continuation."""
    bullish_align = close > sma20 > sma
    bearish_align = close < sma20 < sma
    rsi_ok = config["min_rsi"] < rsi < config["max_rsi"]
    trend_ok = rsi > config["min_trend_strength"]

    pip = pip_size

    if bullish_align and rsi_ok and trend_ok:
        return {
            "type": "READY",
            "direction": "BUY",
            "entry": close,
            "sl": close - config["min_sl_pips"] * pip,
            "tp": close + config["min_sl_pips"] * config["min_rr"] * pip,
        }
    if bearish_align and rsi_ok and trend_ok:
        return {
            "type": "READY",
            "direction": "SELL",
            "entry": close,
            "sl": close + config["min_sl_pips"] * pip,
            "tp": close - config["min_sl_pips"] * config["min_rr"] * pip,
        }

    return {"type": "NONE", "direction": None}


def strategy_mean_reversion(close, sma, sma20, rsi, pip_size, config) -> dict:
    """Strategia mean reversion su RSI + Bollinger estremi."""
    pip = pip_size
    max_trend = config.get("max_trend_strength", 0.35)
    rsi_buy_extreme = config.get("rsi_buy_extreme", 25)
    rsi_sell_extreme = config.get("rsi_sell_extreme", 75)
    bb_period = config.get("bb_period", 20)
    bb_std = config.get("bb_std", 2.0)

    if rsi <= rsi_buy_extreme:
        return {
            "type": "READY",
            "direction": "BUY",
            "entry": close,
            "sl": close - config["min_sl_pips"] * pip,
            "tp": close + config["min_sl_pips"] * config.get("min_rr", 1.0) * pip,
        }
    if rsi >= rsi_sell_extreme:
        return {
            "type": "READY",
            "direction": "SELL",
            "entry": close,
            "sl": close + config["min_sl_pips"] * pip,
            "tp": close - config["min_sl_pips"] * config.get("min_rr", 1.0) * pip,
        }

    return {"type": "NONE", "direction": None}


SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
TIMEFRAMES = ["M15", "M30", "H1"]


def main():
    parser = argparse.ArgumentParser(description="Backtest strategie forex")
    parser.add_argument(
        "--strategy",
        choices=["pullback", "mean_reversion"],
        default="pullback",
    )
    parser.add_argument("--symbol", choices=SYMBOLS, default="EURUSD")
    parser.add_argument("--timeframe", choices=TIMEFRAMES, default="M15")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2025-12-31")
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")

    bars = load_bars(args.symbol, args.timeframe, start_dt, end_dt)

    if not bars:
        print("Nessun dato caricato", file=sys.stderr)
        sys.exit(1)

    config = {
        "symbol": args.symbol,
        "ma_period": 50,
        "rsi_period": 14,
        "atr_period": 14,
        "min_sl_pips": 15,
        "min_tp_pips": 25,
        "min_rr": 1.5,
        "min_rsi": 30,
        "max_rsi": 70,
        "min_trend_strength": 0.6,
        "max_trend_strength": 0.35,
        "rsi_buy_extreme": 25,
        "rsi_sell_extreme": 75,
        "bb_period": 20,
        "bb_std": 2.0,
    }

    strategy_fn = (
        strategy_mean_reversion
        if args.strategy == "mean_reversion"
        else strategy_pullback
    )

    print(f"\n=== Backtest {args.strategy} | {args.symbol} {args.timeframe} ===")
    print(f" Periodo: {args.start} -> {args.end}")

    result = run_backtest(strategy_fn, bars, config)
    print(f"\nRisultato: {result}")


if __name__ == "__main__":
    main()