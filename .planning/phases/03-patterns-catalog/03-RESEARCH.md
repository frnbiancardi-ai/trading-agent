# Phase 3: Patterns Catalog — Research

**Researched:** 2026-05-07
**Domain:** Candlestick pattern detection (pure-Python geometry + calibrated confidence + frozen dataclass schema)
**Confidence:** HIGH (geometry rules book-grounded; sibling Phase 1 config pattern already validated; full surface mapped)

## Summary

Phase 3 replaces `patterns.py`'s 6 minimal `bool`-returning detectors + `scan_patterns(...) -> list[dict]` with a full 7-pattern catalog (PATT-01..06) plus calibrated confidence scoring (PATT-07). The output schema migrates from dict to a `@dataclass(frozen=True) PatternHit`. Thresholds and per-pattern calibration anchors live in a NEW `config/patterns.yaml` (subdir created this phase — does NOT exist yet; sibling Phase 1 used `data/configs/costs.yaml`, NOT `config/`).

The geometry rules are well-established (Murphy ch.10, Probo ch. on price-action, Defendi material in `libri/StrategieOperative.pdf`). The novel work is (a) the calibration mapping that makes confidences comparable across pattern types, and (b) the surgical refactor of strategy.py — which has THREE call sites consuming dict-style hits, not one as the locked decision document mentions.

**Primary recommendation:** Mirror `backtest/costs.py` exactly for the config loader. Implement calibration as a 5-line piecewise-linear function. Refactor all THREE strategy.py consumers (lines 229+241, 314-321, 619-621) in the same plan task — the planner MUST treat this as one atomic refactor, not just line 229.

## <user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Schema:** `@dataclass(frozen=True) PatternHit` with fields `name: str`, `bar_index: int`, `span_bars: int`, `extreme_price: float`, `confidence: float`, `direction: str`. NO dict alias. NO `'pattern'` key. NO DeprecationWarning shim.
- **Confidence:** pure geometry → piecewise-linear interp through per-pattern `(min, typical, max)` calibration anchors → 0-1, comparable across pattern types.
- **Indexing:** `bar_index` = anchor (last/confirmation) bar, negative offset from end (`-1` = last bar). `span_bars` = 1 single-bar, 3 stars. `extreme_price` = swing low (bullish) / swing high (bearish) over full span.
- **Config:** `config/patterns.yaml` (subdir). `load_pattern_config(path: str | None = None) -> PatternConfig` returns frozen `PatternConfig`. Override via parameter or env `PATTERNS_CONFIG_PATH`. Zero magic numbers in `patterns.py`.
- **Detector signature:** pure functions `(bars, cfg: PatternConfig)`. No globals, no side effects.
- **Perf:** no budget. Clean Python loop. Defer optimization to Phase 5.
- **Doji:** kept as-is, neutral direction, NOT counted as PATT-XX.
- **Refactor scope:** `strategy.py:229` MUST be refactored to attribute access in this phase. Tests in `tests/test_patterns.py` updated.
- **Tests:** each detector — hand-crafted positive + near-miss negative. pytest. No MT5 mock.
- **Italian:** comments / log / rationale in italiano (CLAUDE.md).

### Claude's Discretion

- Exact `PatternConfig` and per-pattern sub-dataclass field names.
- Geometry-to-raw-score formula per pattern (must validate against hand-crafted fixtures).
- Piecewise-linear interpolation impl detail (single helper `_calibrate(raw, anchors) -> float`).
- Whether `load_pattern_config` reads YAML directly or factors out a shared loader (recommendation below: read directly, mirror `backtest.costs.load_cost_model`).
- Doji handling: keep, mark non-PATT, do not gate on calibration.

### Deferred Ideas (OUT OF SCOPE)

- Trend-context filter (hammer-after-downtrend gating) → Phase 4
- ATR-relative significance scoring → Phase 4 / Phase 7 ML
- Volume confirmation → Phase 10
- Harmonic / chart patterns (H&S, double-top) → future
- Per-symbol threshold tuning (separate yaml per pair) → conditional on Phase 5
- Performance vectorization (numpy/pandas) → Phase 5 if 23.5y backtest > 30 min
- Strict-mode dict-alias enforcement → moot (r1 idea, dropped in r2)

</user_constraints>

