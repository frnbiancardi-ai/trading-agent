# Codebase Concerns

**Analysis Date:** 2026-05-07

## Tech Debt

**Dual scheduler / dual signal layer (live but unused legacy paths):**
- Issue: `scheduler.py` contains both the legacy APScheduler-based `Orchestrator` + `build_scheduler` (fase 13) and the active `IntradayLoopScheduler` (fase 16). `main.py` only uses `IntradayLoopScheduler`; `Orchestrator`, `operating_slots`, `build_scheduler` are orphaned in the production flow but still exported, tested, and pull `apscheduler` as a hard dependency.
- Files: `C:\trading-agent\scheduler.py` (lines 46-318 legacy, 320-715 active), `C:\trading-agent\main.py`, `C:\trading-agent\requirements.txt`
- Impact: 2× maintenance surface, confusion ("which scheduler runs?"), dead `apscheduler` dependency, `tests/test_scheduler.py` (497 lines) tests the unused path.
- Fix approach: Either delete the fase-13 path (and drop `apscheduler` from `requirements.txt`) or document it as the optional cron-mode entry. Same applies to `StrategyRunner` in `scanner.py` (lines 304-end), used only by `Orchestrator`.

**`claude_agent.py` largely orphaned in the live loop:**
- Issue: 697 lines of `ClaudeAgent` (cycle, scanner workflow, anthropic tool-use loop) survive but `main.py`/`IntradayLoopScheduler` no longer call them. Only `cheap_scan_symbol` (module-level) is reused, by `mcp_server.py`.
- Files: `C:\trading-agent\claude_agent.py`, `C:\trading-agent\mcp_server.py:25` (only import)
- Impact: ~600 lines of dead code on the critical path of imports; `anthropic` Python SDK kept as runtime dep although the daemon no longer calls Claude.
- Fix approach: Extract `cheap_scan_symbol` into `scanner.py` (the STATE.md decision D already plans this) and delete `claude_agent.py`, or scope it explicitly as "optional post-trade explainer".

**`Config` is a class with class-level `os.getenv` evaluated at import time:**
- Issue: `C:\trading-agent\config.py` defines all settings as class attributes. They are evaluated once on import; tests that mutate `cfg.X` mutate the singleton. `Config()` instantiation does not re-read env. `_attach_news_sentiment(Config)` further mutates the class globally.
- Files: `C:\trading-agent\config.py:60-204`
- Impact: Tests must monkey-patch class attributes; in-process re-loading of `.env` is impossible; multiprocessing can drift. `tests/test_scheduler.py:76` already does `cfg.CLAUDE_TEMPERATURE = 0.2`.
- Fix approach: Convert to a dataclass with `from_env()` classmethod, or freeze + provide test fixtures via `pytest` fixtures.

**`SESSION_START_HOUR` derived by string parsing:**
- Issue: `int(os.getenv("SESSION_START", "08:00").split(":")[0])` — silently breaks on `SESSION_START=8` (no colon → IndexError), `SESSION_START=8h00`, etc.
- Files: `C:\trading-agent\config.py:80-81`
- Fix approach: Single robust parser used for both `SESSION_START_HOUR` and `SESSION_END_HOUR`, default-on-failure.

**MCP server uses module-level singletons:**
- Issue: `cfg = Config()`, `log = init_logger(cfg)`, `mt5 = Mt5Client(cfg)` evaluated at import in `mcp_server.py:36-38`. `init_logger` opens `trades.db` and creates schema purely as a side effect of importing the module.
- Files: `C:\trading-agent\mcp_server.py:36-38`
- Impact: Importing `mcp_server` (e.g. from a test) creates `logs/` and a SQLite DB. Tests must work around this.
- Fix approach: Move singletons inside `_bootstrap_mt5()` or a factory; lazy-init.

**Two `.env.example` files committed:**
- Issue: Both `C:\trading-agent\.env.example` and the untracked `C:\trading-agent\.env.example.new` exist.
- Impact: Confusion about which is canonical; risk of stale documentation.
- Fix approach: Diff and merge into a single `.env.example`, delete `.new`.

## Known Bugs

**`_get_int` accepts negative-only sign and returns default silently:**
- Symptoms: `INTRADAY_SCAN_INTERVAL_MINUTES=-` → returns default 15 with no warning. `INTRADAY_SCAN_INTERVAL_MINUTES=-5d` → -5 (then `max(1, -5) = 1`, value silently shifted).
- Files: `C:\trading-agent\config.py:22-41`
- Trigger: Misconfigured env var with sign or trailing unit.
- Workaround: Check logs for unexpected interval; explicit value required.

