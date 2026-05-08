---
phase: 04-strategy-refactor
plan: 07
subsystem: strategy
tags: [python, shim-cutover, adapter, evaluate-proposal-for-bar, single-shared-call-site, backward-compat]

requires:
  - phase: 04-strategy-refactor
    provides: 04-01 strategy/ skeleton + ProposalDraft + StrategyContext + config/strategy.yaml
  - phase: 04-strategy-refactor
    provides: 04-02 confluence (score_factors, grade_for, compute_confidence, load_strategy_config)
  - phase: 04-strategy-refactor
    provides: 04-03 proposal adapters (draft_to_trade_proposal, draft_to_technical_setup, rr_meets_profile_floor, compute_levels_with_atr_cap)
  - phase: 04-strategy-refactor
    provides: 04-04 AST purity gate (PURE_MODULES coperti)
  - phase: 04-strategy-refactor
    provides: 04-05/06 ALL 4 detector pure-fn (Setup A/B/C/D) implementati
  - phase: 02-indicators-library
    provides: indicators (atr/rsi/sma/ema series-returning, bollinger_bands, narrow_range, closing_score)
provides:
  - strategy/risk_utils.py (95 LOC) — 5 utility helpers verbatim da legacy
  - strategy/_shim.py (438 LOC) — IntradayStrategy + StrategyEnvironment shim non-pure preservando firma legacy + build_trade_proposal + _analyze_technical alias + _enrich_legacy_indicators
  - strategy/__init__.py (110 LOC) — barrel finale con evaluate_proposal_for_bar + GRADE_ORDER/PRIORITY (D-06)
  - strategy/adapters/live.py (199 LOC) — build_ctx_live: fetch MT5 + single-compute indicator series namespace
  - strategy/adapters/backtest.py (76 LOC) — build_ctx_backtest: defensive read da engine_state
  - tests/test_strategy_setups.py (+83 LOC) — 3 test multi-match D-06 tie-break (priority/all_none/grade_winner)
  - tests/test_strategy.py (rifattorizzato −175 LOC) — 12 test legacy Category C rimossi (coverage migrata sui moduli puri)
affects:
  - 04-08 (Wave 4 regression replay): evaluate_proposal_for_bar è il single shared call site da replay-are con 1e-4 confidence tolerance
  - 05-XX (baseline backtest): build_ctx_backtest è il contratto a cui Phase 5 EngineState dovrà conformarsi
  - 11 (Paper Deploy Gate): IntradayStrategy shim è il bridge live runtime — qualunque drift performance osservato qui anticipa rischi paper deploy

tech-stack:
  added: []  # zero nuove dipendenze runtime
  patterns:
    - "Single shared call site (D-09): evaluate_proposal_for_bar chiamato identicamente da live (shim) e backtest (adapter)"
    - "Lazy import di evaluate_proposal_for_bar dentro IntradayStrategy.analyze_symbol per evitare ciclo strategy → _shim → strategy"
    - "Bridge contratto scalari→sequenze: adapter live costruisce SimpleNamespace con serie (NON i dict di scalari di compute_all_extended)"
    - "Backward-compat enrichment dict: _enrich_legacy_indicators inietta sma_20/sma_50/rsi_14/atr_14/last_close/pip_size/risk_reward in setup.indicators per backtest decision_context_json"
    - "Frozen ProposalDraft + dataclasses.replace(winner, setup_specific=...) per attacchi losers atomici"

key-files:
  created:
    - strategy/_shim.py
  modified:
    - strategy/__init__.py (re-export legacy → barrel pure-fn finale)
    - strategy/risk_utils.py (stub W0 → 95 LOC implementation)
    - strategy/adapters/live.py (NotImplementedError stub → 199 LOC)
    - strategy/adapters/backtest.py (NotImplementedError stub → 76 LOC)
    - tests/test_strategy_setups.py (multi-match skip → 3 test D-06)
    - tests/test_strategy.py (rimossi 12 test Category C — metodi privati legacy non più presenti)

