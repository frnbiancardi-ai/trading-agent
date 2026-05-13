# Phase 10: Intermarket + News - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 10 consegna **due capability complementari** che entrano in produzione live:

1. **MCP-10 Intermarket context** — loader + tool che espone bias macro (USD strength via DXY, risk-on/off via US10Y + XAUUSD + WTI, JPY safe-haven flag) basato su 4 CSV daily-close Stooq committati. Score consumato da `strategy/confluence.py:263` come adjuster di confidence (hook stub gia attivo). Backtest engine puo opzionalmente leggere lo stesso loader, ma per Phase 10 rimane DISABLED di default (ENABLE_INTERMARKET=false), preservando Phase 5 baseline parquet schema-v2 1076 × 59 immutato.

2. **MCP-13 Economic calendar advisory** — tool `get_economic_calendar(window_minutes)` esposto via MCP, alimentato da ForexFactory RSS feed live (next 7 days) con TTL 60 min on-demand. **NON e' un blackout automatico**: il tool ritorna eventi forward-looking filtrati pair-aware High-only, consultabili dal forex-trader-pro skill come info advisory pre-decision (human-in-loop). Nessun auto-reject in strategy.py o risk_engine.py.

**Out of scope (rispetto a ROADMAP letterale):**
- Backtest blackout su 23.6y storico (DROPPATO — D-10-C0 scope override).
- FRED reconstruction calendar pre-2007.
- ForexFactory CSV historical dump committato.
- Phase 5 parquet re-baseline schema-v3.
- ROADMAP SC#3 ("trades within ±15 min of high-impact events are rejected with explicit reason") = DEVIATED esplicito → vedi sezione Deviazioni ROADMAP.

</domain>

<decisions>
## Implementation Decisions

### Area A — Intermarket data + backfill (5 decisions)

- **D-10-A0:** ROADMAP letterale full scope: MCP-10 + MCP-13 entrambi, tutti e 4 i symbol macro (DXY, US10Y, XAUUSD, WTI). Motivazione utente: "se DXY/US10Y/gold/oil servono per istruire al meglio il sistema allora carichero i dati storici, non importa caricare 20MB in piu". Coerente con project memory `project_training_data_integrity_priority.md` (feature ricche per ML > repo size).

- **D-10-A1:** CSV statici Stooq committati a `data/historical/macro/{DXY,US10Y,XAUUSD,WTI}/daily.csv`. Niente API runtime, niente synthetic. Motivazione: backtest deterministic by construction (sha256-anchored), zero failure mode rete PC secondario, dataset immutabile in repo.

- **D-10-A2:** Daily-close only. Bridge a M15/M30/H1 strategy via lookup `close(D-1)` strict-< (no future leakage, pattern coerente con `news_aggregator._within_lookback`). Motivazione: (1) intermarket e regime macro non confirmation realtime, (2) Phase 7 ML feature space pulito 1 feature/symbol vs 96 OHLC×H1 lookback, (3) Stooq free copre 23.6y daily ma H1 history richiede paid.

- **D-10-A3:** 23.6y full coverage allineata a `data/historical/` forex (2002-10-21 → today). Match copertura baseline parquet (Phase 5 plan 05-10), no mismatch coverage warning, no imputation missing-feature in Phase 7 ML trainer.

- **D-10-A4:** Refresh manuale on-demand via `scripts/refresh_macro_csv.py`. No cron auto-refresh. sha256 di ogni CSV registrato in `metadata.json` del bundle ML (Phase 7 D-15 extension). Phase 7 retrain abort se sha256 cambia senza intent esplicito operator. Motivazione: training integrity prefers explicit-intent dataset changes; cron auto-refresh introduce silent drift risk.

### Area B — Calendar provider (6 decisions, post C0 revision)

- **D-10-B1 [REVISED post C0]:** Solo ForexFactory **RSS** live forward-looking (next 7 days). NO historical CSV dump committato, NO sha256 anchor calendar storico. Tool MCP-13 esposto live-only. Coverage: USD/EUR/GBP/JPY/AUD/CAD/CHF/NZD + flag impact High/Medium/Low. Riusa pattern `news_aggregator.py` (RSS + cache + lookback).

