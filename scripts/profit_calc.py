import sys
sys.path.insert(0, ".")
from backtest import load_bars
from indicators import rsi, sma
from datetime import datetime

SL_PIPS = 15
TP_PIPS = 22.5

print("=== PROFIT TEST (SHORT RSI 65-90 + Above SMA200) ===")
total_profit = 0
total_trades = 0

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    for tf in ["M15"]:
        bars = load_bars(sym, tf, datetime(2024, 1, 1), datetime(2024, 12, 31))
        if not bars or len(bars) < 500:
            continue
        
        pip_value = 100 if "JPY" in sym else 10000  # pips in price units
        wins = 0
        losses = 0
        profit_pips = 0.0
        
        for i in range(200, min(2000, len(bars) - 3)):
            closes = [b["close"] for b in bars[:i]]
            s200_val = sma(closes, 200)
            rs_val = rsi(closes, 14)
            
            if s200_val and rs_val and 65 <= rs_val[-1] <= 90 and bars[i]["close"] > s200_val[-1]:
                entry = bars[i]["close"]
                exit = bars[i + 2]["close"]
                
                if exit < entry:
                    profit_pips = profit_pips + TP_PIPS
                    wins = wins + 1
                else:
                    profit_pips = profit_pips - SL_PIPS
                    losses = losses + 1
        
        total_trades = total_trades + wins + losses
        total_profit = total_profit + profit_pips
        
        if wins + losses > 0:
            wr = wins / (wins + losses) * 100
            print(f"{sym} {tf}: {wins + losses} trades, WR={wr:.1f}%, Profit={profit_pips:.1f} pips")

print(f"\n=== TOTALE: {total_trades} trades, Profit={total_profit:.1f} pips ===")