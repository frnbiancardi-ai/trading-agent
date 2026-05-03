# Phase 17 — Strategy v2 Defendi

Documento di specifica e implementazione della fase 17. Estende la strategia
intraday Python pura (fasi 14–16) con i pattern e i filtri descritti nel
manuale *Strategie Operative per i Mercati Finanziari* (Gianluca Defendi,
Hoepli). Obiettivo: passare da una strategia trend-following+breakout naive a
una strategia multi-setup (compressione volatilità, breakout qualificato,
pullback, multi-timeframe) validata su backtest storico.

Branch di lavoro: `feature/strategy-v2-defendi` (creato da `main` =
`v1.2.0`). Il branch `main` resta intoccato fino a esito positivo della
fase 17.6 (backtest comparativo).

## 1. Motivazione

L'audit della strategia v1.2.0 vs il manuale Defendi ha individuato 15 gap.
I principali, con riferimento ai capitoli del libro:

| # | Gap | Riferimento |
|---|-----|-------------|
| 1 | Compressione volatilità pre-breakout assente (Narrow Range, Boomer, Double Inside, Bollinger BandWidth, ATR contraction, VHF) | Cap 4 |
| 2 | Breakout non rispetta le 4 condizioni Defendi (max ultime 10 barre, range > avg5, volume > avg5, close in upper 80% range) | Cap 5 |
| 3 | Nessun filtro false breakout / trap | Cap 4 |
| 4 | Strategia di pullback su SR (entry low-risk preferita da Defendi) totalmente assente | Cap 5 |
| 5 | `check_rsi_divergence` esiste ma non è mai chiamata nel decision flow | Cap 2 |
| 6 | Indicatori trend quantitativi (MACD, Vortex, Parabolic SAR) assenti | Cap 5 |
| 7 | Volume Profile / VWAP / Value Area assenti | Cap 7 |
| 8 | Multi-timeframe placeholder (`mtf_score=0.1` hardcoded), nessuna conferma H1/H4 | Cap 5 |
| 9 | Pattern reversal avanzati (123 Low/High, Key Reversal, Morning/Evening Star) assenti | Cap 3 |
| 10 | TP fisso 1.5R, no breakeven move, no trailing, no scaling out | Cap 5/7 |
| 11 | Sentiment keyword-based (rumore) | — |
| 12 | Confidence con pesi arbitrari mai calibrati | — |
| 13 | Backtest assente: 173 unit test, zero validazione storica expectancy/Sharpe/MaxDD | — |
| 14 | Sessione awareness assente (Asian/London/NY trattate identiche) | — |
| 15 | Drawdown gate ignora correlazione tra simboli | — |

## 2. Obiettivi e vincoli

- **Non rompere** funzionalità v1.2.0: scheduler H24, kill switch, drawdown
  gate, close end-of-day, MCP server contract, risk engine restano invariati.
- **Backward compatibility**: tutti i 173 test esistenti devono continuare
  a passare.
- **Gate finale di merge**: la v2 deve battere v1.2.0 su backtest 6 mesi
  M15 EURUSD+GBPUSD su almeno 2 metriche tra: expectancy, profit factor,
  Sharpe, max drawdown. In caso contrario, no merge.
- **EXECUTION_MODE=shadow** resta default. `DRY_RUN=true` nei test live.
- **STATE.md** aggiornato dopo ogni micro-step (stessa convenzione fasi
  precedenti).