**`Mt5Client._retry` ignores `last_exc=None` edge case:**
- Symptoms: If `n=0`, the loop never executes, `last_exc` is `None`, and `raise last_exc` raises `TypeError: exceptions must derive from BaseException`.
- Files: `C:\trading-agent\mt5_client.py:26-39`
- Trigger: Calling `@_retry(0)` (not currently in code, but defensive concern).
- Fix: Validate `n >= 1` or raise a `RuntimeError` with diagnostic message instead.

**`scheduler.IntradayLoopScheduler` calls `mt5.get_account_state()` twice per cycle:**
- Symptoms: First call at `scheduler.py:545`, second "refresh" at `scheduler.py:573` even when no state-changing operation happened in between. Each call hits MT5 + `history_deals_get` for the day.
- Files: `C:\trading-agent\scheduler.py:545,573`
- Impact: Doubled MT5 round-trip latency per cycle, doubled chance of MT5 transient error.
- Fix: Reuse first snapshot unless an action (close_position) was taken; only refresh after close.

**`evaluate_open_position` uses naive `datetime.now()` (no tz) when no `now=` passed:**
- Symptoms: Comparison with `cfg.INTRADAY_START_HOUR/END_HOUR` is timezone-dependent; on Windows the system tz may not be Europe/Rome, so the "fuori finestra intraday" decision can fire 1-2 h off.
- Files: `C:\trading-agent\strategy.py:432` (`now = now or datetime.now()`)
- Trigger: Direct calls without `now=` (the live loop does pass `now`, but tests and any external caller do not).
- Fix: Default to `datetime.now(tz=ZoneInfo(cfg.OPERATING_TIMEZONE))`.

**`StrategyEnvironment.is_news_window` swallows callable errors:**
- Symptoms: If `news_window_callable` raises, returns `False` (i.e. trading is allowed). A buggy news provider effectively disables the safety gate without surfacing the error.
- Files: `C:\trading-agent\strategy.py:79-89`
- Fix: Add a configurable `fail_open` flag; default to fail-closed (return True) when the safety gate cannot be evaluated.

**`logger.init_logger` skips re-attach when handlers exist:**
- Symptoms: `if not logger.handlers:` means re-init in the same process keeps the original `RotatingFileHandler` even if `LOG_FILE` env changed; rotation policy from `cfg.LOG_ROTATION` (`weekly`/`daily`/`size`) is declared but never applied — only size-based 5MB rotation is wired.
- Files: `C:\trading-agent\logger.py:49-56`, `C:\trading-agent\config.py:131-134`
- Fix: Implement `TimedRotatingFileHandler` branch driven by `cfg.LOG_ROTATION`; ensure idempotent re-init.

**`risk_engine` margin loop never updates margin if `calc_order_margin` raises:**
- Symptoms: Inside the `while margin > free*0.9` loop (`risk_engine.py:131-143`), if the second `_call_retry` raises, the code does `break` but `margin` is stale; the size has already been reduced. The next `if size < 0.01: reject` branch may pass an under-sized trade as approved with stale margin assumption.
- Files: `C:\trading-agent\risk_engine.py:131-146`
- Fix: On exception, treat as reject ("Margin recompute failed").

**`MultiSymbolScanner.deep_analyze_top_candidates` ignores `cfg.AVOID_MAJOR_NEWS_TIMES` from inside scanner:**
- Symptoms: The scheduler passes `news_blocked=False` always (`scheduler.py:584`), and `_fetch_news_safe` is called only for sentiment, not as a blackout gate. `is_news_window` hook in `StrategyEnvironment` is a no-op until a callable is injected — and `main.py` never injects one.
- Files: `C:\trading-agent\main.py:44`, `C:\trading-agent\strategy.py:79-89`, `C:\trading-agent\scheduler.py:567-570`
- Impact: News blackout window advertised in config + STATE.md is effectively dead code today.
- Fix: Wire RSS-based news window detector to `StrategyEnvironment(cfg, log, news_window_callable=...)` in `main.py`.

**`backtest_suite.py` is a top-level script with side effects on import:**
- Symptoms: All code runs at module load (file I/O, prints, `random.shuffle`). No `if __name__ == "__main__":` guard. `SYMS`, `DATA_PATH` hard-coded.
- Files: `C:\trading-agent\backtest_suite.py:1-135`
- Impact: Cannot import for reuse; pytest collection of any sibling that imports it would execute the full backtest. Output JSON paths are committed (`backtest_results.json`, `backtest_trades.json`) — should be gitignored.
- Fix: Wrap in `main()`, add CLI args, gitignore JSON outputs.

