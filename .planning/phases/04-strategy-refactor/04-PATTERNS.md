# Phase 4: Strategy Refactor — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 22 (14 new source + 3 modified source + 5 new test files)
**Analogs found:** 22 / 22

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `strategy/__init__.py` | package barrel + shim class + orchestrator fn | request-response | `indicators/__init__.py` (Phase 2 plan) + `strategy.py` `IntradayStrategy` | exact (barrel) + role-match (shim) |
| `strategy/context.py` | frozen dataclass container | data model | `models.py` `TechnicalSetup` / `TradeProposal` | exact (frozen dataclass style) |
| `strategy/proposal.py` | frozen dataclass + adapter fn | data model + transform | `backtest/costs.py` `CostModel` + `strategy.py` `build_trade_proposal` | exact (frozen dataclass) + role-match (adapter) |
| `strategy/confluence.py` | pure-fn scorer + grader + calibrator | transform | `strategy.py` `_score_confidence` + `backtest/costs.py` `load_cost_model` | role-match (scorer) + exact (yaml-config loader) |
| `strategy/setups/__init__.py` | registry list | config/barrel | `backtest/__init__.py` + `indicators/__init__.py` plan | exact |
| `strategy/setups/a_breakout.py` | pure-fn detector | transform (CRUD) | `strategy.py` `identify_entry_setup` + `_compute_levels` | exact (lift-and-extend) |
| `strategy/setups/b_reversal.py` | pure-fn detector | transform (CRUD) | `strategy.py` `identify_entry_setup` (structure); `patterns.py` pattern consumer | role-match |
| `strategy/setups/c_compression.py` | pure-fn detector | transform (CRUD) | `strategy.py` `identify_entry_setup` + `indicators.py` `atr` (ATR math) | role-match |
| `strategy/setups/d_pullback.py` | pure-fn detector | transform (CRUD) | `strategy.py` `identify_entry_setup` + `indicators.py` `ema` (EMA math) | role-match |
| `strategy/adapters/live.py` | context builder (adapter) | request-response | `strategy.py` `_analyze_technical` (broker fetch portion) | exact (lift broker-fetch block) |
| `strategy/adapters/backtest.py` | context builder (adapter) | request-response | `backtest/engine.py` bar-loop section | role-match |
| `strategy/adapters/__init__.py` | barrel | config/barrel | `backtest/__init__.py` | exact |
| `strategy/risk_utils.py` | utility helpers | transform | `strategy.py` `estimate_position_risk_amount`, `estimate_proposal_risk_amount`, `estimate_proposal_lots`, `_pip_value_amount`, `_pip_size` | exact (lift verbatim) |
| `config/strategy.yaml` | YAML config (factors, grades, confidence, adjusters) | config | `data/configs/costs.yaml` + `config/patterns.yaml` (Phase 3) | exact |
| `models.py` (modify) | add `RiskProfile` type alias | data model | `models.py` existing `Literal` type aliases | exact |
| `strategy.py` (delete/replace) | replaced by `strategy/` package | — | `strategy.py` is the source; `indicators/__init__.py` backward-compat pattern is the model | — |
| `tests/capture_regression_baseline.py` | one-time capture script | batch | `tests/test_backtest_engine.py` `_uptrend_bars` + CSV loader | role-match |
| `tests/fixtures/strategy_regression_baseline.json` | regression snapshot | fixture | `tests/fixtures/eurusd_5bars.csv` | role-match (fixture data) |
| `tests/test_strategy_setups.py` | unit tests (4 detectors) | test | `tests/test_strategy.py` `identify_entry_setup` tests | exact |
| `tests/test_strategy_confluence.py` | unit tests (scorer + grader + adjusters) | test | `tests/test_backtest_costs.py` hand-calc style | exact |
| `tests/test_strategy_proposal.py` | unit tests (ProposalDraft → TradeProposal adapter + R:R + profile) | test | `tests/test_strategy.py` `build_trade_proposal` tests | exact |
| `tests/test_strategy_purity.py` | AST introspection static gate | test (static) | `tests/test_indicators_purity.py` (Phase 2 plan) | role-match |
| `tests/test_strategy_regression.py` | regression replay 10 fixtures | integration test | `tests/test_backtest_engine.py` end-to-end style | role-match |

---

## Pattern Assignments

### `strategy/__init__.py` (package barrel + shim + orchestrator)

**Analogs:** `backtest/__init__.py` (barrel pattern), `strategy.py:151-175` (`IntradayStrategy.__init__` + `analyze_symbol`), Phase 2 `indicators/__init__.py` plan (backward-compat re-export)

**Barrel + backward-compat re-export pattern** (copy from `backtest/__init__.py` shape, extend with imports like Phase 2 plan):
```python
"""Strategy package — motore Python puro per generare ProposalDraft.

Backward-compat: IntradayStrategy, TechnicalSetup, TradeProposal continuano
a funzionare invariati per scheduler.py, mcp_server.py, claude_agent.py.
"""
from strategy.context import StrategyContext
from strategy.proposal import ProposalDraft, draft_to_trade_proposal, draft_to_technical_setup
from strategy.confluence import score_factors, grade_for, compute_confidence
from strategy.setups import ALL_DETECTORS
from strategy._shim import IntradayStrategy        # backward-compat class

__all__ = [
    "IntradayStrategy",
    "evaluate_proposal_for_bar",
    "ProposalDraft",
    "StrategyContext",
]
```

