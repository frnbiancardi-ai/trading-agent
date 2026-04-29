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
- last_session_end: `<timestamp ISO>`
- last_session_reason: `<es: handoff per token, fase completata, errore bloccante>`

## Stato fase corrente

- current_phase: `3`
- current_phase_title: `MT5 Client`
- phase_status: `VALIDATED`  <!-- NOT_STARTED | IN_PROGRESS | VALIDATED -->
- current_substep: `1`
- last_action: `2026-04-29 — mt5_client.py creato; import OK; tzdata aggiunto a requirements (Windows zoneinfo); live test richiede MT5 demo attivo + credenziali .env`
- next_action: `Avvio Fase 4: risk_engine.py + tests/test_risk.py`

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
  status: NOT_STARTED
  files: []
  validated_at: null

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

## Configurazione runtime corrente

- EXECUTION_MODE: `shadow` (mai modificare a `live` prima di Fase 10 validata + 1 settimana di paper trading).
- RISK_PROFILE: `CONSERVATIVE`
- Symbols attivi: `EURUSD`

## Note di handoff

Compilato dall'orchestrator quando sospende la sessione.

- Ultimo file generato: `<nome>`
- Prossimo file da generare: `<nome>`
- Comando di ripresa: `<es: leggi phase-04-risk-engine.md sezione Specifiche, genera risk_engine.py>`
- Test pendenti: `<es: pytest tests/test_risk.py>`
- Rischi noti per la prossima sessione: `<es: pip_value su XAUUSD da rivalidare>`

## Cronologia sessioni

| Timestamp | Tipo | Fase | Descrizione |
|-----------|------|------|-------------|
| `<ISO>`   | BOOT | 1    | Sessione aperta, stato vergine |
