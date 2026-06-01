# Analisi Tecnica-Funzionale — trading-agent

> **Data:** 2026-05-30 · **Branch analizzato:** `research/edge-discovery` (HEAD `cd1c686`)
> **Metodo:** verifica diretta del codice e riesecuzione della test-suite. Le affermazioni dei
> documenti di progetto (STATE.md, CLAUDE.md, ROADMAP) sono state **trattate come ipotesi da
> verificare**, non come fatti. Dove documenti e codice si contraddicono, prevale il codice.
> Questo report è volutamente critico e imparziale rispetto alle memorie e alla narrativa interna.

---

## 0. TL;DR (executive summary)

Il progetto è **molto più costruito di quanto la sua stessa memoria dichiari**, ma è **fermo su un
fallimento di fondo che nessuna quantità di codice risolve**: la strategia non ha edge.

1. **Codice reale e sostanzioso esiste** per le fasi 1–6 (motore di backtest, libreria indicatori,
   catalogo pattern, refactor strategia in package puri, baseline backtest, MCP tools parte 1). Non
   è "tutto in planning, nessun codice prodotto" come afferma `CLAUDE.md` — quella memoria è **stale**.
2. **La strategia base (4 setup ATR) non ha edge**, e questo è stato **dimostrato con rigore** (motore
   deterministico, 209k trade, 117 sottoinsiemi, poi una ricerca esplorativa pulita in-sample/OOS). Il
   verdetto **NO-GO** è ben supportato dai numeri, non è pessimismo narrativo.
3. **Le fasi 7–11 (tutto il valore "ML" del milestone v2-ml-backtest) sono SOSPESE e non implementate.**
   Esistono solo i PLAN.md. I 3 handler ML in `mcp_tools/handlers/ml.py` sono **stub che sollevano
   `NotImplementedError`**.
4. **La test-suite NON è verde "out of the box" in questo ambiente.** 6 moduli non si collezionano
   nemmeno (mancano `apscheduler`, `feedparser`, `anthropic` dal devcontainer). Dei 500 test
   collezionabili: **477 passati, 2 falliti, 13 skipped, 8 xfailed** in **10m33s**.
5. **Igiene del repo scadente:** binari committati (`tradin-agent.zip` 4 MB, `trades.db`,
   `backtest_trades.json` 2.7 MB), 22 branch locali, sprawl documentale (3 playbook, 5 `.env.example`,
   file `.original`), memoria di progetto contraddittoria.
6. Due bug noti, uno **risolto** (kill-switch giornaliero permanente nel broker di backtest), uno
   **reale e aperto** (offset DST fisso +6h nel loader storico → ~metà anno sfasato di 1h).

**Caratterizzazione onesta dello stato:** *non* "70% completo". Più correttamente: **infrastruttura
ingegneristica matura (fasi 1–6 consegnate e testate) costruita sopra un'ipotesi di trading
falsificata. Il milestone v2-ml-backtest è in pausa indefinita: l'ML a valle non può partire finché
non esiste un edge a monte, e la ricerca dell'edge finora ha prodotto solo falsificazioni pulite.**

---

## 1. Cosa è IMPLEMENTATO (e verificato)

### 1.1 Stack di trading live (top-level) — **completo e cablato**

