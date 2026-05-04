# Strategia Python Pure — Come funziona davvero

Questo documento spiega in modo **umano e completo** cosa fa il daemon
intraday Python (fase 14+16). Letta per intero, ti permette di decidere se
modificare regole o parametri.

> **Lingua di riferimento**: italiano. **Codice citato**: `strategy.py`,
> `scanner.py`, `scheduler.py`, `indicators.py`.

---

## 1. Architettura a due cervelli (perché Python ≠ Agente)

Il sistema ha **due engine decisionali totalmente indipendenti**:

| Engine | Chi decide | Quando gira | Logica |
|---|---|---|---|
| **Daemon Python** (questo doc) | regole boolean fisse | scheduler H24 ogni N minuti | deterministica, replicabile |
| **MCP / Claude Desktop** | LLM Claude (sonnet) | tu chiedi via chat | giudizio qualitativo |

Il daemon è il **safety net** progettato per essere prevedibile.
L'agente è la fonte di **opportunità qualitative** (legge contesto, news,
narrativa). Non sono né allineati né lo saranno: vivono in parallelo, scrivono
sullo stesso log e database, ma non si parlano.

**Conseguenza pratica**: se Claude propone GBPJPY ma il daemon dice NO_TRADE,
non è bug. È il design. Se vuoi l'agente automatico, devi farlo girare con
un orchestratore separato (non incluso in fase 16).

---

## 2. Il ciclo di vita di un'iterazione

Ogni `INTRADAY_SCAN_INTERVAL_MINUTES` minuti il daemon esegue un **ciclo**.
Ecco cosa succede dentro un ciclo, in ordine (da `scheduler.py:530-660`):

### 2.1 Pre-flight checks (interrompono il ciclo se falliscono)
1. **Weekend?** sì → outcome `WEEKEND`, fine.
2. **Lettura account state** da MT5 (`balance`, `equity`, posizioni aperte,
   P&L realizzato del giorno).
3. **Gestione posizioni aperte** → vedi sez. 3.
4. **PAUSE_TRADING attivo?** sì → outcome `PAUSED`, fine.
5. **Dentro la finestra operativa?** (`INTRADAY_START_HOUR..END_HOUR` in
   giorno feriale `OPERATING_WEEKDAYS`) — no → outcome `OUT_OF_WINDOW`, fine.
6. **Finestra news bloccante attiva?** — sì → outcome `NEWS_BLOCKED`, fine.

### 2.2 Scansione dell'universo
1. **Light scan** (`scanner.scan_universe`): per ogni simbolo in
   `INTRADAY_SYMBOLS`, calcola un punteggio rapido basato su SMA20/EMA50, RSI,
   ATR, spread. Scarta se indicatori non pronti o se mancano i bar.
2. **Top-N selezione**: ordina per `candidate_score` decrescente, prende i
   primi `INTRADAY_SCAN_TOP_N`.

### 2.3 Deep analysis sui top-N
Per ogni simbolo selezionato chiama `IntradayStrategy.analyze_symbol`. Vedi
sez. 4 per il dettaglio. L'output è un `TechnicalSetup` con `setup_type` in
`{READY, FORMING, NONE}`.

### 2.4 Decisione finale del ciclo
- **Almeno un READY**: prende quello con `confidence` più alta.
  - Se `confidence < MIN_CONFIDENCE_TO_PROPOSE` → outcome `NO_TRADE` con
    note `best_confidence_below_threshold`.
  - Costruisce `TradeProposal` (entry/SL/TP via ATR e S/R).
  - **Add-on detection**: se esiste già una posizione stessa direzione
    sullo stesso simbolo, marca `comment=python_strategy_addon`.
  - **Drawdown gate**: stima loss potenziale del proposal + posizioni
    esistenti. Se supera `MAX_DAILY_DRAWDOWN_PERCENT` → outcome
    `DRAWDOWN_BLOCK`.
  - Altrimenti → invia ordine via `execution.run_once` →
    `Mt5Client.send_order` → outcome `OK`.
