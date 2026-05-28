# Phase 3: Patterns Catalog — Context

**Gathered:** 2026-05-07
**Updated:** 2026-05-07 (revision 2 — schema, confidence, config, perf revised)
**Status:** Ready for planning
**Source:** /gsd:discuss-phase 3 (interactive, 2 rounds)

<domain>
## Phase Boundary

Replace the existing minimal `patterns.py` with a full candlestick pattern catalog returning structural anchor points (bar_index, extreme_price), confidence scores, and direction. Used downstream by Phase 4 Setup B (reversal) and ML feature extraction.

**In scope:** Hammer / Inverted Hammer (PATT-01), Shooting Star (PATT-02), Bullish/Bearish Engulfing (PATT-03), Morning Star / Evening Star (PATT-04), Key Reversal Bar (PATT-05), Inside Bar / Pin Bar (PATT-06), `PatternHit` schema with confidence + structural refs (PATT-07).

**Out of scope (deferred):** trend-context filtering, ATR normalization, volume confirmation, harmonic patterns, chart patterns (head-and-shoulders etc), performance vectorization.

</domain>

<decisions>
## Implementation Decisions

### Output schema — `@dataclass(frozen=True) PatternHit` (REVISED r2)
- **Switched from extend-dict-with-alias to `@dataclass(frozen=True)`.** No backward-compatible dict alias. No `'pattern'` key, no DeprecationWarning shim.
- Fields:
  - `name: str` — pattern identifier (e.g. `"hammer"`, `"morning_star"`)
  - `bar_index: int` — anchor bar (negative offset from end, e.g. `-1` = last)
  - `span_bars: int` — `1` for single-bar, `3` for star patterns
  - `extreme_price: float` — swing low (bullish) / swing high (bearish) across span
  - `confidence: float` — 0-1, calibrated per pattern (see below)
  - `direction: str` — `"bullish"` | `"bearish"` | `"neutral"`
- Frozen dataclass = hashable, ML-feature-pipeline-friendly, mypy-safe attribute access.
- **`strategy.py:229` MUST be updated in this phase** to consume `.name` attribute instead of `['pattern']` key. Plan must include this refactor task. Existing `tests/test_patterns.py` updated accordingly.

### Confidence — pure geometry + per-pattern calibration anchors (REVISED r2)
- Geometry-only inputs (bar shape, prev-bar relation for multi-bar). No trend, no ATR, no volume.
- **Each pattern has `min`, `typical`, `max` calibration anchors in `config/patterns.yaml`.** Raw geometry score is mapped via piecewise-linear interpolation through the anchors → 0-1 confidence.
- Effect: confidence values are **comparable across pattern types** (a 0.8 hammer ≈ 0.8 engulfing in expected predictive strength). Required for downstream ML feature use.
- Anchors are tuned, not magic — Phase 5 backtest can re-fit them; Phase 7 ML can treat them as hyperparameters.

### Multi-bar indexing — anchor + span_bars + swing extreme (UNCHANGED)
- `bar_index` = anchor bar only (last/confirmation bar).
- `span_bars` = 1 for single-bar, 3 for stars. Forward-compat for future multi-bar patterns.
- `extreme_price` = swing low (bullish) / swing high (bearish) across full span. Used for SL placement in Phase 4.

### Threshold config — `config/patterns.yaml` (REVISED r2)
- **Moved from project root to `config/` subdirectory.** Forward-compat for `config/risk.yaml`, `config/ml.yaml` etc. Cleaner root.
- `load_pattern_config(path: str | None = None) -> PatternConfig` — defaults to `config/patterns.yaml`.
- `PatternConfig` is a frozen dataclass; per-pattern sub-config object with thresholds + calibration anchors.
- Detectors accept `cfg: PatternConfig` parameter — pure functions, no module globals.
- Override path via parameter (tests) or env `PATTERNS_CONFIG_PATH`.
- Zero magic numbers in `patterns.py`.

