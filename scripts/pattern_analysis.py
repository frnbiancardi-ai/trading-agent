"""Analisi pattern semplificata."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import sma, rsi


def analyze_simple(symbol, tf, start, end, max_bars=3000):
    bars = load_bars(symbol, tf, start, end)
    if len(bars) < 100:
        return {"samples": 0}
    
    patterns = {}
    
    for i in range(200, min(len(bars) - 2, max_bars)):
        w = bars[:i + 1]
        closes = [b["close"] for b in w]
        
        rsi_vals = rsi(closes, 14)
        if not rsi_vals:
            continue
        
        rsi_now = rsi_vals[-1]
        sma50 = sma(closes, 50)
        if not sma50:
            continue
        
        close = w[-1]["close"]
        above_50 = close > sma50[-1]
        
        next_bar = bars[i + 1]
        win = next_bar["close"] > close
        
        key = f"rsi{int(rsi_now)}_{'above' if above_50 else 'below'}"
        if key not in patterns:
            patterns[key] = {"win": 0, "total": 0}
        
        patterns[key]["total"] += 1
        if win:
            patterns[key]["win"] += 1
    
    return patterns


def main():
    totals = {}
    
    for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
        for tf in ["M15", "H1"]:
            print(f" {symbol} {tf}", end="")
            r = analyze_simple(symbol, tf, datetime(2024,1,1), datetime(2024,12,31), max_bars=3000)
            
            for k, v in r.items():
                if k not in totals:
                    totals[k] = {"win": 0, "total": 0}
                totals[k]["win"] += v["win"]
                totals[k]["total"] += v["total"]
    
    print("\n=== BEST PATTERNS ===")
    for k, v in sorted(totals.items(), key=lambda x: x[1]["total"], reverse=True)[:15]:
        if v["total"] > 100:
            wr = v["win"] / v["total"] * 100
            print(f"{k}: {v['total']} trades, {wr:.1f}%")


if __name__ == "__main__":
    main()