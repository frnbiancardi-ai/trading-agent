---
phase: 1
slug: backtest-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (existing, `pythonpath = .`) |
| **Quick run command** | `pytest tests/test_backtest_*.py -x --tb=short` |
| **Full suite command** | `pytest -x --tb=short` |
| **Estimated runtime** | quick ~5s · full ~30s (current 173 tests + new) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_backtest_*.py -x --tb=short`
- **After every plan wave:** Run `pytest -x --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | (infra) | — | N/A | scaffold | `python -c "import backtest"` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | (infra) | — | N/A | dep-check | `python -c "import yaml"` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | (infra) | — | N/A | scaffold | `test -f data/configs/costs.yaml` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 0 | (infra) | — | N/A | scaffold | `test -f tests/fixtures/eurusd_5bars.csv` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | BACK-01 | — | Loader yields UTC-sorted Bar list, skips partial | unit | `pytest tests/test_backtest_loader.py::test_basic_load -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | BACK-01 (D-08) | — | GMT-6 bar at 07:00 source = 13:00 UTC | unit | `pytest tests/test_backtest_loader.py::test_gmt6_utc_offset -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 1 | BACK-01 | — | Column header strip handles leading spaces | unit | `pytest tests/test_backtest_loader.py::test_column_strip -x` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 1 | BACK-01 (D-10) | — | NFP candle alignment on real CSV | integration | `pytest tests/test_backtest_loader.py::test_nfp_alignment -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | BACK-03 | — | 1-pip 1-lot EUR/USD = $10.00 | unit | `pytest tests/test_backtest_costs.py::test_eurusd_1pip_1lot -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 1 | BACK-03 | — | USD/JPY pip value at 150 = $6.67 | unit | `pytest tests/test_backtest_costs.py::test_usdjpy_pip_value -x` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 1 | BACK-03 | — | YAML loader produces per-symbol CostModel | unit | `pytest tests/test_backtest_costs.py::test_yaml_load -x` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 1 | BACK-02 | — | BrokerProtocol type-check passes for Mt5Client + BacktestBroker | unit | `pytest tests/test_backtest_broker.py::test_protocol_compliance -x` | ❌ W0 | ⬜ pending |
| 1-04-02 | 04 | 1 | BACK-02 | T-NoFutureLeak | get_ohlc returns only bars in window | unit | `pytest tests/test_backtest_broker.py::test_no_future_leak -x` | ❌ W0 | ⬜ pending |
| 1-04-03 | 04 | 1 | BACK-02 | — | send_order registers virtual position, charges costs | unit | `pytest tests/test_backtest_broker.py::test_send_order -x` | ❌ W0 | ⬜ pending |
| 1-04-04 | 04 | 1 | BACK-02 | — | SL/TP same-bar conflict resolves to SL first | unit | `pytest tests/test_backtest_broker.py::test_sl_tp_priority -x` | ❌ W0 | ⬜ pending |
| 1-04-05 | 04 | 1 | BACK-02 | — | Gap-through fill at bar.open not at SL level | unit | `pytest tests/test_backtest_broker.py::test_gap_fill -x` | ❌ W0 | ⬜ pending |
| 1-05-01 | 05 | 2 | BACK-02 | — | 5-bar fixture run produces non-empty ledger | integration | `pytest tests/test_backtest_engine.py::test_engine_5bar_fixture -x` | ❌ W0 | ⬜ pending |
| 1-05-02 | 05 | 2 | BACK-04 | — | Ledger row has decision_context_json populated | integration | `pytest tests/test_backtest_engine.py::test_decision_context -x` | ❌ W0 | ⬜ pending |
| 1-05-03 | 05 | 2 | BACK-04 | — | Equity curve monotonically updates per closed trade | unit | `pytest tests/test_backtest_engine.py::test_equity_curve -x` | ❌ W0 | ⬜ pending |
| 1-05-04 | 05 | 2 | BACK-04 | — | backtest_runs + backtest_trades schema created | unit | `pytest tests/test_backtest_ledger.py::test_schema_created -x` | ❌ W0 | ⬜ pending |
| 1-06-01 | 06 | 2 | BACK-05 | — | Rolling walk-forward 3-fold no overlap | unit | `pytest tests/test_backtest_walk_forward.py::test_no_overlap -x` | ❌ W0 | ⬜ pending |
| 1-06-02 | 06 | 2 | BACK-05 | — | Expanding mode train grows, test fixed | unit | `pytest tests/test_backtest_walk_forward.py::test_expanding_mode -x` | ❌ W0 | ⬜ pending |
| 1-06-03 | 06 | 2 | BACK-05 | — | fold_cap=10 enforced (ValueError on 11) | unit | `pytest tests/test_backtest_walk_forward.py::test_fold_cap -x` | ❌ W0 | ⬜ pending |
| 1-06-04 | 06 | 2 | BACK-05 | T-NoFutureLeak | Train slice strictly before test slice | unit | `pytest tests/test_backtest_walk_forward.py::test_temporal_order -x` | ❌ W0 | ⬜ pending |
| 1-07-01 | 07 | 2 | BACK-06 | — | Sharpe / MaxDD / hit_rate / expectancy match fixture to 4 decimals | unit | `pytest tests/test_backtest_metrics.py::test_known_fixture -x` | ❌ W0 | ⬜ pending |
| 1-07-02 | 07 | 2 | BACK-06 | — | Empty ledger returns zero/inf-safe metrics | unit | `pytest tests/test_backtest_metrics.py::test_empty_ledger -x` | ❌ W0 | ⬜ pending |
| 1-07-03 | 07 | 2 | BACK-06 | — | Annualization factor by TF (M15/M30/H1) correct | unit | `pytest tests/test_backtest_metrics.py::test_annualization -x` | ❌ W0 | ⬜ pending |
| 1-08-01 | 08 | 3 | SC-6 | — | EUR/USD H1 12 months runs <60s | smoke | `pytest tests/test_backtest_engine.py::test_smoke_12month_under_60s -x` | ❌ W0 | ⬜ pending |
| 1-08-02 | 08 | 3 | (cleanup) | — | backtest_suite.py deleted, ml_feedback archived | unit | `pytest tests/test_legacy_cleanup.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backtest/__init__.py` and module stubs (`loader.py`, `engine.py`, `costs.py`, `broker.py`, `walk_forward.py`, `metrics.py`, `ledger.py`) — needed before any test imports
- [ ] `tests/test_backtest_loader.py` — covers BACK-01
- [ ] `tests/test_backtest_costs.py` — covers BACK-03
- [ ] `tests/test_backtest_broker.py` — covers BrokerProtocol + BacktestBroker fill semantics
- [ ] `tests/test_backtest_engine.py` — covers BACK-02, BACK-04, SC-6 smoke
- [ ] `tests/test_backtest_walk_forward.py` — covers BACK-05
- [ ] `tests/test_backtest_metrics.py` — covers BACK-06
- [ ] `tests/test_backtest_ledger.py` — covers SQLite schema creation
- [ ] `tests/test_legacy_cleanup.py` — covers backtest_suite.py deletion + ml_feedback archive
- [ ] `tests/fixtures/eurusd_5bars.csv` — hand-crafted 5-bar GMT-6 fixture
- [ ] `tests/conftest.py` — shared fixtures (in-memory SQLite, sample BrokerProtocol stub)
- [ ] `data/configs/costs.yaml` — per-symbol cost params
- [ ] `pip install pyyaml` + add to `requirements.txt`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Performance budget on dev laptop | SC-6 | Hardware-dependent — CI may differ | Run `pytest tests/test_backtest_engine.py::test_smoke_12month_under_60s -x` on the actual dev machine; expect <60s. Document machine spec in commit if margin <2x. |
| GMT-6 D-10 sign-off | D-10 | Researcher already verified vs 3 NFP candles; planner should require executor to re-confirm against a freshly chosen NFP candle on a different year before merging the loader | After loader is implemented, pick NFP first-Friday from 2018, 2020, 2023 and assert UTC-converted timestamps match published 13:30 UTC release window |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