| Modulo | Stato | Note |
|---|---|---|
| `mt5_client.py` (407 righe) | ✅ completo | `BrokerProtocol` reale: OHLC, send_order, close, account_state, `modify_position`/`partial_close`/`get_position` (Fase 6); retry `@_retry(3)`, detection filling mode con cache |
| `risk_engine.py` | ✅ completo | kill-switch drawdown, filtro sessione, limiti SL pip, sizing PERCENT/FIXED, loop di downsizing su margine, 3 profili rischio |
| `execution.py` | ✅ completo (minimale) | `run_once` → risk_engine → send_order; rispetta `EXECUTION_MODE` (shadow di default) |
| `scheduler.py` (Fase 16) | ✅ completo | loop H24 interno (`IntradayLoopScheduler`), `DailyRunStateStore` SQLite, `OperatingWindow` timezone-aware, follow-up |
| `scanner.py` | ✅ completo | `MultiSymbolScanner` light-scan + deep analysis, integrazione opzionale news/sentiment |
| `news_aggregator.py` / `sentiment.py` | ✅ implementati, **opt-in** | RSS via feedparser + sentiment keyword-based; **disattivi di default** (`ENABLE_NEWS_SENTIMENT=False`, `RSS_FEEDS=[]`) |
| `models.py`, `config.py`, `logger.py` | ✅ completi | dataclass frozen; config 250+ knob tutto da `.env`, nessun magic number per i parametri critici |
| `claude_agent.py` | ⚠️ presente, non nel path-segnale | wrapper Anthropic; **non richiamato** dal loop live di main.py |

**Nota critica:** il sentiment/news è codice vivo ma **dead-by-default** in produzione → in deploy con
config standard il bias sentiment è sempre NEUTRAL.

### 1.2 `strategy/` — refactor in funzioni pure **reale e completo**

Contrariamente a quanto afferma `CLAUDE.md` ("nessun codice prodotto"), il package esiste ed è
sostanzioso e testato:

- 4 detector ATR puri: `a_breakout.py` (241 righe), `b_reversal.py` (325), `c_compression.py` (376),
  `d_pullback.py` (331).
- `confluence.py`: scorer 5-fattori + grade (A+/A/B/C/reject) + calibratore confidence, `lru_cache` su YAML.
- `proposal.py`: gate `min_grade`, `min_confidence`, `min_rr` per profilo — **tutti e tre cablati** e
  applicati dai 4 setup (era un bug storico CRIT-3 che `min_grade`/`min_confidence` fossero dead; ora
  risolto e testato in `test_profile_grade_filter.py`).
- `__init__.py`: `evaluate_proposal_for_bar` con tie-break (READY>FORMING>NONE, grade order, priorità
  A>C>B>D) e gate `enabled_setups` (frozenset).
- `adapters/{live,backtest}.py`, `context.py`, `_shim.py` (compat legacy `IntradayStrategy`).
- **Purezza enforced via AST** (`tests/test_strategy_purity.py`): vietati import I/O/broker/logging nei
  moduli puri.

**Setup B disabilitato di default** (`ENABLE_SETUP_B=False`): codice completo ma escluso, per scelta di
ricerca (regime-dipendente, zavorra in trend/range). In config default la strategia gira con **3 setup
su 4** (A, C, D).

### 1.3 `backtest/` — motore deterministico **reale**, con un bug risolto e uno aperto

- `engine.py` (396 righe): event-driven per-bar, `run_id` = hash(symbol|tf|times|costs) idempotente,
  nessun future-leakage (decisione a chiusura barra, finestra solo-passato).
- `broker.py`: **bug kill-switch RISOLTO** — `_starting_balance_of_day` ora viene ri-snapshottato al
  rollover di giorno UTC (`bar_day = int(bar.time)//86400`, righe 85–88), replica il comportamento
  live. Regression-test presente. (Il bug `f21abda` lo lasciava hard-coded → mascherava le perdite:
  è la ragione per cui la baseline 1076-trade del 2026-05-12 era un artefatto.)
- `loader.py`: **🔴 BUG DST APERTO E REALE** — `_GMT6_OFFSET = timedelta(hours=6)` applicato
  incondizionatamente (riga 11/51), nessuna gestione ora legale. In estate EU i bar H1 sono sfasati di
  1h. Commento "Verified vs 3 NFP candles" = verifica puntuale, non stagionale.
- `costs.py`, `ledger.py`, `metrics.py`, `walk_forward.py`, `baseline/*`: completi (walk-forward
  expanding, no-overlap; baseline multi-process con writer parquet/report/plot, determinism check).

