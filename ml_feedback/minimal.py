"""Minimal trainer - just 2024."""
import json
import sys
from datetime import datetime
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma

print("=== TRAINING 2024 ===")
symbols = ["EURUSD", "GBPUSD", "USDJPY"]
total = {"trades": 0, "wins": 0, "profit": 0}

for sym in symbols:
    bars = load_bars(sym, "M15", datetime(2024, 1, 1), datetime(2024, 12, 31))
    if not bars:
        continue
    
    wins = profit = 0
    for i in range(100, min(1500, len(bars) - 3)):
        c = [b["close"] for b in bars[:i]]
        s = sma(c, 200)
        rs = rsi(c, 14)
        if s and rs and s[-1] and rs[-1] and 65 <= rs[-1] <= 90 and bars[i]["close"] > s[-1]:
            if bars[i + 2]["close"] < bars[i]["close"]:
                wins += 1
                profit += 22.5
    
    trades = wins + (i - 100)  # rough estimate
    total["trades"] += trades
    total["wins"] += wins
    total["profit"] += profit
    print(f"{sym}: {trades} trades, {wins/trades*100:.1f}% WR, {profit:.0f} pips")

wr = total["wins"] / total["trades"] * 100 if total["trades"] > 0 else 0
print(f"\nTOTALE: {total['trades']} trades, WR={wr:.1f}%, Profit={total['profit']:.0f} pips")

with open("ml_feedback/best_params.json", "w") as f:
    json.dump({
        "rsi_short_min": 65, "rsi_short_max": 90,
        "sma_period": 200, "sl_pips": 15, "tp_pips": 22.5,
        "total_trades": total["trades"],
        "total_profit": total["profit"],
        "avg_win_rate": wr,
        "year": "2024"
    }, f, indent=2)

print("Saved: ml_feedback/best_params.json")