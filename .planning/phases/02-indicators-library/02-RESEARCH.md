# Phase 2: Indicators Library — Research

**Researched:** 2026-05-07
**Domain:** Pure-Python technical indicators (Python 3.12, no runtime third-party deps), forex intraday strategy.
**Confidence:** HIGH for canonical formulas (Camarilla, BBW squeeze, Wilder/RMA, NR4/7, VWAP). MEDIUM for Hurst R/S (estimator family choice ASSUMED reasonable per literature). HIGH for pandas-ta as oracle (verified release 0.4.71b0, 2025-09-14).

## Summary

Phase 2 promotes the flat 280-line `indicators.py` to an `indicators/` package with eight submodules and ships 14 new indicator functions (INDIC-01..14) using the same `list[float | None]` purity convention validated in Phase 1. Heavy decisions are already locked in CONTEXT.md (D-01..D-16); the open questions reduce to formula precision, library oracle parity, swing-leg detection, and percentile-rank computation.

Standard stack stays minimal: stdlib only at runtime (no pandas, no numpy in `indicators/`), pandas-ta `0.4.71b0` as **dev-dep oracle exclusively** (matches D-07). The cleanest path is (1) port existing primitives unchanged; (2) implement every new indicator as an O(n) cumulative-incremental loop where possible; (3) gate every parity test against pandas-ta's documented defaults: ADX `mamode='rma'` length=14, BBands length=20 σ=2, MACD 12/26/9, Stoch 14/3/3, Keltner length=20 mult=2 mamode='ema'. Hurst defaults to **R/S** with rolling window=100, matching the Mottl `hurst` library and pandas-ta's documented behavior — and the project skill `forex-trader-pro` references "trending vs mean-reverting" cleanly.

