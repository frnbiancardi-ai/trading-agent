"""Walk-forward validation VELOCE con pandas."""
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

# Config
SYM = "EURUSD"
TF = "M15"
START = "2020-01-01"
END = "2024-12-31"

def load_csv_fast(symbol, start, end):
    """Load CSV in pandas DataFrame."""
    path = Path("data/historical") / symbol / f"{TF}.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df = df[(df["date"] >= start) & (df["date"] <= end)].copy()
    return df.sort_values("date").reset_index(drop=True)

def calc_indicators(df):
    """Calcola RSI e SMA in una volta."""
    # SMA 200
    df["sma200"] = df[" Close"].rolling(200).mean()
    
    # RSI 14
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    return df

def run_backtest(df, rsi_min=65, rsi_max=90):
    """Backtest vectorizzato."""
    df = df.dropna().copy()
    df["signal"] = (df["rsi"] >= rsi_min) & (df["rsi"] <= rsi_max) & (df[" Close"] > df["sma200"])
    
    # Shift per signals
    df["next_close"] = df[" Close"].shift(-2)
    df["win"] = df["next_close"] < df[" Close"]
    
    # Filtra solo signals
    trades = df[df["signal"]].copy()
    
    if len(trades) == 0:
        return {"trades": 0, "wr": 0}
    
    wins = trades["win"].sum()
    total = len(trades)
    
    return {"trades": total, "wins": int(wins), "wr": round(wins/total*100, 1)}

print("=== WALK-FORWARD (FAST) ===")
print(f"Loading {SYM} {START} to {END}...")

df = load_csv_fast(SYM, START, END)
print(f"Rows: {len(df)}")

print("Calculating indicators...")
df = calc_indicators(df)

# Split train/test
train = df[df["date"] < "2024-01-01"]
test = df[df["date"] >= "2024-01-01"]

print(f"Train: {len(train)} rows (2020-2023)")
print(f"Test: {len(test)} rows (2024)")

# Run backtest su train
train_result = run_backtest(train)
print(f"\nTrain 2020-2023: {train_result['trades']} trades, WR={train_result['wr']}%")

# Run backtest su test
test_result = run_backtest(test)
print(f"Test 2024: {test_result['trades']} trades, WR={test_result['wr']}%")

diff = test_result['wr'] - train_result['wr']
print(f"\nDiff: {diff:+.1f}%")

if abs(diff) < 5:
    print("✅ STABLE")
elif diff > 0:
    print("⚠️ Test > Train - possible overfitting")
else:
    print("⚠️ Test < Train - strategia peggiora")

# Save
with open("ml_feedback/walkforward_fast.json", "w") as f:
    json.dump({
        "train": train_result,
        "test": test_result,
        "diff": diff
    }, f, indent=2)

print("\nSaved: ml_feedback/walkforward_fast.json")