---
phase: 01-backtest-engine
plan: 03
subsystem: backtest
tags: [backtest, costs, yaml, BACK-03]
requires:
  - data/configs/costs.yaml (D-05)
  - PyYAML
provides:
  - backtest.costs.CostModel
  - backtest.costs.load_cost_model
  - backtest.costs._pip_params
affects:
  - Plan 04 (BacktestBroker.close_position will consume CostModel)
  - Plan 05 (engine ledger PnL writes)
tech-stack:
  added: []
  patterns: [frozen-dataclass, yaml.safe_load]
key-files:
  created: []
  modified:
    - backtest/costs.py
    - tests/test_backtest_costs.py
decisions:
  - "JPY detection via 'JPY' in symbol substring (covers USDJPY, EURJPY, GBPJPY)"
  - "load_cost_model accepts optional 'default' yaml key as fallback"
  - "All yaml numeric values float-cast (Pitfall 6 — yaml may parse ints)"
metrics:
  duration: ~5min
  completed: 2026-05-07
  tasks: 2/2
  tests: 5 passed
requirements: [BACK-03]
---

# Phase 01 Plan 03: Cost Model Summary

Pure-math `CostModel` dataclass and YAML loader for per-symbol transaction costs (spread + slippage + commission), enabling realistic PnL simulation for the backtest engine. Validates success criterion 3: a 1-pip spread on a 1-lot EUR/USD round-trip deducts exactly $10.00 USD.

## What Shipped

### `backtest/costs.py` (replaced plan-01 stub)

- `CostModel(frozen=True)` with 5 numeric fields:
  - `spread_pips`, `slippage_pips`, `commission_pips_round_trip` — cost components in pips
  - `pip_size` — 0.0001 USD-quoted, 0.01 JPY-quoted
  - `pip_value_usd` — USD value of 1 pip per standard lot at the entry price
- `total_cost_pips` property = sum of the 3 pip components
- `cost_usd(lots)` method = `lots * total_cost_pips * pip_value_usd`
- `_pip_params(symbol, price)` helper:
  - JPY-quoted (substring check) → `(0.01, 1000.0 / price)` — at price 150 ≈ $6.667/pip/lot
  - Other → `(0.0001, 10.0)` — exactly $10/pip/lot
  - Raises `ValueError` if JPY price ≤ 0
- `load_cost_model(symbol, entry_price, yaml_path)`:
  - Reads YAML with `yaml.safe_load` (T-1-06 mitigation, NOT `yaml.load`)
  - Falls back to `default:` key when symbol absent
  - Raises `KeyError` if neither symbol nor `default` present
  - Float-casts every value to defend against YAML int parsing (Pitfall 6)

### `tests/test_backtest_costs.py` (replaced plan-01 skip-stub)

5 tests — all green, no skips:

| Test | Asserts |
|------|---------|
| `test_eurusd_1pip_1lot` | **SC-3** — 1.0 spread + 0 slippage + 0 commission @ 1 lot → exactly $10.00 (tol 1e-9) |
| `test_usdjpy_pip_value` | `_pip_params("USDJPY", 150.0)` → `(0.01, 1000/150)` |
| `test_yaml_load` | EURUSD yaml params (0.5/0.3/0.5) → total 1.3 pips → cost_usd(1.0) = $13 |
| `test_yaml_unknown_symbol_raises` | `KeyError` on `XAUUSD` (absent and no default in fixture yaml) |
| `test_total_cost_pips_property` | `CostModel(0.5, 0.3, 0.5, ...).total_cost_pips == 1.3` |

## SC-3 Numeric Proof

```
spread        = 1.0 pip
slippage      = 0.0
commission    = 0.0
total_cost    = 1.0 pip
pip_value_usd = 10.0   (EUR/USD: 100_000 lot * 0.0001 = 10 USD)
lots          = 1.0
cost_usd      = 1.0 * 1.0 * 10.0 = 10.000000000 USD   ✅
```

USD/JPY validation (cross-check):
```
pip_size  = 0.01
price     = 150.0
pip_value = 100_000 * 0.01 / 150 = 1000 / 150 = 6.66666... USD per pip per lot
```

## Threat Mitigations

| Threat | Status | Verification |
|--------|--------|--------------|
| T-1-06 (yaml RCE via `yaml.load`) | mitigated | `grep -c "yaml.load(" backtest/costs.py` = 0 — only `yaml.safe_load` is used |
| T-1-05 (costs.yaml tampering) | accepted | Repo-tracked config; audit trail to be added by Plan 05 (`cost_yaml_hash` in `backtest_runs`) |

## Verification Run

```
$ python -m pytest tests/test_backtest_costs.py -x --tb=short -v
============================= test session starts =============================
collected 5 items

tests/test_backtest_costs.py::test_eurusd_1pip_1lot PASSED               [ 20%]
tests/test_backtest_costs.py::test_usdjpy_pip_value PASSED               [ 40%]
tests/test_backtest_costs.py::test_yaml_load PASSED                      [ 60%]
tests/test_backtest_costs.py::test_yaml_unknown_symbol_raises PASSED     [ 80%]
tests/test_backtest_costs.py::test_total_cost_pips_property PASSED       [100%]
============================== 5 passed in 0.13s ==============================
```

Backtest test cohort regression check: `pytest tests/test_backtest_*.py tests/test_legacy_cleanup.py tests/test_patterns.py tests/test_sentiment.py` → 31 passed, 23 skipped (Wave 0 stubs for plans 04–08, expected). Other tests in the repo (`test_mt5`, `test_strategy`, …) error at collection because `MetaTrader5` is not installed in this venv — pre-existing condition, unrelated to this plan.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed on the first attempt with all done-criteria met.

## Commits

| Task | Commit | Subject |
|------|--------|---------|
| 1 | `ed4d1ea` | feat(01-03): implement CostModel + load_cost_model (BACK-03) |
| 2 | `2969f27` | test(01-03): real BACK-03 cost tests incl. SC-3 $10/pip proof |

## Self-Check: PASSED

- `backtest/costs.py` — present, 59 LOC, imports `yaml`, defines `CostModel`/`_pip_params`/`load_cost_model`
- `tests/test_backtest_costs.py` — present, 47 LOC, 5 tests, no skip markers
- Commits `ed4d1ea` and `2969f27` confirmed in `git log`
- `python -c "from backtest.costs import CostModel, load_cost_model, _pip_params"` succeeds
- `grep -c "yaml.load(" backtest/costs.py` = 0
- `grep -c "pytest.mark.skip" tests/test_backtest_costs.py` = 0
- SC-3 asserted to 1e-9 tolerance and verified passing
