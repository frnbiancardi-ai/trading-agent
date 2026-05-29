# Audit Strategy System — Report 2026-05-28

> Read-only audit. Nessun fix, nessuna modifica al codice di produzione. Tutte le
> affermazioni "WIRED/DEAD" sono verificate sul codice eseguito, non su docstring.
> Branch: `main` @ `bdaf3ee`. Working tree pulito (solo file untracked: task + zip).

---

## 1. Config wiring map

### `config/strategy.yaml`

| chiave | stato | dove usata (file:linea) | note |
|---|---|---|---|
| `factors.trend_alignment.use_ema50_slope` | **DEAD** | — | `_check_trend_alignment` (confluence.py:97) usa direttamente `indicators.ema50_slope`, non legge mai questo flag |
| `factors.trend_alignment.counter_trend_allowed_grades` | **DEAD** | — | nessun codice lo legge; era per il gate D-07 rimosso il 2026-05-19. Config orfana |
| `factors.setup_pattern.half_formed_rejected` | **DEAD** | — | `_check_setup_pattern` (confluence.py:111) non lo consulta |
| `factors.momentum.rsi_neutral_band: [40,60]` | **DEAD** | — | `_check_momentum` (confluence.py:152) hard-coda `rsi<75`/`rsi>25`, ignora la banda |
| `factors.momentum.divergence_required_for_reversal` | **DEAD** | — | mai letto |
| `factors.volatility_regime.{breakout,reversal,compression,pullback}_required` | **WIRED** (ma input morto) | confluence.py:171-179 | letto via `key_map`. MA l'input `indicators.volatility_regime` è SEMPRE `None` (vedi §2/§3) → il fattore è sempre False in ogni path reale |
| `factors.spread_session.max_spread_atr_ratio: 0.20` | **WIRED** (ma input morto in BT) | confluence.py:199-200 | letto, MA in backtest non c'è bid/ask né `SPREAD_BASELINE_PIPS` → fattore sempre False (vedi §2) |
| `factors.spread_session.optional_session_bonus: 0.05` | **DEAD** | — | mai letto |
| `grade_map` | **READ-ONLY** | confluence.py:53 (caricato) | caricato nel dataclass, ma il grade è calcolato da `_GRADE_FROM_COUNT` hard-coded (confluence.py:232). `grade_map[...]` mai indicizzato |
| `base_confidence` | **WIRED** | confluence.py:259 | `compute_confidence` usa `cfg.base_confidence[grade]` |
| `adjusters.intermarket_confirmation` | **WIRED** (no-op in BT) | confluence.py:267 | richiede `ctx.intermarket_score_fn` → None in backtest |
| `adjusters.recent_winning_trade_same_pair` | **WIRED** (no-op in BT) | confluence.py:275 | `ctx.recent_trades` vuoto in backtest |
| `adjusters.spread_tighter_than_baseline` | **WIRED** (no-op in BT) | confluence.py:290 | richiede bid/ask + baseline → assenti in backtest |
| `adjusters.macro_event_within_60min` | **WIRED** (no-op in BT) | confluence.py:298 | richiede `news_blackout_fn`; in BT `AVOID_MAJOR_NEWS_TIMES=False` → ritorna sempre False |
| `adjusters.last_2_trades_lost_same_pair` | **WIRED** (no-op in BT) | confluence.py:307 | `recent_trades` vuoto in backtest |
| `adjusters.proposing_against_medium_term_trend` | **WIRED** | confluence.py:310 | unico adjuster realmente attivo in backtest (legge `factors`) |
| `bounds.min_confidence` / `bounds.max_confidence` | **WIRED** | confluence.py:314-315 | clamp finale della confidence. NB: è il clamp dei bound, NON il filtro `profile_filters.min_confidence` |
| `profile_filters.{P}.min_rr` | **WIRED** | proposal.py:159 (`rr_meets_profile_floor`), chiamato da a_breakout.py:166, b_reversal.py:242, c_compression.py:274, d_pullback.py:243 | unico filtro di profilo realmente applicato |
| `profile_filters.{P}.min_grade` | **DEAD** | — | nessun codice non-test lo legge. Appare solo in un commento (engine.py:143) e nei YAML di test. Mai applicato in nessun gate |
| `profile_filters.{P}.min_confidence` | **DEAD** | — | nessun codice lo legge. Da non confondere con `bounds.min_confidence` (chiave diversa, quella è wired) |

