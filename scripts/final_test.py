import sys; sys.path.insert(0, "."); from backtest import load_bars; from indicators import rsi as r, sma; from datetime import datetime

print("=== STRATEGIA VINCENTE: SHORT RSI 65-90 > SMA200 ===")
total = [0, 0]
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    for tf in ["M15", "H1"]:
        bars = load_bars(sym, tf, datetime(2024,1,1), datetime(2024,12,31))
        w=t=0
        for i in range(200, min(2500, len(bars)-3)):
            c=[b["close"] for b in bars[:i]]
            s200=sma(c,200)
            rs=r(c,14)
            if not s200 or not rs: continue
            if 65<=rs[-1]<=90 and bars[i]["close"]>s200[-1]:
                if bars[i+2]["close"]<bars[i]["close"]: w+=1
                t+=1
        total[0] += w; total[1] += t
        if t>0: print(f"{sym} {tf}: {t} trades, {w/t*100:.1f}%")

print(f"\nTOTALE: {total[1]} trades, {total[0]/total[1]*100:.1f}%")

print("\n=== LONG RSI 10-30 < SMA50 ===")
total = [0, 0]
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    for tf in ["M15", "H1"]:
        bars = load_bars(sym, tf, datetime(2024,1,1), datetime(2024,12,31))
        w=t=0
        for i in range(100, min(2500, len(bars)-3)):
            c=[b["close"] for b in bars[:i]]
            s50=sma(c,50)
            rs=r(c,14)
            if not s50 or not rs: continue
            if 10<=rs[-1]<=30 and bars[i]["close"]<s50[-1]:
                if bars[i+2]["close"]>bars[i]["close"]: w+=1
                t+=1
        total[0] += w; total[1] += t
        if t>0: print(f"{sym} {tf}: {t} trades, {w/t*100:.1f}%")

print(f"\nTOTALE: {total[1]} trades, {total[0]/total[1]*100:.1f}%")