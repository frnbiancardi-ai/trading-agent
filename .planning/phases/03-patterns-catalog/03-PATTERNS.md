# Phase 3: Patterns Catalog — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 4 (1 rewritten, 1 modified, 1 extended, 1 new) + 1 new YAML
**Analogs found:** 5 / 5 (every file has a strong sibling in the codebase)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `patterns.py` (rewrite) | pure-fn library + config loader + frozen dataclass schema | transform (bars → list[PatternHit]) | `backtest/costs.py` | exact (config + frozen-dataclass + loader); role-match (pure-fn lib) |
| `config/patterns.yaml` (new) | YAML config (per-key thresholds + calibration anchors) | config | `data/configs/costs.yaml` | exact (sibling YAML config) |
| `strategy.py` (modify, 5 sites) | controller / orchestrator (consumer refactor) | request-response | itself (current `patterns.py` consumer at lines 229,241,314-319,620) | self-refactor (no external analog needed — replace `p["k"]` → `p.k`) |
| `tests/test_patterns.py` (extend) | unit tests (pure-fn detector + dataclass schema + calibration + config loader) | test | `tests/test_backtest_costs.py` | exact (sibling: dataclass + yaml-load + KeyError + numerical tolerance) |

## Pattern Assignments

### `patterns.py` (rewrite — pure-fn library + frozen dataclass + YAML loader)

**Analogs:** `backtest/costs.py` (config-loader + frozen-dataclass), existing `patterns.py` (geometry helpers to retain)

**Imports pattern** — copy verbatim from `backtest/costs.py:1-5`:
```python
"""Riconoscimento pattern candlestick + calibrazione confidence (Phase 3).

Bar dict atteso: {'open': float, 'high': float, 'low': float, 'close': float, ...}
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import yaml
```
(`os` is the only addition over costs.py — needed for `PATTERNS_CONFIG_PATH` env override.)

**Frozen dataclass schema pattern** — mirror `backtest/costs.py:8-22`:
```python
# Source analog: backtest/costs.py:8-14
@dataclass(frozen=True)
class CostModel:
    spread_pips: float
    slippage_pips: float
    ...
```
Apply identically to `PatternHit`, `CalibrationAnchors`, every per-pattern sub-cfg, and `PatternConfig`. Every dataclass `frozen=True`; nested dataclasses make the parent transitively immutable + hashable. Sub-cfgs may carry `@property` helpers analogous to `total_cost_pips` if useful (not required this phase).

**Geometry helpers — KEEP from existing `patterns.py:8-29`:**
```python
def _body(bar: dict) -> float:
    return abs(bar["close"] - bar["open"])
def _range(bar: dict) -> float:
    return bar["high"] - bar["low"]
def _upper_shadow(bar: dict) -> float:
    return bar["high"] - max(bar["open"], bar["close"])
def _lower_shadow(bar: dict) -> float:
    return min(bar["open"], bar["close"]) - bar["low"]
def _is_bullish(bar: dict) -> bool: ...
def _is_bearish(bar: dict) -> bool: ...
```
These survive the rewrite — every detector reuses them.

**Detector signature change — derive from existing `patterns.py:32-51`:**
Existing detector returns `bool`. New detector returns `tuple[bool, float]` (`(matched, raw_score)`). Keep the early `if rng <= 0 or body <= 0` guard verbatim — that's the NaN-prevention pattern (Pitfall 1). Example shape (current → new):
```python
# CURRENT patterns.py:32-40 (keep guard, change return + thresholds source)
def is_hammer(bar: dict, cfg: HammerCfg) -> tuple[bool, float]:
    rng = _range(bar); body = _body(bar)
    if rng <= 0 or body <= 0:
        return False, 0.0
    lower = _lower_shadow(bar); upper = _upper_shadow(bar)
    matched = (
        body  <= cfg.body_ratio_max         * rng
        and lower >= cfg.lower_shadow_body_min * body
        and upper <= cfg.upper_shadow_range_max * rng
    )
    return (matched, lower / body) if matched else (False, 0.0)
```
All 9 detectors follow this `(matched, raw_score)` shape. Raw-score formulae are documented in RESEARCH `Per-pattern raw-score formula` table.