**Nota trasversale**: anche la `confidence` calcolata da `compute_confidence` (e quindi
tutti gli adjusters) **non filtra alcun trade**: `risk_engine.evaluate_trade` non
consulta né `confidence` né `grade` (risk_engine.py usa solo `RISK_MODE` per
`max_lots`/`max_drawdown`). La confidence è quindi un valore registrato ma non
decisionale nel path backtest.

### `config/patterns.yaml`
| chiave | stato | dove usata | note |
|---|---|---|---|
| tutte (geometry+calibration per 10 pattern) | **WIRED** | `patterns.py:118` (`DEFAULT_CONFIG_PATH`), consumate da `scan_patterns` | alimentano solo Setup B (`ctx.patterns`). In live/backtest `scan_patterns` è chiamato solo se `ENABLE_CANDLESTICK_PATTERNS` (default True) |

### `data/configs/costs.yaml`
| chiave | stato | dove usata | note |
|---|---|---|---|
| `{symbol}.{spread,slippage,commission}_pips` | **WIRED** | `backtest/costs.py:42 load_cost_model` | usate da BacktestBroker per P&L |

### `data/configs/regime.yaml`
| chiave | stato | dove usata | note |
|---|---|---|---|
| `default.*`, `symbols.*` | **WIRED ma non-decisionale** | `indicators/volatility.py:249 load_regime_config` ← `slice_worker.py:362` | consumata SOLO da `_extract_extended_snapshot_at_entry` (snapshot ML post-hoc). NON influenza alcuna decisione di trade: il `compute_all_extended` top-level (slice_worker:348) è chiamato SENZA `regime_cfg`, e il detector path (`build_ctx_live`) forza regime=None |

### `data/configs/baseline.yaml`
| chiave | stato | dove usata | note |
|---|---|---|---|
| `equity_initial_eur`, `timeout_bars`, `warm_up_min_bars`, `max_workers`, `date_start/end`, `*_dir`, `dataset_schema_version`, `slippage_seed`, `force_rerun` | **WIRED** | `backtest/baseline/runner.py:62 load_baseline_config` + slice_worker | knob di orchestrazione, tutti consumati |
| `parquet_compression`, `progress_bar` | READ-ONLY/parz. | runner | non verificati come decisionali, sono cosmetici/output |

---

## 2. Evaluation flow (bar → trade)

### Catena reale di chiamate (path backtest baseline)

```
scripts/run_baseline_backtest.py
  └─ backtest/baseline/runner.py  (load_baseline_config, ProcessPool)
       └─ slice_worker.run_slice_3profiles(symbol, tf, ...)
            ├─ load_bars → warm_up slice → compute_all_extended(bars_dict)  [indicators_full]  ← NON usato per detection
            └─ per profile in (CONSERVATIVE, MODERATE, AGGRESSIVE):
                 BacktestEngine(bars, ..., indicators_full=…, risk_profile=profile).run()
                   └─ per bar:
                        broker.advance(bar)                          # chiude SL/TP/timeout
                        strat = IntradayStrategy(cfg, broker)        # broker = "finto MT5"
                        setup = strat.analyze_symbol(symbol, acct)   # strategy/_shim.py:111
                          └─ build_ctx_live(symbol, mt5_client=broker, …)   # adapters/live.py:109
                               ├─ broker.get_ohlc(...) → window bars
                               ├─ _build_extended_indicators(bars)   # RICALCOLA indicatori ogni bar
                               ├─ find_support_resistance(bars)      # popola ctx.sr
                               └─ scan_patterns(bars)                # popola ctx.patterns (se ENABLE_…)
                          └─ evaluate_proposal_for_bar(bars, indicators, ctx)  # strategy/__init__.py:61
                               └─ [detect_a, detect_b, detect_c, detect_d] → winner (D-06)
                          └─ draft_to_technical_setup(draft)
                        if setup.READY:
                          proposal = strat.build_trade_proposal(...)
                          decision = risk_engine.evaluate_trade(...)  # NON guarda grade/confidence
                          if decision.approved: broker.send_order(... entry=bar.close)
```

