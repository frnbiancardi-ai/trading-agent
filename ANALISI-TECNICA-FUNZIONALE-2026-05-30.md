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

## 10. Mappa di TUTTI i branch e tag

> Analisi di ogni branch (locale + remoto) e tag, con divergenza misurata rispetto a `main`
> (`git rev-list --left-right`) e stato di merge verificato. Obiettivo: capire cosa è disponibile,
> cosa è recuperabile e cosa è morto.

### 10.1 Topologia generale

- **`main` = `bdaf3ee` (2026-05-28 "Added Historical data").** Contiene **già** tutto il build GSD v2
  (verificato: `strategy/setups/a_breakout.py`, `indicators/trend.py`, `backtest/engine.py`,
  `mcp_tools/server.py` sono in `main`). Quindi le fasi 1–6 sono su `main`.
- ⚠️ **`main` NON contiene la fix-chain** (confluence repair, `ENABLE_SETUP_*`, attivazione
  `min_grade`, finding NO-GO, batterie edge). Quei 7 commit vivono **solo** su `research/edge-discovery`.
  → **`main` è esso stesso stale**: la strategia su `main` ha ancora i bug morti CRIT-1/2/3; la versione
  corretta è solo sul branch di lavoro corrente.
- **`research/edge-discovery` = HEAD = vera punta** (7 avanti, 0 indietro rispetto a `main`). È il branch
  da promuovere a `main` quando si vorrà consolidare.
- Esiste una **galassia di esperimenti paralleli abbandonati** (strategie alternative) forkati dall'era
  flat-file v1.2.x, 260+ commit indietro, mai reintegrati.

### 10.2 Tag rilasciati (5 release)

| Tag | Data | In `main`? | Contenuto |
|---|---|---|---|
| `v1.0.0` | 2026-04-29 | ✅ sì | MVP 10 fasi: MT5 client, risk engine, indicatori pure-python, Claude agent, MCP server stdio (6 tool). "10/10 phases validated", shadow OK su demo |
| `v1.1.0` | 2026-04-30 | ✅ sì | Multi-symbol scanner + MCP 10 tool + scheduled orchestrator APScheduler. "72/72 test" |
| `v1.1.1` | 2026-05-01 | ❌ no (superato) | Hotfix filling-mode TenTrade. Fuori dalla history di `main` ma rimpiazzato da v1.2.0 |
| `v1.2.0` | 2026-05-02 | ✅ sì | **Python Pure Strategy** (IntradayStrategy + scanner, Claude ridotto a explain_last_trades), RSS sentiment, scheduler H24 interno. "173/173 test" |
| `v1.2.1` | 2026-05-04 | ✅ sì | Fix per-symbol filling mode via bitmask `symbol_info` |

**Lettura critica:** i tag sono coerenti e rappresentano l'**architettura flat-file v1.x** (monolite
`strategy.py`, `indicators.py`, `backtest.py`). Tutto il lavoro v2 (package `strategy/`, `indicators/`,
`backtest/`) è **post-v1.2.1 e NON taggato** — non esiste una release v2. Il sistema "live" realmente
rilasciato e validato dall'utente è la **v1.2.1**, non il codice attuale.

### 10.3 Linea attiva (da tenere)

**`research/edge-discovery`** — *7 avanti / 0 indietro main · HEAD*
La punta reale. Aggiunge alla `main`: fix confluence (regime+spread), `ENABLE_SETUP_*` + disable B,
attivazione `min_grade`/`min_confidence` (CRIT-3), verdetto NO-GO, 2 batterie edge-discovery. **Tutto il
lavoro recente e corretto è qui.** → da promuovere a `main`.

**`feat/activate-min-grade` (5↑), `feat/enable-setup-flags-disable-b` (3↑), `fix/confluence-repair-regime-spread` (1↑)**
Catena lineare di fix, **tutti 0 indietro main**, interamente **subsumed da `research/edge-discovery`**.
Non contengono nulla che non sia già nella punta. → **eliminabili** (locali, ridondanti).

**`fix/setup-b-remove-counter-trend-gate`** — *0 avanti / 6 indietro · merged*
Già in `main`. → eliminabile.

### 10.4 Build GSD v2 (merged in main)

**`feature/update-pythono-pure-strategy`** — *0 avanti / 7 indietro main · merged*
È **il branch su cui è stato costruito tutto il v2-ml-backtest** (fasi 1–6: package puri, baseline,
MCP). Già fuso in `main`. ⚠️ È il branch che **`CLAUDE.md` indica ancora come "corrente"** — riferimento
stale: il lavoro si è spostato su `research/edge-discovery` da settimane. → branch eliminabile (è in
`main`), ma prima va corretta la memoria che lo cita.

### 10.5 Esperimenti strategici paralleli ABBANDONATI (forkati da v1.2.x, mai reintegrati)

