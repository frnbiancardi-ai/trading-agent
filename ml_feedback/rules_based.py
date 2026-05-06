"""Simple rule-based filter using numpy/pandas."""
import pandas as pd
from pathlib import Path
import json

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    return df.sort_values("date").reset_index(drop=True)

def calc(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    return df

print("=== RULE-BASED FILTERS ===\n")

# Get stats for each condition
rules = []

for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[df["date"] >= "2020-01-01"]
    df = df.dropna()
    
    df["signal"] = (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    trades = df[df["signal"]].copy()
    
    # Calculate WR for different hours
    hours = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
    for h in hours:
        t = trades[trades["hour"] == h]
        if len(t) >= 30:
            wr = t["win"].mean()
            rules.append({"sym": sym, "hour": h, "trades": len(t), "wr": wr})

# Aggregate by hour
hour_stats = {}
for r in rules:
    h = r["hour"]
    if h not in hour_stats:
        hour_stats[h] = {"trades": 0, "wins": 0}
    hour_stats[h]["trades"] += r["trades"]
    hour_stats[h]["wins"] += r["trades"] * r["wr"]

# Find best hours
best_hours = []
for h, d in hour_stats.items():
    wr = d["wins"] / d["trades"] if d["trades"] > 0 else 0
    if d["trades"] >= 50:
        best_hours.append((h, wr, d["trades"]))

best_hours.sort(key=lambda x: x[1], reverse=True)

print("Top 10 ore per WR:")
for h, wr, trades in best_hours[:10]:
    print(f"  H{h:02d}: {trades} trades, WR={wr*100:.1f}%")

# Best hour combo
best_h = best_hours[0][0]
print(f"\nBest hour: H{best_h:02d}")

# Test on 2024
print("\n=== TEST 2024 ===")
total = 0
wins = 0
for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[df["date"].dt.year == 2024]
    df = df.dropna()
    
    df["signal"] = (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    # Filter by best hours
    d = df[df["signal"] & (df["hour"].isin([h[0] for h in best_hours[:3]]))]
    if len(d) > 0:
        total += len(d)
        wins += d["win"].sum()
        print(f"  {sym}: {len(d)} trades, WR={d['win'].mean()*100:.1f}%")

print(f"\n  TOTALE: {total} trades, WR={wins/total*100:.1f}%")

print("\nDone")