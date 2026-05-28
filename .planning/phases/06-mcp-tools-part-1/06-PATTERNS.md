# Phase 6: MCP Tools (part 1) — Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 30 (new + modified)
**Analogs found:** 28/30 (2 no-analog: ProcessPoolExecutor JobQueue, BarSource as_of_ts strict-< slice)

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `mcp/__init__.py` | package-init | re-export | (none — trivial) | n/a |
| `mcp/server.py` | mcp-dispatcher | request-response | `mcp_server.py:1-450` (verbatim move) | exact |
| `mcp/schemas.py` | schema-config | static-data | `mcp_server.py:79-114` (`_PROPOSAL_SCHEMA`) | exact |
| `mcp/errors.py` | constants | static-data | `mcp_server.py:429-433` (error envelope shape) | role-match |
| `mcp/bar_source.py` | adapter | request-response | `mt5_client.py:127-144` (`get_ohlc`) + `backtest/loader.py:26-50` | role-match |
| `mcp/job_queue.py` | service / async-worker | event-driven (futures) | none in repo | NEW pattern |
| `mcp/trail_daemon.py` | service / scheduler-tick | CRUD + event-driven | `logger.py:41-66` (table init pattern) + `scheduler.py:553` (tick hook) | role-match |
| `mcp/handlers/__init__.py` | package-init | re-export | (trivial) | n/a |
| `mcp/handlers/account.py` | mcp-handler | request-response | `mcp_server.py:319-388` (3 legacy handlers) | exact |
| `mcp/handlers/market.py` | mcp-handler | request-response | `mcp_server.py:117-155` (`handle_get_symbol_indicators`) | exact |
| `mcp/handlers/proposal.py` | mcp-handler | request-response | `mcp_server.py:158-181` (`handle_propose_trade`) | exact |
| `mcp/handlers/position.py` | mcp-handler + broker-call | CRUD + transform | `mcp_server.py:410-427` (`close_position` handler) + `mt5_client.py:191-250` (`close_position` wrapper) | exact |
| `mcp/handlers/backtest.py` | mcp-handler + orchestrator | event-driven + CRUD | `backtest/walk_forward.py` + `backtest/ledger.py` + `mcp_server.py` (handler shape) | role-match |
| `mt5_client.py` (modify_position add) | broker-wrapper | request-response | `mt5_client.py:191-250` (`close_position`) | exact |
| `mt5_client.py` (partial_close add) | broker-wrapper | request-response | `mt5_client.py:191-250` (`close_position`) | exact |
| `mt5_client.py` (get_position add) | broker-wrapper | request-response | `mt5_client.py:198-204` (positions_get fragment) | exact |
| `mcp_server.py` (post-split shim) | re-export shim | (none) | none — trivial `from mcp.server import *` | n/a |
| `scheduler.py` (trail_tick hook) | scheduler-integration | event-driven | `scheduler.py:544-553` (try/except + manage_open_positions call) | exact |
| `logger.py` (position_trails DDL) | schema-bootstrap | static-data | `logger.py:14-66` (`_TRADES_LOG_SCHEMA` + `init_logger`) | exact |
| `models.py` (TrailIntent dataclass) | model | static-data | `models.py:7-65` (existing dataclasses) | exact |
| `config.py` (4 new env vars) | config | static-data | `config.py:60-80` (existing `Config` class) | exact |
| `.env.example` (4 new vars) | config | static-data | existing `.env.example` block layout | exact |
| `tests/conftest.py` (extend MT5 stub) | test-fixture | static-data | `tests/conftest.py:14-40` (existing stub) | exact |
| `tests/test_mcp_handlers_market.py` | test | request-response | `tests/test_mcp_tools_v2.py:51-153` | exact |
| `tests/test_mcp_handlers_position.py` | test | request-response | `tests/test_mcp_tools_v2.py` + `tests/test_backtest_ledger.py:26-37` | exact |
| `tests/test_mcp_handlers_backtest.py` | test | event-driven | `tests/test_backtest_ledger.py:26-60` + `tests/test_mcp_tools_v2.py:194-225` | role-match |
| `tests/test_mcp_handlers_proposal.py` | test | request-response | `tests/test_mcp_tools_v2.py:156-191` | exact |
| `tests/test_mcp_bar_source.py` | test | request-response | `tests/test_backtest_loader.py` (assumed similar) + `tests/conftest.py` | role-match |
| `tests/test_mcp_job_queue.py` | test | event-driven | none direct — combine `tests/test_backtest_ledger.py` (DB) + stdlib `Future` mocks | role-match |
| `tests/test_mcp_trail_daemon.py` | test | CRUD + event-driven | `tests/test_backtest_ledger.py:26-60` (sqlite3 + tmp_path) + `tests/test_mcp_tools_v2.py:51-70` (MagicMock mt5) | role-match |

