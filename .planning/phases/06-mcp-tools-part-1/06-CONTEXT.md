# Phase 6: MCP Tools (part 1) — Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Source:** /gsd:discuss-phase 6 (interactive, 4 aree, mode=discuss)

<domain>
## Phase Boundary

Esporre attraverso `mcp_server.py` il nuovo surface MCP della milestone v2: 13 tool tra nuovi e refactor di firme esistenti. Categorie:

- **Backtest control plane** (3 tool): `run_backtest` (MCP-01), `get_backtest_metrics` (MCP-02), `walk_forward_validate` (MCP-03)
- **Position management** (2 tool): `modify_position` (MCP-16), `get_position_state` (MCP-17)
- **Market context** (4 tool): `get_correlation_matrix` (MCP-09), `get_session_state` (MCP-11), `get_multi_tf_snapshot` (MCP-12), `get_pattern_catalog` (MCP-14)
- **Audit/replay** (1 tool): `replay_decision` (MCP-15)
- **Refactor backward-compatible** (3 tool): `get_market_snapshot` (MCP-R1), `scan_symbol_candidates` (MCP-R2), `propose_trade` (MCP-R3)

Surface totale `mcp_server.py` dopo questa fase: 11 esistenti + 10 nuovi + 3 refactor + 1 derivato (`cancel_backtest`) = **25 tool registrati** in `tools/list`. (REQUIREMENTS dichiara 13; il +1 `cancel_backtest` è derivato dalla decisione D-A4 sotto e va segnato come "tool extra Phase 6".)

Tutti i nuovi tool si appoggiano a moduli già lockati nelle Phase 1-5: backtest engine, indicators extended, patterns catalog, strategy refactor, baseline dataset. Phase 6 NON introduce nuova business logic — è esposizione MCP di capability esistenti + 1 daemon nuovo (trailing stop persistence).

**In scope:** MCP-01, MCP-02, MCP-03, MCP-09, MCP-11, MCP-12, MCP-14, MCP-15, MCP-16, MCP-17, MCP-R1, MCP-R2, MCP-R3. + `cancel_backtest` (derivato).

**Out of scope (deferred):**
- Tool ML inference/training (`train_ml_filter`, `predict_trade_quality`, `get_ml_calibration`, `evaluate_trade_proposal` ML extension) → Phase 8
- Failure clusters / drift / suggest_position_action → Phase 9
- Intermarket context + economic calendar → Phase 10
- MCP progress notification stream protocol — usato `get_backtest_metrics` polimorfico al suo posto (D-A3)
- Versioning tool `_v2` — additive sempre attivi è la strategia (D-C1)

</domain>

<decisions>
## Implementation Decisions

### Backtest execution model + run lifecycle

- **D-A1 — Async run + run_id immediato + poll.** `run_backtest(symbol, timeframe, date_range, profile)` e `walk_forward_validate(...)` non bloccano: spawnano lavoro in `ProcessPoolExecutor` server-side, ritornano subito `{run_id, status: "started", started_at}`. Client polla `get_backtest_metrics(run_id)`. Niente MCP timeout su run lunghi (single slice ~minuti, baseline 27-run ~30min).
- **D-A2 — Storage condiviso con Phase 5: `logs/trades.db` schema `backtest_runs` + `backtest_trades`.** Run skill-issued atterrano nello stesso DB del baseline. Disambiguazione via prefisso `run_id`: baseline → `baseline_{date}_{symbol}_{tf}_{profile}` (Phase 5 D-13), MCP → `mcp_{utc_ts}_{symbol}_{tf}_{profile}`. Singola origine query per `replay_decision` e `get_backtest_metrics`. Nessun DB separato.
- **D-A3 — `get_backtest_metrics` polimorfico per status.** Stesso tool ritorna progress + metrics finali. Schema response cambia in base a `status`:
  - `status: "running"` → `{run_id, status, progress_pct, bars_processed, bars_total, trades_so_far, started_at, eta_seconds?}`
  - `status: "done"` → `{run_id, status, metrics: {sharpe, sortino, max_dd_pct, hit_rate, expectancy_pips, profit_factor, avg_R, longest_dd_days, trade_count}, equity_curve_path, finished_at}`
  - `status: "failed"` → `{run_id, status, error, started_at, failed_at}`
  Skill flow: chiama tool → branch su `status` → re-poll se running. No tool dedicato `get_backtest_progress` (decisione esplicita: 1 tool, 1 run_id, 1 round-trip per check).
- **D-A4 — Max 1 run async concorrente + tool aggiuntivo `cancel_backtest(run_id)`.** Server tiene 1 `ProcessPoolExecutor` slot. Nuovo `run_backtest` mentre uno gira → ritorna `{error: "run_in_progress", active_run_id}`. `cancel_backtest(run_id)` termina worker + segna `backtest_runs.status = "cancelled"`. Cap evita OOM (Phase 5 D-15 stima 1.8GB peak per slice singola, multi paralleli rischiano 16GB laptop). `cancel_backtest` **è tool extra non in REQUIREMENTS** ma necessario per UX async — segnato come Phase 6 derivato.

### modify_position design + trailing