### 1.4 `indicators/` — funzioni pure, **no look-ahead**

10 moduli (trend, momentum, volatility, structure, bars, volume, mtf, hurst, aggregate, _helpers).
`compute_all` (4-key) + `compute_all_extended` (~37-key). Test di **non-leakage rigorosi e
adversariali** (`test_baseline_no_future_leakage.py`: `compute(full)[i] == compute(bars[:i+1])[-1]`).

### 1.5 `mcp_tools/` — MCP server parte 1 **reale**; parte 2 (ML) **stub**

| Handler | Stato |
|---|---|
| `account.py`, `market.py`, `proposal.py`, `position.py`, `backtest.py` | ✅ reali (job queue ProcessPool cap=1, trail daemon, modify/close, R1/R2/R3 additivi) |
| `ml.py` (`train_ml_filter`, `predict_trade_quality`, `get_ml_calibration`) | 🔴 **stub `NotImplementedError`** (righe 127/142/153) — schema presenti, logica assente |

---

## 2. Cosa è SOSPESO / NON implementato

| Fase | Titolo | Stato reale | Evidenza |
|---|---|---|---|
| 7 | ML Classifier | 🔴 **0% eseguito**, SOSPESA 2026-05-29 | solo 6 PLAN.md; nessun package `ml/`; gate STRAT-REBUILD-03 non superato |
| 8 | MCP Tools parte 2 (ML) | 🔴 **~scaffolding**, SOSPESA | solo schema+stub `ml.py`; Wave 1-5 dipendono da Fase 7 |
| 9 | Failure Analysis + Drift | 🔴 **0% eseguito**, SOSPESA | 7 PLAN.md; assume un edge da monitorare, smentito |
| 10 | Intermarket + News | 🔴 **0% eseguito**, SOSPESA | CONTEXT+PLAN; hook `intermarket_score_fn`/`news_blackout_fn` presenti ma = None |
| 11 | Paper Deploy Gate | 🔴 **non pianificata** | nessun PLAN.md, nessuna dir di fase |

**Causa radice della sospensione (2026-05-29):** dopo aver *riparato e attivato* l'intero design
originale (confluence repair regime+spread, `ENABLE_SETUP_*`, attivazione `min_grade`), la validazione
onesta su 5 regimi × 2 pair ha dato **59/60 configurazioni negative**. L'edge non esiste; l'ML a valle
imparerebbe rumore. Decisione corretta: non costruire ML su una base senza segnale.

**`STRAT-REBUILD-01..04`** (requisiti aperti dal 2026-05-18): la strategia core deve dimostrare
expectancy **> +2 USD/trade su n≥1000 post-costi reali AND median PnL ≥ 0** prima di sbloccare la Fase 7.
Nessuna data di ripartenza, nessun owner formale → **pausa non gestita**, non una sospensione pianificata.

---

## 3. Il track "Edge Discovery" — la ricerca dell'edge

Track esplorativo non-GSD aperto dopo il NO-GO. **Metodologia rigorosa** (verificata indipendentemente
leggendo harness e JSON dei risultati, non solo i report):

- Team scettico: orchestratore + esploratore in-sample + validatore OOS indipendente.
- Anti-leakage con assert runtime + cutoff date documentati; sanity baseline (random/always-long/short);
  costi reali (spread+slippage+commission+swap); **demeaning** per separare segnale da drift; soglia |t|≥2.

**Ipotesi testate e tutte FALSIFICATE** (numeri verificati sui JSON):