## <phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PATT-01 | Hammer / Inverted Hammer detector | Murphy ch.10 geometry + existing `is_hammer`/`is_inverted_hammer` already correct; gain calibration + extreme_price |
| PATT-02 | Shooting Star detector | NEW. Mirror image of inverted hammer + bearish-context body color requirement (geometry only this phase) |
| PATT-03 | Bullish/Bearish Engulfing detector | Existing `is_engulfing` correct; gain calibration (engulfment ratio) + extreme_price (swing low/high prev/curr) |
| PATT-04 | Morning Star / Evening Star (3-bar) | NEW. 3-bar geometry: trend bar → small-body bar → reversal bar; span_bars=3; extreme_price = lowest low (morning) / highest high (evening) across all 3 bars |
| PATT-05 | Key Reversal Bar | NEW. Single bar opens beyond prior extreme, closes back through prior bar's body — "outside reversal" |
| PATT-06 | Inside Bar / Pin Bar | TWO sub-detectors. Inside = NEW (curr.high <= prev.high AND curr.low >= prev.low). Pin Bar exists, gain calibration |
| PATT-07 | Catalog returns confidence + structural refs | The whole `PatternHit` dataclass + `scan_patterns(bars, last_n, cfg) -> list[PatternHit]` design |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bar geometry math (body, range, shadows) | patterns.py (pure helper) | — | Already there, no change |
| Pattern detectors (per-pattern bool/score) | patterns.py | — | Pure-fn library, geometry-only |
| Raw-score → calibrated confidence | patterns.py (`_calibrate`) | — | Stateless math, lives next to detectors |
| Threshold + anchor storage | `config/patterns.yaml` | — | Brand-new directory; per CONTEXT r2 |
| Config loader / dataclass marshalling | patterns.py (`load_pattern_config`) | — | Sibling pattern: `backtest.costs.load_cost_model` |
| Strategy consumption of hits | strategy.py | patterns.py exports | Three call sites must move from dict-key to attribute access in-phase |
| Test fixtures (hand-crafted bars) | `tests/test_patterns.py` | — | Existing file, extend |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses` | 3.12 builtin | `@dataclass(frozen=True)` for `PatternHit` and `PatternConfig` | [VERIFIED: project uses Python 3.12, sibling `backtest/costs.py:CostModel` already uses this exact pattern] |
| Python stdlib `pathlib.Path` | 3.12 builtin | YAML path handling | [VERIFIED: pattern matches `backtest/costs.py:42`] |
| PyYAML | 6.0.3 (installed) | Read `config/patterns.yaml` via `yaml.safe_load` | [VERIFIED: `python -c "import yaml; print(yaml.__version__)"` returned 6.0.3 on 2026-05-07] |
| pytest | already in project | Detector unit tests | [VERIFIED: existing `tests/test_patterns.py`] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `os.environ` | stdlib | Read `PATTERNS_CONFIG_PATH` env override | In `load_pattern_config(path=None)` when path is None and env is set |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `dataclasses` | `pydantic.BaseModel` | Pydantic adds runtime validation but the project doesn't import it elsewhere; CostModel uses stdlib — stay consistent. |
| PyYAML | `tomllib` (stdlib) + `.toml` | TOML is stdlib, but the project already standardized on YAML (`data/configs/costs.yaml`) — be consistent. |
| Piecewise-linear interp | `scipy.interpolate.interp1d` | Adds heavy dep for 5 lines of math. Not justified. |

**Installation:** Nothing new — PyYAML already installed for Phase 1.

**Version verification:** `python -c "import yaml; print(yaml.__version__)"` → `6.0.3` [VERIFIED on dev box 2026-05-07].

## Architecture Patterns

### System Architecture Diagram

```
                ┌────────────────────────────┐
                │ config/patterns.yaml (NEW) │
                │  per-pattern thresholds +  │
                │  (min,typical,max) anchors │
                └────────────┬───────────────┘
                             │ yaml.safe_load
                             ▼
              ┌──────────────────────────────┐
              │ load_pattern_config(path)    │
              │   → PatternConfig (frozen)   │
              └──────────────┬───────────────┘
                             │ cfg
                             ▼
   bars: list[dict] ───►  scan_patterns(bars, last_n, cfg)
                             │
                             ├─► is_hammer(bar, cfg.hammer)        ──┐
                             ├─► is_inverted_hammer(...)            │
                             ├─► is_shooting_star(...)              │  raw_score
                             ├─► is_engulfing(prev, curr, ...)      │  per detector
                             ├─► is_morning_star(b1,b2,b3, ...)     │
                             ├─► is_evening_star(...)               │
                             ├─► is_key_reversal(prev, curr, ...)   │
                             ├─► is_inside_bar(prev, curr, ...)     │
                             └─► is_pin_bar(bar, ...)              ──┘
                                          │
                                          ▼
                         _calibrate(raw, (min,typ,max)) → confidence ∈ [0,1]
                                          │
                                          ▼
                              PatternHit(name, bar_index, span_bars,
                                         extreme_price, confidence, direction)
                                          │
                                          ▼
                              strategy.py: hit.name, hit.direction, hit.confidence
                                          │
                                          ▼
                              Setup B / ML feature pipeline (downstream)
```

### Recommended Project Structure

```
trading-agent/
├── config/
│   └── patterns.yaml             # NEW (Phase 3)
├── patterns.py                   # REWRITTEN (Phase 3)
├── strategy.py                   # MODIFIED 3 sites (Phase 3)
└── tests/
    └── test_patterns.py          # EXTENDED (Phase 3)
```

### Pattern 1: Frozen-dataclass output type

**What:** All hits returned as immutable, hashable, attribute-accessed objects.
**When to use:** Always (this phase). Mirrors `backtest.costs.CostModel`.
**Example:**
```python
# Source: project sibling backtest/costs.py:8 [VERIFIED]
from dataclasses import dataclass

@dataclass(frozen=True)
class PatternHit:
    name: str           # "hammer", "morning_star", etc
    bar_index: int      # negative offset from end of bars list
    span_bars: int      # 1 (single-bar) | 3 (stars)
    extreme_price: float
    confidence: float   # 0.0 .. 1.0
    direction: str      # "bullish" | "bearish" | "neutral"
```

### Pattern 2: YAML config loader (mirror backtest/costs.py)

**What:** Single function reads YAML, builds nested frozen dataclass.
**When to use:** Always — keeps project consistent.
**Example:**
```python
# Source: backtest/costs.py:42-59 (Phase 1 sibling) [VERIFIED]
import os, yaml
from pathlib import Path
from dataclasses import dataclass

DEFAULT_CONFIG_PATH = Path("config/patterns.yaml")

@dataclass(frozen=True)
class CalibrationAnchors:
    min: float
    typical: float
    max: float

@dataclass(frozen=True)
class HammerCfg:
    body_ratio_max: float
    lower_shadow_body_min: float
    upper_shadow_range_max: float
    calibration: CalibrationAnchors

# ... one sub-cfg dataclass per pattern ...

@dataclass(frozen=True)
class PatternConfig:
    hammer: HammerCfg
    inverted_hammer: HammerCfg
    shooting_star: ShootingStarCfg
    engulfing: EngulfingCfg
    morning_star: StarCfg
    evening_star: StarCfg
    key_reversal: KeyReversalCfg
    inside_bar: InsideBarCfg
    pin_bar: PinBarCfg
    doji: DojiCfg

def load_pattern_config(path: str | Path | None = None) -> PatternConfig:
    if path is None:
        path = os.environ.get("PATTERNS_CONFIG_PATH") or DEFAULT_CONFIG_PATH
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    # validate + build nested dataclasses; raise KeyError on missing required keys
    ...