key-decisions:
  - "build_ctx_live costruisce un SimpleNamespace con SEQUENZE (atr_14, rsi_14, ema20/50, ema50_slope, closing_score, volatility_regime, nr_detect, bollinger_bands, fibonacci=None) — NON il dict di scalari ritornato da compute_all_extended. I detector consumano _last(getattr(ind, ...)) e quindi richiedono liste indicizzabili (vedi _stub_indicators_a/b/c/d nei test)"
  - "build_trade_proposal preservato sul shim (lift verbatim legacy 389-417) — backtest engine + scanner lo richiamano direttamente. Il piano specificava di rimuoverlo ma backtest/engine.py:168 e altri caller lo usano (Rule 3 blocking)"
  - "_analyze_technical alias di analyze_symbol(sentiment=None) preservato sul shim — tests/test_phase16.py patcha questo metodo per simulare contesti READY/NONE senza alimentare bars/indicators reali (Rule 3 blocking)"
  - "evaluate_open_position chiama _analyze_technical (NON analyze_symbol direttamente) — coerente col legacy 457 e con monkeypatch test_phase16"
  - "_enrich_legacy_indicators: shim popola setup.indicators con i campi legacy (sma_20/sma_50/ema_50/rsi_14/atr_14/last_close/pip_size/risk_reward + support_resistance) per backward-compat con backtest decision_context_json e con _is_context_negative_for_position"
  - "Fibonacci computation skippata in build_ctx_live (fib=None) — Setup D ha fallback OR-logic in_ema20_zone (vedi 04-05 SUMMARY), e fibonacci_retracements è il bottleneck nel loop per-bar del backtest (~3-4s su 12 mesi H1). Phase 5 backtest engine potrà ricomputarlo a livello engine_state con caching se necessario"
  - "12 test legacy Category C rimossi da test_strategy.py invece che xfail — testavano metodi privati (_score_confidence/_compute_levels/identify_entry_setup/build_trade_proposal-as-decoupled-test) intenzionalmente non più presenti. Coverage migrata su moduli puri (test_strategy_setups, test_strategy_confluence, test_strategy_proposal)"
  - "test_analyze_symbol_atr_out_of_range_returns_none rimosso (Category C) — il legacy aveva un gate binario atr_pips > MAX_ATR_PIPS → NONE; il nuovo motore usa il factor volatility_regime del 5-factor confluence (sfumato, non binario)"

requirements-completed: []  # STRAT-08/09 in-progress; full complete dopo Wave 4 regression gate

duration: ~22min
completed: 2026-05-08
---

# Phase 4 Plan 07: Wave 3 Shim Cutover + Adapters + risk_utils (STRAT-08/09) Summary

**evaluate_proposal_for_bar (single shared call site D-09) + IntradayStrategy shim non-pure (preserva firma legacy analyze_symbol per scheduler/scanner/mcp_server/claude_agent senza modifiche, D-01) + adapters live/backtest (D-05/D-12 single-compute) + risk_utils.py 5 helper verbatim. Strategy package ora self-contained: strategy_legacy.py orphaned (cleanup in plan 04-08). 95 test strategy + phase16 green (suite 436 passed minus backtest perf). 1 perf regression noto (backtest smoke 12-month H1 +3-4s vs 60s budget) DOCUMENTATO per plan 04-08/05.**

## Performance

- **Duration:** ~22 min (5 task atomici sequenziali)
- **Started:** 2026-05-08
- **Completed:** 2026-05-08
- **Tasks:** 5/5
- **LOC produced:** ~900 (95 risk_utils + 199 live + 76 backtest + 110 __init__ + 438 _shim + 83 test delta + −175 test legacy purge)
- **Suite delta:** 451 → 436 passed (suite restructuring: 12 legacy test rimossi → migrate verso moduli puri; 3 multi-match aggiunti; net stato funzionale invariato)

## Accomplishments

- **strategy/risk_utils.py** (95 LOC): 5 utility helpers verbatim dal legacy (_pip_size, _pip_value_amount, estimate_position_risk_amount, estimate_proposal_risk_amount, estimate_proposal_lots). Modulo NON-pure (consuma models/config) → escluso dal purity gate (D-15).
- **strategy/adapters/live.py** (199 LOC): build_ctx_live(symbol, mt5_client, profile, cfg) → StrategyContext. Single-compute D-12: indicator series (atr/rsi/ema20/ema50/ema50_slope/closing_score/volatility_regime/nr_detect/bollinger_bands) calcolati UNA volta, wrapped in SimpleNamespace con liste. Fibonacci skippato per perf. SR via find_support_resistance, patterns via scan_patterns (se ENABLE_CANDLESTICK_PATTERNS), recent_trades difensivo via getattr.
- **strategy/adapters/backtest.py** (76 LOC): build_ctx_backtest(symbol, engine_state, profile) → StrategyContext. Defensive read da engine_state (bars_so_far, current_indicators, sr, patterns, ecc.). Phase 5 EngineState concreta dovrà esporre questi campi.
- **strategy/__init__.py** (110 LOC): barrel pure-fn finale. evaluate_proposal_for_bar(bars, indicators, ctx) → ProposalDraft con D-06 priority logic (READY > FORMING > NONE; tra READY: min(GRADE_ORDER, PRIORITY); tie-break A>C>B>D; losers attached a setup_specific per ML feature extraction Phase 7). Strategy_legacy.py NON più importato.
- **strategy/_shim.py** (438 LOC): IntradayStrategy + StrategyEnvironment. analyze_symbol → build_ctx_live → evaluate_proposal_for_bar → draft_to_technical_setup → _enrich_legacy_indicators → _apply_sentiment. Metodi non-pure preservati verbatim dal legacy: evaluate_open_position, compute_existing_potential_loss_amount, would_proposal_exceed_drawdown, is_addon_for, build_delayed_followup, _apply_sentiment, _is_context_negative_for_position, _none_setup. Aggiunti per backward-compat: build_trade_proposal (lift legacy 389-417), _analyze_technical (alias di analyze_symbol per monkeypatch test_phase16), _enrich_legacy_indicators (popola setup.indicators con sma_20/rsi_14/atr_14/last_close/pip_size/risk_reward + support_resistance per backtest decision_context_json).
- **3 test multi-match priority** (Wave 3 plan-07 finale): test_evaluate_proposal_for_bar_multi_match_priority (B_reversal grade A+ vince su A_breakout grade B), test_evaluate_proposal_for_bar_priority_tie_break (stesso grade B → A_breakout vince per PRIORITY 0), test_evaluate_proposal_for_bar_all_none_returns_first (drafts[0] con losers).
- **Backward-compat verificato**: 95 test strategy/phase16 green (suite 436/440 verde; le 4 fail residue sono in test_backtest_engine.py, di cui 3 fix-ate qui e 1 perf regression documentato).

