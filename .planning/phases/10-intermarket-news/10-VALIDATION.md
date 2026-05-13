---
phase: 10
slug: intermarket-news
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `10-RESEARCH.md` §"Validation Architecture" (linee 1030-1080).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (già in uso per Phase 1-9, version per `requirements.txt`) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/test_intermarket_loader.py tests/test_intermarket_score.py tests/test_calendar_rss_client.py tests/test_mcp_handlers_macro.py -x --tb=short` |
| **Full suite command** | `pytest -x --tb=short` |
| **Estimated runtime** | quick: ~5s, full: ~90s (target — Phase 5 baseline parquet test escluso via marker `slow`) |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_intermarket_loader.py tests/test_intermarket_score.py tests/test_calendar_rss_client.py tests/test_mcp_handlers_macro.py -x --tb=short`
- **After every plan wave:** `pytest -x --tb=short` (full suite, must remain green)
- **Before `/gsd-verify-work`:** Full suite + Phase 5 baseline byte-identical assertion (`test_phase10_no_phase5_drift.py`) + integration smoke test FF feed live (run-once manually, `skipif no-network`)
- **Max feedback latency:** ~10s per commit, ~90s per wave merge

---

## Per-Task Verification Map

> Source: 10-RESEARCH.md §"Phase Requirements → Test Map" (linee 1043-1064).
> Task IDs to be assigned by planner; column placeholder pending PLAN.md creation.

| Req | Behavior | Test Type | Automated Command | File Exists |
|-----|----------|-----------|-------------------|-------------|
| MCP-10 | `get_intermarket_context()` ritorna `usd_strength_bias`, `risk_on_off`, `jpy_safe_haven_flag` | unit | `pytest tests/test_mcp_handlers_macro.py::test_get_intermarket_context_envelope -x` | ❌ Wave 0 |
| MCP-10 | `MacroLoader.close_at()` strict-< no future leakage | unit | `pytest tests/test_intermarket_loader.py::test_close_at_strict_less_than -x` | ❌ Wave 0 |
| MCP-10 | `MacroLoader` sha256 anchor stable on identical CSV | unit | `pytest tests/test_intermarket_loader.py::test_sha256_anchor_stable -x` | ❌ Wave 0 |
| MCP-10 | `MacroLoader` rileva sha256 mismatch (CSV tamper) | unit | `pytest tests/test_intermarket_loader.py::test_sha256_mismatch_detected -x` | ❌ Wave 0 |
| MCP-10 | `build_intermarket_score()` direction sign-flip correct | unit | `pytest tests/test_intermarket_score.py::test_direction_sign_flip -x` | ❌ Wave 0 |
| MCP-10 | `build_intermarket_score()` known regime (2020-03 risk-off) → expected sign | unit | `pytest tests/test_intermarket_score.py::test_known_regime_2020_covid -x` | ❌ Wave 0 |
| MCP-10 | `ENABLE_INTERMARKET=false` → adjuster skipped, baseline parquet byte-identical | regression | `pytest tests/test_phase10_no_phase5_drift.py::test_baseline_immutato_with_flag_off -x` | ❌ Wave 0 |
| MCP-13 | `get_economic_calendar()` filter pair-aware High-only default | unit | `pytest tests/test_mcp_handlers_macro.py::test_economic_calendar_pair_filter -x` | ❌ Wave 0 |
| MCP-13 | `CalendarRSSClient.fetch_events()` cache TTL 60min | unit | `pytest tests/test_calendar_rss_client.py::test_cache_ttl_60min -x` | ❌ Wave 0 |
| MCP-13 | `CalendarRSSClient._parse_event()` ET→UTC EDT (May) correct | unit | `pytest tests/test_calendar_rss_client.py::test_et_to_utc_edt_summer -x` | ❌ Wave 0 |
| MCP-13 | `CalendarRSSClient._parse_event()` ET→UTC EST (Jan) correct | unit | `pytest tests/test_calendar_rss_client.py::test_et_to_utc_est_winter -x` | ❌ Wave 0 |
| MCP-13 | DST cross-year boundary regression (analog Phase 1 D-10) | regression | `pytest tests/test_calendar_rss_client.py::test_dst_boundary_march_november -x` | ❌ Wave 0 |
| MCP-13 | Holiday event → `event_time_utc=00:00 UTC` + `all_day=true` | unit | `pytest tests/test_calendar_rss_client.py::test_holiday_all_day_flag -x` | ❌ Wave 0 |
| MCP-13 | Tentative + All Day non-holiday events skipped | unit | `pytest tests/test_calendar_rss_client.py::test_skip_tentative_all_day -x` | ❌ Wave 0 |
| MCP-13 | Cache roundtrip JSON serialize+deserialize datetime stable | unit | `pytest tests/test_calendar_rss_client.py::test_cache_roundtrip -x` | ❌ Wave 0 |
| MCP-13 | FF feed down → cache fallback + warning | integration | `pytest tests/test_calendar_rss_client.py::test_fetch_remote_failure_fallback -x` | ❌ Wave 0 |
| MCP-13 | MCP envelope shape success | unit | `pytest tests/test_mcp_handlers_macro.py::test_envelope_ok -x` | ❌ Wave 0 |
| MCP-13 | MCP envelope shape error (validation_failed) | unit | `pytest tests/test_mcp_handlers_macro.py::test_envelope_validation_failed -x` | ❌ Wave 0 |