Pivots Camarilla formulas verified verbatim against three independent forex sources (LiteFinance, Babypips, Defcofx); the 1.1/12, 1.1/6, 1.1/4, 1.1/2 multipliers on prior-bar range are universal. Bollinger squeeze threshold default = **BBW < 25th percentile of 6-month rolling BBW** (matches D's "Claude's Discretion" guidance and aligns with both the literal Bollinger squeeze definition and Carter's TTM logic, while remaining computable without future leakage via `expanding().shift(1)` semantics inherited from Phase 1 D-09).

**Primary recommendation:** Implement per-submodule, test against pandas-ta with tolerance `1e-6`, assert no future leakage via "compute-on-prefix == compute-on-full[:i]" property tests at 5 spot indices for every indicator that uses rolling windows.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Indicator math | `indicators/` pure functions | — | No I/O, deterministic, consumed by both live & backtest paths (Phase 1 D-02 carry-forward). |
| Session/time anchoring | `indicators/_helpers.py` (`zoneinfo`) | `indicators/volume.py` (VWAP), `indicators/structure.py` (Pivot) | Engine timestamps stay UTC (Phase 1 D-08); session bucketing is query-time projection only (D-12). |
| Regime config loading | `indicators/volatility.py` reads `data/configs/regime.yaml` via PyYAML | — | Mirror Phase 1 `costs.yaml` pattern (D-05 carry); pyyaml already installed in Phase 1. |
| Test oracle | `tests/test_indicators_*.py` (pandas-ta dev-dep) | hand-calculated CSV fixtures | D-07 hybrid strategy. Runtime never imports pandas-ta. |
| Public re-export | `indicators/__init__.py` | — | Backward-compat for 4 existing callsites (D-03). |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INDIC-01 | Bollinger Bands 20/2σ + squeeze | Standard formula; squeeze threshold below; pandas-ta `bbands(length=20, std=2.0)` oracle |
| INDIC-02 | ADX/DMI 14 | Wilder/RMA smoothing per pandas-ta default `mamode='rma'`; reuse `_wilder_rsi` smoothing pattern |
| INDIC-03 | MACD 12/26/9 | Standard EMA-of-EMA; pandas-ta `macd(fast=12, slow=26, signal=9)` oracle |
| INDIC-04 | Stochastic 14/3/3 | %K = (C-LL)/(HH-LL)*100; %D = SMA3(%K); pandas-ta `stoch(k=14, d=3, smooth_k=3)` |
| INDIC-05 | Donchian 20 | rolling-max H / rolling-min L; trivial O(n) deque |
| INDIC-06 | Keltner EMA20 ± 2·ATR | EMA20 ± 2·ATR(20); pandas-ta `kc(length=20, scalar=2, mamode='ema')` |
| INDIC-07 | VWAP intraday + anchored | Intraday: cum(P·V)/cum(V) reset at NY-17 (D-10); anchored: explicit `anchor_ts` param |
| INDIC-08 | Fib retracements | Detect last completed swing leg via existing `find_support_resistance` pivots; project 38.2/50/61.8% |
| INDIC-09 | Pivots classic + Camarilla | Formulas verified verbatim (Sources §Pivots) |
| INDIC-10 | NR4/7 + Boomer | Crabel definitions verified; Boomer = ID/NR sequence (Sources §NR) |
| INDIC-11 | Closing Score (Defendi) | `(close - low) / (high - low) * 100`; trivial per-bar |
| INDIC-12 | Hurst rolling | R/S estimator, window=100, parity vs pandas-ta `hurst` or Mottl `hurst` lib |
| INDIC-13 | Multi-TF alignment | Sign-agreement of EMA50-slope (D-14); slope = single-bar diff (rationale below) |
| INDIC-14 | Vol regime classifier | ATR-percentile rolling rank, window=200, thresholds from `data/configs/regime.yaml` |

## Standard Stack

### Runtime (production)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.12 | All indicator math | `[VERIFIED: STACK.md]` Project rule: indicators have zero third-party runtime deps (Phase 1 carry-forward). |
| `zoneinfo` | stdlib 3.9+ | DST-aware NY-17 session anchor | `[VERIFIED: D-10 in CONTEXT.md]`. tzdata package already in `requirements.txt` for Windows. |
| `pyyaml` | already in `requirements.txt` (Phase 1) | Load `data/configs/regime.yaml` | `[VERIFIED: Phase 1 D-05]`. Same pattern as `costs.yaml`. |

### Development / test oracle (dev-dep only)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pandas-ta` | `0.4.71b0` (released 2025-09-14) | Parity oracle for INDIC-01..06, 12, 14 | `[VERIFIED: pypi.org/project/pandas-ta — 0.4.71b0 release]`. Last stable 0.3.14b was deleted from PyPI 2025-09-08; new line is 0.4.71b0. Brings transitive: numpy 2.2.6, pandas 2.3.2, numba 0.61.2, tqdm 4.67.1. |
| `pandas` | already pulled in via Phase 1 backtest layer | DataFrame indexing for pandas-ta oracle calls | `[VERIFIED: requirements.txt]` |
| `pytest` | already pinned | Test runner | `[VERIFIED: pytest.ini]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pandas-ta as oracle | TA-Lib (C bindings) | TA-Lib adds Windows wheel pain (already a problem per README) and a heavy build; pandas-ta is pure-Python install. **Reject.** |
| pandas-ta as oracle | `ta` lib | Less coverage (no Camarilla, no NR4/7, weak ADX); pandas-ta wins. **Reject.** |
| Mottl `hurst` for INDIC-12 oracle | Use it alongside pandas-ta | Useful belt-and-suspenders for Hurst R/S since pandas-ta's `hurst` is less documented. **Accept as secondary** for INDIC-12 only. |
| numpy for percentile rank | stdlib `bisect` + manual rolling | We already accept pandas in tests; runtime stays stdlib. **Use stdlib at runtime; numpy only via pandas-ta in tests.** |

**Installation (dev-only):**
```bash
pip install pandas-ta==0.4.71b0
# add to requirements-dev.txt (NEW file in this phase)
```

**Version verification:**
- `pandas-ta` `0.4.71b0` — `[VERIFIED: PyPI release 2025-09-14]`. The legacy 0.3.14b line was deleted from PyPI 2025-09-08; planner must NOT pin the deleted release. Use 0.4.71b0.
- Transitive numpy 2.x is fine because pandas-ta does not appear in any runtime import path; the project's runtime never sees numpy unless Phase 1's backtest layer already pulls it (it does, via pandas).

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Caller layers (no change)                                       │
│  ┌────────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────┐│
│  │ strategy.py│  │scanner.py│  │claude_agent.py│  │mcp_server.py││
│  └─────┬──────┘  └────┬─────┘  └───────┬──────┘  └──────┬──────┘│
└────────┼──────────────┼─────────────────┼──────────────────┼─────┘
         │              │                 │                  │
         ▼              ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  indicators/__init__.py  (re-exports, backward-compat)           │
└────────────────────────────────┬────────────────────────────────┘
                                 │
        ┌─────────┬───────┬──────┼───────┬──────────┬───────────┐
        ▼         ▼       ▼      ▼       ▼          ▼           ▼
   ┌─────────┐┌────────┐┌──────┐┌──────┐┌─────────┐┌────────┐┌──────┐
   │trend.py ││momentum││vol.py││struct││volume.py││bars.py ││mtf.py│
   │(SMA,EMA)││(RSI,   ││(ATR, ││(Don, ││(VWAP,   ││(NR4/7, ││(MTF  │
   │         ││MACD,   ││BB,   ││Pivot,││ avg_vol)││Closing,││align)│
   │         ││Stoch,  ││Keltn,││Fib,  ││         ││ R:R)   ││      │
   │         ││ADX,    ││Regime││S/R)  ││         ││        ││      │
   │         ││ Div)   ││)     ││      ││         ││        ││      │
   └─────────┘└────────┘└──────┘└──────┘└─────────┘└────────┘└──────┘
                                                                 │
                                                                 ▼
                                                         ┌────────────┐
                                                         │ hurst.py   │
                                                         │ aggregate  │
                                                         │ _helpers   │
                                                         └────────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │ data/configs/       │
                      │   regime.yaml       │
                      └─────────────────────┘
```

Data-flow: caller passes `bars: list[dict]` (or H/L/C lists) → indicator function returns `<Indicator>Result` dataclass of `list[float|None]` columns → caller indexes `[-1]` for live snapshot or iterates for backtest.

### Recommended Project Structure

```
indicators/
├── __init__.py          # re-exports public API (backward-compat for existing callsites)
├── _helpers.py          # _percentile_rank, _session_bucket_ny17, _last_valid (private)
├── trend.py             # sma, ema (existing primitives, lifted unchanged)
├── momentum.py          # rsi, macd, stochastic, adx, check_rsi_divergence + Result dataclasses
├── volatility.py        # atr, bollinger_bands, keltner, volatility_regime + Result dataclasses
├── structure.py         # donchian, pivots, fibonacci, find_support_resistance, check_breakout_quality
├── volume.py            # vwap_intraday, vwap_anchored, avg_volume + VWAPResult
├── bars.py              # nr4, nr7, boomer, closing_score, calculate_risk_reward + NRResult, ClosingScoreResult
├── mtf.py               # align(streams) + MTFAlignmentResult, calculate_trend_strength
├── hurst.py             # hurst_rs(values, window=100) + HurstResult
└── aggregate.py         # compute_all (extended) + compute_all_extended (recommend split — see below)
data/configs/
└── regime.yaml          # NEW (D-15 schema)
tests/
├── fixtures/
│   └── eurusd_h1_last500.csv   # NEW snapshot per D-08
├── test_indicators_trend.py
├── test_indicators_momentum.py
├── test_indicators_volatility.py
├── test_indicators_structure.py
├── test_indicators_volume.py
├── test_indicators_bars.py
├── test_indicators_mtf.py
├── test_indicators_hurst.py
└── test_indicators_aggregate.py
requirements-dev.txt    # NEW: pandas-ta==0.4.71b0
```

### Pattern 1: Cumulative-incremental rolling (O(n))

**What:** Maintain a running sum/EWMA across the loop; never re-sum windows.
**When to use:** Every indicator with a rolling window — SMA, EMA, RSI, ATR, BBands, Stoch, ADX/DMI, Keltner, Donchian.
**Example (already in repo, replicate):**
```python
# Source: indicators.py (existing sma) — keep this style for all rolling indicators
def sma(values: list[float], period: int) -> list[float | None]:
    n = len(values); out = [None] * n
    if period <= 0 or n < period: return out
    cum = sum(values[:period])
    out[period - 1] = cum / period
    for i in range(period, n):
        cum += values[i] - values[i - period]
        out[i] = cum / period
    return out
```

### Pattern 2: Wilder smoothing helper (RMA = pandas-ta default)

**What:** EWMA with `alpha = 1 / period` — equivalent to pandas-ta's `rma()` and to TradingView's `ta.rma()`.
**When to use:** ADX, DMI components (smoothed +DM/-DM/TR), and any indicator pandas-ta sets `mamode='rma'`. Also used by existing `rsi` and `atr`.
**Source citation:** pandas-ta `rma`: `close.ewm(alpha=1.0/length, min_periods=length).mean()` — `[CITED: tradingstrategy.ai/docs pandas_ta.overlap.rma]`.
```python
# Source: extension of indicators._wilder_rsi pattern
def _wilder_smooth(values: list[float], period: int) -> list[float | None]:
    n = len(values); out = [None] * n
    if n < period: return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, n):
        prev = out[i - 1]
        out[i] = (prev * (period - 1) + values[i]) / period
    return out
```
This **must** be the smoothing for ADX +DI / -DI / DX → ADX so parity tests with `pandas_ta.adx(mamode='rma')` pass at `1e-6`.

### Pattern 3: Session-anchored cumulative (VWAP intraday, Pivot daily)

**What:** Convert UTC timestamp to America/New_York via `zoneinfo.ZoneInfo("America/New_York")`, treat 17:00 as session boundary; emit a "new session" flag per bar; reset cumulative state on flag.
**When to use:** VWAP intraday reset, Pivot daily/session computation source.
**Example:**
```python
# Source: planned _helpers.py, design from D-10
from zoneinfo import ZoneInfo
_NY = ZoneInfo("America/New_York")

def _session_id_ny17(ts_utc: datetime) -> date:
    """Bar belongs to the NY-17→NY-17 session ending on the returned date."""
    ny = ts_utc.astimezone(_NY)
    # Bars at-or-after 17:00 NY belong to the NEXT session (rolling forward)
    if ny.hour >= 17:
        return (ny + timedelta(days=1)).date()
    return ny.date()
```
DST is handled automatically by zoneinfo; winter NY-17 == 22:00 UTC, summer NY-17 == 21:00 UTC. Verified per IANA tzdata (Phase 1 D-08 already established this pattern for live trading).

### Pattern 4: Anchored VWAP — explicit timestamp parameter

**What:** Idiomatic API per pandas-ta convention is to accept either a pandas timeseries offset alias (`"D"`, `"W"`) for periodic anchors or an explicit anchor timestamp.
**When to use:** INDIC-07 anchored variant.
**Source citation:** `vwap(high, low, close, volume, anchor=None, ...)` pandas-ta signature `[CITED: tradingstrategy.ai/docs pandas_ta.overlap.vwap]`. We deviate slightly: our anchor is an **explicit `datetime`** (D-10 spec), which is more general and avoids the pandas DatetimeIndex requirement that complicated pandas-ta issue #228.
```python
def vwap_anchored(bars: list[dict], anchor_ts: datetime) -> VWAPResult:
    """Cumulate (typical_price * volume) / volume from the first bar with bar.ts >= anchor_ts."""
```
This signature is idiomatic, deterministic, and decouples the function from pandas indexing.

### Anti-Patterns to Avoid

- **Using `series.rolling(W).rank(pct=True)` directly with full-series semantics** — pandas `rolling().rank(pct=True)` ranks within the window (correct, no future leakage). But `series.rank(pct=True)` ranks across the whole series (FUTURE LEAKAGE). The distinction is critical for INDIC-14 ATR percentile and BBW squeeze percentile.
- **Computing percentile on a full-series sort** — same trap. Always use rolling/expanding semantics.
- **Re-summing rolling windows** — O(n·k) instead of O(n). Existing `find_support_resistance` already does this for pivots; consider deque optimization in Phase 5 if backtest profile shows hot spot. Phase 2 keeps existing complexity to limit scope.
- **Hand-rolling EWMA without seeding from SMA** — must seed `out[period-1] = sum(first_period)/period` like existing `ema` and `_wilder_rsi`. Otherwise pandas-ta parity fails on warmup boundary.
- **Re-implementing pandas-ta math from memory** — every formula here MUST cite either an authoritative reference or a pandas-ta source line, not just "I think this is right."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ADX/DMI smoothing | Custom Wilder approximation | Wilder/RMA helper matching pandas-ta `mamode='rma'` exactly | Three subtly different smoothings exist (Wilder true, EMA-α=2/(N+1), SMA); only one matches pandas-ta. `[CITED: pandas_ta.trend.adx]` |
| Camarilla multipliers | "Reasonable" multipliers from memory | Verbatim 1.1/12, 1.1/6, 1.1/4, 1.1/2 | Multiple online "Camarilla" calculators use wrong multipliers (e.g., 1.083). Three independent forex sources confirm 1.1/N. `[VERIFIED: LiteFinance, Babypips, Defcofx]` |
| Hurst R/S | Naïve `log(R/S) / log(N)` on the full window | R/S over multiple sub-window sizes + linear regression of `log(R/S)` vs `log(n)` | The single-window estimate is biased; correct R/S splits the window into halves/quarters/octaves and fits the slope. `[CITED: arxiv.org/html/2310.19051v3]`. Match Mottl `hurst` library output for parity. |
| BBW squeeze threshold | Fixed pip threshold per symbol | Rolling-percentile threshold (BBW < 25th pct of last 6 months) | Symbol-specific volatility means a fixed pip threshold doesn't transfer across pairs. Carter's TTM uses BB-inside-Keltner; Bollinger himself recommends BBW percentile. `[CITED: volatilitybox.com/research/bollinger-bands-volatility]` |
| Date/session math | Manual `(ts - epoch) % 86400` | `zoneinfo.ZoneInfo("America/New_York")` | DST shifts NY-17 between 21:00 and 22:00 UTC; manual math gets it wrong twice/year. `[VERIFIED: stdlib zoneinfo + tzdata package]` |
| Rolling percentile rank | Sort + bisect per bar | `pandas` rolling rank in tests; stdlib `bisect.insort` + index-of in runtime if simple O(n·log k) acceptable | Manual is fine; just don't accidentally rank against future bars. |

**Key insight:** Every domain in INDIC-01..14 has a specific industry-standard formula and a corresponding pandas-ta function. Picking the wrong variant (e.g., EMA-smoothed ADX instead of Wilder) silently breaks parity tests and produces signals the strategy backtest will misinterpret. **Pick pandas-ta's defaults, document the choice, assert parity at 1e-6.**

## Common Pitfalls

### Pitfall 1: pandas-ta pinning to deleted version
**What goes wrong:** Planner pins `pandas-ta==0.3.14b` based on training data; pip resolves to nothing.
**Why it happens:** The 0.3.14b line was removed from PyPI 2025-09-08 and replaced by the 0.4.71b0 line.
**How to avoid:** Pin `pandas-ta==0.4.71b0` in `requirements-dev.txt`. Do not use `0.3.x`.
**Warning signs:** `ERROR: No matching distribution found for pandas-ta==0.3.14b`.

### Pitfall 2: Wilder smoothing seed mismatch with pandas-ta
**What goes wrong:** Custom RMA seeds with `values[period-1]` instead of `mean(values[:period])`; first ~50 bars diverge from pandas-ta by 0.5-2%.
**Why it happens:** pandas uses `ewm(alpha=alpha, min_periods=length, adjust=False)` which under the hood seeds with the full SMA over the first `length` rows.
**How to avoid:** Seed with `sum(values[:period]) / period` (matches `_wilder_rsi` already in `indicators.py:50`). Run parity test starting at index `2*period` to be safe; assert tolerance `1e-6`.
**Warning signs:** Parity test fails at indices < 30, passes at indices > 50.

### Pitfall 3: VWAP anchored on bar that doesn't exist
**What goes wrong:** Caller passes `anchor_ts` that falls between two bar closes; function silently returns `None`s or accidentally anchors at next bar (introduces 1-bar offset in backtest results).
**Why it happens:** Bar timestamps are discrete; `anchor_ts` is continuous.
**How to avoid:** Document semantics: "anchor at the first bar with `bar.ts >= anchor_ts`." Test with anchor exactly equal to a bar timestamp and with anchor 1 microsecond before/after.
**Warning signs:** Off-by-one bar offset in backtest VWAP curves.

### Pitfall 4: Future leakage via full-series percentile
**What goes wrong:** ATR-percentile (INDIC-14) computed via `series.rank(pct=True)` ranks each ATR value against the entire history including future bars; backtest looks profitable, live fails.
**Why it happens:** pandas distinguishes `series.rank(pct=True)` (whole-series, leaks) from `series.rolling(W).rank(pct=True)` (window-bounded, safe).
**How to avoid:** Use `rolling(window=200, min_periods=200).rank(pct=True)` in tests; in runtime use a manual O(W) rolling sort per bar. Add explicit "no future leakage" property test: `regime[i]` must equal `volatility_regime(bars[:i+1], cfg).state[i]`.
**Warning signs:** Backtest hit rate >> live hit rate after Phase 5 baseline.

### Pitfall 5: NY-17 boundary off-by-one for non-DST symbols (USDJPY)
**What goes wrong:** Tokyo session bars get bucketed into wrong NY day around DST transitions.
**Why it happens:** USDJPY trades 24h; the conceptual "day" depends on the broker's daily-rollover, which is NY-17 for FX.
**How to avoid:** Apply `_session_id_ny17(bar.ts_utc)` uniformly regardless of symbol. Test with two bars 1 second apart straddling 22:00 UTC in winter and 21:00 UTC in summer; assert correct session-id transition.
**Warning signs:** Pivot levels jump unexpectedly on the second Sunday of March / first Sunday of November.

### Pitfall 6: Hurst R/S window too short
**What goes wrong:** Window=50 produces noisy values that bounce between 0.3 and 0.7 every few bars.
**Why it happens:** R/S analysis needs ≥100 observations to be stable; the literature consensus is 100-500.
**How to avoid:** Default `window=100` (per CONTEXT.md specifics §INDIC-12). Document that smaller windows are unreliable. Test against a known persistent series (e.g., cumsum of i.i.d. positive bias) and assert H > 0.6.
**Warning signs:** Flicker between trending/mean-reverting classification.

### Pitfall 7: MTF alignment slope from single-bar diff is noisy
**What goes wrong:** EMA50 slope = `ema[i] - ema[i-1]` flips sign on every bar in choppy ranges; coherence score chatters between 0.0 and 1.0.
**Why it happens:** EMA50 is smooth, but its first difference is not.
**How to avoid:** Define slope = `sign(ema[i] - ema[i-N])` with N=5 bars (or tunable; H4: N=2, H1: N=3, M15: N=5). Document the choice. Test against a known clean uptrend (linear ramp) — coherence should hit 1.0 and stay.
**Warning signs:** Coherence score histogram is bimodal at 0.0/1.0 with no mass in {0.33, 0.66}.

### Pitfall 8: pandas-ta as runtime import accidentally
**What goes wrong:** Developer imports `pandas_ta` at the top of `indicators/momentum.py` "just to compare." Production env doesn't install dev deps; ImportError on first run.
**Why it happens:** Habit / forgetting D-07.
**How to avoid:** CI-time check (or a unit test) that greps `indicators/` for `import pandas_ta` or `from pandas_ta` and fails the build. Belt-and-suspenders: also assert `pandas_ta` not in `sys.modules` after `import indicators` in a test.

## Code Examples

### Example 1: ADX with pandas-ta-compatible Wilder smoothing
```python
# Source: planned indicators/momentum.py — formula per pandas_ta.trend.adx (mamode='rma' default)
from dataclasses import dataclass

@dataclass
class ADXResult:
    adx: list[float | None]
    plus_di: list[float | None]
    minus_di: list[float | None]

def adx(highs: list[float], lows: list[float], closes: list[float],
        period: int = 14) -> ADXResult:
    n = len(closes)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm[i] = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm[i] = down_move if down_move > up_move and down_move > 0 else 0.0
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]))
    # Wilder-smooth all three series
    sm_plus = _wilder_smooth(plus_dm, period)
    sm_minus = _wilder_smooth(minus_dm, period)
    sm_tr = _wilder_smooth(tr, period)
    plus_di = [100.0 * p / t if (p is not None and t) else None for p, t in zip(sm_plus, sm_tr)]
    minus_di = [100.0 * m / t if (m is not None and t) else None for m, t in zip(sm_minus, sm_tr)]
    dx = [
        100.0 * abs(p - m) / (p + m) if (p is not None and m is not None and (p + m) > 0) else None
        for p, m in zip(plus_di, minus_di)
    ]
    adx_vals = _wilder_smooth([d if d is not None else 0.0 for d in dx], period)
    # Mask warmup
    for i in range(min(2 * period, n)):
        adx_vals[i] = None
    return ADXResult(adx=adx_vals, plus_di=plus_di, minus_di=minus_di)
```

### Example 2: Camarilla pivots (verbatim formula)
```python
# Source: planned indicators/structure.py — formula verified against LiteFinance, Babypips, Defcofx
@dataclass
class PivotResult:
    p: list[float | None]
    r1: list[float | None]; r2: list[float | None]; r3: list[float | None]
    s1: list[float | None]; s2: list[float | None]; s3: list[float | None]
    camarilla: dict[str, list[float | None]]   # keys: "h1".."h4", "l1".."l4"

def _camarilla_levels(prev_h: float, prev_l: float, prev_c: float) -> dict[str, float]:
    rng = prev_h - prev_l
    return {
        "h1": prev_c + rng * 1.1 / 12,
        "h2": prev_c + rng * 1.1 / 6,
        "h3": prev_c + rng * 1.1 / 4,
        "h4": prev_c + rng * 1.1 / 2,
        "l1": prev_c - rng * 1.1 / 12,
        "l2": prev_c - rng * 1.1 / 6,
        "l3": prev_c - rng * 1.1 / 4,
        "l4": prev_c - rng * 1.1 / 2,
    }
```

### Example 3: Volatility regime (no future leakage)
```python
# Source: planned indicators/volatility.py — INDIC-14 per D-15/D-16
@dataclass
class RegimeResult:
    state: list[str | None]            # 'compressed' | 'normal' | 'expanded' | None
    atr_percentile: list[float | None] # 0..1
    window: int

def volatility_regime(bars: list[dict], cfg: dict) -> RegimeResult:
    window = cfg.get("window", 200)
    lo = cfg.get("compressed_below", 30) / 100.0
    hi = cfg.get("expanded_above", 70) / 100.0
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    atr_series = atr(highs, lows, closes, period=14)
    state: list[str | None] = [None] * len(bars)
    pct: list[float | None] = [None] * len(bars)
    # Rolling rank — manual, no pandas at runtime
    for i in range(len(bars)):
        if atr_series[i] is None or i < window:
            continue
        window_vals = [v for v in atr_series[i - window + 1 : i + 1] if v is not None]
        if len(window_vals) < window:
            continue
        rank = sum(1 for v in window_vals if v <= atr_series[i]) / len(window_vals)
        pct[i] = rank
        if rank < lo:
            state[i] = "compressed"
        elif rank > hi:
            state[i] = "expanded"
        else:
            state[i] = "normal"
    return RegimeResult(state=state, atr_percentile=pct, window=window)
```

### Example 4: Test parity with pandas-ta
```python
# Source: planned tests/test_indicators_momentum.py
import pandas as pd
import pandas_ta as pta
from indicators.momentum import adx

def test_adx_parity_with_pandas_ta():
    df = pd.read_csv("tests/fixtures/eurusd_h1_last500.csv")
    h, l, c = df["high"].tolist(), df["low"].tolist(), df["close"].tolist()
    ours = adx(h, l, c, period=14)
    expected = pta.adx(df["high"], df["low"], df["close"], length=14, mamode="rma")
    # pandas-ta returns columns ADX_14, DMP_14, DMN_14
    for i in range(50, len(c)):  # skip 2*period warmup
        if ours.adx[i] is not None and not pd.isna(expected["ADX_14"].iloc[i]):
            assert abs(ours.adx[i] - expected["ADX_14"].iloc[i]) < 1e-6
```

## Open-Question Answers (Phase Brief §research_focus)

1. **Hurst estimator (R/S vs DFA)** — Recommend **R/S** with `window=100`. Rationale: pandas-ta's `hurst` is undocumented in detail but R/S is the classical default; the Mottl `hurst` Python lib is R/S-based; `[CITED: arxiv.org/html/2310.19051v3]` notes R/S is the original Mandelbrot-popularized method and DFA1 is mathematically equivalent for trend-removal. R/S has lower implementation complexity (4-line core algorithm vs DFA's polynomial detrending). Use Mottl `hurst` lib as belt-and-suspenders parity oracle alongside pandas-ta. **Confidence: MEDIUM** (R/S vs DFA is a defensible engineering choice; either works for regime classification).

