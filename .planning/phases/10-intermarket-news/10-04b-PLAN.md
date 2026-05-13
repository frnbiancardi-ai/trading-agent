---
phase: 10
plan: 04b
type: execute
wave: 2
depends_on:
  - 10-02
  - 10-03
files_modified:
  - mcp_tools/handlers/macro.py
  - mcp_tools/server.py
  - mcp/errors.py
autonomous: true
requirements:
  - MCP-10
  - MCP-13

must_haves:
  truths:
    - "MCP tool get_intermarket_context registrato in list_tools + dispatched in call_tool"
    - "MCP tool get_economic_calendar registrato + dispatched"
    - "handle_get_intermarket_context con ENABLE_INTERMARKET=False ritorna {intermarket_active:False, signals:{}}"
    - "handle_get_intermarket_context con loader=None ritorna envelope INTERNAL_ERROR"
    - "handle_get_economic_calendar invoca client.fetch_events + filter_window con args derivati"
    - "_bootstrap_state istanzia macro_loader_singleton (graceful: None se ENABLE_INTERMARKET=False) e calendar_client_singleton (sempre)"
    - "mcp/errors.py ErrorCodes contiene MACRO_CSV_MISSING + FF_FEED_UNAVAILABLE"
    - "mcp_tools/errors.py wildcard re-export propaga automaticamente i nuovi ErrorCodes (verified via assert hasattr — Blocker #2)"
    - "mcp_tools/server.py:37 import block contiene già `from mcp_tools.errors import ErrorCodes, envelope` (verified pre-existing — Blocker #2)"
    - "7 test stub mcp_handlers_macro PASS GREEN"
  artifacts:
    - path: "mcp_tools/handlers/macro.py"
      provides: "GET_INTERMARKET_CONTEXT_TOOL + GET_ECONOMIC_CALENDAR_TOOL + handle_get_intermarket_context + handle_get_economic_calendar"
      contains: "def handle_get_intermarket_context"
      exports: ["GET_INTERMARKET_CONTEXT_TOOL", "GET_ECONOMIC_CALENDAR_TOOL", "handle_get_intermarket_context", "handle_get_economic_calendar"]
      min_lines: 150
    - path: "mcp_tools/server.py"
      provides: "Imports + bootstrap singleton + list_tools registration + call_tool dispatch per MCP-10/13"
    - path: "mcp/errors.py"
      provides: "Nuovi ErrorCodes MACRO_CSV_MISSING + FF_FEED_UNAVAILABLE (re-exportati automaticamente via mcp_tools/errors.py wildcard, Blocker #2)"
  key_links:
    - from: "mcp_tools/handlers/macro.py"
      to: "intermarket.loader + intermarket.score + calendar_rss.client"
      via: "import"
      pattern: "from (intermarket|calendar_rss)"
    - from: "mcp_tools/server.py::_bootstrap_state"
      to: "MacroLoader.from_repo + CalendarRSSClient()"
      via: "singleton init guarded by ENABLE_INTERMARKET"
      pattern: "macro_loader_singleton"
    - from: "mcp/errors.py::ErrorCodes"
      to: "mcp_tools/errors.py::ErrorCodes (re-export)"
      via: "wildcard `from mcp.errors import ErrorCodes, envelope` (class attribute lookup, Blocker #2 verified)"
      pattern: "from mcp.errors import"

threat_model:
  trust_boundaries:
    - boundary: "MCP client (Anthropic Claude)->MCP tool dispatcher"
      description: "JSON-Schema validated input args; tool whitelist enforcement"
    - boundary: "mcp_tools/server.py->intermarket+calendar_rss singletons"
      description: "Graceful bootstrap (try/except log+None on failure)"
  stride_register:
    - id: "T-10-04b-01"
      category: "Input Validation (V5)"
      component: "GET_ECONOMIC_CALENDAR_TOOL.inputSchema + handle_get_economic_calendar"
      disposition: "mitigate"
      mitigation: "JSON-Schema draft-7: window_minutes integer min=1 max=10080 default 15; min_impact enum [Low,Medium,High]; pair string optional; currencies array string. Handler-side V5 doppia validazione con envelope VALIDATION_FAILED. ASVS V5."
    - id: "T-10-04b-02"
      category: "Information Disclosure"
      component: "envelope error message exposure"
      disposition: "accept"
      mitigation: "envelope(error_code, message, **context) message in italiano, no PII, no path traversal. Pattern Phase 6/8 verificato. ASVS V5 partial."
    - id: "T-10-04b-03"
      category: "DoS (Bootstrap)"
      component: "_bootstrap_state MacroLoader.from_repo / CalendarRSSClient()"
      disposition: "mitigate"
      mitigation: "try/except graceful: singleton=None on failure, log error, server continua. Phase 7 ML singleton pattern analog. ASVS V12 partial."
    - id: "T-10-04b-04"
      category: "Tampering (ErrorCodes Propagation, Blocker #2)"
      component: "mcp/errors.py ErrorCodes attribute add + mcp_tools/errors.py re-export"
      disposition: "mitigate"
      mitigation: "mcp_tools/errors.py:9 fa `from mcp.errors import ErrorCodes, envelope` (wildcard). I nuovi class-attribute MACRO_CSV_MISSING + FF_FEED_UNAVAILABLE sono automaticamente accessibili via mcp_tools.errors.ErrorCodes.X (Python class attribute lookup, NON snapshot). Test verbatim assert hasattr verifica propagation. ASVS V5 partial."
