# Phase 3 — Discussion Log

**Date:** 2026-05-07
**Mode:** standard (no flags)

## Areas selected
All 4 gray areas: schema migration, confidence scoring, multi-bar indexing, threshold config.

## Q1 — Output schema migration
**Options:** extend+alias / break+adapter / TypedDict
**Selected:** extend+alias
**User addition:** runtime DeprecationWarning when `'pattern'` key read (not just docstring). Requires dict subclass.

## Q2 — Confidence scoring formula
**Options:** pure geometry / geometry+trend / geometry+ATR
**Selected:** pure geometry
**Rationale:** keep patterns layer pure, Phase 4 strategy adds context.

## Q3 — Multi-bar pattern indexing
**Options:** anchor+span / full 3-index / anchor only
**Selected:** anchor+span
**Rationale:** uniform schema, ML-friendly, span_bars forward-compat for future multi-bar patterns.

## Q4 — Threshold config strategy
**Options:** patterns.yaml / module constants / .env
**Selected:** patterns.yaml
**Rationale:** sibling to backtest/costs.yaml from Phase 1. Tunable, version-controlled.

## Deferred
- Trend-context filter → Phase 4
- ATR normalization → Phase 4 / Phase 7 ML
- Volume confirmation → Phase 10
- Harmonic/chart patterns → future
- Per-symbol threshold tuning → conditional on Phase 5 evidence

## Claude's discretion
- Exact `PatternConfig` field names
- DeprecationWarning implementation: dict subclass vs MutableMapping wrapper (planner picks)
- Geometry-to-confidence formula coefficients per pattern (planner derives, validates against fixtures)
- Whether `load_pattern_config` reads YAML directly or via existing config plumbing
