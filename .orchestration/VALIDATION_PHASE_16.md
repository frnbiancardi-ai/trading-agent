# Validazione utente — Fase 16 (H24 Strategy Update)

Branch: `main` (post-merge da `feature/python-pure-strategy`)
Tag: `v1.2.0`
Suite automatizzata: **173/173 passed** (142 fasi 14+15 + 31 fase 16).
Live checkpoint: a carico dell'utente. In caso di errore aprire bug e patch.

---

## Pre-requisiti

- [ ] MT5 desktop aperto e loggato sull'account demo TenTrade.
- [ ] File `.env` valorizzato. Variabili minime fase 16:
  - `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
  - `EXECUTION_MODE=shadow` (NON cambiare in `paper`/`live`)
  - `STRATEGY_MODE=intraday`
  - `INTRADAY_SYMBOLS=EURUSD,GBPUSD,...`
  - `INTRADAY_TIMEFRAME=M15`
  - `OPERATING_TIMEZONE=Europe/Rome`
  - `OPERATING_WEEKDAYS=0,1,2,3,4`
  - `INTRADAY_START_HOUR=8`, `INTRADAY_END_HOUR=20`
  - `INTRADAY_SCAN_INTERVAL_MINUTES=15`
  - `INTRADAY_FIRST_CYCLE_DELAY_MINUTES=5`
  - `PAUSE_TRADING=false`
  - `DRY_RUN=false` (per checkpoint live)
  - `MIN_PROTECT_PROFIT_R_MULTIPLIER=1.0`
  - `CLOSE_BEFORE_END_OF_WINDOW=true`
- [ ] venv attivo: `C:\trading-agent\.venv\Scripts\python.exe` (Anaconda 3.12).
- [ ] Dipendenze installate: `pip install -r requirements.txt`.

---

## Step 1 — Sanity check ambiente

```powershell
cd C:\trading-agent
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

Atteso: `173 passed`. Se anche un solo test fallisce, **stop**: aprire bug.

---

## Step 2 — Smoke test import + Config fase 16

```powershell
.\.venv\Scripts\python.exe -c "from main import main; from scheduler import IntradayLoopScheduler, HeartbeatStore; from strategy import IntradayStrategy, StrategyEnvironment; from config import Config; cfg=Config(); print('imports OK'); print('scan_interval=', cfg.INTRADAY_SCAN_INTERVAL_MINUTES); print('first_delay=', cfg.INTRADAY_FIRST_CYCLE_DELAY_MINUTES); print('pause=', cfg.PAUSE_TRADING); print('dry_run=', cfg.DRY_RUN); print('protect_R=', cfg.MIN_PROTECT_PROFIT_R_MULTIPLIER); print('close_eod=', cfg.CLOSE_BEFORE_END_OF_WINDOW)"
```

Atteso: `imports OK`, valori coerenti col `.env`.

---

## Step 3 — Dry run weekend (mercati chiusi)

```powershell
$env:DRY_RUN='true'; .\.venv\Scripts\python.exe scripts\dry_run_cycle.py
```

Verificare:
- [ ] Exit 0 (MT5 connessa) oppure exit 2 (MT5 off, OK).
- [ ] `logs/agent.log` contiene `=== DRY-RUN scheduler H24 (fase 16) ===`.
- [ ] Se sabato/domenica: outcome `WEEKEND` con `note=weekend_off`.
- [ ] Tabella `heartbeat` in `logs/trades.db` ha la nuova riga.
- [ ] Tabella `scheduler_state` aggiornata (riga id=1).

Inspect heartbeat:
```powershell
.\.venv\Scripts\python.exe -c "from config import Config; from scheduler import HeartbeatStore, heartbeat_db_path; s=HeartbeatStore(heartbeat_db_path(Config())); import json; print(json.dumps(s.get_state(), indent=2)); print(json.dumps(s.last_heartbeats(5), indent=2, default=str))"
```

---

## Step 4 — Daemon H24 live in giorno feriale (≥1 ora)

Lanciare in finestra operativa (lun-ven, dentro `INTRADAY_START_HOUR..INTRADAY_END_HOUR`):

```powershell
.\.venv\Scripts\python.exe main.py
```

Atteso a boot:
```
Daemon H24 start: tz=Europe/Rome weekdays=0,1,2,3,4 window=08-20
scan_interval=15min first_delay=5min execution_mode=shadow pause=False
dry_run=False strategy=python_pure timeframe=M15 symbols=[...]
Loop H24 avvio: first_delay=300s interval=900s dry_run=False pause=False
```

