---
name: forex-strategy-builder
description: Build, refine, and validate robust forex intraday strategies inside this Python trading-agent repo. Grounds rules in a curated PDF knowledge base (Murphy intermarket, Probo forex operativo, StrategieOperative) located in C:\trading-agent\libri\. Use when user asks to create/modify trading rules, add indicators, tune entry/exit logic, design SL/TP schemes, add multi-timeframe confluence, sentiment gating, drawdown protection, backtest-ready logic, or cite/apply textbook patterns. Triggers on phrases like "strategia forex", "nuova strategia", "migliora setup READY", "aggiungi indicatore", "regole entry", "trailing stop", "multi-timeframe", "filtra segnali", "robust strategy", "Murphy", "Probo", "intermarket", "libri PDF".
---

# Forex Strategy Builder — Trading Agent (Python Pure)

Skill per progettare strategie forex robuste e deterministiche nel daemon Python di questo repo. Output: codice production-ready in `strategy.py`/`indicators.py`/`scanner.py` + test pytest + parametri `.env`.

## Vincoli non negoziabili

1. **Deterministica** — zero ML, zero random. Stesso input → stesso output.
2. **Config via `.env`** — zero magic numbers nel codice. Aggiungere a `config.py` + `.env.example*`.
3. **EXECUTION_MODE=shadow** default. Mai abilitare `live` senza richiesta esplicita.
4. **Risk engine = unico gate finale** ordine. Non bypassare `risk_engine.evaluate_trade`.
5. **Italiano** per commenti/log/rationale. Codice/identifier in inglese.
6. **Test pytest obbligatori**, mock `Mt5Client` (no connessione reale).
7. **Indicatori** in Python puro (no pandas/ta-lib) — pattern già stabilito in `indicators.py`.

## File chiave (mappa)

| File | Ruolo |
|---|---|
| `strategy.py` | `IntradayStrategy.analyze_symbol`, `identify_entry_setup`, `_compute_levels`, `evaluate_open_position` |
| `indicators.py` | SMA/EMA/RSI/ATR/trend_strength/SR/breakout |
| `patterns.py` | candlestick patterns |
| `scanner.py` | light scan + deep analyze + decisione ciclo |
| `scheduler.py` | loop H24, gestione posizioni, heartbeat |
| `risk_engine.py` | sizing, SL bounds, drawdown rolling 24h |
| `config.py` | parser `.env` |
| `models.py` | `TechnicalSetup`, `TradeProposal`, `OpenPositionVerdict` |
| `tests/test_strategy.py`, `test_indicators.py` | suite pytest |

Doc viva: `STRATEGIA_PYTHON.md`. Aggiornare quando si cambia logica.

## Knowledge base — libreria PDF

