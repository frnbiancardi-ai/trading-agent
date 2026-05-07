# Roadmap: Trading Agent v2 — ML-Backtest Milestone

**Created:** 2026-05-07
**Granularity:** Standard (11 phases)
**Strategy:** Brownfield — surgical extension of existing trading-agent codebase

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Backtest Engine | Event-driven replay of Italian-CSV historical bars with realistic costs and walk-forward harness | BACK-01..06 | 6 |
| 2 | Indicators Library | Expand indicator coverage to support all 4 setups + ML features | INDIC-01..14 | 4 |
| 3 | Patterns Catalog | Full candlestick pattern detection library | PATT-01..07 | 3 |
| 4 | Strategy Refactor | Setup A/B/C/D detectors as pure functions, 5-factor confluence, shared by live + backtest | STRAT-01..09 | 5 |
| 5 | Baseline Backtest | Run strategy-only backtest on 23.5y × 3 pairs × 3 TFs, produce metrics + ML training data | BACK-07, INT-01 | 4 |
| 6 | MCP Tools (part 1) | Backtest, position-management, multi-TF, session, correlation, pattern-catalog tools | MCP-01..03, MCP-09, MCP-11..12, MCP-14..17, MCP-R1..R3 | 4 |
| 7 | ML Classifier | LightGBM trade-quality classifier with walk-forward training and calibration | ML-01..06, ML-10 | 5 |
| 8 | MCP Tools (part 2) | ML training/inference/calibration tools, ML-aware risk evaluation | MCP-04..06, MCP-R4, INT-02 | 4 |
| 9 | Failure Analysis + Drift | Failure clustering, drift monitor, retrain trigger, suggest_position_action | ML-07..09, MCP-07..08, MCP-18, INT-03 | 4 |
| 10 | Intermarket + News | DXY/yields/commodities context + economic calendar blackout | MCP-10, MCP-13 | 3 |
| 11 | Paper Deploy Gate | 30-day demo MT5 run with metric tolerance gate before live activation | DEPLOY-01..03 | 4 |

**Coverage:** 73/73 v1 requirements mapped (100%).

---

## Phase Details

### Phase 1 — Backtest Engine

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

### Phase 2 — Indicators Library

**Goal:** Add the missing indicators required by the forex-trader-pro playbook (Bollinger, ADX, MACD, Stochastic, Donchian, Keltner, VWAP, Fibonacci, Pivot, NR4/7, Closing Score, Hurst, multi-TF alignment, volatility regime classifier) as pure functions consumable by both live and backtest paths.

**Requirements:** INDIC-01, INDIC-02, INDIC-03, INDIC-04, INDIC-05, INDIC-06, INDIC-07, INDIC-08, INDIC-09, INDIC-10, INDIC-11, INDIC-12, INDIC-13, INDIC-14

**Success criteria:**
1. Each indicator has a unit test against a known reference value (TradingView or manual calc).
2. All indicators are pure functions: no side effects, deterministic, no future leakage (rolling computations use only past data, normalization uses `expanding().shift(1)` not full-series).
3. Multi-TF alignment helper accepts (H4, H1, M15) bar streams and returns a coherence score in [0, 1].
4. Volatility-regime classifier returns one of {compressed, normal, expanded} based on ATR percentile vs 200-bar window — verified on known regime samples.

**Hint UI:** no

---

### Phase 3 — Patterns Catalog

**Goal:** Replace the existing minimal `patterns.py` with a full candlestick pattern catalog (Hammer, Shooting Star, Engulfing, Morning/Evening Star, Key Reversal, Inside Bar, Pin Bar) returning structural anchor points usable by Setup B and ML features.

**Requirements:** PATT-01, PATT-02, PATT-03, PATT-04, PATT-05, PATT-06, PATT-07

**Success criteria:**
1. Each pattern detector has a unit test with a hand-crafted positive case AND a near-miss negative case.
2. Pattern catalog returns a list of `PatternHit` dicts with `name`, `bar_index`, `extreme_price`, `confidence` (0–1), `direction`.
3. Existing `scan_patterns()` callers in `strategy.py` continue to work (backward-compatible signature OR adapter shim with deprecation note).

**Hint UI:** no

---

### Phase 4 — Strategy Refactor

**Goal:** Refactor the existing strategy module into pure-function setup detectors (A/B/C/D), a 5-factor confluence scorer, ATR-based R:R proposal builder, with the same code path executed by the live scheduler and the backtest engine — no fork.

**Requirements:** STRAT-01, STRAT-02, STRAT-03, STRAT-04, STRAT-05, STRAT-06, STRAT-07, STRAT-08, STRAT-09

