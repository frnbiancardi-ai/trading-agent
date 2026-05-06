"""Walk-forward con volatility filter."""
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
    df["is_ny"] = (df["hour"] >= 13) & (df["hour"] < 18)
    df = df[(df["date"] >= "2020-01-01") & (df["date"] < "2025-01-01")].copy()
    return df.sort_values("date").reset_index(drop=True)

def calc_indicators(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    
    # Simple ATR: high - low
    df["atr14"] = (df[" High"] - df[" low"]).rolling(14).mean()
    df["atr_pct"] = df["atr14"] / df[" Close"] * 100
    df["atr_pct"] = df["atr14"] / df[" Close"] * 100  # ATR come % del prezzo
    
    return df.dropna()

def backtest(df, ny_session=False, min_vol=0.0005, rsi_min=65, rsi_max=90):
    df = df.copy()
    if ny_session:
        df = df[df["is_ny"]]
    
    # Filtro volatilità: skip se ATR troppo basso (ranging)
    df = df[df["atr_pct"] > min_vol]
    
    df["signal"] = (df["rsi"] >= rsi_min) & (df["rsi"] <= rsi_max) & (df[" Close"] > df["sma200"])
    df["next_close"] = df[" Close"].shift(-2)
    df["win"] = df["next_close"] < df[" Close"]
    
    trades = df[df["signal"]]
    if len(trades) == 0:
        return {"trades": 0, "wr": 0, "avg_vol": 0}
    
    return {
        "trades": len(trades), 
        "wr": round(trades["win"].sum()/len(trades)*100, 1),
        "avg_vol": round(trades["atr_pct"].mean()*10000, 0)  # in pip
    }

print("=== WALK-FORWARD + VOLATILITY FILTER ===\n")

# Test diverse soglie di volatilità
vol_thresholds = [0.0003, 0.0005, 0.0007, 0.001]

for vol_th in vol_thresholds:
    train_total = train_wins = 0
    test_total = test_wins = 0
    
    for sym in SYMS:
        df = load_csv(sym)
        df = calc_indicators(df)
        
        train = df[df["date"] < "2024-01-01"]
        test = df[df["date"] >= "2024-01-01"]
        
        r = backtest(test, ny_session=False, min_vol=vol_th)
        test_total += r["trades"]
        test_wins += r["trades"] * r["wr"] / 100
    
    test_wr = round(test_wins/test_total*100, 1) if test_total > 0 else 0
    print(f"min_vol={vol_th}: {test_total} trades, WR={test_wr}%")

# NY session + volatility
print("\n=== NY + VOL FILTER ===")
for vol_th in [0.0005, 0.0007]:
    test_total = test_wins = 0
    for sym in SYMS:
        df = load_csv(sym)
        df = calc_indicators(df)
        test = df[df["date"] >= "2024-01-01"]
        r = backtest(test, ny_session=True, min_vol=vol_th)
        test_total += r["trades"]
        test_wins += r["trades"] * r["wr"] / 100
    
    test_wr = round(test_wins/test_total*100, 1) if test_total > 0 else 0
    print(f"NY+vol={vol_th}: {test_total} trades, WR={test_wr}%")

print("\nDone")