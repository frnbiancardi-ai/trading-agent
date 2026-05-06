"""Test 5 years: 2020-2024"""
import sys
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma
from datetime import datetime

SL_PIPS = 15
TP_PIPS = 22.5

print("=== TEST 5 ANNI (2020-2024) ===")

results = []

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    for tf in ["M15"]:
        bars = load_bars(sym, tf, datetime(2020, 1, 1), datetime(2024, 12, 31))
        if not bars or len(bars) < 500:
            continue
        
        wins = 0
        losses = 0
        profit_pips = 0.0
        
        for i in range(200, min(5000, len(bars) - 3)):
            closes = [b["close"] for b in bars[:i]]
            s200_val = sma(closes, 200)
            rs_val = rsi(closes, 14)
            
            if s200_val and rs_val and 65 <= rs_val[-1] <= 90 and bars[i]["close"] > s200_val[-1]:
                entry = bars[i]["close"]
                exit = bars[i + 2]["close"]
                
                if exit < entry:
                    profit_pips = profit_pips + TP_PIPS
                    wins = wins + 1
                else:
                    profit_pips = profit_pips - SL_PIPS
                    losses = losses + 1
        
        total = wins + losses
        if total > 0:
            wr = wins / total * 100
            results.append((sym, tf, total, wr, profit_pips))
            print(f"{sym} {tf}: {total} trades, WR={wr:.1f}%, Profit={profit_pips:.1f} pips")

total_trades = sum(r[2] for r in results)
total_profit = sum(r[4] for r in results)
total_wr = sum(r[2]*r[3] for r in results) / total_trades if total_trades else 0

print(f"\n=== TOTALE 5 ANNI ===")
print(f"Trades: {total_trades}")
print(f"Win Rate: {total_wr:.1f}%")
print(f"Profit: {total_profit:.1f} pips")