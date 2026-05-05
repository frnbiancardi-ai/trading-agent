"""Download dati storici MT5 multi-simbolo multi-timeframe.

Salva CSV in data/historical/<symbol>/<timeframe>.csv
Formato compatibile con BacktestMt5Client.

LIMIT BROKER NOTI (TenTrade demo, verificato 2026-05):
- M1:  ~1 anno
- M5:  ~2 anni
- M15: ~4 anni (da 2022-04)
- H1:  ~16 anni (da 2010-03)
- H4:  25+ anni (da 2000)
- D1:  25+ anni (da 2000)

Per backtest M15 oltre 4 anni: usa scripts/import_histdata.py
con dataset HistData.com.
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
}

# Cap massimo anni storia per TF (TenTrade). Override con --no-cap.
TF_MAX_YEARS = {
    "M1": 1,
    "M5": 2,
    "M15": 4,
    "M30": 6,
    "H1": 16,
    "H4": 25,
    "D1": 25,
    "W1": 25,
}

DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "NZDUSD", "USDCAD",
    "XAUUSD", "USOIL",
]


def download_symbol(symbol: str, tf_name: str, start: datetime, end: datetime) -> list[dict]:
    """Scarica barre per simbolo+TF nel range [start, end]."""
    tf = TIMEFRAMES[tf_name]
    if not mt5.symbol_select(symbol, True):
        print(f"  symbol_select fail: {mt5.last_error()}")
        return []
    rates = mt5.copy_rates_range(symbol, tf, start, end)
    if rates is None or len(rates) == 0:
        return []
    bars = []
    for r in rates:
        bars.append({
            "time": int(r["time"]),
            "datetime": datetime.fromtimestamp(r["time"]).isoformat(),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "tick_volume": int(r["tick_volume"]),
            "spread": int(r["spread"]) if "spread" in r.dtype.names else 0,
        })
    return bars


def save_csv(bars: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not bars:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=bars[0].keys())
        writer.writeheader()
        writer.writerows(bars)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download history MT5 → CSV")
    parser.add_argument("--years", type=int, default=10,
                        help="Anni storia richiesti (default 10). Cap automatico per TF.")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--timeframes", nargs="+", default=["M15", "H1", "H4", "D1"])
    parser.add_argument("--output-dir", default="data/historical")
    parser.add_argument("--no-cap", action="store_true",
                        help="Disabilita cap per TF (proverà comunque anni richiesti)")
    args = parser.parse_args()

    if not mt5.initialize():
        print(f"FATAL: MT5 init failed: {mt5.last_error()}")
        return 1

    ti = mt5.terminal_info()
    if not ti or not ti.connected:
        print(f"FATAL: MT5 non connesso. Apri terminal + login.")
        mt5.shutdown()
        return 1

    end = datetime.now()
    out_dir = Path(args.output_dir)

    print(f"Account: {mt5.account_info().login if mt5.account_info() else '?'} "
          f"@ {mt5.account_info().server if mt5.account_info() else '?'}")
    print(f"Anni richiesti: {args.years}")
    print(f"Simboli: {args.symbols}")
    print(f"Timeframes: {args.timeframes}")
    if not args.no_cap:
        print(f"Cap per TF: {TF_MAX_YEARS}")
    print()

    summary: dict[str, int] = {}

    for sym in args.symbols:
        for tf in args.timeframes:
            cap = args.years if args.no_cap else min(args.years, TF_MAX_YEARS.get(tf, args.years))
            start = end - timedelta(days=365 * cap)
            print(f"→ {sym} {tf} ({cap}y, da {start.date()})...", end=" ", flush=True)
            bars = download_symbol(sym, tf, start, end)
            if bars:
                path = out_dir / sym / f"{tf}.csv"
                save_csv(bars, path)
                first = datetime.fromtimestamp(bars[0]["time"]).date()
                last = datetime.fromtimestamp(bars[-1]["time"]).date()
                print(f"{len(bars):,} barre ({first} → {last})")
                summary[f"{sym}/{tf}"] = len(bars)
            else:
                print(f"VUOTO (err={mt5.last_error()})")
                summary[f"{sym}/{tf}"] = 0

    mt5.shutdown()

    total = sum(summary.values())
    successful = sum(1 for v in summary.values() if v > 0)
    print(f"\nRisultato: {successful}/{len(summary)} dataset, {total:,} barre totali")
    return 0


if __name__ == "__main__":
    sys.exit(main())
