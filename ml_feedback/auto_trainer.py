"""Auto-trainer: esegue backtest periodico e aggiorna i parametri."""
import json
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import load_bars
from indicators import rsi, sma


CONFIG_FILE = Path(__file__).parent / "config_store.json"
SL = 15
TP = 22.5


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"current": {}, "history": [], "updated": None}


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Saved: {CONFIG_FILE}")


def run_backtest(year):
    """Esegue backtest per un year e ritorna stats."""
    results = []
    
    for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
        bars = load_bars(sym, "M15", datetime(f"{year}-01-01"), datetime(f"{year}-12-31"))
        if not bars or len(bars) < 100:
            continue
        
        wins = losses = profit = 0
        
        for i in range(200, min(2000, len(bars) - 3)):
            c = [b["close"] for b in bars[:i]]
            s200 = sma(c, 200)
            rs = rsi(c, 14)
            
            if s200 and rs and 65 <= rs[-1] <= 90 and bars[i]["close"] > s200[-1]:
                if bars[i + 2]["close"] < bars[i]["close"]:
                    wins += 1
                    profit += TP
                else:
                    losses += 1
                    profit -= SL
        
        results.append((sym, wins, losses, profit))
    
    total_trades = sum(r[1] + r[2] for r in results)
    total_wr = sum(r[1] for r in results) / total_trades * 100 if total_trades else 0
    total_profit = sum(r[3] for r in results)
    
    return {"year": year, "trades": total_trades, "win_rate": total_wr, "profit": total_profit}


def auto_train():
    """Auto-trainer: backtest + update se migliore."""
    cfg = load_config()
    
    current_wr = cfg.get("current", {}).get("win_rate", 0)
    
    print(f"=== AUTO TRAIN {datetime.now().year} ===")
    print(f"Current WR: {current_wr}%")
    
    # Run current year test
    stats = run_backtest(datetime.now().year)
    print(f"New WR: {stats['win_rate']:.1f}%, Profit: {stats['profit']:.0f} pips")
    
    if stats["win_rate"] > current_wr:
        print(f"✓ IMPROVEMENT! Updating config...")
        
        new_config = {
            "rsi_short_min": 65,
            "rsi_short_max": 90,
            "sma_period": 200,
            "hold_bars": 2,
            "sl_pips": 15,
            "tp_pips": 22.5,
            "win_rate": stats["win_rate"],
            "profit_pips": stats["profit"],
            "period": str(stats["year"]),
            "trades": stats["trades"]
        }
        
        cfg["history"].append(cfg.get("current", {}))
        cfg["current"] = new_config
        cfg["updated"] = datetime.now().isoformat()
        
        save_config(cfg)
    else:
        print(f"✗ No improvement. Keeping current config.")


if __name__ == "__main__":
    auto_train()