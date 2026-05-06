"""Analyze which conditions lead to wins vs losses."""
import pandas as pd
from pathlib import Path

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    df["day"] = df["date"].dt.dayofweek
    return df[(df["date"] >= "2024-01-01") & (df["date"] < "2025-01-01")].sort_values("date").reset_index(drop=True)

def calc(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    
    # ATR
    df["atr"] = (df[" High"] - df[" low"]).rolling(14).mean()
    df["atr_pct"] = df["atr"] / df[" Close"] * 10000  # in pips
    
    return df.dropna()

print("=== CONDITION ANALYSIS ===\n")

all_trades = []

for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    
    # Base signal
    df["signal"] = (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    trades = df[df["signal"]].copy()
    trades["symbol"] = sym
    all_trades.append(trades[["symbol", "hour", "day", "rsi", "atr_pct", "win"]])

df_all = pd.concat(all_trades, ignore_index=True)
df_all = df_all[df_all["win"].notna()]

print(f"Total trades: {len(df_all)}\n")

# Analyze by hour
print("WR by HOUR:")
print("-" * 30)
for hour in sorted(df_all["hour"].unique()):
    d = df_all[df_all["hour"] == hour]
    wr = d["win"].mean() * 100
    print(f"H{hour:02d}: {len(d):4} trades, WR={wr:.1f}%")

# Analyze by day
print("\nWR by DAY:")
print("-" * 30)
days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
for day in range(5):
    d = df_all[df_all["day"] == day]
    wr = d["win"].mean() * 100
    print(f"{days[day]:4}: {len(d):4} trades, WR={wr:.1f}%")

# Analyze by RSI bucket
print("\nWR by RSI:")
print("-" * 30)
for rsiMin in [65, 70, 75, 80]:
    d = df_all[(df_all["rsi"] >= rsiMin) & (df_all["rsi"] < rsiMin+10)]
    wr = d["win"].mean() * 100
    print(f"RSI {rsiMin}-{rsiMin+10}: {len(d):4} trades, WR={wr:.1f}%")

# By ATR bucket
print("\nWR by VOLATILITY (ATR pips):")
print("-" * 30)
for atr in [5, 8, 10, 12, 15]:
    d = df_all[df_all["atr_pct"] < atr]
    wr = d["win"].mean() * 100
    print(f"ATR <{atr}: {len(d):4} trades, WR={wr:.1f}%")

print("\nDone")