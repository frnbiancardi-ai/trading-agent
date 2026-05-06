import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r; from datetime import datetime

bars = load_bars("EURUSD", "M15", datetime(2024,1,1), datetime(2024,12,31))

# Check: stampa RSI quando è nell range
count = 0
for i in range(100, 110):
    c = [b["close"] for b in bars[:i]]
    rs = r(c, 14)
    if rs:
        print(f"i={i}, RSI[-3,-2,-1]={rs[-3]:.1f},{rs[-2]:.1f},{rs[-1]:.1f}, close[i]={bars[i]['close']:.5}, close[i+1]={bars[i+1]['close']:.5}")

print()

# Verifica calcolo
for i in [105, 106, 107]:
    c = [b["close"] for b in bars[:i]]
    rs = r(c, 14)
    if rs:
        rsi_val = rs[-1]
        next_close = bars[i+1]["close"]
        curr_close = bars[i]["close"]
        print(f"RSI={rsi_val:.1f}, next>{curr}? {next_close>curr_close}")