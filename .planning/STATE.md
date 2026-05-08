# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-07)

**Core value:** Every trade pre-filtered by a calibrated ML classifier whose probabilities match realized hit rate, trained on the agent's own decisions, improving with every cycle.

**Current milestone:** v2-ml-backtest
**Current focus:** Phase 4 — Strategy Refactor

---

## Milestone Status

| # | Phase | Status | Plans | Progress |
|---|-------|--------|-------|----------|
| 1 | Backtest Engine | ✓ complete | 8/8 | 100% |
| 2 | Indicators Library | ✓ complete | 9/9 | 100% |
| 3 | Patterns Catalog | ✓ complete | 4/4 | 100% |
| 4 | Strategy Refactor | ◐ in-progress | 3/8 | 38% |
| 5 | Baseline Backtest | ◐ planned | 9/9 | plans only |
| 6 | MCP Tools (part 1) | ○ pending | 0/0 | 0% |
| 7 | ML Classifier | ○ pending | 0/0 | 0% |
| 8 | MCP Tools (part 2) | ○ pending | 0/0 | 0% |
| 9 | Failure Analysis + Drift | ○ pending | 0/0 | 0% |
| 10 | Intermarket + News | ○ pending | 0/0 | 0% |
| 11 | Paper Deploy Gate | ○ pending | 0/0 | 0% |

**Overall progress:** 3/11 phases complete (27%)

---

## Active Work

Phase 4 — Strategy Refactor: ◐ Wave 1 IN-PROGRESS (3/8 plans). 04-03-PLAN COMPLETE 2026-05-08: proposal.py adapters + R:R floor + ATR cap helper (STRAT-07 in-progress, full complete dopo Wave 4). 3 task TDD-backed (cc2ef77 RED smoke import + 17c0504 GREEN 4 funzioni + d7e10bf test 25 cases). 217 LOC source (ProposalDraft W0 preservato + 4 funzioni: draft_to_trade_proposal con comment="python_strategy" literal, draft_to_technical_setup con field-name mapping stop_loss_price→stop_loss/take_profit_price→take_profit + indicators dict carry factors/grade/setup_name/rationale_parts, rr_meets_profile_floor con epsilon FP 1e-9 + (False,0.0) fail-safe per risk≤0, compute_levels_with_atr_cap universale 4 setup con cap 1.5×ATR di default) + 239 LOC test (3 parametrize × 3 cases per profile boundary + SELL symmetric + invalid paths + 4 quadranti ATR cap BUY/SELL × buffer/cap). Full suite 437 passed + 16 skip (+25 pass, –6 skip vs Wave 1-02). 1 deviazione Rule 1 inline (FP epsilon su rr=1.3 boundary aggressive: 0.001*1.3 produce 0.0012999... → fix +1e-9). 1 deviazione Rule 2 (test extra non prescritti per coverage SELL/invalid/inverted). Pure module verificato (0 broker/logging/print/datetime.now). Field name mapping documentato per Wave 4 regression reference.

04-02-PLAN COMPLETE 2026-05-08: confluence.py 5-factor scorer + grade + confidence calibrator (STRAT-05/06 in-progress, full complete dopo Wave 4). 2 task atomici (b0f35e7 feat + 2e16fb2 test). 315 LOC source (12 funzioni: load_strategy_config con lru_cache + StrategyConfig frozen + 5 factor predicates None-safe + score_factors/grade_for/compute_confidence) + 221 LOC test (10 hand-calc no-skip via SimpleNamespace + tmp_path env-override). Full suite 412 passed + 22 skip (+10 pass, –9 skip vs Wave 0). 2 deviazioni Rule 1 inline (FP epsilon 1e-6 su spread_tighter, datetime.now(UTC) deprecation Python 3.12). Pure module verificato: zero broker/logging/print, solo yaml.safe_load cached. Adjuster math A+ +0.15→clamp 0.95, C -0.15→0.25 (no-clamp documentato in deviation §clamp_at_min). compute_confidence ritorna 0.0 (NON min_confidence) per grade='reject' — coerente baseline regression D-11.

04-01-PLAN COMPLETE 2026-05-08 (1/8 plans). Skeleton + regression baseline + config + RiskProfile alias. 5 task atomici (8324d5f, b8237c1, c545826, e1a87a6, 0bfd18c). 21 file creati, 2 modificati. `strategy/` package con 12 moduli stub; legacy renamed `strategy.py → strategy_legacy.py` con re-export selettivo. Backward-compat verificata: 402 passed + 31 skipped. Baseline regression `tests/fixtures/strategy_regression_baseline.json` deterministica (10 scenari `setup_type=NONE confidence=0.0`). `config/strategy.yaml` D-08 schema completo. `models.RiskProfile = Literal[CONS, MOD, AGG]` aggiunto. 3 deviazioni Rule 1/2/3 documentate. Branch `feature/update-pythono-pure-strategy`. Next: 04-03-PLAN Wave 1 (proposal.py adapters + R:R floor + ATR cap helper).

Phase 3 — Patterns Catalog: ✓ COMPLETE 2026-05-08. VERIFICATION PASSED 3/3 ROADMAP truths + 7/7 PATT-01..07 (`03-VERIFICATION.md`). 4 plani in 4 wave seriali. `PatternHit` frozen dataclass (6 campi) + `PatternConfig`/`CalibrationAnchors` + `_calibrate` knee 0.7. 9 detector + Doji emessi da `scan_patterns(bars, last_n, cfg) → list[PatternHit]`. `strategy.py` refactor end-to-end: import `load_pattern_config`, `self._pattern_cfg` init, callsite riga 230, 3 dict-access → attribute access. Suite 402 passed + 1 skipped (Mottl). `config/patterns.yaml` 10 chiavi (9 calibrati + doji geometry-only). Branch `feature/update-pythono-pure-strategy`.

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
*Last updated: 2026-05-08 — Phase 4 Plan 03 (Wave 1 proposal.py adapters + R:R floor + ATR cap) COMPLETE (3/8 plans, STRAT-07 in-progress; 437 passed + 16 skip; 3 task TDD-backed cc2ef77 RED + 17c0504 GREEN + d7e10bf test; 1 bug-fix Rule 1 inline FP epsilon 1e-9 boundary; 1 deviation Rule 2 test extra coverage)*
