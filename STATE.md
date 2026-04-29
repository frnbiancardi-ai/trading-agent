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
- last_session_end: `2026-04-29T22:30:00+02:00`
- last_session_reason: `Fase 12 (MCP Tools Upgrade) completata e validata. In attesa conferma utente per procedere con fase 13 (Scheduled Orchestrator).`

## Stato fase corrente

- current_phase: `13`
- current_phase_title: `Scheduled Orchestrator`
- phase_status: `IN_PROGRESS`  <!-- NOT_STARTED | IN_PROGRESS | VALIDATED -->
- current_substep: `0`
- last_action: `2026-04-29 — Fase 12 pushata (commit 0293f6e). Avviata fase 13 con conferma utente. Decisioni: DailyRunState persistito in SQLite (tabella daily_run_state in logs/trades.db); PHASES.md non aggiornato in questa fase.`
- next_action: `Aggiornare requirements.txt (+apscheduler), .env.example, config.py con parametri scheduler. Estendere models.py con DelayedFollowUpRequest/AgentCycleOutcome/DailyRunState. Aggiornare prompts scanner per follow-up. Estendere claude_agent.py con outcome WAIT_FOLLOW_UP. Creare scheduler.py (BlockingScheduler + persistenza SQLite). Riscrivere main.py come daemon. Test scheduler + daily orchestrator.`

## Roadmap v1.1.0 (residua, NOT_STARTED)

- **Fase 13 — Scheduled Orchestrator**: trasforma `main.py` in daemon continuo. APScheduler con cron lun-ven 08-22, slot 08/11/14/17/20 (ogni 3h), follow-up one-shot (delay max 120 min, una volta per opportunità), target giornaliero 5 decisioni finali. Nuovi file: `scheduler.py`, `models.py` esteso (`DelayedFollowUpRequest`, `AgentCycleOutcome`, `DailyRunState`), test `tests/test_scheduler.py` e `tests/test_daily_orchestrator.py`. Risponde alla domanda architetturale sull'autonomia.

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

phase_11_market_scanner:
  status: VALIDATED
  files:
    - prompts/system_prompt_scanner.txt
    - prompts/context_template_scanner.txt
    - models.py             # aggiunti SymbolScanCandidate, ScannerDecision
    - claude_agent.py       # aggiunti build_scanner_tools, run_market_scan, _cheap_scan_one, _dispatch_scanner_tool
    - tests/test_scanner.py
  validated_at: "2026-04-29"
  notes:
    - "Workflow scanner: account state → risk profile → cheap scan → shortlist (max MAX_SYMBOLS_TO_DEEPEN=5 default) → deep analysis → max 1 propose_trade"
    - "Backward compat: run_cycle single-symbol resta intatto, system_prompt.txt e context_template.txt non modificati"
    - "Anthropic client + Mt5Client mockati nei test, 11 test scanner verdi in 7s. Suite completa 24/24 passed."
    - "MAX_SYMBOLS_TO_DEEPEN letto da Config se presente (cfg.MAX_SYMBOLS_TO_DEEPEN), altrimenti default 5. Sarà reso obbligatorio in fase 13 via .env."

phase_12_mcp_tools_upgrade:
  status: VALIDATED
  files:
    - claude_agent.py       # cheap_scan_symbol estratta come funzione modulo riusabile
    - mcp_server.py         # 4 nuovi tool + handler functions + _bootstrap_mt5 (init lazy, no MT5 all'import)
    - tests/test_mcp_tools_v2.py
  validated_at: "2026-04-29"
  notes:
    - "Nuovi tool MCP: get_symbol_universe, scan_symbol_candidates, get_symbol_indicators, propose_trade. I 6 tool legacy preservati."
    - "propose_trade NON esegue ordini, NON decide size: ritorna proposal echo + status='proposed'/executed=False. Per agire usare evaluate_trade_proposal o submit_order_if_approved."
    - "_bootstrap_mt5() chiamato solo da __main__ block: import del modulo non blocca senza terminale MT5 (importante per i test)."
    - "Suite completa 39/39 passed (4 mt5 + 9 risk + 11 scanner + 15 mcp v2)."
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

