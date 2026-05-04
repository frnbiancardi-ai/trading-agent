# Guida Backtest Trading-Agent — Fino a 10 anni di dati MT5

Guida completa per scaricare dati storici MT5 (fino a 10 anni), eseguire backtest del trading agent, e interpretare le metriche.

---

## 0. Prerequisiti

### 0.1 Software
- **MetaTrader 5 desktop** installato e loggato a un broker (TenTrade demo è già configurato)
- **Python 3.12 64-bit** + venv del progetto già presente in `C:\trading-agent\.venv`
- **Disco**: ~5–8 GB liberi per dataset 10 anni completo (M15 + M5 + H1 + H4 + Daily) su 8–10 simboli
- **RAM**: 8 GB minimo, 16 GB consigliato per backtest multi-simbolo

### 0.2 Verifica setup
```powershell
# Da PowerShell
cd C:\trading-agent
.\.venv\Scripts\python.exe -c "import MetaTrader5 as mt5; mt5.initialize(); print(mt5.terminal_info())"
```
Se output mostra `terminal_info(...connected=True...)` sei OK.

### 0.3 Branch corretto
```powershell
git checkout feature/strategy-v3-intermarket
git pull
```

---

## 1. Download dati storici da MT5

### 1.1 Limiti broker
MT5 generalmente fornisce:
- **M1/M5/M15**: ultimi 2–5 anni (dipende dal broker)
- **H1/H4**: ultimi 5–10 anni
- **Daily**: 15+ anni

**TenTrade demo** (test reale): ha tipicamente **6–8 anni** su M15, **10+ anni** su Daily. Verifica:
```powershell
.\.venv\Scripts\python.exe -c @"
import MetaTrader5 as mt5
from datetime import datetime
mt5.initialize()
rates = mt5.copy_rates_from('EURUSD', mt5.TIMEFRAME_M15, datetime(2015, 1, 1), 1)
print('Prima barra M15 disponibile:', datetime.fromtimestamp(rates[0]['time']) if rates is not None else 'NESSUNA')
mt5.shutdown()
"@
```

### 1.2 Script download dataset

Crea script `scripts/download_history.py`:

```python
"""Scarica dati storici MT5 multi-simbolo multi-timeframe.

Salva in CSV nella directory data/historical/<symbol>/<timeframe>.csv
Compatibile con BacktestMt5Client (load via pandas).
"""
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5

TIMEFRAMES = {
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

# Simboli core fase 18
DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "NZDUSD", "USDCAD",
    "XAUUSD", "USOIL",
]


def download_symbol(symbol: str, tf_name: str, start: datetime, end: datetime) -> list[dict]:
    """Scarica barre per simbolo+timeframe nel range [start, end]."""
    tf = TIMEFRAMES[tf_name]
    rates = mt5.copy_rates_range(symbol, tf, start, end)
    if rates is None or len(rates) == 0:
        print(f"  ⚠ Nessun dato per {symbol} {tf_name}")
        return []
    bars = []
    for r in rates:
        bars.append({
            "time": int(r["time"]),
            "datetime": datetime.fromtimestamp(r["time"]).isoformat(),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "tick_volume": int(r["tick_volume"]),
            "spread": int(r.get("spread", 0)),
        })
    return bars


def save_csv(bars: list[dict], path: Path):
    """Salva bars in CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not bars:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=bars[0].keys())
        writer.writeheader()
        writer.writerows(bars)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=10, help="Anni storia (default 10)")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--timeframes", nargs="+", default=["M15", "H1", "H4", "D1"])
    parser.add_argument("--output-dir", default="data/historical")
    args = parser.parse_args()

    if not mt5.initialize():
        print("FATAL: MT5 init failed:", mt5.last_error())
        sys.exit(1)

    end = datetime.now()
    start = end - timedelta(days=365 * args.years)

    out_dir = Path(args.output_dir)
    print(f"Download {args.years} anni ({start.date()} → {end.date()})")
    print(f"Simboli: {args.symbols}")
    print(f"Timeframes: {args.timeframes}\n")

    total_bars = 0
    for sym in args.symbols:
        for tf in args.timeframes:
            print(f"→ {sym} {tf}...", end=" ", flush=True)
            bars = download_symbol(sym, tf, start, end)
            if bars:
                path = out_dir / sym / f"{tf}.csv"
                save_csv(bars, path)
                print(f"{len(bars)} barre → {path}")
                total_bars += len(bars)
            else:
                print("VUOTO")

    mt5.shutdown()
    print(f"\nTotale barre scaricate: {total_bars:,}")


if __name__ == "__main__":
    main()
```