- **D-10-B2:** Fetch on-demand + TTL 60 min. Cache persistita `data/cache/calendar_rss.json` con timestamp. Refresh automatico solo se cache > 60 min. Zero scheduler overhead. Pattern coerente con Phase 8 `ml/inference` cache singleton + Phase 6 D-D1 BarSource `as_of_ts`.

- **D-10-B3:** Pair-aware High-only nel default param del tool. Args opzionali `min_impact` (default 'High') + `currencies` (default derived dal `pair` query, fallback `['USD','EUR','GBP','JPY']`). Stima ~150-300 eventi/anno per pair. Tool ritorna eventi filtrati come info advisory; nessun gating downstream.

- **D-10-B4:** `window_minutes` default = 15 (ROADMAP SC#3 letterale, anche se non auto-reject). Forex-trader-pro skill puo override (es. `window_minutes=60` per pre-decision pre-flight). Pattern half-open intervallo coerente con `news_aggregator._within_lookback`.

- **D-10-B5:** ET→UTC con DST rules via `zoneinfo('America/New_York')`. RSS FF rilascia `<pubDate>` con timezone esplicita (es. `Fri, 15 May 2026 14:30:00 -0400` = EDT) — parser deve rispettare il marker offset per evitare drift cross-year DST (Phase 5 D-15 DST critical pattern). Tool ritorna sempre UTC.
  - **Chiarimento utente (sessione discuss):** forex CSV GMT-6 sorgente → loader BACK-01 → UTC interno; calendar RSS FF ET sorgente → tool Phase 10 → UTC interno. Comparison sempre in UTC.

- **D-10-B6 [REVISED post C0]:** Skip Tentative + All Day nella risposta tool (filtrati out — non utili come advisory). Holiday events (Christmas, Independence Day, Boxing Day, Thanksgiving) = ritornati nel response con `event_time=00:00 UTC` + flag `all_day=true` per highlight skill consumer. Non gating, solo display advisory.

### Area C — Backtest blackout coverage (1 decision, scope override)

- **D-10-C0 [SCOPE OVERRIDE]:** **Drop backtest blackout totalmente.** Phase 5 parquet schema-v2 1076 × 59 cols IMMUTATO (zero re-run 23.6y, zero schema migration, zero FRED reconstruction 2002-2007). MCP-13 build live-only no auto-reject in `strategy.py` o `risk_engine.py`.
  - **Motivazione utente:** "lo storico dei dati contiene tutti i giorni non esclude le festivita o altri eventi" → strategy + ML implicitamente apprendono dalla distribuzione reale di P&L che include NFP/FOMC/holiday.
  - **Trade-off accettato:** (1) asimmetria backtest/live (blackout live mai validato su storico); (2) spike intrabar M15 NFP appiattito nelle bar close-of-bar = Phase 7 ML potrebbe sottostimare costo trade-on-news, ma e' la distribuzione gia presente nel training dataset.
  - **Compensato da:** forex-trader-pro skill consultation MCP-13 manuale (D-10-D3).
  - **Cascade effects:** D-10-B1 ridotto a RSS-only; D-10-B3/B4/B6 ridefiniti come tool-response shaping invece di gating semantics; Area D scope ridotto (no `ENABLE_NEWS_BLACKOUT` env, no open-position-in-blackout question, no `risk_engine` news gate).

### Area D — Intermarket → strategy wiring (3 decisions)

- **D-10-D1:** Extend signature `intermarket_score_fn(symbol: str, direction: Literal["long","short"]) -> float`. Score positivo = intermarket CONFERMA la direction proposta (es. DXY weak + direction=long su EURUSD → score positivo; DXY weak + direction=short su EURUSD → score negativo). Signature change in `strategy/context.py:17` additive backward-compat (parametro `direction` con default-handling per il caso stub None corrente). Callsite `strategy/confluence.py:266` passa anche `direction` (gia disponibile in proposal context). `if effective > threshold: +adjuster["intermarket_confirmation"]`.

- **D-10-D2:** `ENABLE_INTERMARKET=false` default in `config.py` (pattern identico Phase 7 D-07-06-11 `ENABLE_ML_FILTER`). All'init di `IntradayStrategy.__init__`: `ctx.intermarket_score_fn = build_intermarket_score(...) if cfg.ENABLE_INTERMARKET else None`. Phase 5 baseline parquet **immutato** (env false default). Plan Phase 10 = wire + test, **NO re-baseline**. Operator flippa a `true` in env post-Phase-11 paper trading e fa eventuale re-baseline esplicito plan 10-XX (deferred idea). Zero-impact rollout.

- **D-10-D3:** Phase 10 build: tool MCP-13 esposto + breve sezione documentation nel skill markdown forex-trader-pro ("Pre-decision news check: chiama `get_economic_calendar(window_minutes=30)` se sospetti rilascio imminente, decidi se procedere"). **Skill NON auto-inject MCP-13 in pre-flight** (pre-flight rimane `scan_symbol_candidates` + `get_market_snapshot`). Operator decide se chiamare. Minimo touch al skill (no rebuild pre-flight chain), advisory chiaro, no blackout automatico = coerente D-10-C0.

### Claude's Discretion

Implementazione dettagli lasciati al planner:
- Aggregazione signal interna a `build_intermarket_score` (peso DXY vs US10Y vs XAUUSD vs WTI per ogni pair).
- Threshold del `if effective > threshold` in `compute_confidence` (valore in `config/strategy.yaml` `adjusters`).
- Audit logging di chiamate MCP-13 (su `logs/mcp.log` o estensione `logger.py` schema).
- Fallback se FF RSS down (cache stale > TTL → return cached + warning, oppure raise + skill operator vede error).
- Dataclass/Pydantic model per response MCP-13 (allineato pattern Phase 6 MCP envelope).

</decisions>

## Deviazioni ROADMAP

**ROADMAP Phase 10 SC#3** (linea 325): *"Proposal pipeline applies blackout: trades within ±15 min of high-impact events are rejected with explicit reason."*

→ **DEVIATED esplicitamente** via D-10-C0. Phase 10 SC count ridotto da 3 a 2.
- SC#1: `get_intermarket_context()` returns bias signals → coperto da MCP-10 (Area A + D wiring).
- SC#2: `get_economic_calendar(window_minutes)` returns events + impact flag → coperto da MCP-13 (Area B + D3).
- ~~SC#3: blackout auto-reject~~ → **deferred** a Phase 11+ (vedi `<deferred>` "Backtest blackout retroactive" + "Risk_engine news soft-warning live").

**Action item per planner:** aggiornare `.planning/ROADMAP.md` Phase 10 section con nota deviation + spostare SC#3 al backlog deferred ideas. Aggiornare `.planning/REQUIREMENTS.md` MCP-13 row con nota "live-only advisory, no auto-reject per D-10-C0".

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements
- `.planning/ROADMAP.md` §"Phase 10: Intermarket + News" (L316-329) — Goal + 3 SC originali (SC#3 DEVIATED post D-10-C0).
- `.planning/REQUIREMENTS.md` L86 (MCP-10), L89 (MCP-13).
- `.planning/PROJECT.md` L43 (intermarket Murphy), L44 (economic calendar).

### Prior phase context (carry-forward)
- `.planning/phases/09-failure-analysis-drift/09-CONTEXT.md` — Phase 6/7/8 carry-forward decisions + Phase 9 D-09-* analog patterns (env flag rollout, P14 sha256 strict-fail, training data integrity guards).
- `.planning/phases/08-mcp-tools-part-2/08-CONTEXT.md` — MCP package conventions, JobQueue cap=1, ErrorCodes envelope, async job pattern.
- `.planning/phases/05-baseline-backtest/05-09-PLAN.md` — Phase 5 schema-v2 `_SCHEMA_V2_REQUIRED_KEYS` (IMMUTATO post D-10-C0).
- `.planning/phases/01-backtest-engine/01-02-PLAN.md` — BACK-01 GMT-6→UTC conversion pattern, D-08/D-10 cross-year DST regression (analog per D-10-B5 ET→UTC).

### Codebase integration points
- `news_aggregator.py` — analog parsing + cache + lookback pattern per implementare MCP-13 tool.
- `strategy/confluence.py:263-269` — `intermarket_score_fn` adjuster hook gia stub-active (Phase 10 Area D wire target, signature change additive D-10-D1).
- `strategy/context.py:17` — `intermarket_score_fn: Callable | None = None` field gia presente (signature extend post D-10-D1).
- `config.py:178` — `AVOID_MAJOR_NEWS_TIMES` env var gia presente (DEPRECATED post D-10-C0 — da rimuovere o tenere come legacy stub no-op).
- `config.py:215-231` — `ENABLE_NEWS_SENTIMENT` + `RSS_FEEDS` + `NEWS_LOOKBACK` pattern per zero-impact rollout flag (analogia per `ENABLE_INTERMARKET`).
- `mcp_server.py` (+ `mcp_tools/` package Phase 6) — registrazione tool MCP-10 / MCP-13 (pattern Phase 6 06-02 R1/R2/R3 + Phase 8 MCP-04/05/06).

### Project memory + conventions
- Memory file `project_training_data_integrity_priority.md` — informa D-10-A1, D-10-A4, D-10-C0 drop blackout (training integrity = max priority).
- Memory file `project_max_daily_drawdown_20pct.md` — informa Phase 7 retrain env coherence post-Phase-10.
- `CLAUDE.md` — EXECUTION_MODE=shadow default, `risk_engine` unico gate, log/commenti italiano, zero magic numbers, tutto da `.env`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `news_aggregator.py` (141 LOC, RSS + cache + lookback): pattern direttamente trasferibile per implementare `get_economic_calendar` (RSS fetch + persist cache + TTL check + currency/impact filter). Differenza chiave: news_aggregator e' sentiment-side (already disabled by default via `ENABLE_NEWS_SENTIMENT=false`), MCP-13 e' calendar-side (event time-indexed).
- `strategy/confluence.py:263-269` — adjuster hook `intermarket_confirmation` gia presente con try/except no-op safety. Wire = solo signature extend + builder factory.
- `strategy/context.py:17-18` — campi `intermarket_score_fn` e `news_blackout_fn` gia in `StrategyContext`. Phase 10 usa il primo, **NON usa il secondo** (D-10-C0 drop news_blackout). Decisione planner: rimuovere `news_blackout_fn` field morto, o tenerlo come stub `Callable | None = None` per Phase 11+ retrofit.
- `config.py:215-231` `_apply_runtime` pattern di config attivazione `ENABLE_*` flag — diretto template per `ENABLE_INTERMARKET`.
- Phase 5 `dataset_writer` schema-v2 `_SCHEMA_V2_REQUIRED_KEYS` (Plan 05-09) — IMMUTATO post C0; Phase 10 NON estende il parquet.

### Established Patterns
- **Zero-impact rollout env flag** (Phase 7 D-07-06-11 `ENABLE_ML_FILTER`, Phase 9 `ENABLE_DRIFT_MONITOR`): nuova capability OFF di default, operator opt-in via env. Phase 10 `ENABLE_INTERMARKET=false` segue questo pattern.
- **Pure-function adjuster con try/except no-op** (confluence.py:263-269): hook esteso senza rompere flow se fn lancia exception. Phase 10 mantiene questa convenzione.
- **CSV-static + sha256 anchor** (D-10-A1 macro + Phase 7 D-15 metadata.json): pattern coerente per dataset deterministic in repo.
- **MCP tool envelope** (Phase 6 06-02 + Phase 8 08-*): tool MCP-10 e MCP-13 seguono envelope `{"ok": bool, "data": {...}, "error": null | {"code": str, "message": str}}` + ErrorCodes registrate.
- **Cache TTL on-demand** (Phase 8 ml/inference singleton, Phase 6 D-D1 BarSource as_of_ts): pattern per MCP-13 D-10-B2 RSS cache 60 min.

### Integration Points
- **Confluence scoring** (`strategy/confluence.py:266`): callsite passa `direction` al `intermarket_score_fn`. Signature change D-10-D1 backward-compat (default None handling).
- **Strategy init** (`strategy/_shim.py` o `strategy/__init__.py:IntradayStrategy.__init__`): legge `cfg.ENABLE_INTERMARKET`, costruisce `build_intermarket_score(macro_loader)` se true, set su `ctx.intermarket_score_fn`.
- **MCP server registration** (`mcp_server.py` o `mcp_tools/__init__.py`): aggiunge `get_intermarket_context` e `get_economic_calendar` al tools/list. JSON-Schema + handler.
- **forex-trader-pro skill markdown**: append section "Pre-decision news check" (D-10-D3). Skill repo external — patch documentation only, no auto-inject pre-flight chain.
- **Logger** (`logger.py` schema Phase 9 D-09-D4): valutare se MCP-13 call audit va loggato. Decisione planner.

</code_context>

<specifics>
## Specific Ideas

- **DXY/US10Y/XAUUSD/WTI = Stooq daily CSV** committed (utente specifica "carichero i dati storici, non importa caricare 20MB in piu"). Non e' MT5 broker symbol, non e' synthetic dal basket EUR/JPY/GBP/CHF.
- **23.6y baseline allineamento** (Phase 5 plan 05-10 in flight 2026-05-12 baseline 23.6y full re-run): macro CSV coverage 2002-10-21 → today **deve combaciare** o Phase 7 trainer lancia warning coverage mismatch.
- **Forex CSV sorgente GMT-6** (chiarito da utente): non confondere con timezone calendar FF (ET). Tutte le timezone convergono a UTC nel runtime interno (Phase 1 BACK-01 GMT-6→UTC pattern, Phase 10 D-10-B5 ET→UTC pattern).
- **ROADMAP letterale > scope reduction**: utente confermato Area A "rispetta la roadmap con tutti i dati storici per avere tutto completo" + Area C "rispettiamo i backtest della base line". Pattern: training integrity = priority, scope = letterale tranne quando il work non si giustifica (Area C blackout backtest = drop perche' Phase 5 baseline preservation > completezza letterale).

</specifics>

<deferred>
## Deferred Ideas

- **MCP-10 H1 intraday granularity** — Phase 11+ scope expansion se aggiunti CAD/NOK pair o swing trading (currentemente daily-close basta per regime macro).
- **Auto-refresh cron weekly macro CSV** — Phase 11+ se DEPLOY-02 ops surface refresh-staleness pain (now manual D-10-A4 sufficient).
- **Configurabile pre/post blackout window via env** — moot post D-10-C0 ma tenuto per documentation se Phase 11+ retrofit blackout.
- **Backtest blackout retroactive** — Phase 11+ se paper trading rivela news-day overfit nel ML model. Re-instate work: FRED USD reconstruction pre-2007 + FF CSV dump post-2007 + Phase 5 re-baseline schema-v3 + Phase 7 retrain.
- **Risk_engine news soft-warning live** — Phase 11+ se paper-trading rivela operator manca contesto news pre-decision. Implementation: `risk_engine.PreflightResult` aggiunge field `news_warning` riempito da query MCP-13 sui prossimi 15 min; warning loggato non blocca.
- **Skill forex-trader-pro auto-inject MCP-13 in pre-flight** — Phase 11+ se on-demand consult D-10-D3 si rivela insufficient (operator dimentica di chiamare).
- **Re-baseline Phase 5 con ENABLE_INTERMARKET=true** — Plan 10-XX deferred. Activation: post-Phase-11 paper trading se metric mostra value-add intermarket adjuster.

</deferred>

---

*Phase: 10-intermarket-news*
*Context gathered: 2026-05-13*