---

## Pattern Assignments

### `mcp/server.py` (mcp-dispatcher, request-response)

**Analog:** `mcp_server.py:1-450` — moved verbatim with import paths fixed; logic identical.

**Imports + bootstrap singletons** (mcp_server.py:14-39):
```python
import asyncio
import dataclasses
import json
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from claude_agent import cheap_scan_symbol
from config import Config
from execution import run_once
from indicators import compute_all
from logger import init_logger
from models import TradeProposal
from mt5_client import Mt5Client
from risk_engine import evaluate_trade

# Singleton globali — inizializzati al boot del server (e non al solo import del modulo,
# così i test possono importare mcp_server senza far partire MT5).
cfg = Config()
log = init_logger(cfg)
mt5 = Mt5Client(cfg)
_mt5_ready: bool = False
```

**Server construction + JSON envelope** (mcp_server.py:58-62):
```python
server: Server = Server("trading-agent")


def _text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, default=str, ensure_ascii=False))]
```

**`@list_tools` + `@call_tool` dispatch + try/except envelope** (mcp_server.py:184-433):
```python
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="get_account_state", description=..., inputSchema={...}),
        # ... one Tool per name
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_account_state":
            state = mt5.get_account_state()
            return _text(dataclasses.asdict(state))
        # ... branch per name
        return _text({"error": f"unknown tool: {name}"})
    except Exception as exc:
        log.exception("MCP tool error: name=%s", name)
        return _text({"error": str(exc), "tool": name})
```

**Bootstrap + serve** (mcp_server.py:436-450):
```python
async def _serve() -> None:
    log.info("MCP server starting (mt5_ready=%s)", _mt5_ready)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    _bootstrap_mt5()
    try:
        asyncio.run(_serve())
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass
```

**Phase-6 changes:** D-F4 invariato; insert `JobQueue` + `trail_daemon.ensure_table` between `_bootstrap_mt5()` and `asyncio.run(_serve())`. Wrap legacy `{error, tool}` envelope (line 433) into D-F2 shape `{ok: false, error, message, tool}` via small adapter.

---

### `mcp/schemas.py` (schema-config, static-data)

**Analog:** `mcp_server.py:79-114` (`_PROPOSAL_SCHEMA`, `_PROPOSE_TRADE_SCHEMA`).

**Schema shape pattern** (mcp_server.py:79-95):
```python
_PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "direction": {"type": "string", "enum": ["BUY", "SELL"]},
        "entry_price": {"type": "number"},
        "stop_loss_price": {"type": "number"},
        "take_profit_price": {"type": "number"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
    },
    "required": [
        "symbol", "direction", "entry_price",
        "stop_loss_price", "take_profit_price",
        "confidence", "rationale",
    ],
}
```

**Phase-6 use:** copy verbatim; add `RUN_BACKTEST_SCHEMA`, `MODIFY_POSITION_SCHEMA`, `GET_BACKTEST_METRICS_SCHEMA`, `REPLAY_DECISION_SCHEMA`, `BARS_AS_OF_FIELDS` (the `bars: integer minimum 50 maximum 500 default 200` + `as_of_ts: string` snippet shared across R1/R2/R3 + market handlers). Use `enum` for `direction`, `timeframe` (M15/M30/H1), `profile` (CONSERVATIVE/MODERATE/AGGRESSIVE), `setup_type` (A/B/C/D).

---

### `mcp/handlers/account.py` (mcp-handler, request-response)

**Analog:** `mcp_server.py:319-388` (`get_account_state`, `get_risk_profile`, `get_trade_history` branches).

**`get_account_state` pattern** (mcp_server.py:319-321):
```python
if name == "get_account_state":
    state = mt5.get_account_state()
    return _text(dataclasses.asdict(state))
```

**`get_risk_profile` pattern** (mcp_server.py:359-374):
```python
if name == "get_risk_profile":
    return _text({
        "RISK_MODE": cfg.RISK_MODE,
        "RISK_AMOUNT_MODE": cfg.RISK_AMOUNT_MODE,
        # ... pure cfg attribute extraction
        "EXECUTION_MODE": cfg.EXECUTION_MODE,
        "TIMEFRAME": cfg.TIMEFRAME,
    })
```

**`get_trade_history` SQLite read pattern** (mcp_server.py:376-388):
```python
if name == "get_trade_history":
    n = int(arguments.get("n", 10))
    db_path = Path(cfg.LOG_FILE).parent / "trades.db"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, timestamp, symbol, ... FROM trades_log ORDER BY id DESC LIMIT ?",
            (n,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return _text(rows)
```

