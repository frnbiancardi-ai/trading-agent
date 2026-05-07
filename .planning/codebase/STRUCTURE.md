# Codebase Structure

**Analysis Date:** 2026-05-07

## Directory Layout

```
trading-agent/
├── main.py                       # H24 daemon entry point
├── mcp_server.py                 # MCP stdio server exposing trading tools
├── config.py                     # .env → typed Config class + validation
├── models.py                     # Shared @dataclass domain models
├── mt5_client.py                 # MetaTrader5 SDK adapter
├── indicators.py                 # Pure-Python SMA/EMA/RSI/ATR/S-R
├── patterns.py                   # Candlestick pattern recognition
├── strategy.py                   # IntradayStrategy + StrategyEnvironment
├── scanner.py                    # MultiSymbolScanner (light_scan + deep)
├── risk_engine.py                # Position sizing + drawdown gates
├── execution.py                  # Risk gate → MT5 order send
├── scheduler.py                  # IntradayLoopScheduler + HeartbeatStore (+ legacy APScheduler Orchestrator)
├── logger.py                     # RotatingFileHandler + trades.db schema
├── news_aggregator.py            # RSS fetch + cache (feedparser)
├── sentiment.py                  # Keyword-based forex sentiment
├── claude_agent.py               # Legacy Anthropic-driven agent
├── backtest_suite.py             # Offline pandas RSI_SMA backtests
├── requirements.txt              # Pinned dependencies
├── pytest.ini                    # Test discovery + warnings filter
├── .env / .env.example.new       # Runtime configuration (.env never committed)
│
├── scripts/
│   └── dry_run_cycle.py          # One-shot QA cycle (no orders)
│
├── tests/                        # pytest suite (173 tests baseline)
│   ├── test_strategy.py
│   ├── test_strategy_runner.py
│   ├── test_scanner.py
│   ├── test_scheduler.py
│   ├── test_risk.py
│   ├── test_mt5.py
│   ├── test_patterns.py
│   ├── test_sentiment.py
│   ├── test_news_aggregator.py
│   ├── test_daily_orchestrator.py
│   ├── test_mcp_tools_v2.py
│   ├── test_phase16.py
│   ├── test_pdf_to_markdown_ocr.py
│   └── test_pdf_to_markdown_ocr.py
│
├── prompts/                      # Prompt templates (legacy LLM path)
│   ├── system_prompt.txt
│   ├── system_prompt_scanner.txt
│   ├── context_template.txt
│   └── context_template_scanner.txt
│
├── data/
│   └── historical/<SYMBOL>/M15.csv   # Backtest input (EURUSD, GBPUSD, USDJPY)
│
├── ml_feedback/                  # Walk-forward + grid-search results (JSON)
│   ├── grid_search.json
│   ├── advanced_search.json
│   ├── walkforward_full.json
│   └── verify_final.py
│
├── libri/                        # Reference PDFs (trading literature)
├── logs/
│   ├── agent.log                 # Rotating text log
│   └── trades.db                 # SQLite: trades_log, heartbeat, scheduler_state, daily_run_state
│
├── PHASES.md                     # Project roadmap by phase
├── STATE.md                      # Current phase + suite status
├── HANDOFF_PROTOCOL.md           # Session handoff rules
├── COMMIT_CONVENTIONS.md         # Commit message style
├── README.md
├── CLAUDE.md                     # (deleted in working tree)
└── PromptClaudeCode/             # Legacy prompt artefacts
```

## Directory Purposes

**Project root (flat):**
- Purpose: All production Python modules live at the repo root. There is no `src/` layout.
- Contains: One module per architectural responsibility (entry, config, models, adapters, signal, risk, execution, orchestration, observability).
- Key files: `main.py`, `scheduler.py`, `strategy.py`, `scanner.py`, `mt5_client.py`.

**`scripts/`:**
- Purpose: Operator/QA tools that import the production modules.
- Contains: `dry_run_cycle.py` for executing a single cycle without live orders.
- Convention: Scripts are self-contained executables (run via `python scripts/<name>.py`).

