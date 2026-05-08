"""Test confluence scorer + grade + confidence (STRAT-05, STRAT-06). Mock-free, hand-calc."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from strategy.confluence import (
    compute_confidence,
    grade_for,
    load_strategy_config,
    score_factors,
)
from strategy.context import StrategyContext


# --- Fixtures puri (no MagicMock) -----------------------------------------


def _stub_indicators(
    ema50_slope=1.0,
    rsi_14=55.0,
    atr_14=0.0010,
    closing_score=80.0,
    volatility_regime="expanded",
    nr7=False,
    nr4=False,
    squeeze=False,
):
    """Costruisce uno snapshot ExtendedIndicators-like con liste di un solo elemento."""
    return SimpleNamespace(
        ema50_slope=[ema50_slope],
        rsi_14=[rsi_14],
        atr_14=[atr_14],
        closing_score=[closing_score],
        volatility_regime=[volatility_regime],
        nr_detect=SimpleNamespace(nr7=[nr7], nr4=[nr4]),
        bollinger_bands=SimpleNamespace(squeeze=[squeeze]),
    )


def _stub_ctx(
    spread_pips_current=1.0,
    spread_baseline_pips=2.0,
    recent_trades=None,
    intermarket_fn=None,
    news_fn=None,
):
    """StrategyContext sintetico: bid/ask coerenti con spread_pips_current."""
    pip = 0.0001
    bid = 1.10000
    ask = bid + spread_pips_current * pip
    sym = SimpleNamespace(bid=bid, ask=ask, point=0.00001, digits=5)
    return StrategyContext(
        symbol="EURUSD",
        timeframe="M15",
        profile="MODERATE",
        sr={"resistance": 1.10500, "support": 1.09500},
        regime="normal",
        patterns=[],
        symbol_info=sym,
        pip_size=pip,
        intermarket_score_fn=intermarket_fn,
        news_blackout_fn=news_fn,
        recent_trades=recent_trades or [],
        spread_baseline_pips=spread_baseline_pips,
    )


# --- grade_for ------------------------------------------------------------


def test_grade_for_5_factors_gives_Aplus():
    assert grade_for({"a": True, "b": True, "c": True, "d": True, "e": True}) == "A+"


def test_grade_for_2_factors_gives_C():
    assert grade_for({"a": True, "b": True, "c": False, "d": False, "e": False}) == "C"


def test_grade_for_1_factor_gives_reject():
    assert (
        grade_for({"a": True, "b": False, "c": False, "d": False, "e": False})
        == "reject"
    )


# --- score_factors --------------------------------------------------------


def test_score_factors_all_true():
    """Setup A_breakout BUY con tutti i 5 fattori favorevoli."""
    ind = _stub_indicators(
        ema50_slope=1.5,
        rsi_14=55,
        atr_14=0.0010,
        closing_score=85,
        volatility_regime="expanded",
    )
    # spread/atr = 0.0001/0.001 = 0.10 < 0.20 ✓
    ctx = _stub_ctx(spread_pips_current=1.0)
    f = score_factors("A_breakout", ind, ctx, "BUY")
    assert f == {
        "trend_alignment": True,
        "setup_pattern": True,
        "momentum": True,
        "volatility_regime": True,
        "spread_session": True,
    }, f


# --- compute_confidence ---------------------------------------------------


def test_confidence_Aplus_base_no_adjusters():
    """A+ base 0.85, nessun adjuster fires → 0.85 esatto."""
    # spread = baseline (no tighter); no recent_trades; no intermarket; no news
    ctx = _stub_ctx(spread_pips_current=2.0, spread_baseline_pips=2.0)
    c = compute_confidence("A+", ctx, "A_breakout")
    assert abs(c - 0.85) < 1e-9, c


def test_confidence_adjusters():
    """Solo intermarket positivo → +0.05 → B base 0.55 + 0.05 = 0.60."""
    ctx = _stub_ctx(
        spread_pips_current=2.0,
        spread_baseline_pips=2.0,
        intermarket_fn=lambda sym: 0.5,
    )
    c = compute_confidence("B", ctx, "A_breakout")
    assert abs(c - 0.60) < 1e-9, c


def test_confidence_clamped_at_max():
    """A+ 0.85 + intermarket+spread+win = +0.15 → 1.00 clampato a 0.95."""
    ind = _stub_indicators()

    @dataclass
    class T:
        outcome: str

    ctx = _stub_ctx(
        spread_pips_current=1.0,
        spread_baseline_pips=3.0,  # current 1 < baseline 3 → tighter +0.05
        intermarket_fn=lambda sym: 1.0,  # +0.05
        recent_trades=[T("WIN")],  # +0.05
    )
    c = compute_confidence("A+", ctx, "A_breakout", indicators=ind)
    assert c == 0.95, c


def test_confidence_clamped_at_min():
    """C base 0.40 - news - 2lost - against_trend = 0.25 (no clamp; sopra 0.10)."""

    @dataclass
    class T:
        outcome: str

    ctx = _stub_ctx(
        spread_pips_current=3.0,
        spread_baseline_pips=2.0,  # NOT tighter
        news_fn=lambda dt: True,  # -0.05
        recent_trades=[T("LOSS"), T("LOSS")],  # -0.05
    )
    factors = {
        "trend_alignment": False,
        "setup_pattern": True,
        "momentum": True,
        "volatility_regime": True,
        "spread_session": True,
    }
    c = compute_confidence("C", ctx, "A_breakout", factors=factors)
    # 0.40 - 0.05 (news) - 0.05 (last 2 lost) - 0.05 (against trend) = 0.25
    assert abs(c - 0.25) < 1e-9, c


# --- load_strategy_config -------------------------------------------------


def test_load_strategy_config_default():
    """Default load: schema D-08 esposto correttamente."""
    cfg = load_strategy_config()
    assert "CONSERVATIVE" in cfg.profile_filters
    assert cfg.bounds["min_confidence"] == 0.10
    assert cfg.bounds["max_confidence"] == 0.95


def test_load_strategy_config_env_override(tmp_path, monkeypatch):
    """STRATEGY_CONFIG_PATH override: lru_cache per path-string, no pollution."""
    alt = tmp_path / "alt_strategy.yaml"
    alt.write_text(
        "factors:\n"
        "  trend_alignment: {use_ema50_slope: true, counter_trend_allowed_grades: [\"A+\"]}\n"
        "  setup_pattern: {half_formed_rejected: true}\n"
        "  momentum: {rsi_neutral_band: [40, 60], divergence_required_for_reversal: true}\n"
        "  volatility_regime:\n"
        "    breakout_required: [\"normal\"]\n"
        "    compression_required: [\"compressed\"]\n"
        "    reversal_required: [\"normal\"]\n"
        "    pullback_required: [\"normal\"]\n"
        "  spread_session: {max_spread_atr_ratio: 0.10, optional_session_bonus: 0.0}\n"
        "grade_map: {\"A+\": 5, \"A\": 4, \"B\": 3, \"C\": 2, \"reject\": 1}\n"
        "base_confidence: {\"A+\": 0.99, \"A\": 0.70, \"B\": 0.55, \"C\": 0.40}\n"
        "adjusters:\n"
        "  intermarket_confirmation: 0.05\n"
        "  recent_winning_trade_same_pair: 0.05\n"
        "  spread_tighter_than_baseline: 0.05\n"
        "  macro_event_within_60min: -0.05\n"
        "  last_2_trades_lost_same_pair: -0.05\n"
        "  proposing_against_medium_term_trend: -0.05\n"
        "bounds: {min_confidence: 0.05, max_confidence: 0.99}\n"
        "profile_filters:\n"
        "  CONSERVATIVE: {min_grade: \"A\", min_rr: 2.5, min_confidence: 0.65}\n"
        "  MODERATE: {min_grade: \"B\", min_rr: 1.8, min_confidence: 0.50}\n"
        "  AGGRESSIVE: {min_grade: \"C\", min_rr: 1.3, min_confidence: 0.40}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("STRATEGY_CONFIG_PATH", str(alt))
    # bypass cache: il loader usa lru_cache su path_str, alt è path nuovo → cache miss
    cfg = load_strategy_config()
    assert cfg.base_confidence["A+"] == 0.99, cfg.base_confidence
    assert cfg.bounds["min_confidence"] == 0.05