**Phase-6 use:** Move 3 handlers to `handlers/account.py` as `handle_get_account_state(mt5)`, `handle_get_risk_profile(cfg)`, `handle_get_trade_history(cfg, n)`. No semantic change.

---

### `mcp/handlers/market.py` (mcp-handler, request-response)

**Analog:** `mcp_server.py:117-155` (`handle_get_symbol_indicators`) + `mcp_server.py:323-342` (`get_market_snapshot` inline branch).

**Handler pure-function shape** (mcp_server.py:142-155):
```python
def handle_get_symbol_indicators(symbol: str, timeframe: str | None = None) -> dict:
    """Indicatori approfonditi per un singolo simbolo. SMA(20), EMA(50), RSI(14), ATR(14)."""
    tf = timeframe or cfg.TIMEFRAME
    ohlc = mt5.get_ohlc(symbol, tf, 100)
    if not ohlc:
        return {"error": "no ohlc data", "symbol": symbol, "timeframe": tf}
    indicators = compute_all(ohlc)
    return {
        "symbol": symbol,
        "timeframe": tf,
        "bars_used": len(ohlc),
        "last_close": ohlc[-1]["close"],
        "indicators": indicators,
    }
```

**`get_market_snapshot` legacy 50-bar shape** (mcp_server.py:323-342):
```python
if name == "get_market_snapshot":
    symbol = arguments["symbol"]
    ohlc = mt5.get_ohlc(symbol, cfg.TIMEFRAME, 50)
    sym_info = mt5.get_symbol_info(symbol)
    tick: dict = {}
    if sym_info is not None:
        tick = {"bid": ..., "ask": ..., "point": ..., "digits": ...}
    indicators = compute_all(ohlc) if ohlc else {}
    return _text({
        "symbol": symbol,
        "timeframe": cfg.TIMEFRAME,
        "ohlc": ohlc, "tick": tick, "indicators": indicators,
    })
```

**Phase-6 use (R1 additive):** replace `mt5.get_ohlc(...)` with `BarSource.get(symbol, tf, bars or cfg.MCP_DEFAULT_BARS, as_of_ts=as_of_ts, mt5_client=mt5)`; KEEP legacy `indicators` field; ADD `indicators_extended = compute_all_extended(ohlc)` (Phase 2). For MCP-09/11/12/14: same pure-function shape, delegates to existing modules (`indicators` Phase 2 for multi-tf, `patterns` Phase 3 for catalog), no MT5 logic in handler beyond `BarSource.get`.

---

### `mcp/handlers/proposal.py` (mcp-handler, request-response)

**Analog:** `mcp_server.py:65-76` (`_build_proposal`) + `mcp_server.py:158-181` (`handle_propose_trade`) + `mcp_server.py:344-357` (evaluate + submit branches).

**Proposal builder + log + dataclass-asdict response** (mcp_server.py:158-181):
```python
def handle_propose_trade(args: dict) -> dict:
    """Formalizza una proposta finale dell'agente. NON esegue ordini, NON decide size."""
    timeframe = args.get("timeframe") or cfg.TIMEFRAME
    proposal = TradeProposal(
        symbol=args["symbol"],
        direction=args["direction"],
        entry_price=float(args["entry_price"]),
        # ...
        rationale=args["rationale"],
    )
    log.info("MCP propose_trade formalized: symbol=%s direction=%s confidence=%.2f",
             proposal.symbol, proposal.direction, proposal.confidence)
    return {
        "status": "proposed",
        "executed": False,
        "proposal": dataclasses.asdict(proposal),
        "next_step": "call evaluate_trade_proposal or submit_order_if_approved to act on it",
    }
```

**Phase-6 use (R3 additive):** dopo costruzione `TradeProposal`, invoke Phase 4 `evaluate_proposal_for_bar(...)` to derive `setup_type` (A/B/C/D) and `confluence_score`; if freeform manual call (skill non passa indicatori → impossibile derivare) → `setup_type: None, confluence_score: None`. Add fields to response dict (additive). `evaluate_trade_proposal` and `submit_order_if_approved` invariati: continuano a chiamare `risk_engine.evaluate_trade` (mcp_server.py:347).

---

### `mcp/handlers/position.py` (mcp-handler + broker-call, CRUD + transform)

**Analog:** `mcp_server.py:410-427` (close_position handler) + `mt5_client.py:191-250` (close_position wrapper).