---

<objective>
Wave 2 MCP-10/13 wiring layer MCP (split del Plan 10-04 originale, Warning #3): esporre i tool MCP via `mcp_tools/handlers/macro.py` + bootstrap singletons + dispatch in `mcp_tools/server.py` + nuovi ErrorCodes in `mcp/errors.py`. Layer Strategy + Config delegato al partner parallel Plan 10-04a.

Purpose:
- Esporre MCP-10 + MCP-13 come tool MCP funzionali con envelope verificato (Phase 6/8 convention).
- Singleton bootstrap graceful (MacroLoader gated ENABLE_INTERMARKET, CalendarRSSClient sempre on).
- Blocker #2 resolution: verificare che i nuovi ErrorCodes vengano propagati via mcp_tools/errors.py wildcard re-export + che `envelope` + `ErrorCodes` siano già importati in mcp_tools/server.py.

Output:
- 1 nuovo file (mcp_tools/handlers/macro.py)
- 2 file modificati (mcp_tools/server.py, mcp/errors.py)
- 7 test stub mcp_handlers_macro PASS GREEN
- 0 regression Phase 6 server tests
</objective>

<execution_context>
@C:/trading-agent/.claude/get-shit-done/workflows/execute-plan.md
@C:/trading-agent/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/10-intermarket-news/10-01-PLAN.md
@.planning/phases/10-intermarket-news/10-02-PLAN.md
@.planning/phases/10-intermarket-news/10-03-PLAN.md
@.planning/phases/10-intermarket-news/10-CONTEXT.md
@.planning/phases/10-intermarket-news/10-RESEARCH.md
@.planning/phases/10-intermarket-news/10-PATTERNS.md

# File da modificare (lettura OBBLIGATORIA prima di toccare)
@mcp_tools/server.py
@mcp_tools/errors.py
@mcp_tools/handlers/backtest.py
@mcp_tools/handlers/market.py
@mcp/errors.py
@tests/test_mcp_handlers_macro.py
@intermarket/__init__.py
@calendar_rss/__init__.py

<interfaces>
<!-- Contracts critici da PRESERVARE. -->

From mcp/errors.py:52 (envelope reale signature):
```python
def envelope(error_code: str, message: str, **context) -> dict:
    """Returns: {ok: False, error: <code>, message: <it>, ...context}"""
# Success path: return dict diretto NON wrapped (vedi market.py:114-122)
```

From mcp/errors.py:19 (ErrorCodes constants disponibili):
```python
class ErrorCodes:
    INTERNAL_ERROR = "internal_error"
    VALIDATION_FAILED = "validation_failed"
    HISTORICAL_DATA_UNAVAILABLE = "historical_data_unavailable"
    # Phase 10 nuovi: MACRO_CSV_MISSING, FF_FEED_UNAVAILABLE
```

From mcp_tools/errors.py:9 (Blocker #2 — re-export wildcard verified):
```python
from mcp.errors import ErrorCodes, envelope  # noqa: F401
__all__ = ["ErrorCodes", "envelope"]
```
NB: `__all__` lista i top-level names (la *classe* ErrorCodes e la *funzione* envelope), NON i class attributes. Class attributes (MACRO_CSV_MISSING, FF_FEED_UNAVAILABLE) sono accessibili via lookup `mcp_tools.errors.ErrorCodes.MACRO_CSV_MISSING` automaticamente perché `mcp_tools.errors.ErrorCodes is mcp.errors.ErrorCodes` (stessa class object, non copia). Nessuna modifica a `__all__` necessaria.

From mcp_tools/server.py:37 (Blocker #2 — import block verified pre-existing):
```python
from mcp_tools.errors import ErrorCodes, envelope
```
NB: import block GIÀ presente al rigo 37 (verified grep 2026-05-13). NESSUNA aggiunta richiesta nel dispatch block: `envelope` e `ErrorCodes` già nel namespace del modulo.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: mcp_tools/handlers/macro.py + mcp/errors.py — handlers MCP-10 + MCP-13 + ErrorCodes propagation (Blocker #2)</name>
  <files>
    mcp_tools/handlers/macro.py
    mcp/errors.py
  </files>
  <read_first>
    - mcp_tools/handlers/backtest.py:55-90 (Tool definition pattern verbatim)
    - mcp_tools/handlers/market.py:56-122 (handler signature + envelope usage reale)
    - mcp/errors.py:19-52 (ErrorCodes + envelope signature)
    - **mcp_tools/errors.py (Blocker #2: verifica re-export wildcard `from mcp.errors import ErrorCodes, envelope`; conferma __all__ contiene solo `["ErrorCodes", "envelope"]` top-level)**
    - intermarket/__init__.py + intermarket/loader.py + intermarket/score.py + intermarket/types.py
    - calendar_rss/__init__.py + calendar_rss/client.py
    - tests/test_mcp_handlers_macro.py (7 test stub che codificano envelope+dispatch)
    - .planning/phases/10-intermarket-news/10-RESEARCH.md §Pattern 6 (NB: envelope shape RESEARCH SBAGLIATA — usa quello reale mcp/errors.py:52)
  </read_first>
  <behavior>
    Test stub Wave 0 codificano:
    - test_get_intermarket_context_envelope_disabled: ENABLE_INTERMARKET=False -> {intermarket_active:False, signals:{}}
    - test_get_intermarket_context_envelope_enabled: ENABLE_INTERMARKET=True, mock loader -> dict bias signals
    - test_get_intermarket_context_loader_none_returns_internal_error: loader=None -> envelope INTERNAL_ERROR
    - test_economic_calendar_pair_filter: args.pair=EURUSD -> events country in [USD,EUR]
    - test_economic_calendar_window_minutes_override: args.window_minutes=60
    - test_economic_calendar_envelope_ok_success: dict NON wrapped
    - test_economic_calendar_envelope_validation_failed_window_negative: window_minutes=-1 -> envelope VALIDATION_FAILED
  </behavior>
  <action>
    **STEP A — `mcp/errors.py`** (Blocker #2):
    Cerca `class ErrorCodes:` e dopo `MT5_NOT_READY = "mt5_not_ready"` aggiungi:
    ```python
        # Phase 10 (MCP-10 / MCP-13)
        MACRO_CSV_MISSING = "macro_csv_missing"
        FF_FEED_UNAVAILABLE = "ff_feed_unavailable"
    ```

    **STEP B — Verifica re-export propagation (Blocker #2)**:
    `mcp_tools/errors.py:9` fa `from mcp.errors import ErrorCodes, envelope` (verified read_first sopra). Poiché `ErrorCodes` è una **classe**, l'import porta nel namespace `mcp_tools.errors` un riferimento al *medesimo* class object di `mcp.errors`. Class-attribute lookup `mcp_tools.errors.ErrorCodes.MACRO_CSV_MISSING` segue il MRO della classe → trova l'attributo automaticamente. NESSUNA modifica a `mcp_tools/errors.py`:
    - `__all__ = ["ErrorCodes", "envelope"]` resta invariato (lista i top-level names esposti, non i class attributes).
    - Nessun snapshot, nessuna riassegnazione: l'attributo è disponibile immediatamente dopo lo Step A.
    Se invece `mcp_tools/errors.py` fosse stato `from mcp.errors import ErrorCodes as _EC; class ErrorCodes(_EC): ...` (subclass pattern) — NON è il caso qui — allora servirebbe estendere la subclass. Verifica con grep:
    ```bash
    grep -nE "from mcp.errors import|class ErrorCodes" mcp_tools/errors.py
    ```
    Atteso: 1 riga `from mcp.errors import ErrorCodes, envelope`, 0 righe `class ErrorCodes`. Se diverso, ESCALATE prima di proseguire.

    **STEP C — `mcp_tools/handlers/macro.py`** (nuovo file ~250 LOC):
    Header italiano + imports:
    ```python
    """Phase 10 MCP-10 + MCP-13 handlers.

    - get_intermarket_context: Macro signal aggregator (DXY/US10Y/XAUUSD/WTI -> USD strength,
      risk-on/off, JPY safe-haven flag). Gated da cfg.ENABLE_INTERMARKET (D-10-D2 default OFF).
    - get_economic_calendar: FF RSS forward-looking events advisory, pair-aware High-only,
      ET->UTC zoneinfo. Live-only no-auto-reject (D-10-C0).

    Envelope convention Phase 6/8: envelope(error_code, msg, **context) -> {ok:False, ...}
    Success path: return dict diretto (NON envelope-wrapped), come mcp_tools/handlers/market.py.
    """
    from __future__ import annotations

    from datetime import datetime, timedelta, timezone
    from typing import Any

    from mcp.types import Tool

    from mcp_tools.errors import ErrorCodes, envelope


    # ============================================================================
    # Tool definitions
    # ============================================================================

    GET_INTERMARKET_CONTEXT_TOOL = Tool(
        name="get_intermarket_context",
        description=(
            "Ritorna bias macro intermarket: USD strength (DXY), risk-on/off (US10Y vs XAUUSD), "
            "JPY safe-haven flag. Daily-close lookup strict-< (no future leakage). "
            "Dataset 23.6y committed in data/historical/macro/. "
            "Gated da ENABLE_INTERMARKET=true (D-10-D2). Advisory only (D-10-C0)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "enum": ["EURUSD", "GBPUSD", "USDJPY"]},
                "as_of_ts": {"type": "string", "description": "ISO8601 UTC, default now"},
            },
            "required": [],
        },
    )

    GET_ECONOMIC_CALENDAR_TOOL = Tool(
        name="get_economic_calendar",
        description=(
            "Ritorna eventi calendar forward-looking dal feed ForexFactory RSS (next 7 days, "
            "TTL 60min). Pair-aware High-only default. NON applica auto-reject (D-10-C0 advisory). "
            "Skip Tentative + All Day non-holiday."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "window_minutes": {"type": "integer", "minimum": 1, "maximum": 10080, "default": 15},
                "pair": {"type": "string"},
                "min_impact": {"type": "string", "enum": ["Low", "Medium", "High"], "default": "High"},
                "currencies": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
    )


    # ============================================================================
    # MCP-10 handler
    # ============================================================================

    def handle_get_intermarket_context(args: dict, macro_loader, cfg) -> dict:
        if not getattr(cfg, "ENABLE_INTERMARKET", False):
            return {
                "intermarket_active": False,
                "signals": {},
                "as_of_utc": datetime.now(tz=timezone.utc).isoformat(),
            }
        if macro_loader is None:
            return envelope(
                ErrorCodes.INTERNAL_ERROR,
                "MacroLoader non inizializzato (bootstrap fallito o CSV mancanti)",
                tool="get_intermarket_context",
            )

        try:
            as_of_arg = args.get("as_of_ts")
            now_utc = datetime.fromisoformat(as_of_arg) if as_of_arg else datetime.now(tz=timezone.utc)
            if now_utc.tzinfo is None:
                now_utc = now_utc.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            return envelope(
                ErrorCodes.VALIDATION_FAILED,
                f"as_of_ts ISO8601 non valido: {exc}",
                tool="get_intermarket_context",
                arg="as_of_ts",
            )

        # Compute raw signals (delta % vs D-2)
        signals: dict[str, dict] = {}
        d2_ts = now_utc - timedelta(days=2)
        for sym in macro_loader.symbols():
            c1 = macro_loader.close_at(sym, now_utc)
            c2 = macro_loader.close_at(sym, d2_ts)
            if c1 is None or c2 is None or c2 == 0:
                signals[sym] = {"close": c1, "prev_close": c2, "delta_pct": None}
                continue
            signals[sym] = {
                "close": float(c1),
                "prev_close": float(c2),
                "delta_pct": float((c1 - c2) / c2),
            }

        # Bias derivation
        dxy = signals.get("DXY", {}).get("delta_pct")
        usd_bias = (
            "neutral" if dxy is None
            else "strong" if dxy > 0.003
            else "weak" if dxy < -0.003
            else "neutral"
        )

        us10y = signals.get("US10Y", {}).get("delta_pct")
        xau = signals.get("XAUUSD", {}).get("delta_pct")
        if us10y is None or xau is None:
            risk_bias = "neutral"
        elif us10y > 0 and xau < 0:
            risk_bias = "risk_on"
        elif us10y < 0 and xau > 0:
            risk_bias = "risk_off"
        else:
            risk_bias = "neutral"

        jpy_safe = bool(
            xau is not None and us10y is not None
            and xau > 0.005 and us10y < 0
        )

        return {
            "intermarket_active": True,
            "usd_strength_bias": usd_bias,
            "risk_on_off": risk_bias,
            "jpy_safe_haven_flag": jpy_safe,
            "signals": signals,
            "as_of_utc": now_utc.isoformat(),
        }


    # ============================================================================
    # MCP-13 handler
    # ============================================================================

    def handle_get_economic_calendar(args: dict, calendar_client, cfg) -> dict:
        # V5 input validation
        try:
            window_minutes = int(args.get("window_minutes", getattr(cfg, "CALENDAR_DEFAULT_WINDOW_MINUTES", 15)))
        except (TypeError, ValueError):
            return envelope(
                ErrorCodes.VALIDATION_FAILED,
                "window_minutes deve essere intero >= 1",
                tool="get_economic_calendar", arg="window_minutes",
            )
        if window_minutes < 1 or window_minutes > 10080:
            return envelope(
                ErrorCodes.VALIDATION_FAILED,
                f"window_minutes fuori range [1, 10080]: {window_minutes}",
                tool="get_economic_calendar", arg="window_minutes",
            )

        min_impact = args.get("min_impact", "High")
        if min_impact not in ("Low", "Medium", "High"):
            return envelope(
                ErrorCodes.VALIDATION_FAILED,
                f"min_impact deve essere Low|Medium|High: {min_impact}",
                tool="get_economic_calendar", arg="min_impact",
            )

        pair = args.get("pair")
        currencies = args.get("currencies")
        if not currencies:
            from calendar_rss.client import CalendarRSSClient
            currencies = CalendarRSSClient.derive_currencies_from_pair(pair)

        try:
            now_utc = datetime.now(tz=timezone.utc)
            events = calendar_client.fetch_events(now=now_utc)
            filtered = calendar_client.filter_window(
                events, now=now_utc,
                window_minutes=window_minutes,
                min_impact=min_impact,
                currencies=currencies,
            )
        except Exception as exc:
            return envelope(
                ErrorCodes.FF_FEED_UNAVAILABLE,
                f"FF RSS feed errore: {exc}",
                tool="get_economic_calendar",
            )

        return {
            "events": [_serialize_event(ev) for ev in filtered],
            "count": len(filtered),
            "window_minutes": window_minutes,
            "min_impact": min_impact,
            "currencies": list(currencies),
            "as_of_utc": now_utc.isoformat(),
            "note_advisory": "D-10-C0 advisory only - no auto-reject in strategy/risk_engine.",
        }


    def _serialize_event(ev) -> dict[str, Any]:
        return {
            "title": ev.title,
            "country": ev.country,
            "event_time_utc": ev.event_time_utc.isoformat(),
            "impact": ev.impact,
            "forecast": ev.forecast,
            "previous": ev.previous,
            "url": ev.url,
            "all_day": ev.all_day,
        }
    ```

    Flip 7 test stub `tests/test_mcp_handlers_macro.py` da xfail -> PASS GREEN.

    Tutti i commenti italiani.
  </action>
  <verify>
    <automated>pytest tests/test_mcp_handlers_macro.py -x --tb=short -v 2>&1 | tail -15 && python -c "from mcp_tools.handlers.macro import GET_INTERMARKET_CONTEXT_TOOL, GET_ECONOMIC_CALENDAR_TOOL, handle_get_intermarket_context, handle_get_economic_calendar; print('imports OK', GET_INTERMARKET_CONTEXT_TOOL.name, GET_ECONOMIC_CALENDAR_TOOL.name)" && grep -qE "MACRO_CSV_MISSING|FF_FEED_UNAVAILABLE" mcp/errors.py && python -c "from mcp_tools.errors import ErrorCodes; assert hasattr(ErrorCodes, 'MACRO_CSV_MISSING') and hasattr(ErrorCodes, 'FF_FEED_UNAVAILABLE'), 'Blocker #2 re-export propagation broken'; print('Blocker #2 propagation OK')"</automated>
  </verify>
  <done>
    - mcp_tools/handlers/macro.py esiste (2 Tool definitions + 2 handler functions + _serialize_event helper, ~250 LOC)
    - mcp/errors.py contiene MACRO_CSV_MISSING + FF_FEED_UNAVAILABLE in ErrorCodes
    - **Blocker #2 resolved**: re-export wildcard in mcp_tools/errors.py propaga automaticamente i nuovi ErrorCodes (verified via `assert hasattr(ErrorCodes, 'MACRO_CSV_MISSING')` post-step-A)
    - handle_get_intermarket_context: gate ENABLE_INTERMARKET + loader None envelope + signals computation
    - handle_get_economic_calendar: V5 validation (window range, impact enum) + pair-aware filter + envelope FF_FEED_UNAVAILABLE su fail
    - 7 test stub PASS GREEN
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: mcp_tools/server.py — bootstrap singleton + list_tools + call_tool dispatch (Blocker #2 import block verified)</name>
  <files>
    mcp_tools/server.py
  </files>
  <read_first>
    - **mcp_tools/server.py (intero, ma in particolare riga 37 dove `from mcp_tools.errors import ErrorCodes, envelope` è già presente — Blocker #2 verified)**
    - mcp_tools/server.py (imports linee 54-81, _bootstrap_state ~139-185 MLFilter pattern, list_tools 187-328, call_tool 333-433 ML dispatch branch)
    - mcp_tools/handlers/macro.py (Task 1 output)
    - .planning/phases/10-intermarket-news/10-PATTERNS.md §mcp_server.py modify (pattern verbatim)
  </read_first>
  <action>
    **STEP A (Blocker #2 — pre-flight verify)**:
    Esegui prima:
    ```bash
    grep -nE "^from mcp_tools.errors import|^from mcp_tools\.errors import" mcp_tools/server.py
    ```
    Atteso: 1 match `from mcp_tools.errors import ErrorCodes, envelope` (riga 37 — verified 2026-05-13).
    Se NON presente (regressione vs verified state): aggiungere `from mcp_tools.errors import envelope, ErrorCodes` PRIMA del primo handler import del file. Se presente: NESSUNA modifica al import block.

    **STEP B — Aggiungi nuovi imports macro handlers** dopo l'ultimo handler block esistente:
    ```python
    from mcp_tools.handlers.macro import (
        GET_INTERMARKET_CONTEXT_TOOL,
        GET_ECONOMIC_CALENDAR_TOOL,
        handle_get_intermarket_context,
        handle_get_economic_calendar,
    )
    ```

    **STEP C — Aggiungi 2 singleton globali** sotto `ml_filter_singleton`:
    ```python
    macro_loader_singleton = None
    calendar_client_singleton = None
    ```

    **STEP D — Estendi `_bootstrap_state()`** dopo il blocco MLFilter singleton:
    ```python
        # Phase 10 MCP-10: MacroLoader singleton (gated da cfg.ENABLE_INTERMARKET)
        global macro_loader_singleton
        if getattr(cfg, "ENABLE_INTERMARKET", False):
            try:
                from intermarket.loader import MacroLoader
                macro_loader_singleton = MacroLoader.from_repo(
                    root=getattr(cfg, "MACRO_CSV_ROOT", "data/historical/macro"),
                )
                log.info("MacroLoader singleton caricato (Phase 10 MCP-10)")
            except Exception as exc:
                log.error("MacroLoader bootstrap fallito (graceful): %s", exc)
                macro_loader_singleton = None
        else:
            macro_loader_singleton = None
            log.info("MacroLoader singleton skip (ENABLE_INTERMARKET=false)")

        # Phase 10 MCP-13: CalendarRSSClient singleton (sempre on - advisory tool live-only D-10-B1)
        global calendar_client_singleton
        try:
            from calendar_rss.client import CalendarRSSClient
            calendar_client_singleton = CalendarRSSClient(cfg=cfg, logger=log)
            log.info("CalendarRSSClient singleton caricato (Phase 10 MCP-13)")
        except Exception as exc:
            log.error("CalendarRSSClient bootstrap fallito (graceful): %s", exc)
            calendar_client_singleton = None
    ```

    **STEP E — Estendi `list_tools()`** aggiungendo dopo i tool Phase 8:
    ```python
            # Phase 10 - intermarket + calendar (MCP-10, MCP-13)
            GET_INTERMARKET_CONTEXT_TOOL,
            GET_ECONOMIC_CALENDAR_TOOL,
    ```

    **STEP F — Estendi `call_tool()` dispatch** prima del fallback `raise ValueError(f"Unknown tool: {name}")`:
    ```python
        # Phase 10 - intermarket + calendar (MCP-10, MCP-13)
        if name == "get_intermarket_context":
            return _text(handle_get_intermarket_context(
                arguments, macro_loader_singleton, cfg,
            ))
        if name == "get_economic_calendar":
            if calendar_client_singleton is None:
                return _text(envelope(
                    ErrorCodes.INTERNAL_ERROR,
                    "CalendarRSSClient non inizializzato (chiamare _bootstrap_state() prima)",
                    tool=name,
                ))
            return _text(handle_get_economic_calendar(
                arguments, calendar_client_singleton, cfg,
            ))
    ```
    NB Blocker #2: `envelope` e `ErrorCodes` sono già nel namespace del modulo per via dell'import a riga 37 — nessuna nuova import necessaria nel dispatch.

    Tutti i commenti italiani. NO regression: i test Phase 6 server (test_mcp_tools_v2 + altri) devono restare GREEN.
  </action>
  <verify>
    <automated>python -c "from mcp_tools import server; print('server import OK'); assert hasattr(server, 'macro_loader_singleton'); assert hasattr(server, 'calendar_client_singleton'); print('singletons declared')" && grep -c "GET_INTERMARKET_CONTEXT_TOOL\|GET_ECONOMIC_CALENDAR_TOOL\|macro_loader_singleton\|calendar_client_singleton" mcp_tools/server.py && pytest tests/test_mcp_tools_v2.py -x --tb=short 2>&1 | tail -3 && grep -nE "^from mcp_tools\.errors import ErrorCodes, envelope" mcp_tools/server.py | head -1</automated>
  </verify>
  <done>
    - mcp_tools/server.py contiene 4 import macro handlers
    - macro_loader_singleton + calendar_client_singleton globali dichiarati
    - _bootstrap_state estende con 2 try/except graceful (loader gated + client always-on)
    - list_tools registra 2 nuovi tool
    - call_tool dispatch 2 branch per name == "get_intermarket_context" e "get_economic_calendar"
    - **Blocker #2 verified**: `from mcp_tools.errors import ErrorCodes, envelope` già presente a server.py:37 (no duplicate add)
    - Test Phase 6 legacy GREEN (no regression)
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Wave 2 MCP layer sanity check + integration con 10-04a</name>
  <files>
    .planning/STATE.md
  </files>
  <read_first>
    - .planning/STATE.md (sezione Active Work + Recent Decisions per Phase 10)
    - .planning/phases/10-intermarket-news/10-04a-PLAN.md (partner Wave 2 parallel)
  </read_first>
  <action>
    Step 1 — Run full Wave 2 MCP verification:
    ```bash
    pytest tests/test_intermarket_loader.py tests/test_intermarket_score.py \
           tests/test_calendar_rss_client.py tests/test_mcp_handlers_macro.py \
           tests/test_phase10_no_phase5_drift.py \
           tests/test_mcp_tools_v2.py \
           -x --tb=short
    ```
    Atteso: tutti passed + zero error + zero failure.

    Step 2 — Cross-check con Plan 10-04a:
    ```bash
    # Se 10-04a già eseguito (Wave 2 parallel partner), full Phase 4 + Phase 10:
    pytest tests/test_intermarket_loader.py tests/test_intermarket_score.py \
           tests/test_calendar_rss_client.py tests/test_mcp_handlers_macro.py \
           tests/test_phase10_no_phase5_drift.py \
           tests/test_strategy_confluence.py tests/test_strategy_shim.py \
           tests/test_setup_a_breakout.py tests/test_setup_b_reversal.py \
           tests/test_setup_c_compression.py tests/test_setup_d_pullback.py \
           -x --tb=short
    ```

    Step 3 — Full suite no-regression:
    ```bash
    pytest -x --tb=short 2>&1 | tail -10
    ```

    Step 4 — Aggiorna `.planning/STATE.md` (Wave 2 partial: 10-04b parte):
    - Tabella Milestone Status — Phase 10 status: `🟡 wave-2-mcp-complete`, progress `4/6 plans (67%)` (assumendo 10-04a + 10-04b countano come 2 separati per il count 6-plan; aggiusta a 4/5 se 10-04a+b vengono trattati come unità composta).
    - "Active Work" — registra completamento 10-04b layer MCP separatamente da 10-04a.
    - Last-updated footer.
  </action>
  <verify>
    <automated>pytest tests/test_mcp_handlers_macro.py tests/test_mcp_tools_v2.py tests/test_phase10_no_phase5_drift.py -x --tb=short 2>&1 | tail -5 && grep -q "wave-2" .planning/STATE.md</automated>
  </verify>
  <done>
    - Suite MCP layer + immutability gate GREEN
    - Cross-check con 10-04a (se eseguito) GREEN
    - STATE.md tracciato 10-04b completion
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MCP client (Anthropic Claude)->mcp_tools/server.py dispatch | JSON-Schema validated tool args (V5 + handler-side double-check) |
| mcp_tools/server.py->intermarket+calendar_rss singletons | Graceful bootstrap (try/except log+None on failure) |
| mcp/errors.py->mcp_tools/errors.py re-export | Wildcard import — class attribute lookup automatico (Blocker #2 verified) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-10-04b-01 | Input Validation (V5) | GET_ECONOMIC_CALENDAR_TOOL.inputSchema + handle_get_economic_calendar | mitigate | JSON-Schema draft-7 + handler-side double validation (window_minutes range [1,10080], min_impact enum). Envelope VALIDATION_FAILED. ASVS V5. |
| T-10-04b-02 | Information Disclosure | envelope error message exposure | accept | Message in italiano, no PII, no path traversal. Pattern Phase 6/8 verificato. ASVS V5 partial. |
| T-10-04b-03 | DoS (Bootstrap) | _bootstrap_state singletons | mitigate | try/except graceful: singleton=None on failure, log error, server continua. Pattern Phase 7 ML singleton. ASVS V12 partial. |
| T-10-04b-04 | Tampering (ErrorCodes Propagation, Blocker #2) | mcp/errors.py ErrorCodes attribute add + mcp_tools/errors.py re-export | mitigate | mcp_tools/errors.py:9 wildcard `from mcp.errors import ErrorCodes, envelope`. Class attribute lookup propaga automaticamente i nuovi MACRO_CSV_MISSING + FF_FEED_UNAVAILABLE. Verify: `assert hasattr(mcp_tools.errors.ErrorCodes, 'MACRO_CSV_MISSING')`. ASVS V5 partial. |
</threat_model>

<verification>
After all 3 tasks complete:

```bash
# MCP layer test suite (target ~3s)
pytest tests/test_mcp_handlers_macro.py tests/test_mcp_tools_v2.py -x --tb=short

# Blocker #2 propagation gate
python -c "from mcp_tools.errors import ErrorCodes; assert hasattr(ErrorCodes, 'MACRO_CSV_MISSING') and hasattr(ErrorCodes, 'FF_FEED_UNAVAILABLE'); print('Blocker #2 OK')"

# server.py import block (Blocker #2 verified)
grep -nE "^from mcp_tools\.errors import ErrorCodes, envelope" mcp_tools/server.py
# Atteso: riga 37 match

# Cross-check Phase 4 (se 10-04a eseguito parallel)
pytest tests/test_strategy_confluence.py tests/test_strategy_shim.py -x --tb=short

# Full suite
pytest -x --tb=short 2>&1 | tail -5
```
</verification>

<success_criteria>
- [x] mcp_tools/handlers/macro.py creato (~250 LOC, 2 Tool + 2 handler + serializer)
- [x] mcp/errors.py contiene MACRO_CSV_MISSING + FF_FEED_UNAVAILABLE
- [x] **Blocker #2 resolved**: mcp_tools/errors.py wildcard re-export propaga automaticamente (verified `hasattr` assertion)
- [x] **Blocker #2 verified**: mcp_tools/server.py:37 import block `from mcp_tools.errors import ErrorCodes, envelope` già presente (no duplicate add)
- [x] mcp_tools/server.py singleton bootstrap graceful + list_tools + call_tool dispatch
- [x] 7 test mcp_handlers_macro PASS GREEN
- [x] Phase 6 server regression GREEN
- [x] D-10-C0 immutability gate ancora PASS
- [x] Wave 2 parallel partner Plan 10-04a (strategy/config layer) può essere eseguito simultaneamente
</success_criteria>

<output>
After completion, create `.planning/phases/10-intermarket-news/10-04b-SUMMARY.md` con:
- File creati/modificati + LOC delta (macro.py ~250, server.py ~50 delta, errors.py ~5 delta)
- Test pass count flipped (7 MCP handler + Phase 6 server regression GREEN)
- Blocker #2 resolution documentation (re-export wildcard propagation + server import block verified pre-existing)
- Wave 2 split note: 10-04a (strategy/config) + 10-04b (MCP) parallel partner
- Next: Plan 10-05 (ops + docs Wave 3) — depends_on aggiornato a [10-04a, 10-04b]
</output>