- Ultimo file generato: `tests/test_mcp_tools_v2.py` (fase 12). Tag attivo: `v1.0.0` (fasi 11-12 non ancora taggate).
- Prossimo file da generare: dipende dalla scelta utente. Se procede fase 13: `requirements.txt` (+apscheduler), `config.py` esteso (parametri env scheduler), `models.py` esteso (DelayedFollowUpRequest, AgentCycleOutcome, DailyRunState).
- Comando di ripresa fase 13: `leggi .orchestration/phase-prompts/phase-13-scheduled-orchestrator.md, aggiungi apscheduler, estendi config/models, riscrivi main.py come daemon, scrivi tests`.
- Test pendenti: nessuno (suite completa post-fase-12: 39/39 passed).
- Rischi noti per la prossima sessione:
  - `PHASES.md` non contiene ancora le fasi 11-12-13. Aggiornare per coerenza, idealmente prima della fine di fase 13.
  - La fase 13 introduce `apscheduler` (o equivalente) come nuova dipendenza: aggiungere a `requirements.txt`.
  - La fase 13 ridefinisce `main.py`: da single-shot a daemon continuo. Verificare che i test esistenti non si rompano.
  - Persistenza di `DailyRunState` tra restart per fase 13: decisione aperta (default proposto: in-memory v1.1.0, SQLite in v1.2.0).
  - `MAX_SYMBOLS_TO_DEEPEN` non è ancora in `config.py`/`.env.example`: in fase 13 va aggiunto come parametro env obbligatorio (lo scanner attuale legge fallback hardcodato 5).

## Cronologia sessioni

| Timestamp | Tipo | Fase | Descrizione |
|-----------|------|------|-------------|
| `2026-04-29T00:00:00+02:00` | BOOT | 1 | Sessione aperta, completate fasi 1-4 in sequenza |
| `2026-04-29T00:00:00+02:00` | HANDOFF | 4 | Pausa volontaria utente dopo fase 4 validata, pronto per fase 5 |
| `2026-04-29T00:00:00+02:00` | RESUME | 5 | Ripresa, fasi 5-10 completate end-to-end |
| `2026-04-29T18:30:00+02:00` | COMPLETED | 10 | Validazione live OK, tag v1.0.0 rilasciato |
| `2026-04-29T20:00:00+02:00` | HANDOFF | 11 | Pianificate fasi 11-12-13 (roadmap v1.1.0). Esecuzione rinviata. |
| `2026-04-29T21:30:00+02:00` | RESUME | 11 | Fase 11 (Market Scanner) completata e validata, suite 24/24. |
| `2026-04-29T22:30:00+02:00` | RESUME | 12 | Fase 12 (MCP Tools Upgrade) completata e validata, suite 39/39. |

## Checklist finale

Verifiche automatizzate (eseguite dall'orchestrator):

- [x] **Risk engine ha rifiutato almeno un trade per ogni branch.** Coperto da `tests/test_risk.py`: kill switch, SL stretto, SL largo, margine sotto minimo, sessione fuori orario.
- [x] **Logger registra 100% delle decisioni.** `execution.run_once` chiama `log_trade_decision` *prima* del branch shadow/paper, quindi anche i reject finiscono in `trades_log`.
- [x] **`pytest tests/`** verde con skip MT5 se non disponibile (9 passed, 4 skipped).
- [x] **`README.md` ha tutte le 13 sezioni** richieste dallo spec di Fase 10.

Verifiche manuali (eseguite in Claude Desktop con MT5 demo vivo):

- [x] **MCP server riconosciuto da Claude Desktop, 6 tool visibili** — confermato 2026-04-29 con permission gate "always/never" per tool.
- [x] **Loop tool use coerente senza ricorsione infinita** — Claude Desktop ha orchestrato `get_account_state` + `evaluate_trade_proposal` + `submit_order_if_approved` + `get_trade_history` in chiamate successive senza loop, producendo decisioni allineate al risk engine.
- [x] **Spiegazione in italiano leggibile** — confermato con prompt "spiegami l'ultimo trade": Claude ha prodotto riepilogo strutturato (R:R, conversione pip→USD, stato shadow). Funzionalmente equivalente a `explain_last_trades(5)`.
- [x] **`submit_order_if_approved` rispetta EXECUTION_MODE=shadow** — confermato: riga inserita in `trades_log` (3 righe totali), nessun ordine a MT5, response include `"execution_mode": "shadow"`.

Verifiche differite (gate futuri, non bloccanti per v1.0.0):

- [ ] **Paper trading** — `EXECUTION_MODE=paper` su demo FP Markets dopo ≥ 1 settimana di shadow. Quando eseguito, bumpare a v1.0.1/v1.1.0.
- [ ] **Live trading** — solo dopo ≥ 1 settimana di paper validato. Richiede revisione di `RISK_PER_TRADE_PERCENT`, `MAX_DAILY_DRAWDOWN_PERCENT`, `MAX_LOTS_PER_TRADE`.

Tag rilasciato: `v1.0.0` (`Trading agent MVP ready for shadow testing`).