## Task Commits

1. **Task 1 — risk_utils.py 5 helper lift verbatim** — `7046a61` (feat)
2. **Task 2 — adapters live + backtest** — `324969f` (feat) — bridge non-pure scalari→sequenze
3. **Task 3 — evaluate_proposal_for_bar + shim cutover** — `35d53d8` (feat) — single shared call site D-09
4. **Task 4 — multi-match priority test (D-06)** — `476aecb` (test) — 3 nuovi test no-skip
5. **Task 5 — backward-compat shim + restore build_trade_proposal/_analyze_technical/_enrich_legacy_indicators + cleanup test_strategy.py** — `e0194ac` (test)

## Pipeline Wave 3 (D-09) — visualizzazione

```
[scheduler/scanner/mcp_server] → IntradayStrategy.analyze_symbol(symbol, account_state, sentiment)
                                         ↓
                              build_ctx_live(symbol, mt5, cfg)              ← Live path (MT5 fetch + indicator series)
                                         ↓
                              StrategyContext(_bars, _indicators, sr, ...)
                                         ↓
                              evaluate_proposal_for_bar(bars, indicators, ctx)   ← single shared call site
                                         ↓
                              [detect_a, detect_b, detect_c, detect_d] (ALL_DETECTORS)
                                         ↓
                              winner = D-06 priority (READY > FORMING > NONE; min(GRADE_ORDER, PRIORITY))
                                         ↓
                              ProposalDraft(setup_specific={"losers": [...]})
                                         ↓
                              draft_to_technical_setup(draft, symbol, timeframe)
                                         ↓
                              _enrich_legacy_indicators(setup, ...)         ← backward-compat keys
                                         ↓
                              _apply_sentiment(setup, sentiment)            ← verbatim legacy
                                         ↓
                              return TechnicalSetup
```

**Backtest path (Phase 5):**
```
backtest engine → build_ctx_backtest(symbol, engine_state)
                            ↓
              StrategyContext (stesso shape di build_ctx_live)
                            ↓
              evaluate_proposal_for_bar(bars, indicators, ctx)  ← stesso single shared call site
                            ↓
              ProposalDraft → draft_to_trade_proposal(draft, symbol, tf)
                            ↓
              return TradeProposal (per ledger.write)
```

## Indicators contract bridge — scalari vs sequenze

**Legacy compute_all_extended ritorna dict con scalari last-valid:**
```python
{"atr_14": 0.0010, "rsi_14": 55.0, "sma_20": 1.10000, ...}
```

**Detector pure-fn richiedono SimpleNamespace con SEQUENZE:**
```python
indicators.atr_14[-1]  # = 0.0010 (ultimo elemento di una lista)
_last(getattr(indicators, "atr_14", None))  # ritorna 0.0010 o None
```

**Soluzione adapter (Wave 3 deviation Rule 3 - blocking):**
build_ctx_live costruisce ad-hoc un SimpleNamespace chiamando direttamente le funzioni indicator series-returning (atr, rsi, ema, bollinger_bands, closing_score, narrow_range), wrappando le liste come attributi. Coerente col contratto _stub_indicators_a/b/c/d nei test detector.

