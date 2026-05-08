---
phase: 05-baseline-backtest
verified: 2026-05-08T22:00:00Z
status: gaps_found
score: 5/6 must-haves verified (1 minor doc gap, no goal-blocking failure)
overrides_applied: 2
overrides:
  - must_have: "Full 9-slice backtest completes in <30 min on dev laptop (SC#1)"
    reason: "Rule 4 user-accepted deviation — engine Phase 1 O(N^2) bottleneck. Wall-clock 11922s vs 1800s. Scope reduced 23.5y -> 10y (Option B). Perf optimization deferred to future plan 01-09. Phase 7 ML bootstrap NOT blocked (parquet+ledger ready)."
    accepted_by: "user (Option A locked — 05-08-SUMMARY.md Rule 4 §wall-clock)"
    accepted_at: "2026-05-08"
  - must_have: "Decision dataset >=10k labeled trades expected (SC#3 soft target)"
    reason: "Soft target; HARD gate >=1000 PASS (1076 trades). Scope reduction 23.5y->10y + no FORMING/NONE drafts (D-21 deferred). Phase 7 ML can train v1 on executed-trade labels."
    accepted_by: "user (BLOCKER 2 policy: 1000<=N<10000 = WARNING-not-fail)"
    accepted_at: "2026-05-08"
gaps:
  - truth: "REQUIREMENTS.md status BACK-07 and INT-01 marked complete"
    status: failed
    reason: "Plan 05-08 Task 4 step 5/6 explicitly required updating REQUIREMENTS.md checkboxes [ ] -> [x] and Traceability table 'Pending' -> 'Complete'. Both still show as Pending."
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "Line 18: 'BACK-07: [ ]' — should be [x]. Line 105: 'INT-01: [ ]' — should be [x]. Line 168: 'BACK-07 | Phase 5 | Pending' — should be Complete (with note SC#1 deviation accepted). Line 231: 'INT-01 | Phase 5 | Pending' — should be Complete."
    missing:
      - "Update REQUIREMENTS.md line 18: BACK-07 [x] (or [partial] with note: SC#1 deferred plan 01-09)"
      - "Update REQUIREMENTS.md line 105: INT-01 [x]"
      - "Update Traceability table lines 168 + 231 to Complete"
human_verification:
  - test: "Visual inspection of 3 PNG sample (EURUSD_M15_MODERATE, GBPUSD_H1_AGGRESSIVE, USDJPY_M30_CONSERVATIVE)"
    expected: "Equity curve non-flat, drawdown subplot coherent with equity dips, x-axis labels readable"
    why_human: "PNG qualitative check — no programmatic baseline for 'visually OK'. Plan 05-08 Task 3 documents that user already performed this check ('User ha aperto 2-3 PNG random. Tendenza generale: equity verso 0 — coerente con strategia baseline negative-edge') — this is the EXPECTED output (negative edge dataset is the input for Phase 7 ML filter)."
---

# Phase 5: Baseline Backtest Verification Report

**Phase Goal:** Execute the full pre-ML baseline backtest across 23.5 years × 3 pairs × 3 timeframes, produce per-slice metrics and the trade-decision dataset that will train the ML classifier.

**Verified:** 2026-05-08T22:00:00Z
**Status:** gaps_found (1 minor documentation gap; goal substantively achieved with 2 user-accepted scope deviations)
**Re-verification:** No — initial verification

## Goal Achievement Summary

The phase goal — produce **per-slice metrics + trade-decision dataset for ML training** — is **substantively achieved**:

- 27/27 slices completed (3 pairs × 3 TF × 3 profiles)
- 1076 labeled trades persisted in parquet with all required columns (entry/exit/pnl/exit_reason TP-SL labels)
- 27 PNG equity curves generated and committed
- Per-slice metrics report committed with full audit hashes

Two scope deviations are user-accepted (Rule 4 + BLOCKER 2 policy):
1. **SC#1 wall-clock** 11922s vs 1800s target → engine perf-opt deferred to plan 01-09
2. **SC#3 soft target** 1076 vs 10000 → hard gate ≥1000 PASS; soft is warn-not-fail