- **D-B1 — Single combo tool atomico (MCP-16 fedele).** `modify_position(position_id, new_sl?, new_tp?, partial_close_lots?, move_sl_to_breakeven?, trail_stop_atr_mult?)`. 5 optional arg, almeno 1 deve essere settato (server valida). Atomicity: tutti i campi richiesti vengono applicati in 1 transazione MT5 (dove possibile) o sequenza con rollback logico (se 1 step fallisce, ritorna `{ok: false, error, applied_so_far: [...]}` ma NON tenta rollback degli step già committati su MT5 — broker stateful). Conflict rules:
  - `trail_stop_atr_mult` + `new_sl` simultanei → error `conflict: trail_and_manual_sl`
  - `move_sl_to_breakeven` + `new_sl` simultanei → error `conflict: be_and_manual_sl`
  - `partial_close_lots >= position.volume` → error `partial_exceeds_volume` (suggerire `close_position` per chiusura totale)
- **D-B2 — Trailing stop = in-process daemon, scheduler-driven, persistent SQLite.** `modify_position(..., trail_stop_atr_mult=X)` registra intent in nuova tabella `position_trails`:
  ```sql
  CREATE TABLE IF NOT EXISTS position_trails (
    position_id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,         -- BUY/SELL
    timeframe TEXT NOT NULL,         -- TF su cui calcolare ATR (default cfg.TIMEFRAME)
    atr_mult REAL NOT NULL,
    last_sl REAL NOT NULL,
    activated_at TEXT NOT NULL,
    last_update_at TEXT,
    active INTEGER NOT NULL DEFAULT 1
  );
  ```
  Scheduler esistente (Phase 16 APScheduler, 5min tick) hook nuovo: per ogni row `active=1`, verifica position ancora aperta su MT5; se sì calcola `candidate_sl = bar_close ± atr*atr_mult`; se favorevole vs `last_sl` → `mt5.modify_position(position_id, sl=candidate_sl)` + UPDATE `last_sl`. Se position chiusa → `active=0`. Persistente: riavvio agent ricarica trail attivi.
- **D-B3 — Strict broker validation, no auto-clamp.** Pre-call `mt5.symbol_info(symbol).stops_level` (min distance pip da prezzo corrente) per validare `new_sl`/`new_tp`. Violazione → ritorna `{ok: false, error: "stops_level_violation", current_price, min_distance_pips, requested_sl, suggested_sl}`. Skill può riprovare con `suggested_sl`. **Non** auto-correggere silenziosamente (preserve user intent). Idem per filling mode: `ORDER_FILLING_RETURN` di default (Phase 1 broker convention, TenTrade demo); IOC/FOK rejected con error chiaro.

### Backward-compat MCP-R1/R2/R3

- **D-C1 — Additive fields sempre attivi, no flag opt-in, no `_v2` versioning.** Tutti e 3 i tool refactored ritornano i campi nuovi sempre. Vecchi consumer ignorano campi sconosciuti (JSON additive = backward-compat by spec). Allineato a PROJECT.md "tool signature stable, refactor backward-compatible by default":
  - **MCP-R1 `get_market_snapshot`:** schema response esteso con `indicators_extended: ExtendedIndicators` (Phase 2 D-09). Bar count diventa **200 di default** (vs 50 originale), MA aggiunto arg opzionale `bars: int` (default 200, settable a qualsiasi 50-500) per controllo esplicito. Skill che assume `len(ohlc)==50` deve passare `bars=50` (1 line patch). I vecchi 4 indicatori `sma_20/ema_50/rsi_14/atr_14` restano nel campo `indicators` (compat); nuovi vivono in `indicators_extended` (additive, no key collision).
  - **MCP-R2 `scan_symbol_candidates`:** schema response esteso con `regime: "compressed"|"normal"|"expanded"` (Phase 2 D-15) + `correlation_warnings: [{paired_symbol, rolling_corr, lookback_bars}]` per ogni candidato. Schema input **invariato**.
  - **MCP-R3 `propose_trade`:** schema response esteso con `setup_type: "A"|"B"|"C"|"D"` + `confluence_score: float` (5-factor scorer Phase 4 D-08). Input invariato. Se `setup_type` non determinabile (proposta freeform skill manuale) → `setup_type: null`, `confluence_score: null`.
  
  **Nessun doppio codepath, nessun flag matrix.** Single implementation per tool. Drift testing zero.

### Data source policy (live MT5 vs historical CSV)

- **D-D1 — Live default + `as_of_ts` optional arg per slice point-in-time.** Tool che leggono OHLC (`get_multi_tf_snapshot`, `get_correlation_matrix`, `get_pattern_catalog`, e i 3 refactored MCP-R1/R2 dove applicabile) accettano arg opzionale `as_of_ts: ISO8601 | None`:
  - `as_of_ts == None` (default) → `mt5.get_ohlc(symbol, tf, n)` (live)
  - `as_of_ts == "2024-03-15T10:00:00Z"` → carica da `data/historical/{symbol}/{tf}.csv` via Phase 1 `load_italian_csv` e slice `bars[bisect_left(ts, as_of_ts) - n : bisect_left(ts, as_of_ts)]`
  Implementazione single codepath via nuovo modulo `mcp/bar_source.py` con classe `BarSource.get(symbol, tf, n, as_of_ts=None)`. Tutti i tool MCP che accedono OHLC passano per `BarSource`. Edge case `as_of_ts` oltre fine CSV → ritorna error `as_of_ts_out_of_range`. CSV mancante → error `historical_data_unavailable: {symbol}/{tf}.csv`.