- **Nessun READY ma c'è un FORMING e `FOLLOWUP_ENABLED=true`**: prende il
  forming con confidence più alta, registra un follow-up programmato →
  outcome `OK note=wait_followup_*` (nota: il follow-up non rilancia il
  ciclo, è solo log informativo nel daemon H24).
- **Nessun READY né FORMING** → outcome `NO_TRADE
  note=no_ready_or_forming`.

### 2.5 Heartbeat
A fine ciclo scrive in SQLite (`logs/trades.db`):
- riga in `heartbeat`: timestamp inizio/fine, durata, outcome, note, errore
- riga aggiornata in `scheduler_state`: ultimo outcome, contatore errori
  consecutivi, last_duration_ms

Questo permette monitoring esterno e recovery dopo crash.

---

## 3. Gestione delle posizioni aperte (sez. critica)

**Sì, le posizioni aperte vengono valutate ad OGNI ciclo**, prima della
scansione nuova. Logica in `strategy.evaluate_open_position` (riga 422):

Per ogni posizione **il cui simbolo è in `INTRADAY_SYMBOLS`** (le altre
vengono ignorate dal daemon):

### 3.1 Check 1 — Fine finestra operativa
Se TUTTE queste sono vere:
- `CLOSE_BEFORE_END_OF_WINDOW=true`
- giorno feriale
- ora corrente FUORI da `INTRADAY_START_HOUR..END_HOUR`
- simbolo in `INTRADAY_SYMBOLS`

→ verdetto `CLOSE_END_OF_DAY` → daemon chiude la posizione.
**Scopo**: evitare overnight su strategia intraday.

### 3.2 Check 2 — Contesto tecnico negativo + profitto sufficiente
Se la finestra è ok, il daemon ri-analizza il simbolo (`_analyze_technical`)
e calcola se il **contesto** è diventato negativo per la posizione esistente:

`_is_context_negative_for_position` (strategy.py:535):
- Se nuovo setup è READY in **direzione opposta** alla posizione → contesto
  NEGATIVO (mercato si è invertito).
- Altrimenti guarda allineamento MA: posizione BUY è negativa se
  `last_close < SMA20 < SMA50` (price sotto entrambe le MA, trend bearish).
  Posizione SELL è negativa al contrario.

Calcola anche `profit_r` = `posizione.profit / risk_iniziale_R`.

Verdetto:
- **CLOSE_PROTECT** se `is_negative=true` E `profit_r >=
  MIN_PROTECT_PROFIT_R_MULTIPLIER`. Logica: chiudi solo se hai già
  guadagnato abbastanza, non scappare al primo colpo di trend rumoroso.
- **HOLD** altrimenti.

### 3.3 Cosa NON fa il daemon sulle posizioni
- **Non muove SL/TP** (no trailing stop automatico).
- **Non chiude in profitto** target-based (TP statico settato all'apertura).
- **Non riapre** una posizione chiusa (è scelta del prossimo ciclo
  scansione).
- **Non gestisce posizioni su simboli NON in `INTRADAY_SYMBOLS`**: se hai
  aperto manualmente o via MCP qualcosa fuori universe, il daemon le
  ignora.

---

## 4. Come nasce un setup READY

Questo è il **cuore strategico**. Pipeline in `_analyze_technical` →
`identify_entry_setup`.

### 4.1 Pre-condizioni base (se falliscono → setup NONE)
1. Almeno 50 barre disponibili (lookback ATR/RSI/SMA50).
2. Indicatori calcolabili (no NaN su SMA20, SMA50, RSI14, ATR14).
3. **ATR in pips dentro range**: `MIN_ATR_PIPS <= atr_pips <= MAX_ATR_PIPS`.
   Sotto = mercato morto. Sopra = whipsaw.

### 4.2 Calcolo elementi tecnici
- **`trend_strength`** (0-1): combinazione di
  - separazione SMA20/SMA50 normalizzata (50%)
  - coerenza direzionale: % di candele recenti che seguono la direzione
    SMA (50%)
- **Support/Resistance**: pivot swing high/low su `SR_LOOKBACK_BARS` (con
  finestra ±2 barre). Resistance = max swing high. Support = min swing low.
- **`breakout`** (`CLEAN`/`WEAK`/`NONE`):
  - CLEAN se ultima close ha **rotto attivamente** S o R E volume
    candela >= avg × `MIN_BREAKOUT_VOLUME_RATIO`.
  - WEAK se rottura ma volume basso.
  - NONE se nessuna rottura.
- **Patterns** candle (engulfing, pinbar, etc): se
  `ENABLE_CANDLESTICK_PATTERNS=true`, scansiona ultime
  `PATTERN_CONFIRMATION_BARS` candele.

### 4.3 Regole di entry (`identify_entry_setup`)

#### Setup READY direzione BUY (tutte AND):
1. `bullish_align`: `close > SMA20 > SMA50`
2. `trend_strength > MIN_TREND_STRENGTH`
3. `MIN_RSI_OVERSOLD < RSI < MAX_RSI_OVERBOUGHT`
4. `breakout == "CLEAN"` **OPPURE** `REQUIRE_BREAKOUT_FOR_READY=false`
5. Pattern bullish presente (skippato se `ENABLE_CANDLESTICK_PATTERNS=false`)
6. `resistance is None` **OPPURE** `close > resistance - SR_TOLERANCE_PIPS`

Se tutte vere → READY direction=BUY, mode=`breakout` o
`trend_continuation`.

#### Setup READY direzione SELL: speculare (bearish_align, close < support
+ tol).

