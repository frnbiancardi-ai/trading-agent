# Phase 10: Intermarket + News — Research

**Researched:** 2026-05-13
**Domain:** static macro CSV loader + ForexFactory RSS calendar + MCP envelope wiring + intermarket score adjuster
**Confidence:** HIGH (CONTEXT.md locked 35+ decisioni; FF feed schema verificato live; analoghi codebase abbondanti)

---

## Summary

Phase 10 consegna **due capability live-only complementari**, scope-ridotte da D-10-C0:

1. **MCP-10 intermarket** = 4 macro CSV (DXY, US10Y, XAUUSD, WTI) **statici committati** a `data/historical/macro/`, daily-close, sha256-anchored, **23.6y coverage 2002-10-21 → today** (allineato Phase 5 baseline parquet). Loader `intermarket_loader.py` + `build_intermarket_score(symbol, direction)` puro-funzione + adjuster `intermarket_confirmation` in `strategy/confluence.py:266` (signature extend additive backward-compat). `ENABLE_INTERMARKET=false` default = zero-impact rollout (analogia letterale Phase 7 `ENABLE_ML_FILTER`).

2. **MCP-13 calendar advisory** = `get_economic_calendar(window_minutes)` tool MCP che fetch live ForexFactory RSS `https://nfs.faireconomy.media/ff_calendar_thisweek.xml` (next 7 days) con cache TTL 60min. **Live-only, NO auto-reject** in `strategy.py`/`risk_engine.py` (D-10-C0). Consumato manualmente da forex-trader-pro skill come pre-decision check (doc patch only).

Phase 5 parquet schema-v2 1076×59 **IMMUTATO** (zero re-baseline, zero schema migration, zero FRED reconstruction). ROADMAP SC#3 DEVIATED esplicito.

**Primary recommendation:** Riusare al massimo gli analoghi codebase. `news_aggregator.py` = template diretto per RSS+cache+lookback (141 LOC). `backtest/loader.py` BACK-01 = template per CSV statico semicolon Italian-format (esiste già `data/historical/DXY/1Dyapt2.csv` 3084 row 23.6y in formato BACK-01 — **riuso diretto del loader esistente**). `backtest/baseline/determinism.py::file_sha256` = pattern sha256 anchor verificato. `mcp_tools/handlers/backtest.py` = template handler MCP envelope.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions (35+)

**Area A — Intermarket data (5 decisioni):**
- **D-10-A0:** ROADMAP letterale full scope: DXY + US10Y + XAUUSD + WTI tutti e 4.
- **D-10-A1:** CSV statici Stooq committati `data/historical/macro/{DXY,US10Y,XAUUSD,WTI}/daily.csv`. Niente API runtime. sha256-anchored.
- **D-10-A2:** Daily-close only. Bridge a M15/M30/H1 via lookup `close(D-1)` strict-< (no future leakage, pattern `news_aggregator._within_lookback`).
- **D-10-A3:** 23.6y coverage 2002-10-21 → today (allineamento Phase 5 baseline parquet).
- **D-10-A4:** Refresh manuale on-demand via `scripts/refresh_macro_csv.py`. sha256 registrato in `metadata.json` bundle ML. Phase 7 retrain abort se sha256 cambia senza intent.