- **D-D2 — `replay_decision` union lookup `trades_log` + `baseline_decisions.parquet`.** `replay_decision(decision_id)` cerca:
  1. Prima in `logs/trades.db trades_log` (live decisions, prefix `live_<id>` o id raw int)
  2. Se miss, in `data/training/baseline_decisions.parquet` (Phase 5, prefix `baseline_<run_id>_<idx>` o composite key `run_id + decision_ts_utc`)
  Recovera bar_ts_utc + symbol + timeframe + ProposalDraft snapshot. Poi chiama internamente:
  - `BarSource.get(symbol, tf, n_warmup, as_of_ts=bar_ts_utc)`
  - `compute_all_extended(bars)` (Phase 2)
  - `build_ctx_backtest(...)` (Phase 4 D-05)
  - `evaluate_proposal_for_bar(bars, indicators, ctx)` con codice CORRENTE
  Ritorna `{original_proposal, replayed_proposal, diff, regression: bool}`. `regression=true` se replayed_proposal differisce da original — segnale che strategia è cambiata (intenzionalmente o meno).

### Module layout (Claude's discretion)

- **D-E1 — Split `mcp_server.py` in package `mcp/handlers/` per dominio.** File singolo cresce da ~450 LOC (11 tool) a ~1500+ (25 tool). Pattern già usato in Phase 2 (`indicators/`) e Phase 4 (`strategy/`). Layout proposto (planner conferma):
  ```
  mcp/
  ├── __init__.py            # re-export server + bootstrap
  ├── server.py              # mcp_server.py rinominato — solo Server() + dispatch + bootstrap
  ├── schemas.py             # _PROPOSAL_SCHEMA, _PROPOSE_TRADE_SCHEMA, schemi nuovi
  ├── bar_source.py          # BarSource adapter (D-D1)
  ├── job_queue.py           # ProcessPoolExecutor + run_id registry + cancel (D-A1, D-A4)
  ├── trail_daemon.py        # position_trails table + scheduler hook (D-B2)
  └── handlers/
      ├── __init__.py
      ├── account.py         # get_account_state, get_risk_profile, get_trade_history
      ├── market.py          # get_market_snapshot (R1), scan_symbol_candidates (R2),
      │                      # get_symbol_indicators, get_symbol_universe,
      │                      # get_multi_tf_snapshot (12), get_correlation_matrix (09),
      │                      # get_session_state (11), get_pattern_catalog (14)
      ├── proposal.py        # propose_trade (R3), evaluate_trade_proposal,
      │                      # submit_order_if_approved
      ├── position.py        # modify_position (16), get_position_state (17),
      │                      # close_position
      ├── backtest.py        # run_backtest (01), get_backtest_metrics (02),
      │                      # walk_forward_validate (03), cancel_backtest, replay_decision (15)
  ```
  Backward-compat: `mcp_server.py` resta come **thin shim** che `from mcp.server import *` per non rompere CLI/scripts esterni che fanno `python -m mcp_server`. Eventualmente deprecation cycle.

### Engineering principles

- **D-F1 — JSON-Schema rigoroso per ogni tool.** Ogni `Tool(...)` ha `inputSchema` JSON-Schema completo: type, required, enum dove applicabile (es. `direction`, `timeframe`, `profile`, `setup_type`), constraint numerici (es. `progress_pct: minimum 0 maximum 100`), description per ogni proprietà. Validation server-side prima di handler dispatch (skill agentic riceve error chiaro).
- **D-F2 — Error envelope uniforme.** Tutti i tool che falliscono ritornano `{ok: false, error: <string_code>, message: <human_readable>, ...context}`. Codici standardizzati: `run_in_progress`, `unknown_run_id`, `historical_data_unavailable`, `stops_level_violation`, `as_of_ts_out_of_range`, `partial_exceeds_volume`, `conflict: <type>`, `mt5_not_ready`. Pattern già parziale in `mcp_server.py:430` (`{error: ..., tool: name}`) — formalizzare.
- **D-F3 — Logging stderr-only, mai stdout.** Vincolo MCP protocol esistente (mcp_server.py:11). Tutti i nuovi handler usano `log = init_logger(cfg)` (RotatingFileHandler). Nessun `print()`, nessun `logging.basicConfig` che riconfiguri root logger.
- **D-F4 — Bootstrap ordering invariato.** `_bootstrap_mt5()` chiamato da `__main__`, non a import time (pattern esistente). Job queue + trail daemon inizializzati prima di `stdio_server` ma dopo MT5 ready.

### Claude's Discretion