```

### Pattern 3: Piecewise-linear calibration

**What:** Map raw geometry score (e.g. lower_shadow / body ratio for hammer) into [0, 1] using 3 anchors.
**When to use:** Every detector that returns a hit.
**Example:**
```python
def _calibrate(raw: float, anchors: CalibrationAnchors) -> float:
    """Mappa raw score in [0,1] via interpolazione lineare a tratti.

    raw <= min      -> 0.0
    min < raw < typ -> linear interp 0.0 -> 0.7
    typ <= raw < max -> linear interp 0.7 -> 1.0
    raw >= max      -> 1.0
    """
    lo, typ, hi = anchors.min, anchors.typical, anchors.max
    if raw <= lo:
        return 0.0
    if raw >= hi:
        return 1.0
    if raw < typ:
        return 0.7 * (raw - lo) / (typ - lo)
    return 0.7 + 0.3 * (raw - typ) / (hi - typ)
```

The `0.7` knee at the typical anchor is itself a deliberate calibration choice — it means "a typical-strength hit is rated 0.7" which leaves headroom for stronger-than-typical hits.

### Anti-Patterns to Avoid

- **Storing `pip_size` or per-symbol context inside `PatternConfig`:** keep config geometry-only. Setup B / Phase 4 owns trend, ATR, S/R.
- **Hashing on float fields with NaN:** `extreme_price` must never be NaN. Guard with `if rng <= 0: return None` early in every detector.
- **Reading YAML at module import time:** `load_pattern_config` is a function. No module-level singleton.
- **Mixing config validation with detection:** validation lives in the loader; detectors trust their cfg arg.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom YAML parser | `yaml.safe_load` | Already used in Phase 1; safe_load avoids arbitrary object construction (T-1-06 STRIDE in Phase 1) |
| Frozen value type | `__slots__` + `__hash__` by hand | `@dataclass(frozen=True)` | Sibling `CostModel` proves the pattern works; auto-generates `__eq__`, `__hash__`, `__repr__` |
| Piecewise interp | Generic n-point interpolator | 3-anchor `_calibrate` 5-liner | Only 3 anchors used; `scipy.interp1d` is overkill |
| Config path resolution | Custom CWD walker | `pathlib.Path` + env var precedence | Mirrors `backtest/costs.py` exactly |

**Key insight:** Phase 1 (Backtest Engine) already established the YAML+frozen-dataclass+per-symbol-config pattern. Phase 3 is a near-isomorphic application of the same pattern. Do not invent a new style.

## Runtime State Inventory

> Phase 3 is partially a refactor (replacing return type) — short inventory follows.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — patterns are computed per-bar, never persisted | None — verified by grep for `pickle`, `json.dump`, `parquet` referencing patterns |
| Live service config | None — no MCP tool currently exposes pattern hits (MCP-14 deferred to Phase 6) | None |
| OS-registered state | None | None |
| Secrets/env vars | New env var introduced: `PATTERNS_CONFIG_PATH`. No secret value, just a path override. Add to `.env.example` if project convention requires. | Add to `.env.example` and document; no `.env` change |
| Build artifacts | None — pure Python, no compiled module | None |

**Code-edit dependencies (the actual refactor surface):**

| File | Line(s) | Current dict-style access | Target attribute access |
|------|---------|---------------------------|-------------------------|
| `strategy.py` | 229 | `scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS)` (call site — gain `cfg=pattern_cfg` arg) | Add `cfg=self._pattern_cfg` and ensure `self._pattern_cfg` initialized in `__init__` via `load_pattern_config()` |
| `strategy.py` | 241 | `"patterns": patterns` stored in `indicators_snapshot` dict | Stays — but downstream consumers (ML, MCP-14) will see `list[PatternHit]` not `list[dict]`. Document this in summary. |
| `strategy.py` | 314-316 | `any(p["direction"] == "bullish" for p in patterns)` | `any(p.direction == "bullish" for p in patterns)` |
| `strategy.py` | 317-319 | `any(p["direction"] == "bearish" for p in patterns)` | `any(p.direction == "bearish" for p in patterns)` |
| `strategy.py` | 620 | `any(p["direction"] == wanted for p in patterns)` inside `_score_confidence` | `any(p.direction == wanted for p in patterns)` |
| `tests/test_patterns.py` | 86 | `names = {p["pattern"] for p in found}` | `names = {p.name for p in found}` |
| `tests/test_patterns.py` | 98 | `rels = {p["bar_index"] for p in out}` | `rels = {p.bar_index for p in out}` |

**WARNING for planner — locked decision document said "strategy.py:229 MUST be updated" but the actual refactor surface is FIVE call sites in strategy.py + TWO in tests. Treat all seven as a single atomic refactor task. Verified by:**

```
Grep "p\\[\"direction\"\\]|p\\[\"pattern\"\\]|p\\[\"bar_index\"\\]" — 5 hits in strategy.py:315,318,620 and tests/test_patterns.py:86,98
```

## Common Pitfalls

### Pitfall 1: NaN / division-by-zero in raw score
**What goes wrong:** Bar with zero range (open=high=low=close) computes `lower_shadow / body = 0/0 = NaN`. Frozen dataclass with NaN confidence is hashable but breaks downstream comparisons.
**Why:** Edge-case bars (gap markets, holidays) emit zero-range candles.
**How to avoid:** Mirror existing `is_hammer` guard: `if rng <= 0 or body <= 0: return None`. Detector returns `None` (no hit), not a `PatternHit(confidence=NaN)`.
**Warning sign:** any `PatternHit` with `math.isnan(confidence)` or `extreme_price=0.0` in test fixtures.

### Pitfall 2: Calibration anchors with `min >= typical` or `typical >= max`
**What goes wrong:** Piecewise interp divides by `(typ - lo)` or `(hi - typ)` — division by zero or negative.
**Why:** Hand-edited YAML, copy-paste errors.
**How to avoid:** `load_pattern_config` validates `min < typical < max` for every pattern at load time. Raise `ValueError` with the offending pattern name.
**Warning sign:** Test load with deliberately broken yaml fixture asserts `ValueError`.

### Pitfall 3: 3-bar star indexing — future leakage
**What goes wrong:** Detector for morning star looks at `bars[i]`, `bars[i+1]`, `bars[i+2]` instead of `bars[i-2]`, `bars[i-1]`, `bars[i]`. The "anchor" must be the LAST (confirmation) bar.
**Why:** Easy to slip when porting from textbook examples that show the pattern centered.
**How to avoid:** ALWAYS index `(b1, b2, b3) = bars[i-2], bars[i-1], bars[i]` in the loop. Never look at `bars[i+1]` or beyond. Test with a fixture where `bars[i+1]` would invalidate the pattern but `bars[i]` doesn't — assert hit detected.
**Warning sign:** Any star detector signature accepts a single `bars` list and an int — verify it never reads beyond `i`.

### Pitfall 4: Inside Bar vs Pin Bar disambiguation
**What goes wrong:** A bar can be BOTH inside-bar (range engulfed by prior) AND pin-bar (long wick). Returning two separate hits is correct; returning a merged hit loses information.
**Why:** PATT-06 lumps them in one requirement ID.
**How to avoid:** Two separate detector functions (`is_inside_bar`, `is_pin_bar`), two separate `PatternHit` entries with distinct `name` values (`"inside_bar"` vs `"pin_bar"`). Don't unify under a single name.
**Warning sign:** A test bar that is both produces only one hit — bug.

### Pitfall 5: Environment override precedence
**What goes wrong:** Test passes `path=/tmp/test.yaml` but `PATTERNS_CONFIG_PATH` is set globally — code reads env, ignores parameter.
**Why:** Easy to swap precedence order.
**How to avoid:** Parameter > env > default. `if path is None: path = os.environ.get(...) or DEFAULT_CONFIG_PATH`. Test with monkeypatch.
**Warning sign:** Tests that use env var are flaky on dev box.

### Pitfall 6: PatternConfig immutability with nested dataclasses
**What goes wrong:** `PatternConfig` is frozen but its sub-fields are mutable dicts → still mutable through reference.
**Why:** Forgot to make sub-cfgs frozen too.
**How to avoid:** Every sub-config (HammerCfg, StarCfg, etc.) is `@dataclass(frozen=True)`. Same for `CalibrationAnchors`.
**Warning sign:** `hash(cfg)` raises `TypeError`.

### Pitfall 7: yaml.safe_load returning None on empty file
**What goes wrong:** Empty `config/patterns.yaml` returns `None`, then `None.get("hammer")` crashes.
**Why:** YAML edge case.
**How to avoid:** `raw = yaml.safe_load(f) or {}` (Phase 1 already does this on `backtest/costs.py:45`).

## Code Examples

### Pattern detector — Hammer with calibration

```python
# Source: refactor of patterns.py:32-40 + new calibration
def is_hammer(bar: dict, cfg: HammerCfg) -> tuple[bool, float]:
    """Hammer: body piccolo, lunga lower shadow, upper shadow trascurabile.

    Restituisce (matched, raw_score). raw_score = lower_shadow / body (>=2 tipico).
    """
    rng = bar["high"] - bar["low"]
    body = abs(bar["close"] - bar["open"])
    if rng <= 0 or body <= 0:
        return False, 0.0
    lower = min(bar["open"], bar["close"]) - bar["low"]
    upper = bar["high"] - max(bar["open"], bar["close"])
    matched = (
        body <= cfg.body_ratio_max * rng
        and lower >= cfg.lower_shadow_body_min * body
        and upper <= cfg.upper_shadow_range_max * rng
    )
    if not matched:
        return False, 0.0
    raw_score = lower / body  # ratio that drives confidence
    return True, raw_score