**Config loader pattern** — mirror `backtest/costs.py:42-59` exactly, extending for env override + nested dataclass build:
```python
# Source analog: backtest/costs.py:42-59
DEFAULT_CONFIG_PATH = Path("config/patterns.yaml")

def load_pattern_config(path: str | Path | None = None) -> PatternConfig:
    # Precedenza: parametro > env PATTERNS_CONFIG_PATH > default
    if path is None:
        path = os.environ.get("PATTERNS_CONFIG_PATH") or DEFAULT_CONFIG_PATH
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}      # NB: `or {}` from costs.py:45 (Pitfall 7)
    # Validazione + costruzione dataclass annidate; KeyError su chiavi mancanti
    # (analog: costs.py:47-50 raises KeyError when symbol missing)
    return _build_pattern_config(raw)      # raises ValueError if min>=typical>=max
```
Key parallels:
- `with open(path, encoding="utf-8") as f` — identical to costs.py:44
- `yaml.safe_load(f) or {}` — identical to costs.py:45 (handles empty file)
- `raise KeyError(f"...")` on missing required key — pattern from costs.py:50
- New: validate `min < typical < max` per pattern, `raise ValueError` (Pitfall 2)

**Calibration helper** — new, no analog (pure math, 5 lines):
```python
def _calibrate(raw: float, anchors: CalibrationAnchors) -> float:
    """Mappa raw score in [0,1] via interpolazione lineare a tratti."""
    lo, typ, hi = anchors.min, anchors.typical, anchors.max
    if raw <= lo: return 0.0
    if raw >= hi: return 1.0
    if raw < typ: return 0.7 * (raw - lo) / (typ - lo)
    return 0.7 + 0.3 * (raw - typ) / (hi - typ)
```

**`scan_patterns` core loop** — derive from existing `patterns.py:106-136`:
Existing structure (loop indices, `rel = i - n` for negative offsets, `i > 0` guard for prev-bar) is correct and stays. Each `if is_X(...)` block changes from `out.append({"pattern":..., "bar_index":rel, "direction":...})` (dict) to `out.append(PatternHit(name=..., bar_index=rel, span_bars=..., extreme_price=..., confidence=_calibrate(raw, cfg.X.calibration), direction=...))`. Add `i >= 2` guard for 3-bar star detectors. Add `cfg=None → load_pattern_config()` default at top.

**Error handling pattern** — copy from `backtest/costs.py:47-50`:
```python
sym_cfg = cfg.get(symbol)
if sym_cfg is None: raise KeyError(f"no cost config for symbol {symbol!r} in {yaml_path}")
```
Apply analogously per pattern key in `_build_pattern_config`. Use `KeyError` for missing keys, `ValueError` for invalid anchor ordering.

---

### `config/patterns.yaml` (new file)

**Analog:** `data/configs/costs.yaml`

**Structure pattern** (full file analog `data/configs/costs.yaml:1-18`):
```yaml
# data/configs/costs.yaml — header comment + per-symbol blocks
EURUSD:
  spread_pips: 0.5
  slippage_pips: 0.3
  commission_pips_round_trip: 0.5
GBPUSD:
  spread_pips: 0.7
  ...
```
Apply same shape to `config/patterns.yaml`: header comment in italiano, then one top-level key per pattern, each with `geometry:` + `calibration:` sub-blocks. Full reference schema pre-specified in RESEARCH lines 572-667 — copy verbatim into the new file. Italian comments per CLAUDE.md.

**Conventions to copy:**
- Top-of-file comment block describing purpose + units
- Numeric literals as plain floats (no quoting)
- Two-space indent
- Blank line between top-level keys

