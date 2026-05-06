"""Monte Carlo simulation per robustezza."""
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
import random

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

def get_trades(df):
    """Get all trades con outcome."""
    df = df.dropna()
    df["signal"] = (df["hour"] == 15) & (df["rsi"] >= 65) & (df["rsi"] <= 80) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    return df[df["signal"]]["win"].values

# Collect all trades from 2020-2024
print("=== COLLECTING TRADES ===\n")
all_wins = []

for years, label in [("2020-2023", "Train"), ("2024-2024", "Test")]:
    for sym in SYMS:
        df = load_csv(sym)
        df = calc(df)
        
        if "Train" in label:
            df = df[(df["date"] >= "2020-01-01") & (df["date"] < "2024-01-01")]
        else:
            df = df[(df["date"] >= "2024-01-01") & (df["date"] < "2025-01-01")]
        
        trades = get_trades(df)
        all_wins.extend(trades)
        print(f"{label} {sym}: {len(trades)} trades, WR={trades.mean()*100:.1f}%")

all_wins = np.array(all_wins)
print(f"\nTOTALE: {len(all_wins)} trades, WR={all_wins.mean()*100:.1f}%")

# Monte Carlo: shuffle trade outcomes N times
print("\n=== MONTE CARLO SIMULATION ===")
N_SIMULATIONS = 10000

results = []
for i in range(N_SIMULATIONS):
    # Shuffle outcomes
    shuffled = all_wins.copy()
    np.random.shuffle(shuffled)
    
    # Calculate WR for each block of same size as test
    test_size = 385  # actual test size
    for _ in range(10):  # 10 blocks per simulation
        block = shuffled[:test_size]
        wr = block.mean()
        results.append(wr)

results = np.array(results) * 100

print(f"\n{N_SIMULATIONS} simulations x 10 blocks = {len(results)} samples")
print(f"Mean WR: {results.mean():.1f}%")
print(f"Std Dev: {results.std():.1f}%")

# Confidence intervals
print(f"\n95% CI: [{np.percentile(results, 2.5):.1f}%, {np.percentile(results, 97.5):.1f}%]")
print(f"90% CI: [{np.percentile(results, 5):.1f}%, {np.percentile(results, 95):.1f}%]")
print(f"99% CI: [{np.percentile(results, 0.5):.1f}%, {np.percentile(results, 99.5):.1f}%]")

# Probability of beating 50%
p50 = (results > 50).mean() * 100
print(f"\nP(WR > 50%): {p50:.1f}%")

# Probability of beating 55%
p55 = (results > 55).mean() * 100
print(f"P(WR > 55%): {p55:.1f}%")

# Probability of beating 60%
p60 = (results > 60).mean() * 100
print(f"P(WR > 60%): {p60:.1f}%")

# Worst case
print(f"\nWorst 1%: {np.percentile(results, 1):.1f}%")
print(f"Best 1%: {np.percentile(results, 99):.1f}%")

print("\nDone")