## Security Considerations

**MT5 credentials in `.env` next to repo root:**
- Risk: `MT5_LOGIN`/`MT5_PASSWORD`/`MT5_SERVER` (`config.py:62-64`) are loaded from `.env` via `python-dotenv`. If `.env` is accidentally committed (e.g. via `git add .`) credentials leak.
- Files: `C:\trading-agent\config.py:62-64`, `C:\trading-agent\.env` (must remain gitignored)
- Current mitigation: `.env.example` shipped, `.gitignore` (assumed) excludes `.env`.
- Recommendations: Verify `.gitignore` covers `.env*` (except `.env.example`); add a pre-commit hook scanning for high-entropy strings; consider Windows DPAPI / Credential Manager for production.

**`CLAUDE_API_KEY` shipped through env:**
- Risk: Same as MT5; the key authorizes Anthropic API usage and billing.
- Files: `C:\trading-agent\config.py:89`
- Current mitigation: env-only.
- Recommendations: Rotate on any suspected leak; mark `CLAUDE_API_KEY` no-log and ensure no debug log echoes it.

**`feedparser` accepts arbitrary RSS URLs from env:**
- Risk: `RSS_FEEDS` (`config.py:200`) is a comma-separated list of URLs fed straight to `feedparser.parse`. No allow-list, no scheme check. SSRF if env contains `file://`/`http://localhost/` or internal endpoints.
- Files: `C:\trading-agent\news_aggregator.py:56-60`, `C:\trading-agent\config.py:200`
- Current mitigation: 5s socket timeout (`news_aggregator.py:17`), per-feed exception isolation.
- Recommendations: Validate URL scheme is `https?://`; deny `localhost`/private IPs.

**`mt5_client.send_order` uses fixed `deviation=20` only for closes, none for opens:**
- Risk: `send_order` (`mt5_client.py:171-182`) does not include `deviation` in the request, leaving the broker default. On wide spreads the order may slip beyond risk tolerance silently.
- Files: `C:\trading-agent\mt5_client.py:171-182`
- Recommendation: Make `deviation` configurable and add an upper bound that triggers reject if requote spread exceeds it.

**SQLite without parameterized table names but with WAL mode shared by multiple writers:**
- Risk: `logger.py`, `scheduler.py` (DailyRunStateStore + HeartbeatStore) all open `trades.db` independently with short-lived `sqlite3.connect`. Concurrent writes on Windows can deadlock under WAL contention.
- Files: `C:\trading-agent\logger.py:61-64`, `C:\trading-agent\scheduler.py:73-86,360-368`
- Mitigation: Consider a single connection-per-thread pattern, or migrate to one writer module.

## Performance Bottlenecks

**Per-symbol full deep analysis runs `get_ohlc(N=200)` synchronously, sequentially:**
- Problem: `MultiSymbolScanner.scan_universe` and `deep_analyze_top_candidates` iterate symbols sequentially; each call is a synchronous MT5 IPC.
- Files: `C:\trading-agent\scanner.py:138-146,176-188`, `C:\trading-agent\strategy.py:182`
- Cause: No batching, no parallelism. `cfg.INTRADAY_LOOKBACK_BARS=200` is fetched again in `_analyze_technical` even though `light_scan` already pulled 50 bars.
- Improvement path: Cache OHLC snapshot per cycle keyed by (symbol, timeframe); parallelize via threads (MT5 Python SDK is thread-safe under a single login).

**`history_deals_get` from start of day every call:**
- Problem: `Mt5Client.get_account_state` calls `mt5.history_deals_get(day_start, now_rome)` every invocation; each cycle (and twice per cycle, see bug above) walks the entire day's deal history.
- Files: `C:\trading-agent\mt5_client.py:88-92`
- Improvement path: Cache `today_realized_pnl` with short TTL; recompute only on close events.

**Indicator series allocate full-length arrays of `None`:**
- Problem: Each indicator (`sma`, `ema`, `rsi`, `atr`) allocates `[None] * n` and only the last value is used by callers (`_last_valid` walks from the tail).
- Files: `C:\trading-agent\indicators.py:8-50`, `C:\trading-agent\strategy.py:35-39`
- Impact: Negligible at N=200, but every call returns large lists kept in `indicators_snapshot` (`strategy.py:233-244`) and stored on `TechnicalSetup`.
- Improvement path: Either return only last value or store only summary stats in `indicators` dict.

