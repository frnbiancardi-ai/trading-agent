# Phase 1: Backtest Engine - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver an event-driven backtest framework that replays Italian-format CSV historical bars one-at-a-time through the same strategy code path used by the live scheduler, applies realistic transaction costs (spread + slippage + commission), produces a trade ledger with per-trade decision context, and exposes a walk-forward validation harness with per-slice metrics (Sharpe, Sortino, MaxDD, hit rate, expectancy, profit factor, avg-R).

Phase 1 ships the framework. Phase 4 makes the strategy fully pure. Phase 5 runs the full 23.5y × 3 pairs × 3 TFs baseline. Phase 1 may stub strategy side effects at the broker/IO boundary.

</domain>

<decisions>
## Implementation Decisions

### Broker abstraction
- **D-01:** Define a minimal `BrokerProtocol` (`typing.Protocol`) covering only the methods the strategy actually invokes today (`get_ohlc`, `send_order`, `get_account_state`, `close_position`). Tight scope — not a full mirror of `Mt5Client`. Live path keeps `Mt5Client`; backtest path provides a `BacktestBroker` implementing the same Protocol.
- **D-02:** Strategy/`StrategyEnvironment` consume the Protocol, not the concrete class. No live-vs-backtest fork in strategy code. Phase 4 may extend the Protocol if pure-function refactor reveals more methods.

### Legacy code disposition
- **D-03:** Delete `backtest_suite.py` (RSI_SMA pandas grid, superseded). New event-driven engine takes module space (`backtest/` package).
- **D-04:** Move `ml_feedback/` (grid_search.json, advanced_search.json, walkforward_full.json, verify_final.py) to `.planning/archive/legacy-backtest/`. Historical record preserved, out of code path.

### Configuration surface
- **D-05:** Cost params live in `data/configs/costs.yaml`, per-symbol sections (`spread_pips`, `slippage_pips`, `commission_pips_round_trip`). Loader reads at `run_backtest()` start. Defaults from PROJECT.md (0.5 / 0.3 / 0.5 pip).
- **D-06:** Walk-forward harness exposes `mode='rolling'|'expanding'`, default `rolling`. Fold cap = 10 (per PROJECT.md). Train/test ratio configurable, sensible default (e.g. 4:1).

### Persistence
- **D-07:** Trade ledger persists to existing `logs/trades.db` SQLite — new table `backtest_trades` (and `backtest_runs` for run-level metadata: run_id, symbol, tf, date_range, cost_yaml_hash, started_at, finished_at). Phase 5 will materialize parquet for ML via `pd.read_sql` at training time — no parquet writer in Phase 1.

### Time semantics
- **D-08:** Italian CSV source timezone = **GMT-6** (user-specified). Loader stamps source rows as `Etc/GMT+6` (POSIX inversion) and converts to UTC for the engine. All engine-internal timestamps UTC.
- **D-09:** Decision time = bar close timestamp. Incomplete/partial bars skipped. Strategy never sees a bar before its close.
- **D-10:** **Verify timezone before locking the loader** — researcher/executor must cross-check at least one known event candle (e.g. NFP first-Friday 13:30 UTC reaction) against the assumed GMT-6 stamp on EUR/USD H1. If alignment fails, document discovered tz and update D-08 before merging the loader.

### Claude's Discretion
- Backtest module layout (single file vs `backtest/` package) — default to package: `backtest/{loader.py, engine.py, costs.py, broker.py, walk_forward.py, metrics.py, ledger.py}`.
- Engine event loop shape (generator-driven bar stream vs explicit step()).
- Metrics module return type (dataclass vs dict).
- BacktestBroker fill semantics for limit orders if strategy uses them (likely market-only in Phase 1; Phase 4 may add).
- Pyarrow optionality: not needed for Phase 1 (SQLite only).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project locked specs
- `.planning/PROJECT.md` — milestone scope, constraints, key decisions table (cost defaults, fold cap, performance budget)
- `.planning/REQUIREMENTS.md` §Backtest Engine — BACK-01..BACK-06 (BACK-07 lives in Phase 5)
- `.planning/ROADMAP.md` §Phase 1 — goal, success criteria, requirement mapping

### Codebase maps (current state)
- `.planning/codebase/STRUCTURE.md` — flat root layout, where new modules go, naming conventions
- `.planning/codebase/ARCHITECTURE.md` — strategy/scanner/scheduler/broker layering
- `.planning/codebase/STACK.md` — Python 3.12 (Anaconda), pandas, MetaTrader5
- `.planning/codebase/INTEGRATIONS.md` — Mt5Client surface, RSS, MCP server
- `.planning/codebase/CONVENTIONS.md` — snake_case modules, dataclasses, `_retry` pattern
- `.planning/codebase/TESTING.md` — pytest layout under `tests/`, co-named files
- `.planning/codebase/CONCERNS.md` — known fragility / refactor hot spots

