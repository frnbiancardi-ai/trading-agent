"""Verify backtest - check simple."""
import pandas as pd
from pathlib import Path

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    return df[(df["date"] >= "2024-01-01") & (df["date"] < "2025-01-01")].sort_values("date").reset_index(drop=True)

def calc_indicators(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    return df.dropna()

print("=== VERIFY ===")
for sym in SYMS:
    df = load_csv(sym)
    df = calc_indicators(df)
    
    # Signal: RSI 65-90 + price > SMA200
    df["signal"] = (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next_close2"] = df[" Close"].shift(-2)
    df["win"] = df["next_close2"] < df[" Close"]
    
    trades = df[df["signal"]]
    if len(trades) > 0:
        wr = trades["win"].sum() / len(trades) * 100
        print(f"{sym}: {len(trades)} trades, WR={wr:.1f}%")
    else:
        print(f"{sym}: 0 trades")

print("Done")