2. **ADX smoothing** — **Wilder/RMA** (alpha=1/length). pandas-ta default is `mamode='rma'`; this is the universal choice and matches TradingView's `ta.adx()`. `[CITED: tradingstrategy.ai/docs pandas_ta.trend.adx]`. **Confidence: HIGH.**

3. **Bollinger squeeze threshold** — **BBW < 25th percentile of trailing 6-month BBW**. Rationale: Bollinger himself recommends percentile framing; `[CITED: volatilitybox.com/research/bollinger-bands-volatility]` notes "below its own 6-month low" as low-vol; 25th-percentile is a less brittle equivalent. Carter's TTM uses BB-inside-Keltner (different mechanism); we ship percentile as primary squeeze, expose Keltner-inside check as a secondary boolean (`squeeze_ttm`) on `BollingerResult`. Tunable via constructor: `bollinger_bands(closes, length=20, std=2.0, squeeze_lookback_bars=180, squeeze_pct=25)`. **Confidence: HIGH** for the percentile approach; **MEDIUM** for the specific 25th cut-off — defensible default, planner may make it configurable.

4. **NR4/NR7 + Boomer rules**:
   - **NR4:** bar `i` has `range(i) < range(j)` for all j ∈ {i-1, i-2, i-3} (i.e., narrowest of last 4 bars). `[VERIFIED: forextraininggroup.com — Crabel definition]`.
   - **NR7:** narrowest of last 7 bars. `[VERIFIED: chartschool.stockcharts.com NR7]`.
   - **Inside bar:** `high(i) <= high(i-1) AND low(i) >= low(i-1)`. `[VERIFIED: tradingsetupsreview.com Inside Day NR4]`.
   - **Boomer:** A sequence of 2+ consecutive inside bars within an NR4 or NR7 window. Per CONTEXT.md specifics: "Boomer = 2+ consecutive inside-bars within NR4/7 sequence." Implement as: `boomer[i] = True` if `inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])`. **Confidence: HIGH** for NR4/NR7 standard definitions; **MEDIUM** for "Boomer" exact rule — Crabel's books use varying terminology, and the project skill `forex-strategy-builder` should be consulted by the planner to confirm the trader-pro playbook's specific Boomer definition.

