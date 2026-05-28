# Phase 4: Strategy Refactor — Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Source:** /gsd:discuss-phase 4 (interactive, 4 aree, mode=discuss)

<domain>
## Phase Boundary

Refactor del modulo `strategy.py` (monolitico `IntradayStrategy` con broker calls inline e singolo path breakout-trend) in:
- 4 setup detector pure-function A/B/C/D (Breakout, S/R Reversal, Compression Breakout, Trend Pullback)
- 5-factor confluence scorer + grade A+/A/B/C/reject + confidence calibrator
- ATR-based R:R proposal builder per-setup
- Single code path eseguito identico da live scheduler e backtest engine (no fork)

**In scope:** STRAT-01..STRAT-09 (9 requirements), backward-compat shim su `IntradayStrategy` per scheduler/MCP/tests, regression fixture pre/post.

**Out of scope (deferred):** ML scoring (Phase 7), intermarket/news adjuster reali (Phase 10), MCP tool refactor (Phase 6/8), multi-TF confluence input (consuma `INDIC-13` solo se disponibile, no fallback).

</domain>

<decisions>
## Implementation Decisions

### D-01 — Module layout: `strategy/` package
- Promote flat `strategy.py` (737 linee) a `strategy/` package, mirror del Phase 2 `indicators/`.
- Submodules:
  - `strategy/setups/a_breakout.py` — Setup A detector + `_compute_levels` per-setup
  - `strategy/setups/b_reversal.py` — Setup B detector + levels (uses `PatternHit`)
  - `strategy/setups/c_compression.py` — Setup C detector + levels (uses NR4/NR7, BB squeeze)
  - `strategy/setups/d_pullback.py` — Setup D detector + levels (uses EMA20/Fib)
  - `strategy/setups/__init__.py` — `ALL_DETECTORS` registry list
  - `strategy/confluence.py` — 5-factor scorer + grade map + confidence calibrator + adjusters
  - `strategy/proposal.py` — `ProposalDraft` dataclass + `draft_to_trade_proposal()` adapter
  - `strategy/context.py` — `StrategyContext` dataclass (vedi D-04)
  - `strategy/adapters/live.py` — `build_ctx_live(symbol, mt5_client, ...)` per scheduler
  - `strategy/adapters/backtest.py` — `build_ctx_backtest(symbol, engine_state, ...)` per Phase 5 engine
  - `strategy/__init__.py` — re-export pubblici (`IntradayStrategy` shim, `evaluate_proposal_for_bar`, `ProposalDraft`, `StrategyContext`)
- Backward-compat: `IntradayStrategy` resta esportata da `strategy/__init__.py`. Internamente `analyze_symbol()` costruisce ctx via `live.build_ctx_live()` + chiama `evaluate_proposal_for_bar()`. Scheduler/MCP/tests non si rompono.

### D-02 — Pure-fn detector signature
```python
def detect_<setup_name>(
    bars: list[dict],
    indicators: ExtendedIndicators,
    ctx: StrategyContext,
) -> ProposalDraft:  # sempre Draft, mai None
    ...
```
- `bars` = list[dict] (chiusi al-or-prima-di now), come Phase 1 D-09.
- `indicators` = snapshot pre-computed dall'adapter (no future leakage by construction).
- `ctx` = `StrategyContext` con tutti i side-input (vedi D-04).
- **Output sempre `ProposalDraft`**, mai None. `setup_type ∈ {READY, FORMING, NONE}` con `reason` motivata. Coerente con `TechnicalSetup` attuale + utile per ML feature extraction Phase 7.

### D-03 — `ProposalDraft` dataclass (nuovo)
```python
@dataclass(frozen=True)
class ProposalDraft:
    setup_type: Literal["READY", "FORMING", "NONE"]
    setup_name: Literal["A_breakout", "B_reversal", "C_compression", "D_pullback"] | None
    direction: Literal["BUY", "SELL"] | None
    entry_price: float | None
    stop_loss_price: float | None
    take_profit_price: float | None
    factors: dict[str, bool]            # 5-factor confluence breakdown
    grade: Literal["A+", "A", "B", "C", "reject"] | None
    confidence: float                    # 0..1, post-adjuster
    reason: str
    rationale_parts: dict[str, str]      # per ML feature extraction + debug
    setup_specific: dict                 # compression_range, pullback_low, breakout_level, ecc.
```
- `draft_to_trade_proposal(draft, symbol, timeframe) -> TradeProposal` in `strategy/proposal.py` per uso live.