### Punti dove un segnale può essere scartato silenziosamente (file:linea)
1. **Warm-up**: `engine.py:206` `if idx+1 < lookback: continue` (lookback ≥ 50, +`warm_up` slice in slice_worker:323).
2. **Detector guard**: `insufficient_bars`/`atr_not_ready`/`ema_not_ready`/`last_close_missing` in tutti i detector.
3. **Reject confluence** (`grade=='reject'`, ≤1 fattore True) → NONE. a_breakout:151, b_reversal:214, c_compression:253, d_pullback:205.
4. **Gate R:R** (`rr_meets_profile_floor`) → NONE `rr_below_profile_min_*`. (Unico filtro di profilo attivo.)
5. **`setup.setup_type != "READY"`** → engine.py:217 `continue`.
6. **risk_engine.evaluate_trade** `not approved` → engine.py:234 `continue` (kill-switch DD, margin, max_lots, sizing).
7. **Eccezioni inghiottite**: `analyze_symbol`/`build_trade_proposal`/`evaluate_trade` in `try/except … continue` (engine.py:213/223/231) — un'eccezione silenzia il bar con un solo `_log.warning`.
8. **`_apply_sentiment`** (shim:450) può convertire READY→NONE/FORMING — in backtest `ENABLE_NEWS_SENTIMENT` non è attivo, quindi no-op, ma è un punto di scarto nel path live.

### Dove `min_grade`/`min_confidence`/`min_rr` DOVREBBERO / dove SONO applicati
- **`min_rr`**: applicato DENTRO ogni detector (prima di emettere READY). ✓ presente.
- **`min_grade`**: NON applicato in NESSUN punto della catena. Tracciato il flow per
  conferma: il `grade` viene calcolato (confluence:235), messo nel draft, mappato in
  `TechnicalSetup.indicators["grade"]` (proposal.py:122), e poi **mai consultato** da
  engine, risk_engine, o shim. **DEAD confermato per tracciamento, non solo per grep.**
- **`min_confidence` (profilo)**: NON applicato. La `confidence` non è gate da nessuna
  parte nel path backtest. (Nel path live esiste solo `MIN_CONFIDENCE_TO_PROPOSE` usato
  esclusivamente nel ramo `reduce_confidence` di `_apply_sentiment`, shim:524.)

---

## 3. Live vs backtest adapter parity

**Scoperta principale**: i due adapter NON sono entrambi in uso. Il path backtest reale
(`BacktestEngine`) **non chiama `build_ctx_backtest`** — chiama `strat.analyze_symbol`,
che internamente usa **`build_ctx_live`** passando il `BacktestBroker` come finto
`mt5_client`. `build_ctx_backtest` è **codice morto** nell'esecuzione: gli unici
riferimenti sono `strategy/adapters/__init__.py` (export), `scripts/preflight_phase5.py`
(import-check), e `_tmp_write_05.py` (bozza di planning). Era progettato per la feature
`replay_decision` (MCP-15), che è tuttora **xfail/MISSING** (vedi §5/§7).

Quindi live e backtest condividono LO STESSO codice (`build_ctx_live`); la "parità" non è
il problema — il problema è cosa `build_ctx_live` popola.