#### Setup FORMING (consolation prize):
Se non READY, ma:
- `trend_strength > 0.6` (hardcoded, non configurabile da .env!)
- prezzo **vicino** a S o R (entro `SR_TOLERANCE_PIPS`)
- MAs allineate

→ FORMING. Genera follow-up programmato (no trade immediato).

#### NONE:
- RSI estremo (`>= MAX_RSI_OVERBOUGHT` o `<= MIN_RSI_OVERSOLD`).
- Trend o allineamento MA insufficiente.

### 4.4 Filtri post-READY
- **R/R minimo**: calcolati entry/SL/TP, se `tp_dist/sl_dist <
  MIN_RISK_REWARD_RATIO` → degrada a NONE con motivo `rr_below_min`.
- **Confidence score** (`_score_confidence`): pondera trend_strength,
  presenza pattern, qualità breakout, R/R. Output `[0..1]`.
- **Sentiment** (se `ENABLE_NEWS_SENTIMENT=true`): può **boostare**,
  **ridurre** confidence, **delayare** o **skippare** il setup secondo
  `SENTIMENT_CONFLICT_ACTION`.
- **MIN_CONFIDENCE_TO_PROPOSE** (filtro a livello scanner): se
  `confidence < soglia` → outcome `NO_TRADE
  best_confidence_below_threshold`.

---

## 5. Calcolo SL/TP

`_compute_levels` (strategy.py:577):

**BUY**:
- `entry = last_close`
- `atr_buffer = ATR(14)`
- Se support trovato e support < entry:
  `SL = min(support - 0.5*ATR, entry - ATR)` (sotto support con buffer).
- Altrimenti: `SL = entry - ATR`.
- `risk = entry - SL`
- `TP = entry + max(MIN_RISK_REWARD_RATIO, 1.5) * risk`

**SELL**: speculare con resistance.

Note:
- L'entry è **al prezzo corrente di chiusura ultima candela M15**, non con
  pending order. Quindi può differire dal prezzo MT5 al momento dell'invio
  ordine (slippage minimo intraday FX).
- TP è statico, non si muove dopo apertura.

---

## 6. Risk engine — il vero gate finale

Anche se il setup è READY e MIN_CONFIDENCE è passato, il proposal passa
per `risk_engine.evaluate_trade` che applica:

1. **Profilo broker** (`RISK_MODE` in `[CONSERVATIVE, MODERATE,
   AGGRESSIVE]`):
   - max_lots per trade
   - max_drawdown_pct
2. **Sizing**: calcola lot in base a `RISK_PER_TRADE_PERCENT` (o AMOUNT)
   e `risk_amount = balance * percent / 100`. Lot = `risk_amount / (sl_pips
   * pip_value)`. Cappato a `MAX_LOTS_PER_TRADE` (se >0) o max profilo.
