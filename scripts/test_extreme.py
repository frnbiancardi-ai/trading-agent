"""Test RSI extreme con hold variabile."""
import sys
from datetime import datetime
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi as calc_rsi

results = []

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    for tf in ["M15", "H1"]:
        for hold in [1, 2, 3, 4, 5]:
            bars = load_bars(sym, tf, datetime(2024,1,1), datetime(2024,12,31))
            if len(bars) < 1000:
                continue
            
            wins = 0
            trades = 0
            
            for i in range(50, min(len(bars)-hold-1, 2500)):
                closes = [b["close"] for b in bars[:i+1]]
                r = calc_rsi(closes, 14)
                if r and 15 <= r[-1] <= 25:
                    entry = bars[i]["close"]
                    exit_ = bars[i+hold]["close"]
                    if exit_ > entry:
                        wins += 1
                    trades += 1
            
            if trades > 20:
                wr = wins / trades * 100
                results.append((sym, tf, hold, trades, wr))

print("=== RSI 15-25 LONG ===")
for r in sorted(results, key=lambda x: x[4], reverse=True):
    print(f"{r[0]} {r[1]} h={r[2]}: {r[3]} trades, {r[4]:.1f}%")

results2 = []
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    for tf in ["M15", "H1"]:
        for hold in [1, 2, 3, 4, 5]:
            bars = load_bars(sym, tf, datetime(2024,1,1), datetime(2024,12,31))
            if len(bars) < 1000:
                continue
            
            wins = 0
            trades = 0
            
            for i in range(50, min(len(bars)-hold-1, 2500)):
                closes = [b["close"] for b in bars[:i+1]]
                r = calc_rsi(closes, 14)
                if r and 75 <= r[-1] <= 85:
                    entry = bars[i]["close"]
                    exit_ = bars[i+hold]["close"]
                    if exit_ < entry:
                        wins += 1
                    trades += 1
            
            if trades > 20:
                wr = wins / trades * 100
                results2.append((sym, tf, hold, trades, wr))

print("\n=== RSI 75-85 SHORT ===")
for r in sorted(results2, key=lambda x: x[4], reverse=True):
    print(f"{r[0]} {r[1]} h={r[2]}: {r[3]} trades, {r[4]:.1f}%")