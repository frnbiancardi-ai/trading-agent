"""Test strategie multiple."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import sma, rsi


def run_test(symbol, tf, rsi_low, rsi_high, direction, hold):
    bars = load_bars(symbol, tf, datetime(2024,1,1), datetime(2024,12,31))
    if not bars or len(bars) < 100:
        return 0, 0
    
    wins = 0
    total = 0
    
    for i in range(50, min(len(bars) - hold - 1, 2500)):
        closes = [b["close"] for b in bars[:i+1]]
        rsi_vals = rsi(closes, 14)
        if not rsi_vals:
            continue
        
        r = rsi_vals[-1]
        if r < rsi_low or r > rsi_high:
            continue
        
        entry = bars[i]["close"]
        exit_bar = bars[i + hold]["close"]
        
        if direction == "LONG" and exit_bar > entry:
            wins += 1
        elif direction == "SHORT" and exit_bar < entry:
            wins += 1
        
        total += 1
    
    return wins, total


def main():
    best = {"wr": 0, "params": {}}
    
    combos = [
        (10, 30, "LONG", 1),
        (10, 30, "LONG", 2),
        (10, 30, "LONG", 3),
        (10, 30, "LONG", 4),
        (20, 40, "LONG", 1),
        (20, 40, "LONG", 2),
        (20, 40, "LONG", 3),
        (60, 80, "SHORT", 1),
        (60, 80, "SHORT", 2),
        (60, 80, "SHORT", 3),
        (70, 90, "SHORT", 1),
        (70, 90, "SHORT", 2),
        (15, 25, "LONG", 2),
        (75, 85, "SHORT", 2),
    ]
    
    for rsi_l, rsi_h, d, h in combos:
        wins = 0
        trades = 0
        for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
            for tf in ["M15", "H1"]:
                w, t = run_test(sym, tf, rsi_l, rsi_h, d, h)
                wins += w
                trades += t
        
        if trades > 100:
            wr = wins / trades * 100
            print(f"rsi[{rsi_l}-{rsi_h}] {d} h={h}: {trades} trades, {wr:.1f}%")
            if wr > best["wr"]:
                best = {"wr": wr, "params": (rsi_l, rsi_h, d, h), "trades": trades}
    
    print()
    print(f"BEST: {best}")


if __name__ == "__main__":
    main()