3. **SL bounds**: se SL distance < `MIN_SL_PIPS` o > `MAX_SL_PIPS` →
   rejection.
4. **Drawdown rolling 24h**: se loss cumulato ultimi 24h >
   `ROLLING_DRAWDOWN_MAX_PERCENT` → rejection.

Output: `RiskDecision(approved=bool, lots=float, reason=str)`. Solo se
`approved=true` l'ordine va a `mt5.send_order`.

---

## 7. Outcome possibili di un ciclo (visibili in log e heartbeat)

| Outcome | Quando | Note |
|---|---|---|
| `OK` | Ordine inviato con successo, OPPURE follow-up registrato | Vedi `note` per dettaglio |
| `NO_TRADE` | Nessun setup READY/FORMING o sotto soglia | `note` indica filtro che ha bocciato |
| `OUT_OF_WINDOW` | Fuori `INTRADAY_START_HOUR..END_HOUR` o weekday | |
| `WEEKEND` | Sabato o domenica | |
| `PAUSED` | `PAUSE_TRADING=true` | |
| `NEWS_BLOCKED` | Finestra news critica attiva | |
| `DRAWDOWN_BLOCK` | Proposal supererebbe `MAX_DAILY_DRAWDOWN_PERCENT` | |
| `DRY_RUN` | Setup READY ma `DRY_RUN=true` (solo log, no ordine) | |
| `ERROR` | Eccezione durante ciclo | `error_type`/`error_message` popolati |

---

## 8. Cosa devi modificare per ottenere comportamenti diversi

### Voglio più TRADE (mercato calmo, daemon troppo silente)
1. **`MIN_TREND_STRENGTH`**: abbassa a 0.30-0.40.
2. **`REQUIRE_BREAKOUT_FOR_READY=false`**: ammette trend-continuation.
3. **`SR_TOLERANCE_PIPS`**: alza a 15-20 (READY pre-emptive).
4. **`ENABLE_CANDLESTICK_PATTERNS=false`**: rimuove conferma pattern.
5. **`MIN_CONFIDENCE_TO_PROPOSE`**: 0.30-0.40.
6. **`MIN_BREAKOUT_VOLUME_RATIO=1.0`**: filtra solo volumi sotto media.
7. **`INTRADAY_SCAN_TOP_N`**: pari a `len(INTRADAY_SYMBOLS)` per
   deep-analyze tutti.

### Voglio meno TRADE (troppo rumore, fakeout)
Tutti gli opposti del punto sopra. In più:
- **`PATTERN_CONFIRMATION_BARS=2`**: richiede pattern su 2 candele.
- **`MIN_RISK_REWARD_RATIO`**: alza a 2.0.
- **`SR_LOOKBACK_BARS`**: alza a 150-200 (S/R più "duri").

### Voglio chiusure più aggressive su posizioni aperte
- **`MIN_PROTECT_PROFIT_R_MULTIPLIER`**: abbassa a 0.5 (chiude prima).
- **`CLOSE_BEFORE_END_OF_WINDOW=true`**: niente overnight.

### Voglio tenere posizioni overnight
- **`CLOSE_BEFORE_END_OF_WINDOW=false`**.
  ATTENZIONE: gap weekend / news notturne.

### Voglio cambiare il modo di calcolare SL/TP
Non c'è parametro env. Devi modificare `strategy._compute_levels` (riga
577). Esempio modifiche tipiche:
- ATR buffer × N invece di × 1
- TP a multiple swing successive invece di R/R fisso
- SL al minimo ultime K candele invece che `support - 0.5*ATR`

### Voglio aggiungere un indicatore (MACD, Bollinger, etc)
1. Implementa in `indicators.py`.
2. Calcola in `strategy._analyze_technical` e aggiungi a
   `indicators_snapshot`.
3. Usa in `identify_entry_setup` come AND/OR aggiuntivo.
4. Aggiungi test in `tests/test_strategy.py`.

### Voglio multi-timeframe (M15 entry + H1 trend filter)
Modifica strutturale in `_analyze_technical`:
- Carica anche bars H1.
- Calcola trend_strength su H1.
- Aggiungi condizione `h1_trend_strength > 0.5` in `identify_entry_setup`.

