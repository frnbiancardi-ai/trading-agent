"""Backtest comparativo ottimizzato."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import sma, rsi
from ml_feedback import RegimeDetector, MarketRegime


def optimized_strategy(bars, sma50, sma20, rsi_val, config):
    """Strategia ottimizzata con regole aggiustate."""
    from ml_feedback.regime_detector import RegimeDetector, MarketRegime
    
    close = bars[-1]["close"]
    regime_det = RegimeDetector(adx_trend_threshold=20, volatility_threshold=3.0).detect(bars)
    regime = regime_det.regime
    
    pip = 0.0001
    
    if regime == MarketRegime.TREND:
        rsi_ok = config["min_rsi"] < rsi_val[-1] < config["max_rsi"]
        if rsi_ok:
            bullish = close > sma20[-1] > sma50[-1]
            bearish = close < sma20[-1] < sma50[-1]
            if bullish:
                return {"type": "READY", "direction": "BUY", "sl": close - 15*pip, "tp": close + 25*pip, "regime": "TREND"}
            if bearish:
                return {"type": "READY", "direction": "SELL", "sl": close + 15*pip, "tp": close - 25*pip, "regime": "TREND"}
    
    elif regime == MarketRegime.RANGE:
        if rsi_val[-1] <= 25:
            return {"type": "READY", "direction": "BUY", "sl": close - 15*pip, "tp": close + 20*pip, "regime": "RANGE"}
        if rsi_val[-1] >= 75:
            return {"type": "READY", "direction": "SELL", "sl": close + 15*pip, "tp": close - 20*pip, "regime": "RANGE"}
    
    elif regime == MarketRegime.VOLATILE:
        if rsi_val[-1] <= 20 or rsi_val[-1] >= 80:
            direction = "BUY" if rsi_val[-1] <= 20 else "SELL"
            return {"type": "READY", "direction": direction, "sl": close - 20*pip, "tp": close + 30*pip, "regime": "VOLATILE"}
    
    return {"type": "NONE"}


def run_backtest(symbol, tf, start, end, max_bars=2500):
    bars = load_bars(symbol, tf, start, end)
    if len(bars) < 100:
        return {"trades": 0, "wins": 0, "regimes": {}}
    
    config = {"min_rsi": 30, "max_rsi": 70}
    trades = []
    regimes = {}
    
    for i in range(100, min(len(bars) - 2, max_bars)):
        window = bars[:i + 1]
        closes = [b["close"] for b in window]
        
        sma50 = sma(closes, 50)
        sma20 = sma(closes, 20)
        rsi_val = rsi(closes, 14)
        
        if not sma50 or not sma20 or not rsi_val:
            continue
        
        setup = optimized_strategy(window, sma50, sma20, rsi_val, config)
        if setup["type"] == "NONE":
            continue
        
        regimes[setup["regime"]] = regimes.get(setup["regime"], 0) + 1
        
        direction = setup["direction"]
        next_bar = bars[i + 1]
        
        is_win = (direction == "BUY" and next_bar["close"] > window[-1]["close"]) or (direction == "SELL" and next_bar["close"] < window[-1]["close"])
        
        trades.append({
            "direction": direction,
            "outcome": "WIN" if is_win else "LOSS",
            "regime": setup["regime"],
        })
    
    wins = sum(1 for t in trades if t["outcome"] == "WIN")
    return {
        "trades": len(trades),
        "wins": wins,
        "win_rate": wins / len(trades) if trades else 0,
        "regimes": regimes,
    }


def main():
    print("=== Optimized Backtest ===")
    
    total = {"trades": 0, "wins": 0, "regimes": {}}
    
    for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
        for tf in ["M15", "H1"]:
            r = run_backtest(symbol, tf, datetime(2024,1,1), datetime(2024,12,31), max_bars=2500)
            print(f"{symbol} {tf}: {r['trades']} trades, {r['win_rate']:.0%} win")
            total["trades"] += r["trades"]
            total["wins"] += r["wins"]
            for reg, cnt in r["regimes"].items():
                total["regimes"][reg] = total["regimes"].get(reg, 0) + cnt
    
    print()
    print(f"TOTAL: {total['trades']} trades, {total['wins']/total['trades']*100:.1f}% win")
    print(f"Regimes: {total['regimes']}")


if __name__ == "__main__":
    main()