Path: `C:\trading-agent\libri\` (root repo, fuori worktree). Tre PDF curati = fonte autorevole per regole, pattern, e confluence. Consultare PRIMA di inventare logica nuova.

| File | Autore/Tema | Quando consultare |
|---|---|---|
| `TradingIntermarketMurphy.pdf` | John Murphy — analisi intermarket (USD index, bond, oro, equity, commodity) | Filtri macro, correlazioni cross-asset, regime risk-on/off, conferma trend valuta via DXY/yield |
| `TradingOperativoForexProbo.pdf` | Giuseppe Probo — forex operativo retail | Setup intraday FX, gestione sessioni London/NY, money management, esempi entry/exit pratici |
| `StrategieOperative.pdf` | Strategie operative generaliste | Pattern price action, breakout, pullback, gestione SL/TP, archetipi strategici |

### Come usare i PDF

1. **Lettura targettata** — usare tool `Read` con `pages:"N-M"` (max 20 pagine/call). MAI leggere PDF intero senza range.
2. **Indice prima** — leggere TOC (prime ~5 pagine) per localizzare capitolo rilevante, poi range mirato.
3. **Citare la fonte** nei commenti italiani del codice quando regola viene da libro:
   ```python
   # Filtro intermarket: USD long valido solo se DXY > SMA50 (Murphy, cap. X)
   ```
4. **Verifica empirica** — regola da libro ≠ regola valida. Sempre test pytest + 1 sessione shadow prima di promuovere.
5. **Conflitto fonti** — se Murphy dice X e Probo dice Y, preferire **Probo per intraday FX retail** (più aderente al daemon), Murphy per **filtri di contesto macro**.

### Mappatura libri → componenti repo

| Componente repo | PDF di riferimento primario |
|---|---|
| Filtri trend HTF + bias DXY/yield | Murphy |
| Regole entry/exit M15, sessioni, money management | Probo |
| Pattern price action, breakout/pullback, SL/TP archetipi | StrategieOperative |
| Indicatori base (RSI, MACD, ATR, Bollinger) | tutti e 3 (incrocio) |

### Pattern d'uso tipico

User: "aggiungi filtro intermarket USD" →
1. `Read TradingIntermarketMurphy.pdf` TOC → localizza cap. su DXY.
2. `Read` range mirato (es. 20 pagine).
3. Estrai regola operativa testabile (es. "USD long su EURUSD richiede DXY > SMA50 H4").
4. Implementa in `strategy.py` dietro flag `.env` (`ENABLE_INTERMARKET_FILTER=false` default).
5. Test pytest mock con bars sintetici.
6. Cita Murphy + capitolo nel commento.

---

## Pillars di una strategia forex robusta

Quando proposta nuova strategia o tuning, valutare TUTTI:

1. **Trend filter multi-TF** — entry M15 confermato da bias H1 (e opz. H4). Evita controtrend in trend forte.
2. **Volatility regime** — ATR pips dentro `[MIN_ATR_PIPS, MAX_ATR_PIPS]`. Skip mercato morto e whipsaw.
3. **Entry trigger** — breakout pulito (volume ≥ avg×ratio) **o** pullback su MA in trend. Mai entry "a metà range".
4. **Confluence** — almeno 2 segnali concordi: MA align + (breakout|pattern) + (S/R|RSI non estremo).
5. **Risk:Reward ≥ 1.5** strutturale. SL dietro swing/S-R + buffer ATR, non distanza fissa.
6. **Session/news guard** — finestra operativa, blackout pre/post news ad alto impatto.
7. **Correlation cap** — non aprire N posizioni stesso "basket" (USD-long EURUSD+GBPUSD = 1 trade).
8. **Drawdown rolling** — daily + 24h cap, già in `risk_engine`.
9. **Exit dinamico** — chiusura su contesto negativo + profitto sufficiente (`MIN_PROTECT_PROFIT_R_MULTIPLIER`). Opz. trailing su ATR/swing.
10. **No re-entry whipsaw** — cooldown N minuti dopo stop loss stesso simbolo+direzione.

## Workflow per nuova feature/strategia

1. **Capire intent**: chiedere se più trade, meno trade, miglior win-rate, o nuovo regime.
2. **Mappare ai pillars**: identificare gap (es. manca multi-TF → propose).
3. **Design micro-step**: una feature per volta. No big-bang.
4. **Aggiungere param `.env`** in `config.py` con default safe (mantiene comportamento attuale se `False/0`).
5. **Implementare**:
   - Indicatore nuovo → `indicators.py` + test in `tests/test_indicators.py`.
   - Filtro entry → arg in `identify_entry_setup`, AND nelle regole READY.
   - Filtro exit → ramo in `evaluate_open_position`.
   - Multi-TF → caricare bars TF aggiuntivo via `Mt5Client.copy_rates` in `_analyze_technical`.
6. **Test pytest**: caso positivo, negativo, edge (NaN, len<lookback). Mock `Mt5Client`.
7. **Aggiornare `STRATEGIA_PYTHON.md`** sezione affetta.
8. **Aggiornare `.env.example` + varianti** `aggressive`/`moderate`/`conservative`.
9. **Aggiornare `STATE.md`** dopo ogni micro-step (regola progetto).
10. **Validare in shadow** ≥1 sessione prima di proporre live.

## Snippet pattern — aggiungere filtro entry

```python
# config.py
ENABLE_HTF_TREND_FILTER: bool = _get_bool("ENABLE_HTF_TREND_FILTER", False)
HTF_TIMEFRAME: str = _get_str("HTF_TIMEFRAME", "H1")
HTF_MIN_TREND_STRENGTH: float = _get_float("HTF_MIN_TREND_STRENGTH", 0.4)

