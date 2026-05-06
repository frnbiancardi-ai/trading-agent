import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import sma, rsi
from ml_feedback import MLFeedbackLoop, extract_trade_features


def quick_backtest(symbol, timeframe, start, end, max_bars=5000):
    bars = load_bars(symbol, timeframe, start, end)
    if not bars:
        return []
    
    print(f"Loaded {len(bars)} bars, processing {max_bars}...")
    
    period = 50
    pip_size = 0.0001 if "JPY" not in symbol else 0.01
    
    config = {
        "min_sl_pips": 15,
        "min_rr": 1.5,
        "min_rsi": 30,
        "max_rsi": 70,
    }
    
    trades = []
    for i in range(period + 20, min(len(bars) - 2, max_bars)):
        window = bars[:i + 1]
        last = window[-1]
        closes = [b["close"] for b in window]
        
        sma_val = sma(closes, period)
        sma20 = sma(closes, 20)
        rsi_val = rsi(closes, 14)
        
        if not sma_val or not sma20 or not rsi_val:
            continue
        
        close = last["close"]
        bullish_align = close > sma20[-1] > sma_val[-1]
        bearish_align = close < sma20[-1] < sma_val[-1]
        rsi_ok = config["min_rsi"] < rsi_val[-1] < config["max_rsi"]
        
        if not (bullish_align or bearish_align) or not rsi_ok:
            continue
        
        direction = "BUY" if bullish_align else "SELL"
        next_bar = bars[i + 1]
        exit_price = next_bar["close"]
        
        is_win = (direction == "BUY" and exit_price > close) or (direction == "SELL" and exit_price < close)
        outcome = "WIN" if is_win else "LOSS"
        
        trades.append({
            "symbol": symbol,
            "entry_time": last["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "exit_time": next_bar["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "direction": direction,
            "entry_price": close,
            "exit_price": exit_price,
            "sl": close - config["min_sl_pips"] * pip_size if direction == "BUY" else close + config["min_sl_pips"] * pip_size,
            "tp": close + config["min_sl_pips"] * config["min_rr"] * pip_size,
            "atr_at_entry": 0.001,
            "volatility_regime": "MEDIUM",
        })
    
    return trades


def main():
    ml = MLFeedbackLoop()
    results = []
    
    for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
        for tf in ["M15", "H1"]:
            print(f"\n=== {symbol} {tf} ===")
            trades = quick_backtest(symbol, tf, datetime(2024,1,1), datetime(2024,12,31), max_bars=3000)
            
            if not trades:
                continue
            
            wins = 0
            for t in trades:
                if t["direction"] == "BUY":
                    if t["exit_price"] > t["entry_price"]:
                        wins += 1
                else:
                    if t["exit_price"] < t["entry_price"]:
                        wins += 1
            losses = len(trades) - wins
            
            print(f"Trades: {len(trades)}, WIN: {wins} ({wins/len(trades)*100:.0f}%), LOSS: {losses}")
            
            analysis = ml.analyze_trades(trades)
            print(f"Win rate: {analysis['win_rate']:.0%}")
            
            results.extend(trades)
    
    if not results:
        print("Nessun trade!")
        return
    
    total = len(results)
    wins = sum(1 for r in results)
    print(f"\n=== TOTALI ===")
    print(f"Trades: {total}, WIN: {wins} ({wins/total*100:.0f}%)")
    
    # Save
    with open("backtest_trades.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Salvato: backtest_trades.json")


if __name__ == "__main__":
    main()