### D-04 — `StrategyContext` dataclass — minimal
```python
@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timeframe: str
    profile: RiskProfile               # CONSERVATIVE | MODERATE | AGGRESSIVE
    sr: dict                            # find_support_resistance() output
    regime: str                         # "compressed" | "normal" | "expanded" (INDIC-14)
    patterns: list[PatternHit]          # Phase 3 dataclass
    symbol_info                         # MT5 symbol_info struct (pip_size, digits, tick_value)
    pip_size: float
    # adjuster injection points (D-08)
    intermarket_score_fn: Callable[[str], float] | None = None
    news_blackout_fn: Callable[[datetime], bool] | None = None
    recent_trades: list[TradeOutcome] = field(default_factory=list)
    spread_baseline_pips: float | None = None
```
- Sentiment + intraday-window check vivono in **layer separato post-detector** (esistente `_apply_sentiment` resta in shim `IntradayStrategy`, non entra nel pure detector).

### D-05 — Adapter per ambiente
- `strategy/adapters/live.py::build_ctx_live(symbol, mt5_client, profile, **adjuster_hooks)` — fetch bars, indicators (chiamando `indicators.compute_all_extended` UNA volta, vedi D-09), sr, regime, patterns. Chiamato dallo shim `IntradayStrategy.analyze_symbol`.
- `strategy/adapters/backtest.py::build_ctx_backtest(symbol, engine_state, profile, **adjuster_hooks)` — costruisce stesso ctx da `BacktestEngine` state (Phase 1). Stessa firma di output → detector indistinguibile.
- Detector è agnostico rispetto all'origine.

### D-06 — Setup priority + multi-match resolution
- Detector eseguiti tutti in parallelo sullo stesso bar via `evaluate_proposal_for_bar()`.
- Se >1 ritorna `setup_type=READY`: vince **highest grade**. Tie-break con priorità fissa: **A breakout > C compression > B reversal > D pullback**.
- Razionale: trend-with > mean-revert; A/C più "explosive" e tipicamente cleaner; B/D più mean-revert/pullback contro-momento.
- `evaluate_proposal_for_bar(bars, indicators, ctx) -> ProposalDraft` ritorna il vincitore. Tutti i Draft non-vincenti loggati in `losers: list[ProposalDraft]` su `ProposalDraft.setup_specific["losers"]` per ML training Phase 7.

### D-07 — Counter-trend gating per Setup B (reversal)
- Skill rule: "trade against medium-term trend only counts as confluence if A-grade reversal stack".
- Implementazione: detector `b_reversal` emette `setup_type=READY` solo se grade calcolato è A o A+. Se grade=B o C e direzione contro `indicators.ema50_slope`, downgrade a `setup_type=NONE` con `reason="counter_trend_below_A_grade"`.
- D pullback è sempre trend-with → no gating speciale.

