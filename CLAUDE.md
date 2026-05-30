# Trading Agent — Project Memory

## Stack & ambiente
- Python 3.12 64-bit. Runtime live: Windows + MT5; sviluppo/test anche in devcontainer Linux (deps MT5/apscheduler/feedparser/anthropic possono mancare → alcuni test non collezionano).
- MetaTrader5 (TenTrade, demo)
- Anthropic Claude API (solo explain_last_trades)
- Scheduler H24 interno (`IntradayLoopScheduler`) nel path principale; APScheduler resta solo nella linea legacy v1.1.x

## Struttura repo (v2 — package, verificata 2026-05-30)
trading-agent/
├── config.py, models.py, logger.py
├── mt5_client.py, risk_engine.py, execution.py, scheduler.py, scanner.py, main.py
├── news_aggregator.py, sentiment.py (opt-in, ENABLE_NEWS_SENTIMENT=False di default)
├── claude_agent.py (solo explain_last_trades, NON nel path-segnale live)
├── strategy/        ← package puro: setups/{a_breakout,b_reversal,c_compression,d_pullback}, confluence, proposal, context, adapters/{live,backtest}, _shim
├── indicators/      ← package puro: trend, momentum, volatility, structure, bars, volume, mtf, hurst, aggregate
├── backtest/        ← engine, broker, costs, ledger, loader, metrics, walk_forward, baseline/*
├── mcp_tools/       ← server + handlers/{account,market,proposal,position,backtest,ml(STUB)} + job_queue, trail_daemon
├── patterns.py      ← catalogo pattern (PatternHit)
├── scripts/edge_discovery/, scripts/data_acquisition/  ← track ricerca edge (non-GSD)
├── prompts/, logs/, tests/ (~60 file), libri/ (PDF)
└── .planning/ (STATE/ROADMAP/REQUIREMENTS + phases/) , .orchestration/phase-prompts/
Nota: `indicators.py`/`patterns.py`/`strategy.py` monolitici sono LEGACY (architettura v1.x taggata v1.0.0→v1.2.1); il codice v2 vive nei package omonimi.

## Stato progetto (verificato 2026-05-30 — NON fidarsi di memorie più vecchie)
- Branch di lavoro reale: **`research/edge-discovery`** (HEAD, 7 commit avanti `main`). `main` (`bdaf3ee`) contiene già le fasi 1–6 ma NON la fix-chain né il finding NO-GO → `main` è a sua volta stale.
- Milestone v2-ml-backtest: **fasi 1–6 IMPLEMENTATE, testate e merged** (engine backtest, indicatori, pattern, strategia 4-setup, baseline, MCP tools parte 1). **Fasi 7–11 SOSPESE 2026-05-29** (solo PLAN.md; handler ML = stub `NotImplementedError`).
- **Blocco di fondo: la strategia base NON ha edge** (verdetto NO-GO, 59/60 config negative). Le fasi 7–11 (ML/drift/intermarket) assumono un edge smentito. Track Edge Discovery aperto: 5 ipotesi (DXY/yield momentum, carry, COT) tutte falsificate con rigore.
- Test: 6 moduli non collezionano per deps mancanti nell'ambiente (apscheduler/feedparser/anthropic); dei 500 restanti 477 pass / 2 fail / 13 skip / 8 xfail.
- Bug: kill-switch broker RISOLTO; offset DST +6h fisso in `backtest/loader.py` APERTO. Policy dati nuovi: Dukascopy canonico (UTC).
- Fonte canonica stato: `.planning/STATE.md` + `.planning/ROADMAP.md` + `.planning/REQUIREMENTS.md`. Analisi tecnica completa: `ANALISI-TECNICA-FUNZIONALE-2026-05-30.md`.

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
