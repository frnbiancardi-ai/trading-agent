# Requirements: Trading Agent v2 — ML-Backtest Milestone

**Defined:** 2026-05-07
**Core Value:** Every trade pre-filtered by a calibrated ML classifier whose probabilities match realized hit rate, trained on the agent's own decisions, improving with every cycle.

## v1 Requirements

Requirements for the v2-ml-backtest milestone (the project's "v1 of this milestone"). Each maps to roadmap phases.

### Backtest Engine

- [x] **BACK-01**: Italian-CSV loader parses `data/historical/{SYMBOL}/{TF}.csv` (semicolon-separated, DD/MM/YYYY date, HH:MM:SS time, columns Data/Ora/Open/High/low/Close/Volume) into in-memory bars
- [ ] **BACK-02**: Event-driven backtest engine replays bars one-at-a-time, calling the same strategy code path as live (no parallel implementation)
- [ ] **BACK-03**: Cost model applies spread + commission + slippage on every fill (configurable per symbol)
- [ ] **BACK-04**: Backtest produces equity curve, trade ledger, per-trade decision context for ML training
- [ ] **BACK-05**: Walk-forward harness splits time series into rolling train/test windows (no shuffle, no overlap leakage)
- [ ] **BACK-06**: Metrics module computes Sharpe, Sortino, max drawdown, hit rate, expectancy, profit factor, average R per trade
- [ ] **BACK-07**: Backtest runs over full 23.5y × 3 pairs × 3 TFs in <30 min on dev laptop

### Indicators

- [x] **INDIC-01**: Bollinger Bands (20-period, 2σ) + squeeze detector (BBW < threshold)
- [x] **INDIC-02**: ADX/DMI (14-period) for trend strength + directional bias
- [x] **INDIC-03**: MACD (12/26/9) line + signal + histogram
- [x] **INDIC-04**: Stochastic Oscillator (14/3/3) %K + %D
- [x] **INDIC-05**: Donchian Channel (20-period) high/low for breakout levels
- [x] **INDIC-06**: Keltner Channel (EMA20 ± 2×ATR)
- [x] **INDIC-07**: VWAP intraday + anchored (session/day anchor)
- [x] **INDIC-08**: Fibonacci retracement levels (38.2%, 50%, 61.8%) on detected swing legs
- [x] **INDIC-09**: Pivot points daily / session / weekly (classic + Camarilla)
- [x] **INDIC-10**: NR4 / NR7 detector + Boomer (inside-narrow sequence)
- [x] **INDIC-11**: Closing Score (Defendi formula): position of close in bar range, 0-100
- [x] **INDIC-12**: Hurst exponent (rolling) for trend-vs-mean-revert regime
- [x] **INDIC-13**: Multi-TF alignment helper (H4 + H1 + M15 trend coherence score)
- [x] **INDIC-14**: Volatility-regime classifier: compressed / normal / expanded via ATR percentile vs 200-bar window

### Patterns

- [x] **PATT-01**: Hammer / Inverted Hammer detector <!-- complete 2026-05-08: 03-02 firma (matched, raw_score) + 6+1 test; 03-03 emesso come PatternHit dallo scan; 03-04 callsite strategy.py refactor (commit 42e41dd) -->
- [x] **PATT-02**: Shooting Star detector <!-- complete 2026-05-08: 03-03 is_shooting_star + 1 positivo + 1 near-miss; emesso come PatternHit; 03-04 callsite strategy.py refactor -->
- [x] **PATT-03**: Bullish / Bearish Engulfing detector <!-- complete 2026-05-08: 03-02 firma (matched, raw_score) + gate min_body_ratio + 4+1 test; 03-03 emesso come PatternHit (bull/bear); 03-04 callsite strategy.py refactor -->
- [x] **PATT-04**: Morning Star / Evening Star (3-bar) detector <!-- complete 2026-05-08: 03-03 is_morning_star + is_evening_star (anchor b3, no look-ahead) + 2 positivi + 2 near-miss; emessi come PatternHit span_bars=3; 03-04 callsite strategy.py refactor -->
- [x] **PATT-05**: Key Reversal Bar detector <!-- complete 2026-05-08: 03-03 is_key_reversal (bullish/bearish) + 1 pos bull + 1 pos bear + 1 near-miss; emesso come PatternHit span_bars=2; 03-04 callsite strategy.py refactor -->
- [x] **PATT-06**: Inside Bar / Pin Bar detector <!-- complete 2026-05-08: 03-02 firma (matched, raw_score) PinBar 2 test; 03-03 is_inside_bar + Inside+Pin coexist test (Pitfall 4); emessi come PatternHit span_bars=2 direction='neutral' per inside_bar; 03-04 callsite strategy.py refactor -->

- [x] **PATT-07**: Pattern catalog returns confidence + structural reference points (bar index, extreme prices) <!-- complete 2026-05-08: 03-01 foundation (PatternHit frozen + load_pattern_config + _calibrate + config/patterns.yaml); 03-03 scan_patterns ricostruito a list[PatternHit] su tutti 9 pattern + Doji; 03-04 strategy.py callsite consume PatternHit attribute access + IntradayStrategy._pattern_cfg cached (commits 42e41dd, e61f541) -->


### Strategy Refactor

- [ ] **STRAT-01**: Setup A (Breakout) detector — pure function, takes bars+indicators, returns proposal-ready dict or None
- [ ] **STRAT-02**: Setup B (S/R Reversal) detector — pure function
- [ ] **STRAT-03**: Setup C (Compression Breakout) detector — pure function
- [ ] **STRAT-04**: Setup D (Trend Pullback) detector — pure function
- [ ] **STRAT-05**: 5-factor confluence scorer (trend / setup / momentum / volatility / spread+session)
- [ ] **STRAT-06**: Confidence calibrator: grade → starting confidence + ±0.05 adjusters
- [ ] **STRAT-07**: ATR-based R:R proposal builder with profile-aware minimums
- [x] **STRAT-08**: Strategy module side-effect-free (no broker calls, no DB writes, no print/log) — testable in milliseconds
- [ ] **STRAT-09**: Same strategy module called by live loop AND backtest engine (no fork)

### ML Layer

- [ ] **ML-01**: Feature extraction module: serialize decision context (indicators snapshot, setup type, confluence breakdown, market regime) into feature vector
- [ ] **ML-02**: LightGBM binary classifier (target: trade was profitable y/n at TP/SL resolution)
- [ ] **ML-03**: Walk-forward training pipeline (no shuffle, expanding or rolling window)
- [ ] **ML-04**: Calibration: Platt scaling AND isotonic regression, pick best by Brier score on validation
- [ ] **ML-05**: Inference API returns calibrated probability + raw score
- [ ] **ML-06**: Inference integrated into proposal pipeline — filter (reject if calibrated_prob < threshold) and confidence override
- [ ] **ML-07**: Failure analysis: cluster losing trades by feature vector (k-means or HDBSCAN), surface top failure modes
- [ ] **ML-08**: Drift monitor: track prediction distribution shift (KS-test) and calibration error over rolling window
- [ ] **ML-09**: Retrain trigger: drift threshold breach OR scheduled monthly OR manual via tool
- [ ] **ML-10**: ML-trained models versioned + persisted (`models/classifier_v{N}_{date}.pkl`)

### MCP Tools (new)

- [ ] **MCP-01**: `run_backtest(symbol, timeframe, date_range, profile)` — replay strategy on historical CSV
- [ ] **MCP-02**: `get_backtest_metrics(run_id)` — Sharpe, MaxDD, hit rate, expectancy, equity curve points
- [ ] **MCP-03**: `walk_forward_validate(symbol, timeframe, n_folds)` — rolling train/test report
- [ ] **MCP-04**: `train_ml_filter(data_source)` — retrain classifier from backtest+live trade history
- [ ] **MCP-05**: `predict_trade_quality(proposal_payload)` — ML inference on a proposal, returns score + calibrated_prob
- [ ] **MCP-06**: `get_ml_calibration()` — reliability diagram + Brier score + ECE for current model
- [ ] **MCP-07**: `get_failure_clusters(top_n)` — dominant failure modes from latest analysis
- [ ] **MCP-08**: `get_drift_metrics(window_days)` — prediction distribution shift + calibration error trend
- [ ] **MCP-09**: `get_correlation_matrix(symbols, lookback_bars)` — rolling correlation across pairs
- [ ] **MCP-10**: `get_intermarket_context()` — DXY, US10Y, gold, oil → bias signals
- [ ] **MCP-11**: `get_session_state()` — current FX session + spread profile + optimal-hour flag
- [ ] **MCP-12**: `get_multi_tf_snapshot(symbol)` — H4 + H1 + M15 indicators in single call
- [ ] **MCP-13**: `get_economic_calendar(window_minutes)` — upcoming high-impact events with blackout flag
- [ ] **MCP-14**: `get_pattern_catalog(symbol, timeframe)` — full candlestick pattern scan on recent bars
- [ ] **MCP-15**: `replay_decision(decision_id)` — re-run historical decision with current code (regression test)
- [ ] **MCP-16**: `modify_position(position_id, new_sl?, new_tp?, partial_close_lots?, move_sl_to_breakeven?, trail_stop_atr_mult?)` — active position management
- [ ] **MCP-17**: `get_position_state(position_id)` — current P&L, distance to SL/TP, holding time, max favorable excursion
- [ ] **MCP-18**: `suggest_position_action(position_id)` — ML/rule-based hold/move-SL/partial/full-close suggestion

### MCP Tools (refactor existing)

- [ ] **MCP-R1**: `get_market_snapshot` — extend to 200 bars + opt indicators flag (backward compatible default)
- [ ] **MCP-R2**: `scan_symbol_candidates` — add `regime` and `correlation_warnings` fields
- [ ] **MCP-R3**: `propose_trade` — add `setup_type` (A/B/C/D) and `confluence_score` fields
- [ ] **MCP-R4**: `evaluate_trade_proposal` — integrate ML quality filter, add `ml_score` + `calibrated_prob` to response

### Integration / Deploy

- [ ] **INT-01**: Baseline backtest report committed to `.planning/research/baseline-{date}.md` (pre-ML metrics, 9 slices)
- [ ] **INT-02**: ML-on backtest report committed (post-ML metrics, delta vs baseline)
- [ ] **INT-03**: Drift dashboard (CLI command) shows current model health
- [ ] **DEPLOY-01**: Paper-trading script running on demo MT5 account, ML inference active
- [ ] **DEPLOY-02**: 30-day paper run completed with metrics within tolerance vs backtest before any live activation
- [ ] **DEPLOY-03**: Promotion gate: documented criteria for paper → live transition

## v2 Requirements

Deferred to future milestones.

### Reinforcement Learning

- **RL-01**: PPO/DQN agent for end-to-end entry/exit on backtest replay
- **RL-02**: Reward shaping with risk-adjusted returns
- **RL-03**: Online policy update from live experience

### Deep Learning

- **DL-01**: LSTM/Transformer on sequence features (200-bar windows)
- **DL-02**: Attention-based regime detector
- **DL-03**: Ensemble (LightGBM + DL) with stacking meta-learner

### Coverage Expansion

- **COV-01**: Add EUR/JPY, AUD/USD, NZD/USD pairs
- **COV-02**: M5 timeframe support
- **COV-03**: Crypto and equities adapters

### Tooling

- **TOOL-01**: Web dashboard (FastAPI + React) for run inspection
- **TOOL-02**: Mobile alerts for drift breaches
- **TOOL-03**: News NLP fine-tuning on FX-specific corpus

## Out of Scope

Explicitly excluded for v2.

| Feature | Reason |
|---------|--------|
| Greenfield rewrite of MT5/scheduler/RSS | Existing infra works in production; refactor only the strategy module |
| Reinforcement learning end-to-end | Requires 10-100× more data + infra; classifier delivers value first |
| Crypto / equities trading | FX-only milestone scope |
| Order book / Level-2 data | Broker doesn't expose tick depth reliably |
| Mobile app / web dashboard | CLI + MCP introspection enough for v2 |
| Sub-M15 timeframes | Noise dominates, slippage eats edge |
| Exotic FX pairs | 3 majors enough for first ML cycle |
| News NLP fine-tuning | RSS aggregator existing output sufficient |
| Real-time tick processing | Bar-close decisions only (skill principle: bar boundaries are sacred) |

## Traceability

Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BACK-01 | Phase 1 | Complete (plan 01-02) |
| BACK-02 | Phase 1 | Pending |
| BACK-03 | Phase 1 | Pending |
| BACK-04 | Phase 1 | Pending |
| BACK-05 | Phase 1 | Pending |
| BACK-06 | Phase 1 | Pending |
| BACK-07 | Phase 5 | Pending |
| INDIC-01 | Phase 2 | Complete |
| INDIC-02 | Phase 2 | Complete |
| INDIC-03 | Phase 2 | Complete |
| INDIC-04 | Phase 2 | Complete |
| INDIC-05 | Phase 2 | Complete |
| INDIC-06 | Phase 2 | Complete |
| INDIC-07 | Phase 2 | Complete |
| INDIC-08 | Phase 2 | Complete |
| INDIC-09 | Phase 2 | Complete |
| INDIC-10 | Phase 2 | Complete |
| INDIC-11 | Phase 2 | Complete |
| INDIC-12 | Phase 2 | Complete |
| INDIC-13 | Phase 2 | Complete |
| INDIC-14 | Phase 2 | Complete |
| PATT-01 | Phase 3 | Complete |
| PATT-02 | Phase 3 | Complete |
| PATT-03 | Phase 3 | Complete |
| PATT-04 | Phase 3 | Complete |
| PATT-05 | Phase 3 | Complete |
| PATT-06 | Phase 3 | Complete |
| PATT-07 | Phase 3 | Complete |
| STRAT-01 | Phase 4 | In-progress (04-05 Wave 2: detect_a_breakout 208 LOC pure-fn READY/FORMING/NONE + _compute_levels_a D-10; commit 69ad6cd. Full complete dopo Wave 4 regression replay) |
| STRAT-02 | Phase 4 | In-progress (04-01 Wave 0: detector stub created; Wave 2 plan-06 implements) |
| STRAT-03 | Phase 4 | In-progress (04-01 Wave 0: detector stub created; Wave 2 plan-06 implements) |
| STRAT-04 | Phase 4 | In-progress (04-05 Wave 2: detect_d_pullback 298 LOC pure-fn trend-following mai counter-trend + _compute_levels_d D-10 con prior_swing/leg_size fallback; commit a963130. Full complete dopo Wave 4) |
| STRAT-05 | Phase 4 | In-progress (04-01 Wave 0: confluence.py stub + config/strategy.yaml D-08; Wave 1 implements) |
| STRAT-06 | Phase 4 | In-progress (04-01 Wave 0: base_confidence + adjusters + bounds in config; Wave 1 implements) |
| STRAT-07 | Phase 4 | In-progress (04-01 Wave 0: ProposalDraft + profile_filters in config; Wave 1 implements) |
| STRAT-08 | Phase 4 | Complete (04-04 Wave 1: AST gate 232 LOC, 5 test no-skip, copre import+logging+print/open su 7 moduli puri; adapters/ esclusi by design; negative-test verificato; commit 0260126) |
| STRAT-09 | Phase 4 | In-progress (04-01 Wave 0: adapter stubs + regression baseline JSON; Wave 3/4 wires + verifies) |
| ML-01 | Phase 7 | Pending |
| ML-02 | Phase 7 | Pending |
| ML-03 | Phase 7 | Pending |
| ML-04 | Phase 7 | Pending |
| ML-05 | Phase 7 | Pending |
| ML-06 | Phase 7 | Pending |
| ML-07 | Phase 9 | Pending |
| ML-08 | Phase 9 | Pending |
| ML-09 | Phase 9 | Pending |
| ML-10 | Phase 7 | Pending |
| MCP-01 | Phase 6 | Pending |
| MCP-02 | Phase 6 | Pending |
| MCP-03 | Phase 6 | Pending |
| MCP-04 | Phase 8 | Pending |
| MCP-05 | Phase 8 | Pending |
| MCP-06 | Phase 8 | Pending |
| MCP-07 | Phase 9 | Pending |
| MCP-08 | Phase 9 | Pending |
| MCP-09 | Phase 6 | Pending |
| MCP-10 | Phase 10 | Pending |
| MCP-11 | Phase 6 | Pending |
| MCP-12 | Phase 6 | Pending |
| MCP-13 | Phase 10 | Pending |
| MCP-14 | Phase 6 | Pending |
| MCP-15 | Phase 6 | Pending |
| MCP-16 | Phase 6 | Pending |
| MCP-17 | Phase 6 | Pending |
| MCP-18 | Phase 9 | Pending |
| MCP-R1 | Phase 6 | Pending |
| MCP-R2 | Phase 6 | Pending |
| MCP-R3 | Phase 6 | Pending |
| MCP-R4 | Phase 8 | Pending |
| INT-01 | Phase 5 | Pending |
| INT-02 | Phase 8 | Pending |
| INT-03 | Phase 9 | Pending |
| DEPLOY-01 | Phase 11 | Pending |
| DEPLOY-02 | Phase 11 | Pending |
| DEPLOY-03 | Phase 11 | Pending |

**Coverage:**
- v1 requirements: 73 total
- Mapped to phases: 73
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-07*
*Last updated: 2026-05-07 after initial v2 definition*