**DRY_RUN branch pattern** (mcp_server.py:411-421) — MUST mirror in `modify_position`:
```python
if name == "close_position":
    position_id = int(arguments["position_id"])
    if cfg.DRY_RUN:
        log.info("MCP close_position DRY_RUN ticket=%d (nessun ordine reale)", position_id)
        return _text({
            "success": True,
            "order_id": None,
            "error_message": None,
            "execution_mode": cfg.EXECUTION_MODE,
            "dry_run": True,
            "note": "DRY_RUN: nessun ordine inviato a MT5",
        })
    result = mt5.close_position(position_id)
    return _text({
        **dataclasses.asdict(result),
        "execution_mode": cfg.EXECUTION_MODE,
        "dry_run": False,
    })
```

**Phase-6 modify_position pattern (D-B1 atomic combo):**
1. Pre-validate conflicts (`trail+sl`, `be+sl`, `partial>=volume`) → return D-F2 error envelope.
2. `pos = mt5.get_position(pid)`; if `None` → `{ok: false, error: "position_not_found"}`.
3. `cfg.DRY_RUN` branch (return early `{ok: true, dry_run: true, applied: [<intent>]}`).
4. Stops-level validation via `mt5.get_symbol_info(...).trade_stops_level * point / pip_size` — reject with `suggested_sl`.
5. SL/TP via `mt5.modify_position(pid, sl, tp)` (NEW wrapper).
6. Partial close via `mt5.partial_close(pid, lots)` (NEW wrapper).
7. Trail register via `trail_daemon.register_trail(...)`.
8. Return `{ok: true, applied: [...]}` with array of step actions; on broker reject mid-sequence return `{ok: false, error: "broker_rejected", applied_so_far: [...]}` (no rollback per D-B1).

---

### `mt5_client.py` — `modify_position`, `partial_close`, `get_position` (broker-wrapper)

**Analog (verbatim shape):** `mt5_client.py:191-250` (`close_position`) — mirror retry decorator + positions_get + filling-mode resolve + retcode check.

**Existing `close_position` template** (mt5_client.py:190-250):
```python
@_retry(3)
def close_position(self, position_id: int) -> OrderResult:
    """Chiude esplicitamente la posizione con id dato senza aprirne una opposta."""
    positions = mt5.positions_get(ticket=position_id) or []
    if not positions:
        return OrderResult(success=False, error_message=f"position {position_id} non trovata")
    pos = positions[0]

    tick = mt5.symbol_info_tick(pos.symbol)
    if tick is None:
        return OrderResult(success=False,
                          error_message=f"symbol_info_tick failed per {pos.symbol}: {mt5.last_error()}")

    if pos.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": order_type,
        "position": int(position_id),
        "price": price,
        "deviation": 20,
        "comment": "phase16_close",
        "type_filling": self.resolve_filling_mode(pos.symbol),
        "type_time": mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(request)
    if result is None:
        return OrderResult(success=False,
                          error_message=f"order_send returned None: {mt5.last_error()}")
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info("Close position OK ticket=%s symbol=%s volume=%.4f order=%s",
                   position_id, pos.symbol, pos.volume, result.order)
        return OrderResult(success=True, order_id=result.order)
    return OrderResult(success=False,
                      error_message=f"close rejected retcode={result.retcode} comment={result.comment}")
```

**`modify_position` (NEW) — copy structure, change `action` to `TRADE_ACTION_SLTP`, drop `volume/type/price/deviation`:**
```python
@_retry(3)
def modify_position(self, position_id: int,
                    sl: float | None = None,
                    tp: float | None = None) -> OrderResult:
    positions = mt5.positions_get(ticket=position_id) or []
    if not positions:
        return OrderResult(success=False, error_message=f"position {position_id} non trovata")
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
        logger.info("Modify SL/TP OK ticket=%s sl=%s tp=%s", position_id, sl, tp)
        return OrderResult(success=True, order_id=result.order)
    return OrderResult(success=False,
                      error_message=f"modify rejected retcode={result.retcode} comment={result.comment}")
```

**`partial_close(position_id, lots)`:** Same as `close_position` but `volume=lots` instead of `pos.volume`; comment `"phase6_partial_close"`. Filling mode `resolve_filling_mode(pos.symbol)` → returns `ORDER_FILLING_RETURN` for TenTrade per CLAUDE.md.

**`get_position(position_id) -> PositionInfo | None`:** Thin wrapper:
```python
def get_position(self, position_id: int) -> PositionInfo | None:
    positions = mt5.positions_get(ticket=position_id) or []
    if not positions:
        return None
    p = positions[0]
    return PositionInfo(
        symbol=p.symbol, lots=p.volume,
        direction="BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
        entry_price=p.price_open, stop_loss=p.sl, take_profit=p.tp,
        profit=p.profit, ticket=int(getattr(p, "ticket", position_id)),
    )
```
Construction shape mirrors `mt5_client.py:74-84` (PositionInfo build inside `get_account_state`).

---

### `mcp/bar_source.py` (adapter, request-response)