| Ipotesi | Meccanismo | Esito | Perché muore |
|---|---|---|---|
| H-A1 | momentum prezzo DXY → direzione | ❌ | max \|t\|≈1.4 (<2); EUR circolare (DXY=57.6% EUR), JPY nullo |
| H-A2 | momentum yield US → direzione | ❌ | significativo in-sample (t −3.4/−3.8 EURUSD) ma OOS demeaned **flippa positivo**; GBPUSD non conferma → **regime-switching** |
| H-A3 | livello differenziale tassi (carry) | ❌ | demeaned EURUSD \|t\|<0.5 e incoerente; USDJPY degenera in always-long |
| Carry unconstrained | carry+swap, no flat-by-Friday, hold 1–15gg | ❌ | EURUSD demeaned peggiora con M; USDJPY = solo swap passivo (investing, non trading) |
| COT fade | estremi posizionamento → reversal | ❌ | incoerente cross-pair, nessun \|dem_t\|≥2, t gonfiato da overlap |

**Meta-lezione robusta:** le relazioni intermarket/macro sui major USD sono **cross-pair incoerenti e
regime-switching** — il segno del legame cambia tra crisi e calma. Aree A/B/C considerate esaurite
sotto il confine "trading ≤15gg".

**Caveat critici che ho rilevato sulla ricerca stessa:**
- L'H-A1 nel JSON **non riporta il demeaning** (a differenza di A2/A3): la conclusione "nullo" regge
  comunque (max \|t\|<2), ma c'è una piccola discrepanza tra il "max \|t\|=1.66" del log e i numeri del
  JSON (max ≈1.42). Irrilevante per il verdetto.
- COT: i t-stat **non sono corretti per autocorrelazione da overlap** (a M=15 solo ~43% trade
  indipendenti) → i pochi positivi USDJPY sono ancora più deboli di quanto riportato. Il verdetto
  (nullo) ne esce **rafforzato**, non indebolito.
- **"Mean-reversion 2020/2023 da Setup B" — claim ORFANO.** Il log lo cita come "unico segnale di edge
  reale" ma **non esiste un report/JSON di validazione dedicato**. È un lead non validato, non un
  finding. Andrebbe testato formalmente o ritirato dalla narrativa.

**Bug DST e contaminazione:** l'evidenza Dukascopy (match 99.2% a +1h vs 36% a 0h, giu-2015) è
**plausibile ma non conclusiva** (campione 1 settimana × 2 mesi, solo EURUSD H1). Conclusione corretta
nel log: i test **daily** (A/B/C) sono **DST-immuni** → non invalidati; i test **intraday di
sessione/evento (Area D)** passano da "esclusi" a "contaminati, da ri-testare". ✅ Riclassificazione
sensata, ma le memorie che parlano di "contaminazione" non devono essere lette come "edge nascosto
dimostrato": è un sospetto aperto.

---

## 4. Test — stato reale (rieseguito, non dichiarato)

**La suite NON gira pulita in questo ambiente.**

- **6 moduli non si collezionano** per dipendenze mancanti nel devcontainer (`apscheduler`,
  `feedparser`, `anthropic`): `test_scheduler`, `test_daily_orchestrator`, `test_mcp_handlers_market`,
  `test_mcp_tools_v2`, `test_news_aggregator`, `test_phase16`. `requirements.txt` le elenca ma non sono
  installate qui → ambiente di sviluppo non riproducibile.
- Escludendo quei 6 moduli: **500 test collezionati → 477 passed, 2 failed, 13 skipped, 8 xfailed** in
  **633s (10m33s)**.
