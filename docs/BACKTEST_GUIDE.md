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

### 1.1 Limiti broker (TenTrade demo, confermati 2026-05)

| Timeframe | Storia disponibile | Anno minimo |
|-----------|-------------------|-------------|
| M1        | ~1 anno           | 2025        |
| M5        | ~2 anni           | 2024        |
| **M15**   | **~4 anni**       | **2022-04** |
| M30       | ~6 anni           | 2020        |
| H1        | ~16 anni          | 2010-03     |
| H4        | 25+ anni          | 2000        |
| D1        | 25+ anni          | 2000        |

**Implicazione critica**: backtest puro M15 oltre 4 anni → impossibile con TenTrade. Per estendere usa fonti pubbliche (sezione 1.5).

### 1.2 Verifica storia disponibile
```powershell
cd C:\trading-agent
.\.venv\Scripts\python.exe -c @"
import MetaTrader5 as mt5
from datetime import datetime
mt5.initialize()
mt5.symbol_select('EURUSD', True)
for tf_name, tf in [('M15', mt5.TIMEFRAME_M15), ('H1', mt5.TIMEFRAME_H1), ('H4', mt5.TIMEFRAME_H4), ('D1', mt5.TIMEFRAME_D1)]:
    print(f'\n=== {tf_name} ===')
    for anno in [2024, 2020, 2016, 2012, 2008, 2004, 2000]:
        r = mt5.copy_rates_from('EURUSD', tf, datetime(anno, 6, 1), 1)
        ok = r is not None and len(r) > 0
        print(f'  {anno}: {\"OK \"+str(datetime.fromtimestamp(r[0][\"time\"])) if ok else \"vuoto\"}')
mt5.shutdown()
"@
```

### 1.3 Script download MT5

Script pronto: `scripts/download_history.py`. Cap automatico per TF basato su limit TenTrade. Usa `--no-cap` per disabilitare e provare anni richiesti comunque.

Default symbols:
```python
DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "NZDUSD", "USDCAD",
    "XAUUSD", "USOIL",
]
```

Cap automatico per TF:
```python
TF_MAX_YEARS = {
    "M1": 1, "M5": 2, "M15": 4, "M30": 6,
    "H1": 16, "H4": 25, "D1": 25, "W1": 25,
}
```

### 1.4 Esecuzione download

```powershell
cd C:\trading-agent

# Smoke test (1 simbolo, 1 anno)
.\.venv\Scripts\python.exe scripts\download_history.py --years 1 --symbols EURUSD --timeframes M15

# Full download (max storia per ogni TF)
.\.venv\Scripts\python.exe scripts\download_history.py --years 25

# Solo daily 25 anni
.\.venv\Scripts\python.exe scripts\download_history.py --years 25 --timeframes D1

# Bypass cap (utile su altri broker con storia più lunga)
.\.venv\Scripts\python.exe scripts\download_history.py --years 10 --no-cap
```

Output atteso:
```
Account: 751081 @ TenTrade-Server
→ EURUSD M15 (4y, da 2022-05-05)... 95,000 barre (2022-05 → 2026-05)
→ EURUSD H1 (10y, da 2016-05-05)... 61,440 barre
→ EURUSD H4 (10y, da 2016-05-05)... 15,360 barre
→ EURUSD D1 (10y, da 2016-05-05)... 2,520 barre
...
```

### 1.5 Fonti dati alternative (per superare limit broker)

Per backtest **M15 oltre 4 anni** o per **Gold/Oil intraday**, broker MT5 non basta. Fonti pubbliche gratis:

| Fonte | Cosa | Pro | Contro |
|-------|------|-----|--------|
| **HistData.com** | M1 forex 2000+ | gratis, no API key, CSV pronto | download manuale, 1 zip per mese |
| **Dukascopy** | tick + M1 forex 2003+ | granularità massima | formato bi5 binario, serve converter |
| **Yahoo Finance** (yfinance) | D1 forex/futures/equities/crypto 30+ anni | API Python, super semplice | NO intraday forex >730gg |
| **Alpha Vantage** | M15+ forex 20y | API ufficiale | rate limit 25 req/giorno free |
| **Twelvedata** | M5/M15+ 8 req/min | API gratis | quota 800/giorno |
| Investing.com | tutto | UI bella | scraping vietato ToS, Cloudflare blocca |

**Vincitore per M15 forex 10y gratis**: **HistData**.
**Vincitore per Gold/Oil/SPX D1 10y**: **yfinance**.

#### 1.5a HistData → MT5 format

**Path A — download manuale (raccomandato)**:
1. Vai a https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurusd
2. Scarica zip mensili anno per anno (ogni zip ~50 KB, formato `HISTDATA_COM_ASCII_EURUSD_M1YYYYMM.zip` o `DAT_ASCII_EURUSD_M1_YYYYMM.zip`)
3. Estrai TUTTI i CSV in una directory: `data/histdata/EURUSD/`
4. Converti (vedi sezione 1.5d).

