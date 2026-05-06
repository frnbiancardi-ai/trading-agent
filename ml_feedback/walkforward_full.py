"""Walk-forward con tutti i simboli + session filter."""
import pandas as pd
import json
from pathlib import Path

TF = "M15"
SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / f"{TF}.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    # NY session: 13:00-18:00 UTC (orario NY aperto)
    df["is_ny"] = (df["hour"] >= 13) & (df["hour"] < 18)
    df = df[(df["date"] >= "2020-01-01") & (df["date"] < "2025-01-01")].copy()
    return df.sort_values("date").reset_index(drop=True)

def calc_indicators(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    return df.dropna()

def backtest(df, ny_session=False, rsi_min=65, rsi_max=90):
    df = df.copy()
    if ny_session:
        df = df[df["is_ny"]]
    
    df["signal"] = (df["rsi"] >= rsi_min) & (df["rsi"] <= rsi_max) & (df[" Close"] > df["sma200"])
    df["next_close"] = df[" Close"].shift(-2)
    df["win"] = df["next_close"] < df[" Close"]
    
    trades = df[df["signal"]]
    if len(trades) == 0:
        return {"trades": 0, "wr": 0}
    
    return {"trades": len(trades), "wr": round(trades["win"].sum()/len(trades)*100, 1)}

print("=== WALK-FORWARD + SESSION FILTER ===\n")

all_train = []
all_test = []

for sym in SYMS:
    print(f"Processing {sym}...")
    df = load_csv(sym)
    df = calc_indicators(df)
    
    train = df[df["date"] < "2024-01-01"]
    test = df[df["date"] >= "2024-01-01"]
    
    # Senza filtro
    r_train = backtest(train, ny_session=False)
    r_test = backtest(test, ny_session=False)
    
    # Con NY session
    r_train_ny = backtest(train, ny_session=True)
    r_test_ny = backtest(test, ny_session=True)
    
    all_train.append(r_train)
    all_train.append(r_train_ny)
    all_test.append(r_test)
    all_test.append(r_test_ny)
    
    print(f"  {sym}: Train={r_train['trades']}t WR={r_train['wr']}% | Test={r_test['trades']}t WR={r_test['wr']}%")
    print(f"  {sym}+NY: Train={r_train_ny['trades']}t WR={r_train_ny['wr']}% | Test={r_test_ny['trades']}t WR={r_test_ny['wr']}%")

# Aggregate
train_total = sum(r["trades"] for r in all_train)
train_wins = sum(r["trades"] * r["wr"]/100 for r in all_train)
train_wr = round(train_wins/train_total*100, 1) if train_total > 0 else 0

test_total = sum(r["trades"] for r in all_test)
test_wins = sum(r["trades"] * r["wr"]/100 for r in all_test)
test_wr = round(test_wins/test_total*100, 1) if test_total > 0 else 0

diff = test_wr - train_wr

print(f"\n=== TOTALE ===")
print(f"Train 2020-2023: {train_total} trades, WR={train_wr}%")
print(f"Test 2024: {test_total} trades, WR={test_wr}%")
print(f"Diff: {diff:+.1f}%")

if abs(diff) < 3:
    print("RISULTATO: STABILE")
elif diff > 0:
    print("RISULTATO: Test > Train (possible overfitting)")
else:
    print("RISULTATO: Peggiora su dati nuovi")

with open("ml_feedback/walkforward_full.json", "w") as f:
    json.dump({"train": train_wr, "test": test_wr, "diff": diff, "trades": test_total}, f, indent=2)

print("\nSaved: ml_feedback/walkforward_full.json")