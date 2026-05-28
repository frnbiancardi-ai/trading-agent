# Phase 1: Backtest Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 01-backtest-engine
**Areas discussed:** Broker abstraction, Existing backtest_suite.py fate, Cost + walk-forward config location, Ledger persistence + bar timezone

---

## Broker abstraction shape

| Option | Description | Selected |
|--------|-------------|----------|
| BacktestBroker duck-types Mt5Client | Same method names, no Protocol formalism | |
| Extract Protocol/ABC now | typing.Protocol shared by Mt5Client + BacktestBroker | ✓ |
| StrategyEnvironment swap | Inject differently into Env, no Protocol | |

**User's choice:** Option 2, "minimal Protocol, tight scope."
**Notes:** Cover only methods strategy actually calls today (get_ohlc, send_order, get_account_state, close_position). Phase 4 may extend.

---

## Existing backtest_suite.py fate

| Option | Description | Selected |
|--------|-------------|----------|
| Coexist, deprecate later | Leave legacy untouched, mark superseded | |
| Replace entirely | Delete backtest_suite.py, new engine takes the name | ✓ |
| Coexist, ml_feedback migrated | Bridge outputs to new schema | |

**User's choice:** Replace entirely.

### Follow-up: ml_feedback/ archive

| Option | Description | Selected |
|--------|-------------|----------|
| Delete with backtest_suite.py | Clean removal | |
| Archive under .planning/archive/legacy-backtest/ | Out of code path, history kept | ✓ |
| Keep in place | Untouched | |

**User's choice:** Archive under `.planning/archive/legacy-backtest/`.

---

## Cost + walk-forward config location

### Cost params

| Option | Description | Selected |
|--------|-------------|----------|
| YAML under data/configs/costs.yaml | Per-symbol, diffable, runtime-loaded | ✓ |
| Config class env vars | Verbose for 3+ symbols × 3 params | |
| Python dict in module | Code-as-config | |
| Runtime kwarg only | No defaults | |

**User's choice:** YAML at `data/configs/costs.yaml`.

### Walk-forward harness shape

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling fixed-size window | Stable train size | |
| Expanding window | Train grows from start | |
| Configurable both | mode='rolling'\|'expanding', default rolling | ✓ |

**User's choice:** Configurable both (default rolling).

---

## Ledger persistence + bar timezone

### Trade ledger persistence

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory + parquet | pyarrow writer, schema-aligned for Phase 5 | |
| Extend trades.db SQLite | New table in existing logs/trades.db | ✓ |
| JSON per-run | Human-readable, slow on large ledgers | |

**User's choice:** Extend `logs/trades.db` SQLite.
**Notes:** Phase 5 will materialize parquet via `pd.read_sql` when ML training needs it — no parquet writer in Phase 1.

### Italian CSV source timezone

| Option | Description | Selected |
|--------|-------------|----------|
| Broker server time (EET/EEST) | Standard MT5 broker convention | |
| UTC | Simplest | |
| Europe/Rome | Italian source — maybe local | |
| Verify before locking | Defer, document during execute | |

**User's choice:** GMT-6 (free-text response).
**Notes:** GMT-6 is unusual for FX brokers — most run GMT+2/+3 or NY-anchored GMT-5. CONTEXT.md D-10 mandates verification against a known event candle (e.g. NFP on EUR/USD H1) before the loader is locked. Loader maps to `Etc/GMT+6` (POSIX inversion) and converts internally to UTC.

---

## Claude's Discretion

- Backtest module layout (`backtest/` subpackage default)
- Engine event loop shape (generator vs explicit step())
- Metrics return type (dataclass vs dict)
- BacktestBroker fill semantics for non-market orders (Phase 1: market only)
- Train/test ratio default for walk-forward (suggested 4:1)

## Deferred Ideas

- Multi-TF coordination in single run → Phase 4
- Limit/stop order simulation → when strategy emits non-market orders
- Parquet ledger writer → Phase 5
- BACK-07 (23.5y performance budget) → Phase 5
- Spread-widening slippage model → Phase 10
- Replace POSIX-inverted GMT-6 with broker-confirmed tz → after D-10 verification