Questi sono **universi alternativi** in architettura flat-file, tutti ~260–265 commit indietro `main`.
Contengono codice unico **non presente da nessun'altra parte**. Valore storico/di idee, ma **non
allineati** all'attuale architettura a package e basati su backtest meno rigorosi.

**`feature/strategy-v3-intermarket`** — *27 avanti / 265 indietro · +7705 LOC*
Il più elaborato. Linea "Murphy/Probo": intermarket context engine, regime detector RISK_ON/OFF/INFLATIONARY,
correlation monitor + divergence, cross-asset filter, session awareness, fibonacci multi-target. Più:
importer dati (HistData, yfinance), grid-search confidence, e un commit chiave `fix(backtest): look-ahead
bias + cost modeling realistico`. **Segnale critico:** il fatto che abbiano dovuto *correggere il
look-ahead bias* implica che i numeri di backtest precedenti su questa famiglia erano contaminati. → idee
intermarket riutilizzabili (le stesse poi formalizzate e **falsificate** nel track edge-discovery); codice
non riallineabile facilmente. **Archiviare, non reintegrare.**

**`feature/strategy-v2-defendi`** — *8 avanti / 265 indietro · +3505 LOC*
Antenato di v3. Strategia "Defendi": indicatori avanzati (Bollinger, MACD, Vortex, VHF, PSAR),
compressione volatilità, pullback engine, MTF bias, position management, backtest harness, calibration.
Sottoinsieme di v3-intermarket. → **archiviare.**

**`feature/ml-feedback-loop`** — *18–19 avanti / 261 indietro · +2201 LOC*
Linea "RSI+SMA + auto-learning". Claim espliciti: *"60%+ win rate"*, *"3405 pips in 1 year"*, *"61.5% WR
con H15+RSI65-80"*, *"56% WR no lookahead"*, auto-trainer persistente, skill `forex-ml-feedback`, mean
reversion Bollinger. ⚠️ **Da trattare con forte scetticismo:** sono risultati di un `backtest.py` flat
non sottoposto all'harness rigoroso (in-sample/OOS/demeaning/costi) del track edge-discovery; la stessa
famiglia (mean-reversion/RSI su major H1) è stata poi **esplicitamente testata e rigettata** dalla ricerca
formale. I "60% WR / 3405 pips" sono quasi certamente overfit o look-ahead (cfr. il fix look-ahead di v3).
Cancella anche i file `.original.md` e `STRATEGIA_PYTHON.md`. → **archiviare; NON fidarsi dei numeri.**

**`feature/mean-reversion-strategy`** (solo remoto) — *7 avanti / 261 indietro · +912 LOC*
Radice della linea ml-feedback (commit condiviso `adfd6df`). Mean reversion Bollinger + RSI_SMA + Monte
Carlo "strategy is ROBUST" + backtest engine. 🔑 **Rilevante per il claim orfano "mean-reversion
2020/2023":** esiste davvero una linea mean-reversion con auto-dichiarata robustezza, ma **basata sullo
stesso backtest non rigoroso**. Conferma che il "mean-reversion = unico edge reale" è una **suggestione
ricorrente mai validata col metodo serio**, non un finding. → archiviare; eventualmente ri-testare
l'ipotesi **solo** dentro l'harness edge-discovery.

### 10.6 Branch automazione/agent (leftover — da rimuovere)

**`claude/dreamy-poitras-69931a` (20↑)** — ml-feedback + mapping `.planning/codebase/*`. Il mapping
codebase è **già in `main`**; il resto è ml-feedback. → eliminabile.
**`claude/gracious-antonelli-225ac7` (18↑)** — lineage ml-feedback ("cleanup ml_feedback files"). → eliminabile.
**`claude/youthful-cohen-8ac772` (1↑)** — aggiunge skill `forex-strategy-builder` (PDF KB). La skill è
utile ma vive in `.claude/skills/`; valutare se è già installata globalmente. → eliminabile dopo verifica.
**`claude/loving-thompson-867af8`** — *0 avanti / merged* (= merge commit v1.2.0). → eliminabile.

**`worktree-agent-*` (5 branch)** — leftover dei worktree GSD (fasi 01/06). Tre sono **worktree linkati
e "locked"** con path Windows incorporati (`.git/worktrees/.../C:/trading-agent/...`). Due (`a2a7361d`,
`af91a95`) sono già merged. → **prune worktree + delete branch.**

### 10.7 Branch storici (chiudibili)

| Branch | vs main | Natura | Azione |
|---|---|---|---|
| `feature/python-pure-strategy` | 0↑ / merged | base di v1.2.0 | eliminabile |
| `docs/validation-phases-14-15` | 1↑ / 295↓ | checklist validazione fasi 14-15 | archiviare/eliminare |
| `hotfix/v1.1.1-broker-filling` | 1↑ / 299↓ | = tag v1.1.1, superato da v1.2.x | eliminabile (resta il tag) |