**`evaluate_proposal_for_bar` orchestrator** (lines exact from CONTEXT.md D-06):
```python
# Source: CONTEXT.md D-06 + strategy.py:168-175 (analyze_symbol structure)
from dataclasses import replace
from strategy.setups import ALL_DETECTORS

GRADE_ORDER = {"A+": 0, "A": 1, "B": 2, "C": 3, "reject": 4}
PRIORITY    = {"A_breakout": 0, "C_compression": 1, "B_reversal": 2, "D_pullback": 3}

def evaluate_proposal_for_bar(
    bars: list[dict],
    indicators: "ExtendedIndicators",
    ctx: "StrategyContext",
) -> "ProposalDraft":
    drafts = [detect(bars, indicators, ctx) for detect in ALL_DETECTORS]
    ready = [d for d in drafts if d.setup_type == "READY"]
    if not ready:
        forming = [d for d in drafts if d.setup_type == "FORMING"]
        winner = min(forming, key=lambda d: PRIORITY.get(d.setup_name or "", 99)) if forming else drafts[0]
        losers = [d for d in drafts if d is not winner]
        return replace(winner, setup_specific={**(winner.setup_specific or {}), "losers": losers})
    winner = min(ready, key=lambda d: (GRADE_ORDER[d.grade], PRIORITY[d.setup_name]))
    losers = [d for d in drafts if d is not winner]
    return replace(winner, setup_specific={**winner.setup_specific, "losers": losers})
```

**`IntradayStrategy` shim `analyze_symbol`** (exact existing signature preserved):
```python
# Source: strategy.py:168-175 — MUST preserve exact signature
class IntradayStrategy:
    def __init__(
        self,
        cfg: Config,
        mt5_client: BrokerProtocol,
        logger: logging.Logger | None = None,
        environment: StrategyEnvironment | None = None,
    ):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger or logging.getLogger(__name__)
        self.env = environment or StrategyEnvironment(cfg, self.log)
        self.strategy_cfg = load_strategy_config()

    def analyze_symbol(
        self,
        symbol: str,
        account_state: AccountState,
        sentiment: SentimentAnalysis | None = None,
    ) -> TechnicalSetup:
        # Non-pure wrapper — side-effects permessi (broker calls, logging)
        ctx = build_ctx_live(symbol, self.mt5, profile=self.cfg.RISK_MODE,
                             intermarket_score_fn=None,
                             news_blackout_fn=self.env.is_news_window)
        bars, indicators = ctx._bars, ctx._indicators
        draft = evaluate_proposal_for_bar(bars, indicators, ctx)
        setup = draft_to_technical_setup(draft, symbol, self.cfg.INTRADAY_TIMEFRAME)
        return self._apply_sentiment(setup, sentiment)
```

**`_apply_sentiment` — lift verbatim** from `strategy.py:641-722` (pure copy into shim, not modified).

---

### `strategy/context.py` (frozen dataclass)

**Analog:** `models.py:107-118` (`TechnicalSetup` dataclass) and `models.py:192-196` (`SentimentAnalysis` with optional fields + `field(default_factory=...)`)

**Frozen dataclass with optional fields and `field()` defaults** (lines 1-14 of `models.py` + lines 34-36 `AccountState`):
```python
# Source: models.py:1-4 (imports), models.py:34-36 (field default_factory)
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timeframe: str
    profile: str                          # "CONSERVATIVE" | "MODERATE" | "AGGRESSIVE"
    sr: dict
    regime: str                           # "compressed" | "normal" | "expanded"
    patterns: list                        # list[PatternHit] from Phase 3
    symbol_info: object
    pip_size: float
    intermarket_score_fn: Callable | None = None
    news_blackout_fn: Callable | None = None
    recent_trades: list = field(default_factory=list)
    spread_baseline_pips: float | None = None
    # Campi privati per adapter (esclusi da compare/hash/repr)
    _bars: list = field(default_factory=list, compare=False, hash=False, repr=False)
    _indicators: object = field(default=None, compare=False, hash=False, repr=False)
```

**No mutable defaults without `field()`** — follows `models.py:36` pattern exactly.

---

### `strategy/proposal.py` (frozen dataclass + adapter fn)

**Analogs:** `backtest/costs.py:8-22` (frozen dataclass + `__post_init__` validation), `strategy.py:388-416` (`build_trade_proposal`)

**Frozen dataclass with `__post_init__` for mutable defaults** (copy the CostModel pattern from `backtest/costs.py:8-22`):
```python
# Source: backtest/costs.py:8 (@dataclass(frozen=True)) + models.py:6 (import style)
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ProposalDraft:
    setup_type: Literal["READY", "FORMING", "NONE"]
    setup_name: Literal["A_breakout", "B_reversal", "C_compression", "D_pullback"] | None = None
    direction: Literal["BUY", "SELL"] | None = None
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    factors: dict = None
    grade: Literal["A+", "A", "B", "C", "reject"] | None = None
    confidence: float = 0.0
    reason: str = ""
    rationale_parts: dict = None
    setup_specific: dict = None

    def __post_init__(self):
        # Frozen dataclass: usa object.__setattr__ per inizializzare dict mutabili
        if self.factors is None:
            object.__setattr__(self, "factors", {})
        if self.rationale_parts is None:
            object.__setattr__(self, "rationale_parts", {})
        if self.setup_specific is None:
            object.__setattr__(self, "setup_specific", {})
```

**`draft_to_trade_proposal` adapter** — mirror `strategy.py:388-416` (`build_trade_proposal`):
```python
# Source: strategy.py:388-416 (build_trade_proposal shape)
def draft_to_trade_proposal(
    draft: ProposalDraft,
    symbol: str,
    timeframe: str,
) -> TradeProposal:
    if draft.setup_type != "READY" or draft.direction is None:
        raise ValueError(f"draft_to_trade_proposal richiede setup READY, ricevuto {draft.setup_type}")
    return TradeProposal(
        symbol=symbol,
        direction=draft.direction,
        entry_price=draft.entry_price,
        stop_loss_price=draft.stop_loss_price,
        take_profit_price=draft.take_profit_price,
        timeframe=timeframe,
        comment="python_strategy",
        confidence=draft.confidence,
        rationale=draft.reason,
    )
```

