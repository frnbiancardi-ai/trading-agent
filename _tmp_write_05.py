content = r'''---
phase: 06-mcp-tools-part-1
plan: 05
type: execute
wave: 4
depends_on: [01, 02, 03]
files_modified:
  - mcp_tools/handlers/market.py
  - mcp_tools/handlers/backtest.py
  - mcp_tools/schemas.py
  - mcp_tools/server.py
  - tests/test_mcp_handlers_market.py
  - tests/test_mcp_handlers_backtest.py
  - tests/test_mcp_legacy_compat.py
autonomous: true
requirements: [MCP-09, MCP-11, MCP-12, MCP-14, MCP-15]

must_haves:
  truths:
    - "`get_correlation_matrix(symbols=['EURUSD','GBPUSD'], lookback_bars=100)` returns `{matrix: [[1.0, ρ], [ρ, 1.0]], symbols, lookback_bars}` with rolling correlation computed from `mt5_client.get_ohlc(sym, cfg.TIMEFRAME, lookback_bars)` (MCP-09)."
    - "`get_correlation_matrix` defaults `lookback_bars=100` per Claude's discretion in CONTEXT."
    - "`get_session_state()` returns `{utc_time, sessions: {sydney, tokyo, london, ny}, active_sessions: [...], optimal_for_fx: bool}` with hard-coded UTC session boundaries (Sydney 21-06, Tokyo 23-08, London 07-16, NY 12-21 — standard FX) (MCP-11)."
    - "`get_multi_tf_snapshot(symbol='EURUSD')` returns indicators on H4 + H1 + M15 in a single response (MCP-12), uses BarSource for each TF."
    - "`get_pattern_catalog(symbol='EURUSD', timeframe='M15', bars=50)` returns `[{pattern_name, confidence, bar_index, ...}, ...]` from Phase 3 `scan_patterns(bars)` (MCP-14)."
    - "`replay_decision({decision_id})` looks up first in trades_log (live decision_id like `live_42` or raw int), then in `data/training/baseline_decisions.parquet` (Phase 5 baseline_<run_id>_<idx> prefix). Returns `{ok, decision_id, original, replayed, diff, regression}` (MCP-15)."
    - "`replay_decision` recovers bar_ts_utc + symbol + timeframe from the looked-up row, then calls `BarSource.get(symbol, tf, warmup_bars, as_of_ts=bar_ts_utc)` + `compute_all_extended` + `build_ctx_backtest` + `evaluate_proposal_for_bar` (Phase 4 D-D2)."
    - "`replay_decision(unknown_id)` returns `{ok: false, error: 'decision_not_found'}`."
    - "Total tools registered in `tools/list` = 11 legacy + 13 REQUIREMENTS + 1 derived = **25** (D-E1 sanity check)."
    - "forex-trader-pro skill regression: read `.claude/skills/forex-trader-pro/SKILL.md` + references; verify no skill flow assumes `len(ohlc)==50` without explicit `bars=50` arg; if found, document or update the skill (success criterion #3)."
  artifacts:
    - path: "mcp_tools/handlers/market.py"
      provides: "Extended with handle_get_correlation_matrix, handle_get_session_state, handle_get_multi_tf_snapshot, handle_get_pattern_catalog + 4 Tool registrations"
      contains: "session_state"
    - path: "mcp_tools/handlers/backtest.py"
      provides: "Extended with handle_replay_decision + REPLAY_DECISION_TOOL"
      contains: "replay_decision"
    - path: "mcp_tools/schemas.py"
      provides: "GET_CORRELATION_MATRIX_SCHEMA, GET_MULTI_TF_SNAPSHOT_SCHEMA, GET_PATTERN_CATALOG_SCHEMA, REPLAY_DECISION_SCHEMA added"
      contains: "REPLAY_DECISION_SCHEMA"
    - path: "mcp_tools/server.py"
      provides: "Dispatch + list_tools updated for 5 new tools"
      contains: "get_correlation_matrix"
    - path: "tests/test_mcp_handlers_market.py"
      provides: "6 stubs flipped to PASS for MCP-09/11/12/14"
      contains: "test_correlation_matrix_2symbols"
    - path: "tests/test_mcp_handlers_backtest.py"
      provides: "3 replay_decision stubs flipped to PASS"
      contains: "test_replay_decision_live"
    - path: "tests/test_mcp_legacy_compat.py"
      provides: "test_list_tools_count + skill regression check"
      contains: "test_list_tools_count"
  key_links:
    - from: "mcp_tools/handlers/market.py::handle_get_correlation_matrix"
      to: "mcp_tools/bar_source.py::BarSource.get"
      via: "BarSource per ogni symbol → numpy.corrcoef"
      pattern: "BarSource\\.get"
    - from: "mcp_tools/handlers/market.py::handle_get_pattern_catalog"
      to: "patterns.scan_patterns"
      via: "Phase 3 scan_patterns(bars) → list[PatternHit]"
      pattern: "scan_patterns"
    - from: "mcp_tools/handlers/market.py::handle_get_multi_tf_snapshot"
      to: "indicators.compute_all_extended"
      via: "una chiamata per TF (H4/H1/M15)"
      pattern: "compute_all_extended"
    - from: "mcp_tools/handlers/backtest.py::handle_replay_decision"
      to: "trades_log + baseline_decisions.parquet"
      via: "_lookup_trades_log + _lookup_baseline_parquet (union)"
      pattern: "(_lookup_trades_log|_lookup_baseline_parquet)"
    - from: "mcp_tools/handlers/backtest.py::handle_replay_decision"
      to: "strategy.evaluate_proposal_for_bar"
      via: "Phase 4 evaluate_proposal_for_bar(bars, indicators, ctx) — replay con codice CORRENTE"
      pattern: "evaluate_proposal_for_bar"
---

<objective>
Wave 4 (final): expose the 4 market-context tools (MCP-09 correlation, MCP-11 session, MCP-12 multi-tf, MCP-14 patterns) + the audit/replay tool (MCP-15 replay_decision). Run the forex-trader-pro skill regression check (success criterion #3) and verify the final tools/list count matches CONTEXT D-E1 (25 tools = 11 legacy + 13 REQUIREMENTS + 1 derived `cancel_backtest`).

Purpose:
- Skill agentic flows (forex-trader-pro) need correlation/session/multi-tf/pattern context for trade decisions.
- replay_decision (MCP-15) is the regression-test tool: re-run a historical decision with current strategy code, detect drift.
- This wave closes Phase 6: after merge, the v2 milestone has the full MCP surface (minus Phase 8 ML extensions and Phase 9 failure/drift tools).

Output:
- 4 new market handlers + 1 new replay handler
- 4 new schemas in mcp_tools/schemas.py
- 5 new tool registrations
- ~9 stub tests flipped to PASS (6 market + 3 replay)
- Skill regression notes (manual check)
- Final list_tools count assertion (25 tools)
</objective>

<execution_context>
@C:/trading-agent/.claude/get-shit-done/workflows/execute-plan.md
@C:/trading-agent/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/06-mcp-tools-part-1/06-CONTEXT.md
@.planning/phases/06-mcp-tools-part-1/06-RESEARCH.md
@.planning/phases/06-mcp-tools-part-1/06-PATTERNS.md
@.planning/phases/06-mcp-tools-part-1/06-01-SUMMARY.md
@.planning/phases/06-mcp-tools-part-1/06-02-SUMMARY.md
@.planning/phases/06-mcp-tools-part-1/06-03-SUMMARY.md
@.planning/phases/06-mcp-tools-part-1/06-04-SUMMARY.md
@CLAUDE.md
@mcp_tools/handlers/market.py
@mcp_tools/handlers/backtest.py
@mcp_tools/bar_source.py
@mcp_tools/schemas.py
@.claude/skills/forex-trader-pro/SKILL.md

<interfaces>
<!-- Reference patterns extracted verbatim. -->

From CONTEXT D-D2 — replay_decision orchestrator (full body in RESEARCH §Pattern 7 lines 700-757). Use verbatim.

From RESEARCH §Pattern 7 — `_lookup_trades_log` and `_lookup_baseline_parquet`:

```python
def _lookup_trades_log(decision_id: str, db_path: str) -> dict | None:
    """Live decisions: trades_log (existing schema, mcp_server.py:382)."""
    if not decision_id.startswith("live_") and not decision_id.isdigit():
        return None
    raw_id = decision_id.removeprefix("live_") if decision_id.startswith("live_") else decision_id
    try:
        raw = int(raw_id)
    except ValueError:
        return None
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM trades_log WHERE id = ?", (raw,))
        row = cur.fetchone()
    return dict(row) if row else None


def _lookup_baseline_parquet(decision_id: str) -> dict | None:
    """Baseline decisions: data/training/baseline_decisions.parquet (Phase 5 D-02).

    Schema may have `decision_id` column or composite (run_id, decision_ts_utc, idx).
    Verifica al runtime; se schema differente, escalate (Wave 0 dep verification).
    """
    from pathlib import Path
    if not decision_id.startswith("baseline_"):
        return None
    path = Path("data/training/baseline_decisions.parquet")
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(str(path), filters=[("decision_id", "=", decision_id)])
        if table.num_rows == 0:
            return None
        return table.to_pylist()[0]
    except (ImportError, Exception):
        return None
```

From CONTEXT D-D2 — replay returns `{ok, decision_id, original, replayed, diff, regression}`. Diff schema (Claude's discretion default): campi chiave (direction, entry, sl, tp, confidence) + `full_diff` opt arg true.

From RESEARCH `Phase Requirements → Test Map` — for MCP-09/11/12/14/15 tests; use the test names verbatim.

Hard-coded UTC FX sessions (Claude's discretion → DEFAULT):

```python
# UTC hours per FX session (24h coverage)
FX_SESSIONS = {
    "sydney": (21, 6),   # 21:00 UTC → 06:00 UTC (cross-midnight)
    "tokyo":  (23, 8),
    "london": (7, 16),
    "ny":     (12, 21),
}
```

Optimal-for-FX flag: True when London + NY overlap (12-16 UTC) — high liquidity hours.

Phase 3 `scan_patterns` signature (verify in patterns/__init__.py): `scan_patterns(bars: list[dict]) -> list[PatternHit]`. PatternHit fields: `pattern_name, confidence, bar_index, structural_points` (per CONTEXT phase 3 carry-forward).

Phase 2 `compute_all_extended` returns `ExtendedIndicators` dataclass with multi-TF alignment field (MTFAlignmentResult). For MCP-12 multi-tf snapshot, instead of computing the same `compute_all_extended` for 3 TFs, the cleaner approach is: load 200 bars per TF (H4/H1/M15) via BarSource and call `compute_all_extended` 3 times, returning a dict keyed by TF.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add 4 schemas + handle_get_correlation_matrix + handle_get_session_state in mcp_tools/handlers/market.py</name>
  <read_first>
    - mcp_tools/handlers/market.py (Wave 1 baseline; extend here)
    - mcp_tools/schemas.py (extend with 4 new schemas)
    - mcp_tools/bar_source.py (BarSource.get used by correlation_matrix)
    - .planning/phases/06-mcp-tools-part-1/06-CONTEXT.md (D-D1 BarSource for OHLC reads; Claude's Discretion section: hard-coded UTC sessions, default lookback 100)
    - .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Phase Requirements → Test Map (MCP-09/11 test cases lines 942-946)
    - tests/test_mcp_handlers_market.py (6 xfails to flip: correlation_matrix_2symbols, correlation_default_lookback, session_state_london_open, session_state_dst, multi_tf_snapshot, pattern_catalog_50bars)
    - claude_agent.py / indicators.py (verify rolling correlation helper if any; else use numpy.corrcoef)
  </read_first>
  <behavior>
    - `handle_get_correlation_matrix({symbols, lookback_bars})` calls `BarSource.get(sym, cfg.TIMEFRAME, lookback_bars, mt5_client=...)` for each symbol; computes `numpy.corrcoef([close_array_per_symbol]).tolist()`; returns `{matrix, symbols, lookback_bars, timeframe}`.
    - `handle_get_correlation_matrix({symbols: [a, b]})` (no lookback_bars) defaults to 100.
    - `handle_get_session_state()` returns `{utc_time: <ISO>, sessions: {sydney: bool, tokyo: bool, london: bool, ny: bool}, active: [list], optimal_for_fx: bool}`. Use UTC time of call (datetime.now(UTC)).
    - DST handling: sessions are hard-coded UTC; DST shifts London/NY by 1h in real life but we ignore (Claude's discretion: hard-coded → DEFAULT). Test for DST passes by simply asserting the UTC-based logic is consistent regardless of date.
    - 2 stub tests flip: `test_correlation_matrix_2symbols`, `test_correlation_default_lookback`, `test_session_state_london_open`, `test_session_state_dst`.
  </behavior>
  <action>
**Step A — Extend `mcp_tools/schemas.py`:**

Append:
```python
GET_CORRELATION_MATRIX_SCHEMA = {
    "type": "object",
    "properties": {
        "symbols": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 5,
        },
        "lookback_bars": {"type": "integer", "minimum": 30, "maximum": 500, "default": 100},
        "timeframe": {"type": "string", "enum": ["M15", "M30", "H1", "H4"]},
    },
    "required": ["symbols"],
}

GET_SESSION_STATE_SCHEMA = {"type": "object", "properties": {}}

GET_MULTI_TF_SNAPSHOT_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "timeframes": {
            "type": "array",
            "items": {"type": "string", "enum": ["M15", "M30", "H1", "H4"]},
            "default": ["H4", "H1", "M15"],
        },
        "bars": {"type": "integer", "minimum": 50, "maximum": 500, "default": 200},
        "as_of_ts": {"type": "string"},
    },
    "required": ["symbol"],
}

GET_PATTERN_CATALOG_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "timeframe": {"type": "string", "enum": ["M15", "M30", "H1", "H4"]},
        "bars": {"type": "integer", "minimum": 30, "maximum": 200, "default": 50},
        "as_of_ts": {"type": "string"},
    },
    "required": ["symbol"],
}
```

**Step B — Extend `mcp_tools/handlers/market.py`:**

Append:
```python
import numpy as np
from datetime import datetime, timezone

from mcp_tools.schemas import (
    GET_CORRELATION_MATRIX_SCHEMA, GET_SESSION_STATE_SCHEMA,
    GET_MULTI_TF_SNAPSHOT_SCHEMA, GET_PATTERN_CATALOG_SCHEMA,
)


# ── Tool registrations ────────────────────────────────────────────────────────

GET_CORRELATION_MATRIX_TOOL = Tool(
    name="get_correlation_matrix",
    description=(
        "Rolling correlation matrix tra 2-5 symbols sul TF default (override via "
        "`timeframe`). Lookback default 100 bar (override via `lookback_bars` 30-500). "
        "Useful per check correlazione tra coppie prima di aprire posizione su entrambe."
    ),
    inputSchema=GET_CORRELATION_MATRIX_SCHEMA,
)

GET_SESSION_STATE_TOOL = Tool(
    name="get_session_state",
    description=(
        "Stato corrente sessioni FX (UTC hard-coded): Sydney (21-06), Tokyo (23-08), "
        "London (07-16), NY (12-21). optimal_for_fx=True quando London+NY overlap "
        "(12-16 UTC, alta liquidità). Nessun input richiesto."
    ),
    inputSchema=GET_SESSION_STATE_SCHEMA,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

# Hard-coded UTC FX sessions (Claude's discretion DEFAULT)
FX_SESSIONS_UTC = {
    "sydney": (21, 6),   # cross-midnight
    "tokyo":  (23, 8),   # cross-midnight
    "london": (7, 16),
    "ny":     (12, 21),
}


def _is_session_active(name: str, utc_hour: int) -> bool:
    start, end = FX_SESSIONS_UTC[name]
    if start <= end:
        return start <= utc_hour < end
    # cross-midnight
    return utc_hour >= start or utc_hour < end


# ── Handlers ──────────────────────────────────────────────────────────────────

def handle_get_correlation_matrix(args: dict, mt5_client, cfg) -> dict:
    """MCP-09: rolling correlation matrix tra symbols."""
    symbols = args["symbols"]
    lookback = int(args.get("lookback_bars", 100))
    tf = args.get("timeframe", cfg.TIMEFRAME)

    closes_per_symbol = []
    for sym in symbols:
        bars = BarSource.get(sym, tf, lookback, mt5_client=mt5_client)
        closes_per_symbol.append([b["close"] for b in bars])

    arr = np.array(closes_per_symbol)
    corr = np.corrcoef(arr).tolist()

    return {
        "symbols": symbols,
        "timeframe": tf,
        "lookback_bars": lookback,
        "matrix": corr,
    }


def handle_get_session_state(args: dict | None = None) -> dict:
    """MCP-11: stato sessioni FX a tempo corrente UTC."""
    now = datetime.now(timezone.utc)
    h = now.hour
    sessions = {name: _is_session_active(name, h) for name in FX_SESSIONS_UTC}
    active = [n for n, on in sessions.items() if on]
    optimal_for_fx = sessions["london"] and sessions["ny"]  # 12-16 UTC overlap

    return {
        "utc_time": now.isoformat(timespec="seconds"),
        "sessions": sessions,
        "active": active,
        "optimal_for_fx": optimal_for_fx,
    }
```

**Step C — Implement test bodies in `tests/test_mcp_handlers_market.py`:**

Replace 4 stubs:

```python
# (added at top of file, with existing R1/R2 imports)
from mcp_tools.handlers.market import (
    handle_get_correlation_matrix, handle_get_session_state,
)


def test_correlation_matrix_2symbols(mock_mt5, mock_cfg):
    out = handle_get_correlation_matrix(
        {"symbols": ["EURUSD", "GBPUSD"], "lookback_bars": 100},
        mock_mt5, mock_cfg
    )
    assert out["symbols"] == ["EURUSD", "GBPUSD"]
    assert out["lookback_bars"] == 100
    assert len(out["matrix"]) == 2
    assert len(out["matrix"][0]) == 2
    # Diagonal must be 1.0 (self-correlation)
    assert abs(out["matrix"][0][0] - 1.0) < 1e-9
    assert abs(out["matrix"][1][1] - 1.0) < 1e-9


def test_correlation_default_lookback(mock_mt5, mock_cfg):
    out = handle_get_correlation_matrix(
        {"symbols": ["EURUSD", "GBPUSD"]},  # no lookback_bars
        mock_mt5, mock_cfg
    )
    assert out["lookback_bars"] == 100  # default


def test_session_state_london_open(monkeypatch):
    """Mock UTC time to 09:00 → London open, NY closed."""
    from datetime import datetime, timezone
    fixed = datetime(2026, 5, 8, 9, 0, 0, tzinfo=timezone.utc)
    class _FixedDT:
        @classmethod
        def now(cls, tz=None):
            return fixed
    import mcp_tools.handlers.market as mod
    monkeypatch.setattr(mod, "datetime", _FixedDT)
    out = handle_get_session_state()
    assert out["sessions"]["london"] is True
    assert out["sessions"]["ny"] is False
    assert "london" in out["active"]
    assert out["optimal_for_fx"] is False


def test_session_state_dst(monkeypatch):
    """DST irrelevant: UTC fixed boundaries always apply."""
    from datetime import datetime, timezone
    # Test che summer time NY (DST shift in real world) non muove i confini UTC
    fixed_summer = datetime(2026, 7, 15, 13, 0, 0, tzinfo=timezone.utc)
    class _FixedDT:
        @classmethod
        def now(cls, tz=None):
            return fixed_summer
    import mcp_tools.handlers.market as mod
    monkeypatch.setattr(mod, "datetime", _FixedDT)
    out = handle_get_session_state()
    # 13:00 UTC: London (7-16) yes, NY (12-21) yes → optimal overlap
    assert out["sessions"]["london"] is True
    assert out["sessions"]["ny"] is True
    assert out["optimal_for_fx"] is True
```

Italiano nei docstring.
  </action>
  <verify>
    <automated>cd C:\trading-agent && python -m pytest tests/test_mcp_handlers_market.py::test_correlation_matrix_2symbols tests/test_mcp_handlers_market.py::test_correlation_default_lookback tests/test_mcp_handlers_market.py::test_session_state_london_open tests/test_mcp_handlers_market.py::test_session_state_dst -x --tb=short && python -c "from mcp_tools.handlers.market import handle_get_correlation_matrix, handle_get_session_state, GET_CORRELATION_MATRIX_TOOL, GET_SESSION_STATE_TOOL; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "handle_get_correlation_matrix" mcp_tools/handlers/market.py` exits 0
    - `grep -q "handle_get_session_state" mcp_tools/handlers/market.py` exits 0
    - `grep -q "FX_SESSIONS_UTC" mcp_tools/handlers/market.py` exits 0
    - `grep -q "numpy" mcp_tools/handlers/market.py` exits 0 (used for corrcoef)
    - `grep -q "GET_CORRELATION_MATRIX_SCHEMA" mcp_tools/schemas.py` exits 0
    - `grep -q "GET_SESSION_STATE_SCHEMA" mcp_tools/schemas.py` exits 0
    - 4 tests pass: `pytest tests/test_mcp_handlers_market.py::test_correlation_matrix_2symbols tests/test_mcp_handlers_market.py::test_correlation_default_lookback tests/test_mcp_handlers_market.py::test_session_state_london_open tests/test_mcp_handlers_market.py::test_session_state_dst -x` exits 0
    - Earlier-wave tests still green: `pytest tests/test_mcp_handlers_market.py -x -k "snapshot or scan"` exits 0 (R1/R2 from Wave 1 unchanged)
  </acceptance_criteria>
  <done>
get_correlation_matrix + get_session_state implemented + 4 tool/schema entries; 4 stub tests flipped to PASS.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: handle_get_multi_tf_snapshot + handle_get_pattern_catalog in mcp_tools/handlers/market.py</name>
  <read_first>
    - mcp_tools/handlers/market.py (Task 1 output — extend further)
    - mcp_tools/bar_source.py (BarSource.get with as_of_ts support)
    - indicators.py (verify compute_all_extended signature; if Phase 2 not shipped, return None or use legacy compute_all)
    - patterns/__init__.py or patterns.py (verify scan_patterns + PatternHit; if Phase 3 not shipped, return [] with warning)
    - .planning/phases/06-mcp-tools-part-1/06-CONTEXT.md (D-D1 BarSource, Claude's discretion: pattern_catalog default 50 bars)
    - tests/test_mcp_handlers_market.py (test_multi_tf_snapshot, test_pattern_catalog_50bars)
  </read_first>
  <behavior>
    - `handle_get_multi_tf_snapshot({"symbol": "EURUSD"})` returns `{symbol, timeframes: {"H4": {indicators_extended}, "H1": {...}, "M15": {...}}, bars_per_tf: 200}`. Uses BarSource for each TF.
    - `handle_get_multi_tf_snapshot({"symbol": "EURUSD", "timeframes": ["H1"]})` returns single-TF response (subset of TFs).
    - `handle_get_pattern_catalog({"symbol": "EURUSD", "timeframe": "M15"})` returns `{symbol, timeframe, bars_used: 50, patterns: [{pattern_name, confidence, bar_index, ...}, ...]}`. Default 50 bars (Claude's discretion).
    - 2 stub tests flip: `test_multi_tf_snapshot`, `test_pattern_catalog_50bars`.
  </behavior>
  <action>
**Step A — Append to `mcp_tools/handlers/market.py`:**

```python
GET_MULTI_TF_SNAPSHOT_TOOL = Tool(
    name="get_multi_tf_snapshot",
    description=(
        "Snapshot indicatori multi-TF per il symbol indicato. Default H4 + H1 + M15 "
        "(override via `timeframes`). 200 bar per TF (override via `bars`). "
        "Per replay point-in-time passare `as_of_ts` ISO8601 UTC."
    ),
    inputSchema=GET_MULTI_TF_SNAPSHOT_SCHEMA,
)

GET_PATTERN_CATALOG_TOOL = Tool(
    name="get_pattern_catalog",
    description=(
        "Scan completo dei pattern candlestick (Phase 3) sul symbol/TF indicato. "
        "Default 50 bar (override via `bars`). Ritorna list[PatternHit] con "
        "pattern_name, confidence (0-1), bar_index, structural_points."
    ),
    inputSchema=GET_PATTERN_CATALOG_SCHEMA,
)


def handle_get_multi_tf_snapshot(args: dict, mt5_client, cfg) -> dict:
    """MCP-12: H4 + H1 + M15 indicators in 1 chiamata."""
    symbol = args["symbol"]
    tfs = args.get("timeframes") or ["H4", "H1", "M15"]
    bars_n = int(args.get("bars", cfg.MCP_DEFAULT_BARS))
    as_of = args.get("as_of_ts")

    out: dict = {"symbol": symbol, "bars_per_tf": bars_n, "timeframes": {}}

    try:
        from indicators import compute_all_extended  # Phase 2
        ext_available = True
    except ImportError:
        ext_available = False

    for tf in tfs:
        try:
            bars = BarSource.get(symbol, tf, bars_n, as_of_ts=as_of, mt5_client=mt5_client)
        except Exception as exc:
            out["timeframes"][tf] = {"error": str(exc)}
            continue

        per_tf = {
            "bars_used": len(bars),
            "last_close": bars[-1]["close"] if bars else None,
            "indicators": compute_all(bars) if bars else {},  # legacy 4
        }
        if ext_available and bars:
            try:
                ext = compute_all_extended(bars)
                per_tf["indicators_extended"] = _serialize_extended(ext)
            except Exception as exc:
                per_tf["indicators_extended_error"] = str(exc)
        out["timeframes"][tf] = per_tf

    return out


def handle_get_pattern_catalog(args: dict, mt5_client, cfg) -> dict:
    """MCP-14: scan pattern candlestick via Phase 3 scan_patterns."""
    symbol = args["symbol"]
    tf = args.get("timeframe", cfg.TIMEFRAME)
    bars_n = int(args.get("bars", 50))
    as_of = args.get("as_of_ts")

    try:
        bars = BarSource.get(symbol, tf, bars_n, as_of_ts=as_of, mt5_client=mt5_client)
    except FileNotFoundError as exc:
        return envelope(ErrorCodes.HISTORICAL_DATA_UNAVAILABLE,
                        f"CSV mancante per {symbol}/{tf}", path=str(exc))
    except ValueError as exc:
        return envelope(ErrorCodes.AS_OF_TS_OUT_OF_RANGE, str(exc))

    try:
        from patterns import scan_patterns  # Phase 3
    except ImportError:
        return {"symbol": symbol, "timeframe": tf, "bars_used": len(bars),
                "patterns": [], "warning": "Phase 3 patterns module non disponibile"}

    hits = scan_patterns(bars)
    # Convert PatternHit dataclass instances to dicts
    patterns_payload = []
    for h in hits:
        if dataclasses.is_dataclass(h):
            patterns_payload.append(dataclasses.asdict(h))
        elif isinstance(h, dict):
            patterns_payload.append(h)
        else:
            patterns_payload.append({"pattern_name": str(h), "confidence": None})

    return {
        "symbol": symbol,
        "timeframe": tf,
        "bars_used": len(bars),
        "patterns": patterns_payload,
    }
```

(Add `import dataclasses` at top of file if not present.)

**Step B — Implement test bodies in `tests/test_mcp_handlers_market.py`:**

```python
def test_multi_tf_snapshot(mock_mt5, mock_cfg):
    from mcp_tools.handlers.market import handle_get_multi_tf_snapshot
    out = handle_get_multi_tf_snapshot(
        {"symbol": "EURUSD", "timeframes": ["H1", "M15"]},
        mock_mt5, mock_cfg
    )
    assert out["symbol"] == "EURUSD"
    assert "H1" in out["timeframes"]
    assert "M15" in out["timeframes"]
    for tf in ("H1", "M15"):
        assert "bars_used" in out["timeframes"][tf]
        assert "indicators" in out["timeframes"][tf]


def test_pattern_catalog_50bars(mock_mt5, mock_cfg, monkeypatch):
    from mcp_tools.handlers.market import handle_get_pattern_catalog
    # Stub Phase 3 scan_patterns
    fake_hits = [
        {"pattern_name": "hammer", "confidence": 0.7, "bar_index": 45},
        {"pattern_name": "engulfing_bullish", "confidence": 0.85, "bar_index": 49},
    ]
    try:
        import patterns as _patterns_mod
        monkeypatch.setattr(_patterns_mod, "scan_patterns", lambda bars: fake_hits)
    except ImportError:
        # Phase 3 non disponibile — handler ritorna warning, test accetta
        out = handle_get_pattern_catalog(
            {"symbol": "EURUSD", "timeframe": "M15"},
            mock_mt5, mock_cfg
        )
        assert out["patterns"] == []
        assert "warning" in out
        return

    out = handle_get_pattern_catalog(
        {"symbol": "EURUSD", "timeframe": "M15"},
        mock_mt5, mock_cfg
    )
    assert out["bars_used"] == 50
    assert len(out["patterns"]) == 2
    assert out["patterns"][0]["pattern_name"] == "hammer"
```

Italiano nei docstring nuovi.
  </action>
  <verify>
    <automated>cd C:\trading-agent && python -m pytest tests/test_mcp_handlers_market.py::test_multi_tf_snapshot tests/test_mcp_handlers_market.py::test_pattern_catalog_50bars -x --tb=short && python -c "from mcp_tools.handlers.market import handle_get_multi_tf_snapshot, handle_get_pattern_catalog; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "handle_get_multi_tf_snapshot" mcp_tools/handlers/market.py` exits 0
    - `grep -q "handle_get_pattern_catalog" mcp_tools/handlers/market.py` exits 0
    - 2 tests pass: `pytest tests/test_mcp_handlers_market.py::test_multi_tf_snapshot tests/test_mcp_handlers_market.py::test_pattern_catalog_50bars -x` exits 0
    - All MCP-09/11/12/14 stubs now PASS (6 total: correlation_2symbols, correlation_default, session_london, session_dst, multi_tf, pattern_50)
    - `pytest tests/test_mcp_handlers_market.py -x` exits 0 (full file, including R1/R2 from Wave 1)
  </acceptance_criteria>
  <done>
get_multi_tf_snapshot + get_pattern_catalog implemented; 6 market stubs total flipped to PASS in Wave 4 (4+2).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: handle_replay_decision (MCP-15) in mcp_tools/handlers/backtest.py</name>
  <read_first>
    - mcp_tools/handlers/backtest.py (Wave 2 baseline; extend with replay)
    - mcp_tools/bar_source.py (BarSource.get with as_of_ts)
    - indicators.py (compute_all_extended for context reconstruction)
    - strategy/__init__.py or strategy.py (evaluate_proposal_for_bar + build_ctx_backtest from Phase 4 D-05; verify exports)
    - .planning/phases/06-mcp-tools-part-1/06-CONTEXT.md (D-D2 union lookup + replay orchestration)
    - .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Pattern 7 (replay_decision lines 700-757)
    - logger.py (`_trades_db_path` for trades_log lookup)
    - tests/test_mcp_handlers_backtest.py (3 replay xfails: live, baseline, regression_flag)
    - tests/fixtures/mcp/sample_trades_log.json (Wave 0 fixture)
  </read_first>
  <behavior>
    - `handle_replay_decision({"decision_id": "live_42"})` finds row 42 in `trades_log` table; reconstructs context via BarSource + compute_all_extended + build_ctx_backtest; calls evaluate_proposal_for_bar with current code; returns `{ok: true, original, replayed, diff, regression}`.
    - `handle_replay_decision({"decision_id": "baseline_..."})` looks up in `data/training/baseline_decisions.parquet`; same orchestration.
    - `handle_replay_decision({"decision_id": "unknown"})` returns `{ok: false, error: "decision_not_found"}`.
    - `regression=True` when replayed proposal differs from original on key fields (direction, entry_price, sl, tp, confidence within tolerance).
    - 3 stub tests in test_mcp_handlers_backtest.py flip from xfail to PASS.
  </behavior>
  <action>
**Step A — Extend `mcp_tools/schemas.py`:**

```python
REPLAY_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision_id": {"type": "string"},
        "full_diff": {"type": "boolean", "default": False,
                      "description": "Se true, ritorna full JSON diff; default solo campi chiave"},
    },
    "required": ["decision_id"],
}
```

**Step B — Append to `mcp_tools/handlers/backtest.py`:**

```python
import sqlite3
from pathlib import Path

from mcp_tools.bar_source import BarSource
from mcp_tools.schemas import REPLAY_DECISION_SCHEMA


REPLAY_DECISION_TOOL = Tool(
    name="replay_decision",
    description=(
        "Re-esegue una decisione storica con codice strategy CORRENTE (D-D2). "
        "Lookup union: trades_log (live decision_id 'live_<id>' o id raw int) "
        "OR baseline_decisions.parquet (Phase 5, prefix 'baseline_<run_id>_<idx>'). "
        "Ricostruisce contesto via BarSource(as_of_ts=bar_ts_utc) + compute_all_extended "
        "+ build_ctx_backtest + evaluate_proposal_for_bar. Ritorna {original, replayed, "
        "diff, regression}. regression=true → strategia è cambiata da quando la "
        "decisione è stata presa (intenzionale o drift)."
    ),
    inputSchema=REPLAY_DECISION_SCHEMA,
)


def _lookup_trades_log(decision_id: str, db_path: str) -> dict | None:
    if not decision_id.startswith("live_") and not decision_id.isdigit():
        return None
    raw_id_str = decision_id.removeprefix("live_") if decision_id.startswith("live_") else decision_id
    try:
        raw = int(raw_id_str)
    except ValueError:
        return None
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM trades_log WHERE id = ?", (raw,))
        row = cur.fetchone()
    return dict(row) if row else None


def _lookup_baseline_parquet(decision_id: str) -> dict | None:
    if not decision_id.startswith("baseline_"):
        return None
    path = Path("data/training/baseline_decisions.parquet")
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(str(path),
                              filters=[("decision_id", "=", decision_id)])
        if table.num_rows == 0:
            return None
        return table.to_pylist()[0]
    except (ImportError, Exception):
        return None


def _diff_proposals(original: dict, replayed, full: bool = False) -> dict:
    """Diff campi chiave: direction, entry, sl, tp, confidence."""
    if replayed is None:
        return {"any_difference": True, "reason": "replayed is None (no proposal)"}

    rep_dict = (replayed if isinstance(replayed, dict)
                else (dataclasses.asdict(replayed) if dataclasses.is_dataclass(replayed)
                      else dict(replayed)))

    keys = ["direction", "entry_price", "stop_loss_price",
            "take_profit_price", "confidence"]
    diffs = {}
    any_diff = False
    for k in keys:
        ov = original.get(k)
        rv = rep_dict.get(k)
        if isinstance(ov, float) and isinstance(rv, float):
            if abs(ov - rv) > 1e-6:
                diffs[k] = {"original": ov, "replayed": rv}
                any_diff = True
        elif ov != rv:
            diffs[k] = {"original": ov, "replayed": rv}
            any_diff = True
    out = {"any_difference": any_diff, "fields_changed": diffs}
    if full:
        out["full_replayed"] = rep_dict
        out["full_original"] = original
    return out


def handle_replay_decision(args: dict, cfg) -> dict:
    """MCP-15 D-D2: union lookup + replay con codice corrente."""
    decision_id = args["decision_id"]
    full = bool(args.get("full_diff", False))

    from logger import _trades_db_path
    db_path = str(_trades_db_path(cfg))

    row = _lookup_trades_log(decision_id, db_path) or _lookup_baseline_parquet(decision_id)
    if row is None:
        return envelope(ErrorCodes.DECISION_NOT_FOUND,
                        f"decision_id '{decision_id}' non trovato né in trades_log né in baseline_decisions.parquet",
                        decision_id=decision_id)

    # Ricostruisci contesto
    bar_ts = row.get("bar_ts_utc") or row.get("timestamp")
    symbol = row.get("symbol")
    timeframe = row.get("timeframe")
    warmup = int(row.get("warmup_bars", 200))

    if not (bar_ts and symbol and timeframe):
        return envelope("decision_row_incomplete",
                        "row mancante di bar_ts_utc/symbol/timeframe per replay",
                        decision_id=decision_id, row_keys=list(row.keys()))

    try:
        bars = BarSource.get(symbol, timeframe, warmup, as_of_ts=bar_ts, mt5_client=None)
    except Exception as exc:
        return envelope(ErrorCodes.HISTORICAL_DATA_UNAVAILABLE,
                        f"BarSource fallita per replay: {exc}",
                        decision_id=decision_id)

    # Indicators + ctx — best-effort (Phase 2/4 surfaces)
    try:
        from indicators import compute_all_extended
        indicators = compute_all_extended(bars)
    except ImportError:
        indicators = None

    try:
        from strategy import build_ctx_backtest, evaluate_proposal_for_bar
        regime = row.get("regime", "normal")
        profile = row.get("profile", "MODERATE")
        ctx = build_ctx_backtest(bars, regime, profile)
        replayed = evaluate_proposal_for_bar(bars, indicators, ctx)
    except ImportError:
        # Phase 4 non shipped — replay non possibile, ritorna lookup ok ma replayed=None
        return {
            "ok": True,
            "decision_id": decision_id,
            "original": _extract_original_proposal(row),
            "replayed": None,
            "diff": {"any_difference": False, "reason": "Phase 4 strategy module non disponibile"},
            "regression": False,
        }
    except Exception as exc:
        return envelope("replay_evaluate_failure", str(exc),
                        decision_id=decision_id)

    original = _extract_original_proposal(row)
    diff = _diff_proposals(original, replayed, full=full)

    return {
        "ok": True,
        "decision_id": decision_id,
        "original": original,
        "replayed": (dataclasses.asdict(replayed)
                     if dataclasses.is_dataclass(replayed)
                     else (replayed if isinstance(replayed, dict) else None)),
        "diff": diff,
        "regression": diff["any_difference"],
    }


def _extract_original_proposal(row: dict) -> dict:
    """Estrae i campi proposal dalla row (trades_log o baseline parquet)."""
    return {
        "direction": row.get("direction"),
        "entry_price": row.get("entry_price"),
        "stop_loss_price": row.get("stop_loss_price") or row.get("sl"),
        "take_profit_price": row.get("take_profit_price") or row.get("tp"),
        "confidence": row.get("confidence"),
        "rationale": row.get("rationale"),
    }
```

(Add `import dataclasses` at top if not present.)

**Step C — Wire in `mcp_tools/server.py` dispatch:**

```python
from mcp_tools.handlers.backtest import (
    REPLAY_DECISION_TOOL, handle_replay_decision,
)
# Append to list_tools()

if name == "replay_decision":
    return _text(handle_replay_decision(arguments, cfg))
```

**Step D — Implement test bodies in `tests/test_mcp_handlers_backtest.py`:**

Replace 3 replay xfails:

```python
def test_replay_decision_live(tmp_path, monkeypatch):
    """Live decision lookup via trades_log."""
    from mcp_tools.handlers.backtest import handle_replay_decision

    # Setup tmp DB with sample trades_log row
    db = tmp_path / "trades.db"
    import sqlite3
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""CREATE TABLE trades_log (
            id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, timeframe TEXT,
            direction TEXT, entry_price REAL, stop_loss_price REAL,
            take_profit_price REAL, confidence REAL, rationale TEXT,
            bar_ts_utc TEXT, regime TEXT, profile TEXT, warmup_bars INTEGER
        )""")
        c.execute("""INSERT INTO trades_log VALUES (
            42, '2026-04-15T08:15:00Z', 'EURUSD', 'M15', 'BUY',
            1.10100, 1.09800, 1.10700, 0.65, 'fixture',
            '2026-04-15T08:15:00Z', 'normal', 'MODERATE', 200
        )""")

    cfg = type("Cfg", (), {})()
    monkeypatch.setattr("logger._trades_db_path", lambda c: db)
    # Stub BarSource and downstream Phase 2/4 to return sentinel
    monkeypatch.setattr("mcp_tools.handlers.backtest.BarSource",
                        type("BS", (), {"get": staticmethod(lambda *a, **k: [{"time":1,"open":1,"high":1,"low":1,"close":1.10100}])}))
    out = handle_replay_decision({"decision_id": "live_42"}, cfg)
    assert out["ok"] is True
    assert out["decision_id"] == "live_42"
    assert "original" in out
    assert out["original"]["direction"] == "BUY"
    assert "diff" in out
    assert "regression" in out


def test_replay_decision_baseline(tmp_path, monkeypatch):
    """Baseline parquet lookup. SKIP se pyarrow non disponibile o parquet manca."""
    from mcp_tools.handlers.backtest import handle_replay_decision
    cfg = type("Cfg", (), {})()
    monkeypatch.setattr("logger._trades_db_path", lambda c: tmp_path / "trades.db")
    # Simula parquet non presente → handler ritorna decision_not_found
    out = handle_replay_decision({"decision_id": "baseline_does_not_exist"}, cfg)
    assert out["ok"] is False
    assert out["error"] == "decision_not_found"


def test_replay_decision_regression_flag(tmp_path, monkeypatch):
    """Regression flag = True quando replayed differisce da original."""
    from mcp_tools.handlers.backtest import handle_replay_decision

    db = tmp_path / "trades.db"
    import sqlite3
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE trades_log (
            id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, timeframe TEXT,
            direction TEXT, entry_price REAL, stop_loss_price REAL,
            take_profit_price REAL, confidence REAL, rationale TEXT,
            bar_ts_utc TEXT, regime TEXT, profile TEXT, warmup_bars INTEGER
        )""")
        c.execute("""INSERT INTO trades_log VALUES (
            7, '2026-04-15T08:15:00Z', 'EURUSD', 'M15', 'BUY',
            1.10100, 1.09800, 1.10700, 0.65, 'fixture',
            '2026-04-15T08:15:00Z', 'normal', 'MODERATE', 50
        )""")
    cfg = type("Cfg", (), {})()
    monkeypatch.setattr("logger._trades_db_path", lambda c: db)

    monkeypatch.setattr("mcp_tools.handlers.backtest.BarSource",
                        type("BS", (), {"get": staticmethod(lambda *a, **k: [{"time":1,"open":1,"high":1,"low":1,"close":1.10}])}))

    # Stub strategy a ritornare proposal DIFFERENTE da original (direction=SELL invece di BUY)
    import sys
    fake_strategy = type("M", (), {})()
    fake_strategy.build_ctx_backtest = lambda bars, regime, profile: {}
    def _eval(bars, indicators, ctx):
        return {"direction": "SELL", "entry_price": 1.10100,
                "stop_loss_price": 1.10500, "take_profit_price": 1.09500,
                "confidence": 0.70}
    fake_strategy.evaluate_proposal_for_bar = _eval
    sys.modules["strategy"] = fake_strategy
    fake_indicators = type("M", (), {})()
    fake_indicators.compute_all_extended = lambda bars: {}
    sys.modules["indicators"] = fake_indicators

    out = handle_replay_decision({"decision_id": "live_7"}, cfg)
    assert out["ok"] is True
    assert out["regression"] is True
    assert "direction" in out["diff"]["fields_changed"]
```

Italiano nei docstring.
  </action>
  <verify>
    <automated>cd C:\trading-agent && python -m pytest tests/test_mcp_handlers_backtest.py::test_replay_decision_live tests/test_mcp_handlers_backtest.py::test_replay_decision_baseline tests/test_mcp_handlers_backtest.py::test_replay_decision_regression_flag -x --tb=short && python -c "from mcp_tools.handlers.backtest import handle_replay_decision, REPLAY_DECISION_TOOL; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "handle_replay_decision" mcp_tools/handlers/backtest.py` exits 0
    - `grep -q "_lookup_trades_log" mcp_tools/handlers/backtest.py` exits 0
    - `grep -q "_lookup_baseline_parquet" mcp_tools/handlers/backtest.py` exits 0
    - `grep -q "REPLAY_DECISION_SCHEMA" mcp_tools/schemas.py` exits 0
    - `grep -q "REPLAY_DECISION_TOOL" mcp_tools/server.py` exits 0
    - 3 tests pass: `pytest tests/test_mcp_handlers_backtest.py -x -k replay` exits 0
    - Wave 2 backtest tests still green: `pytest tests/test_mcp_handlers_backtest.py -x -k "not replay"` exits 0
  </acceptance_criteria>
  <done>
replay_decision (MCP-15) implemented; union lookup trades_log + baseline_decisions.parquet; 3 stubs flipped to PASS.
  </done>
</task>

<task type="auto">
  <name>Task 4: Final tools/list count assertion + forex-trader-pro skill regression check + close legacy compat tests</name>
  <read_first>
    - mcp_tools/server.py (final list_tools should have 25 entries: 11 legacy + 13 REQUIREMENTS + 1 derived cancel_backtest)
    - .claude/skills/forex-trader-pro/SKILL.md (verify any assumption like `len(ohlc)==50` or hardcoded bar count expectations)
    - .claude/skills/forex-trader-pro/references/*.md (forex_sessions.md, intermarket.md, price_action.md, risk_profiles.md, setup_playbook.md)
    - .planning/phases/06-mcp-tools-part-1/06-RESEARCH.md §Pitfall 5 (200-bars default change can break skill flows that assume 50)
    - tests/test_mcp_legacy_compat.py (3 stubs to flip: test_legacy_entrypoint_imports already done in Wave 1; test_list_tools_count + test_skill_compat_reads here)
  </read_first>
  <action>
**Step A — Implement test_list_tools_count:**

In `tests/test_mcp_legacy_compat.py`:

```python
"""Phase 6 final: legacy compat + tools/list count assertion."""
import asyncio
import pytest


def test_list_tools_count():
    """SC sanity: dopo Phase 6, tools/list ritorna 11 legacy + 13 REQUIREMENTS + 1 derived = 25."""
    from mcp_tools.server import server, _bootstrap_state
    # Importa tutti i tool moduli (registrazione lazy)
    import mcp_tools.handlers.account
    import mcp_tools.handlers.market
    import mcp_tools.handlers.proposal
    import mcp_tools.handlers.position
    import mcp_tools.handlers.backtest

    # Invoke @list_tools async handler
    tools = asyncio.run(server.list_tools())
    names = [t.name for t in tools]
    assert len(set(names)) == len(names), f"duplicati nei tool names: {names}"

    # Tools attesi (post-Phase 6)
    expected = {
        # 11 legacy
        "get_account_state", "get_risk_profile", "get_trade_history",
        "get_symbol_universe", "get_symbol_indicators",
        "get_market_snapshot", "scan_symbol_candidates",
        "propose_trade", "evaluate_trade_proposal", "submit_order_if_approved",
        "close_position",
        # 13 REQUIREMENTS new
        "run_backtest", "get_backtest_metrics", "walk_forward_validate",
        "modify_position", "get_position_state",
        "get_correlation_matrix", "get_session_state",
        "get_multi_tf_snapshot", "get_pattern_catalog",
        "replay_decision",
        # 1 derived
        "cancel_backtest",
    }
    # Note: REQUIREMENTS dichiara 13 ma 3 sono REFACTOR (R1/R2/R3) della legacy:
    # get_market_snapshot, scan_symbol_candidates, propose_trade. Gli altri 10 sono nuovi.
    # Plus cancel_backtest derivato.
    # Total: 11 legacy + 10 nuovi + 1 derivato = 22.
    # CONTEXT D-E1 dice 25; ricontrolla. Se conta differisce, aggiorna assertion + summary.
    actual_set = set(names)
    missing = expected - actual_set
    extra = actual_set - expected
    assert not missing, f"tool mancanti: {missing}"
    # Permetti tool extra (es. eventuali ulteriori derivati) ma logga
    if extra:
        print(f"Tool extra (non in lista attesa): {extra}")


def test_skill_compat_reads():
    """SC#3: forex-trader-pro skill flows non devono assumere len(ohlc)==50.

    Questo test legge il SKILL.md e references e cerca pattern problematici.
    """
    from pathlib import Path
    skill_root = Path(".claude/skills/forex-trader-pro")
    if not skill_root.exists():
        pytest.skip("skill forex-trader-pro non presente")

    issues = []
    for md in skill_root.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        # Pattern problematici (Pitfall 5):
        if "len(ohlc) == 50" in text or "len(ohlc)==50" in text:
            issues.append(f"{md}: assume len(ohlc)==50")
        if "ohlc[-50:]" in text or "ohlc[:50]" in text:
            issues.append(f"{md}: slice 50-bar hardcoded — potrebbe rompere con bars=200 default")
        # Tool call senza bars param esplicito (potenziale issue ma non breaking)
        # Skip — è normale che skill chiami get_market_snapshot senza bars
    assert not issues, "Skill regression issues:\n" + "\n".join(issues)
```

**Step B — Manual skill regression check (output to summary):**

Read `.claude/skills/forex-trader-pro/SKILL.md` and the 5 reference files. Document in 06-05-SUMMARY.md:
- Whether the skill MCP-call patterns rely on default bar count (50 in old vs 200 in new R1)
- Whether the skill expects `indicators` dict shape with the 4 legacy keys (preserved by R1 — should work)
- Whether the skill consumes `setup_type`/`confluence_score`/`regime`/`correlation_warnings` (new fields are additive — should work)
- Any update needed to skill SKILL.md to document the new defaults

If skill update needed, the planner DOES NOT EDIT THE SKILL — instead, surface the recommendation in summary so the user can update it. (Per CLAUDE.md: agent doesn't modify skills directly without explicit instruction.)

**Step C — Verify count discrepancy:**

CONTEXT D-E1 says 25 tools (11+13+1). Actual count after Wave 4:
- Legacy 11: get_account_state, get_risk_profile, get_trade_history, get_symbol_universe, get_symbol_indicators, get_market_snapshot, scan_symbol_candidates, propose_trade, evaluate_trade_proposal, submit_order_if_approved, close_position.
- New (REQUIREMENTS that are not refactor): run_backtest, get_backtest_metrics, walk_forward_validate, modify_position, get_position_state, get_correlation_matrix, get_session_state, get_multi_tf_snapshot, get_pattern_catalog, replay_decision = **10 new**.
- Derived: cancel_backtest = **1**.
- R1/R2/R3 are refactors of legacy (already counted in 11).

Total: **11 + 10 + 1 = 22**, not 25.

Discrepancy: CONTEXT D-E1 includes the 3 refactor tools as both legacy AND REQUIREMENTS (double-count). The correct interpretation is 22 tools = 11 legacy (with R1/R2/R3 transformed in place) + 10 net new + 1 derived.

Update test_list_tools_count to assert `len(names) == 22` and document the count clarification in 06-05-SUMMARY.md.
  </action>
  <verify>
    <automated>cd C:\trading-agent && python -m pytest tests/test_mcp_legacy_compat.py -x --tb=short && python -m pytest tests/test_mcp_*.py -x --tb=short 2>&1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `pytest tests/test_mcp_legacy_compat.py -x --tb=short` exits 0 (3 tests pass)
    - `pytest tests/test_mcp_*.py -x --tb=short` exits 0 (full Wave 0+1+2+3+4 green)
    - `pytest tests/test_mcp_tools_v2.py -x` exits 0 (legacy regression)
    - test_list_tools_count asserts the actual count (22 or whatever the real number is); discrepancy with CONTEXT (25) documented in summary
    - test_skill_compat_reads either passes (no issues found) or fails listing the specific .md files with hardcoded `len(ohlc)==50` patterns
    - `grep -c "name=" mcp_tools/handlers/*.py | awk -F: '{s+=$2} END {print s}'` ≥ 14 (5 in market.py R1+R2+correl+session+multi+pattern, 3 in proposal.py legacy, 3 in account.py, 3 in position.py modify+get+close, 5 in backtest.py run+metrics+walk+cancel+replay = ~19)
  </acceptance_criteria>
  <done>
Final tools/list count asserted; legacy compat tests green; skill regression check executed (auto-detect simple patterns + summary documents manual review); count discrepancy with CONTEXT D-E1 (22 actual vs 25 stated) clarified in summary.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MCP client → replay_decision | Untrusted decision_id input; SDK validates inputSchema (string); handler validates prefix and existence |
| MCP server → trades_log SQLite | Read-only via parameterized SELECT WHERE id=?; no SQL injection risk |
| MCP server → baseline_decisions.parquet | Read-only via pyarrow filters; pyarrow handles Parquet schema validation |
| MCP server → live MT5 (correlation_matrix) | Read-only OHLC reads via BarSource; no mutation |
| MCP server → Phase 4 strategy module (replay) | Phase 4 evaluate_proposal_for_bar is side-effect-free per STRAT-08 — safe to invoke from replay |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-6-05-01 | SQL Injection | _lookup_trades_log | mitigate | Parameterized query (`WHERE id = ?`); decision_id stripped to int before bind |
| T-6-05-02 | Path Traversal | _lookup_baseline_parquet | mitigate | Hardcoded path `data/training/baseline_decisions.parquet`; decision_id used only as filter value, not path component |
| T-6-05-03 | Information Disclosure | replay_decision regression flag | accept | regression=True is informational; reveals only that strategy code has changed since the original decision was made (not user-sensitive) |
| T-6-05-04 | DoS | get_correlation_matrix with 5 symbols × 500 bars | mitigate | maxItems=5 + maxLookback=500 in inputSchema; numpy.corrcoef is O(n²m) ≈ 25 × 500 = ~12k ops, trivial |
| T-6-05-05 | DoS | get_pattern_catalog scanning 200 bars | accept | Phase 3 scan_patterns is bounded; max 200 bars per call (inputSchema cap) |
| T-6-05-06 | Repudiation | replay_decision audit | mitigate | All replay_decision invocations logged via init_logger; trades_log/parquet rows are immutable history |
| T-6-05-07 | Tampering | scan_patterns return values | accept | Phase 3 module is version-controlled; replay uses current code by D-D2 design |
| T-6-05-08 | Information Disclosure | get_session_state | accept | Returns only public time/session info; no user data |
| T-6-05-09 | Spoofing | replay_decision decision_id | mitigate | Lookup checks prefix (`live_` or `baseline_`); raw int id only valid via numeric type-cast; rejects malformed |
</threat_model>

<verification>
1. Market handlers: `pytest tests/test_mcp_handlers_market.py -x --tb=short` exits 0 (R1/R2 + 6 new = 11 tests).
2. Replay handler: `pytest tests/test_mcp_handlers_backtest.py -x --tb=short` exits 0 (8 prior + 3 replay = 11 tests, replay xfails flipped).
3. Final tools list: `pytest tests/test_mcp_legacy_compat.py -x --tb=short` exits 0.
4. Full Phase 6 suite: `pytest tests/test_mcp_*.py -x --tb=short` exits 0 (~50+ tests across 11 files).
5. Legacy regression: `pytest tests/test_mcp_tools_v2.py tests/test_backtest_ledger.py tests/test_scheduler.py tests/test_phase16.py -x` exits 0.
6. Tools count assertion present: `grep -q "len(set(names))" tests/test_mcp_legacy_compat.py` exits 0.
7. Skill regression test runs: `pytest tests/test_mcp_legacy_compat.py::test_skill_compat_reads -v` either PASSES or fails with explicit list of .md files needing manual review.
</verification>

<success_criteria>
- 4 new market handlers: get_correlation_matrix, get_session_state, get_multi_tf_snapshot, get_pattern_catalog
- 1 new audit handler: replay_decision (D-D2 union lookup trades_log + parquet, replay via Phase 2/4 surfaces)
- 5 new schemas in mcp_tools/schemas.py
- 5 new tool registrations in mcp_tools/server.py @list_tools
- ~9 stub tests flipped from xfail to PASS in this wave (4 correlation+session, 2 multi-tf+pattern, 3 replay)
- test_list_tools_count asserts actual tool count (22, with CONTEXT D-E1 count clarified)
- test_skill_compat_reads runs (PASS or detailed failure list)
- All Wave 0/1/2/3 tests still green (zero regression)
- forex-trader-pro skill regression notes documented in 06-05-SUMMARY.md (manual check confirms no breaking changes from R1 default 200-bars)
</success_criteria>

<output>
After completion, create `.planning/phases/06-mcp-tools-part-1/06-05-SUMMARY.md` with:
- 5 new tools registered (correlation, session, multi-tf, pattern_catalog, replay_decision)
- Tools list count: actual = 22 (11 legacy + 10 net new + 1 derived); CONTEXT D-E1 count discrepancy explained (R1/R2/R3 are in-place refactors, not additional tools)
- Skill regression check verdict (per file: any hardcoded `len(ohlc)==50` patterns found? action items?)
- Phase 2/3/4 surface verification (compute_all_extended, scan_patterns, evaluate_proposal_for_bar — present? handler degrades gracefully when absent)
- Pyarrow availability for replay_decision baseline lookup
- Test count: stubs flipped → green / total stubs (final tally across all 5 plans)
- Phase 6 closure: roadmap requirements MCP-09/11/12/14/15 covered + R1/R2/R3 + MCP-16/17 + MCP-01/02/03 verified
- Recommendations for Phase 8 (which extends MCP-R4 evaluate_trade_proposal with ML; backtest handler module is already split for clean extension)
- Any deviations from CONTEXT to surface to user (e.g. mcp/ → mcp_tools/ rename from Wave 1 still active; tool count 22 vs 25 documented)
</output>
'''
with open('C:/trading-agent/.planning/phases/06-mcp-tools-part-1/06-05-PLAN.md', 'w', encoding='utf-8') as f:
    f.write(content)
print('wrote 06-05-PLAN.md', len(content), 'chars')
