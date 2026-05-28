# Phase 6: MCP Tools (part 1) — Discussion Log

**Session:** 2026-05-07
**Mode:** discuss (interactive, default)
**Areas selected by user:** 4/4 (tutte)
**Total questions:** 11

---

## Area 1 — Backtest execution model + run lifecycle

### Q1.1 — Sync vs Async execution model
**Options presented:**
- Async + run_id immediato + poll (Recommended)
- Sync block fino a fine
- Sync con cap small + async per multi

**User selection:** Async + run_id immediato + poll
**Notes:** Decision motivata da single-slice ~minuti, baseline 27-run ~30min — sync block sfora MCP timeout client.

### Q1.2 — Run storage location
**Options presented:**
- Stesso logs/trades.db Phase 5 schema (Recommended)
- DB separato logs/mcp_runs.db
- In-memory only

**User selection:** Stesso logs/trades.db Phase 5 schema
**Notes:** Disambiguazione via prefisso run_id (`mcp_{ts}_...` vs `baseline_{date}_...`). Single source per replay_decision.

### Q1.3 — Progress reporting (clarify request, deep-dive 3 options)
**Initial options:**
- get_backtest_metrics polimorfico (Recommended)
- Tool dedicato get_backtest_progress
- MCP server progress notifications

**User asked:** "spiega tutti i punti" → fornita analisi dettagliata di tutte 3 opzioni con pro/contro architetturali.
**User selection:** Opt 1 (`get_backtest_metrics` polimorfico, schema branch su `status`).
**Notes:** Allineato con D-A1 async (no protocol streaming). 1 tool, 1 round-trip.

### Q1.4 — Concurrency + cancel
**Options presented:**
- Max 1 run async + cancel_backtest tool (Recommended)
- Multi-run paralleli, no cancel
- Multi-run con global cap + cancel

**User selection:** Max 1 run + cancel_backtest
**Notes:** Cap evita OOM (Phase 5 D-15 ~1.8GB peak). `cancel_backtest` è tool extra non in REQUIREMENTS — segnato derivato Phase 6.

---

## Area 2 — modify_position design + trailing

### Q2.1 — Tool shape (combo vs split)
**Options presented:**
- Single combo tool atomico (Recommended)
- Split: 4 tool separati
- Combo + actions[] esplicite

**User selection:** Single combo tool atomico
**Notes:** Fedele a REQUIREMENTS MCP-16 5-arg signature.

### Q2.2 — Trailing logic location (clarify request → deep-dive opt 1 e opt 3)
**Initial options:**
- In-process daemon (scheduler tick) (Recommended)
- MT5 server-side trailing nativo
- One-shot move SL + skill ricalcola

**User asked:** "capiamo meglio 1 e 3" → fornita analisi architetturale daemon vs one-shot.
**Follow-up clarify:** "in che senso che e' responsabile dello stato trailing?" → spiegato concetto stato persistente (server) vs stateless one-shot (client).
**User selection:** Opt 1 (in-process daemon, SQLite `position_trails`, scheduler hook).
**Notes:** Decisione chiave — trailing autonomo 24/7 senza skill attiva. Coupling con scheduler Phase 16.

### Q2.3 — Broker validation behavior
**Options presented:**
- Strict reject + suggest valid (Recommended)
- Pass-through MT5 error raw
- Auto-clamp a min distance

**User selection:** Strict reject + suggested_sl
**Notes:** Preserve user intent, no magic auto-correct. Skill può riprovare con suggested.

---

## Area 3 — Backward-compat MCP-R1/R2/R3

### Q3.1 — Extension strategy (clarify request → deep-dive 3 options)
**Initial options:**
- Additive sempre attivi (Recommended)
- Opt-in via flag arg
- Tool versioning v2

**User asked:** "analizziamo tutt" → fornita analisi completa (schema, pro/contro, trade-off matrix, edge bar count 50→200).
**User selection:** Opt 1 (additive sempre attivi).
**Notes:** Allineato PROJECT.md "tool signature stable, refactor backward-compatible by default". Single codepath, zero drift. MCP-R1 con `bars` arg opzionale (default 200, override 50 per legacy).

---

## Area 4 — Data source policy (live MT5 vs historical CSV)

### Q4.1 — OHLC source per multi_tf/correlation/pattern_catalog (clarify request → deep-dive 3 options)
**Initial options:**
- Live default + as_of arg per CSV (Recommended)
- Sempre MT5 live, CSV solo replay_decision
- source arg required ovunque

**User asked:** "spiega" → fornita analisi (use case live vs replay, schema, pro/contro, edge cases).
**User selection:** Opt 1 (live default + `as_of_ts` opt).
**Notes:** BarSource adapter unico, `replay_decision` thin orchestrator.

### Q4.2 — replay_decision lookup source
**Options presented:**
- Union: trades_log + baseline_decisions.parquet (Recommended)
- Solo trades_log (live decisions)
- Solo baseline_decisions.parquet

**User selection:** Union lookup
**Notes:** Coverage completa live + backtest decisions. Disambiguazione via prefix decision_id.

---

## Aree NON discusse (Claude's discretion)

- **Module layout** `mcp/handlers/` package vs monolitico — Claude default: split per dominio (account/market/proposal/position/backtest), pattern già usato Phase 2/4. Documentato come D-E1.
- **`equity_curve_path` schema** — file PNG (consistent Phase 5 D-19).
- **`walk_forward_validate` orchestration** — fold in serie nel singolo job (Phase 1 D-06 walk_forward è pure-function).
- **`get_session_state` boundaries** — hard-coded UTC sessions FX standard.
- **`get_correlation_matrix` lookback** — default 100 bar.
- **`get_pattern_catalog` bar count** — default 50.
- **Test integration `modify_position`** — `@pytest.mark.integration`, skip default CI.
- **`replay_decision` diff schema** — campi chiave + `full_diff` opt.

---

## Deferred ideas raccolte

Vedi sezione `<deferred>` in `06-CONTEXT.md` (16 elementi).

---

*Discussion log generated 2026-05-07*