**`draft_to_technical_setup` adapter** — mirror `TechnicalSetup` constructor from `strategy.py:271-276`:
```python
# Source: strategy.py:271-276 (TechnicalSetup READY construction)
def draft_to_technical_setup(draft: ProposalDraft, symbol: str, timeframe: str) -> TechnicalSetup:
    return TechnicalSetup(
        symbol=symbol, timeframe=timeframe,
        setup_type=draft.setup_type,
        direction=draft.direction,
        entry_price=draft.entry_price,
        stop_loss=draft.stop_loss_price,
        take_profit=draft.take_profit_price,
        confidence=draft.confidence,
        reason=draft.reason,
        indicators={"factors": draft.factors, "grade": draft.grade,
                    "rationale_parts": draft.rationale_parts},
        support_resistance=None,
    )
```

---

### `strategy/confluence.py` (pure-fn scorer + grader + calibrator + YAML loader)

**Analogs:** `strategy.py:606-639` (`_score_confidence` — replace, not port), `backtest/costs.py:42-59` (`load_cost_model` for YAML loader pattern), `patterns.py` Phase 3 `load_pattern_config` shape

**YAML config loader** — copy verbatim from `backtest/costs.py:42-59` pattern (as confirmed in Phase 3 PATTERNS.md line 80-95):
```python
# Source: backtest/costs.py:42-59 (yaml.safe_load + env override + KeyError on missing)
from pathlib import Path
import os
import yaml

DEFAULT_STRATEGY_CONFIG_PATH = Path("config/strategy.yaml")

def load_strategy_config(path: str | Path | None = None) -> "StrategyConfig":
    """Carica config strategy.yaml. Priorità: parametro > env > default."""
    if path is None:
        path = os.environ.get("STRATEGY_CONFIG_PATH") or DEFAULT_STRATEGY_CONFIG_PATH
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}   # `or {}` pattern da costs.py:45
    return _build_strategy_config(raw)  # ValueError se chiavi mancanti
```

**`score_factors` pure fn** (key addition over `_score_confidence`):
```python
# Source: strategy.py:606-639 (factor logic — restructured to dict[str,bool], not float)
def score_factors(
    setup_name: str,
    indicators: "ExtendedIndicators",
    ctx: "StrategyContext",
    direction: str,
) -> dict[str, bool]:
    cfg = load_strategy_config()   # cached singleton
    return {
        "trend_alignment":   _check_trend_alignment(indicators, ctx, direction, cfg),
        "setup_pattern":     _check_setup_pattern(setup_name, indicators, direction, cfg),
        "momentum":          _check_momentum(indicators, direction, cfg),
        "volatility_regime": _check_volatility_regime(setup_name, indicators, cfg),
        "spread_session":    _check_spread_session(indicators, ctx, cfg),
    }

def grade_for(factors: dict[str, bool]) -> str:
    n = sum(factors.values())
    return {5: "A+", 4: "A", 3: "B", 2: "C"}.get(n, "reject")
```

**`compute_confidence` calibrator** — replaces `_score_confidence` entirely:
```python
# Source: CONTEXT.md D-08 + D-11 (base_confidence + adjusters from yaml)
def compute_confidence(
    grade: str,
    ctx: "StrategyContext",
    setup_name: str,
    cfg: "StrategyConfig | None" = None,
) -> float:
    cfg = cfg or load_strategy_config()
    base = cfg.base_confidence[grade]        # 0.85 / 0.70 / 0.55 / 0.40
    delta = 0.0
    # Adjusters disponibili subito (D-09)
    if ctx.spread_baseline_pips is not None:
        # ottieni spread corrente dall'indicatore snapshot (via ctx._indicators)
        pass
    if ctx.recent_trades:
        pass
    # Stub callables (Phase 10)
    if ctx.intermarket_score_fn is not None:
        if ctx.intermarket_score_fn(ctx.symbol) > 0:
            delta += cfg.adjusters["intermarket_confirmation"]
    if ctx.news_blackout_fn is not None:
        from datetime import datetime
        if ctx.news_blackout_fn(datetime.now()):
            delta += cfg.adjusters["macro_event_within_60min"]
    raw = base + delta
    return round(max(cfg.bounds["min_confidence"], min(cfg.bounds["max_confidence"], raw)), 4)
```

**Confidence bounds clamp** — mirrors `strategy.py:638-639`:
```python
# Source: strategy.py:638 (min/max clamp pattern)
return round(min(max(total, 0.0), 1.0), 4)
# Phase 4 uses config bounds instead of hardcoded 0.0/1.0:
return round(max(cfg.bounds["min_confidence"], min(cfg.bounds["max_confidence"], raw)), 4)
```

---

### `strategy/setups/__init__.py` (detector registry)

**Analog:** `backtest/__init__.py:1-3`

```python
"""Registry di tutti i detector setup — ordine determina priorità in caso di NONE/FORMING."""
from strategy.setups.a_breakout import detect_a_breakout
from strategy.setups.b_reversal import detect_b_reversal
from strategy.setups.c_compression import detect_c_compression
from strategy.setups.d_pullback import detect_d_pullback

ALL_DETECTORS = [
    detect_a_breakout,
    detect_b_reversal,
    detect_c_compression,
    detect_d_pullback,
]
```

---

### `strategy/setups/a_breakout.py` (pure-fn detector, Setup A)

**Analog:** `strategy.py:293-386` (`identify_entry_setup` — lift and restructure) + `strategy.py:573-604` (`_compute_levels`)

**Pure-fn detector skeleton** — copy the structural pattern from `identify_entry_setup` + `_compute_levels`, reshape to return `ProposalDraft`:

**Imports pattern** (copy from `strategy.py:8-32` then strip non-pure imports):
```python
# Source: strategy.py:8-32 stripped to pure-only imports
from __future__ import annotations
from dataclasses import replace
from strategy.proposal import ProposalDraft
from strategy.context import StrategyContext
from strategy.confluence import score_factors, grade_for, compute_confidence
```

