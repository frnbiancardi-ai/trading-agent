# trading-agent

Agente di trading locale per MetaTrader5 (FP Markets demo) con risk engine deterministico, integrazione Claude API (tool use) e server MCP per Claude Desktop.

---

## 1. Introduzione

`trading-agent` orchestra un ciclo `proposta → validazione → (eventuale) ordine` mantenendo un audit trail completo su SQLite e file di log rotante.

Architettura a blocchi:

```
              ┌──────────────────────────┐
              │   ClaudeAgent (LLM)      │
              │   tool use → proposal    │
              └────────────┬─────────────┘
                           │ TradeProposal
                           ▼
              ┌──────────────────────────┐
              │   risk_engine.evaluate   │ ← unico cancello
              │   (deterministico)       │
              └────────────┬─────────────┘
                           │ RiskDecision
                           ▼
                  ┌────────────────┐
                  │  execution.run │
                  └─┬────┬─────────┘
                    │    │ approved && mode != shadow
                    │    ▼
                    │   ┌──────────────┐
                    │   │ mt5_client   │
                    │   │ send_order   │
                    │   └──────────────┘
                    │
                    ▼
              ┌──────────────────────────┐
              │ logger.log_trade_decision│
              │ → logs/trades.db (WAL)   │
              │ → logs/agent.log         │
              └──────────────────────────┘
```

Lo stesso stack è esposto via **MCP** in `mcp_server.py`, così Claude Desktop può chiamare direttamente i tool (`get_account_state`, `evaluate_trade_proposal`, ecc.).

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
python -c "import MetaTrader5, anthropic, mcp; print('imports OK')"
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

## 5. Lancio in modalità shadow

`shadow` è il default (`EXECUTION_MODE=shadow`): l'agent calcola la decisione, la logga, ma **non invia mai ordini** a MT5.

```powershell
.venv\Scripts\activate
python main.py
```

Ogni ciclo per ogni simbolo in `SYMBOLS` produce una riga in `logs/agent.log` tipo:

```
2026-04-29 10:15:22,341 [INFO] trading_agent: Cycle start symbol=EURUSD balance=10000.00 equity=10000.00
2026-04-29 10:15:24,108 [INFO] trading_agent: ClaudeAgent NO_TRADE symbol=EURUSD stop_reason=end_turn iter=3
```

Se il modello propone un trade e il risk engine approva:

```
DECISION symbol=EURUSD direction=BUY approved=True size_lots=0.0500 reason=OK balance=10000.00
```

In `shadow` non vedrai ordini in MT5 — la riga in `trades.db` è il solo effetto.

---

## 6. Uso diretto di `claude_agent.py`

Per un utilizzo programmatico senza MCP:

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

---

## 7. Avvio MCP server

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

## 8. Configurazione Claude Desktop

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

4. Verifica: in una nuova conversazione, l'icona dei tool elenca `trading-agent` con i 6 tool:

   - `get_account_state`
   - `get_market_snapshot`
   - `evaluate_trade_proposal`
   - `submit_order_if_approved`
   - `get_risk_profile`
   - `get_trade_history`

5. Test rapidi:

   - *"Qual è il mio account state MT5?"* → chiama `get_account_state`.
   - *"Valuta un BUY EURUSD a 1.10 con SL 1.097 e TP 1.106."* → chiama `evaluate_trade_proposal`.
   - *"Mostrami le ultime 5 operazioni."* → chiama `get_trade_history`.

---

## 9. Passaggio shadow → paper → live

Il valore di `EXECUTION_MODE` in `.env` controlla cosa fa `execution.run_once`:

| Modalità  | `send_order` chiamato? | Ordini visibili in MT5? | Conto |
|-----------|------------------------|-------------------------|-------|
| `shadow`  | NO                     | NO                      | demo  |
| `paper`   | SI                     | SI                      | demo  |
| `live`    | SI                     | SI                      | reale |

**Avvertenze obbligatorie:**

- Almeno **1 settimana di shadow** prima di passare a `paper`. Verifica nei log che il risk engine rifiuti i trade ovviamente sbagliati e accetti quelli plausibili.
- Almeno **1 settimana di paper** prima di passare a `live`. Verifica equity curve e drawdown sul conto demo.
- Cambio sempre nel `.env`, **mai** nel codice. Riavvia ogni processo (main.py e mcp_server.py) dopo la modifica.
- `live` richiede credenziali di un conto reale: rivedi `RISK_PER_TRADE_PERCENT`, `MAX_DAILY_DRAWDOWN_PERCENT`, `MAX_LOTS_PER_TRADE` prima.

---

## 10. Tests

```powershell
.venv\Scripts\activate
pytest tests/ -v
```

Cosa è coperto:

- `tests/test_risk.py` — 9 test unitari sul risk engine (kill switch, SL bounds, margin downsize, session filter). Nessuna dipendenza esterna.
- `tests/test_mt5.py` — 4 test E2E sul terminale MT5 reale: skippati automaticamente se `MT5_LOGIN/MT5_PASSWORD` non sono settati o se `Mt5Client.initialize()/login()` fallisce.

---

## 11. Audit trail

Ogni decisione del risk engine è persistita su `logs/trades.db` (SQLite, journal_mode=WAL):

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

Esempi di query:

```powershell
# Ultime 10 decisioni
.venv\Scripts\python.exe -c "import sqlite3, json; conn=sqlite3.connect('logs/trades.db'); conn.row_factory=sqlite3.Row; print(json.dumps([dict(r) for r in conn.execute('SELECT * FROM trades_log ORDER BY id DESC LIMIT 10')], indent=2, default=str))"

# Tasso di approvazione per simbolo
.venv\Scripts\python.exe -c "import sqlite3; conn=sqlite3.connect('logs/trades.db'); print(list(conn.execute('SELECT symbol, AVG(approved)*100 as approved_pct, COUNT(*) as n FROM trades_log GROUP BY symbol')))"
```

Il log testuale è in `logs/agent.log` (rotante, 5MB × 3 backup, UTF-8).

---

## 12. FAQ / Troubleshooting

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

---

## 13. Disclaimer

Questo software è fornito **a scopo didattico e di ricerca personale**. Non è consulenza finanziaria, né un sistema di trading certificato. Ogni operazione, anche su conto demo, è a tuo rischio e responsabilità. L'autore declina ogni responsabilità per perdite finanziarie, malfunzionamenti del broker, errori di configurazione o decisioni del modello LLM. Esegui sempre una validazione approfondita in modalità `shadow` e `paper` prima di considerare l'uso su conto reale.
