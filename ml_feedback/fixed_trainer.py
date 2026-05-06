"""Fixed trainer - correct."""
import json
import sys
from datetime import datetime
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma

print("=== TRAINING CORRETTO 2024 ===")
symbols = ["EURUSD", "GBPUSD", "USDJPY"]
results = []

for sym in symbols:
    bars = load_bars(sym, "M15", datetime(2024, 1, 1), datetime(2024, 12, 31))
    if not bars:
        continue
    
    wins = losses = profit = 0
    
    for i in range(200, len(bars) - 3):
        c = [b["close"] for b in bars[:i]]
        s = sma(c, 200)
        rs = rsi(c, 14)
        
        if s and rs and s[-1] and rs[-1] and 65 <= rs[-1] <= 90 and bars[i]["close"] > s[-1]:
            if bars[i + 2]["close"] < bars[i]["close"]:
                wins += 1
                profit += 22.5
            else:
                losses += 1
                profit -= 15
    
    trades = wins + losses
    wr = wins / trades * 100 if trades > 0 else 0
    results.append({"symbol": sym, "trades": trades, "wins": wins, "losses": losses, "wr": wr, "profit": profit})
    print(f"{sym}: {trades} trades, WR={wr:.1f}%, Profit={profit:.0f} pips")

total_trades = sum(r["trades"] for r in results)
total_wins = sum(r["wins"] for r in results)
total_profit = sum(r["profit"] for r in results)
avg_wr = total_wins / total_trades * 100 if total_trades > 0 else 0

print(f"\nTOTALE: {total_trades} trades, WR={avg_wr:.1f}%, Profit={total_profit:.0f} pips")

with open("ml_feedback/best_params.json", "w") as f:
    json.dump({
        "rsi_short_min": 65,
        "rsi_short_max": 90,
        "sma_period": 200,
        "sl_pips": 15,
        "tp_pips": 22.5,
        "total_trades": total_trades,
        "total_profit": int(total_profit),
        "avg_win_rate": round(avg_wr, 1),
        "year": "2024",
        "training_date": datetime.now().isoformat()
    }, f, indent=2)

print("Saved: ml_feedback/best_params.json")