## Fragile Areas

**Heartbeat overrun handling:**
- Files: `C:\trading-agent\scheduler.py:516-527`
- Why fragile: When a cycle exceeds `INTRADAY_SCAN_INTERVAL_MINUTES` (default 15 min), the loop calculates `slots_to_skip` and waits more — but if `time.monotonic` regressed (rare on Windows under sleep/wake) the math can produce negative `sleep_for` (clamped at 0) and busy-loop until back in sync.
- Safe modification: Add explicit lower bound on `sleep_for >= 1s`, log every skip.
- Test coverage: `tests/test_scheduler.py` covers happy path; overrun path (>interval) not exercised.

**`evaluate_open_position` re-runs full technical analysis per open position per cycle:**
- Files: `C:\trading-agent\strategy.py:418-478,456`
- Why fragile: For each open position the loop calls `_analyze_technical` (200-bar fetch + indicators); failures here are caught but the position remains HOLD, even if the SL has been already breached intraday. There is no cross-check with `tick.bid/ask` versus `position.stop_loss`.
- Safe modification: Add a quick pre-check on current price vs SL/TP before invoking full analysis.

**`anthropic` SDK pinned at undefined version (claude-sonnet-4-6):**
- Files: `C:\trading-agent\config.py:90`
- Why fragile: `CLAUDE_MODEL` default `claude-sonnet-4-6` is a deprecated/unreleased name (current series is `claude-sonnet-4-7`/`claude-opus-4-7`). Any path that still calls `claude_agent` (MCP `propose_trade` flow chained from Claude Desktop) will fail with model-not-found.
- Safe modification: Update default to a current model id and pin via env in production.

**Module-level mutation pattern (`_attach_news_sentiment`):**
- Files: `C:\trading-agent\config.py:183-204`
- Why fragile: Adds attributes to `Config` *class* at import time. If imports happen in unexpected order (e.g. via `mcp_server.py` chain) the class is mutated before tests can intercept. `getattr(cfg, "ENABLE_NEWS_SENTIMENT", False)` defensive reads in `scanner.py:284`, `strategy.py:649` confirm the implicit-attribute pattern is fragile.
- Safe modification: Move all news/sentiment fields into the main `Config` body.

## Scaling Limits

**Single-process daemon, single MT5 terminal:**
- Current capacity: 1 broker connection, sequential symbol processing, 15-min cadence (≈4 cycles/h).
- Files: `C:\trading-agent\main.py`, `C:\trading-agent\scheduler.py:460-528`
- Limit: With `INTRADAY_SYMBOLS` > ~20 the cycle may exceed the interval (overrun branch fires).
- Scaling path: Parallelize OHLC fetch within a cycle; or migrate to `asyncio` and a thread pool for MT5 calls; alternatively shard by symbol across processes (each with its own MT5 terminal).

**SQLite file shared by 3+ writers:**
- Current capacity: Low write rate (a few writes per cycle).
- Files: `C:\trading-agent\logger.py:33`, `C:\trading-agent\scheduler.py:317,712`
- Limit: WAL on Windows under network drives can serialize unpredictably; multi-process daemon would need explicit locking.
- Scaling path: One writer process; or move state to PostgreSQL.

## Dependencies at Risk

**`apscheduler` (kept but unused on the live path):**
- Risk: Live code does not need it after fase 16; still imported by `scheduler.py` top-level and required for tests.
- Impact: Surface area for security advisories without operational benefit.
- Migration plan: Drop legacy `Orchestrator` + remove `apscheduler` from `requirements.txt`.

**`anthropic` SDK (orphaned in critical path):**
- Risk: Same as above. Still imported by `claude_agent.py:9` and `mcp_server.py` indirectly.
- Migration plan: Decide whether MCP-side Claude flow is supported; if not, delete.

**`MetaTrader5 5.0.5735` Windows-only:**
- Risk: Pin tied to a specific TenTrade/FP Markets terminal build; version drift (broker upgrades the terminal) silently changes constants.
- Files: `C:\trading-agent\requirements.txt`, `C:\trading-agent\mt5_client.py`
- Migration plan: Add a runtime check on `mt5.version()` at startup; alert if outside tested range.

