# Coding Conventions

**Analysis Date:** 2026-05-07

## Naming Patterns

**Files:**
- snake_case for all Python modules at repo root (`risk_engine.py`, `mt5_client.py`, `claude_agent.py`, `news_aggregator.py`, `daily_orchestrator`-related code in `scheduler.py`).
- Test files prefixed with `test_` and mirror the module name: `tests/test_risk.py`, `tests/test_strategy.py`, `tests/test_phase16.py`, `tests/test_mt5.py`.
- Documentation uses `UPPERCASE.md` at repo root: `README.md`, `STATE.md`, `PHASES.md`, `HANDOFF_PROTOCOL.md`, `COMMIT_CONVENTIONS.md`.

**Functions:**
- Public functions: `snake_case` (`evaluate_trade`, `init_logger`, `find_support_resistance`, `calculate_trend_strength`).
- Internal helpers prefixed with single underscore: `_get_bool`, `_get_list`, `_call_retry`, `_pip_size`, `_last_valid`, `_now_iso`, `_attach_news_sentiment` (see `config.py`, `risk_engine.py`, `strategy.py`, `logger.py`).
- Decorators are lowercase with leading underscore when private: `_retry` in `mt5_client.py:26`.

**Variables:**
- Local/instance variables: `snake_case` (`distance_pips`, `pip_value`, `volume_step`, `risk_amount`).
- Module-level constants: `UPPER_SNAKE_CASE`, often prefixed with `_` when private to the module: `_TZ_ROME`, `_RETRY_N`, `_LOGGER_NAME`, `_LIGHT_BARS`, `_TRADES_LOG_SCHEMA`, `TIMEFRAME_MAP`, `PROFILES`.
- Dunder-style internal caches: `_db_path`, `_filling_cache`.

**Types:**
- `PascalCase` dataclasses in `models.py`: `TradeProposal`, `AccountState`, `RiskDecision`, `OrderResult`, `ScanResult`, `StrategyOutcome`, `OpenPositionVerdict`, `SchedulerCycleRecord`, `NewsItem`, `SentimentAnalysis`.
- Service classes use `PascalCase`: `Mt5Client`, `IntradayStrategy`, `MultiSymbolScanner`, `StrategyEnvironment`, `IntradayLoopScheduler`, `HeartbeatStore`, `DailyRunStateStore`, `OperatingWindow`, `Orchestrator`, `ClaudeAgent`, `Config`.
- `Literal[...]` types from `typing` used to constrain string enums on dataclasses (`models.py:91`, `models.py:124`, `models.py:159`, `models.py:170`).

## Code Style

**Formatting:**
- No formatter config (no `pyproject.toml`, no `.black`, no `ruff.toml` detected at repo root).
- De-facto style is PEP8-ish, 4-space indent, double quotes preferred, trailing commas in multi-line literals (see `models.py`, `config.py:104-110`).
- Section dividers in long files use Unicode box-drawing comments: `# ── happy path ──` (`tests/test_risk.py:70`), `# ──── identify_entry_setup ────` (`tests/test_strategy.py:97`).

**Linting:**
- No linter config committed. Type hints used pervasively but not enforced via mypy/pyright config.

## Import Organization

**Order:** PEP8 grouping consistently observed (see `risk_engine.py:1-8`, `scanner.py:6-25`, `tests/test_phase16.py:13-40`).

1. `__future__` imports (`from __future__ import annotations` in newer modules — `tests/test_phase16.py:13`, `tests/test_scheduler.py:10`).
2. Standard library (`logging`, `datetime`, `math`, `zoneinfo`, `pathlib`, `sqlite3`, `os`, `functools`).
3. Third-party (`pytest`, `MetaTrader5 as mt5`, `anthropic`, `apscheduler.*`, `feedparser`, `dotenv`).
4. First-party / local (`from config import Config`, `from models import ...`, `from mt5_client import Mt5Client`, `from strategy import ...`).

Imports use absolute paths from repo root (flat layout, `pythonpath = .` in `pytest.ini`). No relative imports observed.

**Path Aliases:**
- None. Repo is a flat single-package layout — every module sits at repo root.

## Error Handling

**Patterns:**
- Retry helper for transient MT5 errors: closure decorator `_retry(n=3)` in `mt5_client.py:26-39`, plus inline `_call_retry(fn, *args, **kwargs)` in `risk_engine.py:22-29`. Both swallow exceptions across attempts and re-raise the last one.
- Reject-with-reason pattern: domain functions never raise on business-rule violations. Instead they return a typed result with `approved=False` and a human-readable Italian `reason` string. See `evaluate_trade` and the local `reject(reason)` closure in `risk_engine.py:44-52`.
- External-call exceptions caught and translated into rejections: `risk_engine.py:76-82` (`get_symbol_info`) and `risk_engine.py:123-129` (`calc_order_margin`).
- Config-level validation raises `ValueError` at import time for unknown enum values (`config.py:170-173`, `config.py:177-180`, `config.py:191-195`). Fail-fast on misconfiguration.
- MT5 boolean APIs: log error via module logger and return `False` rather than raising (`mt5_client.py:48-51`, `mt5_client.py:53-61`).