| campo/funzione | live (`build_ctx_live`) | backtest (`build_ctx_live` + BacktestBroker) | impatto |
|---|---|---|---|
| `sr` | `find_support_resistance(bars)` | idem (broker fornisce window) | parità |
| `patterns` | `scan_patterns` se `ENABLE_CANDLESTICK_PATTERNS` | idem (cfg default True) | parità |
| indicatori | `_build_extended_indicators` (serie) ricalcolate per bar | idem | parità |
| `volatility_regime` | **`[None]*len(bars)`** (live.py:85-86) | **`[None]*…`** | **fattore 4 SEMPRE False in entrambi → grade A+ irraggiungibile ovunque** |
| `fibonacci` | **`None`** (live.py:83) | `None` | Setup D perde la fib-zone; resta solo `in_ema20_zone` |
| `symbol_info.bid/ask` | reali da MT5 | **assenti** (BacktestBroker.get_symbol_info non espone bid/ask, broker.py:115) | spread_session calcolabile in live, **mai in backtest** |
| `spread_baseline_pips` | `cfg.SPREAD_BASELINE_PIPS` → **assente in config.py** quindi None | None | adjuster spread + fattore 5 morti in entrambi (in live solo se bid/ask presenti il fattore 5 funziona) |
| `recent_trades` | `mt5_client.get_trade_history` se presente | BacktestBroker **non ha** `get_trade_history` → `[]` | 2 adjusters morti in backtest |
| `intermarket_score_fn` / `news_blackout_fn` | passabili | None / news disabilitata | 2 adjusters morti in backtest |
| `indicators_full` (precompute) | n/a | passato a `BacktestEngine` ma **mai consumato in `run()`** (engine.py:136 store, zero read) | calcolo costoso sprecato per la detection; usato solo nello snapshot ML post-hoc |

**Conseguenza quantitativa**:
- **In backtest** i fattori 4 (volatility_regime) e 5 (spread_session) sono SEMPRE False
  → **grade massimo = B** (solo trend_alignment + setup_pattern + momentum possono essere
  True). A e A+ sono strutturalmente irraggiungibili in backtest.
- **In live** il fattore 4 è comunque sempre False (regime hard-coded None) → **grade
  massimo = A** (A+ irraggiungibile ovunque).

---

## 4. Detector audit

`ALL_DETECTORS` (`strategy/setups/__init__.py:7`) è **hard-coded** = `[detect_a_breakout,
detect_b_reversal, detect_c_compression, detect_d_pullback]`. **Nessun** meccanismo
enable/disable: nessun `ENABLE_SETUP`, feature flag o filtro della lista trovato in tutto
il repo. `evaluate_proposal_for_bar` esegue sempre tutti e 4 e seleziona il winner per
priorità D-06 (READY>FORMING>NONE, poi `(GRADE_ORDER, PRIORITY)`).

| detector | campi/indicatori consumati | gate (in ordine) | grade max raggiungibile | rischio strutturale |
|---|---|---|---|---|
| **A_breakout** | `ctx.sr.{resistance,support}`, `atr_14`, `closing_score`, `ema50_slope`, `rsi_14`, (regime, spread) | bars→atr→close→FORMING(±5pip)→direzione breakout→reject→R:R | **A** live / **B** backtest | trend_alignment True solo se il breakout concorda con lo slope; closing_score>75/<25 richiesto per setup_pattern (banda stretta) |
| **B_reversal** | `ctx.sr`, `ctx.patterns` (attribute access), `atr_14`, `ema50_slope`, `rsi_14` | bars→atr→close→zona S/R(±8pip)→PatternHit(-3..-1) else FORMING→reject→R:R | **A** live / **B** backtest | counter-trend per design → `trend_alignment` quasi sempre False (perde 1 fattore in partenza). Dipende da `ctx.patterns` (vuoto se `ENABLE_CANDLESTICK_PATTERNS=False`) |
| **C_compression** | `nr_detect.{nr4,nr7}`, `bollinger_bands.squeeze`, `ema50_slope`, `atr_14`, `rsi_14` | bars→atr→compressed?→count≥3 (==2 FORMING)→range>0→slope≠0→reject→R:R | **A** live / **B** backtest | direction = sign(slope) → `trend_alignment` SEMPRE True; ma `volatility_regime` richiede regime=="compressed" che è sempre None → fattore 4 perso comunque |
| **D_pullback** | `ema20`, `ema50`, `ema50_slope`, `atr_14`, `fibonacci` (None), `closing_score`, `rsi_14` | bars→atr→ema→slope≥thr→lato EMA50→zona(ema20 OR fib)→reject→R:R | **A** live / **B** backtest | `fibonacci=None` → solo `in_ema20_zone`. direction = sign(slope) → trend_alignment sempre True |

