"""Walk-forward: H15 + RSI 65-80."""
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

print("=== WALK-FORWARD: H15 + RSI 65-80 ===\n")

# Train 2020-2023
print("=== TRAIN 2020-2023 ===")
train_total = 0
train_wins = 0

for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[(df["date"] >= "2020-01-01") & (df["date"] < "2024-01-01")]
    df = df.dropna()
    
    df["signal"] = (df["hour"] == 15) & (df["rsi"] >= 65) & (df["rsi"] <= 80) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    trades = df[df["signal"]]
    train_total += len(trades)
    train_wins += trades["win"].sum()
    print(f"  {sym}: {len(trades)} trades, WR={trades['win'].mean()*100:.1f}%")

train_wr = train_wins / train_total * 100 if train_total > 0 else 0
print(f"\n  TRAIN TOT: {train_total} trades, WR={train_wr:.1f}%\n")

# Test 2024
print("=== TEST 2024 ===")
test_total = 0
test_wins = 0

for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[df["date"] >= "2024-01-01"]
    df = df.dropna()
    
    df["signal"] = (df["hour"] == 15) & (df["rsi"] >= 65) & (df["rsi"] <= 80) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    trades = df[df["signal"]]
    test_total += len(trades)
    test_wins += trades["win"].sum()
    print(f"  {sym}: {len(trades)} trades, WR={trades['win'].mean()*100:.1f}%")

test_wr = test_wins / test_total * 100 if test_total > 0 else 0
print(f"\n  TEST TOT: {test_total} trades, WR={test_wr:.1f}%\n")

# Diff
diff = test_wr - train_wr
print(f"DIFF: {diff:+.1f}%")

if abs(diff) < 5:
    print("RISULTATO: STABILE")
elif diff > 0:
    print("RISULTATO: Test > Train (possible overfitting)")
else:
    print("RISULTATO: Test < Train (peggiora)")

print("\nDone")