---
phase: 9
slug: failure-analysis-drift
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source of truth: `09-RESEARCH.md` § "Validation Architecture" (lines 641-753) — this file mirrors that contract in execution-friendly form.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest >= 8.0` (project standard, Phase 1-8 baseline) |
| **Config file** | `pytest.ini` (existing) — no Phase 9-specific config |
| **Quick run command** | `pytest tests/test_cluster_hdbscan.py tests/test_drift_compute.py tests/test_retrain_dedup.py tests/test_position_action_rules.py -x -q` |
| **Full suite command** | `pytest tests/ -x` (NB: Phase 1 perf test `test_smoke_12month_under_60s` is pre-existing fail — deferred per Plan 01-09; do not gate on it) |
| **Estimated runtime** | ~60-90 seconds (Phase 9 subset) / ~120-180s (full suite minus Phase 1 perf) |

---

## Sampling Rate

- **After every task commit:** Run quick suite for the area being modified (cluster / drift / retrain / position_action)
- **After every plan wave:** Run full suite (zero regression gate vs Phase 1-8 baseline 458 passed)
- **Before `/gsd-verify-work`:** Full suite green + zero regression delta
- **Max feedback latency:** ~90 seconds quick suite, ~180s full

---

## Per-Task Verification Map

> Plan-phase planner populates this table per task. RESEARCH.md § "Phase Requirements → Test Map" (lines 654-683) lists the 24 test functions mapped to 7 requirements (ML-07, ML-08, ML-09, MCP-07, MCP-08, MCP-18, INT-03). Each PLAN.md task MUST cite at least one row.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-XX-YY | XX | W | REQ-{XX} | T-09-XX / — | {expected secure behavior or "N/A"} | unit / integration | `pytest tests/test_*.py::test_*` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Phase 9 introduces 1 new dep (`hdbscan>=0.8.40,<0.9.0`) + 4 new module trees + 16 new test files. Wave 0 installs the dep and scaffolds the empty test files so subsequent waves get green-on-first-write.

- [ ] `requirements.txt` + `.env.example` — add `hdbscan` dep + Phase 9 env vars (DRIFT_*, RETRAIN_*, BE_R_THRESHOLD_*, MAX_HOLD_BARS_*, PARTIAL_CLOSE_FRACTION, DRIFT_ECE_N_BINS, DRIFT_SYNTH_SEED)
- [ ] `tests/test_cluster_hdbscan.py` — stubs for ML-07 / MCP-07 (Wave 1)
- [ ] `tests/test_cluster_artifact.py` — stubs for HDBSCAN persistence pitfalls P1, P2 (Wave 1)
- [ ] `tests/test_drift_compute.py` — stubs for ML-08 KS + ECE + feature drift (Wave 2)
- [ ] `tests/test_drift_log_db.py` — stubs for SQLite WAL schema (Wave 2)
- [ ] `tests/test_drift_alarm.py` — stubs for 3-tier threshold logic (Wave 2)
- [ ] `tests/test_drift_e2e.py` — stubs for synthetic shift integration (Wave 2)
- [ ] `tests/test_retrain_dedup.py` — stubs for D-09-C3 idempotent dedup (Wave 3)
- [ ] `tests/test_retrain_scheduler.py` — stubs for APScheduler cron + pitfalls P4, P5, P13 (Wave 3)
- [ ] `tests/test_retrain_validation_gate.py` — stubs for ECE + KS + expectancy checks (Wave 3)
- [ ] `tests/test_retrain_promotion.py` — stubs for atomic os.replace + singleton invalidation, pitfalls P6, P7, P8 (Wave 3)
- [ ] `tests/test_position_action_rules.py` — stubs for 4-rule isolation (Wave 4)
- [ ] `tests/test_position_action_ml_recheck.py` — stubs for OOD caveat + cache + recompute, pitfall P9 (Wave 4)
- [ ] `tests/test_position_action_orchestrator.py` — stubs for hybrid combine + summary_it Italian P15 (Wave 4)
- [ ] `tests/test_mcp_handlers_cluster_drift_retrain_position.py` — stubs for 4 handler response shapes (Wave 4-5)
- [ ] `tests/test_show_drift_cli.py` — stubs for INT-03 CLI round-trip (Wave 5)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| APScheduler monthly cron actually fires on day 1 of month 02:00 UTC in production | ML-09 | Calendar-bound, can't simulate in unit test budget realistically (mocked in `test_retrain_scheduler.py`, but real-clock fire needs live observation) | Deploy on demo MT5 → wait next 1st of month → verify `validation_log.db` row + new bundle on disk |
| Cluster artifact actually identifies ≥3 distinct loss-mode clusters on real 778-row losing-trade subset | ML-07 (SC#1) | Quality verdict requires human interpretation (DB index < 2.0 is a quality threshold not a correctness one — "distinct" requires operator review of feature_distribution_summary) | Wave 1 integration test produces artifact; operator reviews cluster summaries (`summary_it` field) for actionability before phase gate |
| Drift dashboard markdown report is operator-readable | INT-03 (SC#2) | Aesthetic / actionability is subjective | Wave 5 generates first sample report; operator reviews `.planning/research/drift-report-{date}.md` against `forex-trader-pro` skill consumption pattern |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (16 test stub files + dep install)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s quick / 180s full
- [ ] `nyquist_compliant: true` set in frontmatter
- [ ] RESEARCH.md § Pitfalls P1-P15 all have at least one test row in plan-phase per-task map

**Approval:** pending — planner populates per-task map then `/gsd-validate-phase 9` or `/gsd-verify-work 9` toggles `nyquist_compliant: true`.