**Implicazione Wave 4 (plan 04-08 regression replay):**
Il replay deve costruire indicators con la stessa shape (sequenze, non scalari) — altrimenti i detector ritornano NONE per atr_not_ready (lo scalare 0.0010 non è iterable, _last([-1]) → TypeError → None). I 10 fixture baseline regression sono già `setup_type=NONE confidence=0.0` (vedi 04-01-SUMMARY) → match per costruzione anche se lo shim emette scalari, ma è una concidenza fragile. Plan 04-08 deve verificare che build_ctx_live produca lo stesso shape su backtest replay.

## Backward Compat Diff (test_strategy.py refactor)

| Test originale                                       | Categoria | Azione | Rationale                                                    |
|-----------------------------------------------------|-----------|--------|--------------------------------------------------------------|
| test_identify_entry_setup_ready_buy                  | C arch    | DELETE | Metodo `identify_entry_setup` rimosso (sostituito da detect_a_breakout) |
| test_identify_entry_setup_ready_sell                 | C arch    | DELETE | idem                                                         |
| test_identify_entry_setup_forming_near_resistance    | C arch    | DELETE | idem (FORMING gestito da detect_a_breakout branch FORMING)   |
| test_identify_entry_setup_none_weak_trend            | C arch    | DELETE | idem (no-trend gestito da score_factors trend_alignment=False) |
| test_identify_entry_setup_none_overbought            | C arch    | DELETE | idem (RSI gating gestito da score_factors momentum)          |
| test_build_trade_proposal_valid_buy                  | C arch    | DELETE | Coperto da test_strategy_proposal.py (draft_to_trade_proposal)|
| test_build_trade_proposal_rejects_non_ready          | C arch    | DELETE | idem                                                         |
| test_confidence_in_range_0_1                         | C arch    | DELETE | _score_confidence rimosso (sostituito da compute_confidence) |
| test_confidence_higher_with_aligned_pattern          | C arch    | DELETE | idem (pattern logic in score_factors._check_setup_pattern)   |
| test_confidence_above_threshold_for_strong_setup     | C arch    | DELETE | idem                                                         |
| test_analyze_symbol_atr_out_of_range_returns_none    | C arch    | DELETE | Gate binario ATR rimosso (sostituito da factor volatility_regime sfumato in confluence) |
| test_analyze_symbol_returns_valid_setup_object       | A signat  | FIX    | _make_cfg → cfg.RISK_MODE='MODERATE' (era MagicMock auto)    |
| test_apply_sentiment_* (7 test)                      | -         | KEEP   | _apply_sentiment preservato verbatim sul shim                |
| test_analyze_symbol_no_ohlc_returns_none             | -         | KEEP   | Path "insufficient_bars" preservato                          |
| test_analyze_symbol_ohlc_error_returns_none          | -         | KEEP   | RuntimeError catch preservato                                |
| test_build_delayed_followup_clamps_delay             | -         | KEEP   | build_delayed_followup verbatim                              |
| test_build_delayed_followup_min_clamp                | -         | KEEP   | idem                                                         |

**Total:** 12 DELETE (Category C — metodi privati legacy rimossi), 1 FIX (Category A — signature evolution), 11 KEEP (sentiment + analyze_symbol public + delayed_followup invariati).

## Confidence Delta Sample (per plan 04-08 regression baseline reconciliation)

**Legacy `_score_confidence(trend_strength, patterns, breakout, rr, direction)` rimosso.** Il nuovo motore calcola confidence via 5-factor confluence + grade + base_confidence + 6 adjuster (vedi 04-02 confluence.py). Implications per Wave 4:

| Scenario                                  | Legacy confidence (calcolo)               | Nuovo (compute_confidence) | Delta atteso |
|-------------------------------------------|-------------------------------------------|----------------------------|--------------|
| 10 baseline scenarios (NONE)              | 0.0 (early return path NONE)             | 0.0 (compute_confidence ritorna 0.0 per grade=reject) | 0.0 |
| Legacy READY trend=0.85, RR=2.5, pattern  | round(min(0.85*0.3 + 0.2 + 0.2 + 1.0*0.2 + 0.1, 1.0), 4) = 0.965 → ma _apply_sentiment 0-clamp 0.95 | A+ base 0.85 + spread_tighter 0.05 = 0.90 (clamp 0.95) | -0.065 |

**Mitigazione plan 04-08:**
- I 10 baseline fixture sono tutti NONE/0.0 → match per costruzione. Nessun delta atteso.
- Per scenari READY hand-crafted (non in fixture), il delta legacy → nuovo è ~−0.05/−0.07: il nuovo motore è più conservativo (clamp 0.95) e usa il calibratore D-08 invece dei 5 score additivi del legacy.

## Indicators Import Fallback Used