**Controllo trasversale grade A/A+**:
- **A+ (5 fattori) è irraggiungibile da OGNI detector in OGNI path** perché
  `volatility_regime` è hard-coded None in `build_ctx_live` (§3).
- **A (4 fattori) è irraggiungibile in BACKTEST** per ogni detector, perché anche
  `spread_session` è sempre False (no bid/ask + no `SPREAD_BASELINE_PIPS`). Ceiling
  backtest = B.
- Conseguenza combinata con un eventuale `min_grade` (che però oggi è DEAD): se in futuro
  si attivasse `min_grade=A` (CONSERVATIVE), **tutti** i trade backtest verrebbero
  silenziosamente azzerati. Oggi non accade solo perché `min_grade` non è wired.

---

## 5. Test coverage

Suite completa (escludendo 6 moduli con import rotti per dipendenze mancanti —
`apscheduler`, `anthropic` — non legati alla strategia):
**443 passed / 2 failed / 13 skipped / 8 xfailed** (~7m18s).

Failure 1: `test_backtest_engine.py::test_smoke_12month_under_60s` — AssertionError di
**performance** (engine O(N²), 12 mesi non sotto i 60s; coerente coi commenti in
baseline.yaml). Non un bug di correttezza.
Failure 2: `test_mcp_legacy_compat.py::test_legacy_entrypoint_imports` — `ModuleNotFound`
(env, `anthropic`/`apscheduler` assenti).

Test mirati strategia+leakage isolati: **96 passed / 1 failed** (solo lo smoke 12-mesi) e
**79 passed / 0 skip** sui file confluence/setups/proposal/leakage/regression.

| area | coperta da test? | quale test | gap |
|---|---|---|---|
| `min_rr` per profilo | **Sì** | `test_strategy_proposal.py:129-187` (3 profili + SELL + invalid) | — |
| `min_grade` filtra i trade | **NO** | — | nessun test verifica che min_grade filtri. **Ecco perché il fatto che sia DEAD è passato inosservato** |
| `min_confidence` (profilo) applicato | **NO** | — | nessun test |
| grade ceiling reale via adapter | **NO** | `test_strategy_setups.py` usa **stub** che popolano `volatility_regime`/`bid/ask` (linee 156-171, 200-215, 229-242) | i detector sono testati con indicatori pieni; nessun test usa `build_ctx_live` reale → il fatto che regime/spread siano sempre None non è mai colto. Asserzioni grade sono deboli: `in ("A+","A","B","C")` (setups:262,313) |
| adapter parity live/backtest | **NO** (parz.) | — | nessun test confronta i due adapter; `build_ctx_backtest` non ha test funzionali sul flow |
| `build_ctx_backtest` realmente in uso | **NO** | preflight import-check only | feature `replay_decision` xfail |
| flow END-TO-END (bar→trade) | **Sì** (parz.) | `test_backtest_engine.py`, `test_baseline_runner.py` | ma con CSV reali spesso skipped (`pytest.skip("CSV non disponibile")`) |
| no future leakage | **Sì** | `test_baseline_no_future_leakage.py`, `test_baseline_no_leakage_extended.py` (passano) | verificano l'invariante causale di `compute_all_extended` (prefix==full[i]); **NON** verificano direttamente i 4 detector (che però usano solo `[-1]`, vedi §6) |
| crowding/sizing | **Sì** (parz.) | `test_backtest_engine.py`, risk tests | sizing in risk_engine; nessun test di martingala (vedi §6) |
| confidence non-gate | **NO** | — | nessun test documenta che confidence non filtri |