### 10.8 Verdetto sui branch

- **Unica fonte di verità del codice corrente:** `research/edge-discovery`. Andrebbe promosso a `main`
  (o mergiato) per eliminare l'ambiguità "main stale vs branch di lavoro".
- **Codice unico a rischio-perdita SOLO se si cancellano i branch esperimento:** `strategy-v3-intermarket`,
  `strategy-v2-defendi`, `ml-feedback-loop`, `mean-reversion-strategy`. Prima di eliminarli, se hanno
  valore, vanno **taggati come archivio** (`archive/strategy-v3-intermarket`, ecc.) così il codice resta
  raggiungibile senza inquinare la lista branch. **In questa sessione li PRESERVO** (vedi §11).
- Tutti gli altri branch (fix-chain locali, `claude/*`, `worktree-agent-*`, merged) sono **ridondanti o
  morti** e rimossi nella fase di igiene.

---

## 11. Igiene del progetto (eseguita in questa sessione)

**File rimossi (~8 MB):**
- `tradin-agent.zip` (4 MB, zip di backup del repo), `trades.db` (root, db runtime), `backtest_trades.json`
  (2.7 MB), `backtest_results.json`, `__pycache__/` (con bytecode Windows `C:\`).
- Tracciati e ridondanti (`git rm`): `_tmp_write_05.py` (55 KB scratch), `CLAUDE.original.md`,
  `COMMIT_CONVENTIONS.original.md`, `HANDOFF_PROTOCOL.original.md`, `logs/trades.db`.
- `.gitignore` aggiornato: aggiunti `/trades.db`, `*.zip`, `_tmp_*.py`. **Mantenute** le righe
  `backtest_results.json`/`backtest_trades.json` perché `tests/test_legacy_cleanup.py` le verifica.

**Worktree:** rimossi 4 worktree GSD orfani (lock PID morti, directory già inesistenti, path Windows
`C:/trading-agent/...` incorporati) via `git worktree prune`. Resta solo il checkout principale.

**Branch: da 22 locali → 5.** Eliminati 17 branch locali, contenuto verificato preservato altrove:
- Subsumed da `research/edge-discovery` (0 dietro main): `feat/activate-min-grade`,
  `feat/enable-setup-flags-disable-b`, `fix/confluence-repair-regime-spread`.
- Già in `main`: `fix/setup-b-remove-counter-trend-gate`, `feature/python-pure-strategy`,
  `feature/update-pythono-pure-strategy`, `claude/loving-thompson-867af8`,
  `docs/validation-phases-14-15` (doc già in main), `claude/dreamy/gracious` (mappe già in main).
- 5 `worktree-agent-*` (leftover scaffolding GSD).
- `hotfix/v1.1.1-broker-filling` (identico al tag `v1.1.1`), `claude/youthful-cohen` (skill).

**Branch PRESERVATI (5 locali):** `research/edge-discovery` (tip), `main`, e i 3 esperimenti con codice
unico — `feature/strategy-v3-intermarket`, `feature/strategy-v2-defendi`, `feature/ml-feedback-loop`
(tutti anche su `origin`).

**Memoria corretta:**
- `CLAUDE.md`: struttura repo aggiornata a package v2, sezione "Stato progetto" riscritta (branch reale,
  fasi 1–6 implementate, 7–11 sospese, no-edge), stack corretto (devcontainer Linux, scheduler interno).
- Auto-memory: nuovo `project-state-2026-05-30.md` + indice — segnala a sessioni future di NON fidarsi
  del claim "nessun codice prodotto".

**Raccomandazioni NON eseguite (outward-facing, lasciate all'utente):**
- Promuovere/mergiare `research/edge-discovery` → `main` per togliere lo stato "main stale".
- Eliminare i branch remoti corrispondenti su `origin` (`git push origin --delete <branch>`): i 17
  branch morti esistono ancora su `origin`. I 3 esperimenti vanno **prima archiviati come tag**
  (`git tag archive/strategy-v3-intermarket origin/feature/strategy-v3-intermarket`) se si vuole
  ridurre la lista remota senza perdere il codice.
- Consolidare i doc ridondanti ancora presenti (root `STATE.md` vs `.planning/STATE.md`, `PHASES.md`
  obsoleto, 3 `STRATEGY-REBUILD-PLAYBOOK` v1/v2/v3, 5 `.env.example*`) — lasciati intatti perché
  contengono narrativa storica; vanno riorganizzati, non cancellati alla cieca.

---
*Report generato verificando il codice, rieseguendo i test e ispezionando ogni branch/tag il 2026-05-30.
Le conclusioni sul "nessun edge" sono confermate dai numeri; le affermazioni di `CLAUDE.md` sullo stato
del codice e sul branch corrente sono risultate stale e sono state corrette (vedi §11).*
