# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

- Python 3.12 64-bit (Windows). Python 3.14 lacks `pydantic-core` wheels — venv must use Anaconda 3.12.
- MetaTrader5 5.0.5735+ (TenTrade demo). MT5 terminal must be open and logged in before launching `main.py` or `mcp_server.py` (Python lib attaches via IPC).
- Anthropic Claude API (`claude_agent.py`, `mcp_server.py`).
- No APScheduler anymore — Phase 16 replaced it with a custom `IntradayLoopScheduler` (H24 loop in `scheduler.py`).

## Common commands

```powershell
# venv
.venv\Scripts\activate

# Run daemon (shadow mode by default — never sends real orders)
python main.py

# Run MCP server for Claude Desktop (stdio JSON-RPC; stdout must stay clean)
python mcp_server.py

# All tests
python -m pytest tests/ -v

# Single test
python -m pytest tests/test_strategy.py::test_identify_entry_setup_ready_buy -v

# Backtest
python backtest.py --strategy pullback --symbol EURUSD --timeframe M15 --start 2024-01-01 --end 2024-06-30

# Weekend smoke test (no MT5 ticks)
python scripts/dry_run_cycle.py

# Sanity checks
python -c "import struct; print(struct.calcsize('P')*8)"   # must print 64
python -c "import MetaTrader5, anthropic, mcp; print('imports OK')"
```

`pytest.ini` sets `pythonpath = .` so tests import top-level modules directly. Tests mock `Mt5Client` (no terminal needed) except `test_mt5.py` which is auto-skipped without MT5.

## Architecture

Pipeline per cycle: **scheduler tick → orchestrator gates → scanner (cheap → shortlist → deep) → strategy.identify_entry_setup → risk_engine.evaluate_trade → execution.run_once → mt5_client.send_order → logger persists**.

### Phase 16 H24 loop (current)

`scheduler.IntradayLoopScheduler` runs continuously, ticking every `INTRADAY_SCAN_INTERVAL_MINUTES` (default 15). Per tick the order of operations is fixed:

1. **Open-position management** — `strategy.evaluate_open_position` returns `HOLD | CLOSE_PROTECT | CLOSE_END_OF_DAY`; `mt5_client.close_position(ticket)` closes by ticket (no opposite-side opening).
2. **Pause / DRY_RUN gates** (`PAUSE_TRADING`, `DRY_RUN`).
3. **Operating window** check (lun–ven, `OPERATING_START_HOUR`–`OPERATING_END_HOUR`, `OPERATING_TIMEZONE`).
4. **News-window block** (hook in `StrategyEnvironment`).
5. **Scanner cycle** (only if all gates pass).
6. **Trade submission** through risk engine + execution.

`HeartbeatStore` writes to `logs/trades.db` tables `heartbeat` + `scheduler_state` every cycle. Overrun is skipped, not queued. There is **no APScheduler** anywhere — references to cron slots `08/11/14/17/20` in older docs are obsolete.

### Three-pass scanner (`scanner.py`)

1. **Cheap scan** — synthetic metrics (trend bias, momentum, volatility, spread) over the full `SYMBOLS` universe.
2. **Shortlist** — top `MAX_SYMBOLS_TO_DEEPEN` (default 3).
3. **Deep analysis** — full OHLC + indicators (`indicators.py`: RSI, SMA, EMA, ATR, Bollinger). Outcome ∈ `{TRADE, NO_TRADE, WAIT_FOLLOW_UP}`. `deep_analyze` accepts `paused`/`news_blocked` flags and tags `is_addon` setups; drawdown violations block trade emission.

### Risk engine is the single approval gate

`risk_engine.evaluate_trade` is deterministic. Every proposal — from `strategy.py`, `claude_agent.py` tool use, or MCP tool calls — must pass through it. It enforces kill switch, SL pip bounds, margin downsize, session filter, drawdown, and lot caps. Phase 16 added `would_proposal_exceed_drawdown` and `compute_existing_potential_loss_amount` for rolling-drawdown protection across open positions + new proposals.

