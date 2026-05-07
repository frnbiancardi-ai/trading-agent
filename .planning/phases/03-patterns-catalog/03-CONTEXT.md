# Phase 3: Patterns Catalog — Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Source:** /gsd:discuss-phase 3 (interactive)

<domain>
## Phase Boundary

Replace the existing minimal `patterns.py` with a full candlestick pattern catalog returning structural anchor points (bar_index, extreme_price), confidence scores, and direction. Used downstream by Phase 4 Setup B (reversal) and ML feature extraction.

**In scope:** Hammer / Inverted Hammer (PATT-01), Shooting Star (PATT-02), Bullish/Bearish Engulfing (PATT-03), Morning Star / Evening Star (PATT-04), Key Reversal Bar (PATT-05), Inside Bar / Pin Bar (PATT-06), `PatternHit` schema with confidence + structural refs (PATT-07).

**Out of scope (deferred):** trend-context filtering, ATR normalization, volume confirmation, harmonic patterns, chart patterns (head-and-shoulders etc).

</domain>

<decisions>
## Implementation Decisions

### Output schema migration
- **Extend dict + alias**: new `PatternHit` dict has `name`, `bar_index`, `extreme_price`, `confidence` (0-1), `direction`, `span_bars`. Keep `'pattern'` key as alias for `'name'` (same value) for backward compatibility with `strategy.py:229`.
- **Runtime DeprecationWarning**: when consumer reads the `'pattern'` key, emit `DeprecationWarning` at runtime — not just a docstring note. Implement via dict subclass `__getitem__` override or `MutableMapping` wrapper. User-locked: must be a real runtime warning, not passive doc.
- Migration target: callers move to `'name'` key; warning triggers for full milestone before removal.

### Confidence scoring
- **Pure geometry only**. Score derived from bar shape: body/range ratio, shadow proportions, prev-bar relation. No trend context, no ATR, no volume.
- Pure function: `(bar_or_bars) -> float in [0,1]`. Deterministic. Easy unit-test.
- Trend gating, regime weighting = Phase 4 strategy concern, not pattern concern.

### Multi-bar indexing (Morning/Evening Star)
- `bar_index` = **anchor only** (last/confirmation bar, e.g. `-1`).
- `span_bars` field: `1` for single-bar patterns, `3` for star patterns (extensible later).
- `extreme_price` = swing low (bullish) or swing high (bearish) computed across the full span — used for SL placement.

### Threshold config
- **patterns.yaml** at project root (sibling of `backtest/costs.yaml` from Phase 1). Single file, all pattern thresholds.
- Loaded once via `load_pattern_config(path: str | None) -> PatternConfig` (typed dict or @dataclass).
- Detectors accept `cfg: PatternConfig` parameter — pure functions, no module-level globals.
- Default config path: `./patterns.yaml`. Override via param (for tests) or env `PATTERNS_CONFIG_PATH`.
- Zero magic numbers in `patterns.py` per CLAUDE.md rule.

### Pattern catalog scope (locked from REQUIREMENTS.md PATT-01..07)
- 7 patterns minimum: Hammer, Inverted Hammer, Shooting Star, Engulfing (bull/bear), Morning Star, Evening Star, Key Reversal, Inside Bar, Pin Bar.
- Existing detectors keep their geometry rules but add `confidence` + `extreme_price` outputs.
- Doji stays (already exists, useful for indecision context) but is not a counted PATT-XX.

### Test strategy
- Each detector: unit test with hand-crafted positive AND near-miss negative case (per ROADMAP success criterion 1).
- pytest, no live broker, no MT5 mock needed (pure functions on bar dicts).
- Italian comments in tests + module per CLAUDE.md.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project rules
- `CLAUDE.md` — italiano comments, zero magic numbers, .env discipline, pytest convention
- `.planning/REQUIREMENTS.md` — PATT-01..07 verbatim definitions
- `.planning/ROADMAP.md` — Phase 3 success criteria (3 items)

### Existing code (touch / extend)
- `patterns.py` — current minimal catalog (Hammer, Inverted, Engulfing, Doji, Pin Bar). Extend, do not rewrite from scratch.
- `strategy.py:229` — only consumer of `scan_patterns`. Backward compat must hold.
- `tests/test_patterns.py` — existing tests. Extend.

### Pattern definitions (book-grounded)
- `libri/` — Murphy *Technical Analysis*, Probo *forex operativo*, StrategieOperative PDFs. Cite for ambiguous geometry rules. Use `forex-strategy-builder` skill if needed.

### Sibling Phase artifacts
- `.planning/phases/01-backtest-engine/` — costs.yaml pattern (sibling for patterns.yaml structure)

### Skills
- `forex-trader-pro` — how Setup B uses pattern hits for reversal trades
- `forex-algo-dev` — pure-function discipline, no future leakage
- `forex-strategy-builder` — book-grounded pattern geometry citations

</canonical_refs>

<specifics>
## Specific Ideas

- `PatternConfig` shape (suggested for planner): per-pattern sub-dict with body/shadow/range ratio thresholds. Example:
  ```yaml
  hammer:
    body_ratio_max: 0.4
    lower_shadow_body_min: 2.0
    upper_shadow_range_max: 0.2
  ```
- DeprecationWarning implementation hint: subclass `dict` override `__getitem__`, or use `collections.abc.MutableMapping`. Tests must assert warning fires on `hit['pattern']` and does NOT fire on `hit['name']`.
- `span_bars` field is forward-compat for future multi-bar patterns (3-Black-Crows, 3-White-Soldiers) — don't gate on it now but reserve.

</specifics>

<deferred>
## Deferred Ideas

- Trend-context filter (hammer-post-downtrend gating) → Phase 4 Strategy
- ATR-relative significance scoring → Phase 4 / Phase 7 ML features
- Volume confirmation → Phase 10 (intermarket has order-flow proxies)
- Harmonic / chart patterns (H&S, double-top) → future milestone backlog
- Per-symbol threshold tuning (different patterns.yaml per pair) → if backtest evidence justifies in Phase 5

</deferred>

---

*Phase: 03-patterns-catalog*
*Context gathered: 2026-05-07 via /gsd:discuss-phase*