### D-08 — 5-factor confluence + soglie in `config/strategy.yaml`
- Mirror del pattern `config/patterns.yaml` (Phase 3) e `config/regime.yaml` (Phase 2).
- Schema:
  ```yaml
  factors:
    trend_alignment:
      use_ema50_slope: true
      counter_trend_allowed_grades: ["A+", "A"]
    setup_pattern:
      half_formed_rejected: true
    momentum:
      rsi_neutral_band: [40, 60]
      divergence_required_for_reversal: true
    volatility_regime:
      breakout_required: ["expanded", "normal"]
      compression_required: ["compressed"]
      reversal_required: ["normal", "expanded"]
      pullback_required: ["normal"]
    spread_session:
      max_spread_atr_ratio: 0.20      # spread/(1xATR) <= 0.20 → factor true
      optional_session_bonus: 0.05     # adjuster, non factor

  grade_map:
    "A+": 5
    "A":  4
    "B":  3
    "C":  2
    "reject": "<=1"

  base_confidence:
    "A+": 0.85
    "A":  0.70
    "B":  0.55
    "C":  0.40

  adjusters:
    intermarket_confirmation: +0.05
    recent_winning_trade_same_pair: +0.05
    spread_tighter_than_baseline: +0.05
    macro_event_within_60min: -0.05
    last_2_trades_lost_same_pair: -0.05
    proposing_against_medium_term_trend: -0.05

  bounds:
    min_confidence: 0.10
    max_confidence: 0.95

  profile_filters:
    CONSERVATIVE: {min_grade: "A",  min_rr: 2.5, min_confidence: 0.65}
    MODERATE:     {min_grade: "B",  min_rr: 1.8, min_confidence: 0.50}
    AGGRESSIVE:   {min_grade: "C",  min_rr: 1.3, min_confidence: 0.40}
  ```
- `load_strategy_config(path: str | None = None) -> StrategyConfig` (frozen dataclass), default `config/strategy.yaml`.
- Override via `STRATEGY_CONFIG_PATH` env per test.

### D-09 — Adjuster Phase 10-dipendenti: stub callable + zero-impact default
- `intermarket_score_fn` e `news_blackout_fn` opzionali in `StrategyContext`. Se None → adjuster ritorna 0 (no impact).
- Phase 10 inietta callable reali via adapter — **zero churn in `confluence.py`**.
- Adjuster già disponibili (spread_baseline, recent_trades) implementati subito.
- `recent_trades` fornito da live adapter via `mt5_client.get_trade_history(n=5)`; backtest adapter via `engine_state.recent_trades_for(symbol)`.

### D-10 — SL/TP per-setup, fn dedicata in ogni setup module
- Cap universale **1.5×ATR** sulla SL distance.
- Buffer universale **0.3–0.5×ATR** dal livello strutturale.
- Per-setup:
  - **A breakout (`a_breakout._compute_levels`):** SL al broken level ± 0.4×ATR; TP = swing-extension o 2.5×ATR projection. R:R floor da profile.
  - **B reversal (`b_reversal._compute_levels`):** SL beyond reversal-bar extreme ± 0.3×ATR; TP = opposite-end of recent range o prior swing.
  - **C compression (`c_compression._compute_levels`):** SL all'opposite side della compression range; TP = 2–3× compression range expansion.
  - **D pullback (`d_pullback._compute_levels`):** SL sotto pullback-low (BUY) / sopra pullback-high (SELL); TP = prior swing extension o 1–1.618 Fib extension del leg.
- Existing `indicators.calculate_risk_reward()` riusato per validation.
- ProposalDraft popolato con `setup_specific = {"breakout_level": ..., "reversal_bar_extreme": ..., "compression_range": (lo,hi), "pullback_low": ...}` per debug + ML feature.

### D-11 — Confidence calibration: stesse soglie in `config/strategy.yaml`
- Vedi D-08 schema (`base_confidence`, `adjusters`, `bounds`).
- Esistente `_score_confidence` deprecata; rimossa dal shim al completamento Phase 4 (no DeprecationWarning, refactor atomico). Tests aggiornati.

### D-12 — Live↔backtest adapter: indicators pre-computed
- Adapter chiama `indicators.compute_all_extended(bars)` UNA volta per bar, passa snapshot `ExtendedIndicators` (estensione di `IndicatorSnapshot` Phase 2 D-09 con tutti i 14 INDIC). Detector consuma — non calcola.
- Costo: 4 detector sullo stesso bar ⇒ 1 sola compute, non 4. Critico per Phase 5 backtest 23.5y × 3 pair × 3 TF.
- Ogni detector specifica nel `__doc__` quali campi di `ExtendedIndicators` usa — auditable + ottimizzabile.