**Path B — auto-download (sperimentale)**:
```powershell
.\.venv\Scripts\python.exe scripts\download_histdata.py --symbol EURUSD --start 2016-01 --end 2026-04
```
HistData richiede form-POST con token CSRF; lo script può fallire se site cambia. In quel caso fallback a Path A.

#### 1.5d Conversione HistData M1 → CSV multi-TF (formato BacktestEngine)

Hai zip estratti in `data/histdata/EURUSD/`. Lancia:
```powershell
.\.venv\Scripts\python.exe scripts\import_histdata.py `
    --input-dir data\histdata\EURUSD `
    --symbol EURUSD `
    --timeframes M15 H1 H4 D1
```

Output:
```
data/historical/EURUSD/
├── M15.csv   (~350K barre, 10y)
├── H1.csv    (~87K barre)
├── H4.csv    (~21K barre)
└── D1.csv    (~3.6K barre)
```

Aggregazione bucket-fissi su epoch (no overlap, no look-ahead). Dedup automatico su confini mese.

Verifica:
```powershell
Get-Content data\historical\EURUSD\M15.csv -TotalCount 3
.\.venv\Scripts\python.exe -c "import csv; r=list(csv.DictReader(open('data/historical/EURUSD/M15.csv'))); print(f'Barre: {len(r):,}'); print(f'Range: {r[0][\"datetime\"]} → {r[-1][\"datetime\"]}')"
```

Atteso: ~350.000 barre M15, range `2016-01-04 00:00:00 → 2026-04-30 23:45:00`.

**Mantieni anche M1 raw** (utile per re-aggregare TF custom):
```powershell
.\.venv\Scripts\python.exe scripts\import_histdata.py --input-dir data\histdata\EURUSD --symbol EURUSD --timeframes M15 H1 H4 D1 --keep-m1
```
M1.csv ~3.5M barre (~500MB). Usa solo se serve.

#### 1.5e Quick start: hai già HistData EURUSD M1 10y

Se hai già estratto zip HistData in `data/histdata/EURUSD/`:

```powershell
# 1. Converti M1 → M15/H1/H4/D1
.\.venv\Scripts\python.exe scripts\import_histdata.py --input-dir data\histdata\EURUSD --symbol EURUSD

# 2. Smoke test 1 anno
.\.venv\Scripts\python.exe scripts\run_backtest.py --start 2024-01-01 --end 2024-12-31 --symbols EURUSD --timeframe M15

# 3. Backtest full 10y M15 (lungo: 30-90 min)
.\.venv\Scripts\python.exe scripts\run_backtest.py --start 2016-01-01 --end 2026-04-30 --symbols EURUSD --timeframe M15 --report reports\eurusd_m15_10y.txt

# 4. Backtest H1 10y (più veloce, ~5 min)
.\.venv\Scripts\python.exe scripts\run_backtest.py --start 2016-01-01 --end 2026-04-30 --symbols EURUSD --timeframe H1 --report reports\eurusd_h1_10y.txt
```

Per intermarket completo (Gold/Oil context), aggiungi:
```powershell
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker GC=F --symbol XAUUSD --interval 1d --years 10
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker CL=F --symbol USOIL --interval 1d --years 10
```
Nota: Gold/Oil D1 da yfinance; M15 intermarket non disponibile gratis. Il `IntermarketEngine` gira su H4/D1 → coerente.

#### 1.5b yfinance → MT5 format (Gold/Oil/SPX/crypto)

```powershell
pip install yfinance

# Gold D1 10 anni
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker GC=F --symbol XAUUSD --interval 1d --years 10

# Oil WTI D1
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker CL=F --symbol USOIL --interval 1d --years 10

# S&P 500 D1
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker ^GSPC --symbol SPX500 --interval 1d --years 10

# BTC D1
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker BTC-USD --symbol BTCUSD --interval 1d --years 10

# H1 max 730gg (limit yfinance)
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker GC=F --symbol XAUUSD --interval 1h --years 2
```

Tickers utili Yahoo:
- `EURUSD=X` `GBPUSD=X` `USDJPY=X` (forex spot D1)
- `GC=F` (Gold futures), `SI=F` (Silver), `CL=F` (WTI Oil), `NG=F` (NatGas)
- `^GSPC` (S&P 500), `^DJI` (Dow), `^IXIC` (Nasdaq), `^VIX` (VIX)
- `BTC-USD` `ETH-USD` (crypto)

#### 1.5c Strategia mista raccomandata

Per backtest 10 anni completo strategia v3:

```powershell
# Forex M15 4y da MT5
.\.venv\Scripts\python.exe scripts\download_history.py --years 4 --timeframes M15 --symbols EURUSD GBPUSD USDJPY USDCHF AUDUSD USDCAD