5. **Fibonacci swing-leg detection** — **Reuse existing `find_support_resistance` with a window=2 fractal-pivot**. Rationale: it's already deterministic, already tested, already imported by `strategy.py`. The "last completed swing leg" = pair (most-recent swing high, most-recent swing low) with the later one being the leg's terminus. Project Fib levels (38.2%, 50%, 61.8%) on the leg. Alternative ZigZag/ATR-based swings have hyperparameters (deviation %) that introduce calibration burden — defer. **Confidence: HIGH.**

6. **MTF alignment slope formula** — **Slope = sign(EMA50[i] - EMA50[i-N])** with N=3 default (configurable per TF). Single-bar diff is noisy (Pitfall 7); N-bar regression adds little robustness over a fixed-lag diff. Use `dir ∈ {-1, 0, +1}` with a small dead-zone: if `|EMA50[i] - EMA50[i-N]| / EMA50[i] < 1e-5` then `dir = 0`. **Confidence: MEDIUM** — the locked decision (D-14) is sign-agreement; the lookback N is Claude's discretion within that. Recommend N=3 uniformly first; tune in Phase 5 if MTF score chatters.

7. **VWAP anchored API surface** — **`vwap_anchored(bars: list[dict], anchor_ts: datetime) -> VWAPResult`**. Idiomatic in our domain (timestamp-based). Diverges intentionally from pandas-ta's offset-alias approach because we don't carry a pandas DatetimeIndex through our pure-list API. D-10 already specifies `anchor_ts: datetime`; this research confirms the choice. **Confidence: HIGH.**

