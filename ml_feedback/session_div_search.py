"""Session & RSI divergence search."""
import pandas as pd
from pathlib import Path
from collections import defaultdict

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    return df[(df["date"] >= "2020-01-01") & (df["date"] < "2025-01-01")].sort_values("date").reset_index(drop=True)

def calc_indicators(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    
    # RSI divergence: price up, RSI down
    df["price_change"] = df[" Close"] - df[" Close"].shift(3)
    df["rsi_change"] = df["rsi"] - df["rsi"].shift(3)
    df["divergence"] = (df["price_change"] > 0) & (df["rsi_change"] < -2)
    
    return df.dropna()

# Sessions (UTC)
# NY: 13:00-18:00
# London: 8:00-12:00
# Asia: 0:00-7:00

def test_config(df, name, rsi_min, rsi_max, hour_start=None, hour_end=None, divergence=False):
    d = df[df["date"] >= "2024-01-01"].copy()
    
    d = d[(d["rsi"] >= rsi_min) & (d["rsi"] <= rsi_max)]
    d = d[d[" Close"] > d["sma200"]]
    
    if hour_start is not None:
        if hour_end is None:
            hour_end = hour_start + 4
        d = d[(d["hour"] >= hour_start) & (d["hour"] < hour_end)]
    
    if divergence:
        d = d[d["divergence"]]
    
    if len(d) == 0:
        return {"trades": 0, "wr": 0}
    
    d["next2"] = d[" Close"].shift(-2)
    d["win"] = d["next2"] < d[" Close"]
    
    wr = d["win"].sum() / len(d) * 100
    return {"trades": len(d), "wr": round(wr, 1)}

print("=== SESSION + DIVERGENCE SEARCH ===\n")

configs = [
    # Base
    ("base", 65, 90, None, None, False),
    
    # RSI ranges
    ("rsi_70_90", 70, 90, None, None, False),
    ("rsi_75_90", 75, 90, None, None, False),
    ("rsi_70_85", 70, 85, None, None, False),
    
    # Sessions
    ("asia", 65, 90, 0, 7, False),
    ("london", 65, 90, 8, 12, False),
    ("ny", 65, 90, 13, 18, False),
    
    # Session + RSI
    ("london_70_90", 70, 90, 8, 12, False),
    ("london_75_90", 75, 90, 8, 12, False),
    ("ny_70_90", 70, 90, 13, 18, False),
    ("ny_75_90", 75, 90, 13, 18, False),
    
    # Divergence
    ("div", 65, 90, None, None, True),
    ("ny_div", 65, 90, 13, 18, True),
    
    # Best combos
    ("london_div", 75, 90, 8, 12, True),
]

results = []
for sym in SYMS:
    df = load_csv(sym)
    df = calc_indicators(df)
    
    for cfg in configs:
        name, rsi_min, rsi_max, hs, he, div = cfg
        r = test_config(df, name, rsi_min, rsi_max, hs, he, div)
        r["symbol"] = sym
        r["name"] = name
        results.append(r)

# Aggregate
agg = defaultdict(lambda: {"trades": 0, "wins": 0})
for r in results:
    agg[r["name"]]["trades"] += r["trades"]
    agg[r["name"]]["wins"] += r["trades"] * r["wr"] / 100

for name, d in agg.items():
    d["wr"] = round(d["wins"] / d["trades"] * 100, 1) if d["trades"] > 0 else 0

sorted_results = sorted(agg.items(), key=lambda x: x[1]["wr"], reverse=True)

print(" Risultati aggregated (3 symbol, 2024):")
print("-" * 50)
for name, d in sorted_results[:15]:
    print(f"{name:15} {d['trades']:5} trades, WR={d['wr']}%")

print("\nDone")