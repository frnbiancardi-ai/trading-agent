# Stato vivo del progetto trading-agent

Verità singola sullo stato corrente. Aggiornato dall'orchestrator dopo ogni micro-step. In caso di conflitto con git, vince questo file più l'ultimo commit pushato.

## Identità progetto

- Nome: trading-agent
- Path locale: `C:\trading-agent`
- Ambiente: Windows + Python 3.12+ + MetaTrader5 5.0.5735
- Broker: FP Markets (conto demo)
- Repo Git: `<da compilare al primo setup>`

## Stato sessione

- session_status: `IN_PROGRESS`  <!-- IDLE | IN_PROGRESS | HANDOFF | BLOCKED | COMPLETED -->
- last_session_end: `2026-04-29T00:00:00+02:00`
- last_session_reason: `pausa volontaria utente, fase 4 completata`

## Stato fase corrente

- current_phase: `10`
- current_phase_title: `E2E + Tests + README`
- phase_status: `VALIDATED`  <!-- NOT_STARTED | IN_PROGRESS | VALIDATED -->
- current_substep: `3`
- last_action: `2026-04-29 — tests/test_mt5.py creato (skip se no MT5); README.md riscritto in italiano con 13 sezioni; pytest 9 passed + 4 skipped (MT5 non disponibile)`
- next_action: `Validazione live E2E (utente): MT5 demo + Claude Desktop. Poi tag v1.0.0 e session COMPLETED`

## File completati per fase

```yaml
phase_1_setup:
  status: VALIDATED
  files:
    - requirements.txt
    - .gitignore
    - logs/.gitkeep
    - prompts/.gitkeep
    - tests/.gitkeep
  validated_at: "2026-04-29"

phase_2_config_models:
  status: VALIDATED
  files:
    - .env.example
    - config.py
    - models.py
  validated_at: "2026-04-29"

phase_3_mt5_client:
  status: VALIDATED
  files:
    - mt5_client.py
    - requirements.txt  # aggiunto tzdata
  validated_at: "2026-04-29"

phase_4_risk_engine:
  status: VALIDATED
  files:
    - risk_engine.py
    - tests/test_risk.py
    - pytest.ini
    - config.py   # aggiunto USE_SESSION_FILTER, SESSION_START/END_HOUR, RISK_AMOUNT_MODE, MAX_LOTS_PER_TRADE
    - .env.example
  validated_at: "2026-04-29"

phase_5_logger:
  status: VALIDATED
  files:
    - logger.py
  validated_at: "2026-04-29"
  notes:
    - "Schema trades_log usa cfg.LOG_FILE come riferimento per la directory; trades.db = parent(LOG_FILE)/trades.db"
    - "journal_mode=WAL verificato"

phase_6_execution:
  status: VALIDATED
  files:
    - execution.py
    - main.py
  validated_at: "2026-04-29"
  notes:
    - "ClaudeAgent rinviato a Fase 8: in main.py c'è un TODO esplicito e proposal=None come placeholder"
    - "Live checkpoint (shadow→DB row, paper→ordine MT5) richiede MT5 vivo + credenziali in .env, non eseguito automaticamente"

phase_7_indicators:
  status: VALIDATED
  files:
    - indicators.py
  validated_at: "2026-04-29"
  notes:
    - "Validazione manuale ±0.1% vs TradingView NON eseguita: richiede dati OHLC reali da MT5"

phase_8_claude_agent:
  status: VALIDATED
  files:
    - prompts/system_prompt.txt
    - prompts/context_template.txt
    - claude_agent.py
    - main.py    # rimosso TODO ClaudeAgent, ora wired
    - config.py  # aggiunto CLAUDE_MAX_TOKENS, CLAUDE_TEMPERATURE, TIMEFRAME
    - .env.example
  validated_at: "2026-04-29"
  notes:
    - "Static checks OK con Mt5Client mockato; _dispatch_tool produce risultati JSON-serializzabili per tutti e 3 i tool"
    - "Live checkpoint NON eseguito: richiede CLAUDE_API_KEY reale + MT5 vivo"
    - "max 6 iterazioni tool use, 50 barre OHLC nel snapshot, 100 barre per indicatori (limite token)"

phase_9_mcp_server:
  status: VALIDATED
  files:
    - mcp_server.py
    - README.md
  validated_at: "2026-04-29"
  notes:
    - "API mcp 1.27.0 verificata: list_tools/call_tool decorators, stdio_server, Tool/TextContent"
    - "stdout pulito (libero per JSON-RPC); logger su file, non stderr/stdout"
    - "MT5 init in try/except: server vive anche senza MT5 (i tool che lo richiedono ritornano errore)"
    - "Test live in Claude Desktop richiede config in %APPDATA%\\Claude\\claude_desktop_config.json e riavvio app"

phase_10_e2e:
  status: VALIDATED
  files:
    - tests/test_mt5.py
    - README.md
  validated_at: "2026-04-29"
  notes:
    - "Test E2E unit-side: 9 risk_engine green, 4 mt5 e2e skipped (MT5 non disponibile in ambiente CI)"
    - "Validazione live (run main.py shadow su EURUSD/GBPUSD, Claude Desktop con 6 tool, paper trading) demandata all'utente"
```

