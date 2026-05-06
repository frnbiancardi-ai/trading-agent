"""Analisi avanzata multi-timeframe."""
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import sma, rsi


def analyze_advanced(symbol, tf, start, end, max_bars=3000):
    bars = load_bars(symbol, tf, start, end)
    if len(bars) < 100:
        return {}
    
    patterns = defaultdict(lambda: {"win": 0, "total": 0, "profits": []})
    
    for i in range(200, min(len(bars) - 10, max_bars)):
        w = bars[:i + 1]
        closes = [b["close"] for b in w]
        
        rsi_vals = rsi(closes, 14)
        sma20 = sma(closes, 20)
        sma50 = sma(closes, 50)
        sma200 = sma(closes, 200)
        
        if not rsi_vals or not sma20 or not sma50 or not sma200:
            continue
        
        rsi_now = rsi_vals[-1]
        close = w[-1]["close"]
        
        above_20 = close > sma20[-1]
        above_50 = close > sma50[-1]
        above_200 = close > sma200[-1]
        below_200 = close < sma200[-1]
        
        prev_rsi = rsi_vals[-3] if len(rsi_vals) >= 3 else rsi_now
        
        rising_rsi = rsi_now > prev_rsi
        falling_rsi = rsi_now < prev_rsi
        
        for look in [1, 2, 3, 5]:
            next_bar = bars[i + look]
            next_close = next_bar["close"]
            profit = (next_close - close) / close * 10000 if close > 0 else 0
            
            key = f"rsi{int(rsi_now)}_{'rise' if rising_rsi else 'fall'}_{look}b"
            patterns[key]["total"] += 1
            patterns[key]["profits"].append(profit)
            if profit > 0:
                patterns[key]["win"] += 1
    
    return patterns


def main():
    totals = defaultdict(lambda: {"win": 0, "total": 0})
    
    for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
        for tf in ["M15", "H1"]:
            r = analyze_advanced(symbol, tf, datetime(2024,1,1), datetime(2024,12,31), max_bars=3000)
            for k, v in r.items():
                totals[k]["win"] += v["win"]
                totals[k]["total"] += v["total"]
    
    print("=== PATTERNS with MULTI-BAR ===")
    for k, v in sorted(totals.items(), key=lambda x: x[1]["total"], reverse=True)[:20]:
        if v["total"] > 100:
            wr = v["win"] / v["total"] * 100
            avg = sum(v["profits"]) / len(v["profits"])
            print(f"{k}: {v['total']} trades, {wr:.1f}% win, avg: {avg:.1f}pips")


if __name__ == "__main__":
    main()