*Status colonna verra' allineata da planner in PLAN.md ↔ task IDs.*

---

## Wave 0 Requirements

- [ ] `tests/test_intermarket_loader.py` — stubs per MCP-10 loader + sha256 anchor
- [ ] `tests/test_intermarket_score.py` — stubs per MCP-10 score aggregator (direction sign-flip + known regimes)
- [ ] `tests/test_calendar_rss_client.py` — stubs per MCP-13 RSS + cache + DST + holiday + fallback
- [ ] `tests/test_mcp_handlers_macro.py` — stubs per MCP-10/13 envelope + dispatch + validation
- [ ] `tests/test_phase10_no_phase5_drift.py` — D-10-C0 enforcement (Phase 5 schema-v2 immutability + parquet sha256 anchor)
- [ ] `tests/fixtures/macro_dxy_smoke.csv` — 200-row deterministic Stooq daily-close excerpt
- [ ] `tests/fixtures/ff_rss_smoke.xml` — 10 event mocked rispettando live FF schema (8 child tags)
- [ ] `tests/fixtures/ff_rss_dst_cross.xml` — DST boundary Mar 2nd Sun / Nov 1st Sun regression fixture
- [ ] Framework install: **nessuno** — `feedparser`, `requests`, `pyarrow`, `pandas` già nel `requirements.txt`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FF RSS feed schema drift detection | MCP-13 | Live network call non in CI, FF può cambiare schema senza preavviso | Run `python -m scripts.refresh_macro_csv --probe-ff-rss` mensilmente. Compare XML root + child tag set vs `tests/fixtures/ff_rss_smoke.xml`. Fail loud se diff. |
| Stooq CAPTCHA gate workaround | MCP-10 | Stooq batch download CAPTCHA-gated post-2020; HTTP 200 con HTML payload | `scripts/refresh_macro_csv.py` con `sleep(30)` rate-limit + HTML detection. Fallback browser manuale documentato nel README script. |
| Phase 5 baseline parquet byte-identical | MCP-10 / D-10-C0 | Validazione richiede parquet 23.6y già generato (Plan 05-10 in flight) — non riproducibile in CI quick | `pytest tests/test_phase10_no_phase5_drift.py::test_baseline_immutato_with_flag_off -x --markers=slow`. Eseguire prima di merge Phase 10. |
| forex-trader-pro skill doc update verification | MCP-13 / D-10-D3 | Skill repo external (.claude/skills/forex-trader-pro/SKILL.md) — review umana | Operator legge skill markdown post-merge, verifica sezione "Pre-decision news check" presente + non auto-inject in pre-flight chain. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (assegnato in PLAN.md)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (8 file/fixture entries sopra)
- [ ] No watch-mode flags (`pytest -x --tb=short` only)
- [ ] Feedback latency < 10s per task commit
- [ ] `nyquist_compliant: true` set in frontmatter (dopo PLAN.md ↔ task IDs assegnati)

**Approval:** pending (verra' approvato da gsd-plan-checker post-spawn)
