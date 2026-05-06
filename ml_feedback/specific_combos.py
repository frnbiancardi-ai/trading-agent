"""Test specific RSI at specific hours."""
import pandas as pd
from pathlib import Path

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    return df[(df["date"] >= "2024-01-01") & (df["date"] < "2025-01-01")].sort_values("date").reset_index(drop=True)

def calc(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    return df.dropna()

print("=== SPECIFIC RSI + HOUR COMBOS ===\n")

# Test specific combos
combos = []

for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    
    # Test each hour + RSI combo
    for hour in [8, 9, 10, 11, 12, 13, 14, 15, 16]:
        for rsi_low in [65, 70, 75, 80]:
            d = df[(df["hour"] >= hour) & (df["hour"] < hour+1)]
            d = d[(d["rsi"] >= rsi_low) & (d["rsi"] <= 95)]
            d = d[d[" Close"] > d["sma200"]]
            
            if len(d) < 50:
                continue
            
            d["next2"] = d[" Close"].shift(-2)
            d["win"] = d["next2"] < d[" Close"]
            
            wr = d["win"].sum() / len(d) * 100
            if wr > 55 and len(d) >= 100:
                combos.append((sym, hour, rsi_low, len(d), round(wr, 1)))

# Sort by WR
combos.sort(key=lambda x: x[4], reverse=True)

print("Migliori combinazioni (WR > 55%):")
print("-" * 55)
for sym, hour, rsi, trades, wr in combos[:15]:
    print(f"{sym} H{hour}:00 rsi>{rsi}: {trades} trades, WR={wr}%")

if not combos:
    print("Nessuna combo > 55%. Cerco > 50%...")
    for sym in SYMS:
        df = load_csv(sym)
        df = calc(df)
        
        for hour in [13, 14, 15]:
            for rsi_low in [65, 70, 75]:
                d = df[(df["hour"] >= hour) & (df["hour"] < hour+1)]
                d = d[(d["rsi"] >= rsi_low) & (d["rsi"] <= 95)]
                d = d[d[" Close"] > d["sma200"]]
                
                if len(d) < 50:
                    continue
                
                d["next2"] = d[" Close"].shift(-2)
                d["win"] = d["next2"] < d[" Close"]
                
                wr = d["win"].sum() / len(d) * 100
                combos.append((sym, hour, rsi_low, len(d), round(wr, 1)))
    
    combos.sort(key=lambda x: x[4], reverse=True)
    for sym, hour, rsi, trades, wr in combos[:10]:
        print(f"{sym} H{hour}:00 rsi>{rsi}: {trades} trades, WR={wr}%")

print("\nDone")