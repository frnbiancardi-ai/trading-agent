import sys
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi as r
from datetime import datetime

bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31))
w = t = 0
for i in range(50, 1500):
    c = [b["close"] for b in bars[:i+1]]
    rs = r(c, 14)
    if rs and 15 <= rs[-1] <= 25:
        if bars[i+2]["close"] > bars[i]["close"]:
            w += 1
        t += 1

print(f"RSI 15-25 h2: {t} trades, {w/t*100:.1f}%")

w = t = 0
for i in range(50, 1500):
    c = [b["close"] for b in bars[:i+1]]
    rs = r(c, 14)
    if rs and 75 <= rs[-1] <= 85:
        if bars[i+2]["close"] < bars[i]["close"]:
            w += 1
        t += 1

print(f"RSI 75-85 h2: {t} trades, {w/t*100:.1f}%")