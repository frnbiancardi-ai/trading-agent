"""Test veloce."""
import sys
from datetime import datetime
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi


def test(rl, rh, d, h, sym, tf):
    bars = load_bars(sym, tf, datetime(2024, 1, 1), datetime(2024, 12, 31))
    if not bars:
        return 0, 0
    w, t = 0, 0
    for i in range(50, min(len(bars) - h - 1, 1500)):
        closes = [b["close"] for b in bars[:i + 1]]
        r = rsi(closes, 14)
        if r and rh > r[-1] > rl:
            entry = bars[i]["close"]
            exit_ = bars[i + h]["close"]
            if (d == "LONG" and exit_ > entry) or (d == "SHORT" and exit_ < entry):
                w += 1
            t += 1
    return w, t


results = []
combos = [(10, 30, "LONG", 2), (20, 40, "LONG", 2), (60, 80, "SHORT", 2), (70, 90, "SHORT", 2), (15, 25, "LONG", 3), (75, 85, "SHORT", 3)]

for rl, rh, d, h in combos:
    for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
        w = 0
        t = 0
        for tf in ["M15", "H1"]:
            wi, ti = test(rl, rh, d, h, sym, tf)
            w += wi
            t += ti
        if t > 50:
            results.append((rl, rh, d, h, sym, t, w / t * 100))

for r in sorted(results, key=lambda x: x[5], reverse=True)[:10]:
    print(f"rsi[{r[0]}-{r[1]}] {r[2]} h={r[3]} {r[4]}: {r[5]} trades, {r[6]:.1f}%")