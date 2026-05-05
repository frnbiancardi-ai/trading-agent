"""Grid-search MIN_CONFIDENCE_TO_PROPOSE per trovare ottimo su backtest 6m EURUSD M15."""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.run_backtest import load_csv, filter_by_date


def run_one(threshold: float, bars: list, intermarket_bars: dict, log) -> dict:
    """Esegue backtest 1 simbolo con threshold dato. Ritorna metriche."""
    os.environ["MIN_CONFIDENCE_TO_PROPOSE"] = str(threshold)

    # Force reload Config + strategy con nuovo env
    if "config" in sys.modules:
        del sys.modules["config"]
    if "strategy" in sys.modules:
        del sys.modules["strategy"]
    if "backtest" in sys.modules:
        del sys.modules["backtest"]

    from config import Config
    from backtest import BacktestEngine, BacktestMt5Client

    cfg = Config()
    mt5 = BacktestMt5Client(cfg, {"EURUSD": bars}, intermarket_bars=intermarket_bars)
    engine = BacktestEngine(cfg=cfg, mt5_client=mt5, initial_balance=10000.0, logger=log)
    report = engine.run(symbols=["EURUSD"])

    return {
        "thr": threshold,
        "trades": report.total_trades,
        "wr": report.winrate,
        "pf": report.profit_factor,
        "exp": report.expectancy,
        "dd": report.max_drawdown_pct,
        "net": report.total_net_profit_usd,
        "sharpe": report.sharpe_ratio,
    }


def main():
    log = logging.getLogger("grid")
    log.setLevel(logging.WARNING)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    bars_all = load_csv(_ROOT / "data/historical/EURUSD/M15.csv")
    bars = filter_by_date(bars_all, datetime(2024, 1, 1), datetime(2024, 6, 30))
    print(f"Dataset EURUSD M15 6m 2024: {len(bars)} bars")

    # Carica intermarket once
    from config import Config as _Cfg
    cfg0 = _Cfg()
    imkt = {}
    for sym in list(cfg0.INTERMARKET_SYMBOLS) + [cfg0.DXY_PROXY_SYMBOL]:
        p = _ROOT / f"data/historical/{sym}/D1.csv"
        if p.exists():
            imkt[sym] = load_csv(p)

    thresholds = [0.30, 0.35, 0.38, 0.40, 0.42, 0.45, 0.48, 0.50]
    results = []
    for t in thresholds:
        r = run_one(t, bars, imkt, log)
        results.append(r)
        print(
            f"thr={r['thr']:.2f}  trades={r['trades']:3d}  WR={r['wr']:.1%}  "
            f"PF={r['pf']:>5.2f}  exp={r['exp']:+.3f}%  DD={r['dd']:.1f}%  "
            f"net=${r['net']:+,.0f}  Sharpe={r['sharpe']:+.2f}"
        )

    # Pareto-best
    print("\nPareto best (max net profit + min DD):")
    valid = [r for r in results if r["trades"] >= 20]
    if valid:
        best = max(valid, key=lambda r: r["net"] - r["dd"] * 50)
        print(
            f"  thr={best['thr']:.2f}  net=${best['net']:+,.0f}  "
            f"PF={best['pf']:.2f}  DD={best['dd']:.1f}%"
        )


if __name__ == "__main__":
    main()
