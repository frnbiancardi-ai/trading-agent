"""Test RSI 75-90 + SMA50 su 5 anni"""
import sys
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma
from datetime import datetime

SL = 15
TP = 22.5

print("=== RSI 75-90 + SMA50 (5 anni) ===")

total_profit = 0
total_trades = 0

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "M15", datetime(2020, 1, 1), datetime(2024, 12, 31))
    if not bars:
        continue
    
    wins = losses = profit = 0
    
    for i in range(100, min(4000, len(bars) - 3)):
        c = [b["close"] for b in bars[:i]]
        s50 = sma(c, 50)
        rs = rsi(c, 14)
        if s50 and rs and 75 <= rs[-1] <= 90 and bars[i]["close"] > s50[-1]:
            if bars[i + 2]["close"] < bars[i]["close"]:
                wins += 1
                profit += TP
            else:
                losses += 1
                profit -= SL
    
    total_trades += wins + losses
    total_profit += profit
    
    if wins + losses > 0:
        wr = wins / (wins + losses) * 100
        print(f"{sym}: {wins + losses} trades, WR={wr:.1f}%, Profit={profit:.1f} pips")

print(f"\nTOTALE: {total_trades} trades, Profit={total_profit:.1f} pips")