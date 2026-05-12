# Roadmap: Trading Agent v2 — ML-Backtest Milestone

**Created:** 2026-05-07
**Granularity:** Standard (11 phases)
**Strategy:** Brownfield — surgical extension of existing trading-agent codebase

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Backtest Engine | Event-driven replay of Italian-CSV historical bars with realistic costs and walk-forward harness | BACK-01..06 | 6 |
| 2 | Indicators Library | Expand indicator coverage to support all 4 setups + ML features | INDIC-01..14 | 4 |
| 3 | Patterns Catalog | Full candlestick pattern detection library (4/4 plans, strategy.py callsite refactor done — pending verify) | PATT-01..07 | 3 |
| 4 | Strategy Refactor | Setup A/B/C/D detectors as pure functions, 5-factor confluence, shared by live + backtest (8/8 plans ✅) | STRAT-01..09 | 5 |
| 5 | Baseline Backtest ✓ COMPLETE 2026-05-12 (9/9 plans) | Run strategy-only backtest on 23.5y × 3 pairs × 3 TFs, produce metrics + ML training data (Plan 05-09 closed D-02 schema gap; parquet schema-v2 1076 × 59 PASS) | BACK-07, INT-01 | 4 |
| 6 | MCP Tools (part 1) ✓ COMPLETE 2026-05-11 (4/4 plans Wave 0-3; Wave 4 deferred) | Backtest, position-management, multi-TF, session, correlation, pattern-catalog tools | MCP-01..03, MCP-09, MCP-11..12, MCP-14..17, MCP-R1..R3 | 4 |
| 7 | ML Classifier | LightGBM trade-quality classifier with walk-forward training and calibration | ML-01..06, ML-10 | 5 |
| 8 | MCP Tools (part 2) | ML training/inference/calibration tools, ML-aware risk evaluation | MCP-04..06, MCP-R4, INT-02 | 4 |
| 9 | Failure Analysis + Drift | Failure clustering, drift monitor, retrain trigger, suggest_position_action | ML-07..09, MCP-07..08, MCP-18, INT-03 | 4 |
| 10 | Intermarket + News | DXY/yields/commodities context + economic calendar blackout | MCP-10, MCP-13 | 3 |
| 11 | Paper Deploy Gate | 30-day demo MT5 run with metric tolerance gate before live activation | DEPLOY-01..03 | 4 |

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

**Goal:** Train a LightGBM binary trade-quality classifier on the Phase 5 baseline decision dataset with walk-forward splits and proper Platt/isotonic calibration; persist versioned models.

**Requirements:** ML-01, ML-02, ML-03, ML-04, ML-05, ML-06, ML-10

**Success criteria:**
1. Feature extractor produces a deterministic feature vector from a decision context (verified by snapshot test).
2. Walk-forward training script runs end-to-end on the baseline dataset, produces 10 fold models, no `train_test_split(shuffle=True)` anywhere.
3. Calibration (Platt + isotonic) applied; reliability diagram + Brier score + ECE reported per fold.
4. Inference API: `predict(features) → (raw_score, calibrated_prob)` with <10ms latency on single sample.
5. Classifier integrated into proposal pipeline: trades with `calibrated_prob < threshold` rejected; verified end-to-end on a held-out month.

**Hint UI:** no

---

### Phase 8: MCP Tools (part 2)

**Goal:** Expose ML training, inference, and calibration introspection through MCP; integrate ML score into `evaluate_trade_proposal` response; produce the post-ML backtest report.

**Requirements:** MCP-04, MCP-05, MCP-06, MCP-R4, INT-02

**Success criteria:**
1. `train_ml_filter`, `predict_trade_quality`, `get_ml_calibration` registered in MCP and pass integration tests.
2. `evaluate_trade_proposal` response includes `ml_score` and `calibrated_prob` fields without breaking existing consumers.
3. Post-ML backtest report committed to `.planning/research/ml-on-{date}.md` showing per-slice delta vs baseline (Sharpe, hit rate, expectancy, drawdown).
4. ML-on backtest demonstrates non-trivial improvement vs baseline OR documented analysis of why not (negative result is acceptable signal, not failure).

**Hint UI:** no

---

### Phase 9: Failure Analysis + Drift

**Goal:** Add failure clustering, drift monitoring, automatic retrain trigger, and ML-driven `suggest_position_action` for active position management.

**Requirements:** ML-07, ML-08, ML-09, MCP-07, MCP-08, MCP-18, INT-03

**Success criteria:**
1. Failure clustering identifies ≥3 distinct loss-mode clusters on baseline dataset with feature-importance interpretation.
2. Drift monitor logs prediction distribution KS-stat + calibration ECE per rolling window; alarm triggers when threshold breached.
3. Retrain trigger fires correctly on simulated drift; new model versioned and loaded without service interruption.
4. `suggest_position_action(position_id)` returns hold/move-SL/partial-close/full-close suggestion with rationale, integration-tested on demo positions.

**Hint UI:** no

---

### Phase 10: Intermarket + News

**Goal:** Wire intermarket context (DXY, US10Y, gold, oil) and economic-calendar blackout into the proposal pipeline as confluence inputs and risk filters.

**Requirements:** MCP-10, MCP-13

**Success criteria:**
1. `get_intermarket_context()` returns USD strength bias, risk-on/off bias, JPY safe-haven flag — verified against known historical regimes.
2. `get_economic_calendar(window_minutes)` returns upcoming events with high-impact flag and blackout window; integrates with at least one provider (e.g., ForexFactory RSS, FRED, or ECB feed).
3. Proposal pipeline applies blackout: trades within ±15 min of high-impact events are rejected with explicit reason.

**Hint UI:** no

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
*Last updated: 2026-05-12 — Phase 5 ✓ COMPLETE 9/9 plans (Plan 05-09 plan-execute completato PC secondario, D-02 gap CHIUSO, parquet schema-v2 1076 × 59, Phase 7 ML sbloccata); Previous: 2026-05-11 — Phase 5 REOPENED per Plan 05-09 (dataset writer extension + baseline re-run, chiude D-02 schema gap inherited from plan 05-08, sblocca Phase 7 ML); Phase 4 ✅ COMPLETE 2026-05-08*
