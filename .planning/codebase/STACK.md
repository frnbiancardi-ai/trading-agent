# Technology Stack

**Analysis Date:** 2026-05-07

## Languages

**Primary:**
- Python 3.12 (64-bit) - All application code (`*.py` at repo root, `tests/`, `scripts/`)

**Secondary:**
- Markdown - Documentation (`README.md`, `PHASES.md`, `STATE.md`, `HANDOFF_PROTOCOL.md`, `COMMIT_CONVENTIONS.md`)
- SQL - Embedded DDL strings inside Python (`logger.py`, `scheduler.py`) for SQLite schemas

## Runtime

**Environment:**
- CPython 3.12 64-bit (must be 64-bit because the `MetaTrader5` package ships only 64-bit wheels)
- Python 3.14 explicitly NOT supported - `pydantic-core` wheels missing on 3.14 (documented in `README.md`)
- Local venv: `.venv/` (Anaconda Python 3.12 backed per project memory)

**Package Manager:**
- `pip` driven by `requirements.txt`
- No lockfile (no `requirements.lock`, no `poetry.lock`, no `Pipfile.lock`)
- No `pyproject.toml` at repo root - packaging is requirements-only

## Frameworks

**Core (production):**
- `MetaTrader5` 5.0.5735 - Native bridge to MetaTrader 5 terminal (`mt5_client.py`)
- `pydantic` 2.11.3 - Data models / validation (`models.py`)
- `python-dotenv` 1.0.1 - `.env` file loading (`config.py`)
- `requests` 2.32.3 - HTTP client (transitive HTTP needs)
- `anthropic` (unpinned) - Claude API SDK (`claude_agent.py`)
- `mcp` (unpinned, requires >= 1.27.0) - Model Context Protocol server SDK (`mcp_server.py`)
- `apscheduler` (unpinned) - Cron-style scheduling (`scheduler.py`, legacy phase 13 path)
- `feedparser` (unpinned) - RSS parsing (`news_aggregator.py`)
- `tzdata` (unpinned) - Timezone DB for `zoneinfo` on Windows

**Testing:**
- `pytest` (unpinned) - Test runner (`tests/test_*.py`, config in `pytest.ini`)

**Build/Dev:**
- No build system - pure Python source executed directly via `python main.py`
- No formatter/linter config detected (no `.ruff.toml`, no `pyproject.toml`, no `setup.cfg`)

## Key Dependencies

**Critical:**
- `MetaTrader5` 5.0.5735 - Hard dependency on Windows + MT5 terminal installed; entire trading layer fails without it
- `pydantic` 2.11.3 - All domain models in `models.py` are pydantic; v2 API in use
- `anthropic` - Required for `claude_agent.ClaudeAgent` (LLM scanner / deep analysis path)
- `mcp` >= 1.27.0 - Required for `mcp_server.py` exposing 10 tools to Claude Desktop
- `apscheduler` - Used by legacy phase-13 `Orchestrator` / `BlockingScheduler` path; phase-16 `IntradayLoopScheduler` is a pure-Python loop and does NOT use it

**Infrastructure:**
- `sqlite3` (stdlib) - Persistence for trades, daily run state, heartbeat (`logs/trades.db`, WAL mode)
- `zoneinfo` (stdlib) + `tzdata` package - Europe/Rome timezone handling
- `logging.handlers.RotatingFileHandler` (stdlib) - Log rotation in `logger.py`
- `signal` (stdlib) - SIGINT/SIGTERM graceful shutdown in `main.py`

## Configuration

**Environment:**
- Loaded by `python-dotenv` in `config.py:4` (`load_dotenv()`)
- Single `Config` class in `config.py` aggregates ALL runtime settings
- Helpers `_get_bool`, `_get_list`, `_get_int`, `_get_int_list` provide typed parsing with defaults
- Validation at import time: `INTRADAY_TIMEFRAME` must be in {M1,M5,M10,M15,M30}; `LOG_ROTATION` in {daily,weekly,size}; `SENTIMENT_CONFLICT_ACTION` in {skip,delay,reduce_confidence}
- `.env` file present at repo root (NOT committed - contains real credentials)
- Template: `.env.example` (full annotated example) and `.env.example.new`

**Key configs required (from `.env.example`):**
- `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` (MetaTrader 5 broker credentials)
- `CLAUDE_API_KEY`, `CLAUDE_MODEL` (Anthropic API)
- `EXECUTION_MODE` = `shadow` | `paper` | `live`
- `STRATEGY_MODE` = `intraday`
- Risk: `RISK_PER_TRADE_PERCENT`, `MAX_DAILY_DRAWDOWN_PERCENT`, `MIN_SL_PIPS`, `MAX_SL_PIPS`, `RISK_MODE`
- Scheduler H24 (phase 16): `INTRADAY_SCAN_INTERVAL_MINUTES`, `INTRADAY_FIRST_CYCLE_DELAY_MINUTES`, `PAUSE_TRADING`, `DRY_RUN`, `OPERATING_TIMEZONE`, `OPERATING_WEEKDAYS`
- Sentiment (phase 15, optional): `ENABLE_NEWS_SENTIMENT`, `RSS_FEEDS`, `NEWS_FETCH_INTERVAL_MINUTES`

**Build:**
- No build artifacts. `pytest.ini` is the only build/test config (`pythonpath = .`)
- `.nvmrc`, `tsconfig.json`, etc. - Not applicable (Python project)

## Platform Requirements

**Development:**
- Windows 10/11 64-bit (required by `MetaTrader5` package)
- Python 3.12 64-bit (Anaconda recommended per project memory)
- MetaTrader 5 terminal installed and authenticated against the configured broker
- Anthropic API key for `claude_agent` / `mcp_server` flows
- Claude Desktop (optional, for MCP server consumption)

**Production:**
- Same as dev. The system is designed to run as a long-lived local daemon (`python main.py`) on the trader's Windows workstation
- Persistent SQLite file at `logs/trades.db` (WAL mode)
- Rotating log files at `logs/agent.log` (default `RotatingFileHandler`, 5 MB x 3 backups)
- No containerization, no remote deployment target detected

---

*Stack analysis: 2026-05-07*
