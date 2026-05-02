# Phase 16 — H24 Strategy Update

Documento di specifica e implementazione della fase 16. Aggiorna la strategia
intraday Python pura (fasi 14–15) per funzionamento quasi H24 5/7, gestione
posizioni aperte ciclo per ciclo, chiusura protettiva in profitto, vincolo di
drawdown potenziale e scheduler interno con heart-beat persistente.

## 1. Obiettivi e vincoli

- Operatività **24/5**: script sempre attivo da apertura FX domenica sera a
  chiusura venerdì sera. Nel weekend la logica trading è spenta.
- Logica intraday: **mai posizioni overnight**. A fine finestra operativa
  giornaliera (`INTRADAY_END_HOUR`) le posizioni residue sulla strategia
  vengono chiuse.
- Cicli frequenti (default 15 min, configurabile), con primo ciclo 5 min
  dopo l'avvio.
- Scheduler **interno Python** (loop infinito + `time.sleep`), nessun cron /
  Task Scheduler / APScheduler nel path principale. La classe APScheduler
  preesistente (`Orchestrator`/`build_scheduler`) resta in repo per backward
  compat dei test, ma **non** è usata dal `main.py` H24.
- Risk engine resta unico cancello deterministico per l'esecuzione
  (`evaluate_trade`). Lo scheduler aggiunge un controllo aggiuntivo di
  drawdown potenziale a livello di portafoglio (somma SL).
- `EXECUTION_MODE=shadow` resta default. `DRY_RUN=true` aggiunge un layer di
  protezione extra: nessun `send_order` né `close_position` reale.
- News/calendar: hook `StrategyEnvironment.is_news_window(now)` predisposto;
  implementazione reale (RSS/calendar) in fase futura.

## 2. Modifiche per file

### 2.1 `config.py` + `.env.example`

Nuove variabili `.env`:

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `INTRADAY_SCAN_INTERVAL_MINUTES` | 15 | Intervallo tra cicli del loop H24 |
| `INTRADAY_FIRST_CYCLE_DELAY_MINUTES` | 5 | Ritardo del primo ciclo dopo avvio |
| `PAUSE_TRADING` | false | Blocca apertura nuovi trade (heart-beat resta vivo) |
| `DRY_RUN` | false | Disattiva tutti gli ordini reali (open/close) |
| `MIN_PROTECT_PROFIT_R_MULTIPLIER` | 1.0 | Soglia profitto in multipli di R per chiusura protettiva |
| `ROLLING_DRAWDOWN_WINDOW_HOURS` | 24 | Finestra rolling per controllo drawdown aggiuntivo |
| `ROLLING_DRAWDOWN_MAX_PERCENT` | 3.0 | Soglia rolling oltre la quale lo scheduler entra in NO_TRADE |
| `LOG_ROTATION` | weekly | Strategia rotazione log: daily \| weekly \| size |
| `WEEKLY_LOG_BACKUP_COUNT` | 8 | Numero file log archiviati con rotazione weekly |
| `CLOSE_BEFORE_END_OF_WINDOW` | true | Chiude posizioni intraday a fine finestra giornaliera (no overnight) |

Helper `_get_int` reso più robusto: ignora suffissi non numerici (`5d`, `15m`)
e fa fallback al default se il valore è non parsabile.

### 2.2 `models.py`

- `PositionInfo` ora include `ticket: int` (richiesto da `close_position`).
- `StrategyOutcome` esteso con campi opzionali:
  - `max_potential_drawdown_percent: float | None`
  - `drawdown_violation: bool`
  - `is_addon: bool`
  - `news_blocked: bool`
  - `paused: bool`
- Nuovo `OpenPositionVerdict(symbol, ticket, action, reason, profit_r_multiple)`
  con `action ∈ {HOLD, CLOSE_PROTECT, CLOSE_END_OF_DAY}`.
- Nuovo `SchedulerCycleRecord` per tracciare l'esito di ciascun ciclo
  (`OK | NO_TRADE | ERROR | PAUSED | NEWS_BLOCKED | OUT_OF_WINDOW | WEEKEND |
  DRAWDOWN_BLOCK | DRY_RUN`).

### 2.3 `mt5_client.py`

- Aggiunto metodo dedicato `close_position(position_id: int) -> OrderResult`
  che usa `mt5.order_send` con `action=TRADE_ACTION_DEAL`, campo `position`
  valorizzato, `type` opposto alla direzione originale e `volume = pos.volume`.
  **Non** apre una posizione opposta: chiude la posizione esistente.
- `get_account_state()` popola `PositionInfo.ticket` da `p.ticket` reale di MT5.

### 2.4 `strategy.py`

Nuovi componenti:

- **`StrategyEnvironment`**: incapsula i gate di contesto.
  - `is_intraday_window(now)`: True se `INTRADAY_START_HOUR ≤ hour <
    INTRADAY_END_HOUR`.
  - `is_weekday(now)` / `is_weekend(now)`: usa `OPERATING_WEEKDAYS`.
  - `is_news_window(now)`: hook. Default False; accetta in injection
    `news_window_callable`.
- **`evaluate_open_position(position, account_state, now)`**: valuta lo stato
  di una posizione aperta:
  - se fuori finestra intraday e `CLOSE_BEFORE_END_OF_WINDOW=true` →
    `CLOSE_END_OF_DAY`.
  - altrimenti analizza il contesto tecnico; se è negativo (setup READY in
    direzione opposta o MAs allineate contrarie) e il profitto è
    `≥ MIN_PROTECT_PROFIT_R_MULTIPLIER * R` (R = distanza entry→SL espressa
    in valuta conto) → `CLOSE_PROTECT`.
  - altrimenti `HOLD`.
- **`compute_existing_potential_loss_amount(account_state)`**: somma la
  perdita potenziale di tutte le posizioni aperte assumendo SL hit; sottrae
  l'eventuale profitto già maturato (worst case = R - profitto già fatto).
- **`would_proposal_exceed_drawdown(proposal, account_state)`**: ritorna
  `(violazione, percent)` dove percent =
  (perdita_existing + perdita_proposal) / starting_balance_of_day * 100.
  Soglia: `MAX_DAILY_DRAWDOWN_PERCENT`.
- **`is_addon_for(proposal, account_state)`**: True se esiste già una
  posizione su stesso simbolo + stessa direzione.

### 2.5 `scanner.py`

`deep_analyze_top_candidates` ha due parametri opzionali nuovi:
`paused: bool` e `news_blocked: bool`. Se uno dei due è True, ritorna
immediatamente `NO_TRADE` con il flag corrispondente popolato (`paused=True`
o `news_blocked=True`).

Quando viene selezionato il miglior setup READY:

1. La strategia costruisce la `TradeProposal`.
2. `is_addon_for` decide il flag `is_addon`. Se True, comment diventa
   `"python_strategy_addon"` e rationale è prefissata con `"ADD-ON: "`.
3. `would_proposal_exceed_drawdown` calcola la percentuale di drawdown
   potenziale. Se > `MAX_DAILY_DRAWDOWN_PERCENT` → `NO_TRADE` con
   `drawdown_violation=True` e `max_potential_drawdown_percent` popolato.
4. Altrimenti `TRADE` con i campi sopra.

### 2.6 `scheduler.py`

Aggiunte due classi principali:

**`HeartbeatStore`** — persistenza SQLite (stesso file `trades.db`):

- Tabella `heartbeat`: storico ciclo per ciclo (started_at, ended_at,
  duration_ms, outcome, error_type, error_message, note).
- Tabella `scheduler_state`: riga singleton con ultimo stato + contatori
  consecutivi (`consecutive_no_trade`, `consecutive_errors`).
- API: `begin_cycle(started_at) -> hb_id`, `end_cycle(hb_id, started_at,
  ended_at, outcome, …)`, `get_state()`, `last_heartbeats(limit)`.

**`IntradayLoopScheduler`** — loop H24 interno. Ordine ciclo:

1. `begin_cycle` (heart-beat START).
2. Check **weekend**: se sabato/domenica → outcome `WEEKEND`, sleep al
   prossimo slot.
3. `mt5.get_account_state()` → cattura saldi e posizioni aperte. In caso di
   eccezione, outcome `ERROR` e contatore `consecutive_errors++`.
4. **Gestione posizioni aperte**: per ogni posizione su `INTRADAY_SYMBOLS`
   → `strategy.evaluate_open_position(...)`. Se verdict ≠ HOLD →
   `mt5.close_position(ticket)` (saltato in DRY_RUN).
5. Check **PAUSE_TRADING**: se True → outcome `PAUSED`, sleep.
6. Check **finestra intraday**: se `now.hour` fuori
   `[INTRADAY_START_HOUR, INTRADAY_END_HOUR)` → outcome `OUT_OF_WINDOW`,
   sleep.
7. Check **news window**: `environment.is_news_window(now)`. Se True →
   outcome `NEWS_BLOCKED`, sleep.
8. Refresh `account_state` dopo le chiusure.
9. `scanner.scan_universe(INTRADAY_SYMBOLS)` →
   `scanner.deep_analyze_top_candidates(...)`.
10. Se `outcome_obj.outcome_type == TRADE`:
    - se `DRY_RUN=true` → outcome `DRY_RUN`.
    - altrimenti `execution.run_once(...)` (rispetta EXECUTION_MODE).
    - In caso di eccezione: outcome `ERROR`, no retry nello stesso slot.