```

### Detector — Morning Star (3-bar)

```python
def is_morning_star(b1: dict, b2: dict, b3: dict, cfg: StarCfg) -> tuple[bool, float]:
    """Morning Star: bearish trend bar -> small-body indecision -> bullish reversal.

    Geometria (Murphy ch.10):
    - b1: bearish, body grande (>= cfg.trend_body_min_ratio del range)
    - b2: small body (<= cfg.star_body_max_ratio del range), gap down vs b1 (close)
    - b3: bullish, chiude oltre la metà del corpo di b1
    """
    if b1["close"] >= b1["open"]:  # b1 must be bearish
        return False, 0.0
    rng1 = b1["high"] - b1["low"]
    body1 = b1["open"] - b1["close"]
    if rng1 <= 0 or body1 / rng1 < cfg.trend_body_min_ratio:
        return False, 0.0
    rng2 = b2["high"] - b2["low"]
    body2 = abs(b2["close"] - b2["open"])
    if rng2 <= 0 or body2 / rng2 > cfg.star_body_max_ratio:
        return False, 0.0
    if b3["close"] <= b3["open"]:  # b3 must be bullish
        return False, 0.0
    midpoint_b1 = (b1["open"] + b1["close"]) / 2
    if b3["close"] <= midpoint_b1:
        return False, 0.0
    # Raw score: penetration of b3 close into b1 body
    penetration = (b3["close"] - midpoint_b1) / body1
    return True, penetration
