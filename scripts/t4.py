import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime

bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31)); print("Loaded")

for low, high in [(10,30),(15,30),(20,35),(10,35),(15,35),(20,40)]:
    w=t=0
    for i in range(50, min(2000, len(bars)-2)):
        c=[b["close"] for b in bars[:i+1]]; rs=r(c,14)
        if rs and low<=rs[-1]<=high and bars[i+1]["close"]>bars[i]["close"]: w+=1; t+=1
    if t>30: print(f"LONG RSI {low}-{high}: {t} trades, {w/t*100:.1f}%")

print()

for low, high in [(70,90),(65,85),(60,80),(65,80),(70,80),(60,90)]:
    w=t=0
    for i in range(50, min(2000, len(bars)-2)):
        c=[b["close"] for b in bars[:i+1]]; rs=r(c,14)
        if rs and low<=rs[-1]<=high and bars[i+1]["close"]<bars[i]["close"]: w+=1; t+=1
    if t>30: print(f"SHORT RSI {low}-{high}: {t} trades, {w/t*100:.1f}%")