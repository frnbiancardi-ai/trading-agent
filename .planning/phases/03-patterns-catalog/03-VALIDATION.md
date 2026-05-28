---
phase: 3
slug: patterns-catalog
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pytest.ini / pyproject.toml (existing) |
| **Quick run command** | `pytest tests/test_patterns.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~10s quick, ~60s full |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_patterns.py tests/test_pattern_config.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Filled by gsd-planner from RESEARCH.md Validation Architecture section. Planner must enumerate every PATT-XX detector test (positive + near-miss negative), calibration snapshot tests, config loader tests, and strategy.py refactor regression tests.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_pattern_config.py -q` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/test_pattern_config.py` — stubs for PatternConfig loader (env override, min<typ<max validation, missing-key KeyError)
- [ ] `config/patterns.yaml` — schema + per-pattern thresholds + calibration anchors
- [ ] `tests/test_patterns.py` — extend with new detector stubs + calibration snapshot fixtures
- [ ] `tests/conftest.py` — shared OHLC fixture builders (existing or new)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Italian docstrings present | CLAUDE.md | Style, non-grep-checkable | Read patterns.py + config/patterns.yaml comments |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