- **2 fallimenti reali:**
  1. `test_smoke_12month_under_60s` — perf: motore O(N²), budget 60s sforato. **Noto e deferito** da
     mesi (plan 01-09 vectorization mai fatto).
  2. `test_legacy_entrypoint_imports` — `import mcp_server` fallisce (dipendenza mancante, stesso
     problema d'ambiente).
- **8 xfailed:** 3 sono gli stub ML (`strict=True`, flipperanno a PASS quando/se la Fase 8 verrà
  implementata); gli altri sono feature Wave 4 deferite.
- Path Windows `C:\trading-agent\...` che appare nei traceback = **bytecode `.pyc` cached** da run
  Windows, non un path hard-coded nei sorgenti (questi usano path relativi). Igiene cross-platform, non
  bug.

**Qualità dei test:** buona ampiezza, profondità media. Forti: backtest engine (segnali sintetici,
determinismo), no-leakage (adversariali), regression snapshot strategia (10 scenari), detector A/B/C/D.
Deboli/assenti: **nessun test unit dedicato** per `risk_engine.py`, `execution.py`, `claude_agent.py`,
`mcp_server.py`, `mcp_tools/handlers/account.py`; i test live MT5 sono skip-gated (servono credenziali).

---

## 5. Bug e rischi tecnici concreti

| # | Severità | Item | Stato |
|---|---|---|---|
| 1 | 🔴 alta | Offset DST fisso +6h in `loader.py` → ~metà anno H1 sfasato 1h; contamina test sessione/evento e qualunque logica intraday time-sensitive | **APERTO** (policy: Dukascopy canonico per dati nuovi, no patch) |
| 2 | 🟢 risolta | Kill-switch giornaliero permanente in `BacktestBroker` (mascherava le perdite della baseline) | **RISOLTO** (`f21abda` + reset rollover UTC) |
| 3 | 🟡 media | Suite non riproducibile: 6 moduli non collezionano per deps mancanti nell'ambiente | **APERTO** (allineare devcontainer a `requirements.txt`) |
| 4 | 🟡 media | Perf motore O(N²): smoke 12-mesi >60s, backtest full ~10min | **deferito** da mesi |
| 5 | 🟡 media | News/sentiment cablati ma dead-by-default; `claude_agent` non nel path-segnale | by-design, ma il valore dichiarato non è attivo |
| 6 | 🟢 bassa | Handler ML = stub `NotImplementedError` ma schema esposti dal server MCP → chiamarli dà errore | atteso (Fase 8 sospesa) |

---

## 6. Igiene repo e disallineamento documentale

**Artefatti binari committati (da rimuovere):** `tradin-agent.zip` (4 MB, anche col typo nel nome),
`backtest_trades.json` (2.7 MB), `trades.db` + `logs/trades.db`, `_tmp_write_05.py` (55 KB),
`__pycache__/`. Diversi violano già `.gitignore` ma erano stati committati prima.

**Sprawl documentale:** 3 `STRATEGY-REBUILD-PLAYBOOK` (v1/v2/v3, precedenza non chiara), 5+ `.env.example*`,
coppie `*.original.md` (CLAUDE/COMMIT_CONVENTIONS/HANDOFF), `PHASES.md` obsoleto (struttura v1 a 13 fasi),
due `STATE.md` (root + `.planning/`).

**Memoria contraddittoria — punto chiave per l'imparzialità richiesta:**
- `CLAUDE.md` afferma: branch `feature/update-pythono-pure-strategy` e *"tutte in PLANNING (nessun codice
  prodotto ancora)"*. **FALSO/STALE:** HEAD è `research/edge-discovery`; fasi 1–6 hanno codice eseguito,
  testato e committato. *Non fidarsi di questa memoria.*
- La fonte canonica accurata è **`.planning/STATE.md` + `.planning/ROADMAP.md` + `.planning/REQUIREMENTS.md`**,
  non `CLAUDE.md` né il `STATE.md` di root.
- ⚠️ **Nota su un'analisi parallela:** un sub-agente che si è basato su `CLAUDE.md` ha concluso "fasi 1–4
  senza codice". È **errato** — smentito dall'albero file e dalla lettura dei sorgenti. Esempio di come la
  memoria stale induce in errore: ho corretto questa conclusione verificando i file.

**Branch:** 22 locali (+16 remoti), molti stale/non-merge (`feature/mean-reversion`, `feature/ml-feedback-loop`,
`feature/strategy-v2-defendi/v3-intermarket`, `hotfix/v1.1.1`, vari `worktree-agent-*` e `claude/*`).

**Sicurezza:** `.env` **non** è tracciato (corretto); solo i `.env.example*` lo sono (nessun segreto).

---

## 7. Caratterizzazione onesta del "completamento"