### Performance — no budget, defer to Phase 5 (NEW r2)
- No latency target this phase. Write clean Python pure-function code (bar-loop dict-style consistent with current).
- If Phase 5 23.5y × 3 pairs × 3 TFs backtest exceeds the 30 min ROADMAP target, profile + optimize then (vectorize, cython, etc).
- Rationale: premature optimization, and ML feature extraction may dominate latency anyway.

### Pattern catalog scope (locked from REQUIREMENTS.md PATT-01..07)
- 7 PATT-XX requirements + Doji (existing, kept for indecision context, not a counted PATT).
- Existing detectors (Hammer, Inverted, Engulfing, Pin Bar) keep geometry rules, gain confidence calibration + extreme_price + dataclass return.
- New detectors: Shooting Star, Morning Star, Evening Star, Key Reversal, Inside Bar.

### Test strategy
- Each detector: unit test hand-crafted positive AND near-miss negative case (per ROADMAP success criterion 1).
- Confidence calibration: snapshot tests on fixture bars asserting expected 0-1 ranges.
- pytest, no MT5 mock needed (pure functions).
- Italian comments per CLAUDE.md.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project rules
- `CLAUDE.md` — italiano comments, zero magic numbers, .env discipline, pytest convention
- `.planning/REQUIREMENTS.md` — PATT-01..07 verbatim definitions
- `.planning/ROADMAP.md` — Phase 3 success criteria

### Existing code (touch / extend)
- `patterns.py` — current minimal catalog. Rewrite return type to dataclass.
- `strategy.py:229` — only consumer of `scan_patterns`. **MUST refactor inline this phase** to attribute access.
- `tests/test_patterns.py` — extend + update assertions for dataclass.

### Pattern definitions (book-grounded)
- `libri/` — Murphy *Technical Analysis*, Probo *forex operativo*, StrategieOperative PDFs. Cite for ambiguous geometry rules.

### Sibling Phase artifacts
- `.planning/phases/01-backtest-engine/` — `backtest/costs.yaml` config-load pattern (sibling for `config/patterns.yaml` structure)

### Skills
- `forex-trader-pro` — Setup B reversal usage of pattern hits
- `forex-algo-dev` — pure-function discipline, no future leakage
- `forex-strategy-builder` — book-grounded pattern geometry

</canonical_refs>

<specifics>
## Specific Ideas

- `config/patterns.yaml` shape:
  ```yaml
  hammer:
    geometry:
      body_ratio_max: 0.4
      lower_shadow_body_min: 2.0
      upper_shadow_range_max: 0.2
    calibration:
      min: 2.0    # raw lower_shadow/body ratio mapped to confidence 0
      typical: 3.5  # mapped to 0.7
      max: 6.0    # mapped to 1.0
  ```
- `PatternHit` import path: `from patterns import PatternHit, scan_patterns`.
- `strategy.py:229` refactor preview:
  ```python
  patterns = scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS, cfg=pattern_cfg)
  for hit in patterns:
      if hit.name == "hammer" and hit.confidence >= threshold: ...
  ```
- `span_bars` is forward-compat for 3-Black-Crows, 3-White-Soldiers (future).
- `direction = "neutral"` reserved for Doji; reversal patterns use bullish/bearish.

</specifics>

<deferred>
## Deferred Ideas

- Trend-context filter (hammer-post-downtrend gating) → Phase 4 Strategy
- ATR-relative significance scoring → Phase 4 / Phase 7 ML features
- Volume confirmation → Phase 10
- Harmonic / chart patterns (H&S, double-top) → future milestone backlog
- Per-symbol threshold tuning (different patterns.yaml per pair) → if Phase 5 backtest evidence justifies
- Performance vectorization (numpy/pandas detectors) → Phase 5 if 23.5y backtest slow
- Strict-mode runtime enforcement (was r1 plan via DeprecationWarning) — moot now that dict alias dropped

</deferred>

---

*Phase: 03-patterns-catalog*
*Context r1 gathered: 2026-05-07*
*Context r2 revised: 2026-05-07 — schema → dataclass, confidence → calibrated, config → config/ subdir, perf deferred*
