<!-- refreshed: 2026-05-07 -->
# Architecture

**Analysis Date:** 2026-05-07

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     Entry / Daemon Layer                     │
├──────────────────┬──────────────────┬───────────────────────┤
│     main.py      │   mcp_server.py  │  scripts/dry_run_*.py │
│  (H24 daemon)    │  (MCP stdio)     │  (one-shot tooling)   │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                    │
         ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│            Orchestration Layer (scheduler.py)                │
│   IntradayLoopScheduler · OperatingWindow · HeartbeatStore   │
│   (legacy: APScheduler Orchestrator + DailyRunStateStore)    │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────┼──────────────────────┐
            ▼              ▼                      ▼
┌────────────────────┐ ┌───────────────────┐ ┌────────────────┐
│ Signal Layer       │ │ News/Sentiment    │ │ Risk/Execution │
│ scanner.py         │ │ news_aggregator.py│ │ risk_engine.py │
│ strategy.py        │ │ sentiment.py      │ │ execution.py   │
│ indicators.py      │ │                   │ │                │
│ patterns.py        │ │                   │ │                │
└─────────┬──────────┘ └─────────┬─────────┘ └────────┬───────┘
          │                      │                    │
          └──────────────────────┴────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                Broker Adapter / Persistence                  │
│   mt5_client.py  →  MetaTrader5 SDK                          │
│   logger.py      →  logs/trades.db (SQLite) + logs/agent.log │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Entry daemon | Build dependencies, install signal handlers, run H24 loop | `main.py` |
| Config loader | Parse `.env` into typed `Config` dataclass + validations | `config.py` |
| Models | Dataclasses shared across layers (`TradeProposal`, `StrategyOutcome`, `ScanResult`, `AccountState`, etc.) | `models.py` |
| MT5 adapter | OHLC fetch, account state, order send, filling-mode resolver | `mt5_client.py` |
| Indicators | Pure-Python SMA/EMA/RSI/ATR + S/R + breakout quality + R:R | `indicators.py` |
| Patterns | Candlestick pattern recognition (engulfing, pin bar, etc.) | `patterns.py` |
| Strategy | `IntradayStrategy` + `StrategyEnvironment` (window/news gates, position protection) | `strategy.py` |
| Multi-symbol scanner | `light_scan` ranking + deep analysis on top-N + sentiment filter | `scanner.py` |
| Risk engine | Position sizing, drawdown gate, profile (CONSERVATIVE/MODERATE/AGGRESSIVE) | `risk_engine.py` |
| Execution | Wraps risk gate + MT5 order, honors `EXECUTION_MODE`/`DRY_RUN` | `execution.py` |
| Scheduler H24 | `IntradayLoopScheduler` main loop + `HeartbeatStore` SQLite + legacy `Orchestrator` | `scheduler.py` |
| News aggregator | RSS fetch with cache + lookback filter (`feedparser`) | `news_aggregator.py` |
| Sentiment | Keyword-based bullish/bearish scoring per forex pair | `sentiment.py` |
| Logger | RotatingFileHandler + SQLite `trades.db` schema for trade decisions | `logger.py` |
| Claude agent (legacy) | Anthropic-based decision agent, still importable from `mcp_server.py` | `claude_agent.py` |
| MCP server | Stdio JSON-RPC server exposing tools to external clients | `mcp_server.py` |
| Backtest suite | Offline pandas-based RSI_SMA backtests on `data/historical/` | `backtest_suite.py` |

## Pattern Overview

**Overall:** Layered modular monolith with dependency injection in `main.py`. The signal/strategy layer is a deterministic Python-pure pipeline (phase 16), not an LLM agent. The legacy `ClaudeAgent` path remains importable for MCP exposure but is bypassed by the daemon.

