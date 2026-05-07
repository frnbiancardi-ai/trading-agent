# Phase 4: Strategy Refactor — Research

**Researched:** 2026-05-07
**Domain:** Python pure-function strategy refactor — setup detectors, confluence scoring, ATR-based R:R, live/backtest convergence
**Confidence:** HIGH (all decisions pre-locked in CONTEXT.md; codebase fully inspected; skill playbooks extracted)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: `strategy/` package layout with submodules (setups/a_b_c_d, confluence, proposal, context, adapters/live+backtest)
- D-02: Pure-fn detector signature `detect_<name>(bars, indicators, ctx) -> ProposalDraft` (always returns Draft, never None)
- D-03: `ProposalDraft` frozen dataclass with `setup_type`, `setup_name`, `direction`, `entry_price`, `stop_loss_price`, `take_profit_price`, `factors: dict[str, bool]`, `grade`, `confidence`, `reason`, `rationale_parts`, `setup_specific`
- D-04: `StrategyContext` frozen dataclass with `symbol`, `timeframe`, `profile`, `sr`, `regime`, `patterns`, `symbol_info`, `pip_size`, plus optional adjuster stubs
- D-05: Two adapters — `adapters/live.py::build_ctx_live()` and `adapters/backtest.py::build_ctx_backtest()` with identical output shape
- D-06: `evaluate_proposal_for_bar()` runs all 4 detectors, picks highest grade; tie-break A>C>B>D; losers logged in `setup_specific["losers"]`
- D-07: Setup B counter-trend gating — emits READY only if grade A or A+; grade B/C against ema50_slope downgrades to NONE with reason `counter_trend_below_A_grade`
- D-08: All thresholds in `config/strategy.yaml`; `load_strategy_config()` frozen dataclass; env override `STRATEGY_CONFIG_PATH`
- D-09: Phase 10 adjuster stubs — `intermarket_score_fn` and `news_blackout_fn` default None → zero impact
- D-10: Per-setup `_compute_levels` with 1.5×ATR cap, 0.3–0.5×ATR buffer, setup-specific TP anchors
- D-11: Confidence calibration via `config/strategy.yaml` `base_confidence` + `adjusters` — existing `_score_confidence` removed atomically
- D-12: Adapters call `compute_all_extended(bars)` once per bar; snapshot passed to all 4 detectors
- D-13: Backtest drive-bar pattern — `bars[:i+1]` slice prevents future leakage by construction
- D-14: Regression fixture Wave 0 — `tests/capture_regression_baseline.py` → `tests/fixtures/strategy_regression_baseline.json` committed BEFORE touching `strategy.py`
- D-15: Engineering principles — bar boundaries sacred, pure-function strategy layer, idempotent + observable, calibration over confidence
- D-16: Test strategy — `test_strategy_setups.py` (4 files), `test_strategy_confluence.py`, `test_strategy_proposal.py`, `test_strategy_purity.py` (AST), `test_strategy_regression.py`

### Claude's Discretion
None specified — all areas were locked in discussion.

### Deferred Ideas (OUT OF SCOPE)
- ML-driven setup ranking (Phase 8)
- Per-symbol strategy.yaml overrides (Phase 5 backtest reveals)
- Vectorized detector (Phase 5 if backtest slow)
- Detector ensemble voting (Phase 8+)
- Real-time multi-TF confluence full use (Phase 6)
- DeprecationWarning on IntradayStrategy (Phase 6/8)
- Setup E (channel/range trading)
- Confidence calibration ML-based (Phase 7)
- Failed breakout auto-flip to Setup C (requires user-confirm)
- Strict purity enforcement runtime decorator (AST only in Phase 4)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STRAT-01 | Setup A (Breakout) detector — pure function, takes bars+indicators, returns proposal-ready output | D-02 signature, D-10 SL/TP, skill `setup_playbook.md` Setup A mechanics |
| STRAT-02 | Setup B (S/R Reversal) detector — pure function | D-07 counter-trend gate, skill Setup B mechanics, PatternHit from Phase 3 |
| STRAT-03 | Setup C (Compression Breakout) detector — pure function | D-10 compression SL/TP, skill Setup C mechanics, NR4/NR7 from Phase 2 |
| STRAT-04 | Setup D (Trend Pullback) detector — pure function | D-10 pullback SL/TP, skill Setup D mechanics, EMA50/Fib from Phase 2 |
| STRAT-05 | 5-factor confluence scorer (trend/setup/momentum/volatility/spread+session) | D-08 config schema, skill confluence checklist (5 factors, grade A+/A/B/C/reject) |
| STRAT-06 | Confidence calibrator: grade → starting confidence + ±0.05 adjusters | D-08 base_confidence + adjusters schema, skill confidence table |
| STRAT-07 | ATR-based R:R proposal builder with profile-aware minimums | D-10 per-setup levels, D-08 profile_filters (CONSERVATIVE 2.5/MODERATE 1.8/AGGRESSIVE 1.3) |
| STRAT-08 | Strategy module side-effect-free (no broker calls, no DB writes, no print/log) | D-15 pure-fn principle, D-16 AST test |
| STRAT-09 | Same strategy module called by live loop AND backtest engine (no fork) | D-05 adapters, D-06 evaluate_proposal_for_bar, D-13 backtest drive-bar pattern |
</phase_requirements>

---

## Summary

Phase 4 refactors `strategy.py` (737 lines, single monolithic `IntradayStrategy` class with broker calls inline and a single breakout-trend path) into a `strategy/` package of pure functions. The architecture is entirely pre-decided in CONTEXT.md via a thorough discussion phase; research confirms the codebase state, verifies skill content, and fills in implementation-level gaps not resolved in discussion.

The current `strategy.py` contains only Setup A logic (breakout with trend-alignment check), a single `_compute_levels` function shared across all directions, and `_score_confidence` with weights that do not match the forex-trader-pro skill table. Setups B/C/D do not exist at all. The `patterns.py` module is pre-Phase 3 (returns raw bool `is_hammer()` etc., not `PatternHit` dataclasses). `indicators.py` is still flat pre-Phase 2. Phase 4 must be planned for the state _as delivered by Phases 2 and 3_, not the current flat state.

The regression fixture (D-14) is the most critical Wave 0 task: it must capture current behavior before any code changes, because the new code's confidence values will differ (new calibration model vs. old `_score_confidence`). The regression test uses a `1e-4` tolerance on confidence — if the new code drifts more than that, it is a bug, not legitimate drift.

