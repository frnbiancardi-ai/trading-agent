# Phase 10: Intermarket + News - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 10-intermarket-news
**Areas discussed:** Intermarket data + backfill, Calendar provider, Backtest blackout coverage, Intermarket → strategy wiring

---

## Area A — Intermarket data + backfill

### D-10-A0 — Scope Phase 10

| Option | Description | Selected |
|--------|-------------|----------|
| A: Solo DXY + US10Y (drop gold/oil) | Phase 10 v1 ridotto a 2 macro | |
| B: Solo news blackout MCP-13 | Drop intermarket MCP-10 | |
| C: ROADMAP letterale full scope | Tutti 4 macro + news | ✓ |

**User's choice:** C — ROADMAP letterale full scope.
**Notes:** "Se DXY/US10Y/gold/oil servono per istruire al meglio il sistema allora carichero i dati storici, non importa caricare 20MB in piu". Coerente con project memory training data integrity priority.

### D-10-A1 — Sorgente dati macro

| Option | Description | Selected |
|--------|-------------|----------|
| Stooq CSV statico committato | Deterministic + sha256 | ✓ |
| Hybrid MT5 + Stooq | Mixed sources | |
| All-API + SQLite cache | Runtime fetch | |
| Synthetic + MT5 | Computed baskets | |

**User's choice:** Stooq CSV statico committato.
**Notes:** Backtest deterministic by construction, zero failure mode rete PC secondario, dataset immutabile in repo.

### D-10-A2 — Granularita temporale

| Option | Description | Selected |
|--------|-------------|----------|
| Daily-only close | close(D-1) lookup strict-< | ✓ |
| H1 OHLC pieno | Full intraday | |
| Mixed daily 23.6y + H1 last-5y | Hybrid | |

**User's choice:** Daily-only close.
**Notes:** Intermarket/regime macro non confirmation realtime; Phase 7 ML feature space pulito 1 feature/symbol; Stooq free copre 23.6y daily ma H1 history richiede paid.

### D-10-A3 — Copertura temporale

| Option | Description | Selected |
|--------|-------------|----------|
| 23.6y full + sha256 anchor + manual refresh | Match Phase 5 baseline | ✓ |
| 10y window (2016+) + sha256 | Shorter coverage | |
| 23.6y full + auto-refresh cron | Auto-update | |

**User's choice:** 23.6y full + sha256 + manual refresh.
**Notes:** Match copertura baseline parquet Phase 5 plan 05-10 in flight, no mismatch coverage warning.

### D-10-A4 — Politica refresh

| Option | Description | Selected |
|--------|-------------|----------|
| Manual on-demand + sha256 abort | Explicit intent | ✓ |
| Cron weekly auto-refresh + sha256 validate | Auto + alarm | |

**User's choice:** Manual on-demand + sha256 abort on unintended change.
**Notes:** Training integrity prefers explicit-intent dataset changes; cron auto-refresh introduce silent drift risk.

---

## Area B — Calendar provider

### D-10-B1 — Provider scelto

| Option | Description | Selected |
|--------|-------------|----------|
| ForexFactory CSV dump + RSS live | UN provider per coerenza live/backtest | ✓ (poi REVISED post C0 a solo RSS live) |
| FRED API storico USD + FF RSS live | Multi-provider | |
| Investing.com scraping | Coverage globale | |
| Static CSV bundled only | No API live | |

**User's choice:** ForexFactory CSV dump + RSS live (poi ridotto a solo RSS live post D-10-C0 drop blackout backtest).
**Notes:** Coerente con ROADMAP SC#2 "es. ForexFactory RSS". Storico FF disponibile ~2007+ pubblico.

### D-10-B2 — Cadenza refresh + TTL cache

| Option | Description | Selected |
|--------|-------------|----------|
| Fetch on-demand + TTL 60 min | Cache persistita | ✓ |
| Cron refresh 30 min in scheduler | Sempre fresca | |
| Fetch ogni chiamata (no cache) | Real-time | |

**User's choice:** Fetch on-demand + TTL 60 min.
**Notes:** Pattern coerente Phase 8 ml/inference cache singleton + Phase 6 D-D1 BarSource as_of_ts.

### D-10-B3 — Filtro currency + impact

| Option | Description | Selected |
|--------|-------------|----------|
| Pair-aware High-only | Pair currencies + High impact | ✓ |
| Pair-aware High+Medium | Include tier-2 events | |
| Currency-agnostic High-only | All currencies, High only | |
| Solo USD High-only | Minimal coverage | |

**User's choice:** Pair-aware High-only.
**Notes:** ROADMAP SC#3 letterale "high-impact events". Stima 150-300 eventi/anno per pair = 0.4-0.8 blackout/giorno medio.

### D-10-B4 — Finestra blackout

| Option | Description | Selected |
|--------|-------------|----------|
| ±15 min strict | ROADMAP letterale | ✓ |
| Asimmetrica -15/+30 min | Pre + extended post | |
| Configurabile via env (default ±15) | Operator override | |

**User's choice:** ±15 min strict (poi post D-10-C0 ridefinito come default param tool, non blackout window).
**Notes:** ROADMAP letterale + pattern utente "rispetta la roadmap" Area A.

### D-10-B5 — Timezone conversion

| Option | Description | Selected |
|--------|-------------|----------|
| ET→UTC con DST rules zoneinfo | Una sola TZ interna | ✓ |
| ET→GMT-6 broker tz + ML in GMT-6 | Match source forex CSV | |
| Source-time everywhere (no conversion) | Runtime conversion | |

