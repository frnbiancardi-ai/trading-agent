# Stato vivo del progetto trading-agent

Verità singola sullo stato corrente. Aggiornato dall'orchestrator dopo ogni micro-step. In caso di conflitto con git, vince questo file più l'ultimo commit pushato.

## Identità progetto

- Nome: trading-agent
- Path locale: `C:\trading-agent`
- Ambiente: Windows + Python 3.12+ + MetaTrader5 5.0.5735
- Broker: FP Markets (conto demo)
- Repo Git: `<da compilare al primo setup>`

## Stato sessione

- session_status: `HANDOFF`  <!-- IDLE | IN_PROGRESS | HANDOFF | BLOCKED | COMPLETED -->
- last_session_end: `2026-04-29T00:00:00+02:00`
- last_session_reason: `pausa volontaria utente, fase 4 completata`

## Stato fase corrente

- current_phase: `5`
- current_phase_title: `Logger`
- phase_status: `NOT_STARTED`  <!-- NOT_STARTED | IN_PROGRESS | VALIDATED -->
- current_substep: `0`
- last_action: `2026-04-29 — fase 4 (Risk Engine) completata e validata: pytest 9/9 verde`
- next_action: `Eseguire Fase 5 dal prompt .orchestration/phase-prompts/phase-05-logger.md, generare logger.py`

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
  status: NOT_STARTED
  files: []
  validated_at: null

phase_6_execution:
  status: NOT_STARTED
  files: []
  validated_at: null

phase_7_indicators:
  status: NOT_STARTED
  files: []
  validated_at: null

phase_8_claude_agent:
  status: NOT_STARTED
  files: []
  validated_at: null

phase_9_mcp_server:
  status: NOT_STARTED
  files: []
  validated_at: null

phase_10_e2e:
  status: NOT_STARTED
  files: []
  validated_at: null
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