**Key Characteristics:**
- Single-process, single-threaded loop (`IntradayLoopScheduler.run_forever`) using `threading.Event` only as a stop flag and interruptible sleep.
- Pure functional indicator/pattern modules (`indicators.py`, `patterns.py`) with no I/O — easily testable.
- Stateless strategy components: state lives in SQLite (`logs/trades.db`) and on the broker (positions, balance).
- Module-level singletons restricted to MCP entry (`mcp_server.cfg/log/mt5`); the daemon path constructs everything explicitly in `main.main()`.
- Time/timezone handling centralised on `Europe/Rome` via `zoneinfo.ZoneInfo` (`logger.py`, `mt5_client.py`, `risk_engine.py`, `scheduler.py`).

## Layers

**Entry Layer:**
- Purpose: Bootstrap, signal handling, lifecycle.
- Location: `main.py`, `mcp_server.py`, `scripts/dry_run_cycle.py`.
- Depends on: every other layer (composition root).

**Configuration Layer:**
- Purpose: Convert env vars into a typed `Config` class with validations and `_attach_news_sentiment` mixin.
- Location: `config.py`.
- Used by: every component (passed explicitly, not imported as singleton).

**Domain Models:**
- Purpose: Plain `@dataclass` records exchanged between layers (no behaviour).
- Location: `models.py`.

**Indicator / Pattern Layer:**
- Purpose: Pure math, no I/O, no logging.
- Location: `indicators.py`, `patterns.py`.

**Signal Layer:**
- Purpose: Translate OHLC + sentiment into `TechnicalSetup` / `StrategyOutcome` / `TradeProposal`.
- Location: `strategy.py`, `scanner.py`.
- Depends on: indicator layer, `mt5_client.py`, optional `news_aggregator.py` + `sentiment.py`.

**Risk & Execution Layer:**
- Purpose: Approve/reject proposal, compute lot size, send order respecting `EXECUTION_MODE`.
- Location: `risk_engine.py`, `execution.py`.

**Orchestration Layer:**
- Purpose: Time-based loop, gates (window/weekend/news/pause), heartbeat persistence, position management.
- Location: `scheduler.py` (`IntradayLoopScheduler` is the active path; `Orchestrator` + APScheduler is legacy).

**Adapter / Persistence Layer:**
- Purpose: External systems (MT5, SQLite, log files, RSS).
- Location: `mt5_client.py`, `logger.py`, `news_aggregator.py`.

## Data Flow

### Primary H24 Cycle (active path)

1. Daemon entry — `main.main()` builds `Config`, `Mt5Client`, `IntradayStrategy`, `MultiSymbolScanner`, `IntradayLoopScheduler` (`main.py:28`).
2. Loop tick — `IntradayLoopScheduler.run_forever` waits `INTRADAY_FIRST_CYCLE_DELAY_MINUTES`, then ticks every `INTRADAY_SCAN_INTERVAL_MINUTES` (`scheduler.py:501`).
3. Heartbeat begin — `HeartbeatStore.begin_cycle` writes a row in `logs/trades.db.heartbeat` (`scheduler.py:370`).
4. Context gates — `StrategyEnvironment` checks weekend / intraday window / news window (`strategy.py:50-100`).
5. Account snapshot — `Mt5Client.get_account_state()` (`mt5_client.py`).
6. Open-position evaluation — `IntradayStrategy.evaluate_open_position` may emit `CLOSE_PROTECT` / `CLOSE_END_OF_DAY` (`strategy.py`).
7. Scan — `MultiSymbolScanner.light_scan` ranks the universe; deep analysis on top-N → `StrategyOutcome` (`scanner.py:50`).
8. Trade decision — if `outcome_type == "TRADE"`, `execution.run_once` calls `risk_engine.evaluate_trade` and (when `EXECUTION_MODE != "shadow"`) `mt5_client.send_order` (`execution.py:10`).
9. Heartbeat end — `HeartbeatStore.end_cycle` records duration + outcome + error (`scheduler.py:383`).
10. Sleep — overrun-aware: skips slots when a cycle exceeds `INTRADAY_SCAN_INTERVAL_MINUTES` (`scheduler.py:516`).