**`feedparser` external feeds:**
- Risk: `feedparser` is permissive; malformed feeds are common, and `bozo` flag is sometimes set even for valid feeds. Errors are isolated per feed (good) but consistent failure of all feeds silently disables the news layer.
- Migration plan: Surface "all feeds failed" as a `WARN` health metric, optionally fail-closed for `is_news_window`.

## Missing Critical Features

**News window blackout not wired:**
- Problem: `StrategyEnvironment.is_news_window` returns `False` unless a callable is injected, and `main.py` never injects one.
- Blocks: `AVOID_MAJOR_NEWS_TIMES`, `SENTIMENT_CONFLICT_*` envs are partially decorative.
- Files: `C:\trading-agent\main.py:44`, `C:\trading-agent\strategy.py:79-89`

**Rolling drawdown enforcement:**
- Problem: `ROLLING_DRAWDOWN_WINDOW_HOURS` and `ROLLING_DRAWDOWN_MAX_PERCENT` (config.py:125-130) are declared but no code path consults them. `would_proposal_exceed_drawdown` only uses `MAX_DAILY_DRAWDOWN_PERCENT`.
- Blocks: H24 rolling drawdown safety net.
- Files: `C:\trading-agent\config.py:125-130`, `C:\trading-agent\strategy.py:497-519`

**Persistence of `_followup_done` across restarts:**
- Problem: In-memory `set` on `Orchestrator` (`scheduler.py:167`); a daemon restart re-allows duplicate follow-ups. Acknowledged in `STATE.md` notes but unresolved.
- Files: `C:\trading-agent\scheduler.py:167`

**Health/alert surface:**
- Problem: HeartbeatStore tracks `consecutive_errors` and `consecutive_no_trade` (`scheduler.py:354-356,415-423`) but nothing reads them. No alert path on N consecutive errors.
- Files: `C:\trading-agent\scheduler.py:354-356`

**Multi-position protective close prioritization:**
- Problem: `_manage_open_positions` iterates positions in arbitrary list order; no tie-break when multiple positions need protection in the same cycle and broker rate-limits.
- Files: `C:\trading-agent\scheduler.py:662-709`

## Test Coverage Gaps

**MT5 integration (`mt5_client.py`):**
- What's not tested: `send_order`, `close_position`, `resolve_filling_mode`, `get_ohlc` are not unit-tested; only mocked indirectly via scheduler/strategy tests. `tests/test_mt5.py` is mostly skipped if MT5 unavailable.
- Files: `C:\trading-agent\mt5_client.py`, `C:\trading-agent\tests\test_mt5.py` (small, env-gated)
- Risk: Real broker quirks (filling mode mask, retcode handling) covered only by manual demo runs.
- Priority: High.

**`IntradayLoopScheduler.run_forever` overrun branch:**
- What's not tested: Overrun → skip-slots math (`scheduler.py:516-527`).
- Files: `C:\trading-agent\scheduler.py:501-528`
- Risk: Silent busy-loop or skipped trading windows.
- Priority: Medium.

**Logger rotation policy:**
- What's not tested: `cfg.LOG_ROTATION="daily"` / `"weekly"` paths — implementation is missing entirely (only size-based rotation is wired).
- Files: `C:\trading-agent\logger.py:49-56`
- Priority: Medium.

**News pipeline end-to-end:**
- What's not tested: Live `feedparser` against a real feed (only static fixtures in `tests/test_news_aggregator.py`); concurrent re-entry of `fetch_recent_news`.
- Files: `C:\trading-agent\news_aggregator.py`, `C:\trading-agent\tests\test_news_aggregator.py`
- Priority: Low (graceful degradation already in place).

**Risk engine margin reduction loop on exception:**
- What's not tested: The path where `mt5_client.calc_order_margin` raises *inside* the reduction loop (`risk_engine.py:131-143`).
- Files: `C:\trading-agent\risk_engine.py:131-143`, `C:\trading-agent\tests\test_risk.py`
- Priority: Medium.

**`backtest_suite.py`:**
- What's not tested: No tests at all; module runs as a script.
- Files: `C:\trading-agent\backtest_suite.py`
- Priority: Low (analysis tool, not production critical).

**`mcp_server.py` close_position branch under live mode:**
- What's not tested: Real `mt5.close_position` call from the MCP tool entry; only DRY_RUN branch.
- Files: `C:\trading-agent\mcp_server.py:407-427`, `C:\trading-agent\tests\test_mcp_tools_v2.py`
- Priority: Medium.

---

*Concerns audit: 2026-05-07*