### Reference modules to read before coding
- `mt5_client.py` — surface to mirror in BrokerProtocol (get_ohlc, send_order, get_account_state, close_position, _retry, filling-mode resolver)
- `strategy.py` — `IntradayStrategy.run_cycle`, `evaluate_open_position`, `StrategyEnvironment` (current side-effect surface to stub at boundary)
- `models.py` — domain dataclasses (TradeProposal, RiskDecision, OrderResult) — extend, don't fork
- `risk_engine.py` — `evaluate_trade`, profile table — backtest must invoke unchanged
- `logger.py` — `_trades_db_path`, schema patterns for `CREATE TABLE IF NOT EXISTS` — mirror for `backtest_trades` / `backtest_runs`
- `indicators.py`, `patterns.py` — pure helpers already side-effect-free

### Skills (consult during implementation)
- `.claude/skills/forex-algo-dev/` — bar boundary discipline, no future leakage, walk-forward, transaction-cost realism, calibration
- `.claude/skills/forex-trader-pro/` — A/B/C/D setup definitions, 5-factor confluence (relevant for ledger decision context fields)

### Data
- `data/historical/{EURUSD,GBPUSD,USDJPY}/{H1,M15,M30}.csv` — semicolon Italian format, columns `Data; Ora; Open; High; low; Close; Volume`, DD/MM/YYYY HH:MM:SS, GMT-6 source per D-08

### Cost config (to be created in this phase)
- `data/configs/costs.yaml` — per-symbol cost params, defaults from PROJECT.md

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Mt5Client._retry` decorator pattern — pull conceptually for any retry needs in loader (file IO).
- `logger._trades_db_path` + schema-creation pattern — copy for `backtest_trades` / `backtest_runs` tables.
- `risk_engine.evaluate_trade` + `PROFILES` — invoke unchanged from backtest engine.
- `indicators.py` + `patterns.py` — already pure, consumable directly by backtest.
- `models.TradeProposal` / `RiskDecision` / `OrderResult` — ledger row composes from these.

### Established Patterns
- Flat root layout — backtest goes in `backtest/` subpackage (only deeper-than-root case besides `scripts/`, `tests/`, `prompts/`).
- Snake_case modules, PascalCase classes, leading underscore for module-private helpers.
- `CREATE TABLE IF NOT EXISTS` on owning module init, single shared `logs/trades.db`.
- Config knobs go on `Config` class via `_get_*` helpers — but cost params bypass this pattern in favor of YAML (D-05) because cardinality (3 symbols × 3 fields) makes env-var explosion ugly. Document the deviation in `config.py` docstring.
- Tests in `tests/test_<module>.py` co-named with production module.

### Integration Points
- `IntradayStrategy.run_cycle` → must accept Protocol-typed broker so backtest can pass BacktestBroker (Phase 4 will polish; Phase 1 minimum viable swap).
- `StrategyEnvironment` (`strategy.py:50`) — broker injection point.
- `risk_engine.evaluate_trade` — invoke from backtest as-is.
- `logs/trades.db` — extend with new tables; do not rename existing tables.
- `pytest.ini` — new tests under `tests/test_backtest_*.py` discovered automatically.

</code_context>

<specifics>
## Specific Ideas

- Cost defaults baked into `data/configs/costs.yaml` initial commit: EUR/USD 0.5/0.3/0.5, GBP/USD 0.7/0.3/0.5, USD/JPY 0.6/0.3/0.5 pip (planner refines if research finds better defaults).
- Walk-forward defaults: rolling, 10 folds, train_bars : test_bars = 4:1, no overlap.
- Performance budget: full backtest of EUR/USD H1 last 12 months <60s on dev laptop (success criterion 6); full 9-slice 23.5y run <30 min (PROJECT.md, validated in Phase 5).
- Engine smoke test fixture: hand-crafted ledger from forex-algo-dev skill examples — verify Sharpe / MaxDD / hit rate / expectancy match expected values to 4 decimals.
- Cost realism unit test: 1-pip-spread fill on 1-lot EUR/USD deducts the exact expected USD amount per success criterion 3.

</specifics>

<deferred>
## Deferred Ideas

- Multi-TF event coordination in a single backtest run (e.g. M15 + H1 simultaneously) — Phase 4 territory once strategy refactor lands and confluence scorer needs multi-TF input.
- Limit / stop order simulation in BacktestBroker — Phase 1 supports market orders only. Add when strategy actually emits non-market orders.
- Parquet writer for ledger — Phase 5 materializes from SQLite when ML training needs it.
- BACK-07 (full 23.5y performance budget validation) — explicitly Phase 5, not Phase 1.
- Slippage model upgrade beyond fixed-pip random (e.g. spread-widening on news) — Phase 10 (intermarket + news).
- Replacing `Etc/GMT+6` POSIX inversion with broker-confirmed tz string — happens after D-10 verification.

</deferred>

---

*Phase: 01-backtest-engine*
*Context gathered: 2026-05-07*