### Legacy APScheduler Path

1. `build_scheduler(cfg, orchestrator)` registers `CronTrigger` slots from `OPERATING_START_HOUR..OPERATING_END_HOUR` step `MAIN_CYCLE_HOURS` (`scheduler.py:300`).
2. `Orchestrator.execute_ordinary_cycle` runs cycles, persists counters in `daily_run_state` table.
3. Not used by `main.py` in phase 16; retained for backwards compatibility and tests.

### News / Sentiment Sub-flow

1. `NewsAggregator.fetch_recent_news` polls every `NEWS_FETCH_INTERVAL_MINUTES`, caches up to `NEWS_CACHE_MAX_HOURS` (`news_aggregator.py:29`).
2. `SimpleSentiment.analyze` scores headlines per currency leg, computes net bias (`sentiment.py`).
3. `MultiSymbolScanner` consumes the `SentimentAnalysis` to filter / boost / delay proposals according to `SENTIMENT_CONFLICT_ACTION`.

**State Management:**
- SQLite `logs/trades.db` holds `trades_log` (logger.py), `daily_run_state` (legacy orchestrator), `heartbeat` and `scheduler_state` (phase 16). All schemas are created idempotently via `CREATE TABLE IF NOT EXISTS`.
- In-memory caches: `NewsAggregator.cache`, `Mt5Client._filling_cache`.

## Key Abstractions

**`Config`** — Single source of truth for runtime knobs. Constructed once per process; passed explicitly. `config.py:60`.

**`StrategyEnvironment`** — Wraps temporal gating (`is_weekday`, `is_intraday_window`, `is_news_window`) so the loop and strategy share identical decisions. `strategy.py:50`.

**`IntradayStrategy`** — Stateless deterministic decision engine returning `StrategyOutcome`. Sub-500 ms target per symbol. `strategy.py`.

**`MultiSymbolScanner`** — Two-stage pipeline (light_scan → deep analysis on top-N). `scanner.py:31`.

**`IntradayLoopScheduler`** — Active scheduler. No external scheduler library required. `scheduler.py:460`.

**`HeartbeatStore`** — Persistence boundary for liveness. Two tables: `heartbeat` (history), `scheduler_state` (singleton row). `scheduler.py:325`.

**`TradeProposal` / `StrategyOutcome` / `RiskDecision` / `OrderResult`** — Wire-format dataclasses crossing layer boundaries. `models.py`.

## Entry Points

**Daemon:**
- Location: `main.py`
- Triggered by: `python main.py` (Windows process, kept alive by SIGINT/SIGTERM).
- Responsibilities: Composition root, MT5 login, signal handlers, run-forever loop.

**MCP server:**
- Location: `mcp_server.py`
- Triggered by: MCP-compatible client over stdio.
- Responsibilities: Expose `cheap_scan_symbol`, `compute_all`, `evaluate_trade`, `run_once` as MCP tools.

**Dry-run script:**
- Location: `scripts/dry_run_cycle.py`
- Triggered by: manual invocation for QA.
- Responsibilities: Run a single cycle without sending orders.

**Backtest:**
- Location: `backtest_suite.py`
- Triggered by: manual invocation against `data/historical/<SYMBOL>/M15.csv`.

**Tests:**
- Location: `tests/test_*.py` (pytest, configured by `pytest.ini`).

## Architectural Constraints