**Analog:** `mt5_client.py:127-144` (`get_ohlc` shape) + `backtest/loader.py:1-50` (CSV loader entry point).

**Live path mirrors `Mt5Client.get_ohlc`:**
```python
@_retry(3)
def get_ohlc(self, symbol: str, timeframe: str, n_bars: int) -> list[dict]:
    tf = TIMEFRAME_MAP.get(timeframe.upper())
    if tf is None:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n_bars)
    # ... return list[dict] of bars
```

**CSV path mirrors Phase 1 loader entry:**
```python
# backtest/loader.py:26-50
def load_bars(path, symbol, timeframe, date_start=None, date_end=None) -> list[Bar]:
    df = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df["dt_source"] = pd.to_datetime(df["Data"] + " " + df["Ora"], format="%d/%m/%Y %H:%M:%S")
    # ... GMT-6 → UTC, sort, dedup
```

**Phase-6 BarSource.get pattern (D-D1 strict-< slice):**
```python
class BarSource:
    @staticmethod
    def get(symbol: str, tf: str, n: int,
            as_of_ts: str | None = None, mt5_client=None) -> list[dict]:
        if as_of_ts is None:
            if mt5_client is None:
                raise ValueError("mt5_client required for live mode")
            return mt5_client.get_ohlc(symbol, tf, n)
        bars = load_italian_csv(symbol, tf)  # Phase 1 entry — TBD module path
        ts_arr = [b["time"] for b in bars]   # int unix UTC ascending
        as_of_unix = int(datetime.fromisoformat(
            as_of_ts.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())
        cutoff = bisect_left(ts_arr, as_of_unix)   # strict < as_of_ts → no future leak
        if cutoff < n:
            raise ValueError(f"as_of_ts_warmup_insufficient: need {n} bars")
        if cutoff > len(ts_arr):
            raise ValueError(f"as_of_ts_out_of_range: {as_of_ts}")
        return bars[cutoff - n : cutoff]
```

**No analog for the strict-< slice math** — new pattern, but `bisect_left` semantic is stdlib-canonical.

---

### `mcp/job_queue.py` (service / async-worker, event-driven)

**No direct analog in repo.** New pattern. Use stdlib `concurrent.futures.ProcessPoolExecutor` (referenced by Phase 5 D-15 baseline orchestration). Reference excerpt from RESEARCH.md §Pattern 2 (already vetted by user).

**Critical constraint inherited from CLAUDE.md + Phase 5 D-15:** Worker function MUST NOT import `MetaTrader5` (not fork-safe). Worker entry point declared as **module-level function** in `mcp/handlers/backtest.py::_backtest_worker(...)` for picklability; uses ONLY `backtest.loader.load_italian_csv`, `backtest.engine.BacktestEngine`, `backtest.broker.BacktestBroker` (CSV-only path).

**SQLite WAL pattern (Phase 5 D-16, mirrored from `logger.py:62`):**
```python
with sqlite3.connect(db_path) as conn:
    conn.execute("PRAGMA journal_mode=WAL")
```
Apply on first connect inside `JobQueue.__init__`, in `_backtest_worker` first connect, in `trail_daemon.ensure_table`.

**`backtest_runs` row update pattern** mirrors `backtest/ledger.py:19-43` (existing schema unchanged; `status` field add already covered by Phase 1 D-07 via `started_at`/`finished_at` columns + Phase 6 may need `status TEXT` column add — verify before Wave 0).

---

### `mcp/trail_daemon.py` (service / scheduler-tick, CRUD + event-driven)

**Analogs (combined):**
- `logger.py:14-66` (table init pattern with `CREATE TABLE IF NOT EXISTS` + WAL).
- `mt5_client.py:67-101` (multi-position iteration via `mt5.positions_get()`).
- `indicators.py:1-60` (ATR computation reuse — `compute_atr` exists in module).

**Table init pattern** (logger.py:14-66, copy literally):
```python
_TRADES_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  ...
)
"""

def init_logger(cfg: Config) -> logging.Logger:
    # ...
    with sqlite3.connect(_db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_TRADES_LOG_SCHEMA)
        conn.commit()
```

**Phase-6 `position_trails` schema** (D-B2):
```python
_POSITION_TRAILS_SCHEMA = """
CREATE TABLE IF NOT EXISTS position_trails (
    position_id    INTEGER PRIMARY KEY,
    symbol         TEXT NOT NULL,
    direction      TEXT NOT NULL,
    timeframe      TEXT NOT NULL,
    atr_mult       REAL NOT NULL,
    last_sl        REAL NOT NULL,
    activated_at   TEXT NOT NULL,
    last_update_at TEXT,
    active         INTEGER NOT NULL DEFAULT 1
)
"""

def ensure_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_POSITION_TRAILS_SCHEMA)
        conn.commit()
```

