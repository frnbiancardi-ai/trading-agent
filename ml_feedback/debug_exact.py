"""Identical to wf_final to debug."""
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

print("=== EXACT COPY OF wf_final ===\n")

# Test 2024 - SAME AS wf_final
print("=== TEST 2024 ===")
test_total = 0
test_wins = 0

for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[df["date"] >= "2024-01-01"]  # NO upper bound filter!
    df = df.dropna()
    
    df["signal"] = (df["hour"] == 15) & (df["rsi"] >= 65) & (df["rsi"] <= 80) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    trades = df[df["signal"]]
    test_total += len(trades)
    test_wins += trades["win"].sum()
    print(f"  {sym}: {len(trades)} trades, WR={trades['win'].mean()*100:.1f}%")

test_wr = test_wins / test_total * 100
print(f"\n  TEST TOT: {test_total} trades, WR={test_wr:.1f}%")

print("\nDone")