### 1.3 Esecuzione download

```powershell
# Quick test (1 simbolo, 1 anno)
.\.venv\Scripts\python.exe scripts\download_history.py --years 1 --symbols EURUSD --timeframes M15

# Full download (10 anni, 9 simboli, 4 TF) — può richiedere 10–30 min
.\.venv\Scripts\python.exe scripts\download_history.py --years 10
```

Output atteso:
```
Download 10 anni (2016-05-04 → 2026-05-04)
Simboli: ['EURUSD', 'GBPUSD', ...]
Timeframes: ['M15', 'H1', 'H4', 'D1']

→ EURUSD M15... 245760 barre → data\historical\EURUSD\M15.csv
→ EURUSD H1... 61440 barre → data\historical\EURUSD\H1.csv
...
Totale barre scaricate: 4,500,000
```

### 1.4 Disponibilità reale per broker
Se broker non fornisce 10 anni su M15 (limite tipico 5 anni):
- Usa `--years 5` per M15
- Usa `--years 10` solo per H1/H4/D1
- Per backtest M15 più lungo: combina dati da provider esterni (Dukascopy, HistData) e converti in CSV stesso formato

---

## 2. Setup environment per backtest

### 2.1 .env override
Crea `.env.backtest` (non committare) per parametri backtest:

```env
# Override per backtest
EXECUTION_MODE=shadow
ENABLE_NEWS_SENTIMENT=false
ENABLE_INTERMARKET_FILTER=true
ENABLE_REGIME_DETECTION=true
ENABLE_CORRELATION_MONITOR=true
ENABLE_CROSS_ASSET_FILTER=true
ENABLE_SESSION_FILTER=true
ENABLE_FIBONACCI_TARGETS=true
ENABLE_ACTIVE_POSITION_MGMT=true

# Backtest range
BACKTEST_START_DATE=2020-01-01
BACKTEST_END_DATE=2025-12-31
BACKTEST_INITIAL_BALANCE=10000.0
BACKTEST_DATA_DIR=data/historical

# Riduci scan per backtest veloce
INTRADAY_TIMEFRAME=M15
INTRADAY_LOOKBACK_BARS=200
```

### 2.2 Loader CSV per BacktestMt5Client

Crea `scripts/run_backtest.py`:

