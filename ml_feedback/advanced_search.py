"""Advanced filter search."""
import pandas as pd
from pathlib import Path
from collections import defaultdict

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    df = df[(df["date"] >= "2020-01-01") & (df["date"] < "2025-01-01")].sort_values("date").reset_index(drop=True)
    return df

def calc_indicators(df):
    df["sma200"] = df[" Close"].rolling(200).mean()
    df["sma50"] = df[" Close"].rolling(50).mean()
    
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    
    # RSI momentum (RSI - RSI 3 bar fa)
    df["rsi_mom"] = df["rsi"] - df["rsi"].shift(3)
    
    # Price vs SMA
    df["price_vs_sma200"] = (df[" Close"] - df["sma200"]) / df["sma200"] * 10000  # in pips
    
    # ATR
    df["atr"] = (df[" High"] - df[" low"]).rolling(14).mean()
    df["atr_pct"] = df["atr"] / df[" Close"] * 100
    
    # Trend: SMA50 > SMA200 (long term trend)
    df["trend_up"] = df["sma50"] > df["sma200"]
    
    return df.dropna()

def run_test(df, name, **filters):
    """Run test con filtri."""
    d = df[df["date"] >= "2024-01-01"].copy()
    
    # Base filter
    d = d[(d["rsi"] >= filters.get("rsi_min", 65)) & (d["rsi"] <= filters.get("rsi_max", 90))]
    d = d[d[" Close"] > d["sma200"]]
    
    # NY
    if filters.get("ny"):
        d = d[(d["hour"] >= 13) & (d["hour"] < 18)]
    
    # Hour range
    if "hour_start" in filters:
        d = d[(d["hour"] >= filters["hour_start"]) & (d["hour"] < filters.get("hour_end", filters["hour_start"]+4))]
    
    # RSI momentum
    if "rsi_mom_neg" in filters:
        d = d[d["rsi_mom"] < 0]
    
    # Trend
    if "trend_up" in filters:
        d = d[d["trend_up"] == filters["trend_up"]]
    
    # RSI range specific
    if "rsi_range" in filters:
        rmin, rmax = filters["rsi_range"]
        d = d[(d["rsi"] >= rmin) & (d["rsi"] <= rmax)]
    
    # ATR min
    if "atr_min" in filters:
        d = d[d["atr_pct"] > filters["atr_min"]]
    
    if len(d) == 0:
        return {"trades": 0, "wr": 0}
    
    d["next2"] = d[" Close"].shift(-2)
    d["win"] = d["next2"] < d[" Close"]
    
    trades = d[d["win"].notna()]
    wr = trades["win"].sum() / len(trades) * 100
    
    return {"trades": len(trades), "wr": round(wr, 1), "name": name}

print("=== ADVANCED FILTER SEARCH ===\n")

filters_to_test = [
    # Base
    ("base", {"rsi_min": 65, "rsi_max": 90}),
    # Narrow RSI
    ("rsi_70_85", {"rsi_min": 70, "rsi_max": 85}),
    ("rsi_75_90", {"rsi_min": 75, "rsi_max": 90}),
    ("rsi_80_90", {"rsi_min": 80, "rsi_max": 90}),
    ("rsi_80_95", {"rsi_min": 80, "rsi_max": 95}),
    # NY + RSI
    ("ny_base", {"ny": True}),
    ("ny_75_90", {"ny": True, "rsi_min": 75, "rsi_max": 90}),
    ("ny_80_90", {"ny": True, "rsi_min": 80, "rsi_max": 90}),
    # RSI momentum (divergence)
    ("rsi_mom_neg", {"rsi_mom_neg": True}),
    ("ny_rsi_mom", {"ny": True, "rsi_mom_neg": True}),
    # Trend
    ("trend_down", {"trend_up": False}),
    ("ny_trend_down", {"ny": True, "trend_up": False}),
    # Combo
    ("combo_ny_hi", {"ny": True, "rsi_min": 80, "rsi_max": 95, "rsi_mom_neg": True}),
    ("combo_ny_trend", {"ny": True, "rsi_min": 75, "rsi_max": 90, "trend_up": False}),
]

results = []
for sym in SYMS:
    df = load_csv(sym)
    df = calc_indicators(df)
    
    for name, filt in filters_to_test:
        r = run_test(df, name, **filt)
        r["symbol"] = sym
        results.append(r)

# Aggregate
agg = defaultdict(lambda: {"trades": 0, "wins": 0})
for r in results:
    agg[r["name"]]["trades"] += r["trades"]
    agg[r["name"]]["wins"] += r["trades"] * r["wr"] / 100

for name, d in agg.items():
    d["wr"] = round(d["wins"] / d["trades"] * 100, 1) if d["trades"] > 0 else 0

sorted_results = sorted(agg.items(), key=lambda x: x[1]["wr"], reverse=True)

print(" Risultati (Test 2024, 3 symbol):")
print("-" * 45)
for name, d in sorted_results[:15]:
    print(f"{name:20} {d['trades']:5} trades, WR={d['wr']}%")

best = sorted_results[0]
print(f"\nMiglior: {best[0]} = {best[1]['wr']}%")

with open("ml_feedback/advanced_search.json", "w") as f:
    json.dump({k: v for k, v in agg.items()}, f, indent=2)