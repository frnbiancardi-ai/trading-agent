"""Ultra quick test 2024."""
import sys
from datetime import datetime
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi as calc_rsi

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    for tf in ["M15", "H1"]:
        bars = load_bars(sym, tf, datetime(2024,1,1), datetime(2024,12,31))
        if len(bars) < 1000:
            continue
        
        trades = []
        for i in range(50, min(2000, len(bars)-3)):
            closes = [b["close"] for b in bars[:i+1]]
            r = calc_rsi(closes, 14)
            if r and 15 <= r[-1] <= 25:
                e = bars[i]["close"]
                x = bars[i+2]["close"]
                if x > e: trades.append(1)
        
        if trades:
            print(f"{sym} {tf} RSI 15-25 LONG h2: {len(trades)} trades, {sum(trades)/len(trades)*100:.1f}%")