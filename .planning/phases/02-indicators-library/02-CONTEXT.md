# Phase 2: Indicators Library — Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Add the 14 indicators required by the forex-trader-pro playbook (Bollinger+squeeze, ADX/DMI, MACD, Stochastic, Donchian, Keltner, VWAP intraday+anchored, Fibonacci on swing legs, Pivots daily/session/weekly classic+Camarilla, NR4/7+Boomer, Closing Score, Hurst, multi-TF alignment H4+H1+M15, ATR-percentile volatility regime classifier) as pure functions consumable by both live (`scheduler.py`/`strategy.py`) and backtest (Phase 1 engine) paths.

Phase 2 ships only the indicator surface + tests. Phase 3 (patterns) and Phase 4 (strategy refactor) consume the API. Phase 5 (baseline backtest) exercises against 23.5y historical.

</domain>

<decisions>
## Implementation Decisions

### Module layout
- **D-01:** Promote flat `indicators.py` (280 lines) to `indicators/` package. Backward-compat preserved by `indicators/__init__.py` re-exports — no churn at the 4 callsites (`claude_agent.py:12`, `mcp_server.py:28`, `scanner.py:10`, `strategy.py:11`).
- **D-02:** Granular submodule split:
  - `indicators/momentum.py` — RSI, MACD, Stochastic, ADX/DMI, `check_rsi_divergence`
  - `indicators/volatility.py` — ATR, Bollinger Bands+squeeze, Keltner, volatility-regime classifier (INDIC-14)
  - `indicators/structure.py` — Donchian, Pivots (classic+Camarilla, daily/session/weekly), Fibonacci retracements on detected swings, `find_support_resistance`, `check_breakout_quality`
  - `indicators/volume.py` — VWAP intraday + anchored, `avg_volume`
  - `indicators/bars.py` — NR4/NR7+Boomer, Closing Score, `calculate_risk_reward`
  - `indicators/mtf.py` — INDIC-13 multi-TF alignment + `calculate_trend_strength`
  - `indicators/hurst.py` — Hurst exponent (rolling)
  - `indicators/trend.py` — SMA, EMA (existing primitives)
  - `indicators/aggregate.py` — `compute_all` snapshot helper (extended with new indicators)
- **D-03:** All public symbols re-exported from `indicators/__init__.py` so existing imports (`from indicators import sma, ema, rsi, atr, compute_all, calculate_trend_strength, find_support_resistance, avg_volume, check_breakout_quality, calculate_risk_reward, check_rsi_divergence`) keep working unchanged.

### Return shape
- **D-04:** Dataclass-of-lists for every indicator output, **uniform** across all 14 (compound and single-series). Naming convention: `<Indicator>Result` suffix (e.g. `BollingerResult`, `MACDResult`, `ADXResult`, `StochasticResult`, `KeltnerResult`, `DonchianResult`, `VWAPResult`, `FibonacciResult`, `PivotResult`, `NRResult`, `ClosingScoreResult`, `HurstResult`, `MTFAlignmentResult`, `RegimeResult`).
- **D-05:** Dataclasses co-located in their owning submodule (e.g. `BollingerResult` lives in `indicators/volatility.py` next to `bollinger_bands()`). Re-exported from `indicators/__init__.py`.
- **D-06:** Each dataclass field is `list[float | None]` (or `list[bool | None]` / `list[str | None]` where appropriate, e.g. `BollingerResult.squeeze: list[bool | None]`, `RegimeResult.state: list[str | None]`). Same length as input bar series — preserves Phase 1 convention.

### Test reference oracle
- **D-07:** Hybrid oracle strategy, tier-by-complexity:
  - **pandas-ta as dev-dep oracle** (`requirements-dev.txt`, never imported at runtime): Bollinger, ADX/DMI, MACD, Stochastic, Keltner, ATR-percentile regime, Hurst. Tolerance `1e-6`.
  - **Hand-calculated fixtures**: NR4/NR7, Closing Score, Donchian, Fibonacci levels, Pivot points, MTF alignment. Deterministic small inputs, expected values computed on paper and asserted exactly.
  - **TradingView spot-check (1 known bar each)**: Bollinger + ADX. Belt-and-suspenders sanity.
- **D-08:** Test fixture data = last 500 bars of `data/historical/EURUSD/H1.csv` loaded via Phase 1 loader, snapshotted to `tests/fixtures/eurusd_h1_last500.csv` to avoid re-load on every test. Single realistic baseline; deterministic + GMT-6→UTC consistent with Phase 1 D-08.
- **D-09:** No future leakage in tests: every indicator-vs-pandas-ta comparison runs the indicator on the full series and asserts equality at each index ≥ warmup. Rolling/expanding semantics validated explicitly.

