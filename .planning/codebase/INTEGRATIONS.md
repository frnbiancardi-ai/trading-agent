# External Integrations

**Analysis Date:** 2026-05-07

## APIs & External Services

**Brokerage / Market Data:**
- MetaTrader 5 terminal - Order routing, account state, OHLC bars, symbol info, position management
  - SDK/Client: `MetaTrader5` 5.0.5735 (Python wrapper around the local MT5 terminal IPC)
  - Implementation: `mt5_client.py` (class `Mt5Client`)
  - Auth: `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` env vars
  - Default server in code: `FPMarkets-Demo` (`config.py:64`); `.env.example` references `TenTrade-Demo`
  - Timeframe mapping: `mt5_client.py:13` (`TIMEFRAME_MAP`)
  - Per-symbol filling-mode resolver via `symbol_info` bitmask (recent fix, commit `4dca7e9`)
  - Retry decorator `_retry(3)` wraps account/order calls

**LLM (Claude / Anthropic):**
- Anthropic Claude API - LLM-based scanner and deep analysis (legacy path, still used by `mcp_server`)
  - SDK/Client: `anthropic` Python SDK (`claude_agent.py:9` `from anthropic import Anthropic`)
  - Auth: `CLAUDE_API_KEY` env var
  - Model: `CLAUDE_MODEL` (default `claude-sonnet-4-6`)
  - Tunables: `CLAUDE_MAX_TOKENS` (default 4096), `CLAUDE_TEMPERATURE` (default 0.5)
  - Tool-use loop with `_MAX_ITERATIONS = 6` and `_MAX_ITERATIONS_SCANNER = 8` (`claude_agent.py:24-25`)
  - Phase-16 daemon (`main.py`) does NOT instantiate `ClaudeAgent` - signal layer is now pure-Python (`IntradayStrategy` + `MultiSymbolScanner`). LLM path remains reachable via MCP server.

**MCP (Model Context Protocol) - server side:**
- Local stdio MCP server exposed to Claude Desktop
  - SDK: `mcp` >= 1.27.0 (`from mcp.server import Server`, `from mcp.server.stdio import stdio_server`)
  - Implementation: `mcp_server.py`
  - Transport: stdio (JSON-RPC over stdin/stdout) - logs MUST stay off stdout (file-only `RotatingFileHandler`)
  - Tools advertised: 10 trading-agent tools (cheap scan, deep analysis, risk eval, run-once, etc.)

## Data Storage

**Databases:**
- SQLite (embedded, stdlib `sqlite3`) - Single file `logs/trades.db` in WAL journal mode
  - Connection: derived from `cfg.LOG_FILE` (`logger.py:33` `_trades_db_path`); `Path(LOG_FILE).parent / "trades.db"`
  - Client: stdlib `sqlite3` (no ORM)
  - Tables created at runtime (DDL strings):
    - `trades_log` - Decision audit trail (`logger.py:14-28`); columns: timestamp, symbol, direction, size_lots, entry_price, stop_loss, take_profit, decision_reason, approved, pnl_realized
    - `daily_run_state` - Daily decision counter for orchestrator (`scheduler.py:78`)
    - `heartbeat` - H24 daemon liveness (`scheduler.py:334`)
    - `scheduler_state` - Loop state persistence (`scheduler.py:346`)
  - Heartbeat DB path resolver: `scheduler.heartbeat_db_path()` (`scheduler.py:712`)

**File Storage:**
- Local filesystem only
- Logs: `logs/agent.log` (rotating 5 MB x 3 backups via `RotatingFileHandler`, `logger.py:50`)
- Historical OHLC dumps: `data/historical/`
- Backtest artifacts: `backtest_results.json`, `backtest_trades.json` (repo root)
- ML feedback dataset: `ml_feedback/`
- No S3 / remote object storage

**Caching:**
- In-memory only:
  - `NewsAggregator.cache: list[NewsItem]` (`news_aggregator.py:24`) - RSS items deduped by `(title, link)`, trimmed to `NEWS_CACHE_MAX_HOURS`
  - `Mt5Client._filling_cache: dict[str, int]` (`mt5_client.py:45`) - per-symbol MT5 filling mode bitmask
- No Redis / Memcached

## Authentication & Identity

**Auth Providers:**
- None for end-user auth - the agent runs locally as the trader's own process
- MT5 terminal auth: login/password/server triplet (`MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`)
- Anthropic API: bearer key (`CLAUDE_API_KEY`)
- No OAuth, no JWT, no session management

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, no Rollbar, no Datadog SDK detected)
- Errors captured via `logger.exception(...)` and `logger.error(...)` only