`STATE.md` dichiara *"70% — 6/11 fasi"*. È fuorviante perché conta le fasi pianificate come fatte.
Letture più oneste:

- **Per codice consegnato:** fasi 1–6 implementate ed eseguite (engine, indicatori, pattern, strategia,
  baseline, MCP parte 1). Fasi 7–11 = **0% codice**. → **~55% del milestone consegnato come
  infrastruttura**, ma…
- **Per valore di prodotto:** il deliverable centrale del milestone v2-ml-backtest è *"ogni trade
  pre-filtrato da un classificatore ML calibrato"*. Questo è **0%**, e **bloccato a monte**: richiede un
  edge che non esiste.
- **Quindi:** il progetto ha un **eccellente apparato ingegneristico (testato, deterministico,
  anti-leakage) al servizio di una strategia senza edge**. Il lavoro di fix non è perso — il codebase è
  pulito e riutilizzabile il giorno in cui emergesse un segnale tradabile — ma oggi **non esiste un
  percorso verso il deploy** senza prima trovare un edge.

---

## 8. Cosa resta da fare (prioritizzato, onesto)

**Bloccante (sblocca tutto il resto):**
1. **Trovare un edge** entro il confine "trading ≤15gg", oppure ridefinire il confine con l'utente. Le
   aree A/B/C sono esauste; restano: Area D (sessione/evento) **da ri-testare su dati DST-corretti
   Dukascopy**, microstruttura/order-flow (Area E, serve tick data), strumenti diversi (futures, Area F),
   e la validazione formale del claim orfano "mean-reversion 2020/2023".
2. Decidere il **bug DST**: adottare Dukascopy come canonico e ri-derivare l'intraday se si torna su edge
   time-sensitive.

**Solo SE emerge un edge (le fasi sono pronte come piani):**
3. Fase 7 ML, poi 8 (implementare i 3 stub), 9 (drift), 10 (intermarket/news), 11 (paper deploy 30gg).

**Indipendente dall'edge (debito tecnico, fattibile ora):**
4. Allineare il devcontainer a `requirements.txt` (suite non riproducibile).
5. Rimuovere binari committati; potare branch; consolidare i doc; **aggiornare o cancellare `CLAUDE.md`**.
6. Vettorizzare il motore di backtest (O(N²) → smoke <60s).
7. Aggiungere test unit per `risk_engine`, `execution`, `mcp_server`.

---

## 9. Tabella di sintesi

| Area | Implementato | Testato | Note critiche |
|---|---|---|---|
| Stack live (MT5/risk/exec/scheduler/scanner) | ✅ | ⚠️ parziale (no unit su risk/exec; live skip-gated) | news/sentiment dead-by-default |
| `strategy/` 4 setup + confluence + gate | ✅ | ✅ (purity AST, regression, setup) | Setup B off di default; **senza edge** |
| `indicators/` | ✅ | ✅ (no-leakage rigoroso) | — |
| `backtest/` engine + baseline | ✅ deterministico | ✅ | KS-bug risolto; **DST-bug aperto**; O(N²) lento |
| `mcp_tools/` parte 1 | ✅ | ✅ | job queue, trail daemon reali |
| `mcp_tools/handlers/ml.py` | 🔴 stub | xfail strict | `NotImplementedError` |
| Fasi 7–11 (ML/drift/intermarket/deploy) | 🔴 solo PLAN | — | **SOSPESE** — nessun edge a monte |
| Edge discovery | ✅ harness + 5 ipotesi | n/a | metodologia solida; **tutte falsificate** |
| Igiene repo / doc | 🔴 | n/a | binari committati, doc sprawl, `CLAUDE.md` stale |

---
*Report generato verificando il codice e rieseguendo i test il 2026-05-30. Le conclusioni sul "nessun
edge" sono confermate dai numeri; le affermazioni di `CLAUDE.md` sullo stato del codice sono risultate
stale e non sono state usate come fonte.*
