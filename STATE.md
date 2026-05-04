# Stato vivo del progetto trading-agent

Verità singola sullo stato corrente. Aggiornato dall'orchestrator dopo ogni micro-step. In caso di conflitto con git, vince questo file più l'ultimo commit pushato.

## Identità progetto

- Nome: trading-agent
- Path locale: `C:\trading-agent`
- Ambiente: Windows + Python 3.12+ + MetaTrader5 5.0.5735
- Broker: TenTrade (conto demo)
- Repo Git: `<da compilare al primo setup>`

## Stato sessione

- session_status: `IN_PROGRESS`  <!-- IDLE | IN_PROGRESS | HANDOFF | BLOCKED | COMPLETED -->
- last_session_start: `2026-05-04T...` (resumed from context compaction)
- last_session_reason: `Continuazione fase 17 implementation da contesto precedente. 17.4, 17.5, 17.6 code-complete e pushed.`

## Stato fase corrente

- current_phase: `17`
- current_phase_title: `Strategy v2 Defendi (multi-setup: squeeze, pullback, MTF, divergence, position mgmt, backtest)`
- phase_status: `IN_PROGRESS`  <!-- NOT_STARTED | IN_PROGRESS | VALIDATED -->
- current_substep: `17.6_code_complete` (17.7 calibration skeleton started)
- branch: `feature/strategy-v2-defendi` (branch da main v1.2.0)
- last_action: `2026-05-04 — Fase 17.4 completed: _compute_mtf_bias() + _score_confidence(h1_bias) integration, divergence veto. Fase 17.5 completed: position_manager.py (BE move, partial close, trailing), models.py esteso (PositionInfo flags, OpenPositionVerdict actions), Mt5Client.modify_position/partial_close. Fase 17.6 completed: backtest.py (BacktestMt5Client, BacktestEngine, metrics), tests. All 3 phases committed + pushed.`
- next_action: `Fase 17.7 calibration + validation: (1) Historical data download script (scripts/download_historical.py — TBD); (2) Grid-search su params chiave (MIN_TREND_STRENGTH, MIN_BREAKOUT_VOLUME_RATIO, MIN_RISK_REWARD_RATIO, BREAKEVEN_TRIGGER_R, BB_SQUEEZE_PERCENTILE); (3) Backtest v1.2.0 vs v2 su 6m EURUSD+GBPUSD; (4) Pareto-optimal selection; (5) PHASE_17_VALIDATION.md report; (6) Merge decision (v2 vs v1.2.0 >=2 metrics). Stimato: 3-4 giorni (dipende da download dati storici).`

## Roadmap v1.1.0 (completata)

- **Fase 13 — Scheduled Orchestrator**: VALIDATED. `main.py` daemon con APScheduler (cron lun-ven, slot 08/11/14/17/20 every MAIN_CYCLE_HOURS), follow-up one-shot via DateTrigger (max 1 per opportunità, delay clampato 1-120 min), target giornaliero 5 decisioni persistito in SQLite (tabella `daily_run_state`).

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

phase_13_scheduled_orchestrator:
  status: VALIDATED
  files:
    - requirements.txt              # +apscheduler
    - .env.example                  # +12 variabili scheduler/daily orchestrator
    - config.py                     # OPERATING_*, MAIN_CYCLE_HOURS, DAILY_TARGET_DECISIONS, MAX_DELAY_MINUTES, MAX_SYMBOLS_TO_DEEPEN, FOLLOWUP_ENABLED, SCHEDULER_POLL_SECONDS
    - models.py                     # DelayedFollowUpRequest, AgentCycleOutcome, DailyRunState
    - prompts/system_prompt_scanner.txt    # outcome TRADE/NO_TRADE/WAIT_FOLLOW_UP, request_followup
    - prompts/context_template_scanner.txt # placeholder followup_mode/symbol/delay/focus_prompt
    - claude_agent.py               # request_followup tool, run_market_cycle, _run_market_scan_internal con outcome strutturato + clamp delay
    - scheduler.py                  # OperatingWindow, DailyRunStateStore (SQLite), Orchestrator, build_scheduler (CronTrigger + DateTrigger)
    - main.py                       # daemon: signal handlers + BlockingScheduler.start()
    - tests/test_scheduler.py
    - tests/test_daily_orchestrator.py
  validated_at: "2026-04-30"
  notes:
    - "Slot ordinari cron: range(START_HOUR, END_HOUR, MAIN_CYCLE_HOURS) → con default 8/22/3 = [8,11,14,17,20]; OPERATING_END_HOUR esclusivo."
    - "DailyRunStateStore persiste in SQLite tabella daily_run_state, db_path = parent(LOG_FILE)/trades.db (stessa di trades_log)."
    - "WAIT_FOLLOW_UP non incrementa decisions_count; il follow-up cycle (TRADE o NO_TRADE) chiude la pratica con +1."
    - "Una opportunità (date, symbol) può essere ritardata al massimo una volta al giorno (set Orchestrator._followup_done in-memory). Una seconda WAIT sullo stesso simbolo viene downgradata a NO_TRADE."
    - "FOLLOWUP_ENABLED=false → WAIT_FOLLOW_UP downgrade automatico a NO_TRADE (testato)."
    - "Delay clampato a [1, MAX_DELAY_MINUTES] lato ClaudeAgent prima di costruire DelayedFollowUpRequest. Test verifica clamp 999→120."
    - "Lock anti-overlap (threading.Lock + _cycle_active) protegge da run concorrenti su stesso Orchestrator."
    - "main.py daemon: signal.SIGINT/SIGTERM → scheduler.shutdown(wait=False) + mt5.shutdown() in finally."
    - "Suite completa 72/72 passed (4 mt5 + 9 risk + 11 scanner + 15 mcp v2 + 24 scheduler + 9 daily_orchestrator)."
    - "Live checkpoint (lanciare python main.py su demo FP Markets per ≥1 giornata operativa) demandato all'utente; non eseguito in ambiente CI."
