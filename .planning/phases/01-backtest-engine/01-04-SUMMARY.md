---
phase: 01-backtest-engine
plan: 04
subsystem: backtest
tags: [backtest, broker, protocol, wave-1]
dependency_graph:
  requires:
    - "models.BrokerProtocol (Plan 01)"
    - "backtest.costs.CostModel (Plan 03 — minimal stub added here, Plan 03 will expand)"
    - "backtest.loader.Bar (Plan 02 — minimal stub added here, Plan 02 will expand)"
  provides:
    - "backtest.broker.BacktestBroker — BrokerProtocol-compliant in-memory broker"
    - "backtest.broker.VirtualPosition — open-position dataclass"
    - "BacktestBroker.get_symbol_info — off-Protocol SimpleNamespace stub"
    - "advance(bar) returns closed-trade rows for engine ledger streaming (Plan 05)"
  affects:
    - "Plan 05 (engine drives broker.advance, consumes closed-trade rows)"
    - "Plan 02 will expand backtest/loader.py (Bar dataclass already locked here)"
    - "Plan 03 will expand backtest/costs.py (CostModel API already locked here)"
tech_stack:
  added: []
  patterns:
    - "typing.Protocol structural compliance (no inheritance) — runtime_checkable isinstance"
    - "deque(maxlen=N) bounded bar window — append-only, no future-leak path"
    - "entry_bar_index guard for off-by-one Pitfall 1"
    - "SimpleNamespace stub for off-Protocol get_symbol_info (research §Open Question 1)"
key_files:
  created:
    - .planning/phases/01-backtest-engine/01-04-SUMMARY.md
  modified:
    - backtest/broker.py (full implementation, 250+ lines)
    - tests/test_backtest_broker.py (11 real tests, replaces skip-stub)
    - backtest/loader.py (minimal Bar dataclass — Plan 02 expand point)
    - backtest/costs.py (minimal CostModel dataclass — Plan 03 expand point)
decisions:
  - "BacktestBroker does NOT inherit from BrokerProtocol — structural typing only (Pitfall 3 of Protocol gotchas)"
  - "Same-bar SL+TP conflict resolved SL-first (D-09 conservative per RESEARCH §BacktestBroker Fill Semantics)"
  - "Gap-through (bar.open beyond SL) fills at bar.open with reason SL_GAP (no phantom SL fill)"
  - "Pitfall 1: entry_bar_index guard — _check_sl_tp skips positions whose entry_bar_index == self._bar_index"
  - "send_order accepts optional context kwarg (Plan 05 will feed decision_context_json)"
  - "Cost deducted ONCE at close (round-trip cost in commission_pips_round_trip covers both legs)"
  - "MTM tracking on open positions deferred — Phase 1 PnL only realized at close (PositionInfo.profit=0.0)"
metrics:
  duration_minutes: 12
  completed: 2026-05-07
  tasks_completed: 2
  files_created: 1
  files_modified: 4
  commits: 2
  tests_added: 11
---

# Phase 01 Plan 04: BacktestBroker Summary

In-memory broker that powers BACK-02. Implements all four `BrokerProtocol` methods plus an off-Protocol `get_symbol_info` stub, with conservative SL/TP fill semantics (SL-first, SL_GAP at bar.open) and the Pitfall 1 same-bar close guard.

## BrokerProtocol Compliance Proof

```python
>>> from backtest.broker import BacktestBroker
>>> from backtest.costs import CostModel
>>> from models import BrokerProtocol
>>> b = BacktestBroker("EURUSD", "H1", 10_000.0, CostModel(0.5, 0.3, 0.5, 0.0001, 10.0))
>>> isinstance(b, BrokerProtocol)
True
```

`Mt5Client` (live broker) verified at the class-surface level (`hasattr` + `callable` for the four methods). Protocol is structural — any instance with matching method signatures passes `isinstance`. We deliberately do NOT instantiate `Mt5Client` in tests because that would attempt a live MT5 connect.

## SL/TP Conflict Resolution Example

Entry: BUY at 1.0950, SL=1.0900, TP=1.1000.
Next bar: open=1.0950, high=1.1000, low=1.0850, close=1.0920.

Both SL and TP are touched on this single bar. Per D-09 conservative resolution:

- `bar.open (1.0950) > SL (1.0900)` → no SL_GAP
- `bar.low (1.0850) <= SL (1.0900)` → close at SL=1.0900, reason `"SL"`
- TP check skipped (SL fired first)

PnL = (1.0900 - 1.0950) / 0.0001 = -50 pips × $10 × 0.1 lot = -$50 gross, less $1 cost = **-$51 net**.

This is verified by `test_sl_tp_priority_sl_first`.

## Gap-Through Example (SL_GAP)

Entry: BUY at 1.0950, SL=1.0900.
Next bar: open=1.0800 (gap below SL).

`bar.open (1.0800) <= SL (1.0900)` → close at `bar.open=1.0800`, reason `"SL_GAP"`.

This represents a real-broker gap-fill — the SL would not be honored at 1.0900 if the market opened at 1.0800. Verified by `test_gap_fill_sl_gap_buy` and `test_gap_fill_sl_gap_sell` (mirror for SELL).

## Cost Deduction Example