Lasciare girare ≥4 cicli (1 ora). Verificare in `logs/agent.log`:
- [ ] Primo ciclo dopo ~5 minuti (non immediato).
- [ ] Ogni 15 min: log `Ciclo done outcome=<X> duration_ms=<N> note=<...>`.
- [ ] Outcome attesi (uno o più tra): `OK`, `NO_TRADE`, `OUT_OF_WINDOW`, `NEWS_BLOCKED`.
- [ ] Nessun outcome `ERROR` ricorrente. Se isolato, controllare `error_message`.
- [ ] Se TRADE in shadow: riga in `trades_log`, **nessun ordine MT5 reale**.
- [ ] Posizioni aperte preesistenti su simboli intraday: log `evaluate_open_position`
      e (se contesto negativo + profit≥R) `Chiusura OK ticket=...`.
- [ ] A fine finestra (`hour >= INTRADAY_END_HOUR`): se ci sono posizioni intraday
      aperte → log `CLOSE_END_OF_DAY`.
- [ ] Shutdown pulito con `Ctrl+C`: log `Signal SIGINT received, stopping H24 loop`.

---

## Step 5 — Verifica persistenza heartbeat post-live

```powershell
.\.venv\Scripts\python.exe -c "from config import Config; from scheduler import HeartbeatStore, heartbeat_db_path; s=HeartbeatStore(heartbeat_db_path(Config())); import json; print(json.dumps(s.get_state(), indent=2)); print('--- last 10 ---'); print(json.dumps(s.last_heartbeats(10), indent=2, default=str))"
```

Verificare:
- [ ] `last_outcome` non è `RUNNING` (ciclo chiuso correttamente).
- [ ] `consecutive_errors` = 0.
- [ ] `last_duration_ms` < `INTRADAY_SCAN_INTERVAL_MINUTES * 60_000` (no overrun).
- [ ] Almeno 4 righe in `last_heartbeats` con outcome non-RUNNING.

---

## Step 6 — Test add-on / drawdown potenziale (opzionale, richiede posizione preesistente)

Se durante step 4 è uscito un TRADE su simbolo già con posizione stessa direzione:
- [ ] Nel log: `note=selected=<sym> conf=<X> addon=True`.
- [ ] `proposal.comment` = `python_strategy_addon`.
- [ ] `proposal.rationale` inizia con `ADD-ON: `.

Se uscito un NO_TRADE per drawdown:
- [ ] Outcome `DRAWDOWN_BLOCK`.
- [ ] `note` contiene `drawdown_violation symbol=<X> max_potential=<Y>%`.

---

## Step 7 — MCP `close_position` da Claude Desktop (opzionale)

Restart Claude Desktop. Verificare che il tool `close_position` sia visibile.

Test:
```
Chiedi a Claude Desktop: "Lista le posizioni aperte"
Poi: "Chiudi la posizione con ticket <N>"
```

Verificare:
- [ ] Tool `close_position` invocato con `position_id=<N>`.
- [ ] Se `DRY_RUN=true` lato MCP server: response `dry_run: true`, nessun ordine MT5.
- [ ] Altrimenti: response `success: true`, `order_id`, posizione effettivamente chiusa.

---

## Esito validazione

| Step | Pass/Fail | Note |
|------|-----------|------|
| 1. Suite test         | [ ]       |      |
| 2. Smoke import       | [ ]       |      |
| 3. Dry run weekend    | [ ]       |      |
| 4. Daemon H24 live    | [ ]       |      |
| 5. Heartbeat SQLite   | [ ]       |      |
| 6. Add-on / drawdown  | [ ] / N/A |      |
| 7. MCP close_position | [ ] / N/A |      |

Se tutti i step PASS:
- Marcare `phase_status: VALIDATED` in `STATE.md`.
- Aggiornare `PHASES.md` con fase 16.

Se errore: aprire bug (titolo `[phase-16] <descrizione>`), allegare:
- Output `last_heartbeats(10)` con riga ERROR.
- Stack trace da `logs/agent.log`.
- Config `.env` (mascherare credenziali).

---

## Rollback rapido

Se daemon H24 si comporta in modo imprevisto:
1. `Ctrl+C` per shutdown pulito.
2. Posizioni aperte: `EXECUTION_MODE=shadow` non apre nulla.
   In paper/live, chiudere manualmente via MT5 o via tool MCP `close_position`.
3. `git checkout v1.2.0~N` per tornare al commit pre-fase-16 (tag `v1.2.0` su HEAD post-merge).
4. Se serve un quick-fix: branch `hotfix/phase-16-<bug>` da `main`, patch, PR, merge, tag `v1.2.1`.
