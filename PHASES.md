# Piano sintetico delle 13 fasi

File di sola lettura. L'orchestrator lo consulta ma non lo modifica, salvo aggiornamenti di roadmap (es. v1.0.0 → v1.1.0).

## Struttura del progetto (immutabile)

```
C:\trading-agent\
├── .env, .env.example, .gitignore
├── main.py, config.py, models.py, scheduler.py
├── mt5_client.py, claude_agent.py, risk_engine.py
├── execution.py, logger.py, indicators.py, mcp_server.py
├── prompts/{system_prompt.txt, context_template.txt,
│           system_prompt_scanner.txt, context_template_scanner.txt}
├── logs/{agent.log, trades.db}
├── requirements.txt, README.md
└── tests/{test_mt5.py, test_risk.py, test_scanner.py,
          test_mcp_tools_v2.py, test_scheduler.py,
          test_daily_orchestrator.py}
```

## Fasi

### v1.0.0 — MVP shadow-ready (fasi 1-10)

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

### v1.1.0 — Multi-symbol scanner + autonomia (fasi 11-13)

| #  | Titolo                          | File chiave                                                                 | Checkpoint                                              |
|----|---------------------------------|------------------------------------------------------------------------------|---------------------------------------------------------|
| 11 | Market Scanner multi-symbol     | `prompts/system_prompt_scanner.txt`, `prompts/context_template_scanner.txt`, `claude_agent.py` (scanner workflow), `models.py` (`SymbolScanCandidate`, `ScannerDecision`), `tests/test_scanner.py` | `pytest tests/test_scanner.py` verde, `run_market_scan` produce ≤1 proposta su universo configurabile |
| 12 | MCP Tools Upgrade               | `mcp_server.py` (+ `get_symbol_universe`, `scan_symbol_candidates`, `get_symbol_indicators`, `propose_trade`), `claude_agent.cheap_scan_symbol`, `tests/test_mcp_tools_v2.py` | `pytest tests/test_mcp_tools_v2.py` verde, 10 tool MCP visibili in Claude Desktop |
| 13 | Scheduled Orchestrator          | `scheduler.py` (BlockingScheduler + DailyRunStateStore SQLite), `main.py` (daemon SIGINT/SIGTERM), `models.py` (`DelayedFollowUpRequest`, `AgentCycleOutcome`, `DailyRunState`), prompt scanner aggiornati per follow-up, `claude_agent.run_market_cycle` con outcome strutturato, `tests/test_scheduler.py`, `tests/test_daily_orchestrator.py` | `pytest tests/test_scheduler.py tests/test_daily_orchestrator.py` verde, daemon completa giornata operativa raggiungendo `DAILY_TARGET_DECISIONS` |

## Vincoli trasversali

- Risk engine = unico cancello di approvazione.
- `EXECUTION_MODE=shadow` di default.
- Tutto da `.env`, zero magic numbers.
- No pandas/ta-lib obbligatori.
- Coerenza assoluta di nomi e firme tra i file.
- v1.1.0: nessuna regressione sulla suite v1.0.0; backward-compat di `run_cycle` single-symbol preservata.

## Ordine consigliato di generazione

### v1.0.0 (fasi 1-10)

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

### v1.1.0 (fasi 11-13)

Fase 11 — Market Scanner:

1. `prompts/system_prompt_scanner.txt`
2. `prompts/context_template_scanner.txt`
3. `models.py` (+ `SymbolScanCandidate`, `ScannerDecision`)
4. `claude_agent.py` (+ `build_scanner_tools`, `run_market_scan`, `_cheap_scan_one`, `_dispatch_scanner_tool`)
5. `tests/test_scanner.py`

Fase 12 — MCP Tools Upgrade:

6. `claude_agent.py` (estrazione `cheap_scan_symbol` modulo-level)
7. `mcp_server.py` (+ 4 tool v2 + `_bootstrap_mt5` lazy)
8. `tests/test_mcp_tools_v2.py`

Fase 13 — Scheduled Orchestrator:

9.  `requirements.txt` (+ `apscheduler`)
10. `.env.example` + `config.py` (parametri scheduler/daily orchestrator)
11. `models.py` (+ `DelayedFollowUpRequest`, `AgentCycleOutcome`, `DailyRunState`)
12. `prompts/system_prompt_scanner.txt` + `prompts/context_template_scanner.txt` (follow-up)
13. `claude_agent.py` (+ `request_followup` tool, `run_market_cycle`, clamp delay)
14. `scheduler.py` (`OperatingWindow`, `DailyRunStateStore`, `Orchestrator`, `build_scheduler`)
15. `main.py` (daemon BlockingScheduler.start + signal handlers)
16. `tests/test_scheduler.py`
17. `tests/test_daily_orchestrator.py`