## Decisioni aperte

(nessuna)

## Decisioni risolte

- [x] **Versione libreria `mcp`** — risolta `2026-04-29`.
  - Decisione: nessun pin di versione in `requirements.txt` (riga `mcp` semplice).
  - Motivazione: `mcp` è in evoluzione rapida; pinnare ora rischia di bloccare API incompatibili. In Fase 9, prima di scrivere `mcp_server.py`, eseguire `pip show mcp` per leggere la versione effettivamente installata, adattare l'API al SDK reale e documentare la versione assunta in cima a `mcp_server.py`.
- [x] **Path Python venv per `claude_desktop_config.json`** — risolta `2026-04-29`.
  - Decisione: `C:\trading-agent\.venv\Scripts\python.exe`.
  - Motivazione: path di sistema deterministico ancorato alla root del progetto, non dipendente dall'username Windows. Coerente con la creazione del venv prevista nello Step 0 della Fase 1 (`python -m venv .venv` da `C:\trading-agent`).
- [x] **Python venv su Windows** — risolta `2026-04-29`.
  - Decisione: usare `C:\Users\Bl4ckBug\anaconda3\python.exe` per creare il venv.
  - Motivazione: Python di sistema è 3.14 (cp314), senza wheel pre-compilati per pydantic-core. Anaconda ha Python 3.12.4 64-bit con tutti i wheel disponibili. Il venv risultante è `C:\trading-agent\.venv\Scripts\python.exe`.

## Configurazione runtime corrente

- EXECUTION_MODE: `shadow` (mai modificare a `live` prima di Fase 10 validata + 1 settimana di paper trading).
- RISK_PROFILE: `CONSERVATIVE`
- Symbols attivi: `EURUSD`

## Note di handoff

- Ultimo file generato: `tests/test_risk.py`
- Prossimo file da generare: `logger.py`
- Comando di ripresa: `leggi .orchestration/phase-prompts/phase-05-logger.md, genera logger.py`
- Test pendenti: nessuno (tutti i test esistenti passano: `pytest tests/test_risk.py -v`)
- Rischi noti per la prossima sessione:
  - Il checkpoint di fase 5 richiede che `trades.db` venga creato fisicamente su disco: verificare path `logs/trades.db` e permessi di scrittura.
  - Il live checkpoint di fase 3 (mt5_client) non è stato eseguito: richiede MT5 aperto con credenziali reali in `.env`.

## Cronologia sessioni

| Timestamp | Tipo | Fase | Descrizione |
|-----------|------|------|-------------|
| `2026-04-29T00:00:00+02:00` | BOOT | 1 | Sessione aperta, completate fasi 1-4 in sequenza |
| `2026-04-29T00:00:00+02:00` | HANDOFF | 4 | Pausa volontaria utente dopo fase 4 validata, pronto per fase 5 |
| `2026-04-29T00:00:00+02:00` | RESUME | 5 | Ripresa, fasi 5-10 completate end-to-end |

## Checklist finale

Verifiche automatizzate (eseguite dall'orchestrator):

- [x] **Risk engine ha rifiutato almeno un trade per ogni branch.** Coperto da `tests/test_risk.py`: kill switch, SL stretto, SL largo, margine sotto minimo, sessione fuori orario.
- [x] **Logger registra 100% delle decisioni.** `execution.run_once` chiama `log_trade_decision` *prima* del branch shadow/paper, quindi anche i reject finiscono in `trades_log`.
- [x] **`pytest tests/`** verde con skip MT5 se non disponibile (9 passed, 4 skipped).
- [x] **`README.md` ha tutte le 13 sezioni** richieste dallo spec di Fase 10.

Verifiche manuali (richiedono ambiente live, demandate all'utente):

- [ ] **MCP server riconosciuto da Claude Desktop, 6 tool visibili** dopo registrazione in `claude_desktop_config.json` e riavvio dell'app.
- [ ] **`claude_agent.run_cycle` produce proposte coerenti senza loop infinito** — il bound dei 6 cicli è imposto da codice; resta da verificare che il modello rispetti la regola "propose_trade solo se confidence ≥ 0.6".
- [ ] **`explain_last_trades(5)` produce riassunto in italiano leggibile.**
- [ ] **Paper trading**: settare `EXECUTION_MODE=paper` su demo FP Markets e verificare che gli ordini approvati appaiano in MT5.

Quando le 4 voci manuali sono spuntate, l'orchestrator può:
- Eseguire `git tag -a v1.0.0 -m "Trading agent MVP ready for shadow testing"` e `git push origin v1.0.0`.
- Aggiornare `session_status` a `COMPLETED`.
