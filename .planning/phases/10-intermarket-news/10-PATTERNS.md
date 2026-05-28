# Phase 10: Intermarket + News - Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 17 new/modified
**Analogs found:** 16 / 17 (1 file = composite analog)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `data/historical/macro/{DXY,US10Y,XAUUSD,WTI}/daily.csv` | data-fixture | CSV-static | `data/historical/EURUSD/M15.csv` (BACK-01 source) — formato adattato | role-match (schema differente: daily-close vs intraday OHLC) |
| `intermarket/__init__.py` | package-init | N/A | `backtest/__init__.py`, `mcp_tools/__init__.py` | exact |
| `intermarket/loader.py` | data-loader | CSV → in-memory cache + strict-< lookup | `backtest/loader.py` (`load_bars` BACK-01) + `backtest/baseline/determinism.py` (`file_sha256`) | composite (CSV semicolon + sha256 anchor) |
| `intermarket/score.py` | service (pure-fn factory) | transform (closure) | `strategy/confluence.py:160-220` (`score_factors`) — pure-fn pattern | role-match |
| `calendar_rss/__init__.py` | package-init | N/A | `intermarket/__init__.py` (sibling new pkg) | exact |
| `calendar_rss/client.py` | service | RSS fetch + cache + lookback filter | `news_aggregator.py:20-141` (RSS+cache+lookback completo) | **exact** (template diretto) |
| `mcp_tools/handlers/macro.py` | MCP-handler | request-response (envelope) | `mcp_tools/handlers/backtest.py:309-467` + `mcp_tools/handlers/market.py:56-122` | **exact** (envelope + Tool + handler) |
| `scripts/refresh_macro_csv.py` | ops-script (CLI) | file-I/O (download → write) | `scripts/run_baseline_05_09.py`, `scripts/dry_run_cycle.py` | role-match |
| `config.py:215-231` extension | config (env loader) | env → class attrs | `config.py:214-235` `_attach_news_sentiment(cls)` | **exact** (template diretto) |
| `mcp_server.py` modify | MCP-router | request-response dispatch | `mcp_tools/server.py:187-328` (`list_tools`) + `:333-433` (`call_tool`) | exact |
| `strategy/context.py:17` modify | dataclass field | N/A (signature extend) | self (`strategy/context.py:17-18` esistente) | exact (modifica in-place) |
| `strategy/confluence.py:266` modify | callsite | N/A | self (`strategy/confluence.py:263-269` esistente) | exact (modifica in-place) |
| `strategy/_shim.py:133` modify | wire-up | constructor injection | self (`strategy/_shim.py:128-135` esistente) | exact (modifica in-place) |
| `tests/test_intermarket_loader.py` | test | unit | `tests/test_backtest_loader.py`, `tests/test_baseline_determinism.py` | exact |
| `tests/test_intermarket_score.py` | test | unit | `tests/test_strategy_confluence.py` (StrategyContext stubs + intermarket_fn) | exact |
| `tests/test_calendar_rss_client.py` | test | unit (RSS mock) | `tests/test_news_aggregator.py:31-80` (feedparser mocked) | **exact** (template diretto) |
| `tests/test_mcp_handlers_macro.py` | test | unit (handler envelope) | `tests/test_mcp_handlers_market.py`, `tests/test_mcp_handlers_backtest.py` | exact |
| `tests/test_phase10_no_phase5_drift.py` | regression test | gate | `tests/test_baseline_determinism.py` (sha256 anchor) + `tests/test_baseline_dataset_writer.py` (`_SCHEMA_V2_REQUIRED_KEYS`) | role-match |
| `tests/fixtures/macro_dxy_smoke.csv` | fixture | data | `tests/fixtures/eurusd_5bars.csv` | role-match (formato differente) |
| `tests/fixtures/ff_rss_smoke.xml` | fixture | data | N/A — RSS XML fixture NUOVO (no analog) | **NO ANALOG** |
| `tests/fixtures/ff_rss_dst_cross.xml` | fixture | data | N/A | **NO ANALOG** (variante del precedente) |

---

## Pattern Assignments

### `intermarket/loader.py` (data-loader, CSV-static + strict-< lookup + sha256 anchor)

**Analoghi composti:** `backtest/loader.py` (CSV semicolon parser) + `backtest/baseline/determinism.py` (sha256 file hash).

**Imports + dataclass pattern** (analog `backtest/loader.py:1-23`):
```python
"""Italian-CSV historical bar loader (BACK-01) — semicolon, DD/MM/YYYY, GMT-6 → UTC."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# D-08: source is GMT-6, add 6h to get UTC. Verified vs 3 NFP candles in research.
_GMT6_OFFSET = timedelta(hours=6)


@dataclass(frozen=True)
class Bar:
    time: int          # UTC unix timestamp (bar OPEN time, seconds)
    open: float
    ...
```
**Adattamento Phase 10:** sostituire `Bar` con `MacroSeries`, usare `MACRO_SYMBOLS = ("DXY", "US10Y", "XAUUSD", "WTI")` come tupla module-level (analoga a `_GMT6_OFFSET`). **NOTA formato CSV:** RESEARCH §Pattern 1 ipotizza CSV `Data;Ora;Close` semicolon (BACK-01 format), ma il DXY committed esistente in `data/historical/DXY/1D.csv` usa formato investing.com (`"Data","Ultimo","Apertura",...` comma-separated, virgola decimale, DD.MM.YYYY). **Decisione planner OBBLIGATORIA**: il D-10-A4 `scripts/refresh_macro_csv.py` può (a) normalizzare a BACK-01 semicolon format così il loader Phase 10 riutilizza esattamente il pattern, oppure (b) il loader supporta entrambi i formati. Default consigliato: il refresh script normalizza → loader semplice = pattern BACK-01 puro.

