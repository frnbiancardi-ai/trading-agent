TITLE Fase 12 MCP Tools Upgrade - Obiettivo

Estendere il server MCP per supportare uno scanner multi-symbol agentico e robusto, mantenendo compatibilità con i tool esistenti già usati da Claude Desktop e dal progetto.

Vincoli:
- Nessun output su stdout: solo stderr o file log.
- Non rompere i tool esistenti se non strettamente necessario.
- Output di tutti i tool sempre JSON-serializzabili.
- Input schema chiari, piatti, piccoli e coerenti con MCP.
- Nessun bypass del risk engine.

TITLE Fase 12 MCP Tools Upgrade - File da creare o modificare

1. `mcpserver.py`
2. `models.py`
3. `tests/test_mcp_tools_v2.py`
4. opzionale: `README.md` o sezione docs solo se necessario a documentare i nuovi tool
5. `STATE.md` solo per tracking stato, non per specifiche tecniche

TITLE Fase 12 MCP Tools Upgrade - Ordine di esecuzione

1. Analizzare `mcpserver.py` esistente e mappare i tool attuali.
2. Estendere `models.py` se servono modelli dati serializzabili per scan/proposal.
3. Aggiungere in `mcpserver.py` i nuovi tool.
4. Verificare che i tool esistenti continuino a funzionare.
5. Aggiungere `tests/test_mcp_tools_v2.py`.
6. Aggiornare `STATE.md` dopo ogni micro-step come da orchestrator root prompt.

TITLE Fase 12 MCP Tools Upgrade - Nuovi tool richiesti

Implementare almeno questi tool:

1. `get_symbol_universe`
- Restituisce l'universo dei simboli candidati, eventualmente filtrato per watchlist, asset class o sessione.
- Output compatto: lista simboli, count, source.

2. `scan_symbol_candidates`
- Esegue scan preliminare leggero su più simboli.
- Deve restituire metriche sintetiche, non OHLC completi salvo stretta necessità.
- Campi suggeriti per candidato:
  - `symbol`
  - `trend_bias`
  - `momentum_bias`
  - `volatility_state`
  - `spread_state`
  - `regime`
  - `candidate_score`
  - `warnings`

3. `get_symbol_indicators`
- Restituisce indicatori approfonditi per un singolo simbolo e timeframe.
- Deve essere il tool di deep analysis dedicato.

4. `propose_trade`
- Formalizza la proposta finale dell'agente.
- Non esegue ordini.
- Non decide la size.
- Deve accettare almeno:
  - `symbol`
  - `timeframe`
  - `direction`
  - `entry_price`
  - `stop_loss_price`
  - `take_profit_price`
  - `confidence`
  - `rationale`

TITLE Fase 12 MCP Tools Upgrade - Requisiti per mcpserver.py

- Mantenere compatibilità con l'SDK MCP installato e documentare in testa al file la versione assunta se necessario.
- Ogni tool deve avere:
  - `name`
  - `description`
  - `inputSchema` valido
- Ogni output deve essere restituito come contenuto testuale JSON serializzato.
- Nessuna eccezione grezza su stdout.
- Errori utili al modello: messaggi chiari, corti e diagnostici.

I tool esistenti da preservare sono almeno:
- `get_account_state`
- `get_market_snapshot`
- `evaluate_trade_proposal`
- `submit_order_if_approved`
- `get_risk_profile`
- `get_trade_history`

TITLE Fase 12 MCP Tools Upgrade - Requisiti per tests/test_mcp_tools_v2.py

Casi minimi:
- tools/list contiene i nuovi tool;
- ogni nuovo tool restituisce output JSON-serializzabile;
- `scan_symbol_candidates` restituisce payload compatto e stabile;
- `propose_trade` crea una proposta valida senza eseguire il trade;
- retrocompatibilità minima dei tool esistenti non regressa.

Usare mock dove necessario per non dipendere da MT5 reale nei test unitari.

TITLE Fase 12 MCP Tools Upgrade - Checkpoint

Comando di checkpoint:

```powershell
pytest tests/test_mcp_tools_v2.py -v
```

Se fallisce:
- non marcare la fase come VALIDATED;
- correggere i file responsabili;
- rieseguire il checkpoint.

TITLE Fase 12 MCP Tools Upgrade - Errori comuni

- Confondere `propose_trade` con `submit_order_if_approved`.
- Fare scan multi-symbol con payload enormi.
- Restituire oggetti non serializzabili.
- Usare stdout e rompere il protocollo MCP.
- Rinominare i tool legacy rompendo Claude Desktop.
- Rendere `scan_symbol_candidates` troppo costoso o troppo verboso.

TITLE Fase 12 MCP Tools Upgrade - Commit attesi

- `feat(mcp): add symbol universe and scanner tools`
- `feat(mcp): add propose_trade and deep indicator tool`
- `test(mcp): add tests for v2 tools`
- `feat(phase-12): complete and validated`