**`trail_tick` body pattern (D-B2):** Iterate active rows, for each: `pos = mt5_client.get_position(pid)`; if None deactivate; else compute candidate `price ± atr * mult`, favorable check, `mt5_client.modify_position(pid, sl=candidate)`. Italian log: `log.info("trail tick: pos=%d new_sl=%.5f atr=%.5f mult=%.2f", ...)`.

---

### `scheduler.py` (trail_tick hook, scheduler-integration)

**Analog:** `scheduler.py:544-553` (`get_account_state` try/except + `_manage_open_positions(account_state, now)` invocation).

**Existing pattern (verbatim):**
```python
try:
    account_state = self.mt5.get_account_state()
except Exception as exc:
    self.log.exception("get_account_state fallito")
    outcome = "ERROR"
    err_type = type(exc).__name__
    err_msg = str(exc)
    return self._finish(hb_id, now, outcome, err_type, err_msg, "account_state_fail")

self._manage_open_positions(account_state, now)
```

**Phase-6 insertion (single line + try/except wrap, BEFORE `_manage_open_positions`):**
```python
try:
    from mcp.trail_daemon import trail_tick
    from logger import _trades_db_path
    trail_tick(self.mt5, str(_trades_db_path(cfg)), cfg)
except Exception:
    self.log.exception("trail_tick fallito (non blocca ciclo)")

self._manage_open_positions(account_state, now)
```

**Match quality:** exact — same try/except shape as scheduler.py:544-551 (project-canonical "non-fatal sub-step" pattern).

---

### `logger.py` (position_trails DDL, schema-bootstrap)

**Analog:** `logger.py:14-66` (existing `_TRADES_LOG_SCHEMA` + `init_logger` bootstrap).

**Pattern (copy literally):** add `_POSITION_TRAILS_SCHEMA` constant near `_TRADES_LOG_SCHEMA`, execute additional `conn.execute(_POSITION_TRAILS_SCHEMA)` inside the existing `with sqlite3.connect(_db_path) as conn:` block at logger.py:61-64.

**Alternative:** keep schema entirely inside `mcp/trail_daemon.py::ensure_table()` invoked at MCP server bootstrap (D-F4). Either is acceptable; planner picks one (D-E1 module discipline favors trail_daemon.ensure_table to keep `logger.py` minimal).

---

### `models.py` (TrailIntent dataclass, optional)

**Analog:** `models.py:7-65` (`TradeProposal`, `PositionInfo`, `OrderResult` dataclasses).

**Pattern (copy literally):**
```python
@dataclass
class TrailIntent:
    position_id: int
    symbol: str
    direction: str  # BUY | SELL
    timeframe: str
    atr_mult: float
    last_sl: float
    activated_at: str
    last_update_at: str | None = None
    active: bool = True
```

**Phase-6 use:** optional. SQLite row tuples or `sqlite3.Row` (logger.py:79 / mcp_server.py:380) suffice; only add dataclass if planner deems it cleaner. Match: existing project convention (`@dataclass`, `field(default_factory=...)`, `Literal` for enums).

---

### `config.py` (4 new env vars, config)

**Analog:** `config.py:60-80` (existing `Config` class with `os.getenv` calls).

**Pattern (mirror existing lines 67-74):**
```python
class Config:
    # ...
    # Phase 6 MCP
    MCP_MAX_CONCURRENT_RUNS: int = int(os.getenv("MCP_MAX_CONCURRENT_RUNS", "1"))
    MCP_DEFAULT_BARS: int = int(os.getenv("MCP_DEFAULT_BARS", "200"))
    TRAIL_TICK_TIMEFRAME: str = os.getenv("TRAIL_TICK_TIMEFRAME", "M15")
    TRAIL_FAVORABLE_ONLY: bool = _get_bool("TRAIL_FAVORABLE_ONLY", True)
```

**Match:** exact — uses existing `_get_bool` helper (config.py:7-11) for boolean env var.

---

### Test Files

#### `tests/test_mcp_handlers_market.py` / `_position.py` / `_proposal.py`

**Analog:** `tests/test_mcp_tools_v2.py:51-225` — autouse fixture that monkeypatches `mcp_server.mt5` and `mcp_server.cfg` with `MagicMock`.

**Fixture pattern** (test_mcp_tools_v2.py:51-70):
```python
@pytest.fixture(autouse=True)
def patch_mcp_singletons(monkeypatch):
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = _bullish_ohlc(100)
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=1.10000, ask=1.10010, point=0.00001, digits=5,
    )

    cfg = MagicMock()
    cfg.SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
    cfg.TIMEFRAME = "M15"
    # ...

    monkeypatch.setattr(mcp_server, "mt5", mt5)
    monkeypatch.setattr(mcp_server, "cfg", cfg)
    yield
```