---

## 9. Cosa il daemon NON fa (limiti del design)

- **No machine learning**, nessun modello allenato. Solo regole.
- **No backtesting integrato**. Devi farlo offline replicando le funzioni.
- **No trailing stop**. SL fisso post-entry.
- **No partial close** automatico (close 50% al primo TP, etc).
- **No hedging**: se hai BUY e SELL stesso simbolo, daemon non gestisce.
- **No correlation filter**: può aprire EURUSD BUY e GBPUSD BUY
  contemporaneamente anche se altamente correlati.
- **No spread guard runtime**: spread valutato solo in light_scan, non
  ricontrollato all'invio ordine.
- **No re-entry logic**: se chiude in stop loss, può riaprire stessa
  direzione al prossimo ciclo (rischio overtrade in whipsaw).

---

## 10. Come capire dal log cosa è successo

Esempio riga ciclo:
```
2026-05-04 14:30:00 [INFO] Ciclo done outcome=OK duration_ms=234
note=selected=GBPUSD conf=0.62 addon=False max_dd=1.20%
```
Significa: ciclo terminato OK, simbolo scelto GBPUSD, confidence 0.62, non
è add-on, drawdown stimato 1.20% del balance giornaliero.

Esempio NO_TRADE motivato:
```
note=no_ready_or_forming
note=best_confidence_below_threshold=0.45
note=drawdown_violation symbol=USDJPY max_potential=3.21%
```

Esempio gestione posizione:
```
[INFO] Chiusura OK ticket=12345 symbol=EURUSD action=CLOSE_PROTECT
reason=contesto_tecnico_negativo: setup=READY profitto=1.20R >= 1.00R
```

Per debug profondo:
```env
LOG_LEVEL=DEBUG
```
mostra anche dettaglio per-simbolo (RSI, ATR, trend_strength) ad ogni
ciclo.

---

## 11. Decision tree per capire se devi modificare

```
Sei soddisfatto della frequenza TRADE?
├─ Sì, troppi → sez. 8 "Voglio meno TRADE"
├─ Sì, ok → non toccare
└─ No, troppi pochi → sez. 8 "Voglio più TRADE"

Le posizioni aperte vengono chiuse come vuoi?
├─ Chiude troppo presto → alza MIN_PROTECT_PROFIT_R_MULTIPLIER
├─ Chiude troppo tardi → abbassa MIN_PROTECT_PROFIT_R_MULTIPLIER
└─ Non chiude mai → controlla CLOSE_BEFORE_END_OF_WINDOW e ora finestra

Il P&L medio per trade ti soddisfa?
├─ Win troppo piccoli → alza MIN_RISK_REWARD_RATIO
├─ Loss troppo grandi → abbassa MAX_SL_PIPS o RISK_PER_TRADE_PERCENT
└─ Hit-rate basso → alza MIN_CONFIDENCE_TO_PROPOSE / MIN_TREND_STRENGTH

Ti serve qualcosa che il daemon NON fa? (vedi sez. 9)
└─ Devi modificare il codice, non basta .env
```

---

## 12. File chiave da leggere se vuoi modificare

| File | Cosa contiene |
|---|---|
| `config.py` | Tutti i parametri da .env |
| `strategy.py` | Logica setup READY/FORMING + gestione posizioni |
| `scanner.py` | Light scan + deep analyze + decisione finale ciclo |
| `scheduler.py` | Loop H24, gestione posizioni, heartbeat, segnali |
| `indicators.py` | SMA/EMA/RSI/ATR/trend_strength/SR/breakout/patterns |
| `risk_engine.py` | Gate finale: sizing, SL bounds, drawdown rolling |
| `execution.py` | Ponte risk_engine → mt5.send_order |
| `mt5_client.py` | Wrapper MT5 (filling mode resolver, ohlc, send/close) |

Modifica unitaria → aggiorna o aggiungi test in `tests/test_*.py` →
esegui suite (`.\.venv\Scripts\python.exe -m pytest tests/ -q`) →
verifica live in `EXECUTION_MODE=shadow` per almeno 1 sessione.