### D-13 — Backtest engine drive-bar pattern
- Phase 5 `BacktestEngine.run()` itera bar-by-bar; per ogni bar:
  1. `bars_so_far = full_csv[:i+1]`
  2. `indicators = compute_all_extended(bars_so_far)`
  3. `ctx = backtest.build_ctx(symbol, engine_state.with_bar(i), profile)`
  4. `draft = evaluate_proposal_for_bar(bars_so_far, indicators, ctx)`
  5. Engine consuma draft → fill simulation + ledger.
- No future leakage by construction (detector vede solo `bars[:i+1]`).

### D-14 — Regression fixture (SC#5): JSON snapshot pre-refactor, Wave 0
- **Wave 0 task #1**: `tests/capture_regression_baseline.py` script → esegue `IntradayStrategy` attuale su 10 scenari (10 simboli × 10 momenti recenti, da `data/historical/EURUSD/M15.csv` last 1000 bars + sample da GBPUSD + USDJPY). Cattura input (bars, account_state mock, sentiment None) + output (TradeProposal | TechnicalSetup) → `tests/fixtures/strategy_regression_baseline.json`.
- Commit fixture **prima** di toccare `strategy.py`.
- `tests/test_strategy_regression.py` (Wave finale): replay fixture con nuovo codice via shim `IntradayStrategy.analyze_symbol`, asserisce output identico al baseline (entry/sl/tp/confidence/setup_type/direction).
- Tolleranza: float comparison `1e-5` su prezzi (rounding); confidence `1e-4`.
- 10 scenari includono mix di READY (almeno 3), FORMING (almeno 2), NONE (almeno 3) per coprire tutti i path.

### D-15 — Engineering principles (non-negoziabili, da forex-algo-dev)
- **Bar boundaries sacred**: detector vede bars[:i+1], mai bars[i+1:].
- **Pure-function strategy layer**: STRAT-08 enforced: no broker calls, no log/print, no DB writes nel detector. Side effect-free verificabile via `tests/test_strategy_purity.py` (introspect AST per chiamate I/O).
- **Idempotent + observable**: stesso input → stesso output. ProposalDraft contiene tutto il rationale.
- **Calibration over confidence**: confidence è calibrato (skill table), non aspirational.