**Logs:**
- Python `logging` module configured in `logger.py:init_logger`
- File-only `RotatingFileHandler` (5 MB, 3 backups, UTF-8) - critical for MCP stdio safety
- Logger name: `trading_agent`; `propagate = False`
- Log level controlled by `LOG_LEVEL` env var (default `INFO`)
- Log rotation strategy controlled by `LOG_ROTATION` env (`daily` | `weekly` | `size`); `WEEKLY_LOG_BACKUP_COUNT` default 8
- Heartbeat liveness in SQLite `heartbeat` table (poor man's monitoring)

## CI/CD & Deployment

**Hosting:**
- Local Windows workstation only - no remote deployment target detected (no `Dockerfile`, no `docker-compose.yml`, no Kubernetes manifests, no Terraform)

**CI Pipeline:**
- No `.github/workflows/`, no `.gitlab-ci.yml`, no `azure-pipelines.yml` detected
- Tests run manually via `pytest` (current state per memory: 173/173 passing)

## Environment Configuration

**Required env vars (critical subset):**
- `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
- `CLAUDE_API_KEY` (only if using `claude_agent` or `mcp_server`)
- `EXECUTION_MODE` (`shadow` | `paper` | `live`)
- `RISK_PER_TRADE_PERCENT`, `MAX_DAILY_DRAWDOWN_PERCENT`
- `OPERATING_TIMEZONE`, `OPERATING_WEEKDAYS`, `INTRADAY_SCAN_INTERVAL_MINUTES`
- `RSS_FEEDS` (only if `ENABLE_NEWS_SENTIMENT=true`)

**Secrets location:**
- `.env` file at repo root (present, gitignored - never read by tooling per security policy)
- Templates: `.env.example`, `.env.example.new` (committed)
- No secret manager (Vault, AWS Secrets Manager, etc.)

## RSS / News Feeds (Phase 15)

**Default feeds (`.env.example` `RSS_FEEDS`):**
- `https://www.investing.com/rss/news_25.rss`
- `https://www.forexlive.com/feed/news`

**Aggregator:** `news_aggregator.py` `NewsAggregator`
- Library: `feedparser`
- Per-feed timeout: 5 seconds (`_DEFAULT_TIMEOUT_SECONDS`, `news_aggregator.py:17`) via `socket.setdefaulttimeout`
- Failure isolation: per-feed `try/except`; logs warning and continues (`news_aggregator.py:42-46`)
- Date parsing: RFC 822 (`email.utils.parsedate_to_datetime`) with ISO-8601 fallbacks
- Cache windowing: items older than `NEWS_CACHE_MAX_HOURS` evicted; lookback filter at `NEWS_LOOKBACK_HOURS`

## Sentiment Analysis (Phase 15)

**Provider:** Local keyword-based analyzer - NOT an external API
- Implementation: `sentiment.py` `SimpleSentiment`
- Lexicons: hard-coded `BULLISH_KEYWORDS` / `BEARISH_KEYWORDS` tuples (`sentiment.py:12-48`)
- Currency relevance map: `CURRENCY_MAP` covers EUR, USD, GBP, JPY, AUD, CAD, CHF, NZD, XAU, XAG (`sentiment.py:50-61`)
- Pair sentiment computed as `base_score - quote_score`; threshold = 1
- No external NLP / sentiment API (no HuggingFace, no OpenAI moderation, no third-party)

## Scheduling

**Phase-16 (current `main.py` path):**
- Pure Python `IntradayLoopScheduler` (`scheduler.py`) - no cron, no Task Scheduler, no APScheduler
- Tick interval: `INTRADAY_SCAN_INTERVAL_MINUTES` (default 15)
- First-cycle delay: `INTRADAY_FIRST_CYCLE_DELAY_MINUTES` (default 5)
- Operating window enforced by `OperatingWindow` (timezone + weekdays + hours)
- Liveness via `HeartbeatStore` -> SQLite

**Legacy phase-13 path (still in repo, used by older entry points):**
- `apscheduler.schedulers.blocking.BlockingScheduler` with `CronTrigger` and `DateTrigger`
- Used by `Orchestrator` for follow-up `DateTrigger` one-shots

## Webhooks & Callbacks

**Incoming:**
- None - no HTTP server, no FastAPI / Flask. The MCP server uses stdio, not HTTP.

**Outgoing:**
- No webhook senders detected
- Only outbound calls: MetaTrader5 IPC (local), Anthropic HTTPS API, RSS feed HTTP GETs

---

*Integration audit: 2026-05-07*
