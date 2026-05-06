import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime
bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31)); print("Loaded")
for h in [1,2,3]:
    w=t=0
    for i in range(50, min(1500, len(bars)-h-1)):
        c=[b["close"] for b in bars[:i+1]]; rs=r(c,14)
        if rs and 15<=rs[-1]<=25 and bars[i+h]["close"]>bars[i]["close"]: w+=1; t+=1
    if t>0: print(f"LONG h={h}: {t} trades, {w/t*100:.1f}%")
    w=t=0
    for i in range(50, min(1500, len(bars)-h-1)):
        c=[b["close"] for b in bars[:i+1]]; rs=r(c,14)
        if rs and 75<=rs[-1]<=85 and bars[i+h]["close"]<bars[i]["close"]: w+=1; t+=1
    if t>0: print(f"SHORT h={h}: {t} trades, {w/t*100:.1f}%")