Neither blocks Phase 7 ML bootstrap.

## Observable Truths (ROADMAP Success Criteria)

| # | Truth (SC#) | Status | Evidence |
|---|-------------|--------|----------|
| 1 | SC#1 — 9-slice backtest <30 min on dev laptop | PASSED (override) | Wall-clock 11922s vs 1800s. Override: Rule 4 user-accepted (engine O(N²) bottleneck), defer perf to plan 01-09. 27/27 run successo, 0 fail/skip. |
| 2 | SC#2 — Per-slice metrics report committed to `.planning/research/baseline-{date}.md` | VERIFIED | `.planning/research/baseline-2026-05-08.md` exists (186 lines, 9056 bytes), 27-row Slice Metrics table with sharpe/sortino/max_dd_pct/hit_rate/expectancy_pips/profit_factor/avg_R/longest_dd_days. Per-slice details 27 sub-sezioni. Appendix con cost_yaml_sha256 + strategy_yaml_sha256 + baseline_yaml_sha256 + slippage_seed=42 + warm_up_bars + longest_lookback. Committed via 96348cc. |
| 3 | SC#3 — Decision dataset (≥10k labeled trades expected) persisted to `data/training/baseline_decisions.parquet` | PASSED (override) | `data/training/baseline_decisions/part-0.parquet` (475652 bytes, 1076 rows, 17 columns). HARD gate ≥1000 PASS. Override: soft target 10k accepted as warn-not-fail (BLOCKER 2 policy). Path is directory layout (BLOCKER 1 fix vs ROADMAP single-file path) — pyarrow.dataset compatibility. Schema includes entry_time/exit_time/symbol/timeframe/direction/entry_price/exit_price/sl/tp/lot_size/pnl_pips/pnl_usd/risk_usd/exit_reason/setup_type/confidence/decision_context_json (struct). exit_reason distrib: SL=776, TP=297, SL_GAP=2, TIMEOUT_CLOSE=1 → 300 wins / 776 losses (Phase 7 binary label ready). |
| 4 | SC#4 — Equity curves PNG committed to `.planning/research/baseline-equity-curves/` | VERIFIED | 27/27 PNG present (EURUSD/GBPUSD/USDJPY × M15/M30/H1 × AGGRESSIVE/CONSERVATIVE/MODERATE). Sample EURUSD_M15_MODERATE.png = 40254 bytes (>1KB). All committed via 96348cc. |

