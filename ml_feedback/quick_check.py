"""Quick check - single symbol, limited iterations."""
import sys
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma
from datetime import datetime

# Just EURUSD 2024, max 500 iterations
bars = load_bars("EURUSD", "M15", datetime(2024, 1, 1), datetime(2024, 12, 31))
print(f"Loaded {len(bars)} bars")

wins = losses = 0

for i in range(200, min(700, len(bars) - 3)):
    c = [b["close"] for b in bars[:i]]
    s = sma(c, 200)
    rs = rsi(c, 14)
    
    if s is None or rs is None:
        continue
    if s[-1] is None or rs[-1] is None:
        continue
    
    if 65 <= rs[-1] <= 90 and bars[i]["close"] > s[-1]:
        if bars[i + 2]["close"] < bars[i]["close"]:
            wins += 1
        else:
            losses += 1

total = wins + losses
wr = wins / total * 100 if total > 0 else 0

print(f"EURUSD 2024: {total} trades, WR={wr:.1f}%")
print(f"Wins: {wins}, Losses: {losses}")