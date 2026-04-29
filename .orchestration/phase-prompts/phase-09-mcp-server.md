# FASE 9 — MCP Server + Claude Desktop

## Obiettivo
Esporre i tool del progetto via MCP, configurare Claude Desktop.

> ⚠️ Fase pesante in token. Prima di iniziare valuta handoff se hai già generato 4+ file in questa sessione.

## File da creare

### 1. `mcp_server.py`

**Versione di riferimento:**
- All'inizio del file, commento: `# Compatibile con mcp >= <versione installata>. Verificare API se aggiorni.`
- Usa l'API stabile della versione installata. Pattern tipico (SDK ufficiale Anthropic MCP Python):

```python
"""
mcp_server.py — Server MCP locale per trading-agent.
Compatibile con mcp SDK ufficiale (verificare versione in requirements.txt).
"""
import json
import logging
import sys
import dataclasses
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from config import Config
from logger import init_logger
from mt5_client import Mt5Client
from risk_engine import evaluate_trade
from execution import run_once
from indicators import compute_all
from models import TradeProposal

# IMPORTANTE: tutti i log su stderr o file, MAI stdout (rompe il protocollo MCP).
cfg = Config()
log = init_logger(cfg)
mt5 = Mt5Client(cfg)
mt5.initialize()
mt5.login()

server = Server("trading-agent")
```

**Tool MCP (nomi esatti):**

1. `get_account_state()` → `json.dumps(dataclasses.asdict(mt5.get_account_state()), default=str)`
2. `get_market_snapshot(symbol)` → `{ohlc: [...], tick: {...}, indicators: compute_all(ohlc)}`
3. `evaluate_trade_proposal(symbol, direction, entry_price, stop_loss_price, take_profit_price, confidence, rationale)`:
   - costruisce `TradeProposal`
   - chiama `evaluate_trade(proposal, account, mt5)`
   - ritorna `RiskDecision` serializzata
4. `submit_order_if_approved(...)`:
   - costruisce `TradeProposal`
   - chiama `execution.run_once(symbol, proposal, cfg, mt5, log)`
   - ritorna decision + order_result
5. `get_risk_profile()`:
   - dict con: `RISK_MODE, RISK_PER_TRADE_PERCENT, RISK_PER_TRADE_AMOUNT, RISK_PROFILE, MAX_DAILY_DRAWDOWN_PERCENT, MAX_LOTS_PER_TRADE, MIN_SL_PIPS, MAX_SL_PIPS, USE_SESSION_FILTER, SESSION_START_HOUR, SESSION_END_HOUR, EXECUTION_MODE`
6. `get_trade_history(n=10)` → SELECT da `trades.db`

Ogni tool registrato come `@server.tool()` (o equivalente nella versione installata) con:
- `name`, `description`, `inputSchema` JSON.
- Output sempre `list[TextContent(type="text", text=json.dumps(result, default=str))]` (o equivalente).

**Avvio:**
```python
async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    finally:
        mt5.shutdown()
```

**Vincoli stdio:**
- `print` solo su `sys.stderr`.
- `logging` configurato per scrivere su file `agent.log`, NON su stdout.

### 2. Sezione README.md (preview, completata in Fase 10)

Includere blocco JSON ESATTO da inserire in `%APPDATA%\Claude\claude_desktop_config.json`:

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

Spiegare:
- Path del file di config su Windows.
- Necessità di **riavviare Claude Desktop** completamente (kill da tray).
- Come verificare i tool: aprire Claude Desktop → icona tool → deve apparire `trading-agent` con i 6 tool.

## Checkpoint

1. Avvio manuale:
   ```powershell
   python mcp_server.py
   ```
   Non deve crashare. Su stderr deve apparire un log di inizializzazione.
2. Configurare Claude Desktop con il JSON, riavviare app.
3. Aprire una conversazione, chiedere: "Qual è il mio account state MT5?" → Claude chiama `get_account_state`.
4. Chiedere: "Valuta un BUY EURUSD con SL 30 pips e TP 60 pips" → Claude chiama `evaluate_trade_proposal`.

## Errori comuni
- Stampa su stdout → rompe il protocollo. Tutto su stderr.
- Path Python con spazi → usa percorso completo del `python.exe` del venv, doppio backslash nel JSON.
- Claude Desktop non rilegge la config → kill completo dalla tray e riavvio.
- `Mt5Client` inizializzato per ogni chiamata → usa singleton globale.
- API `mcp` cambiata → adatta. Documenta in cima la versione assunta.

## Commit attesi
```
feat(mcp): server stdio with 6 tools (account, snapshot, evaluate, submit, profile, history)
docs(readme): add claude desktop setup section with json config
feat(phase-9): complete and validated
```