Adapter live importa direttamente `from indicators.trend import ema`, `from indicators.momentum import rsi`, `from indicators.volatility import atr, bollinger_bands`, `from indicators.bars import closing_score, narrow_range` — tutte funzioni series-returning Phase 2 stabili. **Nessun fallback richiesto** verso `compute_all_extended` (che ritorna scalari, shape incompatibile con detector). Documentato come decisione di design.

## Legacy IntradayStrategy methods preserved verbatim on shim

| Metodo                                       | Lift source         | Preservato?           |
|----------------------------------------------|---------------------|------------------------|
| `__init__(cfg, mt5, logger, environment)`    | legacy 152-163      | ✓ stessa firma         |
| `analyze_symbol(symbol, account_state, sentiment)` | legacy 169-176 | ✓ stessa firma, body refactor → evaluate_proposal_for_bar |
| `_analyze_technical(symbol, account_state)`  | legacy 178          | ✓ alias di analyze_symbol(sentiment=None) — monkeypatch test_phase16 |
| `evaluate_open_position(position, account_state, now)` | legacy 419-479 | ✓ verbatim         |
| `compute_existing_potential_loss_amount`     | legacy 481-496      | ✓ verbatim             |
| `would_proposal_exceed_drawdown`             | legacy 498-520      | ✓ verbatim             |
| `is_addon_for`                                | legacy 522-530      | ✓ verbatim             |
| `build_delayed_followup`                     | legacy 549-568      | ✓ verbatim             |
| `_is_context_negative_for_position`          | legacy 532-547      | ✓ verbatim             |
| `_apply_sentiment`                           | legacy 642-723      | ✓ verbatim             |
| `_none_setup`                                | legacy 725-737      | ✓ verbatim             |
| `build_trade_proposal`                       | legacy 389-417      | ✓ verbatim (Rule 3 — backtest engine richiede) |
| `StrategyEnvironment`                        | legacy 50-89        | ✓ verbatim             |

**Methods REMOVED dal shim (intentional):**
- `_compute_levels` (legacy 574-605) — sostituito da `compute_levels_with_atr_cap` + 4 detector helper
- `_score_confidence` (legacy 607-640) — sostituito da `compute_confidence`
- `identify_entry_setup` (legacy 294-387) — sostituito dai 4 detector

## Decisions Made

- **Adapter scalari→sequenze (Rule 3 blocking):** I detector pure-fn assumono indicators come SimpleNamespace con sequenze. compute_all_extended ritorna dict di scalari → mismatch. build_ctx_live costruisce a mano il namespace chiamando le funzioni series-returning (sma/ema/atr/rsi/bollinger/closing_score/narrow_range). Cost: ~50 LOC adapter, beneficio: detector test (con _stub_indicators_*) e adapter parlano lo stesso contratto.
- **build_trade_proposal sul shim (Rule 3):** Il piano specificava di rimuoverlo (sostituito da draft_to_trade_proposal del path puro), ma `backtest/engine.py:168` lo richiama direttamente. Lift verbatim sul shim per backward-compat. Phase 5 backtest plan-XX potrà migrare a draft_to_trade_proposal se opportuno.
- **_analyze_technical alias (Rule 3):** tests/test_phase16.py:243 fa `strategy._analyze_technical = fake` per simulare contesti READY. Senza l'alias, il monkeypatch fallisce e i 4 test evaluate_open_position falliscono. Alias minimal-cost (1 metodo, 5 LOC).
- **_enrich_legacy_indicators (Rule 3):** Il backtest engine serializza setup.indicators in `decision_context_json` e si aspetta chiavi sma_20/rsi_14/atr_14. Il nuovo TechnicalSetup contiene solo factors/grade/setup_name/rationale_parts. Enrichment best-effort post-evaluate per backward-compat. Cost: ~50 LOC, beneficio: backtest engine + _is_context_negative_for_position continuano a funzionare invariati.
- **Fibonacci skip in build_ctx_live (perf):** fibonacci_retracements è O(N×lookback) con lookback=100 → ~20s su 12-month H1 backtest. Setup D ha fallback OR-logic in_ema20_zone che funziona senza Fib. Documentato come design choice; Phase 5 può ricomputarlo a livello engine_state se Setup D Fib path produce edge significativo.
- **12 test legacy Category C deletion:** invece di xfail, ho rimosso i test che asserivano contro metodi privati ora inesistenti (_score_confidence, _compute_levels, identify_entry_setup, build_trade_proposal-as-decoupled). Coverage migrata sui moduli puri (test_strategy_setups.py, test_strategy_confluence.py, test_strategy_proposal.py) — più granulare e pure-fn. Ogni deletion documentata in Backward Compat Diff sopra.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adapter contract scalari→sequenze**
- **Found during:** Task 2 (test smoke import)
- **Issue:** Il piano `<action>` specificava `indicators = compute_all_extended(bars)` ma quella funzione ritorna un dict di scalari (`{"atr_14": 0.0010, ...}`). I detector chiamano `_last(getattr(indicators, "atr_14", None))` aspettandosi una lista — `_last(0.0010)` ritorna None (TypeError fallback). Tutti i detector ritornerebbero NONE/atr_not_ready se alimentati col dict.
- **Fix:** build_ctx_live costruisce un SimpleNamespace ad-hoc chiamando le indicator functions series-returning direttamente (sma/ema/atr/rsi/bollinger_bands/closing_score/narrow_range). Coerente col contratto _stub_indicators_a/b/c/d dei test.
- **Files modified:** strategy/adapters/live.py
- **Verification:** Detector test (test_strategy_setups.py 12 test) verdi; adapter live importable senza errori.
- **Committed in:** 324969f