**Note on directory:** sibling lives in `data/configs/`, this phase creates `config/` (per CONTEXT r2 decision). The directory itself must be created — Phase 1's location is NOT reused.

---

### `strategy.py` (modify — 5 call sites, atomic refactor)

**Analog:** none external — this is a self-refactor of existing dict-key access to attribute access. The "pattern to copy" is the new `PatternHit` shape from `patterns.py` (this phase).

**Imports pattern** (top of file):
```python
# CURRENT
from patterns import scan_patterns
# TARGET
from patterns import scan_patterns, load_pattern_config
```

**Init pattern** (`IntradayStrategy.__init__`, locate existing init body):
```python
# ADD inside __init__ body
self._pattern_cfg = load_pattern_config()  # carica una volta a startup
```

**Call-site refactor — exact 5 edits** (line numbers from current strategy.py read):
```python
# Line 229 — pass cfg through
- patterns = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS) if cfg.ENABLE_CANDLESTICK_PATTERNS else []
+ patterns = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS, cfg=self._pattern_cfg) if cfg.ENABLE_CANDLESTICK_PATTERNS else []

# Line 315 — dict to attr
- has_pattern_bull = any(p["direction"] == "bullish" for p in patterns)
+ has_pattern_bull = any(p.direction == "bullish" for p in patterns)

# Line 318 — dict to attr
- has_pattern_bear = any(p["direction"] == "bearish" for p in patterns)
+ has_pattern_bear = any(p.direction == "bearish" for p in patterns)

# Line 620 — dict to attr (inside _score_confidence)
- has_aligned = any(p["direction"] == wanted for p in patterns)
+ has_aligned = any(p.direction == wanted for p in patterns)

# Line 241 — `indicators_snapshot["patterns"] = patterns` STAYS unchanged (still a list,
#   now of PatternHit instead of dict; downstream consumers must adapt — document)
```

**No error-handling change required** — the refactor is purely accessor-style; `scan_patterns` contract still returns a list, just of dataclasses instead of dicts.

---

### `tests/test_patterns.py` (extend — assertions update + ~30 new tests)

**Analog:** `tests/test_backtest_costs.py` (frozen-dataclass + yaml-load + KeyError test pattern)

**Import + helper pattern** (extend existing `tests/test_patterns.py:1-14`):
```python
# CURRENT (keep)
from patterns import is_doji, is_engulfing, is_hammer, is_inverted_hammer, is_pin_bar, scan_patterns
# ADD
from patterns import (
    PatternHit, PatternConfig, CalibrationAnchors,
    load_pattern_config, _calibrate,
    is_shooting_star, is_morning_star, is_evening_star,
    is_key_reversal, is_inside_bar,
)

def _bar(o, h, l, c, vol=100):  # existing line 13 — keep verbatim
    return {"open": o, "high": h, "low": l, "close": c, "tick_volume": vol}
```

**Detector signature update pattern** (existing line 19, 24, 29, ...):
```python
# CURRENT (line 19)
- assert is_hammer(bar) is True
# TARGET (detectors now return tuple)
+ matched, raw = is_hammer(bar, cfg.hammer)
+ assert matched is True
+ assert raw >= cfg.hammer.calibration.min
```
Apply to all 6 existing positive/negative tests at lines 17-75. Each test must construct or fixture-load a `PatternConfig`.

**Dict-to-attribute test refactor** (existing lines 86, 98):
```python
# Line 86
- names = {p["pattern"] for p in found}
+ names = {p.name for p in found}

# Line 98
- rels = {p["bar_index"] for p in out}
+ rels = {p.bar_index for p in out}
```