```python
"""Esegue backtest end-to-end caricando CSV storici."""
import argparse
import csv
import logging
from datetime import datetime
from pathlib import Path

from config import Config
from backtest import BacktestEngine, BacktestMt5Client


def load_csv(path: Path) -> list[dict]:
    """Carica CSV in lista dict OHLC."""
    bars = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            bars.append({
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "tick_volume": int(r["tick_volume"]),
            })
    return bars


def filter_by_date(bars: list[dict], start: datetime, end: datetime) -> list[dict]:
    """Filtra barre per date range."""
    s, e = int(start.timestamp()), int(end.timestamp())
    return [b for b in bars if s <= b["time"] <= e]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--data-dir", default="data/historical")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--report", default="reports/backtest_latest.txt")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("backtest")

    cfg = Config()  # carica .env

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)

    # Carica dataset per ogni simbolo
    data_dir = Path(args.data_dir)
    symbol_to_bars = {}
    for sym in args.symbols:
        path = data_dir / sym / f"{args.timeframe}.csv"
        if not path.exists():
            log.error("Manca dataset: %s", path)
            continue
        bars = filter_by_date(load_csv(path), start, end)
        log.info("Caricato %s: %d barre nel range", sym, len(bars))
        symbol_to_bars[sym] = bars

    if not symbol_to_bars:
        log.fatal("Nessun dataset caricato. Eseguire scripts/download_history.py")
        return

    # Avvia engine
    mt5_mock = BacktestMt5Client(cfg, symbol_to_bars)
    engine = BacktestEngine(
        cfg=cfg,
        mt5_client=mt5_mock,
        initial_balance=args.initial_balance,
        logger=log,
    )

    report = engine.run(symbols=list(symbol_to_bars.keys()))

    # Output report
    print("\n" + "=" * 60)
    print(" BACKTEST REPORT")
    print("=" * 60)
    print(f"Range:           {args.start} → {args.end}")
    print(f"Simboli:         {args.symbols}")
    print(f"Saldo iniziale:  ${report.start_balance:,.2f}")
    print(f"Saldo finale:    ${report.end_balance:,.2f}")
    print(f"Profit totale:   {report.total_profit_pct:+.2f}%")
    print(f"Trade totali:    {report.total_trades}")
    print(f"Win rate:        {report.winrate:.1%}")
    print(f"Avg win:         {report.avg_win_pct:+.3f}%")
    print(f"Avg loss:        {report.avg_loss_pct:+.3f}%")
    print(f"Profit factor:   {report.profit_factor:.2f}")
    print(f"Expectancy:      {report.expectancy:+.3f}%")
    print(f"Max DD:          {report.max_drawdown_pct:.2f}%")
    print(f"Sharpe ratio:    {report.sharpe_ratio:.2f}")
    print(f"Max consec loss: {report.max_consecutive_losses}")
    print("=" * 60)

    # Save report file
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Backtest report\n")
        f.write(f"Range: {args.start} → {args.end}\n")
        f.write(f"Symbols: {args.symbols}\n")
        f.write(f"Initial balance: {report.start_balance}\n")
        f.write(f"Final balance: {report.end_balance}\n")
        f.write(f"Trades: {report.total_trades}\n")
        f.write(f"Winrate: {report.winrate}\n")
        f.write(f"Profit factor: {report.profit_factor}\n")
        f.write(f"Expectancy: {report.expectancy}\n")
        f.write(f"Max DD: {report.max_drawdown_pct}%\n")
        f.write(f"Sharpe: {report.sharpe_ratio}\n")
        f.write(f"\nTrades dettaglio:\n")
        for t in report.trades:
            f.write(f"  {t.entry_time.isoformat()} {t.symbol} {t.direction} "
                    f"{t.entry_price:.5f}→{t.exit_price:.5f} {t.exit_reason} "
                    f"profit={t.profit_pct:+.3f}% R={t.profit_r:+.2f}\n")
    log.info("Report salvato in %s", report_path)


if __name__ == "__main__":
    main()
```

---

## 3. Esecuzione backtest

### 3.1 Backtest singolo (smoke test)
```powershell
.\.venv\Scripts\python.exe scripts\run_backtest.py `
    --start 2024-01-01 --end 2024-12-31 `
    --symbols EURUSD `
    --timeframe M15 `
    --report reports\eurusd_2024.txt
```

### 3.2 Backtest 10 anni multi-simbolo
```powershell
.\.venv\Scripts\python.exe scripts\run_backtest.py `
    --start 2016-05-04 --end 2026-05-04 `
    --symbols EURUSD GBPUSD USDJPY USDCHF AUDUSD USDCAD XAUUSD `
    --timeframe M15 `
    --initial-balance 10000 `
    --report reports\full_10y_v3.txt
```

**Tempo stimato**: 30 min – 2 ore su 7 simboli × M15 × 10 anni (≈3M barre processate). Più simboli + tutti filtri intermarket attivi = più lento.

### 3.3 Confronto v2 vs v3 (Defendi vs Defendi+Murphy+Probo)

```powershell
# v2: solo Defendi
$env:ENABLE_INTERMARKET_FILTER = "false"
$env:ENABLE_REGIME_DETECTION = "false"
$env:ENABLE_CROSS_ASSET_FILTER = "false"
$env:ENABLE_SESSION_FILTER = "false"
$env:ENABLE_FIBONACCI_TARGETS = "false"
.\.venv\Scripts\python.exe scripts\run_backtest.py `
    --start 2020-01-01 --end 2025-12-31 `
    --symbols EURUSD GBPUSD `
    --report reports\v2_defendi_only.txt

# v3: tutti filtri attivi
$env:ENABLE_INTERMARKET_FILTER = "true"
$env:ENABLE_REGIME_DETECTION = "true"
$env:ENABLE_CROSS_ASSET_FILTER = "true"
$env:ENABLE_SESSION_FILTER = "true"
$env:ENABLE_FIBONACCI_TARGETS = "true"
.\.venv\Scripts\python.exe scripts\run_backtest.py `
    --start 2020-01-01 --end 2025-12-31 `
    --symbols EURUSD GBPUSD `
    --report reports\v3_intermarket.txt