**CSV parse pattern verbatim** (`backtest/loader.py:45-68`):
```python
df = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str)
df.columns = [c.strip() for c in df.columns]

df["dt_source"] = pd.to_datetime(
    df["Data"] + " " + df["Ora"], format="%d/%m/%Y %H:%M:%S"
)
df["dt_utc"] = df["dt_source"] + _GMT6_OFFSET

for col in ("Open", "High", "low", "Close"):
    df[col] = df[col].astype(float)
df["Volume"] = df["Volume"].astype(int)
...
df = df.sort_values("dt_utc").drop_duplicates("dt_utc").reset_index(drop=True)
```
**Adattamento Phase 10:** rimuovere `_GMT6_OFFSET` (D-10-A2: daily-close = nominal date 00:00 UTC, no timezone offset), tenere `Close` come unica colonna numerica, drop `Open/High/low/Volume`.

**sha256 anchor pattern verbatim** (`backtest/baseline/determinism.py:29-35`):
```python
def file_sha256(path: Path) -> str:
    """Config file hash per backtest_runs audit trail (D-17).

    Hex digest completo (64 char). Letto come bytes — encoding-agnostic, line-ending
    sensible (CRLF vs LF cambia hash; gestito a CI livello).
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
```
**Adattamento Phase 10:** chiamare `file_sha256(csv_path)` in `MacroLoader.from_repo()` per ogni dei 4 CSV; memorizzare in `MacroSeries.sha256` field; D-10-A4 metadata.json scrive questi 4 hash a training time (Phase 7 D-15 extension già definita in CONTEXT.md).

**Strict-< lookup pattern** (D-10-A2 no future leakage):
```python
# In MacroLoader.close_at:
mask = df["ts_utc"] < pd.Timestamp(ts_utc, tz="UTC")  # STRICT-< (NON <=)
if not mask.any():
    return None
return float(df.loc[mask, "close"].iloc[-1])
```
**Source:** RESEARCH §Pattern 4. Test obbligatorio: dato bar @ exact `ts_utc` nella CSV, `close_at(symbol, ts_utc)` ritorna bar `idx-1`, NON quello @ `ts_utc`.

---

### `intermarket/score.py` (service, pure-fn factory closure)

**Analog:** `strategy/confluence.py:160-220` `score_factors` (pure-fn factory pattern, no side-effects, ctx injection).

**Pure-fn pattern** (analog `strategy/confluence.py:97-100`):
```python
def score_factors(
    setup_name: str,
    indicators, ctx: StrategyContext, direction: str, cfg: StrategyConfig
) -> dict:
    """Pure: nessun side-effect. Tutti i parametri sono espliciti."""
```
**Adattamento Phase 10:** firma factory + closure su `loader`:
```python
def build_intermarket_score(loader) -> Callable[[str, Literal["long","short"]], float]:
    def _score(symbol: str, direction: Literal["long","short"]) -> float:
        ...
    return _score
```