- Schema `equity_curve_path` in `get_backtest_metrics`: path file PNG (riusa Phase 5 D-19 dir) o lista point inline. Default: path file (consistente Phase 5).
- `walk_forward_validate` come orchestrator: gira N folds in serie nello stesso job o N sub-job paralleli? Default: serie nel singolo job (semantica più semplice, Phase 1 D-06 walk_forward già pure-function).
- `get_session_state` boundary: hard-coded UTC sessions (Sydney/Tokyo/London/NY) o config esterna? Default: hard-coded constants in `handlers/market.py` (sessions FX standard, pochi cambiamenti storici).
- `get_correlation_matrix` lookback default: 100 bar o config? Default: 100, override via arg.
- `get_pattern_catalog` bar count default: 50 (sufficiente per pattern multi-bar). Override via arg.
- `cancel_backtest`: aggiungere a `tools/list` o nascondere come internal? Default: esposto pubblicamente (UX agentic).
- Test integration `modify_position` su MT5 demo: TenTrade richiede position aperta. Strategy: marker `@pytest.mark.integration` skip default in CI, runnable manualmente prima di merge.
- `replay_decision` regression diff schema: full JSON diff (deep) o solo campi chiave (direction, entry, sl, tp, confidence)? Default: campi chiave + `full_diff` opt arg true.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project locked specs
- `.planning/PROJECT.md` — milestone scope, 11 tool esistenti stabili, refactor additive default, MCP contract stability constraint
- `.planning/REQUIREMENTS.md` §MCP Tools (new) — MCP-01..03, MCP-09, MCP-11, MCP-12, MCP-14, MCP-15, MCP-16, MCP-17; §MCP Tools (refactor existing) — MCP-R1..R3
- `.planning/ROADMAP.md` §Phase 6 — goal, 4 success criteria

### Prior phase carry-forward (MUST READ)
- `.planning/phases/01-backtest-engine/01-CONTEXT.md` — D-01/02 BrokerProtocol, D-05 cost.yaml, D-06 walk_forward harness (USED da MCP-03), D-07 SQLite `backtest_trades`/`backtest_runs` schema (CONDIVISO con Phase 6 D-A2), D-08/D-10 GMT-6→UTC loader (USED da BarSource D-D1), D-09 bar-close decision
- `.planning/phases/02-indicators-library/02-CONTEXT.md` — D-04 ExtendedIndicators dataclass (alimenta MCP-R1 indicators_extended D-C1, MCP-12 multi-TF D-D1), D-09 no future leakage, D-15/16 regime config (alimenta MCP-R2 regime field)
- `.planning/phases/03-patterns-catalog/03-CONTEXT.md` — `PatternHit` dataclass (alimenta MCP-14 `get_pattern_catalog`)
- `.planning/phases/04-strategy-refactor/04-CONTEXT.md` — D-02 detector signature, D-03 ProposalDraft (alimenta MCP-R3 setup_type/confluence_score), D-04 StrategyContext, D-05 build_ctx_backtest (USED da replay_decision D-D2), D-08 5-factor + profile_filters, D-13 drive-bar pattern (USED da replay_decision)
- `.planning/phases/05-baseline-backtest/05-CONTEXT.md` — D-02 baseline_decisions.parquet schema (alimenta replay_decision lookup D-D2), D-13 run_id format (disambigua da MCP run_id D-A2), D-15 hybrid orchestration ProcessPool pattern, D-16 SQLite WAL mode (riusato per concurrency MCP D-A1), D-17 config hashes audit

### Codebase maps
- `.planning/codebase/STRUCTURE.md` — flat root layout, package convention (mcp/ nuovo package per D-E1)
- `.planning/codebase/ARCHITECTURE.md` — strategy/scanner/scheduler/broker/MCP layering
- `.planning/codebase/STACK.md` — Python 3.12 (Anaconda), `mcp >= 1.27.0`, MetaTrader5, pandas, sqlite3
- `.planning/codebase/CONVENTIONS.md` — snake_case, dataclass, leading-underscore handler, italiano commenti/log
- `.planning/codebase/INTEGRATIONS.md` — MCP stdio JSON-RPC, broker filling mode (ORDER_FILLING_RETURN per TenTrade)
- `.planning/codebase/TESTING.md` — pytest, mock Mt5Client, integration marker

### Existing code (touch / extend)
- `mcp_server.py` (450 LOC) — refactor in `mcp/` package (D-E1) mantenendo shim `mcp_server.py` per CLI compat. 11 tool esistenti spostati nei rispettivi handler senza change semantica.
- `mt5_client.py::Mt5Client` — `get_ohlc`, `get_account_state`, `get_position`, `modify_position` (verifica esistenza metodo, altrimenti aggiungere wrapper su `mt5.order_send` con `TRADE_ACTION_SLTP`), `get_symbol_info` per stops_level (D-B3), `close_position`. Aggiungere `modify_position` se non presente come wrapper di `mt5.order_send(action=TRADE_ACTION_SLTP, ...)`.
- `risk_engine.py` — invariato. Tool MCP non bypassano risk_engine per submit (resta gate).
- `execution.py::run_once` — invariato per tool flow.
- `claude_agent.py::cheap_scan_symbol` — usato da MCP-R2 esteso con regime + correlation_warnings.
- `indicators.py::compute_all` (legacy 4 indicatori) — mantenuto per compat MCP-R1 `indicators` field. `indicators/compute_all_extended` (Phase 2) per `indicators_extended`.
- `patterns/` (Phase 3) — `scan_patterns` per MCP-14.
- `strategy/` (Phase 4) — `evaluate_proposal_for_bar`, `build_ctx_backtest` per replay_decision D-D2.
- `backtest/loader.py::load_italian_csv` — usato da BarSource D-D1.
- `backtest/engine.py::BacktestEngine` — invocato da `run_backtest` job queue D-A1.
- `backtest/walk_forward.py` (Phase 1 D-06) — invocato da `walk_forward_validate`.
- `backtest/metrics.py` — usato da `get_backtest_metrics` per status=done.
- `backtest/ledger.py` — schema `backtest_runs`/`backtest_trades` invariato (D-A2 condiviso).
- `scheduler.py` (Phase 16 APScheduler) — hook nuovo per trail daemon D-B2. NON sostituire scheduler, aggiungere job `trail_tick()` con interval=cfg.SCHEDULER_INTERVAL_MINUTES.
- `logger.py` — `_trades_db_path`, WAL mode (Phase 5 D-16) già attivo. Aggiungere `CREATE TABLE position_trails` su init.
- `models.py` — `TradeProposal`, `OrderResult`, `RiskDecision`. Eventualmente nuovo `TrailIntent` dataclass per D-B2.
- `config.py::Config` — leggere new env: `MCP_MAX_CONCURRENT_RUNS=1`, `MCP_DEFAULT_BARS=200`, `TRAIL_TICK_TIMEFRAME=M15`, `TRAIL_FAVORABLE_ONLY=true`.