**Skip/xfail rilevanti**: gli 8 xfail sono tutti feature non implementate dichiarate:
`test_mcp_handlers_ml.py` (3 xfail Phase 8 ML), `test_mcp_handlers_backtest.py` (3 xfail
**MCP-15 replay_decision** — la feature che userebbe `build_ctx_backtest`),
`test_mcp_handlers_market.py` (MCP-09/11/12), `test_mcp_legacy_compat.py` (Wave 4). Gli
skip sono per CSV storici mancanti o dev-dep assenti (`pandas-ta`, `mottl`, `PIL`). **Uno
skip/xfail = una feature non implementata**: replay_decision è la più rilevante per questo
audit perché spiega l'esistenza dell'adapter backtest morto.

---

## 6. Bug trovati

| sev | file:linea | cosa fa | cosa dovrebbe | impatto | test? |
|---|---|---|---|---|---|
| **CRITICAL** | confluence.py (gate `min_grade`) — assente | `profile_filters.min_grade` definito in strategy.yaml ma mai applicato | filtrare i READY per grade di profilo | il profilo CONSERVATIVE/MODERATE non filtra per qualità; ogni grade ≥C passa il gate-grade | **NO** |
| **CRITICAL** | live.py:85-86 | `volatility_regime = [None]*len(bars)` hard-coded | passare un regime calcolato (regime.yaml esiste) | fattore 4 sempre False → **A+ irraggiungibile ovunque**, A irraggiungibile in BT; distorce grade/confidence di tutti i setup | **NO** (stub maschera) |
| **CRITICAL** | live.py:186 + config.py (manca `SPREAD_BASELINE_PIPS`) | spread_baseline None + broker senza bid/ask | fornire spread in backtest | fattore 5 sempre False in BT → **ceiling grade B in backtest** | **NO** |
| **HIGH** | proposal.py min_confidence — assente | `profile_filters.min_confidence` mai applicato | scartare proposte sotto-soglia | confidence non filtra nulla; combinato con risk_engine che ignora confidence, la confidence è puramente cosmetica nel BT | **NO** |
| **HIGH** | engine.py:136 vs 149+ | `self.indicators_full` salvato ma mai letto in `run()` | usare la cache precomputata, o non passarla | la detection ricalcola gli indicatori per ogni bar via `build_ctx_live` (O(N²)) → causa del fail `test_smoke_12month_under_60s`; il precompute è sprecato | parz. (smoke perf fail) |
| **HIGH** | confluence.py: `grade_map` non indicizzato | grade da `_GRADE_FROM_COUNT` hard-coded (232) mentre `grade_map` (strategy.yaml) è caricato e ignorato | usare grade_map o non caricarlo | due fonti di verità per la soglia grade; modificare strategy.yaml `grade_map` non ha effetto (silenzioso) | **NO** |
| **MEDIUM** | adapters/backtest.py (tutto) | `build_ctx_backtest` esiste ma non è nel path eseguito | essere il context builder del backtest (D-05 "single shared context") | il backtest usa `build_ctx_live`+broker finto; l'intento architetturale D-05/D-09 ("single shared call site") **non è realizzato**: il context di backtest è di fatto quello live | import-check only |
| **MEDIUM** | slice_worker.py:114 / 458-493 | snapshot ML su `bars_dict[:idx]` (esclude bar di entry idx) | allinearsi a ciò che il detector ha visto | il detector decide su window che **include** il bar idx (entry=bar.close di idx); lo snapshot feature ML è su `[:idx]` → feature off-by-one rispetto all'input reale del detector. Le feature del dataset Phase 7 non coincidono con quelle decisionali | parz. (no-leakage test non lo copre) |
| **MEDIUM** | confluence.py:295-300 | adjuster `macro_event_within_60min` usa `datetime.now(timezone.utc)` | in un modulo "pure-fn"/replay deve usare il timestamp del bar | impurità: in backtest/replay introduce dipendenza dall'ora reale (no-op oggi perché news disabilitata, ma è un look-ahead/non-determinismo latente) | **NO** |
| **LOW** | context.py:13 (`regime: str`) | campo `ctx.regime` popolato ma **mai letto** da alcun detector (leggono `indicators.volatility_regime`) | rimuovere o usare | campo morto; confonde (sembra il regime ma è ignorato) | **NO** |
| **LOW** | regime.yaml wiring | letta solo per snapshot ML, non per decisioni; `compute_all_extended` top-level chiamato senza `regime_cfg` (slice_worker:348) | — | la soglia regime non influenza mai un trade | **NO** |
| **LOW (noto, FIXATO)** | b_reversal.py:198-211 | counter-trend gate D-07 rimosso il 2026-05-19 (commit e83d2ae) | — | confermato rimosso; `is_counter_trend` ora solo tracciato | `test_strategy_setups.py:317` |

