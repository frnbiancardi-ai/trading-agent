import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "M15", datetime(2024,1,1), datetime(2024,12,31))
    w=t=0
    for i in range(51, min(2000, len(bars)-2)):
        c=[b["close"] for b in bars[:i]]
        rs=r(c,14)
        if rs and 65<=rs[-1]<=85:
            if bars[i+1]["close"]<bars[i]["close"]: w+=1
            t+=1
    if t>0: print(f"{sym} SHORT RSI 65-85: {t} trades, {w/t*100:.1f}%")

print()

# LONG con timeframe H1
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    bars = load_bars(sym, "H1", datetime(2024,1,1), datetime(2024,12,31))
    w=t=0
    for i in range(51, min(2000, len(bars)-2)):
        c=[b["close"] for b in bars[:i]]
        rs=r(c,14)
        if rs and 15<=rs[-1]<=35:
            if bars[i+1]["close"]>bars[i]["close"]: w+=1
            t+=1
    if t>0: print(f"{sym} H1 LONG RSI 15-35: {t} trades, {w/t*100:.1f}%")