"""Same as verify_simple but with extra filters."""
import pandas as pd
from pathlib import Path

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    return df[(df["date"] >= "2024-01-01") & (df["date"] < "2025-01-01")].sort_values("date").reset_index(drop=True)

def calc_indicators(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    return df.dropna()

print("=== COMPARE FILTERS ===\n")

for sym in SYMS:
    df = load_csv(sym)
    df = calc_indicators(df)
    
    # A. Base (same as verify_simple)
    df["signal"] = (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = df["next2"] < df[" Close"]
    a = df[df["signal"]]
    a_wr = a["win"].sum() / len(a) * 100 if len(a) > 0 else 0
    
    # B. Base + NY
    df["signal_ny"] = df["signal"] & (df["hour"] >= 13) & (df["hour"] < 18)
    b = df[df["signal_ny"]]
    b_wr = b["win"].sum() / len(b) * 100 if len(b) > 0 else 0
    
    # C. Base + RSI 75-90
    df["signal_75"] = (df["rsi"] >= 75) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    c = df[df["signal_75"]]
    c_wr = c["win"].sum() / len(c) * 100 if len(c) > 0 else 0
    
    # D. Base + NY + RSI 75-90
    df["signal_combo"] = df["signal_75"] & (df["hour"] >= 13) & (df["hour"] < 18)
    d = df[df["signal_combo"]]
    d_wr = d["win"].sum() / len(d) * 100 if len(d) > 0 else 0
    
    print(f"{sym}:")
    print(f"  Base:     {len(a):5} trades, WR={a_wr:.1f}%")
    print(f"  NY:       {len(b):5} trades, WR={b_wr:.1f}%")
    print(f"  RSI75:    {len(c):5} trades, WR={c_wr:.1f}%")
    print(f"  NY+RSI75: {len(d):5} trades, WR={d_wr:.1f}%")

print("\nDone")