# strategy._analyze_technical (estratto)
htf_strength = None
if cfg.ENABLE_HTF_TREND_FILTER:
    htf_bars = mt5.copy_rates(symbol, cfg.HTF_TIMEFRAME, 200)
    htf_strength = calculate_trend_strength(...)

# identify_entry_setup — AND aggiuntivo
if cfg.ENABLE_HTF_TREND_FILTER:
    if direction == "BUY" and (htf_strength or 0) < cfg.HTF_MIN_TREND_STRENGTH:
        return TechnicalSetup(setup_type="NONE", note="htf_trend_weak", ...)
```

## Snippet pattern — trailing stop ATR

```python
# scheduler ciclo open positions, dopo evaluate_open_position == HOLD
if cfg.ENABLE_ATR_TRAILING and pos.profit_r >= cfg.TRAIL_ACTIVATE_R:
    new_sl = (
        last_close - cfg.TRAIL_ATR_MULT * atr_value if pos.is_buy
        else last_close + cfg.TRAIL_ATR_MULT * atr_value
    )
    if pos.is_buy and new_sl > pos.sl:
        mt5.modify_sl(pos.ticket, new_sl)
    elif (not pos.is_buy) and new_sl < pos.sl:
        mt5.modify_sl(pos.ticket, new_sl)
```

## Checklist anti-overfit

- Param nuovo: ha **range realistico** documentato? (min/max/default)
- Default non altera comportamento attuale (backward compat)?
- Test copre boundary (esattamente al threshold)?
- Logica è **monotona**? (alzare param non genera trade in più paradossali)
- Nessun look-ahead bias? (uso solo bar `[:-1]` chiuse, mai `[-1]` candela in formazione se non close ufficiale)

## Trappole forex note (evitare)

- **Whipsaw breakout**: breakout senza volume conferma → fakeout. Già gestito con `MIN_BREAKOUT_VOLUME_RATIO`.
- **News spike**: SL saltato da gap. Gestire con news blackout (sez. 6 STRATEGIA_PYTHON.md).
- **Spread widening fine sessione**: filtrare con `MAX_SPREAD_PIPS` runtime (oggi solo light_scan).
- **Correlation overload**: EURUSD + GBPUSD + AUDUSD long = stesso bet su USD short.
- **Overnight gap weekend**: `CLOSE_BEFORE_END_OF_WINDOW=true` + chiusura venerdì pre-close.
- **Pip vs point**: JPY pairs digits=3, EURUSD digits=5 → `_pip_size` già normalizza, riusare.
- **Filling mode broker**: TenTrade vuole `ORDER_FILLING_RETURN`. Già gestito.

## Validazione finale (prima di dichiarare done)

1. `python -m pytest tests/ -q` — tutta verde.
2. Revisione manuale che `EXECUTION_MODE` resta `shadow`.
3. `.env.example` aggiornato.
4. `STRATEGIA_PYTHON.md` riflette modifica.
5. `STATE.md` aggiornato fase corrente.
6. Commit segue `COMMIT_CONVENTIONS.md`. **NO** trailer `Co-Authored-By` (regola memoria utente).
7. Push `origin` dopo fase validata (regola memoria utente).

## Quando proporre nuova strategia ex-novo

Se utente chiede "strategia diversa" (non tuning), proporre 2-3 archetipi tra:
- **Trend continuation pullback** (default attuale enhanced)
- **Range mean-reversion** (RSI estremi su S/R, opposto a breakout)
- **London/NY breakout** (range Asian session, breakout su apertura London)
- **Multi-TF momentum** (H1 trend + M15 trigger + M5 entry timing)

Per ognuno: pillars coperti, param `.env` necessari, file da toccare, test minimi. Far scegliere prima di codare.
