# Trading Agent — v2 ML-Backtest Milestone

## What This Is

Automated forex trading agent (MetaTrader 5 + MCP server) that scans EUR/USD, GBP/USD, USD/JPY, proposes trades against a 4-setup playbook (breakout, S/R reversal, compression, trend pullback), validates risk, and executes via broker. v2 milestone adds an event-driven backtest engine running over ~23.5 years of historical bars and a self-improving ML layer (trade-quality classifier + calibration + failure analysis) trained on backtest decisions and live trade outcomes.

## Core Value

Every trade the agent submits has been pre-filtered by a calibrated ML classifier whose probability estimates match realized hit rate, trained continuously on the agent's own historical decisions — so the system gets measurably better with every backtest cycle and every live trade.

## Requirements

### Validated

<!-- Inferred from existing codebase (`.planning/codebase/`) and recent commits (Phase 14-16 done). Locked. -->

- ✓ MT5 broker connector (account state, OHLC, order submit, close) — existing
- ✓ Risk engine with CONSERVATIVE/BALANCED/AGGRESSIVE profiles — existing
- ✓ Symbol scanner (trend/momentum/volatility/spread bias, candidate score) — existing
- ✓ Strategy core (Python pure rules, A/B/C/D setup hints) — existing (Phase 14)
- ✓ RSS sentiment ingestion — existing (Phase 15)
- ✓ H24 scheduler (autonomous run loop) — existing (Phase 16)
- ✓ MCP server with 11 tools (`get_account_state`, `get_market_snapshot`, `evaluate_trade_proposal`, `submit_order_if_approved`, `get_risk_profile`, `get_trade_history`, `get_symbol_universe`, `scan_symbol_candidates`, `get_symbol_indicators`, `propose_trade`, `close_position`) — existing
- ✓ Indicators baseline: SMA, EMA, RSI, ATR, trend strength, S/R, breakout quality, RSI divergence — existing
- ✓ Per-symbol filling-mode resolver (MT5 bitmask) — existing
- ✓ Codebase map in `.planning/codebase/` — existing

### Active

<!-- Hypotheses for v2 milestone. Validated when shipped. -->

- [ ] Event-driven backtest engine that replays Italian-format CSV bars (semicolon-separated) with realistic costs (spread + commission + slippage) and produces equity curve + metrics
- [ ] Walk-forward validation harness (rolling train/test windows) preventing look-ahead leakage on time series
- [ ] Indicator library expansion: Bollinger Bands + squeeze, ADX/DMI, MACD, Stochastic, Donchian, Keltner, VWAP (intraday + anchored), Fibonacci retracement, Pivot points (daily/session/weekly), NR4/NR7 + Boomer compression detector, Closing Score (Defendi), Hurst exponent, multi-TF alignment helper, volatility-regime classifier (compressed/normal/expanded via ATR percentile)
- [ ] Pattern catalog full: Hammer, Shooting Star, Engulfing, Morning/Evening Star, Key Reversal, Inside Bar, Pin Bar
- [ ] Strategy refactor to pure functions: setup detectors A/B/C/D, 5-factor confluence scorer, ATR-based R:R, proposal builder — same code path used by live and backtest
- [ ] Baseline backtest run: 23.5 years × 3 pairs (EUR/USD, GBP/USD, USD/JPY) × 3 timeframes (M15, M30, H1), strategy-only (no ML) — Sharpe, max drawdown, hit rate, expectancy per slice
- [ ] ML trade-quality classifier (LightGBM binary win/loss) with feature extraction from decision context, walk-forward training, Platt/isotonic calibration
- [ ] ML inference integrated into proposal pipeline as filter (rejects low-quality trades) and confidence calibrator (replaces heuristic with calibrated probability)
- [ ] Failure analysis: cluster losing trades by feature vector, surface dominant failure modes via feature importance
- [ ] Drift monitoring: prediction distribution shift, calibration error over time, automatic retrain trigger
- [ ] Correlation guard: rolling correlation matrix across pairs to prevent stacking same risk
- [ ] Intermarket context engine: DXY, US10Y, gold, oil → bias signals (Murphy)
- [ ] Economic calendar integration: news blackout windows for high-impact events
- [ ] MCP server expansion (15 new tools): `run_backtest`, `get_backtest_metrics`, `walk_forward_validate`, `train_ml_filter`, `predict_trade_quality`, `get_ml_calibration`, `get_failure_clusters`, `get_drift_metrics`, `get_correlation_matrix`, `get_intermarket_context`, `get_session_state`, `get_multi_tf_snapshot`, `get_economic_calendar`, `get_pattern_catalog`, `replay_decision`
- [ ] MCP position-management tools: `modify_position` (move SL/TP, partial close, break-even, trailing stop), `get_position_state`, `suggest_position_action`
- [ ] MCP refactor: extend `get_market_snapshot` (200 bars + opt indicators), `scan_symbol_candidates` (regime + correlation_warnings), `propose_trade` (setup_type + confluence_score), `evaluate_trade_proposal` (ML score + calibrated_prob)
- [ ] Paper deploy gate: 30-day demo MT5 run with metrics within tolerance vs backtest before live activation