### Configs (estendere in questa fase)
- `.env.example` (USER ATTENZIONE: file aperto in IDE) — aggiungere:
  ```
  # Phase 6 MCP
  MCP_MAX_CONCURRENT_RUNS=1
  MCP_DEFAULT_BARS=200
  TRAIL_TICK_TIMEFRAME=M15
  TRAIL_FAVORABLE_ONLY=true
  ```
- `data/configs/costs.yaml` — invariato (riusato da `run_backtest` via Phase 1).

### Output paths (creare in questa fase)
- Nessun output dataset nuovo. Riusa:
  - `logs/trades.db` tabelle `backtest_runs`, `backtest_trades`, `trades_log`, **`position_trails` (NEW D-B2)**
  - `data/training/baseline_decisions.parquet` (Phase 5, read-only per replay_decision)
  - `.planning/research/baseline-equity-curves/` (Phase 5, read-only)
- Test fixtures: `tests/fixtures/mcp/sample_position_trails.sql`, `tests/fixtures/mcp/sample_decision_trades_log.json`.

### Skills
- `forex-trader-pro` — consumer principale dei tool. Verificare che signature unchanged (R1/R2/R3 additive D-C1) non rompa skill flow esistente. Skill testing manuale post-merge.
- `forex-algo-dev` — bar boundary discipline, no future leakage (D-D1 BarSource enforce: as_of_ts slice rigoroso `< as_of_ts` non `<=`), idempotency tool, error envelope.

### External libs
- Nessuna nuova dep runtime. `mcp >= 1.27.0` esistente. `pyarrow` (Phase 5) per parquet read in replay_decision. `concurrent.futures.ProcessPoolExecutor` stdlib per job queue D-A1.
- Test: `pytest`, `pytest-asyncio` (per testare `@server.call_tool` async), `unittest.mock.patch` per Mt5Client mock.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `mcp_server.py` (full file, 450 LOC) — pattern handler già consolidato (`handle_get_symbol_universe`, `handle_scan_symbol_candidates`, `handle_get_symbol_indicators`, `handle_propose_trade`). Nuovi tool seguono stessa shape: function pura → `_text(...)` JSON envelope.
- `_text(payload)` helper (mcp_server.py:61) — riusato per ogni response.
- `_PROPOSAL_SCHEMA` / `_PROPOSE_TRADE_SCHEMA` (mcp_server.py:79, 97) — pattern JSON-Schema, esteso D-F1.
- `Mt5Client` — `get_account_state`, `get_ohlc`, `get_symbol_info`, `close_position` esistenti. `modify_position` da verificare/aggiungere come wrapper di `mt5.order_send(TRADE_ACTION_SLTP)`.
- `evaluate_trade(proposal, account, mt5, cfg)` (risk_engine) — gate invariato, riusato da `evaluate_trade_proposal`.
- `run_once` (execution.py) — flow shadow/live invariato.
- `Config` env-driven (mcp_server.py:36) — pattern config ovunque, no magic numbers.
- `init_logger` (logger.py) — RotatingFileHandler, stderr-safe per MCP. Riusato.

### Established Patterns
- **MCP tool shape:** `Tool(name, description, inputSchema=...)` in `list_tools()` + branch in `call_tool()` + handler function `handle_<name>(args) -> dict`.
- **Async handler:** `@server.call_tool() async def call_tool(...)`. Handler interno sync OK (MCP SDK 1.27 supporta sia sync che async return).
- **Error envelope:** `{error: str, tool: name}` esistente — formalizzare schema D-F2.
- **MCP-safe logging:** stderr/file only, mai stdout (mcp_server.py:11 commento esplicito).
- **Pattern thin handler + heavy module:** handler MCP è 5-15 LOC, delega a modulo dominio (indicators, strategy, backtest). Phase 6 mantiene.
- **SQLite shared `logs/trades.db`** con WAL (Phase 5 D-16) e `CREATE TABLE IF NOT EXISTS` su init.

