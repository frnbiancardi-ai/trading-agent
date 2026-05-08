# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-07)

**Core value:** Every trade pre-filtered by a calibrated ML classifier whose probabilities match realized hit rate, trained on the agent's own decisions, improving with every cycle.

**Current milestone:** v2-ml-backtest
**Current focus:** Phase 3 — Patterns Catalog

---

## Milestone Status

| # | Phase | Status | Plans | Progress |
|---|-------|--------|-------|----------|
| 1 | Backtest Engine | ✓ complete | 8/8 | 100% |
| 2 | Indicators Library | ✓ complete | 9/9 | 100% |
| 3 | Patterns Catalog | ◐ in-progress | 3/4 | 75% |
| 4 | Strategy Refactor | ○ pending | 0/0 | 0% |
| 5 | Baseline Backtest | ◐ planned | 9/9 | plans only |
| 6 | MCP Tools (part 1) | ○ pending | 0/0 | 0% |
| 7 | ML Classifier | ○ pending | 0/0 | 0% |
| 8 | MCP Tools (part 2) | ○ pending | 0/0 | 0% |
| 9 | Failure Analysis + Drift | ○ pending | 0/0 | 0% |
| 10 | Intermarket + News | ○ pending | 0/0 | 0% |
| 11 | Paper Deploy Gate | ○ pending | 0/0 | 0% |

**Overall progress:** 2/11 phases complete (18%)

---

## Active Work

Phase 3 — Patterns Catalog: 03-03-PLAN ✓ COMPLETE 2026-05-08 (commits `8753b12`, `9fbe21c`, `dc7676a`). Wave 3 chiusa: 5 nuovi detector + scan_patterns ricostruito a `list[PatternHit]`. (1) `is_shooting_star(bar, cfg)` raw=upper/body. (2) `is_morning_star(b1,b2,b3,cfg)` e (3) `is_evening_star(b1,b2,b3,cfg)` 3-bar Murphy ch.10 con anchor=b3, NO look-ahead, raw=penetrazione close oltre midpoint(b1) normalizzata su body_b1. (4) `is_key_reversal(prev,curr,direction,cfg)` outside reversal 2-bar bullish/bearish, raw=penetrazione close oltre midpoint(prev) su range_prev. (5) `is_inside_bar(prev,curr,cfg)` direction='neutral', raw=1.0-range_curr/range_prev. Tutti tuple-return + guard rng<=0/body<=0 (T-3-07). `scan_patterns(bars, last_n, cfg)` thin orchestrator: itera ultime last_n barre, emette PatternHit con extreme_price = swing low bullish / swing high bearish lungo span (1/2/3 bar), bar_index offset negativo, confidence via `_calibrate(raw, cfg.X.calibration)`, Doji confidence=1.0 hardcoded (CONTEXT — non calibrato), Inside Bar+Pin Bar coexist 2 hit distinti (Pitfall 4). 15 nuovi test (5 positivi + 5 near-miss + 1 bearish key_reversal + 4 scan_patterns coverage) + 2 skip Wave 2 rimossi → 31 test attivi in test_patterns.py (era 14+2 skip), 0 skip residui. Suite globale 402 passed + 1 skipped (Mottl optional). 03-02 ✓ (commits `93f86e7`, `847a0fb`), 03-01 ✓ (commits `3c465c1`, `4b1a2fa`, `0768112`). PATT-01..07 implementati end-to-end nella patterns layer; full Complete dopo 03-04 (strategy.py callsite refactor dict→attribute). Next: `/gsd-execute-phase 3` continua con 03-04-PLAN.

Phase 2 — Indicators Library: ✓ COMPLETE 2026-05-08. VERIFICATION PASSED 4/4 ROADMAP truths + 14/14 INDIC requirements (`02-VERIFICATION.md`). 9 plani eseguiti in 4 wave (W0=01, W1=02-04, W2=05-07, W3=08-09) seriali per overlap intra-wave su `__init__.py` + `test_indicators_purity.py`. Suite 374 passed + 1 skipped (Mottl optional). `compute_all` 4-key dict bit-for-bit immutato (4 callsite invariati). `compute_all_extended` 37-key snapshot disponibile per Phase 1 backtest + Phase 4 strategy refactor. Known item NON-bloccante: Boomer A2 (CONTEXT.md verbatim) ≠ skill `forex-trader-pro`/`price_action.md:43` — reconciliation deferred a Phase 4. Branch `feature/update-pythono-pure-strategy`.


Phase 7 — ML Classifier: CONTEXT.md captured (4 aree, 15 questions, 20 decisioni D-01..D-20 + 7 Claude discretion). Target: y=1 iff TP_HIT, TIMEOUT/BE=loss, scale_pos_weight per fold. Walk-forward expanding 10 fold, embargo timeout_bars[tf], train/val 80/20 temporal early-stop su Brier. Single LightGBM + categorical (symbol, timeframe, profile, setup_name, regime) + raw features. Hybrid hook: prediction in `evaluate_proposal_for_bar` (attacca prob a ProposalDraft, no filter), decision in `risk_engine.evaluate_trade` (threshold gate). Threshold profit-curve optimized per profile, mediana 10 fold. Artifact: joblib + sidecar metadata.json. Resume: `.planning/phases/07-ml-classifier/07-CONTEXT.md`. Next: `/gsd-plan-phase 7`.

Phase 6 — MCP Tools (part 1): CONTEXT.md captured (4 areas, 11 questions, 12 decisioni dirette). Async backtest queue + cancel, in-process trail daemon (position_trails), additive backward-compat MCP-R1/R2/R3, BarSource adapter (live default + as_of_ts opt), replay_decision union lookup, mcp/ package split. Tool surface 25 totali (11 esistenti + 13 REQUIREMENTS + 1 derivato cancel_backtest). Resume: `.planning/phases/06-mcp-tools-part-1/06-CONTEXT.md`. Next: `/gsd-plan-phase 6`.

Phase 5 — Baseline Backtest: 9 PLAN.md scritti (W0..W4), checker PASS iter 2/3, 6 blocker risolti (parquet directory, SC#3 hard/soft, warmup adattivo, D-21 real test, engine slice_until dual-branch, preflight contract probe). Pronto per `/gsd-execute-phase 5` — bloccato in attesa che Phase 1-4 completino esecuzione (preflight gate in 05-08).


Phase 1 — Backtest Engine: COMPLETE 2026-05-07. All 8 plans + VERIFICATION.md PASSED (6/6 truths). Engine event-driven, costs.yaml, walk-forward, metrics, smoke 12-month <60s (6.78s actual). Legacy RSI/SMA grid archived.

---

## Recent Decisions

See `.planning/PROJECT.md` Key Decisions table.

---

## Notes

- Brownfield project. Existing infra (MT5, scheduler, RSS, MCP server) untouched.
- Strategy backed up in git tag — safe to refactor.
- Historical data: 23.5y, 3 pairs × 3 TFs in `data/historical/`.
- Skills: `forex-trader-pro`, `forex-algo-dev`, `forex-strategy-builder`.

---
*Last updated: 2026-05-08 — Phase 3 plan 03 ✓ COMPLETE (5 nuovi detector + scan_patterns rebuild, 3/4 plans, 75%)*
