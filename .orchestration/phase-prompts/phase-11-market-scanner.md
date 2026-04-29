TITLE Fase 11 Market Scanner Multi-Symbol - Obiettivo

Evolvere l'agente da workflow single-symbol a workflow multi-symbol con shortlist, deep analysis e proposta finale di al massimo un trade. La fase deve lasciare il codebase funzionante e coerente con le fasi precedenti.

Vincoli:
- Non rompere `riskengine.py` ed `execution.py`.
- Non cambiare il ruolo del risk engine: resta l'unico cancello di approvazione.
- `EXECUTION_MODE` di default resta `shadow`.
- Nessun output su stdout nei componenti MCP.
- Nessun TODO, pseudocodice o placeholder incompleto nei file creati.

TITLE Fase 11 Market Scanner Multi-Symbol - File da creare o modificare

1. `prompts/system_prompt_scanner.txt`
2. `prompts/context_template_scanner.txt`
3. `claudeagent.py`
4. `models.py`
5. `tests/test_scanner.py`
6. opzionale se utile: `STATE.md` solo per tracking stato, mai per specifiche tecniche

TITLE Fase 11 Market Scanner Multi-Symbol - Ordine di esecuzione

1. Creare `prompts/system_prompt_scanner.txt`.
2. Creare `prompts/context_template_scanner.txt`.
3. Estendere `models.py` con eventuali modelli dati necessari al workflow scanner.
4. Modificare `claudeagent.py` per introdurre il flusso multi-symbol.
5. Aggiungere `tests/test_scanner.py`.
6. Aggiornare `STATE.md` dopo ogni micro-step come da orchestrator root prompt.

TITLE Fase 11 Market Scanner Multi-Symbol - Requisiti per prompts/system_prompt_scanner.txt

Il prompt deve:
- definire Claude come senior quantitative trader assistente di un risk engine deterministico;
- lavorare su un universo di simboli candidati, non su un solo simbolo;
- imporre il workflow: account state -> risk profile -> symbol universe -> cheap scan -> shortlist -> deep analysis -> max 1 trade -> evaluate -> eventuale submit;
- imporre fallback esplicito `NO_TRADE` se confidence < 0.60 o se il contesto è ambiguo;
- vietare più di un trade per ciclo;
- vietare dati inventati;
- richiedere rationale conciso in italiano basato solo sui dati osservati.

TITLE Fase 11 Market Scanner Multi-Symbol - Requisiti per prompts/context_template_scanner.txt

Deve usare placeholder espliciti almeno per:
- `{candidate_symbols}`
- `{timeframe}`
- `{now_local}`
- `{execution_mode}`
- `{min_sl_pips}`
- `{max_sl_pips}`
- `{max_symbols_to_deepen}`
- `{balance}`
- `{equity}`
- `{free_margin}`
- `{open_positions_count}`

Deve essere breve, operativo e adatto a rendering `.format(...)` in Python.

TITLE Fase 11 Market Scanner Multi-Symbol - Requisiti per models.py

Aggiungere solo se servono davvero, mantenendo compatibilità con il resto del progetto. Valutare modelli come:
- `SymbolScanCandidate`
- `ScannerDecision`
- `ScannerContext`

I modelli devono essere semplici, serializzabili e coerenti con l'approccio già usato nel progetto.

TITLE Fase 11 Market Scanner Multi-Symbol - Requisiti per claudeagent.py

Estendere `ClaudeAgent` senza rompere il flusso esistente single-symbol.

Aggiungere almeno:
- `build_scanner_tools(self) -> list[dict]`
- `run_market_scan(self, candidate_symbols: list[str], timeframe: str, account_state: AccountState) -> TradeProposal | None`
- eventuale helper `run_symbol_analysis(...)`

Requisiti di implementazione:
- massimo 8 iterazioni di tool use per il workflow scanner;
- massimo 5 simboli approfonditi;
- massimo 1 proposta finale;
- usare i nuovi prompt scanner senza rimuovere quelli esistenti single-symbol;
- output e tool results sempre JSON-serializzabili;
- logging sintetico ma sufficiente al debug;
- mantenere backward compatibility con `run_cycle(...)` se già usato da altre parti del progetto.

TITLE Fase 11 Market Scanner Multi-Symbol - Requisiti per tests/test_scanner.py

Casi minimi:
- scan con shortlist coerente;
- nessun candidato valido -> ritorna None / NO_TRADE a seconda del design esistente;
- un solo candidato valido -> una sola proposta;
- nessun caso deve produrre più di una trade proposal;
- il loop deve rispettare il limite massimo di iterazioni.

Usare mock per Anthropic client e/o dispatch tool dove necessario.

TITLE Fase 11 Market Scanner Multi-Symbol - Checkpoint

Comando di checkpoint:

```powershell
pytest tests/test_scanner.py -v
```

Se fallisce:
- non marcare la fase come VALIDATED;
- correggere il file responsabile;
- rieseguire il checkpoint.

TITLE Fase 11 Market Scanner Multi-Symbol - Errori comuni

- Rompere `run_cycle(...)` single-symbol invece di aggiungere il nuovo flusso.
- Riutilizzare il vecchio context template senza placeholder multi-symbol.
- Generare payload troppo grandi in tool results.
- Restituire più di una proposta finale.
- Dimenticare il fallback `NO_TRADE`.
- Introdurre dipendenze nuove non consentite.

TITLE Fase 11 Market Scanner Multi-Symbol - Commit attesi

- `docs(prompts): add scanner system and context templates`
- `feat(agent): add multi-symbol scanner workflow`
- `test(agent): add scanner workflow tests`
- `feat(phase-11): complete and validated`