**YAML-load test pattern** — copy structure from `tests/test_backtest_costs.py:30-42`:
```python
# Source analog: tests/test_backtest_costs.py:30-37
def test_yaml_load(costs_yaml_path: Path) -> None:
    model = load_cost_model("EURUSD", 1.10000, costs_yaml_path)
    assert model.spread_pips == 0.5
    ...

# Source analog: tests/test_backtest_costs.py:40-42 (KeyError on bad key)
def test_yaml_unknown_symbol_raises(costs_yaml_path: Path) -> None:
    with pytest.raises(KeyError):
        load_cost_model("XAUUSD", 2000.0, costs_yaml_path)
```
Apply same shape for `test_load_pattern_config_default`, `test_load_config_invalid_anchors_raises` (use `pytest.raises(ValueError)`), `test_load_config_empty_yaml`, `test_load_config_env_override` (with `monkeypatch.setenv("PATTERNS_CONFIG_PATH", ...)`).

**Numerical-tolerance assertion pattern** — copy from `tests/test_backtest_costs.py:20`:
```python
assert abs(cost - 10.0) < 1e-9, f"expected $10.00, got ${cost:.6f}"
```
Use for calibration tests (`_calibrate(typ, anchors)` should be `≈ 0.7`):
```python
assert abs(_calibrate(typ, anchors) - 0.7) < 1e-9
```

**Frozen-dataclass test pattern** — new (no analog uses this):
```python
def test_pattern_hit_frozen_schema():
    h = PatternHit(name="hammer", bar_index=-1, span_bars=1,
                   extreme_price=1.0980, confidence=0.7, direction="bullish")
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        h.confidence = 0.9
    assert hash(h) is not None      # frozen dataclass is hashable
```

**Test list (full 30+) sourced from RESEARCH `Phase Requirements → Test Map` table at lines 515-557.** Planner should emit tests in waves matched to detector implementation order.

---

## Shared Patterns

### Frozen-dataclass schema (apply to: `PatternHit`, `PatternConfig`, all sub-cfgs, `CalibrationAnchors`)
**Source:** `backtest/costs.py:8-14`
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CostModel:
    spread_pips: float
    slippage_pips: float
    ...
```
Every new dataclass in `patterns.py` uses `@dataclass(frozen=True)`. Nested dataclasses must ALSO be frozen (Pitfall 6) — `PatternConfig` containing mutable `dict` sub-fields would defeat hashability.

### YAML safe-load with empty-file guard (apply to: `load_pattern_config`)
**Source:** `backtest/costs.py:44-45`
```python
with open(yaml_path, encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}      # `or {}` handles empty-file → None edge case
```
Identical idiom in `load_pattern_config`. Both `safe_load` (security: T-1-06 STRIDE) and `or {}` (Pitfall 7) are non-negotiable.

### Missing-key error handling (apply to: `load_pattern_config` validation)
**Source:** `backtest/costs.py:47-50`
```python
sym_cfg = cfg.get(symbol)
if sym_cfg is None:
    sym_cfg = cfg.get("default")
if sym_cfg is None:
    raise KeyError(f"no cost config for symbol {symbol!r} in {yaml_path}")
```
Pattern: try the key, fall back if applicable, raise `KeyError` with informative message including key name and path. Apply per-pattern in `_build_pattern_config`. NB: no "default" fallback for patterns — every pattern must be present, or raise.

### Italian docstrings + comments (apply to: every new function in `patterns.py`, every test file, `config/patterns.yaml`)
**Source:** existing `patterns.py:1-5`, `patterns.py:33,55,77,87,107`
```python
"""Riconoscimento pattern candlestick base in Python puro.

Bar dict atteso: {'open': float, ...}
"""

def is_hammer(bar: dict) -> bool:
    """Hammer: long lower shadow (>=2x body), upper shadow <=20% range, body <=40% range."""
```
Per CLAUDE.md "Lingua commenti/log/rationale: italiano". All new docstrings, inline comments, YAML headers in Italian.

### NaN/zero-range guard (apply to: every detector)
**Source:** existing `patterns.py:36-37, 47-48, 61, 80-81, 94-95`
```python
rng = _range(bar); body = _body(bar)
if rng <= 0 or body <= 0:
    return False, 0.0   # was: return False