# Confronto
type reports\v2_defendi_only.txt
type reports\v3_intermarket.txt
```

---

## 4. Calibrazione parametri (grid-search)

Per trovare parametri ottimali su dati storici:

### 4.1 Estendere `scripts/run_calibration.py`

Lo skeleton fase 17.7 supporta grid-search. Esempio param grid:

```python
PARAM_GRID = {
    "MIN_CONFIDENCE_TO_PROPOSE": [0.55, 0.60, 0.65, 0.70],
    "MIN_RISK_REWARD_RATIO": [1.5, 1.8, 2.0],
    "MIN_BREAKOUT_VOLUME_RATIO": [1.2, 1.3, 1.5],
    "MTF_BIAS_WEIGHT": [0.05, 0.10, 0.15],
    "REGIME_CONFIDENCE_PENALTY": [0.10, 0.15, 0.20],
    "CROSS_ASSET_BOOST": [0.05, 0.10, 0.15],
}
```

### 4.2 Esecuzione calibration
```powershell
.\.venv\Scripts\python.exe scripts\run_calibration.py `
    --start 2022-01-01 --end 2024-12-31 `
    --symbols EURUSD `
    --output reports\calibration.csv
```

Output: CSV con riga per ogni combo parametri + metriche (expectancy, Sharpe, MaxDD, profit_factor). Filtra Pareto-ottimali.

### 4.3 Walk-forward validation

Dividi dataset in finestre rolling per evitare overfitting:
- **Training**: 2016–2020 (calibra parametri)
- **Validation**: 2021–2022 (verifica robustezza)
- **Test out-of-sample**: 2023–2026 (metriche finali)

I parametri devono performare consistentemente su tutte e 3 le finestre.

---

## 5. Interpretazione metriche

### 5.1 Metriche chiave

| Metrica | Significato | Target |
|---------|-------------|--------|
| **Expectancy** | Profitto medio per trade (%) | > 0.10% positivo |
| **Profit factor** | Gross profit / Gross loss | > 1.5 buono, > 2.0 ottimo |
| **Win rate** | % trade vincenti | 40–60% (non max obiettivo) |
| **Max DD %** | Massimo drawdown peak-to-trough | < 15% accettabile, < 10% ottimo |
| **Sharpe ratio** | Risk-adjusted return | > 1.0 ok, > 1.5 buono, > 2.0 ottimo |
| **Max consec losses** | Sequenza max perdite | < 6 indica robustezza |
| **Total profit %** | Ritorno totale del periodo | dipende da durata; 30–80% in 5 anni = buono |

### 5.2 Target accettazione fase 18

v3 (intermarket-enhanced) deve battere v2 su **almeno 2** di:
- Expectancy: ≥ +20% rispetto v2
- Sharpe ratio: ≥ +0.3 punti
- Max DD: ≤ v2 (no peggioramento)
- Profit factor: ≥ +0.2

### 5.3 Red flags
- **Profit factor < 1.0**: strategia perde nel lungo periodo
- **Max DD > 25%**: rischio rovinoso
- **Sharpe < 0.5**: non vale rischio
- **Win rate > 80%** ma profit_factor < 1.5: TP troppo stretti, R:R sbilanciato
- **Solo 5 trade in 2 anni**: filtri troppo stretti

---

## 6. Workflow consigliato

### 6.1 Setup iniziale (1 volta)
```powershell
# 1. Download dati
.\.venv\Scripts\python.exe scripts\download_history.py --years 10

# 2. Verifica dataset
ls data\historical\EURUSD\

# 3. Smoke test
.\.venv\Scripts\python.exe scripts\run_backtest.py --start 2024-01-01 --end 2024-06-30 --symbols EURUSD
```