**Core detector pattern** (adapt from `strategy.py:327-342`):
```python
# Source: strategy.py:327-342 (BUY breakout logic block) + 573-604 (_compute_levels)
def detect_a_breakout(
    bars: list[dict],
    indicators: "ExtendedIndicators",
    ctx: StrategyContext,
) -> ProposalDraft:
    """Setup A: rottura pulita di S/R orizzontale.

    Campi ExtendedIndicators usati: ema50_slope, rsi_14[-1], atr_14[-1],
    closing_score[-1], volatility_regime[-1], donchian_high[-1], donchian_low[-1].
    """
    # Guard: insufficient data (mirrors strategy.py:187-188)
    if not bars or len(bars) < 50:
        return ProposalDraft(setup_type="NONE", reason="insufficient_bars")

    atr_val = indicators.atr_14[-1] if indicators.atr_14[-1] is not None else None
    if atr_val is None or atr_val <= 0:
        return ProposalDraft(setup_type="NONE", reason="atr_not_ready")

    last_close = bars[-1]["close"]
    resistance = ctx.sr.get("resistance")
    support    = ctx.sr.get("support")
    tol = ctx.pip_size * 5  # SR_TOLERANCE_PIPS analog

    # FORMING: avvicinamento a livello (mirrors strategy.py:362-369)
    if resistance is not None and 0 < (resistance - last_close) <= tol:
        return ProposalDraft(
            setup_type="FORMING", setup_name="A_breakout", direction="BUY",
            confidence=0.0, reason="prezzo_vicino_a_resistance_attendo_conferma_breakout",
        )

    # READY check (mirrors strategy.py:327-342)
    direction = None
    broken_level = None
    if resistance is not None and last_close > resistance:
        direction = "BUY"
        broken_level = resistance
    elif support is not None and last_close < support:
        direction = "SELL"
        broken_level = support

    if direction is None:
        return ProposalDraft(setup_type="NONE", reason="no_breakout_detected")

    factors = score_factors("A_breakout", indicators, ctx, direction)
    grade   = grade_for(factors)
    if grade == "reject":
        return ProposalDraft(setup_type="NONE", reason="confluence_below_2_factors",
                             factors=factors, grade=grade)

    entry, sl, tp = _compute_levels_a(direction, last_close, broken_level, atr_val, ctx)
    from indicators import calculate_risk_reward
    rr = calculate_risk_reward(entry, sl, tp)
    profile_cfg = _profile_filter(ctx.profile)
    if rr < profile_cfg["min_rr"]:
        return ProposalDraft(setup_type="NONE", reason=f"rr_below_profile_min_{rr:.2f}",
                             factors=factors, grade=grade)

    confidence = compute_confidence(grade, ctx, "A_breakout")
    return ProposalDraft(
        setup_type="READY", setup_name="A_breakout", direction=direction,
        entry_price=entry, stop_loss_price=sl, take_profit_price=tp,
        factors=factors, grade=grade, confidence=confidence,
        reason=f"breakout_{direction.lower()}_resistance={broken_level:.5f}",
        rationale_parts={"broken_level": str(broken_level), "atr": str(atr_val)},
        setup_specific={"breakout_level": broken_level},
    )
```

**`_compute_levels_a` pattern** (adapt from `strategy.py:573-604`):
```python
# Source: strategy.py:573-604 (_compute_levels — split into per-setup versions)
def _compute_levels_a(
    direction: str, entry: float, broken_level: float,
    atr_val: float, ctx: StrategyContext,
) -> tuple[float, float, float]:
    digits = 5 if ctx.pip_size <= 0.001 else 3
    cap = 1.5 * atr_val          # ATR cap universale (D-10)
    buf = 0.4 * atr_val          # buffer A (D-10)
    if direction == "BUY":
        sl = broken_level - buf
        sl = max(sl, entry - cap)   # ATR cap enforced
        tp = entry + 2.5 * atr_val
    else:
        sl = broken_level + buf
        sl = min(sl, entry + cap)
        tp = entry - 2.5 * atr_val
    return round(entry, digits), round(sl, digits), round(tp, digits)
```

---

### `strategy/setups/b_reversal.py` (pure-fn detector, Setup B)

**Analog:** `strategy.py:327-386` (`identify_entry_setup` structure) + `patterns.py:106-136` (`scan_patterns` consumer)

**Counter-trend gate** (D-07 — key addition not present in current codebase):
```python
# Source: CONTEXT.md D-07 — no current analog, new logic
def detect_b_reversal(
    bars: list[dict],
    indicators: "ExtendedIndicators",
    ctx: StrategyContext,
) -> ProposalDraft:
    """Setup B: reversal a S/R con PatternHit confermante.

    Campi ExtendedIndicators usati: ema50_slope, rsi_14[-1], atr_14[-1], volatility_regime[-1].
    Campi ctx.patterns: list[PatternHit] — usa .name, .direction, .bar_index (NON dict key access).
    """
    # ... detection logic ...
    factors = score_factors("B_reversal", indicators, ctx, direction)
    grade   = grade_for(factors)

    # Counter-trend gate D-07
    ema50_slope = indicators.ema50_slope[-1] if indicators.ema50_slope[-1] is not None else 0.0
    trend_dir = "BUY" if ema50_slope > 0 else "SELL"
    if direction != trend_dir and grade not in ("A+", "A"):
        return ProposalDraft(
            setup_type="NONE", reason="counter_trend_below_A_grade",
            factors=factors, grade=grade,
        )
    # ... continue with _compute_levels_b ...
```