CostModel: spread=1.0, slippage=0.0, commission_round_trip=0.0, pip_size=0.0001, pip_value_usd=10.0.
`cost_usd(0.1)` = (1.0 + 0.0 + 0.0) × 10.0 × 0.1 = **$1.00**.

Flat trade (entry == exit, no price movement):
- gross_pnl_usd = 0.0
- net_pnl_usd = 0.0 - 1.00 = **-$1.00**
- balance: 10_000.00 → 9_999.00

Verified by `test_cost_applied_on_close`.

## Pitfall 1 (Off-by-One) Mitigation

`VirtualPosition.entry_bar_index` is set to `self._bar_index` at `send_order()` time. `_check_sl_tp(bar)` runs at the top of `advance(bar)` AFTER incrementing `_bar_index`, then explicitly skips positions whose `entry_bar_index == self._bar_index`.

But because `advance` increments `_bar_index` BEFORE calling `_check_sl_tp`, and `send_order` records the entry on the LAST advance's bar (so `entry_bar_index` was set to e.g. 1 when bar 1 was pushed), the next `advance(bar 2)` will increment `_bar_index` to 2 — and the guard `entry_bar_index == self._bar_index` (1 == 2) is False, so the position IS monitored on bar 2 (correct). The guard is a defensive safety net for any future code path that might call `_check_sl_tp` without advancing first. Verified by `test_no_same_bar_close_pitfall_1`.

## Test Suite Results

```
tests/test_backtest_broker.py::test_protocol_compliance              PASSED
tests/test_backtest_broker.py::test_no_future_leak                   PASSED
tests/test_backtest_broker.py::test_send_order_registers_at_last_close PASSED
tests/test_backtest_broker.py::test_sl_tp_priority_sl_first          PASSED
tests/test_backtest_broker.py::test_gap_fill_sl_gap_buy              PASSED
tests/test_backtest_broker.py::test_gap_fill_sl_gap_sell             PASSED
tests/test_backtest_broker.py::test_no_same_bar_close_pitfall_1      PASSED
tests/test_backtest_broker.py::test_cost_applied_on_close            PASSED
tests/test_backtest_broker.py::test_get_account_state_reflects_positions PASSED
tests/test_backtest_broker.py::test_get_symbol_info_jpy_vs_non_jpy   PASSED
tests/test_backtest_broker.py::test_get_ohlc_symbol_mismatch_returns_empty PASSED

============================= 11 passed in 0.13s ==============================
```

## Done Criteria Verification

| Check | Command | Result |
|-------|---------|--------|
| Protocol compliance | `isinstance(b, BrokerProtocol)` | True |
| File compiles | `python -m py_compile backtest/broker.py` | OK |
| No DB | `grep -c "import sqlite3" backtest/broker.py` | 0 |
| No logging | `grep -c "logging" backtest/broker.py` | 0 |
| Tests green | `pytest tests/test_backtest_broker.py -x` | 11 passed |

## Commits

- `7d250e0` — feat(01-04): implement BacktestBroker with SL/TP fill semantics
- `a0a77b0` — test(01-04): real BacktestBroker tests for Protocol + fill semantics

## Deviations from Plan

### [Rule 3 — Blocker] Added minimal Bar / CostModel stubs in Wave-1 parallel files

- **Found during:** Task 1 (cannot import `from backtest.loader import Bar` and `from backtest.costs import CostModel` — both files were single-line docstring stubs from Plan 01)
- **Issue:** Plans 02 and 03 (Wave 1) define those classes but had not landed yet (parallel wave). Plan 04 cannot test in isolation without them.
- **Fix:** Added the minimal `Bar` (frozen dataclass, attribute access per cross-plan contract) and `CostModel` (frozen dataclass with `cost_usd()` and `total_cost_pips`) — exactly matching the interface signatures in the plan-02 and plan-03 `<interfaces>` blocks. Plans 02/03 will expand these files (loader gets `load_bars`, costs gets `load_cost_model` + `_pip_params`).
- **Files modified:** `backtest/loader.py`, `backtest/costs.py`
- **Coordination note for Plans 02/03 executors:** The dataclass surface is locked — extending is fine, renaming fields would break Plan 04 tests.
- **Commit:** `7d250e0`

## Threat Surface Scan

No new trust boundaries introduced. `BacktestBroker` is in-memory only — no network, no FS writes, no DB. The threat model in PLAN.md (T-NoFutureLeak, T-OffByOne, T-1-07) remains the canonical register, and all three are mitigated and tested:

| Threat | Test | Status |
|--------|------|--------|
| T-NoFutureLeak | `test_no_future_leak` | mitigate ✓ |
| T-OffByOne | `test_no_same_bar_close_pitfall_1` | mitigate ✓ |
| T-1-07 | row dict carries entry_time/exit_time/exit_reason | accepted (Plan 05 ledger persists) |

## Self-Check: PASSED

- backtest/broker.py FOUND
- tests/test_backtest_broker.py FOUND
- backtest/loader.py FOUND
- backtest/costs.py FOUND
- .planning/phases/01-backtest-engine/01-04-SUMMARY.md FOUND
- Commit 7d250e0 FOUND
- Commit a0a77b0 FOUND