### 6.2 Iterazione sviluppo
```powershell
# Modifica strategia/parametri in .env

# Backtest rapido (1 anno, 1 simbolo)
.\.venv\Scripts\python.exe scripts\run_backtest.py --start 2024-01-01 --end 2024-12-31 --symbols EURUSD

# Backtest medio (3 anni, 3 simboli)
.\.venv\Scripts\python.exe scripts\run_backtest.py --start 2022-01-01 --end 2024-12-31 --symbols EURUSD GBPUSD USDJPY

# Backtest finale (10 anni, full universe)
.\.venv\Scripts\python.exe scripts\run_backtest.py --start 2016-05-04 --end 2026-05-04
```

### 6.3 Production check
Prima di passare strategia a live:
1. Backtest 10 anni dati: profit_factor > 1.5, Sharpe > 1.0, MaxDD < 15%
2. Walk-forward 3 finestre: metriche consistenti
3. Calibration grid-search: scelti parametri Pareto-ottimali
4. Live shadow 48h su demo: verifica zero crash, decisioni allineate a backtest
5. Live small-size 1 settimana: monitora slippage, fill rate, news handling
6. Scale-up incrementale

---

## 7. Troubleshooting

### 7.1 MT5 non fornisce abbastanza storia
- **Soluzione 1**: usa broker diverso (IC Markets, Pepperstone hanno 10+ anni M15)
- **Soluzione 2**: scarica da Dukascopy (https://www.dukascopy.com/swiss/english/marketwatch/historical/) e converti CSV → formato MT5
- **Soluzione 3**: limita backtest a 5 anni M15 + 10 anni H1/H4

### 7.2 Backtest lento
- Riduci numero simboli
- Usa H1 invece di M15 per range lungo (24x più veloce)
- Disabilita correlation_monitor se non critico (richiede fetch multipli simboli)
- Usa numpy/pandas internamente per ottimizzare iterazione bar-by-bar

### 7.3 Backtest dà metriche troppo ottimiste
- **Look-ahead bias**: verifica che strategy non legga barre future
- **Survivorship bias**: assicurati simboli scelti non siano stati selezionati a posteriori
- **No-slippage assumption**: aggiungi spread realistico (1–2 pip EURUSD, 3–5 pip GBPJPY) e commission
- **Overfitting**: ripeti calibrazione walk-forward, non riusare stesso dataset per train + test

### 7.4 OutOfMemory su backtest 10 anni
- Processa simboli sequenzialmente invece che parallelamente
- Carica solo barre nel range backtest (filter_by_date già implementato)
- Stream CSV invece che caricare tutto in memoria

---

## 8. Estensioni future

- **Monte Carlo**: shuffle ordine trade per stimare worst-case DD
- **Bootstrap confidence intervals**: stima probabilità statistica metriche
- **Multi-account simulation**: backtest con N account paralleli (diverse seed/parametri)
- **Tick-level backtest**: per scalping H1 in poi richiede dati tick (Dukascopy)
- **Slippage realistico**: modello stocastico di esecuzione fill basato su volume tick

---

## 9. File di riferimento progetto

| File | Ruolo |
|------|-------|
| `backtest.py` | BacktestEngine, BacktestMt5Client, metric calculation |
| `tests/test_backtest_harness.py` | Test unitari engine |
| `scripts/download_history.py` | Download CSV da MT5 (da creare) |
| `scripts/run_backtest.py` | Runner backtest end-to-end (da creare) |
| `scripts/run_calibration.py` | Grid-search calibration (skeleton 17.7) |
| `data/historical/<symbol>/<tf>.csv` | Dataset OHLC |
| `reports/*.txt` | Output backtest |
| `.env.backtest` | Override config |

---

## Note finali

Strategia v3 (Phase 18) attiva tutti i filtri Murphy + Probo + Defendi:
- Intermarket context (Dollar/Gold/Oil trend)
- Regime detection (Risk-On/Off/Inflationary)
- Cross-asset confirmation (BUY EUR/USD richiede USD/CHF debole)
- Session awareness (boost confidence in London/Overlap)
- Fibonacci multi-target (TP_618 primary, partial 38.2/61.8)
- Position management attiva (BE 1R, partial 50% 2R, trailing Chandelier)

Il backtest 10 anni dovrebbe dimostrare che **filtri intermarket riducono falsi positivi senza perdere troppi setup validi** (winrate +5–10%, profit_factor +0.3–0.5, MaxDD ridotto).

Buon backtest.