## Logging

**Framework:** stdlib `logging`. Centralized initializer `init_logger(cfg)` in `logger.py:41` configures a `RotatingFileHandler` (`maxBytes=5_000_000`, `backupCount=3`, UTF-8) on logger name `trading_agent`.

**Patterns:**
- Each module owns a private logger: `logger = logging.getLogger(__name__)` (`risk_engine.py:10`, `mt5_client.py:11`).
- Classes accept an optional `logger` / `log` parameter and fall back to `logging.getLogger(__name__)` (`scanner.py:37,44`, `strategy.py:65`).
- Italian messages, `%`-style formatting (lazy interpolation): `logger.info("Trade rifiutato: %s", reason)` (`risk_engine.py:45`), `logger.warning("retry %d/%d for %s: %s", ...)` (`mt5_client.py:36`).
- Domain audit goes to SQLite (`logs/trades.db`) via the schema defined in `logger.py:14-28`, separate from the rotating text log.

## Comments

**When to Comment:**
- Numbered phase comments mark the linear pipeline of `evaluate_trade`: `# 1. Kill switch giornaliero`, `# 2. Filtro sessione`, `# 3. Limiti SL in pips`, etc. (`risk_engine.py:54-148`).
- Italian inline notes explain non-obvious financial logic (e.g. JPY pip size note in `tests/test_mt5.py:41`).

**JSDoc/TSDoc:**
- Python triple-quoted docstrings on modules and public classes, written in Italian. Examples: `strategy.py:1-6`, `models.py:150-156` (`OpenPositionVerdict`), `tests/test_phase16.py:1-12`, `tests/test_scheduler.py:1-9`.
- Functions are mostly self-documenting (typed signatures + numbered step comments) and skip docstrings except where behavior is subtle (`config.py:24-26` `_get_int`).

## Function Design

**Size:** Most functions stay under ~40 lines. The notable exception is the linear pipeline `evaluate_trade` in `risk_engine.py:32-155` (~120 lines), kept long deliberately so the full risk decision is auditable in one place.

**Parameters:**
- Dependency injection over module globals: `Mt5Client`, `Config`, and loggers are passed in (`evaluate_trade(proposal, account, mt5_client, cfg)`, `IntradayStrategy(cfg, mt5, log)`).
- `cfg: Config | None = None` with `if cfg is None: cfg = Config()` fallback (`risk_engine.py:36-39`).
- Keyword-only overrides via `**overrides` in test fixtures (`tests/test_phase16.py:46-89`, `tests/test_strategy.py:19-44`).

**Return Values:**
- Domain functions return dataclasses, never tuples (`RiskDecision`, `StrategyOutcome`, `OpenPositionVerdict`, `OrderResult`).
- Indicator functions return same-length lists with leading `None`s for the warm-up window (`indicators.py:1-6`, `indicators.py:8-18`).
- Optional results use `T | None` (PEP 604 union syntax, `Python 3.10+`).

## Module Design

**Exports:**
- No `__all__` declarations. Public surface is whatever does not start with `_`.
- Modules import what they need by name (`from indicators import sma, ema, rsi, atr, ...`, `scanner.py:10-15`, `strategy.py:11-21`).

**Barrel Files:**
- None. Flat layout — each domain has its own top-level module.

## Type Hints

- PEP 585 / PEP 604 style throughout: `list[str]`, `dict[str, int]`, `int | None`, `Literal["BUY", "SELL"]`. Requires Python 3.10+. See `models.py`, `config.py:14`, `mt5_client.py:45`.
- Dataclasses use `field(default_factory=list)` for mutable defaults (`models.py:36`, `models.py:65`, `models.py:71`).

## Timezone Handling

- All wall-clock decisions use `ZoneInfo("Europe/Rome")` via the module-level constant `_TZ_ROME` (`risk_engine.py:12`, `logger.py:11`, `mt5_client.py:23`, `tests/test_phase16.py:43`).
- Never use `datetime.now()` without `tz=`; always `datetime.now(tz=_TZ_ROME)` (`risk_engine.py:67`, `logger.py:38`).

## Commit Conventions

Per `COMMIT_CONVENTIONS.md`:
- Conventional Commits format `<tipo>(<scope>): <descrizione>`.
- Allowed types: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`.
- Allowed scopes: `setup`, `config`, `models`, `mt5`, `risk`, `logger`, `execution`, `indicators`, `agent`, `mcp`, `tests`, `phase-N`, `state`, `handoff`.
- Phase checkpoints: `feat(phase-N): complete and validated`.
- One phase per commit. `STATE.md` always included with code from the same phase.
- Never commit `.env`, credentials, `logs/*.db`, `logs/*.log`.
- Push to origin after every `feat(phase-N): complete` and every `chore(handoff)`.
- No `Co-Authored-By` trailers (per user memory).

---

*Convention analysis: 2026-05-07*