### Hot Spots / Risks
- **MCP timeout client su run lunghi** — risolto da D-A1 async, ma skill agentic deve gestire poll loop. Documentare nei descrizioni tool (`get_backtest_metrics description`).
- **`ProcessPoolExecutor` su MCP server long-lived** — workers fork process Python; MetaTrader5 lib NON è fork-safe (stato globale). Worker process NON deve importare/usare `mt5_client` direttamente. `run_backtest` worker usa solo `BacktestBroker` (Phase 1) + `load_italian_csv` (CSV file = no MT5 dependency). Allineato Phase 5 D-15.
- **SQLite contention** `backtest_runs`/`backtest_trades` con MCP server (writer) + scheduler trail daemon (writer `position_trails`) + run_backtest worker (writer `backtest_trades`) — WAL mode (Phase 5 D-16) gestisce. Per-process connection, no sharing.
- **Trail daemon race con utente che chiude position manualmente** — daemon legge `position_trails`, controlla `mt5.get_position(id)`, se chiusa segna `active=0`. Race window <5min (scheduler interval). Mitig: trail update pre-check `mt5.get_position` esistente prima di modify.
- **`as_of_ts` future leakage** — BarSource deve usare `<` non `<=` (esclude bar al timestamp esatto, deve essere già chiusa). Test obbligatorio.
- **modify_position su position non più esistente** (chiusa nel frattempo) — broker ritorna error. Server propaga error envelope. Trail daemon idempotente: prossimo tick segna inactive.
- **`mcp_server.py` shim post-split** — `python -m mcp_server` deve continuare a funzionare. Test smoke obbligatorio.
- **Schema response polimorfico (D-A3)** — JSON-Schema standard non esprime "oneOf basato su status". Usare `oneOf` JSON-Schema o discriminator. Skill agentic deve branchare. Documentare in tool description con esempi.

### Integration Points
- **Phase 5 baseline orchestration** vs Phase 6 MCP `run_backtest` — entrambi usano stesso schema DB ma run_id prefix differenzia. `scripts/run_baseline_backtest.py` (Phase 5) NON passa per MCP; `run_backtest` MCP è API alternativa per skill-issued backtest singolo.
- **Phase 16 scheduler** — hook nuovo `trail_tick()` job. Non sostituire scheduler, registrare job aggiuntivo via `add_job(trail_tick, IntervalTrigger(minutes=cfg.SCHEDULER_INTERVAL_MINUTES))`.
- **forex-trader-pro skill** consumer di MCP-R1/R2/R3 — verificare contract test post-refactor (additive ok, ma bar count default 200 può sorprendere se skill assume 50).
- **Phase 8 MCP Tools (part 2)** estende `evaluate_trade_proposal` (MCP-R4) e aggiunge ML tool — Phase 6 lascia handler `proposal.py` aperto a estensione.

</code_context>

<specifics>
## Specific Ideas

### Job queue skeleton (D-A1, D-A4)

```python
# mcp/job_queue.py
from concurrent.futures import ProcessPoolExecutor, Future
from dataclasses import dataclass
from threading import Lock
from typing import Callable
import uuid, sqlite3

@dataclass
class JobRecord:
    run_id: str
    future: Future
    started_at: str
    status: str  # "running" | "done" | "failed" | "cancelled"

class JobQueue:
    def __init__(self, max_workers: int = 1, db_path: str = "logs/trades.db"):
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
            row = self._load_run_row(run_id)  # fallback DB lookup post-restart
            if row is None:
                return {"ok": False, "error": "unknown_run_id", "run_id": run_id}
            return self._row_to_status(row)
        if rec.status == "running":
            progress = self._read_progress_from_db(run_id)
            return {"run_id": run_id, "status": "running", **progress}
        return self._row_to_status(self._load_run_row(run_id))

    def cancel(self, run_id: str) -> dict:
        rec = self._jobs.get(run_id)
        if rec is None or rec.status != "running":
            return {"ok": False, "error": "no_active_run", "run_id": run_id}
        cancelled = rec.future.cancel()
        if not cancelled:
            # Future già in execution: termina worker (ProcessPool non supporta cancel mid-task)
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = ProcessPoolExecutor(max_workers=self._max)
        rec.status = "cancelled"
        self._update_run_row(run_id, status="cancelled")
        return {"ok": True, "run_id": run_id, "status": "cancelled"}
```

### Trail daemon hook (D-B2)

```python
# mcp/trail_daemon.py
import sqlite3
from logger import init_logger
from indicators import compute_atr  # Phase 2

log = init_logger(cfg)

def ensure_table(db_path: str):
    with sqlite3.connect(db_path) as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS position_trails (
            position_id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            atr_mult REAL NOT NULL,
            last_sl REAL NOT NULL,
            activated_at TEXT NOT NULL,
            last_update_at TEXT,
            active INTEGER NOT NULL DEFAULT 1
        )""")

def register_trail(position_id, symbol, direction, timeframe, atr_mult, initial_sl):
    with sqlite3.connect(_db) as c:
        c.execute("""INSERT OR REPLACE INTO position_trails
                     VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1)""",
                  (position_id, symbol, direction, timeframe, atr_mult, initial_sl, _utcnow_iso()))

def trail_tick(mt5_client):
    """Chiamato dallo scheduler ogni cfg.SCHEDULER_INTERVAL_MINUTES."""
    with sqlite3.connect(_db) as c:
        rows = c.execute("SELECT * FROM position_trails WHERE active=1").fetchall()
    for row in rows:
        pos = mt5_client.get_position(row["position_id"])
        if pos is None:
            _deactivate(row["position_id"])
            continue
        bars = mt5_client.get_ohlc(row["symbol"], row["timeframe"], 14)
        atr_val = compute_atr(bars, period=14)
        candidate = pos.price_current - atr_val * row["atr_mult"] if row["direction"] == "BUY" \
                    else pos.price_current + atr_val * row["atr_mult"]
        favorable = (row["direction"] == "BUY" and candidate > row["last_sl"]) or \
                    (row["direction"] == "SELL" and candidate < row["last_sl"])
        if favorable:
            res = mt5_client.modify_position(row["position_id"], sl=candidate)
            if res.success:
                _update_last_sl(row["position_id"], candidate)
                log.info("trail: pos=%d new_sl=%.5f atr=%.5f", row["position_id"], candidate, atr_val)
```

