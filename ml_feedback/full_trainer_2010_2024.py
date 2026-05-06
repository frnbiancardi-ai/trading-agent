"""Full trainer 2010-2024."""
import json
import sys
from datetime import datetime
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma

print("=== FULL TRAINING 2010-2024 ===")
years = range(2010, 2025)
symbols = ["EURUSD", "GBPUSD", "USDJPY"]

yearly_results = {}
grand_total = {"trades": 0, "wins": 0, "profit": 0}

for year in years:
    year_wins = 0
    year_losses = 0
    year_profit = 0
    
    for sym in symbols:
        bars = load_bars(sym, "M15", datetime(year, 1, 1), datetime(year, 12, 31))
        if not bars or len(bars) < 100:
            continue
        
        wins = losses = profit = 0
        
        for i in range(200, min(2000, len(bars) - 3)):
            c = [b["close"] for b in bars[:i]]
            s = sma(c, 200)
            rs = rsi(c, 14)
            
            if s and rs and s[-1] and rs[-1]:
                # SHORT: RSI 65-90 + above SMA200
                if 65 <= rs[-1] <= 90 and bars[i]["close"] > s[-1]:
                    if bars[i + 2]["close"] < bars[i]["close"]:
                        wins += 1
                        profit += 22.5
                    else:
                        losses += 1
                        profit -= 15
                
                # LONG: RSI 10-30 + below SMA200
                elif 10 <= rs[-1] <= 30 and bars[i]["close"] < s[-1]:
                    if bars[i + 2]["close"] > bars[i]["close"]:
                        wins += 1
                        profit += 22.5
                    else:
                        losses += 1
                        profit -= 15
        
        year_wins += wins
        year_losses += losses
        year_profit += profit
    
    year_trades = year_wins + year_losses
    year_wr = year_wins / year_trades * 100 if year_trades > 0 else 0
    
    yearly_results[year] = {
        "trades": year_trades,
        "wins": year_wins,
        "losses": year_losses,
        "win_rate": round(year_wr, 1),
        "profit": year_profit
    }
    
    grand_total["trades"] += year_trades
    grand_total["wins"] += year_wins
    grand_total["profit"] += year_profit
    
    print(f"Year {year}: {year_trades} trades, WR={year_wr:.1f}%, Profit={year_profit:.0f} pips")

# Grand total
grand_wr = grand_total["wins"] / grand_total["trades"] * 100 if grand_total["trades"] > 0 else 0

print(f"\n=== TOTALE 2010-2024 ===")
print(f"Total Trades: {grand_total['trades']}")
print(f"Win Rate: {grand_wr:.1f}%")
print(f"Profit: {grand_total['profit']:.0f} pips")

# Save
with open("ml_feedback/training_results.json", "w") as f:
    json.dump({
        "yearly": yearly_results,
        "summary": {
            "start_year": 2010,
            "end_year": 2024,
            "total_trades": grand_total["trades"],
            "total_wins": grand_total["wins"],
            "avg_win_rate": round(grand_wr, 1),
            "total_profit": grand_total["profit"]
        }
    }, f, indent=2)

print(f"\nSaved: ml_feedback/training_results.json")