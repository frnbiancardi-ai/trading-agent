import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r, sma; from datetime import datetime
bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31))
w=t=0
for i in range(200, min(1500, len(bars)-3)):
    c=[b["close"] for b in bars[:i]]; s200=sma(c,200); rs=r(c,14)
    if s200 and rs and 65<=rs[-1]<=90 and bars[i]["close"]>s200[-1]:
        if bars[i+2]["close"]<bars[i]["close"]: w+=1; t+=1
print(f"EURUSD M15: {t} trades, {w/t*100:.1f}%")