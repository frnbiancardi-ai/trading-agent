# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-07)

**Core value:** Every trade pre-filtered by a calibrated ML classifier whose probabilities match realized hit rate, trained on the agent's own decisions, improving with every cycle.

**Current milestone:** v2-ml-backtest
**Current focus:** Phase 1 — Backtest Engine

---

## Milestone Status

| # | Phase | Status | Plans | Progress |
|---|-------|--------|-------|----------|
| 1 | Backtest Engine | ◐ in-progress | 2/8 | 25% |
| 2 | Indicators Library | ○ pending | 0/0 | 0% |
| 3 | Patterns Catalog | ○ pending | 0/0 | 0% |
| 4 | Strategy Refactor | ○ pending | 0/0 | 0% |
| 5 | Baseline Backtest | ◐ planned | 9/9 | plans only |
| 6 | MCP Tools (part 1) | ○ pending | 0/0 | 0% |
| 7 | ML Classifier | ○ pending | 0/0 | 0% |
| 8 | MCP Tools (part 2) | ○ pending | 0/0 | 0% |
| 9 | Failure Analysis + Drift | ○ pending | 0/0 | 0% |
| 10 | Intermarket + News | ○ pending | 0/0 | 0% |
| 11 | Paper Deploy Gate | ○ pending | 0/0 | 0% |

**Overall progress:** 0/11 phases complete (0%)

---

## Active Work

Phase 7 — ML Classifier: CONTEXT.md captured (4 aree, 15 questions, 20 decisioni D-01..D-20 + 7 Claude discretion). Target: y=1 iff TP_HIT, TIMEOUT/BE=loss, scale_pos_weight per fold. Walk-forward expanding 10 fold, embargo timeout_bars[tf], train/val 80/20 temporal early-stop su Brier. Single LightGBM + categorical (symbol, timeframe, profile, setup_name, regime) + raw features. Hybrid hook: prediction in `evaluate_proposal_for_bar` (attacca prob a ProposalDraft, no filter), decision in `risk_engine.evaluate_trade` (threshold gate). Threshold profit-curve optimized per profile, mediana 10 fold. Artifact: joblib + sidecar metadata.json. Resume: `.planning/phases/07-ml-classifier/07-CONTEXT.md`. Next: `/gsd-plan-phase 7`.

Phase 6 — MCP Tools (part 1): CONTEXT.md captured (4 areas, 11 questions, 12 decisioni dirette). Async backtest queue + cancel, in-process trail daemon (position_trails), additive backward-compat MCP-R1/R2/R3, BarSource adapter (live default + as_of_ts opt), replay_decision union lookup, mcp/ package split. Tool surface 25 totali (11 esistenti + 13 REQUIREMENTS + 1 derivato cancel_backtest). Resume: `.planning/phases/06-mcp-tools-part-1/06-CONTEXT.md`. Next: `/gsd-plan-phase 6`.

Phase 5 — Baseline Backtest: 9 PLAN.md scritti (W0..W4), checker PASS iter 2/3, 6 blocker risolti (parquet directory, SC#3 hard/soft, warmup adattivo, D-21 real test, engine slice_until dual-branch, preflight contract probe). Pronto per `/gsd-execute-phase 5` — bloccato in attesa che Phase 1-4 completino esecuzione (preflight gate in 05-08).

Phase 1 (in-progress, plan 01-02 complete) sospesa — riprendere quando ROADMAP execution order lo richiede.

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
*Last updated: 2026-05-08 after Phase 7 context gathered (4 aree, 15 Q, 20 decisioni)*
