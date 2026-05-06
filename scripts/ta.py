import sys; sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi as r
from datetime import datetime

bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31))
for h in [3,5,10]:
    w=t=0
    for i in range(51, min(1500, len(bars)-h-1)):
        c=[b["close"] for b in bars[:i]]; rs=r(c,14)
        if rs and 15<=rs[-1]<=35 and bars[i+h]["close"]>bars[i]["close"]: w+=1; t+=1
    print(f"h={h}: {t} trades, {w/t*100:.1f}%")