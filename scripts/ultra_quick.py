"""Ultra quick test."""
import sys
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi as calc_rsi

sym = "EURUSD"
tf = "M15"
bars = load_bars(sym, tf)
print(f"Loaded {len(bars)} bars")

trades = []
for i in range(100, min(800, len(bars)-3)):
    closes = [b["close"] for b in bars[:i+1]]
    r = calc_rsi(closes, 14)
    if r and 15 < r[-1] < 25:
        e = bars[i]["close"]
        x = bars[i+2]["close"]
        trades.append({"win": x > e, "rsi": r[-1]})

wins = sum(1 for t in trades if t["win"])
print(f"RSI 15-25 LONG h2: {len(trades)} trades, {wins/len(trades)*100:.1f}%")

trades2 = []
for i in range(100, min(800, len(bars)-3)):
    closes = [b["close"] for b in bars[:i+1]]
    r = calc_rsi(closes, 14)
    if r and 75 < r[-1] < 85:
        e = bars[i]["close"]
        x = bars[i+2]["close"]
        trades2.append({"win": x < e, "rsi": r[-1]})

wins2 = sum(1 for t in trades2 if t["win"])
print(f"RSI 75-85 SHORT h2: {len(trades2)} trades, {wins2/len(trades2)*100:.1f}%")