**Aggregation logic skeleton:** vedi RESEARCH §Pattern 3 (Claude's Discretion — planner libero di tarare `_PAIR_WEIGHTS`). Riferimento pesi suggeriti:
- `EURUSD/GBPUSD`: `{"DXY": -0.5, "US10Y": +0.2, "XAUUSD": -0.2, "WTI": +0.1}`
- `USDJPY`: `{"DXY": +0.5, "US10Y": +0.3, "XAUUSD": -0.2, "WTI": 0.0}`

**Direction-aware sign flip** (D-10-D1 contract):
```python
raw = weighted_signal / total_weight
if direction == "short":
    raw = -raw
return max(-1.0, min(1.0, raw))   # clamp [-1, 1]
```

---

### `calendar_rss/client.py` (service, RSS fetch + cache + filter window)

**Analog:** `news_aggregator.py:20-141` (template diretto, **exact match**).

**Imports + ctor** (verbatim pattern `news_aggregator.py:1-25`):
```python
"""RSS news aggregator: fetch + cache + filter by lookback window.

Mai bloccare il loop di trading: timeout brevi, errori per-feed isolati,
fallback a cache se nessun feed risponde.
"""
import logging
import socket
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

from config import Config
from models import NewsItem


_DEFAULT_TIMEOUT_SECONDS = 5


class NewsAggregator:
    def __init__(self, cfg: Config, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.log = logger or logging.getLogger(__name__)
        self.cache: list[NewsItem] = []
        self.last_fetch: datetime | None = None
```
**Adattamento Phase 10:** sostituire `NewsItem` con `CalendarEvent` dataclass (vedi RESEARCH §Pattern 2 lines 406-415); cache persistita su disco `data/cache/calendar_rss.json` invece che in-memory (D-10-B2 sopravvive restart).

**TTL on-demand pattern** (verbatim `news_aggregator.py:29-38`):
```python
def fetch_recent_news(self, force: bool = False, now: datetime | None = None) -> list[NewsItem]:
    now = now or datetime.now(tz=timezone.utc)
    interval = timedelta(minutes=self.cfg.NEWS_FETCH_INTERVAL_MINUTES)
    if (
        not force
        and self.last_fetch is not None
        and (now - self.last_fetch) < interval
        and self.cache
    ):
        return self._within_lookback(self.cache, now)
```
**Adattamento Phase 10:** TTL fisso 60min (D-10-B2) invece di `NEWS_FETCH_INTERVAL_MINUTES`; cache fonte = JSON disk read (`_load_cache()`) invece di in-memory `self.cache`; fallback su cache stale + warning se fetch fallisce (analog lines 44-46 `except Exception: ... self.log.warning(...)`).

**socket timeout try/finally** (verbatim `news_aggregator.py:56-62`):
```python
def parse_feed(self, feed_url: str) -> list[NewsItem]:
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_DEFAULT_TIMEOUT_SECONDS)
    try:
        parsed = feedparser.parse(feed_url)
    finally:
        socket.setdefaulttimeout(old_timeout)
```
**Adattamento Phase 10:** **COPIA LETTERALE** (Pitfall 7 RESEARCH §Common Pitfalls). NON skip questo pattern: `setdefaulttimeout` ha side-effect globale.

**bozo guard** (verbatim `news_aggregator.py:64-68`):
```python
entries = getattr(parsed, "entries", []) or []
if getattr(parsed, "bozo", False) and not entries:
    raise RuntimeError(
        f"feedparser bozo: {getattr(parsed, 'bozo_exception', None)}"
    )
```

**Lookback half-open filter** (verbatim `news_aggregator.py:125-129`):
```python
def _within_lookback(self, items: list[NewsItem], now: datetime) -> list[NewsItem]:
    cutoff = now - timedelta(hours=self.cfg.NEWS_LOOKBACK_HOURS)
    recent = [n for n in items if n.published >= cutoff]
    recent.sort(key=lambda n: n.published, reverse=True)
    return recent
```
**Adattamento Phase 10:** `window_minutes` parametro arg (D-10-B4 default 15), filtro bidirezionale `cutoff_start <= ev.event_time_utc < cutoff_end` (half-open, RESEARCH §Pattern 2 lines 447-453).

**Date parser difensivo** (verbatim `news_aggregator.py:100-121`):
```python
@staticmethod
def parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None
```
**Adattamento Phase 10:** NON usare `parsedate_to_datetime` per FF (Pitfall 4 RESEARCH §Common Pitfalls: FF è XML custom, `entry.published` non popolato). Usare `entry.get("date")` + `entry.get("time")` + `_NY = ZoneInfo("America/New_York")` + `dt_et.replace(tzinfo=_NY).astimezone(timezone.utc)` (D-10-B5 pattern, vedi RESEARCH §Pattern 5 lines 894-904).

---

### `mcp_tools/handlers/macro.py` (MCP-handler, request-response envelope)

**Analoghi:** `mcp_tools/handlers/backtest.py:55-136` (Tool registration) + `mcp_tools/handlers/market.py:56-122` (handler shape) + `mcp_tools/handlers/backtest.py:309-456` (handler bodies).

**Imports + envelope import** (verbatim `mcp_tools/handlers/backtest.py:22-31`):
```python
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.types import Tool

from mcp_tools.errors import ErrorCodes, envelope
```

**Tool definition pattern** (verbatim `mcp_tools/handlers/backtest.py:56-76`):
```python
RUN_BACKTEST_TOOL = Tool(
    name="run_backtest",
    description=(
        "Avvia backtest async sullo storico CSV per (symbol, timeframe, date_range, "
        "profile). Ritorna run_id immediato (non blocca); pollare get_backtest_metrics"
        "(run_id) per status/metrics. Max 1 run concorrente (cap MCP_MAX_CONCURRENT_RUNS); "
        "nuovo run mentre uno gira → error run_in_progress. Run prefix: "
        "mcp_<utc_ts>_<symbol>_<tf>_<profile>."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol":     {"type": "string", "enum": ["EURUSD", "GBPUSD", "USDJPY"]},
            "timeframe":  {"type": "string", "enum": ["M15", "M30", "H1"]},
            "date_start": {"type": "string", "description": "ISO8601 UTC, es. 2024-01-01T00:00:00Z"},
            "date_end":   {"type": "string", "description": "ISO8601 UTC, esclusivo"},
            "profile":    {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]},
        },
        "required": ["symbol", "timeframe", "date_start", "date_end", "profile"],
    },
)
```
**Adattamento Phase 10:** clonare in `GET_INTERMARKET_CONTEXT_TOOL` + `GET_ECONOMIC_CALENDAR_TOOL` (schema completi in RESEARCH §Pattern 6 lines 666-701).

**Handler signature pattern** (verbatim `mcp_tools/handlers/market.py:56-87`):
```python
def handle_get_market_snapshot(args: dict, mt5_client, cfg) -> dict:
    """R1 additive (D-C1): default 200 bars + indicators_extended + as_of_ts (D-D1).
    ...
    """
    symbol = args["symbol"]
    bars_n = int(args.get("bars", getattr(cfg, "MCP_DEFAULT_BARS", 200)))
    tf = args.get("timeframe", cfg.TIMEFRAME)
    as_of = args.get("as_of_ts")

    try:
        ohlc = BarSource.get(symbol, tf, bars_n,
                              as_of_ts=as_of, mt5_client=mt5_client)
    except FileNotFoundError as exc:
        return envelope(
            ErrorCodes.HISTORICAL_DATA_UNAVAILABLE,
            f"CSV mancante per {symbol}/{tf}",
            path=str(exc),
        )
    except ValueError as exc:
        msg = str(exc)
        if "warmup_insufficient" in msg:
            return envelope(ErrorCodes.AS_OF_TS_WARMUP_INSUFFICIENT, msg)
        return envelope(ErrorCodes.AS_OF_TS_OUT_OF_RANGE, msg)
```
**Adattamento Phase 10:**
- `handle_get_intermarket_context(args, macro_loader, cfg)` — se `cfg.ENABLE_INTERMARKET == False`: ritorna envelope success con `data={"intermarket_active": False, "signals": {}}` (no error). Vedi RESEARCH §Pattern 6 lines 704-717.
- `handle_get_economic_calendar(args, calendar_client, cfg)` — vedi RESEARCH §Pattern 6 lines 720-737.

**`envelope()` usage NB:** signature reale `mcp.errors.envelope` accetta `(code, msg, **extra_fields)` (vedi `mcp_tools/handlers/backtest.py:354-358`, `mcp_tools/handlers/market.py:78-82`), NON il pattern `envelope(ok=..., data=..., error=...)` mostrato in RESEARCH §Pattern 6. **Il planner deve fare grep `envelope(` in handlers esistenti** per validare la signature reale prima di scrivere `handle_*`. La forma corretta osservata in codebase:
```python
return envelope(
    ErrorCodes.HISTORICAL_DATA_UNAVAILABLE,
    f"CSV mancante per {symbol}/{tf}",
    path=str(exc),
)
# Success path: return diretto dict (NON envelope), come market handlers
return {"symbol": ..., "timeframe": ..., ...}
```

**ErrorCodes registration:** se servono nuovi codici per Phase 10 (es. `MACRO_CSV_MISSING`, `FF_FEED_UNAVAILABLE`), il planner deve verificare il file canonico (probabilmente `mcp/errors.py` — vedi `mcp_tools/errors.py:9` che fa re-export). Pattern Phase 8/9: nuovi error codes aggiunti là.

---

### `mcp_server.py` modify (MCP-router dispatch)

**Analog:** `mcp_tools/server.py` (il vero modulo; `mcp_server.py` è shim PEP 562, `mcp_server.py:15-29` re-esporta).

**Import block additivo** (analog `mcp_tools/server.py:54-81`):
```python
from mcp_tools.handlers.backtest import (
    CANCEL_BACKTEST_TOOL,
    GET_BACKTEST_METRICS_TOOL,
    RUN_BACKTEST_TOOL,
    WALK_FORWARD_VALIDATE_TOOL,
    handle_cancel_backtest,
    handle_get_backtest_metrics,
    handle_run_backtest,
    handle_walk_forward_validate,
)
```
**Adattamento Phase 10:** aggiungere
```python
from mcp_tools.handlers.macro import (
    GET_INTERMARKET_CONTEXT_TOOL,
    GET_ECONOMIC_CALENDAR_TOOL,
    handle_get_intermarket_context,
    handle_get_economic_calendar,
)
```

**Singleton bootstrap pattern** (analog `mcp_tools/server.py:139-155` `MLFilter singleton`):
```python
# Phase 8: MLFilter singleton load (best-effort, fallisce graceful)
global ml_filter_singleton
enable_ml = getattr(cfg, "ENABLE_ML_FILTER", False)
bundle_path = getattr(cfg, "ML_MODEL_PATH", None)
if enable_ml and bundle_path and Path(bundle_path).exists():
    try:
        from ml.inference import MLFilter
        ml_filter_singleton = MLFilter.load(bundle_path)
        log.info("MLFilter singleton caricato: %s", bundle_path)
    except Exception as exc:
        log.error("MLFilter load fallita (graceful): %s", exc)
        ml_filter_singleton = None
else:
    log.info(
        "MLFilter singleton skip (ENABLE_ML_FILTER=%s bundle_exists=%s)",
        enable_ml, bool(bundle_path and Path(bundle_path).exists()),
    )
```
**Adattamento Phase 10:** aggiungere `macro_loader_singleton` + `calendar_client_singleton` in `_bootstrap_state()`:
```python
# Phase 10 MCP-10: MacroLoader singleton (gated da ENABLE_INTERMARKET)
global macro_loader_singleton
if getattr(cfg, "ENABLE_INTERMARKET", False):
    try:
        from intermarket.loader import MacroLoader
        macro_loader_singleton = MacroLoader.from_repo()
        log.info("MacroLoader singleton caricato")
    except Exception as exc:
        log.error("MacroLoader load fallita (graceful): %s", exc)
        macro_loader_singleton = None
else:
    macro_loader_singleton = None
    log.info("MacroLoader singleton skip (ENABLE_INTERMARKET=false)")

# Phase 10 MCP-13: CalendarRSSClient singleton (sempre on — advisory tool)
from calendar_rss.client import CalendarRSSClient
calendar_client_singleton = CalendarRSSClient(cfg, log)
```

**Tool registration in `list_tools()`** (analog `mcp_tools/server.py:316-327`):
```python
# Phase 6 Wave 2 — backtest control plane (MCP-01/02/03 + cancel D-A4)
RUN_BACKTEST_TOOL,
GET_BACKTEST_METRICS_TOOL,
WALK_FORWARD_VALIDATE_TOOL,
CANCEL_BACKTEST_TOOL,
# Phase 6 Wave 3 — position management (MCP-16, MCP-17)
MODIFY_POSITION_TOOL,
GET_POSITION_STATE_TOOL,
# Phase 8 Wave 0 — ML control plane (MCP-04/05/06)
TRAIN_ML_FILTER_TOOL,
PREDICT_TRADE_QUALITY_TOOL,
GET_ML_CALIBRATION_TOOL,
```
**Adattamento Phase 10:** aggiungere dopo i tool Phase 8:
```python
# Phase 10 — intermarket + calendar (MCP-10, MCP-13)
GET_INTERMARKET_CONTEXT_TOOL,
GET_ECONOMIC_CALENDAR_TOOL,
```

**Dispatch in `call_tool()`** (analog `mcp_tools/server.py:412-427` ML branch):
```python
# Phase 8 — ML control plane (MCP-04/05/06)
if name in ("train_ml_filter", "predict_trade_quality", "get_ml_calibration"):
    if name == "train_ml_filter":
        if job_queue is None:
            return _text(envelope(
                ErrorCodes.INTERNAL_ERROR,
                "JobQueue non inizializzata: chiamare _bootstrap_state() prima",
                tool=name,
            ))
        return _text(handle_train_ml_filter(arguments, job_queue, cfg))
    if name == "predict_trade_quality":
        return _text(handle_predict_trade_quality(
            arguments, ml_filter_singleton, mt5, cfg,
        ))
    # get_ml_calibration
    return _text(handle_get_ml_calibration(arguments, cfg))
```
**Adattamento Phase 10:**
```python
# Phase 10 — intermarket + calendar (MCP-10, MCP-13)
if name == "get_intermarket_context":
    return _text(handle_get_intermarket_context(
        arguments, macro_loader_singleton, cfg,
    ))
if name == "get_economic_calendar":
    return _text(handle_get_economic_calendar(
        arguments, calendar_client_singleton, cfg,
    ))
```

---

### `config.py` extension (env flag rollout)

**Analog:** `config.py:214-235` `_attach_news_sentiment(cls)` — **template diretto exact match** (anche citato in CONTEXT.md §canonical_refs e §Established Patterns).

**Verbatim pattern** (`config.py:214-235`):
```python
def _attach_news_sentiment(cls):
    cls.ENABLE_NEWS_SENTIMENT = _get_bool("ENABLE_NEWS_SENTIMENT", False)
    cls.NEWS_FETCH_INTERVAL_MINUTES = max(1, int(os.getenv("NEWS_FETCH_INTERVAL_MINUTES", "15")))
    cls.NEWS_LOOKBACK_HOURS = max(1, int(os.getenv("NEWS_LOOKBACK_HOURS", "2")))
    cls.NEWS_CACHE_MAX_HOURS = max(1, int(os.getenv("NEWS_CACHE_MAX_HOURS", "24")))
    cls.SENTIMENT_MIN_STRENGTH_FILTER = float(os.getenv("SENTIMENT_MIN_STRENGTH_FILTER", "0.6"))
    cls.SENTIMENT_BOOST_FACTOR = float(os.getenv("SENTIMENT_BOOST_FACTOR", "0.15"))
    action = os.getenv("SENTIMENT_CONFLICT_ACTION", "delay").strip().lower()
    if action not in ("skip", "delay", "reduce_confidence"):
        raise ValueError(
            f"SENTIMENT_CONFLICT_ACTION={action} non valido. "
            f"Ammessi: skip, delay, reduce_confidence"
        )
    cls.SENTIMENT_CONFLICT_ACTION = action
    cls.SENTIMENT_CONFLICT_DELAY_MINUTES = max(
        1, int(os.getenv("SENTIMENT_CONFLICT_DELAY_MINUTES", "60"))
    )
    cls.RSS_FEEDS = _get_list("RSS_FEEDS", [])
    return cls


_attach_news_sentiment(Config)
```
**Adattamento Phase 10:** aggiungere nuova funzione `_attach_intermarket_macro(cls)` + chiamata `_attach_intermarket_macro(Config)`:
```python
def _attach_intermarket_macro(cls):
    cls.ENABLE_INTERMARKET = _get_bool("ENABLE_INTERMARKET", False)  # D-10-D2 default OFF
    cls.MACRO_CSV_ROOT = os.getenv("MACRO_CSV_ROOT", "data/historical/macro").strip()
    cls.FF_RSS_URL = os.getenv(
        "FF_RSS_URL",
        "https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
    ).strip()
    cls.CALENDAR_CACHE_TTL_MINUTES = max(
        1, int(os.getenv("CALENDAR_CACHE_TTL_MINUTES", "60"))
    )
    cls.CALENDAR_CACHE_PATH = os.getenv(
        "CALENDAR_CACHE_PATH", "data/cache/calendar_rss.json"
    ).strip()
    cls.CALENDAR_DEFAULT_WINDOW_MINUTES = max(
        1, int(os.getenv("CALENDAR_DEFAULT_WINDOW_MINUTES", "15"))
    )
    return cls


_attach_intermarket_macro(Config)
```
**Estensione `.env.example`:** documentare nuovi 5 env (`ENABLE_INTERMARKET=false`, `MACRO_CSV_ROOT=...`, `FF_RSS_URL=...`, `CALENDAR_CACHE_TTL_MINUTES=60`, `CALENDAR_CACHE_PATH=...`, `CALENDAR_DEFAULT_WINDOW_MINUTES=15`). Sezione analoga a quella esistente per `ENABLE_NEWS_SENTIMENT` block.

---

### `strategy/context.py:17` modify (dataclass field signature extend)

**Analog:** self (`strategy/context.py:1-23`, **exact match — modifica in-place**).

**Stato esistente** (verbatim `strategy/context.py:7-23`):
```python
@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timeframe: str
    profile: str                          # "CONSERVATIVE" | "MODERATE" | "AGGRESSIVE"
    sr: dict
    regime: str                           # "compressed" | "normal" | "expanded"
    patterns: list                        # list[PatternHit] from Phase 3 scan_patterns()
    symbol_info: object
    pip_size: float
    intermarket_score_fn: Callable | None = None  # Phase 10 hook
    news_blackout_fn: Callable | None = None      # Phase 10 hook
    recent_trades: list = field(default_factory=list)
    spread_baseline_pips: float | None = None
    # Campi privati per adapter (esclusi da compare/hash/repr)
    _bars: list = field(default_factory=list, compare=False, hash=False, repr=False)
    _indicators: object = field(default=None, compare=False, hash=False, repr=False)
```

**Modifica D-10-D1:** il field type stay `Callable | None` (Callable in `typing` non vincola signature). La signature contract attesa diventa `Callable[[str, Literal["long","short"]], float]`. Aggiornare commento inline:
```python
intermarket_score_fn: Callable | None = None  # Phase 10 D-10-D1: fn(symbol, direction) -> float [-1,1]
```
**Decisione planner:** `news_blackout_fn` (line 18) può rimanere come stub `Callable | None = None` per Phase 11+ retrofit (deferred D-10-C0), oppure essere rimosso (CONTEXT.md L129). Raccomandato: tenere dormant + commento `# Phase 11+ retrofit (D-10-C0: drop blackout in Phase 10)`.

---

### `strategy/confluence.py:266` modify (callsite signature extend)

**Analog:** self (`strategy/confluence.py:263-270`, **exact match — modifica in-place**).

**Stato esistente** (verbatim `strategy/confluence.py:263-269`):
```python
# Adjuster 1: intermarket_confirmation (D-09 stub: callable opzionale)
if ctx.intermarket_score_fn is not None:
    try:
        if ctx.intermarket_score_fn(ctx.symbol) > 0:
            delta += float(adj["intermarket_confirmation"])
    except Exception:
        pass  # stub safety: zero-impact se chiamata fallisce
```

**Modifica D-10-D1:** la function `compute_confidence` (firma `compute_confidence(grade, ctx, factors=None, cfg=None)` da `strategy/confluence.py:246-251`) NON ha `direction` parameter. Il planner deve scegliere tra due path:

**Path A (raccomandato — minimal change):** estendere signature `compute_confidence(grade, ctx, direction, factors=None, cfg=None)`, aggiornare il chiamante (cercare con grep `compute_confidence(` in repo) per passare anche `direction`. Più pulito ma touchpoint maggiore.

**Path B (alternativo — direction su ctx):** aggiungere `direction: str | None = None` come field a `StrategyContext` (in `strategy/context.py`), e usare `ctx.direction` qui. Più additivo ma sporca il context con field operativo. **Pitfall 5 RESEARCH §Common Pitfalls L833-835** suggerisce questa decisione esplicita.

**In entrambi i casi**, il callsite diventa:
```python
if ctx.intermarket_score_fn is not None:
    try:
        if ctx.intermarket_score_fn(ctx.symbol, direction) > 0:   # ← direction nuovo arg
            delta += float(adj["intermarket_confirmation"])
    except Exception as exc:
        # Pitfall 5: log debug per visibilità (il try/except inghiotte silently
        # TypeError se signature mismatch). Aggiungere logger se non esiste.
        pass  # stub safety: zero-impact se chiamata fallisce
```
**Pitfall 5 raccomandazione:** sostituire `pass` con `_log.debug("intermarket_score_fn error: %s", exc)` per visibility (RESEARCH §Common Pitfalls L837). Decisione planner.

---

### `strategy/_shim.py:133` modify (wire-up constructor injection)

**Analog:** self (`strategy/_shim.py:126-135`) + analogo MLFilter singleton load (`mcp_tools/server.py:139-155`).

**Stato esistente** (verbatim `strategy/_shim.py:127-135`):
```python
try:
    ctx = build_ctx_live(
        symbol=symbol,
        mt5_client=self.mt5,
        profile=getattr(cfg, "RISK_MODE", "MODERATE"),
        cfg=cfg,
        intermarket_score_fn=None,
        news_blackout_fn=getattr(self.env, "is_news_window", None) if self.env else None,
    )
```

**Modifica D-10-D2:** sostituire `intermarket_score_fn=None` con il singleton init-time (analog Phase 7 `_init_intermarket_ctx`, RESEARCH §Code Examples L920-941):
```python
intermarket_score_fn=self._intermarket_score_fn,  # init-time singleton, D-10-D2
```
Dove `self._intermarket_score_fn` è inizializzato in `IntradayStrategy.__init__` (file da identificare con grep — probabilmente `strategy/_shim.py` ctor o `strategy/__init__.py`):
```python
def __init__(self, cfg, mt5, env=None, log=None):
    ...
    self._intermarket_score_fn = self._build_intermarket_score_fn(cfg)

@staticmethod
def _build_intermarket_score_fn(cfg) -> "Callable | None":
    """D-10-D2: zero-impact rollout. Default OFF, opt-in via ENABLE_INTERMARKET=true."""
    if not getattr(cfg, "ENABLE_INTERMARKET", False):
        return None
    try:
        from intermarket.loader import MacroLoader
        from intermarket.score import build_intermarket_score
        return build_intermarket_score(MacroLoader.from_repo())
    except Exception as exc:
        # Phase 8 pattern: bootstrap graceful — log + None
        logging.getLogger(__name__).error(
            "IntradayStrategy intermarket bootstrap fallito: %s", exc
        )
        return None
```

---

### `tests/test_intermarket_loader.py` (test, CSV + sha256 + strict-<)

**Analog:** `tests/test_backtest_loader.py` (CSV load test) + `tests/test_baseline_determinism.py` (sha256 test).

**Required test cases** (RESEARCH §Validation Architecture + §Pattern 4):
1. `test_csv_read_smoke` — load 200-row fixture `tests/fixtures/macro_dxy_smoke.csv`, asserisci 200 row + columns `["ts_utc","close"]`.
2. `test_strict_lt_no_future_leakage` — fixture con bar @ exact `ts_utc=T`, `close_at("DXY", T)` ritorna bar `idx-1` (NON quello @ T).
3. `test_sha256_anchor_stable` — chiamare `MacroLoader.from_repo()` twice, asserisci `loader.sha256("DXY")` stesso valore.
4. `test_missing_symbol_returns_none` — `loader.close_at("XYZ", now)` → None.
5. `test_missing_csv_raises` — `MacroLoader.from_repo(root=Path("/nonexistent"))` → FileNotFoundError.

**Fixture pattern** (analog `tests/fixtures/eurusd_5bars.csv`): formato semicolon, header `Data;Ora;Close` (3 colonne; planner decide se aggiungere O/H/L/V se vuole copia esatta BACK-01 e ignorarli nel parsing).

---

### `tests/test_calendar_rss_client.py` (test, RSS mock + DST regression)

**Analog:** `tests/test_news_aggregator.py:31-80` — **template diretto exact match** (mocked feedparser via `unittest.mock.patch`).

**Imports + mock helper pattern** (verbatim `tests/test_news_aggregator.py:1-40`):
```python
"""Test NewsAggregator: parse_feed, fetch_recent_news, clean_cache, parse_date."""
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from models import NewsItem
from news_aggregator import NewsAggregator


def _make_cfg(**overrides):
    cfg = MagicMock()
    cfg.RSS_FEEDS = ["https://example.com/feed1", "https://example.com/feed2"]
    cfg.NEWS_FETCH_INTERVAL_MINUTES = 15
    cfg.NEWS_LOOKBACK_HOURS = 2
    cfg.NEWS_CACHE_MAX_HOURS = 24
    cfg.ENABLE_NEWS_SENTIMENT = True
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _fake_parsed(entries: list[dict], title: str = "MockFeed", bozo: bool = False):
    parsed = SimpleNamespace()
    parsed.feed = {"title": title}
    parsed.entries = entries
    parsed.bozo = bozo
    parsed.bozo_exception = None
    return parsed
```

**Mock injection pattern** (verbatim `tests/test_news_aggregator.py:63-69`):
```python
with patch("news_aggregator.feedparser.parse", return_value=parsed):
    items = agg.parse_feed("https://example.com/feed1")
assert len(items) == 2
```
**Adattamento Phase 10:** patch `calendar_rss.client.feedparser.parse`, fixture XML deterministica caricata con `feedparser.parse(open("tests/fixtures/ff_rss_smoke.xml").read())` come baseline reference.

**Required test cases** (RESEARCH §Validation Architecture + §Common Pitfalls):
1. `test_parse_event_smoke` — load `ff_rss_smoke.xml`, asserisci 10 eventi parsati + tutti campi pieni.
2. `test_et_to_utc_edt_summer` — evento "05-12-2026 12:30pm" → UTC `2026-05-12 16:30:00+00:00`.
3. `test_et_to_utc_est_winter` — evento "01-15-2026 12:30pm" → UTC `2026-01-15 17:30:00+00:00`.
4. `test_dst_cross_march_boundary` — fixture `ff_rss_dst_cross.xml`, eventi pre/post DST start (2nd Sun March) → asserisci offset switch corretto.
5. `test_dst_cross_november_boundary` — idem per DST end.
6. `test_all_day_holiday_event` — evento "All Day" + impact="Holiday" → ritornato con `all_day=true`, `event_time_utc=00:00 UTC` nominal (D-10-B6).
7. `test_all_day_non_holiday_skipped` — evento "All Day" + impact="Medium" → None (filtrato out).
8. `test_tentative_skipped` — evento impact="Tentative" → None (D-10-B6).
9. `test_cache_ttl_under_60min_returns_cached` — mock `now` < TTL, asserisci `_fetch_remote` NOT called.
10. `test_cache_stale_over_60min_refetches` — mock `now` > TTL, asserisci `_fetch_remote` called.
11. `test_fetch_failure_falls_back_to_cache` — mock `feedparser.parse` raise, asserisci ritorna `cached["events"]` (analog `news_aggregator.py:44-46`).
12. `test_filter_window_pair_aware_USD_only` — `pair="EURUSD"` → solo eventi `country in ["USD","EUR"]`.
13. `test_filter_min_impact_high_default` — eventi Low/Medium filtrati out di default.
14. `test_cache_json_roundtrip` — save + load preserva CalendarEvent uguali (Pitfall 6 datetime serialization).

---

### `tests/test_mcp_handlers_macro.py` (test, MCP handler envelope)

**Analog:** `tests/test_mcp_handlers_market.py` + `tests/test_mcp_handlers_backtest.py`.

**Mock cfg + handler pattern** (analog `tests/test_mcp_handlers_market.py:46-58`):
```python
@pytest.fixture
def mock_mt5():
    """Mock Mt5Client per test handler R1/R2."""
    m = MagicMock()
    m.get_ohlc.side_effect = lambda sym, tf, n: _bullish_ohlc(n)
    m.get_symbol_info.return_value = SimpleNamespace(
        bid=1.105, ask=1.1051, point=0.00001, digits=5,
    ...
```

**Required test cases:**
1. `test_handle_get_intermarket_context_disabled` — `cfg.ENABLE_INTERMARKET=False` → envelope success con `data["intermarket_active"]=False`.
2. `test_handle_get_intermarket_context_enabled_signals` — `cfg.ENABLE_INTERMARKET=True`, mock loader, asserisci envelope success con `data["signals"]` non vuoto.
3. `test_handle_get_intermarket_context_loader_none` — loader=None (bootstrap fail) → envelope error code `internal_error`.
4. `test_handle_get_economic_calendar_default_filter_high` — mock client, asserisci ritorna solo `impact="High"` events.
5. `test_handle_get_economic_calendar_pair_aware` — `args["pair"]="EURUSD"` → solo `country in ["USD","EUR"]`.
6. `test_handle_get_economic_calendar_fetch_fail_envelope` — mock client raise, asserisci envelope error.
7. `test_handle_get_economic_calendar_window_minutes_override` — `window_minutes=60`, asserisci filter usa 60min.

---

### `tests/test_phase10_no_phase5_drift.py` (regression test)

**Analoghi composti:** `tests/test_baseline_determinism.py` (sha256) + `tests/test_baseline_dataset_writer.py` (schema-v2 keys assertion).

**Required gate** (Pitfall 8 RESEARCH §Common Pitfalls):
```python
def test_dataset_writer_schema_v2_immutato():
    """D-10-C0: Phase 5 parquet schema-v2 IMMUTATO. Zero modifica a _build_required_keys_v2()."""
    from backtest.baseline.dataset_writer import _build_required_keys_v2  # o constant analog
    keys = _build_required_keys_v2()
    # Asserisci che NESSUN key contenga "intermarket" o "macro" o "news"
    for k in keys:
        assert "intermarket" not in k.lower()
        assert "macro" not in k.lower()
        assert "news" not in k.lower()
    # Asserisci row count expected da baseline-2026-05-12.md
    assert len(keys) == 59  # Phase 5 schema-v2 1076 × 59 cols certificato

def test_baseline_parquet_sha256_unchanged():
    """D-10-C0: backtest baseline part-0.parquet sha256 deve matchare baseline cert."""
    from backtest.baseline.determinism import file_sha256
    expected = "<sha256 from baseline-2026-05-12.md>"  # da iniettare
    actual = file_sha256(Path("data/training/baseline_decisions/part-0.parquet"))
    assert actual == expected
```
**Decisione planner:** il valore `expected` sha256 va letto dal report Phase 5 (`baseline-2026-05-12.md` o equivalente plan 05-09 cert). Plan-checker iter: confermare che il file esiste prima di scrivere il test.

---

### `scripts/refresh_macro_csv.py` (ops-script, Stooq download)

**Analog:** `scripts/run_baseline_05_09.py` (CLI argparse + logging + main `if __name__`), e pattern `urllib.request.urlretrieve` per download.

**Required logic** (Pitfall 1 RESEARCH §Common Pitfalls):
- Iterate `MACRO_SYMBOLS = ["DXY", "US10Y", "XAUUSD", "WTI"]`.
- `time.sleep(30)` tra simboli per evitare CAPTCHA Stooq.
- Detect HTML response: se `response.text` inizia con `<!DOCTYPE html>` → raise + abort (NON scrivere CSV).
- Post-download: row count > 5000 obbligatorio (23.6y ~6000 daily bar) altrimenti abort.
- Normalizzare CSV a formato BACK-01 (semicolon `Data;Ora;Close`, DD/MM/YYYY) se necessario.
- Log + print sha256 nuovo. Confronto vs sha256 pre-esistente: warning se cambia (operator deve essere consapevole D-10-A4).
- `--symbols` flag CLI per refresh selettivo.
- Documentare in `SETUP.md` o `README.md` il manual fallback Stooq → `https://stooq.com/q/d/?s=^dxy&i=d`.

---

## Shared Patterns

### MCP Envelope (Phase 6/8 convention)
**Source:** `mcp_tools/errors.py:9` → `mcp.errors.envelope` (canonical in `mcp/errors.py`).
**Apply to:** All Phase 10 MCP handlers (`handle_get_intermarket_context`, `handle_get_economic_calendar`).

**Verbatim** (`mcp_tools/handlers/market.py:78-82`):
```python
return envelope(
    ErrorCodes.HISTORICAL_DATA_UNAVAILABLE,
    f"CSV mancante per {symbol}/{tf}",
    path=str(exc),
)
```
**Convenzione:** error = `envelope(code, msg, **extra)`; success = ritorno dict diretto (NON wrapped). Vedi `mcp_tools/handlers/market.py:114-122` per esempio success.

### Env Flag Zero-Impact Rollout
**Source:** `config.py:214-235` `_attach_news_sentiment` + Phase 7 `ENABLE_ML_FILTER` (vedi `mcp_tools/server.py:141-155`).
**Apply to:** `ENABLE_INTERMARKET` (D-10-D2 default `false`) + tutti env Phase 10.

**Verbatim** (`config.py:215`):
```python
cls.ENABLE_NEWS_SENTIMENT = _get_bool("ENABLE_NEWS_SENTIMENT", False)
```

### sha256 Anchor for Data Integrity
**Source:** `backtest/baseline/determinism.py:29-35` `file_sha256(path)`.
**Apply to:** `MacroLoader.from_repo()` + Phase 7 `metadata.json` (D-10-A4 extension).

**Verbatim:**
```python
def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
```
**Re-export pattern:** Phase 10 può importare direttamente `from backtest.baseline.determinism import file_sha256` invece di reimplementare.

### Italian-CSV Parsing (BACK-01)
**Source:** `backtest/loader.py:44-56`.
**Apply to:** `MacroLoader._read_csv` (con adattamenti: no GMT-6 offset, single `Close` column).

**Verbatim:**
```python
df = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str)
df.columns = [c.strip() for c in df.columns]
df["dt_source"] = pd.to_datetime(
    df["Data"] + " " + df["Ora"], format="%d/%m/%Y %H:%M:%S"
)
```

### socket Timeout try/finally
**Source:** `news_aggregator.py:56-62`.
**Apply to:** `CalendarRSSClient._fetch_remote`.
**Pitfall 7 reference:** NON skip questo pattern — `socket.setdefaulttimeout` ha side-effect globale.

**Verbatim:**
```python
old_timeout = socket.getdefaulttimeout()
socket.setdefaulttimeout(_DEFAULT_TIMEOUT_SECONDS)
try:
    parsed = feedparser.parse(feed_url)
finally:
    socket.setdefaulttimeout(old_timeout)
```

### feedparser bozo Guard
**Source:** `news_aggregator.py:64-68`.
**Apply to:** `CalendarRSSClient._fetch_remote`.

**Verbatim:**
```python
entries = getattr(parsed, "entries", []) or []
if getattr(parsed, "bozo", False) and not entries:
    raise RuntimeError(
        f"feedparser bozo: {getattr(parsed, 'bozo_exception', None)}"
    )
```

### Pure-fn `try/except: pass` No-Op Safety
**Source:** `strategy/confluence.py:263-269` (adjuster pattern).
**Apply to:** modifica callsite `intermarket_score_fn(ctx.symbol, direction)`. Pitfall 5: aggiungere `_log.debug(...)` invece di `pass` per visibilità (DECISIONE PLANNER).

### Singleton Bootstrap with Graceful Failure
**Source:** `mcp_tools/server.py:139-155` (MLFilter pattern).
**Apply to:** `macro_loader_singleton` + `calendar_client_singleton` in `_bootstrap_state()`.

### Test Mock Pattern (cfg + RSS feedparser)
**Source:** `tests/test_news_aggregator.py:13-32` (`_make_cfg` + `_fake_parsed` helpers).
**Apply to:** `tests/test_calendar_rss_client.py` (copia letterale + adattamento per CalendarEvent).

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `tests/fixtures/ff_rss_smoke.xml` | fixture | Nessun fixture RSS XML esistente nel codebase. Wave 0 spike obbligatorio (RESEARCH §Wave 0 Gaps): scaricare 1 entry FF reale via WebFetch live, salvare verbatim come baseline. |
| `tests/fixtures/ff_rss_dst_cross.xml` | fixture | Variante sintetica del precedente con eventi @ 2nd Sun March + 1st Sun November DST boundary. Va costruito ad hoc (no analog), ma usa lo stesso schema XML di `ff_rss_smoke.xml`. |

---

## Metadata

**Analog search scope:**
- Top-level Python files (`news_aggregator.py`, `config.py`, `mcp_server.py`, `models.py`, `logger.py`)
- `backtest/`, `backtest/baseline/`
- `mcp_tools/`, `mcp_tools/handlers/`
- `strategy/`, `strategy/adapters/`
- `tests/` (test patterns) + `tests/fixtures/`
- `scripts/` (CLI patterns)
- `data/historical/` (CSV formats discovery — **flagged: existing DXY CSV in investing.com format, NOT BACK-01 semicolon**)

**Files scanned:** ~25 production files + ~10 test files.

**Pattern extraction date:** 2026-05-13

**Critical follow-ups for planner:**
1. **DXY format discrepancy** — `data/historical/DXY/1D.csv` esiste già in formato investing.com (`"Data","Ultimo",...` comma-separated, virgola decimale, DD.MM.YYYY) NON BACK-01 semicolon. Il D-10-A4 refresh script dovrà normalizzare (raccomandato) o il loader supportare entrambi. Decisione esplicita richiesta nel PLAN.
2. **`envelope()` signature discovery** — RESEARCH §Pattern 6 usa shape `envelope(ok=..., data=..., error=...)` ma il codebase usa shape `envelope(code, msg, **extra)`. Plan-checker iter: validare con `grep "envelope(" mcp_tools/handlers/` la signature reale prima di scrivere `handle_*`.
3. **`compute_confidence` signature change** — D-10-D1 richiede passare `direction` al callsite confluence:266. Scelta Path A (estendere `compute_confidence` signature) vs Path B (aggiungere `direction` field a StrategyContext) deve essere esplicita in PLAN. Path A consigliato (minimal touch + esplicito).
4. **Pitfall 5 visibility patch** — il `try/except: pass` esistente in confluence:268-269 inghiotte silently TypeError. RESEARCH consiglia `_log.debug(...)`. PLAN deve dichiarare se applica patch o accetta silent risk.
5. **`news_blackout_fn` dormancy decision** — D-10-C0 droppa blackout. `news_blackout_fn` field rimane in context (line 18) come stub dormant o viene rimosso? Decisione planner esplicita.
6. **Plan 05-09 sha256 baseline** — il test regression `test_baseline_parquet_sha256_unchanged` necessita di leggere il valore certificato. Plan-checker iter: verificare path/valore in `baseline-2026-05-12.md` o report equivalent.