- **Threading:** Single-threaded event loop in `IntradayLoopScheduler.run_forever`. `threading.Event` is used only for cooperative cancellation. Do not introduce worker threads without explicit synchronisation around `Mt5Client` (the MetaTrader5 SDK is not thread-safe).
- **Process model:** One MT5 connection per process. `mt5.initialize()` and `mt5.login()` happen once in `main.main()` and once in `mcp_server._bootstrap_mt5()`. Never call them from library code.
- **Stdout discipline:** `mcp_server.py` uses stdio for JSON-RPC. All logs must go to file/stderr, never `print` to stdout. Logger configured in `logger.py` is file-only (`RotatingFileHandler`).
- **Global state:** Module-level singletons exist only in `mcp_server.py` (`cfg`, `log`, `mt5`, `_mt5_ready`). The daemon path keeps state local to `main.main()`.
- **Timezone:** `Europe/Rome` is the canonical TZ for all human-facing timestamps and operating-window logic. UTC is used for RSS timestamps before normalisation.
- **Config validation:** `config.py` raises `ValueError` at import time for invalid `INTRADAY_TIMEFRAME`, `LOG_ROTATION`, `SENTIMENT_CONFLICT_ACTION`. The process refuses to start with a bad `.env`.
- **No pandas in hot path:** Indicators are pure Python over `list[float]`. Pandas is allowed only in `backtest_suite.py`.

## Anti-Patterns

### Re-importing `Config` for late-bound values

**What happens:** Some legacy paths (e.g., `risk_engine.evaluate_trade`) call `cfg = Config()` when `cfg is None`, re-reading env at runtime.
**Why it's wrong:** Bypasses the composition root and can read a different state if env was mutated.
**Do this instead:** Always pass the `Config` instance built in `main.main()`. Treat the `cfg=None` fallback as a test-only convenience.

### Bypassing `StrategyEnvironment`

**What happens:** Inline checks of `cfg.INTRADAY_START_HOUR <= now.hour` scattered in callers.
**Why it's wrong:** Diverges from the loop's gating and produces inconsistent decisions vs. the scheduler.
**Do this instead:** Inject and call `StrategyEnvironment` (`strategy.py:50`).

### Logging to stdout in MCP-reachable code paths

**What happens:** `print(...)` calls in modules that may be loaded by `mcp_server.py`.
**Why it's wrong:** Corrupts JSON-RPC framing, breaks the MCP protocol.
**Do this instead:** Use the configured logger (`logger.init_logger(cfg)`); see `logger.py`.

### Using APScheduler in new code

**What happens:** Adding new triggers via `build_scheduler` in `scheduler.py:300`.
**Why it's wrong:** That orchestrator is the legacy phase-13 path; the active scheduler is `IntradayLoopScheduler`.
**Do this instead:** Extend `IntradayLoopScheduler.run_one_cycle` or its hooks (`scheduler.py:530`).

## Error Handling

**Strategy:**
- The H24 loop never crashes the process: `run_forever` wraps `run_one_cycle` in `except Exception` and continues (`scheduler.py:512`).
- Per-cycle failures are persisted as `outcome="ERROR"` rows in `heartbeat` with `error_type` / `error_message` set.
- `Mt5Client` uses a `_retry(n=3)` decorator for transient broker errors (`mt5_client.py:26`).

**Patterns:**
- Catch broad `Exception` only at orchestration boundaries (`run_forever`, `mcp_server` bootstrap, `news_aggregator.fetch_recent_news`); keep library code narrow.
- Log via `logger.exception(...)` for stack traces, `logger.warning(...)` for retried failures.
- `Mt5Client.get_ohlc` returns `None` on failure; callers must short-circuit (e.g., `scanner.py:60`).

## Cross-Cutting Concerns

**Logging:** Centralised in `logger.py` via `init_logger(cfg)`. Trade decisions and order results are mirrored to `logs/trades.db` (`trades_log` table).

**Validation:** Done at config load (`config.py`) and at the boundary of strategy decisions (numeric guards in indicators).

**Authentication:** MT5 credentials from `.env` (`MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`). No app-level auth.

**Persistence:** Single SQLite database `logs/trades.db` shared across components, each owning its tables. Schemas are self-initialising.

**Time:** `Europe/Rome` zoneinfo singleton (`_TZ_ROME`) reused across modules; UTC only for RSS ingestion.

---

*Architecture analysis: 2026-05-07*