- **Lingua commenti/log/rationale**: italiano.
- **Una fase per file** in `.orchestration/phase-prompts/`. Sub-fasi 17.1–17.7
  ciascuna con proprio file di specifica (creati al momento dell'esecuzione).

## 3. Roadmap sub-fasi

| Sub-fase | Titolo | Output | Test | Stima |
|----------|--------|--------|------|-------|
| 17.1 | Indicatori avanzati | `indicators_advanced.py` | `test_indicators_advanced.py` | 1 gg |
| 17.2 | Compressione volatilità | `volatility_compression.py` + integrazione `IntradayStrategy` | `test_volatility_compression.py` | 1–2 gg |
| 17.3 | Pullback engine | `pullback_engine.py` + integrazione | `test_pullback_engine.py` | 2 gg |
| 17.4 | Multi-timeframe + divergenze attive | hook H1/H4 in `strategy.py`, attivazione `check_rsi_divergence` | aggiornamento `test_strategy.py` | 1 gg |
| 17.5 | Position management attiva | `position_manager.py` + nuovi `OpenPositionVerdict.action` | `test_position_manager.py` | 2 gg |
| 17.6 | Backtest harness | `backtest.py` + dataset 6m | `test_backtest_harness.py` | 2–3 gg |
| 17.7 | Calibrazione + validazione | grid-search params, report comparativo v1.2.0 vs v2 | report markdown | 2 gg |

Totale stimato: 11–13 giornate full focus.

## 4. Specifica per sub-fase

### 4.1 Phase 17.1 — Indicatori avanzati

**Output**: nuovo modulo `indicators_advanced.py`. Stessa convenzione di
`indicators.py` (Python puro, niente pandas/ta-lib, ogni serie ritorna
lunghezza == input, posizioni iniziali insufficienti = `None`).

Funzioni richieste:

- `bollinger_bands(closes: list[float], period: int = 20, k: float = 2.0) -> dict`
  ritorna `{'middle': list, 'upper': list, 'lower': list, 'bandwidth': list, 'percent_b': list}`.
  - `middle = SMA(period)`
  - `bandwidth = (upper - lower) / middle * 100`
  - `percent_b = (close - lower) / (upper - lower)`
- `macd(closes, fast: int = 12, slow: int = 26, signal: int = 9) -> dict`
  ritorna `{'macd': list, 'signal': list, 'histogram': list}`.
- `vortex(highs, lows, closes, period: int = 14) -> dict`
  ritorna `{'vi_plus': list, 'vi_minus': list}`.
- `vhf(closes, period: int = 28) -> list[float | None]` Vertical Horizontal
  Filter. Valori vicini a 1 = trend, vicini a 0 = range.
- `parabolic_sar(highs, lows, af_step: float = 0.02, af_max: float = 0.2) -> list[float | None]`.
- `bandwidth_squeeze(bandwidth_series: list, lookback: int = 100, percentile: float = 0.2) -> bool`
  True se bandwidth corrente è nel `percentile` più basso degli ultimi
  `lookback` valori.

**Test**: `tests/test_indicators_advanced.py`. Per ogni funzione, almeno:
- comportamento serie troppo corta → tutto `None`
- valori noti su array hardcoded (golden values calcolati a mano)
- gestione input degenere (range nullo, divisione per zero)

**Note**: nessuna integrazione con `IntradayStrategy` in questa sub-fase.
Solo libreria.

### 4.2 Phase 17.2 — Compressione volatilità (Defendi cap 4)

**Output**: nuovo modulo `volatility_compression.py`.

Funzioni:

- `is_narrow_range_bar(bars: list[dict], n: int = 7) -> bool`
  L'ultima barra ha range < min range delle precedenti `n-1` barre (NR7).
- `is_inside_bar(prev: dict, curr: dict) -> bool`
  `curr.high < prev.high and curr.low > prev.low`.
- `is_boomer(bars: list[dict]) -> bool`
  Ultime 2 barre sono entrambe inside rispetto alla precedente.
- `is_double_inside(bars: list[dict]) -> bool`
  Wide Range Bar a `bars[-3]`, le `bars[-2]` e `bars[-1]` entrambe inside
  della Wide Range Bar.
- `is_doji_range_bar(bar: dict, threshold: float = 0.2) -> bool`
  `|close - open| / (high - low) <= threshold`.
- `detect_volatility_squeeze(bars, atr_series, bb_bandwidth_series) -> dict`
  ritorna `{'squeeze': bool, 'type': 'NR'|'BOOMER'|'DI'|'BB_SQUEEZE'|'NONE', 'strength': float}`.

**Integrazione `IntradayStrategy`**:

Nuovi `setup_type` in `identify_entry_setup`: `SQUEEZE_LONG` / `SQUEEZE_SHORT`.

Trigger:
- compressione rilevata (almeno una tra: NR7 + trend bullish/bearish, Boomer,
  Double Inside, BB BandWidth nel 20° percentile lookback 100)
- direzione coerente con trend primario (`bullish_align` per long,
  `bearish_align` per short)
- entry: `bars[-1].high + 0.1*ATR` (long) o `bars[-1].low - 0.1*ATR` (short)
- SL: `bars[-1].low - 0.2*ATR` (long) o `bars[-1].high + 0.2*ATR` (short)
- TP: stesso meccanismo di calcolo R:R esistente (min `MIN_RISK_REWARD_RATIO`).

Nuova flag config `.env`:
- `ENABLE_VOLATILITY_SQUEEZE_SETUP` (default `true`)
- `BB_SQUEEZE_LOOKBACK` (default `100`)
- `BB_SQUEEZE_PERCENTILE` (default `0.2`)

**Test**: `tests/test_volatility_compression.py`. Casi: NR7 in trend → setup
LONG, Boomer in downtrend → setup SHORT, no squeeze in mercato volatile →
no setup, BandWidth basso ma trend neutral → no setup.

### 4.3 Phase 17.3 — Pullback engine (Defendi cap 5)

**Output**: nuovo modulo `pullback_engine.py`.

Logica:

1. **Detect breakout recente**: scan ultime `BREAKOUT_LOOKBACK_BARS` (default
   20) barre. Se trovata barra con close > resistance precedente (long)
   o close < support precedente (short), salva il livello e l'indice.
2. **Detect pullback in corso**: dopo il breakout, contare barre con close
   che si avvicina al livello rotto (ora ex-resistance = supporto per long,
   ex-support = resistenza per short). Soglia: `tolerance = 0.5 * ATR`.
3. **Detect entry trigger**: durante pullback, cercare:
   - Inside Bar o NR7 sull'ultima barra
   - Volume **in contrazione** (volume ultima barra < avg5 volume)
   - No divergenza contraria su RSI (es. long: no divergenza ribassista)
4. **Entry**: se trigger valido → setup `PULLBACK_LONG`/`PULLBACK_SHORT`.
   - Entry: `last_bar.high + 0.1*ATR` (long) / `last_bar.low - 0.1*ATR` (short)
   - SL: `last_bar.low - 0.1*ATR` (long) / `last_bar.high + 0.1*ATR` (short)
   - TP: target = livello breakout originale + (livello - SL_originale_breakout)
     così R:R tipicamente 2:1 o superiore.

**Integrazione**: nuovi `setup_type` in `identify_entry_setup`:
`PULLBACK_LONG`, `PULLBACK_SHORT`.

Config `.env`:
- `ENABLE_PULLBACK_SETUP` (default `true`)
- `BREAKOUT_LOOKBACK_BARS` (default `20`)
- `PULLBACK_TOLERANCE_ATR_MULTIPLE` (default `0.5`)
- `PULLBACK_MIN_BARS_AFTER_BREAKOUT` (default `2`)
- `PULLBACK_MAX_BARS_AFTER_BREAKOUT` (default `8`)

**Test**: `tests/test_pullback_engine.py`. Casi: breakout + pullback su
ex-R con Inside trigger → PULLBACK_LONG, breakout senza pullback →
nessun setup, pullback troppo profondo (oltre il livello) → no setup,
pullback con volume in espansione → no setup (pullback "non sano").

### 4.4 Phase 17.4 — Multi-timeframe + divergenze attive

**Output**: modifiche a `strategy.py` e `scanner.py`. No nuovo file
(estensione minima).

**Multi-timeframe**:

- In `_analyze_technical`, aggiungere fetch H1: `bars_h1 = self.mt5.get_ohlc(symbol, "H1", 100)`.
- Calcolare `sma20_h1`, `sma50_h1` su closes H1.
- Definire `h1_bias`:
  - `BULLISH` se `last_close_h1 > sma20_h1 > sma50_h1`
  - `BEARISH` se `last_close_h1 < sma20_h1 < sma50_h1`
  - `NEUTRAL` altrimenti
- **Filtro**: setup `READY` su M15 viene downgrade a `FORMING` se direzione
  contraria a `h1_bias`. Setup `READY` mantenuto se `h1_bias=NEUTRAL` o
  allineato.
- `_score_confidence`: sostituire `mtf_score = 0.1` placeholder con:
  - `0.2` se `h1_bias` allineato
  - `0.1` se neutral
  - `0.0` se contrario (caso che però è già stato downgradato)

**Divergenze attive**:

- In `_analyze_technical`, dopo `rsi_series`, calcolare
  `divergence = check_rsi_divergence(bars, rsi_series, lookback=20)`.
- Aggiungere a `indicators_snapshot`.
- Veto: setup `READY` long con `divergence == "BEARISH_DIVERGENCE"` →
  downgrade a `NONE` con reason `"divergenza_ribassista_su_long"`.
- Mirror per short.

Config `.env`:
- `ENABLE_MTF_FILTER` (default `true`)
- `MTF_TIMEFRAME` (default `H1`)
- `ENABLE_DIVERGENCE_VETO` (default `true`)
- `DIVERGENCE_LOOKBACK` (default `20`)

**Test**: estensione `tests/test_strategy.py`. Casi: setup READY long
contrario H1 → FORMING, setup READY long con divergenza ribassista → NONE,
mtf_score corretto in confidence.

### 4.5 Phase 17.5 — Position management attiva

**Output**: nuovo modulo `position_manager.py`. Estensione
`models.py::OpenPositionVerdict.action` con nuovi valori.

Nuovi `action` in `OpenPositionVerdict`:
- `MOVE_TO_BREAKEVEN` (sposta SL a entry quando profit ≥ 1R)
- `TRAIL_STOP` (sposta SL secondo logica chandelier exit)
- `PARTIAL_CLOSE_50` (chiude 50% posizione quando profit ≥ 2R)

Logica in `position_manager.evaluate_active_management`:

```
if profit_r >= 1.0 and not position.sl_at_breakeven:
    return MOVE_TO_BREAKEVEN
if profit_r >= 2.0 and not position.partial_closed:
    return PARTIAL_CLOSE_50
if profit_r >= 2.0 and position.partial_closed:
    new_sl = chandelier_exit(bars, atr, multiplier=3.0)
    return TRAIL_STOP(new_sl)
return HOLD
```

`PositionInfo` esteso con flags persistenti (per non ripetere l'azione):
- `sl_at_breakeven: bool = False`
- `partial_closed: bool = False`

Persistenza flags: salvati nel comment del trade MT5 oppure in
`HeartbeatStore` SQLite (preferito: SQLite, meno hack).

`Mt5Client` nuovi metodi:
- `modify_position(ticket: int, sl: float | None, tp: float | None) -> OrderResult`
- `partial_close(ticket: int, lots: float) -> OrderResult`

Integrazione nel loop scheduler: `evaluate_active_management` chiamata su
ogni posizione aperta prima di `evaluate_open_position` esistente
(che resta per CLOSE_PROTECT / CLOSE_END_OF_DAY).

Config `.env`:
- `ENABLE_ACTIVE_POSITION_MGMT` (default `true`)
- `BREAKEVEN_TRIGGER_R` (default `1.0`)
- `PARTIAL_CLOSE_TRIGGER_R` (default `2.0`)
- `PARTIAL_CLOSE_FRACTION` (default `0.5`)
- `TRAIL_ATR_MULTIPLIER` (default `3.0`)

**Test**: `tests/test_position_manager.py`. Casi: profit 1R → BE move,
profit 2R + non chiusa parzialmente → PARTIAL_CLOSE_50, profit 2.5R + già
chiusa parzialmente → TRAIL_STOP, profit < 1R → HOLD.

### 4.6 Phase 17.6 — Backtest harness

**Output**: nuovo modulo `backtest.py` + script `scripts/run_backtest.py`.

Componenti:

- `BacktestMt5Client`: implementa interfaccia `Mt5Client` ma serve barre
  storiche pre-caricate. Costruttore: `BacktestMt5Client(symbol_to_bars: dict[str, list[dict]])`.
- `BacktestEngine`:
  - input: dataset (es. 6 mesi M15 EURUSD+GBPUSD), config Config
  - itera barra per barra simulando il loop scheduler
  - applica strategia + risk engine + position manager
  - traccia ogni trade in `BacktestTrade(entry_time, exit_time, symbol,
    direction, entry, sl, tp, exit_price, exit_reason, profit_pct, profit_r)`
  - genera report finale con metriche
- Metriche:
  - total trades, winrate, avg win, avg loss, expectancy
  - profit factor (sum wins / sum losses)
  - max drawdown (% e assoluto)
  - Sharpe ratio (annualizzato, assumendo daily returns)
  - max consecutive losses
  - tempo medio in trade

Dataset: scaricare via `Mt5Client.get_ohlc` un range storico (offline,
script separato `scripts/download_historical.py`). Salvare CSV in
`tests/data/backtest/`.

Output report: `backtest_report.json` + `backtest_report.md` con
tabella per simbolo + grafico equity curve (matplotlib opzionale).

**Test**: `tests/test_backtest_harness.py`. Verifica deterministicità
(stesso dataset → stesso report), gestione SL/TP hit intra-bar (assunzione:
SL hit prima di TP se entrambi colpiti nella stessa barra = worst case),
sizing coerente con `risk_engine`.

**Vincolo critico**: questa sub-fase è il **gate** prima della merge in
`main`. Backtest v1.2.0 (replay con vecchio codice) vs v2 (codice nuovo)
sullo stesso dataset.

### 4.7 Phase 17.7 — Calibrazione + validazione

**Output**: report markdown `.orchestration/PHASE_17_VALIDATION.md` +
parametri calibrati in `.env.example`.

Attività:

1. Definire grid-search su parametri chiave:
   - `MIN_TREND_STRENGTH` ∈ {0.55, 0.60, 0.65, 0.70, 0.75}
   - `MIN_BREAKOUT_VOLUME_RATIO` ∈ {1.1, 1.3, 1.5, 1.8}
   - `MIN_RISK_REWARD_RATIO` ∈ {1.5, 2.0, 2.5}
   - `BREAKEVEN_TRIGGER_R` ∈ {0.8, 1.0, 1.2}
   - `BB_SQUEEZE_PERCENTILE` ∈ {0.15, 0.20, 0.25}
2. Esecuzione backtest per ogni combo (out-of-sample 80/20 split).
3. Selezione combo Pareto-ottimale su `expectancy + Sharpe - max_dd`.
4. Confronto v1.2.0 (parametri attuali) vs v2 calibrato:
   - tabella metriche affiancate
   - equity curve overlay
   - distribuzione R-multiple
5. **Decisione merge**: solo se v2 batte v1.2.0 su almeno 2 metriche tra
   {expectancy, profit factor, Sharpe, max DD}, procedi al merge.
6. Aggiornare `_score_confidence` con pesi calibrati su correlazioni
   feature → R-multiple del backtest (regressione lineare semplice).

## 5. Modifiche fuori scope (esplicite)

Da NON toccare in fase 17:

- `risk_engine.py`: il gate di rischio resta unico e invariato.
- `mcp_server.py`: contract MCP stabile.
- `scheduler.py`: loop H24, heartbeat, kill switch.
- `news_aggregator.py`/`sentiment.py`: separato in fase 18.
- Volume Profile + VWAP (Defendi cap 7): rinviato a fase 18 (richiede dati
  tick-by-tick, non solo OHLC).
- Pattern reversal avanzati (123 Low/High, Key Reversal, Morning/Evening
  Star) Defendi cap 3: rinviato a fase 19 se le sub-fasi 17.1–17.7
  saturano il tempo.

## 6. Aggiornamenti documentazione

Per ogni sub-fase:

- `STATE.md`: aggiornare dopo ogni micro-step (convenzione fase 16).
- `PHASES.md`: read-only, viene aggiornato solo dall'orchestrator.
- `.env.example`: aggiungere tutte le nuove variabili.
- `README.md`: aggiungere sezione "Strategy v2 (Defendi-based)" con
  panoramica setup multi-tipo.
- `.orchestration/VALIDATION_PHASE_17.md`: checklist validazione utente
  (post-backtest, prima del merge).

## 7. Convenzioni invariate

- Python 3.12, type hints, Mt5Client mock per evitare connessione reale
  nei test.
- `EXECUTION_MODE=shadow` di default, `DRY_RUN=true` durante test live.
- Lingua commenti/log/rationale: italiano.
- Commit secondo `COMMIT_CONVENTIONS.md`. Push su `origin
  feature/strategy-v2-defendi` dopo ogni sub-fase validata.
- Co-Authored-By: NON aggiungere (memoria utente).

## 8. Definition of Done della fase 17

- [ ] Tutte le sub-fasi 17.1–17.7 completate.
- [ ] Suite test esistenti (173) passa al 100%.
- [ ] Nuovi test (>50 attesi) passano al 100%.
- [ ] Backtest 6m EURUSD+GBPUSD: v2 batte v1.2.0 su ≥ 2 metriche tra
      {expectancy, profit factor, Sharpe, max DD}.
- [ ] `STATE.md` segna fase 17 code-complete + validation-complete.
- [ ] `.orchestration/VALIDATION_PHASE_17.md` checklist firmata utente.
- [ ] PR `feature/strategy-v2-defendi` → `main` aperta e mergata.
- [ ] Tag `v2.0.0` su `main` post-merge.
