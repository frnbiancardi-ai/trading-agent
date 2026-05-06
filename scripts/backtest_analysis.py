"""Script per backtest + ML analysis."""
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars, run_backtest, strategy_pullback, strategy_mean_reversion
from ml_feedback import MLFeedbackLoop, extract_trade_features


def parse_csv_trades(bars, strategy_fn, config):
    """Simula trades e li restituisce come lista."""
    trades = []
    
    period_ma = config.get("ma_period", 50)
    period_rsi = config.get("rsi_period", 14)
    pip_size = config.get("pip_size", 0.0001)
    
    from indicators import sma, rsi
    
    for i in range(period_ma + period_rsi + 10, len(bars) - 1):
        window = bars[:i + 1]
        last = window[-1]
        
        closes = [b["close"] for b in window]
        rsi_val = rsi(closes, period_rsi)
        
        sma_val = sma(closes, period_ma)
        sma20 = sma(closes, 20)
        
        last_close = last["close"]
        last_sma = sma_val[-1] if sma_val else None
        last_sma20 = sma20[-1] if sma20 else None
        last_rsi = rsi_val[-1] if rsi_val else None
        
        if last_sma is None or last_sma20 is None or last_rsi is None:
            continue
        
        setup = strategy_fn(
            close=last_close,
            sma=last_sma,
            sma20=last_sma20,
            rsi=last_rsi,
            pip_size=pip_size,
            config=config,
        )
        
        if setup["type"] == "NONE":
            continue
        
        next_bar = bars[i + 1]
        entry = setup.get("entry", last_close)
        direction = setup["direction"]
        
        sl = setup.get("sl")
        tp = setup.get("tp")
        
        if direction == "BUY":
            exit_price = next_bar["close"]
            if next_bar["low"] <= sl:
                outcome = "LOSS"
                profit = -1.0
            elif next_bar["high"] >= tp:
                r_mult = (tp - entry) / (entry - sl)
                outcome = "WIN"
                profit = r_mult
            else:
                outcome = "OPEN"
                profit = (exit_price - entry) / (entry - sl)
        else:
            exit_price = next_bar["close"]
            if next_bar["high"] >= sl:
                outcome = "LOSS"
                profit = -1.0
            elif next_bar["low"] <= tp:
                r_mult = (entry - tp) / (sl - entry)
                outcome = "WIN"
                profit = r_mult
            else:
                outcome = "OPEN"
                profit = (entry - exit_price) / (sl - entry)
        
        if outcome == "OPEN":
            continue
        
        trades.append({
            "symbol": config.get("symbol", "EURUSD"),
            "entry_time": last["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "exit_time": next_bar["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "direction": direction,
            "entry_price": entry,
            "exit_price": exit_price,
            "sl": sl,
            "tp": tp,
            "outcome": outcome,
            "profit_r": profit,
        })
    
    return trades


SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
TIMEFRAMES = ["M15", "M30", "H1"]


def main():
    all_trades = []
    
    configs = [
        {
            "name": "pullback",
            "fn": strategy_pullback,
            "config": {
                "symbol": "EURUSD",
                "ma_period": 50,
                "rsi_period": 14,
                "pip_size": 0.0001,
                "min_sl_pips": 15,
                "min_tp_pips": 25,
                "min_rr": 1.5,
                "min_rsi": 30,
                "max_rsi": 70,
                "min_trend_strength": 0.6,
            },
        },
        {
            "name": "mean_reversion",
            "fn": strategy_mean_reversion,
            "config": {
                "symbol": "EURUSD",
                "ma_period": 50,
                "rsi_period": 14,
                "pip_size": 0.0001,
                "min_sl_pips": 15,
                "min_tp_pips": 15,
                "min_rr": 1.0,
                "max_trend_strength": 0.35,
                "rsi_buy_extreme": 25,
                "rsi_sell_extreme": 75,
            },
        },
    ]
    
    for cfg in configs:
        strategy_name = cfg["name"]
        strategy_fn = cfg["fn"]
        config = cfg["config"]
        
        for symbol in SYMBOLS:
            config["symbol"] = symbol
            config["pip_size"] = 0.0001 if "JPY" not in symbol else 0.01
            
            for tf in TIMEFRAMES:
                print(f"\n=== {strategy_name} | {symbol} {tf} ===")
                
                bars = load_bars(symbol, tf, datetime(2023, 1, 1), datetime(2024, 12, 31))
                
                if not bars:
                    continue
                
                trades = parse_csv_trades(bars, strategy_fn, config)
                print(f"Trade generati: {len(trades)}")
                
                if not trades:
                    continue
                
                wins = [t for t in trades if t["outcome"] == "WIN"]
                losses = [t for t in trades if t["outcome"] == "LOSS"]
                
                print(f"WIN: {len(wins)}, LOSS: {len(losses)}")
                
                all_trades.extend(trades)
    
    if not all_trades:
        print("Nessun trade generato!")
        return
    
    total_wins = sum(1 for t in all_trades if t["outcome"] == "WIN")
    total_losses = sum(1 for t in all_trades if t["outcome"] == "LOSS")
    
    print(f"\n=== TOTALE ===")
    print(f"Trade: {len(all_trades)}")
    print(f"WIN: {total_wins} ({total_wins/len(all_trades)*100:.1f}%)")
    print(f"LOSS: {total_losses} ({total_losses/len(all_trades)*100:.1f}%)")
    
    # Salva trades
    with open("backtest_trades.json", "w") as f:
        json.dump(all_trades, f, indent=2)
    print(f"\nSalvato: backtest_trades.json")
    
    # ML Analysis
    print(f"\n=== ML FEEDBACK ANALYSIS ===")
    ml = MLFeedbackLoop()
    analysis = ml.analyze_trades(all_trades)
    
    print(f"\nWin rate: {analysis['win_rate']:.1%}")
    print(f"Total trades: {analysis['total_trades']}")
    print(f"Wins: {analysis['wins']}, Losses: {analysis['losses']}")
    
    if analysis["by_session"]:
        print(f"\nBy Session:")
        for session, stats in analysis["by_session"].items():
            print(f"  {session}: W={stats['wins']}, L={stats['losses']}")
    
    if analysis["common_failure_patterns"]:
        print(f"\nFailure Patterns:")
        for pattern in analysis["common_failure_patterns"]:
            print(f"  - {pattern}")
    
    # Parameter suggestions
    current_params = {
        "ENABLE_ASIA_SESSION": True,
        "MIN_HOLD_MINUTES": 15,
        "MIN_BREAKOUT_VOLUME_RATIO": 1.5,
    }
    suggestions = ml.suggest_parameters(all_trades, current_params)
    
    if suggestions:
        print(f"\nParameter Suggestions:")
        for s in suggestions:
            print(f"  {s.param_name}: {s.current_value} -> {s.suggested_value}")
            print(f"    Reason: {s.reason}")


if __name__ == "__main__":
    main()