**Bug noti dal task — conferma**:
1. Gate counter-trend D-07 su Setup B → **FIXATO** (commit `e83d2ae`, test verde).
2. `profile_filters.min_grade`/`min_confidence` non wired → **CONFERMATO DEAD** (solo
   `min_rr` wired).

**Sizing/martingala (§6.5 del task)**: il sizing è in `risk_engine`/`risk_utils` basato su
`% rischio per trade` e `max_lots` per profilo; non ho trovato logica che aumenti la size
dopo una perdita (no martingala). Gli adjuster `last_2_trades_lost`/`recent_winning` toccano
solo la confidence (cosmetica), non la size. **Nessun rischio martingala rilevato.**

**Off-by-one / look-ahead nei detector**: i detector leggono solo `bars[-1]`/`indicators[-1]`
(ultimo bar chiuso) e l'engine entra a `bar.close` del bar analizzato dopo `broker.advance`
(con `entry_bar_index` che impedisce l'uscita same-bar). Non ho rilevato uso di dati futuri
nel detector flow. L'unica anomalia temporale è lo snapshot ML off-by-one (sopra, MEDIUM).

---

## 7. Feature deferred/incomplete

- **`drafts_rows` DEFERRED** (slice_worker.py:429, 496): l'engine non cattura le proposte
  FORMING/NONE; il dataset ML Phase 7 di failure-analysis è parziale finché non si aggancia
  un hook in `engine.run()`. Marcato esplicitamente DEFERRED nel codice.
- **`replay_decision` (MCP-15) MISSING/xfail** (test_mcp_handlers_backtest.py:208-219):
  è la feature per cui esistono `build_ctx_backtest` + l'invocazione "pura" di
  `evaluate_proposal_for_bar`. Non implementata → `build_ctx_backtest` resta orfano.
- **ML handlers Phase 8 xfail** (test_mcp_handlers_ml.py:75-107): `predict_trade_quality`,
  `get_ml_calibration`, `train_ml_filter` ancora stub `NotImplementedError`.
- **MCP-09/11/12 xfail** (test_mcp_handlers_market.py:119-139): tool di mercato mancanti.
- Nessun `TODO/FIXME/HACK/XXX` sostanziale in `strategy/`+`backtest/` oltre ai 2 DEFERRED
  di `drafts_rows`.
- Git: `profile_filters` (con min_grade/min_confidence) introdotto in `c545826` (Phase
  04-01) e **mai wired da allora** per min_grade/min_confidence — non è un caso di
  "wired-poi-scollegato", è **mai stato collegato**. Solo `min_rr` è stato wired
  successivamente in STRAT-07 (`rr_meets_profile_floor`).

---

## 8. Sintesi: top 5 problemi per impatto

1. **`volatility_regime` hard-coded a `None` in `build_ctx_live` (live.py:85-86)** —
   azzera 1 fattore su 5 per OGNI setup in OGNI path. A+ è impossibile ovunque; in backtest
   il ceiling crolla a B. Distorce sistematicamente grade e base_confidence di tutti i
   trade, riducendo la qualità apparente dei segnali e alterando ogni statistica del
   baseline.

2. **Fattore `spread_session` sempre False in backtest** (no bid/ask nel broker + `SPREAD_BASELINE_PIPS`
   assente in config.py) — secondo fattore morto in backtest, che fissa il ceiling a grade B.
   Insieme al punto 1, significa che il baseline è generato con un modello di confluence a 3
   fattori effettivi su 5, non quello descritto in strategy.yaml.

3. **`min_grade` e `min_confidence` di profilo completamente DEAD** — l'unico filtro di
   qualità realmente attivo è `min_rr`. La distinzione CONSERVATIVE/MODERATE/AGGRESSIVE si
   riduce a min_rr (2.5/1.8/1.3) e ai limiti di rischio; la selettività per "grado del
   segnale" promessa dal config non esiste. Il baseline non sta filtrando per qualità come
   il design suppone.

4. **Il backtest non usa l'architettura prevista**: `build_ctx_backtest` (single-shared
   context D-05) è morto, `indicators_full` precomputato è ignorato, e la detection passa
   per `build_ctx_live` ricalcolando gli indicatori bar-per-bar. Oltre al costo O(N²) (smoke
   perf fail), significa che il "contesto di backtest" è di fatto il contesto live con un
   broker finto — con tutte le sue limitazioni (regime None, no recent_trades, no spread).