```

### scan_patterns — full surface

```python
def scan_patterns(
    bars: list[dict],
    last_n: int = 5,
    cfg: PatternConfig | None = None,
) -> list[PatternHit]:
    """Scansiona ultime `last_n` barre e restituisce i PatternHit calibrati.

    cfg=None significa "carica default" — comodo per chiamanti rapidi/test.
    """
    if not bars:
        return []
    if cfg is None:
        cfg = load_pattern_config()
    n = len(bars)
    start = max(0, n - last_n)
    out: list[PatternHit] = []
    for i in range(start, n):
        bar = bars[i]
        rel = i - n  # -1 = ultima

        # --- single-bar patterns ---
        ok, raw = is_hammer(bar, cfg.hammer)
        if ok:
            out.append(PatternHit(
                name="hammer", bar_index=rel, span_bars=1,
                extreme_price=bar["low"],
                confidence=_calibrate(raw, cfg.hammer.calibration),
                direction="bullish",
            ))
        # ... inverted_hammer, shooting_star, pin_bar (bull/bear), inside_bar, doji ...

        # --- 2-bar patterns ---
        if i >= 1:
            prev = bars[i - 1]
            ok, raw = is_engulfing(prev, bar, "bullish", cfg.engulfing)
            if ok:
                extreme = min(prev["low"], bar["low"])
                out.append(PatternHit(
                    name="engulfing", bar_index=rel, span_bars=2,
                    extreme_price=extreme,
                    confidence=_calibrate(raw, cfg.engulfing.calibration),
                    direction="bullish",
                ))
            # ... bearish engulfing, key_reversal ...

        # --- 3-bar patterns ---
        if i >= 2:
            b1, b2, b3 = bars[i - 2], bars[i - 1], bar
            ok, raw = is_morning_star(b1, b2, b3, cfg.morning_star)
            if ok:
                extreme = min(b1["low"], b2["low"], b3["low"])
                out.append(PatternHit(
                    name="morning_star", bar_index=rel, span_bars=3,
                    extreme_price=extreme,
                    confidence=_calibrate(raw, cfg.morning_star.calibration),
                    direction="bullish",
                ))
            # ... evening_star ...
    return out
