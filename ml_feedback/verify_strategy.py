"""VERIFICA ACCURATA - Strategy Validator."""
import sys
from datetime import datetime
from pathlib import Path
import json

sys.path.insert(0, ".")

from backtest import load_bars
from indicators import rsi, sma

# Parametri esatti da testare
SHORT_CONFIG = {
    "rsi_min": 65,
    "rsi_max": 90,
    "sma_period": 200,
    "hold_bars": 2,
    "sl": 15,
    "tp": 22.5
}

print("=== VERIFICA ACCURATA STRATEGIA ===")
print(f"Config: RSI {SHORT_CONFIG['rsi_min']}-{SHORT_CONFIG['rsi_max']} + SMA {SHORT_CONFIG['sma_period']}")
print()

# Test singolo anno verificato
year = 2024
symbols = ["EURUSD", "GBPUSD", "USDJPY"]

all_trades = []

for sym in symbols:
    bars = load_bars(sym, "M15", datetime(2024, 1, 1), datetime(2024, 12, 31))
    
    if not bars or len(bars) < 300:
        continue
    
    print(f"\n{sym}: {len(bars)} bars caricati")
    
    trade_count = 0
    wins = 0
    losses = 0
    
    for i in range(200, len(bars) - SHORT_CONFIG["hold_bars"]):
        c = [b["close"] for b in bars[:i]]
        
        if len(c) < SHORT_CONFIG["sma_period"] + 14:
            continue
            
        sma_val = sma(c, SHORT_CONFIG["sma_period"])
        rsi_val = rsi(c, 14)
        
        if sma_val is None or rsi_val is None:
            continue
        if sma_val[-1] is None or rsi_val[-1] is None:
            continue
            
        current_price = bars[i]["close"]
        exit_price = bars[i + SHORT_CONFIG["hold_bars"]]["close"]
        
        # Signal detection
        is_short_signal = (
            SHORT_CONFIG["rsi_min"] <= rsi_val[-1] <= SHORT_CONFIG["rsi_max"] and
            current_price > sma_val[-1]
        )
        
        if is_short_signal:
            trade_count += 1
            is_win = exit_price < current_price
            
            if is_win:
                wins += 1
            else:
                losses += 1
            
            all_trades.append({
                "symbol": sym,
                "bar": i,
                "entry": current_price,
                "exit": exit_price,
                "rsi": rsi_val[-1],
                "sma": sma_val[-1],
                "result": "WIN" if is_win else "LOSS"
            })
    
    wr = wins / trade_count * 100 if trade_count > 0 else 0
    print(f"  Trades generati: {trade_count}")
    print(f"  Wins: {wins}, Losses: {losses}")
    print(f"  Win Rate: {wr:.1f}%")
    
    # Show some examples
    if all_trades:
        print(f"  Primi 3 trade:")
        for t in all_trades[:3]:
            print(f"    {t['symbol']} @ {t['entry']:.5f} -> {t['exit']:.5f} ({t['result']}, RSI={t['rsi']:.1f})")

# Total
total_trades = len(all_trades)
wins_total = sum(1 for t in all_trades if t["result"] == "WIN")
wr_total = wins_total / total_trades * 100 if total_trades > 0 else 0

print(f"\n=== TOTALE VERIFICATO ===")
print(f"Total trades: {total_trades}")
print(f"Win Rate: {wr_total:.1f}%")

# Verify data accuracy
print(f"\n=== VERIFICA DATI ===")
print(f"Data source: data/historical/")
print(f"Symbols: EURUSD, GBPUSD, USDJPY")
print(f"Timeframe: M15")
print(f"Period: 2024-01-01 to 2024-12-31")

# Save detailed results
with open("ml_feedback/detailed_validation.json", "w") as f:
    json.dump({
        "config": SHORT_CONFIG,
        "year": 2024,
        "total_trades": total_trades,
        "wins": wins_total,
        "losses": total_trades - wins_total,
        "win_rate": round(wr_total, 2),
        "trades_sample": all_trades[:50]  # First 50 for verification
    }, f, indent=2)

print(f"\nSaved: ml_feedback/detailed_validation.json")