### Out of Scope

- Reinforcement learning agent (PPO/DQN end-to-end entry/exit) — requires order-of-magnitude more data + infra; revisit when classifier saturates
- Crypto / equities / commodities trading — FX-only milestone
- Mobile app or web dashboard — CLI + MCP introspection only
- Order book / Level-2 data — broker doesn't expose tick depth reliably
- News NLP fine-tuning — RSS sentiment from existing aggregator is enough for v2
- Greenfield rewrite of MT5 connector / scheduler / RSS — works in production, surgical extension only
- Sub-M15 timeframes (M1, M5) — noise dominates, slippage eats edge
- Exotic pair coverage — 3 majors is the v2 scope

## Context

- **Existing codebase:** Phase 14-16 done. Strategy already in pure-Python form but not yet backtest-ready (side effects, broker calls inline). MCP server, scheduler, RSS sentiment, H24 loop all in production.
- **Historical data:** `data/historical/{EURUSD,GBPUSD,USDJPY}/{H1,M15,M30}.csv`, range 2002-10-21 → 2026-05-04 (~23.5 years). Italian CSV format: `Data; Ora; Open; High; low; Close; Volume`, semicolon-separated, DD/MM/YYYY date, HH:MM:SS time. EUR/USD H1 = 148,901 rows; M15 = 595,777; M30 = 298,358.
- **Skills available locally:** `forex-trader-pro` (live playbook — A/B/C/D setups, 5-factor confluence, risk profiles), `forex-algo-dev` (Python implementation guide — bar boundaries, no-future-leak, pure functions, calibration, walk-forward), `forex-strategy-builder` (book-grounded strategy patterns from Murphy/Probo/Defendi).
- **Recent reference:** strategy backed up in git tag — safe to refactor strategy module aggressively.
- **ML scale realism:** ~200 trades = barely useful classifier; ~2000+ = real edge; ~20000+ = strong alpha. Backtest 23.5y × 3 pairs × 3 TFs should produce 10k–50k trades, sufficient for v1 ML.

## Constraints

- **Tech stack**: Python 3.12 (Anaconda — pydantic-core wheels missing on 3.14), MetaTrader5 client lib, MCP SDK, pandas, lightgbm, scikit-learn for ML.
- **Engineering principles** (from forex-algo-dev skill, non-negotiable): bar-boundary discipline, no future leakage, pure-function strategy layer, idempotent order submission, calibration over confidence, transaction-cost realism, walk-forward only.
- **Existing infra preservation**: MT5 connector, scheduler, RSS aggregator must keep working. New code goes alongside, not replaces.
- **MCP contract stability**: existing 11 tool signatures stay compatible. Refactors that change signatures require explicit deprecation cycle.
- **Data format**: backtest must read Italian semicolon CSV verbatim. No conversion script — adapter in loader.
- **Performance**: full backtest (3 pairs × 3 TFs × 23.5y) should run in under 30 min on dev laptop. Walk-forward fold cap: 10 folds.
- **Cost realism**: spread minimum 0.5 pip EUR/USD majors, slippage 0.3 pip random, commission 0.5 pip round-trip — discount backtest returns by 25% mentally.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Refactor mirato instead of full rewrite | MT5 connector, scheduler, RSS work in production; strategy backed up in git tag so safe to refactor strategy module only | — Pending |
| LightGBM classifier first, no RL | Skill principle: calibration > complexity; RL needs 10–100× more data and infra; classifier delivers value at 2k+ trades | — Pending |
| Walk-forward mandatory on 23.5y backtest | Single in-sample pass over 23.5y guarantees overfit; walk-forward is the only honest baseline | — Pending |
| Paper trading 30 days before live activation | Backtests lie by 20-30%; demo run validates execution realism, drift, broker-side surprises | — Pending |
| Use existing 11 MCP tool signatures unchanged, add 18 new tools | Stable contract with `forex-trader-pro` skill and downstream consumers | — Pending |
| Italian CSV adapter inside backtest loader, no pre-conversion | Avoids data fork; one source of truth in `data/historical/` | — Pending |
| EUR/USD + GBP/USD + USD/JPY × M15 + M30 + H1 only | 9 backtest slices is enough to detect regime sensitivity; more pairs/TFs = noise without signal | — Pending |
| `modify_position` tool consolidates SL/TP move + partial close + break-even + trailing | Single API surface for active management; avoids 4 nearly-identical tools | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-07 after v2 ML-Backtest milestone initialization*
