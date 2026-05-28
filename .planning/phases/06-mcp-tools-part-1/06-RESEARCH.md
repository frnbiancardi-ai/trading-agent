# Phase 6: MCP Tools (part 1) — Research

**Researched:** 2026-05-08
**Domain:** MCP tool registration (mcp >= 1.27), async backtest control plane, MT5 position modify (TRADE_ACTION_SLTP + stops_level), trailing-stop daemon (SQLite + APScheduler), backward-compatible schema evolution, point-in-time bar loading (live vs CSV).
**Confidence:** HIGH on existing codebase shape, MCP SDK API, MT5 TRADE_ACTION_SLTP semantics, Phase 1–5 surfaces. MEDIUM on TenTrade-specific `trade_stops_level` value (not measured in this session — must read at runtime). MEDIUM on `ProcessPoolExecutor.cancel_futures` mid-execution semantics on Windows. LOW on long-term broker-side trailing capability (rejected by D-B2 anyway).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Backtest execution model + run lifecycle
- **D-A1:** Async run + `run_id` immediato + poll. `run_backtest`/`walk_forward_validate` non bloccano: `ProcessPoolExecutor`, ritornano subito `{run_id, status: "started", started_at}`. Client polla `get_backtest_metrics(run_id)`.
- **D-A2:** Storage condiviso con Phase 5 — `logs/trades.db` schema `backtest_runs` + `backtest_trades`. Disambiguazione via prefisso `run_id`: baseline → `baseline_{date}_{symbol}_{tf}_{profile}`, MCP → `mcp_{utc_ts}_{symbol}_{tf}_{profile}`.
- **D-A3:** `get_backtest_metrics` polimorfico per status (`running` | `done` | `failed` | `cancelled`). Schema response cambia in base a `status`; nessun tool dedicato `get_backtest_progress`.
- **D-A4:** Max 1 run async concorrente + `cancel_backtest(run_id)`. Nuovo `run_backtest` mentre uno gira → `{error: "run_in_progress", active_run_id}`. `cancel_backtest` è tool extra Phase 6 derivato, non in REQUIREMENTS.

#### modify_position design + trailing
- **D-B1:** Single combo tool atomico `modify_position(position_id, new_sl?, new_tp?, partial_close_lots?, move_sl_to_breakeven?, trail_stop_atr_mult?)`. 5 optional, almeno 1 settato. Conflict rules:
  - `trail_stop_atr_mult` + `new_sl` → `conflict: trail_and_manual_sl`
  - `move_sl_to_breakeven` + `new_sl` → `conflict: be_and_manual_sl`
  - `partial_close_lots >= position.volume` → `partial_exceeds_volume`
- **D-B2:** Trailing stop = in-process daemon, scheduler-driven, persistent SQLite tabella `position_trails`. Scheduler hook `trail_tick()` ogni `SCHEDULER_INTERVAL_MINUTES`. Persistente: riavvio agent ricarica trail attivi.
- **D-B3:** Strict broker validation, no auto-clamp. Pre-call `mt5.symbol_info(symbol).trade_stops_level` per validare `new_sl`/`new_tp`. Violazione → `{ok: false, error: "stops_level_violation", current_price, min_distance_pips, requested_sl, suggested_sl}`. Filling mode `ORDER_FILLING_RETURN` di default.

#### Backward-compat MCP-R1/R2/R3
- **D-C1:** Additive fields sempre attivi, no flag opt-in, no `_v2` versioning. Tutti e 3 i tool ritornano i campi nuovi sempre.
  - **MCP-R1 `get_market_snapshot`:** `indicators_extended: ExtendedIndicators` (Phase 2 D-09). Bar count default **200** (vs 50 originale), nuovo arg opzionale `bars: int` (50–500). I 4 indicatori legacy (sma_20/ema_50/rsi_14/atr_14) restano in `indicators` (compat); nuovi vivono in `indicators_extended`.
  - **MCP-R2 `scan_symbol_candidates`:** schema response esteso con `regime: "compressed"|"normal"|"expanded"` (Phase 2 D-15) + `correlation_warnings: [{paired_symbol, rolling_corr, lookback_bars}]`. Schema input invariato.
  - **MCP-R3 `propose_trade`:** schema response esteso con `setup_type: "A"|"B"|"C"|"D"` + `confluence_score: float` (5-factor scorer Phase 4 D-08). Input invariato. `setup_type: null` / `confluence_score: null` se freeform skill manuale.

#### Data source policy
- **D-D1:** Live default + `as_of_ts` optional arg per slice point-in-time. Tool che leggono OHLC accettano `as_of_ts: ISO8601 | None`. `None` (default) → live MT5; valorizzato → CSV via Phase 1 `load_italian_csv` + `bisect_left` slice `< as_of_ts` (no future leakage). Single codepath via `mcp/bar_source.py::BarSource.get(...)`.
- **D-D2:** `replay_decision` union lookup `trades_log` (live decisions) + `baseline_decisions.parquet` (Phase 5). Recovera `bar_ts_utc + symbol + timeframe + ProposalDraft snapshot`, poi:
  1. `BarSource.get(symbol, tf, n_warmup, as_of_ts=bar_ts_utc)`
  2. `compute_all_extended(bars)` (Phase 2)
  3. `build_ctx_backtest(...)` (Phase 4 D-05)
  4. `evaluate_proposal_for_bar(...)` con codice CORRENTE
  Ritorna `{original, replayed, diff, regression: bool}`.

#### Module layout (Claude's discretion → locked default)
- **D-E1:** Split `mcp_server.py` in package `mcp/` con `mcp/server.py + mcp/schemas.py + mcp/bar_source.py + mcp/job_queue.py + mcp/trail_daemon.py + mcp/handlers/{account,market,proposal,position,backtest}.py`. `mcp_server.py` shim `from mcp.server import *` per CLI compat (`python -m mcp_server`).

#### Engineering principles
- **D-F1:** JSON-Schema rigoroso per ogni tool — `inputSchema` con `type, required, enum, constraint numerici, description`. Validation server-side prima di handler.
- **D-F2:** Error envelope uniforme `{ok: false, error: <code>, message: <human>, ...context}`. Codici standardizzati: `run_in_progress`, `unknown_run_id`, `historical_data_unavailable`, `stops_level_violation`, `as_of_ts_out_of_range`, `partial_exceeds_volume`, `conflict: <type>`, `mt5_not_ready`.
- **D-F3:** Logging stderr-only, mai stdout (vincolo MCP protocol).
- **D-F4:** Bootstrap ordering invariato — `_bootstrap_mt5()` da `__main__`, non a import time. Job queue + trail daemon prima di `stdio_server`.

### Claude's Discretion
- `equity_curve_path` schema: PNG file path (Phase 5 D-19) — DEFAULT.
- `walk_forward_validate` orchestration: fold in serie nello stesso job — DEFAULT.
- `get_session_state` boundaries: hard-coded UTC sessions (Sydney/Tokyo/London/NY) in `handlers/market.py` — DEFAULT.
- `get_correlation_matrix` lookback default: 100 bar, override via arg — DEFAULT.
- `get_pattern_catalog` bar count default: 50, override via arg — DEFAULT.
- `cancel_backtest` esposto pubblicamente in `tools/list` — DEFAULT.
- Test integration `modify_position` su MT5 demo: `@pytest.mark.integration`, skip default in CI, runnable manualmente prima merge — DEFAULT.
- `replay_decision` regression diff schema: campi chiave (direction, entry, sl, tp, confidence) + `full_diff` opt arg true — DEFAULT.

### Deferred Ideas (OUT OF SCOPE)
- MCP progress notifications protocol (sostituito da D-A3 polimorfico)
- Multi-run paralleli (cap=1 da D-A4; future env `MCP_MAX_CONCURRENT_RUNS`)
- `evaluate_trade_proposal` ML extension (MCP-R4) → Phase 8
- Tool versioning `_v2` o flag opt-in (rifiutato D-C1)
- ML-backed `suggest_position_action` → Phase 9
- MT5 server-side trailing nativo (rifiutato D-B2)
- Auto-clamp SL invalid (rifiutato D-B3)
- Tool `cancel_all_backtests` (cap=1 lo rende inutile)
- Schema `oneOf` JSON-Schema rigoroso (preferito permissivo + discriminator `status`)
- Paginazione equity curve (PNG path basta)
- Trail multi-TF (daemon usa `cfg.TRAIL_TICK_TIMEFRAME` fisso)
- Tool intermarket / news → Phase 10
- WebSocket transport MCP (stdio sufficiente)
- Tool `list_active_trails` (diagnostico — aprire se debugging serve)
- Decision replay con strategia storica (replay usa codice CORRENTE; checkout temporaneo out of scope)
- Modify multi-position bulk (1 ticket per call)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-01 | `run_backtest(symbol, timeframe, date_range, profile)` — replay strategy on historical CSV | §Backtest Control Plane (`run_backtest` handler + JobQueue) |
| MCP-02 | `get_backtest_metrics(run_id)` — Sharpe, MaxDD, hit rate, expectancy, equity curve | §Backtest Control Plane (polimorfico per status) + Phase 1 `metrics.compute_metrics` |
| MCP-03 | `walk_forward_validate(symbol, timeframe, n_folds)` — rolling train/test report | §Backtest Control Plane (orchestratore N folds in serie nel job) + Phase 1 `walk_forward.walk_forward_slices` |
| MCP-09 | `get_correlation_matrix(symbols, lookback_bars)` — rolling correlation | §Market Context Tools (rolling corr, default 100 bar) |
| MCP-11 | `get_session_state()` — current FX session + spread profile + optimal-hour flag | §Market Context Tools (hard-coded UTC sessions) |
| MCP-12 | `get_multi_tf_snapshot(symbol)` — H4 + H1 + M15 indicators in single call | §Market Context Tools + Phase 2 `MTFAlignmentResult` |
| MCP-14 | `get_pattern_catalog(symbol, timeframe)` — full candlestick pattern scan | §Market Context Tools + Phase 3 `scan_patterns` |
| MCP-15 | `replay_decision(decision_id)` — re-run historical decision with current code | §Replay Decision Architecture (union lookup trades_log + parquet) |
| MCP-16 | `modify_position(position_id, new_sl?, new_tp?, partial_close_lots?, move_sl_to_breakeven?, trail_stop_atr_mult?)` | §modify_position Architecture (atomic combo + stops_level + trail register) |
| MCP-17 | `get_position_state(position_id)` — P&L, distance to SL/TP, holding time, MFE | §modify_position Architecture (MFE/MAE tracking) |
| MCP-R1 | `get_market_snapshot` — extend to 200 bars + opt indicators flag (backward compatible) | §Backward-Compatible Refactor (additive `indicators_extended`, `bars` arg) |
| MCP-R2 | `scan_symbol_candidates` — add `regime` and `correlation_warnings` fields | §Backward-Compatible Refactor (additive response) |
| MCP-R3 | `propose_trade` — add `setup_type` (A/B/C/D) and `confluence_score` fields | §Backward-Compatible Refactor (Phase 4 D-08 5-factor scorer) |
| (Derived) `cancel_backtest` | Tool extra non in REQUIREMENTS — necessario per D-A4 cancel UX | §Backtest Control Plane (`JobQueue.cancel`) |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

The planner must verify all of these are respected by every task:

| Directive | Source | Implication for Phase 6 |
|-----------|--------|-------------------------|
| Python 3.12 64-bit Anaconda | CLAUDE.md / STACK.md | All new modules target 3.12; type hints `str | None` (PEP 604) OK. |
| `EXECUTION_MODE=shadow` default | CLAUDE.md | `modify_position` MUST honor `cfg.DRY_RUN` like existing `close_position` (mcp_server.py:411-421). Tool returns `{success: True, dry_run: True, note: ...}` when `DRY_RUN`, no broker call. |
| Tutto da `.env`, zero magic numbers | CLAUDE.md | New env: `MCP_MAX_CONCURRENT_RUNS=1`, `MCP_DEFAULT_BARS=200`, `TRAIL_TICK_TIMEFRAME=M15`, `TRAIL_FAVORABLE_ONLY=true`. All in `config.py::Config` + `.env.example`. No hard-coded literals. |
| Risk engine = unico gate trade | CLAUDE.md | `modify_position` does NOT bypass `risk_engine.evaluate_trade` — but it doesn't open new trades either. SL/TP modify is post-risk-gate by definition. Trail daemon ditto: never opens new positions. |
| `ORDER_FILLING_RETURN` only TenTrade | CLAUDE.md | `Mt5Client.modify_position` (new wrapper) MUST resolve filling mode via `resolve_filling_mode(symbol)` (mt5_client.py:110-124) — already returns `ORDER_FILLING_RETURN` for TenTrade GBPUSD/EURUSD. No bypass. |
| Italiano commenti / log / rationale | CLAUDE.md | All new docstrings, `log.info` messages, error `message` text in italiano. Exception: tool descriptions in `inputSchema.description` may stay english per MCP convention (skill consumers expect english). |
| pytest, mock `Mt5Client` | CLAUDE.md | Unit tests for all handlers use `MagicMock` for `mcp.mt5` singleton (existing pattern `tests/test_mcp_tools_v2.py:51-70`). Real-broker integration tests marked `@pytest.mark.integration`, skip default. |
| `tests/conftest.py` MetaTrader5 stub | tests/conftest.py:14-40 | Tests can run on dev laptop without MT5 installed; new tests inherit this. |

---

## Summary

Phase 6 is an **exposure phase**, not a logic phase. 13 of the 14 tools (12 from REQUIREMENTS + 1 derived `cancel_backtest`) wrap surfaces locked in Phases 1–5: backtest engine + walk-forward (Phase 1), `compute_all_extended` + `MTFAlignmentResult` + regime classifier (Phase 2), `scan_patterns` (Phase 3), `evaluate_proposal_for_bar` + `ProposalDraft` + `build_ctx_backtest` (Phase 4), `baseline_decisions.parquet` schema (Phase 5). The only NEW business logic is the **trailing-stop daemon** (D-B2) — a `position_trails` SQLite table + a single `trail_tick()` job registered on the existing scheduler, calling ATR-based candidate-SL math and `Mt5Client.modify_position` per active trail.

