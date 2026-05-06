"""Debug: hour filter."""
import pandas as pd
from pathlib import Path

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    return df[df["date"] >= "2024-01-01"].sort_values("date").reset_index(drop=True)

def calc(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    return df.dropna()

print("=== DEBUG HOUR FILTERS ===\n")

for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    
    # hour == 15
    a = df[(df["hour"] == 15) & (df["rsi"] >= 65) & (df["rsi"] <= 80) & (df[" Close"] > df["sma200"])]
    
    # hour >= 15
    b = df[(df["hour"] >= 15) & (df["rsi"] >= 65) & (df["rsi"] <= 80) & (df[" Close"] > df["sma200"])]
    
    print(f"{sym}: hour==15: {len(a)}, hour>=15: {len(b)}")

print("\nDone")