**PatternHit attribute access** (critical — NOT dict keys; Phase 3 delivers frozen dataclass):
```python
# Source: CONTEXT.md D-15 pitfall #3 — use attribute access, NOT dict keys
# WRONG (current patterns.py dict style): p["direction"] == "bullish"
# CORRECT (Phase 3 PatternHit frozen dataclass):
pattern_at_level = next(
    (p for p in ctx.patterns
     if p.direction == ("bullish" if direction == "BUY" else "bearish")
     and abs(p.bar_index) <= 3),
    None,
)
```

---

### `strategy/setups/c_compression.py` (pure-fn detector, Setup C)

**Analog:** `strategy.py:327-386` (structure), Phase 2 `indicators/bars.py` `NRResult` consumer

**NRResult and BollingerResult consumer pattern:**
```python
# Source: CONTEXT.md D-03 + Phase 2 indicators plan
def detect_c_compression(
    bars: list[dict],
    indicators: "ExtendedIndicators",
    ctx: StrategyContext,
) -> ProposalDraft:
    """Setup C: breakout da compressione (NR4/NR7 o BB squeeze).

    Campi ExtendedIndicators usati: nr_detect (NRResult), bollinger_bands.squeeze[-1],
    atr_14[-1], ema50_slope[-1], volatility_regime[-1], rsi_14[-1].
    """
    # NR7 detection
    nr = indicators.nr_detect
    is_nr7 = nr.nr7[-1] if (nr and nr.nr7 and nr.nr7[-1] is not None) else False
    # BB squeeze detection
    bb  = indicators.bollinger_bands
    is_squeeze = bb.squeeze[-1] if (bb and bb.squeeze and bb.squeeze[-1] is not None) else False

    if not (is_nr7 or is_squeeze):
        return ProposalDraft(setup_type="NONE", reason="no_compression_detected")
    # ...
```

---

### `strategy/setups/d_pullback.py` (pure-fn detector, Setup D)

**Analog:** `strategy.py:327-386` (structure), Phase 2 `indicators/structure.py` `FibonacciResult` consumer

**FibonacciResult consumer pattern:**
```python
# Source: CONTEXT.md D-10 (D pullback Fib levels) + Phase 2 FibonacciResult schema
def detect_d_pullback(
    bars: list[dict],
    indicators: "ExtendedIndicators",
    ctx: StrategyContext,
) -> ProposalDraft:
    """Setup D: pullback su trend consolidato (EMA20/EMA50 + Fib 38.2–61.8%).

    Campi ExtendedIndicators usati: ema20[-1], ema50[-1], ema50_slope[-1],
    rsi_14[-1], atr_14[-1], fibonacci (FibonacciResult), volatility_regime[-1].
    """
    fib = indicators.fibonacci   # FibonacciResult: .levels dict + .leg_high + .leg_low
    fib_38 = fib.levels.get("0.382") if fib else None
    fib_61 = fib.levels.get("0.618") if fib else None
    # ...
```

---

### `strategy/adapters/live.py` (live context builder)

**Analog:** `strategy.py:177-244` (`_analyze_technical` — broker-fetch block, lines 182-244)

**Live context builder** (lifts broker-fetch block from `_analyze_technical`, adds `compute_all_extended` call):
```python
# Source: strategy.py:182-244 (_analyze_technical broker-fetch portion)
from indicators import compute_all_extended
from indicators import find_support_resistance
from patterns import scan_patterns   # Phase 3: returns list[PatternHit]
from strategy.context import StrategyContext

def build_ctx_live(
    symbol: str,
    mt5_client: "BrokerProtocol",
    profile: str,
    intermarket_score_fn=None,
    news_blackout_fn=None,
    cfg: "Config | None" = None,
) -> StrategyContext:
    if cfg is None:
        from config import Config
        cfg = Config()

    # Broker fetch (verbatim from strategy.py:182-196)
    try:
        bars = mt5_client.get_ohlc(symbol, cfg.INTRADAY_TIMEFRAME, cfg.INTRADAY_LOOKBACK_BARS)
    except Exception as exc:
        raise RuntimeError(f"get_ohlc failed for {symbol}: {exc}") from exc

    try:
        sym_info = mt5_client.get_symbol_info(symbol)
    except Exception:
        sym_info = None

    from strategy.proposal import _pip_size
    pip_size = _pip_size(sym_info)

    # Indicatori calcolati UNA VOLTA (D-12)
    indicators = compute_all_extended(bars)
    sr         = find_support_resistance(bars, lookback=cfg.SR_LOOKBACK_BARS)
    patterns   = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS) if cfg.ENABLE_CANDLESTICK_PATTERNS else []

    return StrategyContext(
        symbol=symbol, timeframe=cfg.INTRADAY_TIMEFRAME, profile=profile,
        sr=sr, regime=indicators.get("volatility_regime", "normal"),
        patterns=patterns, symbol_info=sym_info, pip_size=pip_size,
        intermarket_score_fn=intermarket_score_fn,
        news_blackout_fn=news_blackout_fn,
        _bars=bars, _indicators=indicators,
    )
```

---

### `strategy/adapters/backtest.py` (backtest context builder)

**Analog:** `tests/test_backtest_engine.py:22-40` (`_testing_cfg` + backtest engine call structure)

**Same output shape as `build_ctx_live`**, fed from `engine_state` instead of MT5:
```python
# Source: CONTEXT.md D-13 backtest drive-bar pattern
def build_ctx_backtest(
    symbol: str,
    engine_state: "EngineState",
    profile: str,
    intermarket_score_fn=None,
    news_blackout_fn=None,
) -> StrategyContext:
    bars       = engine_state.bars_so_far           # list[dict], already sliced bars[:i+1]
    indicators = engine_state.current_indicators    # compute_all_extended già chiamato da engine
    sr         = engine_state.sr
    patterns   = engine_state.patterns
    sym_info   = engine_state.symbol_info
    pip_size   = engine_state.pip_size
    return StrategyContext(
        symbol=symbol, timeframe=engine_state.timeframe, profile=profile,
        sr=sr, regime=engine_state.regime,
        patterns=patterns, symbol_info=sym_info, pip_size=pip_size,
        recent_trades=engine_state.recent_trades_for(symbol),
        intermarket_score_fn=intermarket_score_fn,
        news_blackout_fn=news_blackout_fn,
        _bars=bars, _indicators=indicators,
    )
```

