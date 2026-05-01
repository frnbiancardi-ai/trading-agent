# Validazione utente — Fase 14 (Python Pure Strategy Engine)

Branch: `feature/python-pure-strategy`
Suite automatizzata: **111/111 passed** (livello CI).
Live checkpoint: a carico dell'utente. Senza OK utente la fase resta `IN_PROGRESS`.

---

## Pre-requisiti

- [ ] MT5 desktop aperto e loggato sull'account demo TenTrade.
- [ ] File `.env` valorizzato. Variabili minime richieste:
  - `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
  - `EXECUTION_MODE=shadow` (NON cambiare in `live`/`paper`)
  - `STRATEGY_MODE=intraday`
  - `INTRADAY_SYMBOLS=EURUSD,GBPUSD,USDJPY,XAUUSD` (o subset disponibile sul broker)
  - `INTRADAY_TIMEFRAME=M15`
  - `OPERATING_TIMEZONE=Europe/Rome`
  - `OPERATING_START_HOUR=8`, `OPERATING_END_HOUR=22`
  - `OPERATING_WEEKDAYS=0,1,2,3,4`
  - `MAIN_CYCLE_HOURS=3`
  - `DAILY_TARGET_DECISIONS=5`
- [ ] venv attivo: `C:\trading-agent\.venv\Scripts\python.exe` (Anaconda 3.12).
- [ ] Dipendenze installate: `pip install -r requirements.txt`.

---

## Step 1 — Sanity check ambiente

```powershell
cd C:\trading-agent
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

Atteso: `111 passed`. Se anche un solo test fallisce, **stop**: aprire issue, non procedere oltre.

---

## Step 2 — Smoke test import

```powershell
.\.venv\Scripts\python.exe -c "from main import main; from strategy import IntradayStrategy; from scanner import MultiSymbolScanner, StrategyRunner; print('imports OK')"
```

Atteso: `imports OK`, nessuna eccezione.

---

## Step 3 — Dry run scanner singolo simbolo (no daemon)

Apri una shell Python interattiva con MT5 vivo:

```powershell
.\.venv\Scripts\python.exe
```

```python
import logging
logging.basicConfig(level=logging.INFO)
from config import Config
from mt5_client import Mt5Client
from strategy import IntradayStrategy
from scanner import MultiSymbolScanner

cfg = Config()
mt5 = Mt5Client(cfg)
assert mt5.initialize() and mt5.login(), "MT5 login failed"

strat = IntradayStrategy(cfg, mt5, logging.getLogger("dryrun"))
scanner = MultiSymbolScanner(cfg, mt5, strat, logging.getLogger("dryrun"))

# Single symbol
setup = strat.analyze_symbol("EURUSD", mt5.get_account_state())
print("setup_type:", setup.setup_type, "direction:", setup.direction,
      "confidence:", setup.confidence, "reason:", setup.reason)

# Multi-symbol
results = scanner.scan_universe(cfg.INTRADAY_SYMBOLS)
for r in results:
    print(r.symbol, r.trend_bias, r.regime, r.candidate_score, r.warnings)

mt5.shutdown()
```

Verificare:
- [ ] `analyze_symbol` ritorna un `TechnicalSetup` con `setup_type` in `{READY, FORMING, NONE}`.
- [ ] `scan_universe` ritorna fino a `INTRADAY_SCAN_TOP_N` `ScanResult`, ordinati per `candidate_score` desc.
- [ ] Nessuna eccezione, nessun crash, latenza per simbolo < 1s.

---

## Step 4 — Daemon end-to-end (almeno 1 ciclo completo)

```powershell
.\.venv\Scripts\python.exe main.py
```

Atteso a boot:
```
Daemon start: tz=Europe/Rome weekdays=0,1,2,3,4 slots=[8,11,14,17,20]
execution_mode=shadow daily_target=5 max_delay_min=120 followup_enabled=True
strategy=python_pure timeframe=M15 symbols=['EURUSD','GBPUSD',...]
```

Lasciar girare fino al primo slot ordinario nella finestra operativa
(o forzare manualmente lo slot abbassando `MAIN_CYCLE_HOURS` a `1` e
attendendo il prossimo cambio d'ora).

Verificare in `logs/agent.log`:
- [ ] Riga "Cycle skipped" se fuori finestra (atteso fuori 8-22 lun-ven).
- [ ] Al primo slot operativo: log di `MultiSymbolScanner.scan_universe` +
      `deep_analyze_top_candidates`.
- [ ] Outcome stampato: `TRADE` (con proposta), `NO_TRADE` (con reason),
      o `WAIT_FOLLOW_UP` (con delay e symbol).
- [ ] Se `TRADE` in shadow: riga inserita in `logs/trades.db` tabella
      `trades_log`, **nessun ordine MT5**, response include
      `"execution_mode":"shadow"`.
- [ ] Contatore `daily_run_state.decisions_count` incrementato in SQLite.
- [ ] Shutdown pulito con `Ctrl+C`: log "Signal SIGINT received, shutting down scheduler".

---

## Step 5 — Verifica persistenza SQLite

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c = sqlite3.connect('logs/trades.db'); print('daily:', c.execute('SELECT * FROM daily_run_state').fetchall()); print('trades:', c.execute('SELECT id,symbol,direction,decision_status FROM trades_log ORDER BY id DESC LIMIT 5').fetchall())"
```

Verificare:
- [ ] `daily_run_state` ha riga per la data odierna con `decisions_count >= 1`.
- [ ] `trades_log` ha almeno una riga inserita oggi se è uscito un `TRADE`.

---

## Step 6 — Sanity follow-up (opzionale, se osservato `WAIT_FOLLOW_UP`)

Se durante step 4 è stato registrato un follow-up:
- [ ] Nel log compare `Follow-up registered for <symbol> @ <timestamp>`.
- [ ] Allo scadere del delay, parte un `execute_followup_cycle`.
- [ ] Outcome del follow-up incrementa `decisions_count` di 1 (e non 2).

---

## Esito validazione

| Step | Pass/Fail | Note |
|------|-----------|------|
| 1. Suite test    | [ ]       |      |
| 2. Smoke import  | [ ]       |      |
| 3. Dry run       | [ ]       |      |
| 4. Daemon E2E    | [ ]       |      |
| 5. SQLite        | [ ]       |      |
| 6. Follow-up     | [ ] / N/A |      |

Se TUTTI gli step sono PASS:
1. Marcare `phase_status: VALIDATED` in `STATE.md`.
2. Aggiornare `PHASES.md` con fase 14.
3. Decidere merge `feature/python-pure-strategy` → `main` (subito) oppure
   prima completare fase 15 (RSS news sentiment) e poi merge unico.
4. Tag candidato: `v1.2.0-rc1` dopo merge.

Se anche solo uno fallisce:
- Lasciare `phase_status: IN_PROGRESS`.
- Aprire issue con repro minimo + log.
- Non taggare, non mergere.

---

## Rollback rapido

Se il daemon si comporta in modo imprevisto:
1. `Ctrl+C` per shutdown pulito (signal SIGINT gestito).
2. Verificare che nessuna posizione aperta sia rimasta orfana
   (`EXECUTION_MODE=shadow` non apre nulla; nei modi `paper`/`live` chiudere manualmente).
3. `git checkout main` per tornare al codice pre-fase-14 (tag `v1.1.1`).
