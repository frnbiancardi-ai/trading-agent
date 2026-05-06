#!/usr/bin/env python3
"""
Converte dati M1 HistData in timeframe superiori (M15, H1, H4, D1).
Legge tutti i CSV M1 da una directory, li aggrega e salva i nuovi timeframe.

Uso:
    python scripts/import_histdata.py --input-dir data/historical/EURUSD --symbol EURUSD
"""

import argparse
import os
import glob
import pandas as pd
from pathlib import Path


def parse_histdata_csv(filepath: str) -> pd.DataFrame:
    """
    Parsa un file CSV HistData M1.
    Formato: YYYYMMDD HHMMSS;Open;High;Low;Close;Volume
    """
    df = pd.read_csv(
        filepath,
        sep=";",
        header=None,
        names=["datetime", "open", "high", "low", "close", "volume"],
        dtype={
            "datetime": str,
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": float,
        },
    )

    # Converte datetime
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d %H%M%S")
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)

    return df


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """
    Ricalcola OHLCV per un timeframe specifico.
    rule: '15T' (M15), '1H' (H1), '4H' (H4), '1D' (D1)
    """
    agg_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    resampled = df.resample(rule).agg(agg_dict)
    resampled.dropna(subset=["open"], inplace=True)
    return resampled


def save_csv(df: pd.DataFrame, output_path: str, timeframe: str):
    """
    Salva il DataFrame come CSV.
    Formato: date,time,open,high,low,close,volume
    """
    with open(output_path, "w") as f:
        f.write("date,time,open,high,low,close,volume\n")
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y.%m.%d")
            time_str = idx.strftime("%H:%M")
            f.write(
                f"{date_str},{time_str},{row['open']:.5f},{row['high']:.5f},{row['low']:.5f},{row['close']:.5f},{row['volume']:.0f}\n"
            )


def main():
    parser = argparse.ArgumentParser(description="Converte dati M1 HistData in timeframe superiori")
    parser.add_argument("--input-dir", required=True, help="Directory con i CSV M1")
    parser.add_argument("--symbol", required=True, help="Simbolo forex (es. EURUSD)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    symbol = args.symbol

    print(f"Simbolo: {symbol}")
    print(f"Directory: {input_dir}")

    # Trova tutti i CSV M1
    m1_files = sorted(input_dir.glob("DAT_ASCII_*_M1_*.csv"))
    if not m1_files:
        print(f"Nessun file M1 trovato in {input_dir}")
        return

    print(f"File M1 trovati: {len(m1_files)}")

    # Carica e concatena tutti i dati M1
    dfs = []
    for f in m1_files:
        print(f"  Caricamento: {f.name}")
        df = parse_histdata_csv(str(f))
        dfs.append(df)

    m1_data = pd.concat(dfs)
    m1_data.sort_index(inplace=True)
    m1_data = m1_data[~m1_data.index.duplicated(keep="first")]

    print(f"  Righe M1 totali: {len(m1_data):,}")
    print(f"  Periodo: {m1_data.index.min()} -> {m1_data.index.max()}")

    # Timeframe da generare
    timeframes = {
        "M15": "15T",
        "H1": "1H",
        "H4": "4H",
        "D1": "1D",
    }

    for tf_name, rule in timeframes.items():
        output_file = input_dir / f"{tf_name}.csv"

        if output_file.exists():
            print(f"  [SKIP] {tf_name}.csv esiste già")
            continue

        print(f"  Generazione {tf_name}...")
        tf_data = resample_ohlc(m1_data, rule)
        save_csv(tf_data, str(output_file), tf_name)
        print(f"  [OK] {tf_name}.csv ({len(tf_data):,} righe)")

    print(f"\nCompletato! File nella directory: {input_dir}")
    csv_files = list(input_dir.glob("*.csv"))
    print(f"  Totale CSV: {len(csv_files)}")


if __name__ == "__main__":
    main()
