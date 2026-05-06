import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime

# Test LONG RSI 15-35 con hold variabile
print("=== EURUSD M15 - LONG RSI 15-35 ===")
for h in [2,3,4,5,8,10]:
    bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31))
    w=t=0
    for i in range(51, min(2000, len(bars)-h-1)):
        c=[b["close"] for b in bars[:i]]
        rs=r(c,14)
        if rs and 15<=rs[-1]<=35 and bars[i+h]["close"]>bars[i]["close"]: w+=1; t+=1
    if t>0: print(f"h={h}: {t} trades, {w/t*100:.1f}%")

# Test SHORT RSI 65-85 con hold variabile
print("\n=== GBPUSD M15 - SHORT RSI 65-85 ===")
for h in [2,3,4,5,8,10]:
    bars = load_bars("GBPUSD", "M15", datetime(2024,1,1), datetime(2024,12,31))
    w=t=0
    for i in range(51, min(2000, len(bars)-h-1)):
        c=[b["close"] for b in bars[:i]]
        rs=r(c,14)
        if rs and 65<=rs[-1]<=85 and bars[i+h]["close"]<bars[i]["close"]: w+=1; t+=1
    if t>0: print(f"h={h}: {t} trades, {w/t*100:.1f}%")