**Primary recommendation:** Follow the locked CONTEXT.md decisions exactly. The primary risk is not architectural (fully designed) but operational: capture the regression baseline first, restructure as a package second, and implement detectors third in setup priority order (A then D then C then B, from simplest to most complex).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Setup detection (A/B/C/D) | Strategy (pure) | — | Pure function, no I/O, testable in isolation |
| Indicator computation | Data/Indicators layer (Phase 2) | — | Pre-computed once by adapter, consumed by detectors |
| Confluence scoring | Strategy (pure) | — | Reads pre-computed indicator snapshot only |
| Confidence calibration | Strategy (pure) | — | Config-driven formula, no external state |
| R:R level computation | Strategy (pure) | — | ATR math, no broker call |
| Context assembly (live) | Live adapter | MT5 broker | Fetches bars, indicators, SR, regime, patterns |
| Context assembly (backtest) | Backtest adapter | BacktestEngine | Same output shape as live adapter |
| Multi-detector orchestration | Strategy `evaluate_proposal_for_bar` | — | Runs all 4, picks winner, logs losers |
| Sentiment adjustment | IntradayStrategy shim | — | Legacy path, stays in non-pure shim layer |
| Broker calls / order execution | Execution layer | MT5 | Strictly outside strategy package |
| Regression fixture capture | Test utility (Wave 0) | — | One-time script before code changes |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python dataclasses | stdlib | `ProposalDraft`, `StrategyContext` frozen dataclasses | Zero dependencies, hashable, mypy-safe |
| PyYAML | already in requirements (Phase 3 confirmed) | `config/strategy.yaml` load | Same pattern as `config/patterns.yaml` Phase 3 |
| `ast` module | stdlib | AST-based purity test in `test_strategy_purity.py` | No dependency, introspects source |
| `dataclasses.replace` | stdlib | Produce modified ProposalDraft without mutation | Correct pattern for frozen dataclass update |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `typing.Literal` | stdlib | Typed literals for `setup_type`, `grade`, `direction` | All `ProposalDraft` and `StrategyContext` fields |
| `typing.Callable` | stdlib | Type hints for adjuster function stubs in `StrategyContext` | D-09 intermarket/news hook typing |
| `dataclasses.field` | stdlib | `default_factory=list` for `recent_trades` in `StrategyContext` | Mutable default handling |

### No New Runtime Dependencies
[VERIFIED: CONTEXT.md canonical_refs section] — "Nessuna nuova dipendenza runtime. Solo PyYAML (già usato da `config/patterns.yaml` Phase 3)."

**Installation:** No new packages needed.

**Version verification:** `python3 -c "import yaml; print(yaml.__version__)"` — PyYAML already installed.

---

## Architecture Patterns

### System Architecture Diagram

```
               Live Scheduler              Backtest Engine
                    │                           │
          build_ctx_live(symbol,mt5,...)    build_ctx_backtest(symbol,engine_state,...)
                    │                           │
                    └──────────┬────────────────┘
                               │
                         StrategyContext
                     (symbol, tf, profile, sr,
                      regime, patterns, pip_size,
                      adjuster_stubs...)
                               │
                               ▼
                  evaluate_proposal_for_bar(bars, indicators, ctx)
                               │
               ┌───────────────┼───────────────┐
               │               │               │               │
         detect_a_        detect_b_        detect_c_       detect_d_
         breakout()       reversal()     compression()    pullback()
               │               │               │               │
        ProposalDraft    ProposalDraft   ProposalDraft   ProposalDraft
         (READY/          (READY/ gate   (READY/          (READY/
         FORMING/         counter-trend) FORMING/         FORMING/
         NONE)            + PatternHit)  NONE + NR7)      NONE + Fib)
               └───────────────┼───────────────┘
                               │
                   multi-match: highest grade wins
                   tie-break: A > C > B > D
                   losers logged in setup_specific["losers"]
                               │
                         ProposalDraft (winner)
                               │
                 ┌─────────────┴─────────────────┐
                 │ (live path)                    │ (backtest path)
                 ▼                                ▼
         draft_to_trade_proposal()        engine.process_draft()
                 │                                │
         _apply_sentiment()             fill simulation + ledger
                 │
         TechnicalSetup (to scheduler)
```

### Recommended Project Structure
```
strategy/
├── __init__.py                   # re-exports: IntradayStrategy, evaluate_proposal_for_bar,
│                                 #   ProposalDraft, StrategyContext
├── context.py                    # StrategyContext dataclass
├── proposal.py                   # ProposalDraft dataclass + draft_to_trade_proposal()
│                                 #   + draft_to_technical_setup()
├── confluence.py                 # score_factors(), grade_for(), compute_confidence()
├── setups/
│   ├── __init__.py               # ALL_DETECTORS list
│   ├── a_breakout.py             # detect_a_breakout() + _compute_levels_a()
│   ├── b_reversal.py             # detect_b_reversal() + _compute_levels_b()
│   ├── c_compression.py          # detect_c_compression() + _compute_levels_c()
│   └── d_pullback.py             # detect_d_pullback() + _compute_levels_d()
├── adapters/
│   ├── __init__.py
│   ├── live.py                   # build_ctx_live(symbol, mt5_client, profile, **hooks)
│   └── backtest.py               # build_ctx_backtest(symbol, engine_state, profile, **hooks)
└── risk_utils.py                 # estimate_position_risk_amount,
                                  #   estimate_proposal_risk_amount,
                                  #   estimate_proposal_lots (moved from strategy.py)

config/
└── strategy.yaml                 # D-08 schema

tests/
├── capture_regression_baseline.py   # Wave 0 one-time script
├── fixtures/
│   └── strategy_regression_baseline.json  # Wave 0 output
├── test_strategy_setups.py           # 4×detector unit tests
├── test_strategy_confluence.py       # 5-factor scoring + grade + adjusters
├── test_strategy_proposal.py         # ProposalDraft→TradeProposal + profile filter + R:R
├── test_strategy_purity.py           # AST introspection purity gate
└── test_strategy_regression.py       # replay 10 fixtures, assert identical output
```

### Pattern 1: Pure-Function Detector (Setup A as exemplar)
**What:** Every setup detector is a stateless function. It reads snapshot fields, applies geometric conditions, calls `score_factors()` and `compute_confidence()`, computes levels, and returns a `ProposalDraft`. Zero side effects.
**When to use:** All 4 setup detectors (STRAT-01..04).
```python
# Source: CONTEXT.md D-02 + D-10 + forex-algo-dev/references/strategy_patterns.md
def detect_a_breakout(
    bars: list[dict],
    indicators: "ExtendedIndicators",
    ctx: "StrategyContext",
) -> "ProposalDraft":
    """Setup A: rottura pulita di S/R orizzontale o trendline.

    Fattori confluence controllati:
      1. trend_alignment: ema50_slope coerente con direction
      2. setup_pattern: closing_score >75 (long) o <25 (short) sulla breakout bar
      3. momentum: RSI non in zona di esaurimento contro la direzione
      4. volatility_regime: espanso o normale (non compresso)
      5. spread_session: spread/atr <= 0.20
    """
    atr_val = indicators.atr_14[-1]  # solo bar[-1], mai bar[0]
    if atr_val is None or atr_val <= 0:
        return ProposalDraft(setup_type="NONE", reason="atr_not_ready", ...)
    # ... geometric detection ...
    factors = score_factors("A_breakout", indicators, ctx, direction)
    grade = grade_for(factors)
    if grade == "reject":
        return ProposalDraft(setup_type="NONE", reason="confluence_below_2_factors", ...)
    entry, sl, tp = _compute_levels_a(direction, broken_level, atr_val, ctx)
    rr = abs(tp - entry) / abs(entry - sl)
    if rr < ctx.profile.min_rr:
        return ProposalDraft(setup_type="NONE", reason=f"rr_below_min_{rr:.2f}", ...)
    confidence = compute_confidence(grade, ctx, setup_name="A_breakout")
    return ProposalDraft(
        setup_type="READY", setup_name="A_breakout", direction=direction,
        entry_price=entry, stop_loss_price=sl, take_profit_price=tp,
        factors=factors, grade=grade, confidence=confidence,
        reason="break_above_resistance_with_expanded_atr",
        rationale_parts={"break_level": str(broken_level), "atr": str(atr_val)},
        setup_specific={"breakout_level": broken_level},
    )
```