**`tests/`:**
- Purpose: pytest suite mirroring the module layout (one `test_<module>.py` per production module).
- Contains: Unit + integration tests, including phase-specific tests (`test_phase16.py`).
- Discovery: Driven by `pytest.ini` at repo root.

**`prompts/`:**
- Purpose: Plain-text prompt templates for the legacy `claude_agent.py` / scanner LLM flow.
- Status: Retained for MCP-exposed legacy path; not used by the daemon's pure-Python loop.

**`data/historical/<SYMBOL>/`:**
- Purpose: CSV OHLC for offline backtests (semicolon-delimited, Italian column names like `Data`, `Ora`, `Close`).
- Generated: No (sourced manually).
- Committed: Yes.

**`ml_feedback/`:**
- Purpose: Persistent backtest / walk-forward / grid-search outputs as JSON.
- Generated: Yes — by `backtest_suite.py` and `verify_final.py`.
- Committed: Yes (treated as experimental record).

**`libri/`:**
- Purpose: Reference PDFs (Murphy, Probo, *StrategieOperative*) used for OCR/RAG experiments (`tests/test_pdf_to_markdown_ocr.py`).
- Committed: Yes.

**`logs/`:**
- Purpose: Runtime artefacts (text log + SQLite state).
- Generated: Yes — created on first run by `logger.init_logger` and `HeartbeatStore`.
- Committed: No (should be `.gitignore`d; verify before commit).

**`PromptClaudeCode/`:**
- Purpose: Historical prompt artefacts. Read-only.

## Key File Locations

**Entry Points:**
- `main.py`: H24 daemon (`python main.py`).
- `mcp_server.py`: MCP stdio server.
- `scripts/dry_run_cycle.py`: One-shot QA cycle.
- `backtest_suite.py`: Offline backtest runner.

**Configuration:**
- `config.py`: Typed `Config` class with `_get_bool`, `_get_int`, `_get_int_list`, `_get_list` helpers and a `_attach_news_sentiment` mixin.
- `.env`: Runtime values (never read by the assistant).
- `.env.example.new`: Template for new variables.
- `pytest.ini`: Test runner config.
- `requirements.txt`: Pinned deps.

**Core Logic:**
- `strategy.py`: `IntradayStrategy.run_cycle`, `evaluate_open_position`, `StrategyEnvironment`.
- `scanner.py`: `MultiSymbolScanner.light_scan` and `deep_analyze`.
- `scheduler.py`: `IntradayLoopScheduler.run_forever` / `run_one_cycle`, `HeartbeatStore`.
- `risk_engine.py`: `evaluate_trade`, profile table `PROFILES`.
- `execution.py`: `run_once` (single-symbol risk → order pipeline).

**Adapters:**
- `mt5_client.py`: `Mt5Client` (initialize/login/get_ohlc/get_account_state/send_order, retry decorator, filling-mode resolver).
- `news_aggregator.py`: `NewsAggregator.fetch_recent_news`.
- `sentiment.py`: `SimpleSentiment` keyword tables and `analyze`.
- `logger.py`: `init_logger`, `log_trade_decision`, `log_order_result`, `_trades_db_path`.

**Domain Models:**
- `models.py`: All shared `@dataclass` types (`TradeProposal`, `StrategyOutcome`, `ScanResult`, `AccountState`, `RiskDecision`, `OrderResult`, `TechnicalSetup`, `OpenPositionVerdict`, `SchedulerCycleRecord`, `NewsItem`, `SentimentAnalysis`, `DailyRunState`, `DelayedFollowUpRequest`, `AgentCycleOutcome`).

**Testing:**
- `tests/test_<module>.py`: Co-named with the module under test (e.g., `tests/test_scanner.py` ↔ `scanner.py`).

## Naming Conventions

**Files (modules):**
- `snake_case.py` mirroring the dominant class/function (e.g., `mt5_client.py` → `Mt5Client`, `news_aggregator.py` → `NewsAggregator`).
- One primary responsibility per module.
- Tests prefixed `test_` + module name in `tests/`.

**Classes:**
- `PascalCase`: `IntradayStrategy`, `MultiSymbolScanner`, `IntradayLoopScheduler`, `HeartbeatStore`, `StrategyEnvironment`, `Mt5Client`.
- Dataclasses named after the value they carry: `TradeProposal`, `StrategyOutcome`.