```

**Note on `span_bars`:** locked decision says "1 single-bar, 3 stars". Engulfing is 2 bars but spec doesn't enumerate it. **Recommendation:** use `span_bars=2` for engulfing/key_reversal — the field is forward-compat for arbitrary multi-bar patterns; restricting to {1,3} would lose info that downstream SL placement (`extreme_price` over span) needs. Flag this for planner — minor deviation from CONTEXT wording, but consistent with intent.

### Per-pattern raw-score formula reference

| Pattern | Raw score formula | Typical range |
|---------|-------------------|---------------|
| Hammer / Inverted | `lower_shadow / body` (or upper for inverted) | 2.0 .. 6.0+ |
| Shooting Star | `upper_shadow / body` | 2.0 .. 6.0+ |
| Engulfing (bull/bear) | `curr_body / prev_body` (engulfment ratio) | 1.0 .. 3.0+ |
| Morning Star | `(b3.close - mid(b1)) / body(b1)` (penetration) | 0.0 .. 1.5 |
| Evening Star | `(mid(b1) - b3.close) / body(b1)` | 0.0 .. 1.5 |
| Key Reversal | `(close - prev.high) / prev_range` (bearish KR) or symmetric | 0.0 .. 1.0+ |
| Inside Bar | `1.0 - range_curr / range_prev` (compression) | 0.0 .. 0.9 |
| Pin Bar | `dominant_wick / range` | 0.66 .. 0.9 |
| Doji | not calibrated (kept as boolean, confidence=1.0) | n/a |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Boolean detectors + `dict` hits | `(matched, raw_score)` detectors + `PatternHit` dataclass | Phase 3 | Enables ML feature use, mypy-safe, hashable |
| Module-constant thresholds (none currently — values hard-coded) | YAML config + frozen `PatternConfig` | Phase 3 | Zero magic numbers (CLAUDE.md), easy to retune in Phase 5 |
| `'pattern'` dict key | `.name` attribute | Phase 3 | Breaks any external caller — but project grep shows zero externals |

**Deprecated/outdated:**
- `'pattern'` dict-key access — ALL three call sites in strategy.py + two in tests must be refactored same plan
- `is_engulfing(prev, curr, "bullish")` returning bool — keep helper as boolean for direct callers (tests already test this); ALSO export the calibrated version that returns `(matched, raw_score)` — or unify and update test assertions. Recommendation: unify on `(matched, raw_score)` tuple, update existing 4 tests in `tests/test_patterns.py:17-75` accordingly.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already in project) |
| Config file | `pyproject.toml` or `pytest.ini` (existing) — no change needed |
| Quick run command | `pytest tests/test_patterns.py -x --tb=short -v` |
| Full suite command | `pytest -x --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PATT-01 | Hammer positive case detected | unit | `pytest tests/test_patterns.py::test_is_hammer_classic -x` | ✅ extend |
| PATT-01 | Hammer near-miss negative (long upper shadow) | unit | `pytest tests/test_patterns.py::test_is_hammer_rejects_long_upper_shadow -x` | ✅ exists |
| PATT-01 | Inverted hammer positive | unit | `pytest tests/test_patterns.py::test_is_inverted_hammer -x` | ✅ exists |
| PATT-01 | Inverted hammer near-miss | unit | `pytest tests/test_patterns.py::test_is_inverted_hammer_rejects_short_upper -x` | ❌ Wave 0 |
| PATT-02 | Shooting star positive | unit | `pytest tests/test_patterns.py::test_is_shooting_star_classic -x` | ❌ Wave 0 |
| PATT-02 | Shooting star near-miss (body too large) | unit | `pytest tests/test_patterns.py::test_is_shooting_star_rejects_large_body -x` | ❌ Wave 0 |
| PATT-03 | Bullish engulfing positive | unit | `pytest tests/test_patterns.py::test_is_engulfing_bullish -x` | ✅ exists (return shape changes) |
| PATT-03 | Bearish engulfing positive | unit | `pytest tests/test_patterns.py::test_is_engulfing_bearish -x` | ✅ exists |
| PATT-03 | Engulfing near-miss (curr does not fully engulf) | unit | `pytest tests/test_patterns.py::test_is_engulfing_partial_negative -x` | ❌ Wave 0 |
| PATT-04 | Morning star positive (3-bar fixture) | unit | `pytest tests/test_patterns.py::test_is_morning_star_classic -x` | ❌ Wave 0 |
| PATT-04 | Evening star positive | unit | `pytest tests/test_patterns.py::test_is_evening_star_classic -x` | ❌ Wave 0 |
| PATT-04 | Morning star near-miss (b3 closes below b1 midpoint) | unit | `pytest tests/test_patterns.py::test_is_morning_star_rejects_shallow_b3 -x` | ❌ Wave 0 |
| PATT-04 | Evening star near-miss | unit | `pytest tests/test_patterns.py::test_is_evening_star_rejects_shallow_b3 -x` | ❌ Wave 0 |
| PATT-05 | Key reversal bullish positive | unit | `pytest tests/test_patterns.py::test_is_key_reversal_bullish -x` | ❌ Wave 0 |
| PATT-05 | Key reversal bearish positive | unit | `pytest tests/test_patterns.py::test_is_key_reversal_bearish -x` | ❌ Wave 0 |
| PATT-05 | Key reversal near-miss (no penetration into prev body) | unit | `pytest tests/test_patterns.py::test_is_key_reversal_rejects_no_penetration -x` | ❌ Wave 0 |
| PATT-06 | Inside bar positive | unit | `pytest tests/test_patterns.py::test_is_inside_bar_classic -x` | ❌ Wave 0 |
| PATT-06 | Inside bar near-miss (curr.high == prev.high — boundary) | unit | `pytest tests/test_patterns.py::test_is_inside_bar_boundary -x` | ❌ Wave 0 |
| PATT-06 | Pin bar bullish positive | unit | `pytest tests/test_patterns.py::test_is_pin_bar_bullish -x` | ✅ exists |
| PATT-06 | Pin bar bearish positive | unit | `pytest tests/test_patterns.py::test_is_pin_bar_bearish -x` | ✅ exists |
| PATT-06 | Inside+Pin coexistence (one bar, two hits emitted) | unit | `pytest tests/test_patterns.py::test_inside_and_pin_coexist -x` | ❌ Wave 0 |
| PATT-07 | PatternHit is frozen dataclass with all 6 fields | unit | `pytest tests/test_patterns.py::test_pattern_hit_frozen_schema -x` | ❌ Wave 0 |
| PATT-07 | PatternHit is hashable | unit | `pytest tests/test_patterns.py::test_pattern_hit_hashable -x` | ❌ Wave 0 |
| PATT-07 | Confidence in [0, 1] for every detector positive case | unit (snapshot-style) | `pytest tests/test_patterns.py::test_confidence_in_unit_interval -x` | ❌ Wave 0 |
| PATT-07 | Calibration: raw < min anchor → confidence == 0.0 | unit | `pytest tests/test_patterns.py::test_calibrate_below_min -x` | ❌ Wave 0 |
| PATT-07 | Calibration: raw == typical → confidence == 0.7 | unit | `pytest tests/test_patterns.py::test_calibrate_at_typical -x` | ❌ Wave 0 |
| PATT-07 | Calibration: raw > max → confidence == 1.0 | unit | `pytest tests/test_patterns.py::test_calibrate_above_max -x` | ❌ Wave 0 |
| PATT-07 | Calibration monotonic non-decreasing | unit | `pytest tests/test_patterns.py::test_calibrate_monotonic -x` | ❌ Wave 0 |
| PATT-07 | extreme_price = swing low for bullish multi-bar | unit | `pytest tests/test_patterns.py::test_morning_star_extreme_is_swing_low -x` | ❌ Wave 0 |
| PATT-07 | bar_index negative offset semantics | unit | `pytest tests/test_patterns.py::test_scan_patterns_respects_last_n -x` | ✅ exists (update assertion to attribute) |
| PATT-07 | scan_patterns empty list returns [] | unit | `pytest tests/test_patterns.py::test_scan_patterns_empty -x` | ✅ exists |
| Config | `load_pattern_config()` reads default `config/patterns.yaml` | unit | `pytest tests/test_patterns.py::test_load_pattern_config_default -x` | ❌ Wave 0 |
| Config | `load_pattern_config(path)` parameter wins over env | unit | `pytest tests/test_patterns.py::test_load_config_param_overrides_env -x` | ❌ Wave 0 |
| Config | `PATTERNS_CONFIG_PATH` env override works when path=None | unit | `pytest tests/test_patterns.py::test_load_config_env_override -x` | ❌ Wave 0 |
| Config | Empty yaml file → safe default OR ValueError | unit | `pytest tests/test_patterns.py::test_load_config_empty_yaml -x` | ❌ Wave 0 |
| Config | Anchor with min >= typical raises ValueError | unit | `pytest tests/test_patterns.py::test_load_config_invalid_anchors_raises -x` | ❌ Wave 0 |
| Config | PatternConfig is frozen (hash works, mutation raises) | unit | `pytest tests/test_patterns.py::test_pattern_config_frozen -x` | ❌ Wave 0 |
| Refactor | strategy.py imports succeed and bullish-direction count uses attribute | unit/regression | `pytest tests/test_strategy.py -x` (existing) | ✅ existing test must still pass |
| Refactor | indicators_snapshot["patterns"] is `list[PatternHit]` not list[dict] | unit | new strategy test | ❌ Wave 0 (small) |
| Zero magic numbers | grep `patterns.py` for hard-coded constants > scope | meta-test | `! grep -E '\b(2\.0|0\.4|0\.2|1\.0/3\.0)\b' patterns.py` | ❌ Wave 0 (optional) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_patterns.py -x --tb=short` (full file, ~50ms expected)
- **Per wave merge:** `pytest -x --tb=short` (entire suite — strategy.py refactor regression-checks)
- **Phase gate:** Full suite green before `/gsd-verify-work`. Plus a smoke-pass: `python -c "from patterns import scan_patterns, PatternHit, load_pattern_config; cfg=load_pattern_config(); print('OK')"`.

### Wave 0 Gaps
- [ ] `config/patterns.yaml` — must be created with all 9 patterns + Doji thresholds + calibration anchors before any test green
- [ ] `tests/test_patterns.py::conftest`-style helper for hand-crafting 1/2/3-bar fixtures (e.g. `_bar(o,h,l,c)` already exists at line 13 — extend with `_morning_star_bars()`, `_engulfing_pair()` helpers)
- [ ] Full `PatternConfig` schema sub-dataclasses
- [ ] Calibration helper `_calibrate(raw, anchors)` + standalone unit tests (4 tests minimum: below min, at typical, above max, monotonic)
- [ ] No new framework install — pytest + pyyaml already present

## config/patterns.yaml — Full Reference Schema

```yaml
# config/patterns.yaml
# Soglie di geometria + calibrazione (min, typical, max) per ogni pattern.
# raw_score per detector definito in 03-RESEARCH.md "Per-pattern raw-score formula".
# Pure geometria — nessun trend/ATR/volume in questa fase (Phase 4+).