```
Universal early-return idiom. Every new detector (`is_shooting_star`, `is_morning_star`, etc.) opens with this guard, on every bar it inspects (3-bar stars guard b1, b2, AND b3). Prevents Pitfall 1 (NaN confidence).

### pytest tolerance assertion (apply to: calibration tests, `_calibrate` boundary tests)
**Source:** `tests/test_backtest_costs.py:20, 27, 35, 37`
```python
assert abs(cost - 10.0) < 1e-9, f"expected $10.00, got ${cost:.6f}"
```
Use `< 1e-9` for calibration boundary tests where exact float equality is fragile.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Every artifact in this phase has a strong sibling. New detectors (`is_shooting_star`, `is_morning_star`, `is_evening_star`, `is_key_reversal`, `is_inside_bar`) follow the existing `is_hammer`/`is_inverted_hammer` template (early guard + geometry comparison + return). Calibration helper `_calibrate` is 5 lines of pure math — no codebase analog needed. |

## Metadata

**Analog search scope:** `C:/trading-agent/backtest/`, `C:/trading-agent/tests/`, repo root (`patterns.py`, `strategy.py`, `indicators.py`, `risk_engine.py`, `execution.py`), `data/configs/`
**Files scanned:** 8 (4 analog candidates read + 4 grep'd for cross-reference)
**Pattern extraction date:** 2026-05-07
**Key insight:** Phase 1 (Backtest Engine) `backtest/costs.py` + `data/configs/costs.yaml` + `tests/test_backtest_costs.py` is a **near-isomorphic triplet** for this phase's `patterns.py` + `config/patterns.yaml` + `tests/test_patterns.py`. The planner should explicitly direct implementation to mirror that triplet. The only structural delta is: this phase has more dataclasses (one per pattern) and adds the calibration helper — neither breaks the analog.

---

## PATTERN MAPPING COMPLETE

**Phase:** 3 - Patterns Catalog
**Files classified:** 4 (+ 1 new YAML)
**Analogs found:** 5 / 5

### Coverage
- Files with exact analog: 3 (`patterns.py` ↔ `backtest/costs.py`; `config/patterns.yaml` ↔ `data/configs/costs.yaml`; `tests/test_patterns.py` ↔ `tests/test_backtest_costs.py`)
- Files with role-match analog: 1 (existing `patterns.py` retains geometry helpers + scan-loop skeleton)
- Self-refactor: 1 (`strategy.py` — 5 call sites, no external pattern needed)
- Files with no analog: 0

### Key Patterns Identified
- **Phase-1 isomorphism:** every Phase 3 artifact has a structural twin in Phase 1 (`backtest/costs.*`). Mirror it line-for-line where shape allows.
- **Frozen dataclass + YAML loader + KeyError-on-missing:** the project's standard config-load idiom. Reuse without invention.
- **`yaml.safe_load(f) or {}`:** non-negotiable empty-file guard.
- **Geometry-helper reuse:** `_body`, `_range`, `_upper_shadow`, `_lower_shadow` survive the rewrite — every new detector calls them.
- **`(matched, raw_score)` tuple return:** unifies all 9 detectors; breaks 6 existing tests (knowingly, planner must update).
- **Italian docstrings:** CLAUDE.md mandate — applies to every line of new prose.

### File Created
`C:/trading-agent/.planning/phases/03-patterns-catalog/03-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns + line numbers in PLAN.md. Recommend the planner emit waves in this order: (W1) `config/patterns.yaml` + `PatternHit`/`PatternConfig` dataclasses + `_calibrate` + `load_pattern_config` + their tests; (W2) refactor existing 4 detectors to `(matched, raw_score)` + update existing 6 tests; (W3) implement 5 new detectors + their unit tests; (W4) atomic strategy.py 5-site refactor + regression test pass.
