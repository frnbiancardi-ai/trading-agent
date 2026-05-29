# Roadmap: Trading Agent v2 — ML-Backtest Milestone

**Created:** 2026-05-07
**Granularity:** Standard (11 phases)
**Strategy:** Brownfield — surgical extension of existing trading-agent codebase

> ⚠️ **2026-05-29: Edge validation NO-GO. Phases 7-11 SUSPENDED** — they assume a
> tradeable edge that 5-regime × 2-pair validation disproved (59/60 configs negative
> even with the full design active: confluence repair + ENABLE_SETUP_* + min_grade).
> A new exploratory **Edge Discovery** track (non-GSD) precedes any resumption — it
> asks whether a raw statistical edge exists in the data at all before building
> anything. The existing phases are valid work, only suspended. See STATE.md "Active
> Work" (2026-05-29) + the report chain in `.planning/research/`
> (audit-strategy-system, confluence-repair, disable-setup-b, validate-5y-mixed-regime,
> activate-min-grade).

## Pre-Phase-7: Edge Discovery (exploratory, non-GSD)

| track | Goal | Status |
|---|---|---|
| Edge Discovery | Find whether an *atomic* statistical edge exists (forward-return of isolated signals: mean-reversion / session / volatility-regime), before assembling any strategy. Iterative, adaptive, non-GSD — each test decides the next. | 🔬 OPEN 2026-05-29 (batteria 1 in `scripts/edge_discovery/`; results in `.planning/research/`). Gates resumption of Phases 7-11. |

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Backtest Engine | Event-driven replay of Italian-CSV historical bars with realistic costs and walk-forward harness | BACK-01..06 | 6 |
| 2 | Indicators Library | Expand indicator coverage to support all 4 setups + ML features | INDIC-01..14 | 4 |
| 3 | Patterns Catalog | Full candlestick pattern detection library (4/4 plans, strategy.py callsite refactor done — pending verify) | PATT-01..07 | 3 |
| 4 | Strategy Refactor | Setup A/B/C/D detectors as pure functions, 5-factor confluence, shared by live + backtest (8/8 plans ✅) | STRAT-01..09 | 5 |
| 5 | Baseline Backtest ✓ COMPLETE 2026-05-12 (9/9 plans) | Run strategy-only backtest on 23.5y × 3 pairs × 3 TFs, produce metrics + ML training data (Plan 05-09 closed D-02 schema gap; parquet schema-v2 1076 × 59 PASS) | BACK-07, INT-01 | 4 |
| 6 | MCP Tools (part 1) ✓ COMPLETE 2026-05-11 (4/4 plans Wave 0-3; Wave 4 deferred) | Backtest, position-management, multi-TF, session, correlation, pattern-catalog tools | MCP-01..03, MCP-09, MCP-11..12, MCP-14..17, MCP-R1..R3 | 4 |
| 7 | ML Classifier ⚠️ SUSPENDED 2026-05-29 | LightGBM trade-quality classifier with walk-forward training and calibration | ML-01..06, ML-10 | 5 |
| 8 | MCP Tools (part 2) ⚠️ SUSPENDED 2026-05-29 | ML training/inference/calibration tools, ML-aware risk evaluation | MCP-04..06, MCP-R4, INT-02 | 4 |
| 9 | Failure Analysis + Drift ⚠️ SUSPENDED 2026-05-29 | Failure clustering, drift monitor, retrain trigger, suggest_position_action | ML-07..09, MCP-07..08, MCP-18, INT-03 | 4 |
| 10 | Intermarket + News ⚠️ SUSPENDED 2026-05-29 | DXY/yields/commodities context + economic calendar blackout | MCP-10, MCP-13 | 3 |
| 11 | Paper Deploy Gate ⚠️ SUSPENDED 2026-05-29 | 30-day demo MT5 run with metric tolerance gate before live activation | DEPLOY-01..03 | 4 |

**Coverage:** 73/73 v1 requirements mapped (100%).

---

## Phase Details

### Phase 1: Backtest Engine

**Goal:** Build an event-driven backtest framework that replays the existing Italian-format CSV historical bars one-at-a-time, applies realistic transaction costs, and exposes the same call surface as the live MT5 client so the strategy module can run identically in both environments.

**Requirements:** BACK-01, BACK-02, BACK-03, BACK-04, BACK-05, BACK-06

**Success criteria:**
1. Loader reads `data/historical/EURUSD/H1.csv` and produces a chronologically ordered bar stream (no shuffling, datetime parsed as UTC).
2. Backtest engine drives the strategy through a multi-month slice and produces a non-empty trade ledger with per-trade decision context.
3. Cost model verifiable via unit test: a 1-pip-spread fill on a 1-lot EUR/USD position deducts the exact expected USD amount.
4. Walk-forward harness produces N non-overlapping (train, test) slices with no look-ahead leakage between them.
5. Metrics module returns Sharpe, max drawdown, hit rate, expectancy on a known hand-crafted ledger fixture.
6. End-to-end smoke test: full backtest of EUR/USD H1 last 12 months runs in <60s on dev laptop.

**Hint UI:** no

**Plans:** 8 plans

Plans:
- [ ] 01-01-PLAN.md — Wave 0 scaffolding: backtest/ skeleton, BrokerProtocol, costs.yaml, test stubs, pyyaml install
- [ ] 01-02-PLAN.md — BACK-01: Italian-CSV loader with GMT-6→UTC conversion (D-08, D-10 cross-year regression)
- [ ] 01-03-PLAN.md — BACK-03: per-symbol CostModel + load_cost_model (SC-3)
- [ ] 01-04-PLAN.md — BACK-02 prep: BacktestBroker + BrokerProtocol compliance + SL/TP fill semantics
- [ ] 01-05-PLAN.md — BACK-02 + BACK-04: BacktestEngine + LedgerWriter + strategy.py annotation (D-02, D-07)
- [ ] 01-06-PLAN.md — BACK-05: walk-forward slice generator (D-06)
- [ ] 01-07-PLAN.md — BACK-06: BacktestMetrics + compute_metrics (SC-5)
- [ ] 01-08-PLAN.md — SC-6 smoke test + legacy cleanup (D-03 delete backtest_suite.py, D-04 archive ml_feedback)

