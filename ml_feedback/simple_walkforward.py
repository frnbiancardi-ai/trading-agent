"""Simple Walk-Forward: Train 2020-2023, Test 2024."""
import sys
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma
from datetime import datetime
import json

print("=== WALK-FORWARD ===")
print("Train: 2020-2023 | Test: 2024")

# Train on 2020-2023
train_wins = train_total = 0
for year in [2020, 2021, 2022, 2023]:
    for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
        bars = load_bars(sym, "M15", datetime(year, 1, 1), datetime(year, 12, 31))
        if not bars:
            continue
        for i in range(200, min(800, len(bars) - 3)):
            c = [b["close"] for b in bars[:i]]
            s = sma(c, 200)
            r = rsi(c, 14)
            if s and r and s[-1] and r[-1]:
                if 65 <= r[-1] <= 90 and bars[i]["close"] > s[-1]:
                    train_total += 1
                    if bars[i+2]["close"] < bars[i]["close"]:
                        train_wins += 1

train_wr = train_wins / train_total * 100 if train_total > 0 else 0
print(f"Train 2020-2023: {train_total} trades, WR={train_wr:.1f}%")

# Test on 2024
test_wins = test_total = 0
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "M15", datetime(2024, 1, 1), datetime(2024, 12, 31))
    if not bars:
        continue
    for i in range(200, min(1000, len(bars) - 3)):
        c = [b["close"] for b in bars[:i]]
        s = sma(c, 200)
        r = rsi(c, 14)
        if s and r and s[-1] and r[-1]:
            if 65 <= r[-1] <= 90 and bars[i]["close"] > s[-1]:
                test_total += 1
                if bars[i+2]["close"] < bars[i]["close"]:
                    test_wins += 1

test_wr = test_wins / test_total * 100 if test_total > 0 else 0
print(f"Test 2024: {test_total} trades, WR={test_wr:.1f}%")

diff = test_wr - train_wr
print(f"Diff: {diff:+.1f}%")

if abs(diff) < 5:
    print("STABILE")
elif diff > 0:
    print("Test > Train - possible overfitting")
else:
    print("Test < Train - peggiora su nuovi dati")

with open("ml_feedback/walkforward.json", "w") as f:
    json.dump({"train": train_wr, "test": test_wr, "diff": diff}, f)

print("Saved: ml_feedback/walkforward.json")