### Execution modes

`EXECUTION_MODE` in `.env` controls `execution.run_once`:

| mode     | `send_order` | orders in MT5 | account |
|----------|--------------|----------------|---------|
| `shadow` | no           | no             | demo    |
| `paper`  | yes          | yes            | demo    |
| `live`   | yes          | yes            | real    |

Default and only safe value is `shadow`. **Never switch to `paper` or `live` without explicit user request in chat.** Change always via `.env`, never via code; restart daemon after change.

### Audit trail (`logs/trades.db`, SQLite WAL)

- `trades_log` — every risk decision (approved or rejected), with `decision_reason` and `pnl_realized` (NULL until close).
- `daily_run_state` — per-day `decisions_count`, `trade_count`, `no_trade_count` (auto-resets per date key, survives restarts).
- `heartbeat`, `scheduler_state` — Phase 16 loop liveness.

### MCP server (`mcp_server.py`)

10 tools exposed to Claude Desktop via stdio. Six v1.0 single-symbol (`get_account_state`, `get_market_snapshot`, `evaluate_trade_proposal`, `submit_order_if_approved`, `get_risk_profile`, `get_trade_history`) plus four v1.1 multi-symbol (`get_symbol_universe`, `scan_symbol_candidates`, `get_symbol_indicators`, `propose_trade`) and Phase 16 `close_position{position_id}` (DRY_RUN bypass). Logs go to `logs/agent.log` only — stdout must stay clean for JSON-RPC.

## Hard rules (project-specific)

- `EXECUTION_MODE=shadow` is the default; never flip to paper/live without explicit chat request.
- All config flows through `config.Config` from `.env`. **Never** `os.getenv` or read `.env` directly. Zero magic numbers — add a config knob instead.
- `risk_engine.evaluate_trade` is the only path to an approved trade. Bypassing it is a bug.
- One file per phase under `.orchestration/phase-prompts/`. `STATE.md` is the live source of truth — update after every micro-step. `PHASES.md` is read-only for the orchestrator.
- Commit conventions: see `COMMIT_CONVENTIONS.md` (Conventional Commits, scope from a fixed list, one phase per commit, `STATE.md` always included with the applicative files it describes). Never commit `.env`, `logs/*.db`, `logs/*.log`. Push to origin after every `feat(phase-N): complete` and every `chore(handoff)` (per user feedback memory).
- Handoff protocol: see `HANDOFF_PROTOCOL.md`.
- Comments, log messages, decision rationales: **Italian**.
- MT5 filling mode: `ORDER_FILLING_RETURN` only. `IOC` and `FOK` unsupported on EURUSD/GBPUSD on TenTrade.

## Common gotchas

- CSV historical data: headers have leading spaces (` Ora`, ` Open`); date format `dd/mm/YYYY HH:MM:SS`.
- Pip size: JPY pairs `0.01`, others `0.0001`. SL bounds (`MIN_SL_PIPS`/`MAX_SL_PIPS`) are pips — `entry_price`/`stop_loss_price` precision must match (5 digits EURUSD, not 4) or every SL gets rejected as too tight/wide.
- `ZoneInfo 'No time zone found with key Europe/Rome'` on Windows → `pip install tzdata`.
- Daemon "stops silently" usually means outside operating window — scheduler is up but no tick fires.
- `WAIT_FOLLOW_UP` doesn't count toward `DAILY_TARGET_DECISIONS`; the eventual TRADE/NO_TRADE does. Max one follow-up per `(date, symbol)` opportunity.

## Current phase

Per `STATE.md`: **Phase 16 (H24 Strategy Update)** — code-complete, awaiting user live validation on TenTrade demo. After validation: merge `feature/python-pure-strategy` → `main`, tag `v1.2.0`.