### BarSource adapter (D-D1)

```python
# mcp/bar_source.py
from bisect import bisect_left
from backtest.loader import load_italian_csv

class BarSource:
    @staticmethod
    def get(symbol: str, tf: str, n: int, as_of_ts: str | None = None,
            mt5_client=None) -> list[dict]:
        if as_of_ts is None:
            if mt5_client is None:
                raise ValueError("mt5_client required for live mode")
            return mt5_client.get_ohlc(symbol, tf, n)
        # Historical mode
        df = load_italian_csv(symbol, tf)  # Phase 1 D-08 GMT-6→UTC handled
        ts_arr = df["timestamp"].values
        cutoff = bisect_left(ts_arr, as_of_ts)  # strict < as_of_ts (no future leakage)
        if cutoff < n:
            raise ValueError(f"as_of_ts_warmup_insufficient: {as_of_ts}, need {n} bars")
        if cutoff > len(ts_arr):
            raise ValueError(f"as_of_ts_out_of_range: {as_of_ts}")
        return df.iloc[cutoff - n : cutoff].to_dict("records")
```

### `get_backtest_metrics` polimorfico (D-A3)

```python
def handle_get_backtest_metrics(run_id: str) -> dict:
    status = job_queue.status(run_id)
    if status.get("error") == "unknown_run_id":
        return {"ok": False, "error": "unknown_run_id", "run_id": run_id}
    if status["status"] == "running":
        return {"run_id": run_id, "status": "running",
                "progress_pct": status["progress_pct"],
                "bars_processed": status["bars_processed"],
                "bars_total": status["bars_total"],
                "trades_so_far": status["trades_so_far"],
                "started_at": status["started_at"]}
    if status["status"] == "done":
        metrics = compute_metrics_for_run(run_id)  # legge backtest_trades + backtest_runs
        return {"run_id": run_id, "status": "done",
                "metrics": metrics,
                "equity_curve_path": _equity_path(run_id),
                "finished_at": status["finished_at"]}
    if status["status"] == "failed":
        return {"run_id": run_id, "status": "failed",
                "error": status.get("error_message"),
                "started_at": status["started_at"],
                "failed_at": status["finished_at"]}
    if status["status"] == "cancelled":
        return {"run_id": run_id, "status": "cancelled",
                "started_at": status["started_at"],
                "cancelled_at": status["finished_at"]}
```

### modify_position handler (D-B1, D-B2, D-B3)

```python
def handle_modify_position(args: dict) -> dict:
    pid = int(args["position_id"])
    pos = mt5.get_position(pid)
    if pos is None:
        return {"ok": False, "error": "position_not_found", "position_id": pid}
    sym = mt5.get_symbol_info(pos.symbol)
    stops_level_pips = sym.stops_level * sym.point / _pip_size(pos.symbol)

    # Conflict detection
    if args.get("trail_stop_atr_mult") and args.get("new_sl"):
        return {"ok": False, "error": "conflict: trail_and_manual_sl"}
    if args.get("move_sl_to_breakeven") and args.get("new_sl"):
        return {"ok": False, "error": "conflict: be_and_manual_sl"}
    if args.get("partial_close_lots", 0) >= pos.volume:
        return {"ok": False, "error": "partial_exceeds_volume",
                "current_volume": pos.volume,
                "hint": "use close_position for full close"}

    applied = []
    # SL/TP atomic in singolo TRADE_ACTION_SLTP
    new_sl = args.get("new_sl") or (pos.price_open if args.get("move_sl_to_breakeven") else None)
    new_tp = args.get("new_tp")
    if new_sl is not None or new_tp is not None:
        # stops_level validation (D-B3)
        if new_sl is not None and not _within_stops_level(pos, new_sl, stops_level_pips):
            suggested = _suggest_sl(pos, stops_level_pips)
            return {"ok": False, "error": "stops_level_violation",
                    "current_price": pos.price_current,
                    "min_distance_pips": stops_level_pips,
                    "requested_sl": new_sl, "suggested_sl": suggested}
        res = mt5.modify_position(pid, sl=new_sl, tp=new_tp)
        if not res.success:
            return {"ok": False, "error": "broker_rejected", "applied_so_far": applied,
                    "broker_error": res.error_message}
        applied.append({"action": "modify_sltp", "sl": new_sl, "tp": new_tp})

    # Partial close
    if args.get("partial_close_lots"):
        res = mt5.partial_close(pid, args["partial_close_lots"])
        if not res.success:
            return {"ok": False, "error": "broker_rejected", "applied_so_far": applied,
                    "broker_error": res.error_message}
        applied.append({"action": "partial_close", "lots": args["partial_close_lots"]})

    # Trail register
    if args.get("trail_stop_atr_mult"):
        from mcp.trail_daemon import register_trail
        register_trail(pid, pos.symbol, pos.direction, cfg.TRAIL_TICK_TIMEFRAME,
                       args["trail_stop_atr_mult"], pos.sl_current)
        applied.append({"action": "trail_registered", "atr_mult": args["trail_stop_atr_mult"]})

    return {"ok": True, "position_id": pid, "applied": applied}
```

