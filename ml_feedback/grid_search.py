"""Grid search filtri per ottimizzare WR."""
import pandas as pd
import json
from pathlib import Path
from itertools import product

TF = "M15"
SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / f"{TF}.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    df = df[(df["date"] >= "2020-01-01") & (df["date"] < "2025-01-01")].copy()
    return df.sort_values("date").reset_index(drop=True)

def calc_indicators(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    
    # SMA slope (trend strength)
    df["sma_slope"] = df["sma200"].diff(10) / df["sma200"] * 10000
    
    # Previous candle
    df["prev_close"] = df[" Close"].shift(1)
    df["prev_direction"] = df[" Close"] - df["prev_close"]
    
    return df.dropna()

def backtest_one(df, config):
    """Single backtest con config."""
    d = df.copy()
    
    # Hour filter
    if config.get("ny_only"):
        d = d[(d["hour"] >= 13) & (d["hour"] < 18)]
    
    # Specific hour
    if config.get("hour_start") is not None:
        d = d[(d["hour"] >= config["hour_start"]) & (d["hour"] < config.get("hour_end", config["hour_start"] + 2))]
    
    # RSI range
    rsi_min = config.get("rsi_min", 65)
    rsi_max = config.get("rsi_max", 90)
    d = d[(d["rsi"] >= rsi_min) & (d["rsi"] <= rsi_max)]
    
    # Price > SMA
    d = d[d[" Close"] > d["sma200"]]
    
    # SMA slope filter (trend direction)
    if config.get("sma_slope_req"):
        if config["sma_slope_req"] > 0:
            d = d[d["sma_slope"] > 0]  # SMA rising
        elif config["sma_slope_req"] < 0:
            d = d[d["sma_slope"] < 0]  # SMA falling
    
    # Prev direction filter (momentum)
    if config.get("prev_down"):
        d = d[d["prev_direction"] < 0]
    
    # Entry
    d["next_close"] = d[" Close"].shift(-2)
    d["win"] = d["next_close"] < d[" Close"]
    
    trades = d[d["win"].notna()]
    if len(trades) == 0:
        return {"trades": 0, "wr": 0}
    
    wr = trades["win"].sum() / len(trades) * 100
    return {"trades": len(trades), "wr": round(wr, 1)}

# Grid search configs
configs = [
    # Base
    {"name": "base", "rsi_min": 65, "rsi_max": 90},
    # Narrower RSI
    {"name": "rsi_70_90", "rsi_min": 70, "rsi_max": 90},
    {"name": "rsi_75_90", "rsi_min": 75, "rsi_max": 90},
    {"name": "rsi_80_90", "rsi_min": 80, "rsi_max": 90},
    # NY
    {"name": "ny", "ny_only": True, "rsi_min": 65, "rsi_max": 90},
    {"name": "ny_rsi70", "ny_only": True, "rsi_min": 70, "rsi_max": 90},
    {"name": "ny_rsi75", "ny_only": True, "rsi_min": 75, "rsi_max": 90},
    # Hour specific
    {"name": "hr_14_16", "hour_start": 14, "hour_end": 16, "rsi_min": 65, "rsi_max": 90},
    {"name": "hr_14_16_rsi75", "hour_start": 14, "hour_end": 16, "rsi_min": 75, "rsi_max": 90},
    # SMA slope
    {"name": "sma_rising", "rsi_min": 65, "rsi_max": 90, "sma_slope_req": 1},
    {"name": "ny_sma_rising", "ny_only": True, "rsi_min": 65, "rsi_max": 90, "sma_slope_req": 1},
    # Prev down
    {"name": "prev_down", "rsi_min": 65, "rsi_max": 90, "prev_down": True},
    {"name": "ny_prev_down", "ny_only": True, "rsi_min": 65, "rsi_max": 90, "prev_down": True},
    # Combo
    {"name": "combo1", "ny_only": True, "rsi_min": 75, "rsi_max": 90, "prev_down": True},
    {"name": "combo2", "ny_only": True, "rsi_min": 70, "rsi_max": 90, "sma_slope_req": 1},
]

print("=== GRID SEARCH FILTRI ===\n")

results = []
for sym in SYMS:
    df = load_csv(sym)
    df = calc_indicators(df)
    test = df[df["date"] >= "2024-01-01"]
    
    for cfg in configs:
        r = backtest_one(test, cfg)
        r["name"] = f"{sym}_{cfg['name']}"
        r["config"] = cfg
        results.append(r)

# Aggregate per config name
from collections import defaultdict
agg = defaultdict(lambda: {"trades": 0, "wins": 0})

for r in results:
    name = r["name"].split("_", 1)[1]  #去掉 symbol prefix
    agg[name]["trades"] += r["trades"]
    agg[name]["wins"] += r["trades"] * r["wr"] / 100

# Calculate WR
for name, d in agg.items():
    wr = d["wins"] / d["trades"] * 100 if d["trades"] > 0 else 0
    d["wr"] = round(wr, 1)

# Sort by WR
sorted_results = sorted(agg.items(), key=lambda x: x[1]["wr"], reverse=True)

print("Top 10 configurazioni (Test 2024):")
print("-" * 50)
for name, d in sorted_results[:10]:
    print(f"{name}: {d['trades']} trades, WR={d['wr']}%")

# Save best
best_name, best_d = sorted_results[0]
print(f"\nBest: {best_name} con WR={best_d['wr']}%")

with open("ml_feedback/grid_search.json", "w") as f:
    json.dump({k: v for k, v in agg.items()}, f, indent=2)

print("\nSaved: ml_feedback/grid_search.json")