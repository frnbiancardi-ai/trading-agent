"""Inspect distribuzione confidence setup READY su backtest dataset."""
import logging
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backtest import BacktestMt5Client
from config import Config
from models import AccountState
from scripts.run_backtest import load_csv, filter_by_date


def main():
    cfg = Config()
    bars_all = load_csv(_ROOT / "data/historical/EURUSD/M15.csv")
    bars = filter_by_date(bars_all, datetime(2024, 1, 1), datetime(2024, 6, 30))

    imkt = {}
    for sym in list(cfg.INTERMARKET_SYMBOLS) + [cfg.DXY_PROXY_SYMBOL]:
        p = _ROOT / f"data/historical/{sym}/D1.csv"
        if p.exists():
            imkt[sym] = load_csv(p)

    mt5 = BacktestMt5Client(cfg, {"EURUSD": bars}, intermarket_bars=imkt)

    from strategy import IntradayStrategy
    log = logging.getLogger("inst")
    log.setLevel(logging.ERROR)
    strat = IntradayStrategy(cfg, mt5, log)

    confs = []
    for i in range(50, len(bars), 10):
        mt5.current_bar_index["EURUSD"] = i
        mt5.current_time = int(bars[i]["time"])
        acc = AccountState(
            balance=10000, equity=10000, free_margin=9500,
            open_positions=[], today_realized_pnl=0,
            starting_balance_of_day=10000,
        )
        setup = strat.analyze_symbol("EURUSD", acc)
        if setup.setup_type == "READY":
            confs.append(setup.confidence)

    print(f"Sampled bars: {len(range(50, len(bars), 10))}")
    print(f"READY setups: {len(confs)}")
    if confs:
        confs.sort()
        n = len(confs)
        print(f"min={confs[0]:.3f} max={confs[-1]:.3f} median={confs[n//2]:.3f}")
        print(f"p10={confs[n//10]:.3f} p25={confs[n//4]:.3f} "
              f"p75={confs[int(n*0.75)]:.3f} p90={confs[int(n*0.9)]:.3f}")
        # Distribuzione bucket
        buckets = {}
        for c in confs:
            b = round(c, 2)
            buckets[b] = buckets.get(b, 0) + 1
        print("\nDistribuzione:")
        for b in sorted(buckets):
            bar = "#" * buckets[b]
            print(f"  {b:.2f}: {buckets[b]:3d} {bar}")


if __name__ == "__main__":
    main()