---

### Phase 2: Indicators Library

**Goal:** Add the missing indicators required by the forex-trader-pro playbook (Bollinger, ADX, MACD, Stochastic, Donchian, Keltner, VWAP, Fibonacci, Pivot, NR4/7, Closing Score, Hurst, multi-TF alignment, volatility regime classifier) as pure functions consumable by both live and backtest paths.

**Requirements:** INDIC-01, INDIC-02, INDIC-03, INDIC-04, INDIC-05, INDIC-06, INDIC-07, INDIC-08, INDIC-09, INDIC-10, INDIC-11, INDIC-12, INDIC-13, INDIC-14

**Success criteria:**
1. Each indicator has a unit test against a known reference value (TradingView or manual calc).
2. All indicators are pure functions: no side effects, deterministic, no future leakage (rolling computations use only past data, normalization uses `expanding().shift(1)` not full-series).
3. Multi-TF alignment helper accepts (H4, H1, M15) bar streams and returns a coherence score in [0, 1].
4. Volatility-regime classifier returns one of {compressed, normal, expanded} based on ATR percentile vs 200-bar window — verified on known regime samples.

**Hint UI:** no

**Plans:** 9 plans

Plans:
- [x] 02-01-PLAN.md — Wave 0 scaffolding: indicators/ package, lift-and-shift, conftest fixture, regime.yaml, dev-dep
- [x] 02-02-PLAN.md — INDIC-01 Bollinger+squeeze + INDIC-06 Keltner (volatility.py, parity 1e-6)
- [x] 02-03-PLAN.md — INDIC-02 ADX/DMI + INDIC-03 MACD + INDIC-04 Stochastic (momentum.py, parity 1e-6)
- [x] 02-04-PLAN.md — INDIC-12 Hurst R/S rolling (hurst.py, log-log regression)
- [x] 02-05-PLAN.md — INDIC-05 Donchian + INDIC-08 Fibonacci + INDIC-09 Pivots classic+Camarilla (NY-17)
- [x] 02-06-PLAN.md — INDIC-07 VWAP intraday (NY-17 reset) + anchored (volume.py)
- [x] 02-07-PLAN.md — INDIC-10 NR4/NR7+Boomer + INDIC-11 Closing Score (bars.py)
- [x] 02-08-PLAN.md — INDIC-13 MTF alignment H4/H1/M15 EMA50-slope (mtf.py)
- [x] 02-09-PLAN.md — INDIC-14 Volatility regime classifier + compute_all_extended aggregator (final phase gate)

---

### Phase 3: Patterns Catalog

**Goal:** Replace the existing minimal `patterns.py` with a full candlestick pattern catalog (Hammer, Shooting Star, Engulfing, Morning/Evening Star, Key Reversal, Inside Bar, Pin Bar) returning structural anchor points usable by Setup B and ML features.

**Requirements:** PATT-01, PATT-02, PATT-03, PATT-04, PATT-05, PATT-06, PATT-07

**Success criteria:**
1. Each pattern detector has a unit test with a hand-crafted positive case AND a near-miss negative case.
2. Pattern catalog returns a list of `PatternHit` dicts with `name`, `bar_index`, `extreme_price`, `confidence` (0–1), `direction`.
3. Existing `scan_patterns()` callers in `strategy.py` continue to work (backward-compatible signature OR adapter shim with deprecation note).

**Hint UI:** no

**Plans:** 4 plans

Plans:
- [x] 03-01-PLAN.md — PATT-07 foundation: dataclasses + _calibrate + load_pattern_config + config/patterns.yaml + tests/test_pattern_config.py
- [x] 03-02-PLAN.md — PATT-01/03/06: refactor 4 existing detectors (hammer/inverted/engulfing/pin_bar) to (matched, raw_score) + update existing tests
- [x] 03-03-PLAN.md — PATT-02/04/05/06/07: 5 new detectors (shooting_star/morning_star/evening_star/key_reversal/inside_bar) + scan_patterns rebuild returning list[PatternHit]
- [x] 03-04-PLAN.md — PATT-07 integration: atomic strategy.py refactor (5 call sites + import + __init__ pattern_cfg) + full-suite regression

---

### Phase 4: Strategy Refactor

**Goal:** Refactor the existing strategy module into pure-function setup detectors (A/B/C/D), a 5-factor confluence scorer, ATR-based R:R proposal builder, with the same code path executed by the live scheduler and the backtest engine — no fork.

**Requirements:** STRAT-01, STRAT-02, STRAT-03, STRAT-04, STRAT-05, STRAT-06, STRAT-07, STRAT-08, STRAT-09

**Success criteria:**
1. Each setup detector is a pure function: `(bars, indicators, regime, profile) → ProposalDraft | None`. No broker calls, no log/print, no DB writes.
2. Confluence scorer returns 5 factor booleans + grade (A+/A/B/C/reject) + starting confidence; matches forex-trader-pro skill table exactly.
3. Strategy unit tests run in <500ms total (sub-millisecond per detector).
4. Backtest engine and live scheduler invoke the *same* `evaluate_proposal_for_bar(bars, indicators, ctx)` function — verified by import graph.
5. Existing live behavior unchanged on a regression fixture (10 historical decisions replayed produce identical proposals to pre-refactor output).

**Hint UI:** no

**Plans:** 8 plans

