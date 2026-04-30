# trading-agent

Agente di trading locale per MetaTrader5 (FP Markets demo) con risk engine deterministico, market scanner multi-symbol, integrazione Claude API (tool use) e server MCP per Claude Desktop. Funziona in modalità daemon continua, pianificando cicli di analisi su slot fissi e gestendo follow-up one-shot.

---

## 1. Introduzione

`trading-agent` orchestra un ciclo continuo `scan → proposta → validazione → (eventuale) ordine` mantenendo un audit trail completo su SQLite e file di log rotante.

Architettura a blocchi:

```
              ┌─────────────────────────────────────────┐
              │  Scheduler (APScheduler BlockingScheduler│
              │  cron lun-ven 08/11/14/17/20, DateTrigger│
              │  follow-up one-shot)                     │
              └─────────────────┬───────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────────┐
              │  Orchestrator                           │
              │  • verifica finestra operativa          │
              │  • lock anti-overlap                    │
              │  • daily target (DAILY_TARGET_DECISIONS)│
              │  • max 1 follow-up per opportunità/giorno│
              └────────────────┬────────────────────────┘
                               │
                               ▼
              ┌─────────────────────────────────────────┐
              │  ClaudeAgent scanner (LLM tool use)     │
              │  1. cheap scan universo simboli         │
              │  2. shortlist (max MAX_SYMBOLS_TO_DEEPEN)│
              │  3. deep analysis (OHLC + indicatori)   │
              │  4. esito: TRADE | NO_TRADE | WAIT_FOLLOW_UP
              └─────────────┬──────────┬────────────────┘
                            │          │
               TradeProposal│          │DelayedFollowUpRequest
                            ▼          ▼
              ┌─────────────────┐  ┌────────────────────┐
              │ risk_engine     │  │ Orchestrator       │
              │ .evaluate_trade │  │ _register_followup │
              │ (deterministico)│  │ (DateTrigger)      │
              └────────┬────────┘  └────────────────────┘
                       │ RiskDecision
                       ▼
              ┌─────────────────────────────────────────┐
              │ execution.run_once                      │
              └──┬─────────────────────────────────────┘
                 │ approved && mode != shadow
                 ▼
        ┌────────────────┐
        │ mt5_client     │
        │ send_order     │
        └────────────────┘
                 │
                 ▼
        ┌────────────────────────────────┐
        │ logger.log_trade_decision      │
        │ → logs/trades.db (WAL)         │
        │   tables: trades_log,          │
        │           daily_run_state      │
        │ → logs/agent.log               │
        └────────────────────────────────┘
```

Lo stesso stack è esposto via **MCP** in `mcp_server.py`, così Claude Desktop può chiamare direttamente i 10 tool disponibili.

---

## 2. Prerequisiti

