# Prompt per Claude Code

Sei un senior AI engineer e quantitative systems architect. Devi modificare questo progetto Python/MCP per evolverlo da single-symbol trading agent a multi-symbol market scanner più agentico e robusto.

## Contesto del progetto
Il progetto attuale è organizzato in fasi e contiene già:
- `riskengine.py` come gate deterministico
- `execution.py` come layer di esecuzione
- `claudeagent.py` con workflow single-symbol
- `mcpserver.py` con tool MCP orientati più all'execution che allo scanning
- prompt in `prompts/system_prompt.txt` e `prompts/context_template.txt`

## Obiettivo
Implementa le modifiche necessarie per supportare questo workflow:
1. leggere account state e risk profile
2. ottenere universo simboli candidati
3. fare una scansione preliminare multi-symbol leggera
4. selezionare automaticamente i migliori candidati
5. fare deep analysis solo sui migliori
6. proporre al massimo un singolo trade
7. farlo valutare dal risk engine
8. inviare l'ordine solo se approvato

## File di riferimento già preparati
Usa e integra questi nuovi file di progetto:
- `prompts/system_prompt_scanner.txt`
- `prompts/context_template_scanner.txt`
- `schemas/mcp_tools_v2.json`
- `schemas/scanner_output_schema.json`
- `docs/phase-11-market-scanner.md`
- `docs/phase-12-mcp-tools-upgrade.md`

## Implementazioni richieste
1. estendi `claudeagent.py` con un workflow scanner multi-symbol
2. estendi `mcpserver.py` con i nuovi tool:
   - `get_symbol_universe`
   - `scan_symbol_candidates`
   - `get_symbol_indicators`
   - `propose_trade`
3. aggiorna `models.py` se servono nuovi modelli dati
4. aggiorna `main.py` se necessario per passare watchlist/timeframe corretti
5. aggiungi test minimi per scanner e MCP tools
6. mantieni compatibilità con i tool e i flussi esistenti dove ragionevole

## Vincoli tecnici
- non rompere `riskengine.py` ed `execution.py`
- niente output su stdout nel server MCP
- output dei tool sempre JSON serializzabile
- input schema semplici, piatti e chiari
- nessun payload eccessivo nello scan preliminare
- max 1 trade proposto per ciclo
- fallback NO_TRADE in caso di dubbio

## Cosa voglio in output da te
- piano sintetico delle modifiche
- patch reali ai file del progetto
- breve spiegazione finale dei file modificati
- istruzioni per testare localmente

## Importante
Non limitarti a descrivere: modifica davvero il codice del progetto.
Favorisci semplicità, robustezza, osservabilità e backward compatibility.