### Pattern 2: Multi-Detector Orchestrator
**What:** Runs all 4 detectors on the same bar (same `indicators` snapshot), picks winner by grade then priority.
**When to use:** Called by both live adapter and backtest engine — the single shared code path (STRAT-09).
```python
# Source: CONTEXT.md D-06
from dataclasses import replace
from strategy.setups import ALL_DETECTORS  # [detect_a_breakout, detect_b_reversal, ...]

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
        if forming:
            winner = min(forming, key=lambda d: PRIORITY.get(d.setup_name or "", 99))
        else:
            winner = drafts[0]  # NONE — Setup A's reason is canonical
        losers = [d for d in drafts if d is not winner]
        return replace(winner, setup_specific={**(winner.setup_specific or {}), "losers": losers})
    winner = min(ready, key=lambda d: (GRADE_ORDER[d.grade], PRIORITY[d.setup_name]))
    losers = [d for d in drafts if d is not winner]
    return replace(winner, setup_specific={**winner.setup_specific, "losers": losers})
```

### Pattern 3: BackwardCompat Shim
**What:** `IntradayStrategy.analyze_symbol()` becomes a thin wrapper — builds ctx via live adapter, calls `evaluate_proposal_for_bar`, converts draft, applies legacy `_apply_sentiment`.
**When to use:** Scheduler/MCP callers — signature unchanged.
```python
# Source: CONTEXT.md D-01 + specifics section
class IntradayStrategy:
    def analyze_symbol(self, symbol, account_state, sentiment=None) -> TechnicalSetup:
        # Non-pure wrapper — side-effects are fine here (broker calls, logging)
        ctx = build_ctx_live(
            symbol, self.mt5, profile=self.cfg.RISK_MODE,
            intermarket_score_fn=None,
            news_blackout_fn=self.env.is_news_window,
        )
        bars, indicators = ctx._bars, ctx._indicators  # stored in ctx by adapter
        draft = evaluate_proposal_for_bar(bars, indicators, ctx)
        setup = draft_to_technical_setup(draft, symbol, self.cfg.INTRADAY_TIMEFRAME)
        return self._apply_sentiment(setup, sentiment)
```

### Pattern 4: Config-Driven Confluence Scoring
**What:** `score_factors()` reads thresholds from `StrategyConfig` (loaded from `config/strategy.yaml`), returns `dict[str, bool]` of 5 factor booleans.
**When to use:** All 4 detectors call this before grading.
```python
# Source: CONTEXT.md D-08
def score_factors(
    setup_name: str,
    indicators: "ExtendedIndicators",
    ctx: "StrategyContext",
    direction: str,
) -> dict[str, bool]:
    cfg = load_strategy_config()  # cached singleton
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

### Pattern 5: AST Purity Gate
**What:** Introspects source files of pure modules to assert no forbidden imports or calls.
**When to use:** `tests/test_strategy_purity.py` (STRAT-08 enforcement).
```python
# Source: CONTEXT.md D-16 + forex-algo-dev skill principle #3
import ast, pathlib

FORBIDDEN_IMPORTS = {"mt5", "MetaTrader5", "requests", "sqlite3", "subprocess"}
FORBIDDEN_CALLS   = {"logging.getLogger", "print", "open"}
PURE_MODULES      = [
    "strategy/setups/a_breakout.py", "strategy/setups/b_reversal.py",
    "strategy/setups/c_compression.py", "strategy/setups/d_pullback.py",
    "strategy/confluence.py", "strategy/proposal.py", "strategy/context.py",
]

def test_strategy_purity():
    for module_path in PURE_MODULES:
        source = pathlib.Path(module_path).read_text()
        tree   = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in FORBIDDEN_IMPORTS, \
                        f"{module_path}: forbidden import {alias.name}"
            # ... check ast.ImportFrom and ast.Call nodes for logging.getLogger etc.
