---
phase: 01-backtest-engine
verified: 2026-05-07T00:00:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 1: Backtest Engine — Verification Report

**Phase goal (ROADMAP):** Build an event-driven backtest framework that replays the existing Italian-format CSV historical bars one-at-a-time, applies realistic transaction costs, and exposes the same call surface as the live MT5 client so the strategy module can run identically in both environments.

**Verified:** 2026-05-07
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #   | Truth                                                                                                                            | Status     | Evidence                                                                                                                                                                          |
| --- | -------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Loader reads `data/historical/EURUSD/H1.csv`, chronological order, datetime as UTC                                              | VERIFIED   | `backtest/loader.py` reads semicolon-separated CSV, parses Data+Ora as DD/MM/YYYY, applies `_GMT6_OFFSET` (D-08), sorts asc by `dt_utc`, drops duplicates. `tests/test_backtest_loader.py` 4 tests passing including D-10 NFP 2018-02-02 13:30 UTC alignment regression (lines 54-82). |
| 2   | Backtest engine drives strategy through multi-month slice; non-empty ledger with per-trade decision context                     | VERIFIED   | `backtest/engine.py` `BacktestEngine.run()` loops bars, calls `strat.analyze_symbol`, builds proposal, runs `evaluate_trade`, opens via `broker.send_order(context=ctx_snapshot)`. `_build_ctx` captures setup_type/confidence/indicators dict, persisted to `decision_context_json` column in ledger. `test_backtest_engine.py::test_uptrend_breakout_*` validates non-empty ledger and ctx attached. |
| 3   | Cost model: 1-pip spread on 1-lot EUR/USD deducts exactly $10 USD                                                                | VERIFIED   | `backtest/costs.py` `CostModel.cost_usd(lots)` = lots × total_cost_pips × pip_value_usd. `tests/test_backtest_costs.py::test_eurusd_1pip_1lot` asserts `abs(cost - 10.0) < 1e-9`. PASSED. |
| 4   | Walk-forward produces N non-overlapping (train, test) slices; no look-ahead leakage                                              | VERIFIED   | `backtest/walk_forward.py` `walk_forward_slices()` enforces fold cap=10 (D-06), bar-count boundaries, train precedes test. `tests/test_backtest_walk_forward.py::test_no_overlap_rolling` and `max(train) < min(test)` assertions (line 54) — 7 tests passing.            |
| 5   | Metrics module returns Sharpe, max drawdown, hit rate, expectancy on hand-crafted ledger fixture                                 | VERIFIED   | `backtest/metrics.py` `compute_metrics()` returns `BacktestMetrics` (sharpe/sortino/max_drawdown_pct/hit_rate/expectancy_usd/profit_factor/avg_r). `tests/test_backtest_metrics.py::test_known_fixture` validates 5-trade fixture; 5 tests pass.                                |
| 6   | End-to-end: full EUR/USD H1 12-month backtest in <60s on dev laptop                                                              | VERIFIED   | `tests/test_backtest_engine.py::test_smoke_12month_under_60s` (lines 234-266) runs `run_backtest` for 2024-01-01..2025-01-01 with budget assertion `elapsed < 60.0`. Test PASSED in suite run (full 47-test backtest module suite completed in 8.43s end-to-end).               |

**Score:** 6 / 6 truths verified

### Required Artifacts