**User's choice:** ET→UTC con DST rules.
**Notes:** Utente ha chiarito "i dati storici hanno il fuso GMT-6". Conferma: forex CSV GMT-6 sorgente → loader BACK-01 → UTC interno; calendar RSS FF ET sorgente → tool Phase 10 → UTC interno. Comparison sempre in UTC.

### D-10-B6 — Eventi senza orario preciso

| Option | Description | Selected |
|--------|-------------|----------|
| Skip Tentative/All Day, blackout Holiday | Filter unreliable + protect holiday | ✓ (poi REVISED post C0 a flag senza blackout) |
| Skip tutti no-time events | Max deterministic | |
| Blackout full-day per tutti | Ultra-defensive | |

**User's choice:** Skip Tentative/All Day, Holiday flag senza blackout (post D-10-C0).
**Notes:** Tentative = unreliable per blackout deterministic; Holiday = deterministic + reale liquidity drought ma post-C0 advisory only.

---

## Area C — Backtest blackout coverage

### D-10-C0 — Drop blackout backtest (scope override)

| Option | Description | Selected |
|--------|-------------|----------|
| FRED reconstruction USD-only pre-2007 + FF dump post + re-baseline Phase 5 | Coverage 23.6y completa | (presented + rejected) |
| Drop blackout, MCP-13 live-only no auto-reject | Baseline Phase 5 immutato | ✓ |
| Skip MCP-13 totalmente | Phase 10 = solo MCP-10 | |
| Build MCP-13 live + risk_engine soft-warning | Hybrid live warning no block | |

**User's choice:** Drop backtest blackout, build MCP-13 live-only no auto-reject.
**Notes:** Utente "non voglio piu fare la parte di blackout, rispettiamo i backtest della base line, lo storico dei dati contiene tutti i giorno non esclude le festivita o altri eventi". Ragionamento: i CSV M15/M30/H1 contengono close-of-bar reali, strategy/ML imparano implicitamente da distribuzione P&L che include news-day spike. Trade-off accettato: asimmetria backtest/live + spike intrabar NFP appiattito nelle bar. Compensato da forex-trader-pro skill consultation MCP-13 manuale.

**ROADMAP impact:** SC#3 DEVIATED esplicito. Phase 10 SC count 3→2. Backlog: "Backtest blackout retroactive (Phase 11+ se paper trading rivela news-day overfit nel ML model)".

---

## Area D — Intermarket → strategy wiring

### D-10-D1 — Direction handling intermarket score

| Option | Description | Selected |
|--------|-------------|----------|
| Extend signature `(symbol, direction) -> float` | Score >0 = conferma direction | ✓ |
| Keep `(symbol,) -> float` + confluence flip se short | Pair-specific logic dentro fn | |
| Symmetric score [-1,+1] + direction_sign multiply | Range vincolato | |

**User's choice:** Extend signature `(symbol, direction)`.
**Notes:** Signature change additive backward-compat. Callsite confluence.py:266 passa direction. Pulito + estendibile.

### D-10-D2 — Rollout pattern

| Option | Description | Selected |
|--------|-------------|----------|
| ENABLE_INTERMARKET=false default, fn=None se false | Zero-impact rollout | ✓ |
| ENABLE_INTERMARKET=true default + re-baseline Phase 5 | Sempre attivo + re-run 23.6y | |
| Always-on, no env flag, no re-baseline | Training/live divergence | |

**User's choice:** ENABLE_INTERMARKET=false default.
**Notes:** Pattern identico Phase 7 D-07-06-11 ENABLE_ML_FILTER. Phase 5 baseline parquet immutato. Plan Phase 10 = wire + test, NO re-baseline. Operator opt-in post-Phase-11 paper trading.

### D-10-D3 — MCP-13 + skill integration

| Option | Description | Selected |
|--------|-------------|----------|
| Tool MCP-13 + doc in skill (consult on-demand) | Minimo touch skill | ✓ |
| Tool MCP-13 + skill auto-inject in pre-flight | Pre-flight chain modified | |
| Tool MCP-13 only, no skill changes | Defer skill integration | |

**User's choice:** Tool MCP-13 + doc in skill (consult on-demand).
**Notes:** Phase 10 = tool + breve sezione documentation nel skill markdown. Skill NON auto-inject in pre-flight chain. Operator decide se chiamare. Coerente D-10-C0 advisory-only.

---

## Claude's Discretion

Implementazione dettagli lasciati al planner (non forzati durante discuss):
- Aggregazione signal interna a `build_intermarket_score` (peso DXY vs US10Y vs XAUUSD vs WTI per ogni pair).
- Threshold del `if effective > threshold` in `compute_confidence`.
- Audit logging chiamate MCP-13.
- Fallback se FF RSS down (cache stale vs raise).
- Dataclass/Pydantic model response MCP-13.

## Deferred Ideas

- MCP-10 H1 intraday granularity (Phase 11+ se aggiunti CAD/NOK pair o swing trading).
- Auto-refresh cron weekly macro CSV (Phase 11+ se DEPLOY-02 ops surface refresh-staleness pain).
- Configurabile pre/post blackout window via env (moot post D-10-C0).
- Backtest blackout retroactive (Phase 11+ se paper trading rivela news-day overfit).
- Risk_engine news soft-warning live (Phase 11+ se operator manca contesto news).
- Skill forex-trader-pro auto-inject MCP-13 in pre-flight (Phase 11+ se on-demand insufficient).
- Re-baseline Phase 5 con ENABLE_INTERMARKET=true (Plan 10-XX deferred post-Phase-11).