- **Python 3.12 64-bit** (`struct.calcsize('P')*8 == 64`). Python 3.14 non ha ancora wheel pre-build per `pydantic-core`.
- **MetaTrader5** installato e funzionante (versione 5.0.5735+).
- **Conto demo FP Markets** (vedi sezione 4).
- **API key Anthropic** (https://console.anthropic.com/) per `claude_agent` e `mcp_server`.
- **Claude Desktop** (https://claude.ai/download) per usare il server MCP.

---

## 3. Setup

```powershell
git clone <repo-url>
cd trading-agent

python -m venv .venv
.venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt

copy .env.example .env
notepad .env   # compila MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, CLAUDE_API_KEY
```

Verifica rapida:

```powershell
python -c "import struct; print(struct.calcsize('P')*8)"             # deve dare 64
python -c "import MetaTrader5, anthropic, mcp, apscheduler; print('imports OK')"
```

---

## 4. Setup MT5 FP Markets demo

1. Apri https://www.fpmarkets.com/ → "Demo Account" → registra un account demo MT5.
2. Riceverai via email **login**, **password**, **server** (es. `FPMarkets-Demo`).
3. Scarica e installa MetaTrader5, accedi al conto demo dal terminale.
4. Inserisci le tre credenziali in `.env`:

   ```env
   MT5_LOGIN=12345678
   MT5_PASSWORD=la_tua_password
   MT5_SERVER=FPMarkets-Demo
   ```

5. Tieni il terminale MT5 **aperto** quando esegui il trading agent o il server MCP: la libreria Python si attacca al terminale via IPC.

---

## 5. Lancio daemon (modalità shadow)

`shadow` è il default (`EXECUTION_MODE=shadow`): l'agent calcola la decisione, la logga, ma **non invia mai ordini** a MT5.

```powershell
.venv\Scripts\activate
python main.py
```

`main.py` è un **daemon continuo**: avvia un `BlockingScheduler` APScheduler e resta in esecuzione finché non riceve `Ctrl+C` (SIGINT) o SIGTERM. Alla ricezione del segnale esegue uno shutdown pulito e chiude MT5.

All'avvio il log riporta la configurazione attiva:

```
Daemon start: tz=Europe/Rome weekdays=0,1,2,3,4 slots=[8, 11, 14, 17, 20]
              execution_mode=shadow daily_target=5 max_delay_min=120 followup_enabled=True
```

I cicli di analisi vengono lanciati sugli slot cron configurati (default: `08:00, 11:00, 14:00, 17:00, 20:00`, lun-ven). Per ogni ciclo il log mostra:

```
2026-04-30 08:00:01 [INFO] trading_agent: Cycle start symbol=EURUSD balance=10000.00
...
2026-04-30 08:00:08 [INFO] trading_agent: ClaudeAgent scanner NO_TRADE stop_reason=end_turn iter=3
2026-04-30 08:00:08 [INFO] trading_agent: Outcome NO_TRADE counted; decisions_count=1/5
```

Se il risk engine approva una proposta in shadow:

```
DECISION symbol=EURUSD direction=BUY approved=True size_lots=0.0500 reason=OK balance=10000.00
Outcome TRADE counted; decisions_count=2/5 trade_count=1
```

Quando `decisions_count` raggiunge `DAILY_TARGET_DECISIONS` (default: 5), nessun nuovo ciclo ordinario viene avviato per quel giorno.

---

## 6. Market Scanner multi-symbol

Il workflow scanner analizza un universo di simboli in due passate:

1. **Cheap scan** — per ogni simbolo calcola metriche sintetiche (trend bias, momentum, volatilità, spread) in modo economico (meno token/barre).
2. **Shortlist** — seleziona i `MAX_SYMBOLS_TO_DEEPEN` (default: 3) simboli con edge potenziale più chiaro.
3. **Deep analysis** — solo per i simboli della shortlist raccoglie OHLC e indicatori completi (SMA, EMA, RSI, ATR).
4. **Decisione finale** — uno tra `TRADE`, `NO_TRADE`, o `WAIT_FOLLOW_UP`.

### Follow-up ritardato

Se l'agente individua un setup non ancora pronto può richiedere un **follow-up one-shot** su un singolo simbolo:

- delay configurabile da 1 a `MAX_DELAY_MINUTES` minuti (default: 120);
- massimo **un follow-up per opportunità** per giornata;
- al follow-up il ciclo è focalizzato sul simbolo e sullo scenario salvato (`focus_prompt`);
- se al follow-up non c'è edge, l'esito è `NO_TRADE` (non si può richiedere un secondo rinvio);
- `WAIT_FOLLOW_UP` non conta come decisione giornaliera finale; TRADE/NO_TRADE successivi contano 1.

Configura i simboli dell'universo in `.env`:

```env
SYMBOLS=EURUSD,GBPUSD,USDJPY,AUDUSD
MAX_SYMBOLS_TO_DEEPEN=3
FOLLOWUP_ENABLED=true
MAX_DELAY_MINUTES=120
```

---

## 7. Scheduled Orchestrator — parametri chiave

Tutte le variabili sono in `.env` (vedi `.env.example`):

| Variabile               | Default         | Significato                                                 |
|-------------------------|-----------------|-------------------------------------------------------------|
| `OPERATING_TIMEZONE`    | `Europe/Rome`   | Timezone per finestra operativa e scheduler                 |
| `OPERATING_START_HOUR`  | `8`             | Ora di inizio finestra (inclusiva)                          |
| `OPERATING_END_HOUR`    | `22`            | Ora di fine finestra (esclusiva)                            |
| `OPERATING_WEEKDAYS`    | `0,1,2,3,4`     | Giorni operativi (0=Lun … 4=Ven)                            |
| `MAIN_CYCLE_HOURS`      | `3`             | Intervallo tra slot ordinari in ore → slot 08/11/14/17/20   |
| `DAILY_TARGET_DECISIONS`| `5`             | N. decisioni finali (TRADE + NO_TRADE) che chiudono la giornata |
| `MAX_DELAY_MINUTES`     | `120`           | Massimo ritardo consentito per un follow-up (clampato)      |
| `FOLLOWUP_ENABLED`      | `true`          | Abilita/disabilita la logica di follow-up ritardato         |
| `SCHEDULER_POLL_SECONDS`| `5`             | Frequenza loop interno APScheduler (parametro tecnico)      |

Il daemon si ferma automaticamente sul raggiungimento del `DAILY_TARGET_DECISIONS`. La persistenza del contatore giornaliero è in `logs/trades.db` (tabella `daily_run_state`), quindi sopravvive ai restart.

---

## 8. Uso diretto di `claude_agent.py`

### Ciclo single-symbol (backward-compat)

```python
from config import Config
from logger import init_logger
from mt5_client import Mt5Client
from claude_agent import ClaudeAgent

cfg = Config()
log = init_logger(cfg)
mt5 = Mt5Client(cfg); mt5.initialize(); mt5.login()

agent = ClaudeAgent(cfg, mt5, log)
proposal = agent.run_cycle("EURUSD", mt5.get_account_state())
print(proposal)

# Riepilogo in italiano delle ultime 5 decisioni
print(agent.explain_last_trades(5))
mt5.shutdown()
```

### Ciclo scanner multi-symbol

```python
from models import AgentCycleOutcome

account = mt5.get_account_state()
outcome: AgentCycleOutcome = agent.run_market_cycle(
    candidate_symbols=["EURUSD", "GBPUSD", "USDJPY"],
    timeframe="M15",
    account_state=account,
    followup=None,   # None = ciclo ordinario; passa DelayedFollowUpRequest per follow-up
)

if outcome.outcome_type == "TRADE":
    print(outcome.proposal)
elif outcome.outcome_type == "WAIT_FOLLOW_UP":
    print(f"Follow-up richiesto: {outcome.follow_up.symbol} tra {outcome.follow_up.delay_minutes} min")
else:
    print("NO_TRADE")
```

---

## 9. Avvio MCP server

```powershell
.venv\Scripts\activate
python mcp_server.py
```

Il server resta in attesa di messaggi JSON-RPC su stdin (stdio_server). **Stdout deve restare pulito**: ogni log finisce in `logs/agent.log`.

In stderr vedrai eventuali errori di import / inizializzazione MT5; per leggere il log strutturato:

```powershell
type logs\agent.log
```

Su startup, il log riporta `MCP server starting (mt5_ready=True/False)`.

---

## 10. Configurazione Claude Desktop

1. Apri (o crea) il file:

   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

2. Inserisci il blocco seguente (mantieni i doppi backslash):

   ```json
   {
     "mcpServers": {
       "trading-agent": {
         "command": "C:\\trading-agent\\.venv\\Scripts\\python.exe",
         "args": ["C:\\trading-agent\\mcp_server.py"],
         "env": {
           "PYTHONUNBUFFERED": "1"
         }
       }
     }
   }
   ```

3. **Chiudi completamente** Claude Desktop (anche dalla tray icon: tasto destro → Quit), poi riapri l'app.

4. Verifica: in una nuova conversazione, l'icona dei tool elenca `trading-agent` con i 10 tool:

   **Tool v1.0 (single-symbol)**
   - `get_account_state`
   - `get_market_snapshot`
   - `evaluate_trade_proposal`
   - `submit_order_if_approved`
   - `get_risk_profile`
   - `get_trade_history`

   **Tool v1.1 (multi-symbol scanner)**
   - `get_symbol_universe`
   - `scan_symbol_candidates`
   - `get_symbol_indicators`
   - `propose_trade`

5. Test rapidi:

   - *"Qual è il mio account state MT5?"* → chiama `get_account_state`.
   - *"Scansiona i candidati migliori tra EURUSD, GBPUSD, USDJPY."* → chiama `get_symbol_universe` + `scan_symbol_candidates`.
   - *"Valuta un BUY EURUSD a 1.10 con SL 1.097 e TP 1.106."* → chiama `evaluate_trade_proposal`.
   - *"Mostrami le ultime 5 operazioni."* → chiama `get_trade_history`.

---

## 11. Passaggio shadow → paper → live

Il valore di `EXECUTION_MODE` in `.env` controlla cosa fa `execution.run_once`:

| Modalità  | `send_order` chiamato? | Ordini visibili in MT5? | Conto |
|-----------|------------------------|-------------------------|-------|
| `shadow`  | NO                     | NO                      | demo  |
| `paper`   | SI                     | SI                      | demo  |
| `live`    | SI                     | SI                      | reale |

**Avvertenze obbligatorie:**

- Almeno **1 settimana di shadow** prima di passare a `paper`. Verifica nei log che il risk engine rifiuti i trade ovviamente sbagliati e accetti quelli plausibili.
- Almeno **1 settimana di paper** prima di passare a `live`. Verifica equity curve e drawdown sul conto demo.
- Cambio sempre nel `.env`, **mai** nel codice. Riavvia il daemon (`python main.py`) dopo la modifica.
- `live` richiede credenziali di un conto reale: rivedi `RISK_PER_TRADE_PERCENT`, `MAX_DAILY_DRAWDOWN_PERCENT`, `MAX_LOTS_PER_TRADE` prima.

---

## 12. Tests

```powershell
.venv\Scripts\activate
pytest tests/ -v
```

Suite: **72 test, 0 skipped** (salvo test MT5 E2E senza terminale aperto).

| File                         | N  | Cosa copre                                                                          |
|------------------------------|----|-------------------------------------------------------------------------------------|
| `test_risk.py`               |  9 | Risk engine: kill switch, SL bounds, margin downsize, session filter                |
| `test_mt5.py`                |  4 | E2E sul terminale MT5 reale (skip automatico se MT5 non disponibile)                |
| `test_scanner.py`            | 11 | Scanner multi-symbol: cheap scan, shortlist, propose_trade, max 1 proposta/ciclo   |
| `test_mcp_tools_v2.py`       | 15 | 10 tool MCP: get_symbol_universe, scan_symbol_candidates, propose_trade, legacy v1 |
| `test_scheduler.py`          | 24 | OperatingWindow, DailyRunStateStore, build_scheduler (slot cron), Orchestrator lock/follow-up/target, clamp delay |
| `test_daily_orchestrator.py` |  9 | Policy giornaliera: target 5, WAIT non conta, follow-up conta 1, focus simbolo, account state letto sempre |

---

## 13. Audit trail

Ogni decisione del risk engine è persistita su `logs/trades.db` (SQLite, journal_mode=WAL).

### Tabella `trades_log`

```sql
CREATE TABLE trades_log (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp       TEXT NOT NULL,        -- ISO 8601, Europe/Rome
  symbol          TEXT NOT NULL,
  direction       TEXT NOT NULL,        -- BUY|SELL
  size_lots       REAL,
  entry_price     REAL,
  stop_loss       REAL,
  take_profit     REAL,
  decision_reason TEXT,                 -- OK oppure motivo del reject
  approved        INTEGER NOT NULL,     -- 0|1
  pnl_realized    REAL                  -- NULL fino a chiusura posizione
);
```

### Tabella `daily_run_state`

```sql
CREATE TABLE daily_run_state (
  date            TEXT PRIMARY KEY,     -- YYYY-MM-DD
  decisions_count INTEGER NOT NULL,     -- TRADE + NO_TRADE finali del giorno
  trade_count     INTEGER NOT NULL,
  no_trade_count  INTEGER NOT NULL,
  updated_at      TEXT NOT NULL
);
```

Esempi di query:

```powershell
# Ultime 10 decisioni
.venv\Scripts\python.exe -c "import sqlite3, json; conn=sqlite3.connect('logs/trades.db'); conn.row_factory=sqlite3.Row; print(json.dumps([dict(r) for r in conn.execute('SELECT * FROM trades_log ORDER BY id DESC LIMIT 10')], indent=2, default=str))"

# Stato giornata corrente
.venv\Scripts\python.exe -c "import sqlite3; conn=sqlite3.connect('logs/trades.db'); print(list(conn.execute('SELECT * FROM daily_run_state ORDER BY date DESC LIMIT 7')))"

# Tasso di approvazione per simbolo
.venv\Scripts\python.exe -c "import sqlite3; conn=sqlite3.connect('logs/trades.db'); print(list(conn.execute('SELECT symbol, AVG(approved)*100 as approved_pct, COUNT(*) as n FROM trades_log GROUP BY symbol')))"
```

Il log testuale è in `logs/agent.log` (rotante, 5MB × 3 backup, UTF-8).

---

## 14. FAQ / Troubleshooting

**1. `pip install` fallisce su `pydantic-core` con errore di compilazione Rust.**
Stai usando Python 3.14 (non ha wheel pre-build). Crea il venv con Python 3.12 64-bit, ad esempio da Anaconda:
`C:\Users\<TU>\anaconda3\python.exe -m venv .venv`.

**2. `mt5.initialize()` ritorna `False` o `IPC timeout`.**
Il terminale MetaTrader5 non è in esecuzione. Apri MT5 manualmente e accedi al conto demo prima di lanciare `main.py` o `mcp_server.py`.

**3. `mt5.login()` ritorna `False` ma il terminale è aperto.**
Credenziali in `.env` sbagliate. Verifica `MT5_LOGIN` (numero, niente quote), `MT5_PASSWORD` e `MT5_SERVER` (esattamente come ricevuto da FP Markets, sensitive a maiuscole/minuscole).

**4. Claude Desktop non vede il server MCP.**
- Path Python sbagliato in `claude_desktop_config.json` (controlla i `\\` doppi).
- Non hai chiuso davvero l'app: tasto destro sull'icona della tray → Quit.
- Errore al boot del server: lancia `python mcp_server.py` da PowerShell e guarda stderr.

**5. ZoneInfo `'No time zone found with key Europe/Rome'`.**
Manca `tzdata` (necessario su Windows). `pip install tzdata`.

**6. SL rifiutato sempre come "troppo stretto" o "troppo largo".**
Il modello propone SL in valore assoluto, ma `MIN_SL_PIPS`/`MAX_SL_PIPS` sono espressi in pip. Controlla che `entry_price` e `stop_loss_price` abbiano la giusta precisione decimale (5 cifre per EURUSD, non 4).

**7. Il daemon si ferma subito senza errori.**
La finestra operativa è chiusa: controlla `OPERATING_TIMEZONE`, `OPERATING_WEEKDAYS` e `OPERATING_START_HOUR`/`OPERATING_END_HOUR`. Se lanci fuori orario, il daemon avvia il BlockingScheduler ma nessun ciclo parte finché non arriva il primo slot cron.

**8. `decisions_count` non si azzera il giorno dopo.**
Il reset è automatico: `DailyRunStateStore.get_or_create(today)` usa la data corrente come chiave. Il contatore del giorno precedente resta in `daily_run_state` per storico ma non influenza i cicli del giorno nuovo.

**9. WAIT_FOLLOW_UP ignorato, log mostra "downgraded to NO_TRADE".**
Cause possibili: `FOLLOWUP_ENABLED=false` in `.env`, oppure la stessa opportunità `(data, simbolo)` ha già ricevuto un follow-up nella giornata corrente (limite: 1 per opportunità per giorno).

---

## 15. Disclaimer

Questo software è fornito **a scopo didattico e di ricerca personale**. Non è consulenza finanziaria, né un sistema di trading certificato. Ogni operazione, anche su conto demo, è a tuo rischio e responsabilità. L'autore declina ogni responsabilità per perdite finanziarie, malfunzionamenti del broker, errori di configurazione o decisioni del modello LLM. Esegui sempre una validazione approfondita in modalità `shadow` e `paper` prima di considerare l'uso su conto reale.