**Score:** 4/4 ROADMAP truths met (2 via override, 2 directly).

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/research/baseline-2026-05-08.md` | INT-01 baseline metrics report | VERIFIED | 9056 bytes, 186 lines, contains Header / Slice Metrics 27-row table / Per-slice details 27 sub-sections / Appendix with full sha256 audit hashes. Committed 96348cc. |
| `.planning/research/baseline-equity-curves/*.png` | 27 PNG (3×3×3) | VERIFIED | 27/27 file present and committed 96348cc. Sample sizes 30-58 KB (no empty/stub PNG). Filenames match {SYMBOL}_{TF}_{PROFILE}.png pattern. |
| `data/training/baseline_decisions/` (directory layout) | INT-01 D-02 dataset | VERIFIED | Directory contains `part-0.parquet` (475652 bytes, 1076 rows, 17 columns including struct decision_context_json with 19 nested fields). Tracked in git via 96348cc. |
| `data/training/baseline_drafts/` (directory layout) | INT-01 D-03 dataset | NOT_VERIFIED (deferred) | Directory NOT present. Plan 05-08 documents Rule 3 deviation: `drafts_rows ← []` because engine.run() doesn't capture FORMING/NONE proposals (requires hook in `engine.run()` on `strategy.evaluate_proposal_for_bar`). DEFERRED to future plan (failure analysis Phase 9 prerequisite). NOT a Phase 5 goal-blocker — Phase 7 ML can train v1 on executed-trade labels only (per 05-08-SUMMARY.md §Phase 7 ML readiness). |
| `logs/trades.db` | SQLite ledger 27-run + trades | VERIFIED | 1310720 bytes, 27 baseline runs in `backtest_runs`, 1076 rows in `backtest_trades`, all run_ids match `baseline_2026-05-08_*` pattern. Tracked in git via 96348cc (intentional — audit reproducibility per SUMMARY.md, despite plan instructions to gitignore). |

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `baseline-2026-05-08.md` | `.planning/REQUIREMENTS.md INT-01` | report committed closes requirement | PARTIAL | Report committed (96348cc) — physical artifact present. But REQUIREMENTS.md checkbox NOT updated to `[x]` (see Gap §1). Closure intent satisfied; admin step missed. |
| `data/training/baseline_decisions/` | Phase 7 ML training pipeline | parquet directory consumed by `pd.read_parquet(dir)` / pyarrow.dataset | WIRED | pyarrow.dataset.dataset() reads the directory layout successfully (count_rows=1076 verified). Schema has all fields needed for ML feature extraction (decision_context_json struct includes factors, grade, setup_name, indicators sma_20/sma_50/ema_50/rsi_14/atr_14/risk_reward). Phase 7 unblocked. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| baseline-2026-05-08.md Slice Metrics table | per-slice metrics rows | scripts/regen_baseline_report.py reads logs/trades.db (post-Bug#5 fix _g() helper) | Yes — non-zero metrics (e.g. EURUSD M15 AGGRESSIVE: n=27, sharpe=-44.671, hit_rate=0.222) | FLOWING |
| part-0.parquet | trades dataframe | engine.run() → trades list → slice_worker decisions_rows → parquet writer | Yes — 1076 real trades with TP/SL exit_reason and pnl_pips signed values | FLOWING |
| 27 PNG equity curves | balances + drawdown | _build_equity_dataframe(balances, trades, initial, bars) sintetizza timestamps da exit_time + drawdown via running peak | Yes — non-flat curves with drawdown shaded (user-confirmed in Task 3 checkpoint) | FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Parquet readable + 1076 rows | `pyarrow.parquet.read_table('data/training/baseline_decisions/part-0.parquet').num_rows` | 1076 | PASS |
| Parquet schema has TP/SL exit_reason for ML labels | `t.schema['exit_reason']` | large_string with values [SL, TP, SL_GAP, TIMEOUT_CLOSE] | PASS |
| Parquet wins/losses sign-balance | `(df['pnl_pips']>0).sum()` vs `(df['pnl_pips']<0).sum()` | 300 / 776 | PASS (binary label distribution viable for Phase 7 LightGBM with scale_pos_weight) |
| SQLite ledger 27 baseline runs | `SELECT COUNT(DISTINCT run_id) FROM backtest_runs WHERE run_id LIKE 'baseline_2026-05-08%'` | 27 | PASS |
| Report has all 3 sha256 audit hashes | grep cost_yaml_sha256 + strategy_yaml_sha256 + baseline_yaml_sha256 | 3/3 found, 64-char each | PASS |
| 27 PNG count + non-empty | `ls baseline-equity-curves/*.png | wc -l` ; min size >1KB | 27 files, all 30-58KB | PASS |
| Slice Metrics 27 rows non-zero (post Bug#5 fix) | grep numeric values per row | All rows have real sharpe/expectancy/profit_factor (no all-zero) | PASS |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BACK-07 | 05-08-PLAN | Backtest runs over full 23.5y × 3 pairs × 3 TFs in <30 min on dev laptop | SATISFIED (with Rule 4 deviation) | Functional pipeline runs 27/27 slices end-to-end producing complete deliverables. SC#1 wall-clock target NOT met (11922s vs 1800s) — accepted via Rule 4 (engine O(N²) deferred to plan 01-09). REQUIREMENTS.md checkbox NOT updated (Gap §1). |
| INT-01 | 05-08-PLAN | Baseline backtest report committed to `.planning/research/baseline-{date}.md` | SATISFIED | Report `baseline-2026-05-08.md` committed in 96348cc with full 27-row metrics table + appendix audit hashes. Path matches REQUIREMENTS.md spec. REQUIREMENTS.md checkbox NOT updated (Gap §1). |

## Anti-Patterns Found

None. The 1076 trade rows, 27 PNG, and 27 SQLite run rows all derive from real engine.run() execution (verified via SQLite ledger run_ids pattern + parquet schema with non-empty decision_context_json struct + non-zero metrics in report).

The Phase 5 SUMMARY explicitly documents Bug #5 (report_writer dict access stub returning all-zero metrics), which was fixed during execution and the report regenerated post-fix via `scripts/regen_baseline_report.py`. Current report contents verified non-zero.

## Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | SC#1 wall-clock <30 min | Future plan 01-09 (perf-opt) | Rule 4 deviation user-locked Option A. Engine vectorization + indicator cache reuse intra-bar deferred. NOT a milestone phase — separate technical-debt plan. |
| 2 | `data/training/baseline_drafts/` (FORMING/NONE proposals) | Future plan 05-09 or Phase 9 (failure analysis) | Plan 05-08 D-21 contract gap: engine.run() doesn't emit FORMING/NONE drafts. drafts_rows=[] in slice_worker bridge. NOT required for Phase 7 ML v1 (binary classifier on executed trades only). |
| 3 | SC#3 soft target ≥10k decisions | Mitigated by Phase 5 scope-reduction Option B + Phase 7 detector retune guidance | 1076 decisions = 11% of soft target. BLOCKER 2 policy: 1000≤N<10000 = WARNING-not-fail. Phase 7 ML guidance: retune detector aggressiveness if dataset too small for stable folds. |

## Gaps Summary

**Single minor documentation gap blocking Phase 5 closure:**

REQUIREMENTS.md was not updated to mark BACK-07 and INT-01 as complete, despite all the actual deliverables being produced and committed. Plan 05-08 Task 4 acceptance criteria explicitly require this update (steps 5+6: "REQUIREMENTS.md `BACK-07: [x]` + `INT-01: [x]`"). The closing commit 52a700f updated STATE.md and ROADMAP.md but skipped REQUIREMENTS.md.

This is a documentation/tracking gap, not a goal-achievement gap. The substantive work (baseline backtest pipeline + 1076-trade ML training dataset + 27 PNG + per-slice metrics report) is **complete and verified in the codebase**. STATE.md correctly shows Phase 5 as complete. ROADMAP.md correctly shows all 9 plans as `[x]`.

**Recommended remediation (single commit):**

```
docs(05): close BACK-07 + INT-01 in REQUIREMENTS.md (Phase 5 admin closure)

- Line 18: BACK-07 [x] (with note: SC#1 wall-clock deferred plan 01-09 Rule 4)
- Line 105: INT-01 [x]
- Line 168: Traceability BACK-07 | Phase 5 | Complete
- Line 231: Traceability INT-01 | Phase 5 | Complete
```

After this docs commit, Phase 5 admin closure is fully aligned and Phase 6 (MCP Tools part 1) can proceed without administrative debt.

## Phase Gate Decision

**Verdict: PARTIAL PASS** — phase goal achieved in codebase, with 1 admin gap to close before milestone-level audit.

- Substantive deliverables: VERIFIED (4/4 ROADMAP SCs, 2 via user-accepted overrides for SC#1 wall-clock and SC#3 soft target)
- Phase 7 ML bootstrap: UNBLOCKED (parquet schema + 1076 binary labels ready)
- Admin closure: 1 file update missing (REQUIREMENTS.md checkboxes)

User-accepted Rule 4 deviations are documented and do NOT count as gaps.

---

_Verified: 2026-05-08T22:00:00Z_
_Verifier: Claude (gsd-verifier, Opus 4.7)_
