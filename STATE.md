# STATE.md — Stato vivo del progetto trading-agent

> **Verità singola** del progetto. Aggiornato dall'Orchestrator dopo ogni micro-step.
> Se in conflitto con git: vince questo file + ultimo commit pushato.
> Non modificare a mano se non sai cosa fai.

---

## Identità progetto

- **Nome**: trading-agent
- **Path locale**: `C:\trading-agent`
- **Ambiente**: Windows + Python 3.12+ + MetaTrader5 5.0.5735
- **Broker**: FP Markets (conto demo)
- **Repo Git**: `<da compilare al primo setup>`

## Stato sessione

- **session_status**: `IDLE` <!-- IDLE | IN_PROGRESS | HANDOFF | BLOCKED -->
- **last_session_end**: `<timestamp ISO>`
- **last_session_reason**: `<es: handoff per token, fase completata, errore bloccante>`

## Stato fase

- **current_phase**: `1`
- **current_phase_title**: `Setup ambiente`
- **phase_status**: `NOT_STARTED` <!-- NOT_STARTED | IN_PROGRESS | VALIDATED -->
- **current_substep**: `0`
- **last_action**: `<timestamp ISO> — <descrizione 1 riga>`
- **next_action**: `Eseguire Fase 1 dal prompt phase-prompts/phase-01-setup.md`

## File completati per fase

```yaml
phase_1_setup:
  status: NOT_STARTED
  files: []
  validated_at: null

phase_2_config_models:
  status: NOT_STARTED
  files: []
  validated_at: null

phase_3_mt5_client:
  status: NOT_STARTED
  files: []
  validated_at: null

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

> Annota qui ambiguità tecniche, scelte rinviate, dipendenze esterne da verificare.

- [ ] Versione esatta della libreria `mcp` da usare (verificare API stabile al momento del setup).
- [ ] Path Python venv su Windows da inserire nel `claude_desktop_config.json` (dipende dall'username).

## Configurazione runtime corrente

- **EXECUTION_MODE**: `shadow` (mai modificare a `live` prima di Fase 10 validata + 1 settimana di paper).
- **RISK_PROFILE**: `CONSERVATIVE`
- **Symbols attivi**: `EURUSD`

## Note di handoff

> Compilato dall'Orchestrator quando sospende la sessione.

- **Ultimo file generato**: `<nome>`
- **Prossimo file da generare**: `<nome>`
- **Comando di ripresa**: `<es: leggi phase-prompts/phase-04-risk-engine.md sezione 'Specifiche', genera risk_engine.py>`
- **Test pendenti**: `<es: pytest tests/test_risk.py>`
- **Rischi noti per la prossima sessione**: `<es: pip_value su XAUUSD da rivalidare>`

## Cronologia sessioni

> Append-only. L'Orchestrator aggiunge una riga ad ogni boot e ad ogni handoff.

| Timestamp | Tipo | Fase | Descrizione |
|-----------|------|------|-------------|
| `<ISO>`   | BOOT | 1    | Sessione aperta, stato vergine |