Three architectural pieces dominate complexity:

1. **Async backtest control plane (D-A1/A3/A4):** `ProcessPoolExecutor(max_workers=1)` + per-process worker that does NOT import `mt5_client` (MetaTrader5 lib is not fork-safe — Phase 5 D-15 carry-forward). The worker uses only `BacktestBroker` + `load_italian_csv` (CSV-only, zero broker dependency). `JobQueue` keeps an in-memory `dict[run_id, JobRecord]` that survives within process lifetime; on restart the rows in `backtest_runs` (status persisted) are the recovery surface — `get_backtest_metrics` falls back to DB lookup when not in memory. **Cancel semantics on Windows:** `Future.cancel()` only works pre-execution; mid-execution requires `pool.shutdown(wait=False, cancel_futures=True)` followed by re-creation of the pool. This terminates the worker process abruptly — backtest engine state is lost, partial rows in `backtest_trades` for that `run_id` may exist; mark `backtest_runs.status='cancelled'` and document the UX expectation that partial trade rows can be queried (or cleaned up by the task wave that delivers the cancel handler).

2. **`modify_position` as atomic combo (D-B1):** Five optional args, three conflict pairs, two MT5 round-trips at most (one `TRADE_ACTION_SLTP` for SL/TP, one `TRADE_ACTION_DEAL` opposite-side partial close — the existing `close_position` pattern). `Mt5Client` does NOT have `modify_position` today — must be added as a thin wrapper around `mt5.order_send(action=TRADE_ACTION_SLTP, ...)`, mirroring `close_position` (mt5_client.py:191-250) for retry + filling-mode + retcode handling. Pre-call validation reads `mt5.symbol_info(symbol).trade_stops_level` (in points; multiply by `point` and divide by pip-size to get pips), rejects with `stops_level_violation` and a `suggested_sl` rather than auto-clamping. **Atomicity caveat:** if step 1 (SL/TP) succeeds and step 2 (partial close) fails, broker state is partially mutated; we return `{ok: false, error: broker_rejected, applied_so_far: [...]}` and do NOT attempt rollback (broker is the source of truth — Phase 6 does not implement compensation actions). This is documented in tool description.

3. **Trailing daemon coupling with scheduler (D-B2):** `position_trails` table is created by `mcp/trail_daemon.py::ensure_table()` on import; the daemon's `trail_tick(mt5_client, db_path)` is the function the scheduler calls. **Two scheduler entry points exist** in this codebase: the legacy `Orchestrator` + APScheduler `BlockingScheduler` (scheduler.py:293-313, Phase 13) AND the Phase-16 `IntradayLoopScheduler.run_one_cycle` (scheduler.py:530-632, internal H24 loop, no APScheduler). The trail tick should be invoked from `IntradayLoopScheduler.run_one_cycle` (the active path — Phase 13 orchestrator is dormant when Phase 16 is running) BEFORE `_manage_open_positions` (so trail-driven SL update happens first; manual close logic runs second on the updated SL). Adding a single line `self._trail_tick(account_state)` between heartbeat begin and PAUSE_TRADING check is the minimum-invasive integration. The daemon survives agent restart because `position_trails.active=1` rows are reloaded each `trail_tick`. **Race condition with manual position close:** between two ticks (5–15 min depending on `INTRADAY_SCAN_INTERVAL_MINUTES`), a user could close manually; daemon's next tick checks `mt5.positions_get(ticket=...)`, finds nothing, sets `active=0` — no broker error, daemon idempotent.

**Primary recommendation:** Execute Phase 6 in 5 waves: (1) `mcp/` package skeleton + shim + tests pass with old surface unchanged; (2) `mcp/bar_source.py` + `mcp/schemas.py` + extended schemas for R1/R2/R3 (additive only); (3) backtest control plane (`mcp/job_queue.py`, `mcp/handlers/backtest.py`, `cancel_backtest`, `replay_decision`); (4) `modify_position` + `Mt5Client.modify_position` wrapper + trail daemon + scheduler hook; (5) market-context tools (`get_correlation_matrix`, `get_session_state`, `get_multi_tf_snapshot`, `get_pattern_catalog`, `get_position_state`) + integration smoke + `forex-trader-pro` skill flow regression.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MCP tool registration + dispatch | `mcp/server.py` | `mcp_server.py` (shim) | Single `Server` instance + `@list_tools` + `@call_tool` per MCP SDK. Shim preserves CLI invocation. |
| JSON-Schema definitions | `mcp/schemas.py` | each handler module | Centralized for shared shapes (proposal); per-handler for tool-specific. |
| Per-domain handlers | `mcp/handlers/{account,market,proposal,position,backtest}.py` | — | Mirrors Phase 2 `indicators/` and Phase 4 `strategy/` package layout (D-E1). |
| Bar source abstraction (live vs CSV) | `mcp/bar_source.py` | `backtest/loader.py` (Phase 1) | Single codepath for OHLC: live MT5 default, `as_of_ts` triggers CSV slice. |
| Async job queue | `mcp/job_queue.py` | `concurrent.futures.ProcessPoolExecutor` | In-memory registry + DB fallback for status. Worker process MUST NOT import MT5. |
| Trail daemon state | `logs/trades.db` `position_trails` | `mcp/trail_daemon.py` | Persistent across restart; per-process connection (WAL mode, Phase 5 D-16). |
| Trail tick invocation | `IntradayLoopScheduler.run_one_cycle` (scheduler.py:530-632) | `mcp/trail_daemon.py::trail_tick` | Active scheduler path Phase 16; legacy `Orchestrator` left untouched. |
| Position modify (broker call) | `Mt5Client.modify_position` (NEW) | `mt5.order_send(TRADE_ACTION_SLTP)` | Mirror existing `close_position` wrapper pattern. |
| Stops-level validation | `mcp/handlers/position.py` | `Mt5Client.get_symbol_info` | Pre-call check, reject with `suggested_sl` per D-B3. |
| Backtest run record | `backtest/ledger.py` (Phase 1 D-07) | `logs/trades.db` `backtest_runs` | Same schema as baseline; prefix `mcp_<utc_ts>` differentiates origin. |
| Decision replay | `mcp/handlers/backtest.py::handle_replay_decision` | `trades_log` (live) + `data/training/baseline_decisions.parquet` (Phase 5) | Union lookup; orchestrates Phase 2/4 surfaces. |
| Risk gate | `risk_engine.evaluate_trade` | — | Untouched. `modify_position` operates post-gate (existing positions); `propose_trade` and `submit_order_if_approved` continue to call it. |

---