5. **La `confidence` non filtra nulla** (risk_engine ignora confidence/grade; min_confidence
   dead): tutti gli adjusters e la calibrazione confidence sono lavoro a vuoto nel path
   backtest. Qualunque ipotesi che il baseline scarti i segnali a bassa confidence è falsa.

> I punti 1-3 insieme spiegano in modo plausibile un baseline a bassa/negativa expectancy:
> il sistema gira con meno fattori di confluence del previsto e senza i filtri di qualità
> per profilo, quindi prende trade C/B indiscriminatamente con l'unico vincolo R:R.

---

## 9. Anomalie / cose che non tornano

- **Doppia fonte di verità per il grade**: `grade_map` in strategy.yaml vs
  `_GRADE_FROM_COUNT` hard-coded in confluence.py. Coincidono oggi, ma modificare il YAML
  non ha effetto.
- **CLAUDE.md descrive un repo diverso** da quello reale: parla di Windows/`C:\trading-agent`,
  branch `feature/update-pythono-pure-strategy`, "tutte le fasi in PLANNING, nessun codice
  prodotto". In realtà siamo su `main`, con strategy/backtest pienamente implementati. La
  project-memory è disallineata dallo stato del codice.
- **`indicators_full` calcolato senza `regime_cfg`** (slice_worker:348) ma `regime_cfg`
  viene caricato (slice_worker:362) e usato solo nello snapshot post-entry → il
  `regime_state` nell'`indicators_full` è sempre None, mentre quello nello snapshot ML è
  popolato. Due "regime" con semantica diversa nello stesso worker.
- **Lo snapshot ML usa `bars[:idx]`** mentre il detector ha deciso su una window che
  include il bar `idx` (entry=close di `idx`). Le feature salvate per il training Phase 7
  non sono quelle che il detector ha effettivamente visto (off-by-one, MEDIUM in §6).
- **`build_trade_proposal` duplicato**: esiste sia in `proposal.py::draft_to_trade_proposal`
  sia in `_shim.py::build_trade_proposal` (engine usa quest'ultimo). Due path di costruzione
  proposta con `comment` diverso ("python_strategy" in entrambi, ma rationale diverso).
- **`_tmp_write_05.py`** (55KB) nella root: bozza di planning Phase 5 con codice
  `build_ctx_backtest`/`replay_decision` — non è codice eseguito ma inquina i grep e la root.

---

## 10. Script di audit creati e cleanup

**Nessuno script temporaneo creato.** L'audit è stato condotto interamente con
`git`, `grep`, lettura file e `pytest` (read-only). Nessun file in `scripts/_audit_*`.

Unico artefatto scritto: **questo report** in
`.planning/research/audit-strategy-system-2026-05-28.md` (documentazione, non codice;
non committato da questo task). Nessuna modifica a detector/config/adapter/test.