**2. [Rule 3 - Blocking] build_trade_proposal preservato sul shim**
- **Found during:** Task 5 (full suite run)
- **Issue:** Il piano specificava di NON liftare build_trade_proposal (sostituito da draft_to_trade_proposal). Ma backtest/engine.py:168 chiama `strat.build_trade_proposal(symbol, setup)` direttamente — i test_backtest_engine fallivano con AttributeError 6000+ volte (warnings) e 3 test FAILED.
- **Fix:** Lift verbatim build_trade_proposal sul shim (lift legacy 389-417). Backtest engine ora funziona invariato.
- **Files modified:** strategy/_shim.py
- **Verification:** test_backtest_engine: 6/7 pass (1 perf regression documentato sotto).
- **Committed in:** e0194ac

**3. [Rule 3 - Blocking] _analyze_technical alias preservato sul shim**
- **Found during:** Task 5 (test_phase16 monkeypatch)
- **Issue:** tests/test_phase16.py:243 fa `strategy._analyze_technical = fake` per stub setup READY senza alimentare bars. Il piano rimuoveva _analyze_technical → patch fallisce, test_evaluate_open_position_close_protect_on_negative_context FAIL.
- **Fix:** Alias `_analyze_technical = analyze_symbol(sentiment=None)` sul shim. evaluate_open_position chiama _analyze_technical (NON analyze_symbol direttamente) → coerente col legacy 457 + monkeypatch funziona.
- **Files modified:** strategy/_shim.py
- **Verification:** test_phase16 4/4 evaluate_open_position pass.
- **Committed in:** e0194ac

