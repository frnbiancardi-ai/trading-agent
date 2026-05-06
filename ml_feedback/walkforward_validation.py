"""Walk-Forward Validation: Train 2020-2023, Test 2024."""
import sys
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma
from datetime import datetime
import json

print("=== WALK-FORWARD VALIDATION ===")
print("Train: 2020-2023 | Test: 2024")
print()

config = {
    "rsi_min": 65,
    "rsi_max": 90,
    "sma_period": 200,
    "hold": 2
}

# === TRAIN PHASE: 2020-2023 ===
print("=== FASE 1: TRAINING (2020-2023) ===")
train_results = []

for year in [2020, 2021, 2022, 2023]:
    year_wins = 0
    year_trades = 0
    
    for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
        bars = load_bars(sym, "M15", datetime(year, 1, 1), datetime(year, 12, 31))
        if not bars:
            continue
        
        for i in range(250, min(1500, len(bars) - config["hold"] - 1)):
            closes = [b["close"] for b in bars[:i]]
            if len(closes) < config["sma_period"] + 14:
                continue
            
            sma_val = sma(closes, config["sma_period"])
            rsi_val = rsi(closes, 14)
            
            if sma_val is None or rsi_val is None:
                continue
            if sma_val[-1] is None or rsi_val[-1] is None:
                continue
            
            if (config["rsi_min"] <= rsi_val[-1] <= config["rsi_max"] and 
                bars[i]["close"] > sma_val[-1]):
                
                if bars[i + config["hold"]]["close"] < bars[i]["close"]:
                    year_wins += 1
                year_trades += 1
    
    if year_trades > 0:
        wr = year_wins / year_trades * 100
        train_results.append({"year": year, "trades": year_trades, "win_rate": wr})
        print(f"  {year}: {year_trades} trades, WR={wr:.1f}%")

train_total = sum(r["trades"] for r in train_results)
train_wins = sum(r["trades"] * r["win_rate"] / 100 for r in train_results)
train_wr = train_wins / train_total * 100 if train_total > 0 else 0

print(f"\nTraining Total: {train_total} trades, WR={train_wr:.1f}%")

# === TEST PHASE: 2024 ===
print("\n=== FASE 2: TEST (2024) - OUT OF SAMPLE ===")

test_wins = 0
test_trades = 0

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "M15", datetime(2024, 1, 1), datetime(2024, 12, 31))
    if not bars:
        continue
    
    sym_wins = 0
    sym_trades = 0
    
    for i in range(250, min(2000, len(bars) - config["hold"] - 1)):
        closes = [b["close"] for b in bars[:i]]
        if len(closes) < config["sma_period"] + 14:
            continue
        
        sma_val = sma(closes, config["sma_period"])
        rsi_val = rsi(closes, 14)
        
        if sma_val is None or rsi_val is None:
            continue
        if sma_val[-1] is None or rsi_val[-1] is None:
            continue
        
        if (config["rsi_min"] <= rsi_val[-1] <= config["rsi_max"] and 
            bars[i]["close"] > sma_val[-1]):
            
            if bars[i + config["hold"]]["close"] < bars[i]["close"]:
                sym_wins += 1
            sym_trades += 1
    
    test_trades += sym_trades
    test_wins += sym_wins
    if sym_trades > 0:
        print(f"  {sym}: {sym_trades} trades, WR={sym_wins/sym_trades*100:.1f}%")

test_wr = test_wins / test_trades * 100 if test_trades > 0 else 0

print(f"\nTest Total: {test_trades} trades, WR={test_wr:.1f}%")

# === COMPARISON ===
print("\n=== COMPARAZIONE ===")
print(f"Training WR: {train_wr:.1f}%")
print(f"Test WR:     {test_wr:.1f}%")
diff = test_wr - train_wr
print(f"Differenza:  {diff:+.1f}%")

if abs(diff) < 5:
    print("✅ RISULTATO STABILE - La strategia generalizza bene")
elif diff > 0:
    print("⚠️ Test > Train: possible overfitting")
else:
    print("⚠️ Test < Train: strategia peggiora su dati nuovi")

# Save results
output = {
    "methodology": "Walk-Forward Validation",
    "train_period": "2020-2023",
    "test_period": "2024",
    "config": config,
    "train_results": train_results,
    "train_total_trades": train_total,
    "train_win_rate": round(train_wr, 1),
    "test_total_trades": test_trades,
    "test_win_rate": round(test_wr, 1),
    "difference": round(diff, 1),
    "stability": "STABLE" if abs(diff) < 5 else "UNSTABLE"
}

with open("ml_feedback/walkforward_results.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\nSaved: ml_feedback/walkforward_results.json")