---

### `strategy/risk_utils.py` (utility helpers moved from strategy.py)

**Analog:** `strategy.py:92-148` — **lift verbatim** (5 functions, zero logic change)

**Import-only change** (remove `from config import Config` since `Config` is passed in):
```python
# Source: strategy.py:35-47 (_pip_size, _pip_value_amount)
# Source: strategy.py:102-113 (estimate_position_risk_amount)
# Source: strategy.py:116-126 (estimate_proposal_risk_amount)
# Source: strategy.py:129-148 (estimate_proposal_lots)
# Lift verbatim — zero logic change. Only import path changes.
from models import PositionInfo, TradeProposal, AccountState
from config import Config
```

---

### `config/strategy.yaml` (new YAML config)

**Analog:** `data/configs/costs.yaml` (Phase 1) and `config/patterns.yaml` (Phase 3)

**YAML structure convention** — top-level keys (not `default:` + `symbols:` nesting; mirrors `patterns.yaml` flat top-level as confirmed in Phase 3 PATTERNS.md):
```yaml
# Source schema: CONTEXT.md D-08
# Loader analog: backtest/costs.py:42-59 (yaml.safe_load + or {})
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
    max_spread_atr_ratio: 0.20
    optional_session_bonus: 0.05

grade_map:
  "A+": 5
  "A":  4
  "B":  3
  "C":  2
  "reject": 1

base_confidence:
  "A+": 0.85
  "A":  0.70
  "B":  0.55
  "C":  0.40

adjusters:
  intermarket_confirmation: 0.05
  recent_winning_trade_same_pair: 0.05
  spread_tighter_than_baseline: 0.05
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

---

### `models.py` (modify — add `RiskProfile`)

**Analog:** `models.py:88-95` (existing `Literal` type alias pattern in `AgentCycleOutcome.outcome_type`)

**Add type alias after existing imports** (RESEARCH open question resolved — use string Literal, not enum):
```python
# Source: models.py:4 (typing import already present)
# Add after existing imports, before first @dataclass:
from typing import Literal

