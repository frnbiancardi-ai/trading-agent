import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime

bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31)); print("Fixed test")

#.entry su bar[i-1], RSI calcolato su bars[:i-1], exit su bar[i]
#FIX: i è la barra PRIMA dell'entry
w=t=0
for i in range(51, min(2000, len(bars)-2)):
    c=[b["close"] for b in bars[:i]]  # closes prima di i (esclude i)
    rs=r(c,14)
    if rs and 15<=rs[-1]<=35:
        if bars[i+1]["close"]>bars[i]["close"]: w+=1
        t+=1
print(f"LONG RSI 15-35 (fixed): {t} trades, {w/t*100:.1f}%")