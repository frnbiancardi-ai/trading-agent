import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime

bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31)); print("EURUSD M15")

for h in [1,2,3,4,5,8,10]:
    w=t=0
    for i in range(50, min(2000, len(bars)-h-1)):
        c=[b["close"] for b in bars[:i+1]]; rs=r(c,14)
        if rs and 15<=rs[-1]<=35 and bars[i+h]["close"]>bars[i]["close"]: w+=1; t+=1
    if t>10: print(f"LONG RSI 15-35 h={h}: {t} trades, {w/t*100:.1f}%")

print()

for h in [1,2,3,4,5,8,10]:
    w=t=0
    for i in range(50, min(2000, len(bars)-h-1)):
        c=[b["close"] for b in bars[:i+1]]; rs=r(c,14)
        if rs and 65<=rs[-1]<=85 and bars[i+h]["close"]<bars[i]["close"]: w+=1; t+=1
    if t>10: print(f"SHORT RSI 65-85 h={h}: {t} trades, {w/t*100:.1f}%")