RiskProfile = Literal["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]
# Matches risk_engine.py:15-18 PROFILES dict keys exactly (verified).
```

---

### `tests/capture_regression_baseline.py` (one-time script)

**Analog:** `tests/test_backtest_engine.py:22-80` (CSV load + synthetic bar construction + Config setup)

**Script structure** (mirrors test_backtest_engine fixture loading style):
```python
# Source: tests/test_backtest_engine.py:22-40 (_testing_cfg config setup)
# Source: tests/conftest.py:43-48 (fixture path resolution via Path(__file__))
import json
import dataclasses
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Carica bars da CSV storica (mirror backtest.loader pattern)
# Esegue IntradayStrategy CORRENTE (pre-refactor) su 10 scenari
# Output: tests/fixtures/strategy_regression_baseline.json
```

**Mock MT5 with CSV data** (mirrors `conftest.py:14-40` MT5 stub + `test_backtest_engine.py` CSV path):
```python
# Source: tests/conftest.py:14-40 (MetaTrader5 stub pattern)
# Source: tests/test_backtest_engine.py:44-58 (_make_bar, _flat_bars shape)
def _mock_mt5_from_csv(csv_path: str, cap_at_bar: int) -> MagicMock:
    """Crea mock mt5_client che ritorna bars da CSV storica troncata a cap_at_bar."""
    from backtest.loader import load_bars
    bars = load_bars(Path(csv_path), symbol="EURUSD", timeframe="M15")
    bars = bars[:len(bars) + cap_at_bar]   # cap_at_bar è negativo
    bar_dicts = [{"time": b.time, "open": b.open, "high": b.high,
                  "low": b.low, "close": b.close, "tick_volume": b.volume}
                 for b in bars]
    mt5 = MagicMock()
    mt5.get_ohlc.return_value = bar_dicts
    mt5.get_symbol_info.return_value = SimpleNamespace(
        bid=bar_dicts[-1]["close"], ask=bar_dicts[-1]["close"] + 0.0001,
        point=0.00001, digits=5, trade_tick_value=10.0, trade_tick_size=0.00001,
    )
    return mt5
```

---

### `tests/test_strategy_setups.py` (detector unit tests)

**Analog:** `tests/test_strategy.py:99-184` (`identify_entry_setup` tests) — copy structure exactly

**Test file header + _make_cfg + _bar helpers** — copy verbatim from `tests/test_strategy.py:1-68`:
```python
# Source: tests/test_strategy.py:1-68 (imports + _make_cfg + _account + _bar)
"""Test detector setup puri (STRAT-01..04) — mock-free, < 500ms."""
import pytest
from strategy.setups.a_breakout import detect_a_breakout
from strategy.context import StrategyContext
from strategy.proposal import ProposalDraft
# ... (no MagicMock needed — detectors are pure fns)
```

**Test case pattern** (mirrors `test_identify_entry_setup_ready_buy` at `test_strategy.py:102-116`):
```python
# Source: tests/test_strategy.py:102-116
def test_detect_a_breakout_ready_buy():
    indicators = _make_indicators(...)   # stub ExtendedIndicators
    ctx = _make_ctx(sr={"resistance": 1.1050, "support": 1.0950}, ...)
    draft = detect_a_breakout(_bullish_breakout_bars(), indicators, ctx)
    assert draft.setup_type == "READY"
    assert draft.direction == "BUY"
    assert draft.grade in ("A+", "A", "B", "C")
    assert 0.0 <= draft.confidence <= 1.0
    assert draft.entry_price is not None
    assert draft.stop_loss_price is not None
    assert draft.take_profit_price is not None
```

**Near-miss / NONE test pattern** (mirrors `test_identify_entry_setup_none_weak_trend`):
```python
# Source: tests/test_strategy.py:154-168
def test_detect_a_breakout_none_no_breakout():
    draft = detect_a_breakout(flat_bars, indicators_no_break, ctx)
    assert draft.setup_type == "NONE"
    assert draft.reason != ""
```

---

### `tests/test_strategy_confluence.py` (scorer + grader + adjuster tests)

**Analog:** `tests/test_backtest_costs.py:9-47` (hand-calculated assertion style)

**Hand-calc fixture pattern** (copy from `test_backtest_costs.py:9-20`):
```python
# Source: tests/test_backtest_costs.py:9-20
def test_score_factors_all_true_gives_Aplus():
    """5/5 fatttori True → grade A+."""
    factors = {"trend_alignment": True, "setup_pattern": True, "momentum": True,
               "volatility_regime": True, "spread_session": True}
    assert grade_for(factors) == "A+"

def test_grade_for_3_gives_B():
    """3/5 fattori True → grade B."""
    factors = {k: (i < 3) for i, k in enumerate(
        ["trend_alignment", "setup_pattern", "momentum", "volatility_regime", "spread_session"])}
    assert grade_for(factors) == "B"

def test_confidence_Aplus_base():
    """Grade A+ → base_confidence = 0.85 (nessun adjuster)."""
    # usa ctx stub con tutti hook None e no recent_trades
    conf = compute_confidence("A+", _make_ctx_no_adjusters(), "A_breakout")
    assert abs(conf - 0.85) < 1e-4

def test_confidence_clamped_at_max():
    """Confidence non supera 0.95 neanche con tutti gli adjuster positivi."""
    conf = compute_confidence("A+", _make_ctx_all_positive_adjusters(), "A_breakout")
    assert conf <= 0.95
```

---

### `tests/test_strategy_proposal.py` (adapter + R:R + profile filter)

**Analog:** `tests/test_strategy.py:192-222` (`build_trade_proposal` tests) — copy structure

**Copy `build_trade_proposal` test shape** (test_strategy.py:192-222):
```python
# Source: tests/test_strategy.py:192-210
def test_draft_to_trade_proposal_valid():
    draft = ProposalDraft(
        setup_type="READY", setup_name="A_breakout", direction="BUY",
        entry_price=1.10800, stop_loss_price=1.10700, take_profit_price=1.10950,
        confidence=0.72, reason="breakout",
    )
    proposal = draft_to_trade_proposal(draft, "EURUSD", "M15")
    assert isinstance(proposal, TradeProposal)
    assert proposal.direction == "BUY"
    assert proposal.comment == "python_strategy"

def test_draft_to_proposal_rejects_non_ready():
    draft = ProposalDraft(setup_type="NONE", reason="weak")
    with pytest.raises(ValueError):
        draft_to_trade_proposal(draft, "EURUSD", "M15")
```

---

### `tests/test_strategy_purity.py` (AST introspection gate)

**Analog:** Phase 2 `tests/test_indicators_purity.py` plan (no file exists yet — use RESEARCH.md pattern)

**AST walk pattern** (from CONTEXT.md D-16 + RESEARCH §Pattern 5):
```python
# Source: CONTEXT.md D-16 + RESEARCH.md §Pattern 5 (AST purity gate)
import ast
import pathlib

FORBIDDEN_IMPORTS = {"mt5", "MetaTrader5", "requests", "sqlite3", "subprocess"}
PURE_MODULES = [
    "strategy/setups/a_breakout.py",
    "strategy/setups/b_reversal.py",
    "strategy/setups/c_compression.py",
    "strategy/setups/d_pullback.py",
    "strategy/confluence.py",
    "strategy/proposal.py",
    "strategy/context.py",
]

def test_strategy_purity_no_forbidden_imports():
    for mod in PURE_MODULES:
        source = pathlib.Path(mod).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in FORBIDDEN_IMPORTS, \
                        f"{mod}: import vietato '{alias.name}'"
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN_IMPORTS, \
                        f"{mod}: from-import vietato '{node.module}'"
```

---

### `tests/test_strategy_regression.py` (regression replay)

**Analog:** `tests/test_backtest_engine.py:1-80` (end-to-end engine test structure) + `tests/test_strategy.py:313-441` (end-to-end `analyze_symbol` tests)

**JSON fixture load + replay pattern:**
```python
# Source: tests/test_backtest_engine.py end-to-end style
# Source: tests/test_strategy.py:291-327 (analyze_symbol end-to-end)
import json
from pathlib import Path
import pytest
from strategy import IntradayStrategy

FIXTURE = Path("tests/fixtures/strategy_regression_baseline.json")

@pytest.mark.parametrize("scenario", json.loads(FIXTURE.read_text()))
def test_regression_replay(scenario, monkeypatch, tmp_path):
    # Ricrea mock mt5_client dal CSV + bar_offset
    mt5 = _mock_mt5_from_csv(scenario["input"]["csv"],
                              scenario["input"]["bar_offset"])
    strategy = IntradayStrategy(_testing_cfg(), mt5)
    setup = strategy.analyze_symbol(scenario["input"]["symbol"], _account())
    expected = scenario["output"]
    assert setup.setup_type == expected["setup_type"]
    assert setup.direction == expected["direction"]
    if expected["entry_price"] is not None:
        assert abs(setup.entry_price - expected["entry_price"]) < 1e-5
    assert abs(setup.confidence - expected["confidence"]) < 1e-4
```

---

## Shared Patterns

### S-1: Italian docstrings + English snake_case test names

**Source:** `strategy.py:1-6` (Italian module docstring) + `tests/test_strategy.py` (English test names)
**Apply to:** All `strategy/` submodules and `tests/test_strategy_*.py` files

```python
# Moduli: Italian docstring al top
"""Detector Setup A: rottura pulita di S/R orizzontale (STRAT-01)."""

# Test: English snake_case
def test_detect_a_breakout_ready_buy():
    ...
```

### S-2: `@dataclass(frozen=True)` + `__post_init__` for mutable defaults

**Source:** `backtest/costs.py:8` (`CostModel`) — already used in Phase 2 and Phase 3
**Apply to:** `ProposalDraft`, `StrategyContext`, `StrategyConfig`

```python
# Source: backtest/costs.py:8 + models.py pattern
@dataclass(frozen=True)
class XxxResult:
    ...
    mutable_field: dict = None

    def __post_init__(self):
        if self.mutable_field is None:
            object.__setattr__(self, "mutable_field", {})
```

### S-3: `dataclasses.replace()` for frozen dataclass modification

**Source:** CONTEXT.md D-06 (`evaluate_proposal_for_bar` loser logging)
**Apply to:** Any place where a `ProposalDraft` needs modification after creation

```python
# Source: stdlib dataclasses.replace — required for frozen dataclass
from dataclasses import replace
draft_with_losers = replace(winner, setup_specific={**winner.setup_specific, "losers": losers})
```

### S-4: YAML config loader with env override

**Source:** `backtest/costs.py:42-59` (exact pattern; copied in Phase 3 for `patterns.yaml`)
**Apply to:** `strategy/confluence.py` `load_strategy_config()` and `config/strategy.yaml`

```python
# Source: backtest/costs.py:42-50
if path is None:
    path = os.environ.get("STRATEGY_CONFIG_PATH") or DEFAULT_STRATEGY_CONFIG_PATH
with open(Path(path), encoding="utf-8") as f:
    raw = yaml.safe_load(f) or {}
```

### S-5: Confidence bound clamp `[min, max]`

**Source:** `strategy.py:638` (`min(max(total, 0.0), 1.0)`) — generalized to config bounds
**Apply to:** `strategy/confluence.py` `compute_confidence()` return

```python
# Source: strategy.py:638 — generalized
return round(max(cfg.bounds["min_confidence"], min(cfg.bounds["max_confidence"], raw)), 4)
```

### S-6: Guard for insufficient data → return NONE draft

**Source:** `strategy.py:187-188` + `strategy.py:212-214` (insufficient bars / indicators not ready)
**Apply to:** All 4 detector functions

```python
# Source: strategy.py:187-188 (insufficient bars guard)
if not bars or len(bars) < 50:
    return ProposalDraft(setup_type="NONE", reason="insufficient_bars")
# Source: strategy.py:212-214 (indicators not ready guard)
if atr_val is None or atr_val <= 0:
    return ProposalDraft(setup_type="NONE", reason="atr_not_ready")
```

### S-7: `MagicMock()` config builder for tests

**Source:** `tests/test_strategy.py:19-44` (`_make_cfg(**overrides)` pattern)
**Apply to:** `tests/test_strategy_setups.py`, `tests/test_strategy_confluence.py`, `tests/test_strategy_proposal.py`

```python
# Source: tests/test_strategy.py:19-44
def _make_cfg(**overrides):
    cfg = MagicMock()
    cfg.INTRADAY_TIMEFRAME = "M15"
    cfg.INTRADAY_LOOKBACK_BARS = 200
    # ... canonical defaults ...
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg
```

### S-8: MetaTrader5 stub in conftest.py

**Source:** `tests/conftest.py:14-40` (MT5 stub for CI machines without broker)
**Apply to:** `tests/conftest.py` (extend, not replace) for any new strategy fixtures

The existing stub in `tests/conftest.py:14-40` is already complete. New strategy tests simply inherit it. No changes to conftest needed unless new MT5 attributes are accessed.

### S-9: `_pip_size` utility

**Source:** `strategy.py:42-47` (`_pip_size(symbol_info)`)
**Apply to:** `strategy/risk_utils.py` (lift verbatim), `strategy/adapters/live.py` (import from risk_utils)

```python
# Source: strategy.py:42-47 — lift verbatim
def _pip_size(symbol_info) -> float:
    if symbol_info is None:
        return 0.0001
    point = getattr(symbol_info, "point", 0.0001) or 0.0001
    digits = getattr(symbol_info, "digits", 5)
    return point * 10 if digits in (3, 5) else point
```

---

## No Analog Found

All files have at least a role-match analog. The following patterns are **genuinely new** (no existing code equivalent — planner uses RESEARCH.md patterns instead):

| File / Pattern | Role | Data Flow | Reason No Analog |
|---|---|---|---|
| Counter-trend gate inside `b_reversal.py` | gating logic | transform | No reversal gating logic exists anywhere in current codebase |
| `_compute_levels_b/c/d` per-setup level formulae | ATR math | transform | Only Setup A logic exists in `strategy.py:573-604`; B/C/D are new |
| Multi-match resolution in `evaluate_proposal_for_bar` | orchestrator | request-response | No multi-detector pattern exists; single detector only |
| AST purity introspection in `test_strategy_purity.py` | static gate | test | First AST-based test in repo |
| `tests/fixtures/strategy_regression_baseline.json` | snapshot fixture | data | First JSON snapshot fixture (prior fixtures are CSV) |
| `strategy/adapters/backtest.py` | context builder | batch | No backtest-context adapter exists yet; Phase 5 engine not yet written |

---

## Metadata

**Analog search scope:** `C:\trading-agent\` root (flat), `backtest/`, `tests/`, `models.py`, `config/`, `.planning/phases/02-indicators-library/02-PATTERNS.md`, `.planning/phases/03-patterns-catalog/03-PATTERNS.md`
**Files scanned:** 14 source modules, 8 test files, 2 prior-phase PATTERNS.md, CONTEXT.md, RESEARCH.md
**Pattern extraction date:** 2026-05-07
**Phase:** 04-strategy-refactor
