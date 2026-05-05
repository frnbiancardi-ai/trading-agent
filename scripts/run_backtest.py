"""Runner backtest end-to-end.

Carica CSV storici da data/historical/<symbol>/<tf>.csv,
istanzia BacktestMt5Client + BacktestEngine, esegue strategia,
salva report testuale in reports/.

Esempio:
    python scripts/run_backtest.py --start 2024-01-01 --end 2024-12-31 --symbols EURUSD
    python scripts/run_backtest.py --start 2022-06-01 --end 2026-05-04 --symbols EURUSD GBPUSD
"""
import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

# Aggiungi root progetto a sys.path per permettere import quando script lanciato da scripts/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backtest import BacktestEngine, BacktestMt5Client
from config import Config


def load_csv(path: Path) -> list[dict]:
    """Carica CSV in lista dict OHLC."""
    if not path.exists():
        return []
    bars = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                bars.append({
                    "time": int(r["time"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "tick_volume": int(r.get("tick_volume", 1) or 1),
                })
            except (ValueError, KeyError):
                continue
    return bars


def filter_by_date(bars: list[dict], start: datetime, end: datetime) -> list[dict]:
    s, e = int(start.timestamp()), int(end.timestamp())
    return [b for b in bars if s <= b["time"] <= e]


def format_pf(pf: float) -> str:
    if pf == float("inf"):
        return "inf (no losses)"
    return f"{pf:.2f}"


def write_report(report, args, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(" BACKTEST REPORT\n")
        f.write("=" * 60 + "\n")
        f.write(f"Range:          {args.start} -> {args.end}\n")
        f.write(f"Symbols:        {', '.join(args.symbols)}\n")
        f.write(f"Timeframe:      {args.timeframe}\n")
        f.write(f"Initial bal.:   ${report.start_balance:,.2f}\n")
        f.write(f"Final bal.:     ${report.end_balance:,.2f}\n")
        f.write(f"Profit total:   {report.total_profit_pct:+.2f}%\n")
        f.write(f"Trades:         {report.total_trades}\n")
        f.write(f"Winrate:        {report.winrate:.1%}\n")
        f.write(f"Avg win:        {report.avg_win_pct:+.3f}%\n")
        f.write(f"Avg loss:       {report.avg_loss_pct:+.3f}%\n")
        f.write(f"Profit factor:  {format_pf(report.profit_factor)}\n")
        f.write(f"Expectancy:     {report.expectancy:+.3f}%\n")
        f.write(f"Max DD:         {report.max_drawdown_pct:.2f}%\n")
        f.write(f"Sharpe ratio:   {report.sharpe_ratio:.2f}\n")
        f.write(f"Max consec L:   {report.max_consecutive_losses}\n")
        f.write("-" * 60 + "\n")
        f.write(" COSTI REALISTICI (spread + commission + slippage)\n")
        f.write("-" * 60 + "\n")
        f.write(f"Gross profit:   ${report.total_gross_profit_usd:+,.2f}\n")
        f.write(f"Net profit:     ${report.total_net_profit_usd:+,.2f}\n")
        f.write(f"Spread cost:    ${report.total_spread_cost_usd:,.2f}\n")
        f.write(f"Commission:     ${report.total_commission_usd:,.2f}\n")
        f.write(f"Slippage cost:  ${report.total_slippage_cost_usd:,.2f}\n")
        f.write("=" * 60 + "\n\n")
        f.write("TRADES DETAIL:\n")
        for t in report.trades:
            f.write(
                f"  {t.entry_time.isoformat()} {t.symbol:8} {t.direction:4} "
                f"{t.entry_price:.5f}->{t.exit_price:.5f} {t.exit_reason:6} "
                f"profit={t.profit_pct:+7.3f}% R={t.profit_r:+5.2f}\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backtest end-to-end")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-05-04")
    parser.add_argument("--data-dir", default="data/historical")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD"])
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--report", default=None,
                        help="Path output report (default: reports/bt_<timestamp>.txt)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("backtest")

    # Silenzia rejects risk_engine + strategy in modalità non-verbose: troppo
    # rumore per backtest (centinaia di setup scartati per SL stretto, R:R basso).
    if not args.verbose:
        logging.getLogger("risk_engine").setLevel(logging.WARNING)
        logging.getLogger("strategy").setLevel(logging.WARNING)

    cfg = Config()  # legge .env

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)

    data_dir = Path(args.data_dir)
    symbol_to_bars: dict[str, list[dict]] = {}
    for sym in args.symbols:
        path = data_dir / sym / f"{args.timeframe}.csv"
        bars_all = load_csv(path)
        if not bars_all:
            log.error("Manca dataset: %s -> skip %s", path, sym)
            continue
        bars = filter_by_date(bars_all, start, end)
        log.info("%s %s: %d barre nel range", sym, args.timeframe, len(bars))
        if bars:
            symbol_to_bars[sym] = bars

    if not symbol_to_bars:
        log.fatal("Nessun dataset valido. Esegui scripts/download_history.py o import_histdata.py")
        return 1

    # Carica intermarket bars per IntermarketEngine se flag attivo.
    # Usa cfg.INTERMARKET_TIMEFRAME (default H4) se disponibile, altrimenti fallback D1.
    intermarket_bars: dict[str, list[dict]] = {}
    if cfg.ENABLE_INTERMARKET_FILTER:
        intermarket_tf = cfg.INTERMARKET_TIMEFRAME
        # Simboli da caricare: INTERMARKET_SYMBOLS + DXY_PROXY (EURUSD)
        intermarket_symbols = list(cfg.INTERMARKET_SYMBOLS) + [cfg.DXY_PROXY_SYMBOL]
        for sym in intermarket_symbols:
            # Skip se già è il TF principale del trading symbol (es. EURUSD M15)
            if sym in symbol_to_bars and intermarket_tf == args.timeframe:
                continue
            path = data_dir / sym / f"{intermarket_tf}.csv"
            bars_all = load_csv(path)
            if not bars_all and intermarket_tf != "D1":
                # Fallback D1
                fallback_path = data_dir / sym / "D1.csv"
                bars_all = load_csv(fallback_path)
                if bars_all:
                    log.warning("Intermarket %s/%s mancante, uso D1 fallback (%d bars)",
                                sym, intermarket_tf, len(bars_all))
            if not bars_all:
                log.warning("Intermarket %s mancante (%s + D1) -> engine fallback NEUTRAL",
                            sym, intermarket_tf)
                continue
            intermarket_bars[sym] = bars_all
            log.info("Intermarket %s %s: %d barre", sym, intermarket_tf, len(bars_all))

    mt5_mock = BacktestMt5Client(cfg, symbol_to_bars, intermarket_bars=intermarket_bars)
    engine = BacktestEngine(
        cfg=cfg,
        mt5_client=mt5_mock,
        initial_balance=args.initial_balance,
        logger=log,
        # strategy_module e risk_engine_module: lasciati None -> engine istanzia default
    )

    log.info("Avvio backtest...")
    report = engine.run(symbols=list(symbol_to_bars.keys()))

    # Console output
    print()
    print("=" * 60)
    print(" BACKTEST REPORT")
    print("=" * 60)
    print(f"Range:          {args.start} -> {args.end}")
    print(f"Symbols:        {', '.join(symbol_to_bars.keys())}")
    print(f"Initial bal.:   ${report.start_balance:,.2f}")
    print(f"Final bal.:     ${report.end_balance:,.2f}")
    print(f"Profit total:   {report.total_profit_pct:+.2f}%")
    print(f"Trades:         {report.total_trades}")
    print(f"Winrate:        {report.winrate:.1%}")
    print(f"Profit factor:  {format_pf(report.profit_factor)}")
    print(f"Expectancy:     {report.expectancy:+.3f}%")
    print(f"Max DD:         {report.max_drawdown_pct:.2f}%")
    print(f"Sharpe:         {report.sharpe_ratio:.2f}")
    print(f"Max consec L:   {report.max_consecutive_losses}")
    print("-" * 60)
    print(f"Gross profit:   ${report.total_gross_profit_usd:+,.2f}")
    print(f"Net profit:     ${report.total_net_profit_usd:+,.2f}")
    print(f"Spread cost:    ${report.total_spread_cost_usd:,.2f}")
    print(f"Commission:     ${report.total_commission_usd:,.2f}")
    print(f"Slippage cost:  ${report.total_slippage_cost_usd:,.2f}")
    print("=" * 60)
    print(f"Backtest costs config: spread={cfg.BACKTEST_SPREAD_PIPS}pip "
          f"commission=${cfg.BACKTEST_COMMISSION_PER_LOT}/lot "
          f"slippage={cfg.BACKTEST_SLIPPAGE_PIPS}pip")

    # File report
    if args.report:
        report_path = Path(args.report)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = Path("reports") / f"bt_{ts}.txt"
    write_report(report, args, report_path)
    log.info("Report salvato in %s", report_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
