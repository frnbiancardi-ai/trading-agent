# trading-agent

Agente di trading locale che combina MetaTrader5 (FP Markets demo), un risk engine deterministico e un agente Claude (Anthropic SDK + tool use). Espone i propri tool anche via Model Context Protocol (MCP) per essere usato direttamente da Claude Desktop.

> **Stato:** in sviluppo — fasi 1-9 completate; fase 10 (E2E) in corso.

## Configurazione di Claude Desktop (server MCP)

Il server `mcp_server.py` espone 6 tool via MCP su stdio. Per registrarlo in Claude Desktop su Windows:

1. Apri (o crea) il file:

   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

2. Inserisci il blocco seguente (sostituisci i due path se il progetto è in una posizione diversa, e mantieni i doppi backslash):

   ```json
   {
     "mcpServers": {
       "trading-agent": {
         "command": "C:\\trading-agent\\.venv\\Scripts\\python.exe",
         "args": ["C:\\trading-agent\\mcp_server.py"],
         "env": {
           "PYTHONUNBUFFERED": "1"
         }
       }
     }
   }
   ```

3. Chiudi **completamente** Claude Desktop (anche dalla tray icon: tasto destro → Quit), poi riapri l'app. Il rilettura della config avviene solo all'avvio pulito.

4. Verifica: in una nuova conversazione, l'icona dei tool deve elencare `trading-agent` con i 6 tool:
   - `get_account_state`
   - `get_market_snapshot`
   - `evaluate_trade_proposal`
   - `submit_order_if_approved`
   - `get_risk_profile`
   - `get_trade_history`

5. Test rapido — prova a chiedere a Claude:
   - *"Qual è il mio account state MT5?"* → deve chiamare `get_account_state`.
   - *"Valuta un BUY EURUSD con SL 30 pip e TP 60 pip."* → deve chiamare `evaluate_trade_proposal` (richiede `entry_price` plausibile).

### Vincoli noti

- MT5 deve essere **installato e raggiungibile**: il server inizializza la connessione all'avvio. Senza credenziali valide in `.env`, le tool call ritornano errore (il server resta vivo).
- Il protocollo MCP usa stdio: **mai** stampare su stdout dal codice del server. Il logger del progetto scrive solo su `logs/agent.log` — sicuro.
- `EXECUTION_MODE=shadow` (default): `submit_order_if_approved` valuta la proposta e logga la decisione, ma NON invia ordini. Per inviare ordini su demo/paper trading: settare `EXECUTION_MODE=paper` in `.env`.

### Aggiornamenti della libreria `mcp`

Il file `mcp_server.py` è verificato contro `mcp == 1.27.0` (vedi commento in cima al file). Se aggiorni la dipendenza, controlla che le firme di `Server.list_tools()`, `Server.call_tool()`, `stdio_server()`, `Tool` e `TextContent` siano ancora compatibili.