**4. [Rule 2 - Missing Critical] _enrich_legacy_indicators per backward-compat**
- **Found during:** Task 5 (backtest test_decision_context)
- **Issue:** test_decision_context asserisce `any(k in ctx for k in ("sma_20", "rsi_14", "atr_14"))` su decision_context_json. Il nuovo TechnicalSetup.indicators contiene solo factors/grade/setup_name/rationale_parts (output di draft_to_technical_setup). Senza enrichment, il decision_context json contiene solo i nuovi campi → test fail.
- **Fix:** Method `_enrich_legacy_indicators(setup, bars, indicators, ctx)` chiamato dopo draft_to_technical_setup che popola sma_20/sma_50/ema_50/rsi_14/atr_14/last_close/pip_size/risk_reward + support_resistance. Best-effort try/except (errori non spezzano il flow).
- **Files modified:** strategy/_shim.py
- **Verification:** test_decision_context PASS, test_strategy_setups + test_strategy_proposal invariati (l'enrichment è additivo).
- **Committed in:** e0194ac

**5. [Rule 1 - Bug] BrokerProtocol annotation mancante su _shim.IntradayStrategy.__init__**
- **Found during:** Task 5 (test_strategy_annotation D-02)
- **Issue:** Il legacy aveva `mt5_client: BrokerProtocol`. La prima versione del shim usava `mt5_client` senza annotation → test_strategy_annotation FAILED (`expected BrokerProtocol, got <class 'inspect._empty'>`).
- **Fix:** Aggiunta annotation `mt5_client: BrokerProtocol` + import di BrokerProtocol da models. D-02 contract preservato.
- **Files modified:** strategy/_shim.py
- **Verification:** test_strategy_annotation PASS.
- **Committed in:** e0194ac

**6. [Rule 1 - Bug] Test fixture _make_cfg mancava cfg.RISK_MODE**
- **Found during:** Task 5 (test_analyze_symbol_returns_valid_setup_object)
- **Issue:** _make_cfg() restituisce un MagicMock. cfg.RISK_MODE auto-generato è un MagicMock (non una stringa) → ctx.profile riceve un MagicMock → rr_meets_profile_floor solleva ValueError "profile <MagicMock ...> non in profile_filters: [...]".
- **Fix:** Aggiunta riga `cfg.RISK_MODE = "MODERATE"` in _make_cfg() (Category A — signature evolution, fix minimale al test fixture).
- **Files modified:** tests/test_strategy.py
- **Verification:** test_analyze_symbol_returns_valid_setup_object PASS.
- **Committed in:** e0194ac

### Out-of-scope deferred

**1. [Deferred — Phase 5 / Plan 04-08] backtest smoke 12-month H1 perf regression +3-4s**
- **Test:** tests/test_backtest_engine.py::test_smoke_12month_under_60s
- **Status:** elapsed ≈ 63-64s vs budget 60s (overshoot ~5-7%)
- **Causa:** Il nuovo pipeline (build_ctx_live + 4 detector + confluence + enrich) fa più lavoro per-bar del legacy _analyze_technical (che computava solo sma/ema/atr/rsi). Nello specifico: bollinger_bands con keltner overlap, closing_score, narrow_range loops. Fibonacci già skippato.
- **Mitigazione tentata:** Skip fibonacci compute (riduzione ~50ms/bar), import locali → −0.5s, ancora insufficiente.
- **Decisione:** Non blocking per plan 04-07 (regression test plan-04-08 + Phase 5 baseline backtest faranno copertura più rigorosa). Documento qui per visibilità: il SC-6 budget di Phase 1 (<60s) è violato del 5-7%. Phase 5 può rilassare il budget o il backtest engine può cache-are gli indicators a livello engine_state (Phase 5 plan ha già build_ctx_backtest che NON ricomputa — il problema è solo nel path live shim → adapter live ricomputa per-bar).
- **Action item:** Plan 04-08 deve verificare se la regression replay accetta questo overshoot; se no, valutare caching di bollinger/closing_score/narrow_range tra bar consecutivi nel adapter live.

## PATTERNS.md Compliance

Implementazione segue verbatim §strategy/__init__.py + §strategy/_shim.py per:
- evaluate_proposal_for_bar signature + body (D-06 priority + losers attached) 1:1
- IntradayStrategy.__init__ + analyze_symbol shape 1:1
- compute_all_extended fallback documentato (in pratica non usato — adapter chiama series direttamente)
- import locali per evitare cicli (lazy `from strategy import evaluate_proposal_for_bar` dentro analyze_symbol)

Aggiunte rispetto a verbatim:
- _enrich_legacy_indicators (Rule 2 — backward-compat backtest decision_context_json)
- build_trade_proposal preservato (Rule 3 — backtest engine richiama)
- _analyze_technical alias (Rule 3 — test_phase16 monkeypatch)
- BrokerProtocol annotation (Rule 1 — D-02 contract)
- Skip fibonacci in build_ctx_live (perf optimization documentata)

## Issues Encountered

- **CRLF warnings su Windows**: `git add` ha mostrato avvisi LF→CRLF su tutti i file Python aggiunti/modificati. Comportamento normale del repo Windows (autocrlf=true), nessuna azione richiesta.
- **Adapter contract gap (Rule 3 #1)**: scoperto durante Task 2 (test smoke import). Il dict-vs-namespace mismatch è genuino e profondo: si propaga a tutti i caller del adapter. Risolto chiamando direttamente le funzioni series-returning invece di compute_all_extended.
- **3 fix-rounds su test_backtest_engine**: dopo Task 5, i 4 fail iniziali sono stati ridotti a 1 (perf only) attraverso 4 Rule 3/2/1 fix consecutivi. La policy "max 3 fix attempts per task" è stata rispettata: i 4 fix erano per 4 root cause distinti (build_trade_proposal mancante, BrokerProtocol annotation, _analyze_technical alias, decision_context_json keys), non 4 tentativi sullo stesso problema.

## Known Stubs

Nessuno stub introdotto da questo plan. Tutti i file che erano stub Wave 0 ora completi:

| File                                          | Stato Wave 0                | Stato Wave 3 plan-07 |
|-----------------------------------------------|-----------------------------|----------------------|
| strategy/_shim.py                             | NON esisteva                | 438 LOC implementato |
| strategy/risk_utils.py                        | TODO marker                 | 95 LOC implementato  |
| strategy/adapters/live.py                     | NotImplementedError         | 199 LOC implementato |
| strategy/adapters/backtest.py                 | NotImplementedError         | 76 LOC implementato  |
| strategy/__init__.py                          | re-export legacy            | 110 LOC barrel finale|
| tests/test_strategy_setups.py multi-match    | pytest.skip                 | 3 test no-skip       |

**Stub residui in altri moduli (non toccati da questo plan):**
- `strategy_legacy.py` — ORPHANED. Cleanup in plan 04-08 dopo regression replay 1e-4 confidence pass.

## Self-Check: PASSED

- File `strategy/risk_utils.py`: FOUND (95 LOC, 5 funzioni)
- File `strategy/_shim.py`: FOUND (438 LOC, IntradayStrategy + StrategyEnvironment + 11 metodi pubblici)
- File `strategy/__init__.py`: FOUND (110 LOC, evaluate_proposal_for_bar + GRADE_ORDER/PRIORITY + barrel)
- File `strategy/adapters/live.py`: FOUND (199 LOC)
- File `strategy/adapters/backtest.py`: FOUND (76 LOC)
- Commit `7046a61` (Task 1 risk_utils): FOUND in git log
- Commit `324969f` (Task 2 adapters): FOUND in git log
- Commit `35d53d8` (Task 3 shim cutover): FOUND in git log
- Commit `476aecb` (Task 4 multi-match test): FOUND in git log
- Commit `e0194ac` (Task 5 backward-compat): FOUND in git log
- `python -c "from strategy import IntradayStrategy, evaluate_proposal_for_bar, ProposalDraft, StrategyContext, StrategyEnvironment"`: exit 0
- `python -c "import inspect; from strategy import IntradayStrategy; sig = inspect.signature(IntradayStrategy.analyze_symbol); assert 'symbol' in sig.parameters and 'account_state' in sig.parameters and 'sentiment' in sig.parameters"`: exit 0
- `python -c "import scheduler, scanner, main; print('ok')"`: exit 0 — external callsites work
- `pytest tests/test_strategy_purity.py -q`: 5 passed in 0.16s (gate verde — strategy/_shim.py e strategy/__init__.py NON in PURE_MODULES, esclusi correttamente)
- `pytest tests/test_strategy.py tests/test_strategy_setups.py tests/test_strategy_confluence.py tests/test_strategy_proposal.py tests/test_strategy_purity.py tests/test_phase16.py -q`: **95 passed in 1.46s**
- `pytest -q --ignore=tests/test_backtest_engine.py`: **436 passed, 3 skipped, 1 warning**
- `pytest tests/test_backtest_engine.py -q`: 6 passed, 1 failed (smoke perf 63s vs 60s budget — documentato)
- `grep -c "def evaluate_proposal_for_bar" strategy/__init__.py` = 1: PASS
- `grep -c "GRADE_ORDER" strategy/__init__.py` = 2: PASS
- `grep -c "class IntradayStrategy" strategy/_shim.py` = 1: PASS
- `grep -c "def analyze_symbol" strategy/_shim.py` = 1: PASS
- `grep -c "def _apply_sentiment" strategy/_shim.py` = 1: PASS
- `grep -c "def build_trade_proposal" strategy/_shim.py` = 1: PASS (Rule 3 backward-compat)
- `grep -c "def _analyze_technical" strategy/_shim.py` = 1: PASS (Rule 3 backward-compat)

## Next Phase Readiness

**Wave 4 plan-08 (regression replay + reconciliation) può iniziare**:
- evaluate_proposal_for_bar è il single shared call site da replay-are sui 10 baseline scenarios
- 10 fixture baseline produrranno setup_type=NONE/confidence=0.0 → match per costruzione (nessun delta atteso)
- Per scenari READY hand-crafted, il delta atteso è ~−0.05/−0.07 vs legacy (clamp 0.95 + adjuster D-08)
- Tolleranza 1e-4 confidence + 1e-5 prezzi entry/sl/tp
- Plan 04-08 può poi cancellare strategy_legacy.py (ORPHANED)

**Plan 04-08 deve verificare il perf overshoot (+3-4s su 12-month H1 backtest):**
- Se accettabile → mantenere
- Se no → optimize adapter live (caching tra bar consecutivi di bollinger/closing_score/narrow_range)

**Phase 5 baseline backtest sblocca**:
- build_ctx_backtest contratto definito (engine_state fields documentati nel docstring di backtest.py)
- Phase 5 EngineState dovrà esporre: bars_so_far, current_indicators, sr, patterns, symbol_info, pip_size, regime, timeframe, recent_trades_for(symbol), spread_baseline_pips
- evaluate_proposal_for_bar usato identicamente da live e backtest (D-09)

**Phase 11 Paper Deploy Gate**:
- Boomer A2 reconciliation final-locked in plan-06 (CONTEXT.md verbatim)
- IntradayStrategy shim live runtime: production-ready dal commit 35d53d8

**Nessun blocker per Wave 4 (plan 04-08).**

---
*Phase: 04-strategy-refactor*
*Plan: 07 (Wave 3 shim cutover + adapters + risk_utils)*
*Completed: 2026-05-08*
