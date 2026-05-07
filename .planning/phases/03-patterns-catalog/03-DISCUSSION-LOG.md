# Phase 3 — Discussion Log

**Date:** 2026-05-07
**Mode:** standard (2 rounds — initial + update)

---

## Round 1 (initial)

### Areas selected
All 4: schema migration, confidence scoring, multi-bar indexing, threshold config.

### Q1 — Output schema migration
**Options:** extend+alias / break+adapter / TypedDict
**Selected r1:** extend+alias + runtime DeprecationWarning on `'pattern'` key access.

### Q2 — Confidence scoring formula
**Options:** pure geometry / geometry+trend / geometry+ATR
**Selected r1:** pure geometry.

### Q3 — Multi-bar pattern indexing
**Options:** anchor+span / full 3-index / anchor only
**Selected r1:** anchor+span.

### Q4 — Threshold config strategy
**Options:** patterns.yaml / module constants / .env
**Selected r1:** patterns.yaml at project root.

---

## Round 2 (update)

User invoked /gsd:discuss-phase 3 again, chose "Update it". All 4 areas revisited + 1 new.

### Q1' — Schema migration (REVISED)
**Options:** keep / strict-mode hard-error / TypedDict / @dataclass(frozen=True)
**Selected r2:** **@dataclass(frozen=True) PatternHit**.
**Effect:** drops `'pattern'` key alias entirely, drops runtime DeprecationWarning. Update `strategy.py:229` inline this phase to attribute access.

### Q2' — Confidence formula (REVISED)
**Options:** keep pure-geom / pure-geom + per-pattern calibration table / geom + prev-bar
**Selected r2:** **pure geometry + per-pattern calibration anchors in patterns.yaml**.
**Effect:** confidences comparable across pattern types; each pattern has min/typical/max anchors mapped piecewise-linear → 0-1.

### Q3' — Multi-bar indexing
**Options:** keep / add start_bar_index / add invalidation_price
**Selected r2:** **keep** (anchor + span_bars + extreme_price).

### Q4' — Threshold config (REVISED)
**Options:** keep root / move to config/ subdir / merge into costs.yaml
**Selected r2:** **`config/patterns.yaml`** (subdir). Forward-compat for risk.yaml, ml.yaml.

### Q5 — Performance budget (NEW)
**Options:** <50µs target / vectorize numpy / no budget defer to Phase 5
**Selected r2:** **no budget, defer**. Profile in Phase 5 if 23.5y backtest exceeds 30 min.

---

## Final locked decisions (r2)

| Area | Decision |
|---|---|
| Schema | `@dataclass(frozen=True) PatternHit`, attribute access, refactor `strategy.py:229` inline |
| Confidence | Pure geometry + calibration anchors (min/typical/max) per pattern in patterns.yaml |
| Multi-bar | bar_index=anchor + span_bars + extreme_price (swing) |
| Config | `config/patterns.yaml`, `PatternConfig` frozen dataclass, env override `PATTERNS_CONFIG_PATH` |
| Perf | No budget, defer to Phase 5 |

## Deferred
- Trend-context filter → Phase 4
- ATR normalization → Phase 4 / Phase 7 ML
- Volume confirmation → Phase 10
- Harmonic/chart patterns → future
- Per-symbol threshold tuning → conditional on Phase 5 evidence
- Performance vectorization → Phase 5 if needed
- Strict-mode dict-alias enforcement (r1 idea, moot now)

## Claude's discretion
- Exact `PatternConfig` and per-pattern dataclass field names
- Geometry-to-raw-score formula per pattern (planner derives, validates against fixtures)
- Piecewise-linear interpolation impl detail
- Whether `load_pattern_config` reads YAML directly or via existing config plumbing
- Doji handling: keep but mark non-PATT (already in r1 decisions)
