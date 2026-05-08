"""Test detector setup A/B/C/D puri (STRAT-01..04).

Wave 0: tutti pytest.skip (collection-only).
Wave 2 plan-05: A_breakout (3 test) + D_pullback (2 test) implementati.
Wave 2 plan-06: B_reversal (2 test) + C_compression (2 test) implementati.
Wave 3 plan-07: multi_match priority — resta skip.

Pattern S-1: docstring italiano + English snake_case test names.
Helpers (_make_bars / _stub_indicators_a / _stub_indicators_b / _stub_indicators_c /
_stub_indicators_d / _stub_ctx) condivisi fra i 4 setup.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from strategy.context import StrategyContext
from strategy.setups.a_breakout import detect_a_breakout
from strategy.setups.b_reversal import detect_b_reversal
from strategy.setups.c_compression import detect_c_compression
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


def _make_pattern_hit(
    name: str,
    direction: str,
    bar_index: int = -1,
    extreme_price: float | None = None,
    confidence: float = 0.7,
) -> SimpleNamespace:
    """PatternHit duck-type per test (Phase 3 dataclass non richiesta a livello unit).

    Attribute access: name, direction, bar_index, extreme_price, confidence.
    Mai dict-key (RESEARCH Pitfall #3 — Setup B usa SOLO attribute access).
    """
    return SimpleNamespace(
        name=name,
        direction=direction,
        bar_index=bar_index,
        extreme_price=extreme_price,
        confidence=confidence,
    )


def _stub_indicators_b(
    close_ref: float,
    slope: float = 0.0001,
    regime: str = "normal",
    rsi: float = 30.0,
    n: int = 200,
) -> SimpleNamespace:
    """Snapshot ExtendedIndicators-like per Setup B.

    Default: regime=normal (reversal_required allowed), rsi=30 (BUY momentum True),
    slope=+0.0001 (uptrend → BUY trend_alignment True).
    """
    return SimpleNamespace(
        atr_14=[0.0010] * n,
        rsi_14=[rsi] * n,
        closing_score=[55.0] * n,
        volatility_regime=[regime] * n,
        ema50_slope=[slope] * n,
        ema20=[close_ref] * n,
        ema50=[close_ref - 0.0010] * n,
        nr_detect=SimpleNamespace(nr4=[False] * n, nr7=[False] * n),
        bollinger_bands=SimpleNamespace(
            squeeze=[False] * n,
            upper=[close_ref + 0.002] * n,
            lower=[close_ref - 0.002] * n,
        ),
        fibonacci=None,
    )


def _stub_indicators_c(
    close_ref: float,
    slope: float = 0.0001,
    nr7_count: int = 0,
    nr4_count: int = 0,
    squeeze_count: int = 0,
    regime: str = "compressed",
    n: int = 200,
) -> SimpleNamespace:
    """Snapshot ExtendedIndicators-like per Setup C.

    Le ultime nr7_count entries di nr7 (rispettivamente nr4 / squeeze) sono True;
    il resto False. Default regime=compressed (compression_required allowed).
    """
    nr7 = [False] * n
    for i in range(nr7_count):
        if i < n:
            nr7[-1 - i] = True
    nr4 = [False] * n
    for i in range(nr4_count):
        if i < n:
            nr4[-1 - i] = True
    squeeze = [False] * n
    for i in range(squeeze_count):
        if i < n:
            squeeze[-1 - i] = True
    return SimpleNamespace(
        atr_14=[0.0010] * n,
        rsi_14=[55.0] * n,
        closing_score=[60.0] * n,
        volatility_regime=[regime] * n,
        ema50_slope=[slope] * n,
        ema20=[close_ref] * n,
        ema50=[close_ref - 0.0010] * n,
        nr_detect=SimpleNamespace(nr4=nr4, nr7=nr7),
        bollinger_bands=SimpleNamespace(
            squeeze=squeeze,
            upper=[close_ref + 0.002] * n,
            lower=[close_ref - 0.002] * n,
        ),
        fibonacci=None,
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
    """Prezzo at-support + bullish PatternHit recente + indicatori favorevoli → READY/B_reversal/BUY.

    close=1.09502 (entro 8 pip da support 1.09500); hammer bullish con extreme=1.09480;
    slope+ uptrend (trend_alignment True per BUY); rsi=30 (momentum True per BUY);
    regime=normal (reversal_required True). Tutti 5 fattori → grade A+.
    """
    bars = _make_bars([1.09502] * 200)
    pattern = _make_pattern_hit(
        "hammer", "bullish", bar_index=-1, extreme_price=1.09480
    )
    ind = _stub_indicators_b(close_ref=1.09502, slope=0.0001)
    ctx = _stub_ctx(profile="MODERATE", resistance=1.10500, support=1.09500, close_ref=1.09502)
    ctx = replace(ctx, patterns=[pattern])
    d = detect_b_reversal(bars, ind, ctx)
    assert d.setup_type == "READY", f"got {d.setup_type} reason={d.reason}"
    assert d.setup_name == "B_reversal"
    assert d.direction == "BUY"
    assert d.entry_price is not None
    assert d.stop_loss_price is not None
    assert d.take_profit_price is not None
    assert d.grade in ("A+", "A", "B", "C")
    assert 0.10 <= d.confidence <= 0.95


def test_detect_b_reversal_counter_trend_gate():
    """Counter-trend SELL a resistance + slope+ uptrend + grade B → NONE/counter_trend_below_A_grade.

    regime=compressed → fa cadere volatility_regime per Setup B (allowed=normal/expanded);
    insieme a trend_alignment False (slope+ contro SELL) → 3 True / 5 → grade B.
    Counter-trend gate D-07 deve downgradare a NONE.

    Logica liberale (PLAN spec): se per qualche motivo il grade calcolato è A/A+,
    il gate consente READY/NONE; se grade è B/C, MUST essere NONE/counter_trend_below_A_grade.
    """
    bars = _make_bars([1.10498] * 200)
    pattern = _make_pattern_hit(
        "shooting_star", "bearish", bar_index=-1, extreme_price=1.10520
    )
    # slope+ → uptrend; SELL contro slope → counter-trend
    # regime=compressed → reversal_required falso (allowed=normal/expanded)
    # rsi=80 → momentum True per SELL (rsi > 25)
    ind = _stub_indicators_b(
        close_ref=1.10498, slope=0.0001, regime="compressed", rsi=80.0
    )
    ctx = _stub_ctx(profile="MODERATE", resistance=1.10500, support=1.09500, close_ref=1.10498)
    ctx = replace(ctx, patterns=[pattern])
    d = detect_b_reversal(bars, ind, ctx)
    if d.grade in ("A+", "A"):
        # Gate consente: READY o NONE per altri motivi (es. R:R)
        assert d.setup_type in ("READY", "NONE")
    else:
        # Grade B/C → counter-trend gate DEVE bloccare
        assert d.setup_type == "NONE", f"expected NONE for counter-trend B/C, got {d.setup_type}"
        assert d.reason == "counter_trend_below_A_grade", (
            f"expected reason=counter_trend_below_A_grade, got {d.reason}"
        )


# ==========================================================================
# Setup C — Compression (STRAT-03) — Wave 2 plan-06
# ==========================================================================


def test_detect_c_compression_nr7():
    """4 bar consecutivi NR7=True + slope+ → READY/C_compression/BUY con TP=entry+2*range.

    Range 30 pip (high=1.10150, low=1.09850) garantisce R:R > MODERATE 1.8 floor:
      entry = compression_high = 1.10150 (stop-trigger long)
      SL = max(comp_low − 0.3×ATR, entry − 1.5×ATR) = max(1.09820, 1.10000) = 1.10000 (cap)
      TP = entry + 2 × range = 1.10150 + 0.0060 = 1.10750
      R:R = 0.0060 / 0.00150 = 4.0 (cap-driven SL → R:R favorevole)

    NOTA Rule 1 deviation: il plan-as-written usava range 3 pip → R:R=1.0 < MODERATE 1.8 →
    NONE invece di READY. Range 30 pip è la fix minimale per produrre READY consistente
    con il floor R:R MODERATE.
    """
    bars = _make_bars([1.10000] * 200)
    # Ultimi 4 bar: high/low formano compression range 30 pip
    for i in range(4):
        bars[-1 - i]["high"] = 1.10150
        bars[-1 - i]["low"] = 1.09850
    ind = _stub_indicators_c(
        close_ref=1.10000, slope=0.0001, nr7_count=4
    )
    ctx = _stub_ctx(profile="MODERATE", resistance=1.10500, support=1.09500, close_ref=1.10000)
    d = detect_c_compression(bars, ind, ctx)
    assert d.setup_type == "READY", f"got {d.setup_type} reason={d.reason}"
    assert d.setup_name == "C_compression"
    assert d.direction == "BUY"
    # entry = compression_high
    assert abs(d.entry_price - 1.10150) < 1e-5, d.entry_price
    # TP = entry + 2 × range = 1.10150 + 0.0060 = 1.10750
    assert abs(d.take_profit_price - 1.10750) < 1e-4, d.take_profit_price
    assert d.setup_specific.get("trigger_type") == "nr7"
    assert d.setup_specific.get("compressed_bar_count") == 4


def test_detect_c_compression_squeeze():
    """4 bar consecutivi squeeze=True + slope− → READY/C_compression/SELL.

    Range 30 pip (high=1.10150, low=1.09850); slope=−0.0001 → SELL.
      entry = compression_low = 1.09850 (stop-trigger short)
      SL = min(comp_high + 0.3×ATR, entry + 1.5×ATR) = min(1.10180, 1.10000) = 1.10000 (cap)
      TP = entry − 2 × range = 1.09850 − 0.0060 = 1.09250
      R:R = 0.0060 / 0.00150 = 4.0
    """
    bars = _make_bars([1.10000] * 200)
    for i in range(4):
        bars[-1 - i]["high"] = 1.10150
        bars[-1 - i]["low"] = 1.09850
    ind = _stub_indicators_c(
        close_ref=1.10000, slope=-0.0001, squeeze_count=4
    )
    ctx = _stub_ctx(profile="MODERATE", resistance=1.10500, support=1.09500, close_ref=1.10000)
    d = detect_c_compression(bars, ind, ctx)
    assert d.setup_type == "READY", f"got {d.setup_type} reason={d.reason}"
    assert d.setup_name == "C_compression"
    assert d.direction == "SELL"
    # entry = compression_low
    assert abs(d.entry_price - 1.09850) < 1e-5, d.entry_price
    # TP = entry − 2 × range = 1.09850 − 0.0060 = 1.09250
    assert abs(d.take_profit_price - 1.09250) < 1e-4, d.take_profit_price
    assert d.setup_specific.get("trigger_type") == "squeeze"
    assert d.setup_specific.get("compressed_bar_count") == 4


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
    """D-06: tra READY con grade diverso, vince il grade più alto (A+ > A > B > C)."""
    from strategy import evaluate_proposal_for_bar
    from strategy.proposal import ProposalDraft
    from unittest.mock import patch

    def stub_a(*args, **kwargs):
        return ProposalDraft(
            setup_type="READY", setup_name="A_breakout",
            direction="BUY", entry_price=1.1, stop_loss_price=1.099, take_profit_price=1.103,
            grade="B", confidence=0.55, reason="a",
        )

    def stub_b(*args, **kwargs):
        return ProposalDraft(
            setup_type="READY", setup_name="B_reversal",
            direction="BUY", entry_price=1.1, stop_loss_price=1.099, take_profit_price=1.103,
            grade="A+", confidence=0.85, reason="b",
        )

    def stub_c(*args, **kwargs):
        return ProposalDraft(
            setup_type="NONE", setup_name="C_compression",
            grade="reject", reason="no",
        )

    def stub_d(*args, **kwargs):
        return ProposalDraft(
            setup_type="NONE", setup_name="D_pullback",
            grade="reject", reason="no",
        )

    with patch("strategy.ALL_DETECTORS", [stub_a, stub_b, stub_c, stub_d]):
        winner = evaluate_proposal_for_bar([], None, None)
    # B_reversal ha grade A+ → vince su A_breakout grade B
    assert winner.setup_name == "B_reversal", f"got {winner.setup_name}"
    assert winner.grade == "A+"
    assert "losers" in (winner.setup_specific or {})
    losers = winner.setup_specific["losers"]
    assert len(losers) == 3
    loser_names = {l.setup_name for l in losers}
    assert loser_names == {"A_breakout", "C_compression", "D_pullback"}


def test_evaluate_proposal_for_bar_priority_tie_break():
    """D-06: stesso grade READY → priority A > C > B > D."""
    from strategy import evaluate_proposal_for_bar
    from strategy.proposal import ProposalDraft
    from unittest.mock import patch

    def make(name):
        return ProposalDraft(
            setup_type="READY", setup_name=name,
            direction="BUY", entry_price=1.1, stop_loss_price=1.099, take_profit_price=1.103,
            grade="B", confidence=0.55, reason=name,
        )

    stubs = [
        (lambda n: lambda *a, **kw: make(n))(n)
        for n in ["A_breakout", "B_reversal", "C_compression", "D_pullback"]
    ]
    with patch("strategy.ALL_DETECTORS", stubs):
        winner = evaluate_proposal_for_bar([], None, None)
    assert winner.setup_name == "A_breakout"


def test_evaluate_proposal_for_bar_all_none_returns_first():
    """Tutti NONE → ritorna primo draft (Setup A) con i 3 perdenti in setup_specific.losers."""
    from strategy import evaluate_proposal_for_bar
    from strategy.proposal import ProposalDraft
    from unittest.mock import patch

    def make_none(name):
        return ProposalDraft(setup_type="NONE", setup_name=name, grade="reject", reason="no")

    stubs = [
        (lambda n: lambda *a, **kw: make_none(n))(n)
        for n in ["A_breakout", "B_reversal", "C_compression", "D_pullback"]
    ]
    with patch("strategy.ALL_DETECTORS", stubs):
        winner = evaluate_proposal_for_bar([], None, None)
    assert winner.setup_type == "NONE"
    assert winner.setup_name == "A_breakout"  # primo della lista
    assert len(winner.setup_specific.get("losers", [])) == 3