hammer:
  geometry:
    body_ratio_max: 0.4              # body <= 40% range
    lower_shadow_body_min: 2.0       # lower shadow >= 2x body
    upper_shadow_range_max: 0.2      # upper shadow <= 20% range
  calibration:
    min: 2.0                         # raw=lower/body=2.0 -> confidence 0.0
    typical: 3.5                     # raw=3.5 -> 0.7
    max: 6.0                         # raw>=6.0 -> 1.0

inverted_hammer:
  geometry:
    body_ratio_max: 0.4
    upper_shadow_body_min: 2.0
    lower_shadow_range_max: 0.2
  calibration:
    min: 2.0
    typical: 3.5
    max: 6.0

shooting_star:
  geometry:
    body_ratio_max: 0.3              # un po' più stringente di inverted_hammer
    upper_shadow_body_min: 2.0
    lower_shadow_range_max: 0.15
  calibration:
    min: 2.0
    typical: 3.5
    max: 6.0

engulfing:
  geometry:
    min_engulfment_ratio: 1.0        # body curr >= body prev
    min_body_ratio: 0.3              # entrambi i body >= 30% del range
  calibration:
    min: 1.0                         # ratio = 1.0 (esatto engulfment) -> 0.0
    typical: 1.5                     # 1.5x -> 0.7
    max: 2.5                         # 2.5x -> 1.0

morning_star:
  geometry:
    trend_body_min_ratio: 0.6        # b1 body >= 60% del suo range
    star_body_max_ratio: 0.3         # b2 body <= 30% del suo range
    min_b3_penetration: 0.5          # b3 close oltre midpoint b1
  calibration:
    min: 0.5                         # penetrazione = midpoint -> 0.0
    typical: 0.8                     # 80% del corpo b1 -> 0.7
    max: 1.2                         # supera l'open di b1 -> 1.0

evening_star:
  geometry:
    trend_body_min_ratio: 0.6
    star_body_max_ratio: 0.3
    min_b3_penetration: 0.5
  calibration:
    min: 0.5
    typical: 0.8
    max: 1.2

key_reversal:
  geometry:
    min_extreme_break_pips: 0.0      # apre OLTRE high/low precedente (>0 strict)
    min_close_penetration_ratio: 0.5 # close oltre midpoint barra precedente
  calibration:
    min: 0.5
    typical: 0.75
    max: 1.0

inside_bar:
  geometry:
    max_compression_ratio: 0.9       # range curr <= 90% range prev
  calibration:
    min: 0.1                         # compressione = 10% -> 0.0
    typical: 0.4                     # 40% compressione -> 0.7
    max: 0.7                         # 70% compressione -> 1.0

pin_bar:
  geometry:
    body_ratio_max: 0.333            # body <= 1/3 range
    dominant_wick_ratio_min: 0.667   # wick dominante >= 2/3 range
  calibration:
    min: 0.667
    typical: 0.75
    max: 0.9

doji:
  geometry:
    body_tolerance: 0.1              # body <= 10% range
  # nessuna calibrazione - confidence sempre 1.0 quando matched
```

## Strategy.py Refactor Surface — Exact diff hint

```python
# strategy.py imports (top of file)
- from patterns import scan_patterns
+ from patterns import scan_patterns, load_pattern_config

# IntradayStrategy.__init__ (find existing __init__ around line 100-180)
+ self._pattern_cfg = load_pattern_config()  # carica una volta a startup

# Line 229
- patterns = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS) if cfg.ENABLE_CANDLESTICK_PATTERNS else []
+ patterns = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS, cfg=self._pattern_cfg) if cfg.ENABLE_CANDLESTICK_PATTERNS else []

# Lines 314-316
- has_pattern_bull = any(p["direction"] == "bullish" for p in patterns)
+ has_pattern_bull = any(p.direction == "bullish" for p in patterns)

# Lines 317-319
- has_pattern_bear = any(p["direction"] == "bearish" for p in patterns)
+ has_pattern_bear = any(p.direction == "bearish" for p in patterns)

# Line 620
- has_aligned = any(p["direction"] == wanted for p in patterns)
+ has_aligned = any(p.direction == wanted for p in patterns)

# tests/test_patterns.py:86
- names = {p["pattern"] for p in found}
+ names = {p.name for p in found}

