import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime

# FIX: usa RSI DEL BAR PRECEDENTE, non includere bar corrente
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "M15", datetime(2024,1,1), datetime(2024,12,31))
    if len(bars) < 100: continue
    
    w=t=0
    for i in range(51, min(2000, len(bars)-2)):
        # RSI calcolato su bar[i-1] (chiuso), entry su bar[i], exit su bar[i+1]
        c=[b["close"] for b in bars[:i]]  # NOT i+1 - esclude current bar
        rs=r(c,14)
        if rs and 15<=rs[-1]<=35 and bars[i+1]["close"]>bars[i]["close"]: w+=1; t+=1
    print(f"{sym} LONG (fixed): {t} trades, {w/t*100:.1f}%")

print()

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "M15", datetime(2024,1,1), datetime(2024,12,31))
    if len(bars) < 100: continue
    
    w=t=0
    for i in range(51, min(2000, len(bars)-2)):
        c=[b["close"] for b in bars[:i]]
        rs=r(c,14)
        if rs and 65<=rs[-1]<=85 and bars[i+1]["close"]<bars[i]["close"]: w+=1; t+=1
    print(f"{sym} SHORT (fixed): {t} trades, {w/t*100:.1f}%")