### `replay_decision` orchestrator (D-D2)

```python
def handle_replay_decision(decision_id: str) -> dict:
    # Lookup: trades_log first, then baseline_decisions.parquet
    row = _lookup_trades_log(decision_id) or _lookup_baseline_parquet(decision_id)
    if row is None:
        return {"ok": False, "error": "decision_not_found", "decision_id": decision_id}

    bars = BarSource.get(row["symbol"], row["timeframe"], row["warmup_bars"],
                         as_of_ts=row["bar_ts_utc"])
    indicators = compute_all_extended(bars)
    ctx = build_ctx_backtest(bars, row["regime"], row["profile"])  # Phase 4 D-05
    replayed = evaluate_proposal_for_bar(bars, indicators, ctx)

    diff = _diff_proposals(row["original_proposal"], replayed)
    return {
        "ok": True, "decision_id": decision_id,
        "original": row["original_proposal"],
        "replayed": replayed.to_dict() if replayed else None,
        "diff": diff,
        "regression": diff["any_difference"],
    }
```

### Tool registration shape (D-F1, D-C1)

```python
# Esempio MCP-R1 schema esteso (additive)
Tool(
    name="get_market_snapshot",
    description=(
        "Snapshot mercato: 200 barre OHLC default (override con `bars` 50-500), "
        "tick corrente, indicatori legacy (sma_20/ema_50/rsi_14/atr_14) + ExtendedIndicators "
        "completo (Phase 2). Per replay point-in-time passare `as_of_ts` ISO8601."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "bars": {"type": "integer", "minimum": 50, "maximum": 500, "default": 200},
            "as_of_ts": {"type": "string", "description": "ISO8601 UTC timestamp; null = live"},
        },
        "required": ["symbol"],
    },
)
```

</specifics>

<deferred>
## Deferred Ideas

- **MCP progress notifications protocol** — usato `get_backtest_metrics` polimorfico al suo posto (D-A3). Se Phase 8/9 servono streaming reale (es. live tick feed) rivalutare.
- **Multi-run paralleli** — locked a 1 (D-A4). Se profili user power vogliono lanciare 3 backtest simultanei senza blocco, alzare cap via `MCP_MAX_CONCURRENT_RUNS` env. Test memory peak prima di abilitare.
- **`evaluate_trade_proposal` ML extension (MCP-R4)** — Phase 8 (richiede classifier Phase 7 trained).
- **Tool versioning `_v2`** — rifiutato da D-C1. Se mai un breaking change inevitabile, riconsiderare.
- **Tool flag opt-in `include_extended`** — rifiutato da D-C1 (drift, doppio codepath).
- **ML-backed `suggest_position_action`** — Phase 9. Trail daemon attuale (D-B2) usa ATR static, non ML.
- **MT5 server-side trailing nativo** — rifiutato da D-B2 (broker support patchy TenTrade demo). Se broker future esponesse trailing affidabile, daemon potrebbe delegare.
- **Auto-clamp SL invalid** — rifiutato da D-B3 (perde user intent).
- **Tool `cancel_all_backtests`** — D-A4 cap=1 lo rende inutile. Aprire se D-A4 alzato.
- **Schema oneOf JSON-Schema rigoroso per response polimorfico (D-A3)** — preferito ora schema "permissive" con campi optional + `status` discriminator. Se skill agentic ha problemi di parsing, formalizzare oneOf.
- **`get_backtest_metrics` con paginazione equity curve** — equity curve può essere milioni di point. Path file PNG (Phase 5) evita; se serve raw data, paginazione.
- **Trail multi-TF** — daemon attuale calcola ATR su `cfg.TRAIL_TICK_TIMEFRAME` fisso. Se utente vuole trail su TF diverso da position TF, configurare per-trail.
- **Tool intermarket / news** — Phase 10.
- **WebSocket transport MCP** — stdio sufficiente per skill agentic locale. Future: HTTP+SSE per remote.
- **Tool `list_active_trails`** — diagnostico per vedere position_trails. Aprire se debugging serve.
- **Decision replay con strategia storica** — replay_decision usa codice CORRENTE. Se servisse riprodurre output strategia "as it was at decision time" (regression vs git_sha del decision_runs row), serve checkout temporaneo. Out of scope.
- **Modify multi-position bulk** — `modify_position` opera su 1 ticket. Bulk mode per close-all/move-all-be richiederebbe nuovo tool. Backlog se UX serve.

</deferred>

---

*Phase: 06-mcp-tools-part-1*
*Context gathered: 2026-05-07 via /gsd:discuss-phase*
*Mode: discuss (4 aree, 11 question, 12 decisioni dirette + 4 Claude discretion)*
