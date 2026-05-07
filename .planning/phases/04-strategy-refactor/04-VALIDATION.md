---
phase: 04
slug: strategy-refactor
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: 04-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` or `pyproject.toml` — Wave 0 task if absent |
| **Quick run command** | `pytest tests/test_strategy_setups.py tests/test_strategy_confluence.py -x -q` |
| **Full suite command** | `pytest tests/test_strategy*.py -v` |
| **Estimated runtime** | <500ms full strategy suite (per SC-3) |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_strategy_setups.py tests/test_strategy_confluence.py -x -q`
- **After every plan wave:** `pytest tests/test_strategy*.py -v`
- **Before `/gsd-verify-work`:** Full suite green + `tests/test_strategy_regression.py` green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| STRAT-01 | Setup A detector returns ProposalDraft | unit | `pytest tests/test_strategy_setups.py::test_detect_a_breakout_ready -x` | ❌ W0 | ⬜ pending |
| STRAT-02 | Setup B reversal + counter-trend gate | unit | `pytest tests/test_strategy_setups.py::test_detect_b_reversal_counter_trend_gate -x` | ❌ W0 | ⬜ pending |
| STRAT-03 | Setup C compression NR4/NR7/squeeze | unit | `pytest tests/test_strategy_setups.py::test_detect_c_compression_nr7 -x` | ❌ W0 | ⬜ pending |
| STRAT-04 | Setup D pullback Fib | unit | `pytest tests/test_strategy_setups.py::test_detect_d_pullback_fib_38 -x` | ❌ W0 | ⬜ pending |
| STRAT-05 | 5-factor scorer booleans + grade | unit | `pytest tests/test_strategy_confluence.py::test_score_factors_all_true -x` | ❌ W0 | ⬜ pending |
| STRAT-06 | Grade→confidence + adjusters | unit | `pytest tests/test_strategy_confluence.py::test_confidence_adjusters -x` | ❌ W0 | ⬜ pending |
| STRAT-07 | ATR-based R:R per profile | unit | `pytest tests/test_strategy_proposal.py::test_rr_floor_conservative -x` | ❌ W0 | ⬜ pending |
| STRAT-08 | Purity gate (no broker/db/print) | static | `pytest tests/test_strategy_purity.py -x` | ❌ W0 | ⬜ pending |
| STRAT-09 | Same `evaluate_proposal_for_bar` live + backtest | integration | `pytest tests/test_strategy_regression.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_strategy_setups.py` — 4 detector unit stubs (STRAT-01..04)
- [ ] `tests/test_strategy_confluence.py` — 5-factor + grade + adjuster stubs (STRAT-05, STRAT-06)
- [ ] `tests/test_strategy_proposal.py` — ProposalDraft→TradeProposal + R:R stubs (STRAT-07)
- [ ] `tests/test_strategy_purity.py` — AST purity gate (STRAT-08)
- [ ] `tests/test_strategy_regression.py` — 10-fixture replay (STRAT-09 + SC-5)
- [ ] `tests/capture_regression_baseline.py` — one-shot pre-refactor capture script
- [ ] `tests/fixtures/strategy_regression_baseline.json` — captured pre-refactor output
- [ ] `config/strategy.yaml` — D-08 5-factor schema
- [ ] `conftest.py` — `mock_mt5_from_csv()` fixture if missing

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confidence calibration parity vs forex-trader-pro skill | STRAT-06 | Skill table is human-curated reference | Cross-check `config/strategy.yaml` adjuster values against forex-trader-pro SKILL.md confluence section |

---

## Validation Sign-Off

- [ ] All STRAT-* tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all 9 MISSING test files
- [ ] No watch-mode flags
- [ ] Feedback latency <10s
- [ ] `nyquist_compliant: true` set in frontmatter at phase gate

**Approval:** pending
