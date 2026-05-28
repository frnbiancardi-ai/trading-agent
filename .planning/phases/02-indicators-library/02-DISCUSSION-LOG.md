# Phase 2: Indicators Library — Discussion Log

**Date:** 2026-05-07
**Mode:** /gsd-discuss-phase (default)

## Areas Selected

User selected all 4 presented gray areas:
1. Module layout
2. Compound return shape
3. Test reference oracle
4. Session anchoring + MTF/regime semantics

---

## Area 1 — Module layout

**Q1.1:** Flat `indicators.py` (280→~1500 lines) vs `indicators/` package vs hybrid `indicators_extra.py`?
- **Selected:** Split into `indicators/` package (D-01).

**Q1.2:** Submodule split granularity — granular (7+ files) vs coarse (4 files) vs Claude-decide?
- **Selected:** Granular (D-02).

**Q1.3:** Existing helpers (`compute_all`, `calculate_trend_strength`, `find_support_resistance`, `avg_volume`, `check_breakout_quality`, `calculate_risk_reward`, `check_rsi_divergence`) — distribute into matching submodules vs `legacy.py` vs Claude-decide?
- **Selected:** Distribute into matching submodules (D-02 mapping).

**Note:** Verified 4 real callsites (`claude_agent.py:12`, `mcp_server.py:28`, `scanner.py:10`, `strategy.py:11`) → re-exports via `__init__.py` keep them unchanged (D-03).

---

## Area 2 — Compound return shape

**Q2.1:** Bollinger/MACD/ADX/Keltner/Stoch return shape — dataclass-of-lists vs dict-of-lists vs tuple vs per-bar snapshot?
- **Selected:** Dataclass-of-lists (D-04). Typed, IDE-friendly, leakage audit easy.

**Q2.2:** Dataclass placement — co-located in submodule vs centralized `models.py` vs new `indicators/types.py`?
- **Selected:** Co-located in owning submodule with `<Indicator>Result` suffix (D-05).

**Q2.3:** Single-series indicators (Donchian, VWAP, Hurst, Closing Score, NR4/7, regime) — same uniform dataclass treatment vs mixed (list for simple) vs partial?
- **Selected:** Uniform dataclass everywhere (D-04 / D-06). Consistent API across all 14.

---

## Area 3 — Test reference oracle

**Q3.1:** Primary oracle — pandas-ta dev-dep vs TradingView screenshots vs hand-calc vs hybrid?
- **Selected:** Hybrid (D-07).

**Q3.2:** Hybrid split — tier-by-complexity vs pandas-ta-everywhere vs Claude-decide-per-indicator?
- **Selected:** Tier-by-complexity (D-07): pandas-ta for Bollinger/ADX/MACD/Stoch/Keltner/regime/Hurst; hand-calc for NR4-7/ClosingScore/Donchian/Fib/Pivot/MTF; TV spot-check for Bollinger+ADX.

**Q3.3:** Fixture data — slice from existing CSV vs synthetic random walk vs multi-symbol parametrized?
- **Selected:** Slice from existing CSV (D-08) — last 500 bars EURUSD H1, snapshotted to `tests/fixtures/eurusd_h1_last500.csv`.

---

## Area 4 — Session anchoring + MTF + Regime

**Q4.1:** Session boundary for VWAP/Pivot — NY 17:00 EST rollover vs UTC midnight vs Europe/Rome midnight vs configurable?
- **Selected:** NY 17:00 EST rollover (D-10). DST-aware via `zoneinfo.ZoneInfo("America/New_York")`.

**Q4.2:** INDIC-13 MTF alignment — dict input + sign-agreement vs positional + ADX-weighted vs reuse `calculate_trend_strength` averaged vs Claude-decide?
- **Selected:** Dict input + sign-agreement of EMA50-slope (D-13 / D-14). Score ∈ {0, 0.33, 0.66, 1.0}.

**Q4.3:** INDIC-14 regime thresholds — configurable `regime.yaml` vs fixed in code vs auto-derive?
- **Selected:** Configurable `data/configs/regime.yaml` (D-15). Auto-derive rejected (look-ahead risk).

---

## Deferred Ideas Captured

- Auto-derive INDIC-14 thresholds (revisit Phase 9 drift).
- Multi-broker session anchors via `sessions.yaml`.
- Anchored VWAP convenience presets.
- ADX divergence detector.
- Volume-profile / TPO indicators (v3).

## Claude's Discretion (planner decides)

- Hurst estimator (R/S vs DFA).
- Fibonacci swing-leg detection algo.
- ADX smoothing variant.
- BollingerBands `squeeze` threshold default.
- NR4/7 + Boomer sequence rules.
- `compute_all` extension vs split.
- Internal helper module placement (`_helpers.py`).

---

*Total questions asked: 12 across 4 areas. No scope creep encountered. All decisions captured in 02-CONTEXT.md.*
