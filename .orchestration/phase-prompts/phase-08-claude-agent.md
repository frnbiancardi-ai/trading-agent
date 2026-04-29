# FASE 8 — Claude Agent + Tool Use REALE

## Obiettivo
Agent che chiama Claude API in loop tool use e produce TradeProposal strutturata.

> ⚠️ Fase pesante in token. Dopo `prompts/system_prompt.txt` e `prompts/context_template.txt`, valuta handoff prima di `claude_agent.py`.

## File da creare

### 1. `prompts/system_prompt.txt`

In italiano. Deve specificare:
- Ruolo: senior quantitative trader, assistente di un risk engine deterministico.
- Il risk engine è la legge: tu (Claude) **proponi**, lui valida.
- Vincoli: rispettare MIN/MAX SL pips configurati, mai forzare contro trend chiaro, sempre razionale conciso.
- Workflow: 1) chiama `get_account_status`, 2) chiama `get_market_snapshot`, 3) chiama `get_indicators`, 4) decidi.
- Output: chiama `propose_trade` solo se conviction ≥ 0.6, altrimenti rispondi testualmente "NO_TRADE" senza chiamare tool.
- Limiti: max 6 iterazioni di tool use.

### 2. `prompts/context_template.txt`

Placeholders: `{symbol}`, `{timeframe}`, `{execution_mode}`, `{balance}`, `{equity}`, `{free_margin}`, `{open_positions_count}`, `{now_local}`.

Esempio:
```
Analizza un possibile trade su {symbol} timeframe {timeframe}.
Ora locale: {now_local}. Modalità esecuzione: {execution_mode}.
Account: balance={balance}, equity={equity}, free_margin={free_margin}, posizioni aperte={open_positions_count}.
Usa i tool per ottenere snapshot di mercato e indicatori, poi decidi se proporre un trade.
```

### 3. `claude_agent.py`

**Import:**
- `from anthropic import Anthropic`
- `import json, os, sqlite3, dataclasses`
- `from datetime import datetime`
- `from zoneinfo import ZoneInfo`

**Classe `ClaudeAgent`:**
```python
class ClaudeAgent:
    def __init__(self, cfg: Config, mt5_client: Mt5Client, logger: logging.Logger):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger
        self.client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
        with open("prompts/system_prompt.txt", encoding="utf-8") as f:
            self.system_prompt = f.read()
        with open("prompts/context_template.txt", encoding="utf-8") as f:
            self.context_template = f.read()
        self.tools = self._build_tools()

    def _build_tools(self) -> list[dict]:
        # JSON schema Anthropic per get_market_snapshot, get_account_status, get_indicators, propose_trade
        ...

    def _dispatch_tool(self, name: str, input_: dict) -> dict:
        # mappa name → metodo Python che ritorna dict serializzabile
        ...

    def run_cycle(self, symbol: str, account_state: AccountState) -> TradeProposal | None:
        # 1. costruisce messaggio iniziale dal context_template
        # 2. loop max 6 iterazioni
        # 3. ritorna TradeProposal o None
        ...

    def explain_last_trades(self, n: int = 5) -> str:
        # SELECT ultime N righe da trades.db, prompt italiano, chiamata Claude senza tools
        ...
```

**Schema tool (esempio per propose_trade):**
```python
{
    "name": "propose_trade",
    "description": "Proponi un trade al risk engine. Verrà valutato deterministicamente.",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "direction": {"type": "string", "enum": ["BUY", "SELL"]},
            "entry_price": {"type": "number"},
            "stop_loss_price": {"type": "number"},
            "take_profit_price": {"type": "number"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"}
        },
        "required": ["symbol", "direction", "entry_price", "stop_loss_price", "take_profit_price", "confidence", "rationale"]
    }
}
```

**Loop tool use (sketch):**
```python
messages = [{"role": "user", "content": context}]
for i in range(6):
    response = self.client.messages.create(
        model=self.cfg.CLAUDE_MODEL,
        max_tokens=self.cfg.CLAUDE_MAX_TOKENS,
        temperature=self.cfg.CLAUDE_TEMPERATURE,
        system=self.system_prompt,
        tools=self.tools,
        messages=messages,
    )
    if response.stop_reason != "tool_use":
        return None  # NO_TRADE
    # accoda assistant content
    messages.append({"role": "assistant", "content": response.content})
    # processa ogni tool_use block
    tool_results = []
    proposal = None
    for block in response.content:
        if block.type == "tool_use":
            if block.name == "propose_trade":
                proposal = TradeProposal(
                    symbol=block.input["symbol"],
                    direction=block.input["direction"],
                    entry_price=block.input["entry_price"],
                    stop_loss_price=block.input["stop_loss_price"],
                    take_profit_price=block.input["take_profit_price"],
                    timeframe=self.cfg.TIMEFRAME,
                    comment="claude",
                    confidence=block.input["confidence"],
                    rationale=block.input["rationale"],
                )
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                     "content": json.dumps({"received": True})})
            else:
                result = self._dispatch_tool(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                     "content": json.dumps(result, default=str)})
    messages.append({"role": "user", "content": tool_results})
    if proposal:
        return proposal
return None
```

**Dispatch tool:**
- `get_market_snapshot` → `mt5.get_ohlc(symbol, cfg.TIMEFRAME, 50)` + `mt5.get_symbol_info(symbol)` (prendi ultimo tick)
- `get_account_status` → `dataclasses.asdict(account_state)`
- `get_indicators` → `compute_all(get_ohlc(symbol, tf, 100))`

**`explain_last_trades`:**
- Connetti a `cfg.LOG_DB_PATH`, `SELECT * FROM trades_log ORDER BY id DESC LIMIT n`
- Costruisci prompt: "Spiega in italiano queste decisioni di trading: <json delle righe>"
- `client.messages.create(...)` SENZA tools
- Ritorna `response.content[0].text`

## Checkpoint
```powershell
python -c "
from config import Config
from logger import init_logger
from mt5_client import Mt5Client
from claude_agent import ClaudeAgent
cfg = Config(); log = init_logger(cfg)
mt5 = Mt5Client(cfg); mt5.initialize(); mt5.login()
agent = ClaudeAgent(cfg, mt5, log)
proposal = agent.run_cycle('EURUSD', mt5.get_account_state())
print('PROPOSAL:', proposal)
mt5.shutdown()
"
```

## Errori comuni
- `tool_result` non incapsulato correttamente → Claude perde il contesto.
- Output non JSON-serializzabile → usa `default=str`.
- Loop infinito → fissato a 6 iterazioni.
- Token cost esplosivi → max 50 barre OHLC nel snapshot.

## Commit attesi
```
docs(prompts): add system_prompt.txt and context_template.txt in italian
feat(agent): claude tool use loop with 4 tools
feat(agent): explain_last_trades helper
feat(phase-8): complete and validated
```