### Session anchoring (VWAP + Pivot)
- **D-10:** Session boundary = **NY 17:00 EST rollover** (industry-standard FX daily close). Implementation uses `zoneinfo.ZoneInfo("America/New_York")` for DST-aware boundary detection (winter 22:00 UTC, summer 21:00 UTC). Pivot daily computed from prior 17:00→17:00 NY bar set's H/L/C. VWAP intraday resets at the same boundary; anchored VWAP accepts an explicit `anchor_ts: datetime` parameter.
- **D-11:** Pivot session/weekly use the same NY-17 anchor scaled (session = same as daily; weekly = Sunday 17:00 NY → Friday 17:00 NY). Returned in `PivotResult{p, r1, r2, r3, s1, s2, s3, camarilla: dict[str, list[float|None]]}`.
- **D-12:** Engine timestamps remain UTC (Phase 1 D-08); session bucketing is a query-time projection, never a storage rewrite.

### INDIC-13 Multi-TF alignment
- **D-13:** Input shape: dict keyed by TF name — `align(streams: dict[str, list[dict]])` with required keys `'H4'`, `'H1'`, `'M15'`. Each stream MUST contain only bars closed at-or-before the current M15 bar timestamp (no future leakage). Caller (strategy) responsible for slicing.
- **D-14:** Coherence formula: **sign-agreement of EMA50-slope** across the 3 TFs vs M15 sign. Score ∈ {0.0, 0.33, 0.66, 1.0}. Returned as `MTFAlignmentResult{score: list[float|None], h4_dir: list[int|None], h1_dir: list[int|None], m15_dir: list[int|None]}` where dir ∈ {-1, 0, +1}.

### INDIC-14 Volatility-regime classifier
- **D-15:** Configurable via `data/configs/regime.yaml`. Schema:
  ```yaml
  default:
    window: 200
    compressed_below: 30   # percentile
    expanded_above: 70     # percentile
  symbols:
    EURUSD: { window: 200, compressed_below: 25, expanded_above: 75 }  # optional override
  ```
- **D-16:** `volatility_regime(bars, config)` returns `RegimeResult(state: list[str|None], atr_percentile: list[float|None], window: int)`. State ∈ {`'compressed'`, `'normal'`, `'expanded'`, `None` for warmup}. Percentile computed via rolling expanding-window rank (no future leakage).

### Claude's Discretion
- Hurst exponent estimator (R/S vs DFA) — default to **R/S** with rolling window=100, but planner may pick DFA if pandas-ta-equivalent uses it.
- Fibonacci swing-leg detection algorithm — default to last completed swing high→swing low (or vice versa) using `find_support_resistance`-style pivots; planner can refine.
- ADX smoothing variant (Wilder vs SMA) — default Wilder (matches existing `_wilder_rsi` pattern).
- BollingerBands `squeeze` threshold — default BBW < 6-month-rolling-percentile-25; tunable via constructor arg.
- NR4/NR7 + Boomer (consecutive inside-narrow) sequence-length caps and confirmation rules.
- Whether `compute_all` snapshot grows to include all 14 (likely yes for live scheduler; planner decides if `compute_all_extended` is a separate fn).
- Internal helpers (`_percentile_rank`, `_session_bucket`) module placement — keep private under `_helpers.py` if reused across submodules.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project locked specs
- `.planning/PROJECT.md` — milestone scope, performance budget, key decisions
- `.planning/REQUIREMENTS.md` §Indicators — INDIC-01..INDIC-14
- `.planning/ROADMAP.md` §Phase 2 — goal, success criteria, requirement mapping

### Phase 1 carry-forward (locks that bind Phase 2)
- `.planning/phases/01-backtest-engine/01-CONTEXT.md` — D-08 timezone (Italian CSV = GMT-6 → UTC), D-09 bar-close decision time, purity convention, Protocol-based broker abstraction
- `.planning/phases/01-backtest-engine/01-VERIFICATION.md` — verified: pure-fn convention, `list[float|None]` shape, no future leakage

### Codebase maps (current state)
- `.planning/codebase/STRUCTURE.md` — flat root layout, where new packages go
- `.planning/codebase/ARCHITECTURE.md` — strategy/scanner layering
- `.planning/codebase/STACK.md` — Python 3.12 (Anaconda), pandas
- `.planning/codebase/CONVENTIONS.md` — snake_case modules, dataclass usage, leading-underscore privates
- `.planning/codebase/TESTING.md` — pytest layout under `tests/`, co-named files

### Reference modules (current code to extend, not fork)
- `indicators.py` — existing 280 lines: `sma`, `ema`, `rsi`, `_wilder_rsi`, `atr`, `_last_valid`, `compute_all`, `calculate_trend_strength`, `find_support_resistance`, `avg_volume`, `check_breakout_quality`, `calculate_risk_reward`, `check_rsi_divergence`. **Becomes** `indicators/` package per D-01..D-03.
- `patterns.py` — pure helpers, leave alone (Phase 3 territory).
- `models.py` — domain dataclasses pattern. Indicator dataclasses follow same `@dataclass` convention but co-located in submodules (D-05).
- `strategy.py:11`, `scanner.py:10`, `claude_agent.py:12`, `mcp_server.py:28` — import callsites that must keep working unchanged via `__init__.py` re-exports.