```

## Decisioni aperte

(nessuna)

## Decisioni di fase 14 (risolte 2026-04-30)

- **A — Cadenza scheduler intraday**: ciclo ogni `INTRADAY_CYCLE_MINUTES=5` minuti per tutta la finestra operativa lun-ven 08:00-22:00. CronTrigger con `minute=*/5`, `hour=START_HOUR..END_HOUR-1`, `day_of_week=0-4`. `MAIN_CYCLE_HOURS` deprecato (commentato in .env.example).
- **B — claude_agent.py**: ridotto a sola `explain_last_trades` (post-trade explanation opzionale). `cheap_scan_symbol` spostato in `scanner.py`.
- **C — mcp_server.py**: mantiene i 10 tool v2 invariati. Import di `cheap_scan_symbol` migra da `claude_agent` a `scanner`. Tool che dipendono dal workflow Claude scanner (es. `evaluate_trade_proposal`) restano: continuano a funzionare via `risk_engine` direttamente.
- **D — tests/test_scanner.py**: sostituito completamente con test su `MultiSymbolScanner` Python. Vecchi test Claude scanner workflow rimossi (workflow obsoleto).
- **E — PHASES.md**: aggiornato a fine fase 15 (un solo commit di docs roadmap v1.2.0).
- **F — Smoke test**: prima del checkpoint, eseguo `scripts/smoke_test.py` che esegue 1 ciclo `Orchestrator.execute_ordinary_cycle()` in shadow. Se MT5 non disponibile, skippa graceful con exit 0.

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

- Ultimo file generato: `PHASES.md` (aggiornato con fasi 11-12-13). Tag attivi: `v1.0.0`, `v1.1.0`. Roadmap v1.1.0 chiusa e taggata.
- Prossimo file da generare: nessuno. Eventuali next step (non bloccanti):
  - live checkpoint del daemon su demo FP Markets per ≥1 giornata operativa (`python main.py` con MT5 vivo);
  - eventuale roadmap v1.2.0 (es. paper trading sustain, persistenza `_followup_done` in SQLite, dashboard log).
- Test pendenti: nessuno (suite completa post-fase-13: 72/72 passed).
- Rischi noti per la prossima sessione:
  - `PHASES.md` non contiene ancora le fasi 11-12-13.
  - DailyRunStateStore persiste lo stato giornaliero su SQLite, ma il set in-memory `Orchestrator._followup_done` (anti-doppio-rinvio per opportunità) si azzera ad ogni restart del daemon: in pratica accettabile (giornata corta), eventualmente promovibile a tabella SQLite in v1.2.0.
  - `main.py` ora è bloccante: lanciarlo richiede una sessione persistente; per shutdown pulito usare `Ctrl+C` (SIGINT) o `SIGTERM`.

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
| `2026-04-30T18:00:00+02:00` | RESUME | 13 | Fase 13 (Scheduled Orchestrator) completata e validata, suite 72/72. Roadmap v1.1.0 chiusa. |
| `2026-04-30T18:30:00+02:00` | COMPLETED | 13 | PHASES.md aggiornato con fasi 11-12-13. Tag `v1.1.0` rilasciato su `main`. |

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
