"""H15 + RSI filter optimization."""
import pandas as pd
from pathlib import Path

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

print("=== H15 + RSI OPTIMIZATION ===\n")

for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[df["date"] >= "2024-01-01"]
    df = df.dropna()
    
    df["signal"] = (df["hour"] == 15) & (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    trades = df[df["signal"]].copy()
    
    print(f"{sym}:")
    
    # Test RSI ranges
    for rsi_low in [65, 70, 75, 80]:
        t = trades[(trades["rsi"] >= rsi_low) & (trades["rsi"] < rsi_low+15)]
        if len(t) >= 20:
            wr = t["win"].mean() * 100
            print(f"  RSI {rsi_low}-{rsi_low+15}: {len(t)} trades, WR={wr:.1f}%")

print("\n=== BEST OVERALL ===")

# All syms, test 2024
all_trades = []
for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[df["date"] >= "2024-01-01"]
    df = df.dropna()
    
    df["signal"] = (df["hour"] == 15) & (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    all_trades.append(df[df["signal"]])

df_all = pd.concat(all_trades)
print(f"H15 base (RSI 65-90): {len(df_all)} trades, WR={df_all['win'].mean()*100:.1f}%")

# H15 + RSI 65-80
df_all = pd.concat(all_trades)
d = df_all[(df_all["rsi"] >= 65) & (df_all["rsi"] <= 80)]
print(f"H15 + RSI 65-80: {len(d)} trades, WR={d['win'].mean()*100:.1f}%")

# H15 + RSI 70-85
df_all = pd.concat(all_trades)
d = df_all[(df_all["rsi"] >= 70) & (df_all["rsi"] <= 85)]
print(f"H15 + RSI 70-85: {len(d)} trades, WR={d['win'].mean()*100:.1f}%")

print("\nDone")