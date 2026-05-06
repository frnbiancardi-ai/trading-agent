"""Quick Trainer: training veloce su dati disponibili."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from backtest import load_bars
from indicators import rsi, sma


RESULTS_FILE = "ml_feedback/training_history.json"
BEST_FILE = "ml_feedback/best_params.json"


def run_quick():
    print("=== QUICK TRAINING ===")
    
    years = [2020, 2021, 2022, 2023, 2024]  # Solo anni recenti
    symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    
    yearly = {}
    total_profit = 0
    total_trades = 0
    total_wins = 0
    
    for year in years:
        year_profit = 0
        year_trades = 0
        year_wins = 0
        
        for sym in symbols:
            for tf in ["M15"]:
                bars = load_bars(sym, tf, datetime(year, 1, 1), datetime(year, 12, 31))
                if not bars or len(bars) < 100:
                    continue
                
                wins = losses = profit = 0
                
                for i in range(100, min(1500, len(bars) - 3)):
                    c = [b["close"] for b in bars[:i]]
                    s = sma(c, 200)
                    rs = rsi(c, 14)
                    
                    if s is None or rs is None or s[-1] is None or rs[-1] is None:
                        continue
                    
                    if 65 <= rs[-1] <= 90 and bars[i]["close"] > s[-1]:
                        if bars[i + 2]["close"] < bars[i]["close"]:
                            wins += 1
                            profit += 22.5
                        else:
                            losses += 1
                            profit -= 15
                
                year_trades += wins + losses
                year_wins += wins
                year_profit += profit
        
        wr = year_wins / year_trades * 100 if year_trades > 0 else 0
        yearly[year] = {"trades": year_trades, "win_rate": wr, "profit": year_profit}
        
        total_trades += year_trades
        total_wins += year_wins
        total_profit += year_profit
        
        print(f"Year {year}: {year_trades} trades, WR={wr:.1f}%, P/L={year_profit:.0f} pips")
    
    avg_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
    
    print(f"\nTOTALE: {total_trades} trades, WR={avg_wr:.1f}%, P/L={total_profit:.0f} pips")
    
    # Save
    best = {
        "rsi_short_min": 65,
        "rsi_short_max": 90,
        "sma_period": 200,
        "sl_pips": 15,
        "tp_pips": 22.5,
        "total_trades": total_trades,
        "total_profit": total_profit,
        "avg_win_rate": avg_wr,
        "training_years": str(years)
    }
    
    with open(BEST_FILE, "w") as f:
        json.dump(best, f, indent=2)
    
    print(f"\nSaved: {BEST_FILE}")


if __name__ == "__main__":
    run_quick()