"""Importa dati Yahoo Finance via yfinance -> formato BacktestMt5Client.

Yahoo fornisce dati gratis per:
- Forex pairs (EURUSD=X, GBPUSD=X, ecc.)
- Futures (GC=F gold, CL=F oil, SI=F silver)
- Indici (^SPX, ^GSPC, ^DJI)
- Crypto (BTC-USD, ETH-USD)

LIMIT yfinance:
- M1 intraday: ultimi 7 giorni
- M5/M15/M30: ultimi 60 giorni
- H1: ultimi 730 giorni (~2 anni)
- D1: 30+ anni

Per Gold/Oil/SPX D1: copertura ottima.
Per Gold/Oil intraday: usare Dukascopy.

Setup:
    pip install yfinance

Esempio:
    python scripts/import_yfinance.py --ticker GC=F --symbol XAUUSD --interval 1d --years 10
    python scripts/import_yfinance.py --ticker CL=F --symbol USOIL --interval 1d --years 10
    python scripts/import_yfinance.py --ticker ^GSPC --symbol SPX500 --interval 1d --years 10
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("FATAL: yfinance non installato. Esegui: pip install yfinance")
    sys.exit(1)


# Mapping interval yfinance -> nome TF interno
INTERVAL_TO_TF = {
    "1m": "M1",
    "2m": "M2",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "60m": "H1",
    "1h": "H1",
    "4h": "H4",  # nota: yfinance non supporta 4h nativo, va aggregato da 1h
    "1d": "D1",
    "5d": "W1",
    "1wk": "W1",
}


def df_to_bars(df) -> list[dict]:
    """Converte DataFrame yfinance in lista dict bars OHLC."""
    bars = []
    for idx, row in df.iterrows():
        # idx è Timestamp pandas
        try:
            ts = int(idx.timestamp())
        except Exception:
            continue
        # Estrai valori scalari (alcune chiamate yfinance restituiscono tuple/Series)
        def _scalar(v):
            try:
                # Se Series con un valore
                if hasattr(v, "iloc"):
                    return float(v.iloc[0])
                return float(v)
            except (TypeError, ValueError):
                return 0.0
        o = _scalar(row["Open"])
        h = _scalar(row["High"])
        l = _scalar(row["Low"])
        c = _scalar(row["Close"])
        v = _scalar(row.get("Volume", 0))
        if o == 0 and h == 0 and c == 0:
            continue  # skip righe vuote
        bars.append({
            "time": ts,
            "datetime": idx.isoformat(),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "tick_volume": int(v) if v > 0 else 1,
        })
    return bars


def save_csv(bars: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "datetime", "open", "high", "low", "close", "tick_volume"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for b in bars:
            w.writerow({k: b.get(k) for k in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description="Yahoo Finance -> MT5-format CSV")
    parser.add_argument("--ticker", required=True,
                        help="Yahoo ticker (es. GC=F, CL=F, ^GSPC, EURUSD=X, BTC-USD)")
    parser.add_argument("--symbol", required=True,
                        help="Nome simbolo interno output (es. XAUUSD, USOIL, SPX500)")
    parser.add_argument("--interval", default="1d",
                        choices=list(INTERVAL_TO_TF.keys()),
                        help="Intervallo yfinance (1m/5m/15m/60m/1d ecc.)")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--start", help="Data inizio YYYY-MM-DD (override --years)")
    parser.add_argument("--end", help="Data fine YYYY-MM-DD (default oggi)")
    parser.add_argument("--output-dir", default="data/historical")
    args = parser.parse_args()

    end = datetime.fromisoformat(args.end) if args.end else datetime.now()
    if args.start:
        start = datetime.fromisoformat(args.start)
    else:
        start = end - timedelta(days=365 * args.years)

    print(f"Download {args.ticker} ({args.interval}) da {start.date()} a {end.date()}...")

    df = yf.download(
        args.ticker,
        start=start,
        end=end,
        interval=args.interval,
        progress=False,
        auto_adjust=False,
    )

    if df is None or len(df) == 0:
        print(f"FATAL: nessun dato per {args.ticker}. Verifica ticker / interval.")
        return 1

    # Flatten MultiIndex columns se presente (yfinance v0.2.40+)
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = [c[0] for c in df.columns]

    print(f"Ricevute {len(df)} barre raw")

    bars = df_to_bars(df)
    if not bars:
        print("FATAL: nessuna barra valida dopo conversione.")
        return 1

    tf_name = INTERVAL_TO_TF.get(args.interval, args.interval.upper())
    out_path = Path(args.output_dir) / args.symbol / f"{tf_name}.csv"
    save_csv(bars, out_path)

    first = datetime.fromtimestamp(bars[0]["time"]).date()
    last = datetime.fromtimestamp(bars[-1]["time"]).date()
    print(f"OK: {len(bars):,} barre {tf_name} ({first} -> {last}) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
