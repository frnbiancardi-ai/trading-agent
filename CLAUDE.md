# Trading Agent — Project Memory

## Stack & ambiente
- Python 3.12 64-bit, Windows
- MetaTrader5 (TenTrade, demo)
- Anthropic Claude API
- APScheduler per scheduling intraday

## Struttura repo
C:\trading-agent\
├── .env, config.py, models.py
├── mt5_client.py, risk_engine.py, execution.py
├── indicators.py, patterns.py, logger.py
├── strategy.py, scanner.py (fase 14)
├── news_aggregator.py, sentiment.py (fase 15)
├── claude_agent.py (solo explain_last_trades)
├── scheduler.py, main.py, mcp_server.py
├── prompts/, logs/, tests/
└── .orchestration/phase-prompts/

## Stato progetto
- Branch: feature/python-pure-strategy
- Fasi validate: 1–13
- Fase corrente: 14 (Python Pure Strategy Engine)
- Prossima: 15 (RSS News Sentiment)

## Regole fondamentali
- EXECUTION_MODE=shadow default sempre
- Tutto da .env, zero magic numbers
- Risk engine = unico gate approvazione trade
- Un file per fase in .orchestration/phase-prompts/
- STATE.md aggiornato dopo ogni micro-step
- PHASES.md read-only per orchestrator

## Operatività intraday
- Timeframe: M15 (configurabile .env)
- Simboli: array INTRADAY_SYMBOLS in .env (es. EURUSD,GBPUSD)
- Ciclo scheduler: ogni 5 min in finestra operativa
- Finestra: lun–ven 08:00–20:00 Europe/Rome
- Target: 5 decisioni/giorno (TRADE o NO_TRADE)
- Follow-up max: 120 min, una volta per opportunità

## Broker / MT5
- Broker: TenTrade demo
- Filling mode: ORDER_FILLING_RETURN (unico supportato GBPUSD/EURUSD)
- Evitare ORDER_FILLING_IOC e ORDER_FILLING_FOK

## Convenzioni
- Mai accedere direttamente a file .env
- Commit seguono COMMIT_CONVENTIONS.md
- Handoff segue HANDOFF_PROTOCOL.md
- Lingua commenti/log/rationale: italiano
- Test pytest, mock Mt5Client per evitare connessione reale
