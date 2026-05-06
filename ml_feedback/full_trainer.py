"""Full Trainer: training completo su 24 anni di dati storici."""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import rsi, sma, atr


RESULTS_FILE = Path(__file__).parent / "training_history.json"
CONFIG_FILE = Path(__file__).parent / "best_params.json"


def run_strategy(bars, config):
    """Run strategy su bars e return stats."""
    rsi_l = config["rsi_short_min"]
    rsi_h = config["rsi_short_max"]
    sma_p = config["sma_period"]
    sl = config["sl_pips"]
    tp = config["tp_pips"]
    
    wins = losses = profit = 0
    trades = []
    
    for i in range(100, len(bars) - 3):
        c = [b["close"] for b in bars[:i]]
        s = sma(c, sma_p)
        rs = rsi(c, 14)
        
        if not s or not rs or s[-1] is None or rs[-1] is None:
            continue
        
        if rsi_l <= rs[-1] <= rsi_h and bars[i]["close"] > s[-1]:
            entry = bars[i]["close"]
            exit_price = bars[i + 2]["close"]
            
            if exit_price < entry:
                wins += 1
                profit += tp
                outcome = "WIN"
            else:
                losses += 1
                profit -= sl
                outcome = "LOSS"
            
            trades.append({
                "time": bars[i]["time"],
                "entry": entry,
                "exit": exit_price,
                "outcome": outcome,
                "profit": tp if outcome == "WIN" else -sl
            })
    
    total = wins + losses
    wr = wins / total * 100 if total > 0 else 0
    
    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": wr,
        "profit": profit,
        "trade_details": trades[-100:]  # Last 100 trades
    }


def train_full():
    """Training completo su tutti i dati disponibili."""
    print("=== FULL TRAINING ===")
    
    symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    timeframes = ["M15", "H1"]
    
    all_results = []
    yearly_results = {}
    
    for year in range(2002, 2025):
        year_results = []
        
        for sym in symbols:
            for tf in timeframes:
                start = datetime(year, 1, 1)
                end = datetime(year, 12, 31)
                bars = load_bars(sym, tf, start, end)
                
                if not bars or len(bars) < 100:
                    continue
                
                # Config standard
                config = {
                    "rsi_short_min": 65,
                    "rsi_short_max": 90,
                    "sma_period": 200,
                    "sl_pips": 15,
                    "tp_pips": 22.5
                }
                
                stats = run_strategy(bars, config)
                
                result = {
                    "year": year,
                    "symbol": sym,
                    "timeframe": tf,
                    "trades": stats["trades"],
                    "win_rate": stats["win_rate"],
                    "profit": stats["profit"]
                }
                
                year_results.append(result)
                all_results.append(result)
        
        if year_results:
            total_trades = sum(r["trades"] for r in year_results)
            total_profit = sum(r["profit"] for r in year_results)
            avg_wr = sum(r["trades"] * r["win_rate"] for r in year_results) / total_trades if total_trades else 0
            
            yearly_results[year] = {
                "trades": total_trades,
                "win_rate": avg_wr,
                "profit": total_profit
            }
            
            print(f"Year {year}: {total_trades} trades, WR={avg_wr:.1f}%, Profit={total_profit:.0f} pips")
    
    # Save results
    with open(RESULTS_FILE, "w") as f:
        json.dump({
            "all_trades": all_results,
            "yearly": yearly_results,
            "updated": datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\nSaved: {RESULTS_FILE}")
    
    # Calculate best params
    total_profit = sum(y["profit"] for y in yearly_results.values())
    total_trades = sum(y["trades"] for y in yearly_results.values())
    avg_wr = sum(y["trades"] * y["win_rate"] for y in yearly_results.values()) / total_trades if total_trades else 0
    
    best_params = {
        "rsi_short_min": 65,
        "rsi_short_max": 90,
        "sma_period": 200,
        "sl_pips": 15,
        "tp_pips": 22.5,
        "total_trades": total_trades,
        "total_profit": total_profit,
        "avg_win_rate": avg_wr,
        "periods_tested": len(yearly_results),
        "training_years": f"2002-2024"
    }
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(best_params, f, indent=2)
    
    print(f"Saved: {CONFIG_FILE}")
    print(f"\n=== TOTALE ===")
    print(f"Total Trades: {total_trades}")
    print(f"Avg Win Rate: {avg_wr:.1f}%")
    print(f"Total Profit: {total_profit:.0f} pips")
    
    return best_params


if __name__ == "__main__":
    train_full()