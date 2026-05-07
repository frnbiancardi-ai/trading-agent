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
| 5 | Baseline Backtest | ○ pending | 0/0 | 0% |
| 6 | MCP Tools (part 1) | ○ pending | 0/0 | 0% |
| 7 | ML Classifier | ○ pending | 0/0 | 0% |
| 8 | MCP Tools (part 2) | ○ pending | 0/0 | 0% |
| 9 | Failure Analysis + Drift | ○ pending | 0/0 | 0% |
| 10 | Intermarket + News | ○ pending | 0/0 | 0% |
| 11 | Paper Deploy Gate | ○ pending | 0/0 | 0% |

**Overall progress:** 0/11 phases complete (0%)

---

## Active Work

Phase 6 — MCP Tools (part 1): CONTEXT.md captured (4 areas, 11 questions, 12 decisioni dirette). Async backtest queue + cancel, in-process trail daemon (position_trails), additive backward-compat MCP-R1/R2/R3, BarSource adapter (live default + as_of_ts opt), replay_decision union lookup, mcp/ package split. Tool surface 25 totali (11 esistenti + 13 REQUIREMENTS + 1 derivato cancel_backtest). Resume: `.planning/phases/06-mcp-tools-part-1/06-CONTEXT.md`. Next: `/gsd-plan-phase 6`.

Phase 5 (CONTEXT.md captured) sospesa — riprendere quando ROADMAP execution order lo richiede.

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
*Last updated: 2026-05-07 after Phase 6 context captured*