```

### Anti-Patterns to Avoid
- **Shared mutable state in detector**: detectors must be pure — never store state on `self` or module globals. Config singleton is acceptable if loaded at import time from YAML.
- **Calling `get_symbol_info` inside a detector**: this is a broker call — belongs in the adapter only. Adapter pre-resolves `pip_size` and `symbol_info` into `StrategyContext`.
- **Computing `compute_all_extended` inside a detector**: the adapter computes indicators ONCE per bar. Four detectors on the same bar = 1 compute, not 4.
- **Sliding window that reads `bars[i+1]`**: bar boundaries are sacred. Detector sees `bars` as `bars_so_far = full[:i+1]`; never peek forward.
- **Confidence > 0.95 or < 0.10**: clamp via `max(0.10, min(0.95, computed))` always — the skill explicitly states "never claim 1.0".
- **Grade in confidence formula**: grade maps to `base_confidence` from config, then adjusters applied. Do not multiply confidence by confluence count directly.
- **`isinstance` check on pattern dicts**: Phase 3 delivers `PatternHit` frozen dataclasses; use `.name`, `.direction`, `.bar_index`, `.extreme_price`, `.confidence` attributes — not dict keys.

---

## 5-Factor Confluence Model

Source: `forex-trader-pro/SKILL.md` confluence checklist + CONTEXT.md D-08. [VERIFIED: extracted from skill via zipfile]

### The 5 Factors

| # | Factor | What Is Checked | Passes When |
|---|--------|-----------------|-------------|
| 1 | `trend_alignment` | EMA50 slope vs trade direction | Slope agrees with direction OR (slope disagrees AND grade is A/A+) |
| 2 | `setup_pattern` | Setup geometry is complete | Pattern is fully formed (half-formed = False) |
| 3 | `momentum` | RSI position and slope | Not in exhaustion zone against direction; divergence satisfies reversal |
| 4 | `volatility_regime` | ATR percentile regime vs setup type | Breakout/D-pullback: expanded/normal; Compression: compressed; Reversal: normal/expanded |
| 5 | `spread_session` | spread vs ATR ratio | `spread / (1×ATR) <= 0.20` (1 pip spread on 5-pip ATR = 0.20 = boundary) |

### Grade Map (from skill table)

| Confluences (True factors out of 5) | Grade |
|:---:|:---:|
| 5 | A+ |
| 4 | A |
| 3 | B |
| 2 | C |
| ≤1 | reject |

### Base Confidence (from skill, confirmed in D-08)

| Grade | Starting Confidence |
|:---:|:---:|
| A+ | 0.85 |
| A | 0.70 |
| B | 0.55 |
| C | 0.40 |

### Adjusters (±0.05 each, cumulative, capped at [0.10, 0.95])

| Condition | Delta |
|-----------|:-----:|
| Intermarket confirmation present (`intermarket_score_fn` returns > 0) | +0.05 |
| Recent winning trade on same pair AND same direction (last 5) | +0.05 |
| Spread tighter than `spread_baseline_pips` | +0.05 |
| Macro event within 60 minutes (`news_blackout_fn` / calendar) | -0.05 |
| Last 2 trades on same pair were losses | -0.05 |
| Proposing against medium-term trend | -0.05 |

### Profile Filters (gate applied after draft is returned)

| Profile | Min Grade | Min R:R | Min Confidence |
|---------|:---:|:---:|:---:|
| CONSERVATIVE | A | 2.5 | 0.65 |
| MODERATE | B | 1.8 | 0.50 |
| AGGRESSIVE | C | 1.3 | 0.40 |

Note: CONTEXT.md D-08 uses "MODERATE" but `risk_engine.py` PROFILES dict uses "MODERATE". The skill table and CONTEXT.md D-08 `profile_filters` use "CONSERVATIVE/MODERATE/AGGRESSIVE" — planner must ensure `RiskProfile` enum values match `PROFILES` dict keys in `risk_engine.py`. [VERIFIED: `risk_engine.py` has `PROFILES = {"CONSERVATIVE":..., "MODERATE":..., "AGGRESSIVE":...}`].

---

## ATR-Based R:R Proposal Builder

Source: CONTEXT.md D-10 + `forex-trader-pro/references/setup_playbook.md`. [VERIFIED: extracted from skill]

### Universal Rules (all setups)
- **SL cap**: distance from entry to SL must not exceed `1.5 × ATR(14)` at decision time
- **Buffer**: structural level gets `0.3–0.5 × ATR` buffer (never place SL exactly on the level)
- **R:R floor**: from `profile_filters[profile].min_rr` in `config/strategy.yaml`

### Per-Setup Level Computation

#### Setup A (Breakout) — `_compute_levels_a()`
```
direction = BUY (break above resistance):
  entry = last_close (close of breakout bar)
  sl    = broken_level - 0.4×ATR          (inside prior range, below the level)
  sl    = max(sl, entry - 1.5×ATR)        (ATR cap enforced)
  tp    = next_swing_high  OR  entry + 2.5×ATR  (whichever is farther and realistic)
  R:R   = (tp - entry) / (entry - sl), must >= profile.min_rr

direction = SELL (break below support):
  sl    = broken_level + 0.4×ATR
  sl    = min(sl, entry + 1.5×ATR)
  tp    = next_swing_low  OR  entry - 2.5×ATR
