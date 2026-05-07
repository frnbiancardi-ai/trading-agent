---
phase: 05
slug: baseline-backtest
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: 05-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (unpinned in requirements.txt) |
| **Config file** | `pytest.ini` (`pythonpath=.`) |
| **Quick run command** | `pytest tests/test_baseline_*.py -x --tb=short` |
| **Full suite command** | `pytest -x --tb=short` |
| **Estimated runtime** | <2 min full baseline suite (single-slice perf test mocked) |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_baseline_<changed_module>.py -x --tb=short` (sub-30s per module)
- **After every plan wave:** `pytest tests/ -x --tb=short` (full suite, target <2 min)
- **Before `/gsd-verify-work`:** Full suite green + manual smoke `python scripts/run_baseline_backtest.py` (full 27-run, accepts <30 min wall-clock)
- **Max feedback latency:** ~30 seconds (per-task), ~120 seconds (per-wave)

---

## Per-Task Verification Map

| Req / Decision | Behavior | Test Type | Automated Command | File Exists | Status |
|----------------|----------|-----------|-------------------|-------------|--------|
| BACK-07 | Single-slice perf budget (<2 min after warm-up, mocked detector) | unit | `pytest tests/test_baseline_runner.py::test_single_slice_perf_budget -x` | ❌ W0 | ⬜ pending |
| BACK-07 | Full 27-run completes <30 min on dev laptop | smoke (manual) | `time python scripts/run_baseline_backtest.py` | ❌ W0 | ⬜ pending |
| INT-01 | `baseline_decisions.parquet` schema (D-02 — identità + ProposalDraft + ExtendedIndicators + ctx + outcome) | unit | `pytest tests/test_baseline_dataset_writer.py::test_decisions_schema -x` | ❌ W0 | ⬜ pending |
| INT-01 | `baseline_drafts.parquet` schema (D-03 — per-bar per-detector READY/FORMING/NONE) | unit | `pytest tests/test_baseline_dataset_writer.py::test_drafts_schema -x` | ❌ W0 | ⬜ pending |
| INT-01 / D-18 | `baseline-{date}.md` report: header + 27-row table + appendix hashes | unit | `pytest tests/test_baseline_report_writer.py::test_report_structure -x` | ❌ W0 | ⬜ pending |
| INT-01 / D-19 | 27 PNG equity curves prodotti, ognuno 2-subplot (equity + DD shaded) | unit | `pytest tests/test_baseline_plot_writer.py::test_equity_png_structure -x` | ❌ W0 | ⬜ pending |
| D-21 | No future leakage (indicators): `compute_all_extended(bars[:i+1]).field[-1] == compute_all_extended(bars).field[i]` | unit | `pytest tests/test_baseline_no_future_leakage.py::test_indicator_full_slice_equals_recompute -x` | ❌ W0 | ⬜ pending |
| D-21 | Temporal ordering invariant: `decision_ts ≤ entry_ts < exit_ts` ogni riga dataset | integration | `pytest tests/test_baseline_no_future_leakage.py::test_decision_dataset_temporal_ordering -x` | ❌ W0 | ⬜ pending |
| D-22 | Bar-close discipline: `entry_price == next_bar.open ± slippage` (non `bar.close`) | unit | `pytest tests/test_baseline_no_future_leakage.py::test_entry_at_next_bar_open -x` | ❌ W0 | ⬜ pending |
| D-14 | Idempotency: re-run senza `--force` skip; con `--force` overwrite | unit | `pytest tests/test_baseline_runner.py::test_idempotency_skip_and_force -x` | ❌ W0 | ⬜ pending |
| D-15 | Hybrid orchestration: indicator cache computed UNA volta per slice (3 profile riusano) | unit | `pytest tests/test_baseline_runner.py::test_indicator_cache_reused_across_profiles -x` (mock + spy) | ❌ W0 | ⬜ pending |
| D-16 | SQLite WAL: 9 worker concurrent INSERT, no lost rows, no `database is locked` after retry | integration | `pytest tests/test_baseline_wal.py::test_wal_concurrent_writes -x` | ❌ W0 | ⬜ pending |
| D-17 | Determinism: `hashlib.sha256(run_id)` → same `slippage_seed_effective` cross-run, cross-process (NO Python `hash()`) | unit | `pytest tests/test_baseline_determinism.py::test_seed_reproducibility -x` | ❌ W0 | ⬜ pending |
| D-17 | Config hashes (sha256 di costs.yaml/strategy.yaml/baseline.yaml) match file content in `backtest_runs` | unit | `pytest tests/test_baseline_determinism.py::test_config_hash_matches -x` | ❌ W0 | ⬜ pending |
| D-23 | Cost realism: `spread_pips + commission_pips_round_trip` deducted on entry, slippage entry+exit | unit | `pytest tests/test_baseline_runner.py::test_cost_deduction -x` | ❌ W0 | ⬜ pending |
| D-19 / D-20 | matplotlib backend `"Agg"` enforced nel worker (no GUI hang Windows) | unit | `pytest tests/test_baseline_plot_writer.py::test_agg_backend_in_worker -x` | ❌ W0 | ⬜ pending |
| (perf) | Memory peak single-slice <250 MB indicator cache | manual | `python scripts/profile_baseline_slice.py EURUSD M15 MODERATE` | ❌ W1 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_baseline_runner.py` — copre BACK-07, D-14, D-15, D-23
- [ ] `tests/test_baseline_dataset_writer.py` — copre INT-01 schema D-02/D-03
- [ ] `tests/test_baseline_no_future_leakage.py` — copre D-21, D-22
- [ ] `tests/test_baseline_determinism.py` — copre D-17 (seed + config hashes)
- [ ] `tests/test_baseline_wal.py` — copre D-16 concurrent writes
- [ ] `tests/test_baseline_plot_writer.py` — copre D-19, D-20
- [ ] `tests/test_baseline_report_writer.py` — copre D-18, INT-01
- [ ] `tests/conftest.py` — shared fixtures (small bars sample, mock cost.yaml, mock baseline.yaml, in-memory SQLite)
- [ ] Framework install: `pip install pyarrow matplotlib` + update `requirements.txt`
- [ ] `scripts/profile_baseline_slice.py` — Wave 1 perf profiler (single slice baseline)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full 27-run wall-clock <30 min | BACK-07 / SC#1 | Real workload, dev laptop, irreducibile a unit test | `time .venv/Scripts/python.exe scripts/run_baseline_backtest.py` — exit 0 + wall-clock <30 min |
| Memory peak monitoring (RAM <8 GB pratico) | (perf risk) | RSS sampling cross-process | `python scripts/profile_baseline_slice.py EURUSD M15 MODERATE` + `psutil` snapshot |
| Equity PNG visual inspection (sanity check curve sensata, no spike artificiosi) | INT-01 / SC#4 | Plot quality is qualitative | Open `.planning/research/baseline-equity-curves/EURUSD_M15_MODERATE.png` — verify no flat-line collapse, no negative equity, drawdown shaded coerente |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies declared
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING test files
- [ ] No watch-mode flags (`pytest --watch` proibito in CI/local sampling)
- [ ] Feedback latency <30s per-task, <120s per-wave
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 complete

**Approval:** pending