# Forex M15 10y da HistData (manuale download zip)
# → data/histdata/EURUSD/  ←  copia tutti CSV anni 2016-2026
.\.venv\Scripts\python.exe scripts\import_histdata.py --input-dir data\histdata\EURUSD --symbol EURUSD

# Gold/Oil D1 10y da yfinance
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker GC=F --symbol XAUUSD --interval 1d --years 10
.\.venv\Scripts\python.exe scripts\import_yfinance.py --ticker CL=F --symbol USOIL --interval 1d --years 10

# Forex H4 25y da MT5 (per regime/intermarket lungo periodo)
.\.venv\Scripts\python.exe scripts\download_history.py --years 25 --timeframes H4 --symbols EURUSD GBPUSD
```

Tutti i CSV finiscono in `data/historical/<symbol>/<TF>.csv` con stesso formato → backtest engine li legge uniformemente.

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

### 2.2 Runner backtest

Script pronto: `scripts/run_backtest.py`. Carica CSV da `data/historical/<symbol>/<tf>.csv`, istanzia BacktestMt5Client + BacktestEngine, salva report in `reports/`.

Args supportati:
- `--start YYYY-MM-DD` / `--end YYYY-MM-DD`
- `--symbols EURUSD GBPUSD ...`
- `--timeframe M15` (default)
- `--initial-balance 10000`
- `--data-dir data/historical`
- `--report path/to/report.txt`
- `-v` verbose

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

### 3.2 Backtest M15 4 anni (max TenTrade)
```powershell
.\.venv\Scripts\python.exe scripts\run_backtest.py `
    --start 2022-06-01 --end 2026-05-04 `
    --symbols EURUSD GBPUSD USDJPY USDCHF AUDUSD USDCAD `
    --timeframe M15 `
    --initial-balance 10000 `
    --report reports\bt_m15_4y.txt
```

### 3.3 Backtest H1 10 anni (storia lunga)
```powershell
.\.venv\Scripts\python.exe scripts\run_backtest.py `
    --start 2016-05-04 --end 2026-05-04 `
    --symbols EURUSD GBPUSD USDJPY `
    --timeframe H1 `
    --report reports\bt_h1_10y.txt
```

### 3.4 Backtest M15 10 anni (con HistData)
Solo dopo aver scaricato HistData (sezione 1.5a):
```powershell
.\.venv\Scripts\python.exe scripts\run_backtest.py `
    --start 2016-01-01 --end 2026-05-04 `
    --symbols EURUSD GBPUSD `
    --timeframe M15 `
    --report reports\bt_m15_10y_histdata.txt
```

**Tempo stimato**:
- M15 4y × 6 simboli ≈ ~500K barre → 5-15 min
- H1 10y × 3 simboli ≈ ~180K barre → 2-5 min
- M15 10y × 2 simboli (HistData) ≈ ~7M barre → 30-90 min

### 3.5 Confronto v2 vs v3 (Defendi vs Defendi+Murphy+Probo)

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

**Opzione A — solo MT5 (cap 4y M15)**:
```powershell
.\.venv\Scripts\python.exe scripts\download_history.py --years 10
ls data\historical\EURUSD\
.\.venv\Scripts\python.exe scripts\run_backtest.py --start 2024-01-01 --end 2024-06-30 --symbols EURUSD
```

**Opzione B — HistData M1 10y (raccomandato)**:
```powershell
# Pre-req: zip HistData estratti in data/histdata/EURUSD/
.\.venv\Scripts\python.exe scripts\import_histdata.py --input-dir data\histdata\EURUSD --symbol EURUSD
ls data\historical\EURUSD\
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
- **Soluzione 1**: usa HistData.com gratis (sezione 1.5a) — M1 forex 25+ anni
- **Soluzione 2**: yfinance per Gold/Oil/SPX D1 (sezione 1.5b)
- **Soluzione 3**: broker diverso con storia più lunga (IC Markets/Pepperstone tipicamente 10+ anni M15)
- **Soluzione 4**: limita backtest a TF cap reali (M15=4y, H1=16y, H4/D1=25y) usando script `download_history.py`

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
| `scripts/download_history.py` | Download CSV da MT5 (cap auto per TF) |
| `scripts/import_histdata.py` | Convert HistData M1 → M15/H1/H4/D1 CSV |
| `scripts/import_yfinance.py` | Yahoo Finance → CSV (Gold/Oil/SPX/crypto) |
| `scripts/download_histdata.py` | Auto-download HistData zip (sperimentale) |
| `scripts/run_backtest.py` | Runner backtest end-to-end |
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