# tests/test_patterns.py:98
- rels = {p["bar_index"] for p in out}
+ rels = {p.bar_index for p in out}
```

## Project Constraints (from CLAUDE.md)

- EXECUTION_MODE=shadow default — N/A this phase (no broker calls in patterns module)
- **Tutto da .env, zero magic numbers** — STRICT here. Move every constant in `patterns.py` to `config/patterns.yaml`. Verifiable by grep.
- Risk engine = unico gate — N/A
- Un file per fase in .orchestration/phase-prompts/ — handled by orchestration system, not by this code
- STATE.md aggiornato dopo ogni micro-step — handled by execute-plan workflow
- Lingua commenti/log/rationale: italiano — applies to docstrings and comments in `patterns.py`, `tests/test_patterns.py`, `config/patterns.yaml`
- **Test pytest, mock Mt5Client per evitare connessione reale** — patterns has no MT5 dep, no mock needed. Note this in summary.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime | ✓ | 3.12.6 | — |
| PyYAML | `load_pattern_config` | ✓ | 6.0.3 | — |
| pytest | tests | ✓ | (project) | — |
| dataclasses | `PatternHit`, `PatternConfig` | ✓ (stdlib) | 3.12 | — |

**Missing dependencies:** none. All required tooling already installed for Phase 1.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Engulfing should use `span_bars=2` (not 1 or 3) — minor deviation from CONTEXT wording {1,3} | Code Examples | Low — `span_bars=2` is more honest for downstream SL placement; can be flipped to 1 with anchor-only semantics if planner/user prefer |
| A2 | Calibration "knee" at `typical → 0.7` (not 0.5 or 0.8) | Pattern 3 | Low — tunable in Phase 5; chosen to leave headroom for above-typical hits |
| A3 | YAML anchor numerical defaults (e.g. hammer min=2.0, typical=3.5, max=6.0) | config/patterns.yaml schema | Medium — these are reasonable starting points from textbook geometry but un-backtested. Phase 5 backtest will refine. |
| A4 | Doji confidence stays binary (1.0 when matched) — no calibration | YAML schema | Low — Doji is non-PATT per CONTEXT, neutral direction, used only as indecision signal |
| A5 | `extreme_price` over engulfing span = `min(prev.low, curr.low)` for bullish, `max(prev.high, curr.high)` for bearish | Code Examples | Low — natural definition for SL placement |
| A6 | `is_engulfing` etc. switch from `bool` return to `(bool, raw_score)` tuple — breaks 4 existing tests at `tests/test_patterns.py:17-75` | Refactor surface | Low — tests must be updated anyway for dataclass; uniform tuple return simplifies scan_patterns |
| A7 | A new `.env.example` entry for `PATTERNS_CONFIG_PATH` — assumed required by project convention | User constraints | Trivial — verifiable by inspecting current `.env.example` |
| A8 | `load_pattern_config` validates `min < typical < max` and raises `ValueError` | Pitfall 2 | Trivial — defensive code, catches yaml hand-edits |

## Open Questions

1. **Should `is_engulfing` and other already-tested detectors keep their current `bool` signature for direct callers, or unify to `(matched, raw_score)`?**
   - What we know: existing tests in `tests/test_patterns.py:17-75` use bare `assert is_hammer(...) is True`. Unifying to tuple breaks these.
   - What's unclear: whether to expose two functions per pattern (`is_X` -> bool for compatibility, `_score_X` -> tuple internally) or to update tests.
   - **Recommendation:** unify to `(matched, raw_score)`, update existing 6 tests. Less surface area, no shadow API. Planner: include this in the "test refactor" task.

2. **Where does `self._pattern_cfg` get initialized in `IntradayStrategy.__init__`?**
   - What we know: line 229 needs cfg, but `__init__` body wasn't read in research scope.
   - **Recommendation:** load once in `__init__` from `load_pattern_config()` (default path/env). Inject via constructor for tests if needed (but tests of strategy.py don't currently mock patterns — likely fine).

3. **Should `patterns.py` move to a package `patterns/` directory** (e.g. `patterns/__init__.py`, `patterns/detectors.py`, `patterns/config.py`)?
   - **Recommendation:** keep single-file `patterns.py`. Project convention favors flat modules (`indicators.py`, `risk_engine.py`, `execution.py`). Splitting is YAGNI.

## Sources

### Primary (HIGH confidence)
- `C:/trading-agent/patterns.py` (existing) — current geometry rules verified [VERIFIED: read on 2026-05-07]
- `C:/trading-agent/strategy.py` lines 32, 229, 241, 314-321, 619-621 — full refactor surface [VERIFIED: grep + read]
- `C:/trading-agent/backtest/costs.py` — sibling pattern for YAML loader + frozen dataclass [VERIFIED: read 60 lines]
- `C:/trading-agent/data/configs/costs.yaml` — sibling YAML structure [VERIFIED: read]
- `C:/trading-agent/.planning/phases/01-backtest-engine/01-03-PLAN.md` — sibling plan structure [VERIFIED: read]
- `C:/trading-agent/.planning/phases/03-patterns-catalog/03-CONTEXT.md` r2 — locked decisions [VERIFIED]
- `C:/trading-agent/.planning/phases/03-patterns-catalog/03-DISCUSSION-LOG.md` — decision rationale [VERIFIED]
- `C:/trading-agent/tests/test_patterns.py` — existing test fixture style [VERIFIED]
- PyYAML 6.0.3 install confirmed [VERIFIED: `python -c "import yaml; print(yaml.__version__)"` 2026-05-07]

### Secondary (MEDIUM confidence)
- Murphy, *Technical Analysis of the Financial Markets*, ch. 10 (candlestick reversal patterns) — geometry rules for hammer/engulfing/star/key reversal [CITED: `libri/TradingIntermarketMurphy.pdf` present in repo]
- Probo, *Trading Operativo Forex*, price-action chapter — pin bar / inside bar geometry [CITED: `libri/TradingOperativoForexProbo.pdf` present]
- Defendi-style pattern catalog [CITED: `libri/StrategieOperative.pdf` present]

### Tertiary (LOW confidence)
- Specific calibration anchor numerical defaults (A3 above) — textbook starting points, un-backtested. Phase 5 should refine.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — direct sibling pattern in `backtest/costs.py`
- Architecture: HIGH — Phase 1 already validated YAML+frozen-dataclass approach
- Refactor surface: HIGH — full grep performed, 7 call sites identified (locked decision underspecified — see Runtime State Inventory)
- Geometry rules: HIGH for the 4 existing detectors (already in code), MEDIUM for the 4 new (Murphy/Probo book-grounded but not implemented yet)
- Calibration anchor numerical defaults: LOW — un-backtested; Phase 5 will refine

**Research date:** 2026-05-07
**Valid until:** 2026-06-06 (30 days; library versions stable, no fast-moving deps)

---

## RESEARCH COMPLETE

Phase 3 research surfaces (a) the full 7-call-site refactor surface in strategy.py + tests (locked decision under-specified at "line 229"), (b) a near-isomorphic config-loader pattern from Phase 1 to copy verbatim, (c) per-pattern raw-score formulae and a 5-line piecewise-linear calibration helper, (d) full `config/patterns.yaml` schema covering all 9 patterns, and (e) a 30-test validation matrix mapped to PATT-01..07.
