import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r, sma; from datetime import datetime

bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31))

results = []
for min_rsi, max_rsi in [(15,30),(20,35),(15,35),(10,30)]:
    w=t=0
    for i in range(200, min(2000, len(bars)-3)):
        c=[b["close"] for b in bars[:i]]
        s200=sma(c,200)
        rs=r(c,14)
        if not s200 or not rs: continue
        if min_rsi<=rs[-1]<=max_rsi and bars[i]["close"]<s200[-1]:
            if bars[i+2]["close"]>bars[i]["close"]: w+=1
            t+=1
    if t>30: results.append((f"LONG RSI {min_rsi}-{max_rsi} < SMA200", t, w/t*100))

for min_rsi, max_rsi in [(65,80),(70,85),(65,90),(70,90)]:
    w=t=0
    for i in range(200, min(2000, len(bars)-3)):
        c=[b["close"] for b in bars[:i]]
        s200=sma(c,200)
        rs=r(c,14)
        if not s200 or not rs: continue
        if min_rsi<=rs[-1]<=max_rsi and bars[i]["close"]>s200[-1]:
            if bars[i+2]["close"]<bars[i]["close"]: w+=1
            t+=1
    if t>30: results.append((f"SHORT RSI {min_rsi}-{max_rsi} > SMA200", t, w/t*100))

results.sort(key=lambda x: x[2], reverse=True)
for name, count, wr in results:
    print(f"{name}: {count} trades, {wr:.1f}%")