"""Multi-symbol grid: testa strategia su tutti i forex pair disponibili.

Per ogni simbolo + timeframe + threshold confidence, salva metriche.
Output: tabella ordinata per net profit / Sharpe.
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.run_backtest import load_csv, filter_by_date


SYMBOLS_FOREX = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD",
    "AUDUSD", "NZDUSD", "EURGBP", "EURJPY",
    "GBPJPY", "AUDJPY",
]


def run_one(symbol: str, tf: str, threshold: float, start: datetime, end: datetime,
            intermarket_bars: dict, log) -> dict | None:
    os.environ["MIN_CONFIDENCE_TO_PROPOSE"] = str(threshold)
    for mod in ("config", "strategy", "backtest"):
        if mod in sys.modules:
            del sys.modules[mod]

    from config import Config
    from backtest import BacktestEngine, BacktestMt5Client

    cfg = Config()
    csv_path = _ROOT / f"data/historical/{symbol}/{tf}.csv"
    bars_all = load_csv(csv_path)
    if not bars_all:
        return None
    bars = filter_by_date(bars_all, start, end)
    if len(bars) < 100:
        return None

    mt5 = BacktestMt5Client(cfg, {symbol: bars}, intermarket_bars=intermarket_bars)
    engine = BacktestEngine(cfg=cfg, mt5_client=mt5, initial_balance=10000.0, logger=log)
    report = engine.run(symbols=[symbol])

    return {
        "sym": symbol, "tf": tf, "thr": threshold,
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
    logging.basicConfig(level=logging.WARNING)

    # Intermarket bars
    from config import Config
    cfg0 = Config()
    imkt = {}
    for sym in list(cfg0.INTERMARKET_SYMBOLS) + [cfg0.DXY_PROXY_SYMBOL]:
        p = _ROOT / f"data/historical/{sym}/D1.csv"
        if p.exists():
            imkt[sym] = load_csv(p)

    # Test: H1 5 anni, threshold 0.42 (sweet spot da grid M15)
    start = datetime(2020, 1, 1)
    end = datetime(2024, 12, 31)
    tf = "H1"
    thr = 0.42

    print(f"Grid: H1 5y 2020-2024, threshold={thr}\n")
    print(f"{'Symbol':8} {'Trades':>6} {'WR':>6} {'PF':>5} {'Exp%':>7} {'DD%':>6} {'Net$':>10} {'Sharpe':>7}")
    print("-" * 72)

    results = []
    for sym in SYMBOLS_FOREX:
        r = run_one(sym, tf, thr, start, end, imkt, log)
        if r is None:
            print(f"{sym:8} (no data)")
            continue
        results.append(r)
        print(
            f"{r['sym']:8} {r['trades']:>6} {r['wr']:>6.1%} {r['pf']:>5.2f} "
            f"{r['exp']:>+7.3f} {r['dd']:>6.1f} {r['net']:>+10,.0f} {r['sharpe']:>+7.2f}"
        )

    # Top 3 per net
    print("\nTop 3 per net profit:")
    results.sort(key=lambda r: r["net"], reverse=True)
    for r in results[:3]:
        print(f"  {r['sym']} net=${r['net']:+,.0f} PF={r['pf']:.2f} WR={r['wr']:.1%} DD={r['dd']:.1f}%")

    print("\nTop 3 per Sharpe:")
    results.sort(key=lambda r: r["sharpe"], reverse=True)
    for r in results[:3]:
        print(f"  {r['sym']} Sharpe={r['sharpe']:+.2f} PF={r['pf']:.2f} net=${r['net']:+,.0f}")


if __name__ == "__main__":
    main()
