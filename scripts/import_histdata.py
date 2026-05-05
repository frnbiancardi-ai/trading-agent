"""Importa CSV HistData.com → formato compatibile BacktestMt5Client.

HistData.com fornisce dati M1 forex gratis dal 2000+.
Download manuale (no API): https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurusd

Formato HistData M1 ASCII:
    YYYYMMDD HHMMSS;OPEN;HIGH;LOW;CLOSE;VOLUME
    20100104 000000;1.43275;1.43286;1.43275;1.43286;0

Workflow:
    1. Scarica zip mensili HistData (uno per mese, ~50KB)
    2. Estrai tutti in data/histdata/EURUSD/
    3. Esegui: python scripts/import_histdata.py --input-dir data/histdata/EURUSD --symbol EURUSD

Output: data/historical/EURUSD/{M15,H1,H4,D1}.csv (formato MT5-style).
"""
import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Minuti per timeframe
TF_MINUTES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
}


def parse_histdata_line(line: str) -> dict | None:
    """Parsa riga formato HistData M1."""
    parts = line.strip().split(";")
    if len(parts) < 5:
        return None
    try:
        dt = datetime.strptime(parts[0], "%Y%m%d %H%M%S")
        return {
            "time": int(dt.timestamp()),
            "open": float(parts[1]),
            "high": float(parts[2]),
            "low": float(parts[3]),
            "close": float(parts[4]),
            "tick_volume": int(parts[5]) if len(parts) > 5 and parts[5] else 1,
        }
    except (ValueError, IndexError):
        return None


def aggregate_m1_to_tf(m1_bars: list[dict], tf_minutes: int) -> list[dict]:
    """Aggrega M1 in barre TF maggiori. Buckets fissi su epoch."""
    if tf_minutes == 1:
        return m1_bars
    seconds = tf_minutes * 60
    buckets: dict[int, list[dict]] = defaultdict(list)
    for b in m1_bars:
        bucket_ts = (b["time"] // seconds) * seconds
        buckets[bucket_ts].append(b)
    out = []
    for ts in sorted(buckets.keys()):
        group = buckets[ts]
        # Ordina per time interno bucket per garantire OHLC coerente
        group.sort(key=lambda x: x["time"])
        out.append({
            "time": ts,
            "datetime": datetime.fromtimestamp(ts).isoformat(),
            "open": group[0]["open"],
            "high": max(g["high"] for g in group),
            "low": min(g["low"] for g in group),
            "close": group[-1]["close"],
            "tick_volume": sum(g["tick_volume"] for g in group),
        })
    return out


def load_all_histdata(in_dir: Path) -> list[dict]:
    """Carica tutti CSV M1 da directory ordinati per time."""
    all_m1: list[dict] = []
    csv_files = sorted(in_dir.glob("*.csv"))
    if not csv_files:
        return []
    for csv_file in csv_files:
        count_before = len(all_m1)
        with open(csv_file, encoding="utf-8") as f:
            for line in f:
                bar = parse_histdata_line(line)
                if bar:
                    all_m1.append(bar)
        added = len(all_m1) - count_before
        print(f"  {csv_file.name}: +{added:,} barre")
    # Ordina per time + dedup (HistData può avere overlap su confini mese)
    all_m1.sort(key=lambda x: x["time"])
    deduped = []
    seen = set()
    for b in all_m1:
        if b["time"] not in seen:
            seen.add(b["time"])
            deduped.append(b)
    return deduped


def save_csv(bars: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "datetime", "open", "high", "low", "close", "tick_volume"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for b in bars:
            row = {k: b.get(k) for k in fields}
            if "datetime" not in b or not b["datetime"]:
                row["datetime"] = datetime.fromtimestamp(b["time"]).isoformat()
            w.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="HistData M1 → MT5-format CSV")
    parser.add_argument("--input-dir", required=True,
                        help="Directory con CSV M1 HistData (es. data/histdata/EURUSD)")
    parser.add_argument("--symbol", required=True, help="Nome simbolo output (es. EURUSD)")
    parser.add_argument("--timeframes", nargs="+", default=["M15", "H1", "H4", "D1"])
    parser.add_argument("--output-dir", default="data/historical")
    parser.add_argument("--keep-m1", action="store_true",
                        help="Salva anche M1 raw (file grosso ~500MB per 10y)")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    if not in_dir.is_dir():
        print(f"FATAL: input dir non esiste: {in_dir}")
        return 1

    out_dir = Path(args.output_dir) / args.symbol
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Lettura CSV M1 da {in_dir}...")
    all_m1 = load_all_histdata(in_dir)

    if not all_m1:
        print("FATAL: nessuna barra M1 valida trovata. Verifica formato HistData ASCII.")
        return 1

    first = datetime.fromtimestamp(all_m1[0]["time"])
    last = datetime.fromtimestamp(all_m1[-1]["time"])
    print(f"\nTotale M1 dedupli: {len(all_m1):,}")
    print(f"Range: {first} → {last}")
    span_years = (last - first).days / 365.25
    print(f"Span: {span_years:.1f} anni\n")

    if args.keep_m1:
        m1_path = out_dir / "M1.csv"
        save_csv(all_m1, m1_path)
        print(f"  M1: {len(all_m1):,} barre → {m1_path}")

    for tf in args.timeframes:
        if tf not in TF_MINUTES:
            print(f"  Skip TF sconosciuto: {tf}")
            continue
        bars = aggregate_m1_to_tf(all_m1, TF_MINUTES[tf])
        out_path = out_dir / f"{tf}.csv"
        save_csv(bars, out_path)
        print(f"  {tf}: {len(bars):,} barre → {out_path}")

    print(f"\nDataset {args.symbol} pronto in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