11. `WAIT_FOLLOW_UP` nel loop H24 è ignorato (il loop ricontrolla il
    simbolo allo slot successivo) e viene contato come `OK` con nota.
12. `end_cycle` (heart-beat END con outcome finale, durata, note,
    error_type/message).
13. Sleep fino al prossimo slot. In caso di overrun (ciclo > intervallo),
    salta gli slot persi senza creare cicli sovrapposti.

### 2.7 `main.py`

Sostituisce `BlockingScheduler` (APScheduler) con `IntradayLoopScheduler`.
SIGINT/SIGTERM → `loop.stop()` → uscita pulita. `mt5.shutdown()` in `finally`.

### 2.8 `mcp_server.py`

Aggiunto tool MCP `close_position{position_id: int}` che chiama
`Mt5Client.close_position`. In DRY_RUN ritorna successo simulato senza
eseguire l'ordine. Nessun nuovo log su stdout (compatibilità stdio MCP).

## 3. Test

`tests/test_phase16.py` (31 test) copre:

- `StrategyEnvironment`: finestra intraday, weekend, news_window default e
  con callable iniettato.
- Drawdown helper: `estimate_position_risk_amount`,
  `would_proposal_exceed_drawdown` (over/under threshold).
- `evaluate_open_position`: HOLD (allineato), CLOSE_PROTECT (negativo +
  profitto sufficiente), HOLD (negativo ma profitto basso),
  CLOSE_END_OF_DAY (fuori finestra).
- Scanner: rispetto di `paused`/`news_blocked`, marcatura `is_addon`,
  blocco per `drawdown_violation`.
- `HeartbeatStore`: begin/end cycle, contatori consecutivi, ordine
  decrescente in `last_heartbeats`.
- `IntradayLoopScheduler.run_one_cycle`: WEEKEND, PAUSED, OUT_OF_WINDOW,
  NEWS_BLOCKED, TRADE → run_once, DRY_RUN, gestione posizioni aperte
  (CLOSE_PROTECT real + DRY_RUN), eccezione `get_account_state`.
- `Mt5Client.close_position`: usa campo `position`, type opposto, price=bid,
  volume corretto; gestisce posizione non trovata.

Tutti gli altri test legacy restano verdi: suite totale **173/173 passed**.

## 4. Validazione weekend / dry-run

A mercati chiusi è possibile validare la pipeline senza lanciare il daemon
completo:

```powershell
$env:DRY_RUN = 'true'
.\.venv\Scripts\python.exe scripts\dry_run_cycle.py
```

Output atteso:

- Log `DRY-RUN scheduler H24 (fase 16)` su `logs/agent.log`.
- Se MT5 non disponibile (weekend o credenziali mancanti): warning e
  `exit 2`. Non è un fail: significa "no terminal connesso".
- Se MT5 disponibile: viene eseguito **un solo ciclo**, nessun ordine reale
  inviato, heart-beat persistito su `logs/trades.db` (tabelle
  `heartbeat` + `scheduler_state`).

Per ispezionare lo stato heart-beat:

```powershell
.\.venv\Scripts\python.exe -c "from config import Config; from scheduler import HeartbeatStore, heartbeat_db_path; s=HeartbeatStore(heartbeat_db_path(Config())); import json; print(json.dumps(s.get_state(), indent=2)); print(json.dumps(s.last_heartbeats(5), indent=2, default=str))"
```

## 5. Avvio in produzione

```powershell
$env:DRY_RUN = 'false'
$env:PAUSE_TRADING = 'false'
.\.venv\Scripts\python.exe main.py
```

`Ctrl+C` → shutdown pulito (signal handler chiama `loop.stop()` →
`mt5.shutdown()`).

## 6. Note operative

- Il flag `EXECUTION_MODE=shadow` resta in vigore: in shadow nessun ordine
  viene inviato a MT5 anche con `DRY_RUN=false`. `DRY_RUN=true` blocca
  qualsiasi ordine indipendentemente dal mode (utile per smoke test
  pre-paper).
- Il limite di drawdown potenziale (`MAX_DAILY_DRAWDOWN_PERCENT`) è
  applicato **prima** dell'invio al risk_engine; un trade rifiutato qui non
  arriva mai a `evaluate_trade`. Lo scheduler espone il pct calcolato in
  `StrategyOutcome.max_potential_drawdown_percent` e nel log heart-beat
  con outcome `DRAWDOWN_BLOCK`.
- Add-on/scale-in: il risk_engine non ha un cap esplicito sul numero di
  posizioni per simbolo. La protezione è data solo dal vincolo di drawdown
  potenziale.
- `is_news_window` è un hook: per attivare blackout su un calendar/RSS
  esterno passare un callable a `StrategyEnvironment(news_window_callable=…)`
  in `main.py`.