**Success criteria:**
1. Each setup detector is a pure function: `(bars, indicators, regime, profile) → ProposalDraft | None`. No broker calls, no log/print, no DB writes.
2. Confluence scorer returns 5 factor booleans + grade (A+/A/B/C/reject) + starting confidence; matches forex-trader-pro skill table exactly.
3. Strategy unit tests run in <500ms total (sub-millisecond per detector).
4. Backtest engine and live scheduler invoke the *same* `evaluate_proposal_for_bar(bars, indicators, ctx)` function — verified by import graph.
5. Existing live behavior unchanged on a regression fixture (10 historical decisions replayed produce identical proposals to pre-refactor output).

**Hint UI:** no

---

### Phase 5 — Baseline Backtest

**Goal:** Execute the full pre-ML baseline backtest across 23.5 years × 3 pairs (EUR/USD, GBP/USD, USD/JPY) × 3 timeframes (M15, M30, H1), produce per-slice metrics and the trade-decision dataset that will train the ML classifier.

**Requirements:** BACK-07, INT-01

**Success criteria:**
1. Full 9-slice backtest completes in <30 min on dev laptop with documented config.
2. Per-slice metrics report (Sharpe, MaxDD, hit rate, expectancy, profit factor, trade count) committed to `.planning/research/baseline-{date}.md`.
3. Decision dataset (≥10k labeled trades expected, target win/loss outcome at TP/SL) persisted to `data/training/baseline_decisions.parquet`.
4. Equity curves plotted per slice (PNG output) committed to `.planning/research/baseline-equity-curves/`.

**Hint UI:** no

---

### Phase 6 — MCP Tools (part 1)

**Goal:** Expose the new backtest, position-management, multi-TF, correlation, session, and pattern-catalog tools through the MCP server, plus refactor existing snapshot/scan/propose tools for backward-compatible expansion.

**Requirements:** MCP-01, MCP-02, MCP-03, MCP-09, MCP-11, MCP-12, MCP-14, MCP-15, MCP-16, MCP-17, MCP-R1, MCP-R2, MCP-R3

**Success criteria:**
1. All 13 new/refactored tools registered in `mcp_server.py` with JSON-Schema descriptions; `tools/list` returns the new surface.
2. `modify_position` validates broker `stops_level`, refuses invalid SL distances, supports break-even and trailing modes — covered by integration test against MT5 demo.
3. Existing `forex-trader-pro` skill-driven flows still pass (existing tool signatures unchanged on default args).
4. End-to-end test: `run_backtest` → `get_backtest_metrics` round-trip via MCP returns metrics matching direct in-process call.

**Hint UI:** no

---

### Phase 7 — ML Classifier

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

### Phase 8 — MCP Tools (part 2)

**Goal:** Expose ML training, inference, and calibration introspection through MCP; integrate ML score into `evaluate_trade_proposal` response; produce the post-ML backtest report.

**Requirements:** MCP-04, MCP-05, MCP-06, MCP-R4, INT-02

**Success criteria:**
1. `train_ml_filter`, `predict_trade_quality`, `get_ml_calibration` registered in MCP and pass integration tests.
2. `evaluate_trade_proposal` response includes `ml_score` and `calibrated_prob` fields without breaking existing consumers.
3. Post-ML backtest report committed to `.planning/research/ml-on-{date}.md` showing per-slice delta vs baseline (Sharpe, hit rate, expectancy, drawdown).
4. ML-on backtest demonstrates non-trivial improvement vs baseline OR documented analysis of why not (negative result is acceptable signal, not failure).

**Hint UI:** no

---

### Phase 9 — Failure Analysis + Drift

**Goal:** Add failure clustering, drift monitoring, automatic retrain trigger, and ML-driven `suggest_position_action` for active position management.

**Requirements:** ML-07, ML-08, ML-09, MCP-07, MCP-08, MCP-18, INT-03

**Success criteria:**
1. Failure clustering identifies ≥3 distinct loss-mode clusters on baseline dataset with feature-importance interpretation.
2. Drift monitor logs prediction distribution KS-stat + calibration ECE per rolling window; alarm triggers when threshold breached.
3. Retrain trigger fires correctly on simulated drift; new model versioned and loaded without service interruption.
4. `suggest_position_action(position_id)` returns hold/move-SL/partial-close/full-close suggestion with rationale, integration-tested on demo positions.

**Hint UI:** no

---

### Phase 10 — Intermarket + News

**Goal:** Wire intermarket context (DXY, US10Y, gold, oil) and economic-calendar blackout into the proposal pipeline as confluence inputs and risk filters.

**Requirements:** MCP-10, MCP-13

**Success criteria:**
1. `get_intermarket_context()` returns USD strength bias, risk-on/off bias, JPY safe-haven flag — verified against known historical regimes.
2. `get_economic_calendar(window_minutes)` returns upcoming events with high-impact flag and blackout window; integrates with at least one provider (e.g., ForexFactory RSS, FRED, or ECB feed).
3. Proposal pipeline applies blackout: trades within ±15 min of high-impact events are rejected with explicit reason.

**Hint UI:** no

---

### Phase 11 — Paper Deploy Gate

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
*Last updated: 2026-05-07 after initial roadmap creation*
