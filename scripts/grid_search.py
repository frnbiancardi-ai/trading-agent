"""Ricerca pattern semplice ed efficace."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import sma, rsi
from ml_feedback.regime_detector import RegimeDetector, MarketRegime


def test_strategy(rsi_low, rsi_high, direction, hold_bars, symbol, tf, max_bars=3000):
    bars = load_bars(symbol, tf, datetime(2024,1,1), datetime(2024,12,31), max_bars)
    if bars is None or len(bars) < 100:
        return 0, 0
    
    wins = 0
    trades = 0
    
    for i in range(200, min(len(bars) - hold_bars, max_bars)):
        w = bars[:i + 1]
        closes = [b["close"] for b in w]
        
        rsi_vals = rsi(closes, 14)
        
        if not rsi_vals:
            continue
        
        close = w[-1]["close"]
        rsi_now = rsi_vals[-1]
        
        if rsi_now < rsi_low or rsi_now > rsi_high:
            continue
        
        next_bar = bars[i + hold_bars]
        next_close = next_bar["close"]
        
        if direction == "LONG" and next_close > close:
            wins += 1
        elif direction == "SHORT" and next_close < close:
            wins += 1
        
        trades += 1
    
    return wins, trades


def grid_search():
    print("=== GRID SEARCH ===")
    
    best = {"wr": 0, "rsi_low": 0, "rsi_high": 100, "direction": "LONG", "hold": 1, "trades": 0}
    count = 0
    
    for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
        for tf in ["M15", "H1"]:
            for rsi_low in [10, 15, 20, 25, 30]:
                for rsi_high in [70, 75, 80, 85, 90]:
                    for direction in ["LONG", "SHORT"]:
                        for hold in [1, 2, 3, 4, 5]:
                            wins, trades = test_strategy(rsi_low, rsi_high, direction, hold, symbol, tf, max_bars=2000)
                            if trades < 50:
                                continue
                            wr = wins / trades
                            count += 1
                            if wr > best["wr"]:
                                best = {"wr": wr, "rsi_low": rsi_low, "rsi_high": rsi_high, "direction": direction, "hold": hold, "trades": trades}
                                print(f"BEST: {symbol} {tf} rsi[{rsi_low}-{rsi_high}] {direction} h={hold} -> {wr:.1%} ({trades})")
    
    print()
    print(f"Tested {count} combinations")
    print(f"BEST: {best}")


def main():
    grid_search()


if __name__ == "__main__":
    main()