```

#### Setup B (S/R Reversal) — `_compute_levels_b()`
```
direction = BUY (bounce from support):
  entry = close of reversal bar (or break of reversal bar's high for confirmation)
  sl    = reversal_bar_extreme_low - 0.3×ATR
  sl    = max(sl, entry - 1.5×ATR)
  tp    = opposite end of recent range OR prior swing high
  extreme stored in ProposalDraft.setup_specific["reversal_bar_extreme"]

direction = SELL:
  sl    = reversal_bar_extreme_high + 0.3×ATR
  tp    = opposite end of range OR prior swing low
```

#### Setup C (Compression Breakout) — `_compute_levels_c()`
```
compression_range = (compression_low, compression_high)
  stored in setup_specific["compression_range"]

direction = BUY (break above compression_high):
  entry = compression_high (stop order trigger price, treated as entry)
  sl    = compression_low - 0.3×ATR         (opposite side of range)
  sl    = max(sl, entry - 1.5×ATR)
  tp    = entry + 2×(compression_high - compression_low)  [2× range expansion]
  secondary_tp = entry + 3×range  (trail rest)

direction = SELL:
  sl = compression_high + 0.3×ATR
  tp = entry - 2×range
```

#### Setup D (Trend Pullback) — `_compute_levels_d()`
```
direction = BUY:
  entry = close of continuation pattern bar
  sl    = pullback_low - 0.3×ATR            (below pullback extreme)
  sl    = max(sl, entry - 1.5×ATR)
  tp    = prior_swing_high                  (primary)
  tp    = entry + 1.618 × leg_size          (Fib extension, if no swing)
  pullback_low stored in setup_specific["pullback_low"]

direction = SELL:
  sl    = pullback_high + 0.3×ATR
  tp    = prior_swing_low  OR  entry - 1.618 × leg_size
```

---

## Setup Detector Contracts

Source: CONTEXT.md D-02 + D-07 + skill `setup_playbook.md`. [VERIFIED: playbook extracted]

### Setup A — Breakout (`strategy/setups/a_breakout.py`)

**Identification criteria:**
1. Prior N bars (configurable, ~20) establish a horizontal resistance (highest high) or support (lowest low)
2. Last closed bar closes beyond the level with Closing Score >75 (BUY) or <25 (SELL) [INDIC-11]
3. Volatility regime is `expanded` or `normal` (not `compressed`) [INDIC-14]
4. `check_breakout_quality()` returns `"CLEAN"` (not `"WEAK"` or `"NONE"`)

**Confluence factors:**
- trend_alignment: EMA50 slope in direction of break
- setup_pattern: closing_score passes threshold (>75 or <25)
- momentum: RSI not stretched against direction (not >75 for BUY, not <25 for SELL)
- volatility_regime: expanded or normal
- spread_session: spread/atr <= 0.20

**ExtendedIndicators fields used:** `ema50`, `ema50_slope`, `rsi_14`, `atr_14`, `closing_score`, `volatility_regime`, `donchian_high`, `donchian_low`

**FORMING condition:** price within `SR_TOLERANCE_PIPS × pip_size` of the level, not yet broken

### Setup B — S/R Reversal (`strategy/setups/b_reversal.py`)

**Identification criteria:**
1. Price at a defined S/R zone (from `ctx.sr`)
2. A `PatternHit` from `ctx.patterns` with matching direction at the level (bar_index recent enough)
3. RSI in stretched zone (>70 for resistance test, <30 for support test) OR RSI divergence
4. Counter-trend gate (D-07): if direction is against `ema50_slope`, grade must be A or A+; otherwise emit NONE

**Confluence factors:**
- trend_alignment: direction with trend OR (against trend AND grade A/A+)
- setup_pattern: `PatternHit` exists at level (any of: hammer, engulfing, morning_star, shooting_star, key_reversal, pin_bar, inverted_hammer, evening_star)
- momentum: RSI divergence present OR RSI in stretched zone
- volatility_regime: normal or expanded
- spread_session: spread/atr <= 0.20

**ExtendedIndicators fields used:** `ema50_slope`, `rsi_14`, `atr_14`, `volatility_regime`
**Pattern fields used:** `ctx.patterns` (list[PatternHit] from Phase 3)

**FORMING condition:** price approaching S/R zone but no reversal pattern yet

### Setup C — Compression Breakout (`strategy/setups/c_compression.py`)

**Identification criteria:**
1. NR4 or NR7 detected [INDIC-10] OR Bollinger squeeze (`bbw < threshold`) [INDIC-01]
2. At least 3 bars of compression (not a single quiet bar)
3. Ideally at a meaningful location (near S/R or session open)
4. Prior trend bias determines directional preference

**Confluence factors:**
- trend_alignment: trend direction exists (EMA50 slope non-zero for preferred direction)
- setup_pattern: NR4/NR7 confirmed OR BB squeeze confirmed
- momentum: RSI not at extreme opposite to break direction
- volatility_regime: compressed (required for this setup)
- spread_session: spread/atr <= 0.20

**ExtendedIndicators fields used:** `nr_detect` (NRResult), `bollinger_bands` (BollingerResult.squeeze), `atr_14`, `ema50_slope`, `volatility_regime`, `rsi_14`

**FORMING condition:** 2 compression bars observed, waiting for 3rd confirmation

### Setup D — Trend Pullback (`strategy/setups/d_pullback.py`)

**Identification criteria:**
1. Established trend: EMA50 with clear slope, price above/below EMA50 for ≥5 bars
2. Recent impulse leg identifiable (5–15 bars)
3. Pullback to EMA20 or Fib 38.2/50/61.8% of prior leg [INDIC-08]
4. Continuation pattern at pullback: flag consolidation, or small reversal candle in trend direction

**Confluence factors:**
- trend_alignment: always True for D (trend-following by definition)
- setup_pattern: continuation pattern present at pullback
- momentum: RSI rolling in trend direction after pullback
- volatility_regime: normal (required — expanded indicates impulse not pullback)
- spread_session: spread/atr <= 0.20

**ExtendedIndicators fields used:** `ema20`, `ema50`, `ema50_slope`, `rsi_14`, `atr_14`, `fibonacci` (FibonacciResult), `volatility_regime`

**No counter-trend gate needed** — D is always trend-following.

---

## Shared `evaluate_proposal_for_bar` Signature

**Purpose:** Single function called identically by live scheduler and backtest engine (STRAT-09).

```python
# strategy/__init__.py
def evaluate_proposal_for_bar(
    bars: list[dict],
    indicators: "ExtendedIndicators",   # pre-computed by adapter once per bar
    ctx: "StrategyContext",
) -> "ProposalDraft":
    ...
```

**Contract:**
- `bars`: list of closed bar dicts, ordered oldest→newest, `bars[-1]` is the bar just closed
- `indicators`: snapshot returned by `compute_all_extended(bars)` — computed by caller ONCE
- `ctx`: `StrategyContext` with all side-inputs pre-assembled by adapter
- Returns: exactly one `ProposalDraft` (never None, never raises except on unrecoverable input error)

**Backtest call site (D-13):**
```python
# backtest/engine.py
for i in range(lookback, len(all_bars)):
    bars_so_far = all_bars[:i+1]              # no future leakage by construction
    indicators  = compute_all_extended(bars_so_far)
    ctx         = build_ctx_backtest(symbol, engine_state.at(i), profile)
    draft       = evaluate_proposal_for_bar(bars_so_far, indicators, ctx)
    engine_state.process(draft)
```

**Live call site (via shim):**
```python
# strategy/adapters/live.py called from IntradayStrategy.analyze_symbol()
bars       = mt5_client.get_ohlc(symbol, timeframe, cfg.INTRADAY_LOOKBACK_BARS)
indicators = compute_all_extended(bars)
ctx        = build_ctx_live(symbol, mt5_client, ...)
draft      = evaluate_proposal_for_bar(bars, indicators, ctx)
```

---

## Regression Fixture Approach (SC-5)

Source: CONTEXT.md D-14. [VERIFIED: current strategy.py inspected, data/historical/ confirmed present]

### Wave 0 Mandatory Sequence

1. **Commit current `strategy.py` state** (no changes) — git snapshot of pre-refactor behavior
2. **Run `tests/capture_regression_baseline.py`** — captures 10 scenarios to JSON
3. **Commit `tests/fixtures/strategy_regression_baseline.json`** — before ANY code changes to `strategy.py`
4. Only then: begin `strategy/` package creation

### Fixture Structure

```json
[
  {
    "scenario_id": 1,
    "symbol": "EURUSD",
    "csv": "data/historical/EURUSD/M15.csv",
    "bar_offset": -200,
    "expected_mix": "READY",
    "input": {
      "bar_count": 200,
      "last_bar_time": "2026-01-10T14:15:00Z"
    },
    "output": {
      "setup_type": "READY",
      "direction": "BUY",
      "entry_price": 1.08234,
      "stop_loss": 1.07891,
      "take_profit": 1.08920,
      "confidence": 0.6500,
      "reason": "trend_strength=0.72, MAs allineate..."
    }
  }
  // ... 9 more scenarios
]
```

### 10-Scenario Mix Design

| # | Symbol | bar_offset | Expected Type | Rationale |
|---|--------|:---------:|:---:|-----------|
| 1 | EURUSD | -200 | READY | Recent strong trend bar |
| 2 | EURUSD | -350 | READY | Another READY to cover SELL path |
| 3 | EURUSD | -500 | READY | Third READY |
| 4 | GBPUSD | -200 | FORMING | Near resistance |
| 5 | GBPUSD | -400 | FORMING | Near support |
| 6 | EURUSD | -150 | NONE | ATR out of range |
| 7 | USDJPY | -200 | NONE | RSI overbought |
| 8 | USDJPY | -350 | NONE | trend/alignment weak |
| 9 | GBPUSD | -300 | NONE | No clear setup |
| 10 | USDJPY | -500 | mixed | Edge case |

**Note:** Phase 4 must discover actual output types by running the capture script — the "Expected Type" above is intent, not guarantee. The regression test asserts the NEW code produces IDENTICAL output to whatever the capture script produces.

### Tolerance
- `float` prices: `abs(new - baseline) < 1e-5`
- `confidence`: `abs(new - baseline) < 1e-4`
- `setup_type`, `direction`: exact string match
- `reason`: exact string match OR configurable to prefix match

### Confidence Delta Risk (Hot Spot)
Current `_score_confidence` uses weights (trend×0.3, pattern×0.2, volume×0.2, rr×0.2, mtf×0.1) that differ from the skill table base_confidence values (A+=0.85, A=0.70, B=0.55, C=0.40). The REGRESSION TEST WILL LIKELY FAIL on confidence values after refactor. The plan must include a reconciliation task:

**If confidence delta > 1e-4:** the regression test reveals intentional behavioral change (new calibration model). The plan must add a task that records the expected delta, validates it is directionally correct (new values more calibrated), and updates the fixture to the new values BEFORE the regression test gates the wave.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ATR computation | Custom ATR function | `atr()` from `indicators.py` (or `indicators/volatility.py` Phase 2) | Already exists, tested, matches backtest path |
| S/R detection | New S/R finder | `find_support_resistance()` from `indicators.py` | Already used by current strategy.py |
| Breakout quality | New breakout checker | `check_breakout_quality()` from `indicators.py` | Already exists |
| Closing Score | Hand-compute `(close-low)/range` | `ClosingScoreResult` from Phase 2 `indicators/bars.py` (INDIC-11) | Canonical Defendi formula |
| NR4/NR7 | Range comparison loop | `NRResult` from Phase 2 `indicators/bars.py` (INDIC-10) | Already correct semantics |
| Fibonacci levels | Manual level math | `FibonacciResult` from Phase 2 `indicators/structure.py` (INDIC-08) | Retracement levels pre-computed |
| YAML config parse | Custom parser | `yaml.safe_load()` + frozen dataclass, same pattern as `config/patterns.yaml` (Phase 3) | Established project pattern |
| Risk amount estimate | New calc | `estimate_proposal_risk_amount()` (moving from strategy.py to `strategy/risk_utils.py`) | Already correct, just relocating |
| Profile thresholds | Hardcoded constants | `config/strategy.yaml` `profile_filters` + `load_strategy_config()` | Zero magic numbers rule |
| Pip size | Custom digit detection | `_pip_size(symbol_info)` already in strategy.py, move to proposal.py | Already handles 3/5 digit pairs |

**Key insight:** The indicators layer (Phase 2) and patterns layer (Phase 3) exist specifically to feed Phase 4 cleanly. Detectors are thin consumers of pre-computed snapshots, not re-implementors of indicator math.

---

## Common Pitfalls

### Pitfall 1: Indicator Computed Inside Detector
**What goes wrong:** `detect_a_breakout()` calls `atr(highs, lows, closes, 14)` directly — defeats D-12 single-compute optimization and introduces leakage risk.
**Why it happens:** Old `strategy.py` computed indicators inline; easy to copy the pattern.
**How to avoid:** Detectors ONLY read from the `indicators: ExtendedIndicators` argument. ATR, RSI, etc. are attributes, not computed calls. Enforce with `test_strategy_purity.py` AST check.
**Warning signs:** Any import of `indicators.py` inside `strategy/setups/*.py`.

### Pitfall 2: ProposalDraft Mutation
**What goes wrong:** Code does `draft.confidence = 0.9` on a frozen dataclass → `FrozenInstanceError` at runtime.
**Why it happens:** Frozen dataclass prevents direct assignment; easy to forget.
**How to avoid:** Always use `dataclasses.replace(draft, confidence=0.9)` to produce a new instance. Import `replace` at module top.
**Warning signs:** Any `draft.<field> =` assignment outside `__init__` or factory functions.

### Pitfall 3: PatternHit Dict Key Access
**What goes wrong:** `pattern["direction"]` raises `AttributeError` because Phase 3 delivers `PatternHit` frozen dataclass, not a dict.
**Why it happens:** Old `patterns.py` returned `is_hammer()` bool; current `strategy.py:229` already uses dict-key access from an intermediate version.
**How to avoid:** Use `pattern.direction`, `pattern.name`, `pattern.bar_index`, `pattern.extreme_price`. Phase 3 CONTEXT.md D-01 confirms frozen dataclass with no dict alias.
**Warning signs:** `pattern["..."]` or `pattern.get(...)` anywhere in `strategy/setups/b_reversal.py`.

### Pitfall 4: Counter-Trend Reversal Without Grade Gate
**What goes wrong:** Setup B emits READY for a counter-trend reversal with grade B → system proposes a trade the skill table says requires grade A minimum.
**Why it happens:** Developer implements detector before implementing the counter-trend gate.
**How to avoid:** D-07 gate is implemented INSIDE `detect_b_reversal()` after grade computation — not in `evaluate_proposal_for_bar()`. Separate unit test for counter-trend downgrade case.
**Warning signs:** Tests pass for Setup B but no test covers `direction != ema50_slope direction` with grade B.

### Pitfall 5: Regression Fixture Captured After Code Change
**What goes wrong:** Developer starts restructuring `strategy.py` into package before running the capture script → fixture captures refactored behavior, not baseline.
**Why it happens:** Temptation to "just start the refactor" before the tedious fixture capture.
**How to avoid:** Git commit the baseline JSON before ANY code modification. CI or plan verification checks that the fixture commit precedes the first `strategy/` directory creation commit.
**Warning signs:** `tests/fixtures/strategy_regression_baseline.json` timestamp is after first `strategy/__init__.py` creation.

### Pitfall 6: `RiskProfile` Enum Mismatch
**What goes wrong:** `StrategyContext.profile` is typed as `RiskProfile` enum but `risk_engine.py` uses `"MODERATE"` string key while CONTEXT.md says "BALANCED" in some places.
**Why it happens:** CONTEXT.md D-08 `profile_filters` uses "CONSERVATIVE/MODERATE/AGGRESSIVE" (matching `risk_engine.py`), but skill table says "CONSERVATIVE/BALANCED/AGGRESSIVE". They differ on the middle value.
**How to avoid:** **Use `risk_engine.py` keys as the source of truth**: CONSERVATIVE / MODERATE / AGGRESSIVE. The skill table entry "BALANCED" maps to MODERATE. Verify at plan time.
**Warning signs:** `KeyError: 'BALANCED'` at runtime, or `profile_filters.BALANCED` not found in strategy.yaml.

### Pitfall 7: `indicators.py` Still Flat When Phase 4 Runs
**What goes wrong:** Phase 4 plan references `from indicators.volatility import ExtendedIndicators` but `indicators.py` is still flat (Phase 2 not yet merged).
**Why it happens:** Phases run sequentially; Phase 4 plan must account for Phase 2's deliverable state.
**How to avoid:** Phase 4 plans for the `indicators/` package state (Phase 2 delivered). If Phase 4 executes before Phase 2, imports must fall back to flat `indicators.py`. The plan should include a conditional import or a Wave 0 dependency check task.
**Warning signs:** `ModuleNotFoundError: No module named 'indicators.volatility'` when running tests.

---

## Runtime State Inventory

Phase 4 is a code refactor (not rename/rebrand), but `strategy.py` exports `IntradayStrategy` which is imported at runtime by:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — strategy module holds no persistent state | None |
| Live service config | `scheduler.py` imports `IntradayStrategy` from `strategy` | Shim preserves signature; no scheduler change |
| OS-registered state | None | None |
| Secrets/env vars | `STRATEGY_CONFIG_PATH` — new env var for test config override | Document in `.env.example`, add to `config.py` if needed |
| Build artifacts | None — no compiled artifacts for pure Python | None |

**`strategy.py` import contract preserved by shim:** All existing callers (`scheduler.py`, `mcp_server.py:28+`, `claude_agent.py:12+`, `scanner.py`) import `IntradayStrategy` from `strategy` — the shim in `strategy/__init__.py` maintains this export exactly. No caller changes required.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All | Checked via CLAUDE.md | 3.12 | — |
| PyYAML | `config/strategy.yaml` | Installed (Phase 3 confirmed) | — | None needed |
| `pytest` | All tests | Not installed via system Python 3.14 default | — | Install via `pip install pytest` in venv |
| `data/historical/EURUSD/M15.csv` | Regression fixture capture | Confirmed present | 23.5y data | — |
| `data/historical/GBPUSD/M15.csv` | Regression fixture capture | Confirmed present | — | — |
| `data/historical/USDJPY/M15.csv` | Regression fixture (implied) | Confirmed present (USDJPY dir exists) | — | — |
| `indicators/` package (Phase 2) | `compute_all_extended`, `ExtendedIndicators` | NOT YET — still flat `indicators.py` | — | Phase 4 must depend on Phase 2 completion |
| `patterns` package (Phase 3) | `PatternHit` dataclass, `scan_patterns()` | NOT YET — still flat `patterns.py` | — | Phase 4 must depend on Phase 3 completion |

**Missing dependencies with no fallback:**
- Phase 2 indicators package (`indicators/`) — Phase 4 must be planned to execute AFTER Phase 2 merge
- Phase 3 patterns package (`patterns.py` → `PatternHit` dataclass) — Phase 4 must be planned AFTER Phase 3 merge
- `pytest` in the project's virtual environment — Wave 0 must include install verification

**Note on Phase 2/3 dependency:** If Phase 4 must proceed concurrently, adapters and detectors should import from `indicators` (flat or package) conditionally via try/except. The plan should make this dependency explicit.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (confirmed via test files in `tests/`) |
| Config file | `pytest.ini` or `pyproject.toml` — not yet present, Wave 0 task |
| Quick run command | `pytest tests/test_strategy_setups.py tests/test_strategy_confluence.py -x -q` |
| Full suite command | `pytest tests/test_strategy*.py -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STRAT-01 | Setup A detector returns ProposalDraft with correct fields | unit | `pytest tests/test_strategy_setups.py::test_detect_a_breakout_ready -x` | ❌ Wave 0 |
| STRAT-02 | Setup B detector + counter-trend gate | unit | `pytest tests/test_strategy_setups.py::test_detect_b_reversal_counter_trend_gate -x` | ❌ Wave 0 |
| STRAT-03 | Setup C detector with NR4/NR7/squeeze | unit | `pytest tests/test_strategy_setups.py::test_detect_c_compression_nr7 -x` | ❌ Wave 0 |
| STRAT-04 | Setup D detector with Fib pullback | unit | `pytest tests/test_strategy_setups.py::test_detect_d_pullback_fib_38 -x` | ❌ Wave 0 |
| STRAT-05 | 5-factor scorer returns correct booleans and grade | unit | `pytest tests/test_strategy_confluence.py::test_score_factors_all_true -x` | ❌ Wave 0 |
| STRAT-06 | Grade → confidence + adjusters calibration | unit | `pytest tests/test_strategy_confluence.py::test_confidence_adjusters -x` | ❌ Wave 0 |
| STRAT-07 | ATR-based levels satisfy R:R for each profile | unit | `pytest tests/test_strategy_proposal.py::test_rr_floor_conservative -x` | ❌ Wave 0 |
| STRAT-08 | No broker/db/print in pure modules (AST) | static | `pytest tests/test_strategy_purity.py -x` | ❌ Wave 0 |
| STRAT-09 | Same `evaluate_proposal_for_bar` called by live and backtest | integration | `pytest tests/test_strategy_regression.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_strategy_setups.py tests/test_strategy_confluence.py -x -q`
- **Per wave merge:** `pytest tests/test_strategy*.py -v` (all strategy tests, <500ms total per SC#3)
- **Phase gate:** Full strategy test suite green + `tests/test_strategy_regression.py` green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_strategy_setups.py` — 4 detector unit tests (STRAT-01..04)
- [ ] `tests/test_strategy_confluence.py` — 5-factor + grade + adjuster tests (STRAT-05, STRAT-06)
- [ ] `tests/test_strategy_proposal.py` — ProposalDraft→TradeProposal + R:R + profile filter (STRAT-07)
- [ ] `tests/test_strategy_purity.py` — AST introspection purity gate (STRAT-08)
- [ ] `tests/test_strategy_regression.py` — 10-fixture replay (STRAT-09 + SC-5)
- [ ] `tests/capture_regression_baseline.py` — one-time pre-refactor capture script
- [ ] `tests/fixtures/strategy_regression_baseline.json` — captured output (requires running capture script)
- [ ] `config/strategy.yaml` — D-08 schema
- [ ] `conftest.py` additions — `mock_mt5_from_csv()` fixture if not already present

---

## Code Examples

### `config/strategy.yaml` — D-08 Schema
```yaml
# Source: CONTEXT.md D-08
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

### `StrategyContext` Dataclass
```python
# Source: CONTEXT.md D-04
from dataclasses import dataclass, field
from typing import Callable
from datetime import datetime

@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timeframe: str
    profile: str                          # "CONSERVATIVE" | "MODERATE" | "AGGRESSIVE"
    sr: dict                              # find_support_resistance() output
    regime: str                           # "compressed" | "normal" | "expanded"
    patterns: list                        # list[PatternHit] from Phase 3 scan_patterns()
    symbol_info: object                   # MT5 symbol_info struct (pip_size, digits)
    pip_size: float
    intermarket_score_fn: Callable | None = None   # Phase 10 hook (returns float, default None)
    news_blackout_fn: Callable | None = None       # Phase 10 hook (returns bool, default None)
    recent_trades: list = field(default_factory=list)   # list[TradeOutcome] for adjusters
    spread_baseline_pips: float | None = None
    # Hidden fields for adapter convenience (not part of pure contract)
    _bars: list = field(default_factory=list, compare=False, hash=False, repr=False)
    _indicators: object = field(default=None, compare=False, hash=False, repr=False)
```

### `ProposalDraft` Dataclass
```python
# Source: CONTEXT.md D-03
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
    factors: dict = None               # dict[str, bool] — 5-factor breakdown
    grade: Literal["A+", "A", "B", "C", "reject"] | None = None
    confidence: float = 0.0
    reason: str = ""
    rationale_parts: dict = None       # dict[str, str] for ML + debug
    setup_specific: dict = None        # per-setup anchors + "losers" list

    def __post_init__(self):
        # Use object.__setattr__ on frozen dataclass for mutable defaults
        if self.factors is None:
            object.__setattr__(self, 'factors', {})
        if self.rationale_parts is None:
            object.__setattr__(self, 'rationale_parts', {})
        if self.setup_specific is None:
            object.__setattr__(self, 'setup_specific', {})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single breakout-trend path in `identify_entry_setup()` | 4 pure-function detectors (A/B/C/D) | Phase 4 | Full setup coverage, ML-feature-extractable |
| `_score_confidence` ad-hoc weights (0.3/0.2/0.2/0.2/0.1) | Skill-table calibrated grades (A+=0.85, A=0.70, B=0.55, C=0.40) + adjusters | Phase 4 | Values match professional playbook; calibration testable |
| Inline broker calls in `_analyze_technical` | Adapter pattern — broker calls in `adapters/live.py` only | Phase 4 | Enables backtest reuse (STRAT-09) |
| `scan_patterns()` returns list[bool] / list[dict] | `scan_patterns()` returns list[PatternHit] frozen dataclasses | Phase 3 | Attribute access, hashable, ML-friendly |
| Single shared `_compute_levels()` | Per-setup `_compute_levels_<a/b/c/d>()` with setup-specific anchors | Phase 4 | Correct TP anchors per setup type |
| `patterns.py` returns `{'pattern': 'hammer', 'direction': 'bullish'}` dict | `patterns.PatternHit(name='hammer', bar_index=-1, ...)` dataclass | Phase 3 | Breaking change at `strategy.py:229` — must update in Phase 3 plan 04 |

**Deprecated/outdated:**
- `strategy.IntradayStrategy._score_confidence`: removed atomically in Phase 4, replaced by `confluence.compute_confidence()`. No DeprecationWarning emitted per D-11.
- `strategy.identify_entry_setup()`: folded into `detect_a_breakout()` (its current logic is purely Setup A). Not deprecated — absorbed.
- `strategy._compute_levels()`: split into 4 per-setup functions. Original removed.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 2 (`indicators/` package with `compute_all_extended`, `ExtendedIndicators`) is delivered and merged before Phase 4 executes | Environment Availability | If Phase 4 starts first, all detector imports break; need conditional import shim |
| A2 | Phase 3 (`PatternHit` dataclass from `scan_patterns()`) is delivered before Phase 4 executes | Environment Availability | Setup B cannot consume pattern hits; need fallback to old bool-return `scan_patterns()` |
| A3 | `risk_engine.py` profile key "MODERATE" (not "BALANCED") is the authoritative spelling | 5-Factor Confluence Model | `KeyError` in `config/strategy.yaml` profile_filters lookup; minor fix but catches inconsistency |
| A4 | `data/historical/USDJPY/M15.csv` exists (needed for regression fixture scenarios 7–10) | Regression Fixture | Fixture script fails on scenarios 7–10; use EURUSD/GBPUSD only, reduce to 8 scenarios |

**All other claims in this research are VERIFIED against codebase, CONTEXT.md decisions, or CITED from extracted skill files.**

---

## Open Questions

1. **Phase 2/3 dependency ordering**
   - What we know: Phase 4 consumes `ExtendedIndicators` (Phase 2) and `PatternHit` (Phase 3)
   - What's unclear: Will Phase 2 and 3 be fully merged before Phase 4 work starts?
   - Recommendation: Plan Wave 0 to include a dependency check task; if Phase 2 not yet merged, provide a stub `ExtendedIndicators` class that wraps flat `indicators.py` results

2. **`RiskProfile` enum vs string**
   - What we know: CONTEXT.md uses `profile: RiskProfile` (enum type); `risk_engine.py` uses string keys `"CONSERVATIVE"/"MODERATE"/"AGGRESSIVE"`
   - What's unclear: Does `RiskProfile` enum already exist in `models.py`? (Checked: not present in current `models.py`)
   - Recommendation: Add `RiskProfile = Literal["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]` to `models.py` (or use plain string type alias); add to `models.py` in Wave 0

3. **Confidence delta in regression test**
   - What we know: New calibration model will produce different confidence values than old `_score_confidence`
   - What's unclear: Whether the `1e-4` tolerance will be achievable, or if the regression test needs to be re-baselined after deliberate calibration change
   - Recommendation: Wave 0 captures pre-refactor baseline; plan must explicitly include a "reconcile confidence delta" task that re-baselines the fixture after the new calibration is in, BEFORE the regression test gates the final wave

4. **`_apply_sentiment` mutation on frozen TechnicalSetup**
   - What we know: `_apply_sentiment` does `setup.confidence = round(boosted, 4)` — mutates the dataclass directly (line 668). `TechnicalSetup` in `models.py` is NOT frozen.
   - What's unclear: Phase 4's `draft_to_technical_setup()` returns a `TechnicalSetup` — this is fine since it's not frozen
   - Recommendation: No change needed; `TechnicalSetup` stays mutable for `_apply_sentiment` compatibility

---

## Security Domain

Phase 4 is pure Python strategy code with no network I/O, authentication, or external service calls in the pure layer. The adapter layer (`adapters/live.py`) calls `mt5_client` which already exists and is not refactored here.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — no auth in strategy layer |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes | Bounds checks on ATR, pip_size, bar count before detector logic |
| V6 Cryptography | No | N/A |

**Input validation minimum:** Detectors must guard against `atr_val is None`, `len(bars) < minimum_lookback`, `pip_size <= 0`. Return `ProposalDraft(setup_type="NONE", reason="insufficient_data")` on any invalid input — never raise in production path.

---

## Sources

### Primary (HIGH confidence)
- CONTEXT.md D-01..D-16 — all architectural decisions locked and verified
- `strategy.py` (737 lines) — full inspection of current monolithic implementation
- `models.py` — confirmed: `TechnicalSetup`, `TradeProposal`, `BrokerProtocol`, `AccountState` exist; `RiskProfile` does NOT exist
- `risk_engine.py` — confirmed: `PROFILES = {"CONSERVATIVE":..., "MODERATE":..., "AGGRESSIVE":...}`
- `forex-trader-pro/references/setup_playbook.md` — extracted from skill zip, full Setup A/B/C/D mechanics
- `forex-trader-pro/SKILL.md` — extracted confluence checklist, 5-factor table, grade/confidence table, ±0.05 adjusters
- `forex-algo-dev/references/strategy_patterns.md` — pure-function patterns, ATR swing detection
- `forex-algo-dev/references/architecture.md` — adapter pattern, pure layer architecture
- `data/historical/{EURUSD,GBPUSD,USDJPY}/M15.csv` — confirmed present for regression fixture

### Secondary (MEDIUM confidence)
- Phase 3 CONTEXT.md — PatternHit schema, `scan_patterns()` contract, `config/patterns.yaml` pattern
- Phase 2 CONTEXT.md — `compute_all_extended`, `ExtendedIndicators`, indicator submodule layout
- Phase 1 backtest CONTEXT.md — D-08 GMT-6→UTC, D-09 bar-close decision, BrokerProtocol

### Tertiary (LOW confidence)
- A1..A4 in Assumptions Log — cross-phase ordering assumptions not yet verified by CI

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all locked in CONTEXT.md
- Architecture: HIGH — fully designed in 16 locked decisions, codebase inspected
- Detector mechanics: HIGH — skill playbook extracted and verified
- Confluence model: HIGH — exact table values extracted from skill zip
- Pitfalls: HIGH — all sourced from current codebase inspection and CONTEXT.md hot-spots
- Phase ordering risk: MEDIUM — Phases 2/3 dependency is assumed but not CI-enforced

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (stable — all decisions locked; only changes if Phase 2/3 deliverables differ from CONTEXT.md expectations)