Plans:
- [x] 04-01-PLAN.md — Wave 0 scaffolding: regression baseline capture (D-14), strategy/ package skeleton, types, config/strategy.yaml, RiskProfile, test stubs ✓ 2026-05-08 (5 task atomici, 21 file creati, 402 passed + 31 skip; baseline 10 scenari NONE confidence=0.0 locked; SUMMARY: `.planning/phases/04-strategy-refactor/04-01-SUMMARY.md`)
- [x] 04-02-PLAN.md — Wave 1: confluence.py — 5-factor scorer + grade + confidence calibrator (STRAT-05, STRAT-06) ✓ 2026-05-08 (2 task atomici b0f35e7 + 2e16fb2; 315 LOC source + 221 LOC test; 10 test pass no-skip; 412 passed + 22 skip; 2 bug-fix Rule 1 inline: FP epsilon spread + datetime.now(UTC); SUMMARY: `.planning/phases/04-strategy-refactor/04-02-SUMMARY.md`)
- [x] 04-03-PLAN.md — Wave 1: proposal.py adapters + R:R floor + ATR cap helper (STRAT-07) ✓ 2026-05-08 (3 task atomici cc2ef77 RED + 17c0504 GREEN + d7e10bf test; 217 LOC source + 239 LOC test; 25 test pass no-skip; 437 passed + 16 skip; 1 bug-fix Rule 1 inline: FP epsilon 1e-9 su rr>=min_rr boundary; SUMMARY: `.planning/phases/04-strategy-refactor/04-03-SUMMARY.md`)
- [x] 04-04-PLAN.md — Wave 1: AST purity gate test — living invariant (STRAT-08) ✓ 2026-05-08 (1 task atomico 0260126; 232 LOC test; 5 test pass 0.16s; 442 passed + 13 skip; negative-test verificato; gate copre import+logging+print/open con eccezione yaml loader confluence; adapters/ esclusi by design; SUMMARY: `.planning/phases/04-strategy-refactor/04-04-SUMMARY.md`)
- [x] 04-05-PLAN.md — Wave 2: Setup A breakout + Setup D pullback detectors (STRAT-01, STRAT-04) ✓ 2026-05-08 (3 task atomici 69ad6cd feat A + a963130 feat D + b52aff0 test; 208 LOC a_breakout + 298 LOC d_pullback + 235 LOC test; 5 test no-skip A+D; 447 passed + 8 skip; pure modules verificati; confidence READY = 0.90 A+ con spread_tighter; 0 deviazioni; SUMMARY: `.planning/phases/04-strategy-refactor/04-05-SUMMARY.md`)
- [x] 04-06-PLAN.md — Wave 2: Setup B reversal (D-07 counter-trend gate) + Setup C compression (STRAT-02, STRAT-03) ✓ 2026-05-08 (3 task atomici d1d6d56 feat B + e021dce feat C + 1f94a38 test; 300 LOC b_reversal + 333 LOC c_compression + 211 LOC test delta; 4 test no-skip B/C; 451 passed + 4 skip; pure modules verificati; counter-trend gate D-07 attivo; Boomer A2 reconciliation final-locked CONTEXT.md verbatim; 1 deviation Rule 1 test fixture math; SUMMARY: `.planning/phases/04-strategy-refactor/04-06-SUMMARY.md`)
- [x] 04-07-PLAN.md — Wave 3: evaluate_proposal_for_bar + IntradayStrategy shim + adapters live/backtest + risk_utils (STRAT-08, STRAT-09) ✓ 2026-05-08 (5 task atomici 7046a61 risk_utils + 324969f adapters + 35d53d8 shim cutover + 476aecb test multi-match + e0194ac backward-compat; 95 LOC risk_utils + 199 LOC adapters/live + 76 LOC adapters/backtest + 110 LOC __init__ + 438 LOC _shim + 83 LOC test multi-match; 12 test legacy Category C rimossi da test_strategy.py; strategy_legacy.py ORPHANED; 95 strategy+phase16 passed, full 436 passed minus backtest perf; 6 deviazioni: 4 Rule 3 blocking (adapter scalari→sequenze gap, build_trade_proposal/_analyze_technical/decision_context_json backward-compat) + 2 Rule 1 (BrokerProtocol annotation, RISK_MODE fixture); 1 deferred backtest smoke +3-4s perf overshoot; single shared call site D-09 attivo live/backtest; SUMMARY: `.planning/phases/04-strategy-refactor/04-07-SUMMARY.md`)
- [x] 04-08-PLAN.md — Wave 4 PHASE GATE: regression fixture replay + reconciliation checkpoint + strategy_legacy.py cleanup (STRAT-09, SC-3/4/5) ✓ 2026-05-08 (5 task commits 5db3049 test + 21abb91 fix + dd3e45d docs + 575b484 re-baseline + a7a252a archive; user decision option-a: ACCEPT calibration + re-baseline fixture nuovo motore 5-factor; 8/10 setup fire vs legacy 10/10 NONE; 11/11 regression PASS in 111s; strategy_legacy.py ARCHIVIATO in .planning/archive/ con provenance README — deviation Plan Task 3 da delete a archive per Phase 5 backtest validation safety; Rule 1 fix spread_baseline_pips defensive cast; Phase 4 SC-1..5 tutti ✅; STRAT-09 ✓ Complete con nota Phase 5 validation requirement; pre-existing 04-07 perf 63.5s deferred a Phase 5 plan-08; SUMMARY: `.planning/phases/04-strategy-refactor/04-08-SUMMARY.md`)

---

### Phase 5: Baseline Backtest

**Goal:** Execute the full pre-ML baseline backtest across 23.5 years × 3 pairs (EUR/USD, GBP/USD, USD/JPY) × 3 timeframes (M15, M30, H1), produce per-slice metrics and the trade-decision dataset that will train the ML classifier.

**Requirements:** BACK-07, INT-01

**Success criteria:**
1. Full 9-slice backtest completes in <30 min on dev laptop with documented config.
2. Per-slice metrics report (Sharpe, MaxDD, hit rate, expectancy, profit factor, trade count) committed to `.planning/research/baseline-{date}.md`.
3. Decision dataset (≥10k labeled trades expected, target win/loss outcome at TP/SL) persisted to `data/training/baseline_decisions.parquet`.
4. Equity curves plotted per slice (PNG output) committed to `.planning/research/baseline-equity-curves/`.