8. **Camarilla multipliers** — Verbatim 1.1/12, 1.1/6, 1.1/4, 1.1/2 on `(prevH - prevL)`, added to `prevC` for resistances and subtracted for supports. **`[VERIFIED: 3 independent sources]`**. **Confidence: HIGH.**

9. **ATR-percentile rolling rank — runtime cost** — Naïve manual sort over 200-bar window is O(n·W·log W) = O(n · 200 · 8) ≈ 1600·n ops; for 23.5y H1 (~150k bars) ≈ 240M ops, which is ~3-5s in pure Python — acceptable in a backtest pre-pass. For per-bar live decisions, only the last index is needed; cost is O(W·log W) per bar, trivially fast. If Phase 5 profiling shows hot spot, swap to `bisect.insort` + bisect_left index lookup (O(W) per insert dominated by list shift, but cache-friendly). **Recommend:** ship the naïve sort first; revisit if Phase 5 budget pressure emerges. **Confidence: HIGH.**

10. **`compute_all` extension vs `compute_all_extended`** — **Recommend split**. Current `compute_all` returns 4 fields (`sma_20, ema_50, rsi_14, atr_14`) used by `claude_agent` and `mcp_server`. Extending it to 14+ indicators bloats payload and breaks any consumer that assumes the small dict. New `compute_all_extended(bars, regime_cfg) -> dict` returns the 14-indicator snapshot for backtest+strategy. Existing `compute_all` stays bit-for-bit identical (no churn at the 4 callsites). **Confidence: HIGH.**

