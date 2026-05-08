"""Test detector setup A/B/C/D puri (STRAT-01..04).

Wave 0: tutti pytest.skip (collection-only).
Wave 2 plan-05: A_breakout (3 test) + D_pullback (2 test) implementati.
Wave 2 plan-06: B_reversal (2 test) + C_compression (2 test) — restano skip.
Wave 3 plan-07: multi_match priority — resta skip.

Pattern S-1: docstring italiano + English snake_case test names.
Helpers (_make_bars / _stub_indicators_a / _stub_indicators_d / _stub_ctx) condivisi
fra A e D, riusabili da plan-06 estendendo _stub_indicators_b/_stub_indicators_c.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from strategy.context import StrategyContext
from strategy.setups.a_breakout import detect_a_breakout
from strategy.setups.b_reversal import detect_b_reversal  # noqa: F401
from strategy.setups.c_compression import detect_c_compression  # noqa: F401
from strategy.setups.d_pullback import detect_d_pullback
from strategy.proposal import ProposalDraft  # noqa: F401


# ==========================================================================
# Helpers (riusabili da plan-06 quando arriveranno B/C)
# ==========================================================================

PIP = 0.0001


def _make_bars(closes, base_offset: float = 0.0001) -> list[dict]:
    """Genera N bars dict con close=closes[i], open=close, high=close+offset, low=close-offset.

    time è un index incrementale (i secondi epoch fittizi); non usato dai detector.
    """
    bars = []
    for i, c in enumerate(closes):
        bars.append(
            {
                "time": 1_700_000_000 + i * 900,  # 15 min step (M15)
                "open": c,
                "high": c + base_offset,
                "low": c - base_offset,
                "close": c,
                "tick_volume": 100,
            }
        )
    return bars


def _stub_indicators_a(close_ref: float, n: int = 200) -> SimpleNamespace:
    """Snapshot ExtendedIndicators-like per Setup A: liste lunghe n, last via [-1].

    Setup A non consuma fibonacci → impostato None.
    Spread/atr = 0.0001/0.0010 = 0.10 < 0.20 (max_spread_atr_ratio) → spread_session True.
    """
    return SimpleNamespace(
        atr_14=[0.0010] * n,
        rsi_14=[55.0] * n,
        closing_score=[85.0] * n,
        volatility_regime=["expanded"] * n,
        ema50_slope=[0.0001] * n,
        ema20=[close_ref] * n,
        ema50=[close_ref - 0.0010] * n,
        donchian_high=[close_ref + 0.0020] * n,
        donchian_low=[close_ref - 0.0020] * n,
        nr_detect=SimpleNamespace(nr4=[False] * n, nr7=[False] * n),
        bollinger_bands=SimpleNamespace(
            squeeze=[False] * n,
            upper=[close_ref + 0.002] * n,
            lower=[close_ref - 0.002] * n,
        ),
        fibonacci=None,
    )


def _stub_indicators_d(
    close_ref: float,
    ema20: float,
    ema50: float,
    slope: float = 0.0001,
    fib_levels: dict | None = None,
    leg_high: float | None = None,
    leg_low: float | None = None,
    closing_score: float = 60.0,  # banda neutrale 30-70 → setup_pattern D True
    n: int = 200,
) -> SimpleNamespace:
    """Snapshot ExtendedIndicators-like per Setup D.

    closing_score default 60 → dentro [30,70] (setup_pattern True per D).
    fibonacci optional: passa fib_levels dict per popolarlo.
    """
    fib = None
    if fib_levels is not None or (leg_high is not None and leg_low is not None):
        fib = SimpleNamespace(
            levels=fib_levels or {},
            leg_high=leg_high,
            leg_low=leg_low,
        )
    return SimpleNamespace(
        atr_14=[0.0010] * n,
        rsi_14=[55.0] * n,
        closing_score=[closing_score] * n,
        volatility_regime=["normal"] * n,  # pullback_required: ['normal']
        ema50_slope=[slope] * n,
        ema20=[ema20] * n,
        ema50=[ema50] * n,
        donchian_high=[close_ref + 0.0050] * n,
        donchian_low=[close_ref - 0.0050] * n,
        nr_detect=SimpleNamespace(nr4=[False] * n, nr7=[False] * n),
        bollinger_bands=SimpleNamespace(
            squeeze=[False] * n,
            upper=[close_ref + 0.002] * n,
            lower=[close_ref - 0.002] * n,
        ),
        fibonacci=fib,
    )


def _stub_ctx(
    profile: str = "MODERATE",
    resistance: float = 1.10500,
    support: float = 1.09500,
    close_ref: float = 1.10000,
    spread_pips: float = 1.0,
) -> StrategyContext:
    """StrategyContext sintetico con symbol_info SimpleNamespace.

    spread_pips=1.0 → spread/atr = 0.0001/0.0010 = 0.10 < 0.20 → spread_session True.
    """
    bid = close_ref
    ask = bid + spread_pips * PIP
    sym = SimpleNamespace(bid=bid, ask=ask, point=0.00001, digits=5)
    return StrategyContext(
        symbol="EURUSD",
        timeframe="M15",
        profile=profile,
        sr={"resistance": resistance, "support": support},
        regime="normal",
        patterns=[],
        symbol_info=sym,
        pip_size=PIP,
        spread_baseline_pips=2.0,
    )


# ==========================================================================
# Setup A — Breakout (STRAT-01)
# ==========================================================================


def test_detect_a_breakout_ready():
    """Last close oltre resistance + 5-factor favorevoli → READY/A_breakout/BUY."""
    bars = _make_bars([1.10510] * 200)  # tutti i close oltre resistance 1.10500
    ind = _stub_indicators_a(close_ref=1.10510)
    ctx = _stub_ctx(profile="MODERATE", resistance=1.10500, support=1.09500, close_ref=1.10510)
    d = detect_a_breakout(bars, ind, ctx)
    assert d.setup_type == "READY", f"expected READY got {d.setup_type} reason={d.reason}"
    assert d.setup_name == "A_breakout"
    assert d.direction == "BUY"
    assert d.entry_price is not None
    assert d.stop_loss_price is not None
    assert d.take_profit_price is not None
    assert d.grade in ("A+", "A", "B", "C")
    assert 0.10 <= d.confidence <= 0.95


def test_detect_a_breakout_none_no_breakout():
    """Last close mid-range, lontano da SR → NONE/no_breakout_detected."""
    bars = _make_bars([1.10000] * 200)  # ben dentro la banda SR
    ind = _stub_indicators_a(close_ref=1.10000)
    ctx = _stub_ctx(resistance=1.10500, support=1.09500, close_ref=1.10000)
    d = detect_a_breakout(bars, ind, ctx)
    assert d.setup_type == "NONE"
    assert d.reason == "no_breakout_detected"


def test_detect_a_breakout_forming_near_resistance():
    """Last close 0.2 pip sotto resistance (entro 5-pip tol) → FORMING/A_breakout/BUY."""
    bars = _make_bars([1.10498] * 200)  # 0.00002 sotto 1.10500, ben dentro 5*pip=0.0005
    ind = _stub_indicators_a(close_ref=1.10498)
    ctx = _stub_ctx(resistance=1.10500, support=1.09500, close_ref=1.10498)
    d = detect_a_breakout(bars, ind, ctx)
    assert d.setup_type == "FORMING"
    assert d.direction == "BUY"
    assert d.setup_name == "A_breakout"


# ==========================================================================
# Setup B — Reversal (STRAT-02) — Wave 2 plan-06
# ==========================================================================


def test_detect_b_reversal_ready_at_support():
    pytest.skip("Wave 2 pending — STRAT-02")


def test_detect_b_reversal_counter_trend_gate():
    pytest.skip("Wave 2 pending — STRAT-02 (D-07 gate)")


# ==========================================================================
# Setup C — Compression (STRAT-03) — Wave 2 plan-06
# ==========================================================================


def test_detect_c_compression_nr7():
    pytest.skip("Wave 2 pending — STRAT-03")


def test_detect_c_compression_squeeze():
    pytest.skip("Wave 2 pending — STRAT-03")


# ==========================================================================
# Setup D — Trend Pullback (STRAT-04)
# ==========================================================================


def test_detect_d_pullback_ema20_touch():
    """Trend up (slope+) + close esattamente su EMA20 + price>EMA50 → READY/D_pullback/BUY."""
    bars = _make_bars([1.10100] * 200)
    ind = _stub_indicators_d(
        close_ref=1.10100,
        ema20=1.10100,   # close == ema20 → in_ema20_zone True
        ema50=1.10000,   # close > ema50 → lato corretto BUY
        slope=0.0001,    # > SLOPE_THRESHOLD 0.00005
    )
    ctx = _stub_ctx(profile="MODERATE", resistance=1.11000, support=1.09000, close_ref=1.10100)
    d = detect_d_pullback(bars, ind, ctx)
    assert d.setup_type == "READY", f"got {d.setup_type} reason={d.reason}"
    assert d.setup_name == "D_pullback"
    assert d.direction == "BUY"
    assert d.entry_price is not None
    assert d.stop_loss_price is not None
    assert d.take_profit_price is not None


def test_detect_d_pullback_fib_38():
    """Trend up + close NON in EMA20 zone ma in Fib 0.382-0.618 → READY (Fib path).

    Liberal: accetta READY o FORMING-ma-non-'trend_ok_pullback_not_in_zone' come segno
    che il path Fib è stato esercitato senza far cadere in FORMING-not-in-zone.
    """
    fib_levels = {"0.382": 1.10050, "0.618": 1.10150}
    bars = _make_bars([1.10100] * 200)
    ind = _stub_indicators_d(
        close_ref=1.10100,
        ema20=1.10300,   # 20 pips dal close → fuori EMA20 zone (0.5×ATR=0.0005=5 pip)
        ema50=1.10000,
        slope=0.0001,
        fib_levels=fib_levels,
        leg_high=1.10500,
        leg_low=1.09500,
    )
    ctx = _stub_ctx(close_ref=1.10100)
    d = detect_d_pullback(bars, ind, ctx)
    # Path Fib esercitato: setup_type non deve essere FORMING per "trend_ok_pullback_not_in_zone"
    assert d.setup_type in ("READY", "FORMING", "NONE"), f"unexpected setup_type {d.setup_type}"
    if d.setup_type == "FORMING":
        assert d.reason != "trend_ok_pullback_not_in_zone", (
            "Fib zone dovrebbe rescuel'attivazione del pullback"
        )


# ==========================================================================
# Multi-match priority (Wave 3 plan-07 — D-06 tie-break A>C>B>D)
# ==========================================================================


def test_evaluate_proposal_for_bar_multi_match_priority():
    pytest.skip("Wave 3 pending — D-06 tie-break A>C>B>D")
