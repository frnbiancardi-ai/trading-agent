"""Test best combo: hour 15 + RSI 70-80."""
import pandas as pd
from pathlib import Path

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    return df[(df["date"] >= "2020-01-01") & (df["date"] < "2025-01-01")].sort_values("date").reset_index(drop=True)

def calc(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    return df.dropna()

print("=== BEST COMBO: H15 + RSI 70-80 ===\n")

# Train 2020-2023, Test 2024
for period, (start, end) in [("Train 2020-2023", ("2020-01-01", "2024-01-01")), ("Test 2024", ("2024-01-01", "2025-01-01"))]:
    print(f"=== {period} ===")
    
    total_wins = 0
    total_trades = 0
    results = []
    
    for sym in SYMS:
        df = load_csv(sym)
        df = calc(df)
        
        d = df[(df["date"] >= start) & (df["date"] < end)].copy()
        
        # Best: hour 15 + RSI 70-80 + price > SMA200
        d = d[(d["hour"] >= 15) & (d["hour"] < 16)]
        d = d[(d["rsi"] >= 70) & (d["rsi"] <= 80)]
        d = d[d[" Close"] > d["sma200"]]
        
        if len(d) == 0:
            continue
        
        d["next2"] = d[" Close"].shift(-2)
        d["win"] = (d["next2"] < d[" Close"]).astype(int)
        
        wins = d["win"].sum()
        trades = len(d)
        
        total_wins += wins
        total_trades += trades
        results.append((sym, trades, wins))
        
        wr = wins / trades * 100
        print(f"  {sym}: {trades} trades, WR={wr:.1f}%")
    
    if total_trades > 0:
        wr = total_wins / total_trades * 100
        print(f"\n  TOTALE: {total_trades} trades, WR={wr:.1f}%")
    print()

# Test also: H15 alone
print("=== H15 ONLY ===")
for period, (start, end) in [("Train", ("2020-01-01", "2024-01-01")), ("Test", ("2024-01-01", "2025-01-01"))]:
    total = []
    for sym in SYMS:
        df = load_csv(sym)
        df = calc(df)
        d = df[(df["date"] >= start) & (df["date"] < end)].copy()
        d = d[(d["hour"] >= 15) & (d["hour"] < 16)]
        d = d[(d["rsi"] >= 65) & (d["rsi"] <= 90)]
        d = d[d[" Close"] > d["sma200"]]
        
        if len(d) > 0:
            d["next2"] = d[" Close"].shift(-2)
            d["win"] = (d["next2"] < d[" Close"]).astype(int)
            total.append((len(d), d["win"].sum()))
    
    tot_trades = sum(t[0] for t in total)
    tot_wins = sum(t[1] for t in total)
    print(f"{period}: {tot_trades} trades, WR={tot_wins/tot_trades*100:.1f}%")

print("\nDone")