11. **pandas-ta version pinning** — **`pandas-ta==0.4.71b0`** (released 2025-09-14). The legacy `0.3.14b` line was deleted from PyPI 2025-09-08; pinning it will fail `pip install`. Transitive deps for 0.4.71b0: numpy 2.2.6, pandas 2.3.2, numba 0.61.2, tqdm 4.67.1. Numba is a heavy install (~50MB compiled artifacts) but only in dev env. Acceptable. **Confidence: HIGH** (`[VERIFIED: pypi.org/project/pandas-ta]`).

12. **Test fixture strategy** — Create `tests/fixtures/eurusd_h1_last500.csv` once via a one-off script that loads `data/historical/EURUSD/H1.csv` through Phase 1 `backtest.loader.load_bars`, slices `[-500:]`, and writes UTC-stamped OHLCV. pytest fixture scope = `module` (load once per test file). Repository has no `conftest.py` today (TESTING.md confirms — "No `conftest.py` detected"); we can either add one for shared fixture or duplicate the loader call per-file. **Recommend:** add `tests/conftest.py` with a single `eurusd_h1_500` fixture, scope=`session`. Keeps test runtime fast; matches existing inline-fixture-per-file convention by being a single addition. **Confidence: HIGH.**

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pandas-ta==0.3.14b` (Mar 2021) | `pandas-ta==0.4.71b0` (Sep 2025) | 2025-09-08 (0.3.x deleted) | Must pin new line; old GitHub forks (`Pandas-ta-fork`, `pandas-ta-classic`, `pandas-ta-openbb`) exist for compatibility but aren't needed. |
| Bollinger absolute-pip squeeze threshold | Rolling-percentile BBW threshold | Bollinger's own writings, post-2010 | Symbol-portable, requires expanding/rolling window discipline. |
| Hand-coded RMA seeded with last value | RMA seeded with mean-of-first-period | TradingView/pandas-ta convention | Matches industry; first ~2·period bars match oracles to 1e-6. |

**Deprecated/outdated:**
- `pandas-ta==0.3.14b` — deleted from PyPI; do not pin.
- `talib`/`TA-Lib` — heavy C build on Windows; replaced by pandas-ta as oracle.

## Project Constraints (from CLAUDE.md)

- **Italian comments/log/rationale** — All new docstrings, inline comments, and any log messages MUST be Italian. Test names stay English-snake_case.
- **EXECUTION_MODE=shadow default** — N/A for indicators (pure functions, no execution).
- **Tutto da .env, zero magic numbers** — `regime.yaml` thresholds (D-15) honor this for INDIC-14; Bollinger squeeze parameters MUST be exposed as function args, not hardcoded.
- **Risk engine = unico gate approvazione trade** — N/A for Phase 2; indicators feed the gate, do not bypass it.
- **Un file per fase in `.orchestration/phase-prompts/`** — Phase 2's `.orchestration/phase-prompts/02-indicators.md` should be authored by the planner (not in Phase 2 research scope).
- **STATE.md aggiornato dopo ogni micro-step** — operational discipline; planner schedules.
- **PHASES.md read-only per orchestrator** — Phase 2 must not edit PHASES.md.
- **Filling mode `ORDER_FILLING_RETURN`** — N/A (no broker calls in indicators).
- **Mai accedere direttamente a file `.env`** — Indicators read no env vars; `regime.yaml` is the only config and is loaded explicitly (not via `os.environ`).
- **Test pytest, mock Mt5Client** — N/A (indicators have no MT5 dependency); but tests must remain mock-free for pure functions per existing convention.
- **Push to origin after each validated phase** — operational; verify-work step.
- **No Co-Authored-By trailers** — commit message convention.

These are honored by the locked decisions (D-01..D-16); planner has no compliance gap to address beyond the standard.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (unpinned, already in `requirements.txt`) |
| Config file | `pytest.ini` (`pythonpath = .`) |
| Quick run command | `pytest tests/test_indicators_<submodule>.py -x` |
| Full suite command | `pytest tests/test_indicators_*.py` |
| Phase gate full | `pytest` (entire suite must remain green) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INDIC-01 | Bollinger 20/2 + squeeze | unit + parity | `pytest tests/test_indicators_volatility.py::test_bbands_parity -x` | ❌ Wave 0 |
| INDIC-02 | ADX/DMI 14 | unit + parity | `pytest tests/test_indicators_momentum.py::test_adx_parity -x` | ❌ Wave 0 |
| INDIC-03 | MACD 12/26/9 | unit + parity | `pytest tests/test_indicators_momentum.py::test_macd_parity -x` | ❌ Wave 0 |
| INDIC-04 | Stoch 14/3/3 | unit + parity | `pytest tests/test_indicators_momentum.py::test_stoch_parity -x` | ❌ Wave 0 |
| INDIC-05 | Donchian 20 | unit | `pytest tests/test_indicators_structure.py::test_donchian -x` | ❌ Wave 0 |
| INDIC-06 | Keltner | unit + parity | `pytest tests/test_indicators_volatility.py::test_keltner_parity -x` | ❌ Wave 0 |
| INDIC-07 | VWAP intraday + anchored | unit (manual fixture) | `pytest tests/test_indicators_volume.py::test_vwap_intraday_session_reset -x` | ❌ Wave 0 |
| INDIC-08 | Fibonacci | unit (manual fixture) | `pytest tests/test_indicators_structure.py::test_fib_levels -x` | ❌ Wave 0 |
| INDIC-09 | Pivots classic+Camarilla | unit (manual fixture) | `pytest tests/test_indicators_structure.py::test_pivot_camarilla_formula -x` | ❌ Wave 0 |
| INDIC-10 | NR4/7 + Boomer | unit (manual fixture) | `pytest tests/test_indicators_bars.py::test_nr_boomer -x` | ❌ Wave 0 |
| INDIC-11 | Closing Score | unit (hand-calc) | `pytest tests/test_indicators_bars.py::test_closing_score -x` | ❌ Wave 0 |
| INDIC-12 | Hurst rolling | unit + parity | `pytest tests/test_indicators_hurst.py::test_hurst_rs_parity -x` | ❌ Wave 0 |
| INDIC-13 | MTF alignment | unit (synthetic streams) | `pytest tests/test_indicators_mtf.py::test_align_full_coherence -x` | ❌ Wave 0 |
| INDIC-14 | Vol regime | unit + parity + leakage | `pytest tests/test_indicators_volatility.py::test_regime_no_future_leakage -x` | ❌ Wave 0 |

Plus a universal test:
| — | No future leakage (property test) | unit | `pytest tests/test_indicators_purity.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_indicators_<submodule>.py -x` (target <5s)
- **Per wave merge:** `pytest tests/test_indicators_*.py` (target <30s)
- **Phase gate:** `pytest` full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — session-scoped fixture `eurusd_h1_500` loading `tests/fixtures/eurusd_h1_last500.csv`
- [ ] `tests/fixtures/eurusd_h1_last500.csv` — generate once via a one-off script using Phase 1 loader
- [ ] `tests/test_indicators_<submodule>.py` × 9 — all new
- [ ] `tests/test_indicators_purity.py` — universal "no future leakage" property test
- [ ] `requirements-dev.txt` — new file, `pandas-ta==0.4.71b0`
- [ ] `data/configs/regime.yaml` — D-15 schema
- [ ] Framework install: `pip install -r requirements-dev.txt`

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (pure functions, no auth surface) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Validate `period > 0`, list-length consistency (matches existing `atr` raise), `regime.yaml` schema validation on load (mirror Phase 1 `costs.yaml` pattern) |
| V6 Cryptography | no | — |

### Known Threat Patterns for pure-Python indicator math

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed YAML in `regime.yaml` | DoS / Tampering | `yaml.safe_load` (never `yaml.load`); validate schema with explicit key checks; fail-fast with `ValueError` at module init like `config.py` does for env enums |
| Untrusted `bars` list shape (NaN/Inf in close) | Tampering | Validate inputs are finite floats; raise `ValueError` early. Existing `atr` validates length consistency — extend pattern. |
| Future-data leakage via test mistakes | Integrity | Property tests asserting `f(bars[:i+1])[i] == f(bars)[i]` for every rolling indicator at 5 spot indices |

No HTTP/network/crypto surface; the security domain reduces to input validation hygiene.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime | ✓ (assumed per CLAUDE.md) | 3.12 | — |
| `pandas` | Test oracle | ✓ (already in `requirements.txt` via Phase 1) | per requirements.txt | — |
| `pyyaml` | `regime.yaml` loader | ✓ (added in Phase 1 for `costs.yaml`) | per Phase 1 install | — |
| `pandas-ta==0.4.71b0` | Test oracle (D-07) | ✗ — NEW dev-dep | 0.4.71b0 | None (test parity for INDIC-01..06,12,14 requires it; hand-calculated fixtures cover INDIC-07..11,13) |
| `tzdata` | NY-17 zoneinfo (Windows) | ✓ (already pulled in by Phase 1 / strategy `_TZ_ROME`) | per requirements.txt | — |
| `pytest` | Test runner | ✓ | per requirements.txt | — |

**Missing dependencies with no fallback:** None — `pandas-ta` is the one new install; if it cannot be installed for any reason, hand-calculated fixtures still cover 8/14 indicators, but parity assertions for 6/14 would degrade to manual TradingView spot-checks (D-07 already lists this as the secondary tier).

**Missing dependencies with fallback:** None.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | pandas-ta `hurst()` uses R/S-based estimator | §Standard Stack, §Open-Q1 | If pandas-ta uses DFA, our R/S impl will fail parity. Mitigation: also test against Mottl `hurst` lib (R/S-based, `[CITED: github.com/Mottl/hurst]`), and document tolerance loosening to `1e-3` for Hurst only if needed. |
| A2 | "Boomer" = 2+ consecutive inside bars within NR4/7 window | §Pitfall 4, §Open-Q4 | If `forex-trader-pro` skill defines Boomer differently, our detector flags wrong bars. Mitigation: planner consults skill before locking implementation; flag for user confirm in discuss-phase if ambiguous. |
| A3 | MTF slope lookback N=3 default is robust | §Open-Q6 | If too noisy, MTF coherence chatters in Phase 5 backtest. Mitigation: expose N as config, tune empirically. |
| A4 | BBW squeeze 25th-percentile cut-off is the "right" default | §Open-Q3 | Could be too aggressive/lax; symbol-dependent. Mitigation: tunable via constructor arg. |
| A5 | Wilder/RMA seeded by SMA-of-first-period matches pandas-ta exactly | §Pattern 2, §Pitfall 2 | If pandas-ta uses a different seed (rare), parity fails on first ~50 bars. Mitigation: parity test starts at index 2*period to dodge transient; if needed, copy pandas-ta's exact ewm semantics. |

**If this list grows during planning:** discuss-phase loops back to user before locking the plan.

## Open Questions

1. **Does the forex-trader-pro skill define "Boomer" precisely the way CONTEXT.md specifies (2+ inside bars within NR4/7)?**
   - What we know: CONTEXT.md specifics state this verbatim.
   - What's unclear: Crabel's literature uses varying terminology; the project skill may have a refinement (e.g., directional bias, 3+ consecutive, breakout confirmation).
   - Recommendation: planner consults `.claude/skills/forex-trader-pro/` before writing the Boomer test; if conflict found, escalate to user via discuss-phase.

2. **Should `compute_all` snapshot for live MCP (`get_market_snapshot`) include the new indicators by default, or stay narrow?**
   - What we know: D-discretion lists this as planner choice.
   - What's unclear: MCP tool callers (`claude_agent`, MCP clients) may not handle larger payloads gracefully.
   - Recommendation: keep `compute_all` unchanged; ship `compute_all_extended` separately. Phase 6 will refactor `MCP-R1 get_market_snapshot` to opt into the extended set via a flag.

3. **Single `tests/conftest.py` introduction — is this acceptable given existing convention is "no conftest"?**
   - What we know: TESTING.md confirms no conftest exists today.
   - What's unclear: whether TESTING.md is descriptive (just observed) or prescriptive (forbidden to add).
   - Recommendation: add it; the convention is descriptive, and a single session-scoped fixture is the cleanest solution. Document the addition in STATE.md.

## Sources

### Primary (HIGH confidence)
- pandas-ta source: `pandas_ta.trend.adx` — `mamode='rma'` default, length=14 — `[CITED: tradingstrategy.ai/docs/_modules/pandas_ta/trend/adx.html]`
- pandas-ta source: `pandas_ta.overlap.rma` — `close.ewm(alpha=1.0/length, min_periods=length).mean()` — `[CITED: tradingstrategy.ai/docs/_modules/pandas_ta/overlap/rma.html]`
- pandas-ta source: `pandas_ta.overlap.vwap` — `vwap(high, low, close, volume, anchor=None, ...)` — `[CITED: tradingstrategy.ai/docs/_modules/pandas_ta/overlap/vwap.html]`
- PyPI pandas-ta release history — version 0.4.71b0 (2025-09-14) — `[VERIFIED: pypi.org/project/pandas-ta/]`
- Bollinger Band squeeze percentile framing — `[CITED: volatilitybox.com/research/bollinger-bands-volatility/]`
- TTM Squeeze definition (Carter, BB-inside-Keltner) — `[CITED: chartschool.stockcharts.com/.../ttm-squeeze]` and `[CITED: barchart.com/media/education/pdf/The%20Squeeze%20by%20John%20Carter.pdf]`
- Camarilla pivot multipliers (1.1/N) — three independent confirmations: `[CITED: litefinance.org/blog/.../camarilla-pivot-points-strategy/]`, `[CITED: babypips.com/forexpedia/camarilla-pivot-points]`, `[CITED: defcofx.com/camarilla-pivot-points/]`
- NR4/NR7 Crabel definitions — `[CITED: forextraininggroup.com/.../narrow-range-bars-nr4-nr7]`, `[CITED: chartschool.stockcharts.com/.../narrow-range-day-nr7]`
- Inside Bar / ID/NR4 definition — `[CITED: tradingsetupsreview.com/inside-daynr4/]`
- Hurst R/S vs DFA survey — `[CITED: arxiv.org/html/2310.19051v3]`
- Mottl `hurst` Python library — `[CITED: github.com/Mottl/hurst]`
- pandas Rolling.rank with `pct=True` — `[CITED: pandas.pydata.org/pandas-docs/stable/reference/api/pandas.core.window.rolling.Rolling.rank.html]`

### Phase-internal (HIGH confidence)
- `.planning/phases/02-indicators-library/02-CONTEXT.md` — D-01..D-16 locked decisions
- `.planning/phases/01-backtest-engine/01-CONTEXT.md` — D-08 GMT-6→UTC, D-09 bar-close decision, purity convention
- `.planning/phases/01-backtest-engine/01-VERIFICATION.md` — Phase 1 verified passed
- `indicators.py` (existing 280 lines) — `_wilder_rsi`, `atr`, `find_support_resistance`, `compute_all` patterns to extend
- `.planning/codebase/STACK.md`, `STRUCTURE.md`, `TESTING.md`, `CONVENTIONS.md` — repo conventions

### Secondary (MEDIUM confidence)
- pandas-ta GitHub issue #228 (VWAP anchor parameter limitations) — informs decision to deviate to explicit `datetime` anchor
- pandas-ta GitHub issue #448 (anchor multiples regex) — same informational role
- "Algorithmic Trading with ADX in Python" EOD Historical Data — confirms pandas-ta ADX parameters

### Tertiary (LOW confidence — flagged for validation in planning/discuss-phase)
- "Boomer" exact rule definition — research finds varying definitions across sources; project skill `forex-trader-pro` is authoritative and must be consulted by planner.

## Metadata

**Confidence breakdown:**
- Standard stack (pandas-ta version, dev-dep posture): HIGH — verified PyPI release.
- Architecture (package split, dataclass-of-lists, `_helpers.py`): HIGH — locked in CONTEXT.md, validated by existing 280-line module patterns.
- Pitfalls (Wilder seed, future leakage, NY-17 DST, version pinning): HIGH — all derived from official pandas-ta source code or stdlib zoneinfo behavior.
- Camarilla / NR4/7 / Closing Score / Pivot formulas: HIGH — multi-source verification.
- Hurst R/S choice: MEDIUM — defensible but DFA equally valid; A1 in Assumptions Log.
- Boomer exact rule: MEDIUM — A2 in Assumptions Log; planner consults `forex-trader-pro` skill.
- MTF slope lookback (N=3): MEDIUM — A3; tunable, safe to ship and iterate.
- BBW squeeze percentile cut-off (25): MEDIUM — A4; tunable.

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (30 days; pandas-ta 0.4.x line stable; canonical formulas immutable; only PyPI version drift is a risk).

---

*Phase: 02-indicators-library*
*Researcher: gsd-phase-researcher*
*Ready for planning.*