### D-16 — Test strategy
- `tests/test_strategy_setups.py` — un file per detector (4 file). Cases per detector: clean READY positivo, near-miss NONE, FORMING transition, multi-match priority (test composito).
- `tests/test_strategy_confluence.py` — 5-factor scoring + grade map + adjuster zero-impact + adjuster con stub callable.
- `tests/test_strategy_proposal.py` — `ProposalDraft → TradeProposal` adapter, profile filtering, R:R floor.
- `tests/test_strategy_purity.py` — AST introspection: nessun import di `mt5`, `requests`, `logging.getLogger.*.{info,warning}` dentro `strategy/setups/`, `strategy/confluence.py`, `strategy/proposal.py` (escludi shim/adapters).
- `tests/test_strategy_regression.py` — replay 10 fixture (D-14).
- Tutti pure → mock-free. <500ms totale (SC#3).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project locked specs
- `.planning/PROJECT.md` — milestone scope, key decisions
- `.planning/REQUIREMENTS.md` §Strategy Refactor — STRAT-01..STRAT-09 verbatim
- `.planning/ROADMAP.md` §Phase 4 — goal, success criteria, requirements

### Prior phase carry-forward
- `.planning/phases/01-backtest-engine/01-CONTEXT.md` — D-08 GMT-6→UTC, D-09 bar-close decision, BrokerProtocol decoupling
- `.planning/phases/02-indicators-library/02-CONTEXT.md` — D-04 dataclass-of-lists return, D-09 (no future leakage), D-10 NY-17 session anchor (factor #5 spread_session), D-15/16 regime config
- `.planning/phases/03-patterns-catalog/03-CONTEXT.md` — `PatternHit` dataclass, calibrazione confidence, `config/patterns.yaml` location pattern (mirror per `config/strategy.yaml`)

### Codebase maps
- `.planning/codebase/STRUCTURE.md` — layout flat root, packaging convention
- `.planning/codebase/ARCHITECTURE.md` — strategy/scanner layering, scheduler entry-points
- `.planning/codebase/CONVENTIONS.md` — snake_case, dataclass, leading-underscore privates, italiano commenti
- `.planning/codebase/TESTING.md` — pytest layout `tests/test_strategy_*.py`

### Existing code (touch / extend)
- `strategy.py` (737 linee) — refactor in `strategy/` package. `IntradayStrategy` class diventa shim.
- `models.py` — `TradeProposal`, `TechnicalSetup`, `BrokerProtocol`, `AccountState`, `PositionInfo`, `OpenPositionVerdict` (preservare signature). Aggiungere `RiskProfile` enum se non esiste.
- `indicators/` package (Phase 2) — consumer principale: `compute_all_extended`, `bollinger_bands`, `adx`, `macd`, `keltner`, `volatility_regime`, `mtf_align`, `closing_score`, `nr_detect`, ecc.
- `patterns.py` (Phase 3) — `scan_patterns()` ritorna `list[PatternHit]`, consumato da Setup B.
- `scheduler.py` — caller `IntradayStrategy.analyze_symbol()`. Shim mantiene firma.
- `mcp_server.py:28+` — caller (`propose_trade`, `evaluate_trade_proposal`). Shim mantiene firma.
- `claude_agent.py:12+` — `explain_last_trades` consumer (read-only). Shim non rompe.
- `risk_engine.py` — `PROFILES` dict (CONSERVATIVE/MODERATE/AGGRESSIVE) — single source di profile keys.

### Configs (creare in questa fase)
- `config/strategy.yaml` — D-08 schema (factors, grade_map, base_confidence, adjusters, profile_filters)
- `tests/fixtures/strategy_regression_baseline.json` — D-14 snapshot pre-refactor

### Skills
- `forex-trader-pro` — Setup A/B/C/D playbook completo, 5-factor table, base_confidence numerico, R:R per profile, SL prescrizioni per-setup
- `forex-algo-dev` — pure-fn discipline, no future leakage, calibration patterns, walk-forward
- `forex-strategy-builder` — book-grounded geometry (Murphy/Probo/Defendi)

### External libs
- Nessuna nuova dipendenza runtime. Solo PyYAML (già usato da `config/patterns.yaml` Phase 3).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `strategy.IntradayStrategy._score_confidence` — logica scoring esistente (trend/pattern/volume/rr/mtf placeholder). Sostituita da nuovo confluence.py ma utile come reference durante migrazione.
- `strategy._compute_levels` — reference per buffer ATR + SR. Splittato in 4 versioni per-setup.
- `strategy.identify_entry_setup` — single breakout-trend logica esistente. Diventa `strategy/setups/a_breakout.py` (con espansione real Setup A skill).
- `strategy.estimate_position_risk_amount`, `estimate_proposal_risk_amount`, `estimate_proposal_lots` — utility risk calc. Spostate in `strategy/risk_utils.py` (preservate, non-pure ma utility usate dallo shim e dal risk_engine).
- `strategy.evaluate_open_position`, `compute_existing_potential_loss_amount`, `would_proposal_exceed_drawdown`, `is_addon_for`, `build_delayed_followup` — non-pure (usano broker). Restano sullo shim `IntradayStrategy`, non migrate al pure layer. Phase 4 NON tocca queste.
- `strategy._apply_sentiment` — non-pure layer post-detector. Preservata sullo shim, applicata su `TradeProposal` finale dopo `draft_to_trade_proposal`.

### Established Patterns
- `config/<module>.yaml` + `load_<module>_config()` + frozen dataclass + `<MODULE>_CONFIG_PATH` env override (da Phase 3).
- `@dataclass(frozen=True)` per output dei pure layer (PatternHit Phase 3 → ProposalDraft Phase 4).
- Re-export tutto da `__init__.py` per backward compat (Phase 2 D-03).
- Test puri mock-free; AST-introspection per purity gate (nuovo Phase 4).

### Hot Spots / Risks
- **`strategy.py:229`** — già refactorato in Phase 3 per `PatternHit` dataclass. Phase 4 deve sostituire intera funzione `_analyze_technical` + `identify_entry_setup`.
- **Scheduler entry-point** — `scheduler.py` chiama `IntradayStrategy(cfg, mt5, log).analyze_symbol(symbol, account_state, sentiment)`. Shim DEVE mantenere questa firma esatta.
- **MCP `propose_trade`** — Phase 6 lo refactora con `setup_type` + `confluence_score` (MCP-R3). Phase 4 espone questi campi via `TradeProposal` extra fields opzionali (no-op per consumatori legacy).
- **Confidence delta pre/post**: `_score_confidence` attuale produce valori in 0..1 ma con weights diversi dalla skill table. Regression fixture (D-14) catturerà output attuale → test asserisce delta tollerato `1e-4`. **Se delta supera tolleranza, è bug del nuovo codice, non drift legittimo.** Plan deve includere task di reconciliation.
- **Performance**: SC#3 dice <500ms totale per tutti i test. Critico: `compute_all_extended` può essere lento su 200-bar lookback × 14 indicators. Profile durante Wave 1.

</code_context>

<specifics>
## Specific Ideas

### Pure-fn skeleton esempio (Setup A)
```python
# strategy/setups/a_breakout.py
from strategy.proposal import ProposalDraft
from strategy.context import StrategyContext
from strategy.confluence import score_factors, base_confidence_for_grade
from indicators.volatility import ExtendedIndicators

def detect_a_breakout(
    bars: list[dict],
    indicators: ExtendedIndicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    """Setup A: clean break of horizontal S/R or trendline.

    Confluence factors checked:
      1. trend_alignment (ema50_slope coerente con direction)
      2. setup_pattern (range bar wide + Closing Score >75 long / <25 short)
      3. momentum (RSI not stretched against)
      4. volatility_regime ∈ {expanded, normal}
      5. spread_session (spread/atr <= 0.20)
    """
    ...
    factors = score_factors(setup_name="A_breakout", ...)
    grade = grade_for(factors)
    if grade == "reject":
        return ProposalDraft(setup_type="NONE", reason="confluence_below_2_factors", ...)
    entry, sl, tp = _compute_levels(direction, broken_level, atr, ctx.pip_size)
    rr = (tp - entry) / (entry - sl) if direction == "BUY" else (entry - tp) / (sl - entry)
    if rr < ctx.profile.min_rr:
        return ProposalDraft(setup_type="NONE", reason=f"rr_below_profile_min_{rr:.2f}", ...)
    confidence = compute_confidence(grade, ctx, base_adjusters=...)
    return ProposalDraft(
        setup_type="READY", setup_name="A_breakout", direction=direction,
        entry_price=entry, stop_loss_price=sl, take_profit_price=tp,
        factors=factors, grade=grade, confidence=confidence,
        reason="clean_break_above_resistance_with_expanded_atr",
        rationale_parts={"break_level": broken_level, "atr_at_break": atr, ...},
        setup_specific={"breakout_level": broken_level},
    )
```

### `evaluate_proposal_for_bar` orchestrator
```python
# strategy/__init__.py
def evaluate_proposal_for_bar(
    bars: list[dict],
    indicators: ExtendedIndicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    drafts = [detect(bars, indicators, ctx) for detect in ALL_DETECTORS]
    ready = [d for d in drafts if d.setup_type == "READY"]
    if not ready:
        forming = [d for d in drafts if d.setup_type == "FORMING"]
        if forming:
            return forming[0]  # primo FORMING in priority order
        return drafts[0]  # NONE con reason del primo detector (A)
    # Highest grade, tie-break A>C>B>D
    GRADE_ORDER = {"A+": 0, "A": 1, "B": 2, "C": 3}
    PRIORITY = {"A_breakout": 0, "C_compression": 1, "B_reversal": 2, "D_pullback": 3}
    winner = min(ready, key=lambda d: (GRADE_ORDER[d.grade], PRIORITY[d.setup_name]))
    losers = [d for d in drafts if d is not winner]
    return replace(winner, setup_specific={**winner.setup_specific, "losers": losers})
```

### Shim `IntradayStrategy.analyze_symbol`
```python
# strategy/__init__.py
class IntradayStrategy:
    def __init__(self, cfg, mt5, logger=None, environment=None):
        self.cfg, self.mt5, self.log = cfg, mt5, logger or logging.getLogger(__name__)
        self.env = environment or StrategyEnvironment(cfg, self.log)
        self.strategy_cfg = load_strategy_config()

    def analyze_symbol(self, symbol, account_state, sentiment=None) -> TechnicalSetup:
        ctx = build_ctx_live(symbol, self.mt5, profile=self.cfg.RISK_MODE,
                             intermarket_score_fn=None,  # Phase 10 hook
                             news_blackout_fn=self.env.is_news_window)
        bars, indicators = ctx.bars, ctx.indicators
        draft = evaluate_proposal_for_bar(bars, indicators, ctx)
        proposal_or_setup = draft_to_technical_setup(draft, symbol, self.cfg.INTRADAY_TIMEFRAME)
        return self._apply_sentiment(proposal_or_setup, sentiment)  # legacy path preserved
```

### `config/strategy.yaml` — vedi schema in D-08

### Regression baseline capture script
```python
# tests/capture_regression_baseline.py
# UNA TANTUM, prima di toccare strategy.py.
# Executa IntradayStrategy ATTUALE su 10 scenari → JSON.
import json
from strategy import IntradayStrategy   # versione pre-refactor
from tests.fixtures.mock_mt5 import MockMt5Client  # carica bars da CSV storica
SCENARIOS = [
    {"symbol": "EURUSD", "csv": "data/historical/EURUSD/M15.csv", "bar_offset": -200},
    {"symbol": "EURUSD", "csv": "data/historical/EURUSD/M15.csv", "bar_offset": -350},
    # ... 10 totali, mix di expected READY/FORMING/NONE
]
fixture = []
for s in SCENARIOS:
    mt5 = MockMt5Client.from_csv(s["csv"], cap_at_bar=s["bar_offset"])
    strategy = IntradayStrategy(cfg, mt5)
    setup = strategy.analyze_symbol(s["symbol"], MOCK_ACCOUNT_STATE)
    fixture.append({"input": s, "output": dataclasses.asdict(setup)})
json.dump(fixture, open("tests/fixtures/strategy_regression_baseline.json", "w"), indent=2)
```

</specifics>

<deferred>
## Deferred Ideas

- **ML-driven setup ranking** (use Phase 7 calibrated_prob to break tie instead of grade) — Phase 8 quando ML è online
- **Per-symbol strategy.yaml** override (es. XAUUSD usa soglie più larghe) — se Phase 5 backtest rivela edge differente per pair
- **Vectorized detector** (numpy/pandas batch su intera serie) — Phase 5 se 23.5y backtest > 30 min
- **Detector ensemble voting** (weighted vote invece di highest-grade) — backlog ML tuning, Phase 8+
- **Real-time multi-TF confluence** (input H4+H1+M15 simultaneo) — INDIC-13 esiste ma uso pieno richiede Phase 6 `get_multi_tf_snapshot`
- **DeprecationWarning su `IntradayStrategy`** — non emessa in Phase 4 (cleanup atomico). Eventuale Phase 6/8 quando MCP refactor consolida
- **Setup E (channel/range trading)** — non in scope (4 setup canonici skill)
- **Confidence calibration ML-based** (replace heuristic con isotonic) — Phase 7 ML, sostituisce config/strategy.yaml `base_confidence`
- **Failed breakout (Setup A failure)** auto-flip → Setup C contrarian — skill menziona ma richiede user-confirm; backlog
- **Adjuster: spread vs hourly baseline** real (ora usa simple `spread_baseline_pips`) — Phase 10 con session-state tool
- **Strict purity enforcement runtime** (decorator `@pure_function` con runtime check) — solo AST test in Phase 4

</deferred>

---

*Phase: 04-strategy-refactor*
*Context gathered: 2026-05-07 via /gsd:discuss-phase*
*Mode: discuss (4 aree, ~12 question)*
