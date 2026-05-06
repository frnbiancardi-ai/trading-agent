import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime

# Test con exit DOPO 2 bar (più realistico)
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "M15", datetime(2024,1,1), datetime(2024,12,31))
    if len(bars) < 100: continue
    
    w=t=0
    for i in range(51, min(2000, len(bars)-3)):
        c=[b["close"] for b in bars[:i]]  # RSI from closed bars
        rs=r(c,14)
        # RSI extreme: LONG when oversold
        if rs and 15<=rs[-1]<=35:
            entry = bars[i]["close"]
            exit_at_2 = bars[i+2]["close"]
            if exit_at_2 > entry: w+=1
            t+=1
    if t>0: print(f"{sym} LONG (exit2): {t} trades, {w/t*100:.1f}%")

print()

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "M15", datetime(2024,1,1), datetime(2024,12,31))
    if len(bars) < 100: continue
    
    w=t=0
    for i in range(51, min(2000, len(bars)-3)):
        c=[b["close"] for b in bars[:i]]
        rs=r(c,14)
        # RSI extreme: SHORT when overbought
        if rs and 65<=rs[-1]<=85:
            entry = bars[i]["close"]
            exit_at_2 = bars[i+2]["close"]
            if exit_at_2 < entry: w+=1
            t+=1
    if t>0: print(f"{sym} SHORT (exit2): {t} trades, {w/t*100:.1f}%")