## Standard Stack

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` | `1.27.0` | MCP SDK — `Server`, `Tool`, `TextContent`, `stdio_server` | [VERIFIED: `pip show` via `.venv/Lib/site-packages/mcp-1.27.0.dist-info/METADATA`] Already pinned `>=1.27.0` in requirements.txt; existing 11 tools use it. |
| `MetaTrader5` | `5.0.5735` | Position read/modify, symbol_info, retcode handling | [VERIFIED: requirements.txt:1] Already used in `mt5_client.py`; new `modify_position` wrapper extends pattern. |
| `pydantic` | `2.11.3` | (Indirect via `mcp` types) | [VERIFIED: requirements.txt:3] Used by mcp SDK internally for `Tool` model. |
| `apscheduler` | unpinned | Existing scheduler (Phase 13 path); Phase 16 `IntradayLoopScheduler` is pure-python | [VERIFIED: requirements.txt:7] Trail tick hooks on Phase 16 path; APScheduler not extended in this phase. |
| `concurrent.futures.ProcessPoolExecutor` | stdlib | Job queue worker pool (D-A1) | [VERIFIED: stdlib 3.12; pattern from Phase 5 D-15] Same constraint: workers MUST NOT import MetaTrader5 (not fork-safe). |
| `sqlite3` | stdlib | `position_trails` table; `backtest_runs` shared with Phase 5 | [VERIFIED: existing `logs/trades.db`] WAL mode (Phase 5 D-16) handles multi-writer contention. |
| `pyarrow` | (Phase 5 dep) | Parquet read for `replay_decision` lookup in `baseline_decisions.parquet` | [CITED: Phase 5 D-01 dataset format] Required transitively if Phase 5 has shipped; verify present in `requirements.txt` before Phase 6 Wave 0. |
| `bisect` | stdlib | `BarSource.get(as_of_ts)` strict-< slice | [VERIFIED: Phase 1 contract] |
| `pytest` | unpinned | Test runner | [VERIFIED: pytest.ini, tests/test_mcp_tools_v2.py] |

### Supporting (stdlib)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses` | stdlib | `JobRecord`, `TrailIntent` | Project convention (models.py). |
| `threading` | stdlib | `JobQueue._lock` (Lock around in-memory registry) | Server is single-process; lock guards against handler concurrency under asyncio. |
| `uuid` | stdlib | Optional fallback for `run_id` if no symbol/tf/profile derivation | Default scheme: `mcp_{utc_ts}_{symbol}_{tf}_{profile}` — UUID only as tiebreaker. |
| `hashlib` | stdlib | `cost_yaml_hash` (re-used from Phase 1 D-07) when run record written | No new use beyond Phase 1 pattern. |
| `zoneinfo` | stdlib + `tzdata` package | `get_session_state` UTC ↔ session boundaries | [VERIFIED: requirements.txt:11 `tzdata`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ProcessPoolExecutor(max_workers=1)` | `asyncio.create_task` running BacktestEngine in event loop | Would block the MCP event loop on heavy CPU work (BacktestEngine is sync). ProcessPool isolates CPU + survives crashes. Locked by D-A1. |
| In-memory `JobQueue` registry | Pure DB-backed (no in-memory dict) | DB-only would require polling DB on every status call; in-memory is faster and DB serves as fallback for restart. |
| New `mcp_runs.db` | Shared `logs/trades.db` | Single-source rejected by D-A2; same DB simplifies `replay_decision` lookups. |
| Schema versioning `_v2` tools | Additive fields | Drift + double codepath; rejected by D-C1. |
| `Mt5Client.modify_position` returning bare `bool` | `OrderResult` (existing dataclass models.py:51) | Consistency with `send_order` / `close_position` shape. |
| `mcp_server.py` monolithic | `mcp/` package split | At ~450 LOC current + ~1,000 LOC new = 1,500 LOC unmaintainable. D-E1 locks split. |
| Schema `oneOf` for `get_backtest_metrics` polymorphic | Permissive schema with `status` discriminator + optional fields | `oneOf` not universally supported by MCP clients; permissive + descriminator is safer. Locked by deferred-ideas note in CONTEXT. |

**No new runtime dependencies required.** All Phase 6 work uses existing libraries.

**Version verification (executed 2026-05-08 in this session):**
- `mcp 1.27.0` — [VERIFIED: `cat .venv/Lib/site-packages/mcp-1.27.0.dist-info/METADATA | head -10` returned Version: 1.27.0]
- Server decorators `@server.list_tools()` and `@server.call_tool(*, validate_input: bool = True)` — [VERIFIED: `mcp/server/lowlevel/server.py:492` shows `def call_tool(self, *, validate_input: bool = True):`. Default validates input against `inputSchema` automatically — important for D-F1.]
- `Tool` model fields: `name, description, inputSchema: dict[str, Any], outputSchema: dict[str, Any] | None` — [VERIFIED: `mcp/types.py:1315-1322`]

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MCP client (forex-trader-pro skill / claude-desktop / agent SDK)       │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ JSON-RPC over stdio
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  mcp_server.py (THIN SHIM)                                              │
│      from mcp.server import *  (D-E1; preserves `python -m mcp_server`) │
└────────────────────────────┬────────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  mcp/server.py — Server("trading-agent")                                │
│    @server.list_tools()  → 25 Tool entries (11 existing + 13 + 1)       │
│    @server.call_tool()   → dispatch by name to handlers/                │
│    bootstrap order: cfg → log → mt5 → JobQueue → trail_table → stdio    │
└────┬───────────────┬─────────────┬──────────────┬─────────────┬─────────┘
     │               │             │              │             │
     ▼               ▼             ▼              ▼             ▼
┌─────────┐ ┌──────────────┐ ┌───────────┐ ┌────────────┐ ┌──────────┐
│account.py│ │market.py     │ │proposal.py│ │position.py │ │backtest. │
│          │ │              │ │           │ │            │ │py        │
│account_  │ │market_       │ │propose_   │ │modify_     │ │run_      │
│state     │ │snapshot (R1) │ │trade (R3) │ │position    │ │backtest  │
│risk_     │ │scan_         │ │evaluate_  │ │(16)        │ │(01)      │
│profile   │ │candidates(R2)│ │trade_     │ │get_        │ │get_      │
│trade_    │ │symbol_       │ │proposal   │ │position_   │ │backtest_ │
│history   │ │indicators    │ │submit_    │ │state (17)  │ │metrics   │
│          │ │symbol_       │ │order_if_  │ │close_      │ │(02)      │
│          │ │universe      │ │approved   │ │position    │ │walk_     │
│          │ │multi_tf (12) │ │           │ │            │ │forward(03)│
│          │ │correlation(09)│ │           │ │            │ │cancel_   │
│          │ │session(11)   │ │           │ │            │ │backtest  │
│          │ │pattern_cat14 │ │           │ │            │ │replay(15)│
└────┬─────┘ └──────┬───────┘ └─────┬─────┘ └─────┬──────┘ └────┬─────┘
     │              │                │             │              │
     └──────────────┼────────────────┼─────────────┼──────────────┘
                    │                │             │
                    ▼                ▼             ▼
         ┌──────────────────┐ ┌─────────────┐ ┌──────────────────┐
         │ mcp/bar_source.py│ │mcp/schemas. │ │ mcp/job_queue.py │
         │  BarSource.get(  │ │py           │ │  ProcessPool     │
         │   live | as_of)  │ │ JSON-Schema │ │  cancel + status │
         └──────┬───────────┘ │ shared      │ │  in-mem registry │
                │             │ shapes      │ │  +  DB fallback  │
                │             └─────────────┘ └────────┬─────────┘
                │                                       │
                ▼                                       │
   ┌────────────────────────────┐                      │
   │ Mt5Client.get_ohlc (live)  │                      │
   │ backtest.loader.load_      │                      │
   │ italian_csv (CSV slice)    │                      │
   └────────────────────────────┘                      │
                                                        │
                ┌───────────────────────────────────────┴────────────────┐
                │ ProcessPoolExecutor worker (NO MT5 import)             │
                │   BacktestEngine (Phase 1) + load_italian_csv (CSV)    │
                │   writes to logs/trades.db backtest_runs/_trades       │
                └────────────────────────────────────────────────────────┘

──────────────────────────────────────────────────────────────────────────
TRAIL DAEMON (D-B2) — passive tick model
──────────────────────────────────────────────────────────────────────────

  IntradayLoopScheduler.run_one_cycle  (scheduler.py:530, every 5–15 min)
              │
              ▼
  mcp/trail_daemon.py::trail_tick(mt5, db_path)
              │
              ▼
  SELECT * FROM position_trails WHERE active=1
              │
              ├── for each row:
              │     pos = mt5.positions_get(ticket=row.position_id)
              │     if pos is None  → UPDATE active=0  (position closed)
              │     else:
              │       atr = compute_atr(mt5.get_ohlc(sym, tf, 14))
              │       candidate_sl = price ± atr * row.atr_mult
              │       if favorable vs row.last_sl:
              │         mt5_client.modify_position(pid, sl=candidate_sl)
              │         UPDATE last_sl = candidate_sl
              │
              ▼
  log.info() ; return; scheduler proceeds to _manage_open_positions
```

### Recommended Project Structure

```
mcp/                                      # NEW package (D-E1)
├── __init__.py                           # re-export Server + bootstrap helpers
├── server.py                             # mcp_server.py rinominato; @list_tools + @call_tool
├── schemas.py                            # _PROPOSAL_SCHEMA, _PROPOSE_TRADE_SCHEMA, +nuovi
├── bar_source.py                         # BarSource.get(symbol, tf, n, as_of_ts=None)
├── job_queue.py                          # JobQueue + JobRecord; ProcessPool wrapper
├── trail_daemon.py                       # ensure_table, register_trail, trail_tick, deactivate
├── errors.py                             # ErrorCodes constants (D-F2)
└── handlers/
    ├── __init__.py
    ├── account.py                        # 3 tool legacy
    ├── market.py                         # 8 tool (R1, R2, plus MCP-09/11/12/14 + symbol_universe + symbol_indicators)
    ├── proposal.py                       # 3 tool legacy + R3 refactor
    ├── position.py                       # close_position (esistente) + modify_position (16) + get_position_state (17)
    └── backtest.py                       # run_backtest (01), get_backtest_metrics (02), walk_forward (03), cancel_backtest, replay_decision (15)

mcp_server.py                             # THIN SHIM (preserves `python -m mcp_server`)

config.py                                 # +MCP_MAX_CONCURRENT_RUNS, MCP_DEFAULT_BARS,
                                          #  TRAIL_TICK_TIMEFRAME, TRAIL_FAVORABLE_ONLY
.env.example                              # +new vars

mt5_client.py                             # +modify_position(ticket, sl, tp) wrapper around
                                          #  mt5.order_send(TRADE_ACTION_SLTP, ...)
                                          # +partial_close(ticket, lots) wrapper (TRADE_ACTION_DEAL)
                                          # +get_position(ticket) wrapper around mt5.positions_get
                                          # +get_open_positions_max_favorable_excursion (or compute in handler)

scheduler.py                              # +trail_tick call inside IntradayLoopScheduler.run_one_cycle
                                          #  (single line BEFORE _manage_open_positions)

logger.py                                 # +CREATE TABLE position_trails on init (or in trail_daemon.ensure_table)

models.py                                 # +TrailIntent dataclass (optional; or rely on tuple from SQLite row)

tests/
├── conftest.py                           # extend MetaTrader5 stub with TRADE_ACTION_SLTP, modify_position fns
├── fixtures/
│   ├── mcp/
│   │   ├── sample_position_trails.sql    # seed for trail daemon tests
│   │   ├── sample_baseline_decisions.parquet  # tiny parquet for replay_decision tests
│   │   └── sample_trades_log.json         # seed for replay_decision live-lookup
├── test_mcp_handlers_market.py           # MCP-09/11/12/14 + R1/R2
├── test_mcp_handlers_position.py         # MCP-16/17 (validation, conflicts, dry_run)
├── test_mcp_handlers_backtest.py         # MCP-01/02/03/15 + cancel
├── test_mcp_handlers_proposal.py         # R3 (setup_type, confluence_score)
├── test_mcp_bar_source.py                # D-D1 (live vs as_of_ts, no future leakage strict-<)
├── test_mcp_job_queue.py                 # status, cancel, run_in_progress, restart fallback
├── test_mcp_trail_daemon.py              # ensure_table, register, tick, position_closed, no-favorable
├── test_mcp_smoke_round_trip.py          # success criterion #4: run_backtest → get_backtest_metrics
└── test_mcp_legacy_compat.py             # success criterion #3: existing tool list + signatures unchanged
                                          #  (rename of test_mcp_tools_v2.py? keep it green)
```

### Pattern 1: MCP Tool Registration (existing pattern, extend)

**What:** Each tool = `Tool(name, description, inputSchema=...)` in `list_tools()` + branch in `call_tool()` + handler `handle_<name>(args) -> dict`. Existing pattern (`mcp_server.py:184-313` for `list_tools`, `mcp_server.py:316-433` for `call_tool`).

**When to use:** Always — Phase 6 follows this structure literally.

**Source:** `mcp_server.py:184-313` (list_tools), `tests/test_mcp_tools_v2.py:73-88` (validates each tool has `inputSchema.type=='object'`).

```python
# mcp/handlers/backtest.py — Tool registration shape
from mcp.types import Tool

RUN_BACKTEST_TOOL = Tool(
    name="run_backtest",
    description=(
        "Avvia backtest async sullo storico CSV per (symbol, timeframe, date_range, profile). "
        "Ritorna run_id immediato; pollare get_backtest_metrics(run_id) per status/metrics. "
        "Max 1 run concorrente; nuovo run mentre uno gira → error run_in_progress."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol":     {"type": "string", "enum": ["EURUSD", "GBPUSD", "USDJPY"]},
            "timeframe":  {"type": "string", "enum": ["M15", "M30", "H1"]},
            "date_start": {"type": "string", "description": "ISO8601 UTC, e.g. 2024-01-01T00:00:00Z"},
            "date_end":   {"type": "string", "description": "ISO8601 UTC, esclusivo"},
            "profile":    {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]},
        },
        "required": ["symbol", "timeframe", "date_start", "date_end", "profile"],
    },
)
```

[VERIFIED: signature pattern matches `mcp_server.py:286-292` (`propose_trade` tool registration); inputSchema validation per `tests/test_mcp_tools_v2.py:81-87`]

### Pattern 2: Async Job Queue (D-A1, D-A4)

**What:** `JobQueue` wraps `ProcessPoolExecutor(max_workers=1)`, keeps `dict[run_id, JobRecord]` in memory, persists `backtest_runs.status` to disk so `get_backtest_metrics(run_id)` works after server restart.

**When to use:** `run_backtest` and `walk_forward_validate` only. `cancel_backtest` operates on the queue.

```python
# mcp/job_queue.py
from concurrent.futures import ProcessPoolExecutor, Future
from dataclasses import dataclass
from threading import Lock
from typing import Callable
from datetime import datetime, timezone


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class JobRecord:
    run_id: str
    future: Future
    started_at: str
    status: str  # "running" | "done" | "failed" | "cancelled"


class JobQueue:
    """In-memory + DB-backed registry of running/completed backtests."""

    def __init__(self, max_workers: int, db_path: str):
        self._pool = ProcessPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._max = max_workers
        self._db = db_path

    def submit(self, run_id: str, fn: Callable, *args, **kwargs) -> dict:
        with self._lock:
            active = [j for j in self._jobs.values() if j.status == "running"]
            if len(active) >= self._max:
                return {"ok": False, "error": "run_in_progress",
                        "active_run_id": active[0].run_id}
            fut = self._pool.submit(fn, *args, **kwargs)
            rec = JobRecord(run_id, fut, _utcnow_iso(), "running")
            self._jobs[run_id] = rec
            self._insert_run_row(run_id, status="running")
        fut.add_done_callback(lambda f: self._on_done(run_id, f))
        return {"ok": True, "run_id": run_id, "status": "started",
                "started_at": rec.started_at}

    def status(self, run_id: str) -> dict:
        rec = self._jobs.get(run_id)
        if rec is None:
            row = self._load_run_row(run_id)            # post-restart fallback
            if row is None:
                return {"ok": False, "error": "unknown_run_id", "run_id": run_id}
            return self._row_to_status(row)
        if rec.status == "running":
            return {"run_id": run_id, "status": "running",
                    **self._read_progress_from_db(run_id)}
        return self._row_to_status(self._load_run_row(run_id))

    def cancel(self, run_id: str) -> dict:
        rec = self._jobs.get(run_id)
        if rec is None or rec.status != "running":
            return {"ok": False, "error": "no_active_run", "run_id": run_id}
        cancelled = rec.future.cancel()
        if not cancelled:
            # Future already running: ProcessPool cannot cancel mid-task on Windows.
            # Tear down + recreate (loses other queued futures, but max_workers=1).
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = ProcessPoolExecutor(max_workers=self._max)
        rec.status = "cancelled"
        self._update_run_row(run_id, status="cancelled")
        return {"ok": True, "run_id": run_id, "status": "cancelled"}
```

[VERIFIED: `concurrent.futures.ProcessPoolExecutor` with `cancel_futures=True` is stdlib 3.9+; works on Windows. Mid-execution cancel always returns False from `Future.cancel()` per Python docs.]

**Worker function constraint (CRITICAL):** The function passed to `pool.submit` must be importable at top level (Python pickles it). Must NOT import `mt5_client` directly — MetaTrader5 lib is not fork-safe (Phase 5 D-15 carry-forward). Worker entry point:

```python
# mcp/handlers/backtest.py — top-level for picklability
def _backtest_worker(run_id: str, symbol: str, timeframe: str,
                     date_start: str, date_end: str, profile: str,
                     db_path: str, costs_yaml_path: str) -> None:
    """Worker: pure CSV-driven backtest, no MT5."""
    from backtest.loader import load_italian_csv
    from backtest.engine import BacktestEngine
    from backtest.broker import BacktestBroker
    from backtest.costs import load_cost_model
    # ... build engine, run, write to logs/trades.db (per-process connection)
```

### Pattern 3: BarSource Adapter (D-D1)

**What:** Single entry point for bar retrieval. Live mode → MT5; historical mode → Phase 1 CSV loader sliced strict-< `as_of_ts` (no future leakage).

```python
# mcp/bar_source.py
from bisect import bisect_left
from backtest.loader import load_italian_csv  # Phase 1


class BarSource:
    @staticmethod
    def get(symbol: str, tf: str, n: int,
            as_of_ts: str | None = None,
            mt5_client=None) -> list[dict]:
        if as_of_ts is None:
            if mt5_client is None:
                raise ValueError("mt5_client required for live mode")
            return mt5_client.get_ohlc(symbol, tf, n)
        # Historical mode (Phase 1 D-08 GMT-6 → UTC inside loader)
        bars = load_italian_csv(symbol, tf)
        ts_arr = [b["time"] for b in bars]   # int unix UTC sorted ascending
        # Convert as_of_ts string → int unix
        from datetime import datetime, timezone
        as_of_unix = int(datetime.fromisoformat(
            as_of_ts.replace("Z", "+00:00")
        ).astimezone(timezone.utc).timestamp())
        cutoff = bisect_left(ts_arr, as_of_unix)   # strict < as_of_ts
        if cutoff < n:
            raise ValueError(f"as_of_ts_warmup_insufficient: {as_of_ts}, need {n} bars")
        if cutoff > len(ts_arr):
            raise ValueError(f"as_of_ts_out_of_range: {as_of_ts}")
        return bars[cutoff - n : cutoff]
```

[VERIFIED: `bisect_left` returns the **leftmost insertion index**, so `arr[:cutoff]` contains all elements **strictly less than** `as_of_unix` — this is the no-future-leakage semantic. Test obligatory: bar at exact `as_of_unix` must NOT be included.]

### Pattern 4: Polymorphic `get_backtest_metrics` (D-A3)

**What:** Same tool returns different shapes based on `status`. Schema is permissive (all fields optional except `status` + `run_id`); skill branches on `status`.

```python
# mcp/handlers/backtest.py
def handle_get_backtest_metrics(run_id: str) -> dict:
    status = job_queue.status(run_id)
    if status.get("error") == "unknown_run_id":
        return {"ok": False, "error": "unknown_run_id", "run_id": run_id}
    if status["status"] == "running":
        return {"run_id": run_id, "status": "running",
                "progress_pct":  status.get("progress_pct", 0.0),
                "bars_processed": status.get("bars_processed", 0),
                "bars_total":    status.get("bars_total", 0),
                "trades_so_far": status.get("trades_so_far", 0),
                "started_at":    status["started_at"]}
    if status["status"] == "done":
        metrics = _compute_metrics_for_run(run_id)   # via Phase 1 metrics.compute_metrics
        return {"run_id": run_id, "status": "done",
                "metrics": metrics,
                "equity_curve_path": _equity_path(run_id),
                "finished_at": status["finished_at"]}
    if status["status"] == "failed":
        return {"run_id": run_id, "status": "failed",
                "error":  status.get("error_message"),
                "started_at": status["started_at"],
                "failed_at": status.get("finished_at")}
    if status["status"] == "cancelled":
        return {"run_id": run_id, "status": "cancelled",
                "started_at": status["started_at"],
                "cancelled_at": status.get("finished_at")}
```

**Tool description MUST document the polymorphic schema with examples.** MCP clients without strict schema validation will accept this; clients with strict `oneOf` requirement will need an enhancement (deferred per CONTEXT.md).

### Pattern 5: `modify_position` Atomic Combo (D-B1, D-B3)

**What:** Validate conflicts → validate stops_level → SL/TP via `TRADE_ACTION_SLTP` → partial_close via `TRADE_ACTION_DEAL` opposite-side → register trail intent if `trail_stop_atr_mult`.

**MT5 wrapper (NEW in mt5_client.py):**

```python
# mt5_client.py — addition
@_retry(3)
def modify_position(self, position_id: int,
                    sl: float | None = None,
                    tp: float | None = None) -> OrderResult:
    """Modifica SL/TP di posizione esistente via TRADE_ACTION_SLTP.

    Mirror del pattern close_position (mt5_client.py:191-250):
    - positions_get(ticket) per validare esistenza + recuperare symbol
    - order_send(action=TRADE_ACTION_SLTP, position=ticket, sl=..., tp=...)
    - retcode=TRADE_RETCODE_DONE → success
    """
    positions = mt5.positions_get(ticket=position_id) or []
    if not positions:
        return OrderResult(success=False,
                          error_message=f"position {position_id} non trovata")
    pos = positions[0]
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": pos.symbol,
        "position": int(position_id),
        "sl": float(sl) if sl is not None else pos.sl,
        "tp": float(tp) if tp is not None else pos.tp,
    }
    result = mt5.order_send(request)
    if result is None:
        return OrderResult(success=False,
                          error_message=f"order_send returned None: {mt5.last_error()}")
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info("Modify SL/TP OK ticket=%s sl=%s tp=%s",
                   position_id, sl, tp)
        return OrderResult(success=True, order_id=result.order)
    return OrderResult(success=False,
                      error_message=f"modify rejected retcode={result.retcode} comment={result.comment}")
```

[CITED: Per MQL5 forum (https://www.mql5.com/en/forum/389359, https://www.mql5.com/en/forum/341452), `TRADE_ACTION_SLTP` is the canonical action for stop modification. The minimal request needs `action`, `symbol`, `position`, `sl`, `tp`. **Important:** SL/TP must be `float` (str causes silent rejection — known footgun).]

**`partial_close` wrapper:** The existing `close_position` (mt5_client.py:191-250) closes the entire `pos.volume`. Partial close uses the same `TRADE_ACTION_DEAL` opposite-direction order with `volume = partial_lots` (instead of `pos.volume`). MT5 leaves the residual position open with the same ticket. Add as `partial_close(position_id, lots) -> OrderResult` mirroring `close_position` body but with `volume=lots`.

**Stops-level validation pattern:**

```python
# mcp/handlers/position.py
def _stops_level_pips(symbol_info, pip_size: float) -> float:
    """trade_stops_level (in points) → pips."""
    return symbol_info.trade_stops_level * symbol_info.point / pip_size

def _validate_sl_distance(pos, new_sl: float, stops_level_pips: float, pip_size: float) -> tuple[bool, float]:
    """Returns (ok, suggested_sl)."""
    if pos.type == 0:  # BUY
        min_distance = stops_level_pips * pip_size
        if pos.price_current - new_sl < min_distance:
            suggested = pos.price_current - min_distance
            return False, suggested
    else:  # SELL
        if new_sl - pos.price_current < stops_level_pips * pip_size:
            suggested = pos.price_current + stops_level_pips * pip_size
            return False, suggested
    return True, new_sl
```

[CITED: Per Switch Markets (https://www.switchmarkets.com/learn/trailing-stop-loss-mt4-5) and Profit Smasher (https://www.profitsmasher.com/2025/08/smart-position-sizer-for-metatrader-5.html), `trade_stops_level` is in **points** (not pips), zero means "no minimum"; for 5-digit forex pairs `points * symbol.point = price units`. Common TenTrade values are 5–10 points (≈ 0.5–1.0 pip), but MUST be read at runtime — don't hardcode.] [ASSUMED: TenTrade does not require freeze_level (a separate min distance for modifying); plan should also check `symbol_info.trade_freeze_level` and surface separately if non-zero.]

### Pattern 6: Trail Daemon (D-B2)

**What:** SQLite table `position_trails` stores `{position_id, symbol, direction, timeframe, atr_mult, last_sl, activated_at, last_update_at, active}`. The `trail_tick(mt5_client, db_path)` function is invoked from `IntradayLoopScheduler.run_one_cycle` once per cycle.

```sql
CREATE TABLE IF NOT EXISTS position_trails (
    position_id     INTEGER PRIMARY KEY,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,           -- BUY | SELL
    timeframe       TEXT NOT NULL,           -- TRAIL_TICK_TIMEFRAME
    atr_mult        REAL NOT NULL,
    last_sl         REAL NOT NULL,
    activated_at    TEXT NOT NULL,           -- ISO8601 UTC
    last_update_at  TEXT,                    -- ISO8601 UTC, NULL on register
    active          INTEGER NOT NULL DEFAULT 1
);
```

```python
# mcp/trail_daemon.py
def trail_tick(mt5_client, db_path: str, cfg) -> None:
    """Run by scheduler each cycle.

    Idempotent: closed positions auto-deactivate; broker reject (e.g. stops_level
    violation on candidate) logged but not re-tried (next tick re-evaluates).
    Italiano log per CLAUDE.md.
    """
    with sqlite3.connect(db_path) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM position_trails WHERE active=1").fetchall()
    for row in rows:
        pos = mt5_client.get_position(row["position_id"])  # NEW thin wrapper
        if pos is None:
            _deactivate(db_path, row["position_id"])
            continue
        bars = mt5_client.get_ohlc(row["symbol"], row["timeframe"], 14)
        if not bars or len(bars) < 14:
            continue
        atr_val = compute_atr(bars, period=14)             # indicators.atr (existing)
        candidate = (pos.price_current - atr_val * row["atr_mult"]
                     if row["direction"] == "BUY"
                     else pos.price_current + atr_val * row["atr_mult"])
        favorable = (
            (row["direction"] == "BUY"  and candidate > row["last_sl"]) or
            (row["direction"] == "SELL" and candidate < row["last_sl"])
        )
        if cfg.TRAIL_FAVORABLE_ONLY and not favorable:
            continue
        res = mt5_client.modify_position(row["position_id"], sl=candidate)
        if res.success:
            _update_last_sl(db_path, row["position_id"], candidate)
            log.info("trail tick: pos=%d new_sl=%.5f atr=%.5f mult=%.2f",
                    row["position_id"], candidate, atr_val, row["atr_mult"])
        else:
            log.warning("trail tick fallito: pos=%d err=%s",
                       row["position_id"], res.error_message)
```

**Integration into scheduler (single line, minimum-invasive):**

```python
# scheduler.py:530+ — IntradayLoopScheduler.run_one_cycle
# BEFORE _manage_open_positions, AFTER account_state refresh:

try:
    from mcp.trail_daemon import trail_tick
    trail_tick(self.mt5, str(daily_db_path(cfg)), cfg)
except Exception:
    self.log.exception("trail_tick fallito (non blocca ciclo)")
```

[VERIFIED: scheduler.py:553 `self._manage_open_positions(account_state, now)` is the existing open-positions handler called immediately after `account_state` retrieval. Trail tick goes one line before. The try/except wrap is consistent with project pattern (scheduler.py:545-551 already wraps `get_account_state` in try/except).]

### Pattern 7: `replay_decision` Orchestrator (D-D2)

```python
# mcp/handlers/backtest.py
def handle_replay_decision(decision_id: str, full_diff: bool = False) -> dict:
    # 1. Union lookup
    row = _lookup_trades_log(decision_id) or _lookup_baseline_parquet(decision_id)
    if row is None:
        return {"ok": False, "error": "decision_not_found", "decision_id": decision_id}

    # 2. Reconstruct context as-of decision time
    bars = BarSource.get(row["symbol"], row["timeframe"],
                         row["warmup_bars"], as_of_ts=row["bar_ts_utc"])
    indicators = compute_all_extended(bars)        # Phase 2
    ctx = build_ctx_backtest(bars, row["regime"],  # Phase 4 D-05
                             row["profile"])

    # 3. Re-evaluate with CURRENT code
    replayed = evaluate_proposal_for_bar(bars, indicators, ctx)

    # 4. Compute diff
    diff = _diff_proposals(row["original_proposal"], replayed,
                          full=full_diff)
    return {
        "ok": True, "decision_id": decision_id,
        "original":  row["original_proposal"],
        "replayed":  replayed.to_dict() if replayed else None,
        "diff":      diff,
        "regression": diff["any_difference"],
    }


def _lookup_trades_log(decision_id: str) -> dict | None:
    """Live decisions in trades_log (existing schema, mcp_server.py:382)."""
    if not decision_id.startswith("live_") and not decision_id.isdigit():
        return None
    raw_id = decision_id.removeprefix("live_") if decision_id.startswith("live_") else decision_id
    with sqlite3.connect(daily_db_path(cfg)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM trades_log WHERE id = ?", (int(raw_id),))
        return dict(cur.fetchone() or {}) or None


def _lookup_baseline_parquet(decision_id: str) -> dict | None:
    """Baseline decisions in data/training/baseline_decisions.parquet (Phase 5 D-02)."""
    import pyarrow.parquet as pq
    path = "data/training/baseline_decisions.parquet"
    if not Path(path).exists():
        return None
    # Filter by composite key: prefix `baseline_` decoded into run_id + idx
    if not decision_id.startswith("baseline_"):
        return None
    table = pq.read_table(path,
        filters=[("decision_id", "=", decision_id)])  # via parquet column or composite
    if table.num_rows == 0:
        return None
    return table.to_pylist()[0]
```

**[ASSUMED: Phase 5 baseline_decisions.parquet schema includes a `decision_id` column or composite `(run_id, decision_ts_utc, idx)` that allows lookup. Verify against Phase 5 actual schema before Wave 0 implementation. If not present, Phase 6 either adds derivation logic (`run_id + bar_ts_utc → unique key`) or Phase 5 must be amended (out-of-scope for Phase 6 — escalate to user).]**

### Anti-Patterns to Avoid

- **Importing `mt5_client` (or any module that imports MetaTrader5) in the `ProcessPoolExecutor` worker function.** Phase 5 D-15 carry-forward: MT5 lib is not fork-safe; spawned worker process will crash with hangs / SIGSEGV depending on OS. Worker uses CSV + `BacktestBroker` only.
- **Mutating SL/TP via two consecutive `order_send` calls without re-reading `pos`.** Between calls, broker may have moved SL via stop-out logic; reading once and applying twice introduces stale-state writes. Always re-fetch via `mt5.positions_get(ticket=...)` at start of `modify_position`, then apply atomically.
- **Trail daemon registering a trail without setting `last_sl` to current position SL.** First tick would compute a candidate vs `last_sl=0.0` → "favorable" → instant modify. Initialization MUST set `last_sl = pos.sl` (or `pos.price_open` if no SL). Test required.
- **Polling `get_backtest_metrics` more than once per second from skill flow.** SQLite WAL handles concurrent readers but each call hits disk. Tool description SHOULD recommend ≥ 5 s interval.
- **Returning raw MT5 retcode integers in error envelope.** D-F2 mandates standardized `error: <string_code>`. Wrap retcode in `broker_rejected` with retcode in `context.broker_retcode`.
- **`oneOf` JSON-Schema for polymorphic responses without testing all MCP clients.** Some clients (older claude-desktop) don't implement strict response validation — `oneOf` is harmless; some implement it and reject permissive shapes. Use permissive `status` discriminator. (Locked in CONTEXT deferred ideas.)
- **Forgetting `cfg.DRY_RUN` branch in `modify_position`.** Existing `close_position` (mcp_server.py:411-421) has the pattern; `modify_position` MUST mirror it for shadow-mode safety per CLAUDE.md.
- **Using `mcp_server.py:430` raw exception envelope shape `{error: ..., tool: name}`.** D-F2 formalizes new shape `{ok: false, error: <code>, message: <human>, ...context}`. Wrap the catch-all to convert legacy → new shape.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async job queue / progress tracking | Custom thread + futures + signals | `concurrent.futures.ProcessPoolExecutor` + DB-backed status | Stdlib, battle-tested. Cancel semantics on Windows are well-documented. |
| MCP tool registration boilerplate | Custom RPC handler | `mcp.server.Server` + `@server.list_tools()` + `@server.call_tool()` | SDK already used (mcp_server.py); skill consumers expect MCP protocol. |
| JSON-Schema validation | Custom validators | `mcp.server.Server.call_tool(*, validate_input=True)` (default) | [VERIFIED: mcp/server/lowlevel/server.py:492] SDK validates inputSchema automatically; never bypass. |
| Backtest engine | Reuse Phase 1 `BacktestEngine` | Phase 1 surface | One code path live + backtest (Phase 4 D-13 carry). |
| Walk-forward slicing | Custom rolling windows | `backtest.walk_forward.walk_forward_slices` (Phase 1 D-06) | Already pure-function with fold cap, no overlap, exclusive ranges. |
| Metrics computation | Custom Sharpe/MaxDD | `backtest.metrics.compute_metrics` (Phase 1) | Annualization factors verified for H1/M30/M15. |
| Italian-CSV loading | Custom CSV parser | `backtest.loader.load_italian_csv` (Phase 1 D-08) | GMT-6 → UTC verified against 3 NFP dates. |
| `compute_all_extended` indicators | Recompute each indicator manually | Phase 2 `compute_all_extended(bars)` | Cached, dataclass-of-lists, no future leakage. |
| Pattern detection | Custom candlestick scanners | Phase 3 `scan_patterns` + `PatternHit` | Already calibrated 0–1 confidence per pattern type. |
| Setup detection + 5-factor scoring | Custom rules | Phase 4 `evaluate_proposal_for_bar` | Single code path, drives `setup_type` + `confluence_score` for MCP-R3. |
| `ProposalDraft` → `TradeProposal` adapter | Custom dict mapping | Phase 4 `draft_to_trade_proposal` | Existing utility. |
| MT5 stop-modification request body | Custom dict assembly | `mt5.order_send({"action": TRADE_ACTION_SLTP, ...})` mirroring `close_position` | Existing wrapper pattern (mt5_client.py:191-250); existing retry decorator. |
| ATR computation for trail | Custom rolling stdev | `indicators.atr` (already in `indicators.py`) | Existing primitive used elsewhere. |
| Parquet read for replay | Custom binary parser | `pyarrow.parquet.read_table(filters=...)` | Phase 5 baseline writes; pyarrow already in dep tree. |
| SQLite WAL + per-process connection | Custom locking | Phase 5 D-16 pattern + `with sqlite3.connect(...) as conn` | Already enabled across phases. |
| Hash for run audit trail | Custom hashing | Phase 1 D-07 `cost_yaml_hash` (`hashlib.md5(...).hexdigest()[:16]`) | Already in `backtest_runs` schema. |
| RotatingFileHandler logger | Custom log spinner | `init_logger(cfg)` (logger.py) | Stderr-safe for MCP protocol (D-F3). |

**Key insight:** Phase 6 is mostly MCP-tool-facade work over Phase 1–5 surfaces. The only NEW logic is the trail daemon math (`candidate = price ± atr × mult`, favorable check, idempotent activation). Anything else is glue: schemas, dispatch, error envelopes, JobQueue lifecycle.

---

## Runtime State Inventory

> Phase 6 is a feature-addition phase, not a rename/refactor — but it adds runtime state (new SQLite table + new in-memory job registry) and MUST integrate cleanly with restart semantics.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (NEW) | `position_trails` table in `logs/trades.db` (D-B2). Survives restart; agent reload reads `active=1` rows. | Create table on `mcp/trail_daemon.py` import via `CREATE TABLE IF NOT EXISTS`. Add to `logger.py` schema bootstrap if Phase 5 hasn't already. |
| Stored data (NEW) | `backtest_runs.status` column for MCP runs uses Phase 1 schema; prefix `mcp_<utc_ts>_<symbol>_<tf>_<profile>`. | Verify Phase 1 `backtest_runs` already has a `status` column (or `started_at`/`finished_at` from Phase 1 D-07 line 681 of 01-RESEARCH.md). If not, add. |
| Stored data (read-only) | `data/training/baseline_decisions.parquet` (Phase 5 D-02) — replay_decision lookup. | None — Phase 5 owns; verify schema column `decision_id` or composite key exists before Wave 0. |
| Stored data (read-only) | `logs/trades.db trades_log` (existing) — replay_decision live-lookup. | None — schema already in mcp_server.py:382 query. |
| Live service config | None. MCP stdio server is process-lifetime; no UI configuration to drift from git. | None. |
| OS-registered state | None. APScheduler `BlockingScheduler` lives in-process (Phase 13). Phase 16 `IntradayLoopScheduler` is pure-python loop. No Windows Task Scheduler entries, no pm2, no systemd. | None — verified by reading scheduler.py:293-313 (build_scheduler) and scheduler.py:460-528 (IntradayLoopScheduler). |
| Secrets/env vars (NEW) | `MCP_MAX_CONCURRENT_RUNS=1`, `MCP_DEFAULT_BARS=200`, `TRAIL_TICK_TIMEFRAME=M15`, `TRAIL_FAVORABLE_ONLY=true`. | Add to `config.py::Config` + `.env.example`. No secret values; .env update non-sensitive. |
| Build artifacts | None. Pure Python, no compiled wheels for new code. | Verify `python -m mcp_server` still works after package split (D-E1 shim). |
| In-memory state (NEW) | `JobQueue._jobs: dict[run_id, JobRecord]` survives only within process. | Document: on restart, `get_backtest_metrics(run_id)` falls back to `backtest_runs` table; "running" status persists in DB but no actual job is alive. Plan needs a `_reconcile_on_startup()` helper that scans `backtest_runs` for `status='running'` and either marks them `failed` (worker died) or restarts (TBD; default = mark failed, document as known limitation). |

**The canonical question — after this phase ships, what runtime state exists that didn't before?**
- 1 new SQLite table (`position_trails`)
- 1 new in-memory queue (`JobQueue._jobs` per process)
- 1 new scheduler hook (`trail_tick` in `IntradayLoopScheduler.run_one_cycle`)
- 4 new env vars
- 0 new external services

---

## Common Pitfalls

### Pitfall 1: ProcessPool worker imports MetaTrader5 transitively

**What goes wrong:** Worker function imports `backtest.engine` which (transitively) imports `mt5_client` for type hints, even if not used. Worker process tries to load MT5 lib → segfault on Windows or hang on Linux.

**Why it happens:** Python import side effects are eager; any `from mt5_client import Mt5Client` at module top level is executed in the worker.

**How to avoid:** Worker entry point is a top-level function in `mcp/handlers/backtest.py` whose body uses `from backtest.X import Y` LOCALLY. Audit: grep `mt5_client` in `backtest/`, `strategy/`, `indicators/` modules — all imports must be either (a) inside functions, or (b) under `if TYPE_CHECKING:` guard. Phase 4 already follows TYPE_CHECKING pattern (CONTEXT.md line 38).

**Warning signs:** Worker process exits with code 1 immediately, no Python traceback. CPU never spikes.

**Test:** A unit test that `multiprocessing.spawn`s the worker with a tiny CSV slice and asserts a `backtest_runs` row appears within 30 s.

### Pitfall 2: Trail daemon stops_level violation creates infinite reject loop

**What goes wrong:** Position is profitable; ATR-based candidate would move SL closer than `trade_stops_level` to current price. Broker rejects. Daemon logs warning, continues. Next tick: same calculation, same rejection. Log spam.

**Why it happens:** `trail_tick` doesn't pre-validate stops_level; relies on broker reject.

**How to avoid:** In `trail_tick`, validate candidate against `stops_level_pips` BEFORE calling `modify_position`. If too tight, **clamp candidate to stops_level boundary** (NOT update last_sl unless successful). Document: trailing math is "best within broker constraint" — minor deviation from pure ATR-mult logic.

**Warning signs:** Log file grows with `trail tick fallito: stops_level_violation` repeats.

### Pitfall 3: `as_of_ts` boundary off-by-one (future leakage)

**What goes wrong:** `BarSource.get(..., as_of_ts="2024-03-01T08:00:00Z")` returns bars including the bar at exactly 08:00 UTC. But that bar's CLOSE is at 08:15 (M15) — using its data at 08:00 is future leakage.

**Why it happens:** `bisect_left` with `<=` semantics OR off-by-one in cutoff index.

**How to avoid:** `bisect_left(arr, target)` returns leftmost index where target could be inserted to keep sorted, i.e. arr[:cutoff] < target. Use `cutoff = bisect_left(ts_arr, as_of_unix)`, then `bars[cutoff - n : cutoff]`. **Test obligatorio:** insert a bar at exact `as_of_unix`, assert it is NOT in returned slice.

**Warning signs:** Replay_decision returns identical proposals for very similar `as_of_ts` values straddling a bar boundary.

### Pitfall 4: Concurrent SQLite writes during MCP run + scheduler trail tick

**What goes wrong:** MCP `run_backtest` worker writes to `backtest_trades`; concurrently `IntradayLoopScheduler.trail_tick()` updates `position_trails`; concurrently `MCP server` reads `backtest_runs.status`. Without WAL, second writer gets `database is locked`.

**Why it happens:** SQLite default journal mode is rollback (one writer at a time).

**How to avoid:** WAL mode is enabled in Phase 5 D-16 (`PRAGMA journal_mode=WAL`). Verify it's enabled in MCP server bootstrap (`mcp/server.py::_bootstrap`) and per worker on first connect:

```python
with sqlite3.connect(db_path) as conn:
    conn.execute("PRAGMA journal_mode=WAL")
```

Phase 5 already does this in baseline runner. Phase 6 must do it in: (a) `mcp/server.py` startup, (b) `mcp/handlers/backtest.py::_backtest_worker` first connect, (c) `mcp/trail_daemon.py::ensure_table`.

**Warning signs:** Sporadic `OperationalError: database is locked` in logs.

### Pitfall 5: `forex-trader-pro` skill receives 200 bars instead of expected 50

**What goes wrong:** Skill flow assumes `len(snapshot["ohlc"]) == 50`. After D-C1 default change, snapshot returns 200 bars by default — possibly LLM context-window or skill assertion fails.

**Why it happens:** D-C1 default-bars change is a behavioral break, even though signature is "additive."

**How to avoid:** **Success criterion #3** — verify `forex-trader-pro` skill flows pass post-refactor. Practical mitigation: skill's MCP call passes `bars=50` explicitly, OR document the new default in skill's reference. Phase 6 plan task: read `.claude/skills/forex-trader-pro/SKILL.md` + reference docs, audit any `len(ohlc)` or `bars[-50]` usage; update skill if needed. **Skill update is part of Phase 6 scope** for backward compat (success criterion #3).

**Warning signs:** Manual skill flow fails post-merge with assertion errors or context-window overflow.

### Pitfall 6: `cancel_backtest` on Windows leaves zombie process

**What goes wrong:** `pool.shutdown(wait=False, cancel_futures=True)` returns immediately on Windows. Worker process may still be holding write lock on `logs/trades.db`. Re-creating `ProcessPoolExecutor` succeeds; but next `run_backtest` worker spawns alongside zombie → 2 processes briefly write to same DB.

**Why it happens:** Windows `subprocess` termination is asynchronous; OS may take a few seconds to fully clean up.

**How to avoid:** After cancel, sleep 1 s before marking ready for new runs. Better: `JobQueue.cancel` returns immediately with status="cancelled"; subsequent `submit` checks both in-mem registry AND DB for "running" rows. If DB shows running but in-mem shows cancelled, treat as ghost → reject new run with `cleanup_in_progress` error.

**Warning signs:** `database is locked` errors right after a cancel.

### Pitfall 7: Replay_decision uses CURRENT strategy code on OLD decision

**What goes wrong:** A baseline decision from 6 months ago was made by old strategy logic. Replay re-evaluates with current code. If they differ, tool reports `regression=true` — but this is INTENDED behavior (skill is detecting strategy drift), not a bug.

**Why it happens:** D-D2 explicitly: replay uses current code. This is a feature, not a pitfall — but easy to misinterpret in tool description.

**How to avoid:** Tool description MUST clearly state: "Replays the decision against CURRENT strategy code. `regression=true` means strategy has changed since the decision was originally made — could be intentional (improvement) or unintentional (drift)."

**Warning signs:** User confused by `regression` semantic.

### Pitfall 8: MCP stdio protocol broken by stdout write

**What goes wrong:** Any `print()`, `traceback.print_exc()` to stdout breaks JSON-RPC framing → MCP client disconnects with "invalid JSON" error.

**Why it happens:** stdlib `multiprocessing.Process` workers spawned by ProcessPoolExecutor inherit parent's stdin/stdout in some configurations. If worker accidentally writes to stdout (e.g. via tqdm), parent's MCP protocol corrupted.

**How to avoid:** Use `multiprocessing` start method `'spawn'` (default on Windows); workers do NOT share stdio. Verify worker has only `init_logger` → stderr. **Audit:** `tqdm` is in dep tree (Phase 5 D-20 imports for progress bars in baseline runner). If a `tqdm()` call leaks into the worker, stdout corruption. Worker must NOT use `tqdm` for progress — use DB row updates instead, queried via `get_backtest_metrics`.

**Warning signs:** MCP client disconnects partway through a long-running tool call.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (unpinned in `requirements.txt:9`) |
| Config file | `pytest.ini` (`pythonpath = .`) — existing |
| Quick run command | `pytest tests/test_mcp_*.py -x --tb=short` |
| Full suite command | `pytest -x --tb=short` |
| MT5 stub | `tests/conftest.py:14-40` — extend with `TRADE_ACTION_SLTP`, `positions_get(ticket=...)` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| MCP-01 | `run_backtest` returns `{run_id, status:"started", started_at}` immediately | unit | `pytest tests/test_mcp_handlers_backtest.py::test_run_backtest_returns_run_id -x` | Wave 0 |
| MCP-01 | Concurrent `run_backtest` while one running → `run_in_progress` | unit | `pytest tests/test_mcp_handlers_backtest.py::test_run_backtest_concurrency_cap -x` | Wave 0 |
| MCP-01 | Worker writes to `backtest_runs` + `backtest_trades` (smoke 5-bar fixture) | integration | `pytest tests/test_mcp_smoke_round_trip.py::test_run_backtest_writes_db -x` | Wave 0 |
| MCP-02 | `get_backtest_metrics` polymorphic: running, done, failed, cancelled | unit | `pytest tests/test_mcp_handlers_backtest.py::test_get_metrics_polymorphic -x` | Wave 0 |
| MCP-02 | `get_backtest_metrics(unknown_id)` returns `unknown_run_id` error | unit | `pytest tests/test_mcp_handlers_backtest.py::test_get_metrics_unknown -x` | Wave 0 |
| MCP-02 (SC#4) | End-to-end: `run_backtest` → poll `get_backtest_metrics` → metrics match in-process call | integration | `pytest tests/test_mcp_smoke_round_trip.py::test_round_trip_metrics -x` | Wave 0 |
| MCP-03 | `walk_forward_validate(symbol, tf, n_folds=3)` returns N-fold report after job completes | integration | `pytest tests/test_mcp_handlers_backtest.py::test_walk_forward_3fold -x` | Wave 0 |
| MCP-03 | `walk_forward_validate(n_folds=11)` rejected (Phase 1 cap=10) | unit | `pytest tests/test_mcp_handlers_backtest.py::test_walk_forward_fold_cap -x` | Wave 0 |
| MCP-09 | `get_correlation_matrix(["EURUSD","GBPUSD"], 100)` returns `[[1.0, ρ], [ρ, 1.0]]` | unit | `pytest tests/test_mcp_handlers_market.py::test_correlation_matrix_2symbols -x` | Wave 0 |
| MCP-09 | Correlation default lookback = 100 bar | unit | `pytest tests/test_mcp_handlers_market.py::test_correlation_default_lookback -x` | Wave 0 |
| MCP-11 | `get_session_state()` at 09:00 UTC returns `{london: true, ny: false, ...}` | unit | `pytest tests/test_mcp_handlers_market.py::test_session_state_london_open -x` | Wave 0 |
| MCP-11 | Sessions transition correctly across DST boundary | unit | `pytest tests/test_mcp_handlers_market.py::test_session_state_dst -x` | Wave 0 |
| MCP-12 | `get_multi_tf_snapshot("EURUSD")` returns H4 + H1 + M15 indicators | unit | `pytest tests/test_mcp_handlers_market.py::test_multi_tf_snapshot -x` | Wave 0 |
| MCP-14 | `get_pattern_catalog("EURUSD", "M15", bars=50)` returns `[PatternHit, ...]` | unit | `pytest tests/test_mcp_handlers_market.py::test_pattern_catalog_50bars -x` | Wave 0 |
| MCP-15 | `replay_decision(live_id)` finds row in trades_log + replays | integration | `pytest tests/test_mcp_handlers_backtest.py::test_replay_decision_live -x` | Wave 0 |
| MCP-15 | `replay_decision(baseline_id)` finds row in baseline_decisions.parquet + replays | integration | `pytest tests/test_mcp_handlers_backtest.py::test_replay_decision_baseline -x` | Wave 0 |
| MCP-15 | Replay diff detects strategy regression | integration | `pytest tests/test_mcp_handlers_backtest.py::test_replay_decision_regression_flag -x` | Wave 0 |
| MCP-16 | `modify_position(123, new_sl=X)` calls `Mt5Client.modify_position` | unit | `pytest tests/test_mcp_handlers_position.py::test_modify_sl_only -x` | Wave 0 |
| MCP-16 | `move_sl_to_breakeven=True` → SL = entry_price (BUY: price_open) | unit | `pytest tests/test_mcp_handlers_position.py::test_move_sl_to_breakeven -x` | Wave 0 |
| MCP-16 | Conflict `trail + new_sl` → `conflict: trail_and_manual_sl` | unit | `pytest tests/test_mcp_handlers_position.py::test_conflict_trail_and_manual -x` | Wave 0 |
| MCP-16 | `partial_close_lots >= pos.volume` → `partial_exceeds_volume` | unit | `pytest tests/test_mcp_handlers_position.py::test_partial_exceeds_volume -x` | Wave 0 |
| MCP-16 (SC#2) | `stops_level_violation` returns `{suggested_sl}` | unit | `pytest tests/test_mcp_handlers_position.py::test_stops_level_violation_suggests -x` | Wave 0 |
| MCP-16 | `trail_stop_atr_mult=2.0` registers row in `position_trails` table | unit | `pytest tests/test_mcp_trail_daemon.py::test_register_trail_inserts_row -x` | Wave 0 |
| MCP-16 (SC#2) | Real broker `modify_position` accepts SL within stops_level | integration | `pytest tests/test_mcp_integration_modify.py::test_real_broker_modify -m integration` | Wave 0, MANUAL |
| MCP-16 | `cfg.DRY_RUN` skips broker call, returns `{success: true, dry_run: true}` | unit | `pytest tests/test_mcp_handlers_position.py::test_modify_dry_run -x` | Wave 0 |
| MCP-17 | `get_position_state(123)` returns `{pnl_pips, pnl_money, distance_to_sl_pips, distance_to_tp_pips, holding_minutes, mfe_pips}` | unit | `pytest tests/test_mcp_handlers_position.py::test_position_state_full_payload -x` | Wave 0 |
| MCP-R1 | `get_market_snapshot("EURUSD")` returns 200 bars by default | unit | `pytest tests/test_mcp_handlers_market.py::test_snapshot_default_200_bars -x` | Wave 0 |
| MCP-R1 | `get_market_snapshot("EURUSD", bars=50)` returns 50 bars | unit | `pytest tests/test_mcp_handlers_market.py::test_snapshot_explicit_50_bars -x` | Wave 0 |
| MCP-R1 | Response includes both `indicators` (legacy 4) AND `indicators_extended` (Phase 2 D-09) | unit | `pytest tests/test_mcp_handlers_market.py::test_snapshot_legacy_and_extended -x` | Wave 0 |
| MCP-R1 | `as_of_ts` parameter slices CSV correctly (no future leakage) | unit | `pytest tests/test_mcp_bar_source.py::test_as_of_strict_lt_no_future_leak -x` | Wave 0 |
| MCP-R2 | `scan_symbol_candidates` includes `regime` field in each candidate | unit | `pytest tests/test_mcp_handlers_market.py::test_scan_includes_regime -x` | Wave 0 |
| MCP-R2 | `correlation_warnings` populated when `rolling_corr` > 0.8 | unit | `pytest tests/test_mcp_handlers_market.py::test_scan_correlation_warnings -x` | Wave 0 |
| MCP-R3 | `propose_trade` response includes `setup_type` and `confluence_score` | unit | `pytest tests/test_mcp_handlers_proposal.py::test_propose_includes_setup_type -x` | Wave 0 |
| MCP-R3 | freeform manual proposal → `setup_type: null, confluence_score: null` | unit | `pytest tests/test_mcp_handlers_proposal.py::test_propose_freeform_null_setup -x` | Wave 0 |
| Derived | `cancel_backtest(unknown_id)` → `no_active_run` | unit | `pytest tests/test_mcp_handlers_backtest.py::test_cancel_unknown -x` | Wave 0 |
| Derived | `cancel_backtest(active_id)` marks DB status = "cancelled" | unit | `pytest tests/test_mcp_handlers_backtest.py::test_cancel_active -x` | Wave 0 |
| (D-B2) | Trail daemon `trail_tick`: position closed → mark active=0 | unit | `pytest tests/test_mcp_trail_daemon.py::test_tick_position_closed_deactivates -x` | Wave 0 |
| (D-B2) | Trail daemon: favorable candidate → modify SL + update last_sl | unit | `pytest tests/test_mcp_trail_daemon.py::test_tick_favorable_modifies -x` | Wave 0 |
| (D-B2) | Trail daemon: non-favorable → skip | unit | `pytest tests/test_mcp_trail_daemon.py::test_tick_non_favorable_skip -x` | Wave 0 |
| (D-B2) | Trail daemon: stops_level violation → clamp to boundary | unit | `pytest tests/test_mcp_trail_daemon.py::test_tick_stops_level_clamp -x` | Wave 0 |
| (D-E1) | `python -m mcp_server` still works post-split (smoke) | smoke | `pytest tests/test_mcp_legacy_compat.py::test_legacy_entrypoint_imports -x` | Wave 0 |
| (D-E1) | `tools/list` returns 25 tools (11 existing + 13 + 1 derived) | unit | `pytest tests/test_mcp_legacy_compat.py::test_list_tools_count -x` | Wave 0 |
| SC#3 | All existing 11 legacy tools still pass `tests/test_mcp_tools_v2.py` (unchanged) | regression | `pytest tests/test_mcp_tools_v2.py -x` | EXISTING — must remain green |

### Sampling Rate

- **Per task commit:** `pytest tests/test_mcp_*.py -x --tb=short` (≈ 30 s once tests authored)
- **Per wave merge:** `pytest -x --tb=short` (full suite — ~3 min including phase 1–5 tests)
- **Phase gate:** Full suite green + `tests/test_mcp_tools_v2.py` (legacy) green + manual `@pytest.mark.integration` modify_position run on demo MT5 before merge
- **Skill regression (manual, success criterion #3):** Run `forex-trader-pro` skill flow against MCP server, verify no errors

### Wave 0 Gaps (files to create before implementation)

- [ ] `mcp/__init__.py` — re-export server
- [ ] `mcp/server.py` — moved from `mcp_server.py`; reduced to bootstrap + dispatch
- [ ] `mcp/schemas.py` — moved `_PROPOSAL_SCHEMA`, `_PROPOSE_TRADE_SCHEMA` + new schemas
- [ ] `mcp/bar_source.py` — `BarSource.get`
- [ ] `mcp/job_queue.py` — `JobQueue` + `JobRecord`
- [ ] `mcp/trail_daemon.py` — `ensure_table`, `register_trail`, `trail_tick`, `_deactivate`, `_update_last_sl`
- [ ] `mcp/errors.py` — `ErrorCodes` constants per D-F2
- [ ] `mcp/handlers/__init__.py`
- [ ] `mcp/handlers/account.py` — moved from `mcp_server.py`
- [ ] `mcp/handlers/market.py` — extends with R1/R2 + 4 new market tools
- [ ] `mcp/handlers/proposal.py` — extends with R3
- [ ] `mcp/handlers/position.py` — `modify_position`, `get_position_state` + existing `close_position`
- [ ] `mcp/handlers/backtest.py` — `run_backtest`, `get_backtest_metrics`, `walk_forward_validate`, `cancel_backtest`, `replay_decision`, `_backtest_worker`
- [ ] `mcp_server.py` thin shim (replaces existing 450 LOC file)
- [ ] `tests/test_mcp_handlers_market.py`
- [ ] `tests/test_mcp_handlers_position.py`
- [ ] `tests/test_mcp_handlers_backtest.py`
- [ ] `tests/test_mcp_handlers_proposal.py`
- [ ] `tests/test_mcp_bar_source.py`
- [ ] `tests/test_mcp_job_queue.py`
- [ ] `tests/test_mcp_trail_daemon.py`
- [ ] `tests/test_mcp_smoke_round_trip.py` (success criterion #4)
- [ ] `tests/test_mcp_legacy_compat.py` (D-E1 verifies shim)
- [ ] `tests/test_mcp_integration_modify.py` (`@pytest.mark.integration`, demo MT5)
- [ ] `tests/conftest.py` — extend MetaTrader5 stub with `TRADE_ACTION_SLTP`, `positions_get(ticket=...)`, `POSITION_TYPE_BUY/SELL`
- [ ] `tests/fixtures/mcp/sample_position_trails.sql`
- [ ] `tests/fixtures/mcp/sample_trades_log.json`
- [ ] `tests/fixtures/mcp/sample_baseline_decisions.parquet` (small parquet — 5 rows for replay test)
- [ ] `mt5_client.py` — add `modify_position`, `partial_close`, `get_position` wrappers (3 new methods)
- [ ] `scheduler.py` — add `trail_tick` invocation in `IntradayLoopScheduler.run_one_cycle` (1 line + try/except)
- [ ] `config.py` — add 4 new env vars
- [ ] `.env.example` — append 4 new env vars block

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All | ✓ | 3.12 (Anaconda) | — |
| `mcp` SDK | server, handlers | ✓ | 1.27.0 | — |
| `MetaTrader5` | live tools (`get_account_state`, `modify_position`, `get_ohlc`) | ✓ | 5.0.5735 | Tests use stub (conftest.py) |
| `pyarrow` | `replay_decision` parquet read | ? | (Phase 5 dep) | If absent, parquet lookup raises clear error; live trades_log lookup still works |
| `concurrent.futures.ProcessPoolExecutor` | `JobQueue` | ✓ | stdlib | — |
| `apscheduler` | Existing (Phase 13 path) — NOT extended | ✓ | unpinned | — |
| `IntradayLoopScheduler` (Phase 16, scheduler.py:460) | trail_tick hook | ✓ | in-codebase | — |
| `sqlite3` + WAL mode | `position_trails`, `backtest_runs` | ✓ | stdlib + Phase 5 D-16 | — |
| TenTrade demo broker | `modify_position` integration test | ✓ (per CLAUDE.md) | — | Skip integration test if `MT5_LOGIN` env unset |
| Phase 1 `backtest/` package | All `run_backtest` work | ? (Phase 1 status) | per `.planning/STATE.md` | If Phase 1 not shipped, `run_backtest` not implementable — escalate |
| Phase 2 `indicators/` + `compute_all_extended` | MCP-R1, MCP-12, MCP-14, replay_decision | ? (Phase 2 status) | per CONTEXT.md | If Phase 2 not shipped, `indicators_extended` field absent — escalate |
| Phase 3 `patterns/` + `scan_patterns` + `PatternHit` | MCP-14 | ? (Phase 3 status) | per CONTEXT.md | If Phase 3 not shipped, `get_pattern_catalog` not implementable — escalate |
| Phase 4 `strategy/` + `evaluate_proposal_for_bar` + `ProposalDraft` | MCP-R3, replay_decision | ? (Phase 4 status) | per CONTEXT.md | If Phase 4 not shipped, no `setup_type` / `confluence_score` derivation — escalate |
| Phase 5 `data/training/baseline_decisions.parquet` | replay_decision baseline lookup | ? (Phase 5 status) | per CONTEXT.md | If Phase 5 not shipped, replay_decision falls back to live-only lookup |

**Missing dependencies with no fallback:**
- None blocking. All Phase 6 work can proceed assuming Phases 1–5 are shipped per ROADMAP order. If `STATE.md` indicates Phase 1–5 are NOT yet complete at execution time, **planner MUST escalate** before producing PLAN files.

**Missing dependencies with fallback:**
- `pyarrow` — if Phase 5 hasn't pinned it, replay_decision degrades to live-trades-only. Add to `requirements.txt` if absent (low risk: pyarrow already installed transitively via pandas in many environments).

**Verification command (run during Wave 0):**
```bash
python -c "import pyarrow; print(pyarrow.__version__)"
python -c "from backtest.engine import BacktestEngine; print('phase1 ok')"
python -c "from indicators import compute_all_extended; print('phase2 ok')"
python -c "from patterns import scan_patterns; print('phase3 ok')"
python -c "from strategy import evaluate_proposal_for_bar, ProposalDraft; print('phase4 ok')"
python -c "import os; print('phase5 baseline parquet:', os.path.exists('data/training/baseline_decisions.parquet'))"
```

---

## Code Examples

### Schema for MCP-R1 (additive `indicators_extended` + `bars` arg)

```python
# mcp/handlers/market.py
from mcp.types import Tool

GET_MARKET_SNAPSHOT_TOOL = Tool(
    name="get_market_snapshot",
    description=(
        "Snapshot mercato per il symbol indicato. Per default 200 barre OHLC sul TF configurato + "
        "ultimo tick + indicatori legacy (sma_20/ema_50/rsi_14/atr_14) in `indicators` + "
        "ExtendedIndicators completo (Phase 2: BB, ADX, MACD, Stoch, Donchian, Keltner, VWAP, Fib, "
        "Pivot, NR4/7, Closing Score, Hurst, MTF align, regime) in `indicators_extended`. "
        "Override bar count con `bars` (50-500). Per replay point-in-time passare "
        "`as_of_ts` ISO8601 UTC; default = live MT5."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol":    {"type": "string"},
            "bars":      {"type": "integer", "minimum": 50, "maximum": 500,
                          "default": 200,
                          "description": "Bar count (default 200; legacy 50 = pass bars=50 esplicitamente)"},
            "timeframe": {"type": "string",
                          "description": "Override cfg.TIMEFRAME (default M15)"},
            "as_of_ts":  {"type": "string",
                          "description": "ISO8601 UTC; null/missing = live"},
        },
        "required": ["symbol"],
    },
)


def handle_get_market_snapshot(args: dict, mt5_client, cfg) -> dict:
    symbol = args["symbol"]
    bars_n = int(args.get("bars", cfg.MCP_DEFAULT_BARS))
    tf = args.get("timeframe", cfg.TIMEFRAME)
    as_of = args.get("as_of_ts")

    ohlc = BarSource.get(symbol, tf, bars_n, as_of_ts=as_of, mt5_client=mt5_client)

    # Tick: only if live (CSV has no live tick)
    sym_info = mt5_client.get_symbol_info(symbol) if as_of is None else None
    tick = {}
    if sym_info is not None:
        tick = {
            "bid": getattr(sym_info, "bid", None),
            "ask": getattr(sym_info, "ask", None),
            "point": getattr(sym_info, "point", None),
            "digits": getattr(sym_info, "digits", None),
        }

    # Legacy 4 indicators (compat)
    from indicators import compute_all
    indicators_legacy = compute_all(ohlc) if ohlc else {}

    # Extended (Phase 2 D-09)
    from indicators import compute_all_extended
    indicators_ext = compute_all_extended(ohlc) if ohlc else None

    return {
        "symbol":              symbol,
        "timeframe":           tf,
        "bars_used":           len(ohlc),
        "ohlc":                ohlc,
        "tick":                tick,
        "indicators":          indicators_legacy,            # backward compat
        "indicators_extended": _serialize_extended(indicators_ext),  # additive D-C1
    }
```

### Bootstrap order (D-F4)

```python
# mcp/server.py — bootstrap section
from mcp.server import Server
from mcp.server.stdio import stdio_server
import asyncio

from config import Config
from logger import init_logger
from mt5_client import Mt5Client
from mcp.job_queue import JobQueue
from mcp.trail_daemon import ensure_table as trail_ensure_table

cfg = Config()
log = init_logger(cfg)
mt5 = Mt5Client(cfg)
_mt5_ready: bool = False
job_queue: JobQueue | None = None


def _bootstrap_mt5() -> bool:
    global _mt5_ready
    try:
        _mt5_ready = mt5.initialize() and mt5.login()
    except Exception:
        log.exception("MCP server: errore init MT5")
        _mt5_ready = False
    return _mt5_ready


def _bootstrap_state() -> None:
    """Order-sensitive: MT5 → DB tables → JobQueue → stdio (D-F4)."""
    global job_queue
    db_path = str(daily_db_path(cfg))   # logs/trades.db
    # WAL mode (Phase 5 D-16)
    import sqlite3
    with sqlite3.connect(db_path) as c:
        c.execute("PRAGMA journal_mode=WAL")
    trail_ensure_table(db_path)
    job_queue = JobQueue(max_workers=cfg.MCP_MAX_CONCURRENT_RUNS, db_path=db_path)


server: Server = Server("trading-agent")
# ... @server.list_tools() and @server.call_tool() handlers populated
# from mcp.handlers (registered at module import) ...


async def _serve() -> None:
    log.info("MCP server starting (mt5_ready=%s, queue=%s)",
             _mt5_ready, "ready" if job_queue else "missing")
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    _bootstrap_mt5()
    _bootstrap_state()
    try:
        asyncio.run(_serve())
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass
```

### Test pattern: ProcessPool + DB write smoke

```python
# tests/test_mcp_smoke_round_trip.py
import asyncio
import time
import sqlite3
from pathlib import Path

import pytest

from mcp.server import job_queue, _bootstrap_state
from mcp.handlers.backtest import handle_run_backtest, handle_get_backtest_metrics


@pytest.fixture(autouse=True)
def setup_state(tmp_path, monkeypatch):
    db_path = tmp_path / "trades.db"
    # Patch daily_db_path
    from scheduler import daily_db_path
    monkeypatch.setattr("scheduler.daily_db_path", lambda cfg: db_path)
    # Initialize Phase 1 schema (backtest_runs / backtest_trades)
    from backtest.ledger import _ensure_schema
    _ensure_schema(db_path)
    _bootstrap_state()
    yield


def test_round_trip_metrics(monkeypatch):
    """Success criterion #4: run_backtest → poll → metrics match in-process."""
    args = {"symbol": "EURUSD", "timeframe": "H1",
            "date_start": "2024-01-01T00:00:00Z",
            "date_end":   "2024-01-31T23:00:00Z",
            "profile":    "MODERATE"}
    started = handle_run_backtest(args)
    assert started["status"] == "started"
    run_id = started["run_id"]

    # Poll every 0.5s up to 30s
    for _ in range(60):
        status = handle_get_backtest_metrics(run_id)
        if status["status"] in {"done", "failed", "cancelled"}:
            break
        time.sleep(0.5)
    assert status["status"] == "done", f"timeout / failure: {status}"
    assert "metrics" in status
    assert "sharpe" in status["metrics"]

    # Compare with direct in-process call
    from backtest.engine import BacktestEngine
    direct = BacktestEngine().run(...)   # same params
    assert abs(status["metrics"]["sharpe"] - direct.sharpe) < 1e-6
```

### Test pattern: trail daemon idempotent + favorable

```python
# tests/test_mcp_trail_daemon.py
import sqlite3
from unittest.mock import MagicMock
import pytest

from mcp.trail_daemon import ensure_table, register_trail, trail_tick


def _make_db(tmp_path):
    db = tmp_path / "trades.db"
    ensure_table(str(db))
    return str(db)


def test_register_trail_inserts_row(tmp_path):
    db = _make_db(tmp_path)
    register_trail(db, position_id=123, symbol="EURUSD", direction="BUY",
                   timeframe="M15", atr_mult=2.0, initial_sl=1.0980)
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT * FROM position_trails WHERE position_id=123").fetchone()
    assert row is not None


def test_tick_position_closed_deactivates(tmp_path):
    db = _make_db(tmp_path)
    register_trail(db, 123, "EURUSD", "BUY", "M15", 2.0, 1.0980)
    mt5 = MagicMock()
    mt5.get_position.return_value = None   # closed
    cfg = MagicMock(TRAIL_FAVORABLE_ONLY=True)
    trail_tick(mt5, db, cfg)
    with sqlite3.connect(db) as c:
        active = c.execute(
            "SELECT active FROM position_trails WHERE position_id=123"
        ).fetchone()[0]
    assert active == 0


def test_tick_favorable_modifies(tmp_path):
    db = _make_db(tmp_path)
    register_trail(db, 123, "EURUSD", "BUY", "M15", 2.0, 1.0980)
    mt5 = MagicMock()
    pos = MagicMock(price_current=1.1050, sl=1.0980, type=0)  # BUY
    mt5.get_position.return_value = pos
    mt5.get_ohlc.return_value = [
        {"high": 1.1010, "low": 1.0990, "close": 1.1000} for _ in range(14)
    ]
    mt5.modify_position.return_value = MagicMock(success=True)
    cfg = MagicMock(TRAIL_FAVORABLE_ONLY=True)
    trail_tick(mt5, db, cfg)
    mt5.modify_position.assert_called_once()
    args, kwargs = mt5.modify_position.call_args
    new_sl = kwargs.get("sl") or args[1]
    assert new_sl > 1.0980, f"expected SL > 1.0980 (favorable BUY), got {new_sl}"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monolithic `mcp_server.py` (450 LOC, 11 tools) | Package `mcp/` with per-domain handlers | Phase 6 (D-E1) | Maintainable past 25 tools; mirrors Phase 2/4 layout |
| Sync MCP tool blocking on long-running ops | Async + run_id + poll (D-A1, D-A3) | Phase 6 | Avoids MCP client timeout on 30-min baseline runs |
| Hand-rolled trailing in skill flow | Server-side daemon with persistent state (D-B2) | Phase 6 | Trailing autonomous 24/7 without skill activity |
| Tool versioning `_v2` | Additive fields by spec (D-C1) | Phase 6 | Single codepath; zero drift; aligned to PROJECT.md "tool signature stable" |
| Live-only OHLC | Live default + `as_of_ts` for replay (D-D1) | Phase 6 | Single BarSource adapter; replay_decision becomes thin orchestrator |
| Per-tool error format | Uniform error envelope `{ok: false, error: <code>, ...}` (D-F2) | Phase 6 | Skill flows can branch deterministically |

**Deprecated/outdated:**
- `mcp_server.py:430` legacy error envelope `{error: ..., tool: name}` — replaced by D-F2 standardized form. Wrap-then-translate during refactor; keep backward-compatible mapping for one cycle if needed. **Decision: replace fully — no skill consumer expects the old shape (verified from `tests/test_mcp_tools_v2.py:228-230` which only checks `"error" in payload`).**

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 5 `baseline_decisions.parquet` has a `decision_id` column (or composite key derivable to one) | replay_decision lookup | replay_decision baseline path can't lookup; escalate to amend Phase 5 schema OR make Phase 6 derive on-the-fly |
| A2 | TenTrade demo `trade_stops_level` is small (5–10 points = 0.5–1.0 pip on EURUSD) | modify_position validation | If broker returns 0 (no minimum), validation passes trivially. If broker returns large value (e.g. 30 pips), most user SL changes would be rejected — expected; suggested_sl mitigates UX |
| A3 | TenTrade does NOT require `freeze_level` checks for SLTP modification | modify_position validation | If freeze_level is non-zero, additional pre-validation needed; surfaced as separate error code `freeze_level_violation` if encountered. Easy to add post-discovery. |
| A4 | `ProcessPoolExecutor` spawn start method is default on Windows | JobQueue | On non-Windows, fork is default and inherits MT5 lib state; would crash. Phase 6 is Windows-only per CLAUDE.md, so non-issue. |
| A5 | Phase 1 `backtest_runs` schema includes `status` column (or equivalent) | JobQueue persistence | Phase 1 D-07 lists fields including `started_at`/`finished_at` but not `status` explicitly. Plan should add `ALTER TABLE` migration if absent. |
| A6 | `IntradayLoopScheduler` is the active scheduler in production (not legacy `Orchestrator`) | trail daemon hook | If user runs `Orchestrator`, trail tick won't fire; document for user, plan task adds hook to BOTH paths if needed. |
| A7 | `forex-trader-pro` skill currently does not assert `len(snapshot["ohlc"]) == 50` literally — assertion happens via LLM context, not code | MCP-R1 default change | If skill code DOES assert literal 50, default change breaks it. Wave 0 audit needed before merge. |
| A8 | `pyarrow` is in dep tree (transitively or directly) at Phase 6 execution time | replay_decision baseline lookup | If absent, install before Wave 0 (`pip install pyarrow`); otherwise replay_decision baseline path raises ImportError |
| A9 | The MCP SDK `validate_input=True` (default) on `@server.call_tool()` rejects malformed args BEFORE the handler runs | D-F1 enforcement | If `validate_input` is default-False in some SDK versions, manual validation needed. [VERIFIED: 1.27.0 default is True per server.py:492.] |
| A10 | TenTrade allows partial close via `mt5.order_send(action=TRADE_ACTION_DEAL, position=ticket, volume=partial_lots)` (less than total volume) | modify_position partial close | If broker rejects partial close and only allows full close, `partial_close_lots` must be reported as `partial_not_supported_by_broker`; integration test on demo confirms |

**If this table is not empty:** 10 assumptions need verification — most at Wave 0 audit time, two (A2, A3, A10) only verifiable against real demo broker via integration test.

---

## Open Questions

1. **Should `cancel_backtest` clean up partial `backtest_trades` rows, or leave them queryable?**
   - What we know: Worker may have written N closed trades to `backtest_trades` before being killed.
   - What's unclear: UX expectation — does skill want partial trades visible in `get_backtest_metrics(cancelled_id)` (status=cancelled, metrics=partial), or pretend the run never happened?
   - Recommendation: **Keep the rows**, mark `backtest_runs.status='cancelled'`, return `metrics: null` in `get_backtest_metrics` for cancelled runs (or partial metrics with a `partial=true` flag). User can manually `DELETE FROM backtest_trades WHERE run_id=...` if needed. Cheaper to implement than rollback.

2. **Should `replay_decision` ALSO accept a `baseline_drafts.parquet` lookup (per-bar per-detector) for non-trade Drafts?**
   - What we know: D-D2 specifies trades_log + baseline_decisions.parquet (both = closed trades only).
   - What's unclear: Skill may want to replay a `FORMING` or `NONE` Draft (for ML feature debugging — Phase 7 territory).
   - Recommendation: Out of scope Phase 6 — the 65M baseline_drafts rows don't have stable `decision_id` per Phase 5 D-03. Re-evaluate at Phase 7 when ML pipeline needs draft replay.

3. **Should `walk_forward_validate` save its N-fold metrics to a new schema `backtest_walkforward_runs`, or fold into `backtest_runs` with a `n_folds` column?**
   - What we know: Phase 1 D-07 schema has `n_folds`, `fold_mode`, `train_ratio` columns already (per `01-RESEARCH.md` line 678-684). Each fold's metrics could go to `backtest_runs` rows with shared parent `walkforward_run_id`.
   - Recommendation: Use Phase 1 schema as-is. Each fold = 1 `backtest_runs` row with `run_id = walkforward_<parent>_fold<i>`; parent walkforward run is recorded with a synthetic row containing aggregate metrics. Aligns with Phase 1 D-06.

4. **What's the `equity_curve_path` format — PNG (Phase 5 D-19) or JSON points list?**
   - Recommendation: PNG file, written by handler post-run using same matplotlib pattern as Phase 5 D-20. Path in `.planning/research/baseline-equity-curves/{run_id}.png`. Already a CONTEXT default. Plan task: write tiny PNG generator in `mcp/handlers/backtest.py` that re-uses Phase 5 plot helper if available, else inline plain matplotlib.

5. **Skill flow regression test: which exact skill paths must be green?**
   - What we know: success criterion #3 says "existing tool signatures unchanged on default args".
   - What's unclear: which forex-trader-pro flows constitute "existing".
   - Recommendation: Keep `tests/test_mcp_tools_v2.py` 100% green (it tests current 11-tool surface). Plus a manual checklist: skill-driven `get_market_snapshot` → `propose_trade` → `evaluate_trade_proposal` → `submit_order_if_approved` round-trip on EURUSD M15 returns same outcome shape as pre-Phase-6.

---

## Sources

### Primary (HIGH confidence — verified in this session)

- **`C:\trading-agent\mcp_server.py`** (450 LOC) — exact tool registration pattern, `@server.list_tools()` and `@server.call_tool()` shapes, error envelope, dispatch branch, MCP-safe stdio/stderr discipline. Lines 184-313, 316-433.
- **`C:\trading-agent\mt5_client.py`** (251 LOC) — exact `close_position` wrapper pattern (lines 191-250), `_retry(3)` decorator (lines 26-39), filling-mode resolution (lines 110-124), `get_ohlc` (lines 126-144), `send_order` (lines 154-188). All `modify_position` and `partial_close` wrappers will mirror this shape.
- **`C:\trading-agent\models.py`** — `BrokerProtocol` (lines 200-228), `OrderResult`, `AccountState`, `PositionInfo`, `TradeProposal` shapes confirmed.
- **`C:\trading-agent\scheduler.py`** — `IntradayLoopScheduler.run_one_cycle` (lines 530-632), `_manage_open_positions` placement (line 553), `daily_db_path` helper (line 316). Trail tick injection point identified.
- **`C:\trading-agent\.venv\Lib\site-packages\mcp\server\lowlevel\server.py:492`** — `def call_tool(self, *, validate_input: bool = True):` confirms input validation is default-on per D-F1.
- **`C:\trading-agent\.venv\Lib\site-packages\mcp\types.py:1315-1322`** — Tool model schema fields confirmed.
- **`C:\trading-agent\.venv\Lib\site-packages\mcp-1.27.0.dist-info\METADATA`** — `Version: 1.27.0` confirms SDK version.
- **`tests/test_mcp_tools_v2.py`** — existing test pattern (asyncio.run, MagicMock for mcp_server.mt5/cfg, `monkeypatch.setattr` on singletons). New tests inherit this.
- **`tests/conftest.py`** — MetaTrader5 stub for dev laptops without MT5 installed.
- **`.planning/phases/01-backtest-engine/01-RESEARCH.md`** — Phase 1 BacktestEngine, walk_forward, metrics, ledger schema, GMT-6 verification, BacktestBroker pattern.
- **`.planning/phases/05-baseline-backtest/05-CONTEXT.md`** — Phase 5 ProcessPool pattern (D-15), WAL mode (D-16), parquet schemas (D-01/02/03), equity curve PNG (D-19/20), `run_id` format (D-13).
- **`.planning/phases/04-strategy-refactor/04-CONTEXT.md`** — `evaluate_proposal_for_bar`, `ProposalDraft` schema (D-03), `StrategyContext` (D-04), `build_ctx_backtest` (D-05).
- **`.planning/phases/02-indicators-library/02-CONTEXT.md`** — `compute_all_extended`, `MTFAlignmentResult`, `RegimeResult` shapes; Phase 2 D-09 ExtendedIndicators dataclass.
- **`.planning/phases/03-patterns-catalog/03-CONTEXT.md`** — `PatternHit` frozen dataclass schema (name, bar_index, span_bars, extreme_price, confidence, direction).
- **`.planning/codebase/STACK.md`** — Python 3.12, mcp>=1.27.0, sqlite3 WAL, MetaTrader5 5.0.5735.
- **`.planning/codebase/TESTING.md`** — pytest patterns, MagicMock conventions, `@pytest.mark.skipif` for MT5 e2e.
- **`requirements.txt`** — pinned versions verified.
- **`pytest.ini`** — `pythonpath = .` confirmed.
- **`CLAUDE.md`** — Italian comments, EXECUTION_MODE=shadow, ORDER_FILLING_RETURN, .env-only config, mock Mt5Client in tests.

### Secondary (MEDIUM confidence — web-verified)

- **MT5 `TRADE_ACTION_SLTP` request shape** — [CITED: https://www.mql5.com/en/forum/389359 "Modifying SL/TP in an open position in MT5 with MetaTrader5 package and python"] confirms `action`, `symbol`, `position`, `sl`, `tp` (float-typed) is the canonical request body. [CITED: https://www.mql5.com/en/forum/341452 "python:Change open position Stop Loss and Take Profit by python code"] supplements with retcode handling.
- **`trade_stops_level` semantics** — [CITED: https://www.switchmarkets.com/learn/trailing-stop-loss-mt4-5] and [CITED: https://www.profitsmasher.com/2025/08/smart-position-sizer-for-metatrader-5.html] confirm `trade_stops_level` is in points; `points × symbol.point` = price-unit minimum distance from current price. Zero means no minimum.
- **`Future.cancel()` semantics on Windows** — Python stdlib docs (verified through training knowledge): `cancel()` on a Future already in execution returns False; `pool.shutdown(wait=False, cancel_futures=True)` is the only way to terminate running workers. ProcessPool worker termination on Windows is asynchronous (OS-level subprocess cleanup).

### Tertiary (LOW confidence — flagged for validation)

- TenTrade-specific `trade_stops_level` and `trade_freeze_level` actual values [ASSUMED A2, A3] — must be read at runtime via `mt5.symbol_info()` per symbol (EURUSD, GBPUSD). Integration test discovers actual values.
- Whether `forex-trader-pro` skill code asserts literal `len(ohlc)==50` somewhere [ASSUMED A7] — manual audit required before merge.
- `pyarrow` presence in environment [ASSUMED A8] — verify via `pip show pyarrow` at Wave 0.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified via dist-info or grep.
- Architecture: HIGH — D-A1..D-F4 fully locked in CONTEXT.md; pattern derived from existing mcp_server.py + Phase 1/5 surfaces.
- MT5 modify_position semantics: MEDIUM — `TRADE_ACTION_SLTP` confirmed via 2 forum sources; broker-specific `trade_stops_level` value MUST be read at runtime, not assumed.
- Trail daemon coupling: MEDIUM — single-line scheduler hook is straightforward; race conditions (concurrent close + tick) mitigated by daemon idempotency, but require integration testing.
- Backward compat: MEDIUM — additive schema is safe in spec, but skill flow regression requires manual audit.
- Pitfalls: HIGH — derived from reading code paths in this session; ProcessPool + MT5 fork-safety carry from Phase 5.

**Research date:** 2026-05-08
**Valid until:** 2026-08-08 (stable domain — MCP SDK and MT5 lib versions stable; broker behavior may shift if user changes brokers)

---

## RESEARCH COMPLETE

**Phase:** 6 — MCP Tools (part 1)
**Confidence:** HIGH

### Key Findings

1. **Phase 6 is exposure work, not logic work.** 13 of 14 tools wrap Phase 1–5 surfaces; only NEW logic is the trailing-stop daemon (~150 LOC: `position_trails` table + `trail_tick` function + 1-line scheduler hook). All algorithmic complexity is delegated downstream.

2. **`Mt5Client.modify_position` does not exist today** — must be added as a thin wrapper around `mt5.order_send(action=TRADE_ACTION_SLTP, ...)` mirroring the existing `close_position` pattern (mt5_client.py:191-250). Same retry decorator, same filling-mode resolution, same retcode handling. Plus `partial_close` and `get_position` wrappers. **3 new methods on Mt5Client.**

3. **ProcessPool worker constraint is the single biggest implementation risk.** MetaTrader5 lib is not fork-safe (Phase 5 D-15 carry). Worker function must use ONLY `BacktestBroker` + `load_italian_csv` + `BacktestEngine` (Phase 1 surfaces) — never import `mt5_client`. Test by spawning worker on dev laptop without MT5 terminal connected; if it crashes, diagnose import chain.

4. **`forex-trader-pro` skill flow regression is the under-appreciated risk** (success criterion #3). The default-bars change (50 → 200) on `get_market_snapshot` is technically additive but behaviorally non-trivial. Wave 0 must include a code audit of `.claude/skills/forex-trader-pro/` for any literal `50` assertion. Manual end-to-end skill round-trip required before merge.

5. **Trail daemon stops_level violation needs clamping**, not raw broker-rejection retry. Otherwise log spam during favorable trail moves on tight-stops_level brokers.

6. **`get_backtest_metrics` polymorphic schema works on permissive JSON-Schema** with `status` discriminator + optional fields. `oneOf` strict variant deferred per CONTEXT.md unless skill clients prove unable to parse.

7. **Phase 1 `backtest_runs` schema may need a `status` column** for D-A1 lifecycle tracking (running/done/failed/cancelled). Phase 1 RESEARCH §Trade Ledger Schema lists `started_at`/`finished_at` but no explicit status enum. Wave 0 task: verify; add `ALTER TABLE backtest_runs ADD COLUMN status TEXT NOT NULL DEFAULT 'unknown'` migration if absent.

8. **Replay decision relies on Phase 5 parquet schema column `decision_id`** (or derivable composite). [ASSUMED A1] — verify in Wave 0; if not present, either derive from `(run_id, bar_ts_utc)` composite or escalate to amend Phase 5.

### File Created

`C:\trading-agent\.planning\phases\06-mcp-tools-part-1\06-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | mcp 1.27.0 verified via dist-info; all dependencies present in requirements.txt |
| Architecture | HIGH | D-A1..D-F4 locked in CONTEXT; existing mcp_server.py pattern direct extension |
| MT5 modify_position | MEDIUM | `TRADE_ACTION_SLTP` semantics confirmed via web sources; broker-specific `trade_stops_level` value runtime-only |
| Trail daemon | MEDIUM | Pattern straightforward; integration with `IntradayLoopScheduler` proven; race conditions documented |
| Backward compat | MEDIUM | Additive by JSON spec; skill flow audit required |
| Pitfalls | HIGH | 8 distinct pitfalls catalogued with code-level mitigation |
| Tests | HIGH | 40+ test entries mapped to requirements; existing pytest patterns followed |

### Open Questions for Planner

- (Q1) Cancel backtest cleanup policy — keep partial trades or wipe? Recommendation: keep + `partial=true` flag.
- (Q2) Replay decision via `baseline_drafts.parquet` for non-trade Drafts — out of scope, defer to Phase 7.
- (Q3) `walk_forward_validate` storage — fold into `backtest_runs` with `walkforward_<parent>_fold<i>` naming. Recommendation: yes.
- (Q4) Equity curve format — PNG via Phase 5 plot helper. Recommendation: yes.
- (Q5) Skill regression scope — keep `tests/test_mcp_tools_v2.py` green + manual round-trip checklist. Recommendation: yes.

### Ready for Planning

Research complete. Planner can now create PLAN.md files using this research + 06-CONTEXT.md as references. Suggested wave structure (5 waves):

1. **Wave 0** — Test infrastructure (conftest stub extensions, fixtures, all test files empty-stubbed) + dependency verification (`pyarrow`, Phase 1–5 imports).
2. **Wave 1** — `mcp/` package skeleton + shim + extended `Mt5Client` (modify_position, partial_close, get_position) + `mcp/bar_source.py` + `mcp/schemas.py` + R1/R2/R3 backward-compat refactor. Existing `tests/test_mcp_tools_v2.py` stays green.
3. **Wave 2** — `mcp/job_queue.py` + `mcp/handlers/backtest.py` (run_backtest, get_backtest_metrics, walk_forward_validate, cancel_backtest) + smoke round-trip test (success criterion #4).
4. **Wave 3** — `mcp/trail_daemon.py` + `mcp/handlers/position.py` (modify_position, get_position_state) + scheduler hook + DB migration if needed. Integration test for modify_position (manual MT5 demo).
5. **Wave 4** — `mcp/handlers/market.py` extensions (get_correlation_matrix, get_session_state, get_multi_tf_snapshot, get_pattern_catalog) + `replay_decision` (union lookup + Phase 4 evaluate). End-to-end skill flow regression test (success criterion #3).