**Hint UI:** no

**Plans:** 9 plans (originali 8 completi 2026-05-08; +1 Plan 05-09 aperto 2026-05-11 per chiudere D-02 schema gap inherited from Phase 5 → blocca Phase 7 ML training)

Plans:
- [x] 05-01-PLAN.md — Wave 0 scaffolding ✓ 2026-05-08 (5 commit; pyarrow+matplotlib + baseline.yaml + warmup.py + ledger schema migration + preflight script)
- [x] 05-02-PLAN.md — Wave 0 test scaffolding ✓ 2026-05-08 (3 commit; 30 test stub + 5 active warmup; Nyquist gate verde)
- [x] 05-03-PLAN.md — Wave 1 determinism + WAL ✓ 2026-05-08 (3 commit; 9/9 test pass cross-process determinism + multi-writer concurrency)
- [x] 05-04-PLAN.md — Wave 1 parquet + plot writers ✓ 2026-05-08 (3 commit; 9/9 test pass; Agg backend headless)
- [x] 05-05-PLAN.md — Wave 2 engine extension + metrics ✓ 2026-05-08 (4 commit; 4 kwargs Phase 5 + virtual_positions + force_close + longest_dd_days; 4/5 preflight gate chiusi)
- [x] 05-06a-PLAN.md — Wave 2 slice_worker ✓ 2026-05-08 (4 commit; D-14/D-15/D-07; WARNING 7/8/12 chiusi)
- [x] 05-06b-PLAN.md — Wave 2 report_writer ✓ 2026-05-08 (3 commit; D-18 schema; INT-01 + WARNING 12)
- [x] 05-07-PLAN.md — Wave 3 runner + CLI ✓ 2026-05-08 (4 commit; ProcessPoolExecutor + BaselineConfig + profiler; ThreadPool injection per testability)
- [x] 05-08-PLAN.md — Wave 4 PHASE GATE smoke E2E ✓ 2026-05-08 (5 commit; 27/27 run, 1076 trade > 1000 hard gate SC#3; SC#1 wall-clock 11922s vs 1800s = Rule 4 deviation user-accepted, defer perf-opt plan 01-09; 5 deviation totali; Phase 7 ML dataset ready)
- [x] 05-09-PLAN.md — Wave 5 dataset writer extension + baseline re-run ✓ 2026-05-12 (plan-write 6 commit `5630bcc...9e477cc` 2026-05-11 + plan-execute PC secondario 14038s wall-clock + 2 commit primario post-pull `0410bf2..de13199` 2026-05-12; parquet schema-v2 1076 × 59 cols SCHEMA validation PASS; 27/27 ok 0 fail/skip; D-02 gap CHIUSO; Phase 7 ML sbloccata per /gsd-plan-phase 7 --skip-research)

---

### Phase 6: MCP Tools (part 1) ✓ COMPLETE 2026-05-11

**Status:** 4/4 plans Wave 0-3 shipped. MCP-R1/R2/R3 + MCP-01/02/03 + MCP-16/17 ✓ Complete. MCP-09/11/12/14/15 deferred a Wave 4 (Plan 06-05 scheduling post-Phase 7 ML).

**Plans:**
- [x] 06-01-PLAN.md — Wave 0 scaffolding ✓ 2026-05-11 (55 stub xfail + ErrorCodes D-F2 + backtest_runs.status migration)
- [x] 06-02-PLAN.md — Wave 1 mcp_tools/ package split + R1/R2/R3 additive refactor ✓ 2026-05-11 (5 commit; BarSource D-D1 + 3 Mt5Client wrappers Phase 6 D-B1)
- [x] 06-03-PLAN.md — Wave 2 backtest async control plane ✓ 2026-05-11 (5 commit; JobQueue ProcessPool D-A1/A3/A4 + 4 nuovi tool + smoke round-trip SC#4 PASS 31s)
- [x] 06-04-PLAN.md — Wave 3 position management + trail daemon ✓ 2026-05-11 (5 commit; MCP-16 D-B1 atomic combo + DRY_RUN gate + D-B3 stops_level + MCP-17 + D-B2 trail_daemon position_trails + scheduler hook non-fatal)
- [ ] 06-05-PLAN.md — Wave 4 correlation/session/multi_tf/patterns/replay_decision (DEFERRED a scheduling post-Phase 7; 10 stub xfail preservati in test_mcp_*.py)

**Goal:** Expose the new backtest, position-management, multi-TF, correlation, session, and pattern-catalog tools through the MCP server, plus refactor existing snapshot/scan/propose tools for backward-compatible expansion.

**Requirements:** MCP-01, MCP-02, MCP-03, MCP-09, MCP-11, MCP-12, MCP-14, MCP-15, MCP-16, MCP-17, MCP-R1, MCP-R2, MCP-R3

**Success criteria:**
1. All 13 new/refactored tools registered in `mcp_server.py` with JSON-Schema descriptions; `tools/list` returns the new surface. — ✓ 8/13 shipped Wave 0-3 (R1/R2/R3 + run_backtest/get_backtest_metrics/walk_forward_validate/cancel_backtest + modify_position/get_position_state); 5 deferred Wave 4.
2. `modify_position` validates broker `stops_level`, refuses invalid SL distances, supports break-even and trailing modes — covered by integration test against MT5 demo. — ✓ 06-04 D-B3 pre-validation con suggested_sl + trail_stop_atr_mult via D-B2 position_trails + integration test SC#2 in tests/test_mcp_integration_modify.py (SKIP CI / runnabile manualmente PC con MT5 demo).
3. Existing `forex-trader-pro` skill-driven flows still pass (existing tool signatures unchanged on default args). — ✓ zero regressione Wave 1-3 (test_mcp_tools_v2.py 15/15 pass attraverso 06-02/03/04).
4. End-to-end test: `run_backtest` → `get_backtest_metrics` round-trip via MCP returns metrics matching direct in-process call. — ✓ 06-03 SC#4 (tests/test_mcp_smoke_round_trip.py 2/2 PASS 31s su Codespace; SKIP cleanly senza CSV/yaml).

**Hint UI:** no

---

### Phase 7: ML Classifier

**Status:** 🟢 plans-written 2026-05-12 (CONTEXT.md ✓ + RESEARCH.md ✓ + PATTERNS.md ✓ + VALIDATION.md ✓ + 6 PLAN.md ✓ post plan-check 3 iter PASS). Ready for `/gsd-execute-phase 7`.

**Goal:** Train a LightGBM binary trade-quality classifier on the Phase 5 baseline decision dataset (parquet schema-v2 1076 × 59 cols, committed `0410bf2`) with walk-forward splits and proper Platt/isotonic calibration; persist versioned models.

**Requirements:** ML-01, ML-02, ML-03, ML-04, ML-05, ML-06, ML-10

**Success criteria:**
1. Feature extractor produces a deterministic feature vector from a decision context (verified by snapshot test).
2. Walk-forward training script runs end-to-end on the baseline dataset, produces 10 fold models, no `train_test_split(shuffle=True)` anywhere.
3. Calibration (Platt + isotonic) applied; reliability diagram + Brier score + ECE reported per fold.
4. Inference API: `predict(features) → (raw_score, calibrated_prob)` with **p95 < 10ms** on 1000-sample benchmark (locked HANDOFF, NOT p99).
5. Classifier integrated into proposal pipeline: trades with `calibrated_prob < threshold` rejected; verified end-to-end on a held-out month.

**Hint UI:** no

**Plans:** 6 plans (Wave 0-5) — plan-check 3 iter PASS 2026-05-12

Plans:
- [ ] 07-01-PLAN.md — Wave 0 scaffolding: `ml/` package + `feature_extraction.py` (D-09-G derivation 8 fields da decision_context_json + pnl_pips + timestamps) + AST purity gate active da day-1 + ml.yaml (deterministic LightGBM 4.x flag + dataset section) + 200-row smoke fixture
- [ ] 07-02-PLAN.md — Wave 1 walk_forward: expanding 10 fold + per-TF embargo (timeout_bars[tf] uniform max=120) + train/val 80/20 temporal + no-shuffle AST guard
- [ ] 07-03-PLAN.md — Wave 2 calibration + train: manual Platt+Isotonic (sklearn 1.8 senza CalibratedClassifierCV cv='prefit') + LightGBM fold loop con scale_pos_weight per fold + FoldArtifacts NamedTuple cross-plan contract + Brier-winner picking fold≥3 + Platt-only val<50 + categorical "regime" canonical (rename regime_state→regime at pipeline entry)
- [ ] 07-04-PLAN.md — Wave 3 threshold: profit-curve sweep per-profile + mediana aggregator + AST guard val-not-test
- [ ] 07-05-PLAN.md — Wave 4 inference + artifact: MLFilter singleton predict + joblib bundle + sidecar metadata.json + p95<10ms benchmark split fixture/real (integration mark) + final retrain 100% post-fold-loop
- [ ] 07-06-PLAN.md — Wave 5 integration + phase gate: ProposalDraft extension (3 ML fields) + single-callsite ml-attach in evaluate_proposal_for_bar (AST guard adapters) + risk_engine ML gate (threshold from metadata.json) + ENABLE_ML_FILTER=false default zero-impact rollout + held-out month E2E fold-9 + human-verify checkpoint

---

### Phase 8: MCP Tools (part 2)

**Status:** 🟢 plans-written 2026-05-12 (CONTEXT.md ✓ + PATTERNS.md ✓ + 7 PLAN.md ✓). Ready for `/gsd-execute-phase 8` post Phase 7 execute.

**Goal:** Expose ML training, inference, and calibration introspection through MCP; integrate ML score into `evaluate_trade_proposal` response; produce the post-ML backtest report.

**Requirements:** MCP-04, MCP-05, MCP-06, MCP-R4, INT-02

**Success criteria:**
1. `train_ml_filter`, `predict_trade_quality`, `get_ml_calibration` registered in MCP and pass integration tests.
2. `evaluate_trade_proposal` response includes `ml_score` and `calibrated_prob` fields without breaking existing consumers.
3. Post-ML backtest report committed to `.planning/research/ml-on-{date}.md` showing per-slice delta vs baseline (Sharpe, hit rate, expectancy, drawdown).
4. ML-on backtest demonstrates non-trivial improvement vs baseline OR documented analysis of why not (negative result is acceptable signal, not failure).

**Hint UI:** no

**Plans:** 7 plans (Wave 0-5)

**Cross-cutting constraints** (must_haves.truths che ricorrono in ≥2 plan):
- *Italiano per docstring/log/rationale, English per code/identifier* (CLAUDE.md) — TUTTI i plan 08-01..08-07
- *EXECUTION_MODE=shadow rispetto + .env via config.py zero magic numbers* (CLAUDE.md) — TUTTI i plan
- *Phase 7 pre-flight Bash gate (`test -f ml/inference.py && test -f models/classifier_v1_latest.pkl`)* — 08-02, 08-03, 08-04, 08-05, 08-06 (Wave 1-4)
- *ErrorCodes envelope (`mcp_tools/errors.py`)* — 08-01, 08-02, 08-03, 08-04
- *MLFilter singleton process-local bootstrap (Phase 7 Plan 07-05 carry-forward)* — 08-01, 08-02, 08-05
- *Training data integrity priority (project memory)* — 08-04 (sha256 audit D-08-B3), 08-06 (output_dir separato D-08-D1)

Plans:

**Wave 0** *(parallel-with-Phase-7-execute, no hard dependency)*
- [x] 08-01-PLAN.md — Wave 0 scaffolding: 3 Tool schemas MCP-04/05/06 + stub handler NotImplementedError + 3 ErrorCodes additivi (VALIDATION_FAILED/NOT_FOUND/INTERNAL_ERROR) + 3 env var config (ML_MODEL_PATH/MCP_TRAINING_DATA_PATH/MCP_ML_THRESHOLD_MARGIN_PCT) + bootstrap singleton + xfail strict gate test

**Wave 1** *(blocked on Wave 0 + phase-7-complete; 08-02 and 08-05 run in parallel — zero file overlap)*
- [ ] 08-02-PLAN.md — handle_predict_trade_quality GREEN (MCP-05) — 3 branche (disabled, success, exception) + riuso build_feature_vector Phase 7 + threshold lookup per profile + 7 test (incl. B4 parity test_predict_branch_A_eq_branch_B_features_match per regime/regime_state disambig)
- [ ] 08-05-PLAN.md — evaluate_trade_proposal extension (MCP-R4) — 4 additive fields (ml_score, calibrated_prob, ml_threshold, ml_filter_active) + backward-compat absolute (B1 RiskDecision adjusted_stop_loss/adjusted_take_profit signature) + try/except swallow Plan 07-06 pattern + 6 test

**Wave 2** *(blocked on Wave 1 completion — overlap su mcp_tools/handlers/ml.py)*
- [ ] 08-03-PLAN.md — handle_get_ml_calibration GREEN (MCP-06) — D-08-C1 default per-fold + D-08-C2 summary_only opt-out + 9 fields enumerati per fold (D-08-C3) + 5 test

**Wave 3** *(blocked on Wave 2 completion — overlap su mcp_tools/handlers/ml.py)*
- [ ] 08-04-PLAN.md — handle_train_ml_filter GREEN (MCP-04) — async JobQueue cap=1 shared D-08-A2 + worker top-level picklable + 3-layer security (enum D-08-B2 + schema-v2 + sha256 audit D-08-B3 con B5 post-train metadata injection atomic + path-traversal mitigation T-8-04-04) + 6 unit + 1 integration test

**Wave 4** *(blocked on Wave 3 completion — bundle.pkl + metadata.json prodotti da Plan 08-04 hard dependency)*
- [ ] 08-06-PLAN.md — INT-02 deliverable: Task 0 B2 refactor runner.py `output_dir` kwarg threaded down a slice_worker.py + dataset_writer.py (preserva training data integrity priority: `data/training/baseline_ml_on/` separato da `baseline_decisions/`) + scripts/run_ml_on_backtest.py wrapper (analog Plan 05-09) + backtest/baseline/ml_on_report_writer.py (6 sezioni D-08-D4 + verdict YAML D-08-D5) + Degraded Slices Analysis automatica + 11+ test + PC secondario checkpoint notturno ~14000s

**Wave 5** *(blocked on Wave 4 completion + PC secondario report ml-on-{date}.md committed)*
- [ ] 08-07-PLAN.md — Phase gate: 08-VERIFICATION.md (4 SC closure verbatim 22 unit + 1 integration via test count math block + 5 req + 14 D-08-XX decisioni coverage + security gates) + REQUIREMENTS.md update + ROADMAP.md update + STATE.md update + commit atomico

---

### Phase 9: Failure Analysis + Drift

**Status:** 🟢 plans-written 2026-05-12 (CONTEXT.md ✓ + RESEARCH.md ✓ + PATTERNS.md ✓ + VALIDATION.md ✓ + 7 PLAN.md ✓). Ready for `/gsd-execute-phase 9` post Phase 7 + Phase 8 execute (cross-phase deps: ml/feature_extraction + ml/inference + mcp_tools/handlers/ml._train_ml_filter_worker).

**Goal:** Add failure clustering, drift monitoring, automatic retrain trigger, and ML-driven `suggest_position_action` for active position management.

**Requirements:** ML-07, ML-08, ML-09, MCP-07, MCP-08, MCP-18, INT-03

**Success criteria:**
1. Failure clustering identifies ≥3 distinct loss-mode clusters on baseline dataset with feature-importance interpretation.
2. Drift monitor logs prediction distribution KS-stat + calibration ECE per rolling window; alarm triggers when threshold breached.
3. Retrain trigger fires correctly on simulated drift; new model versioned and loaded without service interruption.
4. `suggest_position_action(position_id)` returns hold/move-SL/partial-close/full-close suggestion with rationale, integration-tested on demo positions.

**Hint UI:** no

**Plans:** 7 plans (Wave 0-6)

Plans:

**Wave 0** *(no hard cross-phase deps — scaffolding-only, can run anytime)*
- [ ] 09-01-PLAN.md — Wave 0 scaffolding: requirements.txt `hdbscan>=0.8.40,<0.9.0` (P2 anti-sklearn-switch comment) + 26 env var Phase 9 in config.py + .env.example (DRIFT_*, RETRAIN_*, BE_R_THRESHOLD_*, MAX_HOLD_BARS_*, PARTIAL_CLOSE_FRACTION, TIME_STOP_R_THRESHOLD, DRIFT_ECE_N_BINS=10 P10 invariant, DRIFT_SYNTH_SEED=42, HDBSCAN_*) + 4 package barrels (cluster/, drift/, retrain/, position_action/) + 4 handler stub files mcp_tools/handlers/ + logger.py extension `_ensure_ml_calibrated_prob_column` idempotente + ml/inference.py `_invalidate_singleton()` P8 hook + 16 test stub xfail strict gate

**Wave 1** *(blocked on Wave 0 + phase-7-execute per ml/feature_extraction)*
- [ ] 09-02-PLAN.md — Area A failure clustering (ML-07 + MCP-07) — cluster/preprocessing.py (batch wrapper su Phase 7 build_feature_vector D-09-A4) + cluster/hdbscan_runner.py (P1 prediction_data=True + P2 anti-sklearn AST guard + P3 contrib min_samples + core_dist_n_jobs=1 determinism) + cluster/artifact.py (joblib + sidecar metadata.json + dataset_hash audit anchor) + mcp_tools/handlers/cluster.py + schema + server dispatch. SC#1 verified

**Wave 2** *(blocked on Wave 0 — can run parallel to Wave 1)*
- [ ] 09-03-PLAN.md — Area B drift monitor (ML-08 + MCP-08) — drift/reference.py (sha256 strict-fail P14) + drift/compute.py (KS+ECE+feature drift top-K P10/P12 guards) + drift/log_db.py (SQLite WAL P11 + drift_log schema D-09-B4) + drift/alarm.py (3-tier ANY-of-3 D-09-B3) + mcp_tools/handlers/drift.py (response shape verbatim CONTEXT.md). Rule 3 architectural deviation: `_load_current/reference_window` resta NotImplementedError until Wave 6

**Wave 3** *(blocked on Wave 0 + Wave 2 drift alarm + phase-8-execute per _train_ml_filter_worker)*
- [ ] 09-04-PLAN.md — Area C retrain trigger (ML-09) — retrain/dedup.py (idempotent D-09-C3 + reuse Phase 8 worker D-09-C1) + retrain/scheduler.py (APScheduler BackgroundScheduler P4 MemoryJobStore + P5 replace_existing + P13 misfire_grace_time=3600) + retrain/validation_gate.py (3-check D-09-C2 + validation_log.db audit) + retrain/promotion.py (P6 os.replace pair + P7 metadata FIRST .pkl SECOND + P8 singleton invalidate) + mcp_tools/handlers/retrain.py (thin wrapper). SC#3 verified

**Wave 4** *(blocked on Wave 0; parallel-feasible with Wave 2/3 — no shared modules)*
- [ ] 09-05-PLAN.md — Area D suggest_position_action (MCP-18) — position_action/rules.py (4 rule families D-09-D3 + profile-aware getattr cfg dinamico) + position_action/ml_recheck.py (OOD caveat P9 + cache lookup D-09-D4 + fallback recompute + ENABLE_ML_FILTER=false fallback) + position_action/orchestrator.py (hybrid combine + structured rationale D-09-D2 + summary_it P15 italiano regex) + mcp_tools/handlers/position_action.py (read-only consume Phase 6 handle_get_position_state). SC#4 verified

**Wave 5** *(blocked on Wave 2 drift handler)*
- [ ] 09-06-PLAN.md — INT-03 CLI dashboard — drift/report_writer.py (markdown 6-section Pattern K) + scripts/show_drift.py (argparse + exit codes 0/1/2/3/4 + WAL reader P11) + tests round-trip + determinism + exit codes. SC#2 partial CLI dashboard ready

**Wave 6** *(blocked on Wave 1-5 completion — phase gate)*
- [ ] 09-07-PLAN.md — Integration + E2E smoke + phase gate verification: implementa `_load_current_window` + `_load_reference_window` in mcp_tools/handlers/drift.py (resolves Wave 2 Rule 3 deviation) + 3 E2E test file (drift→retrain rejected + drift→retrain promoted + cluster/drift coexistence + MCP-18 ENABLE_ML_FILTER=false integration + retrain concurrent 3-trigger dedup) + 09-VERIFICATION.md (coverage matrix 7 req × 16 D-09-* × 4 SC × 15 P) + REQUIREMENTS.md update + ROADMAP.md update + STATE.md update + commit atomico phase-complete

---

### Phase 10: Intermarket + News

**Goal:** Wire intermarket context (DXY, US10Y, gold, oil) and economic-calendar advisory into the proposal pipeline as confluence inputs and operator-driven pre-decision check (no auto-reject per D-10-C0).

**Requirements:** MCP-10, MCP-13

**Plans:** 6 plans (Wave 2 split 10-04 → 10-04a + 10-04b per revision-loop Warning #3)

**Success criteria:**
1. `get_intermarket_context()` returns USD strength bias, risk-on/off bias, JPY safe-haven flag — verified against known historical regimes.
2. `get_economic_calendar(window_minutes)` returns upcoming events with high-impact flag and blackout window; integrates with at least one provider (e.g., ForexFactory RSS, FRED, or ECB feed).
3. ~~Proposal pipeline applies blackout: trades within ±15 min of high-impact events are rejected with explicit reason.~~ **DEVIATED via D-10-C0** (2026-05-13): drop backtest blackout totalmente. Phase 5 parquet schema-v2 1076x59 IMMUTATO. MCP-13 live-only advisory NO auto-reject in strategy/risk_engine. Motivazione utente: lo storico include news/holiday naturalmente — strategy+ML apprendono dalla distribuzione reale P&L. Trade-off accettato: asimmetria backtest/live. Compensato da: forex-trader-pro skill consultation MCP-13 manuale (D-10-D3). Backlog deferred: Backtest blackout retroactive + Risk_engine news soft-warning live + Skill auto-inject MCP-13 -> Phase 11+.

**Decision references:** D-10-A0..A4 (intermarket data + sha256 anchor + manual refresh), D-10-B1..B6 (FF RSS calendar + cache TTL 60min + ET->UTC zoneinfo + holiday/Tentative handling), D-10-C0 (SCOPE OVERRIDE drop blackout), D-10-D1..D3 (signature extend + ENABLE_INTERMARKET zero-impact rollout + skill doc patch).

**Hint UI:** no

Plans:
- [ ] 10-01-PLAN.md — Wave 0 scaffolding: 5 test stub (33 xfail Nyquist) + 3 fixtures (ff_rss_smoke + ff_rss_dst_cross + macro_dxy_smoke) + 4 macro CSV committed (DXY reuse 1Dyapt2.csv + US10Y/XAUUSD/WTI manual download checkpoint) + metadata.json sha256 anchor + D-10-C0 immutability gate (4 test GREEN da Wave 0) + .gitignore data/cache/
- [ ] 10-02-PLAN.md — Wave 1 MCP-10 core: intermarket/ package (loader.py MacroLoader + sha256 + STRICT-< close_at no future leakage; score.py build_intermarket_score factory pure-fn direction-aware sign flip clamp [-1,+1]; types.py IntermarketContext dataclass; _PAIR_WEIGHTS hardcoded EURUSD/GBPUSD/USDJPY Murphy intermarket)
- [ ] 10-03-PLAN.md — Wave 1 MCP-13 core: calendar_rss/ package (client.py CalendarRSSClient RSS+cache TTL 60min disk JSON + ET->UTC zoneinfo DST-aware imaginary detection + holiday handling + Tentative skip + pair-aware filter; CalendarEvent dataclass; Pitfall 3/4/6/7 mitigations)
- [ ] 10-04a-PLAN.md — Wave 2 strategy/config layer (parallel a 10-04b): config.py _attach_intermarket_macro 6 env (ENABLE_INTERMARKET=false default D-10-D2) + .env.example block + strategy/confluence.py signature extend direction (Path A) + Pitfall 5 patch _log.debug + Warning #4 retry simplification + Warning #5 threshold doc + strategy/context.py field annotation + strategy/_shim.py:83 init-time wire + 4 setups callsite
- [ ] 10-04b-PLAN.md — Wave 2 MCP layer (parallel a 10-04a): mcp_tools/handlers/macro.py (Tools + handlers envelope Phase 6/8) + mcp_tools/server.py singleton bootstrap graceful + mcp/errors.py 2 new ErrorCodes + Blocker #2 re-export verify (mcp_tools/errors.py wildcard propagation hasattr assert)
- [ ] 10-05-PLAN.md — Wave 3 ops+docs: scripts/refresh_macro_csv.py CLI (Pitfall 1 mitigation + Warning #6 ASC ordering enforced + FF probe Pitfall 4) + ROADMAP SC#3 DEVIATED + REQUIREMENTS MCP-10/13 annotation + forex-trader-pro SKILL.md "Pre-decision news check" section (D-10-D3 NO auto-inject) + STATE.md COMPLETE 6/6

---

### Phase 11: Paper Deploy Gate

**Goal:** Run a 30-day paper trading session on demo MT5 with ML inference active, compare live execution metrics vs backtest within tolerance, and document the live-promotion criteria gate.

**Requirements:** DEPLOY-01, DEPLOY-02, DEPLOY-03

**Success criteria:**
1. Paper trading script runs continuously on demo MT5 with ML filter and active-management suggestions; logs every decision + outcome.
2. After 30 days: live metrics report (Sharpe, hit rate, drawdown) compared to backtest expectations; deviation within documented tolerance band.
3. Promotion criteria documented: minimum trade count, max drift, calibration ECE, no critical incidents — all logged with pass/fail.
4. Live promotion DECISION (go / no-go / extend) recorded in `.planning/research/paper-deploy-{date}.md` with rationale.

**Hint UI:** no

---

## Cross-Phase Notes

- **Engineering principles** (forex-algo-dev skill, applies to every phase): bar boundaries sacred, no future in features, pure-function strategy layer, idempotent + observable, calibration over confidence, backtests lie (-25% mental discount), transaction costs eat alpha, regime awareness.
- **Existing infra preservation:** MT5 connector, scheduler, RSS aggregator stay untouched. Refactor only the strategy module + add new modules.
- **MCP contract:** existing 11 tool signatures stable. New tools additive. Refactor extensions backward-compatible by default.
- **Reference data:** `data/historical/{EURUSD,GBPUSD,USDJPY}/{H1,M15,M30}.csv`, semicolon Italian format, 2002-10 → 2026-05.
- **Skills:** consult `forex-trader-pro` for setup/confluence/risk specifics; `forex-algo-dev` for ML pipeline + data quality + backtesting + failure modes; `forex-strategy-builder` for book-grounded patterns.

---
*Last updated: 2026-05-12 — Phase 9 plan-write COMPLETE via /gsd-plan-phase 9 (7 PLAN.md ~4889 LOC totali, ~290 KB). Wave structure: 09-01 Wave 0 scaffolding (hdbscan dep + 26 env var + 4 package + 4 handler stub + D-09-D4 logger.py schema migration + P8 ml/inference._invalidate_singleton hook + 16 test stub xfail) → 09-02 Wave 1 ML-07/MCP-07 cluster (D-09-A1..A4, P1/P2/P3 guards) → 09-03 Wave 2 ML-08/MCP-08 drift (D-09-B1..B4, P10/P11/P12/P14 guards) → 09-04 Wave 3 ML-09 retrain (D-09-C1..C4, P4/P5/P6/P7/P8/P13 guards, riusa Phase 8 _train_ml_filter_worker per D-09-C1 zero-duplication training data integrity priority) → 09-05 Wave 4 MCP-18 position_action (D-09-D1..D4, P9/P15 guards, OOD caveat + italiano markers regex + ENABLE_ML_FILTER=false fallback) → 09-06 Wave 5 INT-03 CLI dashboard (Pattern K markdown 6-section, P11 WAL reader) → 09-07 Wave 6 phase gate (3 E2E test file + VERIFICATION.md coverage matrix + REQUIREMENTS/ROADMAP/STATE update). All 7 requirement IDs covered, all 16 D-09-* decisions traceable, all 15 pitfalls P1-P15 guarded, all 4 SC#1..4 ROADMAP verified. Project memory training data integrity priority preserved: D-09-A1 baseline-only, D-09-C1 zero-duplication, D-09-C2 validation gate silently-worse-model protection, P6 atomic pair-rename, P14 sha256 strict-fail, drift_log.reference_hash audit chain. Phase 9 status: 🟢 plans-written, ready for /gsd-execute-phase 9 post Phase 7 + Phase 8 execute (hard cross-phase deps: ml/feature_extraction Phase 7 Plan 07-01 + ml/inference Phase 7 Plan 07-05 + mcp_tools/handlers/ml._train_ml_filter_worker Phase 8 Plan 08-04). Previous: 2026-05-12 — Phase 8 plan-write COMPLETE via /gsd-plan-phase 8.*