**Async dispatch test** (test_mcp_tools_v2.py:194-208):
```python
def test_call_tool_dispatches_get_symbol_universe():
    result_blocks = asyncio.run(mcp_server.call_tool("get_symbol_universe", {}))
    assert len(result_blocks) == 1
    payload = json.loads(result_blocks[0].text)
    assert "symbols" in payload
    assert payload["count"] == 3
```

**Phase-6 use:** copy fixture verbatim; substitute `mcp_server` with `mcp.server` (post-split). Update `_bullish_ohlc(n)` factory to support 200-bar default. For `position` tests, MagicMock `mt5.modify_position`, `mt5.partial_close`, `mt5.get_position`, `mt5.get_symbol_info` (with `trade_stops_level=10, point=0.00001`).

#### `tests/test_mcp_trail_daemon.py` / `test_mcp_handlers_backtest.py` / `test_mcp_job_queue.py`

**Analog:** `tests/test_backtest_ledger.py:1-60` — `tmp_path` SQLite + DDL inspection + parameterized inserts.

**`tmp_path` SQLite pattern** (test_backtest_ledger.py:26-37):
```python
def test_schema_created(tmp_path: Path) -> None:
    db = tmp_path / "trades.db"
    LedgerWriter(db)  # ensure_schema runs in __init__
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"backtest_runs", "backtest_trades"}.issubset(tables)
```

**Phase-6 use:** `tests/test_mcp_trail_daemon.py::test_ensure_table_creates_schema(tmp_path)` mirrors this exactly. Tests for `register_trail`, `trail_tick(closed_position)`, `trail_tick(favorable)`, `trail_tick(non_favorable)` use MagicMock for `mt5_client` (return `None` for closed, return `PositionInfo(...)` for active). For `test_mcp_job_queue.py` test cancel via `MagicMock` Future + verify `backtest_runs.status='cancelled'` row update.

#### `tests/conftest.py` (extend MT5 stub)

**Analog:** `tests/conftest.py:14-40` — existing stub adds `TRADE_ACTION_SLTP` already (line 24), `positions_get` (line 38), `order_send` (line 38). No additions needed; verify stub is exhaustive for Phase 6 surface (`POSITION_TYPE_BUY`, `TRADE_RETCODE_DONE` already there).

---

## Shared Patterns (Cross-Cutting)

### Pattern A — JSON envelope + `_text` helper

**Source:** `mcp_server.py:61-62`
**Apply to:** every handler in `mcp/handlers/*.py`
```python
def _text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, default=str, ensure_ascii=False))]
```
**Note:** keep in `mcp/server.py` (or `mcp/__init__.py`); handlers return plain `dict`, server wraps via `_text(handler(args))` in dispatch.

### Pattern B — DRY_RUN gate (CLAUDE.md `EXECUTION_MODE=shadow`)

**Source:** `mcp_server.py:411-421` (close_position branch)
**Apply to:** every position-mutating handler — `modify_position`, `partial_close`, future Phase 8 trade-execution tools
```python
if cfg.DRY_RUN:
    log.info("MCP <tool> DRY_RUN ...", ...)
    return {"success": True, ..., "execution_mode": cfg.EXECUTION_MODE,
            "dry_run": True, "note": "DRY_RUN: nessun ordine inviato a MT5"}
```

### Pattern C — `_retry(3)` decorator on broker calls

**Source:** `mt5_client.py:26-39`
**Apply to:** all NEW `Mt5Client` methods (`modify_position`, `partial_close`, `get_position`)
```python
def _retry(n: int = 3):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(n):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    logger.warning("retry %d/%d for %s: %s", attempt + 1, n, fn.__name__, exc)
            raise last_exc
        return wrapper
    return decorator
```

### Pattern D — `resolve_filling_mode` (TenTrade ORDER_FILLING_RETURN)

**Source:** `mt5_client.py:110-124`
**Apply to:** `partial_close` (uses `TRADE_ACTION_DEAL`, needs filling). `modify_position` does NOT need it (`TRADE_ACTION_SLTP` ignores filling type per MQL5 spec).
```python
"type_filling": self.resolve_filling_mode(pos.symbol),
```

### Pattern E — Error envelope (D-F2 formalization)

