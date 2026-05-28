# Phase 2: Indicators Library - Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 25 (12 modules + 1 config + 2 fixtures + 9 tests + 1 dev-deps)
**Analogs found:** 25 / 25 (100% — every new file has a strong intra-repo analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `indicators/__init__.py` | package barrel (re-export) | request-response | `backtest/__init__.py` | role-match (barrel) |
| `indicators/_helpers.py` | utility (private) | transform | `indicators.py` `_wilder_rsi`/`_last_valid` | exact |
| `indicators/trend.py` | indicator submodule | transform (cumulative-incremental) | `indicators.py` `sma`/`ema` | exact (lift-and-shift) |
| `indicators/momentum.py` | indicator submodule + dataclasses | transform | `indicators.py` `rsi`/`check_rsi_divergence` | exact |
| `indicators/volatility.py` | indicator submodule + dataclasses + YAML loader | transform + config-load | `indicators.py` `atr` + `backtest/costs.py` `load_cost_model` | exact (split: math from `atr`, loader from `costs.py`) |
| `indicators/structure.py` | indicator submodule + dataclasses | transform | `indicators.py` `find_support_resistance`/`check_breakout_quality` | exact |
| `indicators/volume.py` | indicator submodule + dataclasses | transform (session-anchored cumulative) | `indicators.py` `avg_volume` | role-match (volume primitive); session-anchor pattern is new |
| `indicators/bars.py` | indicator submodule + dataclasses | transform (per-bar) | `indicators.py` `calculate_risk_reward` | role-match |
| `indicators/mtf.py` | indicator submodule + dataclasses | transform (cross-stream) | `indicators.py` `calculate_trend_strength` | exact (generalization) |
| `indicators/hurst.py` | indicator submodule + dataclass | transform (rolling window) | `indicators.py` `atr` (rolling shape) | role-match |
| `indicators/aggregate.py` | indicator submodule (snapshot helper) | transform (fan-out) | `indicators.py` `compute_all` | exact (extension, additive) |
| `requirements-dev.txt` | dev-dep manifest | config | `requirements.txt` | role-match |
| `data/configs/regime.yaml` | config (YAML) | config-load | `data/configs/costs.yaml` | exact |
| `tests/conftest.py` | test fixture (session-scoped) | fixture-load | `tests/conftest.py` (existing — to be EXTENDED, not replaced) | exact |
| `tests/fixtures/eurusd_h1_last500.csv` | test snapshot data | data-fixture | `tests/fixtures/eurusd_5bars.csv` | exact |
| `tests/test_indicators_momentum.py` | unit + parity test | request-response | `tests/test_backtest_costs.py` + new pandas-ta-oracle pattern | role-match |
| `tests/test_indicators_volatility.py` | unit + parity + leakage test | request-response | `tests/test_backtest_loader.py` (loader+leakage style) | role-match |
| `tests/test_indicators_structure.py` | unit (hand-calc fixture) | request-response | `tests/test_backtest_costs.py` (`_pip_params` hand-calc style) | exact |
| `tests/test_indicators_volume.py` | unit (manual fixture) | request-response | `tests/test_backtest_loader.py::test_gmt6_utc_offset` (timezone-aware fixture) | role-match |
| `tests/test_indicators_bars.py` | unit (hand-calc) | request-response | `tests/test_backtest_costs.py` | exact |
| `tests/test_indicators_mtf.py` | unit (synthetic streams) | request-response | `tests/test_backtest_costs.py` | role-match |
| `tests/test_indicators_hurst.py` | unit + parity | request-response | (new pandas-ta oracle pattern) | role-match |
| `tests/test_indicators_purity.py` | universal property test | request-response | `tests/test_backtest_loader.py::test_gmt6_utc_offset` regression style | role-match |
| `tests/test_indicators_aggregate.py` | unit | request-response | `tests/test_backtest_costs.py` | exact |

## Pattern Assignments

### `indicators/__init__.py` (package barrel, re-export)

**Analog:** `backtest/__init__.py:1-3`

**Re-export pattern (extend the existing pattern with explicit symbol re-imports):**
```python
"""Indicators package — math puro, niente pandas/ta-lib a runtime.

Convenzione: ogni serie restituita ha la stessa lunghezza dell'input.
Le posizioni iniziali insufficienti per il calcolo sono `None`.
"""
# Backward-compat re-exports: the 4 callsites in claude_agent.py:12, mcp_server.py:28,
# scanner.py:10, strategy.py:11 must keep working unchanged (D-03).
from indicators.trend import sma, ema
from indicators.momentum import rsi, check_rsi_divergence
from indicators.volatility import atr
from indicators.structure import find_support_resistance, check_breakout_quality
from indicators.volume import avg_volume
from indicators.bars import calculate_risk_reward
from indicators.mtf import calculate_trend_strength
from indicators.aggregate import compute_all, compute_all_extended

__all__ = [
    "sma", "ema", "rsi", "atr", "avg_volume",
    "calculate_trend_strength", "find_support_resistance",
    "check_breakout_quality", "calculate_risk_reward", "check_rsi_divergence",
    "compute_all", "compute_all_extended",
    # ... plus new symbols (BollingerResult, MACDResult, adx, macd, ...)
]
```

**Existing callsites that MUST keep working** (verified via Grep):
- `claude_agent.py:12` — `from indicators import compute_all`
- `mcp_server.py:28` — `from indicators import compute_all`
- `scanner.py:10-15` — `from indicators import (sma, ema, rsi, atr,)`
- `strategy.py:11-21` — `from indicators import (sma, ema, rsi, atr, avg_volume, calculate_trend_strength, find_support_resistance, check_breakout_quality, calculate_risk_reward,)`

**Note:** `backtest/__init__.py` uses `__all__` declaratively without imports yet — Phase 2 must IMPORT and re-export, not just declare `__all__`, otherwise the existing callsites break.

---

### `indicators/_helpers.py` (private utilities)

**Analog:** `indicators.py:62-66` (`_wilder_rsi`) and `indicators.py:99-103` (`_last_valid`)

**Wilder smoothing template to GENERALIZE** (existing in `indicators.py:62-66`):
```python
def _wilder_rsi(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)
```

**Generalize to** (research §Pattern 2):
```python
def _wilder_smooth(values: list[float], period: int) -> list[float | None]:
    """Smoothing Wilder/RMA: alpha=1/period, seed = SMA del primo periodo.
    Equivalente a pandas-ta `rma()` (mamode='rma') — parity 1e-6 garantita.
    """
    n = len(values)
    out: list[float | None] = [None] * n
    if n < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, n):
        prev = out[i - 1]
        out[i] = (prev * (period - 1) + values[i]) / period  # type: ignore[operator]
    return out
```

**Carry-over `_last_valid` verbatim** from `indicators.py:99-103`:
```python
def _last_valid(series: list[float | None]) -> float | None:
    for v in reversed(series):
        if v is not None:
            return v
    return None
```

**Session bucketing helper** (research §Pattern 3, NEW):
```python
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
_NY = ZoneInfo("America/New_York")

def _session_id_ny17(ts_utc: datetime) -> date:
    """Sessione FX ancorata a NY-17. Bar a/dopo 17:00 NY appartengono al giorno successivo."""
    ny = ts_utc.astimezone(_NY)
    if ny.hour >= 17:
        return (ny + timedelta(days=1)).date()
    return ny.date()
```

**Naming convention** (CONVENTIONS.md §Naming): leading underscore for module-private helpers — confirmed by `_wilder_rsi`, `_last_valid`, `_pip_size`, `_get_bool` precedents.

---

### `indicators/trend.py` (SMA, EMA — lift unchanged)

**Analog:** `indicators.py:8-32` — copy verbatim.

**SMA cumulative-incremental loop** (`indicators.py:8-18`) — KEEP STYLE for every new rolling indicator:
```python
def sma(values: list[float], period: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    cum = sum(values[:period])
    out[period - 1] = cum / period
    for i in range(period, n):
        cum += values[i] - values[i - period]
        out[i] = cum / period
    return out
```

**EMA seed-from-SMA pattern** (`indicators.py:21-32`) — replicate seed semantics for any EWMA-style indicator:
```python
def ema(values: list[float], period: int) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    alpha = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, n):
        prev = out[i - 1]
        out[i] = alpha * values[i] + (1.0 - alpha) * prev  # type: ignore[operator]
    return out
```

---

### `indicators/momentum.py` (RSI, MACD, Stochastic, ADX/DMI, divergence)

**Analog:** `indicators.py:35-59` (RSI) + `indicators.py:246-279` (`check_rsi_divergence`)

**Existing RSI** (`indicators.py:35-59`) — port verbatim:
```python
def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    # ... preserves Wilder seeding from sum(gains[1:period+1])/period
    avg_gain = sum(gains[1:period + 1]) / period
    avg_loss = sum(losses[1:period + 1]) / period
    out[period] = _wilder_rsi(avg_gain, avg_loss)
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = _wilder_rsi(avg_gain, avg_loss)
    return out
```

**Existing divergence detector** (`indicators.py:246-279`) — port verbatim, return string literal `"BULLISH_DIVERGENCE"`/`"BEARISH_DIVERGENCE"`/`"NONE"` (consumed by strategy as-is).

**Dataclass pattern** (`models.py:6-17` style — co-located per D-05):
```python
from dataclasses import dataclass

@dataclass
class MACDResult:
    macd: list[float | None]
    signal: list[float | None]
    histogram: list[float | None]

@dataclass
class ADXResult:
    adx: list[float | None]
    plus_di: list[float | None]
    minus_di: list[float | None]

@dataclass
class StochasticResult:
    k: list[float | None]
    d: list[float | None]
```

**ADX implementation** — RESEARCH.md §Code Examples Example 1 (uses `_wilder_smooth` from `_helpers.py`).

---

### `indicators/volatility.py` (ATR, Bollinger+squeeze, Keltner, regime)

**Analog (math):** `indicators.py:69-96` (`atr`) — port verbatim.
**Analog (config loading):** `backtest/costs.py:42-59` (`load_cost_model`) — clone the YAML+default+symbol-override pattern.

**ATR with input validation** (`indicators.py:69-96`) — note the `ValueError` on length mismatch (CONVENTIONS §Error Handling: fail-fast, Italian message):
```python
def atr(highs, lows, closes, period=14):
    n = len(closes)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period + 1:
        return out
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, closes devono avere la stessa lunghezza")
    tr = [0.0] * n
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]))
    seed = sum(tr[1:period + 1]) / period
    out[period] = seed
    for i in range(period + 1, n):
        prev = out[i - 1]
        out[i] = (prev * (period - 1) + tr[i]) / period
    return out
```

**YAML config loader pattern from `backtest/costs.py:42-59`** — clone for `regime.yaml`:
```python
def load_regime_config(symbol: str, yaml_path: Path) -> dict:
    """Carica config regime.yaml: default + override per simbolo (mirror Phase 1 D-05)."""
    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    sym_cfg = (cfg.get("symbols") or {}).get(symbol)
    if sym_cfg is None:
        sym_cfg = cfg.get("default")
    if sym_cfg is None:
        raise KeyError(f"no regime config for symbol {symbol!r} in {yaml_path}")
    return sym_cfg
```

**Volatility regime no-future-leakage implementation** — RESEARCH.md §Example 3 (uses `atr()` + manual rolling rank, never `pd.Series.rank(pct=True)` on full series — Pitfall 4).

**Bollinger+Keltner dataclasses:**
```python
@dataclass
class BollingerResult:
    upper: list[float | None]
    middle: list[float | None]
    lower: list[float | None]
    bbw: list[float | None]              # bandwidth (upper - lower) / middle
    squeeze: list[bool | None]           # BBW < squeeze_pct of trailing N-bar BBW
    squeeze_ttm: list[bool | None]       # BB-inside-Keltner (Carter TTM, secondary)

@dataclass
class KeltnerResult:
    upper: list[float | None]
    middle: list[float | None]
    lower: list[float | None]

@dataclass
class RegimeResult:
    state: list[str | None]              # 'compressed' | 'normal' | 'expanded' | None
    atr_percentile: list[float | None]
    window: int
```

---

### `indicators/structure.py` (Donchian, Pivots, Fibonacci, S/R)

**Analog (S/R):** `indicators.py:164-195` (`find_support_resistance`) — port verbatim, REUSE for Fibonacci leg detection (research §Open-Q5).
**Analog (breakout quality):** `indicators.py:209-234` (`check_breakout_quality`) — port verbatim.

**Existing pivot-based S/R** (`indicators.py:164-195`) — keep as-is and reuse for INDIC-08 swing-leg detection:
```python
def find_support_resistance(bars: list[dict], lookback: int = 100, window: int = 2) -> dict:
    # ... swing pivots: bar i is high-pivot if high[i] >= high[j] for j ∈ [i-window..i+window], j != i
    # Reused by Fibonacci to detect "last completed swing leg" (high → low or low → high)
```

**Pivot dataclass** (D-11) and **Camarilla formula** — RESEARCH.md §Example 2:
```python
@dataclass
class PivotResult:
    p: list[float | None]
    r1: list[float | None]; r2: list[float | None]; r3: list[float | None]
    s1: list[float | None]; s2: list[float | None]; s3: list[float | None]
    camarilla: dict[str, list[float | None]]  # keys: "h1".."h4", "l1".."l4"

@dataclass
class DonchianResult:
    upper: list[float | None]
    lower: list[float | None]
    middle: list[float | None]

@dataclass
class FibonacciResult:
    levels: dict[str, float | None]   # keys: "0", "0.382", "0.5", "0.618", "1.0"
    leg_high: float | None
    leg_low: float | None
    direction: str  # "up" | "down" | "none"
```

---

### `indicators/volume.py` (VWAP intraday + anchored, avg_volume)

**Analog:** `indicators.py:198-206` (`avg_volume`) — port verbatim (handles `tick_volume` fallback to `volume`):
```python
def avg_volume(bars: list[dict], period: int = 20) -> float:
    if not bars or period <= 0:
        return 0.0
    sub = bars[-period:]
    vols = [b.get("tick_volume", b.get("volume", 0)) or 0 for b in sub]
    if not vols:
        return 0.0
    return sum(vols) / len(vols)
```

**VWAPResult dataclass:**
```python
@dataclass
class VWAPResult:
    vwap: list[float | None]
    cumulative_pv: list[float | None]
    cumulative_v: list[float | None]
```

**Session-anchored cumulative** uses `_session_id_ny17` from `_helpers.py` (research §Pattern 3). Anchored VWAP signature per D-10: `vwap_anchored(bars: list[dict], anchor_ts: datetime) -> VWAPResult`.

---

### `indicators/bars.py` (NR4/NR7+Boomer, Closing Score, R:R)

**Analog:** `indicators.py:237-243` (`calculate_risk_reward`) — port verbatim:
```python
def calculate_risk_reward(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    if risk == 0:
        return 0.0
    reward = abs(tp - entry)
    return round(reward / risk, 4)
```

**New dataclasses:**
```python
@dataclass
class NRResult:
    nr4: list[bool | None]
    nr7: list[bool | None]
    inside: list[bool | None]
    boomer: list[bool | None]

@dataclass
class ClosingScoreResult:
    score: list[float | None]   # (close - low) / (high - low) * 100, ∈ [0,100]
```

Closing Score (Defendi) = `(close - low) / (high - low) * 100` per bar — trivial loop, mask `None` when `high == low` (degenerate bar).

---

### `indicators/mtf.py` (multi-TF alignment INDIC-13)

**Analog:** `indicators.py:125-161` (`calculate_trend_strength`) — port verbatim AND extend with new `align()`:
```python
def calculate_trend_strength(
    bars: list[dict], sma_fast: float | None, sma_slow: float | None,
    coherence_window: int = 10,
) -> float:
    # ... existing combination of SMA-separation (50%) + close-direction coherence (50%)
    # Phase 2 KEEPS this signature unchanged — strategy.py:11 imports it.
```

**New `align()` per D-13/D-14:**
```python
@dataclass
class MTFAlignmentResult:
    score: list[float | None]      # ∈ {0.0, 0.33, 0.66, 1.0}
    h4_dir: list[int | None]       # ∈ {-1, 0, +1}
    h1_dir: list[int | None]
    m15_dir: list[int | None]

def align(streams: dict[str, list[dict]]) -> MTFAlignmentResult:
    """INDIC-13: sign-agreement of EMA50 slope across H4/H1/M15.
    Caller (strategy) MUST pass only bars closed at-or-before current M15 bar (no future leakage)."""
    # required keys: 'H4', 'H1', 'M15'
```

---

### `indicators/hurst.py` (Hurst R/S)

**No exact analog** — pattern guidance: rolling-window math identical in shape to `atr` (input list → list[float|None] same length). Use R/S estimator with `window=100` per CONTEXT specifics §INDIC-12.

```python
@dataclass
class HurstResult:
    hurst: list[float | None]      # ∈ [0, 1]
    window: int
```

---

### `indicators/aggregate.py` (compute_all + compute_all_extended)

**Analog:** `indicators.py:106-117` (`compute_all`) — port VERBATIM (do not modify; D-discretion + research §Open-Q10 confirms split):
```python
def compute_all(ohlc: list[dict]) -> dict:
    """Estrae closes/highs/lows e ritorna l'ultimo valore valido di sma_20, ema_50, rsi_14, atr_14.
    SHAPE PRESERVED: claude_agent.py:12 + mcp_server.py:28 import this — do NOT change keys."""
    closes = [b["close"] for b in ohlc]
    highs = [b["high"] for b in ohlc]
    lows = [b["low"] for b in ohlc]
    return {
        "sma_20": _last_valid(sma(closes, 20)),
        "ema_50": _last_valid(ema(closes, 50)),
        "rsi_14": _last_valid(rsi(closes, 14)),
        "atr_14": _last_valid(atr(highs, lows, closes, 14)),
    }
```

**New extended snapshot** (additive, D-Discretion + research §Open-Q10):
```python
def compute_all_extended(bars: list[dict], regime_cfg: dict | None = None) -> dict:
    """Snapshot 14-indicator per backtest + futura strategy refactor (Phase 4).
    Non rompe `compute_all` legacy."""
    # _last_valid of each new indicator series + classic 4-key block
```

---

### `requirements-dev.txt` (NEW)

**Analog:** `requirements.txt` (existing pinned manifest).

**Content** (RESEARCH §Standard Stack):
```
# Test-only dependencies (D-07 oracle). Mai importati a runtime.
pandas-ta==0.4.71b0
```
NOTE — Pitfall 1: do NOT pin `0.3.14b` (deleted from PyPI 2025-09-08).

---

### `data/configs/regime.yaml` (NEW config)

**Analog:** `data/configs/costs.yaml` (existing — Phase 1 D-05).

**Schema pattern from `costs.yaml`** (per-symbol override + sensible default):
```yaml
# data/configs/regime.yaml
# INDIC-14 volatility regime classifier thresholds (D-15).
# atr_percentile rolling-rank window e cut-off compressed/expanded.

default:
  window: 200
  compressed_below: 30   # percentile (0..100)
  expanded_above: 70

symbols:
  EURUSD:
    window: 200
    compressed_below: 25
    expanded_above: 75
  GBPUSD:
    window: 200
    compressed_below: 30
    expanded_above: 70
  USDJPY:
    window: 200
    compressed_below: 30
    expanded_above: 70
```

NOTE — costs.yaml uses **flat top-level keys**; regime.yaml needs the `default:` + `symbols:` nesting per CONTEXT D-15. The loader (`load_regime_config` in `volatility.py`) bridges.

---

### `tests/conftest.py` (EXTEND existing)

**Analog (and target):** `tests/conftest.py:1-50` (existing — has `MetaTrader5` stub + `fixture_5bars_path` + `costs_yaml_path`).

**ADD a session-scoped fixture (research §Open-Q12)** without breaking existing fixtures:
```python
# Append to tests/conftest.py — DO NOT replace existing content.
import csv
from datetime import datetime, timezone

@pytest.fixture(scope="session")
def eurusd_h1_500() -> list[dict]:
    """500-bar EURUSD H1 snapshot per D-08. Loaded once per session.
    Generato via tests/fixtures/build_eurusd_h1_last500.py (one-off) usando backtest.loader.load_bars."""
    fpath = Path(__file__).parent / "fixtures" / "eurusd_h1_last500.csv"
    out: list[dict] = []
    with open(fpath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append({
                "time": int(row["time"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "tick_volume": int(row["volume"]),
            })
    return out
```

---

### `tests/fixtures/eurusd_h1_last500.csv` (NEW snapshot)

**Analog:** `tests/fixtures/eurusd_5bars.csv` (Phase 1 fixture, used via `fixture_5bars_path`).

**Generation (one-off script under `scripts/` or `tests/fixtures/`):**
```python
# tests/fixtures/build_eurusd_h1_last500.py — esegui una volta, commit del CSV risultante.
from pathlib import Path
import csv
from backtest.loader import load_bars

REPO = Path(__file__).resolve().parents[2]
src = REPO / "data" / "historical" / "EURUSD" / "H1.csv"
bars = load_bars(src, "EURUSD", "H1")[-500:]
out = REPO / "tests" / "fixtures" / "eurusd_h1_last500.csv"
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["time", "open", "high", "low", "close", "volume"])
    for b in bars:
        w.writerow([b.time, b.open, b.high, b.low, b.close, b.volume])
```

CSV columns: simple `time,open,high,low,close,volume` (UTC unix seconds — already converted from GMT-6 by Phase 1 loader). Schema chosen for round-trip simplicity, NOT mimicking the Italian semicolon source (that would re-introduce GMT-6 ambiguity).

---

### `tests/test_indicators_*.py` (9 new test files)

**Analog (general layout + Italian docstring):** `tests/test_backtest_costs.py` and `tests/test_backtest_loader.py`.

**Imports + module docstring pattern** (`tests/test_backtest_loader.py:1-12`):
```python
"""Test indicators.<submodule> (INDIC-XX) — copre D-07 hybrid oracle."""
from __future__ import annotations
from pathlib import Path
import pytest

from indicators.momentum import adx, macd, stochastic, ADXResult, MACDResult
```

**Hand-calculated assertion pattern** (`tests/test_backtest_costs.py:9-20`):
```python
def test_eurusd_1pip_1lot() -> None:
    """SC-3: 1-pip spread on 1-lot EUR/USD = exactly $10.00."""
    pip_size, pip_value = _pip_params("EURUSD", 1.10000)
    model = CostModel(...)
    cost = model.cost_usd(lots=1.0)
    assert abs(cost - 10.0) < 1e-9, f"expected $10.00, got ${cost:.6f}"
```
Apply this pattern to: NR4/NR7 (`test_indicators_bars.py`), Closing Score, Donchian, Camarilla, Pivots, MTF synthetic streams.

**pandas-ta parity oracle pattern** (NEW, RESEARCH.md §Code Examples Example 4):
```python
import pandas as pd
import pandas_ta as pta
from indicators.momentum import adx

def test_adx_parity_with_pandas_ta(eurusd_h1_500):
    df = pd.DataFrame(eurusd_h1_500)
    h, l, c = df["high"].tolist(), df["low"].tolist(), df["close"].tolist()
    ours = adx(h, l, c, period=14)
    expected = pta.adx(df["high"], df["low"], df["close"], length=14, mamode="rma")
    for i in range(50, len(c)):  # skip 2*period warmup
        if ours.adx[i] is not None and not pd.isna(expected["ADX_14"].iloc[i]):
            assert abs(ours.adx[i] - expected["ADX_14"].iloc[i]) < 1e-6
```

**Skip-when-missing pattern for parity tests** (analog: `tests/test_backtest_loader.py:52-53`):
```python
import importlib.util
_HAVE_PTA = importlib.util.find_spec("pandas_ta") is not None

@pytest.mark.skipif(not _HAVE_PTA, reason="pandas-ta dev-dep non installato")
def test_adx_parity_with_pandas_ta(eurusd_h1_500):
    ...
```

**Universal future-leakage property test** (`tests/test_indicators_purity.py`, NEW):
```python
"""Universal property test: ogni indicatore rolling deve essere leakage-free.
   compute(bars[:i+1])[i] == compute(bars)[i] per spot indices i."""
def test_no_future_leakage_atr(eurusd_h1_500):
    bars = eurusd_h1_500
    full = atr([b["high"] for b in bars], [b["low"] for b in bars], [b["close"] for b in bars], 14)
    for i in (50, 100, 200, 350, 499):
        prefix = bars[:i+1]
        partial = atr([b["high"] for b in prefix], [b["low"] for b in prefix], [b["close"] for b in prefix], 14)
        assert partial[i] == full[i], f"future leakage at i={i}"
```

---

## Shared Patterns

### Convention 1: Italian docstrings/comments, English snake_case test names

**Source:** CLAUDE.md §Convenzioni + CONVENTIONS.md §Comments.
**Apply to:** Every new `.py` file in `indicators/` and `tests/`.

**Module docstring (Italian)** — `indicators.py:1-5`:
```python
"""Indicatori tecnici in Python puro su array OHLC. Niente pandas/ta-lib.

Convenzione: ogni serie restituita ha la stessa lunghezza dell'input.
Le posizioni iniziali insufficienti per il calcolo sono `None`.
"""
```

**Test name pattern (English snake_case)** — `tests/test_backtest_costs.py:9`:
```python
def test_eurusd_1pip_1lot() -> None:
    """SC-3: 1-pip spread on 1-lot EUR/USD = exactly $10.00."""
```

### Convention 2: PEP 604 type hints + `list[float | None]` purity

**Source:** `indicators.py` everywhere; CONVENTIONS.md §Type Hints.
**Apply to:** Every indicator return.

```python
def my_indicator(values: list[float], period: int = 14) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return out
    # ... fill out[period-1:] preserving leading None warmup
```

### Convention 3: Dataclass-of-lists (D-04, D-06)

**Source:** `models.py:6-17` style + RESEARCH §Examples.
**Apply to:** All compound-output indicators (BollingerResult, MACDResult, ADXResult, StochasticResult, KeltnerResult, DonchianResult, VWAPResult, FibonacciResult, PivotResult, NRResult, ClosingScoreResult, HurstResult, MTFAlignmentResult, RegimeResult).

```python
from dataclasses import dataclass

@dataclass
class XxxResult:
    primary: list[float | None]
    secondary: list[float | None]
    flag: list[bool | None]   # where appropriate
```
Co-located in owning submodule (D-05); re-exported from `indicators/__init__.py`.

### Convention 4: Input validation = fail-fast `ValueError` with Italian message

**Source:** `indicators.py:79-80` (`atr` length check), `backtest/costs.py:34, 50` (price/symbol checks).
**Apply to:** All multi-list indicators (ADX, Stochastic, Bollinger, Keltner, Donchian, etc.).

```python
if not (len(highs) == len(lows) == len(closes)):
    raise ValueError("highs, lows, closes devono avere la stessa lunghezza")
if period <= 0:
    raise ValueError(f"period deve essere > 0, ricevuto {period}")
```

### Convention 5: YAML config — `yaml.safe_load` + default + per-symbol override

**Source:** `backtest/costs.py:42-59`.
**Apply to:** `data/configs/regime.yaml` loader in `indicators/volatility.py`.

```python
with open(yaml_path, encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}
sym_cfg = (cfg.get("symbols") or {}).get(symbol)
if sym_cfg is None:
    sym_cfg = cfg.get("default")
if sym_cfg is None:
    raise KeyError(f"no regime config for symbol {symbol!r} in {yaml_path}")
```

### Convention 6: Test imports + path resolution

**Source:** `tests/test_backtest_loader.py:1-12`.
**Apply to:** All new `tests/test_indicators_*.py`.

```python
from __future__ import annotations
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
```

### Convention 7: Cumulative-incremental rolling (O(n))

**Source:** `indicators.py:13-17` (`sma`).
**Apply to:** Every new rolling indicator (Donchian, BBands, Stoch, Keltner middle).

```python
cum = sum(values[:period])
out[period - 1] = cum / period
for i in range(period, n):
    cum += values[i] - values[i - period]
    out[i] = cum / period
```
NOT `sum(values[i-period+1:i+1])` per iteration.

### Convention 8: Wilder/RMA smoothing seeded by SMA-of-first-period

**Source:** `indicators.py:50-57` (RSI inline) — generalize to `_wilder_smooth` helper.
**Apply to:** ADX components (+DM, -DM, TR), ATR-percentile if needed.

```python
seed = sum(values[:period]) / period
out[period - 1] = seed
for i in range(period, n):
    out[i] = (out[i-1] * (period - 1) + values[i]) / period
```
Critical for pandas-ta parity at `1e-6` (Pitfall 2).

### Convention 9: Backward-compat re-exports from package barrel

**Source:** Existing 4 callsites must keep working — `claude_agent.py:12`, `mcp_server.py:28`, `scanner.py:10`, `strategy.py:11`.
**Apply to:** `indicators/__init__.py` — explicit `from indicators.<sub> import <name>` for each public symbol.

### Convention 10: `pandas-ta` NEVER imported at runtime

**Source:** D-07 + Pitfall 8.
**Apply to:** Production guard — every `indicators/*.py` file. Suggested CI test:
```python
# tests/test_indicators_purity.py
def test_no_pandas_ta_at_runtime():
    import sys
    # importing indicators must NOT pull pandas_ta
    if "pandas_ta" in sys.modules:
        del sys.modules["pandas_ta"]
    import indicators  # noqa: F401
    assert "pandas_ta" not in sys.modules, "pandas_ta importato a runtime — vietato"
```

## No Analog Found

All 25 files have at least a role-match analog inside the repo. The two **patterns** with no direct intra-repo precedent (deferred to RESEARCH.md):

| Pattern | Why no analog | Reference |
|---|---|---|
| Session-anchored cumulative (NY-17 VWAP/Pivot reset) | First use of `zoneinfo.ZoneInfo("America/New_York")` in repo (existing code uses `_TZ_ROME` for wall-clock, not session boundaries) | RESEARCH §Pattern 3 |
| pandas-ta parity oracle in tests | First dev-dep of this kind | RESEARCH §Code Examples Example 4 |
| Hurst R/S estimator | No precedent for log-log regression over sub-windows | RESEARCH §Don't Hand-Roll, §Open-Q1 |

Planner falls back to RESEARCH.md for these three; the rest is fully covered by repo precedent.

## Metadata

**Analog search scope:** repo root flat layout + `backtest/`, `indicators.py`, `models.py`, `tests/`, `data/configs/`.
**Files scanned:** 11 source modules, 7 test files, 1 YAML config, 1 conftest, 1 fixture CSV.
**Pattern extraction date:** 2026-05-07.
**Phase:** 02-indicators-library.