**Functions:**
- `snake_case` for public functions (`evaluate_trade`, `run_once`, `cheap_scan_symbol`).
- Leading underscore for module-private helpers (`_pip_size`, `_last_valid`, `_get_bool`, `_call_retry`, `_retry`).

**Constants:**
- `UPPER_SNAKE_CASE` at module top: `_LIGHT_BARS`, `_TZ_ROME`, `_MAX_ITERATIONS`, `PROFILES`, `TIMEFRAME_MAP`.
- Underscore prefix for module-private constants.

**Config attributes:**
- `UPPER_SNAKE_CASE` matching the env var name verbatim (`Config.INTRADAY_SCAN_INTERVAL_MINUTES` ↔ `INTRADAY_SCAN_INTERVAL_MINUTES`).

**SQLite tables:**
- `snake_case`: `trades_log`, `daily_run_state`, `heartbeat`, `scheduler_state`.

## Where to Add New Code

**New strategy / signal logic:**
- Implementation: extend `strategy.py` (add a method on `IntradayStrategy`) or `scanner.py`.
- Pure helpers: add to `indicators.py` or `patterns.py` (no I/O, no logging).
- Tests: `tests/test_strategy.py` / `tests/test_scanner.py` / new `tests/test_<feature>.py`.

**New scheduler hook / gate:**
- Implementation: add a method to `StrategyEnvironment` (`strategy.py:50`) and call it from `IntradayLoopScheduler.run_one_cycle` (`scheduler.py:530`).
- Tests: `tests/test_scheduler.py` and `tests/test_phase16.py`.

**New broker capability:**
- Implementation: extend `Mt5Client` in `mt5_client.py`. Reuse `_retry`. Cache like `_filling_cache` for per-symbol metadata.
- Tests: `tests/test_mt5.py` (mock `MetaTrader5`).

**New domain dataclass:**
- Add to `models.py`. Keep it behaviourless. Import from `models import ...`.

**New configuration knob:**
- Add an attribute on `Config` in `config.py` using one of `_get_bool` / `_get_int` / `_get_list`.
- Update `.env.example.new`.
- If it has a constrained value set, add validation at module bottom (mirror `_VALID_INTRADAY_TIMEFRAMES` / `_VALID_LOG_ROTATIONS`).

**New external integration (HTTP/RSS/SDK):**
- Create a new top-level `<integration>.py` module mirroring `news_aggregator.py` (own cache, short timeout, isolated exceptions).
- Inject it explicitly in `main.main()` — never as a global singleton.

**New MCP tool:**
- Register in `mcp_server.py` using the existing `@server.list_tools()` / `@server.call_tool()` pattern. Never `print` to stdout.

**New script / operator tool:**
- Place under `scripts/`. Use absolute paths and import production modules; do not duplicate logic.

**New persistence:**
- Add a `CREATE TABLE IF NOT EXISTS` block on the owning module (mirroring `logger.py`, `scheduler.py`). Reuse `logs/trades.db` unless there is a strong reason for a separate file.

**New tests:**
- File: `tests/test_<module>.py`.
- Run via: `python -m pytest` (config in `pytest.ini`).

## Special Directories

**`logs/`:**
- Purpose: runtime log file + SQLite state.
- Generated: Yes (auto-created).
- Committed: No.

**`__pycache__/`:**
- Purpose: Python bytecode cache.
- Generated: Yes.
- Committed: No.

**`.opencode/`, `.planning/`:**
- Purpose: Tooling metadata (planning docs, agent skills).
- Generated: Yes (by GSD / OpenCode).
- Committed: Selectively (planning docs yes, transient state no).

**`ml_feedback/`:**
- Purpose: Backtest result JSON archive.
- Generated: Yes (by `backtest_suite.py` / `verify_final.py`).
- Committed: Yes.

**`data/historical/`:**
- Purpose: Offline OHLC CSV for backtests.
- Generated: No (manually sourced).
- Committed: Yes.

---

*Structure analysis: 2026-05-07*