### Data
- `data/historical/{EURUSD,GBPUSD,USDJPY}/{H1,M15,M30}.csv` — semicolon Italian format, GMT-6 source (Phase 1 D-08 verified).

### Configs (to be created or extended in this phase)
- `data/configs/regime.yaml` — INDIC-14 thresholds + window per D-15.
- `tests/fixtures/eurusd_h1_last500.csv` — derived snapshot for oracle tests per D-08.

### Skills (consult during implementation)
- `.claude/skills/forex-algo-dev/` — bar-boundary discipline, no future leakage, calibration patterns
- `.claude/skills/forex-trader-pro/` — A/B/C/D setup definitions (which indicators feed which setup → relevance ordering during planning)
- `.claude/skills/forex-strategy-builder/` — Murphy/Probo/Defendi formulas (Closing Score = Defendi; squeeze = Murphy intermarket)

### External oracle (dev-dep only)
- `pandas-ta` — added to `requirements-dev.txt`. Never imported in runtime code paths. Used in `tests/test_indicators_*.py` for parity assertions per D-07.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `indicators._wilder_rsi` — Wilder smoothing pattern; reuse for ADX/DMI smoothing.
- `indicators.atr` — already correct; ATR-percentile regime (INDIC-14) consumes it directly.
- `indicators.calculate_trend_strength` — partial MTF logic; INDIC-13 generalizes it across H4/H1/M15.
- `indicators.find_support_resistance` — swing pivot detection; Fibonacci leg detection (INDIC-08) reuses pivot extraction.
- `indicators._last_valid` — keep, extend, useful for `compute_all` aggregator.
- Phase 1 `backtest/loader.py` (Italian-CSV GMT-6 → UTC) — provides the bar stream tests + indicators consume.
- Phase 1 `BrokerProtocol` — irrelevant to pure indicators but confirms strategy decoupling principle Phase 2 must preserve.

### Established Patterns
- `list[float | None]` returns, length == input length, warmup positions = `None`.
- Cumulative-incremental loops (see `sma`, `ema`) preferred over re-summing windows — O(n) vs O(n·k).
- Wilder smoothing helper pattern (`_wilder_rsi`) — replicate for ADX, ATR-percentile.
- `_last_valid(series)` snapshot extraction — keep for `compute_all`.
- Module-private helpers prefixed `_`.
- Tests live in `tests/test_indicators*.py` co-named, mock-free for pure functions.

### Hot Spots / Risks
- Existing `compute_all` returns `dict[str, float|None]` snapshot. Adding 14 indicators may bloat it. D-decision (Claude's Discretion) on whether to extend or branch.
- `calculate_trend_strength` already imported by `strategy.py` — INDIC-13 must not break its signature; new MTF helper is additive.
- pandas-ta dev-dep adds ~30 transitive packages to `requirements-dev.txt`. Acceptable — runtime stays clean.
- Session anchor (D-10) needs `zoneinfo.ZoneInfo` (stdlib in 3.12, no extra dep).

</code_context>

<specifics>
## Specific Ideas

- INDIC-11 Closing Score = Defendi formula: `(close - low) / (high - low) * 100` per bar (0–100). Position of close in bar range. Consult `forex-strategy-builder` skill for Defendi reference.
- INDIC-10 NR4/NR7: bar `i` is NR4 if `range(i) < range(j)` for j ∈ {i-1..i-3}; NR7 over 6-bar lookback. Boomer = 2+ consecutive inside-bars within NR4/7 sequence.
- INDIC-08 Fibonacci levels = 38.2%, 50%, 61.8% on the most recent completed swing leg detected via `find_support_resistance` pivots.
- INDIC-09 Pivots: classic formula (P = (H+L+C)/3; R1 = 2P - L; S1 = 2P - H; R2 = P + (H-L); S2 = P - (H-L); R3 = H + 2(P-L); S3 = L - 2(H-P)) + Camarilla (R1..R4, S1..S4 with 1.1/12, 1.1/6, 1.1/4, 1.1/2 multipliers on prior range).
- INDIC-12 Hurst: rolling window=100 default, R/S estimator. Returns ∈ [0,1]; >0.5 trending, <0.5 mean-reverting.

</specifics>

<deferred>
## Deferred Ideas

- Auto-derive INDIC-14 thresholds from training-set ATR distribution (rejected for Phase 2 — risk of look-ahead; revisit Phase 9 drift).
- Multi-broker session anchors via per-broker config (`sessions.yaml`) — out of scope; default NY-17 sufficient for single-broker TenTrade demo.
- Anchored VWAP convenience presets ("session start", "weekly start") — Phase 4 strategy refactor will expose if needed.
- ADX divergence detector (price vs ADX) — useful but not in INDIC-01..14; future phase.
- Volume-profile / TPO indicators — not in scope; possible v3 milestone.

</deferred>

---

*Phase: 02-indicators-library*
*Context gathered: 2026-05-07 via /gsd-discuss-phase*