| Artifact                                  | Expected                                                            | Status   | Details                                                                                                       |
| ----------------------------------------- | ------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| `backtest/__init__.py`                    | package marker                                                      | VERIFIED | exists                                                                                                        |
| `backtest/loader.py`                      | Italian-CSV loader, GMT-6→UTC                                       | VERIFIED | 84 lines, complete impl, GMT-6 offset, date filters, dedupe                                                   |
| `backtest/costs.py`                       | CostModel + per-symbol YAML loader                                  | VERIFIED | 60 lines, JPY-aware pip params, YAML loading                                                                  |
| `backtest/broker.py`                      | BacktestBroker satisfies BrokerProtocol; SL/TP fill semantics       | VERIFIED | 278 lines, `advance/get_ohlc/send_order/get_account_state/close_position` + Pitfall-1 entry-bar guard          |
| `backtest/engine.py`                      | Event-driven engine; `run_backtest` convenience                     | VERIFIED | 343 lines, full loop, force-close at end, ledger persistence, run_id idempotency                              |
| `backtest/ledger.py`                      | SQLite writer, `backtest_runs`/`backtest_trades` schema             | VERIFIED | DDL with `IF NOT EXISTS`, parameterized inserts, batched executemany                                          |
| `backtest/walk_forward.py`                | Rolling/expanding slice generator, fold cap 10                      | VERIFIED | 60 lines, `_FOLD_CAP=10`, mode validation                                                                     |
| `backtest/metrics.py`                     | Sharpe/Sortino/MaxDD/hit/expectancy/PF/avg_r                        | VERIFIED | 134 lines; empty-ledger zero-safe; annualization by timeframe                                                 |
| `data/configs/costs.yaml`                 | Per-symbol cost params per D-05                                     | VERIFIED | EURUSD 0.5/0.3/0.5, GBPUSD 0.7/0.3/0.5, USDJPY 0.6/0.3/0.5                                                    |
| `models.py::BrokerProtocol`               | Protocol with 4 methods (get_ohlc/send_order/get_account_state/close_position) | VERIFIED | lines 200-228, `@runtime_checkable`                                                                  |
| `strategy.py` annotation update           | `mt5_client: BrokerProtocol` (D-02)                                 | VERIFIED | line 24 import, line 155 type annotation                                                                      |
| `.planning/archive/legacy-backtest/`      | grid_search.json, advanced_search.json, walkforward_full.json, verify_final.py + README per D-04 | VERIFIED | all 5 files present                                       |
| Legacy `backtest_suite.py` deleted (D-03) | Removed from repo                                                   | VERIFIED | file does not exist; `tests/test_legacy_cleanup.py` 3 tests passing                                           |

### Key Link Verification

| From                           | To                                                | Via                                         | Status |
| ------------------------------ | ------------------------------------------------- | ------------------------------------------- | ------ |
| `BacktestEngine.run`           | `IntradayStrategy.analyze_symbol` / `build_trade_proposal` | direct call (line 158, 168 of engine.py) | WIRED |
| `BacktestEngine.run`           | `risk_engine.evaluate_trade`                      | line 175 import + call                      | WIRED  |
| `BacktestEngine.run`           | `BacktestBroker`                                  | constructed line 120, injected to strategy as `mt5_client` line 127 | WIRED |
| `BacktestEngine.run`           | `LedgerWriter.record_run` / `insert_trades`       | lines 238-240                               | WIRED  |
| `BacktestBroker`               | `BrokerProtocol` (structural typing)              | implements get_ohlc/send_order/get_account_state/close_position | WIRED |
| `strategy.IntradayStrategy`    | `BrokerProtocol`                                  | constructor `mt5_client: BrokerProtocol` (line 155) | WIRED |
| `loader.load_bars`             | `engine.run_backtest`                             | line 321 call                               | WIRED  |
| `costs.load_cost_model`        | `engine.run_backtest`                             | line 324 call                               | WIRED  |

### Data-Flow Trace (Level 4)

| Artifact          | Data Variable      | Source                                                   | Produces Real Data | Status   |
| ----------------- | ------------------ | -------------------------------------------------------- | ------------------ | -------- |
| BacktestEngine    | `closed_trades`    | `BacktestBroker._close_virtual` triggered by `_check_sl_tp` on real bar OHLC | Yes (proven by uptrend test producing non-empty ledger) | FLOWING |
| LedgerWriter      | `backtest_trades` rows | `engine._row_for_ledger` → `insert_trades` real values from broker close events | Yes               | FLOWING |
| Strategy → Broker | `bars window`      | `BacktestBroker.advance` pushes from `load_bars` Italian CSV | Yes (4-test loader, 12-month smoke 1000+ bars consumed) | FLOWING |

### Behavioral Spot-Checks

| Behavior                                               | Command                                                                | Result                                | Status |
| ------------------------------------------------------ | ---------------------------------------------------------------------- | ------------------------------------- | ------ |
| Phase 1 backtest test suite passes                     | `pytest tests/test_backtest_*.py tests/test_legacy_cleanup.py`         | 47 passed in 8.43s                    | PASS   |
| Full importable suite (excl. apscheduler/MCP/PDF deps) | `pytest --ignore=...`                                                  | 125 passed, 4 skipped (MT5 only)       | PASS   |
| SC-3 1-pip 1-lot = $10                                 | `test_eurusd_1pip_1lot`                                                | exact match within 1e-9                | PASS   |
| SC-6 12-month <60s                                     | `test_smoke_12month_under_60s`                                         | runs under 60s, 1000+ bars consumed    | PASS   |
| D-10 NFP timezone alignment                            | `test_nfp_alignment` in test_backtest_loader.py                        | 13:30 UTC bar is top-range            | PASS   |