**Source legacy:** `mcp_server.py:429-433` `{error: ..., tool: name}` (informal)
**Phase-6 new shape (D-F2):** `{ok: false, error: <code>, message: <human>, ...context}`
**Apply to:** every handler error path. Standardized codes inventory:
```python
# mcp/errors.py
class ErrorCodes:
    RUN_IN_PROGRESS         = "run_in_progress"
    UNKNOWN_RUN_ID          = "unknown_run_id"
    HISTORICAL_DATA_UNAVAILABLE = "historical_data_unavailable"
    STOPS_LEVEL_VIOLATION   = "stops_level_violation"
    AS_OF_TS_OUT_OF_RANGE   = "as_of_ts_out_of_range"
    AS_OF_TS_WARMUP_INSUFFICIENT = "as_of_ts_warmup_insufficient"
    PARTIAL_EXCEEDS_VOLUME  = "partial_exceeds_volume"
    POSITION_NOT_FOUND      = "position_not_found"
    BROKER_REJECTED         = "broker_rejected"
    MT5_NOT_READY           = "mt5_not_ready"
    NO_ACTIVE_RUN           = "no_active_run"
    DECISION_NOT_FOUND      = "decision_not_found"
    CONFLICT_TRAIL_AND_MANUAL_SL = "conflict: trail_and_manual_sl"
    CONFLICT_BE_AND_MANUAL_SL    = "conflict: be_and_manual_sl"
```

### Pattern F — SQLite WAL + `with sqlite3.connect(...) as`

**Source:** `logger.py:61-64`, `mcp_server.py:378-388`
**Apply to:** `mcp/job_queue.py`, `mcp/trail_daemon.py`, every worker subprocess first-connect, every read in `mcp/handlers/account.py::handle_get_trade_history`
```python
with sqlite3.connect(db_path) as conn:
    conn.execute("PRAGMA journal_mode=WAL")  # idempotent
    conn.row_factory = sqlite3.Row
    # ... query
```

### Pattern G — Italiano log/comment/rationale (CLAUDE.md)

**Source:** `mt5_client.py:192` (`"""Chiude esplicitamente la posizione..."""`), `mcp_server.py:413` (`"MCP close_position DRY_RUN ticket=%d (nessun ordine reale)"`), `scheduler.py:528` (`"Loop H24 terminato"`).
**Apply to:** every docstring, `log.info/warning/error` message text, error envelope `message` field. `inputSchema.description` (skill-facing) MAY remain English per MCP convention (also Phase 6 RESEARCH §Project Constraints line 117).

### Pattern H — Bootstrap singleton + lazy MT5 init (D-F4)

**Source:** `mcp_server.py:34-55` — `cfg`, `log`, `mt5` constructed at module import; `_bootstrap_mt5()` called only from `__main__`.
**Apply to:** `mcp/server.py` (verbatim move). Insert `JobQueue(...)` and `trail_daemon.ensure_table(...)` instantiation INSIDE `_bootstrap_mt5()` AFTER successful MT5 login — never at import time (so tests can `import mcp.server` without spawning ProcessPool).

### Pattern I — JSON-serializable response (test discipline)

**Source:** `tests/test_mcp_tools_v2.py:96, 124, 146, 175` — every handler test ends with `json.dumps(result)`.
**Apply to:** every new handler unit test. Detects accidental `datetime`, `numpy.float64`, dataclass leakage that would break MCP transport.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `mcp/job_queue.py` | service / async-worker | event-driven (futures) | First use of `ProcessPoolExecutor` registry in this repo. Phase 5 D-15 introduced ProcessPool for baseline orchestration but in a one-shot script context (`scripts/run_baseline_backtest.py`), not a long-lived registry. Pattern lives in CONTEXT/RESEARCH excerpt; planner copies that excerpt. |
| `mcp/bar_source.py` strict-< slice math | adapter | request-response | `bisect_left` cutoff is stdlib-canonical but no existing module slices CSV bars by ISO timestamp in this repo. Closest related code is `backtest/loader.py` (load_bars with `date_start`/`date_end` filtering), but that is calendar-range filtering, not point-in-time cutoff. Test pattern obligatory: insert bar at exact `as_of_unix`, assert NOT in returned slice. |

Both are explicitly anchored by RESEARCH.md (§Pattern 2, §Pattern 3) — planner uses those excerpts directly with no internal analog.

---

## Metadata

**Analog search scope:** root-level Python modules + `backtest/` + `tests/` + `mcp_server.py` + `scheduler.py` + `logger.py` + `models.py` + `config.py`.
**Files scanned:** 22 (mcp_server.py, mt5_client.py, logger.py, scheduler.py, indicators.py, models.py, config.py, backtest/{loader,ledger,walk_forward}.py, tests/{conftest,test_mcp_tools_v2,test_backtest_ledger}.py + 9 file listings).
**Pattern extraction date:** 2026-05-08

---

*Phase: 06-mcp-tools-part-1 — Pattern map ready for planner.*