**Area B — Calendar (6 decisioni, post C0):**
- **D-10-B1:** Solo FF RSS **live forward-looking** (next 7 days). NO historical CSV committato. Pattern `news_aggregator.py` (RSS+cache+lookback) riusato. Currencies: USD/EUR/GBP/JPY/AUD/CAD/CHF/NZD.
- **D-10-B2:** Fetch on-demand + TTL 60min. Cache persistita `data/cache/calendar_rss.json` con timestamp.
- **D-10-B3:** Pair-aware High-only nel default. Args: `min_impact='High'`, `currencies=derived from pair`, fallback `['USD','EUR','GBP','JPY']`.
- **D-10-B4:** `window_minutes` default = 15 (ROADMAP SC#3 letterale anche se NON auto-reject). Skill può override.
- **D-10-B5:** ET→UTC via `zoneinfo('America/New_York')` (DST-aware). FF feed timezone implicita ET (default NY).
- **D-10-B6:** Skip Tentative + All Day. Holiday events (Christmas, NFP, etc.) ritornati con `event_time=00:00 UTC` + flag `all_day=true`.

**Area C — Backtest blackout (1 SCOPE OVERRIDE):**
- **D-10-C0:** **DROP backtest blackout totalmente.** Phase 5 parquet IMMUTATO. MCP-13 live-only no gating in strategy.py/risk_engine.py.

**Area D — Strategy wiring (3 decisioni):**
- **D-10-D1:** Signature extend additive `intermarket_score_fn(symbol: str, direction: Literal["long","short"]) -> float`. Score positivo = CONFERMA direction. Backward-compat con stub-None caller.
- **D-10-D2:** `ENABLE_INTERMARKET=false` default. Phase 5 baseline immutato. Zero-impact rollout.
- **D-10-D3:** Skill forex-trader-pro doc patch only (sezione "Pre-decision news check"). NO auto-inject pre-flight.

### Claude's Discretion (Phase 10 planner decide)
- Aggregazione signal interna a `build_intermarket_score` (peso DXY vs US10Y vs XAUUSD vs WTI per pair).
- Threshold `if effective > threshold` in `compute_confidence` (valore in `config/strategy.yaml` adjusters).
- Audit logging MCP-13 (logs/mcp.log o estensione logger.py).
- Fallback FF RSS down (cache stale > TTL → return cached + warning, OR raise).
- Dataclass/Pydantic model per response MCP-13 (allineato MCP envelope Phase 6/8).

### Deferred Ideas (OUT OF SCOPE)
- MCP-10 H1 intraday granularity (Phase 11+).
- Auto-refresh cron weekly macro CSV (Phase 11+).
- Configurabile pre/post blackout window via env (moot post C0).
- Backtest blackout retroactive (Phase 11+ se paper trading rivela news-overfit).
- Risk_engine news soft-warning live (Phase 11+).
- Skill auto-inject MCP-13 pre-flight (Phase 11+).
- Re-baseline Phase 5 con `ENABLE_INTERMARKET=true` (Plan 10-XX deferred).

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-10 | `get_intermarket_context()` → DXY, US10Y, gold, oil → bias signals | Area A (loader+CSV) + Area D (strategy wire) + §Standard Stack (Stooq URL discovery) + §Architecture Pattern 1 (intermarket score aggregator) + §Pattern 6 (MCP envelope) |
| MCP-13 | `get_economic_calendar(window_minutes)` → upcoming events + impact flag | Area B (FF RSS) + §Standard Stack (feedparser) + §Architecture Pattern 2 (RSS+cache+lookback analog) + §Pattern 5 (ET→UTC zoneinfo) + §Pattern 6 (MCP envelope) |

ROADMAP SC#3 (auto-reject blackout) DEVIATED via D-10-C0 — non implementato in questo phase.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Macro CSV loader (DXY/US10Y/XAUUSD/WTI) | Data layer (`intermarket/loader.py`) | — | Pure I/O, no broker call, daily-close lookup strict-< pattern. Analog `backtest/loader.py`. |
| Intermarket score aggregator | Strategy layer (`intermarket/score.py`) | — | Pure-function `(symbol, direction) -> float`. Consumato da `confluence.py:266` via callable injection (D-10-D1). |
| Strategy wiring (intermarket adjuster) | Strategy layer (`strategy/confluence.py`) | — | Adjuster hook già stub-active a riga 263-269. Signature extend additive. |
| Strategy init (build score fn) | Adapter layer (`strategy/_shim.py` o `adapters/live.py`) | Config layer | Legge `cfg.ENABLE_INTERMARKET`, costruisce `build_intermarket_score(loader)` se true. |
| FF RSS fetcher + cache | Calendar layer (`calendar_rss/client.py`) | — | RSS fetch + persist cache + TTL check + currency/impact filter. Analog `news_aggregator.py`. |
| ET→UTC conversion | Calendar layer (utility) | — | `zoneinfo('America/New_York')` per DST cross-year correctness. |
| `get_intermarket_context` MCP tool | MCP layer (`mcp_tools/handlers/macro.py`) | Data layer (loader) | Read-only handler, envelope `{ok, data, error}`. |
| `get_economic_calendar` MCP tool | MCP layer (`mcp_tools/handlers/macro.py` o `calendar.py`) | Calendar layer (RSS client) | Read-only handler, envelope. |
| Skill doc patch | Skill docs (`forex-trader-pro/SKILL.md`) | — | Section "Pre-decision news check". NO code execution. |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **feedparser** | 6.0.11+ | RSS XML parsing | [VERIFIED: `requirements.txt` line `feedparser`] Già usato in `news_aggregator.py` (RSS news sentiment). Drop-in. Maneggia bozo errors, multiple date formats, malformed XML gracefully. |
| **zoneinfo (stdlib Py 3.9+)** | Py 3.12 builtin | ET→UTC DST-aware | [CITED: python.org/3/library/zoneinfo.html] Stdlib, niente install. `ZoneInfo("America/New_York")` gestisce automatico EST/EDT switch. |
| **pandas** | (già in env) | CSV semicolon Italian-format read | [VERIFIED: codebase ubiquo via `backtest/loader.py`] Riusa pattern BACK-01 esistente. |
| **hashlib (stdlib)** | Py 3.12 builtin | sha256 anchor verifica | [VERIFIED: `backtest/baseline/determinism.py:35` `hashlib.sha256(Path(path).read_bytes()).hexdigest()`] Pattern existing, copy-paste. |
| **requests** | 2.32.3 | HTTP fetch FF RSS (alternative a feedparser network) | [VERIFIED: `requirements.txt` line `requests==2.32.3`] **Raccomandato per FF**: feedparser network handling è OK ma `requests` permette retry/timeout/UA control esplicito. Pattern: `requests.get(url, timeout=5, headers={'User-Agent':'trading-agent/2.0'})` poi `feedparser.parse(response.content)`. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **defusedxml** | 0.7.1+ | XXE/billion-laughs hardening | [CITED: pypi.org/project/defusedxml] Quando si parsa XML untrusted (FF è external feed, possibile tampering). Raccomandato per `xml.etree.ElementTree` ma `feedparser` ha già le sue mitigazioni (`feedparser.api.parse` chiama `feedparser.sanitizer`). [ASSUMED] **Decisione planner**: usare feedparser stock (già pattern esistente) — defusedxml NON aggiunge valore qui se feedparser è il parser. Se invece il planner decide `xml.etree.ElementTree` puro per minor surface, allora **OBBLIGATORIO defusedxml**. |
| **pyarrow** | (già in env) | Parquet IO (Phase 7 metadata sha256 audit) | [VERIFIED: `requirements.txt` line `pyarrow`] Solo per integrazione D-10-A4 metadata.json sha256 in Phase 7 retrain bundle. NON serve dentro Phase 10. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| feedparser + requests | `xml.etree.ElementTree` puro + `urllib` | Pro: stdlib zero-dep. Contro: gestione bozo/timezone manuale, security manuale (defusedxml obbligatorio). Già esiste feedparser pattern nel repo → riusa. |
| Stooq direct CSV download | `pandas-datareader` web.DataReader(ticker, 'stooq') | Pro: alta-livello. Contro: dipendenza in più, CAPTCHA breaks comunque, [VERIFIED: github.com/pydata/pandas-datareader/issues/925 commodity issue]. **Decisione D-10-A1 = CSV statici committati, niente runtime download**, quindi questo tradeoff è moot. |
| `pytz` per ET→UTC | `zoneinfo` stdlib | `zoneinfo` Py 3.9+ è canonical PEP 615. `pytz` ha API ambigua (`.localize()` vs `.replace()`). Decisione: **zoneinfo** (CONTEXT.md D-10-B5 already locks). |

**Installation:**
```bash
# Nulla da installare: feedparser, requests, pyarrow, pandas già in requirements.txt
# Solo se planner sceglie defusedxml per hardening esplicito:
# (NON raccomandato dato pattern feedparser already-existing)
pip install defusedxml==0.7.1
```

**Version verification (Stooq URL endpoints):**
```bash
# Stooq daily CSV URL pattern (no API key required per ticker singolo, CAPTCHA-protetto per batch):
# https://stooq.com/q/d/l/?s={ticker}&i=d&d1={YYYYMMDD}&d2={YYYYMMDD}
# Verified tickers (lowercase obbligatorio):
# - DXY:    ^dxy   (ICE U.S. Dollar Index)
# - US10Y:  ^tnx   (CBOE 10-Year Treasury Yield Index)
# - XAUUSD: xauusd (Gold spot vs USD)
# - WTI:    cl.f   (Crude Oil WTI continuous front-month future)
# [CITED: stooq.com search per ticker]
# [ASSUMED] Symbol caret prefix (^dxy, ^tnx) per index — da verificare via download manuale Wave 0.
```

---

## Architecture Patterns

### System Architecture Diagram

```
                          ENABLE_INTERMARKET=false (default)
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          STRATEGY INIT                                    │
│  IntradayStrategy.__init__:                                              │
│    ctx.intermarket_score_fn = (                                          │
│       build_intermarket_score(MacroLoader.from_repo())                   │
│       if cfg.ENABLE_INTERMARKET else None                                │
│    )                                                                      │
└────────────────────────┬─────────────────────────────────────────────────┘
                         │ (callable injection)
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ strategy/confluence.py:266 (adjuster hook GIÀ stub-active)               │
│   if ctx.intermarket_score_fn is not None:                               │
│       try:                                                                │
│           if ctx.intermarket_score_fn(ctx.symbol, direction) > thr:      │
│               delta += adj["intermarket_confirmation"]                   │
│       except Exception:                                                   │
│           pass  # stub safety                                            │
└──────────────────────────────────────────────────────────────────────────┘
                         ▲
                         │ (lookup close(D-1) strict-<)
                         │
┌──────────────────────────────────────────────────────────────────────────┐
│ intermarket/loader.py     intermarket/score.py                           │
│   ┌─────────────┐         ┌──────────────────┐                          │
│   │ MacroLoader │────────▶│ build_intermarket│                          │
│   │  - DXY      │         │  _score(loader)  │                          │
│   │  - US10Y    │         │  → fn(sym, dir)  │                          │
│   │  - XAUUSD   │         │  → float [-1..1] │                          │
│   │  - WTI      │         └──────────────────┘                          │
│   │ sha256 cache│                                                        │
│   └─────────────┘                                                        │
│         ▲                                                                 │
│         │ read once (immutable)                                          │
│         │                                                                 │
│   data/historical/macro/{DXY,US10Y,XAUUSD,WTI}/daily.csv                 │
│   (committed; refresh manuale scripts/refresh_macro_csv.py)              │
└──────────────────────────────────────────────────────────────────────────┘


                  MCP SERVER (Anthropic Claude API consumer)
                                    │
              ┌─────────────────────┴─────────────────────┐
              ▼                                            ▼
     get_intermarket_context()                  get_economic_calendar(window_minutes)
              │                                            │
              ▼                                            ▼
┌──────────────────────────┐              ┌──────────────────────────────┐
│ handlers/macro.py        │              │ handlers/macro.py            │
│  handle_get_intermarket  │              │  handle_get_economic_cal     │
│  - MacroLoader read      │              │  - CalendarRSSClient fetch   │
│  - score per major pair  │              │  - cache TTL check 60min     │
│  - USD strength bias     │              │  - parse FF XML (feedparser) │
│  - risk-on/off (US10Y    │              │  - ET→UTC zoneinfo conv      │
│    vs XAUUSD)            │              │  - filter pair-aware High    │
│  - JPY safe-haven flag   │              │  - skip Tentative/All Day    │
└──────────────────────────┘              │  - holiday → all_day=true    │
                                          └────────────┬─────────────────┘
                                                       │
                                                       ▼
                              ┌──────────────────────────────────────┐
                              │ data/cache/calendar_rss.json         │
                              │   {fetched_at: ISO8601, events: []}  │
                              │   TTL 60min, persisted across runs   │
                              └──────────────────────────────────────┘
                                                       │
                                                       ▼
                              https://nfs.faireconomy.media/
                              ff_calendar_thisweek.xml
                              (next 7 days, ET timezone)


                  forex-trader-pro SKILL (manual consumer)
                                    │
                                    ▼ (D-10-D3 doc patch)
                      "Pre-decision news check:
                       call get_economic_calendar(window_minutes=30)
                       if rilascio imminente, decide if procedere"
                       (NO auto-inject pre-flight)
```

### Component Responsibilities

| Module | Path | Responsibility |
|--------|------|----------------|
| `MacroLoader` | `intermarket/loader.py` (NEW ~120 LOC) | Read 4 CSV at bootstrap, cache in-memory, `close_at(symbol, ts_utc) -> float` con strict-< lookup `D-1` |
| `build_intermarket_score` | `intermarket/score.py` (NEW ~100 LOC) | Factory fn: closure `(symbol, direction) -> float [-1..1]`. Logica aggregata DXY/US10Y/XAUUSD/WTI |
| `IntermarketContext` | `intermarket/types.py` (NEW ~30 LOC) | Dataclass response: `usd_strength_bias`, `risk_on_off`, `jpy_safe_haven_flag`, `as_of_utc`, `signals: dict[str,float]` |
| Strategy init | `strategy/_shim.py` o `adapters/live.py` (MODIFY ~10 LOC) | Legge `cfg.ENABLE_INTERMARKET`, wires `ctx.intermarket_score_fn` |
| Confluence adjuster | `strategy/confluence.py:266` (MODIFY ~5 LOC) | Signature extend additive: `fn(symbol, direction)` invece di `fn(symbol)` |
| `CalendarRSSClient` | `calendar_rss/client.py` (NEW ~150 LOC) | Fetch+cache+parse FF RSS, filter pair-aware High, ET→UTC |
| `get_intermarket_context` handler | `mcp_tools/handlers/macro.py` (NEW ~80 LOC) | MCP envelope wrap loader → response |
| `get_economic_calendar` handler | `mcp_tools/handlers/macro.py` (NEW ~80 LOC) | MCP envelope wrap RSS client → response |
| Tool registration | `mcp_tools/server.py` (MODIFY ~30 LOC) | `MACRO_TOOLS` list, dispatch bucket, list_tools extension |
| Env flag | `config.py` (MODIFY ~3 LOC) | `ENABLE_INTERMARKET: bool = _get_bool("ENABLE_INTERMARKET", False)` |
| Refresh CLI | `scripts/refresh_macro_csv.py` (NEW ~120 LOC) | Stooq download + sha256 verify + commit-ready CSV |
| Skill doc patch | `.claude/skills/forex-trader-pro/SKILL.md` (MODIFY ~15 LOC) | Section "Pre-decision news check" |

### Recommended Project Structure

```
intermarket/                          # NEW package
├── __init__.py                       # public re-exports
├── loader.py                         # MacroLoader (CSV read + cache + close_at)
├── score.py                          # build_intermarket_score factory
└── types.py                          # IntermarketContext dataclass

calendar_rss/                         # NEW package
├── __init__.py
└── client.py                         # CalendarRSSClient (FF RSS fetch+cache+parse)

mcp_tools/handlers/
└── macro.py                          # NEW: handle_get_intermarket_context + handle_get_economic_calendar

data/historical/macro/                # NEW
├── DXY/daily.csv                     # 2002-10-21 → today, BACK-01 Italian format
├── US10Y/daily.csv                   # idem
├── XAUUSD/daily.csv                  # idem
└── WTI/daily.csv                     # idem

data/cache/                           # NEW (gitignored)
└── calendar_rss.json                 # FF RSS cache TTL 60min

scripts/
└── refresh_macro_csv.py              # NEW Stooq download + sha256 verify

tests/
├── test_intermarket_loader.py        # NEW ~120 LOC (csv read, strict-< lookup, sha256 mismatch)
├── test_intermarket_score.py         # NEW ~80 LOC (aggregation, direction handling)
├── test_calendar_rss_client.py       # NEW ~150 LOC (RSS parse, ET→UTC DST, cache TTL, holiday)
├── test_mcp_handlers_macro.py        # NEW ~100 LOC (envelope, error codes)
├── fixtures/
│   ├── macro_dxy_smoke.csv           # 200-row deterministic
│   ├── ff_rss_smoke.xml              # 10 event mocked
│   └── ff_rss_dst_cross.xml          # NEW: Mar/Nov DST boundary regression
└── ...
```

### Pattern 1: Static CSV Loader with sha256 Anchor (D-10-A1, D-10-A4)

**What:** Read committed CSV at bootstrap, verify sha256, cache in-memory dataframe.
**When to use:** Macro data che NON cambia in runtime, immutability è valore di sicurezza (training reproducibility).
**Example (riuso pattern BACK-01 + determinism.file_sha256):**

```python
# intermarket/loader.py
"""Macro CSV loader (D-10-A1, A2, A3, A4).

Riusa pattern BACK-01: pandas semicolon Italian-format.
Riusa pattern Phase 5 baseline: hashlib.sha256 anchor.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

MACRO_SYMBOLS = ("DXY", "US10Y", "XAUUSD", "WTI")
DEFAULT_MACRO_ROOT = Path("data/historical/macro")


@dataclass(frozen=True)
class MacroSeries:
    symbol: str
    df: pd.DataFrame  # columns: ['ts_utc', 'close'] sorted asc
    sha256: str       # hex digest of source CSV bytes


class MacroLoader:
    def __init__(self, series_by_symbol: dict[str, MacroSeries]):
        self._series = series_by_symbol

    @classmethod
    def from_repo(cls, root: Path = DEFAULT_MACRO_ROOT) -> "MacroLoader":
        series = {}
        for sym in MACRO_SYMBOLS:
            csv_path = root / sym / "daily.csv"
            df = cls._read_csv(csv_path)
            sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            series[sym] = MacroSeries(symbol=sym, df=df, sha256=sha)
        return cls(series)

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        # Riusa BACK-01 pattern: semicolon, Italian DD/MM/YYYY, strip headers
        df = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str)
        df.columns = [c.strip() for c in df.columns]
        df["ts_source"] = pd.to_datetime(
            df["Data"] + " " + df["Ora"],
            format="%d/%m/%Y %H:%M:%S",
        )
        # NOTA: daily-close CSV non ha timezone significativa (sono daily bar);
        # convenzione: trattare come 00:00 UTC della data nominale
        df["ts_utc"] = df["ts_source"].dt.tz_localize(timezone.utc).dt.normalize()
        df["close"] = df["Close"].astype(float)
        df = (df[["ts_utc", "close"]]
              .sort_values("ts_utc")
              .drop_duplicates("ts_utc")
              .reset_index(drop=True))
        return df

    def close_at(self, symbol: str, ts_utc: datetime) -> float | None:
        """Strict-< lookup: ritorna close(D-1) per il primo bar PRIMA di ts_utc.

        D-10-A2: no future leakage. Pattern coerente news_aggregator._within_lookback.
        """
        series = self._series.get(symbol)
        if series is None:
            return None
        df = series.df
        mask = df["ts_utc"] < pd.Timestamp(ts_utc, tz="UTC")
        if not mask.any():
            return None
        return float(df.loc[mask, "close"].iloc[-1])

    def sha256(self, symbol: str) -> str | None:
        s = self._series.get(symbol)
        return s.sha256 if s else None
```

**Source:** BACK-01 pattern `backtest/loader.py` + `backtest/baseline/determinism.py:35`.

### Pattern 2: RSS Cache TTL + Lookback (analog news_aggregator.py)

**What:** Fetch RSS once per TTL window, persist cache JSON, filter by lookback half-open interval.
**When to use:** External feed con rate limit (FF 2/5min cap), no scheduler overhead, deterministic test via mock.
**Example:**

```python
# calendar_rss/client.py
"""ForexFactory RSS calendar client (D-10-B1..B6).

Pattern riusato da news_aggregator.py (RSS+cache+lookback).
Cache persistita data/cache/calendar_rss.json TTL 60min.
"""
from __future__ import annotations
import json
import logging
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser

_NY = ZoneInfo("America/New_York")  # D-10-B5: FF feed default timezone
_TIMEOUT_SEC = 5
_CACHE_PATH = Path("data/cache/calendar_rss.json")
_FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    country: str           # currency code: USD, EUR, GBP, JPY, ...
    event_time_utc: datetime
    impact: str            # 'High' | 'Medium' | 'Low' | 'Holiday'
    forecast: str | None = None
    previous: str | None = None
    url: str | None = None
    all_day: bool = False  # D-10-B6 holiday flag


class CalendarRSSClient:
    def __init__(self, cfg, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.log = logger or logging.getLogger(__name__)

    def fetch_events(self, *, force: bool = False, now: datetime | None = None) -> list[CalendarEvent]:
        now = now or datetime.now(tz=timezone.utc)
        cached = self._load_cache()
        if not force and cached is not None:
            fetched_at = cached["fetched_at"]
            if (now - fetched_at) < timedelta(minutes=60):  # D-10-B2 TTL
                return cached["events"]
        try:
            events = self._fetch_remote()
            self._save_cache(now, events)
            return events
        except Exception as exc:
            self.log.warning("FF RSS fetch failed: %s — fallback cache", exc)
            return cached["events"] if cached else []

    def filter_window(
        self,
        events: list[CalendarEvent],
        now: datetime,
        window_minutes: int,
        min_impact: str = "High",
        currencies: list[str] | None = None,
    ) -> list[CalendarEvent]:
        """Half-open lookback pattern (analog news_aggregator._within_lookback)."""
        cutoff_start = now - timedelta(minutes=window_minutes)
        cutoff_end = now + timedelta(minutes=window_minutes)
        impact_order = {"Holiday": 0, "Low": 1, "Medium": 2, "High": 3}
        min_rank = impact_order.get(min_impact, 3)
        result = []
        for ev in events:
            if not (cutoff_start <= ev.event_time_utc < cutoff_end):
                continue
            if impact_order.get(ev.impact, 0) < min_rank and ev.impact != "Holiday":
                continue
            if currencies and ev.country not in currencies:
                continue
            result.append(ev)
        return sorted(result, key=lambda e: e.event_time_utc)

    def _fetch_remote(self) -> list[CalendarEvent]:
        old_to = socket.getdefaulttimeout()
        socket.setdefaulttimeout(_TIMEOUT_SEC)
        try:
            parsed = feedparser.parse(_FF_URL)
        finally:
            socket.setdefaulttimeout(old_to)
        if parsed.bozo and not parsed.entries:
            raise RuntimeError(f"FF feed bozo: {parsed.bozo_exception}")
        # FF schema (verificato 2026-05-13):
        # <event>
        #   <title>...</title>
        #   <country>USD</country>
        #   <date>MM-DD-YYYY</date>
        #   <time>H:MMam/pm</time>   ← ET (default NY tz)
        #   <impact>High|Medium|Low|Holiday</impact>
        # </event>
        events = []
        for entry in parsed.entries:
            ev = self._parse_event(entry)
            if ev is not None and ev.impact != "Tentative":  # D-10-B6 skip Tentative
                events.append(ev)
        return events

    def _parse_event(self, entry) -> CalendarEvent | None:
        title = (entry.get("title") or "").strip()
        country = (entry.get("country") or "").strip().upper()
        date_str = (entry.get("date") or "").strip()      # "05-12-2026"
        time_str = (entry.get("time") or "").strip()      # "12:30pm" or "All Day"
        impact = (entry.get("impact") or "").strip()
        if not title or not country or not date_str:
            return None
        all_day = time_str.lower() in ("all day", "")
        if all_day:
            # D-10-B6: Holiday → 00:00 UTC + flag all_day=true; skip All Day non-holiday
            if impact != "Holiday":
                return None
            dt_et = datetime.strptime(date_str, "%m-%d-%Y").replace(tzinfo=_NY)
            dt_utc = dt_et.astimezone(timezone.utc)
            return CalendarEvent(title, country, dt_utc, impact, all_day=True)
        # Time format: "1:30am", "12:30pm"
        try:
            dt_naive = datetime.strptime(f"{date_str} {time_str}", "%m-%d-%Y %I:%M%p")
        except ValueError:
            return None
        # D-10-B5: ET→UTC via zoneinfo (DST-aware)
        dt_et = dt_naive.replace(tzinfo=_NY)
        dt_utc = dt_et.astimezone(timezone.utc)
        return CalendarEvent(
            title=title, country=country, event_time_utc=dt_utc, impact=impact,
            forecast=entry.get("forecast") or None,
            previous=entry.get("previous") or None,
            url=entry.get("url") or None,
        )

    def _load_cache(self) -> dict | None:
        if not _CACHE_PATH.exists():
            return None
        try:
            raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(raw["fetched_at"])
            events = [
                CalendarEvent(
                    title=e["title"], country=e["country"],
                    event_time_utc=datetime.fromisoformat(e["event_time_utc"]),
                    impact=e["impact"],
                    forecast=e.get("forecast"), previous=e.get("previous"),
                    url=e.get("url"), all_day=e.get("all_day", False),
                ) for e in raw["events"]
            ]
            return {"fetched_at": fetched_at, "events": events}
        except (KeyError, ValueError, json.JSONDecodeError):
            return None

    def _save_cache(self, fetched_at: datetime, events: list[CalendarEvent]) -> None:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            "fetched_at": fetched_at.isoformat(),
            "events": [
                {
                    "title": e.title, "country": e.country,
                    "event_time_utc": e.event_time_utc.isoformat(),
                    "impact": e.impact, "forecast": e.forecast,
                    "previous": e.previous, "url": e.url, "all_day": e.all_day,
                } for e in events
            ],
        }
        _CACHE_PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")
```

**Source:** `news_aggregator.py` template (RSS+cache+lookback), FF schema verified live [VERIFIED: WebFetch 2026-05-13 nfs.faireconomy.media/ff_calendar_thisweek.xml].

### Pattern 3: Intermarket Score Aggregator (Claude's Discretion)

**What:** Pure-function factory che chiude su MacroLoader, ritorna `(symbol, direction) -> float [-1..1]`. Score positivo = CONFERMA direction.
**Example signature & logic skeleton:**

```python
# intermarket/score.py
"""Build intermarket score function (D-10-D1, Claude's Discretion: aggregation logic)."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Callable, Literal

# Pair → relevant macro signal weight mapping (Claude's Discretion).
# Logica suggerita (Murphy intermarket):
#   - EURUSD/GBPUSD: DXY weak → BUY favored (USD strength inverso)
#   - USDJPY: DXY strong + risk-on (US10Y up) → BUY favored; risk-off (XAUUSD up) → SELL favored (JPY safe-haven)
#   - Tutte le pair USD-quote: WTI/XAUUSD secondary risk-on/off signal
_PAIR_WEIGHTS = {
    "EURUSD": {"DXY": -0.5, "US10Y": +0.2, "XAUUSD": -0.2, "WTI": +0.1},
    "GBPUSD": {"DXY": -0.5, "US10Y": +0.2, "XAUUSD": -0.2, "WTI": +0.1},
    "USDJPY": {"DXY": +0.5, "US10Y": +0.3, "XAUUSD": -0.2, "WTI": 0.0},
}


def build_intermarket_score(loader) -> Callable[[str, Literal["long", "short"]], float]:
    """Factory: closure su loader. Ritorna fn(symbol, direction) -> float [-1, 1].

    Score > 0 ⇒ macro CONFERMA direction.
    Score < 0 ⇒ macro CONTRARIA.
    Robust to None close (D-1 mancante): contribuente skippato, score normalizzato.
    """
    def _score(symbol: str, direction: Literal["long", "short"]) -> float:
        # Ricerca close(D-1) e close(D-2) per delta direzionale macro
        now_utc = datetime.now(tz=timezone.utc)
        weights = _PAIR_WEIGHTS.get(symbol)
        if weights is None:
            return 0.0  # symbol non mappato: neutral
        total_weight = 0.0
        weighted_signal = 0.0
        for macro_sym, w in weights.items():
            c_now = loader.close_at(macro_sym, now_utc)
            c_prev = loader.close_at(
                macro_sym,
                now_utc.replace(hour=0, minute=0, second=0, microsecond=0),
            )
            if c_now is None or c_prev is None or c_prev == 0:
                continue
            macro_delta_pct = (c_now - c_prev) / c_prev  # daily ret
            weighted_signal += w * macro_delta_pct * 100  # scaled
            total_weight += abs(w)
        if total_weight == 0:
            return 0.0
        raw = weighted_signal / total_weight
        # D-10-D1: direction-aware sign flip
        if direction == "short":
            raw = -raw
        # Clamp [-1, 1]
        return max(-1.0, min(1.0, raw))
    return _score
```

**Note Pattern 3:** Aggregation weights `_PAIR_WEIGHTS` is **Claude's Discretion** (CONTEXT.md). Planner libero di affinare. Sopra è uno schema riferimento sul peso Murphy intermarket; può finire in `config/strategy.yaml` adjusters per tune.

### Pattern 4: Strict-< Daily Close Lookup (D-10-A2, no future leakage)

**What:** Lookup `close(D-1)` strict-less-than il timestamp corrente per garantire NO future leakage.
**Why critical:** Phase 7 ML feature extraction MUST never see future data. Pattern uniforme con `news_aggregator._within_lookback` half-open interval.

```python
# In MacroLoader.close_at (vedi Pattern 1):
mask = df["ts_utc"] < pd.Timestamp(ts_utc, tz="UTC")  # STRICT-< (NON <=)
```

**Test obbligatorio:** Wave 0 / scaffolding test che asserisce: data un bar @ exact `ts_utc` nella CSV, `close_at(symbol, ts_utc)` ritorna il bar PRECEDENTE (idx-1), NON il bar @ ts_utc.

### Pattern 5: ET → UTC con zoneinfo DST-aware (D-10-B5)

**What:** Convertire ET (EST/EDT switching) a UTC senza drift cross-year.
**Why critical:** FF feed time è in ET (default NY tz [VERIFIED: WebSearch forexfactory.com/thread/16117 + 614780]). EDT in estate (-04:00), EST in inverno (-05:00). Naive UTC offset = bug DST cross-year.

```python
from datetime import datetime
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")

# 2026-05-13 (EDT, summer): 12:30pm ET = 16:30 UTC
dt_et = datetime(2026, 5, 13, 12, 30).replace(tzinfo=_NY)
dt_utc = dt_et.astimezone(timezone.utc)
# → 2026-05-13 16:30:00+00:00

# 2026-01-15 (EST, winter): 12:30pm ET = 17:30 UTC
dt_et = datetime(2026, 1, 15, 12, 30).replace(tzinfo=_NY)
dt_utc = dt_et.astimezone(timezone.utc)
# → 2026-01-15 17:30:00+00:00 (1h different from EDT)
```

**Regression test obbligatorio:** Mirror del BACK-01 D-10 NFP alignment pattern. Test su FF feed con eventi sintetici a marzo (DST start) e novembre (DST end) — verifica che UTC offset switch correttamente. Pattern coerente con Phase 1 D-08/D-10 GMT-6 cross-year regression.

**Source:** [CITED: docs.python.org/3/library/zoneinfo.html], [VERIFIED: forexfactory.com/thread/16117 "calendar uses New York time"], Phase 1 `01-02-PLAN.md` D-10 pattern.

### Pattern 6: MCP Envelope (Phase 6/8 convention)

**What:** Tutti i tool MCP ritornano envelope uniforme `{"ok": bool, "data": {...}, "error": null | {"code": str, "message": str}}`.
**Pattern existing:** `mcp_tools/errors.py` re-exports `ErrorCodes` + `envelope` from `mcp.errors` (Wave 0 Plan 06-01).

```python
# mcp_tools/handlers/macro.py
from mcp.types import Tool
from mcp_tools.errors import ErrorCodes, envelope


GET_INTERMARKET_CONTEXT_TOOL = Tool(
    name="get_intermarket_context",
    description=(
        "Ritorna bias macro intermarket per supportare decisioni FX: USD strength (DXY), "
        "risk-on/off (US10Y vs XAUUSD), JPY safe-haven flag. Daily-close lookup strict-< "
        "(no future leakage). Dataset 23.6y committed in data/historical/macro/."
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
        "Ritorna eventi calendar advisory forward-looking dal feed ForexFactory RSS "
        "(next 7 days, TTL 60min). Pair-aware High-only default. NON applica auto-reject "
        "(advisory only per D-10-C0). Skip Tentative + All Day non-holiday."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "window_minutes": {"type": "integer", "minimum": 1, "maximum": 10080, "default": 15},
            "pair": {"type": "string", "description": "FX pair per filtro currency-aware (optional)"},
            "min_impact": {"type": "string", "enum": ["Low", "Medium", "High"], "default": "High"},
            "currencies": {"type": "array", "items": {"type": "string"}},
        },
        "required": [],
    },
)


def handle_get_intermarket_context(args, macro_loader, cfg) -> dict:
    if not cfg.ENABLE_INTERMARKET:
        return envelope(ok=True, data={"intermarket_active": False, "signals": {}}, error=None)
    if macro_loader is None:
        return envelope(ok=False, data=None,
                        error={"code": ErrorCodes.internal_error,
                               "message": "MacroLoader non inizializzato (bootstrap)"})
    try:
        # Esegue il computo USD strength + risk-on/off + JPY flag da loader
        ...
        return envelope(ok=True, data={...}, error=None)
    except Exception as exc:
        return envelope(ok=False, data=None,
                        error={"code": ErrorCodes.internal_error, "message": str(exc)})


def handle_get_economic_calendar(args, calendar_client, cfg) -> dict:
    try:
        events = calendar_client.fetch_events()
        filtered = calendar_client.filter_window(
            events,
            now=datetime.now(timezone.utc),
            window_minutes=args.get("window_minutes", 15),
            min_impact=args.get("min_impact", "High"),
            currencies=args.get("currencies") or _derive_currencies(args.get("pair")),
        )
        return envelope(ok=True, data={
            "events": [_serialize(ev) for ev in filtered],
            "as_of_utc": datetime.now(timezone.utc).isoformat(),
            "count": len(filtered),
        }, error=None)
    except Exception as exc:
        return envelope(ok=False, data=None,
                        error={"code": ErrorCodes.internal_error, "message": str(exc)})
```

**Source:** `mcp_tools/handlers/backtest.py` analog (Plan 06-03), `mcp_tools/handlers/proposal.py`.

### Anti-Patterns to Avoid

- **NON usare `pytz.timezone("America/New_York")`** invece di `zoneinfo`. `pytz.localize()` vs `replace()` ambiguità è bug-source noto. zoneinfo è canonical PEP 615 Py 3.9+.
- **NON usare `datetime.utcnow()`** (deprecato Py 3.12). Sempre `datetime.now(tz=timezone.utc)`.
- **NON scrivere parser XML custom** senza defusedxml. Feedparser è OK perché ha sanitizer built-in [CITED: feedparser docs sanitization].
- **NON aggiungere campi parquet schema-v2** in `dataset_writer._build_required_keys_v2()`. D-10-C0 IMMUTATO. Qualunque drift = regressione Phase 5 baseline 1076×59.
- **NON usare `socket.setdefaulttimeout` globale senza try/finally restore** (`news_aggregator.py:57-62` mostra pattern corretto). Altrimenti contamina altri network call.
- **NON parsare `<![CDATA[...]]>` manualmente** — feedparser estrae automatic; check `entry.get("date")` ritorna già stringa pulita.
- **NON assumere fast-fail fetch FF**: il feed può essere down (HTTP 5xx, timeout) — pattern fallback cache stale + warning (analog `news_aggregator.fetch_recent_news` line 49-54).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RSS XML parsing | Custom ElementTree parser | `feedparser` (già in requirements.txt) | Handles bozo, multiple date formats, malformed XML, sanitization. Battle-tested. Codebase precedent in `news_aggregator.py`. |
| Timezone DST switch | Hardcoded `timedelta(hours=4 or 5)` ET→UTC | `zoneinfo.ZoneInfo("America/New_York")` | DST cross-year bugs (2 weekend/year) silent. Stdlib Py 3.9+, zero-dep. |
| RFC822 date parsing | `strptime` con multiple format fallback | `email.utils.parsedate_to_datetime` (già in `news_aggregator.parse_date`) | RFC2822 spec compliant, handles weekday, tz markers. |
| sha256 of file | Custom chunked read | `hashlib.sha256(Path(p).read_bytes()).hexdigest()` (già in `backtest/baseline/determinism.py:35`) | Stdlib. Single-line. Pattern existing. |
| CSV semicolon Italian-format read | Manual parser | `pd.read_csv(path, sep=";", dtype=str)` + `[c.strip() for c in df.columns]` (BACK-01 pattern) | Already proven across 23.6y × 3 pair × 3 TF. |
| MCP envelope | Inline dict construction | `from mcp_tools.errors import envelope, ErrorCodes` | Uniformity cross-phase. Single source of truth `mcp/errors.py`. |
| Cache TTL | New scheduler thread | On-demand check at handler call (analog `news_aggregator.fetch_recent_news`) | Zero scheduler overhead, deterministic test via mock `now`. |

**Key insight:** Phase 10 ha ABBONDANTI analoghi nel codebase. Riuso > rebuild. Ogni componente nuovo ha ≥1 file template da copiare (sha256, CSV loader, RSS+cache, MCP envelope, env flag rollout).

---

## Runtime State Inventory

> Phase 10 è **additive greenfield + 1 signature extend backward-compat**. Nessun rename. Nessuna migrazione. Verifica esplicita per categoria:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | Nessun rename/migrazione. Nuovi file CSV statici 4 path nuovi `data/historical/macro/{...}/daily.csv`. **Verified:** Phase 5 parquet `data/training/baseline_decisions/part-0.parquet` 1076×59 IMMUTATO per D-10-C0. SQLite `trades.db` non toccato. ChromaDB/Mem0 N/A. | Nessuna data migration. Solo creazione 4 CSV nuovi + 1 cache JSON nuovo. |
| **Live service config** | Nessun servizio esterno con stato pre-esistente. Nuovo: TTL cache `data/cache/calendar_rss.json` (gitignored). | Nessuna patch UI. `.gitignore` aggiunta path `data/cache/` (1-line). |
| **OS-registered state** | Nessuna registrazione OS. Scripts/refresh_macro_csv.py = CLI on-demand, no cron, no scheduler hook. APScheduler già attivo per `news_aggregator` non viene toccato. | Nessuna re-registration. |
| **Secrets / env vars** | 1 nuovo env var: `ENABLE_INTERMARKET=false` (default). `.env.example` da estendere. Eventuali env nuove per FF URL override (opzionale: `FF_RSS_URL=https://nfs.faireconomy.media/ff_calendar_thisweek.xml` con default hardcoded). `AVOID_MAJOR_NEWS_TIMES` già esistente in `config.py:178` rimane **legacy stub no-op** (CONTEXT.md L112). | Estendere `.env.example`. NON rimuovere `AVOID_MAJOR_NEWS_TIMES` (legacy compat). Decisione planner: marcare deprecated docstring o tenerlo dormant. |
| **Build artifacts / installed packages** | Nessun rename. Nessun egg-info. Pacchetti `feedparser`, `requests`, `pyarrow`, `pandas` già installati e dichiarati in `requirements.txt`. | Nessuna reinstall. |

**Conclusione:** Phase 10 è additive greenfield. L'unica modifica retroattiva è D-10-D1 signature extend `intermarket_score_fn(symbol)` → `intermarket_score_fn(symbol, direction)`. **Backward-compat verificata:** in `strategy/confluence.py:264-269` il callsite è dentro `try/except: pass` no-op safety, quindi una vecchia callable `fn(symbol)` invocata con `fn(symbol, direction)` lancerebbe TypeError SILENT-IGNORATA. Il chiamante con stub `None` (default) non viene mai invocato. **Rischio zero su nuovo direction param mismatch**, ma planner deve esplicitamente testare che callable nuova rispetti la signature 2-arg attesa.

---

## Common Pitfalls

### Pitfall 1: Stooq CAPTCHA gate per batch refresh

**What goes wrong:** `scripts/refresh_macro_csv.py` automatizzato fa 4 download Stooq batch → triggera CAPTCHA dopo 2-3 request rapide → script fallisce silently con HTML 200 ma contenuto CAPTCHA page invece di CSV.
**Why it happens:** [VERIFIED: pandas-datareader issue #82, ml4trading.io thread] Stooq disabilitò automatic downloads Dec 2020. CAPTCHA su batch requests.
**How to avoid:**
- Rate-limit script: `time.sleep(30)` tra simboli.
- Detect HTML response: se `response.text` inizia con `<!DOCTYPE html>` → raise + abort senza scrivere CSV.
- Manual fallback documentato in `SETUP.md`: "Se script fallisce → scarica manualmente da `https://stooq.com/q/d/?s=^dxy&i=d` → save as `data/historical/macro/DXY/daily.csv`".
- Alternative considerate: `pandas-datareader` web.DataReader (stesso problema CAPTCHA), Yahoo Finance (DXY come `DX=F`, gold come `GC=F`) — **decisione planner**: tenere Stooq letterale come D-10-A1 dice, oppure proporre Yahoo come secondary fallback in Wave 0.
**Warning signs:** Script "successo" ma sha256 nuovo identico al precedente (HTML CAPTCHA fingerprint stesso). Test obbligatorio post-refresh: row count > 5000 (23.6y ~6000 daily bar) altrimenti abort.

### Pitfall 2: FF RSS feed timezone implicit (NY default) NON sempre stabile

**What goes wrong:** Utente FF cambia timezone preference nel suo account → feed XML serve time nel TZ utente, NON in ET → tutti gli eventi shift di N ore → MCP-13 ritorna eventi mal-allineati.
**Why it happens:** [VERIFIED: forexfactory.com/thread/614780] "timezone you set in ForexFactory determines the timezone for the news". Default è NY ma può essere overridden.
**How to avoid:**
- Documentare in README: il feed assume default NY tz (no user override). Se user customizza FF account → feed time è in user tz → mismatch.
- Difensiva: parsare il feed senza header timezone esplicito → assumere ET. **NON inferire da entry tags**, non c'è marker.
- Regression test settimanale: prendi un evento ben-noto (FOMC, NFP) — controlla che `event_time_utc` matcha l'orario UTC pubblicamente conosciuto. Se diverge di 1-5 ore → flag config drift FF.
**Warning signs:** Eventi US a "midnight ET" che paiono normali in UTC (ovvio NY override). Test deterministic via fixture mocked XML, NON via fetch live.

### Pitfall 3: DST cross-year boundary bug ET→UTC (Phase 1 D-10 analog)

**What goes wrong:** Evento FF a "2:30am ET" durante DST switch weekend (es. 2026-03-08 2:00am locale → 3:00am locale skip) → `datetime.strptime("03-08-2026 2:30am", "%m-%d-%Y %I:%M%p")` produce datetime naive, poi `.replace(tzinfo=_NY)` → zoneinfo capisce salto DST se `fold=0/1`. Pre-DST + Post-DST switch può produrre stesso UTC su date diverse.
**Why it happens:** Stesso pattern Phase 1 BACK-01 D-10 NFP regression risolto via cross-year test. zoneinfo gestisce ambiguità via `fold` attribute, ma `.replace(tzinfo=...)` di default `fold=0` può sbagliare per ambigui 1:30am EST→EDT transitions.
**How to avoid:**
- Test regression obbligatorio: fixture `ff_rss_dst_cross.xml` con eventi al weekend DST (2nd Sun March, 1st Sun November) — assert UTC corretto per ENTRAMBI lati transition.
- Edge case: eventi su Sunday 2:00-2:59am durante DST start NON esistono fisicamente (skip hour) — comportamento atteso: skippare l'evento + warning. zoneinfo `is_imaginary()` non disponibile direttamente, ma `dt.astimezone(timezone.utc).astimezone(_NY)` round-trip diverge se imaginary → detectable.
**Warning signs:** Test passa a marzo ma fallisce a novembre (asymmetric DST handling). Eventi a 2:30am NY ritornati con UTC strano (es. 06:30 UTC invece di 07:30 UTC).

### Pitfall 4: feedparser `entry.published` vs FF custom `<time>` tag

**What goes wrong:** `news_aggregator.py:82-87` assume RSS standard tag `published`/`updated`/`pubDate`. FF feed usa schema custom `<date>` + `<time>` (NON standard RSS pubDate). feedparser potrebbe NON popolare `entry.published` automatic.
**Why it happens:** FF RSS è in realtà XML custom (`<weeklyevents><event>...`), NON RSS 2.0 standard. feedparser lo riconosce come "atom-like" ma campi custom devono essere acceduti via `entry.get("date")`, `entry.get("time")` direttamente — NON via `entry.published`.
**How to avoid:**
- Wave 0 spike: fetch live FF feed, dump `parsed.entries[0].keys()` → conferma esattamente quali campi feedparser espone.
- Pattern: usare `entry.get("date")` + `entry.get("time")` invece di `entry.get("published")`. Riferimento `_parse_event` in Pattern 2 sopra.
- Test fixture deterministic: salva 1 entry FF reale in `tests/fixtures/ff_rss_smoke.xml`, parsa via feedparser, asserisci 8 campi visibili (title, country, date, time, impact, forecast, previous, url).
**Warning signs:** `event_time_utc` sempre = `datetime.now(tz=utc)` (fallback) per ogni evento. Significa che il parsing date+time è fallito silently.

### Pitfall 5: `intermarket_score_fn` signature backward-compat (D-10-D1)

**What goes wrong:** Cambio signature `fn(symbol) -> float` → `fn(symbol, direction) -> float`. Stub esistenti in test (es. mockate lambda) lanciano TypeError con 2 args.
**Why it happens:** Strategy.context riga 17 dice `intermarket_score_fn: Callable | None = None` — Callable senza signature constraint. Test/codice esistente possono aver passato `lambda s: 0.0`.
**How to avoid:**
- Grep esaustivo Wave 0: `rg "intermarket_score_fn" --type py` → identifica ogni callsite + ogni assignment.
- Modifica callsite `confluence.py:266` per passare anche `direction` (già disponibile nel call context — `score_factors(setup_name, indicators, ctx, direction, cfg)`).
- Default-handling: in `compute_confidence` (lavora su `Grade` non `direction`), recupera direction da factors o da ctx (ATTENZIONE: ctx.direction non esiste → planner decide se aggiungere field a StrategyContext o passare direction esplicito da `score_factors` upstream).
- Test esplicito: `test_intermarket_score_fn_signature_backward_compat` mock 1-arg vs 2-arg, verifica che il try/except no-op safety regge.
**Warning signs:** `try/except: pass` a riga 268 di confluence.py inghiotte silently TypeError → bug invisibile ma adjuster mai applicato. Aggiungere log `_log.debug("intermarket_score_fn error: %s", exc)` per visibilità.

### Pitfall 6: Cache JSON serialization datetime not native

**What goes wrong:** `json.dumps({...datetime: ...})` lancia TypeError ("datetime not JSON serializable"). Cache mai persistita → ogni call MCP-13 fa fetch fresh → rate limit FF (2/5min).
**Why it happens:** stdlib `json` non sa serializzare datetime. `event_time_utc` deve essere convertito a `isoformat()` string per persist.
**How to avoid:** Pattern Pattern 2 sopra: `event_time_utc.isoformat()` in save, `datetime.fromisoformat()` in load. Asserzione test `test_cache_roundtrip` che salva, ricarica, confronta CalendarEvent uguali.
**Warning signs:** `data/cache/calendar_rss.json` mai si crea (file assente). Logs mostrano TypeError gestita silently da `except (KeyError, ValueError, json.JSONDecodeError)` (NON cattura TypeError!). Aggiungere TypeError al except clause.

### Pitfall 7: `socket.setdefaulttimeout` global side effect

**What goes wrong:** `socket.setdefaulttimeout(5)` modifica state globale Python. Se test parallelo non resetta → altri test network falliscono inattesi.
**Why it happens:** [VERIFIED: codebase] `news_aggregator.py:57-62` ha già pattern try/finally restore. Da copiare letterale.
**How to avoid:** Pattern Pattern 2 sopra: `old_to = socket.getdefaulttimeout(); try: ...; finally: socket.setdefaulttimeout(old_to)`. NON SKIP.

### Pitfall 8: Phase 5 parquet schema drift accidentale (D-10-C0 violation)

**What goes wrong:** Planner aggiunge campo intermarket a `_SCHEMA_V2_REQUIRED_KEYS` "per future use" → re-run baseline obbligato → 14000s wall-clock + git diff parquet bytes → D-10-C0 violato.
**Why it happens:** Voglia di "future-proof" il dataset. Ma Phase 5 baseline 1076×59 cols è certificato sha256 Plan 05-09 commit `0410bf2`.
**How to avoid:**
- Gate AST/grep nel CI Phase 10: `tests/test_phase10_no_phase5_drift.py` che verifica `_SCHEMA_V2_REQUIRED_KEYS` (Plan 05-09 `_build_required_keys_v2()` programmatic source-of-truth) — NESSUNA modifica permessa. Confronto sha256 `data/training/baseline_decisions/part-0.parquet` con valore atteso da `baseline-2026-05-12.md` (1076 row, 59 cols).
- Plan-checker iter requisito: ogni plan Phase 10 deve dichiarare esplicitamente "Phase 5 parquet IMMUTATO. Zero modifica a `dataset_writer.py` keys." nel `<truths>` block.
**Warning signs:** Diff lines `+_REQUIRED_KEYS.add("intermarket_...")` in PR. Re-run baseline triggered da test/fixture.

---

## Code Examples

Verified patterns from official sources / codebase analogs:

### Read FF RSS XML deterministic (Wave 0 spike)
```python
# Source: feedparser 6.0.11 docs + WebFetch nfs.faireconomy.media 2026-05-13
import feedparser
parsed = feedparser.parse("tests/fixtures/ff_rss_smoke.xml")
for entry in parsed.entries:
    print(entry.get("title"), entry.get("country"),
          entry.get("date"), entry.get("time"), entry.get("impact"))
# Expected output per evento (verified live FF):
#   "Core CPI m/m" "USD" "05-12-2026" "12:30pm" "High"
```

### sha256 anchor a CSV (D-10-A4 metadata.json integration)
```python
# Source: backtest/baseline/determinism.py:35 (VERIFIED, in production)
import hashlib
from pathlib import Path

def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

# Usage:
sha = file_sha256(Path("data/historical/macro/DXY/daily.csv"))
# → "abc123...64-char hex digest..."
```

### ET → UTC DST-safe (D-10-B5)
```python
# Source: docs.python.org/3/library/zoneinfo.html + Pattern 5
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
dt_et = datetime.strptime("05-12-2026 12:30pm", "%m-%d-%Y %I:%M%p")
dt_et = dt_et.replace(tzinfo=NY)
dt_utc = dt_et.astimezone(timezone.utc)
# 2026-05-12 16:30:00+00:00 (EDT, -4h from UTC)
```

### MCP envelope (Phase 6/8 convention)
```python
# Source: mcp_tools/handlers/backtest.py + mcp_tools/errors.py
from mcp_tools.errors import envelope, ErrorCodes

# Success
return envelope(ok=True, data={"events": [...], "count": 3}, error=None)

# Error
return envelope(ok=False, data=None,
                error={"code": ErrorCodes.validation_failed,
                       "message": "window_minutes deve essere >= 1"})
```

### Env flag zero-impact rollout (D-10-D2, analog Phase 7)
```python
# Source: Phase 7 Plan 07-06 D-07-06-11 + config.py:215 ENABLE_NEWS_SENTIMENT
# In config.py:
class Config:
    ...
    ENABLE_INTERMARKET: bool = _get_bool("ENABLE_INTERMARKET", False)  # D-10-D2 default OFF

# In strategy/_shim.py (o adapters/live.py):
def _init_intermarket_ctx(cfg):
    if not cfg.ENABLE_INTERMARKET:
        return None
    from intermarket.loader import MacroLoader
    from intermarket.score import build_intermarket_score
    return build_intermarket_score(MacroLoader.from_repo())

# In IntradayStrategy.__init__:
self.ctx = StrategyContext(
    ...,
    intermarket_score_fn=_init_intermarket_ctx(cfg),
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pytz.timezone("America/New_York").localize(dt)` | `dt.replace(tzinfo=ZoneInfo("America/New_York"))` | Python 3.9 (PEP 615, 2020) | zoneinfo stdlib, no pytz dependency. zoneinfo respects `fold` attribute for DST ambiguity. |
| `datetime.utcnow()` | `datetime.now(tz=timezone.utc)` | Python 3.12 (deprecated) | utcnow ritornava naive — bug source. Now obbligatorio aware. |
| FF historical CSV download | FF RSS forward-looking only (post-2024 rate limit) | 2024 forexfactory.com rate limit 2 fetch / 5min | Confirms D-10-B1/C0 decision: NO historical dump, RSS-only advisory. |
| Stooq automated CSV bulk download | Manual download + commit (post-2020 CAPTCHA) | Dec 2020 | Confirms D-10-A1/A4 decision: static CSV committed + manual refresh CLI. |
| `xml.etree.ElementTree.parse()` for untrusted XML | `defusedxml.ElementTree` or `feedparser` (has sanitizer) | Post-2013 (defusedxml release) | Mitigate XXE, billion-laughs. Feedparser already-secure. |

**Deprecated/outdated:**
- `pytz` library: replaced by stdlib `zoneinfo` (Py 3.9+). Still works but discouraged for new code.
- `datetime.utcnow()`: deprecated Py 3.12, removal Py 3.13+. Always `datetime.now(timezone.utc)`.
- `pandas-datareader` web.DataReader (Stooq): broken since CAPTCHA Dec 2020 [VERIFIED: github.com/pydata/pandas-datareader/issues/925].

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Stooq tickers per macro symbols: `^dxy`, `^tnx` (US10Y yield idx), `xauusd`, `cl.f` (WTI continuous) | Standard Stack §Version verification | Medio: refresh CLI scarica simbolo sbagliato → CSV con dati errati → loader passa ma score errato. **Mitigation:** Wave 0 spike scarica manualmente ognuno, verifica row count > 5000 (23.6y) + sample close values vs ICE/CME public spot. |
| A2 | FF RSS feed default timezone è ET (NY), constante salvo override account utente | Pattern 5 + Pitfall 2 | Medio: se feed serve in altro TZ, `event_time_utc` shift di N ore. **Mitigation:** weekly regression test pin FOMC/NFP public time. |
| A3 | FF feed schema (`<title><country><date><time><impact>...`) è stabile cross-month | Pattern 2 (CalendarRSSClient._parse_event) | Basso: FF cambia raramente schema (last change >5y). **Mitigation:** test fixture `ff_rss_smoke.xml` aggiornato Wave 0, regression test rileva drift. |
| A4 | `feedparser.parse()` espone campi custom FF (`country`, `date`, `time`, `impact`) tramite `entry.get(...)` | Pitfall 4 | Medio: feedparser potrebbe filtrare campi non-standard RSS. **Mitigation:** Wave 0 spike: `parsed.entries[0].keys()` dump, conferma o switch a `xml.etree.ElementTree` puro (+ defusedxml). |
| A5 | `xauusd` su Stooq = gold spot 23.6y daily, NON futures continuous | Standard Stack §Version verification | Medio: gold spot vs CME GC futures hanno spread/contango drift → bias intermarket score sistematico. **Mitigation:** Wave 0 confronto manuale 5 sample close vs public XAU gold price (kitco.com pubblico). |
| A6 | `cl.f` Stooq = WTI continuous front-month, NON CL1/CL2 explicit | Standard Stack §Version verification | Basso: continuous front-month è convenzione standard, ma rollover gap possibili. **Mitigation:** detect outlier delta > 5% day-over-day → flag warning in loader. |
| A7 | Pair weight aggregation Murphy ('_PAIR_WEIGHTS' Pattern 3) sufficiente per produrre score con segno corretto su test storici noti | Pattern 3 | Alto: aggregation è Claude's Discretion. Senza backtest validation, score può essere noise. **Mitigation:** Wave 2 test deterministic con scenari noti (es. 2020-03 COVID risk-off: DXY+, US10Y-, XAUUSD+, WTI- → expected score EURUSD long < 0). User explicit accept che adjuster è "stub-active" senza re-baseline (D-10-D2). |
| A8 | `ENABLE_INTERMARKET=false` default mantiene Phase 5 baseline parquet byte-identical | D-10-D2 + Pitfall 8 | Basso: env flag a false → callable None → adjuster non triggera → confidence calc identica. **Mitigation:** test `test_phase5_baseline_byte_identical_with_enable_off` post Wave 2 esegue 1 slice mini-range e confronta sha256 parquet vs commit `0410bf2`. |
| A9 | DXY/US10Y/XAUUSD/WTI daily CSV in Italian semicolon format BACK-01 disponibili da Stooq | Standard Stack | Medio: Stooq potrebbe servire CSV in formato US (comma-decimal, MM/DD/YYYY) → loader BACK-01 incompatibile. **Mitigation:** **GIA VERIFICATO** parzialmente: `data/historical/DXY/1Dyapt2.csv` esiste in repo già in formato BACK-01 (semicolon, DD/MM/YYYY) coprendo 2002-10-21 → 2026-04, 3084 row. Significa che il loader BACK-01 funziona out-of-box su DXY almeno. **Wave 0 spike:** verificare se gli altri 3 simboli (US10Y/XAU/WTI) hanno format compatibile o richiedono conversion script. |

**Critical signal:** A7 (Pair Weight aggregation correctness) è il rischio singolo più alto in questo phase. Senza validazione storica empirica, il `intermarket_score_fn` può essere noise statistico travestito da signal. Planner deve riconoscere che D-10-D2 (`ENABLE_INTERMARKET=false` default) è una **risk mitigation deliberate** — il flag rimane OFF fino a paper trading Phase 11 mostra value-add empirico.

---

## Open Questions

1. **Stooq ticker exact format per macro symbols (US10Y/XAUUSD/WTI)**
   - What we know: `^dxy` confirmed [VERIFIED stooq.com/q/a2/?s=xauusd]; existing repo CSV `data/historical/DXY/1Dyapt2.csv` BACK-01 format confirms format compatibility.
   - What's unclear: Exact ticker syntax per US10Y (`^tnx`? `10usy.b`? `tnx.f`?), XAUUSD (spot vs futures), WTI (`cl.f`? `cl1.f`?).
   - Recommendation: Wave 0 spike (1-task plan) — operator scarica manualmente ognuno via browser, verifica row count 5000+ + sample value match public price. Lock i 4 ticker in `scripts/refresh_macro_csv.py` constante.

2. **Reuso `data/historical/DXY/1Dyapt2.csv` esistente vs fresh Stooq download**
   - What we know: 3084 row coprendo 2002-10-21 → 2026-04 in formato BACK-01 perfetto.
   - What's unclear: D-10-A1 dice "Stooq committati". Significa: re-scarica + commit fresh OR riutilizza existing CSV + commit a `data/historical/macro/DXY/daily.csv`?
   - Recommendation: planner riusa existing DXY CSV (move/copy a `data/historical/macro/DXY/daily.csv`, no waste). Scarica solo i 3 mancanti. sha256 anchor sul file finale.

3. **Direction parameter source in `compute_confidence` (D-10-D1 wiring)**
   - What we know: `score_factors(setup_name, indicators, ctx, direction, cfg)` has `direction` parameter. `compute_confidence(grade, ctx, setup_name, factors=None, indicators=None, cfg=None)` does NOT.
   - What's unclear: Per D-10-D1 il callsite `confluence.py:266` deve passare `direction` al `intermarket_score_fn`. Ma `compute_confidence` non ha direction in signature. Soluzioni: (a) add direction param a `compute_confidence`, (b) inferire da factors snapshot, (c) memorizzare in `ctx.direction` campo nuovo.
   - Recommendation: opzione (a) — add `direction: Literal["long","short"] | None = None` param a `compute_confidence` con default None (backward-compat). Caller passa direction esplicito. Adjuster gated `if direction is not None and ctx.intermarket_score_fn is not None`.

4. **Pair weight aggregation source-of-truth: hardcoded vs config.yaml**
   - What we know: Pattern 3 mostra `_PAIR_WEIGHTS` dict hardcoded. CONTEXT.md Claude's Discretion list "pesi DXY vs US10Y vs XAUUSD vs WTI" libera.
   - What's unclear: hardcode in `intermarket/score.py` o esporre come YAML in `config/strategy.yaml` adjusters? Tradeoff: YAML = tunable post-deploy, hardcode = test deterministic.
   - Recommendation: hardcode in Phase 10. Promote a YAML solo se Phase 11 paper trading mostra need-to-tune.

5. **`AVOID_MAJOR_NEWS_TIMES` legacy env: rimuovere o tenere stub no-op?**
   - What we know: CONTEXT.md L112 dice "DEPRECATED post D-10-C0 — da rimuovere o tenere come legacy stub no-op".
   - What's unclear: rimuovere = breaking change `.env` setups esistenti operator. Tenere = morto code.
   - Recommendation: planner tiene legacy con docstring "DEPRECATED — Phase 10 D-10-C0 dropped auto-reject blackout; flag no-op until Phase 11+ retrofit". Removal a Phase 11+ se Risk_engine news soft-warning live attiva.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.12 | Codebase | ✓ (verified `3.12.13`) | 3.12.13 | — |
| `feedparser` | RSS XML parse | ✓ (requirements.txt) | declared | — |
| `requests` | HTTP fetch FF | ✓ (requirements.txt) | 2.32.3 | — |
| `pyarrow` | Parquet metadata.json sha256 (Phase 7 D-15) | ✓ (requirements.txt) | declared | — |
| `pandas` | CSV semicolon read | ✓ (codebase ubiquo) | declared | — |
| `zoneinfo` | ET→UTC DST | ✓ stdlib Py 3.9+ | builtin | — |
| `hashlib` | sha256 anchor | ✓ stdlib | builtin | — |
| `defusedxml` | XML XXE hardening | ✗ NOT in requirements | — | Use feedparser stock (built-in sanitization) OR add to requirements if planner wants explicit `xml.etree.ElementTree` parsing |
| Network access FF feed | RSS fetch | ✓ (codespace + PC primario) | — | Cache stale fallback (analog `news_aggregator.fetch_recent_news`) |
| Network access stooq.com | Macro CSV refresh (manual on-demand) | Likely ✓ (manual operator step) | — | Manual browser download fallback documented |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** `defusedxml` — only needed if planner decides explicit ElementTree parsing instead of feedparser. Decision rests with planner.

---

## Validation Architecture

> `workflow.nyquist_validation` non explicit in `.planning/config.json`; treat as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already in use, version per `requirements.txt`) |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/test_intermarket_loader.py tests/test_intermarket_score.py tests/test_calendar_rss_client.py tests/test_mcp_handlers_macro.py -x --tb=short` |
| Full suite command | `pytest -x --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-10 | `get_intermarket_context()` ritorna `usd_strength_bias`, `risk_on_off`, `jpy_safe_haven_flag` | unit | `pytest tests/test_mcp_handlers_macro.py::test_get_intermarket_context_envelope -x` | ❌ Wave 0 |
| MCP-10 | `MacroLoader.close_at()` strict-< no future leakage | unit | `pytest tests/test_intermarket_loader.py::test_close_at_strict_less_than -x` | ❌ Wave 0 |
| MCP-10 | `MacroLoader` sha256 anchor stable on identical CSV | unit | `pytest tests/test_intermarket_loader.py::test_sha256_anchor_stable -x` | ❌ Wave 0 |
| MCP-10 | `MacroLoader` rileva sha256 mismatch (CSV tamper) | unit | `pytest tests/test_intermarket_loader.py::test_sha256_mismatch_detected -x` | ❌ Wave 0 |
| MCP-10 | `build_intermarket_score()` direction sign-flip correct | unit | `pytest tests/test_intermarket_score.py::test_direction_sign_flip -x` | ❌ Wave 0 |
| MCP-10 | `build_intermarket_score()` known regime (e.g., 2020-03 risk-off) → expected sign | unit | `pytest tests/test_intermarket_score.py::test_known_regime_2020_covid -x` | ❌ Wave 0 |
| MCP-10 | `ENABLE_INTERMARKET=false` → adjuster skipped, baseline parquet byte-identical | regression | `pytest tests/test_phase10_no_phase5_drift.py::test_baseline_immutato_with_flag_off -x` | ❌ Wave 0 |
| MCP-13 | `get_economic_calendar()` filter pair-aware High-only default | unit | `pytest tests/test_mcp_handlers_macro.py::test_economic_calendar_pair_filter -x` | ❌ Wave 0 |
| MCP-13 | `CalendarRSSClient.fetch_events()` cache TTL 60min | unit | `pytest tests/test_calendar_rss_client.py::test_cache_ttl_60min -x` | ❌ Wave 0 |
| MCP-13 | `CalendarRSSClient._parse_event()` ET→UTC EDT (May) correct | unit | `pytest tests/test_calendar_rss_client.py::test_et_to_utc_edt_summer -x` | ❌ Wave 0 |
| MCP-13 | `CalendarRSSClient._parse_event()` ET→UTC EST (Jan) correct | unit | `pytest tests/test_calendar_rss_client.py::test_et_to_utc_est_winter -x` | ❌ Wave 0 |
| MCP-13 | DST cross-year boundary regression (analog Phase 1 D-10) | regression | `pytest tests/test_calendar_rss_client.py::test_dst_boundary_march_november -x` | ❌ Wave 0 |
| MCP-13 | Holiday event → `event_time_utc=00:00 UTC` + `all_day=true` | unit | `pytest tests/test_calendar_rss_client.py::test_holiday_all_day_flag -x` | ❌ Wave 0 |
| MCP-13 | Tentative + All Day non-holiday events skipped | unit | `pytest tests/test_calendar_rss_client.py::test_skip_tentative_all_day -x` | ❌ Wave 0 |
| MCP-13 | Cache roundtrip JSON serialize+deserialize datetime stable | unit | `pytest tests/test_calendar_rss_client.py::test_cache_roundtrip -x` | ❌ Wave 0 |
| MCP-13 | FF feed down → cache fallback + warning | integration | `pytest tests/test_calendar_rss_client.py::test_fetch_remote_failure_fallback -x` | ❌ Wave 0 |
| MCP-13 | MCP envelope shape success | unit | `pytest tests/test_mcp_handlers_macro.py::test_envelope_ok -x` | ❌ Wave 0 |
| MCP-13 | MCP envelope shape error (validation_failed) | unit | `pytest tests/test_mcp_handlers_macro.py::test_envelope_validation_failed -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_intermarket_*.py tests/test_calendar_rss_*.py tests/test_mcp_handlers_macro.py -x --tb=short`
- **Per wave merge:** `pytest -x --tb=short` (full suite, must remain green)
- **Phase gate:** Full suite + Phase 5 baseline byte-identical assertion (`test_phase10_no_phase5_drift.py`) + integration smoke test FF feed live (run-once manually, skipif no-network)

### Wave 0 Gaps
- [ ] `tests/test_intermarket_loader.py` — covers MCP-10 (loader + sha256)
- [ ] `tests/test_intermarket_score.py` — covers MCP-10 (score aggregator)
- [ ] `tests/test_calendar_rss_client.py` — covers MCP-13 (RSS+cache+DST)
- [ ] `tests/test_mcp_handlers_macro.py` — covers MCP-10/13 (envelope + dispatch)
- [ ] `tests/test_phase10_no_phase5_drift.py` — D-10-C0 enforcement (Phase 5 immutability gate)
- [ ] `tests/fixtures/macro_dxy_smoke.csv` — 200-row deterministic
- [ ] `tests/fixtures/ff_rss_smoke.xml` — 10 event mocked (live FF schema)
- [ ] `tests/fixtures/ff_rss_dst_cross.xml` — DST boundary Mar/Nov regression
- [ ] Framework install: nothing — `feedparser`, `requests`, `pyarrow`, `pandas` already in env

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | MCP server local-only (stdio JSON-RPC), no external auth needed |
| V3 Session Management | no | MCP stateless per call |
| V4 Access Control | no | Tool registration whitelist, no privileged escalation |
| V5 Input Validation | **yes** | JSON-Schema draft-7 inputSchema su tool args (Pattern 6). `min_impact` enum-restricted. `window_minutes` integer min/max bounds. `currencies` array string. |
| V6 Cryptography | **partial** | sha256 anchor su CSV (integrity audit, NON encryption). hashlib.sha256 stdlib — no hand-roll. |
| V10 Malicious Code | **yes** (XML external entity) | feedparser ha sanitizer built-in. Se planner sceglie `xml.etree.ElementTree` puro → `defusedxml` obbligatorio. |
| V12 Files & Resources | **yes** | Cache JSON `data/cache/calendar_rss.json` deserialization via `json.loads` (stdlib safe). CSV read via pandas (no injection vector). |
| V13 API & Web Service | **partial** | FF RSS feed: HTTPS endpoint, no auth header, public. Stooq: HTTPS, CAPTCHA-gated. |

### Known Threat Patterns for Phase 10 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XXE attack on FF RSS XML | Tampering | feedparser sanitizer (built-in). If planner uses ElementTree → defusedxml. |
| Billion-laughs attack on FF RSS | DoS | feedparser sanitizer + entity expansion limit. |
| FF feed tampering / DNS hijack | Spoofing | HTTPS endpoint + content schema validation (`<weeklyevents>` root tag check). |
| Stooq CSV replacement (data poisoning) | Tampering | sha256 anchor in metadata.json (D-10-A4). Phase 7 retrain abort if sha256 changes without intent (D-10-A4). |
| Cache JSON tampering | Tampering | File mode `data/cache/` gitignored (no commit); read-only filesystem in production. Schema validation at load (TypeError-safe). |
| MCP tool argument injection | Input Validation | JSON-Schema enum restrictions (e.g., `min_impact` enum). |
| Network DOS (FF down) | Availability | Cache TTL stale fallback (analog `news_aggregator.fetch_recent_news` line 49-54). Graceful degrade. |
| Future leakage (M15 strategy sees today's daily close) | Data Integrity | Strict-< lookup `close_at(symbol, ts_utc)` Pattern 4. Test `test_close_at_strict_less_than` mandatory. |

---

## Project Constraints (from CLAUDE.md)

- **EXECUTION_MODE=shadow default sempre** — Phase 10 tool MCP non chiamano `risk_engine.evaluate_trade` né `mt5_client.send_order` (sono read-only advisory). NO shadow-mode mandate violation possibile.
- **Tutto da .env, zero magic numbers** — `ENABLE_INTERMARKET`, `FF_RSS_URL` (opzionale), tutti via `.env` + `Config` class.
- **Risk engine = unico gate approvazione trade** — Phase 10 NON aggiunge gate (D-10-C0 drop blackout). `intermarket_confirmation` adjuster modifica solo confidence, NON è gate.
- **Italiano commenti/log/rationale** — Tutti i docstring + log message in italiano.
- **Test pytest, mock Mt5Client per evitare connessione reale** — Phase 10 testing fixture-deterministic (mocked RSS XML, smoke CSV) NON require Mt5Client.
- **Un file per fase in .orchestration/phase-prompts/** — Plan format coerente con phase 1-9 (XX-NN-PLAN.md).
- **STATE.md aggiornato dopo ogni micro-step** — Phase 10 update STATE.md "Active Work" + "Recent Decisions" sezioni dopo ogni Plan execute.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED] WebFetch https://nfs.faireconomy.media/ff_calendar_thisweek.xml (2026-05-13) — FF RSS XML schema, 8 child tags per `<event>`, date `MM-DD-YYYY`, time `H:MMam/pm`, impact `High|Medium|Low|Holiday`
- [VERIFIED] `news_aggregator.py` (141 LOC, in production) — RSS+cache+lookback analog
- [VERIFIED] `backtest/loader.py` BACK-01 + `backtest/baseline/determinism.py:35` — CSV semicolon + sha256 patterns
- [VERIFIED] `strategy/confluence.py:263-269` — adjuster hook stub-active
- [VERIFIED] `strategy/context.py:17` — `intermarket_score_fn` field already declared
- [VERIFIED] `config.py:215-231` `_attach_news_sentiment` — env flag rollout template
- [VERIFIED] `mcp_tools/handlers/backtest.py` — MCP envelope + Tool registration analog
- [VERIFIED] `data/historical/DXY/1Dyapt2.csv` (3084 row, 2002-10-21 → 2026-04, BACK-01 format) — existing usable DXY data
- [CITED] docs.python.org/3/library/zoneinfo.html — ZoneInfo PEP 615 stdlib Py 3.9+
- [CITED] docs.python.org/3/library/datetime.html — datetime.now(tz=timezone.utc) Py 3.12

### Secondary (MEDIUM confidence)
- [VERIFIED via WebSearch] forexfactory.com/thread/614780 "What timezone is ffcal_week_this.xml" — confirms NY default + DST adjustment
- [VERIFIED via WebSearch] forexfactory.com/thread/16117 "Is Forex Factory Calendar EST time" — same
- [VERIFIED via WebSearch] pypi.org/project/defusedxml — XXE/billion-laughs mitigation
- [VERIFIED via WebSearch] github.com/pydata/pandas-datareader/issues/925 — Stooq commodity CAPTCHA issue confirmed
- [VERIFIED via WebSearch] github.com/stefan-jansen/machine-learning-for-trading/issues/82 — Stooq CAPTCHA Dec 2020 confirmed
- [VERIFIED via WebSearch] forum.portfolio-performance.info/t/37973 — Stooq URL structure `https://stooq.com/q/d/?s=...&c=0`

### Tertiary (LOW confidence — needs Wave 0 spike validation)
- [ASSUMED] Stooq ticker exact form: `^dxy`, `^tnx` (US10Y), `xauusd`, `cl.f` (WTI continuous) — needs manual browser download verification
- [ASSUMED] feedparser exposes FF custom tags `country`, `date`, `time`, `impact` via `entry.get(...)` — needs Wave 0 spike `parsed.entries[0].keys()` dump
- [ASSUMED] `_PAIR_WEIGHTS` aggregation weights in Pattern 3 produce empirically-correct scores on known historical regimes — needs Wave 2 test scenario validation (2020-03 COVID, 2022-Q1 FOMC hike cycle)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `feedparser`, `requests`, `pyarrow`, `pandas`, `zoneinfo`, `hashlib` all already in env, no install needed
- Architecture: HIGH — every component has ≥1 codebase analog (news_aggregator.py, backtest/loader.py, mcp_tools/handlers/backtest.py, config.py:215)
- FF feed schema: HIGH — live-fetched and verified 2026-05-13
- Stooq ticker exact form: MEDIUM-LOW — symbol confirmation needed manually per A1 + A5 + A6
- Pair weight aggregation correctness: LOW — Claude's Discretion + no historical validation pre-Phase-11 paper
- DST/timezone correctness: HIGH — zoneinfo PEP 615 + Phase 1 D-08/D-10 analog pattern locked
- Phase 5 baseline preservation (D-10-C0): HIGH — sha256 commit `0410bf2` reference + AST gate test possible
- Backward-compat signature extend (D-10-D1): MEDIUM — try/except no-op safety holds but TypeError silent-swallow is hidden bug risk

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (30 days — stable domain, codebase analogs preserve relevance)
