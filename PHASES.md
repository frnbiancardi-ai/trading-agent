# Piano sintetico delle 10 fasi

File di sola lettura. L'orchestrator lo consulta ma non lo modifica.

## Struttura del progetto (immutabile)

```
C:\trading-agent\
├── .env, .env.example, .gitignore
├── main.py, config.py, models.py
├── mt5_client.py, claude_agent.py, risk_engine.py
├── execution.py, logger.py, indicators.py, mcp_server.py
├── prompts/{system_prompt.txt, context_template.txt}
├── logs/{agent.log, trades.db}
├── requirements.txt, README.md
└── tests/{test_mt5.py, test_risk.py}
```

## Fasi

| #  | Titolo                          | File chiave                                       | Checkpoint                                      |
|----|---------------------------------|---------------------------------------------------|-------------------------------------------------|
| 1  | Setup ambiente                  | `requirements.txt`, `.gitignore`, struttura       | `pip install -r requirements.txt` + import OK   |
| 2  | Config & modelli                | `.env.example`, `config.py`, `models.py`          | `Config()` istanziabile, dataclasses serializzabili |
| 3  | MT5 client                      | `mt5_client.py`                                   | `get_account_state` su demo FP Markets          |
| 4  | Risk engine                     | `risk_engine.py`, `tests/test_risk.py`            | `pytest tests/test_risk.py` tutto verde         |
| 5  | Logger                          | `logger.py`                                       | `trades.db` creato, schema corretto             |
| 6  | Execution + EXECUTION_MODE      | `execution.py`, `main.py`                         | shadow run produce log, paper run invia ordine  |
| 7  | Indicators                      | `indicators.py`                                   | SMA/EMA/RSI/ATR coerenti con TradingView ±0.1%  |
| 8  | Claude agent + tool use         | `claude_agent.py`, `prompts/*`                    | run_cycle produce TradeProposal o NO_TRADE      |
| 9  | MCP server + Claude Desktop     | `mcp_server.py`, sezione README                   | tool MCP visibili in Claude Desktop             |
| 10 | E2E demo                        | `tests/test_mt5.py`, `README.md`                  | giro completo shadow + paper su FP Markets      |

## Vincoli trasversali

- Risk engine = unico cancello di approvazione.
- `EXECUTION_MODE=shadow` di default.
- Tutto da `.env`, zero magic numbers.
- No pandas/ta-lib obbligatori.
- Coerenza assoluta di nomi e firme tra i file.

## Ordine consigliato di generazione

1. `requirements.txt`
2. `.gitignore`
3. `.env.example`
4. `config.py`
5. `models.py`
6. `indicators.py`
7. `mt5_client.py`
8. `logger.py`
9. `risk_engine.py`
10. `tests/test_risk.py`
11. `execution.py`
12. `prompts/system_prompt.txt`
13. `prompts/context_template.txt`
14. `claude_agent.py`
15. `mcp_server.py`
16. `main.py`
17. `tests/test_mt5.py`
18. `README.md`
