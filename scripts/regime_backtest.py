"""Backtest comparativo: Pullback vs Regime-Based."""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import sma, rsi
from ml_feedback import RegimeDetector, create_regime_strategy, MarketRegime


def basic_strategy(close, sma50, sma20, rsi_val, config):
    """Basic pullback strategy (senza regime)."""
    bullish = close > sma20 > sma50
    bearish = close < sma20 < sma50
    
    if config["min_rsi"] < rsi_val < config["max_rsi"]:
        if bullish:
            return {"type": "READY", "direction": "BUY", "sl": close - 15 * 0.0001, "tp": close + 25 * 0.0001}
        if bearish:
            return {"type": "READY", "direction": "SELL", "sl": close + 15 * 0.0001, "tp": close - 25 * 0.0001}
    return {"type": "NONE"}


def regime_backtest(symbol, tf, start, end, max_bars=2000):
    """Backtest con regime."""
    bars = load_bars(symbol, tf, start, end)
    if len(bars) < 100:
        return {"trades": 0, "wins": 0, "losses": 0, "regimes": {}}
    
    detector = RegimeDetector()
    strategy = create_regime_strategy()
    
    config = {"min_rsi": 30, "max_rsi": 70}
    
    trades = []
    regimes = {}
    
    for i in range(200, min(len(bars) - 2, max_bars)):
        window = bars[:i + 1]
        closes = [b["close"] for b in window]
        highs = [b["high"] for b in window]
        lows = [b["low"] for b in window]
        
        sma50 = sma(closes, 50)
        sma20 = sma(closes, 20)
        rsi_val = rsi(closes, 14)
        
        if not sma50 or not sma20 or not rsi_val:
            continue
        
        close = window[-1]["close"]
        
        regime_det = detector.detect(window)
        regime = regime_det.regime.value
        
        regimes[regime] = regimes.get(regime, 0) + 1
        
        if regime == "VOLATILE":
            continue
        
        basic = basic_strategy(close, sma50[-1], sma20[-1], rsi_val[-1], config)
        if basic["type"] == "NONE":
            continue
        
        regime_result = strategy.analyze(window, [rsi_val[-1]], {"sma50": sma50, "sma20": sma20})
        
        if regime_result["type"] == "NONE":
            continue
        
        direction = regime_result.get("direction", basic.get("direction"))
        next_bar = bars[i + 1]
        
        is_win = (direction == "BUY" and next_bar["close"] > close) or (direction == "SELL" and next_bar["close"] < close)
        
        trades.append({
            "direction": direction,
            "outcome": "WIN" if is_win else "LOSS",
            "regime": regime,
        })
    
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    return {
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": wins / len(trades) if trades else 0,
        "regimes": regimes,
    }


def main():
    print("=== Backtest Comparison ===")
    print(f"Period: 2024-01-01 to 2024-12-31")
    print()
    
    results = []
    
    for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
        for tf in ["M15", "H1"]:
            print(f"Testing: {symbol} {tf}")
            r = regime_backtest(symbol, tf, datetime(2024, 1, 1), datetime(2024, 12, 31), max_bars=2000)
            results.append({"symbol": symbol, "tf": tf, **r})
            
            print(f"  Trades: {r['trades']}, Win: {r['win_rate']:.0%}")
            print(f"  Regimes: {r['regimes']}")
    
    print()
    
    total_trades = sum(r["trades"] for r in results)
    total_wins = sum(r["wins"] for r in results)
    
    print("=== TOTAL ===")
    print(f"Trades: {total_trades}")
    print(f"Win Rate: {total_wins / total_trades * 100:.1f}%" if total_trades > 0 else "N/A")
    
    print()
    print("Previous (basic pullback): ~47.6%")
    print(f"New (Regime-based): {total_wins / total_trades * 100:.1f}%" if total_trades > 0 else "N/A")


if __name__ == "__main__":
    main()