### Requirements Coverage

| Requirement | Source Plan(s)            | Description                                                                  | Status     | Evidence                                                            |
| ----------- | ------------------------- | ---------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------- |
| BACK-01     | 01-02                     | Italian-CSV loader (semicolon, DD/MM/YYYY, GMT-6→UTC)                        | SATISFIED  | `loader.py` + 4 loader tests including NFP regression               |
| BACK-02     | 01-04, 01-05              | Event-driven engine, same code path as live (BrokerProtocol)                 | SATISFIED  | `engine.py`, `broker.py`, `BrokerProtocol`, strategy.py annotation  |
| BACK-03     | 01-03                     | Cost model spread+commission+slippage configurable per-symbol                | SATISFIED  | `costs.py` + costs.yaml + `test_eurusd_1pip_1lot`                   |
| BACK-04     | 01-05                     | Equity curve + trade ledger + decision context                               | SATISFIED  | engine returns equity_curve, ledger has decision_context_json column |
| BACK-05     | 01-06                     | Walk-forward rolling/expanding, no overlap, no leakage                       | SATISFIED  | `walk_forward.py` + 7 tests                                         |
| BACK-06     | 01-07                     | Sharpe, Sortino, max DD, hit rate, expectancy, PF, avg-R                     | SATISFIED  | `metrics.py` BacktestMetrics + 5 tests + hand-crafted fixture       |

### Anti-Patterns Found

No blocker anti-patterns. Two informational notes:

| File                    | Line     | Pattern                                                          | Severity | Impact                                                                                |
| ----------------------- | -------- | ---------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------- |
| backtest/engine.py      | 198, 211 | private attribute access `broker._positions`, `broker._closed_trades`, `broker._balance`, `broker._close_virtual` | INFO | Engine and Broker are tightly coupled by design; documented and contained within Phase 1 package. Not a leak across module boundaries. |
| backtest/broker.py      | 181      | `profit=0.0` for open MTM (comment: "MTM tracking not implemented in Phase 1 — engine computes on close") | INFO | Documented intentional Phase-1 simplification; strategy never reads it. Phase 4 / 5 territory. |

### Decision Compliance (D-01..D-10)

| Decision | Requirement | Status |
|----------|-------------|--------|
| D-01     | Minimal BrokerProtocol (4 methods) | VERIFIED — models.py:205-228 |
| D-02     | Strategy consumes Protocol, no fork | VERIFIED — strategy.py:24,155 |
| D-03     | Delete `backtest_suite.py` | VERIFIED — file absent |
| D-04     | Move ml_feedback to `.planning/archive/legacy-backtest/` | VERIFIED — 5 files archived |
| D-05     | costs.yaml per-symbol | VERIFIED — data/configs/costs.yaml |
| D-06     | Walk-forward rolling default, fold cap 10, train_ratio default 4 | VERIFIED — walk_forward.py:11,18 |
| D-07     | logs/trades.db backtest_runs/backtest_trades | VERIFIED — ledger.py |
| D-08     | GMT-6 source → UTC | VERIFIED — loader.py:11,51 |
| D-09     | Decision time = bar close, no partials | VERIFIED — broker.py:153 (close as entry), engine starts after lookback |
| D-10     | NFP timezone cross-check | VERIFIED — test_backtest_loader.py NFP regression test |

### Human Verification Required

None. All success criteria are programmatically verifiable and were verified.

### Gaps Summary

No gaps. All 6 ROADMAP success criteria verified by code + passing tests. All 6 BACK requirements satisfied. All 10 locked decisions (D-01..D-10) honored. Legacy cleanup (D-03/D-04) completed. 47/47 phase-1 tests pass; 125/125 importable repo-wide tests pass (4 MT5-only skips, 6 pre-existing collection errors due to optional deps `apscheduler`/MCP/OCR libs unrelated to Phase 1).

---

## VERIFICATION PASSED

_Verified: 2026-05-07_
_Verifier: Claude (gsd-verifier)_
